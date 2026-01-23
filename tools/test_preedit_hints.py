#!/usr/bin/env python3
"""
Test script to visualize IBus Preedit Hint styles.

This creates a simple GTK window with an IBus-enabled text entry
and simulates different preedit hint styles.

Usage:
    python tools/test_preedit_hints.py

Requirements:
    - IBus daemon running
    - GTK 3.0
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('IBus', '1.0')
from gi.repository import Gtk, IBus, Pango

# AttrPreedit hint values (IBus >= 1.5.33)
HINT_NAMES = {
    0: "DEFAULT (internal only)",
    1: "WHOLE",
    2: "SELECTION",
    3: "PREDICTION",
    4: "PREFIX",
    5: "SUFFIX",
    6: "ERROR_SPELLING",
    7: "ERROR_COMPOSE",
}

class PreeditHintTester(Gtk.Window):
    def __init__(self):
        super().__init__(title="IBus Preedit Hint Tester")
        self.set_default_size(600, 400)
        self.set_border_width(20)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # Header
        header = Gtk.Label()
        header.set_markup("<b>IBus Preedit Hint Styles</b>\n"
                         "<small>Colors are determined by your desktop theme/panel</small>")
        vbox.pack_start(header, False, False, 10)

        # Create sample displays for each hint type
        for hint_value, hint_name in HINT_NAMES.items():
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            # Label
            label = Gtk.Label(label=f"{hint_value}: {hint_name}")
            label.set_width_chars(25)
            label.set_xalign(0)
            hbox.pack_start(label, False, False, 0)

            # Sample text with Pango attributes (approximation)
            sample = Gtk.Label()
            sample.set_text("へんかんテスト")

            # Apply visual style based on hint type
            self._apply_hint_style(sample, hint_value)

            hbox.pack_start(sample, True, True, 0)
            vbox.pack_start(hbox, False, False, 5)

        # Separator
        vbox.pack_start(Gtk.Separator(), False, False, 10)

        # Explanation
        note = Gtk.Label()
        note.set_markup(
            "<small><b>Note:</b> This shows approximate GTK styling.\n"
            "Actual IBus preedit appearance depends on:\n"
            "• Your IBus panel implementation (ibus-ui-gtk3, kimpanel, etc.)\n"
            "• Desktop environment (GNOME, KDE, etc.)\n"
            "• GTK/Qt theme settings\n\n"
            "<b>To test real IBus rendering:</b>\n"
            "1. Use your IME in an application\n"
            "2. The engine sets AttrType.HINT with AttrPreedit.* values\n"
            "3. The panel interprets these semantically</small>"
        )
        note.set_line_wrap(True)
        vbox.pack_start(note, False, False, 10)

        # Live test entry
        vbox.pack_start(Gtk.Separator(), False, False, 10)
        entry_label = Gtk.Label()
        entry_label.set_markup("<b>Live test (type here with your IME):</b>")
        entry_label.set_xalign(0)
        vbox.pack_start(entry_label, False, False, 5)

        entry = Gtk.Entry()
        entry.set_placeholder_text("Type here to see actual preedit rendering...")
        vbox.pack_start(entry, False, False, 5)

    def _apply_hint_style(self, label, hint_value):
        """Apply approximate visual style based on hint type."""
        # These are approximations - actual IBus panel rendering may differ
        styles = {
            0: "",  # DEFAULT - no special style
            1: "background='#E8E8E8' underline='single'",  # WHOLE
            2: "background='#D1EAFF' underline='double'",  # SELECTION (highlighted)
            3: "foreground='#888888' style='italic'",      # PREDICTION (grayed)
            4: "foreground='#666666'",                     # PREFIX
            5: "foreground='#666666'",                     # SUFFIX
            6: "underline='error' foreground='#CC0000'",   # ERROR_SPELLING
            7: "underline='error' foreground='#CC0000'",   # ERROR_COMPOSE
        }

        style = styles.get(hint_value, "")
        if style:
            label.set_markup(f"<span {style}>へんかんテスト</span>")


def main():
    # Check IBus version for HINT support
    ibus_version = f"{IBus.MAJOR_VERSION}.{IBus.MINOR_VERSION}.{IBus.MICRO_VERSION}"
    print(f"IBus version: {ibus_version}")

    if (IBus.MAJOR_VERSION, IBus.MINOR_VERSION, IBus.MICRO_VERSION) < (1, 5, 33):
        print("Warning: AttrType.HINT requires IBus >= 1.5.33")
        print("Your version may not support semantic preedit hints.")

    win = PreeditHintTester()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
