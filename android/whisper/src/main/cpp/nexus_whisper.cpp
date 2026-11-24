// NEXUS: ponte JNI verso whisper.cpp, solo per frasi brevi (sentire il nome dell'agente).
#include <jni.h>
#include <android/log.h>
#include <algorithm>
#include <mutex>
#include <string>
#include "whisper.h"

#define TAG "NexusWhisper"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

static std::mutex g_mu;
static whisper_context * g_ctx = nullptr;

static std::string jstr(JNIEnv * env, jstring s) {
    if (!s) return "";
    const char * c = env->GetStringUTFChars(s, nullptr);
    std::string out(c);
    env->ReleaseStringUTFChars(s, c);
    return out;
}

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

extern "C" JNIEXPORT jboolean JNICALL
Java_dev_nexus_whisper_WhisperNative_load(JNIEnv * env, jobject, jstring path) {
    std::lock_guard<std::mutex> lk(g_mu);
    if (g_ctx) { whisper_free(g_ctx); g_ctx = nullptr; }
    auto cp = whisper_context_default_params();
    cp.use_gpu = false;
    g_ctx = whisper_init_from_file_with_params(jstr(env, path).c_str(), cp);
    LOGI("modello %s", g_ctx ? "caricato" : "NON caricato");
    return g_ctx != nullptr;
}

extern "C" JNIEXPORT void JNICALL
Java_dev_nexus_whisper_WhisperNative_free(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lk(g_mu);
    if (g_ctx) { whisper_free(g_ctx); g_ctx = nullptr; }
}

// pcm: audio 16 kHz mono in [-1, 1]. prompt: suggerimento (es. "Ehi Marco.") perché scriva bene il nome.
extern "C" JNIEXPORT jstring JNICALL
Java_dev_nexus_whisper_WhisperNative_transcribe(JNIEnv * env, jobject, jfloatArray pcm, jstring lang, jstring prompt, jint threads) {
    std::lock_guard<std::mutex> lk(g_mu);
    if (!g_ctx) return jnew(env, "");
    jsize n = env->GetArrayLength(pcm);
    jfloat * data = env->GetFloatArrayElements(pcm, nullptr);
    std::string l = jstr(env, lang), p = jstr(env, prompt);
    auto wp = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    wp.n_threads = threads;
    wp.language = l.c_str();
    wp.initial_prompt = p.empty() ? nullptr : p.c_str();
    wp.translate = false;
    wp.no_context = true;
    wp.no_timestamps = true;
    wp.single_segment = true;
    wp.print_progress = false;
    wp.print_realtime = false;
    wp.print_timestamps = false;
    wp.print_special = false;
    wp.suppress_blank = true;
    // contesto audio ridotto alla durata vera (+ margine): molto più veloce per frasi di pochi secondi
    double secs = n / 16000.0;
    wp.audio_ctx = std::min(1500, (int) (secs * 50) + 128);
    std::string out;
    if (whisper_full(g_ctx, wp, data, n) == 0) {
        int ns = whisper_full_n_segments(g_ctx);
        for (int i = 0; i < ns; i++) out += whisper_full_get_segment_text(g_ctx, i);
    }
    env->ReleaseFloatArrayElements(pcm, data, JNI_ABORT);
    return jnew(env, out);
}
