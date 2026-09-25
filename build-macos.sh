#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="1.1.0"
PYTHON="${PYTHON:-python3}"
BUILD_DIR="$ROOT/build/$VERSION/macos-arm64"
DIST_DIR="$ROOT/dist/$VERSION/macos-arm64"

for path in "$ROOT/preview_v110.py" \
            "$ROOT/packaging/macos/SpaceMan.spec" \
            "$ROOT/tools/mhc2gen/MHC2Gen" \
            "$ROOT/tools/mhc2gen/runtime/MHC2Gen" \
            "$ROOT/assets/icon-sp.icns"; do
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

printf 'Built application: %s\n' "$APP"
