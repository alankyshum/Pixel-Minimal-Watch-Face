package com.alanshum.pixelminimal.bridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import java.util.concurrent.atomic.AtomicBoolean

/** Manifest receiver is intentionally limited to meaningful charging transitions. */
class BatteryReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        val finished = AtomicBoolean(false)
        val finishOnce = { if (finished.compareAndSet(false, true)) pending.finish() }
        BridgeSendExecutor.submit("battery-broadcast", {
            try {
                // Read the sticky battery broadcast and enqueue the coalesced upload off the receiver main thread.
                BridgeSync(context.applicationContext).syncBattery()
            } finally {
                finishOnce()
            }
        }, finishOnce)
    }
}
