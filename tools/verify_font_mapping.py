#!/usr/bin/env python3
"""Assert the v1.0.13 literal -0.5em system-font top/bottom mapping against HEAD."""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
BASELINE = "HEAD:watchface/src/main/res/raw/watchface.xml"


def fonts(element: ET.Element) -> list[tuple[str | None, str | None, str | None]]:
    return [(font.get("family"), font.get("size"), font.get("letterSpacing")) for font in element.findall(".//Font")]


def serialized(element: ET.Element | None) -> bytes:
    assert element is not None
    return ET.tostring(element)


def main() -> int:
    baseline = ET.fromstring(subprocess.check_output(["git", "show", BASELINE], cwd=ROOT))
    current = ET.parse(WATCHFACE).getroot()
    old_slots = {slot.get("slotId"): slot for slot in baseline.findall(".//ComplicationSlot")}
    new_slots = {slot.get("slotId"): slot for slot in current.findall(".//ComplicationSlot")}
    old_fonts = {slot_id: fonts(slot) for slot_id, slot in old_slots.items()}

    assert fonts(new_slots["0"]) == [("orbitron_wght", "24", None), ("orbitron_wght", "24", None), ("orbitron_wght", "21", None)]
    assert fonts(new_slots["1"]) == [("orbitron_wght", "24", None), ("orbitron_wght", "26", None), ("orbitron_wght", "22", None), ("orbitron_wght", "27", None), ("orbitron_wght", "22", None), ("orbitron_wght", "26", None), ("orbitron_wght", "26", None)]
    for slot_id in ("2", "3"):
        assert len(old_fonts[slot_id]) == 7
        assert fonts(new_slots[slot_id]) == [("SYNC_TO_DEVICE", size, "-0.5") for _, size, _ in old_fonts[slot_id]]
    assert sum(font.get("family") == "SYNC_TO_DEVICE" and font.get("letterSpacing") == "-0.5" for slot_id in ("2", "3") for font in new_slots[slot_id].findall(".//Font")) == 14

    # Geometry, configurations, provider policies, and image/notification branches are byte-stable.
    for slot_id in ("0", "1", "2", "3"):
        old, new = old_slots[slot_id], new_slots[slot_id]
        assert old.attrib == new.attrib, f"slot {slot_id} geometry/configuration changed"
        for node in ("DefaultProviderPolicy", "BoundingOval", "BoundingRoundBox"):
            old_node, new_node = old.find(node), new.find(node)
            assert (old_node is None) == (new_node is None), (slot_id, node)
            if old_node is not None:
                assert serialized(old_node) == serialized(new_node), (slot_id, node)
        old_images = [ET.tostring(node) for node in old.findall(".//PartImage")]
        new_images = [ET.tostring(node) for node in new.findall(".//PartImage")]
        assert old_images == new_images, f"slot {slot_id} image branch changed"
        # Slot 0's SHORT_TEXT rendering is intentionally provider-independent date text.
        if slot_id == "0":
            old_short = old.find("Complication[@type='SHORT_TEXT']")
            new_short = new.find("Complication[@type='SHORT_TEXT']")
            assert old_short is not None and new_short is not None
            old_without_short = ET.fromstring(serialized(old))
            new_without_short = ET.fromstring(serialized(new))
            old_without_short.remove(old_without_short.find("Complication[@type='SHORT_TEXT']"))
            new_without_short.remove(new_without_short.find("Complication[@type='SHORT_TEXT']"))
            assert serialized(old_without_short) == serialized(new_without_short)
            assert serialized(old_short.find("PartDraw")) == serialized(new_short.find("PartDraw"))
            date_lines = new_short.findall("PartText")
            assert len(date_lines) == 2
            assert [(line.get("name"), line.get("x"), line.get("y"), line.get("width"), line.get("height")) for line in date_lines] == [
                ("date", "0", "24", "130", "38"),
                ("weekday", "0", "67", "130", "34"),
            ]
            assert [fonts(line) for line in date_lines] == [[("orbitron_wght", "24", None)], [("orbitron_wght", "21", None)]]
            assert [line.find("Localization").attrib for line in date_lines] == [{"locales": "en_US"}, {"locales": "en_US"}]
            assert date_lines[0].find(".//Parameter").get("expression") == 'icuText("MM/dd", [UTC_TIMESTAMP])'
            assert date_lines[1].find(".//Upper/Template/Parameter").get("expression") == 'icuText("EEE", [UTC_TIMESTAMP])'
            assert new_short.findall(".//Condition") == []
            continue
        # Compare all condition behavior after removing only permitted font mappings.
        for condition in old.findall(".//Condition"):
            for font in condition.findall(".//Font"):
                font.attrib.pop("family", None)
                font.attrib.pop("letterSpacing", None)
        for condition in new.findall(".//Condition"):
            for font in condition.findall(".//Font"):
                font.attrib.pop("family", None)
                font.attrib.pop("letterSpacing", None)
        assert [ET.tostring(node) for node in old.findall(".//Condition")] == [ET.tostring(node) for node in new.findall(".//Condition")], f"slot {slot_id} condition behavior changed"

    old_clock = baseline.find(".//DigitalClock")
    new_clock = current.find(".//DigitalClock")
    assert old_clock is not None and new_clock is not None
    assert ET.tostring(old_clock) == ET.tostring(new_clock)
    print("v1.0.13 numeric slot-0 date and literal -0.5em system-font top/bottom mappings verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
