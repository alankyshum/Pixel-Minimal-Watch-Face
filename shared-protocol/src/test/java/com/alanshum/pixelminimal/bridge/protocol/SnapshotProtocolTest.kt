package com.alanshum.pixelminimal.bridge.protocol

import org.junit.Assert.*
import org.junit.Test

class SnapshotProtocolTest {
 @Test fun validSnapshotDecodes() { val s=SnapshotProtocol.Snapshot("42%", 100); assertEquals(s, SnapshotProtocol.decode(1, 100, "42%", false, 1000)) }
 @Test fun rejectsBadOrFutureData() { assertNull(SnapshotProtocol.decode(2, 100, "x", false, 1000)); assertNull(SnapshotProtocol.decode(1, 100, "x".repeat(81), false, 1000)); assertNull(SnapshotProtocol.decode(1, 400_000, "x", false, 1)) }
 @Test fun deltaIgnoresTimestampOnly() { val a=SnapshotProtocol.Snapshot("42%",1); assertFalse(SnapshotProtocol.materiallyChanged(a,a.copy(timestampMillis=2))) }
 @Test fun stalenessIsBounded() { assertTrue(SnapshotProtocol.Snapshot("x",0).isStale(SnapshotProtocol.MAX_AGE_MS+1)) }
}
