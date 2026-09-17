# Changelog

### v1.0.17 release note

- AOD session-name rows are centred on the watch face using its dimensions, without the large numerals' optical offset; verification derives raster and ink-gap checks from the same geometry.
- Session labels default to `THU 09/17 PEAK` without a separator; `EEE`/`MMM` use numeric clock-field name chains (original case when `uppercaseDate: false`), and other whitespace-delimited tokens stay in ICU.

Bottom `LONG_TEXT` now wraps at an ASCII word boundary with an approximately 49% larger nominal 61-character two-line budget; it suppresses provider `TITLE`, adds no artificial hyphen, and falls back to one truncated line when no space exists. `CalendarComplicationService` now declares an explicit service-level icon so compatible provider pickers can list it. This is source-only: no APK is included or released.

### v1.0.16 release note

Ships exact 30%-wider adaptive bottom arcs, plus the restored minute-interpolated **Hour Animation** while retaining the `secIndicator` compatibility ID. It also includes the Nova Mono clock, safe side/`PartText` tracking, WFF validation hardening, and lower-power local bridge updates. This source-only release is neither release-signed nor accompanied by an uploaded APK.

### v1.0.15 release note

Adds an independent second top circular text complication (slot 4). Its `LONG_TEXT` rendering includes both provider text and title (for example, `Now > 11:15`) while keeping the existing top slot's battery and notification behavior inside its circular arc.
