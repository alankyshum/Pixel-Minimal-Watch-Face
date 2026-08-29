#!/usr/bin/env python3
"""Regression tests for the README configuration inventory generator."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate_readme_config", ROOT / "tools/generate_readme_config.py")
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class GenerateReadmeConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.paths = (generator.ROOT, generator.README, generator.WATCHFACE, generator.STRINGS)
        generator.ROOT = root
        generator.README = root / "README.md"
        generator.WATCHFACE = root / "watchface.xml"
        generator.STRINGS = root / "strings.xml"
        generator.README.write_text(generator.BEGIN + "\nold\n" + generator.END + "\n")
        generator.STRINGS.write_text("<resources><string name='label'>Label</string><string name='option'>Option</string><string name='slot'>Slot</string></resources>")
        generator.WATCHFACE.write_text("""<WatchFace><UserConfigurations>
            <ListConfiguration id='setting' displayName='label' defaultValue='a'><ListOption id='a' displayName='option'/></ListConfiguration>
            <Flavors defaultValue='base'><Flavor id='base' displayName='Base'><Configuration id='setting' optionId='a'/></Flavor></Flavors>
            </UserConfigurations><Scene><ComplicationSlot slotId='0' displayName='slot' width='1' height='1' x='0' y='0' supportedTypes='EMPTY'><DefaultProviderPolicy/></ComplicationSlot></Scene></WatchFace>""")

    def tearDown(self) -> None:
        generator.ROOT, generator.README, generator.WATCHFACE, generator.STRINGS = self.paths
        self.directory.cleanup()

    def test_renders_and_replaces_marker_content(self) -> None:
        rendered = generator.replace_generated(generator.README.read_text(), generator.inventory())
        self.assertIn("| `setting` | Label | list | `a` | `a` Option |", rendered)
        self.assertIn("| `0` | Slot | 1 × 1 at 0,0 | `EMPTY` |", rendered)

    def test_rejects_invalid_default(self) -> None:
        generator.WATCHFACE.write_text(generator.WATCHFACE.read_text().replace("defaultValue='a'", "defaultValue='missing'", 1))
        with self.assertRaisesRegex(ValueError, "invalid default"):
            generator.inventory()

    def test_rejects_duplicate_option(self) -> None:
        generator.WATCHFACE.write_text(generator.WATCHFACE.read_text().replace("</ListConfiguration>", "<ListOption id='a' displayName='missing'/></ListConfiguration>"))
        with self.assertRaisesRegex(ValueError, "duplicate/missing option"):
            generator.inventory()

    def test_rejects_missing_string_resource(self) -> None:
        generator.WATCHFACE.write_text(generator.WATCHFACE.read_text().replace("displayName='option'", "displayName='missing'"))
        with self.assertRaisesRegex(ValueError, "missing string resource"):
            generator.inventory()

    def test_rejects_malformed_xml(self) -> None:
        generator.WATCHFACE.write_text("<WatchFace>")
        with self.assertRaisesRegex(ValueError, "malformed XML"):
            generator.inventory()

    def test_rejects_missing_or_duplicate_markers(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            generator.replace_generated(generator.BEGIN + generator.BEGIN + generator.END, "content\n")

    def test_check_mode_detects_stale_readme(self) -> None:
        original_argv = sys.argv
        try:
            sys.argv = ["generate_readme_config.py"]
            self.assertEqual(generator.main(), 0)
            sys.argv = ["generate_readme_config.py", "--check"]
            self.assertEqual(generator.main(), 0)
            generator.README.write_text(generator.README.read_text().replace("### User configurations", "### stale configurations"))
            self.assertEqual(generator.main(), 1)
        finally:
            sys.argv = original_argv


if __name__ == "__main__":
    unittest.main()
