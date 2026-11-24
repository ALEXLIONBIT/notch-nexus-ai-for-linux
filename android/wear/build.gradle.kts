plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "dev.nexus.assistant.wear"
    compileSdk = 35
    ndkVersion = "29.0.14206865"   // serve per togliere i simboli di debug dalle librerie native
    defaultConfig {
        // stesso applicationId e stessa firma dell'app del telefono: serve per ricevere le impostazioni (Data Layer)
        applicationId = "dev.nexus.assistant"
        minSdk = 30            // Wear OS 3 e successivi (Galaxy Watch 4+, Pixel Watch, …)
        targetSdk = 34
        versionCode = 100007
        versionName = "0.2.2"
    }
    // firma delle release: ~/.android/nexus-release.keystore (fuori dal repo). Stessa chiave per telefono e orologio,
    // altrimenti gli aggiornamenti non si installano e l'orologio non riceve le impostazioni dal telefono.
    val nexusKey = file(System.getProperty("user.home") + "/.android/nexus-release.keystore")
    signingConfigs {
        create("nexus") {
            storeFile = nexusKey
            storePassword = "android"; keyAlias = "androiddebugkey"; keyPassword = "android"
        }
    }
    buildTypes {
        release {
            // R8 toglie il codice che non serve (soprattutto le icone): APK molto più leggero
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // solo le architetture dei dispositivi veri (NEXUS_ABI_ALL=1 per includere anche l'emulatore x86_64)
            if (System.getenv("NEXUS_ABI_ALL") == null) ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
            signingConfig = if (nexusKey.exists()) signingConfigs.getByName("nexus") else signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    // librerie native compresse dentro l'APK (Tailscale pesa ~30 MB non compresso): download e spazio molto minori
    packaging { jniLibs { useLegacyPackaging = true } }
    buildFeatures { compose = true }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.wear.compose:compose-material:1.4.0")
    implementation("androidx.wear.compose:compose-foundation:1.4.0")
    implementation("androidx.wear.compose:compose-navigation:1.4.0")
    implementation("androidx.wear:wear-remote-interactions:1.1.0")
    implementation("androidx.wear:wear-input:1.2.0")
    implementation("com.google.android.gms:play-services-wearable:19.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-guava:1.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation(project(":llama"))
    if (rootProject.file("libs/tsbridge.aar").exists()) implementation(files(rootProject.file("libs/tsbridge.aar")))
    implementation("com.google.zxing:core:3.5.3")
}
