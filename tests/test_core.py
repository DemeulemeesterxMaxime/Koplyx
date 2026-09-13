#!/usr/bin/env python3
"""Tests de régression du stockage local et des aperçus Koplyx."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


TEST_HOME = tempfile.mkdtemp(prefix="koplyx-core-")
os.environ["XDG_CONFIG_HOME"] = f"{TEST_HOME}/config"
os.environ["XDG_DATA_HOME"] = f"{TEST_HOME}/data"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from koplyx.main import Config, CryptoBox, HistoryStore, file_title_from_uris, private_preview, text_excerpt


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

    def test_pinned_text_is_exposed_in_its_dedicated_view(self) -> None:
        self.store.add("text", "text/plain", b"a garder", "aperçu")
        self.store.add("text", "text/plain", b"ordinaire", "aperçu")
        item = self.store.list()[0]
        self.store.toggle_pin(item.id)

        pinned = self.store.recent(pinned_text_only=True)
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0].id, item.id)

    def test_file_title_is_human_readable(self) -> None:
        self.assertEqual(file_title_from_uris(["file:///tmp/rapport final.pdf"]), "rapport final.pdf")
        self.assertEqual(file_title_from_uris(["file:///tmp/a.txt", "file:///tmp/b.txt"]), "2 fichiers")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TEST_HOME, ignore_errors=True)
