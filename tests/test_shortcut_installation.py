#!/usr/bin/env python3
"""Vérifie l'écriture automatique du raccourci GNOME."""

from __future__ import annotations

import sys
import os
import shlex
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from koplyx.main import APP_NAME, install_gnome_shortcut, shortcut_command


class ShortcutInstallationTests(unittest.TestCase):
    def test_source_shortcut_keeps_profile_even_with_installed_snap(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/profil avec espaces"}, clear=True), patch(
            "koplyx.main.shutil.which", return_value="/snap/bin/koplyx"
        ):
            command = shlex.split(shortcut_command())
        self.assertIn("XDG_CONFIG_HOME=/tmp/profil avec espaces", command)
        self.assertEqual(command[-2:], [str(PROJECT_ROOT / "bin/koplyx"), "--toggle"])

    def test_installs_and_updates_the_koplyx_binding(self) -> None:
        calls: list[list[str]] = []

        def record(command: list[str]) -> bool:
            calls.append(command)
            return True

        with (
            patch("koplyx.main.read_gsettings", return_value="['/existing/']"),
            patch("koplyx.main.run_gsettings", side_effect=record),
        ):
            self.assertTrue(install_gnome_shortcut("<Super>v", "/snap/bin/koplyx --toggle"))

        rendered_calls = "\n".join(" ".join(call) for call in calls)
        self.assertIn("'/existing/'", rendered_calls)
        self.assertIn("'/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/koplyx/'", rendered_calls)
        self.assertIn(f" name {APP_NAME}", rendered_calls)
        self.assertIn(" command /snap/bin/koplyx --toggle", rendered_calls)
        self.assertIn(" binding <Super>v", rendered_calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
