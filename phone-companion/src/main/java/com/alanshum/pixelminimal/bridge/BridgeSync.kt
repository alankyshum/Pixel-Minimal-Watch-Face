package com.alanshum.pixelminimal.bridge

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.BatteryManager
import android.provider.CalendarContract
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.alanshum.pixelminimal.bridge.protocol.SnapshotProtocol
import com.alanshum.pixelminimal.bridge.protocol.CalendarFormatting
import com.alanshum.pixelminimal.bridge.protocol.CalendarEvent
import com.google.android.gms.tasks.Tasks
import com.google.android.gms.wearable.CapabilityClient
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import java.text.DateFormat
import java.util.Date
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors

private const val WEARABLE_TIMEOUT_SECONDS = 10L
private const val CAPABILITY_NAME = "pixel_minimal_bridge"

/**
 * A serialized, per-key coalescing executor. At most one pending task is kept
 * for each Data Layer path, so an outage cannot turn repeated broadcasts into
 * an unbounded queue and the most recent material snapshot is retained.
 */
internal object BridgeSendExecutor {
  private data class PendingTask(val run: () -> Unit, val onReplaced: (() -> Unit)?)
  private val executor = Executors.newSingleThreadExecutor { runnable ->
    Thread(runnable, "pixel-minimal-bridge-send").apply { isDaemon = true }
  }
  private val lock = Any()
  private val pending = LinkedHashMap<String, PendingTask>()
  private var draining = false

  fun submit(path: String, task: () -> Unit, onReplaced: (() -> Unit)? = null) {
   val (replaced, startDraining) = synchronized(lock) {
     val discarded = pending.put(path, PendingTask(task, onReplaced))
     if (draining) discarded to false else {
      draining = true
      discarded to true
     }
   }
   // A replacement callback is cleanup (not work); it must not wedge the drain.
   try { replaced?.onReplaced?.invoke() } catch (_: Throwable) { }
   if (!startDraining) return
   try {
    executor.execute {
     while (true) {
      val next = synchronized(lock) {
       val entry = pending.entries.firstOrNull()
       if (entry == null) { draining = false; return@synchronized null }
       pending.remove(entry.key); entry.value.run
      } ?: return@execute
      try { next() } catch (_: Throwable) { /* Continue draining later snapshots. */ }
     }
    }
   } catch (_: Throwable) {
    val abandoned = synchronized(lock) { draining = false; pending.values.toList().also { pending.clear() } }
    abandoned.forEach { try { it.onReplaced?.invoke() } catch (_: Throwable) { } }
   }
  }
}

class BridgeSync(private val context: Context) {
 private val prefs = context.getSharedPreferences("bridge_sent", Context.MODE_PRIVATE)
 fun sync() { syncBattery(); if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED) syncCalendar(); scheduleFallback() }
  fun syncBattery() {
  val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return
   val level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1); val scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, 100); val status=battery.getIntExtra(BatteryManager.EXTRA_STATUS,BatteryManager.BATTERY_STATUS_UNKNOWN)
  if(level < 0 || scale <= 0) return
   send(SnapshotProtocol.BATTERY_PATH, SnapshotProtocol.Snapshot("${level * 100 / scale}%", System.currentTimeMillis(), status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL))
  }
  fun syncCalendar() {
   val now = System.currentTimeMillis()
   val events = CalendarReader(context).events(now)
   CalendarFormatting.select(events, now)?.let { event -> send(SnapshotProtocol.CALENDAR_PATH, SnapshotProtocol.Snapshot(CalendarFormatting.render(event) { DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(it)) }, now)) }
   CalendarFormatting.nextBoundaryDelay(events, now)?.let { delay -> WorkManager.getInstance(context).enqueueUniqueWork("pixel-minimal-calendar-boundary", androidx.work.ExistingWorkPolicy.REPLACE, androidx.work.OneTimeWorkRequestBuilder<BridgeWorker>().setInitialDelay(delay, TimeUnit.MILLISECONDS).build()) }
  }
 private fun send(path:String, snapshot: SnapshotProtocol.Snapshot) {
    BridgeSendExecutor.submit(path, task = submit@{
    val prior=SnapshotProtocol.Snapshot(prefs.getString("$path.text","")!!, prefs.getLong("$path.time",0), prefs.getBoolean("$path.charge",false))
    if(!SnapshotProtocol.materiallyChanged(prior,snapshot)) return@submit
    try {
     val cap=Tasks.await(Wearable.getCapabilityClient(context).getCapability(CAPABILITY_NAME, CapabilityClient.FILTER_REACHABLE), WEARABLE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
     if(cap.nodes.isEmpty()) return@submit
      val request=PutDataMapRequest.create(path).apply { dataMap.putInt(SnapshotProtocol.VERSION_FIELD,SnapshotProtocol.VERSION); dataMap.putLong(SnapshotProtocol.TIMESTAMP_FIELD,snapshot.timestampMillis); dataMap.putString(SnapshotProtocol.TEXT_FIELD,snapshot.text); dataMap.putBoolean(SnapshotProtocol.CHARGING_FIELD,snapshot.charging) }.asPutDataRequest()
     Tasks.await(Wearable.getDataClient(context).putDataItem(request), WEARABLE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
     prefs.edit().putString("$path.text",snapshot.text).putLong("$path.time",snapshot.timestampMillis).putBoolean("$path.charge",snapshot.charging).apply()
    } catch (_: Exception) {
      // Retain the prior sent-cache value so the next material sync retries.
     }
    })
   }
 private fun scheduleFallback() { WorkManager.getInstance(context).enqueueUniquePeriodicWork("pixel-minimal-sync", ExistingPeriodicWorkPolicy.KEEP, PeriodicWorkRequestBuilder<BridgeWorker>(15,TimeUnit.MINUTES).build()) }
}
class BridgeWorker(app:Context, params:WorkerParameters): CoroutineWorker(app,params) { override suspend fun doWork(): Result { BridgeSync(applicationContext).sync(); return Result.success() } }

class CalendarReader(private val context: Context) {
  fun events(now:Long):List<CalendarEvent> {
  val projection=arrayOf(CalendarContract.Instances.BEGIN,CalendarContract.Instances.END,CalendarContract.Instances.TITLE,CalendarContract.Instances.ALL_DAY,CalendarContract.Instances.STATUS,selfAttendeeStatus())
  val uri=CalendarContract.Instances.CONTENT_URI.buildUpon().appendPath((now-24*60*60*1000).toString()).appendPath((now+7*24*60*60*1000).toString()).build()
  val items=mutableListOf<CalendarEvent>(); context.contentResolver.query(uri,projection,null,null,"${CalendarContract.Instances.BEGIN} ASC")?.use { c -> while(c.moveToNext()) items += CalendarEvent(c.getLong(0),c.getLong(1),c.getString(2).orEmpty(),c.getInt(3)!=0,c.getInt(4)==CalendarContract.Instances.STATUS_CANCELED,c.columnCount>5 && c.getInt(5)==CalendarContract.Attendees.ATTENDEE_STATUS_DECLINED) }; return items
 }
 private fun selfAttendeeStatus()=CalendarContract.Instances.SELF_ATTENDEE_STATUS
}
