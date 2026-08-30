plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }

android { namespace = "com.alanshum.pixelminimal.bridge"; compileSdk = 35
    defaultConfig { applicationId = "com.alanshum.pixelminimal.bridge"; minSdk = 34; targetSdk = 34; versionCode = 1; versionName = "1.0" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    lint { disable += "WearableBindListener" }
}
kotlin { jvmToolchain(17) }
dependencies {
    implementation(project(":shared-protocol"))
    implementation("com.google.android.gms:play-services-wearable:18.2.0")
    implementation("androidx.wear.watchface:watchface-complications-data-source:1.2.1")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
