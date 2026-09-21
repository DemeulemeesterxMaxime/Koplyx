#!/usr/bin/env python3
"""Vérifie l'activation des cartes de l'historique Koplyx."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


TEST_HOME = tempfile.mkdtemp(prefix="koplyx-history-ui-")
os.environ["XDG_CONFIG_HOME"] = f"{TEST_HOME}/config"
os.environ["XDG_DATA_HOME"] = f"{TEST_HOME}/data"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from koplyx.main import KoplyxApplication


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


if __name__ == "__main__":
    raise SystemExit(main())
