#!/usr/bin/env python3
# ui/conversion_model.py - Conversion Model Panel for IBus-PSKK

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk
import logging
logger = logging.getLogger(__name__)


class ConversionModelPanel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Conversion Model")

        self.set_default_size(800, 600)
        self.set_border_width(10)

        # Create UI
        notebook = Gtk.Notebook()
        notebook.append_page(self.create_test_tab(), Gtk.Label(label="Test"))
        notebook.append_page(self.create_train_tab(), Gtk.Label(label="Train"))
        self.add(notebook)

        # Connect Esc key to close window
        self.connect("key-press-event", self.on_key_press)

    def on_key_press(self, widget, event):
        """Handle key press events"""
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def create_test_tab(self):
        """Create Test tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)
        return box

    def create_train_tab(self):
        """Create Train tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)
        return box


def main():
    """Run conversion model panel standalone"""
    win = ConversionModelPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
