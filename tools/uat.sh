#!/bin/sh
# End-to-end Watch Face Format UAT on isolated Wear OS emulator AVDs.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}
JAVA_HOME=${JAVA_HOME:-/Users/alanshum/Applications/IB Gateway 10.48/.install4j/jre.bundle/Contents/Home}
export JAVA_HOME ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
ADB="$SDK/platform-tools/adb"
EMULATOR="$SDK/emulator/emulator"
AVDMANAGER="$SDK/cmdline-tools/latest/bin/avdmanager"
IMAGE=${UAT_SYSTEM_IMAGE:-system-images;android-36;android-wear-signed;arm64-v8a}
PACKAGE=com.alanshum.pixelminimal.longtext
APK="$ROOT/watchface/build/outputs/apk/debug/watchface-debug.apk"
PROVIDER_APK="$ROOT/watch-provider/build/outputs/apk/debug/watch-provider-debug.apk"
EVIDENCE=${UAT_EVIDENCE_DIR:-$ROOT/evidence/uat}
DEVICE=all
MODE=all
STYLE=all
KEEP_AVD=0
EMU_PID=

usage() {
    cat <<'EOF'
Usage: tools/uat.sh [--device all|pixel-watch-3-41mm|pixel-watch-3-45mm|oneplus-watch-4]
                     [--mode all|interactive|ambient]
                     [--style all|dimmed|session-countdown] [--keep-avd]

Runs a Wear OS 6 WFF emulator, installs and selects the real debug watch face,
captures screenshots, and applies image assertions. The Session Countdown style
is selected through the system watch-face editor with UIAutomator; no private adb
configuration API or release-default change is used.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --device) DEVICE=$2; shift 2 ;;
        --mode) MODE=$2; shift 2 ;;
        --style) STYLE=$2; shift 2 ;;
        --keep-avd) KEEP_AVD=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

case "$MODE" in all|interactive|ambient) ;; *) echo "Invalid mode: $MODE" >&2; exit 2;; esac
case "$STYLE" in all|dimmed|session-countdown) ;; *) echo "Invalid style: $STYLE" >&2; exit 2;; esac

command -v python3 >/dev/null
for tool in "$ADB" "$EMULATOR" "$AVDMANAGER"; do
    [ -x "$tool" ] || { echo "Required Android SDK tool not found: $tool" >&2; exit 2; }
done
[ -x "$JAVA_HOME/bin/java" ] || { echo "JDK 17 not found at JAVA_HOME=$JAVA_HOME" >&2; exit 2; }

SPECS=$(python3 "$ROOT/tools/uat_assertions.py" specs --tsv)
if [ "$DEVICE" != all ] && ! printf '%s\n' "$SPECS" | cut -f1 | grep -qx "$DEVICE"; then
    echo "Unknown device: $DEVICE" >&2
    exit 2
fi

cleanup() {
    if [ -n "$EMU_PID" ]; then
        "$ADB" -s "$SERIAL" emu kill >/dev/null 2>&1 || kill "$EMU_PID" >/dev/null 2>&1 || true
        wait "$EMU_PID" 2>/dev/null || true
        EMU_PID=
    fi
}
trap cleanup EXIT INT TERM

choose_port() {
    port=5580
    while "$ADB" devices | grep -q "^emulator-$port[[:space:]]"; do port=$((port + 2)); done
    printf '%s\n' "$port"
}

wait_for_boot() {
    waited=0
    "$ADB" -s "$SERIAL" wait-for-device
    while [ "$("$ADB" -s "$SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != 1 ]; do
        waited=$((waited + 2))
        [ "$waited" -lt 300 ] || { echo "$SERIAL did not boot within 300 seconds" >&2; return 1; }
        sleep 2
    done
    "$ADB" -s "$SERIAL" shell getprop ro.build.characteristics | grep -q watch || {
        echo "$SERIAL booted a non-Wear image" >&2; return 1;
    }
    [ -n "$("$ADB" -s "$SERIAL" shell getprop ro.cw_build.wear_sdk.version | tr -d '\r')" ] || {
        echo "$SERIAL has no Wear OS runtime" >&2; return 1;
    }
    "$ADB" -s "$SERIAL" shell pm path com.google.wear.watchface.runtime >/dev/null || {
        echo "$SERIAL does not include the WFF runtime" >&2; return 1;
    }
}

create_avd() {
    key=$1 width=$2 height=$3 density=$4
    AVD="pixel-minimal-uat-$key"
    # AVD Manager supplies the official Wear OS hardware profile and system image;
    # the target device's verified panel geometry overrides only display properties.
    printf 'no\n' | "$AVDMANAGER" create avd --force --name "$AVD" --package "$IMAGE" --device wearos_small_round >/dev/null
    AVD_DIR=$($EMULATOR -list-avds >/dev/null 2>&1; find "${ANDROID_AVD_HOME:-${ANDROID_SDK_HOME:-$HOME}/.android/avd}" -maxdepth 1 -type d -name "$AVD.avd" -print -quit)
    [ -n "$AVD_DIR" ] || {
        # avdmanager reports the canonical path in the .ini even when SDK_HOME is customized.
        ini=$(find "$HOME/.android/avd" "$SDK/.android/avd" -maxdepth 1 -name "$AVD.ini" -print -quit 2>/dev/null || true)
        [ -n "$ini" ] && AVD_DIR=$(sed -n 's/^path=//p' "$ini")
    }
    [ -f "$AVD_DIR/config.ini" ] || { echo "Cannot locate generated AVD $AVD" >&2; return 1; }
    python3 - "$AVD_DIR/config.ini" "$width" "$height" "$density" <<'PY'
import sys
from pathlib import Path
path, width, height, density = Path(sys.argv[1]), *sys.argv[2:]
lines = path.read_text().splitlines()
updates = {"hw.lcd.width": width, "hw.lcd.height": height, "hw.lcd.density": density, "hw.lcd.circular": "true"}
kept = [line for line in lines if line.split("=", 1)[0].strip() not in updates]
path.write_text("\n".join(kept + [f"{key}={value}" for key, value in updates.items()]) + "\n")
PY
}

verify_current_face() {
    "$ADB" -s "$SERIAL" shell pm path "$PACKAGE" >/dev/null || { echo "$PACKAGE is not installed" >&2; return 1; }
    dump="$OUT/current-face.txt"
    { "$ADB" -s "$SERIAL" shell dumpsys wallpaper; "$ADB" -s "$SERIAL" shell dumpsys activity services com.google.wear.watchface.runtime; } >"$dump" 2>&1
    grep -q 'mWallpaperComponent=ComponentInfo{com.google.wear.watchface.runtime/' "$dump" || {
        echo "The active wallpaper is not the WFF runtime (see $dump)" >&2
        return 1
    }
    grep -q 'result=1, data="Favorite Id=' "$OUT/set-watchface.txt" || {
        echo "Wear OS did not accept $PACKAGE as a WFF favorite (see $OUT/set-watchface.txt)" >&2
        return 1
    }
}

capture_interactive() {
    CAPTURE_OUT=$1
    mkdir -p "$CAPTURE_OUT"
    "$ADB" -s "$SERIAL" shell input keyevent KEYCODE_WAKEUP
    "$ADB" -s "$SERIAL" shell am broadcast -a com.google.android.wearable.app.DEBUG_SYSUI --es operation show-watchface >/dev/null
    sleep 4
    "$ADB" -s "$SERIAL" exec-out screencap -p >"$CAPTURE_OUT/interactive.png"
    python3 "$ROOT/tools/uat_assertions.py" check --device "$key" --mode interactive "$CAPTURE_OUT/interactive.png" >"$CAPTURE_OUT/interactive.json"
}

capture_ambient() {
    CAPTURE_OUT=$1 ASSERT_MODE=$2
    mkdir -p "$CAPTURE_OUT"
    "$ADB" -s "$SERIAL" shell am broadcast -a com.google.android.wearable.app.DEBUG_SYSUI --es operation show-watchface >/dev/null
    sleep 3
    "$ADB" -s "$SERIAL" shell settings put secure doze_enabled 1
    "$ADB" -s "$SERIAL" shell settings put global always_on_display_enabled 1
    # A powered emulator otherwise replaces the face with its charging animation.
    "$ADB" -s "$SERIAL" shell dumpsys battery unplug
    "$ADB" -s "$SERIAL" shell input keyevent KEYCODE_SLEEP
    waited=0
    while ! "$ADB" -s "$SERIAL" shell dumpsys power | grep -q 'mWakefulness=Dozing'; do
        waited=$((waited + 1))
        [ "$waited" -lt 30 ] || { echo "$SERIAL did not enter ambient (Dozing) within 30 seconds" >&2; return 1; }
        sleep 1
    done
    sleep 2
    {
        echo '== settings =='
        echo "doze_enabled=$("$ADB" -s "$SERIAL" shell settings get secure doze_enabled | tr -d '\r')"
        echo "always_on_display_enabled=$("$ADB" -s "$SERIAL" shell settings get global always_on_display_enabled | tr -d '\r')"
        echo '== dumpsys power =='
        "$ADB" -s "$SERIAL" shell dumpsys power
        echo '== dumpsys window =='
        "$ADB" -s "$SERIAL" shell dumpsys window
        echo '== dumpsys display =='
        "$ADB" -s "$SERIAL" shell dumpsys display
        echo '== watch-face runtime =='
        "$ADB" -s "$SERIAL" shell dumpsys activity services com.google.wear.watchface.runtime
    } >"$CAPTURE_OUT/ambient-state.txt"
    grep -q 'mWakefulness=Dozing' "$CAPTURE_OUT/ambient-state.txt" || { echo "PowerManager did not confirm Dozing (see $CAPTURE_OUT/ambient-state.txt)" >&2; return 1; }
    grep -q 'Display{#0 state=DOZE' "$CAPTURE_OUT/ambient-state.txt" || { echo "WindowManager did not confirm display DOZE (see $CAPTURE_OUT/ambient-state.txt)" >&2; return 1; }
    grep -q 'mAwake=false' "$CAPTURE_OUT/ambient-state.txt" || { echo "WindowManager still reports awake (see $CAPTURE_OUT/ambient-state.txt)" >&2; return 1; }
    "$ADB" -s "$SERIAL" exec-out screencap -p >"$CAPTURE_OUT/ambient.png"
    python3 "$ROOT/tools/uat_assertions.py" check --device "$key" --mode "$ASSERT_MODE" "$CAPTURE_OUT/ambient.png" >"$CAPTURE_OUT/ambient.json"
    "$ADB" -s "$SERIAL" shell input keyevent KEYCODE_WAKEUP
}

run_device() {
    key=$1 name=$2 width=$3 height=$4 density=$5 round=$6
    [ "$DEVICE" = all ] || [ "$DEVICE" = "$key" ] || return 0
    printf '\n== %s (%sx%s @ %sdpi, round=%s) ==\n' "$name" "$width" "$height" "$density" "$round"
    create_avd "$key" "$width" "$height" "$density"
    PORT=$(choose_port); SERIAL="emulator-$PORT"; OUT="$EVIDENCE/$key"
    mkdir -p "$OUT"
    "$EMULATOR" -avd "$AVD" -port "$PORT" -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data -gpu swiftshader_indirect </dev/null >"$OUT/emulator.log" 2>&1 &
    EMU_PID=$!
    wait_for_boot
    actual_size=$("$ADB" -s "$SERIAL" shell wm size | sed -n 's/.*size: //p' | tail -1 | tr -d '\r')
    actual_density=$("$ADB" -s "$SERIAL" shell wm density | sed -n 's/.*density: //p' | tail -1 | tr -d '\r')
    [ "$actual_size" = "${width}x${height}" ] && [ "$actual_density" = "$density" ] || {
        echo "AVD geometry mismatch: expected ${width}x${height}@$density, got $actual_size@$actual_density" >&2; return 1;
    }
    "$ADB" -s "$SERIAL" install -r "$APK" >"$OUT/install.txt"
    "$ADB" -s "$SERIAL" install -r "$PROVIDER_APK" >"$OUT/install-provider.txt"
    "$ADB" -s "$SERIAL" shell am broadcast -a com.google.android.wearable.app.DEBUG_SURFACE --es operation set-watchface --es watchFaceId "$PACKAGE" >"$OUT/set-watchface.txt"
    sleep 5
    verify_current_face
    python3 "$ROOT/tools/uat_device.py" --adb "$ADB" --serial "$SERIAL" --evidence "$OUT/complication-assignments.txt"
    case "$MODE" in all|interactive) capture_interactive "$OUT/normal";; esac
    if [ "$STYLE" = all ] || [ "$STYLE" = dimmed ]; then
        case "$MODE" in all|ambient) capture_ambient "$OUT/dimmed-aod" ambient;; esac
    fi
    if [ "$MODE" = all ] && { [ "$STYLE" = all ] || [ "$STYLE" = dimmed ]; }; then
        python3 "$ROOT/tools/uat_assertions.py" compare --device "$key" "$OUT/normal/interactive.png" "$OUT/dimmed-aod/ambient.png" >"$OUT/dimmed-comparison.json"
    fi
    if [ "$STYLE" = all ] || [ "$STYLE" = session-countdown ]; then
        "$ADB" -s "$SERIAL" shell input keyevent KEYCODE_WAKEUP
        python3 "$ROOT/tools/uat_device.py" --adb "$ADB" --serial "$SERIAL" --evidence "$OUT/session-countdown-aod/editor.xml" --aod-style "Session Countdown"
        case "$MODE" in all|ambient) capture_ambient "$OUT/session-countdown-aod" session-countdown;; esac
    fi
    printf 'PASS %s (%s); evidence: %s\n' "$key" "$MODE" "$OUT"
    cleanup
    if [ "$KEEP_AVD" -eq 0 ]; then "$AVDMANAGER" delete avd --name "$AVD" >/dev/null 2>&1 || true; fi
}

mkdir -p "$EVIDENCE"
cd "$ROOT"
bash ./gradlew :watchface:assembleDebug :watch-provider:assembleDebug
[ -f "$APK" ] || { echo "Debug APK not produced: $APK" >&2; exit 1; }
[ -f "$PROVIDER_APK" ] || { echo "Debug provider APK not produced: $PROVIDER_APK" >&2; exit 1; }

TAB=$(printf '\t')
printf '%s\n' "$SPECS" >"$EVIDENCE/device-specs.tsv"
while IFS="$TAB" read -r key name width height density round <&3; do
    run_device "$key" "$name" "$width" "$height" "$density" "$round"
done 3<"$EVIDENCE/device-specs.tsv"
