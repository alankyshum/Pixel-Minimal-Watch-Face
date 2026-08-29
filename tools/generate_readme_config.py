#!/usr/bin/env python3
"""Generate the marker-bounded WFF2 configuration inventory in README.md."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WATCHFACE = ROOT / "watchface/src/main/res/raw/watchface.xml"
STRINGS = ROOT / "watchface/src/main/res/values/strings.xml"
BEGIN = "<!-- BEGIN GENERATED CONFIGURATION INVENTORY -->"
END = "<!-- END GENERATED CONFIGURATION INVENTORY -->"


def fail(message: str) -> None:
    raise ValueError(message)


def parse_xml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as error:
        fail(f"malformed XML in {path.relative_to(ROOT)}: {error}")


def strings() -> dict[str, str]:
    root = parse_xml(STRINGS)
    values: dict[str, str] = {}
    for node in root.findall("string"):
        name = node.get("name")
        if not name or name in values:
            fail(f"duplicate or missing string name in {STRINGS.relative_to(ROOT)}")
        values[name] = "".join(node.itertext()).strip()
    return values


def label(resources: dict[str, str], identifier: str, where: str) -> str:
    if identifier not in resources:
        fail(f"missing string resource {identifier!r} referenced by {where}")
    return resources[identifier]


def inventory() -> str:
    resources = strings()
    root = parse_xml(WATCHFACE)
    configurations = root.find("UserConfigurations")
    if configurations is None:
        fail("watchface.xml has no UserConfigurations element")

    lines = ["### User configurations", "", "| ID | Label | Type | Default | Options |", "| --- | --- | --- | --- | --- |"]
    known: dict[str, set[str]] = {}
    for config in list(configurations):
        if config.tag not in {"ColorConfiguration", "ListConfiguration", "BooleanConfiguration"}:
            continue
        identifier = config.get("id")
        display_name = config.get("displayName")
        default = config.get("defaultValue")
        if not identifier or identifier in known or not display_name or default is None:
            fail(f"configuration has duplicate/missing ID, label, or default: {ET.tostring(config, encoding='unicode')}")
        option_tag = "ColorOption" if config.tag == "ColorConfiguration" else "ListOption"
        options: list[str] = []
        option_ids: set[str] = set()
        for option in config.findall(option_tag):
            option_id, option_label = option.get("id"), option.get("displayName")
            if not option_id or option_id in option_ids or not option_label:
                fail(f"configuration {identifier!r} has duplicate/missing option ID or label")
            option_ids.add(option_id)
            options.append(f"`{option_id}` {label(resources, option_label, f'option {option_id} in {identifier}')}")
        if config.tag == "BooleanConfiguration":
            if list(config):
                fail(f"boolean configuration {identifier!r} must not declare option elements")
            option_ids = {"TRUE", "FALSE"}
            options = ["`FALSE` Off", "`TRUE` On"]
        if default not in option_ids:
            fail(f"configuration {identifier!r} has invalid default {default!r}")
        known[identifier] = option_ids
        kind = {"ColorConfiguration": "color", "ListConfiguration": "list", "BooleanConfiguration": "boolean"}[config.tag]
        lines.append(f"| `{identifier}` | {label(resources, display_name, f'configuration {identifier}')} | {kind} | `{default}` | {'; '.join(options)} |")

    slots = root.findall(".//Scene/ComplicationSlot")
    seen_slots: set[str] = set()
    lines += ["", "### Complication slots", "", "| Slot | Label | Bounds | Supported types | Default policy |", "| --- | --- | --- | --- | --- |"]
    for slot in slots:
        slot_id, display_name = slot.get("slotId"), slot.get("displayName")
        if not slot_id or slot_id in seen_slots or not display_name:
            fail("complication slot has duplicate/missing ID or label")
        seen_slots.add(slot_id)
        policy = slot.find("DefaultProviderPolicy")
        if policy is None:
            fail(f"slot {slot_id!r} has no DefaultProviderPolicy")
        policy_text = ", ".join(f"`{key}`={value}" for key, value in sorted(policy.attrib.items()))
        bounds = " × ".join(slot.get(key, "?") for key in ("width", "height")) + " at " + ",".join(slot.get(key, "?") for key in ("x", "y"))
        lines.append(f"| `{slot_id}` | {label(resources, display_name, f'slot {slot_id}')} | {bounds} | `{slot.get('supportedTypes', '')}` | {policy_text} |")

    flavors = configurations.find("Flavors")
    if flavors is not None:
        flavor_ids: set[str] = set()
        lines += ["", "### Flavors", "", "| ID | Label | Assignments |", "| --- | --- | --- |"]
        for flavor in flavors.findall("Flavor"):
            flavor_id = flavor.get("id")
            if not flavor_id or flavor_id in flavor_ids:
                fail("flavor has duplicate or missing ID")
            flavor_ids.add(flavor_id)
            assignments: list[str] = []
            used_configs: set[str] = set()
            for assignment in flavor.findall("Configuration"):
                config_id, option_id = assignment.get("id"), assignment.get("optionId")
                if not config_id or not option_id or config_id in used_configs or config_id not in known or option_id not in known[config_id]:
                    fail(f"flavor {flavor_id!r} has invalid/duplicate assignment")
                used_configs.add(config_id)
                assignments.append(f"`{config_id}`=`{option_id}`")
            lines.append(f"| `{flavor_id}` | {flavor.get('displayName', '')} | {', '.join(assignments) or '—'} |")
        default_flavor = flavors.get("defaultValue")
        if default_flavor not in flavor_ids:
            fail(f"Flavors has invalid default {default_flavor!r}")
        lines.append(f"\nDefault flavor: `{default_flavor}`.")
    return "\n".join(lines) + "\n"


def replace_generated(readme: str, generated: str) -> str:
    if readme.count(BEGIN) != 1 or readme.count(END) != 1:
        fail("README must contain exactly one begin and one end configuration marker")
    start, end = readme.index(BEGIN), readme.index(END)
    if start > end:
        fail("README configuration markers are out of order")
    return readme[: start + len(BEGIN)] + "\n\n" + generated + readme[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when README inventory is stale")
    args = parser.parse_args()
    try:
        current = README.read_text(encoding="utf-8")
        expected = replace_generated(current, inventory())
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.check:
        if current != expected:
            print("error: README configuration inventory is stale; run python3 tools/generate_readme_config.py", file=sys.stderr)
            return 1
        return 0
    README.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
