#!/usr/bin/env python3
"""Focused, file-free tests for the session schedule generator."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
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

    def test_existing_schedule(self):
        rows = [{"name": "SLEEP", "start": "00:00", "end": "06:00"}, {"name": "PEAK", "duration": 300}, {"name": "TRANSITION", "duration": 60}, {"name": "TROUGH", "duration": 300}, {"name": "PERSONAL", "duration": 300}, {"name": "SLEEP", "duration": 120}]
        self.assertEqual(len(self.schedule(rows)), 6)

    def test_first_and_last_names_differ(self):
        text = self.render([{"name": "NIGHT", "duration": 60}, {"name": "DAY", "duration": 1380}])
        self.assertIn("session_countdown_s0_night", text)
        self.assertIn("session_countdown_s1_day", text)
        self.assertNotIn("1800", text)

    def test_two_sessions_and_repeated_nonadjacent_names(self):
        rows = [{"name": "A", "duration": 60}, {"name": "B", "duration": 60}, {"name": "A", "duration": 1320}]
        text = self.render(rows)
        self.assertEqual(text.count('name="session_countdown_s0_a"'), 1)
        self.assertEqual(text.count('name="session_countdown_s2_a"'), 1)

    def test_final_24_hour_end_and_idempotent_render(self):
        rows = [{"name": "A", "start": "00:00", "end": "12:00"}, {"name": "B", "start": "12:00", "end": "24:00"}]
        text = self.render(rows)
        self.assertIn("session_countdown_s1_b", text)
        self.assertEqual(generator.render(text, self.schedule(rows)), text)

    def test_single_full_day_does_not_add_midnight_carryover(self):
        text = self.render([{"name": "ALL DAY", "duration": 1440}])
        ET.fromstring(text)
        label = text[text.index("<!-- Condition owns"):text.index("<!-- Condition owns") + 500]
        self.assertIn("<Expressions>", label)
        self.assertIn("<Expression name=\"is_s0_all_day\"><![CDATA[1 == 1]]>", label)
        self.assertIn("<Compare expression=\"is_s0_all_day\">", label)
        self.assertIn("floor((1440 -", text)
        self.assertNotIn("1800", text)
        conditions = [condition for condition in ET.fromstring(text).findall(".//Condition")
                      if condition.find("Expressions/Expression") is not None]
        self.assertTrue(all(condition.find("Compare") is not None for condition in conditions))
        java_home = os.environ.get("JAVA_HOME")
        candidates = []
        if java_home:
            candidates.append(Path(java_home) / "bin/java")
        candidates.append(Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home/bin/java"))
        java_path = next((str(path) for path in candidates if path.is_file()), shutil.which("java"))
        jars = list((Path.home() / ".cache").glob("**/wff-validator.jar"))
        java_works = False
        java_command = java_path or ""
        if java_path:
            java_works = subprocess.run([java_command, "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).returncode == 0
        if java_works and jars:
            with tempfile.TemporaryDirectory() as directory:
                xml_path = Path(directory) / "one-session.xml"
                xml_path.write_text(text, encoding="utf-8")
                result = subprocess.run(
                    [java_command, "-jar", str(jars[0]), "2", "--stop-on-fail", str(xml_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_alternate_midnight_wrap_duration(self):
        text = self.render([{"name": "NIGHT", "duration": 120}, {"name": "DAY", "duration": 1320}])
        self.assertIn("1440", text)
        self.assertNotIn("1800", text)

    def test_same_name_midnight_merge_uses_first_end_for_arc(self):
        text = self.render([{"name": "NIGHT", "duration": 120}, {"name": "DAY", "duration": 600}, {"name": "NIGHT", "duration": 720}])
        arc = text[text.index('name="session_countdown_arc"'):text.index('name="session_countdown_arc"') + 1200]
        self.assertIn("? 60", arc)

    def test_nonmerged_final_end_uses_360_arc_endpoint(self):
        text = self.render([{"name": "NIGHT", "duration": 120}, {"name": "DAY", "duration": 1320}])
        arc = text[text.index('name="session_countdown_arc"'):text.index('name="session_countdown_arc"') + 1200]
        self.assertIn(": 360", arc)

    def test_invalid_configs(self):
        for rows in ([{"name": "A", "duration": 1}], [{"name": "", "duration": 1440}], [{"name": "A", "start": "00:00", "end": "24:00"}, {"name": "B", "duration": 60}]):
            with self.assertRaises(ValueError):
                self.schedule(rows)


if __name__ == "__main__":
    unittest.main()
