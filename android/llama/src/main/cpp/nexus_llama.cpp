// NEXUS: ponte JNI verso llama.cpp. Un modello alla volta; la cache della conversazione viene riusata
// (il prompt di sistema con gli strumenti non si ricalcola a ogni domanda: sull'orologio fa la differenza).
#include <jni.h>
#include <android/log.h>

#include <algorithm>
#include <chrono>
#include <atomic>
#include <mutex>
#include <string>
#include <vector>

#include "chat.h"
#include "common.h"
#include "llama.h"
#include "sampling.h"

#define TAG "NexusLlama"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

static std::mutex g_mu;
static llama_model * g_model = nullptr;
static llama_context * g_ctx = nullptr;
static common_chat_templates_ptr g_tmpls;
static std::vector<llama_token> g_cached;     // token già nella cache KV
static std::atomic<bool> g_cancel{false};

static std::string jstr(JNIEnv * env, jstring s) {
    if (!s) return "";
    const char * c = env->GetStringUTFChars(s, nullptr);
    std::string out(c);
    env->ReleaseStringUTFChars(s, c);
    return out;
}

// String Java dai byte UTF-8 (NewStringUTF va in crash con emoji e caratteri spezzati)
static jstring jnew(JNIEnv * env, const std::string & s) {
    jbyteArray arr = env->NewByteArray((jsize) s.size());
    env->SetByteArrayRegion(arr, 0, (jsize) s.size(), reinterpret_cast<const jbyte *>(s.data()));
    jclass cls = env->FindClass("java/lang/String");
    jmethodID ctor = env->GetMethodID(cls, "<init>", "([BLjava/lang/String;)V");
    jstring cs = env->NewStringUTF("UTF-8");
    auto out = (jstring) env->NewObject(cls, ctor, arr, cs);
    env->DeleteLocalRef(arr); env->DeleteLocalRef(cs); env->DeleteLocalRef(cls);
    return out;
}

// lunghezza della parte di s fatta di caratteri UTF-8 completi
static size_t utf8_complete(const std::string & s) {
    size_t n = s.size(), i = n;
    int back = 0;
    while (i > 0 && back < 4) {
        unsigned char c = (unsigned char) s[i - 1];
        if ((c & 0xC0) != 0x80) {                     // primo byte di un carattere
            int need = (c & 0x80) == 0 ? 1 : (c & 0xE0) == 0xC0 ? 2 : (c & 0xF0) == 0xE0 ? 3 : 4;
            return (back + 1 >= need) ? n : i - 1;
        }
        i--; back++;
    }
    return n;
}

static void free_all() {
    g_tmpls.reset();
    if (g_ctx) { llama_free(g_ctx); g_ctx = nullptr; }
    if (g_model) { llama_model_free(g_model); g_model = nullptr; }
    g_cached.clear();
}

extern "C" JNIEXPORT void JNICALL
Java_dev_nexus_llama_LlamaNative_init(JNIEnv * env, jobject, jstring libDir) {
    std::string dir = jstr(env, libDir);
    ggml_backend_load_all_from_path(dir.c_str());     // sceglie la variante della CPU giusta
    llama_backend_init();
    LOGI("backend pronto (%s)", dir.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_nexus_llama_LlamaNative_load(JNIEnv * env, jobject, jstring path, jint nCtx, jint nThreads) {
    std::lock_guard<std::mutex> lk(g_mu);
    free_all();
    auto mp = llama_model_default_params();
    g_model = llama_model_load_from_file(jstr(env, path).c_str(), mp);
    if (!g_model) return env->NewStringUTF("modello non caricato (file rovinato o formato non supportato)");
    auto cp = llama_context_default_params();
    cp.n_ctx = nCtx;
    cp.n_batch = 512;
    cp.n_ubatch = 512;
    cp.n_threads = nThreads;
    cp.n_threads_batch = nThreads;
    g_ctx = llama_init_from_model(g_model, cp);
    if (!g_ctx) { free_all(); return env->NewStringUTF("memoria insufficiente per questo modello"); }
    try {
        g_tmpls = common_chat_templates_init(g_model, "");
    } catch (const std::exception & e) {
        LOGE("template: %s", e.what());
        free_all();
        return jnew(env, std::string("template della chat non supportato: ") + e.what());
    }
    LOGI("modello caricato: ctx %d, %d thread", nCtx, nThreads);
    return env->NewStringUTF("");
}

extern "C" JNIEXPORT void JNICALL
Java_dev_nexus_llama_LlamaNative_unload(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lk(g_mu);
    free_all();
}

extern "C" JNIEXPORT void JNICALL
Java_dev_nexus_llama_LlamaNative_cancel(JNIEnv *, jobject) { g_cancel = true; }

// valuta i token nuovi a partire dalla parte in comune con la cache
static bool eval_prompt(const std::vector<llama_token> & toks) {
    size_t n = 0;
    while (n < g_cached.size() && n < toks.size() && g_cached[n] == toks[n]) n++;
    if (n == toks.size() && n > 0) n--;                    // serve almeno un token da valutare per avere i logit
    llama_memory_seq_rm(llama_get_memory(g_ctx), 0, (llama_pos) n, -1);
    g_cached.resize(n);
    const int nb = 512;
    for (size_t i = n; i < toks.size(); i += nb) {
        if (g_cancel) return false;
        int len = (int) std::min((size_t) nb, toks.size() - i);
        llama_batch b = llama_batch_get_one(const_cast<llama_token *>(toks.data() + i), len);
        if (llama_decode(g_ctx, b) != 0) return false;
        g_cached.insert(g_cached.end(), toks.begin() + i, toks.begin() + i + len);
    }
    return true;
}

// messages/tools in formato OpenAI (JSON). Ritorna il messaggio dell'assistente in formato OpenAI (JSON),
// oppure {"error": "..."}; onToken(String): Boolean riceve il testo man mano (false = interrompi).
extern "C" JNIEXPORT jstring JNICALL
Java_dev_nexus_llama_LlamaNative_chat(JNIEnv * env, jobject, jstring messagesJson, jstring toolsJson,
                                      jint maxTokens, jfloat temp, jboolean thinking, jobject listener) {
    std::lock_guard<std::mutex> lk(g_mu);
    g_cancel = false;
    auto err = [&](const std::string & e) {
        common_json j = {{"error", e}};
        return jnew(env, j.dump());
    };
    if (!g_model || !g_ctx) return err("nessun modello caricato");
    jmethodID onToken = nullptr;
    if (listener) onToken = env->GetMethodID(env->GetObjectClass(listener), "onToken", "(Ljava/lang/String;)Z");
    try {
        const llama_vocab * vocab = llama_model_get_vocab(g_model);
        common_chat_templates_inputs in;
        in.messages = common_chat_msgs_parse_oaicompat(common_json::parse(jstr(env, messagesJson)));
        std::string tj = jstr(env, toolsJson);
        if (!tj.empty() && tj != "[]") in.tools = common_chat_tools_parse_oaicompat(common_json::parse(tj));
        in.use_jinja = true;
        in.add_generation_prompt = true;
        in.enable_thinking = thinking;
        in.reasoning_format = COMMON_REASONING_FORMAT_AUTO;
        common_chat_session session(g_tmpls.get(), vocab, in);

        // prompt → token (il testo scritto dall'utente non deve diventare token speciali)
        std::vector<llama_token> toks;
        bool first = true;
        for (const auto & part : session.prompt().parts) {
            auto t = common_tokenize(vocab, part.text, first, !part.is_input);
            first = false;
            toks.insert(toks.end(), t.begin(), t.end());
        }
        const int n_ctx = (int) llama_n_ctx(g_ctx);
        if ((int) toks.size() + 16 >= n_ctx) return err("conversazione troppo lunga per questo modello");
        size_t reused = 0;
        while (reused < g_cached.size() && reused < toks.size() && g_cached[reused] == toks[reused]) reused++;
        auto t0 = std::chrono::steady_clock::now();
        if (!eval_prompt(toks)) return err(g_cancel ? "interrotto" : "errore nel calcolo del prompt");
        auto t1 = std::chrono::steady_clock::now();
        int n_gen = 0;

        common_params_sampling sp;
        sp.temp = temp;
        sp.top_k = 40;
        sp.top_p = 0.9f;
        session.apply_sampling(sp);
        common_sampler * smp = common_sampler_init(g_model, sp);
        if (!smp) return err("campionatore non creato");

        common_chat_input out;
        std::string text, pending;
        const auto & stops = session.additional_stops();
        int limit = std::min((int) maxTokens, n_ctx - (int) toks.size() - 4);
        for (int i = 0; i < limit && !g_cancel; i++) {
            llama_token tok = common_sampler_sample(smp, g_ctx, -1);
            common_sampler_accept(smp, tok, true);
            if (llama_vocab_is_eog(vocab, tok)) break;
            n_gen++;
            std::string piece = common_token_to_piece(g_ctx, tok);
            out.append(piece, tok);
            text += piece;
            pending += piece;
            size_t ok = utf8_complete(pending);
            if (onToken && ok > 0) {
                jstring js = jnew(env, pending.substr(0, ok));
                jboolean go = env->CallBooleanMethod(listener, onToken, js);
                env->DeleteLocalRef(js);
                if (!go) g_cancel = true;
            }
            pending.erase(0, ok);
            bool stop = false;
            for (const auto & s : stops) if (!s.empty() && text.size() >= s.size() && text.compare(text.size() - s.size(), s.size(), s) == 0) stop = true;
            llama_batch b = llama_batch_get_one(&tok, 1);
            if (llama_decode(g_ctx, b) != 0) break;
            g_cached.push_back(tok);
            if (stop) break;
        }
        common_sampler_free(smp);
        auto t2 = std::chrono::steady_clock::now();
        double ep = std::chrono::duration<double>(t1 - t0).count(), eg = std::chrono::duration<double>(t2 - t1).count();
        LOGI("prompt %zu token (%zu riusati) in %.1f s (%.1f t/s) · risposta %d token in %.1f s (%.1f t/s)",
             toks.size(), reused, ep, (toks.size() - reused) / std::max(ep, 0.001), n_gen, eg, n_gen / std::max(eg, 0.001));
        const common_chat_msg & msg = session.finish(out);
        return jnew(env, msg.to_json_oaicompat().dump());
    } catch (const std::exception & e) {
        LOGE("chat: %s", e.what());
        g_cached.clear();
        llama_memory_clear(llama_get_memory(g_ctx), true);
        return err(e.what());
    }
}
