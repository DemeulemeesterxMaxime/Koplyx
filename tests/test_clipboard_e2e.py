#!/usr/bin/env python3
"""Parcours GTK réel isolé : python3 tests/test_clipboard_e2e.py.

Dépendances système : Xvfb, xauth, xfwm4, xdotool, dbus-run-session et
les dépendances GTK/Python de Koplyx. Aucun accès à la session graphique réelle.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKER = "Koplyx E2E : été, € et texte exact"
TARGET_TITLE = "Cible E2E Koplyx"


def run_isolated() -> int:
    with tempfile.TemporaryDirectory(prefix="koplyx-e2e-") as directory:
        root = Path(directory)
        env = os.environ.copy()
        for name, child in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
                            ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                            ("XDG_RUNTIME_DIR", "runtime")):
            path = root / child
            path.mkdir(mode=0o700)
            env[name] = str(path)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
                     "SESSION_MANAGER", "AT_SPI_BUS_ADDRESS"):
            env.pop(name, None)
        env.update(GSETTINGS_BACKEND="memory", GTK_A11Y="none", NO_AT_BRIDGE="1",
                   GDK_BACKEND="x11", XDG_SESSION_TYPE="x11")
        return subprocess.run([
            "dbus-run-session", "--config-file=" + str(PROJECT_ROOT / "tests/fixtures/session.conf"),
            "--", "xvfb-run", "-a", sys.executable, str(Path(__file__).resolve()),
            "--isolated", str(root),
        ], env=env, check=False).returncode


def stop(process):
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def graphical_main() -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    def pump(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while GLib.MainContext.default().iteration(False):
                pass
            time.sleep(0.01)

    def until(predicate, message, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if predicate():
                return
            pump(0.05)
        status = app.status_message if app is not None else "application non démarrée"
        target_text = state.read_text() if state.exists() else "cible non démarrée"
        raise AssertionError(f"{message} Statut Koplyx : {status!r}; cible : {target_text!r}")

    def xd(*args):
        return subprocess.check_output(["xdotool", *map(str, args)], text=True, timeout=5).strip()

    if sys.argv[1] == "--target":
        window = Gtk.Window(title=TARGET_TITLE)
        entry = Gtk.Entry()
        entry.set_text(MARKER)
        window.set_child(entry)
        window.set_default_size(650, 120)
        window.present()
        entry.grab_focus()

        def save():
            # Remplacement atomique : le lecteur ne voit jamais un fichier tronqué.
            state = Path(sys.argv[2])
            temporary = state.with_suffix(".tmp")
            temporary.write_text(entry.get_text(), encoding="utf-8")
            temporary.replace(state)
            return True

        GLib.timeout_add(50, save)
        GLib.MainLoop().run()
        return 0

    sys.path.insert(0, str(PROJECT_ROOT))
    from koplyx import main as m

    root = Path(sys.argv[2])
    state = root / "target.txt"
    wm = subprocess.Popen(["xfwm4", "--compositor=off"], stdout=subprocess.DEVNULL)
    target = None
    app = None
    try:
        pump(1)
        assert wm.poll() is None, "Le gestionnaire de fenêtres X11 doit démarrer."
        # Seul le trousseau est remplacé : injection et presse-papiers restent réels.
        with patch.object(m.CryptoBox, "load_secret_service_key", return_value=None):
            app = m.KoplyxApplication()
        assert app.register(None)
        app.hold()
        app.config.set("onboarding_completed", True)
        app.config.set("paste_backend", "xorg")
        app.ensure_window()
        target = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--target", str(state)])
        until(lambda: state.exists(), "La cible GTK doit démarrer.")
        wid = xd("search", "--name", f"^{TARGET_TITLE}$").splitlines()[-1]
        xd("windowactivate", "--sync", wid)
        assert xd("getactivewindow") == wid
        xd("key", "ctrl+a", "ctrl+c")
        until(lambda: len(app.store.recent()) == 1, "La copie clavier doit être capturée.")
        item = app.store.recent()[0]
        assert app.store.payload(item.id)[2].decode() == MARKER
        assert MARKER.encode() not in (m.DATA_DIR / "history.db").read_bytes()
        print("PASS copie réelle, capture et stockage chiffré", flush=True)

        xd("key", "BackSpace")
        until(lambda: state.read_text() == "", "Le champ cible doit être vide avant restauration.")
        app.window.present_focused()
        pump(0.3)
        assert app.previous_window_id == wid, "Koplyx doit mémoriser la fenêtre cible avant de s'afficher."
        row = app.window.listbox.get_first_child()
        app.window.listbox.emit("row-activated", row)
        until(lambda: state.read_text() == MARKER,
              "Le collage automatique n'a pas rempli le champ GTK avec le texte exact.")
        pump(1.2)
        assert len(app.store.recent()) == 1, "La restauration ne doit pas créer de doublon."
        print("PASS collage automatique dans un processus GTK distinct, sans doublon", flush=True)

        app.window.search.set_text("été")
        app.refresh()
        assert len(app.display_items()) == 1
        app.window.search.set_text("introuvable")
        app.refresh()
        assert not app.display_items()
        app.window.search.set_text("")
        app.refresh()
        app.window.listbox.get_first_child().on_pin(None)
        app.window.set_active_view("pinned")
        assert len(app.display_items()) == 1
        app.window.set_active_view("history")
        print("PASS recherche et épinglage", flush=True)

        clipboard = Gdk.Display.get_default().get_clipboard()
        pixbuf = m.GdkPixbuf.Pixbuf.new(m.GdkPixbuf.Colorspace.RGB, True, 8, 2, 2)
        pixbuf.fill(0x22AA44FF)
        clipboard.set_content(Gdk.ContentProvider.new_for_value(Gdk.Texture.new_for_pixbuf(pixbuf)))
        until(lambda: any(i.kind == "image" for i in app.store.recent()), "L'image doit être capturée.")
        path = root / "fichier-épreuve.txt"
        path.write_text("preuve E2E", encoding="utf-8")
        clipboard.set_content(Gdk.ContentProvider.new_for_value(
            Gdk.FileList.new_from_list([Gio.File.new_for_path(str(path))])))
        until(lambda: any(i.kind == "file" for i in app.store.recent()), "Le fichier doit être capturé.")
        # Attendre deux intervalles de polling pour détecter une capture texte tardive.
        pump(2)
        assert len(app.store.recent()) == 3, "Un fichier ne doit pas créer d'entrée parasite."
        assert [app.store.payload(i.id)[2].decode() for i in app.store.recent() if i.kind == "text"] == [MARKER]
        print("PASS capture image et fichier, sans entrée texte parasite", flush=True)

        for kind in ("image", "file"):
            restored = next(i for i in app.store.recent() if i.kind == kind)
            app.restore_item(restored.id)
            pump(1.2)
            values = []
            if kind == "image":
                clipboard.read_texture_async(None, lambda c, r: values.append(c.read_texture_finish(r)))
            else:
                # Extraire les URI pendant le callback évite de conserver un FileList invalide.
                clipboard.read_value_async(Gdk.FileList.__gtype__, GLib.PRIORITY_DEFAULT, None,
                    lambda c, r: values.append([f.get_uri() for f in c.read_value_finish(r).get_files()]))
            until(lambda: bool(values), f"Le format {kind} doit être relu après restauration.")
            if kind == "image":
                assert values[0].get_width() == 2 and values[0].get_height() == 2
            else:
                assert values[0] == [path.as_uri()]
        assert len(app.store.recent()) == 3
        print("PASS restauration des formats image et fichier", flush=True)

        before = [(i.id, i.kind, i.pinned) for i in app.store.recent()]
        with patch.object(m.CryptoBox, "load_secret_service_key", return_value=None):
            reloaded = m.HistoryStore(m.CryptoBox(), m.Config())
        try:
            assert [(i.id, i.kind, i.pinned) for i in reloaded.recent()] == before
            assert reloaded.payload(item.id)[2].decode() == MARKER
        finally:
            reloaded.conn.close()
        app.window.set_active_view("pinned")
        app.window.listbox.get_first_child().on_delete(None)
        assert len(app.store.recent()) == 2
        app.store.clear()
        assert not app.store.recent()
        print("PASS persistance, suppression unitaire et effacement", flush=True)
        return 0
    finally:
        stop(target)
        if app is not None:
            app.control_server.close()
            app.store.conn.close()
            app.quit()
        stop(wm)


if __name__ == "__main__":
    raise SystemExit(graphical_main() if len(sys.argv) > 1 else run_isolated())
