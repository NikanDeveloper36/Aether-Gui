#!/usr/bin/env bash
# Aether GUI — Linux packaging (.deb, .rpm, .AppImage)
#
#   ./installer/linux/package.sh <version> [arch]
#
# Expects, in the repo root:
#   dist/AetherGUI   — the PyInstaller build
#   aether           — the core engine
#   assets/icon-256.png
#
# Outputs into installer/output/.
set -euo pipefail

VERSION="${1:?usage: package.sh <version> [arch]}"
ARCH="${2:-amd64}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/installer/output"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

case "$ARCH" in
  amd64)  RPM_ARCH=x86_64;  APPIMAGE_ARCH=x86_64 ;;
  arm64)  RPM_ARCH=aarch64; APPIMAGE_ARCH=aarch64 ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$OUT"
echo "== packaging Aether GUI $VERSION ($ARCH) =="

# ── shared file tree ────────────────────────────────────────────────
TREE="$WORK/root"
mkdir -p "$TREE/usr/lib/aether-gui" \
         "$TREE/usr/bin" \
         "$TREE/usr/share/applications" \
         "$TREE/usr/share/icons/hicolor/256x256/apps" \
         "$TREE/usr/share/doc/aether-gui"

install -m 0755 "$ROOT/dist/AetherGUI"        "$TREE/usr/lib/aether-gui/AetherGUI"
install -m 0755 "$ROOT/aether"                "$TREE/usr/lib/aether-gui/aether"
install -m 0644 "$ROOT/assets/icon-256.png"   "$TREE/usr/lib/aether-gui/icon.png"
install -m 0644 "$ROOT/assets/icon-256.png"   "$TREE/usr/share/icons/hicolor/256x256/apps/aether-gui.png"
install -m 0644 "$ROOT/LICENSE"               "$TREE/usr/share/doc/aether-gui/copyright"

# The engine must sit next to the GUI binary: the app looks in its own
# directory first, so the pair stays together under /usr/lib/aether-gui.
cat > "$TREE/usr/bin/aether-gui" <<'LAUNCHER'
#!/bin/sh
exec /usr/lib/aether-gui/AetherGUI "$@"
LAUNCHER
chmod 0755 "$TREE/usr/bin/aether-gui"

cat > "$TREE/usr/share/applications/aether-gui.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Aether GUI
GenericName=Network Client
Comment=Aether networking core client
Exec=aether-gui
Icon=aether-gui
Terminal=false
Categories=Network;Security;
Keywords=aether;vpn;proxy;tunnel;warp;masque;wireguard;
StartupWMClass=Aether
DESKTOP

# ── .deb ────────────────────────────────────────────────────────────
DEB="$WORK/deb"
cp -a "$TREE" "$DEB"
mkdir -p "$DEB/DEBIAN"
INSTALLED_KB=$(du -sk --exclude=DEBIAN "$DEB" | cut -f1)
cat > "$DEB/DEBIAN/control" <<CONTROL
Package: aether-gui
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_KB
Maintainer: Nikan Developer <NikanDeveloper36@users.noreply.github.com>
Homepage: https://github.com/NikanDeveloper36/Aether-Gui
Depends: libc6, libx11-6, libxext6, libxrender1, libxft2
Recommends: libgtk-3-0
Description: Aether GUI — desktop client for the Aether networking core
 A graphical interface for the Aether networking core (MASQUE, WireGuard,
 WARP-in-WARP). Includes the core engine.
CONTROL

dpkg-deb --root-owner-group -Zxz --build "$DEB" \
  "$OUT/AetherGUI-${VERSION}-Linux-${ARCH}.deb" >/dev/null
echo "  built AetherGUI-${VERSION}-Linux-${ARCH}.deb"

# ── .rpm ────────────────────────────────────────────────────────────
if command -v rpmbuild >/dev/null 2>&1; then
  TOP="$WORK/rpmbuild"
  mkdir -p "$TOP"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
  cat > "$TOP/SPECS/aether-gui.spec" <<SPEC
Name:           aether-gui
Version:        $VERSION
Release:        1
Summary:        Desktop client for the Aether networking core
License:        GPL-3.0-or-later
URL:            https://github.com/NikanDeveloper36/Aether-Gui
BuildArch:      $RPM_ARCH
Requires:       libX11, libXext, libXrender, libXft
AutoReqProv:    no
%description
A graphical interface for the Aether networking core (MASQUE, WireGuard,
WARP-in-WARP). Includes the core engine.
%install
mkdir -p %{buildroot}
cp -a $TREE/. %{buildroot}/
%files
/usr/bin/aether-gui
/usr/lib/aether-gui
/usr/share/applications/aether-gui.desktop
/usr/share/icons/hicolor/256x256/apps/aether-gui.png
/usr/share/doc/aether-gui/copyright
%changelog
* Sun Nov 08 2026 Nikan Developer <NikanDeveloper36@users.noreply.github.com> - $VERSION
- Initial package
SPEC
  rpmbuild --define "_topdir $TOP" --define "_binary_payload w9.xzdio" \
           -bb "$TOP/SPECS/aether-gui.spec" >/dev/null 2>&1 \
    || rpmbuild --define "_topdir $TOP" -bb "$TOP/SPECS/aether-gui.spec" >/dev/null
  find "$TOP/RPMS" -name '*.rpm' -exec cp {} "$OUT/AetherGUI-${VERSION}-Linux-${ARCH}.rpm" \;
  echo "  built AetherGUI-${VERSION}-Linux-${ARCH}.rpm"
else
  echo "  skipping .rpm (rpmbuild not installed)" >&2
fi

# ── .AppImage ───────────────────────────────────────────────────────
APPDIR="$WORK/AetherGUI.AppDir"
mkdir -p "$APPDIR/usr/bin"
install -m 0755 "$ROOT/dist/AetherGUI" "$APPDIR/usr/bin/AetherGUI"
install -m 0755 "$ROOT/aether"         "$APPDIR/usr/bin/aether"
install -m 0644 "$ROOT/assets/icon-256.png" "$APPDIR/aether-gui.png"
install -m 0644 "$ROOT/assets/icon-256.png" "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/AetherGUI" "$@"
APPRUN
chmod 0755 "$APPDIR/AppRun"

cat > "$APPDIR/aether-gui.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Aether GUI
Comment=Aether networking core client
Exec=AetherGUI
Icon=aether-gui
Terminal=false
Categories=Network;Security;
StartupWMClass=Aether
DESKTOP

if command -v appimagetool >/dev/null 2>&1; then
  ARCH="$APPIMAGE_ARCH" appimagetool --no-appstream "$APPDIR" \
    "$OUT/AetherGUI-${VERSION}-Linux-${ARCH}.AppImage" >/dev/null
  chmod +x "$OUT/AetherGUI-${VERSION}-Linux-${ARCH}.AppImage"
  echo "  built AetherGUI-${VERSION}-Linux-${ARCH}.AppImage"
else
  echo "  skipping .AppImage (appimagetool not installed)" >&2
fi

echo "== done =="
ls -lh "$OUT"
