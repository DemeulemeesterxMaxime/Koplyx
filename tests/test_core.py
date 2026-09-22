#!/usr/bin/env python3
"""Tests de régression du stockage local et des aperçus Koplyx."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


TEST_HOME = tempfile.mkdtemp(prefix="koplyx-core-")
os.environ["XDG_CONFIG_HOME"] = f"{TEST_HOME}/config"
os.environ["XDG_DATA_HOME"] = f"{TEST_HOME}/data"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from koplyx.main import Config, CryptoBox, HistoryStore, file_title_from_uris, private_preview, text_content, text_excerpt, text_tooltip


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

    def test_pinned_position_controls_history_order(self) -> None:
        self.store.add("text", "text/plain", b"normal", "aperçu")
        self.store.add("image", "image/png", b"image", "aperçu")
        self.store.add("file", "text/uri-list", b"file:///tmp/a.txt", "aperçu")
        items = {self.store.payload(item.id)[2]: item.id for item in self.store.list()}

        self.store.toggle_pin(items[b"image"])
        self.store.toggle_pin(items[b"file:///tmp/a.txt"])
        self.store.set_pinned_position(items[b"image"], "bottom")
        self.store.set_pinned_position(items[b"file:///tmp/a.txt"], "pinned_only")

        history = self.store.recent()
        self.assertEqual([item.id for item in history], [items[b"normal"], items[b"image"]])
        pinned = self.store.recent(pinned_only=True)
        self.assertEqual({item.id for item in pinned}, {items[b"image"], items[b"file:///tmp/a.txt"]})
        self.assertEqual(next(item for item in pinned if item.id == items[b"file:///tmp/a.txt"]).pinned_position, "pinned_only")

    def test_existing_database_gets_default_pinned_position(self) -> None:
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
        self.assertEqual(migrated[0].pinned_position, "top")

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


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TEST_HOME, ignore_errors=True)
