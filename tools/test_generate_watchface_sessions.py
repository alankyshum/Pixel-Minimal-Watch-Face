#!/usr/bin/env python3
"""Focused tests for the logical circular session schedule generator."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate_watchface_sessions", ROOT / "tools/generate_watchface_sessions.py")
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)

DEFAULT_SESSIONS = [
    {"name": "PEAK", "start": "09:00", "end": "17:00"},
    {"name": "PERSONAL", "start": "17:00", "end": "23:00"},
    {"name": "SLEEP", "start": "23:00", "end": "09:00"},
]


def expected_date_parameters(tokens: str, uppercase: bool = True) -> list[dict[str, str]]:
    names = {
        "MMM": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
        "EEE": "Sun Mon Tue Wed Thu Fri Sat".split(),
    }
    result = []
    for token in tokens.split():
        expression = f'icuText("{token}", [UTC_TIMESTAMP])'
        if token in names:
            field = "MONTH" if token == "MMM" else "DAY_OF_WEEK"
            expression = "".join(
                f'[{field}] == {index if token == "MMM" else index - 1 + generator.DAY_OF_WEEK_SUNDAY} ? "{name.upper() if uppercase else name}" : '
                for index, name in enumerate(names[token], 1)
            ) + '""'
        result.append({"expression": expression})
    return result


class SessionGeneratorTests(unittest.TestCase):
    def schedule(self, rows, **formats):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.json"
            path.write_text(json.dumps({"sessions": rows, **formats}), encoding="utf-8")
            return generator.load(path)

    def render(self, rows, **formats):
        return generator.render(generator.TEMPLATE.read_text(encoding="utf-8"), *self.schedule(rows, **formats))

    def test_default_config_composes_date_and_name(self):
        rows, label_format, date_format, uppercase_date = self.schedule(DEFAULT_SESSIONS)
        self.assertEqual(label_format, "{date} {name}")
        self.assertEqual(date_format, "EEE MM/dd")
        self.assertIs(uppercase_date, True)
        text = generator.render(generator.TEMPLATE.read_text(encoding="utf-8"), rows)
        self.assertIn('<Template>%s %s PEAK<Parameter expression="[DAY_OF_WEEK] == ', text)
        root = ET.fromstring(text)
        for row in rows:
            template = root.find(f'.//PartText[@name="session_countdown_{row["key"]}"]/Text/Font/Template')
            assert template is not None
            self.assertEqual(template.text, f'%s %s {row["name"]}')
            self.assertEqual([p.attrib for p in template], expected_date_parameters("EEE MM/dd"))

    def test_label_position_follows_face_geometry(self) -> None:
        rows, *formats = self.schedule(DEFAULT_SESSIONS)
        source = generator.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(generator.SESSION_LABEL_X, (generator.FACE_SIZE - generator.SESSION_LABEL_WIDTH) / 2)
        self.assertEqual(generator.SESSION_LABEL_Y, (generator.FACE_SIZE - generator.SESSION_LABEL_HEIGHT) / 2)
        for face_size in (generator.FACE_SIZE, generator.FACE_SIZE + 20):
            with self.subTest(face_size=face_size), patch.object(generator, "FACE_SIZE", face_size):
                root = ET.fromstring(generator.render(source, rows, *formats))
                expected_x = (face_size - generator.SESSION_LABEL_WIDTH) / 2
                expected_y = (face_size - generator.SESSION_LABEL_HEIGHT) / 2
                for row in rows:
                    part = root.find(f'.//PartText[@name="session_countdown_{row["key"]}"]')
                    assert part is not None
                    self.assertEqual(part.get("x"), f"{expected_x:g}")
                    self.assertEqual(part.get("y"), f"{expected_y:g}")
                    self.assertEqual(float(part.attrib["x"]) + float(part.attrib["width"]) / 2, face_size / 2)
                    self.assertEqual(float(part.attrib["y"]) + float(part.attrib["height"]) / 2, face_size / 2)

    def test_custom_token_order_and_whitespace(self):
        rows = [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]
        text = self.render(rows, dateFormat="  EEE\t d  MMM\n", uppercaseDate=True)
        template = ET.fromstring(text).find('.//PartText[@name="session_countdown_s0_all_day"]/Text/Font/Template')
        assert template is not None
        self.assertEqual(template.text, "%s %s %s ALL DAY")
        self.assertEqual([p.attrib for p in template], expected_date_parameters("EEE d MMM"))

    def test_uppercase_false_keeps_original_names_per_token(self):
        rows = [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]
        text = self.render(rows, dateFormat="EEE  d MMM", uppercaseDate=False)
        template = ET.fromstring(text).find('.//PartText[@name="session_countdown_s0_all_day"]/Text/Font/Template')
        assert template is not None
        self.assertEqual(template.text, "%s %s %s ALL DAY")
        self.assertEqual([p.attrib for p in template], expected_date_parameters("EEE d MMM", False))

    def test_non_name_tokens_remain_icu_for_both_case_modes(self):
        # Given numeric, multi-field, and time tokens, with either casing mode.
        tokens = "M MM d dd yyyy MM/dd yyyy-MM-dd HH:mm"
        for uppercase in (True, False):
            with self.subTest(uppercase=uppercase):
                # When the session label is generated.
                text = self.render(DEFAULT_SESSIONS, dateFormat=tokens, uppercaseDate=uppercase)
                template = ET.fromstring(text).find('.//PartText[@name="session_countdown_s0_peak"]/Text/Font/Template')
                assert template is not None
                # Then each token is exactly one unchanged ICU parameter.
                self.assertEqual([p.attrib for p in template], [
                    {"expression": f'icuText("{token}", [UTC_TIMESTAMP])'} for token in tokens.split()
                ])

    def test_uppercase_date_requires_bool(self):
        rows = [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]
        for value in (None, 0, 1, "true", "false", [], {}):
            with self.subTest(uppercaseDate=value), self.assertRaisesRegex(ValueError, "uppercaseDate"):
                self.schedule(rows, uppercaseDate=value)

    def test_unmapped_tokens_and_xml_escaping(self):
        rows = [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]
        tokens = 'dd yyyy MMMM EEEE \'&<>"\''
        text = self.render(rows, labelFormat="<{name}> & {date}", dateFormat=tokens)
        template = ET.fromstring(text).find('.//PartText[@name="session_countdown_s0_all_day"]/Text/Font/Template')
        assert template is not None
        self.assertEqual(template.text, "<ALL DAY> & %s %s %s %s %s")
        self.assertEqual([p.attrib for p in template], expected_date_parameters(tokens))
        self.assertIn("&amp;&lt;&gt;&quot;", text)

    def test_custom_formats_flow_into_xml(self):
        rows = [{"name": "DAY", "start": "00:00", "end": "12:00"}, {"name": "NIGHT", "start": "12:00", "end": "24:00"}]
        for schedule in (rows, [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]):
            with self.subTest(rows=schedule):
                text = self.render(schedule, labelFormat="<{name}> & {date}!", dateFormat="yyyy-MM-dd '&<>'", uppercaseDate=False)
                root = ET.fromstring(text)
                for row in schedule:
                    self.assertIn(f'<Template>&lt;{row["name"]}&gt; &amp; %s %s!', text)
                templates = root.findall('.//PartText/Text/Font/Template')
                labels = [t for t in templates if (t.text or "").endswith("%s!")]
                self.assertEqual(len(labels), len(schedule))
                for template in labels:
                    self.assertEqual([p.attrib for p in template], expected_date_parameters("yyyy-MM-dd '&<>'", False))

    def test_invalid_label_and_date_formats(self):
        rows = [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]
        for value in ("", "{name}", "{date}", "{date}{date}{name}", "{date}{name}{name}", None, 42, []):
            with self.subTest(labelFormat=value), self.assertRaisesRegex(ValueError, "labelFormat"):
                self.schedule(rows, labelFormat=value)
        for value in ("", None, 42, []):
            with self.subTest(dateFormat=value), self.assertRaisesRegex(ValueError, "dateFormat"):
                self.schedule(rows, dateFormat=value)

    def test_format_backslashes_and_attribute_quotes_remain_literal(self):
        rows = [{"name": "ALL DAY", "start": "00:00", "end": "24:00"}]
        text = self.render(rows, labelFormat=r"{name}\1 ⋅ {date}", dateFormat='MMM d \'"\'', uppercaseDate=False)
        template = ET.fromstring(text).find('.//PartText[@name="session_countdown_s0_all_day"]/Text/Font/Template')
        assert template is not None
        self.assertEqual(template.text, r"ALL DAY\1 ⋅ %s %s %s")
        self.assertEqual([p.attrib for p in template], expected_date_parameters('MMM d \'"\'', False))

    def test_missing_formats_use_defaults(self):
        _, label_format, date_format, uppercase_date = self.schedule([{"name": "ALL DAY", "start": "00:00", "end": "24:00"}])
        self.assertEqual((label_format, date_format, uppercase_date), ("{date} {name}", "EEE MM/dd", True))

    def test_default_logical_schedule_has_one_overnight_sleep(self):
        rows = [
            {"name": "PEAK", "start": "06:00", "end": "11:00"},
            {"name": "TRANSITION", "start": "11:00", "end": "12:00"},
            {"name": "TROUGH", "start": "12:00", "end": "17:00"},
            {"name": "PERSONAL", "start": "17:00", "end": "22:00"},
            {"name": "SLEEP", "start": "22:00", "end": "06:00"},
        ]
        result = self.schedule(rows)[0]
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
        self.assertEqual(text, generator.render(text, *self.schedule(rows)))

    def test_overnight_end_other_than_six_and_midnight_end(self):
        self.assertTrue(self.schedule([{"name": "DAY", "start": "05:00", "end": "23:00"}, {"name": "NIGHT", "start": "23:00", "end": "05:00"}])[0][-1]["wraps"])
        self.assertFalse(self.schedule([{"name": "A", "start": "00:00", "end": "12:00"}, {"name": "B", "start": "12:00", "end": "24:00"}])[0][-1]["wraps"])

    def test_single_full_day(self):
        text = self.render([{"name": "ALL DAY", "start": "00:00", "end": "24:00"}])
        ET.fromstring(text)
        self.assertIn("<Expression name=\"is_s0_all_day\"><![CDATA[1 == 1]]>", text)

    def test_countdown_overnight_math(self):
        text = self.render([{"name": "DAY", "start": "06:00", "end": "22:00"}, {"name": "NIGHT", "start": "22:00", "end": "06:00"}])
        self.assertIn("1800", text)
        self.assertIn(": 180", text)
        self.assertIn("+ 1440", text)

    def test_session_aod_center_uses_sync_to_device_current_time(self):
        root = ET.fromstring(self.render(DEFAULT_SESSIONS))
        center = [time for time in root.findall(".//TimeText")
                  if time.find("Variant") is not None
                  and time.find("Variant").get("value") == "[CONFIGURATION.aod] == 3 ? 255 : 0"]
        self.assertEqual([(time.get("format"), time.get("hourFormat"), time.get("x"), time.get("y")) for time in center], [
            ("hh", "SYNC_TO_DEVICE", "4", "64"),
            ("mm", "SYNC_TO_DEVICE", "4", "222"),
        ])

    def test_session_aod_arc_formats_remaining_time_including_midnight_sleep(self):
        rows, *formats = self.schedule([
            {"name": "DAY", "start": "06:00", "end": "22:00"},
            {"name": "SLEEP", "start": "22:00", "end": "06:00"},
        ])
        root = ET.fromstring(generator.render(generator.TEMPLATE.read_text(encoding="utf-8"), rows, *formats))
        arc_templates = root.findall(".//PartText[@name='session_current_time_lower']/TextCircular/Font/Template")
        arc_templates += root.findall(".//PartText[@name='session_current_time_upper']/TextCircular/Font/Template")
        expected_sleep = generator.remaining_end(rows[-1])
        self.assertIn("+ 1440", expected_sleep)
        self.assertEqual(expected_sleep, "(1800 - (([HOUR_0_23] * 60 + [MINUTE]) < 1320 ? ([HOUR_0_23] * 60 + [MINUTE]) + 1440 : ([HOUR_0_23] * 60 + [MINUTE])))")
        self.assertEqual(len(arc_templates), 2)
        for template in arc_templates:
            self.assertEqual(template.text, "%sh%sm")
            expressions = [parameter.get("expression") for parameter in template]
            self.assertEqual(len(expressions), 2)
            self.assertTrue(expressions[0].startswith('numberFormat("00", floor('))
            self.assertTrue(expressions[0].endswith(" / 60))"))
            self.assertTrue(expressions[1].startswith('numberFormat("00", floor('))
            self.assertTrue(expressions[1].endswith(" % 60))"))
            self.assertIn("+ 1440", expressions[0])
            self.assertIn("+ 1440", expressions[1])

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
