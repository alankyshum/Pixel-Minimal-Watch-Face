# Pixel Minimal Long Text (Local)

This is a configurable derivative of an upstream WFF2 watch face for Wear OS 5+. It is source-available for personal use and GitHub forking under the written upstream permission recorded in [UPSTREAM_PERMISSION.md](UPSTREAM_PERMISSION.md).

## Quick start

1. Edit [`config/watchface-sessions.json`](config/watchface-sessions.json). The `sessions` array must contain exactly `name`, `start`, and `end` in `HH:MM`; schedules must be ordered, contiguous, and cover 24 hours. An overnight entry such as `22:00`→`06:00` may be last. Optional top-level `labelFormat` (default `"{date} {name}"`), `dateFormat` (default `"EEE MM/dd"`), and `uppercaseDate` (boolean, default `true`) configure the session row, for example `THU 09/17 PEAK`. Date formats split on whitespace into one parameter per token: `EEE`/`MMM` select English names from numeric `[DAY_OF_WEEK]`/`[MONTH]` fields; `uppercaseDate: false` selects original-case names. Every other token, including `MM/dd`, stays in ICU. The verifier bounds the configured name tables and the `d`/`MM/dd` numeric tokens; other ICU patterns require a verified width budget.
2. Validate and generate the WFF resource:

   ```sh
   ./scripts/validate
   ```

3. Build the debug APK (this validates/generates again, then builds):

   ```sh
   ./scripts/build-watchface
   ```

4. Find the printed APK path at `watchface/build/outputs/apk/debug/watchface-debug.apk`. Install it to a compatible Wear OS 5+ watch with Android Studio or `adb` for personal use.

The scripts are thin wrappers around the existing Python tools, official WFF validator, and Gradle build. They require Python 3, a Wear OS/Android SDK for Gradle, and Java 17; the build script discovers Java 17 on macOS when `JAVA_HOME` is not already set.

## Development

The session generator validates JSON and regenerates `watchface.xml` before Android resource processing. Gradle's `preBuild` task also runs it, so direct Gradle builds remain safe. `24:00` is allowed only as a non-wrapping end boundary. The generated configuration inventory below comes from the static watchface template and `strings.xml`; do not edit it manually.

Useful direct commands:

```sh
python3 tools/generate_watchface_sessions.py
python3 tools/generate_watchface_sessions.py --check
python3 tools/generate_readme_config.py --check
python3 -m unittest tools/test_generate_watchface_sessions.py
python3 -m unittest tools/test_generate_readme_config.py
python3 tools/verify_font_mapping.py
tools/validate_wff_v2.sh
```

For one-time repository-local pre-commit checks (without changing global Git configuration):

```sh
git config core.hooksPath .githooks
```

The official WFF validator uses a checksum-pinned Google watchface source cache under `${XDG_CACHE_HOME:-$HOME/.cache}`. It needs `curl`, `tar`, a POSIX shell, and Java 17 when rebuilding or downloading that cache. The validator source is Google’s Apache-2.0 [watchface repository](https://github.com/google/watchface), commit `44b1855d445686ac8de5dbc95003d6f8e6623643`; the downloaded codeload archive must match SHA-256 `d32b020cd7130b0d5d0a576878b452785b46c1c614642f4af55a937ef551ed4d`.

See [LOCAL_ARCHITECTURE.md](LOCAL_ARCHITECTURE.md) for the optional local phone/watch bridge modules. The third-party [Phone Battery Complication](https://play.google.com/store/apps/details?id=com.weartools.phonebattcomp) is not bundled here.

## Current layout and assignments

- Center: large Nova Mono digital clock.
- Top outer arc (slot 2): Phone Battery Complication or another supported text provider.
- Top inner arc (slot 4): independent text-only `SHORT_TEXT` or `LONG_TEXT` complication.
- Bottom (slot 3): adaptive circular text; left (slot 0) is Day & Date and right (slot 1) is a timer/countdown.
- Hour Animation retains the compatibility `secIndicator` setting and moves at minute-level granularity without seconds.
- Session Countdown is an opt-in AOD style with configurable session labels, countdown rows, current time, endpoint labels, and arc.

Slots remain configurable in the Wear OS complication editor. Install and configure third-party provider apps separately if used.

## Configuration inventory

<!-- BEGIN GENERATED CONFIGURATION INVENTORY -->

### User configurations

| ID | Label | Type | Default | Options |
| --- | --- | --- | --- | --- |
| `themeColor` | Material Theme | color | `72` | `0` Graphite; `1` Cloud; `2` Almond; `3` Watermelon; `4` Pomelo; `5` Champagne; `6` Wheat; `7` Limoncello; `8` Key Lime; `9` Lemongrass; `10` Spring; `11` Lime; `12` Pear; `13` Grass Green; `14` Proto Green; `15` Moss Green; `16` Fern; `17` Spearmint; `72` Alpine Green; `18` Mint; `19` Jade; `20` Steam Green; `21` Sage; `22` Avocado; `23` Forest; `71` Pine Green; `24` Seafoam; `25` Stream; `26` Aqua; `27` Lagoon; `29` Sky; `30` Ocean; `31` Sapphire; `32` Royal Blue; `33` Arctic; `34` Icy Blue; `35` Amethyst; `36` Lilac; `38` Lavender; `39` Flamingo; `40` Verbena; `41` Guava; `42` Coral; `43` Peach; `44` Orange; `45` Chai; `46` Honey; `47` Melon; `48` Dandelion; `49` Milkshake; `50` Sand; `51` Salmon; `52` Amber; `54` Charcoal; `55` Ocean Research; `56` Nothing; `57` Submarine; `58` Proto Blue; `59` Khaki; `60` Olive Vibrant; `61` Olive Dull; `62` Candy; `63` United 24; `64` Iridescent; `65` Industrial; `66` Green Shock; `67` Juniper Haze; `68` Neon Green; `69` Neon Lime |
| `timeColor` | Digital Clock Color | color | `71` | `100` White; `0` Graphite; `1` Cloud; `2` Almond; `3` Watermelon; `4` Pomelo; `5` Champagne; `6` Wheat; `7` Limoncello; `8` Key Lime; `9` Lemongrass; `10` Spring; `11` Lime; `12` Pear; `62` Grass Green; `63` Proto Green; `13` Moss Green; `14` Fern; `15` Spearmint; `16` Mint; `17` Jade; `72` Alpine Green; `18` Steam Green; `19` Sage; `20` Avocado; `21` Forest; `71` Pine Green; `22` Seafoam; `23` Stream; `24` Aqua; `25` Lagoon; `26` Sunset; `27` Sky; `28` Ocean; `29` Sapphire; `30` Royal Blue; `31` Arctic; `32` Icy Blue; `33` Amethyst; `34` Lilac; `35` Macaron; `36` Lavender; `37` Flamingo; `38` Verbena; `39` Guava; `40` Coral; `41` Peach; `42` Chai; `43` Honey; `44` Melon; `45` Dandelion; `46` Milkshake; `47` Sand; `48` Salmon; `49` Amber; `50` Creamsicle; `51` Mustard; `52` Charcoal; `53` Radar; `54` Cyborg; `55` Sealab; `56` Voltage; `57` Ocean Research; `58` Nothing; `59` Thermal; `60` Submarine; `61` Proto Blue; `64` Khaki; `65` Industrial; `66` Green Shock; `67` Juniper Haze; `68` Neon Green; `69` Neon Lime; `70` Neon Orange |
| `aod` | AOD Style | list | `0` | `0` Dimmed; `1` Time Only; `2` Time Only ++; `3` Session Countdown |
| `hollowAOD` | AOD Clock | list | `0` | `0` Solid; `1` Solid (formerly Outlined) |
| `topComplicationFontSize` | Top complication font size | list | `22` | `18` Small; `22` Medium; `26` Large |
| `bottomComplicationFontSize` | Bottom complication font size | list | `22` | `18` Small; `22` Medium; `26` Large |
| `secIndicator` | Hour Animation | boolean | `FALSE` | `FALSE` Off; `TRUE` On |

### Complication slots

| Slot | Label | Bounds | Supported types | Default policy |
| --- | --- | --- | --- | --- |
| `0` | Left Circle Slot | 130 × 130 at 5,160 | `RANGED_VALUE SHORT_TEXT MONOCHROMATIC_IMAGE SMALL_IMAGE EMPTY` | `defaultSystemProvider`=DAY_AND_DATE, `defaultSystemProviderType`=SHORT_TEXT |
| `1` | Right Circle Slot | 130 × 130 at 315,160 | `RANGED_VALUE SHORT_TEXT MONOCHROMATIC_IMAGE SMALL_IMAGE EMPTY` | `defaultSystemProvider`=TIMER, `defaultSystemProviderType`=SHORT_TEXT |
| `2` | Top Box Slot | 402 × 112 at 24,0 | `SHORT_TEXT LONG_TEXT EMPTY` | `defaultSystemProvider`=DAY_AND_DATE, `defaultSystemProviderType`=SHORT_TEXT, `primaryProvider`=com.weartools.phonebattcomp/com.weartools.phonebattcomp.complication.MobileBatteryComplicationService, `primaryProviderType`=SHORT_TEXT |
| `3` | Bottom Box Slot | 402 × 150 at 24,300 | `SHORT_TEXT LONG_TEXT EMPTY` | `defaultSystemProvider`=DAY_AND_DATE, `defaultSystemProviderType`=SHORT_TEXT |
| `4` | Second Top Text Slot | 256 × 80 at 97,57 | `SHORT_TEXT LONG_TEXT EMPTY` | — |

### Flavors

| ID | Label | Assignments |
| --- | --- | --- |
| `0` | 1st flavor | `themeColor`=`72`, `timeColor`=`71` |
| `1` | 2nd flavor | `themeColor`=`17`, `timeColor`=`26`, `secIndicator`=`TRUE` |
| `2` | 3rd flavor | `themeColor`=`65`, `timeColor`=`0`, `secIndicator`=`TRUE` |
| `3` | 4th flavor | `themeColor`=`64`, `timeColor`=`70` |
| `4` | 5th flavor | `themeColor`=`60`, `timeColor`=`72` |
| `5` | 6th flavor | `themeColor`=`36`, `timeColor`=`35`, `secIndicator`=`TRUE` |

Default flavor: `0`.
<!-- END GENERATED CONFIGURATION INVENTORY -->

## Build and personal use

This checkout has no release signing setup. Compiled APKs are not distributed by this repository. Install the debug APK with Android Studio or `adb`; the scripts intentionally do not select a device or install automatically.

## Font mapping and circular-text safety

The 112px center clock uses the unmodified static Nova Mono Regular Google Fonts artifact. Left date and right Timer retain bundled Orbitron. Provenance, source URLs, and SHA-256 values are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The static font/geometry invariants are checked by `tools/verify_font_mapping.py`.

## Changelog

Release history is maintained separately in [CHANGELOG.md](CHANGELOG.md).

## Permission, licensing, and publication status

This repository is **source-available, not OSI open source**. The supplied written upstream permission is quoted verbatim in [UPSTREAM_PERMISSION.md](UPSTREAM_PERMISSION.md). It does not grant or claim commercial rights, sublicensing, general redistribution, or APK/release distribution. The bundled fonts are unmodified and licensed under the SIL Open Font License 1.1; see [OFL.txt](OFL.txt), [NOVA_MONO_OFL.txt](NOVA_MONO_OFL.txt), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
