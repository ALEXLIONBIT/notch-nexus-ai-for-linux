// whisper.cpp per il telefono: sentire il nome dell'agente (vedi src/main/cpp).
// NEXUS_NATIVE_BUILD=/percorso  sposta i file di compilazione C++ (sono tanti) su un altro disco.
// NEXUS_WHISPER_SRC=/percorso   usa un sorgente di whisper.cpp già scaricato invece di scaricarlo.
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

val nativeBuild = System.getenv("NEXUS_NATIVE_BUILD")
if (nativeBuild != null) layout.buildDirectory.set(file("$nativeBuild/whisper-gradle"))

android {
    namespace = "dev.nexus.whisper"
    compileSdk = 35
    ndkVersion = "29.0.14206865"

    defaultConfig {
        minSdk = 28
        consumerProguardFiles("consumer-rules.pro")
        ndk {
            abiFilters += if (System.getenv("NEXUS_ABI_ALL") != null) listOf("arm64-v8a", "armeabi-v7a", "x86_64") else listOf("arm64-v8a", "armeabi-v7a")
        }
        externalNativeBuild {
            cmake {
                arguments += listOf("-DCMAKE_BUILD_TYPE=Release", "-DANDROID_STL=c++_shared")
                System.getenv("NEXUS_WHISPER_SRC")?.let { arguments += "-DFETCHCONTENT_SOURCE_DIR_WHISPER=$it" }
            }
        }
    }
    externalNativeBuild {
        cmake {
            path("src/main/cpp/CMakeLists.txt")
            version = "3.22.1+"
            if (nativeBuild != null) buildStagingDirectory = file("$nativeBuild/whisper-cxx")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
