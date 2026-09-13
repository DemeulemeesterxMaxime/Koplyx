#!/usr/bin/env python3
"""Contrôle manuel automatisable sur une vraie session de bureau D-Bus."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import dbus


ITEM_BUS_NAME = "dev.limax.koplyx.StatusNotifierItem"
ITEM_PATH = "/StatusNotifierItem"
WATCHER_BUS_NAME = "org.kde.StatusNotifierWatcher"


def main() -> int:
    bus = dbus.SessionBus()
    if not bus.name_has_owner(WATCHER_BUS_NAME):
        raise RuntimeError("Aucun StatusNotifierWatcher n'est disponible dans cette session.")

    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="koplyx-session-tray-") as test_home:
        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(Path(test_home) / "config")
        environment["XDG_DATA_HOME"] = str(Path(test_home) / "data")
        process = subprocess.Popen(
            [str(root / "bin" / "koplyx"), "--hidden"],
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Koplyx s'est arrêté avec le code {process.returncode}.")
                if bus.name_has_owner(ITEM_BUS_NAME):
                    item = bus.get_object(ITEM_BUS_NAME, ITEM_PATH)
                    properties = dbus.Interface(item, "org.freedesktop.DBus.Properties")
                    values = properties.GetAll("org.kde.StatusNotifierItem")
                    assert str(values["Id"]) == "koplyx"
                    assert str(values["Status"]) == "Active"
                    print("session tray verification passed")
                    return 0
                time.sleep(0.25)
            raise RuntimeError("Koplyx n'a pas exposé son indicateur système dans le délai attendu.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
