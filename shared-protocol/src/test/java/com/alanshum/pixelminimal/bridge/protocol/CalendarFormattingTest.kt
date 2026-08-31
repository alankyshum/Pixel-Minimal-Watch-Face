package com.alanshum.pixelminimal.bridge.protocol
import org.junit.Assert.*
import org.junit.Test
class CalendarFormattingTest {
 @Test fun selectsCurrentTimedBeforeAllDay() { val e=CalendarFormatting.select(listOf(CalendarEvent(0,99,"All",true),CalendarEvent(20,40,"Next",false)), 25); assertEquals("Next",e?.title) }
 @Test fun skipsCancelledAndBoundsText() { val e=CalendarFormatting.select(listOf(CalendarEvent(0,10,"bad",false,cancelled=true),CalendarEvent(20,30,"x".repeat(60),false)),15)!!; assertEquals("20-30 ${"x".repeat(45)}",CalendarFormatting.render(e){it.toString()}) }
 @Test fun boundaryUsesTheSameEligibleTimedEvents() {
  val events=listOf(CalendarEvent(90,110,"current",false),CalendarEvent(140,160,"next",false),CalendarEvent(120,130,"declined",false,declined=true),CalendarEvent(105,125,"cancelled",false,cancelled=true),CalendarEvent(120,200,"all day",true))
  assertEquals(40L, CalendarFormatting.nextBoundaryDelay(events,100))
 }
 @Test fun boundaryIsAbsentWhenOnlyEndedOrAllDayEventsRemain() {
  assertNull(CalendarFormatting.nextBoundaryDelay(listOf(CalendarEvent(0,100,"ended",false),CalendarEvent(0,200,"all day",true)),100))
 }
}
