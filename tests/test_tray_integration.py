#!/usr/bin/env python3
"""Vérifie l'enregistrement et les actions de l'indicateur système Koplyx."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib


WATCHER_BUS_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM_BUS_NAME_PREFIX = "org.kde.StatusNotifierItem-"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/StatusNotifierItem/menu"
TRAY_HOST = """
import os
from pathlib import Path
from gi.repository import GLib
from koplyx.main import TrayIndicator

class BackgroundApp:
    def __init__(self):
        self.action_path = Path(os.environ[\"KOPLYX_TRAY_ACTION_PATH\"])
    def _record(self, action):
        self.action_path.write_text(action, encoding=\"utf-8\")
    def toggle_window(self):
        self._record(\"toggle\")
        return GLib.SOURCE_REMOVE
    def show_from_tray(self):
        self._record(\"show\")
        return GLib.SOURCE_REMOVE
    def open_settings_from_tray(self):
        self._record(\"settings\")
        return GLib.SOURCE_REMOVE
    def quit_from_tray(self):
        self._record(\"quit\")
        return GLib.SOURCE_REMOVE

app = BackgroundApp()
tray = TrayIndicator(app)
if not tray.available:
    raise RuntimeError(tray.error)
GLib.MainLoop().run()
"""


class StatusNotifierWatcher(dbus.service.Object):
    def __init__(self, bus) -> None:
        self.bus_name = dbus.service.BusName(WATCHER_BUS_NAME, bus)
        super().__init__(self.bus_name, WATCHER_PATH)
        self.registered_item = ""

    @dbus.service.method(WATCHER_BUS_NAME, in_signature="s", out_signature="")
    def RegisterStatusNotifierItem(self, service: str) -> None:
        self.registered_item = str(service)


def main() -> int:
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    watcher = StatusNotifierWatcher(bus)
    assert bus.name_has_owner(WATCHER_BUS_NAME), "Le watcher simulé ne possède pas son nom D-Bus."

    root = Path(__file__).resolve().parents[1]
    test_home = Path(tempfile.mkdtemp(prefix="koplyx-tray-"))
    action_path = test_home / "action.txt"
    environment = os.environ.copy()
    environment["KOPLYX_TRAY_ACTION_PATH"] = str(action_path)
    process = subprocess.Popen(
        [sys.executable, "-c", TRAY_HOST],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 6
    failure = ""
    loop = GLib.MainLoop()

    def verify_registration() -> bool:
        nonlocal failure
        if process.poll() is not None:
            failure = f"L'hôte d'indicateur s'est arrêté prématurément avec le code {process.returncode}."
            loop.quit()
            return GLib.SOURCE_REMOVE
        if not watcher.registered_item:
            if time.monotonic() >= deadline:
                failure = "Koplyx ne s'est pas enregistré auprès de StatusNotifierWatcher."
                loop.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        try:
            assert watcher.registered_item.startswith(ITEM_BUS_NAME_PREFIX)
            item = bus.get_object(watcher.registered_item, ITEM_PATH)
            properties = dbus.Interface(item, "org.freedesktop.DBus.Properties")
            values = properties.GetAll("org.kde.StatusNotifierItem")
            assert str(values["Id"]) == "koplyx"
            assert str(values["Title"]) == "Koplyx"
            assert str(values["Status"]) == "Active"

            menu = bus.get_object(watcher.registered_item, MENU_PATH)
            menu_api = dbus.Interface(menu, "com.canonical.dbusmenu")
            _revision, layout = menu_api.GetLayout(0, -1, [])
            assert "Afficher Koplyx" in str(layout)
            assert "Paramètres" in str(layout)
            assert "Quitter Koplyx" in str(layout)
        except Exception as error:
            failure = f"Indicateur système invalide : {error}"
            loop.quit()
            return GLib.SOURCE_REMOVE

        actions = [
            ("toggle", lambda: dbus.Interface(item, "org.kde.StatusNotifierItem").Activate(0, 0)),
            ("settings", lambda: menu_api.Event(2, "clicked", dbus.String(""), 0)),
            ("quit", lambda: menu_api.Event(3, "clicked", dbus.String(""), 0)),
        ]
        action_index = 0

        def dispatch_next_action() -> bool:
            nonlocal action_index, failure
            if action_index >= len(actions):
                loop.quit()
                return GLib.SOURCE_REMOVE
            expected, dispatch = actions[action_index]
            action_path.unlink(missing_ok=True)
            try:
                dispatch()
            except Exception as error:
                failure = f"Impossible de déclencher l'action {expected} du menu : {error}"
                loop.quit()
                return GLib.SOURCE_REMOVE
            GLib.timeout_add(50, verify_action, expected)
            return GLib.SOURCE_REMOVE

        def verify_action(expected: str) -> bool:
            nonlocal action_index, failure
            if action_path.exists() and action_path.read_text(encoding="utf-8") == expected:
                action_index += 1
                GLib.idle_add(dispatch_next_action)
                return GLib.SOURCE_REMOVE
            if time.monotonic() >= deadline:
                failure = f"L'action {expected} de l'indicateur n'a pas été transmise à Koplyx."
                loop.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.idle_add(dispatch_next_action)
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(50, verify_registration)
    try:
        loop.run()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        stdout, stderr = process.communicate(timeout=1)
        shutil.rmtree(test_home, ignore_errors=True)

    if failure:
        raise AssertionError(f"{failure}\nstdout : {stdout}\nstderr : {stderr}")
    print("tray integration passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
