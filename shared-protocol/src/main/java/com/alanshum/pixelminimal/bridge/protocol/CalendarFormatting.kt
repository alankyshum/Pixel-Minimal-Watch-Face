package com.alanshum.pixelminimal.bridge.protocol

/** Pure selection and bounded rendering make calendar provider behavior testable without Android. */
data class CalendarEvent(val begin: Long, val end: Long, val title: String, val allDay: Boolean, val cancelled: Boolean = false, val declined: Boolean = false)
object CalendarFormatting {
    fun select(events: List<CalendarEvent>, now: Long): CalendarEvent? =
        events.asSequence().filterNot { it.cancelled || it.declined }
            .filter { !it.allDay && it.end >= now }.minByOrNull { it.begin }
            ?: events.asSequence().filterNot { it.cancelled || it.declined }.filter { it.allDay }.minByOrNull { it.begin }
    fun render(event: CalendarEvent, time: (Long) -> String): String =
        if (event.allDay) "All day ${event.title.take(55)}" else "${time(event.begin)}-${time(event.end)} ${event.title.take(45)}"
}
