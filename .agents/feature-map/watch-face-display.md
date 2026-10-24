---
id: watch-face-display
title: Watch face display, complications, ambient mode, and settings
aliases: ["watch face", "clock", "layout", "complications", "slots", "AOD", "ambient", "colors", "font", "Nova Mono", "Orbitron", "hour animation", "flavors"]
routes: ["watchface:face", "watchface:slot:0", "watchface:slot:1", "watchface:slot:2", "watchface:slot:3", "watchface:slot:4", "watchface:config:aod", "watchface:config:bottomComplicationFontSize", "watchface:config:hollowAOD", "watchface:config:secIndicator", "watchface:config:themeColor", "watchface:config:timeColor", "watchface:config:topComplicationFontSize", "watchface:ambient", "watchface:font:SYNC_TO_DEVICE", "watchface:font:nova_mono", "watchface:font:orbitron_wght"]
paths: ["watchface/src/main/**"]
---
# Watch face display, complications, ambient mode, and settings

Provides the resource-only Wear OS 5+ face: a large digital clock, five configurable complication slots, color and text-size choices, optional hour animation, flavors, and ambient-display styles. These behaviors share one WFF template, so they have one file-level owner.

## Sub-features
- Center Nova Mono clock; circular date/timer slots; two curved top text slots and adaptive bottom text.
- Dimmed, time-only, and Session Countdown ambient modes, with visibility controlled by WFF variants.
- Theme and clock colors, complication text sizes, hour animation, and preset flavors.

## How to reach it
- Install the `watchface` debug APK on Wear OS 5+, select Pixel Minimal Long Text (Local), and open the system complication/style editor.

## How to drive it
- Assign providers to slots 0–4 and change AOD style, colors, text sizes, hour animation, or flavor in the editor.

## Gotchas
- `watchface-template.xml` is the shared implementation for layout, slots, configuration, fonts, and ambient behavior; update this feature as a unit when those semantics change.
- The build generates `watchface.xml` from the template and the configured session schedule.
