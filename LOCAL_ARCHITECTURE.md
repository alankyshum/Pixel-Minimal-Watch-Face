# Local bridge architecture

`watchface` remains a resource-only WFF v2 APK. `phone-companion` reads the
phone battery and (after an explicit runtime permission granted through its
single activity) `CalendarContract.Instances`; it sends compact, validated
version-1 Data Layer snapshots only when their displayed content or charging
state changes. It checks the reachable `pixel_minimal_bridge` capability first.

`watch-provider` is the companion Wear APK. Its Data Layer listener validates
each snapshot, writes the cache to DataStore (and a synchronous mirror used by
the provider process), and requests complication updates only for changed
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
