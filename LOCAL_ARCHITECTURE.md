# Local bridge architecture

`watchface` remains a resource-only WFF v2 APK. `phone-companion` reads the
phone battery and (after an explicit runtime permission granted through its
single activity) `CalendarContract.Instances`; it sends compact, validated
version-1 Data Layer snapshots only when their displayed content or charging
state changes. It checks the reachable `pixel_minimal_bridge` capability first.

The resource-only face keeps the persisted `secIndicator` configuration ID and
TRUE/FALSE option IDs for compatibility, but presents it as **Hour Animation**:
its ambient-hidden visual arc uses `[HOUR_0_11] * 30 + [MINUTE] * 0.5` and a
non-repeating 0.4s clockwise transition. It moves proportionally through every
hour with minute-level updates (09:00=270°, 09:30=285°, 09:59=299.5°,
11:59=359.5°, 12:00=0°) without using seconds. Slot 3's adaptive lower arcs use
title presence to select outer-only versus TEXT-inner/TITLE-outer rendering.
Arc A is geometrically expanded 30% to r205 `251.5→108.5`; Arc B is expanded
30% to r160 `238.5→121.5`; and the r182.5 crop is `259→101`, radial 140..225.
The 23-character outer and 20-character inner budgets are retained. This
deliberately brings rendered endpoints closer to the side visuals, so validation
uses rendered-content/raster, crop, screen, clock, and AOD checks rather than an
obsolete side-box endpoint-clearance claim. The `BoundingArc` remains
authoritative cropping for unusually wide glyph sequences; title-less LONG_TEXT
uses documented fixed-position 18-plus-hyphen / `subText(...,18,41)` splitting
because WFF v2 has no word-boundary API.

`watch-provider` is the companion Wear APK. Its Data Layer listener validates
each snapshot, writes the sole SharedPreferences cache used by the provider
process, and requests complication updates only for changed
content. Battery is `SHORT_TEXT`; calendar supplies `LONG_TEXT` and `SHORT_TEXT`.
Snapshots older than six hours (or implausibly future dated) return NoData.

The battery manifest receiver is restricted to charging transitions. A 15-minute
WorkManager periodic fallback is the only polling fallback. Calendar refresh is
owner-initiated/periodic and one non-exact WorkManager job is scheduled at the
next selected event boundary. No calendar `PROVIDER_CHANGED` receiver is used:
its delivery differs across calendar implementations; a persistent content
observer would violate the local low-power design.

Both bridge APKs intentionally use the same package name and Gradle's same local
debug signing identity. They are installed on different devices (phone/watch),
not together. A release/local keystore was not generated, so local deployment is
limited to debug identity until an owner-provided signing setup is configured.
