import com.android.build.gradle.internal.tasks.factory.dependsOn

plugins {
    id("com.android.application")
}

android {
    namespace = "com.alanshum.pixelminimal.longtext"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.alanshum.pixelminimal.longtext"
        minSdk = 34
        targetSdk = 34
        versionCode = 10000010
        versionName = "1.0.10"

        manifestPlaceholders["publisher"] = "Alan Shum (Local Personal Use)"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            /** We are not using isDebuggable flag as it is not possible to debug Watch Face Format package.
             * Instead, we debug com.samsung.wear.watchface.runtime (Galaxy Watches) and/or
             * com.google.wear.watchface.runtime (Pixel Watches)
             */
            isDebuggable = false
        }
    }
}
