#!/usr/bin/env python3
"""Fail-closed verification for Nova Mono, WFF v2 arcs, and hour animation."""

from __future__ import annotations

import hashlib
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
NOVA_MONO = ROOT / "watchface/src/main/res/font/nova_mono.ttf"
NOVA_MONO_SHA256 = "648eadb6648c0801b186d3dcef60ee6aa84a791b1e09c726935c0712508b4807"
HOUR_INDICATOR_FORMULA = "[HOUR_0_11] * 30 + [MINUTE] * 0.5"
UNRELATED_SLOT_SNAPSHOTS = {
    "0": "db6264d8e566bd140fd14642f8131a7ce10d7ca5287e9d1e0d1ee39f87cd9681",
    "1": "27c959502dfbbd256eb95a423e9554fa81c224c1c0e7dcd9ef6dd32cf9c0be58",
    "2": "f996e4d58bdbac4392a0889bbbb1194b8aee660d242a57cc0623028b9ef25c36",
}


def snapshot(slot: ET.Element) -> str:
    """Pin unrelated slot behavior while allowing this change's font work."""
    normalized = ET.fromstring(ET.tostring(slot))
    for font in normalized.findall(".//Font"):
        font.attrib.pop("letterSpacing", None)
        if normalized.get("slotId") in {"2", "4"}:
            font.attrib.pop("family", None)
    return hashlib.sha256(ET.tostring(normalized)).hexdigest()


def part_for(slot: ET.Element, text: ET.Element) -> ET.Element:
    return next(part for part in slot.iter("PartText") if text in list(part))


def global_center(slot: ET.Element, part: ET.Element, text: ET.Element) -> tuple[float, float]:
    return (float(slot.get("x")) + float(part.get("x")) + float(text.get("centerX")),
            float(slot.get("y")) + float(part.get("y")) + float(text.get("centerY")))


def sweep_angles(text: ET.Element) -> list[float]:
    """Return endpoints and cardinal extrema that fall on this WFF sweep."""
    start, end = map(float, (text.get("startAngle"), text.get("endAngle")))
    if text.get("direction") == "CLOCKWISE":
        end += 360 if end < start else 0
        return [start, end] + [a for a in (0, 90, 180, 270, 360) if start <= a <= end]
    start += 360 if start < end else 0
    return [start, end] + [a for a in (0, 90, 180, 270, 360) if end <= a <= start]


def path_bounds(part: ET.Element, text: ET.Element) -> None:
    """The complete circular sweep plus 26px ink stays in its individual raster."""
    r, ink = float(text.get("width")) / 2, 13
    cx, cy = float(text.get("centerX")), float(text.get("centerY"))
    points = [(r * math.sin(math.radians(a)), -r * math.cos(math.radians(a))) for a in sweep_angles(text)]
    assert min(cx + x - ink for x, _ in points) >= 0
    assert max(cx + x + ink for x, _ in points) <= float(part.get("width"))
    assert min(cy + y - ink for _, y in points) >= 0
    assert max(cy + y + ink for _, y in points) <= float(part.get("height"))


def parameters(text: ET.Element) -> list[str]:
    return [p.get("expression", "") for p in text.findall("Font/Template/Parameter")]


def normal_options(branch: ET.Element) -> list[ET.Element]:
    options = branch.findall(".//ListOption")
    assert [o.get("id") for o in options] == ["18", "22", "26"]
    return options


def assert_paths(slot: ET.Element, options: list[ET.Element], *, one_line: bool = False, split: bool = False) -> None:
    for option in options:
        paths = option.findall(".//TextCircular")
        assert len(paths) == (1 if one_line else 2)
        for text in paths:
            part = part_for(slot, text)
            assert len(part.findall("TextCircular")) == 1
            assert global_center(slot, part, text) == (225.0, 225.0)
            assert text.get("direction") == "COUNTER_CLOCKWISE"
            assert text.get("align") == "CENTER" and text.get("ellipsis") == "TRUE"
            assert float(text.find("Font").get("size")) in {18, 22, 26}
            path_bounds(part, text)
        if one_line:
            assert (paths[0].get("width"), paths[0].get("startAngle"), paths[0].get("endAngle")) == ("410", "251.5", "108.5")
            assert parameters(paths[0]) == ["subText([COMPLICATION.TEXT],0,23)"]
        else:
            assert [(p.get("width"), p.get("startAngle"), p.get("endAngle")) for p in paths] == [("320", "238.5", "121.5"), ("410", "251.5", "108.5")]
            expected = (["subText([COMPLICATION.TEXT],0,18)"], ["subText([COMPLICATION.TEXT],18,41)"]) if split else (["subText([COMPLICATION.TEXT],0,20)"], ["subText([COMPLICATION.TITLE],0,23)"])
            assert [parameters(p) for p in paths] == list(expected)
            if split:
                assert paths[0].find("Font/Template").text == "%s-"


def main() -> int:
    if sys.flags.optimize:
        raise RuntimeError("verify_font_mapping.py must not run with Python optimization enabled")
    root = ET.parse(WATCHFACE).getroot()
    assert hashlib.sha256(NOVA_MONO.read_bytes()).hexdigest() == NOVA_MONO_SHA256
    assert all(e.get("direction") in {"CLOCKWISE", "COUNTER_CLOCKWISE"} for e in root.iter() if e.get("direction"))
    clock_fonts = root.findall(".//DigitalClock//Font")
    assert len(clock_fonts) == 4 and all(f.attrib == {"color":"#fafafa", "size":"112", "family":"nova_mono", "weight":"NORMAL"} for f in clock_fonts)
    slots = {slot.get("slotId"): slot for slot in root.findall(".//ComplicationSlot")}
    assert set(slots) == {"0", "1", "2", "3", "4"}
    for slot_id, expected in UNRELATED_SLOT_SNAPSHOTS.items():
        assert snapshot(slots[slot_id]) == expected, f"unrelated slot {slot_id} behavior changed"
    for slot_id in ("0", "1"):
        assert all(font.get("letterSpacing") == "-0.05" for font in slots[slot_id].findall(".//PartText//Font"))
    assert all(font.get("letterSpacing") == "-0.05" for font in root.findall(".//PartText//Font"))

    indicator = root.find(".//Scene/BooleanConfiguration[@id='secIndicator']/BooleanOption/PartDraw")
    assert indicator is not None and indicator.find("Variant").attrib == {"mode":"AMBIENT", "target":"alpha", "value":"0"}
    transform = indicator.find("Transform")
    assert transform is not None and transform.get("value") == HOUR_INDICATOR_FORMULA
    assert {key: indicator.get(key) for key in ("x", "y", "pivotX", "pivotY")} == {
        "x": "225", "y": "1", "pivotX": "0", "pivotY": "0.5"
    }
    indicator_xml = ET.tostring(indicator, encoding="unicode")
    assert "SECOND" not in indicator_xml
    for clock_time, hour, minute, expected_angle in (
        ("09:00", 9, 0, 270),
        ("09:30", 9, 30, 285),
        ("09:59", 9, 59, 299.5),
        ("11:59", 11, 59, 359.5),
        ("12:00", 0, 0, 0),
    ):
        assert hour * 30 + minute * 0.5 == expected_angle, clock_time
    assert transform.find("Animation").attrib == {"duration":"0.4", "repeat":"0", "angleDirection":"CLOCKWISE"}

    slot = slots["3"]
    shape = slot.find("BoundingArc")
    assert shape is not None and shape.attrib == {"centerX":"201", "centerY":"-75", "width":"365", "height":"365", "startAngle":"259", "endAngle":"101", "direction":"COUNTER_CLOCKWISE", "thickness":"85"}
    # Arc A: r205 251.5→108.5°; Arc B: r160 238.5→121.5°.
    assert 205 - 20 - (160 + 20) == 5
    # A single BoundingArc cannot encode the gap, but must crop all actual ink.
    crop_inner, crop_outer = 182.5 - 42.5, 182.5 + 42.5
    assert crop_inner <= 160 - 20 and crop_outer >= 205 + 20
    # Full 13px-ink path containment, crop containment, clock/edge safety, and AOD safety.
    clock = root.find(".//DigitalClock")
    assert clock is not None
    clock_bottom = float(clock.get("y")) + max(float(t.get("y")) + float(t.get("height")) for t in clock.findall("TimeText"))
    for radius, start, end in ((160, 238.5, 121.5), (205, 251.5, 108.5)):
        for angle in (start, end):
            assert 140 <= radius - 13 and radius + 13 <= 225
            assert 101 <= angle <= 259
        assert 225 + radius - 13 > clock_bottom
    # Arc A's crop has at least a conservative 13px tangential endpoint margin.
    angular_margin = math.degrees(math.asin(13 / 205))
    assert 259 - 251.5 >= angular_margin and 108.5 - 101 >= angular_margin
    assert 225 + 205 + 13 <= float(root.get("height"))
    # Wider paths deliberately approach the side visuals. Verify what is actually
    # rendered instead: every 13px ink bound is in the slot crop and on-screen.
    for radius, start, end in ((160, 238.5, 121.5), (205, 251.5, 108.5)):
        for angle in sweep_angles(ET.fromstring(
            f'<TextCircular width="{radius * 2}" startAngle="{start}" endAngle="{end}" direction="COUNTER_CLOCKWISE"/>'
        )):
            x = 225 + radius * math.sin(math.radians(angle))
            y = 225 - radius * math.cos(math.radians(angle))
            assert 0 <= x - 13 and x + 13 <= 450 and 0 <= y - 13 and y + 13 <= 450
    assert slot.find("Variant").attrib == {"mode":"AMBIENT", "target":"alpha", "value":"[CONFIGURATION.aod] == 0 ? 165 : 0"}
    battery_path = slot.find("Complication[@type='SHORT_TEXT']/Condition/Compare/PartText/TextCircular")
    assert battery_path is not None
    assert battery_path.attrib == {"centerX":"212", "centerY":"-52", "width":"410", "height":"410", "startAngle":"251.5", "endAngle":"108.5", "direction":"COUNTER_CLOCKWISE", "align":"CENTER", "ellipsis":"TRUE"}
    assert parameters(battery_path) == ["[BATTERY_PERCENT]", "subText([COMPLICATION.TEXT],1,4)==100?100:(subText([COMPLICATION.TEXT],1,3))"]
    short = slot.find("Complication[@type='SHORT_TEXT']/Condition/Default/Condition")
    assert short is not None and (short.find("Expressions/Expression").text or "") == "textLength([COMPLICATION.TITLE]) > 0"
    assert_paths(slot, normal_options(short.find("Compare")))
    assert_paths(slot, normal_options(short.find("Default")), one_line=True)
    long_condition = slot.find("Complication[@type='LONG_TEXT']/Condition")
    assert long_condition is not None
    expressions = ET.tostring(long_condition.find("Expressions"), encoding="unicode")
    assert '"---"' in expressions and "textLength([COMPLICATION.TITLE]) == 0" in expressions and "!= null" not in expressions
    nested = long_condition.find("Default/Condition")
    assert nested is not None
    assert_paths(slot, normal_options(nested.find("Compare")))
    over_budget = nested.find("Default/Condition")
    assert over_budget is not None
    assert "textLength([COMPLICATION.TEXT]) > 23" in (over_budget.find("Expressions/Expression").text or "")
    assert_paths(slot, normal_options(over_budget.find("Compare")), split=True)
    assert_paths(slot, normal_options(over_budget.find("Default")), one_line=True)

    # The notification icon's full raster must remain inside slot 3's BoundingArc,
    # not merely within the rectangular slot.
    notification = long_condition.find("Compare/PartImage")
    assert notification is not None
    center_x = float(slot.get("x")) + float(shape.get("centerX"))
    center_y = float(slot.get("y")) + float(shape.get("centerY"))
    inner, outer = 182.5 - 42.5, 182.5 + 42.5
    for x in (float(notification.get("x")), float(notification.get("x")) + float(notification.get("width"))):
        for y in (float(notification.get("y")), float(notification.get("y")) + float(notification.get("height"))):
            dx, dy = float(slot.get("x")) + x - center_x, float(slot.get("y")) + y - center_y
            radius = math.hypot(dx, dy)
            angle = math.degrees(math.atan2(dx, -dy)) % 360
            assert inner <= radius <= outer and 101 <= angle <= 259

    # Slot 4 is independently named and checked rather than treated as a snapshot.
    slot4 = slots["4"]
    assert slot4.find("DefaultProviderPolicy") is None
    assert {group.get("name") for group in slot4.findall(".//Group")} == {"second_top_short_text", "second_top_long_text"}
    slot4_shape = slot4.find("BoundingArc")
    assert slot4_shape is not None
    slot4_radius, slot4_half_thickness = float(slot4_shape.get("width")) / 2, float(slot4_shape.get("thickness")) / 2
    for text in slot4.findall(".//TextCircular"):
        part = part_for(slot4, text)
        assert global_center(slot4, part, text) == (225.0, 225.0)
        assert text.get("direction") == "CLOCKWISE"
        text_radius = float(text.get("width")) / 2
        assert slot4_radius - slot4_half_thickness <= text_radius - 13
        assert text_radius + 13 <= slot4_radius + slot4_half_thickness
        path_bounds(part, text)
    print("Nova Mono, safe adaptive arc, minute-proportional hour animation, and safety invariants verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
