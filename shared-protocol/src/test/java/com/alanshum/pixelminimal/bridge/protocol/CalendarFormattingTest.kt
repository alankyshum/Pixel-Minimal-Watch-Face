package com.alanshum.pixelminimal.bridge.protocol
import org.junit.Assert.*
import org.junit.Test
class CalendarFormattingTest {
 @Test fun selectsCurrentTimedBeforeAllDay() { val e=CalendarFormatting.select(listOf(CalendarEvent(0,99,"All",true),CalendarEvent(20,40,"Next",false)), 25); assertEquals("Next",e?.title) }
 @Test fun skipsCancelledAndBoundsText() { val e=CalendarFormatting.select(listOf(CalendarEvent(0,10,"bad",false,cancelled=true),CalendarEvent(20,30,"x".repeat(60),false)),15)!!; assertEquals("20-30 ${"x".repeat(45)}",CalendarFormatting.render(e){it.toString()}) }
}
