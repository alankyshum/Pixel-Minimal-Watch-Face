package com.alanshum.pixelminimal.bridge

import android.content.ComponentName
import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import com.alanshum.pixelminimal.bridge.protocol.SnapshotProtocol
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

private val Context.bridgeStore by preferencesDataStore("bridge_snapshots")
private val scope = CoroutineScope(Dispatchers.IO)
private fun textKey(path: String) = stringPreferencesKey("${path}_text")
private fun timeKey(path: String) = longPreferencesKey("${path}_time")
private fun chargeKey(path: String) = booleanPreferencesKey("${path}_charge")

class BridgeListenerService : WearableListenerService() {
 override fun onDataChanged(events: DataEventBuffer) {
  events.forEach { event ->
   if (event.type != 1 || event.dataItem.uri.path !in setOf(SnapshotProtocol.BATTERY_PATH, SnapshotProtocol.CALENDAR_PATH)) return@forEach
   val path = event.dataItem.uri.path!!; val map = DataMapItem.fromDataItem(event.dataItem).dataMap
   val snapshot = SnapshotProtocol.decode(map.getInt(SnapshotProtocol.VERSION_FIELD), map.getLong(SnapshotProtocol.TIMESTAMP_FIELD), map.getString(SnapshotProtocol.TEXT_FIELD), map.getBoolean(SnapshotProtocol.CHARGING_FIELD), System.currentTimeMillis()) ?: return@forEach
   scope.launch {
    val previous = SnapshotProtocol.Snapshot(BridgeCache.text(this@BridgeListenerService,path), BridgeCache.time(this@BridgeListenerService,path), BridgeCache.charging(this@BridgeListenerService,path))
    bridgeStore.edit { it[textKey(path)]=snapshot.text; it[timeKey(path)]=snapshot.timestampMillis; it[chargeKey(path)]=snapshot.charging }
    getSharedPreferences("bridge_cache", MODE_PRIVATE).edit().putString("${path}_text",snapshot.text).putLong("${path}_time",snapshot.timestampMillis).putBoolean("${path}_charge",snapshot.charging).apply()
    if (SnapshotProtocol.materiallyChanged(previous, snapshot)) {
     val component = if (path == SnapshotProtocol.BATTERY_PATH) PhoneBatteryComplicationService::class.java else CalendarComplicationService::class.java
     ComplicationDataSourceUpdateRequester.create(this@BridgeListenerService, ComponentName(this@BridgeListenerService, component)).requestUpdateAll()
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
