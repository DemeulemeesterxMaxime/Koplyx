#!/usr/bin/env python3
"""Tests isolés du helper système ydotool."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = PROJECT_ROOT / "packaging/scripts/koplyx-system-setup"
LOADER = SourceFileLoader("koplyx_system_setup", str(HELPER_PATH))
SPEC = importlib.util.spec_from_loader("koplyx_system_setup", LOADER)
assert SPEC
system_setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(system_setup)


class UinputTriggerTests(unittest.TestCase):
    def test_trigger_targets_the_uinput_sysfs_device(self) -> None:
        with patch.object(system_setup, "run", return_value=True) as run:
            self.assertTrue(system_setup.trigger_uinput_device())

        run.assert_called_once_with(
            ["udevadm", "trigger", "--action=change", "/sys/devices/virtual/misc/uinput"]
        )

    def test_trigger_failure_is_reported(self) -> None:
        with patch.object(system_setup, "run", return_value=False):
            self.assertFalse(system_setup.trigger_uinput_device())


if __name__ == "__main__":
    unittest.main(verbosity=2)
