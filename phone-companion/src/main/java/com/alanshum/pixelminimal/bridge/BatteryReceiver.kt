package com.alanshum.pixelminimal.bridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Manifest receiver is intentionally limited to meaningful charging transitions. */
class BatteryReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        Thread { try { BridgeSync(context).syncBattery() } finally { pending.finish() } }.start()
    }
}
