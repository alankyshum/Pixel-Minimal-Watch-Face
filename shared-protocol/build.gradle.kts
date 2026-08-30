plugins { id("com.android.library"); id("org.jetbrains.kotlin.android") }

android { namespace = "com.alanshum.pixelminimal.bridge.protocol"; compileSdk = 35
    defaultConfig { minSdk = 34 }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}

kotlin { jvmToolchain(17) }

dependencies {
    testImplementation("junit:junit:4.13.2")
}
