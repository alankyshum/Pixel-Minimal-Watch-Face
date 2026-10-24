#!/usr/bin/env python3
"""Generate and validate the repository's deterministic agent feature map."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_DIRECTORY = ROOT / ".agents/feature-map"
INDEX = MAP_DIRECTORY / "README.md"
MODULE_SOURCE_ROOTS = (
    ROOT / "watchface/src/main",
    ROOT / "phone-companion/src/main",
    ROOT / "shared-protocol/src/main",
    ROOT / "watch-provider/src/main",
)
FIELDS = ("id", "title", "aliases", "routes", "paths")
HEADINGS = ("## Sub-features", "## How to reach it", "## How to drive it", "## Gotchas")
ANDROID = "{http://schemas.android.com/apk/res/android}"


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    aliases: tuple[str, ...]
    routes: tuple[str, ...]
    paths: tuple[str, ...]
    file: str


def repository_files() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)


def owned_source_files() -> list[str]:
    return sorted(path.relative_to(ROOT).as_posix() for directory in MODULE_SOURCE_ROOTS for path in directory.rglob("*") if path.is_file())


def glob_regex(pattern: str) -> re.Pattern[str]:
    escaped = re.escape(pattern).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.compile(f"^{escaped}$")


def matches(pattern: str, path: str) -> bool:
    return glob_regex(pattern).match(path) is not None


def parse_array(value: str) -> tuple[str, ...] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        return None
    return tuple(parsed)


def parse_feature(path: Path) -> tuple[Feature | None, list[str]]:
    relative = path.relative_to(ROOT).as_posix()
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if match is None:
        return None, [f"{relative}: missing YAML frontmatter"]
    lines = match.group(1).splitlines()
    values: dict[str, str] = {}
    errors: list[str] = []
    for line in lines:
        field_match = re.match(r"^([a-z]+):\s*(.*)$", line)
        if field_match is None:
            errors.append(f"{relative}: invalid frontmatter line {line!r}")
            continue
        field, value = field_match.groups()
        if field in values:
            errors.append(f"{relative}: duplicate frontmatter field '{field}'")
        values[field] = value
    errors.extend(f"{relative}: missing frontmatter field '{field}'" for field in FIELDS if field not in values)
    errors.extend(f"{relative}: unknown frontmatter field '{field}'" for field in values if field not in FIELDS)
    feature_id = values.get("id", "")
    title = values.get("title", "")
    aliases = parse_array(values.get("aliases", ""))
    routes = parse_array(values.get("routes", ""))
    paths = parse_array(values.get("paths", ""))
    if not re.fullmatch(r"[a-z0-9-]+", feature_id):
        errors.append(f"{relative}: id must use lowercase kebab-case")
    if not title.strip():
        errors.append(f"{relative}: title must not be empty")
    if relative != f".agents/feature-map/{feature_id}.md":
        errors.append(f"{relative}: id '{feature_id}' must match its file name")
    for name, value in (("aliases", aliases), ("routes", routes), ("paths", paths)):
        if value is None:
            errors.append(f"{relative}: frontmatter '{name}' must be a JSON string array")
    errors.extend(f"{relative}: missing '{heading}' section" for heading in HEADINGS if f"\n{heading}\n" not in text)
    if errors:
        return None, errors
    assert aliases is not None and routes is not None and paths is not None
    return Feature(feature_id, title, aliases, routes, paths, relative), []


def discover_entry_points() -> list[str]:
    entries: set[str] = set()
    watchface = ET.parse(ROOT / "watchface/src/main/watchface-template.xml").getroot()
    entries.add("watchface:face")
    entries.update(f"watchface:slot:{slot.get('slotId')}" for slot in watchface.findall(".//ComplicationSlot"))
    entries.update(
        f"watchface:config:{configuration.get('id')}"
        for configuration in watchface.findall("./UserConfigurations/*")
        if configuration.tag.endswith("Configuration") and configuration.get("id")
    )
    if watchface.find(".//Variant[@mode='AMBIENT']") is not None:
        entries.add("watchface:ambient")
    session_option = watchface.find("./UserConfigurations/ListConfiguration[@id='aod']/ListOption[@id='3']")
    if session_option is not None and any(
        time.get("hourFormat") == "SYNC_TO_DEVICE"
        and time.find("Variant[@mode='AMBIENT'][@value='[CONFIGURATION.aod] == 3 ? 255 : 0']") is not None
        for time in watchface.findall(".//TimeText")
    ):
        entries.add("watchface:aod-style:session-countdown")
    entries.update(f"watchface:font:{family}" for family in {font.get("family") for font in watchface.findall(".//Font")} if family)

    phone_manifest = ET.parse(ROOT / "phone-companion/src/main/AndroidManifest.xml").getroot()
    for activity in phone_manifest.findall(".//activity"):
        if activity.find(f".//action[@{ANDROID}name='android.intent.action.MAIN']") is not None:
            entries.add(f"phone-companion:activity:{activity.get(ANDROID + 'name')}")
    for receiver in phone_manifest.findall(".//receiver"):
        if receiver.findall(".//action"):
            entries.add(f"phone-companion:receiver:{receiver.get(ANDROID + 'name')}")

    provider_manifest = ET.parse(ROOT / "watch-provider/src/main/AndroidManifest.xml").getroot()
    complication_action = "android.support.wearable.complications.ACTION_COMPLICATION_UPDATE_REQUEST"
    for service in provider_manifest.findall(".//service"):
        if service.find(f".//action[@{ANDROID}name='{complication_action}']") is not None:
            entries.add(f"watch-provider:complication:{service.get(ANDROID + 'name')}")
    return sorted(entries)


def inspect() -> tuple[list[Feature], list[str], str]:
    feature_paths = sorted(path for path in MAP_DIRECTORY.glob("*.md") if path.name != "README.md")
    parsed = [parse_feature(path) for path in feature_paths]
    features = [feature for feature, _ in parsed if feature is not None]
    errors = [error for _, feature_errors in parsed for error in feature_errors]
    all_files = repository_files()
    source_files = owned_source_files()
    entries = discover_entry_points()
    for feature in features:
        for pattern in feature.paths:
            if not any(matches(pattern, file) for file in all_files):
                errors.append(f"{feature.file}: path '{pattern}' matches no files")
    for source in source_files:
        owners = [feature.id for feature in features if any(matches(pattern, source) for pattern in feature.paths)]
        if not owners:
            errors.append(f"Unowned source file '{source}'")
        elif len(owners) > 1:
            errors.append(f"Source file '{source}' is owned by multiple features: {', '.join(owners)}")
    claims = [(route, feature) for feature in features for route in feature.routes]
    for entry in entries:
        owners = [feature.id for route, feature in claims if route == entry]
        if not owners:
            errors.append(f"Unclaimed entry point '{entry}'")
        elif len(owners) > 1:
            errors.append(f"Entry point '{entry}' is claimed by multiple features: {', '.join(owners)}")
    for route, feature in claims:
        if route not in entries:
            errors.append(f"{feature.file}: entry point '{route}' is not discoverable")
    return features, errors, render_index(features)


def render_index(features: list[Feature]) -> str:
    rows = []
    entry_rows = []
    for feature in sorted(features, key=lambda item: item.id):
        routes = ", ".join(f"`{route}`" for route in feature.routes)
        rows.append(f"| [{feature.id}](./{feature.id}.md) | {feature.title} | {', '.join(feature.aliases)} | {routes} |")
        entry_rows.extend((route, feature) for route in feature.routes)
    entry_lines = [f"| `{route}` | [{feature.title}](./{feature.id}.md) |" for route, feature in sorted(entry_rows, key=lambda item: item[0])]
    return "\n".join((
        "# Agent Feature Map", "",
        "For vague or feature-level work, find the user's words below and read the matching feature file before changing code. Update the owning feature file with user-facing behavior changes; do not hand-edit this generated index.", "",
        "## Features", "", "| ID | Title | User vocabulary and aliases | Entry points |", "| --- | --- | --- | --- |",
        *rows, "", "## Entry point to feature", "", "| Entry point | Feature |", "| --- | --- |", *entry_lines, "",
    ))


def check_or_generate(check: bool) -> int:
    features, errors, rendered = inspect()
    stale = not INDEX.exists() or INDEX.read_text() != rendered
    if check and stale:
        errors.append(".agents/feature-map/README.md is stale; run 'python3 tools/feature_map.py'")
    if errors:
        print("Feature map validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    if check:
        print(f"Feature map OK: {len(features)} features claim {len(discover_entry_points())} entry points.")
    else:
        MAP_DIRECTORY.mkdir(parents=True, exist_ok=True)
        INDEX.write_text(rendered)
        print("Updated .agents/feature-map/README.md.")
    return 0


def changed_features(ref: str) -> int:
    features, errors, _ = inspect()
    if errors:
        print("Feature map validation failed; fix it before selecting changed features.", file=sys.stderr)
        return 1
    result = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMRD", ref, "--"], cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    changed = result.stdout.splitlines()
    for feature in features:
        if any(matches(pattern, file) for pattern in feature.paths for file in changed):
            print(feature.file)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--changed", metavar="REF")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all:
        features, errors, _ = inspect()
        if errors:
            return check_or_generate(True)
        print("\n".join(feature.file for feature in features))
        return 0
    if args.changed:
        return changed_features(args.changed)
    return check_or_generate(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
