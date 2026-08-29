plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }

android { namespace = "com.alanshum.pixelminimal.bridge"; compileSdk = 35
    defaultConfig { applicationId = "com.alanshum.pixelminimal.bridge"; minSdk = 34; targetSdk = 34; versionCode = 1; versionName = "1.0" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
kotlin { jvmToolchain(17) }
dependencies {
    implementation(project(":shared-protocol"))
    implementation("com.google.android.gms:play-services-wearable:18.2.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.8.1")
}
