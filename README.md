# Pixel Minimal Long Text (Local)

This is a configurable derivative of an upstream WFF2 watch face for Wear OS 5+. It is source-available for personal use and GitHub forking under the written upstream permission recorded in [UPSTREAM_PERMISSION.md](UPSTREAM_PERMISSION.md).

## Current layout and assignments

- **Center:** large Nova Mono digital clock.
- **Top outer arc (slot 2):** the third-party [Phone Battery Complication](https://play.google.com/store/apps/details?id=com.weartools.phonebattcomp) default provider. Its normal text behavior is retained; its combined-battery presentation follows the same outer arc so it remains inside that slot's selectable/cropped arc shape, preserving watch and companion/phone percentages as plain circular text separated by a centered dot, without inline watch/phone icons because inline images are not used on the circular path. Special top notification rows use a compact monochromatic icon at the arc apex.
- **Top inner arc (slot 4):** an independent, initially unassigned text-only `SHORT_TEXT` or `LONG_TEXT` complication. `SHORT_TEXT` displays provider text only; `LONG_TEXT` displays provider text followed by its title (for example, `Now > 11:15`). Its narrower circular-text arc is below slot 2 and above the clock, leaving the left and right circular complication areas clear.
- **Bottom (slot 3):** adaptive lower circular text, defaulting to Day & Date. Arc A (outer/farther) is radius 205/diameter 410, `251.5→108.5°`, and Arc B (inner/closer) is radius 160/diameter 320, `238.5→121.5°`, both counter-clockwise about global 225,225: exact 30% geometric expansions of the former 110°/90° paths. Their 40px ink-safe bands leave a 5px radial gap. `SHORT_TEXT` retains its title-aware behavior: one-line content uses Arc A for 23 characters; with a nonempty title, `TEXT` (read first) uses Arc B for 20 and `TITLE` uses Arc A for 23. `LONG_TEXT` notification previews ignore `TITLE` (which providers can use for an app name). The nominal two-line capacity is 61 characters: Arc B receives up to 27 and Arc A up to 34. For overflow, WFF v2's lack of native search is addressed by the same finite descending `subText` comparison chain on both arcs: it selects the last ASCII space at indices 27 through 1 and consumes exactly that selected separator before rendering the preceding/following text without an artificial hyphen. Adjacent repeated ASCII spaces are not normalized: a space immediately before the selected separator remains at the end of Arc B, and one immediately after it remains at the start of Arc A. If no such space exists (including unbroken words and CJK text), it deliberately stays on one Arc-A line truncated to 34 characters rather than breaking a word across arcs. The sole `r=182.5`, 85px-thick `BoundingArc` crop is `259→101°`, covering radial 140..225 with a conservative 13px angular ink margin. This deliberate wider layout comes closer to the left/right side visuals; it no longer promises side-box endpoint clearance. The verifier instead checks rendered-path/raster containment, crop containment, on-screen bounds, clock clearance, and AOD visibility. Unusually wide glyph sequences remain authoritatively cropped. Exact `---` notification sentinel remains icon-only even when its provider supplies a title. Combined battery (invisible U+FEFF sentinel) uses Arc A.
- **Left (slot 0):** system **Day & Date** `SHORT_TEXT`, customized to omit the provider icon and show centered `MM/DD` and uppercase English weekday lines.
- **Right (slot 1):** timer/countdown complication.
- **Hour Animation:** the compatibility-preserved `secIndicator` setting is labelled **Hour Animation**. When enabled, its visual arc is hidden in ambient and uses exactly `[HOUR_0_11] * 30 + [MINUTE] * 0.5`, updating at minute-level granularity so it moves proportionally through each hour: 09:00=270°, 09:30=285°, 09:59=299.5°, 11:59=359.5°, and 12:00=0°. It uses a one-shot 0.4-second clockwise transition (`repeat="0"`) and does not use seconds.

Slots remain configurable in the Wear OS complication editor. Phone Battery Complication is a third-party app and is **not bundled** here. The optional `phone-companion`, `watch-provider`, and `shared-protocol` modules are local bridge modules; they are separate from the third-party provider and are not required for the assignments above. See [LOCAL_ARCHITECTURE.md](LOCAL_ARCHITECTURE.md) for their local-only design.

## Build and personal use

1. Open the project in Android Studio with an installed Wear OS SDK, or run `bash ./gradlew :watchface:assembleDebug`.
2. Install the resulting debug APK to a compatible Wear OS 5+ watch using Android Studio or `adb` for your own personal use.
3. Select **Pixel Minimal Long Text (Local)** and set the five complication slots in the watch/phone complication editor. Install and configure the third-party provider apps separately if you use them.
4. For the optional local bridge, build/install its phone and watch debug APKs on their respective devices; its current signing/deployment constraints are documented in [LOCAL_ARCHITECTURE.md](LOCAL_ARCHITECTURE.md).

This checkout has no release signing setup. Compiled APKs are not distributed by this repository.

## Font mapping and circular-text safety

- The 112px center clock uses the unmodified static Nova Mono Regular Google Fonts artifact (OS/2 weight class 400); provenance, source URL, and SHA-256 are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Its fixed-pitch metrics keep clock glyphs neat without tracking, because WFF v2 `TimeText` fonts do not permit `letterSpacing`. Left date display and right Timer retain bundled Orbitron with `letterSpacing="-0.05"` (−0.05em).
- Top and bottom text complications (slots 2, 4, and 3) use `SYNC_TO_DEVICE` with `letterSpacing="-0.05"`. Slot 3 retains 18/22/26px options, exactly one `TextCircular` per sibling `PartText`, tight ±13px-ink rasters, and explicit bounded expressions. Its conservative single `BoundingArc` remains the authoritative crop; path-level verification additionally enforces separate radial bands, crop containment, clock/edge clearance, and AOD safety.

### v1.0.17 release note

Bottom `LONG_TEXT` now wraps at an ASCII word boundary with an approximately 49% larger nominal 61-character two-line budget; it suppresses provider `TITLE`, adds no artificial hyphen, and falls back to one truncated line when no space exists. `CalendarComplicationService` now declares an explicit service-level icon so compatible provider pickers can list it. This is source-only: no APK is included or released.

### v1.0.16 release note

Ships exact 30%-wider adaptive bottom arcs, plus the restored minute-interpolated **Hour Animation** while retaining the `secIndicator` compatibility ID. It also includes the Nova Mono clock, safe side/`PartText` tracking, WFF validation hardening, and lower-power local bridge updates. This source-only release is neither release-signed nor accompanied by an uploaded APK.

### v1.0.15 release note

Adds an independent second top circular text complication (slot 4). Its `LONG_TEXT` rendering includes both provider text and title (for example, `Now > 11:15`) while keeping the existing top slot's battery and notification behavior inside its circular arc.

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

## Contributor checks

```sh
# One-time, repository-local hook setup (does not alter global Git configuration)
git config core.hooksPath .githooks

# Refresh/check this README's generated inventory
python3 tools/generate_readme_config.py
python3 tools/generate_readme_config.py --check

# Verify the fixed font mapping and non-font WFF invariants
python3 tools/verify_font_mapping.py

# Download a checksum-pinned Google watchface source tree, build its official
# validator, and validate this resource against WFF schema version 2.
tools/validate_wff_v2.sh
```

The tracked pre-commit hook runs the README `--check` command, static font/geometry verifier, and the portable official WFF v2 validation command. The latter caches a checksum-pinned source archive under `${XDG_CACHE_HOME:-$HOME/.cache}`; before executing it validates the archive, pinned validator build source, and validator JAR digests, so a verified cache does not force network access. It needs `curl`, `tar`, a POSIX shell, and Java 17 only when rebuilding/downloading. It is intentionally activated only after the explicit local `core.hooksPath` command above.

The validator source is Google’s Apache-2.0 [watchface repository](https://github.com/google/watchface), commit `44b1855d445686ac8de5dbc95003d6f8e6623643`; the downloaded codeload archive must match SHA-256 `d32b020cd7130b0d5d0a576878b452785b46c1c614642f4af55a937ef551ed4d`. It builds the repository’s documented `:specification:validator:executable-jar` target and invokes `java -jar wff-validator.jar 2 watchface/src/main/res/raw/watchface.xml`. This is a portable replacement for the reviewer-session schema-tree path; `xmllint` cannot compile the official schema because its XSD 1.0 implementation rejects the schema’s repeated members in `xs:all`.

## Permission, licensing, and publication status

This repository is **source-available, not OSI open source**. The supplied written upstream permission is quoted verbatim in [UPSTREAM_PERMISSION.md](UPSTREAM_PERMISSION.md). It is interpreted narrowly as permission for public source hosting and GitHub forking for personal use. It does not grant or claim commercial rights, sublicensing, general redistribution, or APK/release distribution. Downstream users should seek clarification from the upstream rights holder for rights beyond that quoted permission. This is practical compliance information, not legal advice.

The bundled Orbitron and Nova Mono fonts are unmodified and licensed under the SIL Open Font License 1.1; see [OFL.txt](OFL.txt), [NOVA_MONO_OFL.txt](NOVA_MONO_OFL.txt), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No blanket license applies to the remaining upstream-derived material.
