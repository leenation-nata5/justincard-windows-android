plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "org.yugioh.kartenliste"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.yugioh.kartenliste.yugiohkartenliste"
        minSdk = 24
        targetSdk = 35
        versionCode = 14100
        versionName = "14.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
    }

    signingConfigs {
        create("ciTest") {
            storeFile = rootProject.file("ci/justincard-ci-test.keystore")
            storePassword = "justincard-ci"
            keyAlias = "justincard-ci"
            keyPassword = "justincard-ci"
        }
        val releaseKeystore = System.getenv("ANDROID_KEYSTORE_PATH")
        val releaseStorePass = System.getenv("ANDROID_KEYSTORE_PASSWORD")
        val releaseAlias = System.getenv("ANDROID_KEY_ALIAS")
        val releaseKeyPass = System.getenv("ANDROID_KEY_PASSWORD")
        if (!releaseKeystore.isNullOrBlank() && !releaseStorePass.isNullOrBlank() &&
            !releaseAlias.isNullOrBlank() && !releaseKeyPass.isNullOrBlank()) {
            create("production") {
                storeFile = file(releaseKeystore)
                storePassword = releaseStorePass
                keyAlias = releaseAlias
                keyPassword = releaseKeyPass
            }
        }
    }

    flavorDimensions += "channel"
    productFlavors {
        create("ci") {
            dimension = "channel"
            applicationIdSuffix = ".ci"
            versionNameSuffix = "-ci"
            signingConfig = signingConfigs.getByName("ciTest")
        }
        create("prod") {
            dimension = "channel"
            signingConfig = signingConfigs.findByName("production") ?: signingConfigs.getByName("ciTest")
        }
    }

    buildTypes {
        debug {
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources.excludes += setOf(
            "META-INF/DEPENDENCIES",
            "META-INF/LICENSE*",
            "META-INF/NOTICE*"
        )
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")

    implementation("androidx.compose.ui:ui:1.10.3")
    implementation("androidx.compose.ui:ui-tooling-preview:1.10.3")
    implementation("androidx.compose.foundation:foundation:1.10.3")
    implementation("androidx.compose.material3:material3:1.4.0")
    implementation("androidx.compose.material:material-icons-extended:1.7.8")
    debugImplementation("androidx.compose.ui:ui-tooling:1.10.3")

    implementation("androidx.camera:camera-core:1.5.3")
    implementation("androidx.camera:camera-camera2:1.5.3")
    implementation("androidx.camera:camera-lifecycle:1.5.3")
    implementation("androidx.camera:camera-view:1.5.3")

    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    implementation("com.google.mlkit:text-recognition-japanese:16.0.1")
    implementation("com.google.mlkit:text-recognition-korean:16.0.1")
    implementation("com.google.mlkit:text-recognition-devanagari:16.0.1")

    implementation("com.google.android.gms:play-services-auth:22.0.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.code.gson:gson:2.11.0")
    implementation("io.coil-kt:coil-compose:2.7.0")

    testImplementation("junit:junit:4.13.2")
}
