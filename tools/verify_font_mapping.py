#!/usr/bin/env python3
"""Assert the fixed v1.0.14 font mapping and non-font WFF invariants."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
SLOT_SNAPSHOTS = {
    "0": "db6264d8e566bd140fd14642f8131a7ce10d7ca5287e9d1e0d1ee39f87cd9681",
    "1": "27c959502dfbbd256eb95a423e9554fa81c224c1c0e7dcd9ef6dd32cf9c0be58",
    "2": "d28f473095cc59f146c7838bbf07fdedf1c8f1e1c3abb2910d351bb1618b1f99",
    "3": "f593a4b6fe0f2d031bcae70dfcc0133f7e2cb1847eac7caf3651e67b73173f4c",
}
CLOCK_SNAPSHOT = "dc5876b4c79e8ab0a74230e900e02ee23a7d77b0dac155b8ed9e643767935be9"


def fonts(element: ET.Element) -> list[tuple[str | None, str | None, str | None]]:
    return [(font.get("family"), font.get("size"), font.get("letterSpacing")) for font in element.findall(".//Font")]


def serialized(element: ET.Element | None) -> bytes:
    assert element is not None
    return ET.tostring(element)


def snapshot(slot: ET.Element) -> str:
    """Hash a slot after removing only its approved top/bottom font mapping."""
    normalized = ET.fromstring(serialized(slot))
    if normalized.get("slotId") in ("2", "3"):
        for font in normalized.findall(".//Font"):
            font.attrib.pop("family", None)
            font.attrib.pop("letterSpacing", None)
    return hashlib.sha256(serialized(normalized)).hexdigest()


def main() -> int:
    current = ET.parse(WATCHFACE).getroot()
    slots = {slot.get("slotId"): slot for slot in current.findall(".//ComplicationSlot")}
    assert set(slots) == set(SLOT_SNAPSHOTS)

    assert fonts(slots["0"]) == [("orbitron_wght", "24", None), ("orbitron_wght", "24", None), ("orbitron_wght", "21", None)]
    assert fonts(slots["1"]) == [("orbitron_wght", "24", None), ("orbitron_wght", "26", None), ("orbitron_wght", "22", None), ("orbitron_wght", "27", None), ("orbitron_wght", "22", None), ("orbitron_wght", "26", None), ("orbitron_wght", "26", None)]
    for slot_id in ("2", "3"):
        expected_sizes = ["32", "18", "22", "26", "18", "22", "26"]
        assert fonts(slots[slot_id]) == [("SYNC_TO_DEVICE", size, "-0.05") for size in expected_sizes]
    assert sum(font.get("family") == "SYNC_TO_DEVICE" and font.get("letterSpacing") == "-0.05" for slot_id in ("2", "3") for font in slots[slot_id].findall(".//Font")) == 14

    # These v1.0.14 snapshots retain every slot's geometry, policies, images,
    # conditions, and other non-font behavior. Only approved font attributes
    # are normalized for slots 2 and 3 before hashing.
    for slot_id, expected in SLOT_SNAPSHOTS.items():
        assert snapshot(slots[slot_id]) == expected, f"slot {slot_id} behavior changed"

    date_lines = slots["0"].find("Complication[@type='SHORT_TEXT']").findall("PartText")
    assert [(line.get("name"), line.get("x"), line.get("y"), line.get("width"), line.get("height")) for line in date_lines] == [("date", "0", "24", "130", "38"), ("weekday", "0", "67", "130", "34")]
    assert [line.find("Localization").attrib for line in date_lines] == [{"locales": "en_US"}, {"locales": "en_US"}]
    assert date_lines[0].find(".//Parameter").get("expression") == 'icuText("MM/dd", [UTC_TIMESTAMP])'
    assert date_lines[1].find(".//Upper/Template/Parameter").get("expression") == 'icuText("EEE", [UTC_TIMESTAMP])'
    clock = current.find(".//DigitalClock")
    assert hashlib.sha256(serialized(clock)).hexdigest() == CLOCK_SNAPSHOT
    print("v1.0.14 fixed font mapping and non-font WFF snapshots verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
