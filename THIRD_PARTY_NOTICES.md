# Third-party notices

## Orbitron

`watchface/src/main/res/font/orbitron_wght.ttf` is the unmodified
`Orbitron[wght].ttf` from [google/fonts `ofl/orbitron`](https://github.com/google/fonts/tree/main/ofl/orbitron), retrieved 2026-08-29.

* Source repository: `https://github.com/google/fonts.git`, branch `main`.
* Upstream font source commit recorded in `METADATA.pb`: `f16482824e0ce4d008dee59b9b632e9ce9663359`.
* SHA-256: `f42db2dd16e642258e35782916eceb1dcdbea06fb958d77ad71dc5963587e8fd`.
* Copyright: Copyright 2018 The Orbitron Project Authors.
* License: SIL Open Font License 1.1, reproduced verbatim in [`OFL.txt`](OFL.txt).

The face uses Orbitron for left/right complication text.

## Nova Mono

`watchface/src/main/res/font/nova_mono.ttf` is the official, unmodified static
Regular artifact retrieved from Google Fonts on 2026-08-30.

* Exact source URL: `https://raw.githubusercontent.com/google/fonts/main/ofl/novamono/NovaMono.ttf`.
* Provenance: [google/fonts `ofl/novamono`](https://github.com/google/fonts/tree/main/ofl/novamono), branch `main`.
* SHA-256: `648eadb6648c0801b186d3dcef60ee6aa84a791b1e09c726935c0712508b4807`.
* Status: static Regular, unmodified (no `fvar` table); `OS/2.usWeightClass` is 400.
* Copyright: Copyright (c) 2011, wmk69 (wmk69@o2.pl).
* License: SIL Open Font License 1.1, retrieved verbatim from `https://raw.githubusercontent.com/google/fonts/main/ofl/novamono/OFL.txt` as [`NOVA_MONO_OFL.txt`](NOVA_MONO_OFL.txt) (SHA-256 `197c3f48cff4df3d768230e0bbdbc4305d8b8b9041ea6fb5e00872af66adc5ae`).
* Reserved Font Name: `NovaMono` (preserved; this bundled artifact is unmodified).

Nova Mono is used only for the 112px center clock; Orbitron remains bundled and
in use for the left/right complications.
The outlined-AOD schema option is retained for configuration compatibility, but
now renders the same solid clock treatment as the solid option.
