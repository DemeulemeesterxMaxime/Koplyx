#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

install_xdotool_if_possible() {
  if [ "${XDG_SESSION_TYPE:-}" != "x11" ] || command -v xdotool >/dev/null 2>&1; then
    return 0
  fi
  if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    printf '%s\n' "xdotool est requis pour le collage automatique sur X11."
    printf '%s\n' "Tentative d'installation via apt. Saisissez votre mot de passe sudo si demande."
    sudo apt-get update
    sudo apt-get install -y xdotool
  else
    printf '%s\n' "Installez xdotool pour activer le collage automatique sur X11."
  fi
}

install_xdotool_if_possible

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

cat > "$BIN_DIR/koplyx" <<EOF
#!/usr/bin/env sh
exec /usr/bin/python3 "$ROOT_DIR/koplyx/main.py" "\$@"
EOF
chmod +x "$BIN_DIR/koplyx"

cp "$ROOT_DIR/packaging/dev.limax.koplyx.desktop" "$APP_DIR/dev.limax.koplyx.desktop"
cp "$ROOT_DIR/assets/icons/dev.limax.koplyx.svg" "$ICON_DIR/dev.limax.koplyx.svg"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

printf '%s\n' "Koplyx installe. Lancez avec: koplyx"
