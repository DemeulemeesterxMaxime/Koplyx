#!/usr/bin/env python3
"""Tests du canal local utilisé par le raccourci global Snap."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="koplyx-control-")
os.environ["XDG_RUNTIME_DIR"] = TEST_RUNTIME.name
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from gi.repository import GLib

from koplyx.main import CONTROL_SOCKET_PATH, LocalControlServer, send_control_command


class FakeApplication:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def toggle_window(self) -> bool:
        self.actions.append("toggle")
        return GLib.SOURCE_REMOVE

    def show_from_tray(self) -> bool:
        self.actions.append("show")
        return GLib.SOURCE_REMOVE


class LocalControlServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FakeApplication()
        self.server = LocalControlServer(self.app)
        self.assertTrue(self.server.start())

    def tearDown(self) -> None:
        self.server.close()

    def wait_for_action(self, expected: str) -> None:
        loop = GLib.MainLoop()

        def check() -> bool:
            if expected in self.app.actions:
                loop.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        def timeout() -> bool:
            loop.quit()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(20, check)
        GLib.timeout_add(1000, timeout)
        loop.run()
        self.assertIn(expected, self.app.actions)

    def test_toggle_is_delivered_to_the_existing_instance(self) -> None:
        self.assertTrue(send_control_command("toggle"))
        self.wait_for_action("toggle")

    def test_show_is_delivered_to_the_existing_instance(self) -> None:
        self.assertTrue(send_control_command("show"))
        self.wait_for_action("show")

    def test_socket_is_private(self) -> None:
        self.assertEqual(CONTROL_SOCKET_PATH.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        TEST_RUNTIME.cleanup()
