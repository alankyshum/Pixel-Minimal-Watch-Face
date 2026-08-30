# Pixel Minimal Long Text (Local)

This is a configurable derivative of an upstream WFF2 watch face for Wear OS 5+. It is source-available for personal use and GitHub forking under the written upstream permission recorded in [UPSTREAM_PERMISSION.md](UPSTREAM_PERMISSION.md).

## Current layout and assignments

- **Center:** large digital clock.
- **Top (slot 2):** the third-party [Phone Battery Complication](https://play.google.com/store/apps/details?id=com.weartools.phonebattcomp) Event Timer complication. Its event/title and time-until or remaining information are supplied by that provider.
- **Bottom (slot 3):** a Calendar Pro `LONG_TEXT` next-event complication. In the observed setup it supplies next-event text with time/remaining information; the face displays the provider's text and title and does not guarantee separate start and end times.
- **Left (slot 0):** system **Day & Date** `SHORT_TEXT`, customized to omit the provider icon and show centered `MM/DD` and uppercase English weekday lines.
- **Right (slot 1):** timer/countdown complication.

Slots remain configurable in the Wear OS complication editor. Phone Battery Complication and Calendar Pro are third-party apps and are **not bundled** here. The optional `phone-companion`, `watch-provider`, and `shared-protocol` modules are local bridge modules; they are separate from both third-party providers and are not required for the assignments above. See [LOCAL_ARCHITECTURE.md](LOCAL_ARCHITECTURE.md) for their local-only design.

## Build and personal use

1. Open the project in Android Studio with an installed Wear OS SDK, or run `bash ./gradlew :watchface:assembleDebug`.
2. Install the resulting debug APK to a compatible Wear OS 5+ watch using Android Studio or `adb` for your own personal use.
3. Select **Pixel Minimal Long Text (Local)** and set the four complication slots in the watch/phone complication editor. Install and configure the third-party provider apps separately if you use them.
4. For the optional local bridge, build/install its phone and watch debug APKs on their respective devices; its current signing/deployment constraints are documented in [LOCAL_ARCHITECTURE.md](LOCAL_ARCHITECTURE.md).

This checkout has no release signing setup. Compiled APKs are not distributed by this repository.

## Font mapping (local v1.0.12 experiment)

- Center clock, left date display, and right Timer use the bundled Orbitron font; the left display is provider-independent `MM/DD` plus uppercase English weekday, the clock remains 112px, and the circular-complication text is scaled for fit.
- Top and bottom text complications (slots 2 and 3) use the Wear OS system font with `letterSpacing="-0.05"`, including their combined-battery layouts, while retaining the existing 18/22/26px font-size options and long-text behavior. Center, left, and right remain on Orbitron.

## Configuration inventory

This section is generated from `watchface.xml` and `strings.xml`. Do not edit it manually: run `python3 tools/generate_readme_config.py` after changing watch-face configuration resources. CI and the repository hook use `--check` to reject stale content.

<!-- BEGIN GENERATED CONFIGURATION INVENTORY -->

### User configurations

| ID | Label | Type | Default | Options |
| --- | --- | --- | --- | --- |
| `themeColor` | Material Theme | color | `72` | `0` Graphite; `1` Cloud; `2` Almond; `3` Watermelon; `4` Pomelo; `5` Champagne; `6` Wheat; `7` Limoncello; `8` Key Lime; `9` Lemongrass; `10` Spring; `11` Lime; `12` Pear; `13` Grass Green; `14` Proto Green; `15` Moss Green; `16` Fern; `17` Spearmint; `72` Alpine Green; `18` Mint; `19` Jade; `20` Steam Green; `21` Sage; `22` Avocado; `23` Forest; `71` Pine Green; `24` Seafoam; `25` Stream; `26` Aqua; `27` Lagoon; `29` Sky; `30` Ocean; `31` Sapphire; `32` Royal Blue; `33` Arctic; `34` Icy Blue; `35` Amethyst; `36` Lilac; `38` Lavender; `39` Flamingo; `40` Verbena; `41` Guava; `42` Coral; `43` Peach; `44` Orange; `45` Chai; `46` Honey; `47` Melon; `48` Dandelion; `49` Milkshake; `50` Sand; `51` Salmon; `52` Amber; `54` Charcoal; `55` Ocean Research; `56` Nothing; `57` Submarine; `58` Proto Blue; `59` Khaki; `60` Olive Vibrant; `61` Olive Dull; `62` Candy; `63` United 24; `64` Iridescent; `65` Industrial; `66` Green Shock; `67` Juniper Haze; `68` Neon Green; `69` Neon Lime |
| `timeColor` | Digital Clock Color | color | `71` | `100` White; `0` Graphite; `1` Cloud; `2` Almond; `3` Watermelon; `4` Pomelo; `5` Champagne; `6` Wheat; `7` Limoncello; `8` Key Lime; `9` Lemongrass; `10` Spring; `11` Lime; `12` Pear; `62` Grass Green; `63` Proto Green; `13` Moss Green; `14` Fern; `15` Spearmint; `16` Mint; `17` Jade; `72` Alpine Green; `18` Steam Green; `19` Sage; `20` Avocado; `21` Forest; `71` Pine Green; `22` Seafoam; `23` Stream; `24` Aqua; `25` Lagoon; `26` Sunset; `27` Sky; `28` Ocean; `29` Sapphire; `30` Royal Blue; `31` Arctic; `32` Icy Blue; `33` Amethyst; `34` Lilac; `35` Macaron; `36` Lavender; `37` Flamingo; `38` Verbena; `39` Guava; `40` Coral; `41` Peach; `42` Chai; `43` Honey; `44` Melon; `45` Dandelion; `46` Milkshake; `47` Sand; `48` Salmon; `49` Amber; `50` Creamsicle; `51` Mustard; `52` Charcoal; `53` Radar; `54` Cyborg; `55` Sealab; `56` Voltage; `57` Ocean Research; `58` Nothing; `59` Thermal; `60` Submarine; `61` Proto Blue; `64` Khaki; `65` Industrial; `66` Green Shock; `67` Juniper Haze; `68` Neon Green; `69` Neon Lime; `70` Neon Orange |
| `aod` | AOD Style | list | `0` | `0` Dimmed; `1` Time Only; `2` Time Only ++ |
| `hollowAOD` | AOD Clock | list | `0` | `0` Solid; `1` Solid (formerly Outlined) |
| `topComplicationFontSize` | Top complication font size | list | `22` | `18` Small; `22` Medium; `26` Large |
| `bottomComplicationFontSize` | Bottom complication font size | list | `22` | `18` Small; `22` Medium; `26` Large |
| `secIndicator` | Seconds Indicator | boolean | `FALSE` | `FALSE` Off; `TRUE` On |

### Complication slots

| Slot | Label | Bounds | Supported types | Default policy |
| --- | --- | --- | --- | --- |
| `0` | Left Circle Slot | 130 × 130 at 5,160 | `RANGED_VALUE SHORT_TEXT MONOCHROMATIC_IMAGE SMALL_IMAGE EMPTY` | `defaultSystemProvider`=DAY_AND_DATE, `defaultSystemProviderType`=SHORT_TEXT |
| `1` | Right Circle Slot | 130 × 130 at 315,160 | `RANGED_VALUE SHORT_TEXT MONOCHROMATIC_IMAGE SMALL_IMAGE EMPTY` | `defaultSystemProvider`=TIMER, `defaultSystemProviderType`=SHORT_TEXT |
| `2` | Top Box Slot | 402 × 112 at 24,0 | `SHORT_TEXT LONG_TEXT EMPTY` | `defaultSystemProvider`=DAY_AND_DATE, `defaultSystemProviderType`=SHORT_TEXT, `primaryProvider`=com.weartools.phonebattcomp/com.weartools.phonebattcomp.complication.MobileBatteryComplicationService, `primaryProviderType`=SHORT_TEXT |
| `3` | Bottom Box Slot | 256 × 46 at 97,355 | `SHORT_TEXT LONG_TEXT EMPTY` | `defaultSystemProvider`=DAY_AND_DATE, `defaultSystemProviderType`=SHORT_TEXT |

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

## Contributor checks

```sh
# One-time, repository-local hook setup (does not alter global Git configuration)
git config core.hooksPath .githooks

# Refresh/check this README's generated inventory
python3 tools/generate_readme_config.py
python3 tools/generate_readme_config.py --check
```

The tracked pre-commit hook runs the `--check` command. It is intentionally activated only after the explicit local `core.hooksPath` command above.

## Permission, licensing, and publication status

This repository is **source-available, not OSI open source**. The supplied written upstream permission is quoted verbatim in [UPSTREAM_PERMISSION.md](UPSTREAM_PERMISSION.md). It is interpreted narrowly as permission for public source hosting and GitHub forking for personal use. It does not grant or claim commercial rights, sublicensing, general redistribution, or APK/release distribution. Downstream users should seek clarification from the upstream rights holder for rights beyond that quoted permission. This is practical compliance information, not legal advice.

All four uncleared font files were removed. The bundled unmodified `orbitron_wght.ttf` font is licensed under the SIL Open Font License 1.1; see [OFL.txt](OFL.txt) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No blanket license applies to the remaining upstream-derived material.
