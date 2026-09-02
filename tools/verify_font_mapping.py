#!/usr/bin/env python3
"""Fail-closed verification for Nova Mono, WFF v2 arcs, hour animation, and AOD sessions."""

from __future__ import annotations

import hashlib
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
NOVA_MONO = ROOT / "watchface/src/main/res/font/nova_mono.ttf"
NOVA_MONO_SHA256 = "648eadb6648c0801b186d3dcef60ee6aa84a791b1e09c726935c0712508b4807"
MARKER = ROOT / "watchface/src/main/res/drawable-nodpi/session_current_marker.png"
MARKER_SHA256 = "5e385773f58d25179acf8fe7ce0a86bdff705608a74754c0c5f8c5015d287144"
HOUR_INDICATOR_FORMULA = "[HOUR_0_11] * 30 + [MINUTE] * 0.5"
FACE_RADIUS = 225.0
# The face is physical r=225. The arc's r=216.5 outer edge is deliberately
# joined by the marker's r=217 apex, rather than being the old global limit.
SESSION_SAFE_INK_RADIUS = 217.2
# ImageMagick/FreeType raster ink measurements of the SHA-pinned Nova Mono
# artifact at the WFF point sizes below. Keep each rendered string distinct:
# substituting the largest row's box for both is an inaccurate metric claim.
HOURS_ROW_INK = (243, 118)       # `00h` at 158px
MINUTES_ROW_INK = (250, 117)     # `00m` at 158px
# Approved conservative painted-ink envelope for each shipped 24px session
# time string. It is a verifier pin, not a renderer-specific precision claim.
# Do not substitute synthetic SEMI_BOLD: the bundled file is Regular (OS/2 400).
CURRENT_TIME_INK = (66, 19)
WORST_ENDPOINT_INK = (66, 19)
SESSION_FADED_COLOR = "#cccccc"
SESSION_OPTICAL_OFFSET = (2.0, -2.0)
CURRENT_TRAIL = 19.0
CURRENT_PATH_SPAN = 22.0
MARKER_TO_CURRENT_PATH_CLEARANCE = 14.0
# Deliberately independent of the WFF expressions below: this is the product
# specification against which their *evaluated* results are checked.
SESSION_SPEC = (
    (0, 6, "SLEEP", 360, 180),
    (6, 11, "PEAK", 660, 330),
    (11, 12, "TRANSITION", 720, 360),
    (12, 17, "TROUGH", 1020, 150),
    (17, 22, "PERSONAL", 1320, 300),
    (22, 24, "SLEEP", 1800, 180),
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
    """Pin each central raster, including its intentional x=2 blank overrun."""
    expected = {
        "session_countdown_hours": (2.0, 66.0, 450.0, 158.0),
        "session_countdown_minutes": (2.0, 224.0, 450.0, 158.0),
        **{f"session_countdown_{label}": (2.0, 219.0, 450.0, 26.0)
           for label in ("peak", "transition", "trough", "personal", "sleep")},
    }
    geometry = tuple(float(part.get(key)) for key in ("x", "y", "width", "height"))
    assert geometry == expected[part.get("name")], (part.get("name"), geometry)
    # x=2,width=450 deliberately makes blank raster reach x=452; actual ink
    # from this center is separately proved inside the circular display.
    assert geometry[0] + geometry[2] == FACE_RADIUS * 2 + SESSION_OPTICAL_OFFSET[0]


def radius_for_box(half_width: float, y_from_center: float) -> float:
    """Conservative far-corner radius for horizontally centred text ink."""
    return math.hypot(half_width, abs(y_from_center))


def png_size(path: Path) -> tuple[int, int]:
    """Read the PNG IHDR without accepting a vector or density-scaled asset."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def png_alpha(path: Path) -> tuple[int, int, list[list[int]]]:
    """Decode this pinned non-interlaced RGBA PNG enough to prove its apex."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset, compressed = 8, b""
    width = height = bit_depth = color_type = interlace = None
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind, payload = data[offset + 4:offset + 8], data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed += payload
        elif kind == b"IEND":
            break
    # The deliberately compact marker is 8-bit grayscale+alpha (PNG type 4).
    assert (bit_depth, color_type, interlace) == (8, 4, 0)
    raw, stride, previous, rows = zlib.decompress(compressed), width * 2, [0] * (width * 2), []
    cursor = 0
    for _ in range(height):
        filter_type, encoded = raw[cursor], list(raw[cursor + 1:cursor + 1 + stride]); cursor += stride + 1
        decoded: list[int] = []
        for index, value in enumerate(encoded):
            left = decoded[index - 2] if index >= 2 else 0
            up = previous[index]
            upper_left = previous[index - 2] if index >= 2 else 0
            if filter_type == 1: value = (value + left) & 255
            elif filter_type == 2: value = (value + up) & 255
            elif filter_type == 3: value = (value + ((left + up) // 2)) & 255
            elif filter_type == 4:
                estimate = left + up - upper_left
                nearest = min((left, up, upper_left), key=lambda pixel: (abs(estimate - pixel), pixel))
                value = (value + nearest) & 255
            else: assert filter_type == 0
            decoded.append(value)
        rows.append(decoded[1::2]); previous = decoded
    assert cursor == len(raw)
    return width, height, rows


def angle_distance(left: float, right: float) -> float:
    """Smallest unsigned angular separation in degrees."""
    return abs((left - right + 180) % 360 - 180)


def circular_text_bounds(radius: float, angle: float, width: float, height: float) -> tuple[float, float, float, float]:
    """Conservative axis-aligned ink bounds for text tangent to a circular path."""
    radians = math.radians(angle)
    x = FACE_RADIUS + radius * math.sin(radians)
    y = FACE_RADIUS - radius * math.cos(radians)
    tangent_x, tangent_y = math.cos(radians), math.sin(radians)
    radial_x, radial_y = math.sin(radians), -math.cos(radians)
    half_width, half_height = width / 2, height / 2
    x_extent = abs(tangent_x) * half_width + abs(radial_x) * half_height
    y_extent = abs(tangent_y) * half_width + abs(radial_y) * half_height
    return x - x_extent, y - y_extent, x + x_extent, y + y_extent


def boxes_disjoint(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    """Whether two conservative axis-aligned ink bounds do not overlap."""
    return left[2] < right[0] or right[2] < left[0] or left[3] < right[1] or right[3] < left[1]


def oriented_text_box(radius: float, angle: float, width: float, height: float) -> tuple[tuple[float, float], ...]:
    """Measured text ink rectangle, tangent to its circular baseline."""
    radians = math.radians(angle)
    center = (FACE_RADIUS + radius * math.sin(radians), FACE_RADIUS - radius * math.cos(radians))
    tangent, radial = (math.cos(radians), math.sin(radians)), (math.sin(radians), -math.cos(radians))
    return tuple((center[0] + horizontal * width / 2 * tangent[0] + vertical * height / 2 * radial[0], center[1] + horizontal * width / 2 * tangent[1] + vertical * height / 2 * radial[1]) for horizontal in (-1, 1) for vertical in (-1, 1))


def oriented_box_clearance(left: tuple[tuple[float, float], ...], right: tuple[tuple[float, float], ...]) -> float:
    """Maximum positive projection gap over both rectangles' edge normals.

    This is the exact SAT separation criterion used here: a positive result
    proves non-overlap; zero or negative means no separating axis and fails.
    It is deliberately reported as SAT clearance, not Euclidean distance.
    """
    axes = []
    for box in (left, right):
        for first, second in ((0, 1), (0, 2)):
            dx, dy = box[second][0] - box[first][0], box[second][1] - box[first][1]
            length = math.hypot(dx, dy)
            assert length > 0
            axes.append((-dy / length, dx / length))
    return max(max(min(x * point[0] + y * point[1] for point in right) - max(x * point[0] + y * point[1] for point in left), min(x * point[0] + y * point[1] for point in left) - max(x * point[0] + y * point[1] for point in right)) for x, y in axes)


def assert_approved_session_ink_constants(current: tuple[int, int], endpoint: tuple[int, int]) -> None:
    """Fail closed on any reduction of the hash-pinned-source safety bounds."""
    assert current == (66, 19), current
    assert endpoint == (66, 19), endpoint


def assert_approved_session_faded_color(color: str) -> None:
    """Pin the specified 1.5× #888888 annotation color below white ink."""
    assert color == "#cccccc", color
    assert all(channel < 0xff for channel in bytes.fromhex(color[1:])), color


def assert_session_countdown_centering(parts: list[ET.Element]) -> None:
    """All seven central rasters share the specified +2px/-2px optical shift."""
    assert len(parts) == 7
    for part in parts:
        baseline_y = {"session_countdown_hours": 68, "session_countdown_minutes": 226}.get(part.get("name"), 221)
        assert float(part.get("x")) + float(part.get("width")) / 2 == FACE_RADIUS + SESSION_OPTICAL_OFFSET[0]
        assert float(part.get("y")) == baseline_y + SESSION_OPTICAL_OFFSET[1]


def assert_stacked_countdown_ink(hours: ET.Element, minutes: ET.Element) -> None:
    """Prove the distinct measured 158px Nova Mono rows retain a 40.5px gap.

    ImageMagick/FreeType measures hash-pinned Nova Mono `00h` at 158px as
    243×118px and `00m` as 250×117px. WFF centres each ink box in its
    PartText raster.
    """
    hour_y, hour_height = map(float, (hours.get("y"), hours.get("height")))
    minute_y, minute_height = map(float, (minutes.get("y"), minutes.get("height")))
    hour_ink_top, hour_ink_bottom = (
        hour_y + (hour_height - HOURS_ROW_INK[1]) / 2,
        hour_y + (hour_height + HOURS_ROW_INK[1]) / 2,
    )
    minute_ink_top, minute_ink_bottom = (
        minute_y + (minute_height - MINUTES_ROW_INK[1]) / 2,
        minute_y + (minute_height + MINUTES_ROW_INK[1]) / 2,
    )
    # Assert ink containment directly; a font line-box is not raster ink and
    # must not be used to require an otherwise unnecessary geometry change.
    assert hour_y <= hour_ink_top < hour_ink_bottom <= hour_y + hour_height
    assert minute_y <= minute_ink_top < minute_ink_bottom <= minute_y + minute_height
    assert minute_ink_top - hour_ink_bottom == 40.5, (hour_ink_bottom, minute_ink_top)


def assert_session_text_ink_containment(countdown: dict[str, ET.Element]) -> None:
    """Prove measured/conservative session text ink stays in the safe circle.

    ImageMagick/FreeType independently measures hash-pinned Nova Mono `00h`
    at 158px as 243×118px and `00m` as 250×117px, and the widest session label,
    `TRANSITION`, at 26px as 149×19px. These conservative bounds prove ink
    containment rather than treating blank PartText raster corners as visible
    ink.
    """
    for name, (ink_width, ink_height) in (
        ("session_countdown_hours", HOURS_ROW_INK),
        ("session_countdown_minutes", MINUTES_ROW_INK),
    ):
        part = countdown[name]
        ink_x = float(part.get("x")) + float(part.get("width")) / 2 - FACE_RADIUS
        ink_y = float(part.get("y")) + float(part.get("height")) / 2 - FACE_RADIUS
        assert radius_for_box(abs(ink_x) + ink_width / 2, abs(ink_y) + ink_height / 2) <= SESSION_SAFE_INK_RADIUS < FACE_RADIUS
    for name in ("session_countdown_peak", "session_countdown_transition",
                 "session_countdown_trough", "session_countdown_personal",
                 "session_countdown_sleep"):
        part = countdown[name]
        ink_x = float(part.get("x")) + float(part.get("width")) / 2 - FACE_RADIUS
        ink_y = float(part.get("y")) + float(part.get("height")) / 2 - FACE_RADIUS
        assert radius_for_box(abs(ink_x) + 74.5, abs(ink_y) + 9.5) <= SESSION_SAFE_INK_RADIUS < FACE_RADIUS


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


def endpoint_label_geometry(paths: dict[str, ET.Element]) -> dict[str, float]:
    """Extract endpoint-label centers/spans under their structural direction."""
    expected = {
        "SLEEP": (180, 22),
        "PEAK": (330, 22),
        "TRANSITION": (0, 22),
        "TROUGH": (150, 22),
        "PERSONAL": (300, 22),
    }
    assert set(paths) == set(expected)
    centers: dict[str, float] = {}
    for label, path in paths.items():
        source_angles = tuple(path.get(angle) for angle in ("startAngle", "endAngle"))
        assert all(angle is not None for angle in source_angles), (label, source_angles)
        start, end = (float(angle) for angle in source_angles)
        direction = path.get("direction")
        assert direction in {"CLOCKWISE", "COUNTER_CLOCKWISE"}
        span = (end - start) % 360 if direction == "CLOCKWISE" else (start - end) % 360
        center = (start + span / 2) % 360 if direction == "CLOCKWISE" else (start - span / 2) % 360
        assert (center, span) == expected[label], (label, start, end, center, span)
        assert direction == ("COUNTER_CLOCKWISE" if label in {"SLEEP", "TROUGH"} else "CLOCKWISE")
        centers[label] = center
    return centers


def main() -> int:
    if sys.flags.optimize:
        raise RuntimeError("verify_font_mapping.py must not run with Python optimization enabled")
    root = ET.parse(WATCHFACE).getroot()
    assert hashlib.sha256(NOVA_MONO.read_bytes()).hexdigest() == NOVA_MONO_SHA256
    assert_approved_session_ink_constants(CURRENT_TIME_INK, WORST_ENDPOINT_INK)
    assert_approved_session_faded_color(SESSION_FADED_COLOR)
    # Mutation checks make a reduced current or endpoint ink bound fail even if
    # a later edit accidentally stops using one of the load-bearing constants.
    for mutated_current, mutated_endpoint in (((65, 19), WORST_ENDPOINT_INK),
                                              (CURRENT_TIME_INK, (65, 19))):
        try:
            assert_approved_session_ink_constants(mutated_current, mutated_endpoint)
        except AssertionError:
            pass
        else:
            raise AssertionError("session ink-bound mutation survived")
    for mutated_color in ("#cdcdcd", "#ffffff"):
        try:
            assert_approved_session_faded_color(mutated_color)
        except AssertionError:
            pass
        else:
            raise AssertionError("session faded-color mutation survived")
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
    assert all(font.get("color") == SESSION_FADED_COLOR for font in session_fonts
               if font is not None and font.text in {"PEAK", "TRANSITION", "TROUGH", "PERSONAL", "SLEEP"})

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
        assert variant is not None and variant.attrib == {"mode": "AMBIENT", "target": "alpha", "value": "[CONFIGURATION.aod] == 3 ? 255 : 0"}
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
    absurd_width = ET.fromstring(ET.tostring(countdown["session_countdown_hours"]))
    absurd_width.set("width", "600")
    try:
        assert_session_part_containment(absurd_width)
    except AssertionError:
        pass
    else:
        raise AssertionError("absurd central PartText width survived")
    hours_template = countdown["session_countdown_hours"].find("Text/Font/Template").text
    minutes_template = countdown["session_countdown_minutes"].find("Text/Font/Template").text
    assert hours_template == "%sh"
    assert minutes_template == "%sm"
    hours_expression = countdown["session_countdown_hours"].find("Text/Font/Template/Parameter").get("expression")
    minutes_expression = countdown["session_countdown_minutes"].find("Text/Font/Template/Parameter").get("expression")
    assert_zero_padded_countdown(hours_expression, "/")
    assert_zero_padded_countdown(minutes_expression, "%")
    assert_stacked_countdown_ink(countdown["session_countdown_hours"], countdown["session_countdown_minutes"])
    assert_session_text_ink_containment(countdown)
    for part in (countdown["session_countdown_hours"], countdown["session_countdown_minutes"]):
        font = part.find("Text/Font")
        assert font is not None and font.attrib == {"color": "#ffffff", "family": "nova_mono", "size": "158", "weight": "NORMAL", "letterSpacing": "-0.05"}
    # Measured 158px row ink: centred rows are contained by the safe circle,
    # rather than by a vacuous full-width PartText raster check.
    assert [(float(p.get("y")) + (float(p.get("height")) - ink[1]) / 2,
              float(p.get("y")) + (float(p.get("height")) + ink[1]) / 2)
             for p, ink in ((countdown["session_countdown_hours"], HOURS_ROW_INK),
                            (countdown["session_countdown_minutes"], MINUTES_ROW_INK))] == [(86, 204), (244.5, 361.5)]
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
        assert part.find("Text/Font").text == label
        assert part.find("Text/Font/Template") is None
    default_part = label_condition.find("Default/PartText")
    assert default_part is countdown["session_countdown_sleep"]
    assert default_part.find("Text/Font").text == "SLEEP"
    assert default_part.find("Text/Font/Template") is None
    # The 26px label's measured 19px ink is centred in the 40.5px row gap:
    # y=222.5..241.5 leaves 18.5px below hours and exactly 3px above minutes.
    label_ink_top = float(default_part.get("y")) + (float(default_part.get("height")) - 19) / 2
    assert label_ink_top - 204 == 18.5
    assert 244.5 - (label_ink_top + 19) == 3
    for name, label in (("session_countdown_peak", "PEAK"), ("session_countdown_transition", "TRANSITION"),
                        ("session_countdown_trough", "TROUGH"), ("session_countdown_personal", "PERSONAL"),
                        ("session_countdown_sleep", "SLEEP")):
        assert countdown[name].find("Text/Font").text == label
        assert countdown[name].find("Text/Font/Template") is None
    arc_condition = next(
        (condition for condition in root.findall(".//Scene/Condition")
         if condition.find("Expressions/Expression[@name='sessionArcEnabled']") is not None),
        None,
    )
    assert arc_condition is not None
    arc_enabled_expression = arc_condition.find("Expressions/Expression").text
    assert arc_enabled_expression == "[HOUR_0_23] >= 0"
    arc = arc_condition.find("Compare/PartDraw[@name='session_countdown_arc']")
    assert arc is not None and {key: arc.get(key) for key in ("width", "height", "x", "y", "alpha")} == {
        "width": "450", "height": "450", "x": "0", "y": "0", "alpha": "0",
    }
    arc_variant = arc.find("Variant")
    assert arc_variant is not None and arc_variant.get("mode") == "AMBIENT"
    assert arc_variant.get("value") == "[CONFIGURATION.aod] == 3 ? 255 : 0"
    arc_shape = arc.find("Arc")
    assert arc_shape is not None and arc_shape.attrib == {
        "centerX": "225", "centerY": "225", "width": "430", "height": "430",
        "startAngle": "0", "endAngle": "0", "direction": "CLOCKWISE",
    }
    transforms = {transform.get("target"): transform.get("value") for transform in arc_shape.findall("Transform")}
    assert set(transforms) == {"startAngle", "endAngle"}
    assert arc_shape.find("Stroke").attrib == {"color": SESSION_FADED_COLOR, "cap": "BUTT", "thickness": "3"}
    arc_radius = float(arc_shape.get("width")) / 2
    arc_ink_radius = arc_radius + float(arc_shape.find("Stroke").get("thickness")) / 2
    assert arc_ink_radius == 216.5 <= FACE_RADIUS
    assert MARKER.is_file() and png_size(MARKER) == (14, 12)
    assert hashlib.sha256(MARKER.read_bytes()).hexdigest() == MARKER_SHA256
    marker_width, marker_height, marker_alpha = png_alpha(MARKER)
    assert (marker_width, marker_height) == (14, 12)
    # The top-center apex is fully opaque; the hash-pinned authored silhouette
    # also has partial-alpha fringe pixels at its outer reach.
    assert marker_alpha[0][7] == 255
    marker_partial_reach = max(
        math.hypot(225 - (218 + x), 225 - (8 + y))
        for y, row in enumerate(marker_alpha) for x, alpha in enumerate(row)
        if 0 < alpha < 255
    )
    assert marker_partial_reach > 217
    assert not (ROOT / "watchface/src/main/res/drawable/session_current_marker.xml").exists()
    # The only literal WFF image is the marker. It resolves to this transparent
    # raster. All other Image resources are the four schema-defined complication
    # image fields, supplied by the platform rather than packaged resources.
    image_resources = [image.get("resource") for image in root.findall(".//Image")]
    literal_images = [resource for resource in image_resources if not resource.startswith("[")]
    assert literal_images == ["session_current_marker"]
    assert set(image_resources) <= {
        "session_current_marker", "[COMPLICATION.MONOCHROMATIC_IMAGE]",
        "[COMPLICATION.SMALL_IMAGE]", "[COMPLICATION.MONOCHROMATIC_IMAGE_AMBIENT]",
    }
    furnishings = {element.get("name"): element for element in arc_condition.find("Compare") if element.get("name")}
    marker = furnishings["session_current_marker"]
    assert marker.attrib == {"name": "session_current_marker", "width": "450", "height": "450", "x": "0", "y": "0", "pivotX": "0.5", "pivotY": "0.5", "alpha": "0"}
    marker_image = marker.find("PartImage")
    assert marker_image is not None and marker_image.attrib == {"width": "14", "height": "12", "x": "218", "y": "8"}
    assert marker_image.find("Image").get("resource") == "session_current_marker"
    # Its fully opaque apex is y=8 (r=217): 0.5px beyond the r=216.5 arc outer
    # edge. Partial-alpha fringe reaches farther, stays in the approved circle,
    # and remains pinned by the PNG hash above.
    assert FACE_RADIUS - float(marker_image.get("y")) == 217 <= SESSION_SAFE_INK_RADIUS < FACE_RADIUS
    assert marker_partial_reach <= SESSION_SAFE_INK_RADIUS
    assert arc_ink_radius < FACE_RADIUS - float(marker_image.get("y")) <= arc_ink_radius + 0.5
    assert marker.find("Transform").get("value") == transforms["startAngle"]
    marker_variant = marker.find("Variant")
    assert marker_variant is not None and marker_variant.get("value") == "[CONFIGURATION.aod] == 3 ? 255 : 0"
    current_condition = arc_condition.find("Compare/Condition")
    assert current_condition is not None
    current_lower_expression = current_condition.find("Expressions/Expression[@name='sessionCurrentLower']")
    assert current_lower_expression is not None and current_lower_expression.text == "[HOUR_0_11] * 30 + [MINUTE] * 0.5 >= 109 && [HOUR_0_11] * 30 + [MINUTE] * 0.5 <= 289"
    current_parts = {
        "lower": current_condition.find("Compare[@expression='sessionCurrentLower']/PartText"),
        "upper": current_condition.find("Default/PartText"),
    }
    assert {key: part.get("name") for key, part in current_parts.items()} == {
        "lower": "session_current_time_lower", "upper": "session_current_time_upper"}
    assert all(part.get("alpha") == "0" and part.find("Variant").get("value") == "[CONFIGURATION.aod] == 3 ? 255 : 0"
               for part in current_parts.values())
    current_texts = {key: part.find("TextCircular") for key, part in current_parts.items()}
    assert all(text is not None and parameters(text) == ['icuText("HH:mm", [UTC_TIMESTAMP])'] for text in current_texts.values())
    assert {key: text.get("direction") for key, text in current_texts.items()} == {"upper": "CLOCKWISE", "lower": "COUNTER_CLOCKWISE"}
    for text in current_texts.values():
        assert {key: text.get(key) for key in ("centerX", "centerY", "width", "height", "startAngle", "endAngle", "align")} == {"centerX": "225", "centerY": "225", "width": "406", "height": "406", "startAngle": "0", "endAngle": "0", "align": "CENTER"}
        assert set(t.get("target") for t in text.findall("Transform")) == {"startAngle", "endAngle"}
        assert text.find("Font").attrib == {"color": "#ffffff", "family": "nova_mono", "size": "24", "weight": "NORMAL", "letterSpacing": "-0.05"}
    # Current r203 is
    # outside endpoints r195 but inside the arc's inner r213.5 edge; its 22°
    # path gives glyph fit beyond letter spacing alone.
    central_ink_radius = max(
        radius_for_box(127, 225 - 86.5), radius_for_box(127, 361.5 - 225),
        radius_for_box(76.5, 391 - 225),
    )
    current_radius, endpoint_radius = 203, 195
    # The approved 66x19 ink envelope has a 9.5px radial half-height, leaving exactly 1px
    # before the arc's 213.5px inner ink edge; the path is therefore not used
    # as a proxy for a collision-free painted bound.
    assert current_radius + CURRENT_TIME_INK[1] / 2 < arc_radius - 1.5
    end_labels = {part.get("name"): part for part in arc_condition.findall(".//PartText") if (part.get("name") or "").startswith("session_end_")}
    assert {name: part.find("TextCircular/Font").text for name, part in end_labels.items()} == {"session_end_sleep": "06:00", "session_end_peak": "11:00", "session_end_transition": "12:00", "session_end_trough": "17:00", "session_end_personal": "22:00"}
    assert all(part.find("TextCircular/Font/Template") is None for part in end_labels.values())
    assert all(part.find("TextCircular").get("width") == "390" for part in end_labels.values())
    assert all(part.find("TextCircular/Font").get("size") == "24" for part in end_labels.values())
    assert all(part.find("TextCircular/Font").get("weight") == "NORMAL" for part in end_labels.values())
    assert all(part.find("TextCircular/Font").get("color") == SESSION_FADED_COLOR for part in end_labels.values())
    # Derive each label path from XML, then compare its center and clockwise
    # span to the independent endpoint-placement specification.  Checking both
    # catches a mutation to either source angle for every endpoint label.
    endpoint_paths = {
        "SLEEP": end_labels["session_end_sleep"].find("TextCircular"),
        "PEAK": end_labels["session_end_peak"].find("TextCircular"),
        "TRANSITION": end_labels["session_end_transition"].find("TextCircular"),
        "TROUGH": end_labels["session_end_trough"].find("TextCircular"),
        "PERSONAL": end_labels["session_end_personal"].find("TextCircular"),
    }
    assert all(path is not None for path in endpoint_paths.values())
    endpoint_centers = endpoint_label_geometry(endpoint_paths)
    # Mutation-test every source endpoint in memory.  This proves that the
    # extraction above, rather than a duplicated fixed center, rejects either
    # angle changing for SLEEP, PEAK, TRANSITION, TROUGH, or PERSONAL.
    for label, path in endpoint_paths.items():
        for angle in ("startAngle", "endAngle"):
            source = path.get(angle)
            assert source is not None
            path.set(angle, str(float(source) + 1))
            try:
                endpoint_label_geometry(endpoint_paths)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"{label} {angle} mutation survived")
            path.set(angle, source)
    # Endpoint labels use r195. Their conservative ink box is intentionally
    # verified by Euclidean distance at every rendered current-time position;
    # neither label relies on letter spacing or a radial-only fit claim.
    assert all(part.find("Variant").get("value") == "[CONFIGURATION.aod] == 3 ? 255 : 0" for part in end_labels.values())
    endpoint_condition = next(
        (condition for condition in arc_condition.findall("Compare/Condition")
         if condition.find("Expressions/Expression[@name='sessionEndPeak']") is not None),
        None,
    )
    assert endpoint_condition is not None
    endpoint_expressions = {e.get("name"): e.text for e in endpoint_condition.findall("Expressions/Expression")}
    assert endpoint_expressions == {
        "sessionEndSleep": "[HOUR_0_23] >= 22 || !([HOUR_0_23] >= 6)",
        "sessionEndPeak": label_expressions["isPeak"],
        "sessionEndTransition": label_expressions["isTransition"],
        "sessionEndTrough": label_expressions["isTrough"],
    }
    assert {compare.get("expression"): compare.find("PartText").get("name") for compare in endpoint_condition.findall("Compare")} == {
        "sessionEndSleep": "session_end_sleep",
        "sessionEndPeak": "session_end_peak",
        "sessionEndTransition": "session_end_transition",
        "sessionEndTrough": "session_end_trough",
    }
    assert endpoint_condition.find("Default/PartText").get("name") == "session_end_personal"
    for clock_time, hour, minute, expected in (
        ("00:00", 0, 0, (6, 0, "SLEEP", 180)),
        ("05:59", 5, 59, (0, 1, "SLEEP", 180)),
        ("06:00", 6, 0, (5, 0, "PEAK", 330)),
        ("10:59", 10, 59, (0, 1, "PEAK", 330)),
        ("11:00", 11, 0, (1, 0, "TRANSITION", 360)),
        ("11:59", 11, 59, (0, 1, "TRANSITION", 360)),
        ("12:00", 12, 0, (5, 0, "TROUGH", 150)),
        ("14:30", 14, 30, (2, 30, "TROUGH", 150)),
        ("16:59", 16, 59, (0, 1, "TROUGH", 150)),
        ("17:00", 17, 0, (5, 0, "PERSONAL", 300)),
        ("21:59", 21, 59, (0, 1, "PERSONAL", 300)),
        ("22:00", 22, 0, (8, 0, "SLEEP", 180)),
        ("23:59", 23, 59, (6, 1, "SLEEP", 180)),
    ):
        actual = specified_session(hour, minute)
        assert actual == expected, (clock_time, actual)
        assert 0 <= actual[0] <= 8 and 0 <= actual[1] < 60
    # Evaluate and render the extracted WFF source at every minute against the
    # independent schedule. This kills threshold/end/operator/floor/modulo and
    # zero-padding mutations, rather than merely comparing expression text.
    previous_current_center: float | None = None
    minimum_sat_clearance = math.inf
    minimum_sat_at: tuple[int, int, str] | None = None
    minimum_sleep_sat_clearance = math.inf
    minimum_sleep_sat_at: tuple[int, int] | None = None
    sleep_minutes = 0
    sleep_sweeps: list[float] = []
    for hour in range(24):
        for minute in range(60):
            expected_hours, expected_minutes, expected_label, expected_end = specified_session(hour, minute)
            if expected_label == "SLEEP":
                sleep_minutes += 1
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
            assert enabled is True, (hour, minute, enabled)
            if enabled:
                assert evaluate_wff(transforms["endAngle"], hour, minute) == expected_end, (hour, minute, "endAngle")
                start_angle = evaluate_wff(transforms["startAngle"], hour, minute)
                assert start_angle == (hour % 12) * 30 + minute * 0.5
                lower = bool(evaluate_wff(current_lower_expression.text, hour, minute))
                current_text = current_texts["lower" if lower else "upper"]
                current_transforms = {t.get("target"): t.get("value") for t in current_text.findall("Transform")}
                upper_transforms = {t.get("target"): t.get("value") for t in current_texts["upper"].findall("Transform")}
                lower_transforms = {t.get("target"): t.get("value") for t in current_texts["lower"].findall("Transform")}
                # Direction cannot be transformed: both structural branches must
                # nevertheless describe exactly the same normalized physical arc.
                upper_path = {evaluate_wff(value, hour, minute) for value in upper_transforms.values()}
                lower_path = {evaluate_wff(value, hour, minute) for value in lower_transforms.values()}
                assert upper_path == lower_path and len(upper_path) == 2
                current_start = evaluate_wff(current_transforms["startAngle"], hour, minute)
                current_end = evaluate_wff(current_transforms["endAngle"], hour, minute)
                # Every current-time path angle is explicitly normalized, rather
                # than depending on renderer treatment of negative or >360°.
                assert 0 <= current_start <= 360 and 0 <= current_end <= 360
                span = ((current_end - current_start) if not lower else (current_start - current_end)) % 360
                assert span == CURRENT_PATH_SPAN
                current_center = ((current_start + CURRENT_PATH_SPAN / 2) if not lower else (current_start - CURRENT_PATH_SPAN / 2)) % 360
                trail = (start_angle - current_center) % 360
                assert trail == CURRENT_TRAIL
                # The source predicate is expressed in hand angle: subtracting
                # the 19° trail puts the label centre in lower 90°..270°.
                assert lower == (109 <= start_angle <= 289)
                # Upper clockwise faces glyph tops outward; lower counter-
                # clockwise faces them inward. These are the only directions
                # permitted by the structural hemisphere branch.
                assert current_text.get("direction") == ("COUNTER_CLOCKWISE" if lower else "CLOCKWISE")
                if previous_current_center is not None:
                    # Consecutive session minutes advance by 0.5° even at
                    # normalized noon wrap: no geometry branch can teleport it.
                    assert (current_center - previous_current_center) % 360 == 0.5
                previous_current_center = current_center
                marker_path_clearance = 2 * current_radius * math.sin(
                    math.radians((trail - CURRENT_PATH_SPAN / 2) / 2)
                )
                assert marker_path_clearance > MARKER_TO_CURRENT_PATH_CLEARANCE
                # Current sits behind the marker: its leading path edge stops
                # 8° before the arc begins, whose clockwise sweep continues to
                # the session endpoint. This is checked at all 1,440 minutes.
                current_leading_edge = (current_center + CURRENT_PATH_SPAN / 2) % 360
                arc_sweep = (expected_end - start_angle) % 360
                if expected_label == "SLEEP":
                    sleep_sweeps.append(arc_sweep)
                assert (start_angle - current_leading_edge) % 360 == CURRENT_TRAIL - CURRENT_PATH_SPAN / 2
                assert 0 < arc_sweep < 360
                assert not (0 <= (current_leading_edge - start_angle) % 360 <= arc_sweep)
                endpoint_angle = endpoint_centers[expected_label]
                endpoint_separation = angle_distance(current_center, endpoint_angle)
                separation = math.sqrt(
                    current_radius ** 2 + endpoint_radius ** 2
                    - 2 * current_radius * endpoint_radius
                    * math.cos(math.radians(endpoint_separation))
                )
                current_box = oriented_text_box(current_radius, current_center, *CURRENT_TIME_INK)
                endpoint_box = oriented_text_box(endpoint_radius, endpoint_angle, *WORST_ENDPOINT_INK)
                # Actual oriented measured ink boxes, rather than a weakened
                # centre-distance proxy, must have positive SAT clearance.
                sat_clearance = oriented_box_clearance(current_box, endpoint_box)
                if sat_clearance < minimum_sat_clearance:
                    minimum_sat_clearance = sat_clearance
                    minimum_sat_at = (hour, minute, expected_label)
                if expected_label == "SLEEP" and sat_clearance < minimum_sleep_sat_clearance:
                    minimum_sleep_sat_clearance = sat_clearance
                    minimum_sleep_sat_at = (hour, minute)
                assert sat_clearance > 0, (hour, minute, separation)
                # The central ink's conservative outer radius is below the
                # current path's r195.5 inner edge, so it cannot overlap the
                # circular current annotation at any angle.
                assert central_ink_radius < current_radius - 8.5
                # Endpoints are fixed at session boundaries, so prove their
                # approved 66×19px tangent boxes avoid both independently
                # measured rows and the widest 26px label at every selection.
                endpoint_box = circular_text_bounds(endpoint_radius, endpoint_angle, *WORST_ENDPOINT_INK)
                central_boxes = (
                    (105.5, 86, 348.5, 204),     # 00h: 243×118, +2/-2
                    (102, 244.5, 352, 361.5),    # 00m: 250×117, +2/-2
                    (152.5, 222.5, 301.5, 241.5),  # TRANSITION: 149×19, +2/-2
                )
                assert all(boxes_disjoint(endpoint_box, box) for box in central_boxes), (hour, minute, endpoint_box)
                expected_end_part = {"SLEEP": "session_end_sleep", "PEAK": "session_end_peak", "TRANSITION": "session_end_transition", "TROUGH": "session_end_trough", "PERSONAL": "session_end_personal"}[expected_label]
                selected_end = [name for name, source in endpoint_expressions.items() if evaluate_wff(source, hour, minute)]
                assert len(selected_end) <= 1, (hour, minute, selected_end)
                actual_end_part = ({"sessionEndSleep": "session_end_sleep", "sessionEndPeak": "session_end_peak", "sessionEndTransition": "session_end_transition", "sessionEndTrough": "session_end_trough"}[selected_end[0]] if selected_end else "session_end_personal")
                assert actual_end_part == expected_end_part, (hour, minute, actual_end_part)
    assert sleep_minutes == 480
    assert len(sleep_sweeps) == 480
    assert min(sleep_sweeps) == 0.5 and max(sleep_sweeps) == 240
    assert minimum_sleep_sat_at is not None
    # Normalized endpoint 180 with CLOCKWISE wrapping produces these boundary
    # fixtures without relying on an out-of-range 540° endpoint.
    for clock_time, hour, minute, expected_sweep in (
        ("22:00", 22, 0, 240), ("23:59", 23, 59, 180.5),
        ("00:00", 0, 0, 180), ("05:59", 5, 59, 0.5),
    ):
        hand_angle = (hour % 12) * 30 + minute * 0.5
        assert (180 - hand_angle) % 360 == expected_sweep, clock_time
    assert (14 % 12) * 30 + 30 * 0.5 == 75
    # Arc end 360° is valid WFF sweep geometry; all TextCircular source angles
    # are normalized. The existing 305→55° TextCircular pattern establishes
    # WFF's normalized clockwise wrap used by the TRANSITION 349→11° label.
    transition_sweep = sweep_angles(ET.fromstring(
        '<Arc startAngle="330" endAngle="360" direction="CLOCKWISE"/>'
    ))
    assert transition_sweep == [330.0, 360.0, 360]
    assert all(
        0 <= float(part.find("TextCircular").get(angle)) <= 360
        for part in end_labels.values() for angle in ("startAngle", "endAngle")
    )
    # Unselected branches are consumed without evaluation, matching WFF's
    # short-circuit semantics while still checking expression structure.
    assert evaluate_wff("0 && (1 / 0)", 0, 0) is False
    assert evaluate_wff("1 || (1 / 0)", 0, 0) is True
    assert evaluate_wff("1 ? 7 : (1 / 0)", 0, 0) == 7
    assert evaluate_wff("-([MINUTE] + 1)", 0, 4) == -5
    assert evaluate_wff('numberFormat("00", 2)', 0, 0) == "02"
    assert evaluate_wff('numberFormat("00", 30)', 0, 0) == "30"

    assert minimum_sat_at is not None

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
    print(
        "Nova Mono, safe adaptive arc, hour animation, AOD session countdown, and safety invariants verified; "
        "all-minute evaluation=1440 (SLEEP=480); SLEEP sweep=0.5..240°; "
        f"minimum current/endpoint SAT clearance={minimum_sat_clearance:.6f}px at "
        f"{minimum_sat_at[0]:02d}:{minimum_sat_at[1]:02d} {minimum_sat_at[2]}; "
        f"minimum SLEEP current/06:00 SAT clearance={minimum_sleep_sat_clearance:.6f}px at "
        f"{minimum_sleep_sat_at[0]:02d}:{minimum_sleep_sat_at[1]:02d}; "
        f"marker/current-path clearance={marker_path_clearance:.6f}px"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
