#!/usr/bin/env python3
"""Vérifie que le CSS Koplyx ne redimensionne pas les contrôles natifs GTK."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koplyx.main import Gtk, GLib, apply_css


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from descendants(child)
        child = child.get_next_sibling()


Gtk.init()
window = Gtk.Window(title="Contrôles natifs")
header = Gtk.HeaderBar()
window.set_titlebar(header)
window.set_default_size(640, 200)
Gtk.Settings.get_default().set_property("gtk-decoration-layout", ":minimize,maximize,close")
window.present()
loop = GLib.MainLoop()
measurements = []


def sizes():
    return [
        (tuple(button.get_css_classes()), button.measure(Gtk.Orientation.HORIZONTAL, -1)[:2],
         button.measure(Gtk.Orientation.VERTICAL, -1)[:2])
        for button in descendants(header) if isinstance(button, Gtk.Button)
    ]


def after():
    measurements.append(sizes())
    window.destroy()
    loop.quit()
    return GLib.SOURCE_REMOVE


def before():
    measurements.append(sizes())
    apply_css()
    GLib.timeout_add(100, after)
    return GLib.SOURCE_REMOVE


GLib.timeout_add(100, before)
loop.run()
assert len(measurements[0]) == 3, measurements
assert measurements[0] == measurements[1], measurements
print("Dimensions natives préservées pour réduire, agrandir et fermer.")
