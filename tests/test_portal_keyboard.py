#!/usr/bin/env python3
"""Contrat du portail : autorisation, réutilisation, refus et fermeture."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koplyx.portal_keyboard import PortalKeyboard, GLib, REQUEST, SESSION


class FakeBus:
    def __init__(self):
        self.signals = {}
        self.calls = []
        self.keys = []
        self.counter = 0

    def get_unique_name(self):
        return ":1.42"

    def signal_subscribe(self, _name, interface, _signal, path, _arg, _flags, callback):
        self.counter += 1
        self.signals[self.counter] = (interface, path, callback)
        return self.counter

    def signal_unsubscribe(self, ident):
        del self.signals[ident]

    def call(self, name, path, interface, method, parameters, *_args):
        self.calls.append((interface, method, parameters.unpack() if parameters else None))

    def call_sync(self, name, path, interface, method, parameters, *_args):
        self.keys.append(parameters.unpack()[2:])

    def respond(self, keyboard, code=0, **results):
        callback = next(v[2] for v in self.signals.values() if v[0] == REQUEST)
        values = {k: GLib.Variant("u" if isinstance(v, int) else "s", v) for k, v in results.items()}
        callback(self, None, keyboard._request_path, REQUEST, "Response", GLib.Variant("(ua{sv})", (code, values)))


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.responses = []
        self.tokens = []
        self.patch = patch("koplyx.portal_keyboard.Gio.bus_get_sync", return_value=self.bus)
        self.patch.start()
        self.keyboard = PortalKeyboard(lambda: "ancien-token", self.tokens.append)

    def tearDown(self):
        self.keyboard.close()
        self.patch.stop()

    def prepare(self):
        self.keyboard.prepare(lambda *args: self.responses.append(args))
        self.bus.respond(self.keyboard, session_handle="/session/test")
        self.assertEqual(self.bus.calls[-1][1], "SelectDevices")
        self.assertEqual(self.bus.calls[-1][2][1]["types"], 1)
        self.assertEqual(self.bus.calls[-1][2][1]["persist_mode"], 2)
        self.assertEqual(self.bus.calls[-1][2][1]["restore_token"], "ancien-token")
        self.bus.respond(self.keyboard)
        self.assertEqual(self.bus.calls[-1][1], "Start")

    def test_permission_before_keys_and_reuse(self):
        self.prepare()
        self.assertFalse(self.keyboard.paste())
        self.assertEqual(self.bus.keys, [])
        self.bus.respond(self.keyboard, devices=1, restore_token="nouveau-token")
        # La réponse d'autorisation ne colle jamais dans sa propre boîte de dialogue.
        self.assertEqual(self.bus.keys, [])
        self.assertTrue(self.responses[0][0])
        self.assertEqual(self.tokens, ["nouveau-token"])
        for _ in range(2):
            self.assertTrue(self.keyboard.paste())
        self.assertEqual(self.bus.keys, [(65507, 1), (118, 1), (118, 0), (65507, 0)] * 2)
        self.assertEqual(sum(method == "Start" for _, method, _ in self.bus.calls), 1)

    def test_denied_permission_closes_session_without_keys(self):
        self.prepare()
        self.bus.respond(self.keyboard, code=1)
        self.assertFalse(self.keyboard.ready)
        self.assertFalse(self.keyboard.pending)
        self.assertFalse(self.responses[0][0])
        self.assertEqual(self.bus.keys, [])
        self.assertEqual(self.bus.calls[-1][:2], (SESSION, "Close"))
        self.assertEqual(self.bus.signals, {})

    def test_revoked_session_requires_new_authorization(self):
        self.prepare()
        self.bus.respond(self.keyboard, devices=1)
        callback = next(v[2] for v in self.bus.signals.values() if v[0] == SESSION)
        callback()
        self.assertFalse(self.keyboard.paste())
        self.assertEqual(self.bus.keys, [])

    def test_timeout_cancels_request(self):
        self.keyboard.prepare(lambda *args: self.responses.append(args))
        # Expiration simulée sans laisser la vraie source GLib en attente.
        GLib.source_remove(self.keyboard._timeout_id)
        self.keyboard._expired()
        self.assertEqual(self.bus.calls[-1][:2], (REQUEST, "Close"))
        self.assertFalse(self.responses[0][0])
        self.assertEqual(self.bus.signals, {})

    def test_partial_key_failure_closes_session(self):
        self.prepare()
        self.bus.respond(self.keyboard, devices=1)
        with patch.object(self.bus, "call_sync", side_effect=GLib.Error("refus")):
            self.assertFalse(self.keyboard.paste())
        self.assertFalse(self.keyboard.ready)
        self.assertEqual(self.bus.calls[-1][:2], (SESSION, "Close"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
