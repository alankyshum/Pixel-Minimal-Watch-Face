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
        versionCode = 10000017
        versionName = "1.0.17"

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

val generateWatchfaceSessions = tasks.register("generateWatchfaceSessions") {
    inputs.file(rootProject.file("config/watchface-sessions.json"))
    inputs.file(rootProject.file("tools/generate_watchface_sessions.py"))
    inputs.file(rootProject.file("watchface/src/main/watchface-template.xml"))
    val generated = layout.buildDirectory.file("generated/session-res/raw/watchface.xml")
    outputs.file(generated)
    doLast {
        exec {
            commandLine("python3", rootProject.file("tools/generate_watchface_sessions.py").absolutePath,
                "--output", generated.get().asFile.absolutePath)
        }
    }
}

tasks.named("preBuild") { dependsOn(generateWatchfaceSessions) }
android.sourceSets["main"].res.srcDir(layout.buildDirectory.dir("generated/session-res"))
