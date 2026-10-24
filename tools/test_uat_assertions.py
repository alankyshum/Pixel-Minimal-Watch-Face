#!/usr/bin/env python3
"""Unit tests for emulator-independent UAT image checks and device data."""

from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("uat_assertions", ROOT / "tools/uat_assertions.py")
assert SPEC and SPEC.loader
uat = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = uat
SPEC.loader.exec_module(uat)


def write_png(path: Path, width: int, height: int, pixel) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel(x, y))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


class UatAssertionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.device = uat.Device("fixture", 100, 100, 320, True, "test")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def face_pixel(x: int, y: int, ambient: bool = False):
        radius = ((x - 50) ** 2 + (y - 50) ** 2) ** 0.5
        clock = 30 <= x < 70 and (25 <= y < 34 or 60 <= y < 69)
        detail = not ambient and 15 <= x < 22 and 42 <= y < 58
        return (180, 180, 180, 255) if radius < 39 and (clock or detail) else (0, 0, 0, 255)

    def test_registry_has_verified_round_target_specs(self) -> None:
        self.assertEqual((uat.DEVICES["pixel-watch-3-41mm"].width, uat.DEVICES["pixel-watch-3-41mm"].density), (408, 320))
        self.assertEqual((uat.DEVICES["pixel-watch-3-45mm"].width, uat.DEVICES["pixel-watch-3-45mm"].density), (456, 320))
        self.assertEqual((uat.DEVICES["oneplus-watch-4"].width, uat.DEVICES["oneplus-watch-4"].density), (466, 310))
        self.assertTrue(all(device.round and device.source.startswith("https://") for device in uat.DEVICES.values()))

    def test_valid_face_and_mode_difference_pass(self) -> None:
        interactive, ambient = self.root / "interactive.png", self.root / "ambient.png"
        write_png(interactive, 100, 100, lambda x, y: self.face_pixel(x, y))
        write_png(ambient, 100, 100, lambda x, y: self.face_pixel(x, y, True))
        self.assertGreater(uat.analyze(interactive, self.device, "interactive")["lit_fraction"], 0)
        self.assertLessEqual(uat.analyze(ambient, self.device, "ambient")["lit_fraction"], 0.15)
        self.assertGreater(uat.compare_modes(interactive, ambient, self.device)["changed_fraction"], 0.01)

    def test_blank_wrong_size_and_round_clipping_fail(self) -> None:
        blank = self.root / "blank.png"
        write_png(blank, 100, 100, lambda _x, _y: (0, 0, 0, 255))
        with self.assertRaisesRegex(uat.AssertionFailure, "blank"):
            uat.analyze(blank, self.device, "interactive")
        wrong = self.root / "wrong.png"
        write_png(wrong, 99, 100, lambda x, y: self.face_pixel(x, y))
        with self.assertRaisesRegex(uat.AssertionFailure, "expected 100x100"):
            uat.analyze(wrong, self.device, "interactive")
        clipped = self.root / "clipped.png"
        write_png(clipped, 100, 100, lambda x, y: (255, 255, 255, 255) if x < 10 and y < 10 else self.face_pixel(x, y))
        with self.assertRaisesRegex(uat.AssertionFailure, "outside"):
            uat.analyze(clipped, self.device, "interactive")

    def test_aod_budget_edge_and_identical_modes_fail(self) -> None:
        bright = self.root / "bright.png"
        write_png(bright, 100, 100, lambda x, y: (255, 255, 255, 255) if (x - 50) ** 2 + (y - 50) ** 2 < 35 ** 2 else (0, 0, 0, 255))
        with self.assertRaisesRegex(uat.AssertionFailure, "overlap|budget"):
            uat.analyze(bright, self.device, "ambient")
        edge = self.root / "edge.png"
        write_png(edge, 100, 100, lambda x, y: (200, 200, 200, 255) if self.face_pixel(x, y)[0] or (47 <= x <= 52 and y == 2) else (0, 0, 0, 255))
        with self.assertRaisesRegex(uat.AssertionFailure, "round edge"):
            uat.analyze(edge, self.device, "ambient")
        same = self.root / "same.png"
        write_png(same, 100, 100, lambda x, y: self.face_pixel(x, y))
        with self.assertRaisesRegex(uat.AssertionFailure, "do not meaningfully differ"):
            uat.compare_modes(same, same, self.device)

    def test_session_countdown_rows_and_label_are_centered(self) -> None:
        image = self.root / "session.png"
        def pixel(x: int, y: int):
            hour = 35 <= x < 65 and 23 <= y < 34
            minute = 35 <= x < 65 and 61 <= y < 70
            label = 35 <= x < 65 and 48 <= y < 52
            return (180, 180, 180, 255) if hour or minute or label else (0, 0, 0, 255)
        write_png(image, 100, 100, pixel)
        report = uat.analyze(image, self.device, "session-countdown")
        self.assertEqual(report["session_row_centers"], [50.0, 50.0, 50.0])

    def test_off_center_session_countdown_fails(self) -> None:
        image = self.root / "off-center-session.png"
        def pixel(x: int, y: int):
            hour = 50 <= x < 74 and 27 <= y < 34
            minute = 35 <= x < 65 and 61 <= y < 70
            label = 35 <= x < 65 and 48 <= y < 52
            return (180, 180, 180, 255) if hour or minute or label else (0, 0, 0, 255)
        write_png(image, 100, 100, pixel)
        with self.assertRaisesRegex(uat.AssertionFailure, "not centered"):
            uat.analyze(image, self.device, "session-countdown")


if __name__ == "__main__":
    unittest.main()
