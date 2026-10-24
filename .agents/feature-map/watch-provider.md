---
id: watch-provider
title: Optional watch complication providers
aliases: ["watch provider", "phone battery complication", "calendar complication", "cached snapshot", "NoData", "PERSONAL fixture"]
routes: ["watch-provider:complication:.CalendarComplicationService", "watch-provider:complication:.PhoneBatteryComplicationService"]
paths: ["watch-provider/src/main/**", "watch-provider/src/debug/**"]
---
# Optional watch complication providers

Receives validated phone snapshots, caches them locally, and exposes phone battery and calendar values as Wear OS complication data sources.

## Sub-features
- Battery provider emits `SHORT_TEXT`; calendar emits `SHORT_TEXT` or `LONG_TEXT`.
- Data Layer listener caches updates and requests complication refreshes.
- Missing or stale snapshots return `NoData`.
- Debug builds include a PERSONAL timer fixture used only by emulator UAT.

## How to reach it
- Install `watch-provider` on the watch, then choose a Pixel Minimal provider in a complication slot.

## How to drive it
- Trigger a phone bridge sync and request or refresh the selected complication through Wear OS.

## Gotchas
- The debug PERSONAL fixture is absent from release builds.
- These providers are optional and separate from any third-party default provider.
