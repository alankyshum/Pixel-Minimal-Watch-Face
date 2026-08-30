#!/usr/bin/env python3
"""Assert the v1.0.11 Noto Sans HK top/bottom experiment against HEAD."""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
BASELINE = "HEAD:watchface/src/main/res/raw/watchface.xml"


def fonts(element: ET.Element) -> list[tuple[str | None, str | None]]:
    return [(font.get("family"), font.get("size")) for font in element.findall(".//Font")]


def serialized(element: ET.Element | None) -> bytes:
    assert element is not None
    return ET.tostring(element)


def main() -> int:
    baseline = ET.fromstring(subprocess.check_output(["git", "show", BASELINE], cwd=ROOT))
    current = ET.parse(WATCHFACE).getroot()
    old_slots = {slot.get("slotId"): slot for slot in baseline.findall(".//ComplicationSlot")}
    new_slots = {slot.get("slotId"): slot for slot in current.findall(".//ComplicationSlot")}
    old_fonts = {slot_id: fonts(slot) for slot_id, slot in old_slots.items()}

    assert fonts(new_slots["0"]) == [("orbitron_wght", "24"), ("orbitron_wght", "24"), ("orbitron_wght", "21"), ("orbitron_wght", "24")]
    assert fonts(new_slots["1"]) == [("orbitron_wght", "24"), ("orbitron_wght", "26"), ("orbitron_wght", "22"), ("orbitron_wght", "27"), ("orbitron_wght", "22"), ("orbitron_wght", "26"), ("orbitron_wght", "26")]
    assert fonts(new_slots["2"]) == [("noto_sans_hk_wght", size) for _, size in old_fonts["2"]]
    assert fonts(new_slots["3"]) == [("noto_sans_hk_wght", size) for _, size in old_fonts["3"]]

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
        # Compare all condition behavior after removing only the permitted family mapping.
        for condition in old.findall(".//Condition"):
            for font in condition.findall(".//Font"):
                font.attrib.pop("family", None)
        for condition in new.findall(".//Condition"):
            for font in condition.findall(".//Font"):
                font.attrib.pop("family", None)
        assert [ET.tostring(node) for node in old.findall(".//Condition")] == [ET.tostring(node) for node in new.findall(".//Condition")], f"slot {slot_id} condition behavior changed"

    old_clock = baseline.find(".//DigitalClock")
    new_clock = current.find(".//DigitalClock")
    assert old_clock is not None and new_clock is not None
    assert ET.tostring(old_clock) == ET.tostring(new_clock)
    print("v1.0.11 Noto Sans HK top/bottom mapping and protected WFF subtrees verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
