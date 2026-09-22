#!/usr/bin/env python3
"""Vérifie l'activation des cartes de l'historique Koplyx."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4


TEST_HOME = tempfile.mkdtemp(prefix="koplyx-history-ui-")
os.environ["XDG_CONFIG_HOME"] = f"{TEST_HOME}/config"
os.environ["XDG_DATA_HOME"] = f"{TEST_HOME}/data"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from koplyx import main as koplyx_main
from koplyx.main import HistoryRow, KoplyxApplication, OnboardingWindow, SettingsWindow


def main() -> int:
    app = KoplyxApplication()
    try:
        assert app.register(None)
        app.ensure_window()
        assert app.window is not None
        assert app.window.listbox.get_activate_on_single_click(), (
            "Un clic simple sur une carte doit déclencher row-activated et restaurer la copie."
        )
    finally:
        app.quit()
        app.store.conn.close()
        app.control_server.close()
        shutil.rmtree(TEST_HOME, ignore_errors=True)
    print("history interaction passed")
    return 0


def test_global_pinned_filter_and_single_line_title() -> None:
    app = new_test_app()
    try:
        app.ensure_window()
        assert app.window is not None
        assert type(app.window.pinned_filter).__name__ == "MenuButton"
        assert app.window.pinned_filter.get_label() == "Épingles en haut"
        assert app.window.pinned_filter.get_popover() is not None
        app.store.add("text", "text/plain", b"un texte suffisamment long pour etre tronque visuellement", "aperçu")
        item = app.store.list()[0]
        app.store.toggle_pin(item.id)
        row = HistoryRow(app, app.display_item(app.store.list(pinned_only=True)[0]))
        root = row.get_child()
        assert root is not None
        actions = root.get_last_child()
        assert actions is not None
        assert not any(type(child).__name__ == "MenuButton" for child in iter_children(actions))
        title = root.get_first_child().get_next_sibling().get_first_child()
        assert title.get_lines() == 1
        assert title.get_ellipsize().value_nick == "end"
        assert title.get_tooltip_text()
    finally:
        app.quit()
        app.store.conn.close()
        app.control_server.close()
        shutil.rmtree(TEST_HOME, ignore_errors=True)


def test_restore_pastes_to_previous_window_without_new_history_item() -> None:
    app = new_test_app()
    try:
        app.store.add("text", "text/plain", b"coller ici", "aperçu")
        item = app.store.list()[0]
        app.store.add("text", "text/plain", b"plus recent", "aperçu")
        app.store.conn.execute("UPDATE items SET created_at = created_at - 60 WHERE id = ?", (item.id,))
        app.store.conn.commit()
        before = [(entry.id, entry.created_at) for entry in app.store.recent()]
        callbacks = []

        class FakeWatcher:
            def __init__(self) -> None:
                self.text = None

            def set_text(self, text: str) -> None:
                self.text = text

        watcher = FakeWatcher()
        app.watcher = watcher
        app.portal_keyboard.ready = True
        app.previous_window_id = "target-window"
        app.sleep_to_tray = lambda: True
        with patch.object(koplyx_main.GLib, "timeout_add", side_effect=lambda _delay, callback: callbacks.append(callback) or 1):
            app.restore_item(item.id)

        assert watcher.text == "coller ici"
        assert [(entry.id, entry.created_at) for entry in app.store.recent()] == before
        assert len(callbacks) == 1

        with patch.object(koplyx_main.GLib, "timeout_add", side_effect=lambda _delay, callback: callbacks.append(callback) or 1), patch.object(
            koplyx_main, "activate_x11_window", return_value=True
        ), patch.object(koplyx_main, "paste_clipboard_now", return_value=True), patch.object(
            app.portal_keyboard, "paste", return_value=True
        ):
            callbacks.pop(0)()
            assert len(callbacks) == 1
            callbacks.pop(0)()

        app.portal_keyboard.ready = False
        callbacks.clear()
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}), patch.object(
            app.portal_keyboard, "prepare"
        ) as prepare, patch.object(koplyx_main, "paste_tool_candidates", return_value=[]), patch.object(
            app, "set_status"
        ) as set_status, patch.object(koplyx_main.GLib, "timeout_add") as schedule:
            app.restore_item(item.id)
            prepare.assert_not_called()
            set_status.assert_called_once()
            schedule.assert_not_called()
        assert watcher.text == "coller ici"
        assert [(entry.id, entry.created_at) for entry in app.store.recent()] == before
    finally:
        app.quit()
        app.store.conn.close()
        app.control_server.close()
        shutil.rmtree(TEST_HOME, ignore_errors=True)


def test_settings_does_not_expose_backend_selector_and_onboarding_is_guided() -> None:
    app = new_test_app()
    try:
        app.ensure_window()
        assert app.window is not None
        settings = SettingsWindow(app, app.window)
        assert not any(type(widget).__name__ == "ComboBoxText" for widget in walk_widgets(settings))
        onboarding = OnboardingWindow(app, app.window)
        onboarding.show_page(1)
        assert onboarding.primary.get_label() == "Tester"
        assert "solutions" in onboarding.status.get_text()
        onboarding.on_primary(None)
        assert onboarding.page == 2
        assert onboarding.primary.get_label() == "Tester cette solution"
        onboarding.close()
        settings.close()
    finally:
        app.quit()
        app.store.conn.close()
        app.control_server.close()
        shutil.rmtree(TEST_HOME, ignore_errors=True)


def iter_children(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()


def walk_widgets(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from walk_widgets(child)
        child = child.get_next_sibling()


def new_test_app() -> KoplyxApplication:
    app = KoplyxApplication()
    app.set_flags(koplyx_main.Gio.ApplicationFlags.NON_UNIQUE)
    app.set_application_id("dev.limax.koplyx.Test" + uuid4().hex)
    with patch.object(app, "sync_autostart"), patch.object(app, "sync_global_shortcut"), patch.object(app, "sync_tray"):
        assert app.register(None)
    return app


if __name__ == "__main__":
    result = main()
    test_global_pinned_filter_and_single_line_title()
    test_restore_pastes_to_previous_window_without_new_history_item()
    test_settings_does_not_expose_backend_selector_and_onboarding_is_guided()
    raise SystemExit(result)
