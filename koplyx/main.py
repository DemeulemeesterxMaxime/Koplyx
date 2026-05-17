#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import signal
import sqlite3
import shutil
import subprocess
import sys
import time
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
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from cryptography.fernet import Fernet

from koplyx import APP_ID, APP_NAME


POLL_INTERVAL_MS = 900
DEFAULT_CONFIG = {
    "max_items": 500,
    "max_age_days": 30,
    "max_storage_mb": 256,
    "shortcut": "<Ctrl><Alt>V",
    "capture_text": True,
    "capture_images": True,
    "auto_paste": True,
    "show_tray": True,
    "start_hidden": False,
}

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


def user_desktop_path() -> Path:
    return xdg_path("XDG_DATA_HOME", ".local/share") / "applications" / "dev.limax.koplyx.desktop"


def autostart_desktop_path() -> Path:
    return xdg_path("XDG_CONFIG_HOME", ".config") / "autostart" / "koplyx.desktop"


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def paste_tool_name() -> str | None:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        if command_exists("wtype"):
            return "wtype"
        if command_exists("ydotool"):
            return "ydotool"
    if command_exists("xdotool"):
        return "xdotool"
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
    if not window_id or not command_exists("xdotool"):
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


def paste_clipboard_now() -> bool:
    tool = paste_tool_name()
    if tool == "xdotool":
        return subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=False).returncode == 0
    if tool == "wtype":
        return subprocess.run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], check=False).returncode == 0
    if tool == "ydotool":
        return subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=False).returncode == 0
    return False


def accelerator_label(accelerator: str) -> str:
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
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = CONFIG_DIR / "config.json"
        self.data = DEFAULT_CONFIG.copy()
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        if not global_shortcut_valid(str(self.data.get("shortcut", ""))):
            self.data["shortcut"] = DEFAULT_CONFIG["shortcut"]
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get(self, key: str):
        return self.data.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()


class CryptoBox:
    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        key_path = CONFIG_DIR / "key.bin"
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
            ensure_private_file(key_path)
        self.fernet = Fernet(key)

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


class HistoryStore:
    def __init__(self, crypto: CryptoBox, config: Config) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
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

    def add(self, kind: str, mime: str, data: bytes, preview: str) -> bool:
        digest = sha256(kind, data)
        encrypted = self.crypto.encrypt(data)
        ts = now_ts()
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO items(kind, mime, hash, encrypted_blob, preview, bytes_size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (kind, mime, digest, encrypted, preview[:500], len(data), ts),
            )
            inserted = True
        except sqlite3.IntegrityError:
            cur.execute("UPDATE items SET created_at = ? WHERE hash = ?", (ts, digest))
            inserted = False
        self.conn.commit()
        self.prune()
        return inserted

    def list(self, query: str = "", pinned_text_only: bool = False) -> list[HistoryItem]:
        conditions = []
        params = []
        if query.strip():
            conditions.append("preview LIKE ?")
            params.append(f"%{query.strip()}%")
        if pinned_text_only:
            conditions.append("pinned = 1")
            conditions.append("kind = 'text'")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""
            SELECT id, kind, mime, preview, created_at, pinned
            FROM items
            {where}
            ORDER BY pinned DESC, created_at DESC
            LIMIT 300
            """,
            params,
        ).fetchall()
        return [HistoryItem(*row) for row in rows]

    def payload(self, item_id: int) -> tuple[str, str, bytes] | None:
        row = self.conn.execute(
            "SELECT kind, mime, encrypted_blob FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            return None
        kind, mime, encrypted = row
        return kind, mime, self.crypto.decrypt(encrypted)

    def delete(self, item_id: int) -> None:
        self.conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM items")
        self.conn.commit()

    def toggle_pin(self, item_id: int) -> None:
        self.conn.execute(
            "UPDATE items SET pinned = CASE pinned WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
            (item_id,),
        )
        self.conn.commit()

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


class ClipboardWatcher:
    def __init__(self, app: "KoplyxApplication") -> None:
        self.app = app
        display = Gdk.Display.get_default()
        self.clipboard = display.get_clipboard()
        self.last_text_hash = ""
        self.last_image_hash = ""
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
        return True

    def on_text(self, clipboard, result) -> None:
        try:
            text = clipboard.read_text_finish(result)
        except GLib.Error:
            return
        if not text or not text.strip():
            return
        data = text.encode("utf-8")
        digest = sha256("text", data)
        if digest == self.last_text_hash:
            return
        self.last_text_hash = digest
        preview = " ".join(text.strip().split())
        self.app.store.add("text", "text/plain;charset=utf-8", data, preview)
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
        self.app.store.add("image", "image/png", png_bytes, f"Image PNG - {w} x {h}")
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


class HistoryRow(Gtk.ListBoxRow):
    def __init__(self, app: "KoplyxApplication", item: HistoryItem) -> None:
        super().__init__()
        self.app = app
        self.item = item
        self.set_activatable(True)
        self.add_css_class("history-row")

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        root.set_margin_top(6)
        root.set_margin_bottom(6)
        root.set_margin_start(10)
        root.set_margin_end(8)
        self.set_child(root)

        type_box = Gtk.Box()
        type_box.set_size_request(42, 42)
        type_box.add_css_class("type-box")
        type_label = Gtk.Label(label="IMG" if item.kind == "image" else "TXT")
        type_label.add_css_class("type-label")
        type_box.append(type_label)
        root.append(type_box)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        title = Gtk.Label(label=item.preview)
        title.set_xalign(0)
        title.set_ellipsize(3)
        title.add_css_class("preview")
        meta = Gtk.Label(label=f"{item.kind.upper()} · {human_time(item.created_at)}" + (" · epingle" if item.pinned else ""))
        meta.set_xalign(0)
        meta.add_css_class("meta")
        text_box.append(title)
        text_box.append(meta)
        root.append(text_box)

        pin = Gtk.Button(icon_name="view-pin-symbolic")
        pin.set_tooltip_text("Epingler")
        pin.add_css_class("flat-icon")
        pin.connect("clicked", self.on_pin)
        paste = Gtk.Button(icon_name="edit-paste-symbolic")
        paste.set_tooltip_text("Restaurer dans le presse-papiers")
        paste.add_css_class("accent-icon")
        paste.connect("clicked", self.on_paste)
        delete = Gtk.Button(icon_name="user-trash-symbolic")
        delete.set_tooltip_text("Supprimer")
        delete.add_css_class("flat-icon")
        delete.connect("clicked", self.on_delete)
        root.append(pin)
        root.append(paste)
        root.append(delete)

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
        self.set_default_size(560, 620)
        self.set_size_request(420, 360)
        self.add_css_class("koplyx-window")
        self.active_view = "history"

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.set_margin_top(14)
        header.set_margin_bottom(10)
        header.set_margin_start(14)
        header.set_margin_end(14)
        root.append(header)

        brand = Gtk.Label(label="Koplyx")
        brand.add_css_class("brand")
        header.append(brand)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Rechercher dans l'historique")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda _w: app.refresh())
        header.append(self.search)

        settings = Gtk.Button(icon_name="emblem-system-symbolic")
        settings.set_tooltip_text("Parametres")
        settings.add_css_class("flat-icon")
        settings.connect("clicked", lambda _b: self.open_settings())
        header.append(settings)

        clear = Gtk.Button(icon_name="edit-clear-all-symbolic")
        clear.set_tooltip_text("Effacer l'historique")
        clear.add_css_class("flat-icon")
        clear.connect("clicked", lambda _b: self.confirm_clear())
        header.append(clear)

        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tabs.set_margin_start(14)
        tabs.set_margin_end(14)
        tabs.set_margin_bottom(10)
        tabs.add_css_class("tabs")
        root.append(tabs)

        self.history_tab = Gtk.Button(label="Historique")
        self.history_tab.connect("clicked", lambda _b: self.set_active_view("history"))
        tabs.append(self.history_tab)

        self.pinned_text_tab = Gtk.Button(label="Textes epingles")
        self.pinned_text_tab.connect("clicked", lambda _b: self.set_active_view("pinned_text"))
        tabs.append(self.pinned_text_tab)
        self.update_tabs()

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        root.append(scroller)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.connect("row-activated", self.on_row_activated)
        scroller.set_child(self.listbox)

        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.add_css_class("status")
        self.status.set_margin_top(8)
        self.status.set_margin_bottom(10)
        self.status.set_margin_start(14)
        self.status.set_margin_end(14)
        root.append(self.status)

    def present_focused(self) -> None:
        self.app.remember_active_window()
        self.present()
        self.search.grab_focus()

    def query(self) -> str:
        return self.search.get_text()

    def set_active_view(self, view: str) -> None:
        self.active_view = view
        if view == "pinned_text":
            self.search.set_placeholder_text("Rechercher dans les textes epingles")
        else:
            self.search.set_placeholder_text("Rechercher dans l'historique")
        self.update_tabs()
        self.app.refresh()

    def update_tabs(self) -> None:
        for button in (self.history_tab, self.pinned_text_tab):
            button.remove_css_class("tab-active")
        if self.active_view == "pinned_text":
            self.pinned_text_tab.add_css_class("tab-active")
        else:
            self.history_tab.add_css_class("tab-active")

    def on_row_activated(self, _box, row) -> None:
        item = getattr(row, "item", None)
        if item:
            self.app.restore_item(item.id)

    def set_items(self, items: list[HistoryItem]) -> None:
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
        if not items:
            message = (
                "Aucun texte epingle"
                if self.active_view == "pinned_text"
                else "Aucune copie enregistree"
            )
            empty = Gtk.Label(label=message)
            empty.add_css_class("empty")
            empty.set_margin_top(80)
            self.listbox.append(empty)
        else:
            for item in items:
                self.listbox.append(HistoryRow(self.app, item))
        count, total = self.app.store.stats()
        mb = total / 1024 / 1024
        view_label = "textes epingles" if self.active_view == "pinned_text" else "historique"
        message = self.app.status_message
        if message:
            self.status.set_text(message)
        else:
            self.status.set_text(f"{view_label} · {count} elements · {mb:.1f} Mo · stockage local chiffre")

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
        super().__init__(title="Parametres Koplyx", transient_for=parent, modal=True)
        self.app = app
        self.set_default_size(460, 460)
        self.add_css_class("settings-window")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)
        self.set_child(root)

        title = Gtk.Label(label="Parametres")
        title.set_xalign(0)
        title.add_css_class("settings-title")
        root.append(title)

        self.shortcut = self.shortcut_row(root, "Raccourci global", "shortcut")
        self.max_items = self.spin(root, "Nombre max d'entrees", "max_items", 10, 10000)
        self.max_age = self.spin(root, "Retention en jours", "max_age_days", 1, 3650)
        self.max_storage = self.spin(root, "Stockage max (Mo)", "max_storage_mb", 16, 8192)
        self.capture_text = self.switch(root, "Capturer le texte", "capture_text")
        self.capture_images = self.switch(root, "Capturer les images", "capture_images")
        self.auto_paste = self.switch(root, "Coller automatiquement apres un clic", "auto_paste")
        self.show_tray = self.switch(root, "Afficher dans la barre systeme", "show_tray")

        install = Gtk.Button(label="Installer raccourci GNOME")
        install.add_css_class("primary")
        install.connect("clicked", self.install_shortcut)
        root.append(install)

        autostart = Gtk.Button(label="Activer autostart")
        autostart.connect("clicked", self.install_autostart)
        root.append(autostart)

        self.feedback = Gtk.Label()
        self.feedback.set_wrap(True)
        self.feedback.set_xalign(0)
        self.feedback.add_css_class("settings-feedback")
        root.append(self.feedback)

        tools = paste_tool_name()
        paste_note = tools if tools else "non disponible, installer xdotool sur X11 ou wtype sur Wayland"
        tray_note = "disponible" if app.tray and app.tray.available else "non detecte"
        note = Gtk.Label(
            label=f"Outil collage auto: {paste_note}. Barre systeme: {tray_note}. Wayland peut limiter les raccourcis globaux selon le bureau."
        )
        note.set_wrap(True)
        note.set_xalign(0)
        note.add_css_class("settings-note")
        root.append(note)

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
        self.feedback.set_text(f"Raccourci pret: {accelerator_label(shortcut)}.")
        self.app.set_status("Raccourci modifie. Cliquez Installer raccourci GNOME pour l'appliquer.")

    def spin(self, root, label: str, key: str, minimum: int, maximum: int) -> Gtk.SpinButton:
        row = self.row(root, label)
        widget = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        widget.set_value(float(self.app.config.get(key)))
        widget.connect("value-changed", lambda w: self.app.config.set(key, int(w.get_value())))
        row.append(widget)
        return widget

    def switch(self, root, label: str, key: str) -> Gtk.Switch:
        row = self.row(root, label)
        widget = Gtk.Switch(active=bool(self.app.config.get(key)))
        widget.connect("notify::active", lambda w, _p: self.app.config.set(key, w.get_active()))
        row.append(widget)
        return widget

    def row(self, root, label: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)
        root.append(row)
        return row

    def install_shortcut(self, _button) -> None:
        shortcut = self.app.config.get("shortcut")
        ok = install_gnome_shortcut(shortcut, "koplyx --toggle")
        self.feedback.set_text("Raccourci GNOME installe." if ok else "Impossible d'installer le raccourci GNOME.")
        self.app.set_status("Raccourci GNOME installe." if ok else "Erreur raccourci GNOME.")

    def install_autostart(self, _button) -> None:
        ok = install_autostart_file()
        self.feedback.set_text("Autostart active." if ok else "Impossible d'activer l'autostart.")
        self.app.set_status("Autostart active." if ok else "Erreur autostart.")


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


class TrayIndicator:
    MENU_PATH = "/Menu"
    MENU_SETTINGS_ID = 1
    MENU_QUIT_ID = 2

    def __init__(self, app: "KoplyxApplication") -> None:
        self.app = app
        self.available = False
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
        except Exception:
            self.dbus = None
            return

        self.dbus = dbus
        DBusGMainLoop(set_as_default=True)
        try:
            self.bus = dbus.SessionBus()
            if not self.bus.name_has_owner("org.kde.StatusNotifierWatcher"):
                return
        except Exception:
            return

        class DBusMenu(dbus.service.Object):
            def __init__(self, owner: "TrayIndicator") -> None:
                self.owner = owner
                super().__init__(owner.bus_name, TrayIndicator.MENU_PATH)

            def menu_item(self, item_id: int, label: str) -> "dbus.Struct":
                props = dbus.Dictionary(
                    {
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
                        self.menu_item(TrayIndicator.MENU_SETTINGS_ID, "Parametres"),
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
                    TrayIndicator.MENU_SETTINGS_ID: "Parametres",
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
                    if int(item_id) == TrayIndicator.MENU_SETTINGS_ID:
                        return dbus.String("Parametres")
                    if int(item_id) == TrayIndicator.MENU_QUIT_ID:
                        return dbus.String("Quitter Koplyx")
                if prop in ("enabled", "visible"):
                    return dbus.Boolean(True)
                return dbus.String("")

            @dbus.service.method("com.canonical.dbusmenu", in_signature="isvu", out_signature="")
            def Event(self, item_id, event_id, _data, _timestamp):
                if event_id != "clicked":
                    return
                if int(item_id) == TrayIndicator.MENU_SETTINGS_ID:
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
                GLib.idle_add(self.owner.app.toggle_window)

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

        self.bus_name = dbus.service.BusName("dev.limax.koplyx.StatusNotifierItem", self.bus)
        self.menu = DBusMenu(self)
        self.item = StatusNotifierItem(self)
        watcher = self.bus.get_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
        watcher.RegisterStatusNotifierItem(
            "dev.limax.koplyx.StatusNotifierItem",
            dbus_interface="org.kde.StatusNotifierWatcher",
        )
        self.available = True


class KoplyxApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.config = Config()
        self.crypto = CryptoBox()
        self.store = HistoryStore(self.crypto, self.config)
        self.window: KoplyxWindow | None = None
        self.watcher: ClipboardWatcher | None = None
        self.tray: TrayIndicator | None = None
        self.previous_window_id: str | None = None
        self.status_message = ""

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        repair_user_desktop_files()
        apply_css()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_shutdown_signal)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_shutdown_signal)
        if self.config.get("show_tray"):
            self.tray = TrayIndicator(self)

    def on_shutdown_signal(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_activate(self) -> None:
        self.ensure_window()
        if not self.config.get("start_hidden"):
            self.window.present_focused()

    def do_command_line(self, command_line) -> int:
        args = command_line.get_arguments()[1:]
        self.ensure_window()
        if "--hidden" in args:
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
        if self.window.is_visible():
            self.window.hide()
        else:
            self.window.present_focused()

    def open_settings_from_tray(self) -> bool:
        self.ensure_window()
        self.window.present_focused()
        self.window.open_settings()
        return GLib.SOURCE_REMOVE

    def quit_from_tray(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def remember_active_window(self) -> None:
        window_id = x11_active_window()
        if not window_id:
            return
        if x11_window_pid(window_id) == os.getpid():
            return
        self.previous_window_id = window_id

    def set_status(self, message: str) -> None:
        self.status_message = message
        if self.window:
            self.window.set_items(
                self.store.list(
                    self.window.query(),
                    pinned_text_only=self.window.active_view == "pinned_text",
                )
            )

    def refresh(self) -> None:
        if self.window:
            self.window.set_items(
                self.store.list(
                    self.window.query(),
                    pinned_text_only=self.window.active_view == "pinned_text",
                )
            )

    def restore_item(self, item_id: int) -> None:
        payload = self.store.payload(item_id)
        if not payload or not self.watcher:
            return
        kind, _mime, data = payload
        if kind == "text":
            self.watcher.set_text(data.decode("utf-8", errors="replace"))
        elif kind == "image":
            self.watcher.set_image_png(data)
        if self.window:
            self.window.hide()
        if self.config.get("auto_paste"):
            GLib.timeout_add(120, self.activate_then_paste)

    def activate_then_paste(self) -> bool:
        if activate_x11_window(self.previous_window_id):
            GLib.timeout_add(180, self.try_auto_paste)
        else:
            self.set_status("Copie restauree. Collage auto impossible: fenetre precedente introuvable.")
        return GLib.SOURCE_REMOVE

    def try_auto_paste(self) -> bool:
        if paste_clipboard_now():
            self.set_status("Texte colle dans la fenetre active.")
        else:
            self.set_status("Copie restauree. Collage auto impossible: xdotool indisponible ou refuse.")
        return GLib.SOURCE_REMOVE


def run_gsettings(args: list[str]) -> bool:
    try:
        proc = Gio.Subprocess.new(args, Gio.SubprocessFlags.NONE)
        proc.wait(None)
        return proc.get_successful()
    except GLib.Error:
        return False


def install_gnome_shortcut(shortcut: str, command: str) -> bool:
    base = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
    binding = f"{base}/koplyx/"
    current = os.popen("gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings").read().strip()
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
            autostart_path.write_text(desktop_entry("koplyx --hidden"), encoding="utf-8")
        except OSError:
            pass


def install_autostart_file() -> bool:
    try:
        autostart_path = autostart_desktop_path()
        autostart_path.parent.mkdir(parents=True, exist_ok=True)
        autostart_path.write_text(desktop_entry("koplyx --hidden"), encoding="utf-8")
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
      background: #111614;
      color: #eef3ef;
    }
    .brand {
      font-size: 20px;
      font-weight: 700;
      color: #dff7ea;
    }
    searchentry, entry, spinbutton {
      background: #1a211f;
      color: #eef3ef;
      border: 1px solid #2a3531;
      border-radius: 8px;
      min-height: 36px;
    }
    .history-row {
      background: #171d1b;
      border-bottom: 1px solid #24302c;
    }
    .history-row:hover {
      background: #1d2723;
    }
    .type-box {
      background: #20312b;
      border-radius: 8px;
    }
    .type-label {
      color: #73e6a2;
      font-size: 11px;
      font-weight: 700;
    }
    .preview {
      color: #f2f6f2;
      font-size: 14px;
      font-weight: 600;
    }
    .meta, .status, .settings-note {
      color: #8fa099;
      font-size: 12px;
    }
    .settings-feedback {
      color: #73e6a2;
      font-size: 12px;
    }
    .shortcut-value {
      color: #dff7ea;
      font-weight: 700;
      margin-right: 4px;
    }
    .shortcut-dialog-value {
      background: #20312b;
      border: 1px solid #2fa862;
      border-radius: 8px;
      color: #dff7ea;
      font-size: 24px;
      font-weight: 800;
      padding: 18px;
    }
    .empty {
      color: #8fa099;
      font-size: 14px;
    }
    button {
      border-radius: 8px;
      min-height: 34px;
      padding: 6px 10px;
      background: #202925;
      color: #edf5ef;
      border: 1px solid #314039;
    }
    button:hover {
      background: #28352f;
    }
    .tabs {
      border-bottom: 1px solid #24302c;
      padding-bottom: 8px;
    }
    .tabs button {
      min-height: 30px;
      padding: 5px 12px;
      background: transparent;
      border-color: transparent;
      color: #9dadA6;
      font-weight: 600;
    }
    .tabs button:hover {
      background: #1d2723;
      color: #eef3ef;
    }
    .tabs .tab-active {
      background: #20312b;
      border-color: #2fa862;
      color: #dff7ea;
    }
    .flat-icon {
      background: transparent;
      border-color: transparent;
      color: #aebdb6;
      padding: 6px;
    }
    .accent-icon, .primary {
      background: #1f7a49;
      border-color: #2fa862;
      color: #f4fff7;
    }
    .settings-title {
      font-size: 22px;
      font-weight: 700;
      color: #dff7ea;
    }
    switch:checked {
      background: #1f7a49;
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
    parser.parse_known_args()
    app = KoplyxApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        app.quit()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
