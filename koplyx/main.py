#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import signal
import sqlite3
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from cryptography.fernet import Fernet, InvalidToken

from koplyx import APP_ID, APP_NAME
from koplyx.portal_keyboard import PortalKeyboard
from koplyx.system_setup import (
    command_available,
    run_privileged,
    xorg_sessions,
)


POLL_INTERVAL_MS = 900
DEFAULT_CONFIG = {
    "max_items": 500,
    "max_age_days": 30,
    "max_storage_mb": 256,
    "shortcut": "<Ctrl><Alt>V",
    "capture_text": True,
    "capture_images": True,
    "show_tray": True,
    "start_hidden": True,
    "autostart_enabled": True,
    "pinned_history_position": "top",
    "wayland_restore_token": "",
    "paste_backend": "auto",
    "onboarding_completed": False,
}

PINNED_HISTORY_POSITIONS = {"top", "bottom", "pinned_only"}
PINNED_HISTORY_POSITION_LABELS = {
    "top": "Épingles en haut",
    "bottom": "Épingles en bas",
    "pinned_only": "Épingles uniquement dans Épinglés",
}
MAX_TOOLTIP_CHARS = 4000
PASTE_BACKENDS = {"auto", "wtype", "xwayland", "xorg", "ydotool", "portal", "clipboard_only"}

MODIFIER_KEYS = {
    Gdk.KEY_Shift_L,
    Gdk.KEY_Shift_R,
    Gdk.KEY_Control_L,
    Gdk.KEY_Control_R,
    Gdk.KEY_Alt_L,
    Gdk.KEY_Alt_R,
    Gdk.KEY_Meta_L,
    Gdk.KEY_Meta_R,
    Gdk.KEY_Super_L,
    Gdk.KEY_Super_R,
    Gdk.KEY_Hyper_L,
    Gdk.KEY_Hyper_R,
}


def xdg_path(env_name: str, default_suffix: str) -> Path:
    return Path(os.environ.get(env_name, Path.home() / default_suffix)).expanduser()


CONFIG_DIR = xdg_path("XDG_CONFIG_HOME", ".config") / "koplyx"
DATA_DIR = xdg_path("XDG_DATA_HOME", ".local/share") / "koplyx"
RUNTIME_DIR = xdg_path("XDG_RUNTIME_DIR", ".cache") / "koplyx"
CONTROL_SOCKET_PATH = RUNTIME_DIR / "control.sock"
ICON_NAME = "dev.limax.koplyx"


def now_ts() -> int:
    return int(time.time())


def human_time(ts: int) -> str:
    delta = max(0, now_ts() - ts)
    if delta < 60:
        return "maintenant"
    if delta < 3600:
        return f"{delta // 60} min"
    if delta < 86400:
        return f"{delta // 3600} h"
    return f"{delta // 86400} j"


def sha256(kind: str, data: bytes) -> str:
    return hashlib.sha256(kind.encode() + b":" + data).hexdigest()


def ensure_private_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def ensure_private_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    except OSError:
        pass


def send_control_command(command: str) -> bool:
    if command not in {"toggle", "show", "keep-alive"}:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.35)
            client.connect(str(CONTROL_SOCKET_PATH))
            client.sendall(command.encode("ascii"))
        return True
    except OSError:
        return False


class LocalControlServer:
    """Canal local pour contrôler une instance Snap sans dépendre de D-Bus."""

    def __init__(self, app: "KoplyxApplication") -> None:
        self.app = app
        self.socket: socket.socket | None = None
        self.source_id: int | None = None
        self.available = False

    def start(self) -> bool:
        ensure_private_dir(RUNTIME_DIR)
        if CONTROL_SOCKET_PATH.exists() or CONTROL_SOCKET_PATH.is_socket():
            if send_control_command("keep-alive"):
                return False
            try:
                if stat.S_ISSOCK(CONTROL_SOCKET_PATH.stat().st_mode):
                    CONTROL_SOCKET_PATH.unlink()
                else:
                    return False
            except OSError:
                return False
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.bind(str(CONTROL_SOCKET_PATH))
            CONTROL_SOCKET_PATH.chmod(0o600)
            self.socket.listen(4)
            self.socket.setblocking(False)
            self.source_id = GLib.io_add_watch(self.socket, GLib.PRIORITY_DEFAULT, GLib.IO_IN, self.on_ready)
            self.available = True
            return True
        except OSError:
            self.close()
            return False

    def on_ready(self, _source, _condition) -> bool:
        if not self.socket:
            return GLib.SOURCE_REMOVE
        try:
            client, _address = self.socket.accept()
            with client:
                command = client.recv(32).decode("ascii", errors="ignore")
        except OSError:
            return GLib.SOURCE_CONTINUE
        if command == "toggle":
            GLib.idle_add(self.app.toggle_window)
        elif command == "show":
            GLib.idle_add(self.app.show_from_tray)
        return GLib.SOURCE_CONTINUE

    def close(self) -> None:
        if self.source_id is not None:
            GLib.source_remove(self.source_id)
            self.source_id = None
        if self.socket:
            self.socket.close()
            self.socket = None
        try:
            if CONTROL_SOCKET_PATH.is_socket():
                CONTROL_SOCKET_PATH.unlink()
        except OSError:
            pass
        self.available = False


def harden_local_permissions() -> None:
    for directory in (CONFIG_DIR, DATA_DIR):
        ensure_private_dir(directory)
    for path in (
        CONFIG_DIR / "config.json",
        CONFIG_DIR / "key.bin",
        DATA_DIR / "history.db",
        DATA_DIR / "history.db-wal",
        DATA_DIR / "history.db-shm",
    ):
        if path.exists():
            ensure_private_file(path)


def private_preview(kind: str, mime: str, data: bytes, width: int | None = None, height: int | None = None) -> str:
    if kind == "text":
        try:
            count = len(data.decode("utf-8"))
        except UnicodeDecodeError:
            count = len(data)
        unit = "caractere" if count == 1 else "caracteres"
        return f"Texte, {count} {unit}"
    if kind == "image":
        size_kb = max(1, round(len(data) / 1024))
        if width is not None and height is not None:
            return f"Image PNG, {width} x {height}, {size_kb} KB"
        return f"Image PNG, {size_kb} KB"
    if kind in ("file", "files"):
        count = len(uri_list_from_bytes(data))
        if count == 1:
            return "Fichier, 1 element"
        return f"Fichiers, {count} elements"
    return f"{mime}, {len(data)} octets"


def text_excerpt(data: bytes, limit: int = 180) -> str:
    text = data.decode("utf-8", errors="replace").replace("\x00", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    excerpt = " / ".join(lines[:2]) if lines else text.strip()
    excerpt = " ".join(excerpt.split())
    if not excerpt:
        return "Texte vide"
    if len(excerpt) > limit:
        return excerpt[: limit - 1].rstrip() + "…"
    return excerpt


def text_content(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace").replace("\x00", "")
    return " ".join(text.split()) or "Texte vide"


def text_tooltip(data: bytes) -> str:
    content = text_content(data)
    if len(content) <= MAX_TOOLTIP_CHARS:
        return content
    return content[: MAX_TOOLTIP_CHARS - 1].rstrip() + "…"


def uri_list_from_bytes(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    uris = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            uris.append(line)
    return uris


def uri_display_name(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "file":
        path = urllib.parse.unquote(parsed.path)
        name = Path(path).name
        return name or path or uri
    path = urllib.parse.unquote(parsed.path)
    return Path(path).name or parsed.netloc or uri


def file_title_from_uris(uris: list[str]) -> str:
    if not uris:
        return "Fichier"
    if len(uris) == 1:
        return uri_display_name(uris[0])
    return f"{len(uris)} fichiers"


def format_uri_list(uris: list[str]) -> bytes:
    return ("\r\n".join(uris) + "\r\n").encode("utf-8")


def user_desktop_path() -> Path:
    return xdg_path("XDG_DATA_HOME", ".local/share") / "applications" / "dev.limax.koplyx.desktop"


def autostart_desktop_path() -> Path:
    return xdg_path("XDG_CONFIG_HOME", ".config") / "autostart" / "koplyx.desktop"


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def xwayland_active_window() -> str | None:
    """Retourne la fenêtre XWayland active lorsqu'elle est identifiable."""
    if os.environ.get("XDG_SESSION_TYPE", "").lower() != "wayland" or not command_exists("xdotool"):
        return None
    result = subprocess.run(["xdotool", "getactivewindow"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    window_id = result.stdout.strip()
    if not window_id:
        return None
    pid = x11_window_pid(window_id)
    if not pid or pid == os.getpid():
        return None
    return window_id


def ydotool_available() -> bool:
    """Vérifie que le daemon ydotool expose réellement son socket utilisateur."""
    if not command_exists("ydotool"):
        return False
    socket_path = os.environ.get("YDOTOOL_SOCKET")
    if not socket_path:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        socket_path = str(Path(runtime_dir) / ".ydotool_socket")
    return Path(socket_path).exists() and os.access(socket_path, os.W_OK)


def paste_tool_candidates(window_id: str | None = None, paste_backend: str | None = None) -> list[str]:
    """Retourne les outils directs dans l'ordre de repli souhaité."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    backend = paste_backend or "auto"
    if backend not in PASTE_BACKENDS:
        backend = "auto"
    candidates = []
    if backend in {"portal", "clipboard_only"}:
        return candidates
    if session == "wayland":
        if backend in {"auto", "wtype"} and command_exists("wtype"):
            candidates.append("wtype")
        # xdotool ne doit être proposé que si une vraie cible XWayland a été
        # mémorisée. Sinon son code retour peut être positif sans rien coller.
        if backend in {"auto", "xwayland"} and window_id and command_exists("xdotool"):
            candidates.append("xdotool")
        if backend in {"auto", "ydotool"} and ydotool_available():
            candidates.append("ydotool")
        return candidates
    if backend in {"auto", "xorg", "xwayland"} and command_exists("xdotool"):
        candidates.append("xdotool")
    if backend in {"auto", "ydotool"} and ydotool_available():
        candidates.append("ydotool")
    return candidates


def paste_tool_name(window_id: str | None = None, paste_backend: str | None = None) -> str | None:
    candidates = paste_tool_candidates(window_id, paste_backend)
    backend = paste_backend or "auto"
    if backend == "clipboard_only":
        return "presse-papiers uniquement"
    if backend == "portal":
        return "portail du bureau"
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        labels = list(candidates)
        if backend == "auto" and "xdotool" not in labels and command_exists("xdotool"):
            labels.append("xdotool (XWayland)")
        if backend == "auto" and "ydotool" not in labels and ydotool_available():
            labels.append("ydotool")
        if backend == "auto":
            labels.append("portail du bureau")
        return " → ".join(labels)
    if candidates:
        return " → ".join(candidates)
    return None


def x11_active_window() -> str | None:
    if os.environ.get("XDG_SESSION_TYPE", "").lower() != "x11" or not command_exists("xdotool"):
        return None
    result = subprocess.run(["xdotool", "getactivewindow"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    window_id = result.stdout.strip()
    return window_id or None


def x11_window_pid(window_id: str) -> int | None:
    result = subprocess.run(["xdotool", "getwindowpid", window_id], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def activate_x11_window(window_id: str | None) -> bool:
    if (
        os.environ.get("XDG_SESSION_TYPE", "").lower() != "x11"
        or not window_id
        or not command_exists("xdotool")
    ):
        return False
    return (
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", window_id],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def paste_clipboard_now(window_id: str | None = None, paste_backend: str | None = None) -> bool:
    for tool in paste_tool_candidates(window_id, paste_backend):
        if tool == "xdotool":
            command = ["xdotool", "key"]
            if window_id:
                command.extend(["--window", window_id])
            command.extend(["--clearmodifiers", "ctrl+v"])
        elif tool == "wtype":
            command = ["wtype", "-M", "ctrl", "v", "-m", "ctrl"]
        else:
            command = ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]
        try:
            if subprocess.run(command, check=False).returncode == 0:
                return True
        except OSError:
            continue
    return False


def accelerator_label(accelerator: str) -> str:
    if not accelerator:
        return "Aucune touche"
    success, keyval, modifiers = Gtk.accelerator_parse(accelerator)
    if success:
        return Gtk.accelerator_get_label(keyval, modifiers)
    return accelerator


def normalize_accelerator(keyval: int, state: Gdk.ModifierType) -> str:
    modifiers = state & (
        Gdk.ModifierType.SHIFT_MASK
        | Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.ALT_MASK
        | Gdk.ModifierType.SUPER_MASK
        | Gdk.ModifierType.META_MASK
        | Gdk.ModifierType.HYPER_MASK
    )
    return Gtk.accelerator_name(keyval, modifiers)


def accelerator_from_parts(keyval: int, modifiers: Gdk.ModifierType) -> str:
    if not keyval:
        return ""
    return Gtk.accelerator_name(keyval, Gdk.ModifierType(modifiers))


def parse_accelerator_parts(accelerator: str) -> tuple[int, Gdk.ModifierType]:
    success, keyval, modifiers = Gtk.accelerator_parse(accelerator)
    if success:
        return keyval, modifiers
    success, keyval, modifiers = Gtk.accelerator_parse(DEFAULT_CONFIG["shortcut"])
    return keyval, modifiers


def global_shortcut_valid(accelerator: str) -> bool:
    success, keyval, modifiers = Gtk.accelerator_parse(accelerator)
    if not success:
        return False
    required = (
        Gdk.ModifierType.CONTROL_MASK
        | Gdk.ModifierType.ALT_MASK
        | Gdk.ModifierType.SUPER_MASK
        | Gdk.ModifierType.META_MASK
        | Gdk.ModifierType.HYPER_MASK
    )
    return Gtk.accelerator_valid(keyval, modifiers) and bool(modifiers & required)


class Config:
    def __init__(self) -> None:
        ensure_private_dir(CONFIG_DIR)
        self.path = CONFIG_DIR / "config.json"
        existing_profile = self.path.exists()
        self.data = DEFAULT_CONFIG.copy()
        loaded = {}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
                else:
                    loaded = {}
            except (json.JSONDecodeError, OSError):
                loaded = {}
        for key, value in DEFAULT_CONFIG.items():
            self.data.setdefault(key, value)
        # La présence du fichier distingue un profil historique d'un profil
        # réellement neuf. Les profils existants restent utilisables sans
        # interrompre leur démarrage par l'assistant.
        if existing_profile and "onboarding_completed" not in loaded:
            self.data["onboarding_completed"] = True
        self.data.pop("auto_paste", None)
        self.data["start_hidden"] = True
        if self.data.get("pinned_history_position") not in PINNED_HISTORY_POSITIONS:
            self.data["pinned_history_position"] = DEFAULT_CONFIG["pinned_history_position"]
        if self.data.get("paste_backend") not in PASTE_BACKENDS:
            self.data["paste_backend"] = DEFAULT_CONFIG["paste_backend"]
        if not global_shortcut_valid(str(self.data.get("shortcut", ""))):
            self.data["shortcut"] = DEFAULT_CONFIG["shortcut"]
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        ensure_private_file(self.path)

    def get(self, key: str):
        return self.data.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()


class CryptoBox:
    def __init__(self) -> None:
        ensure_private_dir(CONFIG_DIR)
        key = self.load_secret_service_key()
        if key is None:
            key = self.load_file_key()
        self.fernet = Fernet(key)

    def load_file_key(self) -> bytes:
        key_path = CONFIG_DIR / "key.bin"
        if key_path.exists():
            return key_path.read_bytes()
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        ensure_private_file(key_path)
        return key

    def load_secret_service_key(self) -> bytes | None:
        try:
            import secretstorage

            connection = secretstorage.dbus_init()
            attributes = {"application": "koplyx", "purpose": "fernet-key"}
            for item in secretstorage.search_items(connection, attributes):
                item.ensure_not_locked()
                return bytes(item.get_secret())

            key_path = CONFIG_DIR / "key.bin"
            key = key_path.read_bytes() if key_path.exists() else Fernet.generate_key()
            collection = secretstorage.get_default_collection(connection)
            collection.ensure_not_locked()
            collection.create_item("Koplyx local encryption key", attributes, key, replace=True)
            ensure_private_file(key_path) if key_path.exists() else None
            return key
        except Exception:
            return None

    def encrypt(self, data: bytes) -> bytes:
        return self.fernet.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        return self.fernet.decrypt(data)


@dataclass
class HistoryItem:
    id: int
    kind: str
    mime: str
    preview: str
    created_at: int
    pinned: int


@dataclass
class DisplayItem:
    id: int
    kind: str
    mime: str
    stored_preview: str
    title: str
    detail: str
    search_text: str
    created_at: int
    pinned: int
    title_tooltip: str | None = None
    image_data: bytes | None = None


class HistoryStore:
    def __init__(self, crypto: CryptoBox, config: Config) -> None:
        ensure_private_dir(DATA_DIR)
        self.crypto = crypto
        self.config = config
        self.db_path = DATA_DIR / "history.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                mime TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE,
                encrypted_blob BLOB NOT NULL,
                preview TEXT NOT NULL,
                bytes_size INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()
        harden_local_permissions()

    def add(self, kind: str, mime: str, data: bytes, preview: str) -> bool:
        digest = sha256(kind, data)
        encrypted = self.crypto.encrypt(data)
        stored_preview = private_preview(kind, mime, data)
        if kind == "image" and preview.startswith("Image PNG,"):
            stored_preview = preview
        ts = now_ts()
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO items(kind, mime, hash, encrypted_blob, preview, bytes_size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (kind, mime, digest, encrypted, stored_preview[:500], len(data), ts),
            )
            inserted = True
        except sqlite3.IntegrityError:
            cur.execute("UPDATE items SET created_at = ? WHERE hash = ?", (ts, digest))
            inserted = False
        self.conn.commit()
        harden_local_permissions()
        self.prune()
        return inserted

    def list(
        self,
        query: str = "",
        pinned_only: bool = False,
        pinned_history_position: str | None = None,
    ) -> list[HistoryItem]:
        pinned_history_position = pinned_history_position or self.config.get("pinned_history_position")
        if pinned_history_position not in PINNED_HISTORY_POSITIONS:
            pinned_history_position = "top"
        conditions = []
        params = []
        if query.strip():
            conditions.append("preview LIKE ?")
            params.append(f"%{query.strip()}%")
        if pinned_only:
            conditions.append("pinned = 1")
            order_by = "created_at DESC"
        elif pinned_history_position == "pinned_only":
            conditions.append("pinned = 0")
            order_by = "created_at DESC"
        elif pinned_history_position == "bottom":
            order_by = "CASE WHEN pinned = 0 THEN 0 ELSE 1 END, created_at DESC"
        else:
            order_by = "CASE WHEN pinned = 1 THEN 0 ELSE 1 END, created_at DESC"
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            SELECT id, kind, mime, preview, created_at, pinned
            FROM items
            {where}
            ORDER BY {order_by}
            LIMIT 300
            """,
            params,
        ).fetchall()
        return [HistoryItem(*row) for row in rows]

    def recent(
        self,
        pinned_only: bool = False,
        pinned_history_position: str | None = None,
    ) -> list[HistoryItem]:
        return self.list("", pinned_only=pinned_only, pinned_history_position=pinned_history_position)

    def payload(self, item_id: int) -> tuple[str, str, bytes] | None:
        row = self.conn.execute(
            "SELECT kind, mime, encrypted_blob FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            return None
        kind, mime, encrypted = row
        try:
            return kind, mime, self.crypto.decrypt(encrypted)
        except InvalidToken:
            return None

    def delete(self, item_id: int) -> None:
        self.conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self.conn.commit()
        harden_local_permissions()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM items")
        self.conn.commit()
        harden_local_permissions()

    def toggle_pin(self, item_id: int) -> None:
        row = self.conn.execute("SELECT pinned FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return
        if row[0]:
            self.conn.execute("UPDATE items SET pinned = 0 WHERE id = ?", (item_id,))
        else:
            self.conn.execute("UPDATE items SET pinned = 1 WHERE id = ?", (item_id,))
        self.conn.commit()
        harden_local_permissions()

    def stats(self) -> tuple[int, int]:
        row = self.conn.execute("SELECT COUNT(*), COALESCE(SUM(bytes_size), 0) FROM items").fetchone()
        return int(row[0]), int(row[1])

    def prune(self) -> None:
        max_items = int(self.config.get("max_items"))
        max_age_days = int(self.config.get("max_age_days"))
        max_storage = int(self.config.get("max_storage_mb")) * 1024 * 1024
        if max_age_days > 0:
            cutoff = now_ts() - max_age_days * 86400
            self.conn.execute("DELETE FROM items WHERE pinned = 0 AND created_at < ?", (cutoff,))
        if max_items > 0:
            self.conn.execute(
                """
                DELETE FROM items
                WHERE id IN (
                    SELECT id FROM items
                    WHERE pinned = 0
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (max_items,),
            )
        while True:
            count, total = self.stats()
            if total <= max_storage or count <= 1:
                break
            self.conn.execute(
                """
                DELETE FROM items
                WHERE id = (
                    SELECT id FROM items WHERE pinned = 0 ORDER BY created_at ASC LIMIT 1
                )
                """
            )
        self.conn.commit()
        harden_local_permissions()


class ClipboardWatcher:
    def __init__(self, app: "KoplyxApplication") -> None:
        self.app = app
        display = Gdk.Display.get_default()
        self.clipboard = display.get_clipboard()
        self.last_text_hash = ""
        self.last_image_hash = ""
        self.last_file_hash = ""
        self.paused_until = 0.0

    def start(self) -> None:
        GLib.timeout_add(POLL_INTERVAL_MS, self.poll)

    def poll(self) -> bool:
        if time.time() < self.paused_until:
            return True
        if self.app.config.get("capture_text"):
            self.clipboard.read_text_async(None, self.on_text)
        if self.app.config.get("capture_images"):
            self.clipboard.read_texture_async(None, self.on_texture)
        self.clipboard.read_value_async(Gdk.FileList.__gtype__, GLib.PRIORITY_DEFAULT, None, self.on_files)
        return True

    def on_text(self, clipboard, result) -> None:
        try:
            text = clipboard.read_text_finish(result)
        except GLib.Error:
            return
        if not text or not text.strip():
            return
        if text.strip().startswith("file://"):
            return
        data = text.encode("utf-8")
        digest = sha256("text", data)
        if digest == getattr(self.app, "onboarding_test_digest", ""):
            self.last_text_hash = digest
            return
        if digest == self.last_text_hash:
            return
        self.last_text_hash = digest
        self.app.store.add("text", "text/plain;charset=utf-8", data, private_preview("text", "text/plain;charset=utf-8", data))
        self.app.refresh()

    def on_texture(self, clipboard, result) -> None:
        try:
            texture = clipboard.read_texture_finish(result)
        except GLib.Error:
            return
        if texture is None:
            return
        try:
            png_bytes = bytes(texture.save_to_png_bytes().get_data())
        except Exception:
            return
        digest = sha256("image", png_bytes)
        if digest == self.last_image_hash:
            return
        self.last_image_hash = digest
        w, h = texture.get_width(), texture.get_height()
        self.app.store.add("image", "image/png", png_bytes, private_preview("image", "image/png", png_bytes, w, h))
        self.app.refresh()

    def on_files(self, clipboard, result) -> None:
        try:
            file_list = clipboard.read_value_finish(result)
        except (GLib.Error, TypeError):
            return
        if not file_list:
            return
        try:
            files = list(file_list.get_files())
        except Exception:
            return
        uris = [file.get_uri() for file in files if file.get_uri()]
        if not uris:
            return
        data = format_uri_list(uris)
        digest = sha256("files", data)
        if digest == self.last_file_hash:
            return
        self.last_file_hash = digest
        kind = "file" if len(uris) == 1 else "files"
        self.app.store.add(kind, "text/uri-list", data, private_preview(kind, "text/uri-list", data))
        self.app.refresh()

    def set_text(self, text: str) -> None:
        self.paused_until = time.time() + 1.0
        self.last_text_hash = sha256("text", text.encode("utf-8"))
        self.clipboard.set(text)

    def set_image_png(self, data: bytes) -> None:
        self.paused_until = time.time() + 1.0
        self.last_image_hash = sha256("image", data)
        loader = GdkPixbuf.PixbufLoader.new_with_type("png")
        loader.write(data)
        loader.close()
        texture = Gdk.Texture.new_for_pixbuf(loader.get_pixbuf())
        provider = Gdk.ContentProvider.new_for_value(texture)
        self.clipboard.set_content(provider)

    def set_files(self, data: bytes) -> bool:
        uris = uri_list_from_bytes(data)
        files = [Gio.File.new_for_uri(uri) for uri in uris]
        if not files:
            return False
        self.paused_until = time.time() + 1.0
        self.last_file_hash = sha256("files", format_uri_list(uris))
        file_list = Gdk.FileList.new_from_list(files)
        provider = Gdk.ContentProvider.new_for_value(file_list)
        return self.clipboard.set_content(provider)


class HistoryRow(Gtk.ListBoxRow):
    def __init__(self, app: "KoplyxApplication", item: DisplayItem) -> None:
        super().__init__()
        self.app = app
        self.item = item
        self.set_activatable(True)
        self.add_css_class("history-row")

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.set_margin_top(10)
        root.set_margin_bottom(10)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.set_child(root)

        root.append(self.preview_widget(item))

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        title = Gtk.Label(label=item.title)
        title.set_xalign(0)
        title.set_hexpand(True)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_lines(1)
        title.set_tooltip_text(item.title_tooltip or item.title)
        title.add_css_class("history-title")
        meta = Gtk.Label(label=f"{item.detail} · {human_time(item.created_at)}" + (" · epingle" if item.pinned else ""))
        meta.set_xalign(0)
        meta.add_css_class("meta")
        text_box.append(title)
        text_box.append(meta)
        root.append(text_box)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        actions.add_css_class("row-actions")
        actions.set_valign(Gtk.Align.CENTER)
        pin = Gtk.Button(icon_name="view-pin-symbolic")
        pin.set_tooltip_text("Retirer des epingles" if item.pinned else "Epingler")
        pin.add_css_class("icon-button")
        if item.pinned:
            pin.add_css_class("is-pinned")
        pin.connect("clicked", self.on_pin)
        paste = Gtk.Button(icon_name="edit-paste-symbolic")
        paste.set_tooltip_text("Restaurer dans le presse-papiers")
        paste.add_css_class("restore-button")
        paste.connect("clicked", self.on_paste)
        delete = Gtk.Button(icon_name="user-trash-symbolic")
        delete.set_tooltip_text("Supprimer")
        delete.add_css_class("icon-button")
        delete.add_css_class("danger-button")
        delete.connect("clicked", self.on_delete)
        for button in (pin, paste, delete):
            button.set_halign(Gtk.Align.CENTER)
            button.set_valign(Gtk.Align.CENTER)
            actions.append(button)
        root.append(actions)

    def preview_widget(self, item: DisplayItem) -> Gtk.Widget:
        if item.kind == "image" and item.image_data:
            try:
                texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(item.image_data))
                picture = Gtk.Picture.new_for_paintable(texture)
                picture.set_size_request(48, 48)
                picture.set_halign(Gtk.Align.CENTER)
                picture.set_valign(Gtk.Align.CENTER)
                picture.add_css_class("thumb")
                return picture
            except Exception:
                pass

        type_box = Gtk.CenterBox()
        type_box.set_size_request(48, 48)
        type_box.set_hexpand(False)
        type_box.set_vexpand(False)
        type_box.set_halign(Gtk.Align.CENTER)
        type_box.set_valign(Gtk.Align.CENTER)
        type_box.add_css_class("type-box")
        icon_name = {
            "text": "text-x-generic-symbolic",
            "file": "text-x-generic-symbolic",
            "files": "folder-symbolic",
            "image": "image-x-generic-symbolic",
        }.get(item.kind, "edit-copy-symbolic")
        image = Gtk.Image.new_from_icon_name(icon_name)
        image.set_pixel_size(20)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        image.add_css_class("type-icon")
        type_box.set_center_widget(image)
        return type_box

    def on_paste(self, _button) -> None:
        self.app.restore_item(self.item.id)

    def on_pin(self, _button) -> None:
        self.app.store.toggle_pin(self.item.id)
        self.app.refresh()

    def on_delete(self, _button) -> None:
        self.app.store.delete(self.item.id)
        self.app.refresh()


class KoplyxWindow(Gtk.ApplicationWindow):
    def __init__(self, app: "KoplyxApplication") -> None:
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        self.set_default_size(640, 720)
        self.set_size_request(460, 480)
        self.add_css_class("koplyx-window")
        self.active_view = "history"
        self.connect("close-request", self.on_close_request)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("app-shell")
        self.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header.set_margin_top(22)
        header.set_margin_bottom(16)
        header.set_margin_start(22)
        header.set_margin_end(22)
        header.add_css_class("hero")
        root.append(header)

        brand_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        brand_box.set_hexpand(True)
        eyebrow = Gtk.Label(label="PRESSE-PAPIERS LOCAL")
        eyebrow.set_xalign(0)
        eyebrow.add_css_class("eyebrow")
        brand_box.append(eyebrow)
        brand = Gtk.Label(label="Koplyx")
        brand.set_xalign(0)
        brand.add_css_class("brand")
        brand_box.append(brand)
        subtitle = Gtk.Label(label="Vos copies restent sur votre machine.")
        subtitle.set_xalign(0)
        subtitle.add_css_class("subtitle")
        brand_box.append(subtitle)
        header.append(brand_box)

        header_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_actions.add_css_class("header-actions")

        settings = Gtk.Button(icon_name="emblem-system-symbolic")
        settings.set_tooltip_text("Parametres")
        settings.add_css_class("icon-button")
        settings.connect("clicked", lambda _b: self.open_settings())
        header_actions.append(settings)

        clear = Gtk.Button(icon_name="edit-clear-all-symbolic")
        clear.set_tooltip_text("Effacer l'historique")
        clear.add_css_class("icon-button")
        clear.add_css_class("danger-button")
        clear.connect("clicked", lambda _b: self.confirm_clear())
        header_actions.append(clear)
        header.append(header_actions)

        search_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        search_panel.set_margin_start(22)
        search_panel.set_margin_end(22)
        search_panel.set_margin_bottom(14)
        search_panel.add_css_class("search-panel")
        search_label = Gtk.Label(label="RETROUVER UNE COPIE")
        search_label.set_xalign(0)
        search_label.add_css_class("search-label")
        search_panel.append(search_label)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Rechercher dans l'historique")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda _w: app.refresh())
        search_panel.append(self.search)
        root.append(search_panel)

        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tabs.set_margin_start(22)
        tabs.set_margin_end(22)
        tabs.set_margin_bottom(14)
        tabs.add_css_class("tabs")
        root.append(tabs)

        self.history_tab = Gtk.Button(label="Historique")
        self.history_tab.connect("clicked", lambda _b: self.set_active_view("history"))
        tabs.append(self.history_tab)

        self.pinned_tab = Gtk.Button(label="Épinglés")
        self.pinned_tab.connect("clicked", lambda _b: self.set_active_view("pinned"))
        tabs.append(self.pinned_tab)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        tabs.append(spacer)

        self.pinned_filter = Gtk.MenuButton()
        self.pinned_filter.add_css_class("filter-button")
        self.pinned_filter.set_tooltip_text("Filtre global des éléments épinglés")
        self.pinned_filter.set_popover(self.pinned_filter_popover())
        tabs.append(self.pinned_filter)
        self.update_pinned_filter()
        self.update_tabs()

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_margin_start(14)
        scroller.set_margin_end(14)
        scroller.set_margin_bottom(10)
        scroller.add_css_class("history-scroller")
        root.append(scroller)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self.on_row_activated)
        self.listbox.add_css_class("history-list")
        scroller.set_child(self.listbox)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_margin_top(4)
        footer.set_margin_bottom(18)
        footer.set_margin_start(22)
        footer.set_margin_end(22)
        footer.add_css_class("status-panel")
        self.status_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        self.status_icon.set_pixel_size(16)
        self.status_icon.add_css_class("status-icon")
        footer.append(self.status_icon)
        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        self.status.set_wrap(True)
        self.status.add_css_class("status")
        footer.append(self.status)
        self.tray_badge = Gtk.Label()
        self.tray_badge.add_css_class("tray-badge")
        footer.append(self.tray_badge)
        root.append(footer)

    def present_focused(self) -> None:
        self.app.remember_active_window()
        self.present()
        self.search.grab_focus()

    def on_close_request(self, _window) -> bool:
        if self.app.background_access_available():
            self.app.sleep_to_tray()
            return True
        self.app.quit()
        return True

    def query(self) -> str:
        return self.search.get_text()

    def set_active_view(self, view: str) -> None:
        self.active_view = view
        if view == "pinned":
            self.search.set_placeholder_text("Rechercher dans les éléments épinglés")
        else:
            self.search.set_placeholder_text("Rechercher dans l'historique")
        self.update_tabs()
        self.app.refresh()

    def update_tabs(self) -> None:
        for button in (self.history_tab, self.pinned_tab):
            button.remove_css_class("tab-active")
        if self.active_view == "pinned":
            self.pinned_tab.add_css_class("tab-active")
        else:
            self.history_tab.add_css_class("tab-active")

    def update_pinned_filter(self) -> None:
        position = self.app.config.get("pinned_history_position")
        if position not in PINNED_HISTORY_POSITION_LABELS:
            position = "top"
        self.pinned_filter.set_label(PINNED_HISTORY_POSITION_LABELS[position])

    def pinned_filter_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("pinned-filter-popover")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_margin_start(8)
        content.set_margin_end(8)
        for position, label in PINNED_HISTORY_POSITION_LABELS.items():
            button = Gtk.Button(label=label)
            button.add_css_class("flat")
            button.set_halign(Gtk.Align.FILL)
            button.connect("clicked", self.on_pinned_filter, position, popover)
            content.append(button)
        popover.set_child(content)
        return popover

    def on_pinned_filter(self, _button, position: str, popover: Gtk.Popover) -> None:
        self.app.config.set("pinned_history_position", position)
        self.update_pinned_filter()
        popover.popdown()
        self.app.refresh()

    def on_row_activated(self, _box, row) -> None:
        item = getattr(row, "item", None)
        if item:
            self.app.restore_item(item.id)

    def set_items(self, items: list[DisplayItem]) -> None:
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
        if not items:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            empty.set_halign(Gtk.Align.CENTER)
            empty.set_valign(Gtk.Align.CENTER)
            empty.set_vexpand(True)
            empty.add_css_class("empty-state")
            icon = Gtk.Image.new_from_icon_name("view-pin-symbolic" if self.active_view == "pinned" else "edit-copy-symbolic")
            icon.set_pixel_size(34)
            icon.add_css_class("empty-icon")
            empty.append(icon)
            title = Gtk.Label(label="Aucun élément épinglé" if self.active_view == "pinned" else "Votre historique est prêt")
            title.add_css_class("empty-title")
            empty.append(title)
            detail = Gtk.Label(label="Épinglez les éléments importants pour les garder à portée de main." if self.active_view == "pinned" else "Copiez du texte, une image ou un fichier pour le retrouver ici.")
            detail.set_wrap(True)
            detail.set_justify(Gtk.Justification.CENTER)
            detail.set_max_width_chars(38)
            detail.add_css_class("empty-detail")
            empty.append(detail)
            self.listbox.append(empty)
        else:
            for item in items:
                self.listbox.append(HistoryRow(self.app, item))
        count, total = self.app.store.stats()
        mb = total / 1024 / 1024
        view_label = "éléments épinglés" if self.active_view == "pinned" else "historique"
        message = self.app.status_message
        if message:
            self.status.set_text(message)
        else:
            self.status.set_text(f"{view_label} · {count} elements · {mb:.1f} Mo · stockage local chiffre")
        self.tray_badge.set_text(self.app.tray_label())
        self.tray_badge.set_tooltip_text(self.app.tray_detail())
        if self.app.background_mode_active():
            self.tray_badge.remove_css_class("tray-warning")
            self.tray_badge.add_css_class("tray-active")
            self.status_icon.set_from_icon_name("emblem-ok-symbolic")
        else:
            self.tray_badge.remove_css_class("tray-active")
            self.tray_badge.add_css_class("tray-warning")
            self.status_icon.set_from_icon_name("dialog-warning-symbolic")

    def confirm_clear(self) -> None:
        dialog = Gtk.AlertDialog(message="Effacer tout l'historique Koplyx ?")
        dialog.set_detail("Les entrees chiffrees seront supprimees de la base locale.")
        dialog.set_buttons(["Annuler", "Effacer"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)
        dialog.choose(self, None, self.on_clear_response)

    def on_clear_response(self, dialog, result) -> None:
        try:
            if dialog.choose_finish(result) == 1:
                self.app.store.clear()
                self.app.refresh()
        except GLib.Error:
            pass

    def open_settings(self) -> None:
        SettingsWindow(self.app, self).present()


class SettingsWindow(Gtk.Window):
    def __init__(self, app: "KoplyxApplication", parent: Gtk.Window) -> None:
        super().__init__(title="Paramètres Koplyx", transient_for=parent, modal=True)
        self.app = app
        self.set_default_size(520, 660)
        self.set_size_request(420, 480)
        self.add_css_class("settings-window")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("settings-shell")
        self.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header.set_margin_top(22)
        header.set_margin_bottom(14)
        header.set_margin_start(22)
        header.set_margin_end(22)
        header.add_css_class("settings-hero")
        title = Gtk.Label(label="Paramètres")
        title.set_xalign(0)
        title.add_css_class("settings-title")
        header.append(title)
        subtitle = Gtk.Label(label="Personnalisez la capture, la confidentialité et l'accès rapide.")
        subtitle.set_xalign(0)
        subtitle.set_wrap(True)
        subtitle.add_css_class("subtitle")
        header.append(subtitle)
        self.tray_status = Gtk.Label(label=f"{app.tray_label()} · {app.tray_detail()}")
        self.tray_status.set_xalign(0)
        self.tray_status.set_wrap(True)
        self.tray_status.add_css_class("settings-note")
        header.append(self.tray_status)
        root.append(header)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        root.append(scroller)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(8)
        content.set_margin_bottom(22)
        content.set_margin_start(22)
        content.set_margin_end(22)
        scroller.set_child(content)

        self.section(content, "ACCÈS RAPIDE")
        shortcut_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        shortcut_card.add_css_class("settings-card")
        shortcut_card.set_margin_bottom(6)
        content.append(shortcut_card)
        self.shortcut = self.shortcut_row(shortcut_card, "Raccourci global", "shortcut")
        self.shortcut_state = Gtk.Label()
        self.shortcut_state.set_xalign(0)
        self.shortcut_state.set_wrap(True)
        self.shortcut_state.add_css_class("shortcut-state")
        shortcut_card.append(self.shortcut_state)
        self.update_shortcut_state(app.shortcut_sync_ok)
        onboarding_button = Gtk.Button(label="Relancer l'assistant de collage")
        onboarding_button.connect("clicked", lambda _b: app.open_onboarding(self))
        shortcut_card.append(onboarding_button)

        self.section(content, "HISTORIQUE")
        self.max_items = self.spin(content, "Nombre max d'entrées", "max_items", 10, 10000)
        self.max_age = self.spin(content, "Rétention en jours", "max_age_days", 1, 3650)
        self.max_storage = self.spin(content, "Stockage max (Mo)", "max_storage_mb", 16, 8192)
        self.capture_text = self.switch(content, "Capturer le texte", "capture_text")
        self.capture_images = self.switch(content, "Capturer les images", "capture_images")

        self.section(content, "COLLAGE DIRECT")
        backend_note = Gtk.Label(label=self.app.paste_backend_description())
        backend_note.set_xalign(0)
        backend_note.set_wrap(True)
        backend_note.add_css_class("settings-note")
        content.append(backend_note)
        assistant_note = Gtk.Label(
            label="Pour modifier cette configuration, relancez l'assistant. Koplyx essaiera les solutions une par une et ne mémorisera votre choix qu'après votre confirmation."
        )
        assistant_note.set_xalign(0)
        assistant_note.set_wrap(True)
        assistant_note.add_css_class("settings-note")
        content.append(assistant_note)

        self.section(content, "ARRIÈRE-PLAN")
        self.show_tray = self.switch(content, "Afficher dans la barre système", "show_tray", self.on_tray_changed)
        self.autostart = self.switch(content, "Lancer Koplyx au démarrage", "autostart_enabled", self.on_autostart_changed)

        self.feedback = Gtk.Label()
        self.feedback.set_wrap(True)
        self.feedback.set_xalign(0)
        self.feedback.add_css_class("settings-feedback")
        content.append(self.feedback)

        shortcut_warning = Gtk.Label(
            label="Le raccourci est appliqué automatiquement à GNOME. En cas de conflit, modifiez-le dans Paramètres > Clavier > Raccourcis clavier."
        )
        shortcut_warning.set_wrap(True)
        shortcut_warning.set_xalign(0)
        shortcut_warning.add_css_class("settings-warning")
        content.append(shortcut_warning)

        note = Gtk.Label(label="Le mode presse-papiers reste toujours disponible si votre bureau refuse le collage automatique.")
        note.set_wrap(True)
        note.set_xalign(0)
        note.add_css_class("settings-note")
        content.append(note)

    def section(self, root: Gtk.Box, label: str) -> None:
        title = Gtk.Label(label=label)
        title.set_xalign(0)
        title.set_margin_top(12)
        title.add_css_class("section-title")
        root.append(title)

    def entry(self, root, label: str, key: str) -> Gtk.Entry:
        row = self.row(root, label)
        widget = Gtk.Entry(text=str(self.app.config.get(key)))
        widget.connect("changed", lambda w: self.app.config.set(key, w.get_text()))
        row.append(widget)
        return widget

    def shortcut_row(self, root, label: str, key: str) -> Gtk.Box:
        row = self.row(root, label)
        value = Gtk.Label(label=accelerator_label(self.app.config.get(key)))
        value.add_css_class("shortcut-value")
        button = Gtk.Button(label="Modifier")
        button.connect("clicked", lambda _button: self.open_shortcut_dialog(key, value))
        row.append(value)
        row.append(button)
        return row

    def open_shortcut_dialog(self, key: str, value_label: Gtk.Label) -> None:
        dialog = ShortcutCaptureDialog(self, self.app.config.get(key))
        dialog.present()
        dialog.on_done = lambda shortcut: self.on_shortcut_dialog_done(key, value_label, shortcut)

    def on_shortcut_dialog_done(self, key: str, value_label: Gtk.Label, shortcut: str) -> None:
        self.app.config.set(key, shortcut)
        value_label.set_text(accelerator_label(shortcut))
        ok = self.app.sync_global_shortcut()
        self.update_shortcut_state(ok)
        if ok:
            self.feedback.set_text(f"Raccourci appliqué automatiquement : {accelerator_label(shortcut)}.")
            self.app.set_status("Raccourci global appliqué.")
        else:
            self.feedback.set_text("Raccourci enregistré, mais GNOME n'a pas pu l'appliquer.")
            self.app.set_status("Erreur de configuration du raccourci GNOME.")

    def update_shortcut_state(self, synced: bool) -> None:
        shortcut = accelerator_label(self.app.config.get("shortcut"))
        if synced:
            self.shortcut_state.set_text(f"Actif dans GNOME : {shortcut}")
            self.shortcut_state.remove_css_class("shortcut-state-error")
            self.shortcut_state.add_css_class("shortcut-state-ok")
        else:
            self.shortcut_state.set_text("À configurer dans les réglages clavier de GNOME.")
            self.shortcut_state.remove_css_class("shortcut-state-ok")
            self.shortcut_state.add_css_class("shortcut-state-error")

    def spin(self, root, label: str, key: str, minimum: int, maximum: int) -> Gtk.SpinButton:
        row = self.row(root, label)
        widget = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        widget.set_value(float(self.app.config.get(key)))
        widget.connect("value-changed", lambda w: self.app.config.set(key, int(w.get_value())))
        row.append(widget)
        return widget

    def switch(self, root, label: str, key: str, callback=None) -> Gtk.Switch:
        row = self.row(root, label)
        widget = Gtk.Switch(active=bool(self.app.config.get(key)))
        if callback is None:
            widget.connect("notify::active", lambda w, _p: self.app.config.set(key, w.get_active()))
        else:
            widget.connect("notify::active", callback)
        row.append(widget)
        return widget

    def row(self, root, label: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("settings-row")
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        text.set_wrap(True)
        text.set_hexpand(True)
        row.append(text)
        root.append(row)
        return row

    def on_autostart_changed(self, widget: Gtk.Switch, _param) -> None:
        active = widget.get_active()
        ok = self.app.set_autostart_enabled(active)
        if ok:
            self.feedback.set_text("Autostart active." if active else "Autostart desactive.")
            self.app.set_status("Autostart active." if active else "Autostart desactive.")
        else:
            self.feedback.set_text("Impossible de modifier l'autostart.")
            self.app.set_status("Erreur autostart.")

    def on_tray_changed(self, widget: Gtk.Switch, _param) -> None:
        enabled = widget.get_active()
        available = self.app.set_tray_enabled(enabled)
        self.tray_status.set_text(f"{self.app.tray_label()} · {self.app.tray_detail()}")
        if enabled and not available:
            self.feedback.set_text("Indicateur système non disponible. Koplyx restera visible pour rester accessible.")
        elif enabled:
            self.feedback.set_text("Indicateur système actif. Koplyx peut rester en arrière-plan.")
        else:
            self.feedback.set_text("Indicateur système désactivé. La fenêtre restera accessible.")


class ShortcutCaptureDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window, current_shortcut: str) -> None:
        super().__init__(title="Modifier le raccourci", transient_for=parent, modal=True)
        self.set_default_size(460, 330)
        self.add_css_class("settings-window")
        self.capturing = False
        self.keyval, self.modifiers = parse_accelerator_parts(current_shortcut)
        self.pending_shortcut = accelerator_from_parts(self.keyval, self.modifiers)
        self.on_done = None

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.add_css_class("shortcut-shell")
        root.set_margin_top(20)
        root.set_margin_bottom(18)
        root.set_margin_start(20)
        root.set_margin_end(20)
        self.set_child(root)

        title = Gtk.Label(label="Modifier le raccourci global")
        title.set_xalign(0)
        title.add_css_class("settings-title")
        root.append(title)

        self.instructions = Gtk.Label()
        self.instructions.set_xalign(0)
        self.instructions.set_wrap(True)
        self.instructions.add_css_class("settings-note")
        root.append(self.instructions)

        self.value = Gtk.Label()
        self.value.add_css_class("shortcut-dialog-value")
        self.value.set_hexpand(True)
        root.append(self.value)

        modifiers = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        modifiers.set_halign(Gtk.Align.CENTER)
        root.append(modifiers)

        self.ctrl_button = self.modifier_button("Ctrl", Gdk.ModifierType.CONTROL_MASK)
        self.alt_button = self.modifier_button("Alt", Gdk.ModifierType.ALT_MASK)
        self.super_button = self.modifier_button("Super", Gdk.ModifierType.SUPER_MASK)
        self.fn_button = Gtk.ToggleButton(label="Fn")
        self.fn_button.set_tooltip_text("Fn est materiel sur la plupart des claviers et ne peut pas etre enregistre par GNOME.")
        self.fn_button.connect("toggled", self.on_fn_toggled)
        for button in (self.ctrl_button, self.alt_button, self.super_button, self.fn_button):
            modifiers.append(button)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        actions.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Annuler")
        cancel.connect("clicked", lambda _button: self.close())
        actions.append(cancel)
        self.primary = Gtk.Button(label="Demarrer")
        self.primary.add_css_class("primary")
        self.primary.connect("clicked", lambda _button: self.toggle_capture())
        actions.append(self.primary)
        root.append(actions)

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(controller)
        self.update_view()

    def modifier_button(self, label: str, mask: Gdk.ModifierType) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton(label=label)
        button.modifier_mask = mask
        button.connect("toggled", self.on_modifier_toggled)
        return button

    def on_modifier_toggled(self, button: Gtk.ToggleButton) -> None:
        if button.get_active():
            self.modifiers = Gdk.ModifierType(self.modifiers | button.modifier_mask)
        else:
            self.modifiers = Gdk.ModifierType(self.modifiers & ~button.modifier_mask)
        self.sync_pending_shortcut()
        self.update_view()

    def on_fn_toggled(self, _button: Gtk.ToggleButton) -> None:
        self.instructions.set_text("Fn ne peut pas etre enregistre par GNOME. Utilisez Ctrl, Alt ou Super.")

    def sync_modifier_buttons(self) -> None:
        for button in (self.ctrl_button, self.alt_button, self.super_button):
            button.handler_block_by_func(self.on_modifier_toggled)
            button.set_active(bool(self.modifiers & button.modifier_mask))
            button.handler_unblock_by_func(self.on_modifier_toggled)

    def sync_pending_shortcut(self) -> None:
        self.pending_shortcut = accelerator_from_parts(self.keyval, self.modifiers)

    def update_view(self) -> None:
        self.sync_modifier_buttons()
        self.value.set_text(accelerator_label(self.pending_shortcut))
        if self.capturing:
            self.instructions.set_text(
                "Capture active. Appuyez sur la touche principale, ou cliquez Ctrl/Alt/Super, puis Valider."
            )
        else:
            self.instructions.set_text(
                "Cliquez Demarrer, appuyez sur la touche principale, ajustez Ctrl/Alt/Super, puis Valider."
            )
        self.primary.set_label("Valider" if self.capturing else "Demarrer")

    def toggle_capture(self) -> None:
        if self.capturing:
            self.finish()
        else:
            self.capturing = True
            self.keyval = 0
            self.modifiers = Gdk.ModifierType(0)
            self.pending_shortcut = ""
            self.fn_button.set_active(False)
            self.update_view()
            self.grab_focus()

    def finish(self) -> None:
        if not global_shortcut_valid(self.pending_shortcut):
            self.instructions.set_text("Combinaison invalide. Ajoutez Ctrl, Alt ou Super, puis Valider.")
            return
        if callable(self.on_done):
            self.on_done(self.pending_shortcut)
        self.close()

    def on_key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        if keyval in (Gdk.KEY_Escape,):
            self.close()
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return True

        if not self.capturing:
            return True

        if keyval in MODIFIER_KEYS:
            return True

        state_modifiers = state & (
            Gdk.ModifierType.SHIFT_MASK
            | Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.ALT_MASK
            | Gdk.ModifierType.SUPER_MASK
            | Gdk.ModifierType.META_MASK
            | Gdk.ModifierType.HYPER_MASK
        )
        self.keyval = keyval
        self.modifiers = Gdk.ModifierType(self.modifiers | state_modifiers)
        self.sync_pending_shortcut()
        if not global_shortcut_valid(self.pending_shortcut):
            self.instructions.set_text("Combinaison invalide. Ajoutez Ctrl, Alt ou Super, puis Valider.")
        else:
            self.instructions.set_text(f"Touche capturee: {accelerator_label(self.pending_shortcut)}. Cliquez Valider.")
        self.value.set_text(accelerator_label(self.pending_shortcut))
        self.primary.set_label("Valider")
        self.sync_modifier_buttons()
        return True


class OnboardingWindow(Gtk.Window):
    """Assistant guidé qui essaie les solutions dans un ordre compréhensible."""

    def __init__(self, app: "KoplyxApplication", parent: Gtk.Window | None = None) -> None:
        super().__init__(title="Configurer le collage direct - Koplyx", transient_for=parent or app.window, modal=True)
        self.app = app
        self.page = 0
        self.action_mode = "page"
        self.test_plan: list[str] = []
        self.test_index = -1
        self.test_backend = ""
        self.set_default_size(560, 500)
        self.set_size_request(460, 420)
        self.add_css_class("settings-window")
        self.connect("close-request", self.on_close_request)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(26)
        root.set_margin_bottom(24)
        root.set_margin_start(26)
        root.set_margin_end(26)
        root.add_css_class("settings-shell")
        self.set_child(root)

        self.title_label = Gtk.Label()
        self.title_label.set_xalign(0)
        self.title_label.add_css_class("settings-title")
        root.append(self.title_label)
        self.body = Gtk.Label()
        self.body.set_xalign(0)
        self.body.set_wrap(True)
        self.body.set_selectable(False)
        self.body.add_css_class("settings-note")
        root.append(self.body)
        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.set_wrap(True)
        self.status.add_css_class("settings-feedback")
        root.append(self.status)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content.set_vexpand(True)
        root.append(self.content)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        root.append(actions)
        self.secondary = Gtk.Button(label="Quitter")
        self.secondary.connect("clicked", self.on_secondary)
        actions.append(self.secondary)
        self.primary = Gtk.Button(label="Continuer")
        self.primary.add_css_class("primary")
        self.primary.connect("clicked", self.on_primary)
        actions.append(self.primary)
        self.show_page(0)
        GLib.idle_add(self.focus_primary_once)

    def on_close_request(self, _window) -> bool:
        self.app.onboarding = None
        return False

    def focus_primary_once(self) -> bool:
        self.primary.grab_focus()
        return GLib.SOURCE_REMOVE

    def clear_content(self) -> None:
        while child := self.content.get_first_child():
            self.content.remove(child)

    def show_page(self, page: int) -> None:
        self.page = page
        self.action_mode = "page"
        self.clear_content()
        self.status.set_text("")
        if page == 0:
            self.title_label.set_text("Bienvenue dans Koplyx")
            self.body.set_text(
                "Koplyx va essayer automatiquement plusieurs façons de coller dans la fenêtre précédente. "
                "Vous confirmerez simplement si le texte apparaît au bon endroit."
            )
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("settings-row")
            value = Gtk.Label(label=accelerator_label(self.app.config.get("shortcut")))
            value.set_hexpand(True)
            value.set_xalign(0)
            row.append(value)
            button = Gtk.Button(label="Modifier le raccourci")
            button.connect("clicked", lambda _b: self.open_shortcut(value))
            row.append(button)
            self.content.append(row)
            state = "Raccourci prêt." if self.app.shortcut_sync_ok else "Raccourci enregistré, synchronisation à vérifier dans GNOME."
            self.status.set_text(state)
            self.secondary.set_label("Quitter")
            self.primary.set_label("Commencer les tests")
        elif page == 1:
            self.title_label.set_text("Préparons le test")
            self.body.set_text(
                "Ouvrez un champ texte dans une autre application. Ensuite, revenez ici et cliquez sur « Tester ». "
                "Koplyx masquera sa fenêtre, collera un texte de test puis reviendra automatiquement."
            )
            self.test_plan = self.app.onboarding_test_plan()
            self.test_index = -1
            self.status.set_text(f"Koplyx va essayer jusqu'à {len(self.test_plan)} solutions, de la plus discrète à la plus assistée.")
            self.secondary.set_label("Retour")
            self.primary.set_label("Tester")
        elif page == 2:
            self.show_test_step()

    def show_test_step(self, message: str = "") -> None:
        self.page = 2
        self.action_mode = "page"
        self.clear_content()
        if self.test_index < 0:
            self.test_index = 0
        if self.test_index >= len(self.test_plan):
            self.test_backend = "clipboard_only"
            self.title_label.set_text("Dernière solution")
            self.body.set_text("Aucun collage automatique n'est disponible dans cette session. Koplyx peut tout de même restaurer chaque élément dans le presse-papiers pour que vous utilisiez Ctrl+V.")
            self.status.set_text("Ce choix n'active aucun accès système.")
            self.primary.set_label("Utiliser le presse-papiers")
            self.secondary.set_label("Retour")
            return
        self.test_backend = self.test_plan[self.test_index]
        self.title_label.set_text(f"Essai {self.test_index + 1} sur {len(self.test_plan)}")
        descriptions = {
            "wtype": "une méthode silencieuse adaptée à votre bureau",
            "xwayland": "la compatibilité avec les applications X",
            "xorg": "une session graphique classique au prochain redémarrage",
            "ydotool": "une méthode système dédiée au collage",
            "portal": "l'autorisation clavier d'Ubuntu",
        }
        description = descriptions.get(self.test_backend, "une autre méthode de collage")
        self.body.set_text(
            f"Nous allons essayer {description}. Placez le curseur dans votre champ texte, puis cliquez sur « Tester cette solution ». "
            "Si le texte n'apparaît pas, Koplyx passera à la suivante."
        )
        if message:
            self.status.set_text(message)
        elif self.test_backend == "ydotool":
            self.status.set_text("Ubuntu peut demander votre mot de passe. Koplyx envoie uniquement Ctrl+V et ne lit pas le clavier.")
        elif self.test_backend == "portal":
            self.status.set_text("Ubuntu affichera une autorisation « Bureau à distance ». Aucun écran ne sera partagé.")
        else:
            self.status.set_text("Aucun accès supplémentaire n'est demandé pour cet essai.")
        self.primary.set_label("Tester cette solution")
        self.secondary.set_label("Passer à la suivante")

    def open_shortcut(self, value: Gtk.Label) -> None:
        dialog = ShortcutCaptureDialog(self, self.app.config.get("shortcut"))
        dialog.on_done = lambda shortcut: self.on_shortcut_done(value, shortcut)
        dialog.present()

    def on_shortcut_done(self, value: Gtk.Label, shortcut: str) -> None:
        self.app.config.set("shortcut", shortcut)
        value.set_text(accelerator_label(shortcut))
        self.app.sync_global_shortcut()
        self.status.set_text("Raccourci synchronisé." if self.app.shortcut_sync_ok else "Raccourci enregistré, synchronisation à vérifier.")

    def on_primary(self, _button) -> None:
        if self.action_mode == "success":
            self.finish_success(self.test_backend)
            return
        if self.action_mode == "failure":
            self.next_test()
            return
        if self.page == 0:
            self.show_page(1)
        elif self.page == 1:
            self.test_index = 0
            self.show_test_step()
        elif self.page == 2:
            if self.test_backend == "clipboard_only":
                self.finish_success("clipboard_only")
            else:
                self.app.begin_onboarding_test(self, self.test_backend)

    def on_secondary(self, _button) -> None:
        if self.action_mode == "success":
            self.next_test()
            return
        if self.action_mode == "failure":
            self.next_test()
            return
        if self.page == 0:
            self.close()
        elif self.page == 1:
            self.show_page(0)
        elif self.page == 2:
            self.next_test()

    def next_test(self) -> None:
        self.test_index += 1
        self.show_test_step("Cette solution n'a pas été confirmée. Essayons la suivante.")

    def test_result(self, success: bool, backend: str) -> None:
        self.present()
        if success:
            self.test_backend = backend
            self.status.set_text("Le collage a été envoyé. Est-ce que le texte est apparu dans le champ cible ?")
            self.body.set_text("Répondez simplement oui ou non. La méthode ne sera mémorisée qu'après votre confirmation.")
            self.primary.set_label("Oui, ça fonctionne")
            self.secondary.set_label("Non, essayer la suivante")
            self.action_mode = "success"
        else:
            self.status.set_text("Cette solution n'a pas fonctionné dans votre session.")
            self.primary.set_label("Essayer la suivante")
            self.secondary.set_label("Essayer la suivante")
            self.action_mode = "failure"

    def finish_success(self, backend: str) -> None:
        self.app.config.set("paste_backend", backend)
        self.app.config.set("onboarding_completed", True)
        self.app.onboarding = None
        self.close()
        self.app.set_status("Collage direct configuré.")


class TrayIndicator:
    MENU_PATH = "/StatusNotifierItem/menu"
    MENU_SHOW_ID = 1
    MENU_SETTINGS_ID = 2
    MENU_QUIT_ID = 3

    def __init__(self, app: "KoplyxApplication") -> None:
        self.app = app
        self.available = False
        self.error = ""
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
        except Exception:
            self.dbus = None
            self.error = "La bibliothèque D-Bus n'est pas disponible."
            return

        self.dbus = dbus
        DBusGMainLoop(set_as_default=True)
        try:
            self.bus = dbus.SessionBus()
            if not self.bus.name_has_owner("org.kde.StatusNotifierWatcher"):
                self.error = "Aucun hôte d'indicateurs système n'est détecté."
                return
        except Exception:
            self.error = "La session D-Bus est indisponible."
            return

        class DBusMenu(dbus.service.Object):
            def __init__(self, owner: "TrayIndicator") -> None:
                self.owner = owner
                super().__init__(owner.bus_name, TrayIndicator.MENU_PATH)

            def menu_item(self, item_id: int, label: str) -> "dbus.Struct":
                props = dbus.Dictionary(
                    {
                        "type": dbus.String("standard"),
                        "label": dbus.String(label),
                        "enabled": dbus.Boolean(True),
                        "visible": dbus.Boolean(True),
                    },
                    signature="sv",
                )
                return dbus.Struct((dbus.Int32(item_id), props, dbus.Array([], signature="v")), signature="ia{sv}av")

            def root_layout(self) -> "dbus.Struct":
                props = dbus.Dictionary(
                    {
                        "children-display": dbus.String("submenu"),
                        "visible": dbus.Boolean(True),
                    },
                    signature="sv",
                )
                children = dbus.Array(
                    [
                        self.menu_item(TrayIndicator.MENU_SHOW_ID, "Afficher Koplyx"),
                        self.menu_item(TrayIndicator.MENU_SETTINGS_ID, "Paramètres"),
                        self.menu_item(TrayIndicator.MENU_QUIT_ID, "Quitter Koplyx"),
                    ],
                    signature="v",
                )
                return dbus.Struct((dbus.Int32(0), props, children), signature="ia{sv}av")

            @dbus.service.method("com.canonical.dbusmenu", in_signature="iias", out_signature="u(ia{sv}av)")
            def GetLayout(self, _parent_id, _recursion_depth, _property_names):
                return dbus.UInt32(1), self.root_layout()

            @dbus.service.method("com.canonical.dbusmenu", in_signature="aias", out_signature="a(ia{sv})")
            def GetGroupProperties(self, ids, _property_names):
                rows = []
                labels = {
                    TrayIndicator.MENU_SHOW_ID: "Afficher Koplyx",
                    TrayIndicator.MENU_SETTINGS_ID: "Paramètres",
                    TrayIndicator.MENU_QUIT_ID: "Quitter Koplyx",
                }
                for item_id in ids:
                    label = labels.get(int(item_id))
                    if label:
                        rows.append(
                            dbus.Struct(
                                (
                                    dbus.Int32(item_id),
                                    dbus.Dictionary(
                                        {
                                            "type": dbus.String("standard"),
                                            "label": dbus.String(label),
                                            "enabled": dbus.Boolean(True),
                                            "visible": dbus.Boolean(True),
                                        },
                                        signature="sv",
                                    ),
                                ),
                                signature="ia{sv}",
                            )
                        )
                return dbus.Array(rows, signature="(ia{sv})")

            @dbus.service.method("com.canonical.dbusmenu", in_signature="is", out_signature="v")
            def GetProperty(self, item_id, prop):
                if prop == "label":
                    if int(item_id) == TrayIndicator.MENU_SHOW_ID:
                        return dbus.String("Afficher Koplyx")
                    if int(item_id) == TrayIndicator.MENU_SETTINGS_ID:
                        return dbus.String("Paramètres")
                    if int(item_id) == TrayIndicator.MENU_QUIT_ID:
                        return dbus.String("Quitter Koplyx")
                if prop in ("enabled", "visible"):
                    return dbus.Boolean(True)
                return dbus.String("")

            @dbus.service.method("com.canonical.dbusmenu", in_signature="isvu", out_signature="")
            def Event(self, item_id, event_id, _data, _timestamp):
                if event_id != "clicked":
                    return
                if int(item_id) == TrayIndicator.MENU_SHOW_ID:
                    GLib.idle_add(self.owner.app.show_from_tray)
                elif int(item_id) == TrayIndicator.MENU_SETTINGS_ID:
                    GLib.idle_add(self.owner.app.open_settings_from_tray)
                elif int(item_id) == TrayIndicator.MENU_QUIT_ID:
                    GLib.idle_add(self.owner.app.quit_from_tray)

            @dbus.service.method("com.canonical.dbusmenu", in_signature="i", out_signature="b")
            def AboutToShow(self, _item_id):
                return False

            @dbus.service.method("com.canonical.dbusmenu", in_signature="ai", out_signature="aiai")
            def AboutToShowGroup(self, ids):
                return dbus.Array([], signature="i"), dbus.Array(ids, signature="i")

            @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
            def Get(self, interface, prop):
                values = self.GetAll(interface)
                if prop in values:
                    return values[prop]
                raise dbus.exceptions.DBusException(
                    f"Unknown property {prop}",
                    name="org.freedesktop.DBus.Error.InvalidArgs",
                )

            @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
            def GetAll(self, interface):
                if interface != "com.canonical.dbusmenu":
                    return dbus.Dictionary({}, signature="sv")
                return dbus.Dictionary(
                    {
                        "Version": dbus.UInt32(3),
                        "TextDirection": dbus.String("ltr"),
                        "Status": dbus.String("normal"),
                        "IconThemePath": dbus.String(str(PROJECT_ROOT / "assets/icons")),
                    },
                    signature="sv",
                )

            @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv", out_signature="")
            def Set(self, _interface, _prop, _value):
                return

            @dbus.service.signal("com.canonical.dbusmenu", signature="ui")
            def LayoutUpdated(self, revision, parent):
                return

        class StatusNotifierItem(dbus.service.Object):
            def __init__(self, owner: "TrayIndicator") -> None:
                self.owner = owner
                super().__init__(owner.bus_name, "/StatusNotifierItem")

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
            def Activate(self, _x, _y):
                GLib.idle_add(self.owner.app.toggle_window)

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
            def SecondaryActivate(self, _x, _y):
                GLib.idle_add(self.owner.app.toggle_window)

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
            def ContextMenu(self, _x, _y):
                return

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="is", out_signature="")
            def Scroll(self, _delta, _orientation):
                return

            @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
            def Get(self, interface, prop):
                values = self.GetAll(interface)
                if prop in values:
                    return values[prop]
                raise dbus.exceptions.DBusException(
                    f"Unknown property {prop}",
                    name="org.freedesktop.DBus.Error.InvalidArgs",
                )

            @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
            def GetAll(self, interface):
                if interface != "org.kde.StatusNotifierItem":
                    return {}
                icon_path = str(PROJECT_ROOT / "assets/icons")
                tooltip = dbus.Struct(
                    (
                        dbus.String(ICON_NAME),
                        dbus.Array([], signature="(iiay)"),
                        dbus.String("Koplyx"),
                        dbus.String("Historique presse-papiers"),
                    ),
                    signature="sa(iiay)ss",
                )
                menu_path = dbus.ObjectPath(TrayIndicator.MENU_PATH)
                return dbus.Dictionary(
                    {
                        "Category": dbus.String("ApplicationStatus"),
                        "Id": dbus.String("koplyx"),
                        "Title": dbus.String("Koplyx"),
                        "Status": dbus.String("Active"),
                        "WindowId": dbus.UInt32(0),
                        "IconName": dbus.String(ICON_NAME),
                        "IconThemePath": dbus.String(icon_path),
                        "AttentionIconName": dbus.String(""),
                        "ToolTip": tooltip,
                        "Menu": menu_path,
                        "ItemIsMenu": dbus.Boolean(False),
                    },
                    signature="sv",
                )

            @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv", out_signature="")
            def Set(self, _interface, _prop, _value):
                return

        try:
            self.service_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
            self.bus_name = dbus.service.BusName(self.service_name, self.bus)
            self.menu = DBusMenu(self)
            self.item = StatusNotifierItem(self)
            watcher = self.bus.get_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
            watcher.RegisterStatusNotifierItem(
                self.service_name,
                dbus_interface="org.kde.StatusNotifierWatcher",
            )
            self.available = True
        except Exception:
            self.error = "L'enregistrement de l'indicateur système a échoué."


class KoplyxApplication(Gtk.Application):
    def __init__(self) -> None:
        # Sous Snap strict, l'autorisation du nom D-Bus est fournie par le
        # Store après revue. L'absence temporaire de cette autorisation ne
        # doit jamais empêcher l'ouverture de la fenêtre principale.
        application_id = None if os.environ.get("SNAP") else APP_ID
        super().__init__(application_id=application_id, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.control_server = LocalControlServer(self)
        self.control_server.start()
        self.config = Config()
        self.crypto = CryptoBox()
        self.store = HistoryStore(self.crypto, self.config)
        self.window: KoplyxWindow | None = None
        self.watcher: ClipboardWatcher | None = None
        self.tray: TrayIndicator | None = None
        self.previous_window_id: str | None = None
        self.portal_keyboard = PortalKeyboard(
            get_restore_token=lambda: self.config.get("wayland_restore_token"),
            save_restore_token=lambda token: self.config.set("wayland_restore_token", token),
        )
        self.status_message = ""
        self.shortcut_sync_ok = False
        self.onboarding: OnboardingWindow | None = None
        self.onboarding_test_marker = ""
        self.onboarding_test_digest = ""
        self.onboarding_previous_text: str | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(ICON_NAME)
        repair_user_desktop_files()
        self.sync_autostart()
        self.shortcut_sync_ok = self.sync_global_shortcut()
        apply_css()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_shutdown_signal)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_shutdown_signal)
        self.sync_tray()

    def on_shutdown_signal(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_shutdown(self) -> None:
        self.portal_keyboard.close()
        Gtk.Application.do_shutdown(self)

    def do_activate(self) -> None:
        self.ensure_window()
        if not self.config.get("onboarding_completed"):
            self.open_onboarding()
            return
        if not self.config.get("start_hidden"):
            self.window.present_focused()
        elif self.background_access_available():
            self.set_status(self.background_status_message())
        else:
            self.set_status("Indicateur système indisponible : Koplyx reste visible pour rester accessible.")
            self.window.present_focused()

    def do_command_line(self, command_line) -> int:
        args = command_line.get_arguments()[1:]
        if "--restore-display-session" in args:
            ok, message = run_privileged("gdm-restore")
            print(message)
            return 0 if ok else 1
        self.ensure_window()
        if not self.config.get("onboarding_completed"):
            self.open_onboarding()
            return 0
        if "--hidden" in args:
            if self.background_access_available():
                self.set_status(self.background_status_message())
            else:
                self.set_status("Indicateur système indisponible : Koplyx reste visible pour rester accessible.")
                self.window.present_focused()
            return 0
        if "--toggle" in args:
            self.toggle_window()
        else:
            self.window.present_focused()
        return 0

    def ensure_window(self) -> None:
        if self.window is None:
            self.window = KoplyxWindow(self)
            self.watcher = ClipboardWatcher(self)
            self.watcher.start()
            self.refresh()

    def toggle_window(self) -> None:
        self.ensure_window()
        if self.window.is_visible():
            self.sleep_to_tray()
        else:
            self.window.present_focused()

    def show_from_tray(self) -> bool:
        self.ensure_window()
        self.window.present_focused()
        self.set_status("Koplyx est ouvert.")
        return GLib.SOURCE_REMOVE

    def open_settings_from_tray(self) -> bool:
        self.ensure_window()
        self.window.present_focused()
        self.window.open_settings()
        return GLib.SOURCE_REMOVE

    def open_onboarding(self, parent: Gtk.Window | None = None) -> None:
        if self.onboarding is not None:
            self.onboarding.present()
            return
        self.ensure_window()
        self.onboarding = OnboardingWindow(self, parent)
        self.onboarding.present()

    def paste_backend_description(self) -> str:
        descriptions = {
            "auto": "Le collage direct est en cours de configuration par l'assistant.",
            "wtype": "Le collage direct fonctionne avec la méthode validée par l'assistant.",
            "xwayland": "Le collage direct fonctionne avec la méthode validée par l'assistant.",
            "xorg": "Le collage direct est préparé pour la session graphique validée par l'assistant.",
            "ydotool": "Le collage direct fonctionne avec la méthode système validée par l'assistant.",
            "portal": "Le collage direct utilise l'autorisation Ubuntu validée par l'assistant.",
            "clipboard_only": "Koplyx restaure les éléments dans le presse-papiers. Utilisez Ctrl+V pour les insérer.",
        }
        return descriptions.get(self.config.get("paste_backend"), descriptions["auto"])

    def onboarding_test_plan(self) -> list[str]:
        plan: list[str] = []
        if command_available("wtype"):
            plan.append("wtype")
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" and os.environ.get("DISPLAY") and command_exists("xdotool"):
            plan.append("xwayland")
        if xorg_sessions():
            plan.append("xorg")
        if command_available("ydotool") and not os.environ.get("SNAP") and not os.environ.get("FLATPAK_ID"):
            plan.append("ydotool")
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            plan.append("portal")
        return plan

    def begin_onboarding_test(self, onboarding: OnboardingWindow, backend: str) -> None:
        if not self.watcher:
            onboarding.test_result(False, backend)
            return
        if backend == "xorg":
            sessions = xorg_sessions()
            if not sessions:
                onboarding.test_result(False, backend)
                return
            ok, message = run_privileged("gdm-xorg-enable", str(sessions[0]))
            if ok:
                onboarding.test_result(True, backend)
                onboarding.status.set_text(message + " Après le redémarrage, confirmez que le collage fonctionne.")
            else:
                onboarding.test_result(False, backend)
                onboarding.status.set_text(message)
            return
        if backend == "ydotool":
            ok, message = run_privileged("ydotool-enable")
            if not ok:
                onboarding.test_result(False, backend)
                onboarding.status.set_text(message)
                return
        if backend == "portal":
            onboarding.status.set_text("Ubuntu va demander l'autorisation clavier. Acceptez-la pour continuer le test.")

            def portal_ready(ok, message):
                if not ok:
                    onboarding.test_result(False, backend)
                    onboarding.status.set_text(message)
                    return
                self.prepare_onboarding_injection(onboarding, backend)

            self.portal_keyboard.prepare(portal_ready)
            return
        self.prepare_onboarding_injection(onboarding, backend)

    def prepare_onboarding_injection(self, onboarding: OnboardingWindow, backend: str) -> None:
        self.onboarding_test_marker = "KOPLYX-TEST-COLLAGE-7F3A"
        self.onboarding_test_digest = sha256("text", self.onboarding_test_marker.encode("utf-8"))
        self.onboarding_previous_text = None
        self.watcher.paused_until = time.time() + 7.0

        def save_previous(_clipboard, result) -> None:
            try:
                self.onboarding_previous_text = self.watcher.clipboard.read_text_finish(result)
            except GLib.Error:
                self.onboarding_previous_text = None
            self.watcher.set_text(self.onboarding_test_marker)
            onboarding.hide()
            if self.window:
                self.window.hide()
            GLib.timeout_add(1800, self.inject_onboarding_test, onboarding, backend)

        try:
            self.watcher.clipboard.read_text_async(None, save_previous)
        except Exception:
            self.watcher.set_text(self.onboarding_test_marker)
            onboarding.hide()
            if self.window:
                self.window.hide()
            GLib.timeout_add(1800, self.inject_onboarding_test, onboarding, backend)

    def inject_onboarding_test(self, onboarding: OnboardingWindow, backend: str) -> bool:
        self.remember_active_window()
        if backend == "portal":
            sent = bool(self.portal_keyboard.ready and self.portal_keyboard.paste())
            candidates = ["portal"]
        else:
            candidates = paste_tool_candidates(self.previous_window_id, backend)
            sent = False
        selected = candidates[0] if candidates else backend
        used = selected
        if backend != "portal":
            for candidate in candidates:
                candidate_backend = {
                    "wtype": "wtype",
                    "xdotool": "xwayland" if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" else "xorg",
                    "ydotool": "ydotool",
                }.get(candidate, backend)
                if paste_clipboard_now(self.previous_window_id, candidate_backend):
                    sent = True
                    used = candidate
                    break
        if backend == "portal":
            self.portal_keyboard.close()
        GLib.timeout_add(700, self.restore_onboarding_clipboard)
        GLib.idle_add(onboarding.test_result, sent, used)
        return GLib.SOURCE_REMOVE

    def restore_onboarding_clipboard(self) -> bool:
        if self.watcher and self.onboarding_previous_text is not None:
            self.watcher.set_text(self.onboarding_previous_text)
        self.onboarding_test_marker = ""
        self.onboarding_test_digest = ""
        return GLib.SOURCE_REMOVE

    def launch_xwayland_backend(self) -> None:
        environment = os.environ.copy()
        environment["GDK_BACKEND"] = "x11"
        self.config.set("onboarding_completed", True)
        self.control_server.close()
        try:
            subprocess.Popen([sys.executable, str(Path(__file__)), "--show"], env=environment)
            self.quit()
        except OSError as exc:
            self.set_status(f"Impossible de relancer Koplyx sous XWayland : {exc}")

    def quit_from_tray(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def background_mode_active(self) -> bool:
        return bool(self.tray and self.tray.available)

    def background_access_available(self) -> bool:
        return self.background_mode_active() or self.control_server.available

    def background_status_message(self) -> str:
        if self.background_mode_active():
            return "Koplyx est actif en arrière-plan. Utilisez l'indicateur système pour l'afficher."
        return "Koplyx est actif en arrière-plan. Utilisez le raccourci global pour l'afficher."

    def tray_label(self) -> str:
        return "Arrière-plan actif" if self.background_access_available() else "Fenêtre visible"

    def tray_detail(self) -> str:
        if self.background_mode_active():
            return "Indicateur système connecté"
        if self.control_server.available:
            return "Raccourci global prêt"
        if not self.config.get("show_tray"):
            return "Indicateur système désactivé"
        if self.tray and self.tray.error:
            return self.tray.error
        return "Indicateur système indisponible"

    def sync_tray(self) -> bool:
        self.tray = TrayIndicator(self) if self.config.get("show_tray") else None
        return self.background_mode_active()

    def sync_global_shortcut(self) -> bool:
        self.shortcut_sync_ok = install_gnome_shortcut(self.config.get("shortcut"), shortcut_command())
        return self.shortcut_sync_ok

    def set_tray_enabled(self, enabled: bool) -> bool:
        self.config.set("show_tray", enabled)
        available = self.sync_tray()
        self.refresh()
        return available if enabled else True

    def sleep_to_tray(self) -> bool:
        if not self.background_access_available():
            self.set_status("Indicateur système indisponible : la fenêtre reste ouverte.")
            if self.window:
                self.window.present_focused()
            return False
        if self.window:
            self.window.hide()
        self.set_status(self.background_status_message())
        return True

    def sync_autostart(self) -> None:
        if self.config.get("autostart_enabled"):
            ok = install_autostart_file()
            if not ok:
                self.set_status("Autostart indisponible dans cet environnement.")
        else:
            remove_autostart_file()

    def set_autostart_enabled(self, enabled: bool) -> bool:
        ok = install_autostart_file() if enabled else remove_autostart_file()
        if ok:
            self.config.set("autostart_enabled", enabled)
        return ok

    def remember_active_window(self) -> None:
        window_id = x11_active_window()
        if not window_id:
            window_id = xwayland_active_window()
        if not window_id:
            self.previous_window_id = None
            return
        if x11_window_pid(window_id) == os.getpid():
            return
        self.previous_window_id = window_id

    def set_status(self, message: str) -> None:
        self.status_message = message
        if self.window:
            self.window.set_items(self.display_items())

    def refresh(self) -> None:
        if self.window:
            self.window.set_items(self.display_items())

    def display_items(self) -> list[DisplayItem]:
        if not self.window:
            return []
        query = self.window.query().strip().lower()
        pinned_only = self.window.active_view == "pinned"
        pinned_history_position = self.config.get("pinned_history_position")
        display_items = []
        for item in self.store.recent(
            pinned_only=pinned_only,
            pinned_history_position=pinned_history_position,
        ):
            display_item = self.display_item(item)
            if query and query not in display_item.search_text.lower():
                continue
            display_items.append(display_item)
        return display_items

    def display_item(self, item: HistoryItem) -> DisplayItem:
        payload = self.store.payload(item.id)
        if not payload:
            return DisplayItem(
                item.id,
                item.kind,
                item.mime,
                item.preview,
                item.preview,
                item.kind.upper(),
                item.preview,
                item.created_at,
                item.pinned,
            )
        kind, mime, data = payload
        if kind == "text":
            title = text_content(data)
            detail = private_preview(kind, mime, data)
            search_text = f"{title} {detail}"
            return DisplayItem(
                item.id,
                kind,
                mime,
                item.preview,
                title,
                detail,
                search_text,
                item.created_at,
                item.pinned,
                title_tooltip=text_tooltip(data),
            )
        if kind == "image":
            detail = private_preview(kind, mime, data)
            return DisplayItem(
                item.id,
                kind,
                mime,
                item.preview,
                "Image copiee",
                detail,
                detail,
                item.created_at,
                item.pinned,
                image_data=data,
            )
        if kind in ("file", "files"):
            uris = uri_list_from_bytes(data)
            title = file_title_from_uris(uris)
            detail = private_preview(kind, mime, data)
            search_text = " ".join([title, detail, *[uri_display_name(uri) for uri in uris]])
            return DisplayItem(
                item.id,
                kind,
                mime,
                item.preview,
                title,
                detail,
                search_text,
                item.created_at,
                item.pinned,
            )
        return DisplayItem(
            item.id,
            kind,
            mime,
            item.preview,
            item.preview,
            kind.upper(),
            item.preview,
            item.created_at,
            item.pinned,
        )

    def restore_item(self, item_id: int) -> None:
        payload = self.store.payload(item_id)
        if not payload or not self.watcher:
            return
        kind, _mime, data = payload
        restored = True
        if kind == "text":
            self.watcher.set_text(data.decode("utf-8", errors="replace"))
        elif kind == "image":
            self.watcher.set_image_png(data)
        elif kind in ("file", "files"):
            restored = self.watcher.set_files(data)
            if not restored:
                self.set_status("Restauration fichier impossible.")
        else:
            restored = False
        if restored:
            backend = self.config.get("paste_backend") or "auto"
            if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" and backend == "portal" and not self.portal_keyboard.ready:
                # Les outils directs restent prioritaires et n'affichent
                # aucun indicateur de session distante.
                if self.portal_keyboard.has_restore_token():
                    self.set_status("Contenu restauré. Réactivation du collage direct…")

                    def paste_after_restore(ok, message):
                        if not ok:
                            self.set_status(
                                "Contenu restauré. Autorisez le collage direct dans Paramètres pour l'envoyer au curseur."
                            )
                            return
                        self.set_status(message)
                        if self.sleep_to_tray():
                            GLib.timeout_add(120, self.activate_then_paste)

                    # Avec un jeton persistant valide, le portail réactive la
                    # session sans afficher de nouvelle demande au bureau.
                    self.portal_keyboard.prepare(paste_after_restore)
                else:
                    self.set_status("Contenu restauré. Autorisez le portail dans Paramètres pour l'envoyer au curseur.")
                return
            if backend != "portal" and not paste_tool_candidates(self.previous_window_id, backend):
                self.set_status("Contenu restauré dans le presse-papiers. Le backend choisi ne permet pas le collage direct.")
                return
            if self.sleep_to_tray():
                GLib.timeout_add(120, self.activate_then_paste)
        else:
            self.set_status("Restauration impossible.")

    def authorize_paste(self, feedback=None) -> None:
        def update(ok, message):
            self.set_status(message)
            if feedback:
                feedback(message)
            # L'autorisation est conservée par le jeton, pas par une session
            # RemoteDesktop maintenue ouverte en permanence. L'icône GNOME
            # disparaît ainsi dès que la demande est terminée.
            if ok:
                self.config.set("paste_backend", "portal")
                self.portal_keyboard.close()
        update(False, "Autorisez le clavier dans la demande du bureau pour activer le collage direct.")
        self.portal_keyboard.prepare(update)

    def activate_then_paste(self) -> bool:
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11":
            if not activate_x11_window(self.previous_window_id):
                self.paste_failed("Fenêtre cible introuvable : contenu restauré, utilisez Ctrl+V.")
                return GLib.SOURCE_REMOVE
        GLib.timeout_add(180, self.try_auto_paste)
        return GLib.SOURCE_REMOVE

    def try_auto_paste(self) -> bool:
        if self.window and self.window.is_active():
            self.paste_failed("Koplyx a encore le focus. Sélectionnez le champ cible puis réessayez.")
            return GLib.SOURCE_REMOVE
        backend = self.config.get("paste_backend") or "auto"
        if backend == "portal":
            sent = self.portal_keyboard.ready and self.portal_keyboard.paste()
            if not sent and self.portal_keyboard.has_restore_token():
                self.set_status("Outil de collage direct indisponible. Réactivation du portail…")

                def paste_with_portal(ok, message):
                    if not ok:
                        self.paste_failed(message)
                        return
                    portal_sent = self.portal_keyboard.paste()
                    if portal_sent:
                        self.set_status("Commande de collage envoyée à la fenêtre active.")
                        self.portal_keyboard.close()
                    else:
                        self.paste_failed("Collage non autorisé ou indisponible. Contenu restauré : utilisez Ctrl+V.")

                self.portal_keyboard.prepare(paste_with_portal)
                return GLib.SOURCE_REMOVE
        else:
            sent = paste_clipboard_now(self.previous_window_id, backend)
        if sent:
            self.set_status("Commande de collage envoyée à la fenêtre active.")
            if self.portal_keyboard.ready:
                self.portal_keyboard.close()
        else:
            self.paste_failed("Collage non autorisé ou indisponible. Contenu restauré : utilisez Ctrl+V.")
        return GLib.SOURCE_REMOVE

    def paste_failed(self, message: str) -> None:
        self.set_status(message)
        if self.window:
            self.window.present()


def run_gsettings(args: list[str]) -> bool:
    try:
        proc = Gio.Subprocess.new(args, Gio.SubprocessFlags.NONE)
        proc.wait(None)
        return proc.get_successful()
    except GLib.Error:
        return False


def read_gsettings(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True)
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def install_gnome_shortcut(shortcut: str, command: str) -> bool:
    base = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
    binding = f"{base}/koplyx/"
    current = read_gsettings(["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"])
    if not current or current == "@as []":
        bindings = [binding]
    else:
        try:
            bindings = [x.strip("'") for x in current.strip("[]").split(", ") if x]
        except Exception:
            bindings = []
        if binding not in bindings:
            bindings.append(binding)
    list_value = "[" + ", ".join(f"'{b}'" for b in bindings) + "]"
    ok = run_gsettings(["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", list_value])
    schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
    ok = run_gsettings(["gsettings", "set", schema + ":" + binding, "name", APP_NAME]) and ok
    ok = run_gsettings(["gsettings", "set", schema + ":" + binding, "command", command]) and ok
    ok = run_gsettings(["gsettings", "set", schema + ":" + binding, "binding", shortcut]) and ok
    return ok


def shortcut_command() -> str:
    if os.environ.get("SNAP"):
        return "/snap/bin/koplyx --toggle"
    if (PROJECT_ROOT / ".git").exists():
        # Une session source doit rouvrir son propre profil, même si le Snap est installé.
        environment = " ".join(
            shlex.quote(f"{key}={os.environ[key]}")
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR") if key in os.environ
        )
        return f"env {environment} {shlex.quote(str(PROJECT_ROOT / 'bin/koplyx'))} --toggle"
    installed = shutil.which("koplyx")
    return f"{shlex.quote(installed)} --toggle" if installed else f"/usr/bin/python3 {shlex.quote(str(PROJECT_ROOT / 'koplyx/main.py'))} --toggle"


def desktop_entry(command: str) -> str:
    return f"""[Desktop Entry]
Type=Application
Name=Koplyx
Comment=Historique local chiffre du presse-papiers
Exec={command}
Icon={ICON_NAME}
Terminal=false
Categories=Utility;GTK;
StartupNotify=false
"""


def autostart_command() -> str:
    installed = shutil.which("koplyx")
    if installed:
        return "koplyx --hidden"
    return f"/usr/bin/python3 {shlex.quote(str(PROJECT_ROOT / 'koplyx/main.py'))} --hidden"


def repair_user_desktop_files() -> None:
    desktop_path = user_desktop_path()
    if desktop_path.exists():
        try:
            desktop_path.write_text(desktop_entry("koplyx"), encoding="utf-8")
        except OSError:
            pass

    autostart_path = autostart_desktop_path()
    if autostart_path.exists():
        try:
            autostart_path.write_text(desktop_entry(autostart_command()), encoding="utf-8")
        except OSError:
            pass


def install_autostart_file() -> bool:
    try:
        autostart_path = autostart_desktop_path()
        autostart_path.parent.mkdir(parents=True, exist_ok=True)
        autostart_path.write_text(desktop_entry(autostart_command()), encoding="utf-8")
        return True
    except OSError:
        return False


def remove_autostart_file() -> bool:
    try:
        autostart_path = autostart_desktop_path()
        if autostart_path.exists():
            autostart_path.unlink()
        return True
    except OSError:
        return False


def apply_css() -> None:
    css = b"""
    * {
      font-family: Inter, Cantarell, system-ui, sans-serif;
      letter-spacing: 0;
    }
    window, .koplyx-window, .settings-window {
      background: #080b09;
      color: #f4fff7;
    }
    .app-shell, .settings-shell {
      background: linear-gradient(145deg, #080b09 0%, #101812 48%, #0a0f0b 100%);
    }
    .hero, .settings-hero {
      background: #111b14;
      border: 1px solid #294533;
      border-radius: 18px;
    }
    .hero {
      margin: 0;
      padding: 18px;
    }
    .settings-hero {
      padding: 18px;
    }
    .eyebrow, .search-label, .section-title {
      color: #72d99c;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 1.2px;
    }
    .brand {
      color: #f7fff9;
      font-size: 28px;
      font-weight: 800;
    }
    .subtitle {
      color: #afc2b4;
      font-size: 13px;
    }
    .header-actions {
      margin-top: 2px;
    }
    .search-panel {
      background: #101812;
      border: 1px solid #294533;
      border-radius: 14px;
      padding: 12px;
    }
    searchentry, entry, spinbutton {
      background: #090e0b;
      color: #f5fff7;
      border: 1px solid #31563e;
      border-radius: 10px;
      min-height: 40px;
      caret-color: #83ebb0;
    }
    searchentry:focus, entry:focus, spinbutton:focus-within {
      border-color: #4dcc7f;
      box-shadow: 0 0 0 2px alpha(#4dcc7f, 0.16);
    }
    .history-scroller {
      background: transparent;
    }
    .history-row {
      background: #101812;
      border: 1px solid #284431;
      border-radius: 14px;
      margin: 0 0 8px 0;
    }
    .history-row:hover {
      background: #17231a;
      border-color: #4d9b68;
    }
    .type-box {
      background: #153d2a;
      border: 1px solid #2f8555;
      border-radius: 12px;
      min-width: 48px;
      min-height: 48px;
      padding: 0;
    }
    .type-icon {
      color: #d7ffe5;
    }
    .thumb {
      background: #153d2a;
      border-radius: 12px;
    }
    .history-title {
      color: #f4fff7;
      font-size: 14px;
      font-weight: 700;
    }
    .meta, .status, .settings-note {
      color: #a8bdad;
      font-size: 12px;
    }
    .settings-feedback {
      color: #8cebb4;
      font-size: 12px;
      font-weight: 600;
    }
    .settings-warning {
      color: #d2e7d7;
      font-size: 11px;
    }
    .shortcut-value {
      color: #d9ffe6;
      font-weight: 700;
      margin-right: 8px;
    }
    .shortcut-dialog-value {
      background: #143522;
      border: 1px solid #46bd73;
      border-radius: 14px;
      color: #effff4;
      font-size: 24px;
      font-weight: 800;
      padding: 18px;
    }
    .empty-state {
      margin-top: 86px;
      margin-bottom: 86px;
    }
    .empty-icon {
      color: #64cf8e;
    }
    .empty-title {
      color: #effff4;
      font-size: 16px;
      font-weight: 700;
    }
    .empty-detail {
      color: #a4b9a9;
      font-size: 13px;
    }
    .app-shell button, .settings-shell button, .shortcut-shell button, .pinned-filter-popover button {
      border-radius: 10px;
      min-height: 36px;
      padding: 6px 12px;
      background: #18251b;
      color: #edf9f0;
      border: 1px solid #31523a;
    }
    .app-shell button:hover, .settings-shell button:hover, .shortcut-shell button:hover, .pinned-filter-popover button:hover {
      background: #203526;
      border-color: #57a872;
    }
    .app-shell button:active, .settings-shell button:active, .shortcut-shell button:active, .pinned-filter-popover button:active {
      background: #111c14;
    }
    button.icon-button {
      min-width: 36px;
      min-height: 36px;
      padding: 6px;
      background: #142018;
      color: #c7f6d6;
    }
    button.danger-button:hover {
      background: #2a211e;
      border-color: #806057;
      color: #fff0ea;
    }
    button.restore-button, button.primary {
      background: #1e8d50;
      border-color: #52d582;
      color: #f7fff9;
      font-weight: 700;
    }
    button.restore-button:hover, button.primary:hover {
      background: #27aa62;
      border-color: #8af0af;
    }
    button.is-pinned {
      background: #1c3524;
      border-color: #4a9b66;
      color: #c6ffd9;
    }
    .tabs {
      background: #0d130e;
      border: 1px solid #294332;
      border-radius: 12px;
      padding: 5px;
    }
    .tabs button {
      min-height: 32px;
      padding: 5px 14px;
      background: transparent;
      border-color: transparent;
      color: #9eb4a4;
      font-weight: 600;
    }
    .tabs button:hover {
      background: #1a2c1e;
      color: #effff4;
    }
    .tabs .tab-active {
      background: #1c8d50;
      border-color: #56d784;
      color: #f6fff8;
    }
    .settings-title {
      font-size: 25px;
      font-weight: 800;
      color: #f4fff7;
    }
    .settings-row {
      background: #101812;
      border: 1px solid #284431;
      border-radius: 12px;
      min-height: 44px;
      padding: 8px 12px;
    }
    .settings-card {
      background: #0d160f;
      border: 1px solid #315a3f;
      border-radius: 14px;
      padding: 10px;
    }
    .settings-card .settings-row {
      margin: 0;
      border-color: #3b6649;
    }
    .shortcut-state {
      font-size: 12px;
      font-weight: 700;
      padding: 2px 4px;
    }
    .shortcut-state-ok {
      color: #94efb7;
    }
    .shortcut-state-error {
      color: #ffd2bd;
    }
    .status-panel {
      background: #0d150f;
      border: 1px solid #294533;
      border-radius: 12px;
      padding: 8px 12px;
    }
    .status-icon {
      color: #72d99c;
    }
    .tray-badge {
      border-radius: 8px;
      padding: 4px 8px;
      font-size: 11px;
      font-weight: 700;
    }
    .tray-active {
      background: #173d25;
      color: #a7f6c2;
    }
    .tray-warning {
      background: #222b23;
      color: #d4e2d6;
    }
    switch:checked {
      background: #2baf61;
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Koplyx clipboard history")
    parser.add_argument("--toggle", action="store_true", help="toggle the quick window")
    parser.add_argument("--hidden", action="store_true", help="start in background")
    parser.add_argument("--restore-display-session", action="store_true", help="restaurer la sauvegarde GDM Koplyx")
    args, _unknown = parser.parse_known_args()
    if args.restore_display_session:
        ok, message = run_privileged("gdm-restore")
        print(message)
        return 0 if ok else 1
    if args.toggle and send_control_command("toggle"):
        return 0
    if not args.hidden and not args.toggle and send_control_command("show"):
        return 0
    if args.hidden and send_control_command("keep-alive"):
        return 0
    app = KoplyxApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        app.quit()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
