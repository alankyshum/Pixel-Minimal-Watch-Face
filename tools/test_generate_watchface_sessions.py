#!/usr/bin/env python3
"""Focused tests for the logical circular session schedule generator."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate_watchface_sessions", ROOT / "tools/generate_watchface_sessions.py")
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class SessionGeneratorTests(unittest.TestCase):
    def schedule(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.json"
            path.write_text(json.dumps({"sessions": rows}), encoding="utf-8")
            return generator.schedule(path)

    def render(self, rows):
        return generator.render(generator.TEMPLATE.read_text(encoding="utf-8"), self.schedule(rows))

    def test_default_logical_schedule_has_one_overnight_sleep(self):
        rows = [
            {"name": "PEAK", "start": "06:00", "end": "11:00"},
            {"name": "TRANSITION", "start": "11:00", "end": "12:00"},
            {"name": "TROUGH", "start": "12:00", "end": "17:00"},
            {"name": "PERSONAL", "start": "17:00", "end": "22:00"},
            {"name": "SLEEP", "start": "22:00", "end": "06:00"},
        ]
        result = self.schedule(rows)
        self.assertEqual(len(result), 5)
        self.assertTrue(result[-1]["wraps"])
        text = self.render(rows)
        self.assertEqual(text.count('name="session_countdown_s4_sleep"'), 1)
        self.assertEqual(text.count("06:00"), 1)

    def test_changed_boundaries_and_counts(self):
        rows = [{"name": "A", "start": "00:00", "end": "08:00"}, {"name": "B", "start": "08:00", "end": "24:00"}]
        text = self.render(rows)
        self.assertIn("session_countdown_s1_b", text)
        self.assertIn(": 360", text)
        self.assertEqual(text, generator.render(text, self.schedule(rows)))

    def test_overnight_end_other_than_six_and_midnight_end(self):
        self.assertTrue(self.schedule([{"name": "DAY", "start": "05:00", "end": "23:00"}, {"name": "NIGHT", "start": "23:00", "end": "05:00"}])[-1]["wraps"])
        self.assertFalse(self.schedule([{"name": "A", "start": "00:00", "end": "12:00"}, {"name": "B", "start": "12:00", "end": "24:00"}])[-1]["wraps"])

    def test_single_full_day(self):
        text = self.render([{"name": "ALL DAY", "start": "00:00", "end": "24:00"}])
        ET.fromstring(text)
        self.assertIn("<Expression name=\"is_s0_all_day\"><![CDATA[1 == 1]]>", text)

    def test_countdown_overnight_math(self):
        text = self.render([{"name": "DAY", "start": "06:00", "end": "22:00"}, {"name": "NIGHT", "start": "22:00", "end": "06:00"}])
        self.assertIn("1800", text)
        self.assertIn(": 180", text)
        self.assertIn("+ 1440", text)

    def test_duplicate_start_rejected_separately(self):
        rows = [
            {"name": "A", "start": "00:00", "end": "06:00"},
            {"name": "B", "start": "00:00", "end": "24:00"},
        ]
        with self.assertRaisesRegex(ValueError, r"session 1: duplicate start boundary 00:00"):
            self.schedule(rows)

    def test_invalid_start_order_rejected_separately(self):
        rows = [
            {"name": "A", "start": "00:00", "end": "12:00"},
            {"name": "B", "start": "12:00", "end": "18:00"},
            {"name": "C", "start": "06:00", "end": "24:00"},
        ]
        with self.assertRaisesRegex(ValueError, r"sessions must be in chronological start-time order"):
            self.schedule(rows)

    def test_overnight_session_must_be_last(self):
        rows = [
            {"name": "A", "start": "00:00", "end": "06:00"},
            {"name": "NIGHT", "start": "06:00", "end": "03:00"},
            {"name": "B", "start": "12:00", "end": "24:00"},
        ]
        with self.assertRaisesRegex(ValueError, r"^the overnight session must be last in chronological start-time order$"):
            self.schedule(rows)

    def test_invalid_configs(self):
        invalid = [
            [{"name": "A", "duration": 60}],
            [{"name": "A", "start": "00:30", "end": "01:00"}],
            [{"name": "A", "start": "00:00", "end": "02:00"}, {"name": "B", "start": "03:00", "end": "00:00"}],
            [{"name": "A", "start": "00:00", "end": "12:00"}, {"name": "B", "start": "12:00", "end": "06:00"}, {"name": "C", "start": "06:00", "end": "00:00"}],
            [{"name": "A", "start": "00:00", "end": "12:00"}],
        ]
        for rows in invalid:
            with self.assertRaises(ValueError):
                self.schedule(rows)


if __name__ == "__main__":
    unittest.main()
