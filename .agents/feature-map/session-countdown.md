---
id: session-countdown
title: Configurable Session Countdown AOD
aliases: ["Session Countdown", "session timer", "AOD countdown", "PERSONAL label", "session schedule", "watchface sessions"]
routes: ["watchface:aod-style:session-countdown"]
paths: ["config/watchface-sessions.json", "tools/generate_watchface_sessions.py", "tools/test_generate_watchface_sessions.py"]
---
# Configurable Session Countdown AOD

Generates the opt-in `aod=3` ambient style from a contiguous 24-hour session schedule. It shows the current time in the large center rows, zero-padded remaining time (`XXhYYm`) on the arc, endpoint labels and arc, plus a centered date/session label.

## Sub-features
- Validated ordered session names and whole-hour boundaries, including one overnight segment.
- Configurable date/name label formatting and English uppercase weekday/month names.
- Generated arc countdown expressions, sync-to-device center time, active endpoint marker, and safe centered geometry.

## How to reach it
- Select **Session Countdown** under **AOD Style** in the system watch-face editor, then let the watch enter ambient mode.

## How to drive it
- Edit `config/watchface-sessions.json`, run `python3 tools/generate_watchface_sessions.py`, and build the watch face.

## Gotchas
- The WFF layout lives in the shared watch-face template and remains owned by `watch-face-display`; this feature owns the schedule and generator.
- Wear OS has no supported adb API for directly mutating WFF user configuration.
