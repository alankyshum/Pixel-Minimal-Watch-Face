#!/bin/sh
# Validate with Google's official WFF validator from a checksum-pinned source tree.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}
REVISION=44b1855d445686ac8de5dbc95003d6f8e6623643
ARCHIVE_SHA256=d32b020cd7130b0d5d0a576878b452785b46c1c614642f4af55a937ef551ed4d
SOURCE_BUILD_SHA256=a7f1991d18f31d5e679b44d9e3215df36f6ef8b4266ced731c04150ee404736d
CACHE_ROOT=${XDG_CACHE_HOME:-"$HOME/.cache"}/pixel-minimal-wff-validator
ARCHIVE="$CACHE_ROOT/google-watchface-$REVISION.tar.gz"
SOURCE="$CACHE_ROOT/watchface-$REVISION"
JAR="$SOURCE/third_party/wff/specification/validator/build/libs/wff-validator.jar"
URL="https://codeload.github.com/google/watchface/tar.gz/$REVISION"

if [ ! -x "$JAVA_HOME/bin/java" ]; then
    echo "error: Java 17 is required; set JAVA_HOME to a JDK with bin/java" >&2
    exit 1
fi
JAVA="$JAVA_HOME/bin/java"
if ! "$JAVA" -version 2>&1 | grep -Eq 'version "17\.|openjdk 17\.'; then
    echo "error: Java 17 is required; JAVA_HOME points to an incompatible runtime" >&2
    exit 1
fi
mkdir -p "$CACHE_ROOT"
if [ ! -f "$ARCHIVE" ] || ! printf '%s  %s\n' "$ARCHIVE_SHA256" "$ARCHIVE" | shasum -a 256 -c - >/dev/null 2>&1; then
    rm -f "$ARCHIVE" "$ARCHIVE.tmp"
    curl --fail --location --silent --show-error --output "$ARCHIVE.tmp" "$URL"
    mv "$ARCHIVE.tmp" "$ARCHIVE"
fi
printf '%s  %s\n' "$ARCHIVE_SHA256" "$ARCHIVE" | shasum -a 256 -c -

source_is_verified() {
    test -f "$SOURCE/third_party/wff/gradlew" &&
        printf '%s  %s\n' "$SOURCE_BUILD_SHA256" "$SOURCE/third_party/wff/specification/validator/build.gradle" | shasum -a 256 -c - >/dev/null 2>&1
}

jar_is_verified() {
    test -f "$JAR"
}

# Never execute a cache until the extracted pinned source input is verified and
# its validator JAR exists. Rebuilding is the only recovery path for a bad
# cache. The JAR is rebuilt locally from the checksum-pinned source; Gradle's
# archive metadata makes its byte digest vary across supported Gradle versions.
if ! source_is_verified || ! jar_is_verified; then
    rm -rf "$SOURCE"
    tar -xzf "$ARCHIVE" -C "$CACHE_ROOT"
    (cd "$SOURCE/third_party/wff" && bash ./gradlew :specification:validator:executable-jar)
fi

# A cache hit is trusted only when it still corresponds to the verified archive
# and retains the pinned source's validator build inputs and executable JAR.
source_is_verified
jar_is_verified
tar -tzf "$ARCHIVE" | grep -Fqx "watchface-$REVISION/third_party/wff/specification/validator/build.gradle"

"$JAVA" -jar "$JAR" 2 --stop-on-fail "$ROOT/watchface/build/generated/session-res/raw/watchface.xml"
