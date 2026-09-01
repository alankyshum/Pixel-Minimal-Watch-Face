#!/usr/bin/env python3
"""Fail-closed verification for Nova Mono, WFF v2 arcs, hour animation, and AOD sessions."""

from __future__ import annotations

import hashlib
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
NOVA_MONO = ROOT / "watchface/src/main/res/font/nova_mono.ttf"
NOVA_MONO_SHA256 = "648eadb6648c0801b186d3dcef60ee6aa84a791b1e09c726935c0712508b4807"
HOUR_INDICATOR_FORMULA = "[HOUR_0_11] * 30 + [MINUTE] * 0.5"
# The outer countdown arc establishes the largest intentional AOD ink radius:
# its 215px path radius plus its 1.5px stroke. Text rasters must fit inside it.
FACE_RADIUS = 225.0
SESSION_SAFE_INK_RADIUS = 216.5
# Deliberately independent of the WFF expressions below: this is the product
# specification against which their *evaluated* results are checked.
SESSION_SPEC = (
    (0, 6, "SLEEP", 360, None),
    (6, 11, "PEAK", 660, 330),
    (11, 12, "TRANSITION", 720, 360),
    (12, 17, "TROUGH", 1020, 150),
    (17, 22, "PERSONAL", 1320, 300),
    (22, 24, "SLEEP", 1800, None),
)
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


def space_search_expression(*, line: str) -> str:
    """The WFF-v2-only descending ASCII-space search used by LONG_TEXT paths."""
    text = "[COMPLICATION.TEXT]"
    terms: list[str] = []
    for index in range(27, 0, -1):
        if line == "inner":
            result = f"subText({text},0,{index})"
        else:
            # Start after the consumed separator and retain at most 34 characters.
            result = f"subText({text},{index + 1},{index + 35})"
        terms.append(f'subText({text},{index},{index + 1}) == " " ? {result}')
    # The terminal branch is the shared index-1 decision. `hasSplitSpace`
    # already established that one of 27..1 is ASCII space, so after tests
    # 27..2 fail, index 1 is necessarily the selected separator.
    terms.pop()
    return " : ".join(terms) + (f" : subText({text},0,1)" if line == "inner" else f" : subText({text},2,36)")


def renders_long_text(text: str) -> tuple[str, str | None]:
    """Model the XML split policy, including its intentional one-line fallback."""
    if len(text) <= 34:
        return text[:34], None
    split_at = next((index for index in range(27, 0, -1) if text[index:index + 1] == " "), None)
    if split_at is None:
        return text[:34], None
    return text[:split_at], text[split_at + 1:split_at + 35]


TOKEN = re.compile(r'\s*(floor|numberFormat|"[^"]*"|\[HOUR_0_23\]|\[HOUR_0_11\]|\[MINUTE\]|\d+(?:\.\d+)?|&&|\|\||>=|<=|==|!=|[?:(),+*/%!<>-])')


class WffExpression:
    """Small evaluator for the WFF expression subset used by the countdown.

    It parses XML-extracted source rather than mirroring its decision tree, so
    changed thresholds, terminal constants, operators, or grouping are tested.
    """

    def __init__(self, source: str, hour: int, minute: int):
        self.source, self.hour, self.minute = source, hour, minute
        self.tokens = TOKEN.findall(source)
        assert "".join(self.tokens) == re.sub(r"\s+", "", source), source
        self.index = 0

    def take(self, token: str | None = None) -> str:
        assert self.index < len(self.tokens), self.source
        result = self.tokens[self.index]
        assert token is None or result == token, (token, result, self.source)
        self.index += 1
        return result

    def expression(self, evaluate: bool = True):
        value = self.or_expression(evaluate)
        if self.index < len(self.tokens) and self.tokens[self.index] == "?":
            self.take("?")
            yes = self.expression(evaluate and bool(value))
            self.take(":")
            no = self.expression(evaluate and not bool(value))
            return (yes if value else no) if evaluate else 0
        return value if evaluate else 0

    def or_expression(self, evaluate: bool):
        value = self.and_expression(evaluate)
        while self.index < len(self.tokens) and self.tokens[self.index] == "||":
            self.take()
            other = self.and_expression(evaluate and not bool(value))
            value = bool(value) or bool(other) if evaluate else 0
        return value

    def and_expression(self, evaluate: bool):
        value = self.comparison(evaluate)
        while self.index < len(self.tokens) and self.tokens[self.index] == "&&":
            self.take()
            other = self.comparison(evaluate and bool(value))
            value = bool(value) and bool(other) if evaluate else 0
        return value

    def comparison(self, evaluate: bool):
        value = self.additive(evaluate)
        if self.index < len(self.tokens) and self.tokens[self.index] in {">=", "<=", "==", "!=", ">", "<"}:
            operator, other = self.take(), self.additive(evaluate)
            if evaluate:
                return {">=": value >= other, "<=": value <= other, "==": value == other,
                        "!=": value != other, ">": value > other, "<": value < other}[operator]
            return 0
        return value

    def additive(self, evaluate: bool):
        value = self.product(evaluate)
        while self.index < len(self.tokens) and self.tokens[self.index] in {"+", "-"}:
            operator, other = self.take(), self.product(evaluate)
            if evaluate:
                value = value + other if operator == "+" else value - other
        return value

    def product(self, evaluate: bool):
        value = self.unary(evaluate)
        while self.index < len(self.tokens) and self.tokens[self.index] in {"*", "/", "%"}:
            operator, other = self.take(), self.unary(evaluate)
            if evaluate:
                value = value * other if operator == "*" else value / other if operator == "/" else value % other
        return value

    def unary(self, evaluate: bool):
        if self.index < len(self.tokens) and self.tokens[self.index] == "!":
            self.take(); operand = self.unary(evaluate); return not bool(operand) if evaluate else 0
        if self.index < len(self.tokens) and self.tokens[self.index] == "-":
            self.take(); operand = self.unary(evaluate); return -operand if evaluate else 0
        return self.primary(evaluate)

    def primary(self, evaluate: bool):
        token = self.take()
        if token == "(":
            value = self.expression(evaluate); self.take(")"); return value
        if token == "floor":
            self.take("("); value = self.expression(evaluate); self.take(")"); return math.floor(value) if evaluate else 0
        if token == "numberFormat":
            self.take("("); pattern = self.take(); self.take(",")
            value = self.expression(evaluate); self.take(")")
            if not evaluate:
                return ""
            assert pattern == '"00"', pattern
            # The countdown's remaining minutes are strictly positive, so its
            # integer floor/modulo result is non-negative and WFF/Python agree.
            assert value >= 0, value
            return f"{int(value):02d}"
        if not evaluate: return 0
        if token == "[HOUR_0_23]": return self.hour
        if token == "[HOUR_0_11]": return self.hour % 12
        if token == "[MINUTE]": return self.minute
        return float(token) if "." in token else int(token)


def evaluate_wff(source: str, hour: int, minute: int):
    evaluator = WffExpression(source, hour, minute)
    value = evaluator.expression()
    assert evaluator.index == len(evaluator.tokens), (source, evaluator.tokens[evaluator.index:])
    return value


def specified_session(hour: int, minute: int) -> tuple[int, int, str, int | None]:
    """Independent, explicit local-time session schedule specification."""
    start, _, label, end, angle = next(row for row in SESSION_SPEC if row[0] <= hour < row[1])
    del start
    remaining = end - (hour * 60 + minute)
    # Session end instants belong to the next session, so remaining is 1..480.
    # This positive-input precondition makes Python // and % match WFF here.
    assert 0 < remaining <= 480
    return remaining // 60, remaining % 60, label, angle


def matching_paren(expression: str, opening: int) -> int:
    """Return the matching close parenthesis, rejecting malformed WFF expressions."""
    depth = 0
    for index in range(opening, len(expression)):
        if expression[index] == "(":
            depth += 1
        elif expression[index] == ")":
            depth -= 1
            if depth == 0:
                return index
            assert depth >= 0
    raise AssertionError(f"unclosed parenthesis: {expression}")


def assert_zero_padded_countdown(expression: str, operator: str) -> None:
    """Require WFF's string formatter around an integer countdown expression."""
    assert expression.startswith('numberFormat("00", floor(')
    floor_start = expression.index("floor(")
    close = matching_paren(expression, floor_start + len("floor"))
    assert close == len(expression) - 2 and expression.endswith(")")
    body = expression[floor_start + len("floor("):close]
    # The operation must be inside floor(), after complete remaining-minute
    # subtraction. This rejects the former `floor(remaining) / 60` bug.
    assert body.endswith(f" {operator} 60")
    assert " - ([HOUR_0_23] * 60 + [MINUTE])" in body


def assert_session_part_containment(part: ET.Element) -> None:
    """Every countdown text raster stays inside the face and safe AOD ink circle."""
    x, y = float(part.get("x")), float(part.get("y"))
    width, height = float(part.get("width")), float(part.get("height"))
    for point_x in (x, x + width):
        for point_y in (y, y + height):
            assert 0 <= point_x <= FACE_RADIUS * 2 and 0 <= point_y <= FACE_RADIUS * 2
            assert math.hypot(point_x - FACE_RADIUS, point_y - FACE_RADIUS) <= SESSION_SAFE_INK_RADIUS


def assert_session_countdown_centering(parts: list[ET.Element]) -> None:
    """The two countdown rows and five session labels center on the 450px face."""
    assert len(parts) == 7
    for part in parts:
        assert float(part.get("x")) + float(part.get("width")) / 2 == FACE_RADIUS


def assert_stacked_countdown_ink(hours: ET.Element, minutes: ET.Element) -> None:
    """Prove the two 70px Nova Mono rows cannot overlap when raster-centered.

    Nova Mono is checksum-pinned above. At 70px, HarfBuzz with its FreeType
    font functions reports 52px of vertical ink for the tallest glyphs used by
    `00h` and `00m` (`0` and `h`; `m` is 38px). This intentionally rounds to
    the measured raster maximum rather than relying on the 51px OpenType-outline
    result. WFF centers Text ink in its PartText raster: the 90px raster therefore
    has 19px clearance above and below the 52px ink, despite Nova Mono's 97.55px
    typographic line box. The 75px row-center separation leaves 23px of ink
    clearance. Every bound below is strict so a geometry or font change fails closed.
    """
    tallest_ink = 52
    hour_y, hour_height = map(float, (hours.get("y"), hours.get("height")))
    minute_y, minute_height = map(float, (minutes.get("y"), minutes.get("height")))
    hour_ink_top, hour_ink_bottom = (
        hour_y + (hour_height - tallest_ink) / 2,
        hour_y + (hour_height + tallest_ink) / 2,
    )
    minute_ink_top, minute_ink_bottom = (
        minute_y + (minute_height - tallest_ink) / 2,
        minute_y + (minute_height + tallest_ink) / 2,
    )
    # Assert ink containment directly; a font line-box is not raster ink and
    # must not be used to require an otherwise unnecessary geometry change.
    assert hour_y <= hour_ink_top < hour_ink_bottom <= hour_y + hour_height
    assert minute_y <= minute_ink_top < minute_ink_bottom <= minute_y + minute_height
    assert hour_ink_bottom < minute_ink_top, (hour_ink_bottom, minute_ink_top)


def render_countdown_template(template: str, value: str) -> str:
    """Render the deliberately restricted `%s` unit templates under test."""
    assert template in {"%sh", "%sm"}
    assert re.fullmatch(r"\d{2}", value), value
    return template.replace("%s", value)


def assert_paths(slot: ET.Element, options: list[ET.Element], *, one_line: bool = False, split: bool = False, one_line_budget: int = 23) -> None:
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
            assert parameters(paths[0]) == [f"subText([COMPLICATION.TEXT],0,{one_line_budget})"]
        else:
            assert [(p.get("width"), p.get("startAngle"), p.get("endAngle")) for p in paths] == [("320", "238.5", "121.5"), ("410", "251.5", "108.5")]
            expected = ([space_search_expression(line="inner")], [space_search_expression(line="outer")]) if split else (["subText([COMPLICATION.TEXT],0,20)"], ["subText([COMPLICATION.TITLE],0,23)"])
            assert [parameters(p) for p in paths] == list(expected)
            if split:
                assert paths[0].find("Font/Template").text == "%s"


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
    # AOD option 3 is an exclusive session view: no complication slot may draw.
    for slot_id, slot in slots.items():
        variants = slot.findall("Variant")
        assert len(variants) == 1, slot_id
        assert variants[0].attrib == {
            "mode": "AMBIENT", "target": "alpha",
            "value": "[CONFIGURATION.aod] == 0 ? 165 : 0",
        }, slot_id
    part_fonts = root.findall(".//PartText//Font")
    assert all(font.get("letterSpacing") == "-0.05" for font in part_fonts)
    session_fonts = {
        part.find("Text/Font")
        for part in root.findall(".//PartText")
        if (part.get("name") or "").startswith("session_countdown_")
    }
    assert len(session_fonts) == 7
    assert all(font is not None and font.get("letterSpacing") == "-0.05" for font in session_fonts)

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

    # AOD option 3 replaces only the ambient digital clock with the session
    # countdown. Options 0/1/2 preserve their exact existing AOD selection.
    aod = root.find(".//UserConfigurations/ListConfiguration[@id='aod']")
    assert aod is not None and aod.get("defaultValue") == "0"
    assert [option.get("id") for option in aod.findall("ListOption")] == ["0", "1", "2", "3"]
    clock = root.find(".//DigitalClock")
    assert clock is not None
    for time_text in clock.findall("TimeText"):
        variant = time_text.find("Variant")
        assert variant is not None and variant.get("mode") == "AMBIENT"
        assert variant.get("value", "").startswith("[CONFIGURATION.aod] == 3 ? 0 : ")

    countdown = {part.get("name"): part for part in root.findall(".//PartText") if (part.get("name") or "").startswith("session_countdown_")}
    assert set(countdown) == {
        "session_countdown_hours", "session_countdown_minutes", "session_countdown_peak",
        "session_countdown_transition", "session_countdown_trough", "session_countdown_personal",
        "session_countdown_sleep",
    }
    for part in countdown.values():
        assert part.get("alpha") == "0"
        variant = part.find("Variant")
        assert variant is not None and variant.attrib == {"mode": "AMBIENT", "target": "alpha", "value": "[CONFIGURATION.aod] == 3 ? 165 : 0"}
        assert_session_part_containment(part)
    assert_session_countdown_centering([
        countdown["session_countdown_hours"],
        countdown["session_countdown_minutes"],
        countdown["session_countdown_peak"],
        countdown["session_countdown_transition"],
        countdown["session_countdown_trough"],
        countdown["session_countdown_personal"],
        countdown["session_countdown_sleep"],
    ])
    hours_template = countdown["session_countdown_hours"].find("Text/Font/Template").text
    minutes_template = countdown["session_countdown_minutes"].find("Text/Font/Template").text
    assert hours_template == "%sh"
    assert minutes_template == "%sm"
    hours_expression = countdown["session_countdown_hours"].find("Text/Font/Template/Parameter").get("expression")
    minutes_expression = countdown["session_countdown_minutes"].find("Text/Font/Template/Parameter").get("expression")
    assert_zero_padded_countdown(hours_expression, "/")
    assert_zero_padded_countdown(minutes_expression, "%")
    assert_stacked_countdown_ink(countdown["session_countdown_hours"], countdown["session_countdown_minutes"])
    label_condition = next(
        (condition for condition in root.findall(".//Scene/Condition")
         if condition.find("Expressions/Expression[@name='isPeak']") is not None),
        None,
    )
    assert label_condition is not None
    label_expressions = {
        expression.get("name"): expression.text
        for expression in label_condition.findall("Expressions/Expression")
    }
    assert set(label_expressions) == {"isPeak", "isTransition", "isTrough", "isPersonal"}
    label_bindings = {
        compare.get("expression"): compare.find("PartText")
        for compare in label_condition.findall("Compare")
    }
    expected_label_bindings = {
        "isPeak": ("session_countdown_peak", "PEAK"),
        "isTransition": ("session_countdown_transition", "TRANSITION"),
        "isTrough": ("session_countdown_trough", "TROUGH"),
        "isPersonal": ("session_countdown_personal", "PERSONAL"),
    }
    assert set(label_bindings) == set(expected_label_bindings)
    for expression_name, (expected_name, label) in expected_label_bindings.items():
        part = label_bindings[expression_name]
        assert part is not None and part.get("name") == expected_name
        assert part is countdown[expected_name]
        assert part.find("Text/Font/Template").text == "%s"
        assert part.find("Text/Font/Template/Parameter").get("expression") == f"icuText(\"'{label}'\", [UTC_TIMESTAMP])"
    default_part = label_condition.find("Default/PartText")
    assert default_part is countdown["session_countdown_sleep"]
    assert default_part.find("Text/Font/Template").text == "%s"
    assert default_part.find("Text/Font/Template/Parameter").get("expression") == 'icuText("\'SLEEP\'", [UTC_TIMESTAMP])'
    for name, label in (("session_countdown_peak", "PEAK"), ("session_countdown_transition", "TRANSITION"),
                        ("session_countdown_trough", "TROUGH"), ("session_countdown_personal", "PERSONAL"),
                        ("session_countdown_sleep", "SLEEP")):
        assert countdown[name].find("Text/Font/Template").text == "%s"
        assert countdown[name].find("Text/Font/Template/Parameter").get("expression") == f"icuText(\"'{label}'\", [UTC_TIMESTAMP])"
    arc_condition = next(
        (condition for condition in root.findall(".//Scene/Condition")
         if condition.find("Expressions/Expression[@name='sessionArcEnabled']") is not None),
        None,
    )
    assert arc_condition is not None
    arc_enabled_expression = arc_condition.find("Expressions/Expression").text
    arc = arc_condition.find("Compare/PartDraw[@name='session_countdown_arc']")
    assert arc is not None and {key: arc.get(key) for key in ("width", "height", "x", "y", "alpha")} == {
        "width": "450", "height": "450", "x": "0", "y": "0", "alpha": "0",
    }
    arc_variant = arc.find("Variant")
    assert arc_variant is not None and arc_variant.get("mode") == "AMBIENT"
    assert arc_variant.get("value") == "[CONFIGURATION.aod] == 3 ? 165 : 0"
    arc_shape = arc.find("Arc")
    assert arc_shape is not None and arc_shape.attrib == {
        "centerX": "225", "centerY": "225", "width": "430", "height": "430",
        "startAngle": "0", "endAngle": "0", "direction": "CLOCKWISE",
    }
    transforms = {transform.get("target"): transform.get("value") for transform in arc_shape.findall("Transform")}
    assert set(transforms) == {"startAngle", "endAngle"}
    assert arc_shape.find("Stroke").attrib == {"color": "#fafafa", "cap": "BUTT", "thickness": "3"}
    arc_radius = float(arc_shape.get("width")) / 2
    arc_ink_radius = arc_radius + float(arc_shape.find("Stroke").get("thickness")) / 2
    assert arc_ink_radius == SESSION_SAFE_INK_RADIUS <= FACE_RADIUS
    for clock_time, hour, minute, expected in (
        ("00:00", 0, 0, (6, 0, "SLEEP", None)),
        ("05:59", 5, 59, (0, 1, "SLEEP", None)),
        ("06:00", 6, 0, (5, 0, "PEAK", 330)),
        ("10:59", 10, 59, (0, 1, "PEAK", 330)),
        ("11:00", 11, 0, (1, 0, "TRANSITION", 360)),
        ("11:59", 11, 59, (0, 1, "TRANSITION", 360)),
        ("12:00", 12, 0, (5, 0, "TROUGH", 150)),
        ("14:30", 14, 30, (2, 30, "TROUGH", 150)),
        ("16:59", 16, 59, (0, 1, "TROUGH", 150)),
        ("17:00", 17, 0, (5, 0, "PERSONAL", 300)),
        ("21:59", 21, 59, (0, 1, "PERSONAL", 300)),
        ("22:00", 22, 0, (8, 0, "SLEEP", None)),
        ("23:59", 23, 59, (6, 1, "SLEEP", None)),
    ):
        actual = specified_session(hour, minute)
        assert actual == expected, (clock_time, actual)
        assert 0 <= actual[0] <= 8 and 0 <= actual[1] < 60
    # Evaluate and render the extracted WFF source at every minute against the
    # independent schedule. This kills threshold/end/operator/floor/modulo and
    # zero-padding mutations, rather than merely comparing expression text.
    for hour in range(24):
        for minute in range(60):
            expected_hours, expected_minutes, expected_label, expected_end = specified_session(hour, minute)
            actual_hours = evaluate_wff(hours_expression, hour, minute)
            actual_minutes = evaluate_wff(minutes_expression, hour, minute)
            assert actual_hours == f"{expected_hours:02d}", (hour, minute, "hours", actual_hours)
            assert actual_minutes == f"{expected_minutes:02d}", (hour, minute, "minutes", actual_minutes)
            assert render_countdown_template(hours_template, actual_hours) == f"{expected_hours:02d}h", (hour, minute)
            assert render_countdown_template(minutes_template, actual_minutes) == f"{expected_minutes:02d}m", (hour, minute)
            selected = [name for name, source in label_expressions.items() if evaluate_wff(source, hour, minute)]
            assert len(selected) <= 1, (hour, minute, selected)
            selected_part = label_bindings[selected[0]] if selected else default_part
            actual_label = next(label for name, label in expected_label_bindings.values() if name == selected_part.get("name")) if selected else "SLEEP"
            assert actual_label == expected_label, (hour, minute, actual_label)
            enabled = evaluate_wff(arc_enabled_expression, hour, minute)
            assert enabled == (expected_end is not None), (hour, minute, enabled)
            if enabled:
                assert evaluate_wff(transforms["endAngle"], hour, minute) == expected_end, (hour, minute, "endAngle")
                assert evaluate_wff(transforms["startAngle"], hour, minute) == (hour % 12) * 30 + minute * 0.5
    assert (14 % 12) * 30 + 30 * 0.5 == 75
    # At TRANSITION start the analog hand is 330°; 360° is the proven
    # clockwise representation of noon. A literal 0° would not meet this
    # source-level invariant even though generic angle normalization can mask it.
    transition_sweep = sweep_angles(ET.fromstring(
        '<Arc startAngle="330" endAngle="360" direction="CLOCKWISE"/>'
    ))
    assert transition_sweep == [330.0, 360.0, 360]
    # Unselected branches are consumed without evaluation, matching WFF's
    # short-circuit semantics while still checking expression structure.
    assert evaluate_wff("0 && (1 / 0)", 0, 0) is False
    assert evaluate_wff("1 || (1 / 0)", 0, 0) is True
    assert evaluate_wff("1 ? 7 : (1 / 0)", 0, 0) == 7
    assert evaluate_wff("-([MINUTE] + 1)", 0, 4) == -5
    assert evaluate_wff('numberFormat("00", 2)', 0, 0) == "02"
    assert evaluate_wff('numberFormat("00", 30)', 0, 0) == "30"

    slot = slots["3"]
    shape = slot.find("BoundingArc")
    assert shape is not None and shape.attrib == {"centerX":"201", "centerY":"-75", "width":"365", "height":"365", "startAngle":"259", "endAngle":"101", "direction":"COUNTER_CLOCKWISE", "thickness":"85"}
    # Arc A: r205 251.5→108.5°; Arc B: r160 238.5→121.5°.
    assert 205 - 20 - (160 + 20) == 5
    # A single BoundingArc cannot encode the gap, but must crop all actual ink.
    crop_inner, crop_outer = 182.5 - 42.5, 182.5 + 42.5
    assert crop_inner <= 160 - 20 and crop_outer >= 205 + 20
    # Full 13px-ink path containment, crop containment, clock/edge safety, and AOD safety.
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
    sentinel = long_condition.find("Expressions/Expression")
    assert sentinel is not None and (sentinel.text or "") == '[COMPLICATION.TEXT] == "---"'
    # LONG_TEXT previews deliberately ignore provider titles (for example, app names).
    assert "COMPLICATION.TITLE" not in ET.tostring(long_condition, encoding="unicode")
    over_budget = long_condition.find("Default/Condition")
    assert over_budget is not None
    condition = over_budget.find("Expressions/Expression")
    assert condition is not None
    expected_conditions = " || ".join(
        f'subText([COMPLICATION.TEXT],{index},{index + 1}) == " "' for index in range(27, 0, -1)
    )
    assert (condition.text or "") == f"textLength([COMPLICATION.TEXT]) > 34 && ({expected_conditions})"
    assert_paths(slot, normal_options(over_budget.find("Compare")), split=True)
    assert_paths(slot, normal_options(over_budget.find("Default")), one_line=True, one_line_budget=34)
    # The rightmost qualifying ASCII space is the only character consumed.
    # Adjacent repeated spaces therefore remain in their respective slices.
    # Unbroken and CJK text has no qualifying separator, so over-budget input
    # takes the one-line 34-character truncated fallback.
    for source, expected in (
        ("Meet the team in the cafeteria for lunch tomorrow", ("Meet the team in the", "cafeteria for lunch tomorrow")),
        ("one two three four five xx  seven eight nine", ("one two three four five xx ", "seven eight nine")),
        ("one two three four five six  seven eight nine", ("one two three four five six", " seven eight nine")),
        ("supercalifragilisticexpialidociouswordthatcannotbreak", ("supercalifragilisticexpialidocious", None)),
        ("這是一段沒有空格而且足夠長的中文通知文字不能跨行切開請保持單行截斷測試資料", ("這是一段沒有空格而且足夠長的中文通知文字不能跨行切開請保持單行截斷測", None)),
    ):
        rendered = renders_long_text(source)
        assert rendered == expected, (source, rendered)
        if rendered[1] is not None:
            # These fixtures fit their second-line budget: rejoining proves
            # exactly one ASCII separator, not a whitespace run, was consumed.
            assert source == rendered[0] + " " + rendered[1]
            assert len(rendered[0]) <= 27 and len(rendered[1]) <= 34
    cjk_source = "這是一段沒有空格而且足夠長的中文通知文字不能跨行切開請保持單行截斷測試資料"
    cjk_rendered = renders_long_text(cjk_source)
    assert len(cjk_source) > 34 and cjk_rendered == (cjk_source[:34], None)

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
    print("Nova Mono, safe adaptive arc, hour animation, AOD session countdown, and safety invariants verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
