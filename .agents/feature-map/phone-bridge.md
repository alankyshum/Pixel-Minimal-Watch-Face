---
id: phone-bridge
title: Optional phone battery and calendar bridge
aliases: ["phone companion", "phone battery", "phone calendar", "calendar permission", "sync", "Data Layer", "bridge protocol"]
routes: ["phone-companion:activity:.SyncActivity", "phone-companion:receiver:.BatteryReceiver"]
paths: ["phone-companion/src/main/**", "shared-protocol/src/main/**"]
---
# Optional phone battery and calendar bridge

Reads phone battery state and, after explicit permission, calendar instances; sends validated snapshots to a reachable watch over the Wear Data Layer.

## Sub-features
- Launcher activity requests calendar permission and starts synchronization.
- Charging-transition receiver and scheduled work refresh battery and calendar snapshots.
- Shared protocol validates snapshots and formats the selected calendar event.

## How to reach it
- Install `phone-companion` on the paired phone and open Pixel Minimal Bridge to grant calendar access.

## How to drive it
- Open the activity, change charging state, or wait for scheduled work while the watch capability is reachable.

## Gotchas
- Calendar access is requested only from the foreground activity.
- The phone and watch bridge APKs use the same package on their respective devices.
