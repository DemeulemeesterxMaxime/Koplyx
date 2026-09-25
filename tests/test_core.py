#!/usr/bin/env python3
"""Tests de régression du stockage local et des aperçus Koplyx."""

from __future__ import annotations

import os
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path


TEST_HOME = tempfile.mkdtemp(prefix="koplyx-core-")
os.environ["XDG_CONFIG_HOME"] = f"{TEST_HOME}/config"
os.environ["XDG_DATA_HOME"] = f"{TEST_HOME}/data"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.fernet import Fernet

from koplyx import main as koplyx_main
from koplyx.main import (
    Config,
    CryptoBox,
    HistoryStore,
    KoplyxApplication,
    file_title_from_uris,
    paste_clipboard_now,
    paste_tool_candidates,
    private_preview,
    running_x11,
    text_content,
    text_excerpt,
    text_tooltip,
    x11_active_window,
)


class HistoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config()
        self.store = HistoryStore(CryptoBox(), self.config)

    def tearDown(self) -> None:
        self.store.clear()
        self.store.conn.close()

    def test_text_payload_is_encrypted_and_preview_stays_private(self) -> None:
        secret = b"un texte prive qui ne doit pas etre stocke dans preview"
        self.assertTrue(self.store.add("text", "text/plain", secret, "aperçu"))

        item = self.store.list()[0]
        self.assertNotIn("texte prive", item.preview)
        self.assertEqual(item.preview, private_preview("text", "text/plain", secret))
        self.assertEqual(self.store.payload(item.id), ("text", "text/plain", secret))
        self.assertEqual(text_excerpt(secret), "un texte prive qui ne doit pas etre stocke dans preview")

    def test_duplicate_is_refreshed_without_creating_a_second_row(self) -> None:
        payload = b"copie unique"
        self.assertTrue(self.store.add("text", "text/plain", payload, "aperçu"))
        self.assertFalse(self.store.add("text", "text/plain", payload, "aperçu"))
        self.assertEqual(len(self.store.list()), 1)

    def test_pinned_items_are_exposed_in_their_dedicated_view(self) -> None:
        self.store.add("text", "text/plain", b"a garder", "aperçu")
        self.store.add("text", "text/plain", b"ordinaire", "aperçu")
        item = self.store.list()[0]
        self.store.toggle_pin(item.id)

        pinned = self.store.recent(pinned_only=True)
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0].id, item.id)

    def test_global_pinned_filter_controls_history_order(self) -> None:
        self.store.add("text", "text/plain", b"normal", "aperçu")
        self.store.add("image", "image/png", b"image", "aperçu")
        self.store.add("file", "text/uri-list", b"file:///tmp/a.txt", "aperçu")
        items = {self.store.payload(item.id)[2]: item.id for item in self.store.list()}
        self.store.conn.execute(
            "UPDATE items SET created_at = CASE id WHEN ? THEN 10 WHEN ? THEN 20 WHEN ? THEN 30 END",
            (items[b"normal"], items[b"image"], items[b"file:///tmp/a.txt"]),
        )
        self.store.conn.commit()

        self.store.toggle_pin(items[b"image"])
        self.store.toggle_pin(items[b"file:///tmp/a.txt"])

        history = self.store.recent(pinned_history_position="top")
        self.assertEqual(
            [item.id for item in history],
            [items[b"file:///tmp/a.txt"], items[b"image"], items[b"normal"]],
        )
        history = self.store.recent(pinned_history_position="bottom")
        self.assertEqual(
            [item.id for item in history],
            [items[b"normal"], items[b"file:///tmp/a.txt"], items[b"image"]],
        )
        history = self.store.recent(pinned_history_position="pinned_only")
        self.assertEqual([item.id for item in history], [items[b"normal"]])
        pinned = self.store.recent(pinned_only=True)
        self.assertEqual({item.id for item in pinned}, {items[b"image"], items[b"file:///tmp/a.txt"]})
        self.config.set("pinned_history_position", "bottom")
        reloaded = Config()
        self.assertEqual(reloaded.get("pinned_history_position"), "bottom")

    def test_existing_database_with_legacy_pin_column_remains_readable(self) -> None:
        self.store.conn.close()
        self.store.db_path.unlink()
        connection = sqlite3.connect(self.store.db_path)
        connection.execute(
            """
            CREATE TABLE items (
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
        data = b"ancienne epingle"
        connection.execute(
            "INSERT INTO items(kind, mime, hash, encrypted_blob, preview, bytes_size, created_at, pinned) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            ("text", "text/plain", "legacy", self.store.crypto.encrypt(data), "Texte, 15 caracteres", len(data), 1),
        )
        connection.commit()
        connection.close()

        self.store = HistoryStore(self.store.crypto, self.config)
        migrated = self.store.recent(pinned_only=True)
        self.assertEqual(len(migrated), 1)
        self.assertEqual(migrated[0].pinned, 1)

    def test_xdotool_active_window_is_not_used_on_wayland(self) -> None:
        result = SimpleNamespace(returncode=0, stdout="123456\n")
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
            "koplyx.main.command_exists", return_value=True
        ), patch("koplyx.main.subprocess.run", return_value=result) as run:
            self.assertIsNone(x11_active_window())
        run.assert_not_called()

    def test_xdotool_active_window_is_available_on_x11(self) -> None:
        result = SimpleNamespace(returncode=0, stdout="123456\n")
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "GDK_BACKEND": ""}), patch(
            "koplyx.main.command_exists", return_value=True
        ), patch("koplyx.main.subprocess.run", return_value=result) as run:
            self.assertEqual(x11_active_window(), "123456")
        run.assert_called_once_with(
            ["xdotool", "getactivewindow"], check=False, capture_output=True, text=True
        )

    def test_wayland_paste_tool_order_prefers_ydotool_before_xdotool(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
            "koplyx.main.command_exists", side_effect=lambda command: command in {"wtype", "xdotool", "ydotool"}
        ), patch("koplyx.main.ydotool_available", return_value=True):
            self.assertEqual(paste_tool_candidates("123"), ["wtype", "ydotool", "xdotool"])

    def test_wayland_skips_xdotool_without_xwayland_target(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
            "koplyx.main.command_exists", side_effect=lambda command: command in {"xdotool", "ydotool"}
        ), patch("koplyx.main.ydotool_available", return_value=True):
            self.assertEqual(paste_tool_candidates(), ["ydotool"])

    def test_direct_paste_continues_after_a_tool_failure(self) -> None:
        calls = []
        results = iter([
            SimpleNamespace(returncode=1), SimpleNamespace(returncode=1),
            SimpleNamespace(returncode=0, stdout="123\n"), SimpleNamespace(returncode=0),
        ])
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
            "koplyx.main.command_exists", return_value=True
        ), patch("koplyx.main.ydotool_available", return_value=True), patch(
            "koplyx.main.subprocess.run", side_effect=lambda command, **_kwargs: calls.append(command) or next(results)
        ):
            self.assertTrue(paste_clipboard_now("123"))
        self.assertEqual(calls[0][0], "wtype")
        self.assertEqual(calls[1][0], "ydotool")
        self.assertEqual(calls[2], ["xdotool", "getactivewindow"])
        self.assertEqual(calls[3], ["xdotool", "key", "--clearmodifiers", "ctrl+v"])

    def test_x11_paste_refuses_a_different_active_window(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}), patch(
            "koplyx.main.command_exists", return_value=True
        ), patch("koplyx.main.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="456\n")) as run:
            self.assertFalse(paste_clipboard_now("123", "xorg"))
        run.assert_called_once_with(["xdotool", "getactivewindow"], check=False, capture_output=True, text=True)

    def test_x11_paste_refuses_an_unknown_target(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}), patch(
            "koplyx.main.command_exists", return_value=True
        ), patch("koplyx.main.subprocess.run") as run:
            self.assertFalse(paste_clipboard_now(None, "xorg"))
        run.assert_not_called()

    def test_invalid_payload_does_not_break_history_rendering(self) -> None:
        self.store.add("text", "text/plain", b"ancienne cle", "aperçu")
        item = self.store.list()[0]
        self.store.conn.execute(
            "UPDATE items SET encrypted_blob = ? WHERE id = ?",
            (Fernet.generate_key(), item.id),
        )
        self.store.conn.commit()
        self.assertIsNone(self.store.payload(item.id))

    def test_pinned_view_keeps_images_and_files(self) -> None:
        self.store.add("image", "image/png", b"image", "aperçu")
        self.store.add("file", "text/uri-list", b"file:///tmp/a.txt", "aperçu")
        for item in self.store.list():
            self.store.toggle_pin(item.id)

        self.assertEqual({item.kind for item in self.store.recent(pinned_only=True)}, {"image", "file"})

    def test_long_text_has_single_line_content_and_safe_tooltip(self) -> None:
        data = ("première ligne\n" + "x" * 5000).encode()
        self.assertNotIn("\n", text_content(data))
        self.assertTrue(text_excerpt(data).endswith("…"))
        self.assertLessEqual(len(text_tooltip(data)), 4000)

    def test_file_title_is_human_readable(self) -> None:
        self.assertEqual(file_title_from_uris(["file:///tmp/rapport final.pdf"]), "rapport final.pdf")
        self.assertEqual(file_title_from_uris(["file:///tmp/a.txt", "file:///tmp/b.txt"]), "2 fichiers")

    def test_new_profile_requires_onboarding_and_legacy_profile_is_migrated(self) -> None:
        profile = Path(tempfile.mkdtemp(prefix="koplyx-config-migration-"))
        try:
            with patch("koplyx.main.CONFIG_DIR", profile):
                fresh = Config()
                self.assertFalse(fresh.get("onboarding_completed"))
                self.assertEqual(fresh.get("paste_backend"), "auto")

                legacy = {"shortcut": "<Ctrl><Alt>V", "max_items": 42}
                (profile / "config.json").write_text(json.dumps(legacy), encoding="utf-8")
                migrated = Config()
                self.assertTrue(migrated.get("onboarding_completed"))
                self.assertEqual(migrated.get("paste_backend"), "auto")
        finally:
            shutil.rmtree(profile, ignore_errors=True)

    def test_paste_backend_can_limit_direct_candidates(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
            "koplyx.main.command_exists", return_value=True
        ), patch("koplyx.main.ydotool_available", return_value=True):
            self.assertEqual(paste_tool_candidates("window", "wtype"), ["wtype"])
            self.assertEqual(paste_tool_candidates("window", "xwayland"), ["xdotool"])
            self.assertEqual(paste_tool_candidates("window", "clipboard_only"), [])

    def test_onboarding_does_not_offer_ydotool_without_packaged_helper(self) -> None:
        app = KoplyxApplication()
        try:
            with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
                "koplyx.main.command_available", side_effect=lambda command: command in {"wtype", "xdotool", "ydotool"}
            ), patch("koplyx.main.helper_path", return_value=None), patch(
                "koplyx.main.xorg_sessions", return_value=[]
            ):
                self.assertEqual(app.onboarding_test_plan(), ["wtype", "xwayland", "portal"])
        finally:
            app.store.conn.close()
            app.control_server.close()

    def test_xwayland_relaunch_has_a_dedicated_follow_up_plan(self) -> None:
        app = KoplyxApplication()
        try:
            app.xwayland_relaunch = True
            with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}), patch(
                "koplyx.main.command_available", side_effect=lambda command: command in {"wtype", "xdotool", "ydotool"}
            ), patch("koplyx.main.helper_path", return_value=Path("/usr/lib/koplyx/koplyx-system-setup")), patch(
                "koplyx.main.xorg_sessions", return_value=[]
            ):
                self.assertEqual(app.onboarding_test_plan(), ["xwayland", "ydotool", "portal"])
        finally:
            app.store.conn.close()
            app.control_server.close()

    def test_xwayland_relaunch_skips_ydotool_without_packaged_helper(self) -> None:
        app = KoplyxApplication()
        try:
            app.xwayland_relaunch = True
            with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}), patch(
                "koplyx.main.command_available", side_effect=lambda command: command in {"wtype", "xdotool", "ydotool"}
            ), patch("koplyx.main.helper_path", return_value=None), patch(
                "koplyx.main.xorg_sessions", return_value=[]
            ):
                self.assertEqual(app.onboarding_test_plan(), ["xwayland", "portal"])
        finally:
            app.store.conn.close()
            app.control_server.close()

    def test_gdk_x11_is_treated_as_an_x11_runtime(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": "x11", "DISPLAY": ":0"}):
            self.assertTrue(running_x11())

    def test_xwayland_launch_keeps_onboarding_pending(self) -> None:
        app = KoplyxApplication()
        try:
            app.config.set("onboarding_completed", False)
            with patch("koplyx.main.subprocess.Popen") as popen, patch.object(app, "quit") as quit_app:
                app.launch_xwayland_backend()
            environment = popen.call_args.kwargs["env"]
            self.assertEqual(environment["GDK_BACKEND"], "x11")
            self.assertEqual(environment["KOPLYX_XWAYLAND_TEST"], "1")
            self.assertFalse(app.config.get("onboarding_completed"))
            quit_app.assert_called_once()
        finally:
            app.store.conn.close()

    def test_onboarding_test_holds_application_until_result(self) -> None:
        app = KoplyxApplication()
        try:
            with patch.object(app, "hold") as hold, patch.object(app, "release") as release:
                app.hold_onboarding_test()
                app.hold_onboarding_test()
                self.assertTrue(app.onboarding_test_held)
                hold.assert_called_once_with()

                app.release_onboarding_test()
                app.release_onboarding_test()
                self.assertFalse(app.onboarding_test_held)
                release.assert_called_once_with()
        finally:
            app.store.conn.close()
            app.control_server.close()

    def test_clipboard_only_onboarding_still_attempts_ctrl_v(self) -> None:
        app = KoplyxApplication()
        try:
            app.previous_window_id = "target"
            with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
                "koplyx.main.paste_tool_candidates", return_value=["wtype"]
            ), patch("koplyx.main.paste_clipboard_now", return_value=True) as paste:
                class FakePortal:
                    ready = False

                    def close(self):
                        return None

                app.portal_keyboard = FakePortal()
                onboarding = type("Onboarding", (), {"test_result": lambda *_args: None})()
                with patch.object(app, "remember_active_window"), patch.object(koplyx_main.GLib, "timeout_add", return_value=1) as timeout_add, patch.object(
                    koplyx_main.GLib, "idle_add", side_effect=lambda callback, *args: callback(*args) or 1
                ):
                    app.inject_onboarding_test(onboarding, "clipboard_only")
                paste.assert_called_once_with("target", "auto")
                timeout_add.assert_called_once_with(700, app.restore_onboarding_clipboard)
        finally:
            app.store.conn.close()
            app.control_server.close()

    def test_clipboard_only_failure_keeps_test_text_available_for_manual_paste(self) -> None:
        app = KoplyxApplication()
        try:
            app.previous_window_id = "target"
            with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "GDK_BACKEND": ""}), patch(
                "koplyx.main.paste_tool_candidates", return_value=[]
            ), patch("koplyx.main.paste_clipboard_now", return_value=False), patch.object(
                app, "remember_active_window"
            ), patch.object(koplyx_main.GLib, "timeout_add") as timeout_add, patch.object(
                koplyx_main.GLib, "idle_add", return_value=1
            ):
                class FakePortal:
                    ready = False

                    def close(self):
                        return None

                app.portal_keyboard = FakePortal()
                app.inject_onboarding_test(type("Onboarding", (), {"test_result": lambda *_args: None})(), "clipboard_only")

            timeout_add.assert_not_called()
        finally:
            app.store.conn.close()
            app.control_server.close()


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TEST_HOME, ignore_errors=True)
