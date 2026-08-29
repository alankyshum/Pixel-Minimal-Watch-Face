package com.alanshum.pixelminimal.bridge

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
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

class BridgeSync(private val context: Context) {
 private val prefs = context.getSharedPreferences("bridge_sent", Context.MODE_PRIVATE)
 fun sync() { syncBattery(); if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED) syncCalendar(); scheduleFallback() }
 fun syncBattery() {
  val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return
  val level = battery.getIntExtra("level", -1); val scale = battery.getIntExtra("scale", 100); val status=battery.getIntExtra("status",0)
  if(level < 0 || scale <= 0) return
  send(SnapshotProtocol.BATTERY_PATH, SnapshotProtocol.Snapshot("${level * 100 / scale}%", System.currentTimeMillis(), status == 2 || status == 5))
 }
 fun syncCalendar() { CalendarReader(context).currentText(System.currentTimeMillis())?.let { send(SnapshotProtocol.CALENDAR_PATH, SnapshotProtocol.Snapshot(it,System.currentTimeMillis())) }; CalendarReader(context).nextBoundary(System.currentTimeMillis())?.let { delay -> WorkManager.getInstance(context).enqueueUniqueWork("pixel-minimal-calendar-boundary", androidx.work.ExistingWorkPolicy.REPLACE, androidx.work.OneTimeWorkRequestBuilder<BridgeWorker>().setInitialDelay(delay, TimeUnit.MILLISECONDS).build()) } }
 private fun send(path:String, snapshot: SnapshotProtocol.Snapshot) {
  val prior=SnapshotProtocol.Snapshot(prefs.getString("$path.text","")!!, prefs.getLong("$path.time",0), prefs.getBoolean("$path.charge",false))
  if(!SnapshotProtocol.materiallyChanged(prior,snapshot)) return
  Thread {
   val cap=Tasks.await(Wearable.getCapabilityClient(context).getCapability("pixel_minimal_bridge", CapabilityClient.FILTER_REACHABLE))
   if(cap.nodes.isEmpty()) return@Thread
   val request=PutDataMapRequest.create(path).apply { dataMap.putInt(SnapshotProtocol.VERSION_FIELD,1); dataMap.putLong(SnapshotProtocol.TIMESTAMP_FIELD,snapshot.timestampMillis); dataMap.putString(SnapshotProtocol.TEXT_FIELD,snapshot.text); dataMap.putBoolean(SnapshotProtocol.CHARGING_FIELD,snapshot.charging) }.asPutDataRequest()
   Tasks.await(Wearable.getDataClient(context).putDataItem(request))
   prefs.edit().putString("$path.text",snapshot.text).putLong("$path.time",snapshot.timestampMillis).putBoolean("$path.charge",snapshot.charging).apply()
  }.start()
 }
 private fun scheduleFallback() { WorkManager.getInstance(context).enqueueUniquePeriodicWork("pixel-minimal-sync", ExistingPeriodicWorkPolicy.KEEP, PeriodicWorkRequestBuilder<BridgeWorker>(15,TimeUnit.MINUTES).build()) }
}
class BridgeWorker(app:Context, params:WorkerParameters): CoroutineWorker(app,params) { override suspend fun doWork(): Result { BridgeSync(applicationContext).sync(); return Result.success() } }

class CalendarReader(private val context: Context) {
 fun currentText(now:Long):String? {
  val items=events(now); return CalendarFormatting.select(items,now)?.let { CalendarFormatting.render(it) { DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(it)) } }
 }
 fun nextBoundary(now:Long):Long? = events(now).asSequence().filter { !it.allDay && !it.cancelled && !it.declined && it.end > now }.map { minOf(it.begin,it.end) }.filter { it > now }.minOrNull()?.minus(now)
 private fun events(now:Long):List<CalendarEvent> {
  val projection=arrayOf(CalendarContract.Instances.BEGIN,CalendarContract.Instances.END,CalendarContract.Instances.TITLE,CalendarContract.Instances.ALL_DAY,CalendarContract.Instances.STATUS,selfAttendeeStatus())
  val uri=CalendarContract.Instances.CONTENT_URI.buildUpon().appendPath((now-24*60*60*1000).toString()).appendPath((now+7*24*60*60*1000).toString()).build()
  val items=mutableListOf<CalendarEvent>(); context.contentResolver.query(uri,projection,null,null,"${CalendarContract.Instances.BEGIN} ASC")?.use { c -> while(c.moveToNext()) items += CalendarEvent(c.getLong(0),c.getLong(1),c.getString(2).orEmpty(),c.getInt(3)!=0,c.getInt(4)==CalendarContract.Instances.STATUS_CANCELED,c.columnCount>5 && c.getInt(5)==CalendarContract.Attendees.ATTENDEE_STATUS_DECLINED) }; return items
 }
 private fun selfAttendeeStatus()=CalendarContract.Instances.SELF_ATTENDEE_STATUS
}
