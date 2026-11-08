#!/usr/bin/env bash
# Aether GUI — macOS packaging (.dmg)
#
#   ./installer/macos/package.sh <version> [arm64|x64]
#
# Expects dist/AetherGUI.app (from `pyinstaller --windowed`) and ./aether.
set -euo pipefail

VERSION="${1:?usage: package.sh <version> [arm64|x64]}"
ARCH="${2:-arm64}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/installer/output"
APP="$ROOT/dist/AetherGUI.app"

[ -d "$APP" ] || { echo "missing $APP — run pyinstaller first" >&2; exit 1; }
[ -f "$ROOT/aether" ] || { echo "missing $ROOT/aether" >&2; exit 1; }

mkdir -p "$OUT"
echo "== packaging Aether GUI $VERSION (macOS $ARCH) =="

# The engine has to live beside the GUI executable inside the bundle: the app
# resolves it from dirname(sys.executable), which is Contents/MacOS.
cp "$ROOT/aether" "$APP/Contents/MacOS/aether"
chmod 0755 "$APP/Contents/MacOS/aether"

# Copying a file into the bundle invalidates the signature PyInstaller applied.
# Apple Silicon refuses to run an unsigned/ad-hoc-broken arm64 bundle at all, so
# re-sign ad-hoc after the copy. (No Developer ID here — see the README note.)
codesign --force --deep --sign - "$APP" 2>/dev/null || \
  echo "  warning: ad-hoc codesign failed (the app may need right-click > Open)" >&2

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

DMG="$OUT/AetherGUI-${VERSION}-macOS-${ARCH}.dmg"
rm -f "$DMG"
hdiutil create -volname "Aether GUI" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null

echo "  built $(basename "$DMG")"
ls -lh "$OUT"
