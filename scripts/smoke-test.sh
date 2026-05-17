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
from koplyx.main import CONFIG_DIR, DATA_DIR, Config, CryptoBox, HistoryStore

config = Config()
crypto = CryptoBox()
store = HistoryStore(crypto, config)
store.add("text", "text/plain", b"koplyx smoke pinned", "koplyx smoke pinned")
item = store.list("")[0]
store.toggle_pin(item.id)
pinned = store.list("", pinned_text_only=True)
assert len(pinned) == 1
assert pinned[0].preview != "koplyx smoke pinned"
assert store.payload(pinned[0].id)[2] == b"koplyx smoke pinned"
assert (CONFIG_DIR.stat().st_mode & 0o777) == 0o700
assert (DATA_DIR.stat().st_mode & 0o777) == 0o700
assert ((CONFIG_DIR / "config.json").stat().st_mode & 0o777) == 0o600
assert ((DATA_DIR / "history.db").stat().st_mode & 0o777) == 0o600
store.clear()
print("storage ok")
PY

rm -rf "$KOPLYX_SMOKE_HOME"

timeout 3s ./bin/koplyx --hidden >/tmp/koplyx-smoke.out 2>/tmp/koplyx-smoke.err || code=$?
code="${code:-0}"
if [ "$code" != "0" ] && [ "$code" != "124" ]; then
  cat /tmp/koplyx-smoke.err >&2
  exit "$code"
fi

printf '%s\n' "gtk startup ok"
printf '%s\n' "smoke test passed"
