#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

/usr/bin/python3 - <<'PY'
import gi
from cryptography.fernet import Fernet
gi.require_version("Gtk", "4.0")
print("deps ok")
PY

/usr/bin/python3 -m py_compile koplyx/main.py koplyx/__init__.py

if command -v xdotool >/dev/null 2>&1 || command -v wtype >/dev/null 2>&1; then
  printf '%s\n' "auto paste tool ok"
else
  printf '%s\n' "auto paste tool missing: install xdotool on X11 or wtype on Wayland"
fi

if gdbus call --session --dest org.kde.StatusNotifierWatcher --object-path /StatusNotifierWatcher --method org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
  printf '%s\n' "tray watcher ok"
else
  printf '%s\n' "tray watcher missing: install/enable AppIndicator support for your desktop"
fi

KOPLYX_SMOKE_HOME="$(mktemp -d)"
export XDG_CONFIG_HOME="$KOPLYX_SMOKE_HOME/config"
export XDG_DATA_HOME="$KOPLYX_SMOKE_HOME/data"

/usr/bin/python3 - <<'PY'
from koplyx.main import (
    CONFIG_DIR,
    DATA_DIR,
    Config,
    CryptoBox,
    HistoryStore,
    file_title_from_uris,
    autostart_desktop_path,
    install_autostart_file,
    remove_autostart_file,
    private_preview,
    text_excerpt,
    uri_list_from_bytes,
)

config = Config()
assert config.get("start_hidden") is True
assert config.get("autostart_enabled") is True
crypto = CryptoBox()
store = HistoryStore(crypto, config)
store.add("text", "text/plain", b"koplyx smoke pinned", "koplyx smoke pinned")
item = store.list("")[0]
store.toggle_pin(item.id)
pinned = store.list("", pinned_text_only=True)
assert len(pinned) == 1
assert pinned[0].preview != "koplyx smoke pinned"
assert store.payload(pinned[0].id)[2] == b"koplyx smoke pinned"
assert text_excerpt(store.payload(pinned[0].id)[2]) == "koplyx smoke pinned"
assert private_preview("text", "text/plain", b"secret visible only in memory") == "Texte, 29 caracteres"
image_png = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\x0e\x82\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)
assert store.add("image", "image/png", image_png, "Image PNG, 1 x 1, 1 KB")
image_item = next(item for item in store.list("") if item.kind == "image")
assert image_item.preview == "Image PNG, 1 x 1, 1 KB"
file_data = b"file:///tmp/koplyx-smoke.txt\r\n"
assert store.add("file", "text/uri-list", file_data, "koplyx-smoke.txt")
file_item = next(item for item in store.list("") if item.kind == "file")
assert file_item.preview == "Fichier, 1 element"
assert uri_list_from_bytes(store.payload(file_item.id)[2]) == ["file:///tmp/koplyx-smoke.txt"]
assert file_title_from_uris(["file:///tmp/koplyx-smoke.txt"]) == "koplyx-smoke.txt"
assert (CONFIG_DIR.stat().st_mode & 0o777) == 0o700
assert (DATA_DIR.stat().st_mode & 0o777) == 0o700
assert ((CONFIG_DIR / "config.json").stat().st_mode & 0o777) == 0o600
assert ((DATA_DIR / "history.db").stat().st_mode & 0o777) == 0o600
assert install_autostart_file()
autostart = autostart_desktop_path()
assert autostart.exists()
assert "--hidden" in autostart.read_text(encoding="utf-8")
assert remove_autostart_file()
assert not autostart.exists()
store.clear()
print("storage ok")
PY

timeout 3s ./bin/koplyx --hidden >/tmp/koplyx-smoke.out 2>/tmp/koplyx-smoke.err || code=$?
code="${code:-0}"
if [ "$code" != "0" ] && [ "$code" != "124" ]; then
  cat /tmp/koplyx-smoke.err >&2
  rm -rf "$KOPLYX_SMOKE_HOME"
  exit "$code"
fi
rm -rf "$KOPLYX_SMOKE_HOME"

printf '%s\n' "gtk startup ok"
printf '%s\n' "smoke test passed"
