#!/usr/bin/env python3
"""Validate config/watchface-sessions.json and generate the session WFF fragments."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/watchface-sessions.json"
TEMPLATE = ROOT / "watchface/src/main/watchface-template.xml"
GENERATED = ROOT / "watchface/build/generated/session-res/raw/watchface.xml"


def parse_time(value: object, *, final: bool = False) -> int:
    pattern = r"(?:[01]\d|2[0-3]):[0-5]\d" + (r"|24:00" if final else "")
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError(f"invalid time {value!r}; expected HH:MM" + (" or 24:00" if final else ""))
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def schedule(path: Path = CONFIG) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid session JSON: {error}") from error
    rows = data.get("sessions") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("sessions must be a non-empty array")
    result: list[dict] = []
    cursor = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip():
            raise ValueError(f"session {index}: name must be a non-empty string")
        name = row["name"].strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 _-]{0,31}", name):
            raise ValueError(f"session {index}: invalid name")
        key = f"s{index}_{re.sub(r'[^A-Za-z0-9_]', '_', name.lower())}"
        if "duration" in row:
            if set(row) != {"name", "duration"}:
                raise ValueError(f"session {index}: duration cannot be combined with start/end")
            duration = row["duration"]
            if isinstance(duration, bool) or not isinstance(duration, int) or not 0 < duration <= 1440 or duration % 60:
                raise ValueError(f"session {index}: duration must be a positive whole number of hours in minutes")
            start, end = cursor, cursor + duration
        elif set(row) == {"name", "start", "end"}:
            start = parse_time(row["start"])
            end = parse_time(row["end"], final=index == len(rows) - 1)
            if start != cursor:
                raise ValueError(f"session {index}: gap/overlap at {cursor // 60:02d}:{cursor % 60:02d}")
            if end <= start:
                raise ValueError(f"session {index}: end must be after start")
            if start % 60 or end % 60:
                raise ValueError(f"session {index}: times must be on hour boundaries")
        else:
            raise ValueError(f"session {index}: provide duration or start and end")
        if start != cursor or end > 1440:
            raise ValueError(f"session {index}: schedule must be contiguous and within one day")
        result.append({"name": name, "key": key, "start": start, "end": end})
        cursor = end
    if cursor != 1440:
        raise ValueError(f"schedule covers {cursor} minutes, not a full 24-hour day")
    return result


def condition(row: dict) -> str:
    return f"[HOUR_0_23] >= {row['start'] // 60} && !([HOUR_0_23] >= {row['end'] // 60})"


def chain(rows: list[dict], value) -> str:
    return "".join(f"({condition(row)} ? {value(row)} : " for row in rows[:-1]) + str(value(rows[-1])) + ")" * (len(rows) - 1)


def endpoint_block(rows: list[dict]) -> tuple[str, str]:
    """Generate the visible endpoint labels, merging equal target instants."""
    targets: list[dict] = []
    for row in rows:
        target_end = rows[0]["end"] if row is rows[-1] and len(rows) > 1 and rows[0]["name"] == row["name"] else row["end"]
        existing = next((item for item in targets if item["end"] == target_end), None)
        if existing is None:
            existing = {"end": target_end, "name": row["name"], "conditions": []}
            targets.append(existing)
        existing["conditions"].append(condition(row))
    parts = []
    for index, target in enumerate(targets):
        end = target["end"]
        angle = 360 if end % 720 == 0 else (end // 60 * 30) % 360
        center = (angle + 15) % 360
        clockwise = not 90 <= center <= 270
        start, finish = ((center - 11) % 360, (center + 11) % 360) if clockwise else ((center + 11) % 360, (center - 11) % 360)
        if clockwise and finish == 0: finish = 360
        if not clockwise and start == 0: start = 360
        expression_name = f"sessionEnd{target['name'].lower().capitalize()}" if len(rows) == 6 and target["name"] in {"SLEEP", "PEAK", "TRANSITION", "TROUGH", "PERSONAL"} else f"sessionEnd_{index}"
        base_part_name = f"session_end_{re.sub(r'[^A-Za-z0-9_]', '_', target['name'].lower())}"
        part_name = base_part_name if len(rows) == 6 and target["name"] in {"SLEEP", "PEAK", "TRANSITION", "TROUGH", "PERSONAL"} else f"{base_part_name}_{index}"
        text = f"{end // 60:02d}:00" if end < 1440 else "24:00"
        direction = "CLOCKWISE" if clockwise else "COUNTER_CLOCKWISE"
        part = f'<PartText name="{part_name}" width="450" height="450" x="0" y="0" alpha="0"><Variant mode="AMBIENT" target="alpha" value="[CONFIGURATION.aod] == 3 ? 255 : 0"/><TextCircular centerX="225" centerY="225" width="406" height="406" startAngle="{start:g}" endAngle="{finish:g}" direction="{direction}" align="CENTER"><Font color="#cccccc" family="nova_mono" size="24" weight="NORMAL" letterSpacing="-0.05">{text}</Font></TextCircular></PartText>'
        parts.append((expression_name, part))
    if len(rows) == 1:
        # WFF v2 requires an Expressions/Compare pair even when the single
        # session is unconditional.
        compares = f'<Compare expression="{parts[0][0]}">{parts[0][1]}</Compare>'
        expressions = [f'<Expression name="{parts[0][0]}"><![CDATA[1 == 1]]></Expression>']
        return "\n                        ".join(expressions), compares
    expressions = []
    for index, target in enumerate(targets):
        name = parts[index][0]
        expressions.append(f'<Expression name="{name}"><![CDATA[{" || ".join(f"({item})" for item in target["conditions"])}]]></Expression>')
    compares = "\n                    ".join(f'<Compare expression="{name}">{part}</Compare>' for name, part in parts[:-1])
    if parts:
        compares += ("\n                    " if compares else "") + f'<Default>{parts[-1][1]}</Default>'
    return "\n                        ".join(expressions), compares


def render(source: str, rows: list[dict]) -> str:
    # Last is Default; every preceding row gets its own indexed identifier.
    expressions = "\n                ".join(
        f'<Expression name="is_{row["key"]}"><![CDATA[{condition(row)}]]></Expression>' for row in rows[:-1]
    )
    compares = "\n            ".join(
        f'<Compare expression="is_{row["key"]}"><PartText name="session_countdown_{row["key"]}" width="450" height="26" x="4" y="217" alpha="0"><Variant mode="AMBIENT" target="alpha" value="[CONFIGURATION.aod] == 3 ? 255 : 0"/><Text align="CENTER"><Font color="#cccccc" family="nova_mono" size="26" weight="NORMAL" letterSpacing="-0.05">{row["name"]}</Font></Text></PartText></Compare>'
        for row in rows[:-1]
    )
    last = rows[-1]
    compares += f'\n            <Default><PartText name="session_countdown_{last["key"]}" width="450" height="26" x="4" y="217" alpha="0"><Variant mode="AMBIENT" target="alpha" value="[CONFIGURATION.aod] == 3 ? 255 : 0"/><Text align="CENTER"><Font color="#cccccc" family="nova_mono" size="26" weight="NORMAL" letterSpacing="-0.05">{last["name"]}</Font></Text></PartText></Default>'
    label_pattern = re.compile(r"(<!-- Condition owns time-varying label selection; Variant only gates AOD mode\. -->\n        <Condition>\n            <Expressions>\n).*?(\n            </Expressions>).*?(\n        </Condition>)", re.S)
    if len(rows) == 1:
        expressions = f'<Expression name="is_{last["key"]}"><![CDATA[1 == 1]]></Expression>'
        compares = compares.replace(
            f'<Default><PartText name="session_countdown_{last["key"]}"',
            f'<Compare expression="is_{last["key"]}"><PartText name="session_countdown_{last["key"]}"',
        ).replace('</PartText></Default>', '</PartText></Compare>')
        single_label_pattern = re.compile(r"(<!-- Condition owns time-varying label selection; Variant only gates AOD mode\. -->\n        <Condition>\n).*?(\n        </Condition>)", re.S)
        source, count = single_label_pattern.subn(r"\1            <Expressions>" + expressions + r"</Expressions>\n            " + compares + r"\2", source, count=1)
    else:
        label_replacement = r"\1                " + expressions + r"\2" + compares + r"\3"
        source, count = label_pattern.subn(label_replacement, source, count=1)
    if count != 1:
        raise ValueError(f"expected exactly one session label block, found {count}")

    endpoint_expressions, endpoint_compares = endpoint_block(rows)
    endpoint_pattern = re.compile(r"(<Condition>\s*<Expressions>\s*)<Expression name=\"sessionEnd[^\"]+\".*?(</Condition>)", re.S)
    source, count = endpoint_pattern.subn(r"\1" + endpoint_expressions + r"\n                    </Expressions>\n                    " + endpoint_compares + r"\2", source, count=1)
    if count != 1:
        raise ValueError(f"expected exactly one endpoint label block, found {count}")

    midnight_merge = len(rows) > 1 and rows[0]["name"] == rows[-1]["name"]
    end_expression = chain(rows, lambda row: row["end"] + (rows[0]["end"] if row is rows[-1] and midnight_merge else 0))
    countdown_pattern = re.compile(r'expression="numberFormat\(&quot;00&quot;, floor\(.*?\) ([/%]) 60\)\)"')
    escaped_end = end_expression.replace("&", "&amp;")
    source, count = countdown_pattern.subn(
        lambda match: f'expression="numberFormat(&quot;00&quot;, floor(({escaped_end} - ([HOUR_0_23] * 60 + [MINUTE])) {match.group(1)} 60))"',
        source,
        count=2,
    )
    if count != 2:
        raise ValueError(f"expected exactly two countdown expressions, found {count}")

    # 12:00 and 24:00 normalize to 360; other boundaries use their hour angle.
    def arc_endpoint(row: dict) -> int:
        target_end = rows[0]["end"] if row is rows[-1] and midnight_merge else row["end"]
        return 360 if target_end % 720 == 0 else (target_end // 60 * 30) % 360
    arc_expression = chain(rows, arc_endpoint)
    arc_pattern = re.compile(r'(<PartDraw name="session_countdown_arc".*?<Transform target="endAngle" value=")[^"]*("/>)', re.S)
    source, count = arc_pattern.subn(
        lambda match: f'{match.group(1)}{arc_expression.replace("&", "&amp;")}{match.group(2)}',
        source,
        count=1,
    )
    if count != 1:
        raise ValueError(f"expected exactly one arc end-angle transform, found {count}")
    return source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=GENERATED)
    args = parser.parse_args()
    try:
        template = TEMPLATE.read_text(encoding="utf-8")
        generated = render(template, schedule())
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if args.check and current != generated:
            print("error: generated watchface.xml is stale; run python3 tools/generate_watchface_sessions.py", flush=True)
            return 1
        if not args.check:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(generated, encoding="utf-8")
        return 0
    except (OSError, ValueError, re.error) as error:
        print(f"error: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
