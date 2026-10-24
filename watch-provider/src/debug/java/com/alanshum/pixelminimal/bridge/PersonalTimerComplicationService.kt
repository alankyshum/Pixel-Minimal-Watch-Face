package com.alanshum.pixelminimal.bridge

import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest

/** Debug-only fixture matching the event-timer complication used during watch-face UAT. */
class PersonalTimerComplicationService : ComplicationDataSourceService() {
    private fun data(): ComplicationData = ShortTextComplicationData.Builder(
        PlainComplicationText.Builder("23m").build(),
        PlainComplicationText.Builder("PERSONAL").build(),
    ).setTitle(PlainComplicationText.Builder("PERSONAL").build()).build()

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener,
    ) {
        listener.onComplicationData(data())
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData = data()
}
