package com.alanshum.pixelminimal.bridge

import android.Manifest
import android.app.Activity
import android.os.Bundle

/** Deliberately small: calendar access is requested only after the owner opens this activity. */
class SyncActivity : Activity() {
    override fun onCreate(state: Bundle?) { super.onCreate(state); requestPermissions(arrayOf(Manifest.permission.READ_CALENDAR), 1) }
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        BridgeSync(this).sync(); finish()
    }
}
