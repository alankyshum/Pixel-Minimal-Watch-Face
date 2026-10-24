# Agent Feature Map

For vague or feature-level work, find the user's words below and read the matching feature file before changing code. Update the owning feature file with user-facing behavior changes; do not hand-edit this generated index.

## Features

| ID | Title | User vocabulary and aliases | Entry points |
| --- | --- | --- | --- |
| [phone-bridge](./phone-bridge.md) | Optional phone battery and calendar bridge | phone companion, phone battery, phone calendar, calendar permission, sync, Data Layer, bridge protocol | `phone-companion:activity:.SyncActivity`, `phone-companion:receiver:.BatteryReceiver` |
| [session-countdown](./session-countdown.md) | Configurable Session Countdown AOD | Session Countdown, session timer, AOD countdown, PERSONAL label, session schedule, watchface sessions | `watchface:aod-style:session-countdown` |
| [watch-face-display](./watch-face-display.md) | Watch face display, complications, ambient mode, and settings | watch face, clock, layout, complications, slots, AOD, ambient, colors, font, Nova Mono, Orbitron, hour animation, flavors | `watchface:face`, `watchface:slot:0`, `watchface:slot:1`, `watchface:slot:2`, `watchface:slot:3`, `watchface:slot:4`, `watchface:config:aod`, `watchface:config:bottomComplicationFontSize`, `watchface:config:hollowAOD`, `watchface:config:secIndicator`, `watchface:config:themeColor`, `watchface:config:timeColor`, `watchface:config:topComplicationFontSize`, `watchface:ambient`, `watchface:font:SYNC_TO_DEVICE`, `watchface:font:nova_mono`, `watchface:font:orbitron_wght` |
| [watch-provider](./watch-provider.md) | Optional watch complication providers | watch provider, phone battery complication, calendar complication, cached snapshot, NoData, PERSONAL fixture | `watch-provider:complication:.CalendarComplicationService`, `watch-provider:complication:.PhoneBatteryComplicationService` |

## Entry point to feature

| Entry point | Feature |
| --- | --- |
| `phone-companion:activity:.SyncActivity` | [Optional phone battery and calendar bridge](./phone-bridge.md) |
| `phone-companion:receiver:.BatteryReceiver` | [Optional phone battery and calendar bridge](./phone-bridge.md) |
| `watch-provider:complication:.CalendarComplicationService` | [Optional watch complication providers](./watch-provider.md) |
| `watch-provider:complication:.PhoneBatteryComplicationService` | [Optional watch complication providers](./watch-provider.md) |
| `watchface:ambient` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:aod-style:session-countdown` | [Configurable Session Countdown AOD](./session-countdown.md) |
| `watchface:config:aod` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:config:bottomComplicationFontSize` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:config:hollowAOD` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:config:secIndicator` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:config:themeColor` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:config:timeColor` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:config:topComplicationFontSize` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:face` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:font:SYNC_TO_DEVICE` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:font:nova_mono` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:font:orbitron_wght` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:slot:0` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:slot:1` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:slot:2` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:slot:3` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
| `watchface:slot:4` | [Watch face display, complications, ambient mode, and settings](./watch-face-display.md) |
