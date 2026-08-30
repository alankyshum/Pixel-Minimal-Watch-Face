#!/usr/bin/env python3
"""Assert the fixed v1.0.14 font mapping and non-font WFF invariants."""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
SLOT_SNAPSHOTS = {
    "0": "db6264d8e566bd140fd14642f8131a7ce10d7ca5287e9d1e0d1ee39f87cd9681",
    "1": "27c959502dfbbd256eb95a423e9554fa81c224c1c0e7dcd9ef6dd32cf9c0be58",
    "2": "f996e4d58bdbac4392a0889bbbb1194b8aee660d242a57cc0623028b9ef25c36",
    "3": "f593a4b6fe0f2d031bcae70dfcc0133f7e2cb1847eac7caf3651e67b73173f4c",
    "4": "fb10c55af69d5eda2d4c5a130198352e009f5032f2dfa2739e46d41244de76a6",
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
    if normalized.get("slotId") in ("2", "3", "4"):
        for font in normalized.findall(".//Font"):
            font.attrib.pop("family", None)
            font.attrib.pop("letterSpacing", None)
    return hashlib.sha256(serialized(normalized)).hexdigest()


def bounding_arc(slot: ET.Element) -> dict[str, float | str]:
    """Parse a slot-local BoundingArc into global-center arc geometry."""
    arc = slot.find("BoundingArc")
    assert arc is not None, f"slot {slot.get('slotId')} needs BoundingArc"
    return {
        "center_x": float(slot.attrib["x"]) + float(arc.attrib["centerX"]),
        "center_y": float(slot.attrib["y"]) + float(arc.attrib["centerY"]),
        "radius": float(arc.attrib["width"]) / 2,
        "height": float(arc.attrib["height"]),
        "start": float(arc.attrib["startAngle"]),
        "end": float(arc.attrib["endAngle"]),
        "thickness": float(arc.attrib["thickness"]),
        "direction": arc.attrib["direction"],
    }


def angle_in_arc(angle: float, arc: dict[str, float | str]) -> bool:
    """Return whether an angle lies in this clockwise arc (including endpoints)."""
    start, end = float(arc["start"]), float(arc["end"])
    return start <= end and start <= angle <= end or start > end and (angle >= start or angle <= end)


def max_configured_top_font_size(slot: ET.Element) -> float:
    """Read the largest option in the shared top-complication size setting."""
    sizes = [
        float(font.attrib["size"])
        for config in slot.findall(".//ListConfiguration[@id='topComplicationFontSize']")
        for font in config.findall(".//Font")
    ]
    assert sizes, f"slot {slot.get('slotId')} has no top font-size configuration"
    return max(sizes)


def path_ink_margin(text: ET.Element, slot: ET.Element) -> float:
    """Cover the shared top font setting and any inline image on a text path."""
    font_half_size = max(float(font.attrib["size"]) / 2 for font in text.findall(".//Font"))
    inline_half_size = max(
        (max(float(image.attrib["width"]), float(image.attrib["height"])) / 2 for image in text.findall(".//InlineImage")),
        default=0.0,
    )
    return max(max_configured_top_font_size(slot) / 2, font_half_size, inline_half_size)


def assert_box_in_arc(box: ET.Element, slot: ET.Element, arc: dict[str, float | str]) -> None:
    """Assert every global corner of an axis-aligned PartImage is in its BoundingArc."""
    slot_x, slot_y = float(slot.attrib["x"]), float(slot.attrib["y"])
    x, y = slot_x + float(box.attrib["x"]), slot_y + float(box.attrib["y"])
    for point_x, point_y in ((x, y), (x + float(box.attrib["width"]), y), (x, y + float(box.attrib["height"])), (x + float(box.attrib["width"]), y + float(box.attrib["height"]))):
        dx, dy = point_x - float(arc["center_x"]), point_y - float(arc["center_y"])
        radius = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dx, -dy)) % 360
        assert float(arc["radius"]) - float(arc["thickness"]) / 2 <= radius <= float(arc["radius"]) + float(arc["thickness"]) / 2
        assert angle_in_arc(angle, arc)


def main() -> int:
    current = ET.parse(WATCHFACE).getroot()
    slots = {slot.get("slotId"): slot for slot in current.findall(".//ComplicationSlot")}
    assert set(slots) == set(SLOT_SNAPSHOTS)

    assert fonts(slots["0"]) == [("orbitron_wght", "24", None), ("orbitron_wght", "24", None), ("orbitron_wght", "21", None)]
    assert fonts(slots["1"]) == [("orbitron_wght", "24", None), ("orbitron_wght", "26", None), ("orbitron_wght", "22", None), ("orbitron_wght", "27", None), ("orbitron_wght", "22", None), ("orbitron_wght", "26", None), ("orbitron_wght", "26", None)]
    for slot_id in ("2", "3"):
        expected_sizes = ["32", "18", "22", "26", "18", "22", "26"]
        assert fonts(slots[slot_id]) == [("SYNC_TO_DEVICE", size, "-0.05") for size in expected_sizes]
    assert slots["4"].attrib == {
        "slotId": "4", "displayName": "slot_4", "supportedTypes": "SHORT_TEXT LONG_TEXT EMPTY",
        "x": "97", "y": "57", "width": "256", "height": "80",
    }
    assert slots["4"].find("DefaultProviderPolicy") is None
    assert slots["2"].attrib["height"] == "112"
    outer_arc, inner_arc = bounding_arc(slots["2"]), bounding_arc(slots["4"])
    assert outer_arc == {
        "center_x": 225.0, "center_y": 225.0, "radius": 205.0, "height": 410.0,
        "start": 295.0, "end": 65.0, "thickness": 40.0, "direction": "CLOCKWISE",
    }
    assert inner_arc == {
        "center_x": 225.0, "center_y": 225.0, "radius": 160.0, "height": 320.0,
        "start": 305.0, "end": 55.0, "thickness": 40.0, "direction": "CLOCKWISE",
    }
    assert fonts(slots["4"]) == [("SYNC_TO_DEVICE", size, "-0.05") for size in ["18", "22", "26"] * 2]
    for slot_id, arc in (("2", outer_arc), ("4", inner_arc)):
        for text in slots[slot_id].findall(".//TextCircular"):
            part = next(part for part in slots[slot_id].iter("PartText") if part.find(".//TextCircular") is text)
            diameter = float(text.attrib["width"])
            assert diameter == float(text.attrib["height"])
            slot_x, slot_y = float(slots[slot_id].attrib["x"]), float(slots[slot_id].attrib["y"])
            center_x = slot_x + float(part.attrib["x"]) + float(text.attrib["centerX"])
            center_y = slot_y + float(part.attrib["y"]) + float(text.attrib["centerY"])
            radius = diameter / 2
            radial_ink_margin = path_ink_margin(text, slots[slot_id])
            angular_ink_margin = math.degrees(math.asin(radial_ink_margin / radius))
            assert (center_x, center_y) == (arc["center_x"], arc["center_y"])
            assert radius + radial_ink_margin <= arc["radius"] + arc["thickness"] / 2
            assert radius - radial_ink_margin >= arc["radius"] - arc["thickness"] / 2
            assert arc["start"] <= float(text.attrib["startAngle"]) - angular_ink_margin
            assert arc["end"] >= float(text.attrib["endAngle"]) + angular_ink_margin

    for complication_type, expected_template, expected_parameters in (
        ("SHORT_TEXT", "%s", ["[COMPLICATION.TEXT]"]),
        ("LONG_TEXT", "%s %s", ["[COMPLICATION.TEXT]", "[COMPLICATION.TITLE]"]),
    ):
        slot_4_texts = slots["4"].findall(f"Complication[@type='{complication_type}']//TextCircular")
        assert len(slot_4_texts) == 3, f"slot 4 {complication_type} needs all three font-size branches"
        for text in slot_4_texts:
            assert text.attrib == {
            "centerX": "225", "centerY": "225", "width": "320", "height": "320",
            "startAngle": "315", "endAngle": "45", "direction": "CLOCKWISE", "align": "CENTER",
            "ellipsis": "TRUE",
        }
            template = text.find("Font/Template")
            assert template is not None and "".join(template.itertext()).strip() == expected_template
            assert [parameter.get("expression") for parameter in template.findall("Parameter")] == expected_parameters

            part = next(part for part in slots["4"].iter("PartText") if part.find(".//TextCircular") is text)
            diameter = float(text.attrib["width"])
            radius = diameter / 2
            slot_x, slot_y = float(slots["4"].attrib["x"]), float(slots["4"].attrib["y"])
            center_x = slot_x + float(part.attrib["x"]) + float(text.attrib["centerX"])
            center_y = slot_y + float(part.attrib["y"]) + float(text.attrib["centerY"])
            angles = (float(text.attrib["startAngle"]), 0.0, float(text.attrib["endAngle"]))
            arc_points = [
                (center_x + radius * math.sin(math.radians(angle)), center_y - radius * math.cos(math.radians(angle)))
                for angle in angles
            ]
            assert (center_x, center_y) == (inner_arc["center_x"], inner_arc["center_y"])
            # Keep the 26px glyph ink above the side complication circles.
            assert all(y + 13 < float(slots["0"].attrib["y"]) for _, y in arc_points)

    slot_2_images = slots["2"].findall(".//PartImage")
    assert len(slot_2_images) == 1
    icon = slot_2_images[0]
    assert icon.attrib == {"width": "32", "height": "32", "x": "185", "y": "4", "tintColor": "[CONFIGURATION.themeColor.1]"}
    assert icon.find("Image").attrib == {"resource": "[COMPLICATION.MONOCHROMATIC_IMAGE_AMBIENT]"}
    assert_box_in_arc(icon, slots["2"], outer_arc)
    combined_battery = slots["2"].find("Complication[@type='SHORT_TEXT']/Condition/Compare")
    battery_text = combined_battery.find("PartText/TextCircular")
    assert battery_text is not None and battery_text.attrib == {
        "centerX": "225", "centerY": "225", "width": "410", "height": "410",
        "startAngle": "305", "endAngle": "55", "direction": "CLOCKWISE", "align": "CENTER",
        "ellipsis": "TRUE",
    }
    battery_font = battery_text.find("Font")
    assert battery_font is not None and battery_font.attrib == {
        "color": "[CONFIGURATION.themeColor.0]", "family": "SYNC_TO_DEVICE", "size": "32", "letterSpacing": "-0.05",
    }
    battery_template = battery_font.find("Template")
    assert battery_template is not None and "".join(battery_template.itertext()).strip() == "%s · %s"
    assert [parameter.attrib["expression"] for parameter in battery_template.findall("Parameter")] == [
        "[BATTERY_PERCENT]", "subText([COMPLICATION.TEXT],1,4)==100?100:(subText([COMPLICATION.TEXT],1,3))",
    ]
    assert not battery_text.findall(".//InlineImage")
    for slot_id in ("2", "4"):
        for part in slots[slot_id].findall(".//PartText"):
            assert part.find("TextCircular") is not None, f"slot {slot_id} has non-arc text that BoundingArc could crop"
        for image in slots[slot_id].findall(".//PartImage"):
            assert_box_in_arc(image, slots[slot_id], bounding_arc(slots[slot_id]))

    # The bands are concentric: inner=140..180, outer=185..225, a 5px gap.
    # WFF BoundingArc is authoritative for selection/crop.
    assert inner_arc["radius"] + inner_arc["thickness"] / 2 < outer_arc["radius"] - outer_arc["thickness"] / 2
    assert outer_arc["radius"] - outer_arc["thickness"] / 2 - (inner_arc["radius"] + inner_arc["thickness"] / 2) >= 5
    assert sum(font.get("family") == "SYNC_TO_DEVICE" and font.get("letterSpacing") == "-0.05" for slot_id in ("2", "3", "4") for font in slots[slot_id].findall(".//Font")) == 20

    # These snapshots retain the pre-existing slots' geometry, policies,
    # images, conditions, and other non-font behavior. Only approved font
    # attributes are normalized for slots 2, 3, and 4 before hashing.
    for slot_id, expected in SLOT_SNAPSHOTS.items():
        assert snapshot(slots[slot_id]) == expected, f"slot {slot_id} behavior changed"

    date_lines = slots["0"].find("Complication[@type='SHORT_TEXT']").findall("PartText")
    assert [(line.get("name"), line.get("x"), line.get("y"), line.get("width"), line.get("height")) for line in date_lines] == [("date", "0", "24", "130", "38"), ("weekday", "0", "67", "130", "34")]
    assert [line.find("Localization").attrib for line in date_lines] == [{"locales": "en_US"}, {"locales": "en_US"}]
    assert date_lines[0].find(".//Parameter").get("expression") == 'icuText("MM/dd", [UTC_TIMESTAMP])'
    assert date_lines[1].find(".//Upper/Template/Parameter").get("expression") == 'icuText("EEE", [UTC_TIMESTAMP])'
    clock = current.find(".//DigitalClock")
    assert hashlib.sha256(serialized(clock)).hexdigest() == CLOCK_SNAPSHOT
    print("fixed font mapping and non-font WFF snapshots verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
