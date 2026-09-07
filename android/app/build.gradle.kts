plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val releaseStoreFile = providers.environmentVariable("JIC_KEYSTORE_FILE").orNull

android {
    namespace = "org.yugioh.kartenliste"
    // API 36 is a stable platform on the hosted GitHub Actions runners.
    // Avoid the Android 17/API 37 preview platform in CI.
    compileSdk = 36

    defaultConfig {
        applicationId = "org.yugioh.kartenliste.yugiohkartenliste"
        minSdk = 24
        targetSdk = 36
        versionCode = 13002
        versionName = "13.0.2"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
        buildConfigField("String", "CATALOG_API_BASE", "\"https://db.ygoprodeck.com/api/v7/\"")
        buildConfigField("String", "GOOGLE_DRIVE_API_BASE", "\"https://www.googleapis.com/drive/v3/\"")
        buildConfigField("String", "GOOGLE_DRIVE_UPLOAD_BASE", "\"https://www.googleapis.com/upload/drive/v3/\"")
        buildConfigField("String", "GOOGLE_SHEETS_API_BASE", "\"https://sheets.googleapis.com/v4/\"")
    }

    signingConfigs {
        create("ciTest") {
            storeFile = rootProject.file("ci/justincard-ci-test.keystore")
            storePassword = "justincard-ci"
            keyAlias = "justincard-ci"
            keyPassword = "justincard-ci"
        }
        create("release") {
            if (!releaseStoreFile.isNullOrBlank()) {
                storeFile = file(releaseStoreFile)
                storePassword = providers.environmentVariable("JIC_KEYSTORE_PASSWORD").orNull
                keyAlias = providers.environmentVariable("JIC_KEY_ALIAS").orNull
                keyPassword = providers.environmentVariable("JIC_KEY_PASSWORD").orNull
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
                enableV4Signing = true
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            if (!releaseStoreFile.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
        create("ciRelease") {
            // Jeder GitHub-Lauf kann damit auch ohne private Produktions-Secrets
            // einen installierbaren, optimierten Release-Build prüfen. Die eigene
            // Paket-ID verhindert Signaturkonflikte mit der echten Release-App.
            initWith(getByName("release"))
            applicationIdSuffix = ".ci"
            versionNameSuffix = "-ci-release"
            signingConfig = signingConfigs.getByName("ciTest")
            matchingFallbacks += listOf("release")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources.excludes += setOf(
            "META-INF/AL2.0",
            "META-INF/LGPL2.1",
            "META-INF/DEPENDENCIES",
            "META-INF/LICENSE*",
            "META-INF/NOTICE*",
        )
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

dependencies {
    // Compose BOM 2026.02.00 is published in Google Maven and resolved to the
    // API-36-compatible Compose 1.10.3 line in the GitHub CI log. Do not use 2026.04.00: that
    // coordinate does not exist. Newer Compose 1.12.x requires compileSdk 37.
    val composeBom = enforcedPlatform("androidx.compose:compose-bom:2026.02.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    // Enforce the Coil BOM as well as the requested modules. A normal version
    // request may be upgraded during conflict resolution; the enforced BOM keeps
    // every Coil target module (including the Android variants) on API-36-safe 3.5.0.
    val coilBom = enforcedPlatform("io.coil-kt.coil3:coil-bom:3.5.0")
    implementation(coilBom)
    implementation("io.coil-kt.coil3:coil-compose")
    implementation("io.coil-kt.coil3:coil-network-okhttp")

    val cameraX = "1.5.3"
    implementation("androidx.camera:camera-core:$cameraX")
    implementation("androidx.camera:camera-camera2:$cameraX")
    implementation("androidx.camera:camera-lifecycle:$cameraX")
    implementation("androidx.camera:camera-view:$cameraX")

    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    implementation("com.google.mlkit:text-recognition-devanagari:16.0.1")
    implementation("com.google.mlkit:text-recognition-japanese:16.0.1")
    implementation("com.google.mlkit:text-recognition-korean:16.0.1")
    implementation("com.google.android.gms:play-services-auth:22.0.0")
    implementation("androidx.exifinterface:exifinterface:1.4.2")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
