#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="$(tr -d '[:space:]' < VERSION)"
DIST_DIR="$ROOT_DIR/dist"
STAGE_DIR="$DIST_DIR/koplyx-$VERSION"
DEB_ROOT="$DIST_DIR/deb-root"
PACKAGE_NAME="koplyx"

rm -rf "$DIST_DIR"
mkdir -p "$STAGE_DIR" "$DEB_ROOT"

./scripts/build-html-docs.py

cp -R .github assets bin docs koplyx packaging scripts snap CODE_OF_CONDUCT.md CONTRIBUTING.md LICENSE README.md SECURITY.md VERSION "$STAGE_DIR/"
find "$STAGE_DIR" -type d -name __pycache__ -prune -exec rm -rf {} +

tar -C "$DIST_DIR" -czf "$DIST_DIR/koplyx-$VERSION-linux-source.tar.gz" "koplyx-$VERSION"

mkdir -p \
  "$DEB_ROOT/DEBIAN" \
  "$DEB_ROOT/opt/koplyx" \
  "$DEB_ROOT/usr/bin" \
  "$DEB_ROOT/usr/share/applications" \
  "$DEB_ROOT/usr/share/icons/hicolor/scalable/apps" \
  "$DEB_ROOT/usr/share/metainfo"

cp -R assets bin docs koplyx packaging scripts CODE_OF_CONDUCT.md CONTRIBUTING.md LICENSE README.md SECURITY.md VERSION "$DEB_ROOT/opt/koplyx/"
find "$DEB_ROOT/opt/koplyx" -type d -name __pycache__ -prune -exec rm -rf {} +

cat > "$DEB_ROOT/usr/bin/koplyx" <<'EOF'
#!/usr/bin/env sh
exec /usr/bin/python3 /opt/koplyx/koplyx/main.py "$@"
EOF
chmod 0755 "$DEB_ROOT/usr/bin/koplyx"

cp packaging/dev.limax.koplyx.desktop "$DEB_ROOT/usr/share/applications/dev.limax.koplyx.desktop"
cp assets/icons/dev.limax.koplyx.svg "$DEB_ROOT/usr/share/icons/hicolor/scalable/apps/dev.limax.koplyx.svg"
cp packaging/metainfo/dev.limax.koplyx.metainfo.xml "$DEB_ROOT/usr/share/metainfo/dev.limax.koplyx.metainfo.xml"

cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Maintainer: Limax <limax@example.local>
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-gdkpixbuf-2.0, python3-cryptography, python3-pil, python3-dbus, python3-secretstorage, dbus-user-session, xdotool
Recommends: gnome-shell-extension-appindicator
Description: Local encrypted clipboard history for Linux
 Koplyx stores text and image clipboard history locally with encryption,
 search, pinned text, quick restore, optional auto paste, and system tray support.
EOF

cat > "$DEB_ROOT/DEBIAN/postinst" <<'EOF'
#!/usr/bin/env sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 0755 "$DEB_ROOT/DEBIAN/postinst"

if command -v fakeroot >/dev/null 2>&1; then
  fakeroot dpkg-deb --build "$DEB_ROOT" "$DIST_DIR/koplyx_${VERSION}_all.deb"
else
  dpkg-deb --build "$DEB_ROOT" "$DIST_DIR/koplyx_${VERSION}_all.deb"
fi

(
  cd "$DIST_DIR"
  sha256sum ./*.tar.gz ./*.deb > SHA256SUMS
)
printf '%s\n' "Artifacts written to $DIST_DIR"
