#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="1.2.0"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="python3"
fi
BUILD_DIR="$ROOT/build/$VERSION/macos-arm64"
DIST_DIR="$ROOT/dist/$VERSION/macos-arm64"
DMG_DIR="$ROOT/releases/$VERSION/macos"
DMG_PATH="$DMG_DIR/SpaceMan-ICC-Bridge-$VERSION-macos-arm.dmg"

for path in "$ROOT/preview_v110.py" \
            "$ROOT/packaging/macos/SpaceMan.spec" \
            "$ROOT/tools/mhc2gen/MHC2Gen" \
            "$ROOT/tools/mhc2gen/runtime/MHC2Gen" \
            "$ROOT/assets/icon-sp.icns" \
            "$ROOT/assets/background.png"; do
    if [[ ! -e "$path" ]]; then
        printf 'Required build input is missing: %s\n' "$path" >&2
        exit 1
    fi
done

"$PYTHON" -m PyInstaller --noconfirm \
    --workpath "$BUILD_DIR" \
    --distpath "$DIST_DIR" \
    "$ROOT/packaging/macos/SpaceMan.spec"

APP="$DIST_DIR/SpaceMan ICC Bridge.app"
if [[ ! -d "$APP" ]]; then
    printf 'Expected application bundle was not created: %s\n' "$APP" >&2
    exit 1
fi

chmod +x "$APP/Contents/Resources/tools/mhc2gen/MHC2Gen" \
         "$APP/Contents/Resources/tools/mhc2gen/runtime/MHC2Gen"

if ! command -v create-dmg >/dev/null 2>&1; then
    printf 'create-dmg is required to build the disk image.\n' >&2
    exit 1
fi

mkdir -p "$DMG_DIR"
if [[ -e "$DMG_PATH" ]]; then
    printf 'Refusing to overwrite existing release artifact: %s\n' "$DMG_PATH" >&2
    exit 1
fi
STAGE_DIR="$(mktemp -d "$BUILD_DIR/dmg-stage.XXXXXX")"
trap 'rm -rf "$STAGE_DIR"' EXIT
cp -R "$APP" "$STAGE_DIR/"
create-dmg \
    --volname "SpaceMan ICC Bridge" \
    --window-pos 200 120 \
    --window-size 800 400 \
    --icon-size 100 \
    --icon "SpaceMan ICC Bridge.app" 200 150 \
    --background "$ROOT/assets/background.png" \
    --hide-extension "SpaceMan ICC Bridge.app" \
    --app-drop-link 600 150 \
    "$DMG_PATH" "$STAGE_DIR"

printf 'Built application: %s\nBuilt disk image: %s\n' "$APP" "$DMG_PATH"
