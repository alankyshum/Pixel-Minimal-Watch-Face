package com.alanshum.pixelminimal.bridge.protocol

object SnapshotProtocol {
    const val BATTERY_PATH = "/pixel-minimal/v1/battery"
    const val CALENDAR_PATH = "/pixel-minimal/v1/calendar"
    const val VERSION = 1
    const val VERSION_FIELD = "v"
    const val TIMESTAMP_FIELD = "t"
    const val TEXT_FIELD = "x"
    const val CHARGING_FIELD = "c"
    const val MAX_TEXT_LENGTH = 80
    const val MAX_AGE_MS = 6 * 60 * 60 * 1000L

    data class Snapshot(val text: String, val timestampMillis: Long, val charging: Boolean = false) {
        fun isStale(now: Long) = now - timestampMillis > MAX_AGE_MS || timestampMillis > now + 5 * 60 * 1000L
    }
    fun decode(version: Int, time: Long, rawText: String?, charging: Boolean, now: Long = System.currentTimeMillis()): Snapshot? {
        if (version != VERSION) return null
        val text = rawText?.trim() ?: return null
        if (text.isEmpty() || text.length > MAX_TEXT_LENGTH || time <= 0 || time > now + 5 * 60 * 1000L) return null
        return Snapshot(text, time, charging)
    }
    fun materiallyChanged(old: Snapshot?, next: Snapshot) = old?.let { it.text != next.text || it.charging != next.charging } ?: true
}
