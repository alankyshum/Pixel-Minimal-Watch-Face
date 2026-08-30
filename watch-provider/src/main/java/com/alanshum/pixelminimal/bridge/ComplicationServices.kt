package com.alanshum.pixelminimal.bridge

import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.NoDataComplicationData
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import com.alanshum.pixelminimal.bridge.protocol.SnapshotProtocol

private fun valid(service: ComplicationDataSourceService, path: String) = SnapshotProtocol.Snapshot(BridgeCache.text(service,path),BridgeCache.time(service,path),BridgeCache.charging(service,path)).takeUnless { it.text.isBlank() || it.isStale(System.currentTimeMillis()) }
abstract class BaseService : ComplicationDataSourceService() { abstract val path:String; abstract fun data(snapshot: SnapshotProtocol.Snapshot, type: ComplicationType): ComplicationData
 override fun onComplicationRequest(request: ComplicationRequest, listener: ComplicationDataSourceService.ComplicationRequestListener) { listener.onComplicationData(valid(this,path)?.let { data(it, request.complicationType) } ?: NoDataComplicationData()) }
}
class PhoneBatteryComplicationService : BaseService() { override val path=SnapshotProtocol.BATTERY_PATH
 override fun data(snapshot: SnapshotProtocol.Snapshot, type: ComplicationType) = ShortTextComplicationData.Builder(PlainComplicationText.Builder(snapshot.text).build(), PlainComplicationText.Builder("Phone battery ${snapshot.text}").build()).build()
 override fun getPreviewData(type: ComplicationType)=ShortTextComplicationData.Builder(PlainComplicationText.Builder("85%").build(),PlainComplicationText.Builder("Phone battery").build()).build()
}
class CalendarComplicationService : BaseService() { override val path=SnapshotProtocol.CALENDAR_PATH
 override fun data(snapshot: SnapshotProtocol.Snapshot, type: ComplicationType): ComplicationData = if(type == ComplicationType.SHORT_TEXT) ShortTextComplicationData.Builder(PlainComplicationText.Builder(snapshot.text.take(20)).build(),PlainComplicationText.Builder("Phone calendar").build()).build() else LongTextComplicationData.Builder(PlainComplicationText.Builder(snapshot.text).build(),PlainComplicationText.Builder("Phone calendar").build()).build()
 override fun getPreviewData(type:ComplicationType): ComplicationData = data(SnapshotProtocol.Snapshot("08:30-09:30 Meeting", 1), type)
}
