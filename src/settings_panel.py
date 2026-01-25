#!/usr/bin/env python3
# ui/settings_panel.py - GUI Settings Panel for IBus-PSKK

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import json
import os
import logging
logger = logging.getLogger(__name__)

import util


class SettingsPanel(Gtk.Window):
    """
    GUI Settings Panel for IBus-PSKK configuration.

    Features:
    - Enable/disable features (SandS, Murenso, Forced Preedit, Learning)
    - Configure mode switch keys
    - Set conversion key bindings
    - Manage dictionaries
    - Edit Murenso mappings
    - Import/export configuration
    """
    def __init__(self):
        super().__init__(title="IBus-PSKK Settings")

        self.set_default_size(800, 600)
        self.set_border_width(10)

        # Config file path
        #self.config_path = os.path.expanduser("~/.config/ibus-pskk/config.json")
        #self.config = self.load_config()
        self.config, warnings = util.get_config_data()
        # save (back) the config to file
        util.save_config_data(self.config)

        # Load kanchoku layout
        self.kanchoku_layout = util.get_kanchoku_layout(self.config)

        # Create UI
        self.create_ui()

        # Load current settings into UI
        self.load_settings_to_ui()

        # Show warnings if any
        if warnings:
            GLib.idle_add(self.show_config_warnings, warnings)

        # Connect Esc key to close window
        self.connect("key-press-event", self.on_key_press)

    def on_key_press(self, widget, event):
        """Handle key press events"""
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def show_config_warnings(self, warnings):
        """Display configuration warnings in a dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="Configuration Warnings"
        )
        dialog.format_secondary_text(warnings)
        dialog.run()
        dialog.destroy()
        return False  # Don't call again

    def on_hiragana_key_button_clicked(self, button):
        """Show key capture dialog for hiragana mode key"""
        result = self.show_key_capture_dialog("Hiragana Mode Key", self.hiragana_key_value)
        if result is not None:
            self.hiragana_key_value = result
            # result is now a string (e.g., "Alt_R", "Ctrl+K", or "" for removed)
            self.hiragana_key_button.set_label(result if result else "Not Set")

    def on_direct_key_button_clicked(self, button):
        """Show key capture dialog for direct mode key"""
        result = self.show_key_capture_dialog("Direct Mode Key", self.direct_key_value)
        if result is not None:
            self.direct_key_value = result
            # result is now a string (e.g., "Alt_L", "Ctrl+K", or "" for removed)
            self.direct_key_button.set_label(result if result else "Not Set")

    def on_to_hiragana_button_clicked(self, button):
        """Show key capture dialog for to_hiragana conversion key"""
        result = self.show_key_capture_dialog("To Hiragana Key", self.to_hiragana_value)
        if result is not None:
            self.to_hiragana_value = result
            self.to_hiragana_button.set_label(result if result else "Not Set")

    def on_to_katakana_button_clicked(self, button):
        """Show key capture dialog for to_katakana conversion key"""
        result = self.show_key_capture_dialog("To Katakana Key", self.to_katakana_value)
        if result is not None:
            self.to_katakana_value = result
            self.to_katakana_button.set_label(result if result else "Not Set")

    def on_to_ascii_button_clicked(self, button):
        """Show key capture dialog for to_ascii conversion key"""
        result = self.show_key_capture_dialog("To ASCII Key", self.to_ascii_value)
        if result is not None:
            self.to_ascii_value = result
            self.to_ascii_button.set_label(result if result else "Not Set")

    def on_to_zenkaku_button_clicked(self, button):
        """Show key capture dialog for to_zenkaku conversion key"""
        result = self.show_key_capture_dialog("To Zenkaku Key", self.to_zenkaku_value)
        if result is not None:
            self.to_zenkaku_value = result
            self.to_zenkaku_button.set_label(result if result else "Not Set")

    def show_key_capture_dialog(self, title, current_value):
        """Show dialog to capture key press

        Args:
            title: Dialog title
            current_value: Current key binding as a string (e.g., "Alt_R", "Ctrl+K")

        Returns:
            str: The captured key combination as a "+"-joined string,
                 empty string "" if removed, or None if cancelled
        """
        dialog = Gtk.Dialog(
            title=title,
            transient_for=self,
            modal=True
        )
        dialog.set_default_size(400, 150)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_border_width(10)

        # Instruction label
        instruction = Gtk.Label()
        # current_value is now a string (e.g., "Alt_R", "Ctrl+K")
        current_str = current_value if current_value else "Not Set"
        instruction.set_markup(
            f"<b>Press a key or key combination</b>\n\n"
            f"Current: <i>{current_str}</i>"
        )
        content.pack_start(instruction, False, False, 0)

        # Display for captured key
        self.captured_keys = []
        self.key_display = Gtk.Label(label="Waiting for key press...")
        content.pack_start(self.key_display, False, False, 0)

        # Connect key press handler
        dialog.connect("key-press-event", self.on_key_capture)
        dialog.connect("key-release-event", self.on_key_release)

        # Add buttons using the modern API (avoids get_action_area deprecation)
        dialog.add_button("Remove", Gtk.ResponseType.REJECT)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)

        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            # Join the captured keys list into a string (e.g., ["Ctrl", "K"] -> "Ctrl+K")
            return "+".join(self.captured_keys) if self.captured_keys else current_value
        elif response == Gtk.ResponseType.REJECT:
            return ""  # Remove - empty string indicates no key binding
        else:
            return None  # Cancel - None means no change

    def _check_ibus_hint_support(self):
        """Check if IBus version supports AttrPreedit HINT (>= 1.5.33)"""
        try:
            gi.require_version('IBus', '1.0')
            from gi.repository import IBus
            version = (IBus.MAJOR_VERSION, IBus.MINOR_VERSION, IBus.MICRO_VERSION)
            return version >= (1, 5, 33)
        except Exception:
            return False

    def on_use_ibus_hint_toggled(self, checkbox):
        """Handle toggle of 'Use IBus theme colors' checkbox"""
        use_hint = checkbox.get_active()

        # Enable/disable color entry fields based on checkbox state
        self.preedit_fg_entry.set_sensitive(not use_hint)
        self.preedit_bg_entry.set_sensitive(not use_hint)

        # Visual feedback - gray out the labels too
        if use_hint:
            self.preedit_fg_entry.set_opacity(0.5)
            self.preedit_bg_entry.set_opacity(0.5)
        else:
            self.preedit_fg_entry.set_opacity(1.0)
            self.preedit_bg_entry.set_opacity(1.0)

    def on_color_entry_changed(self, entry):
        """Validate color entry and update preview"""
        text = entry.get_text().strip().lower()
        # Remove any leading '0x' or '#' if present
        if text.startswith('0x'):
            text = text[2:]
        if text.startswith('#'):
            text = text[1:]

        # Validate: must be exactly 6 hex characters
        is_valid = len(text) == 6 and all(c in '0123456789abcdef' for c in text)

        # Use CSS styling instead of deprecated override_background_color
        style_context = entry.get_style_context()
        if is_valid or not text:
            # Valid color or empty - remove error class
            style_context.remove_class("error")
        else:
            # Invalid but not empty - add error class
            style_context.add_class("error")

        # Update the color preview
        if entry == self.preedit_fg_entry:
            self.preedit_fg_preview.queue_draw()
        elif entry == self.preedit_bg_entry:
            self.preedit_bg_preview.queue_draw()

    def on_color_preview_draw(self, widget, cr, color_type):
        """Draw color preview square"""
        if color_type == "fg":
            entry = self.preedit_fg_entry
        else:
            entry = self.preedit_bg_entry

        text = entry.get_text().strip().lower()
        # Remove any leading '0x' or '#' if present
        if text.startswith('0x'):
            text = text[2:]
        if text.startswith('#'):
            text = text[1:]

        # Parse color
        try:
            if len(text) == 6 and all(c in '0123456789abcdef' for c in text):
                r = int(text[0:2], 16) / 255.0
                g = int(text[2:4], 16) / 255.0
                b = int(text[4:6], 16) / 255.0
            else:
                # Invalid - show gray
                r, g, b = 0.5, 0.5, 0.5
        except ValueError:
            r, g, b = 0.5, 0.5, 0.5

        # Draw color square with border
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Fill with color
        cr.set_source_rgb(r, g, b)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Draw border
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, width - 1, height - 1)
        cr.stroke()

        return False

    def get_validated_color(self, entry, default="000000"):
        """Get validated hex color from entry, or return default"""
        text = entry.get_text().strip().lower()
        # Remove any leading '0x' or '#' if present
        if text.startswith('0x'):
            text = text[2:]
        if text.startswith('#'):
            text = text[1:]

        # Validate: must be exactly 6 hex characters
        if len(text) == 6 and all(c in '0123456789abcdef' for c in text):
            return text
        return default

    def on_key_capture(self, widget, event):
        """Capture key press"""
        # Get key name
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval)

        # Build list of pressed keys (modifiers + key)
        keys = []

        # Check for modifiers
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            keys.append("Control")
        if event.state & Gdk.ModifierType.SHIFT_MASK:
            keys.append("Shift")
        if event.state & Gdk.ModifierType.MOD1_MASK:  # Alt
            keys.append("Alt")
        if event.state & Gdk.ModifierType.SUPER_MASK:
            keys.append("Super")

        # Add the main key if it's not a modifier
        if keyname not in ["Control_L", "Control_R", "Shift_L", "Shift_R",
                           "Alt_L", "Alt_R", "Super_L", "Super_R"]:
            keys.append(keyname)

        # Validate: must have at least one non-modifier key
        # Modifier-only keys (from state mask) that are not allowed alone
        modifier_only_names = {"Control", "Shift", "Alt", "Super"}
        has_non_modifier = any(k not in modifier_only_names for k in keys)

        if keys and has_non_modifier:
            # Valid combination - save it
            self.captured_keys = keys
            self.key_display.set_label("+".join(keys))
        elif keys:
            # Only modifiers captured - show warning, don't save
            self.key_display.set_label("Modifier keys alone not allowed")

        return True

    def on_key_release(self, widget, event):
        """Handle key release"""
        return True

    def save_config(self):
        """Save configuration to file"""
        success = util.save_config_data(self.config)

        if success:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Settings Saved"
            )
            dialog.format_secondary_text("Configuration saved successfully!")
            dialog.run()
            dialog.destroy()
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Save Failed"
            )
            dialog.format_secondary_text("Error saving configuration. Check logs for details.")
            dialog.run()
            dialog.destroy()


    def create_ui(self):
        """Create the user interface"""
        # Apply CSS for entry validation styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            entry.error {
                background-color: #ffcccc;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)
        
        # Notebook for tabs
        notebook = Gtk.Notebook()
        main_box.pack_start(notebook, True, True, 0)
        
        # Create tabs
        notebook.append_page(self.create_general_tab(), Gtk.Label(label="General"))
        notebook.append_page(self.create_input_tab(), Gtk.Label(label="Input"))
        notebook.append_page(self.create_conversion_tab(), Gtk.Label(label="Conversion"))
        notebook.append_page(self.create_dictionaries_tab(), Gtk.Label(label="Dictionaries"))
        notebook.append_page(self.create_murenso_tab(), Gtk.Label(label="無連想配列"))
        
        # Button box
        button_box = Gtk.Box(spacing=6)
        main_box.pack_start(button_box, False, False, 0)
        
        # Save button
        save_button = Gtk.Button(label="Save Settings")
        save_button.connect("clicked", self.on_save_clicked)
        button_box.pack_end(save_button, False, False, 0)
        
        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda x: self.destroy())
        button_box.pack_end(close_button, False, False, 0)


    def create_general_tab(self):
        """Create General settings tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)
        
        # Layout selection
        layout_frame = Gtk.Frame(label="Layout")
        layout_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        layout_box.set_border_width(10)
        layout_frame.add(layout_box)
        
        self.layout_combo = Gtk.ComboBoxText()
        # Layout options will be populated dynamically in load_settings_to_ui()
        layout_box.pack_start(Gtk.Label(label="Input Layout:", xalign=0), False, False, 0)
        layout_box.pack_start(self.layout_combo, False, False, 0)
        
        box.pack_start(layout_frame, False, False, 0)
        
        # Mode switch keys
        mode_frame = Gtk.Frame(label="Mode Switch Keys")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mode_box.set_border_width(10)
        mode_frame.add(mode_box)

        # Create size group for labels to ensure equal button widths
        mode_label_size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        hiragana_box = Gtk.Box(spacing=6)
        hiragana_label = Gtk.Label(label="Hiragana Mode:")
        mode_label_size_group.add_widget(hiragana_label)
        hiragana_box.pack_start(hiragana_label, False, False, 0)
        self.hiragana_key_button = Gtk.Button(label="Not Set")
        self.hiragana_key_button.connect("clicked", self.on_hiragana_key_button_clicked)
        hiragana_box.pack_start(self.hiragana_key_button, True, True, 0)
        mode_box.pack_start(hiragana_box, False, False, 0)

        direct_box = Gtk.Box(spacing=6)
        direct_label = Gtk.Label(label="Direct Mode:")
        mode_label_size_group.add_widget(direct_label)
        direct_box.pack_start(direct_label, False, False, 0)
        self.direct_key_button = Gtk.Button(label="Not Set")
        self.direct_key_button.connect("clicked", self.on_direct_key_button_clicked)
        direct_box.pack_start(self.direct_key_button, True, True, 0)
        mode_box.pack_start(direct_box, False, False, 0)

        # Store key values
        self.hiragana_key_value = None
        self.direct_key_value = None
        
        box.pack_start(mode_frame, False, False, 0)
        
        # UI preferences
        ui_frame = Gtk.Frame(label="UI Preferences")
        ui_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ui_box.set_border_width(10)
        ui_frame.add(ui_box)

        self.show_annotations_check = Gtk.CheckButton(label="Show candidate annotations (frequency, source)")
        ui_box.pack_start(self.show_annotations_check, False, False, 0)

        page_size_box = Gtk.Box(spacing=6)
        page_size_box.pack_start(Gtk.Label(label="Candidates per page:"), False, False, 0)
        self.page_size_spin = Gtk.SpinButton()
        self.page_size_spin.set_range(5, 15)
        self.page_size_spin.set_increments(1, 1)
        page_size_box.pack_start(self.page_size_spin, False, False, 0)
        ui_box.pack_start(page_size_box, False, False, 0)

        # Preedit color settings
        color_label_size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        # Preedit foreground color
        fg_color_box = Gtk.Box(spacing=6)
        fg_color_label = Gtk.Label(label="Preedit foreground color:")
        fg_color_label.set_xalign(0)
        color_label_size_group.add_widget(fg_color_label)
        fg_color_box.pack_start(fg_color_label, False, False, 0)
        self.preedit_fg_entry = Gtk.Entry()
        self.preedit_fg_entry.set_placeholder_text("e.g., 000000")
        self.preedit_fg_entry.set_max_length(6)
        self.preedit_fg_entry.set_width_chars(10)
        self.preedit_fg_entry.connect("changed", self.on_color_entry_changed)
        fg_color_box.pack_start(self.preedit_fg_entry, False, False, 0)
        self.preedit_fg_preview = Gtk.DrawingArea()
        self.preedit_fg_preview.set_size_request(24, 24)
        self.preedit_fg_preview.connect("draw", self.on_color_preview_draw, "fg")
        fg_color_box.pack_start(self.preedit_fg_preview, False, False, 0)
        ui_box.pack_start(fg_color_box, False, False, 0)

        # Preedit background color
        bg_color_box = Gtk.Box(spacing=6)
        bg_color_label = Gtk.Label(label="Preedit background color:")
        bg_color_label.set_xalign(0)
        color_label_size_group.add_widget(bg_color_label)
        bg_color_box.pack_start(bg_color_label, False, False, 0)
        self.preedit_bg_entry = Gtk.Entry()
        self.preedit_bg_entry.set_placeholder_text("e.g., d1eaff")
        self.preedit_bg_entry.set_max_length(6)
        self.preedit_bg_entry.set_width_chars(10)
        self.preedit_bg_entry.connect("changed", self.on_color_entry_changed)
        bg_color_box.pack_start(self.preedit_bg_entry, False, False, 0)
        self.preedit_bg_preview = Gtk.DrawingArea()
        self.preedit_bg_preview.set_size_request(24, 24)
        self.preedit_bg_preview.connect("draw", self.on_color_preview_draw, "bg")
        bg_color_box.pack_start(self.preedit_bg_preview, False, False, 0)
        ui_box.pack_start(bg_color_box, False, False, 0)

        # Color format hint
        color_hint = Gtk.Label()
        color_hint.set_markup("<small>Format: 6-digit hex (e.g., ff0000 for red, 00ff00 for green)</small>")
        color_hint.set_xalign(0)
        ui_box.pack_start(color_hint, False, False, 0)

        # Use IBus HINT colors checkbox
        self.use_ibus_hint_check = Gtk.CheckButton(
            label="Use IBus theme colors (let desktop theme decide preedit appearance)"
        )
        self.use_ibus_hint_check.connect("toggled", self.on_use_ibus_hint_toggled)

        # Check IBus version for HINT support (requires >= 1.5.33)
        ibus_supports_hint = self._check_ibus_hint_support()
        if ibus_supports_hint:
            self.use_ibus_hint_check.set_tooltip_text(
                "When enabled, preedit colors are determined by your desktop theme/IBus panel "
                "instead of the custom colors above."
            )
        else:
            self.use_ibus_hint_check.set_sensitive(False)
            self.use_ibus_hint_check.set_tooltip_text(
                "Requires IBus 1.5.33 or newer. Your IBus version does not support this feature."
            )

        ui_box.pack_start(self.use_ibus_hint_check, False, False, 0)

        box.pack_start(ui_frame, False, False, 0)
        
        return box


    def create_input_tab(self):
        """Create Input settings tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)
        
        # SandS settings
        sands_frame = Gtk.Frame(label="SandS (Space and Shift)")
        sands_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sands_box.set_border_width(10)
        sands_frame.add(sands_box)
        
        self.sands_enabled_check = Gtk.CheckButton(label="Enable SandS (Space acts as Shift when held)")
        sands_box.pack_start(self.sands_enabled_check, False, False, 0)
        
        box.pack_start(sands_frame, False, False, 0)
        
        # Forced Preedit settings
        fp_frame = Gtk.Frame(label="Forced Preedit Mode")
        fp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        fp_box.set_border_width(10)
        fp_frame.add(fp_box)
        
        self.forced_preedit_enabled_check = Gtk.CheckButton(
            label="Enable Forced Preedit (Mixed Kanji-Kana input for disambiguation)")
        fp_box.pack_start(self.forced_preedit_enabled_check, False, False, 0)
        
        trigger_box = Gtk.Box(spacing=6)
        trigger_box.pack_start(Gtk.Label(label="Trigger Key:"), False, False, 0)
        self.forced_preedit_trigger_entry = Gtk.Entry()
        trigger_box.pack_start(self.forced_preedit_trigger_entry, True, True, 0)
        fp_box.pack_start(trigger_box, False, False, 0)
        
        box.pack_start(fp_frame, False, False, 0)
        
        # Murenso settings
        murenso_frame = Gtk.Frame(label="無連想配列 (Direct Kanji Input)")
        murenso_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        murenso_box.set_border_width(10)
        murenso_frame.add(murenso_box)
        
        self.murenso_enabled_check = Gtk.CheckButton(
            label="Enable 無連想配列 (Direct Kanji input via 2-key chords)")
        murenso_box.pack_start(self.murenso_enabled_check, False, False, 0)
        
        box.pack_start(murenso_frame, False, False, 0)
        
        return box


    def create_conversion_tab(self):
        """Create Conversion settings tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)
        
        # Learning settings
        learning_frame = Gtk.Frame(label="Learning System")
        learning_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        learning_box.set_border_width(10)
        learning_frame.add(learning_box)
        
        self.learning_enabled_check = Gtk.CheckButton(
            label="Enable learning (Remember frequently used candidates)")
        learning_box.pack_start(self.learning_enabled_check, False, False, 0)
        
        box.pack_start(learning_frame, False, False, 0)
        
        # Conversion keys
        keys_frame = Gtk.Frame(label="Conversion Key Bindings")
        keys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        keys_box.set_border_width(10)
        keys_frame.add(keys_box)

        # Create size group for labels to ensure equal button widths
        conv_label_size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        # Hiragana
        hira_box = Gtk.Box(spacing=6)
        hira_label = Gtk.Label(label="To Hiragana:")
        conv_label_size_group.add_widget(hira_label)
        hira_box.pack_start(hira_label, False, False, 0)
        self.to_hiragana_button = Gtk.Button(label="Not Set")
        self.to_hiragana_button.connect("clicked", self.on_to_hiragana_button_clicked)
        hira_box.pack_start(self.to_hiragana_button, True, True, 0)
        keys_box.pack_start(hira_box, False, False, 0)

        # Katakana
        kata_box = Gtk.Box(spacing=6)
        kata_label = Gtk.Label(label="To Katakana:")
        conv_label_size_group.add_widget(kata_label)
        kata_box.pack_start(kata_label, False, False, 0)
        self.to_katakana_button = Gtk.Button(label="Not Set")
        self.to_katakana_button.connect("clicked", self.on_to_katakana_button_clicked)
        kata_box.pack_start(self.to_katakana_button, True, True, 0)
        keys_box.pack_start(kata_box, False, False, 0)

        # ASCII
        ascii_box = Gtk.Box(spacing=6)
        ascii_label = Gtk.Label(label="To ASCII:")
        conv_label_size_group.add_widget(ascii_label)
        ascii_box.pack_start(ascii_label, False, False, 0)
        self.to_ascii_button = Gtk.Button(label="Not Set")
        self.to_ascii_button.connect("clicked", self.on_to_ascii_button_clicked)
        ascii_box.pack_start(self.to_ascii_button, True, True, 0)
        keys_box.pack_start(ascii_box, False, False, 0)

        # Zenkaku
        zen_box = Gtk.Box(spacing=6)
        zen_label = Gtk.Label(label="To Zenkaku:")
        conv_label_size_group.add_widget(zen_label)
        zen_box.pack_start(zen_label, False, False, 0)
        self.to_zenkaku_button = Gtk.Button(label="Not Set")
        self.to_zenkaku_button.connect("clicked", self.on_to_zenkaku_button_clicked)
        zen_box.pack_start(self.to_zenkaku_button, True, True, 0)
        keys_box.pack_start(zen_box, False, False, 0)

        # Initialize conversion key instance variables
        self.to_hiragana_value = None
        self.to_katakana_value = None
        self.to_ascii_value = None
        self.to_zenkaku_value = None

        box.pack_start(keys_frame, False, False, 0)

        return box


    def create_dictionaries_tab(self):
        """Create Dictionaries tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # System dictionaries
        sys_frame = Gtk.Frame(label="System Dictionaries")
        sys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sys_box.set_border_width(10)
        sys_frame.add(sys_box)

        # Info label
        sys_info_label = Gtk.Label()
        sys_info_label.set_markup(
            "<small>Dictionary files found in /opt/ibus-pskk/dictionaries/\n"
            "Check the box to enable a dictionary for conversion.</small>"
        )
        sys_info_label.set_xalign(0)
        sys_box.pack_start(sys_info_label, False, False, 0)

        # System dictionary list with checkboxes
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(150)
        # Store: (enabled: bool, filename: str, full_path: str)
        self.sys_dict_store = Gtk.ListStore(bool, str, str)
        self.sys_dict_view = Gtk.TreeView(model=self.sys_dict_store)

        # Checkbox column
        toggle_renderer = Gtk.CellRendererToggle()
        toggle_renderer.connect("toggled", self.on_sys_dict_toggled)
        toggle_column = Gtk.TreeViewColumn("Enable", toggle_renderer, active=0)
        toggle_column.set_min_width(60)
        self.sys_dict_view.append_column(toggle_column)

        # Filename column
        text_renderer = Gtk.CellRendererText()
        text_column = Gtk.TreeViewColumn("Dictionary File", text_renderer, text=1)
        self.sys_dict_view.append_column(text_column)

        scroll.add(self.sys_dict_view)
        sys_box.pack_start(scroll, True, True, 0)

        # System dictionary buttons
        sys_btn_box = Gtk.Box(spacing=6)
        refresh_btn = Gtk.Button(label="Refresh List")
        refresh_btn.connect("clicked", self.on_refresh_system_dicts)
        sys_btn_box.pack_start(refresh_btn, False, False, 0)

        convert_btn = Gtk.Button(label="Convert under $HOME")
        convert_btn.connect("clicked", self.on_convert_system_dicts)
        sys_btn_box.pack_start(convert_btn, False, False, 0)

        sys_box.pack_start(sys_btn_box, False, False, 0)

        box.pack_start(sys_frame, True, True, 0)

        # User dictionaries
        user_frame = Gtk.Frame(label="User Dictionaries")
        user_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        user_box.set_border_width(10)
        user_frame.add(user_box)

        # Info label
        user_info_label = Gtk.Label()
        user_info_label.set_markup(
            "<small>Place SKK-format .txt files in <b>~/.config/ibus-pskk/dictionaries/</b>\n"
            "Then click 'Convert' to generate user_dictionary.json</small>"
        )
        user_info_label.set_xalign(0)
        user_box.pack_start(user_info_label, False, False, 0)

        # User dictionary list (shows .txt files in dictionaries/)
        user_scroll = Gtk.ScrolledWindow()
        user_scroll.set_min_content_height(100)
        self.user_dict_store = Gtk.ListStore(str)
        self.user_dict_view = Gtk.TreeView(model=self.user_dict_store)
        user_renderer = Gtk.CellRendererText()
        user_column = Gtk.TreeViewColumn("SKK Source Files (.txt)", user_renderer, text=0)
        self.user_dict_view.append_column(user_column)
        user_scroll.add(self.user_dict_view)
        user_box.pack_start(user_scroll, True, True, 0)

        # User dict buttons
        user_btn_box = Gtk.Box(spacing=6)

        refresh_user_btn = Gtk.Button(label="Refresh List")
        refresh_user_btn.connect("clicked", self.on_refresh_user_dicts)
        user_btn_box.pack_start(refresh_user_btn, False, False, 0)

        convert_user_btn = Gtk.Button(label="Convert")
        convert_user_btn.connect("clicked", self.on_convert_user_dicts)
        user_btn_box.pack_start(convert_user_btn, False, False, 0)

        user_box.pack_start(user_btn_box, False, False, 0)

        box.pack_start(user_frame, True, True, 0)

        return box


    def create_murenso_tab(self):
        """Create Murenso mappings tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # Kanchoku layout selection
        layout_frame = Gtk.Frame(label="Kanchoku Layout")
        layout_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        layout_box.set_border_width(10)
        layout_frame.add(layout_box)

        layout_label = Gtk.Label(label="Select Layout:")
        layout_box.pack_start(layout_label, False, False, 0)

        self.kanchoku_layout_combo = Gtk.ComboBoxText()
        self.kanchoku_layout_combo.connect("changed", self.on_kanchoku_layout_changed)
        layout_box.pack_start(self.kanchoku_layout_combo, True, True, 0)

        box.pack_start(layout_frame, False, False, 0)

        # Search box with 3 separate fields
        search_box = Gtk.Box(spacing=6)
        search_box.set_border_width(5)

        # First key search
        first_key_label = Gtk.Label(label="1st Key:")
        search_box.pack_start(first_key_label, False, False, 0)
        self.murenso_search_first = Gtk.Entry()
        self.murenso_search_first.set_placeholder_text("Filter by 1st key...")
        self.murenso_search_first.set_width_chars(15)
        self.murenso_search_first.connect("changed", self.on_murenso_search_changed)
        search_box.pack_start(self.murenso_search_first, True, True, 0)

        # Second key search
        second_key_label = Gtk.Label(label="2nd Key:")
        search_box.pack_start(second_key_label, False, False, 0)
        self.murenso_search_second = Gtk.Entry()
        self.murenso_search_second.set_placeholder_text("Filter by 2nd key...")
        self.murenso_search_second.set_width_chars(15)
        self.murenso_search_second.connect("changed", self.on_murenso_search_changed)
        search_box.pack_start(self.murenso_search_second, True, True, 0)

        # Kanji search
        kanji_label = Gtk.Label(label="Kanji:")
        search_box.pack_start(kanji_label, False, False, 0)
        self.murenso_search_kanji = Gtk.Entry()
        self.murenso_search_kanji.set_placeholder_text("Filter by kanji...")
        self.murenso_search_kanji.set_width_chars(15)
        self.murenso_search_kanji.connect("changed", self.on_murenso_search_changed)
        search_box.pack_start(self.murenso_search_kanji, True, True, 0)

        box.pack_start(search_box, False, False, 0)

        # Murenso mapping table
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(400)

        # Store: first_key, second_key, kanji
        self.murenso_store = Gtk.ListStore(str, str, str)

        # Create filter model
        self.murenso_filter = self.murenso_store.filter_new()
        self.murenso_filter.set_visible_func(self.murenso_filter_func)

        self.murenso_view = Gtk.TreeView(model=self.murenso_filter)

        # Enable grid lines for better visibility
        self.murenso_view.set_grid_lines(Gtk.TreeViewGridLines.BOTH)

        # Apply CSS for visible cell borders and gray headers
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            treeview {
                -GtkTreeView-grid-line-width: 1;
                -GtkTreeView-grid-line-pattern: '';
            }
            treeview.view {
                border: 1px solid #ccc;
            }
            treeview.view:selected {
                background-color: #4a90d9;
            }
            treeview header button {
                background-color: #d0d0d0;
                background-image: none;
                border: 1px solid #999;
                color: #000000;
                font-size: 14pt;
                font-weight: bold;
                padding: 2px 10px;
                min-height: 40px;
            }
            treeview header button:hover {
                background-color: #c0c0c0;
            }
        """)
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # First key column
        first_renderer = Gtk.CellRendererText()
        first_renderer.set_property("editable", True)
        first_renderer.set_property("cell-background", "#ffffff")  # White background
        first_renderer.set_property("cell-background-set", True)
        first_renderer.set_property("ypad", 1)  # Vertical padding
        first_renderer.set_property("xpad", 10)  # Horizontal padding
        first_renderer.set_property("height", 40)  # Minimum cell height
        first_renderer.set_property("size-points", 14.0)  # Font size in points
        first_renderer.set_property("xalign", 0.5)  # Center align horizontally
        first_renderer.connect("edited", self.on_murenso_first_edited)
        first_column = Gtk.TreeViewColumn("1st Key", first_renderer, text=0)
        first_column.set_alignment(0.5)  # Center align column header
        self.murenso_view.append_column(first_column)

        # Second key column
        second_renderer = Gtk.CellRendererText()
        second_renderer.set_property("editable", True)
        second_renderer.set_property("cell-background", "#ffffff")  # White background
        second_renderer.set_property("cell-background-set", True)
        second_renderer.set_property("ypad", 1)  # Vertical padding
        second_renderer.set_property("xpad", 10)  # Horizontal padding
        second_renderer.set_property("height", 40)  # Minimum cell height
        second_renderer.set_property("size-points", 14.0)  # Font size in points
        second_renderer.set_property("xalign", 0.5)  # Center align horizontally
        second_renderer.connect("edited", self.on_murenso_second_edited)
        second_column = Gtk.TreeViewColumn("2nd Key", second_renderer, text=1)
        second_column.set_alignment(0.5)  # Center align column header
        self.murenso_view.append_column(second_column)

        # Kanji column
        kanji_renderer = Gtk.CellRendererText()
        kanji_renderer.set_property("editable", True)
        kanji_renderer.set_property("cell-background", "#ffffff")  # White background
        kanji_renderer.set_property("cell-background-set", True)
        kanji_renderer.set_property("ypad", 1)  # Vertical padding
        kanji_renderer.set_property("xpad", 10)  # Horizontal padding
        kanji_renderer.set_property("height", 40)  # Minimum cell height
        kanji_renderer.set_property("size-points", 16.0)  # Larger font for Kanji
        kanji_renderer.set_property("xalign", 0.5)  # Center align horizontally
        kanji_renderer.connect("edited", self.on_murenso_kanji_edited)
        kanji_column = Gtk.TreeViewColumn("Kanji", kanji_renderer, text=2)
        kanji_column.set_alignment(0.5)  # Center align column header
        self.murenso_view.append_column(kanji_column)

        scroll.add(self.murenso_view)
        box.pack_start(scroll, True, True, 0)

        # Button box
        btn_box = Gtk.Box(spacing=6)

        add_btn = Gtk.Button(label="Add Mapping")
        add_btn.connect("clicked", self.on_add_murenso)
        btn_box.pack_start(add_btn, False, False, 0)

        remove_btn = Gtk.Button(label="Remove Selected")
        remove_btn.connect("clicked", self.on_remove_murenso)
        btn_box.pack_start(remove_btn, False, False, 0)

        load_btn = Gtk.Button(label="Load from File")
        load_btn.connect("clicked", self.on_load_murenso)
        btn_box.pack_start(load_btn, False, False, 0)

        save_btn = Gtk.Button(label="Save to File")
        save_btn.connect("clicked", self.on_save_murenso)
        btn_box.pack_start(save_btn, False, False, 0)

        box.pack_start(btn_box, False, False, 0)

        return box


    def load_settings_to_ui(self):
        """Load current settings into UI widgets"""
        # Load default config to use as fallback for default values
        default_config = util.get_default_config_data() or {}

        # General tab - populate layout combo with available layout files
        self.layout_combo.remove_all()

        # Search for layout JSON files in both user and system directories
        user_layouts_dir = os.path.join(util.get_user_configdir(), 'layouts')
        system_layouts_dir = os.path.join(util.get_datadir(), 'layouts')

        # Track files and their locations
        user_files = set()
        system_files = set()

        # Scan user layouts directory
        if os.path.exists(user_layouts_dir):
            for filename in os.listdir(user_layouts_dir):
                if filename.endswith('.json'):
                    user_files.add(filename)

        # Scan system layouts directory
        if os.path.exists(system_layouts_dir):
            for filename in os.listdir(system_layouts_dir):
                if filename.endswith('.json'):
                    system_files.add(filename)

        # Get all unique filenames
        all_files = user_files | system_files

        # Add found layouts to combo box with location info
        for filename in sorted(all_files):
            in_user = filename in user_files
            in_system = filename in system_files

            # Build display label with location info
            if in_user and in_system:
                # File exists in both locations - user version takes precedence
                display_label = f"{filename} (User: $HOME/.config/, System: /opt/)"
            elif in_user:
                display_label = f"{filename} (User: $HOME/.config/)"
            else:
                display_label = f"{filename} (System: /opt/)"

            # Use filename as ID for selection
            self.layout_combo.append(filename, display_label)

        # Set the current selection
        default_layout = default_config.get("layout", "shingeta.json")
        layout = self.config.get("layout", default_layout)
        if isinstance(layout, dict):
            layout_type = layout.get("type", default_layout)
        else:
            layout_type = layout  # layout is a string
        self.layout_combo.set_active_id(layout_type)

        # Load enable_hiragana_key from config
        default_enable_key = default_config.get("enable_hiragana_key", "Alt_R")
        self.hiragana_key_value = self.config.get("enable_hiragana_key", default_enable_key)
        self.hiragana_key_button.set_label(self.hiragana_key_value or "Not Set")

        # Load disable_hiragana_key from config
        default_disable_key = default_config.get("disable_hiragana_key", "Alt_L")
        self.direct_key_value = self.config.get("disable_hiragana_key", default_disable_key)
        self.direct_key_button.set_label(self.direct_key_value or "Not Set")

        ui = self.config.get("ui") or {}
        if not isinstance(ui, dict):
            ui = {}
        self.show_annotations_check.set_active(ui.get("show_annotations", True))
        self.page_size_spin.set_value(ui.get("candidate_window_size", 9))

        # Load preedit colors
        default_fg = default_config.get("preedit_foreground_color", "0x000000")
        default_bg = default_config.get("preedit_background_color", "0xd1eaff")
        fg_color = self.config.get("preedit_foreground_color", default_fg)
        bg_color = self.config.get("preedit_background_color", default_bg)

        # Strip '0x' prefix if present for display
        if isinstance(fg_color, str) and fg_color.startswith("0x"):
            fg_color = fg_color[2:]
        if isinstance(bg_color, str) and bg_color.startswith("0x"):
            bg_color = bg_color[2:]

        self.preedit_fg_entry.set_text(fg_color)
        self.preedit_bg_entry.set_text(bg_color)

        # Load use_ibus_hint_colors setting
        use_hint = self.config.get("use_ibus_hint_colors", False)
        if self._check_ibus_hint_support():
            self.use_ibus_hint_check.set_active(use_hint)
            # Trigger the toggle handler to update field states
            self.on_use_ibus_hint_toggled(self.use_ibus_hint_check)

        # Input tab
        self.sands_enabled_check.set_active(self.config.get("enable_sands", True))

        fp = self.config.get("forced_preedit_trigger_entry") or {}
        if not isinstance(fp, dict):
            fp = {}
        self.forced_preedit_enabled_check.set_active(fp.get("enabled", True))
        self.forced_preedit_trigger_entry.set_text(fp.get("trigger_key", "f"))

        self.murenso_enabled_check.set_active(self.config.get("enable_murenso", True))

        # Conversion tab
        self.learning_enabled_check.set_active(self.config.get("enable_learning", True))

        conv_keys = self.config.get("conversion_keys") or {}
        if not isinstance(conv_keys, dict):
            conv_keys = {}
        default_conv_keys = default_config.get("conversion_keys") or {}
        if not isinstance(default_conv_keys, dict):
            default_conv_keys = {}

        self.to_katakana_value = conv_keys.get("to_katakana", default_conv_keys.get("to_katakana", "Ctrl+K"))
        self.to_katakana_button.set_label(self.to_katakana_value or "Not Set")

        self.to_hiragana_value = conv_keys.get("to_hiragana", default_conv_keys.get("to_hiragana", "Ctrl+J"))
        self.to_hiragana_button.set_label(self.to_hiragana_value or "Not Set")

        self.to_ascii_value = conv_keys.get("to_ascii", default_conv_keys.get("to_ascii", "Ctrl+L"))
        self.to_ascii_button.set_label(self.to_ascii_value or "Not Set")

        self.to_zenkaku_value = conv_keys.get("to_zenkaku", default_conv_keys.get("to_zenkaku", "Ctrl+Shift+L"))
        self.to_zenkaku_button.set_label(self.to_zenkaku_value or "Not Set")

        # Dictionaries tab
        dictionaries = self.config.get("dictionaries") or {}
        if not isinstance(dictionaries, dict):
            dictionaries = {}

        # Get the list of currently enabled system dictionaries from config
        enabled_system_paths = set(dictionaries.get("system", []) or [])

        # Scan the system dictionaries directory recursively
        sys_dict_dir = os.path.join(util.get_datadir(), 'dictionaries')
        if os.path.exists(sys_dict_dir) and os.path.isdir(sys_dict_dir):
            # Collect all dictionary files with their relative paths
            dict_files = []
            for root, dirs, files in os.walk(sys_dict_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    # Calculate relative path for display
                    rel_path = os.path.relpath(full_path, sys_dict_dir)
                    dict_files.append((rel_path, full_path))

            # Sort by relative path and add to store
            for rel_path, full_path in sorted(dict_files):
                # Check if this dictionary is enabled in config
                enabled = full_path in enabled_system_paths
                self.sys_dict_store.append([enabled, rel_path, full_path])

        # Load user dictionaries by scanning the dictionaries/ directory for .txt files
        user_dict_dir = util.get_user_dictionaries_dir()
        if os.path.exists(user_dict_dir):
            for filename in sorted(os.listdir(user_dict_dir)):
                if filename.endswith('.txt'):
                    self.user_dict_store.append([filename])

        # Murenso tab - populate kanchoku layout combo
        self.kanchoku_layout_combo.remove_all()

        # Search for kanchoku layout JSON files in both user and system directories
        user_kanchoku_dir = os.path.join(util.get_user_configdir(), 'kanchoku_layouts')
        system_kanchoku_dir = os.path.join(util.get_datadir(), 'kanchoku_layouts')

        # Track files and their locations
        user_kanchoku_files = set()
        system_kanchoku_files = set()

        # Scan user kanchoku layouts directory
        if os.path.exists(user_kanchoku_dir):
            for filename in os.listdir(user_kanchoku_dir):
                if filename.endswith('.json'):
                    user_kanchoku_files.add(filename)

        # Scan system kanchoku layouts directory
        if os.path.exists(system_kanchoku_dir):
            for filename in os.listdir(system_kanchoku_dir):
                if filename.endswith('.json'):
                    system_kanchoku_files.add(filename)

        # Get all unique filenames
        all_kanchoku_files = user_kanchoku_files | system_kanchoku_files

        # Add found layouts to combo box with location info
        for filename in sorted(all_kanchoku_files):
            in_user = filename in user_kanchoku_files
            in_system = filename in system_kanchoku_files

            # Build display label with location info
            if in_user and in_system:
                display_label = f"{filename} (User, System)"
            elif in_user:
                display_label = f"{filename} (User)"
            else:
                display_label = f"{filename} (System)"

            # Use filename as ID for selection
            self.kanchoku_layout_combo.append(filename, display_label)

        # Set the current selection
        default_kanchoku = default_config.get("kanchoku_layout", "aki_code.json")
        kanchoku_layout = self.config.get("kanchoku_layout", default_kanchoku)
        self.kanchoku_layout_combo.set_active_id(kanchoku_layout)

        # Load mappings
        self.load_murenso_mappings()


    def on_save_clicked(self, button):
        """Save button clicked - collect all UI values and save to config.json"""
        # General tab
        self.config["layout"] = self.layout_combo.get_active_id() or "shingeta.json"
        self.config["kanchoku_layout"] = self.kanchoku_layout_combo.get_active_id() or "aki_code.json"
        self.config["enable_hiragana_key"] = self.hiragana_key_value or ""
        self.config["disable_hiragana_key"] = self.direct_key_value or ""

        self.config["ui"] = {
            "show_annotations": self.show_annotations_check.get_active(),
            "candidate_window_size": int(self.page_size_spin.get_value())
        }

        # Save preedit colors (with 0x prefix)
        fg_color = self.get_validated_color(self.preedit_fg_entry, "000000")
        bg_color = self.get_validated_color(self.preedit_bg_entry, "d1eaff")
        self.config["preedit_foreground_color"] = f"0x{fg_color}"
        self.config["preedit_background_color"] = f"0x{bg_color}"

        # Save use_ibus_hint_colors setting
        self.config["use_ibus_hint_colors"] = self.use_ibus_hint_check.get_active()

        # Input tab
        self.config["enable_sands"] = self.sands_enabled_check.get_active()
        self.config["forced_preedit_trigger_key"] = self.forced_preedit_trigger_entry.get_text()
        self.config["enable_murenso"] = self.murenso_enabled_check.get_active()

        # Conversion tab
        self.config["enable_learning"] = self.learning_enabled_check.get_active()

        self.config["conversion_keys"] = {
            "to_katakana": self.to_katakana_value or "",
            "to_hiragana": self.to_hiragana_value or "",
            "to_ascii": self.to_ascii_value or "",
            "to_zenkaku": self.to_zenkaku_value or ""
        }

        # Dictionaries tab
        # For system dictionaries, save only the full paths of enabled entries
        # Note: User dictionaries are no longer saved to config - they're discovered
        # by scanning ~/.config/ibus-pskk/dictionaries/ for .txt files
        enabled_system_dicts = [row[2] for row in self.sys_dict_store if row[0]]
        self.config["dictionaries"] = {
            "system": enabled_system_dicts
        }

        # Save config to JSON file
        config_path = os.path.join(util.get_user_configdir(), 'config.json')
        try:
            os.makedirs(util.get_user_configdir(), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"Configuration saved to {config_path}")

            # Save murenso/kanchoku mappings to separate file
            self.save_murenso_mappings()

            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Settings Saved"
            )
            dialog.format_secondary_text(f"Configuration saved to:\n{config_path}")
            dialog.run()
            dialog.destroy()

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Save Failed"
            )
            dialog.format_secondary_text(f"Error saving configuration:\n{e}")
            dialog.run()
            dialog.destroy()


    # Dictionary management methods
    def on_sys_dict_toggled(self, widget, path):
        """Handle checkbox toggle for system dictionary"""
        # Toggle the enabled state in the store
        self.sys_dict_store[path][0] = not self.sys_dict_store[path][0]

    def on_refresh_system_dicts(self, button):
        """Refresh the system dictionaries list by scanning the directory recursively"""
        # Remember currently enabled dictionaries
        enabled_paths = set()
        for row in self.sys_dict_store:
            if row[0]:  # enabled
                enabled_paths.add(row[2])  # full_path

        # Clear and rescan
        self.sys_dict_store.clear()

        # Scan the system dictionaries directory recursively
        sys_dict_dir = os.path.join(util.get_datadir(), 'dictionaries')
        if os.path.exists(sys_dict_dir) and os.path.isdir(sys_dict_dir):
            # Collect all dictionary files with their relative paths
            dict_files = []
            for root, dirs, files in os.walk(sys_dict_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    # Calculate relative path for display
                    rel_path = os.path.relpath(full_path, sys_dict_dir)
                    dict_files.append((rel_path, full_path))

            # Sort by relative path and add to store
            for rel_path, full_path in sorted(dict_files):
                # Check if this path was previously enabled
                enabled = full_path in enabled_paths
                self.sys_dict_store.append([enabled, rel_path, full_path])

        logger.info(f"Refreshed system dictionaries from {sys_dict_dir}")

    def on_convert_system_dicts(self, button):
        """Convert SKK dictionaries to merged system_dictionary.json under $HOME"""
        # Show a progress message
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="Converting dictionaries..."
        )
        dialog.format_secondary_text("Please wait while SKK dictionaries are being converted.")
        dialog.show_all()

        # Process GTK events to show the dialog
        while Gtk.events_pending():
            Gtk.main_iteration()

        # Perform the conversion
        success, output_path, stats = util.generate_system_dictionary()

        # Close progress dialog
        dialog.destroy()

        # Show result
        if success:
            result_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Conversion Complete"
            )
            result_dialog.format_secondary_text(
                f"System dictionary created successfully.\n\n"
                f"Output: {output_path}\n"
                f"Files processed: {stats['files_processed']}\n"
                f"Total readings: {stats['total_readings']:,}\n"
                f"Total candidates: {stats['total_candidates']:,}"
            )
        else:
            result_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Conversion Failed"
            )
            result_dialog.format_secondary_text(
                "Failed to convert SKK dictionaries.\n"
                "Please check that the SKK dictionaries directory exists."
            )

        result_dialog.run()
        result_dialog.destroy()

    def on_add_system_dict(self, button):
        """Add system dictionary"""
        dialog = Gtk.FileChooserDialog(
            title="Select Dictionary File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON dictionaries")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            self.sys_dict_store.append([path])

        dialog.destroy()


    def on_remove_system_dict(self, button):
        """Remove selected system dictionary"""
        selection = self.sys_dict_view.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            model.remove(treeiter)


    def on_refresh_user_dicts(self, button):
        """Refresh the list of user dictionary source files (.txt)"""
        self.user_dict_store.clear()
        user_dict_dir = util.get_user_dictionaries_dir()

        if not os.path.exists(user_dict_dir):
            logger.info(f"User dictionaries directory not found: {user_dict_dir}")
            return

        # List all .txt files in the user dictionaries directory
        for filename in sorted(os.listdir(user_dict_dir)):
            if filename.endswith('.txt'):
                self.user_dict_store.append([filename])

        logger.info(f"Refreshed user dictionaries from {user_dict_dir}")

    def on_convert_user_dicts(self, button):
        """Convert user SKK dictionary files to merged user_dictionary.json"""
        # Show a progress message
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="Converting user dictionaries..."
        )
        dialog.format_secondary_text("Please wait while SKK files are being converted.")
        dialog.show_all()

        # Process GTK events to show the dialog
        while Gtk.events_pending():
            Gtk.main_iteration()

        # Perform the conversion
        success, output_path, stats = util.generate_user_dictionary()

        # Close progress dialog
        dialog.destroy()

        # Show result
        if success:
            if output_path:
                result_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Conversion Complete"
                )
                result_dialog.format_secondary_text(
                    f"User dictionary created successfully.\n\n"
                    f"Output: {output_path}\n"
                    f"Files processed: {stats['files_processed']}\n"
                    f"Total readings: {stats['total_readings']}\n"
                    f"Total candidates: {stats['total_candidates']}"
                )
            else:
                result_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="No Files to Convert"
                )
                result_dialog.format_secondary_text(
                    "No .txt files found in the user dictionaries directory.\n\n"
                    f"Place SKK-format .txt files in:\n"
                    f"{util.get_user_dictionaries_dir()}"
                )
        else:
            result_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Conversion Failed"
            )
            result_dialog.format_secondary_text("Failed to convert user dictionaries. Check logs for details.")

        result_dialog.run()
        result_dialog.destroy()


    def on_import_skk_jisyo(self, button):
        """Import SKK-JISYO file"""
        dialog = Gtk.FileChooserDialog(
            title="Select SKK-JISYO File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            input_path = dialog.get_filename()
            dialog.destroy()

            # Ask for output location
            save_dialog = Gtk.FileChooserDialog(
                title="Save Converted Dictionary As",
                parent=self,
                action=Gtk.FileChooserAction.SAVE
            )
            save_dialog.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_SAVE, Gtk.ResponseType.OK
            )
            save_dialog.set_current_name("dictionary.json")

            response = save_dialog.run()
            if response == Gtk.ResponseType.OK:
                output_path = save_dialog.get_filename()
                save_dialog.destroy()

                # Import the dictionary
                try:
                    import subprocess
                    result = subprocess.run(
                        ["python3", "-m", "conversion.skk_dict", "--import", input_path, "--output", output_path],
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0:
                        # Add to system dictionaries
                        self.sys_dict_store.append([output_path])

                        info_dialog = Gtk.MessageDialog(
                            transient_for=self,
                            flags=0,
                            message_type=Gtk.MessageType.INFO,
                            buttons=Gtk.ButtonsType.OK,
                            text="Import Successful"
                        )
                        info_dialog.format_secondary_text(f"Dictionary imported to {output_path}")
                        info_dialog.run()
                        info_dialog.destroy()
                    else:
                        raise Exception(result.stderr)

                except Exception as e:
                    error_dialog = Gtk.MessageDialog(
                        transient_for=self,
                        flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Import Failed"
                    )
                    error_dialog.format_secondary_text(f"Error importing dictionary: {e}")
                    error_dialog.run()
                    error_dialog.destroy()
            else:
                save_dialog.destroy()
        else:
            dialog.destroy()


    # Murenso management methods
    def load_murenso_mappings(self):
        """Load murenso mappings from kanchoku layout"""
        self.murenso_store.clear()

        # Load from kanchoku layout if available
        if self.kanchoku_layout:
            try:
                # Convert nested dict to flat list for display
                for first_key, second_dict in self.kanchoku_layout.items():
                    for second_key, kanji in second_dict.items():
                        self.murenso_store.append([first_key, second_key, kanji])

                logger.info(f"Loaded {len(self.murenso_store)} kanchoku mappings")
            except Exception as e:
                logger.error(f"Error loading kanchoku layout mappings: {e}")
        else:
            logger.warning("No kanchoku layout loaded")


    def save_murenso_mappings(self, path=None):
        """Save murenso mappings to user config directory"""
        if path is None:
            # Save to user's config directory with the same filename as kanchoku_layout
            # This allows user edits to override the system layout
            kanchoku_filename = self.config.get('kanchoku_layout', 'aki_code.json')
            user_config_dir = util.get_user_configdir()
            path = os.path.join(user_config_dir, kanchoku_filename)

        # Convert flat list to nested dict
        mappings = {}
        for row in self.murenso_store:
            first_key, second_key, kanji = row[0], row[1], row[2]
            if first_key not in mappings:
                mappings[first_key] = {}
            mappings[first_key][second_key] = kanji

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved kanchoku layout mappings to {path}")
        except Exception as e:
            logger.error(f"Error saving kanchoku layout mappings: {e}")
            error_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Save Failed"
            )
            error_dialog.format_secondary_text(f"Error saving murenso mappings: {e}")
            error_dialog.run()
            error_dialog.destroy()


    def on_add_murenso(self, button):
        """Add new murenso mapping"""
        self.murenso_store.append(["", "", ""])


    def on_remove_murenso(self, button):
        """Remove selected murenso mapping"""
        selection = self.murenso_view.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            # Convert filtered iter to store iter
            store_iter = self.murenso_filter.convert_iter_to_child_iter(treeiter)
            self.murenso_store.remove(store_iter)


    def on_load_murenso(self, button):
        """Load murenso mappings from custom file"""
        dialog = Gtk.FileChooserDialog(
            title="Load Murenso Mappings",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        # Set default directory to kanchoku_layouts subdirectory
        kanchoku_dir = os.path.join(util.get_user_configdir(), 'kanchoku_layouts')
        if os.path.exists(kanchoku_dir):
            dialog.set_current_folder(kanchoku_dir)
        else:
            # Create it if it doesn't exist
            os.makedirs(kanchoku_dir, exist_ok=True)
            dialog.set_current_folder(kanchoku_dir)

        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            dialog.destroy()

            self.murenso_store.clear()

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)

                for first_key, second_dict in mappings.items():
                    for second_key, kanji in second_dict.items():
                        self.murenso_store.append([first_key, second_key, kanji])

            except Exception as e:
                error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Load Failed"
                )
                error_dialog.format_secondary_text(f"Error loading mappings: {e}")
                error_dialog.run()
                error_dialog.destroy()
        else:
            dialog.destroy()


    def on_save_murenso(self, button):
        """Save murenso mappings to custom file"""
        dialog = Gtk.FileChooserDialog(
            title="Save Murenso Mappings",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )

        # Set default directory to kanchoku_layouts subdirectory
        kanchoku_dir = os.path.join(util.get_user_configdir(), 'kanchoku_layouts')
        if os.path.exists(kanchoku_dir):
            dialog.set_current_folder(kanchoku_dir)
        else:
            # Create it if it doesn't exist
            os.makedirs(kanchoku_dir, exist_ok=True)
            dialog.set_current_folder(kanchoku_dir)

        dialog.set_current_name("murenso.json")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            dialog.destroy()
            self.save_murenso_mappings(path)

            info_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Saved Successfully"
            )
            info_dialog.format_secondary_text(f"Mappings saved to {path}")
            info_dialog.run()
            info_dialog.destroy()
        else:
            dialog.destroy()


    def on_murenso_first_edited(self, widget, path, text):
        """First key cell edited"""
        # Convert filtered path to store path
        filter_iter = self.murenso_filter.get_iter(path)
        store_iter = self.murenso_filter.convert_iter_to_child_iter(filter_iter)

        if len(text) > 1:
            # Show warning dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Invalid Input"
            )
            dialog.format_secondary_text(
                f"First Key must be a single character.\n"
                f"You entered: '{text}' ({len(text)} characters)\n"
                f"Only the first character '{text[0]}' will be saved."
            )
            dialog.run()
            dialog.destroy()
            # Save only the first character
            self.murenso_store[store_iter][0] = text[0] if text else ""
        else:
            self.murenso_store[store_iter][0] = text


    def on_murenso_second_edited(self, widget, path, text):
        """Second key cell edited"""
        # Convert filtered path to store path
        filter_iter = self.murenso_filter.get_iter(path)
        store_iter = self.murenso_filter.convert_iter_to_child_iter(filter_iter)

        if len(text) > 1:
            # Show warning dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Invalid Input"
            )
            dialog.format_secondary_text(
                f"Second Key must be a single character.\n"
                f"You entered: '{text}' ({len(text)} characters)\n"
                f"Only the first character '{text[0]}' will be saved."
            )
            dialog.run()
            dialog.destroy()
            # Save only the first character
            self.murenso_store[store_iter][1] = text[0] if text else ""
        else:
            self.murenso_store[store_iter][1] = text


    def on_murenso_kanji_edited(self, widget, path, text):
        """Kanji cell edited"""
        # Convert filtered path to store path
        filter_iter = self.murenso_filter.get_iter(path)
        store_iter = self.murenso_filter.convert_iter_to_child_iter(filter_iter)

        self.murenso_store[store_iter][2] = text

    def on_kanchoku_layout_changed(self, combo):
        """Handle kanchoku layout selection change"""
        selected_layout = combo.get_active_id()
        if selected_layout:
            # Update config
            self.config["kanchoku_layout"] = selected_layout
            # Reload kanchoku layout
            self.kanchoku_layout = util.get_kanchoku_layout(self.config)
            # Reload mappings in the table
            self.load_murenso_mappings()

    def on_murenso_search_changed(self, entry):
        """Handle search text changes"""
        # Refilter the tree view when search text changes
        self.murenso_filter.refilter()

    def murenso_filter_func(self, model, iter, data):
        """Filter function for murenso mappings"""
        # Get search text from each field
        search_first = self.murenso_search_first.get_text().lower()
        search_second = self.murenso_search_second.get_text().lower()
        search_kanji = self.murenso_search_kanji.get_text().lower()

        # Get row data
        first_key = model[iter][0].lower()
        second_key = model[iter][1].lower()
        kanji = model[iter][2].lower()

        # All non-empty search fields must match (AND logic)
        if search_first and search_first not in first_key:
            return False
        if search_second and search_second not in second_key:
            return False
        if search_kanji and search_kanji not in kanji:
            return False

        return True


def main():
    """Run settings panel standalone"""
    win = SettingsPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
