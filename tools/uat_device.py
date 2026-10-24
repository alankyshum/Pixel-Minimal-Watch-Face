#!/usr/bin/env python3
"""Device-side UI automation used by the Wear OS UAT harness."""

from __future__ import annotations

import argparse
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path


class DeviceAutomationError(RuntimeError):
    pass


class Device:
    def __init__(self, adb: str, serial: str) -> None:
        self.command = [adb, "-s", serial]
        size = self.shell("wm", "size", capture=True)
        match = re.search(r"(\d+)x(\d+)", size)
        if match is None:
            raise DeviceAutomationError(f"cannot determine display size from {size!r}")
        self.width, self.height = map(int, match.groups())

    def run(self, *arguments: str, capture: bool = False) -> str:
        result = subprocess.run(
            [*self.command, *arguments], check=True, text=True,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        )
        return result.stdout if capture else ""

    def shell(self, *arguments: str, capture: bool = False) -> str:
        return self.run("shell", *arguments, capture=capture)

    def dump(self) -> ET.Element:
        for _ in range(4):
            self.shell("uiautomator", "dump", "/sdcard/uat-window.xml")
            try:
                return ET.fromstring(self.run("exec-out", "cat", "/sdcard/uat-window.xml", capture=True))
            except ET.ParseError:
                time.sleep(0.5)
        raise DeviceAutomationError("uiautomator did not produce valid XML")

    def tap(self, node: ET.Element) -> None:
        values = [int(value) for value in re.findall(r"\d+", node.get("bounds", ""))]
        if len(values) != 4:
            raise DeviceAutomationError(f"node has no usable bounds: {node.attrib}")
        left, top, right, bottom = values
        self.shell("input", "tap", str((left + right) // 2), str((top + bottom) // 2))
        time.sleep(1)

    def swipe(self, left: bool) -> None:
        y = str(self.height // 2)
        points = (str(self.width * 4 // 5), y, str(self.width // 5), y) if left else (str(self.width // 5), y, str(self.width * 4 // 5), y)
        self.shell("input", "swipe", *points, "250")
        time.sleep(0.5)


def find(root: ET.Element, predicate) -> ET.Element | None:
    return next((node for node in root.iter() if predicate(node)), None)


def open_editor(device: Device) -> ET.Element:
    device.shell("input", "keyevent", "KEYCODE_WAKEUP")
    edit = None
    for _ in range(3):
        device.shell(
            "am", "broadcast", "-a", "com.google.android.wearable.app.DEBUG_SYSUI",
            "--es", "operation", "show-watchface",
        )
        time.sleep(2)
        device.shell("input", "swipe", "204", "204", "204", "204", "1200")
        for _ in range(4):
            time.sleep(1)
            edit = find(device.dump(), lambda node: node.get("content-desc") == "Edit watch face")
            if edit is not None:
                break
        if edit is not None:
            break
    if edit is None:
        raise DeviceAutomationError("system watch-face picker did not expose Edit watch face")
    device.tap(edit)
    return device.dump()


def editor_page(device: Device, label: str) -> ET.Element:
    root = open_editor(device)
    pages = []
    for _ in range(24):
        pages.append([node.get("content-desc", "") for node in root.iter() if node.get("content-desc")])
        if find(root, lambda node: "page_indicator" not in node.get("resource-id", "")
                and label.lower() in (node.get("content-desc", "") + " " + node.get("text", "")).lower()) is not None:
            return root
        # Reopening the editor resumes on the last page. AOD Style is before
        # Complications in this face's configuration order.
        device.swipe(left=label.lower() != "aod style")
        root = device.dump()
    raise DeviceAutomationError(f"system editor did not expose the {label} page; pages: {pages}")


def open_complications(device: Device) -> ET.Element:
    root = open_editor(device)
    for _ in range(9):
        if find(root, lambda node: "Swipe to edit Other options" in node.get("content-desc", "")) is not None:
            return root
        device.swipe(left=True)
        root = device.dump()
    raise DeviceAutomationError("system editor did not expose the Complications page")


def select_aod_style(device: Device, style: str, evidence: Path) -> None:
    """Select a WFF list option through the supported system editor UI."""
    root = editor_page(device, "AOD Style")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(ET.tostring(root, encoding="unicode") + "\n")

    def selected(tree: ET.Element) -> bool:
        return find(tree, lambda node: style.lower() in (node.get("text", "") + " " + node.get("content-desc", "")).lower()) is not None

    if selected(root):
        device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
        return
    # The system editor exposes WFF list configurations as a rotary list. Drive
    # the same public editor control used by the emulator crown and verify its
    # accessibility model after every detent.
    for direction, count in (("-1", 6), ("1", 12)):
        for _ in range(count):
            device.shell("input", "rotaryencoder", "scroll", "--axis", f"SCROLL,{direction}")
            time.sleep(0.5)
            root = device.dump()
            evidence.write_text(evidence.read_text() + ET.tostring(root, encoding="unicode") + "\n")
            if selected(root):
                device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
                time.sleep(2)
                return
    # Also handle runtimes that expose a clickable option picker.
    page = find(root, lambda node: node.get("resource-id", "").endswith("editor_list_current_option_chip"))
    if page is not None and page.get("clickable") == "true":
        device.tap(page)
        root = device.dump()
        choice = find(root, lambda node: style.lower() in (node.get("text", "") + " " + node.get("content-desc", "")).lower())
        if choice is not None:
            device.tap(choice)
            device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
            evidence.write_text(evidence.read_text() + ET.tostring(device.dump(), encoding="unicode") + "\n")
            return
        device.shell("input", "keyevent", "KEYCODE_BACK")
        root = editor_page(device, "AOD Style")
    for _ in range(6):
        device.shell("input", "swipe", str(device.width // 2), str(device.height * 3 // 4), str(device.width // 2), str(device.height // 4), "300")
        time.sleep(0.7)
        root = device.dump()
        evidence.write_text(evidence.read_text() + ET.tostring(root, encoding="unicode") + "\n")
        if selected(root):
            device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
            time.sleep(2)
            return
    raise DeviceAutomationError(f"system editor did not offer AOD style {style!r}")


def select_provider(device: Device, slot: str, provider: str) -> ET.Element:
    root = open_complications(device)

    def wanted_slot(node: ET.Element) -> bool:
        if node.get("clickable") != "true":
            return False
        values = [int(value) for value in re.findall(r"\d+", node.get("bounds", ""))]
        if len(values) != 4:
            return False
        left, top, right, bottom = values
        return (
            slot == "left" and right < device.width / 2 and device.height * 0.25 < top < device.height * 0.70
        ) or (
            slot == "top" and top < device.height * 0.40
            and right - left > device.width * 0.70
        )

    target = find(root, wanted_slot)
    if target is None:
        clickables = [node.attrib for node in root.iter() if node.get("clickable") == "true"]
        raise DeviceAutomationError(f"system editor did not expose the {slot} complication slot; clickable nodes: {clickables}")
    device.tap(target)
    for _ in range(18):
        root = device.dump()
        choice = find(
            root,
            lambda node: node.get("clickable") == "true"
            and (node.get("text", "") == provider or node.get("text", "").startswith(provider + ",")),
        )
        if choice is not None:
            device.tap(choice)
            return root
        device.shell("input", "swipe", "204", "340", "204", "80", "250")
        time.sleep(0.4)
    raise DeviceAutomationError(f"system complication picker did not list {provider!r}")


def assign(adb: str, serial: str, evidence: Path) -> None:
    device = Device(adb, serial)
    device.shell("logcat", "-c")
    select_provider(device, "left", "Day and date")
    device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
    time.sleep(1)
    select_provider(device, "top", "UAT PERSONAL timer")
    device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
    time.sleep(2)

    # Reopening the editor makes SysUI log its authoritative slot/provider model.
    open_complications(device)
    device.shell("input", "keyevent", "KEYCODE_STEM_PRIMARY")
    log = device.shell("logcat", "-d", capture=True)
    assignment_lines = [
        line for line in log.splitlines()
        if "EditingFavInfo" in line or "PersonalTimerComplicationService" in line
    ]
    evidence.write_text("\n".join(assignment_lines) + "\n")
    if not any("PersonalTimerComplicationService" in line and "complicationInfos=" in line for line in assignment_lines):
        raise DeviceAutomationError("SysUI did not confirm the PERSONAL provider assignment")
    if not any("DayAndDateProviderService" in line and "complicationInfos=" in line for line in assignment_lines):
        raise DeviceAutomationError("SysUI did not confirm the Day & Date assignment")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--aod-style")
    args = parser.parse_args()
    try:
        if args.aod_style:
            select_aod_style(Device(args.adb, args.serial), args.aod_style, args.evidence)
        else:
            assign(args.adb, args.serial, args.evidence)
    except (DeviceAutomationError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
