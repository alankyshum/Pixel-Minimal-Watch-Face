#!/usr/bin/env python3
"""Dependency-free device registry and screenshot checks for watch-face UAT."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Device:
    name: str
    width: int
    height: int
    density: int
    round: bool
    source: str


# Keep this as the single device-spec registry. tools/uat.sh reads it through `specs --tsv`.
DEVICES = {
    "pixel-watch-3-41mm": Device(
        "Google Pixel Watch 3 41 mm", 408, 408, 320, True,
        "https://support.google.com/googlepixelwatch/answer/12651869 and "
        "https://www.o2.co.uk/help/phones-sims-and-devices/google/pixel-watch-3-android-wear-os/specifications",
    ),
    "pixel-watch-3-45mm": Device(
        "Google Pixel Watch 3 45 mm", 456, 456, 320, True,
        "https://support.google.com/googlepixelwatch/answer/12651869 and "
        "https://www.o2.co.uk/help/phones-sims-and-devices/google/pixel-watch-3-android-wear-os/specifications",
    ),
    "oneplus-watch-4": Device(
        "OnePlus Watch 4", 466, 466, 310, True,
        "https://www.oneplus.com/global/oneplus-watch-4/specs",
    ),
}

LIT_LUMA = 20
MAX_AOD_LIT_FRACTION = 0.15
MAX_SESSION_AOD_LIT_FRACTION = 0.22
MIN_FACE_LIT_FRACTION = 0.005
MAX_OUTSIDE_LIT_FRACTION = 0.001
MIN_MODE_DIFFERENCE = 0.01
BURN_IN_INSET_PX = 10
MAX_UNSAFE_EDGE_FRACTION = 0.0001


class AssertionFailure(ValueError):
    pass


def read_png(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionFailure(f"{path}: not a PNG")
    offset, chunks = 8, {}
    idat = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IDAT":
            idat.extend(payload)
        else:
            chunks.setdefault(kind, payload)
        if kind == b"IEND":
            break
    try:
        width, height, depth, color, compression, filtering, interlace = struct.unpack(
            ">IIBBBBB", chunks[b"IHDR"]
        )
    except (KeyError, struct.error) as error:
        raise AssertionFailure(f"{path}: malformed PNG header") from error
    if depth != 8 or color not in (0, 2, 6) or compression or filtering or interlace:
        raise AssertionFailure(f"{path}: unsupported PNG format (8-bit non-interlaced RGB/RGBA/gray required)")
    channels = {0: 1, 2: 3, 6: 4}[color]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    rows, prior, cursor = [], bytearray(stride), 0
    for _ in range(height):
        filter_type = raw[cursor]
        encoded = raw[cursor + 1:cursor + 1 + stride]
        cursor += stride + 1
        row = bytearray(stride)
        for index, value in enumerate(encoded):
            left = row[index - channels] if index >= channels else 0
            up = prior[index]
            upper_left = prior[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                p = left + up - upper_left
                distances = (abs(p - left), abs(p - up), abs(p - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
            else:
                raise AssertionFailure(f"{path}: invalid PNG filter {filter_type}")
            row[index] = (value + predictor) & 255
        rows.append(row)
        prior = row
    pixels = []
    for row in rows:
        for x in range(width):
            sample = row[x * channels:(x + 1) * channels]
            if channels == 1:
                pixels.append((sample[0], sample[0], sample[0], 255))
            elif channels == 3:
                pixels.append((*sample, 255))
            else:
                pixels.append(tuple(sample))
    return width, height, pixels


def luminance(pixel: tuple[int, int, int, int]) -> float:
    r, g, b, alpha = pixel
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) * alpha / 255


def _inside_circle(x: int, y: int, width: int, height: int, inset: float = 0) -> bool:
    radius = min(width, height) / 2 - inset
    return (x + 0.5 - width / 2) ** 2 + (y + 0.5 - height / 2) ** 2 <= radius ** 2


def analyze(path: Path, device: Device, mode: str) -> dict[str, float | int | str]:
    width, height, pixels = read_png(path)
    if (width, height) != (device.width, device.height):
        raise AssertionFailure(
            f"expected {device.width}x{device.height}, got {width}x{height}; AVD profile is not the target device"
        )
    lit = [luminance(pixel) > LIT_LUMA for pixel in pixels]
    inside_indices, outside_indices, unsafe_indices = [], [], []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if _inside_circle(x, y, width, height):
                inside_indices.append(index)
                if not _inside_circle(x, y, width, height, BURN_IN_INSET_PX):
                    unsafe_indices.append(index)
            else:
                outside_indices.append(index)
    lit_fraction = sum(lit[index] for index in inside_indices) / len(inside_indices)
    outside_lit_fraction = sum(lit[index] for index in outside_indices) / max(1, len(outside_indices))
    if lit_fraction < MIN_FACE_LIT_FRACTION:
        raise AssertionFailure(f"render is blank or not a watch face: only {lit_fraction:.2%} lit pixels")
    if outside_lit_fraction > MAX_OUTSIDE_LIT_FRACTION:
        raise AssertionFailure(
            f"content clips outside the round display: {outside_lit_fraction:.3%} of corner pixels are lit"
        )

    # This face always has two large clock rows near the center. Requiring both is a
    # face-specific guard against a blank screen, setup UI, or a generic system face.
    clock_rows = []
    for top, bottom in ((0.22, 0.54), (0.47, 0.82)):
        count = total = 0
        for y in range(round(height * top), round(height * bottom)):
            for x in range(round(width * 0.22), round(width * 0.78)):
                total += 1
                count += lit[y * width + x]
        clock_rows.append(count / total)
    if min(clock_rows) < 0.01:
        raise AssertionFailure(
            f"expected Pixel Minimal's two center clock rows; occupancy is {clock_rows[0]:.2%}/{clock_rows[1]:.2%}"
        )
    separator_rows = 0
    for y in range(round(height * 0.40), round(height * 0.55)):
        row_lit = sum(
            lit[y * width + x] for x in range(round(width * 0.30), round(width * 0.70))
        )
        separator_rows = separator_rows + 1 if row_lit == 0 else 0
        if separator_rows >= 3:
            break
    if separator_rows < 3:
        raise AssertionFailure("center hour and minute rows overlap: no 3-pixel dark separator")

    unsafe_lit = sum(lit[index] for index in unsafe_indices)
    if mode in ("ambient", "session-countdown"):
        budget = MAX_SESSION_AOD_LIT_FRACTION if mode == "session-countdown" else MAX_AOD_LIT_FRACTION
        if lit_fraction > budget:
            raise AssertionFailure(
                f"AOD burn-in budget exceeded: {lit_fraction:.2%} lit (limit {budget:.0%})"
            )
        if mode == "ambient":
            max_unsafe_lit = max(1, math.floor(len(inside_indices) * MAX_UNSAFE_EDGE_FRACTION))
            if unsafe_lit > max_unsafe_lit:
                raise AssertionFailure(
                    f"AOD has {unsafe_lit} lit pixels within {BURN_IN_INSET_PX}px of the round edge "
                    f"(antialias allowance {max_unsafe_lit}); content may clip when shifted"
                )
    result = {
        "path": str(path), "width": width, "height": height, "mode": mode,
        "lit_fraction": lit_fraction, "outside_lit_fraction": outside_lit_fraction,
        "unsafe_aod_lit_pixels": unsafe_lit, "clock_hour_occupancy": clock_rows[0],
        "clock_minute_occupancy": clock_rows[1], "clock_separator_rows": separator_rows,
    }
    if mode == "session-countdown":
        def bounds(left: float, top: float, right: float, bottom: float) -> tuple[int, int, int, int]:
            points = [
                (x, y) for y in range(round(height * top), round(height * bottom))
                for x in range(round(width * left), round(width * right)) if lit[y * width + x]
            ]
            if not points:
                raise AssertionFailure(f"Session Countdown has no lit content in {top:.0%}-{bottom:.0%} center band")
            xs, ys = zip(*points)
            return min(xs), min(ys), max(xs), max(ys)

        # Keep the endpoint arc out of the large-numeral measurements.
        hour_bounds = bounds(0.20, 0.13, 0.80, 0.43)
        minute_bounds = bounds(0.20, 0.57, 0.80, 0.87)
        label_bounds = bounds(0.12, 0.46, 0.88, 0.54)
        centers = [(box[0] + box[2] + 1) / 2 for box in (hour_bounds, minute_bounds, label_bounds)]
        if any(abs(center - width / 2) > width * 0.04 for center in centers):
            raise AssertionFailure(f"Session Countdown rows are not centered: centers={centers}, face={width / 2}")
        if label_bounds[2] - label_bounds[0] < width * 0.20:
            raise AssertionFailure(f"Session Countdown date/session label is missing or too narrow: {label_bounds}")
        result.update({
            "session_hour_bounds": hour_bounds, "session_minute_bounds": minute_bounds,
            "session_label_bounds": label_bounds, "session_row_centers": centers,
        })
    return result


def compare_modes(interactive: Path, ambient: Path, device: Device) -> dict[str, float]:
    iw, ih, ip = read_png(interactive)
    aw, ah, ap = read_png(ambient)
    if (iw, ih) != (aw, ah) or (iw, ih) != (device.width, device.height):
        raise AssertionFailure("interactive and ambient screenshots have different dimensions")
    changed = 0
    total = 0
    for y in range(ih):
        for x in range(iw):
            if not _inside_circle(x, y, iw, ih):
                continue
            total += 1
            changed += abs(luminance(ip[y * iw + x]) - luminance(ap[y * iw + x])) >= 12
    fraction = changed / total
    if fraction < MIN_MODE_DIFFERENCE:
        raise AssertionFailure(
            f"interactive and AOD do not meaningfully differ: {fraction:.2%} changed pixels (minimum {MIN_MODE_DIFFERENCE:.0%})"
        )
    return {"changed_fraction": fraction}


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    specs = subparsers.add_parser("specs")
    specs.add_argument("--tsv", action="store_true")
    check = subparsers.add_parser("check")
    check.add_argument("--device", choices=DEVICES, required=True)
    check.add_argument("--mode", choices=("interactive", "ambient", "session-countdown"), required=True)
    check.add_argument("image", type=Path)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--device", choices=DEVICES, required=True)
    compare.add_argument("interactive", type=Path)
    compare.add_argument("ambient", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "specs":
            if args.tsv:
                for key, device in DEVICES.items():
                    print(key, device.name, device.width, device.height, device.density, str(device.round).lower(), sep="\t")
            else:
                print(json.dumps({key: asdict(value) for key, value in DEVICES.items()}, indent=2))
        elif args.command == "check":
            print(json.dumps(analyze(args.image, DEVICES[args.device], args.mode), indent=2))
        else:
            print(json.dumps(compare_modes(args.interactive, args.ambient, DEVICES[args.device]), indent=2))
    except (AssertionFailure, OSError, zlib.error) as error:
        print(f"UAT assertion failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
