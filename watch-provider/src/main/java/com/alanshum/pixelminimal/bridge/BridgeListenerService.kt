package com.alanshum.pixelminimal.bridge

import android.content.ComponentName
import android.content.Context
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import com.alanshum.pixelminimal.bridge.protocol.SnapshotProtocol
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.WearableListenerService
import java.util.concurrent.Executors

private object ListenerExecutor {
 private val executor = Executors.newSingleThreadExecutor { runnable ->
  Thread(runnable, "pixel-minimal-bridge-cache").apply { isDaemon = true }
 }
 private val lock = Any()
 private val pending = LinkedHashMap<String, () -> Unit>()
 private var draining = false

 /** Retain only the newest pending Data Layer event per path. */
 fun submit(path: String, task: () -> Unit) {
  synchronized(lock) {
   pending[path] = task
   if (draining) return
   draining = true
  }
  try {
   executor.execute {
    while (true) {
     val next = synchronized(lock) {
      val entry = pending.entries.firstOrNull()
      if (entry == null) { draining = false; return@synchronized null }
      pending.remove(entry.key); entry.value
     } ?: return@execute
     try { next() } catch (_: Throwable) { /* A bad event must not stop later updates. */ }
    }
   }
  } catch (_: Throwable) {
   synchronized(lock) { draining = false; pending.clear() }
  }
 }
}

class BridgeListenerService : WearableListenerService() {
 override fun onDataChanged(events: DataEventBuffer) {
  val appContext = applicationContext
  events.forEach { event ->
     if (event.type != DataEvent.TYPE_CHANGED || event.dataItem.uri.path !in setOf(SnapshotProtocol.BATTERY_PATH, SnapshotProtocol.CALENDAR_PATH)) return@forEach
   val path = event.dataItem.uri.path!!; val map = DataMapItem.fromDataItem(event.dataItem).dataMap
   val snapshot = SnapshotProtocol.decode(map.getInt(SnapshotProtocol.VERSION_FIELD), map.getLong(SnapshotProtocol.TIMESTAMP_FIELD), map.getString(SnapshotProtocol.TEXT_FIELD), map.getBoolean(SnapshotProtocol.CHARGING_FIELD), System.currentTimeMillis()) ?: return@forEach
     ListenerExecutor.submit(path) {
    val previous = SnapshotProtocol.Snapshot(BridgeCache.text(appContext,path), BridgeCache.time(appContext,path), BridgeCache.charging(appContext,path))
     appContext.getSharedPreferences("bridge_cache", MODE_PRIVATE).edit().putString("${path}_text",snapshot.text).putLong("${path}_time",snapshot.timestampMillis).putBoolean("${path}_charge",snapshot.charging).apply()
    if (SnapshotProtocol.materiallyChanged(previous, snapshot)) {
     val component = if (path == SnapshotProtocol.BATTERY_PATH) PhoneBatteryComplicationService::class.java else CalendarComplicationService::class.java
      ComplicationDataSourceUpdateRequester.create(appContext, ComponentName(appContext, component)).requestUpdateAll()
    }
   }
  }
 }
}

object BridgeCache {
 private fun p(context: Context) = context.getSharedPreferences("bridge_cache", Context.MODE_PRIVATE)
 fun text(c: Context,path:String)=p(c).getString("${path}_text", "")!!
 fun time(c: Context,path:String)=p(c).getLong("${path}_time",0)
 fun charging(c: Context,path:String)=p(c).getBoolean("${path}_charge",false)
}
