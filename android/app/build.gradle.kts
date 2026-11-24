plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "dev.nexus.assistant"
    compileSdk = 35
    defaultConfig {
        applicationId = "dev.nexus.assistant"
        minSdk = 28
        targetSdk = 35
        versionCode = 7
        versionName = "0.5.0"
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
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material3:material3-window-size-class")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    if (rootProject.file("libs/tsbridge.aar").exists()) implementation(files(rootProject.file("libs/tsbridge.aar")))
    implementation("com.google.android.gms:play-services-wearable:19.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.9.0")
}
