#!/usr/bin/env python3
# ui/settings_panel.py - GUI Settings Panel for IBus-PSKK

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import json
import os


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
        self.config_path = os.path.expanduser("~/.config/ibus-pskk/config.json")
        self.config = self.load_config()

        # Create UI
        self.create_ui()

        # Load current settings into UI
        self.load_settings_to_ui()

        # Connect Esc key to close window
        self.connect("key-press-event", self.on_key_press)

    def on_key_press(self, widget, event):
        """Handle key press events"""
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        
        # Return default config
        return self.get_default_config()


    def get_default_config(self):
        """Get default configuration"""
        return {
            "dictionaries": {
                "system": [],
                "user": ["~/.config/ibus-pskk/dictionary/*.json"]
            },
            "learning": {
                "enabled": True,
                "priority_file": "~/.config/ibus-pskk/candidate_priority.json"
            },
            "layout": {
                "type": "shingeta"
            },
            "sands": {
                "enabled": True,
                "keys": ["space"]
            },
            "input_mode": {
                "hiragana_key": "Alt_R",
                "direct_key": "Alt_L"
            },
            "conversion_keys": {
                "to_katakana": "Ctrl+K",
                "to_hiragana": "Ctrl+J",
                "to_ascii": "Ctrl+L",
                "to_zenkaku": "Ctrl+Shift+L"
            },
            "forced_preedit": {
                "enabled": True,
                "trigger_key": "f"
            },
            "murenso": {
                "enabled": True,
                "mapping_file": "~/.config/ibus-pskk/murenso.json"
            },
            "ui": {
                "candidate_window_size": 9,
                "show_annotations": True
            }
        }


    def save_config(self):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
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
            
        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Save Failed"
            )
            dialog.format_secondary_text(f"Error saving configuration: {e}")
            dialog.run()
            dialog.destroy()


    def create_ui(self):
        """Create the user interface"""
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
        self.layout_combo.append("shingeta", "新下駄配列 (ShinGeta)")
        self.layout_combo.append("qwerty-romaji", "QWERTY Romaji")
        self.layout_combo.append("custom", "Custom Layout")
        layout_box.pack_start(Gtk.Label(label="Input Layout:", xalign=0), False, False, 0)
        layout_box.pack_start(self.layout_combo, False, False, 0)
        
        box.pack_start(layout_frame, False, False, 0)
        
        # Mode switch keys
        mode_frame = Gtk.Frame(label="Mode Switch Keys")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mode_box.set_border_width(10)
        mode_frame.add(mode_box)
        
        hiragana_box = Gtk.Box(spacing=6)
        hiragana_box.pack_start(Gtk.Label(label="Hiragana Mode:"), False, False, 0)
        self.hiragana_key_entry = Gtk.Entry()
        hiragana_box.pack_start(self.hiragana_key_entry, True, True, 0)
        mode_box.pack_start(hiragana_box, False, False, 0)
        
        direct_box = Gtk.Box(spacing=6)
        direct_box.pack_start(Gtk.Label(label="Direct Mode:"), False, False, 0)
        self.direct_key_entry = Gtk.Entry()
        direct_box.pack_start(self.direct_key_entry, True, True, 0)
        mode_box.pack_start(direct_box, False, False, 0)
        
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
        
        # Katakana
        kata_box = Gtk.Box(spacing=6)
        kata_box.pack_start(Gtk.Label(label="To Katakana:"), False, False, 0)
        self.to_katakana_entry = Gtk.Entry()
        kata_box.pack_start(self.to_katakana_entry, True, True, 0)
        keys_box.pack_start(kata_box, False, False, 0)
        
        # Hiragana
        hira_box = Gtk.Box(spacing=6)
        hira_box.pack_start(Gtk.Label(label="To Hiragana:"), False, False, 0)
        self.to_hiragana_entry = Gtk.Entry()
        hira_box.pack_start(self.to_hiragana_entry, True, True, 0)
        keys_box.pack_start(hira_box, False, False, 0)
        
        # ASCII
        ascii_box = Gtk.Box(spacing=6)
        ascii_box.pack_start(Gtk.Label(label="To ASCII:"), False, False, 0)
        self.to_ascii_entry = Gtk.Entry()
        ascii_box.pack_start(self.to_ascii_entry, True, True, 0)
        keys_box.pack_start(ascii_box, False, False, 0)
        
        # Zenkaku
        zen_box = Gtk.Box(spacing=6)
        zen_box.pack_start(Gtk.Label(label="To Zenkaku:"), False, False, 0)
        self.to_zenkaku_entry = Gtk.Entry()
        zen_box.pack_start(self.to_zenkaku_entry, True, True, 0)
        keys_box.pack_start(zen_box, False, False, 0)
        
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

        # System dictionary list
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(150)
        self.sys_dict_store = Gtk.ListStore(str)  # Dictionary path
        self.sys_dict_view = Gtk.TreeView(model=self.sys_dict_store)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Dictionary Path", renderer, text=0)
        self.sys_dict_view.append_column(column)
        scroll.add(self.sys_dict_view)
        sys_box.pack_start(scroll, True, True, 0)

        # System dict buttons
        sys_btn_box = Gtk.Box(spacing=6)
        add_sys_btn = Gtk.Button(label="Add Dictionary")
        add_sys_btn.connect("clicked", self.on_add_system_dict)
        sys_btn_box.pack_start(add_sys_btn, False, False, 0)

        remove_sys_btn = Gtk.Button(label="Remove Selected")
        remove_sys_btn.connect("clicked", self.on_remove_system_dict)
        sys_btn_box.pack_start(remove_sys_btn, False, False, 0)

        import_btn = Gtk.Button(label="Import SKK-JISYO...")
        import_btn.connect("clicked", self.on_import_skk_jisyo)
        sys_btn_box.pack_start(import_btn, False, False, 0)

        sys_box.pack_start(sys_btn_box, False, False, 0)

        box.pack_start(sys_frame, True, True, 0)

        # User dictionaries
        user_frame = Gtk.Frame(label="User Dictionaries")
        user_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        user_box.set_border_width(10)
        user_frame.add(user_box)

        # User dictionary list
        user_scroll = Gtk.ScrolledWindow()
        user_scroll.set_min_content_height(100)
        self.user_dict_store = Gtk.ListStore(str)
        self.user_dict_view = Gtk.TreeView(model=self.user_dict_store)
        user_renderer = Gtk.CellRendererText()
        user_column = Gtk.TreeViewColumn("Dictionary Path/Pattern", user_renderer, text=0)
        self.user_dict_view.append_column(user_column)
        user_scroll.add(self.user_dict_view)
        user_box.pack_start(user_scroll, True, True, 0)

        # User dict buttons
        user_btn_box = Gtk.Box(spacing=6)
        add_user_btn = Gtk.Button(label="Add Dictionary/Pattern")
        add_user_btn.connect("clicked", self.on_add_user_dict)
        user_btn_box.pack_start(add_user_btn, False, False, 0)

        remove_user_btn = Gtk.Button(label="Remove Selected")
        remove_user_btn.connect("clicked", self.on_remove_user_dict)
        user_btn_box.pack_start(remove_user_btn, False, False, 0)

        user_box.pack_start(user_btn_box, False, False, 0)

        box.pack_start(user_frame, True, True, 0)

        return box


    def create_murenso_tab(self):
        """Create Murenso mappings tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # Info label
        info_label = Gtk.Label()
        info_label.set_markup(
            "<b>無連想配列 (Direct Kanji Input)</b>\n"
            "Map 2-key sequences to Kanji characters while holding Space.\n"
            "Example: Space + i + 1 → 一"
        )
        info_label.set_line_wrap(True)
        box.pack_start(info_label, False, False, 0)

        # Murenso mapping table
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(400)

        # Store: first_key, second_key, kanji
        self.murenso_store = Gtk.ListStore(str, str, str)
        self.murenso_view = Gtk.TreeView(model=self.murenso_store)

        # First key column
        first_renderer = Gtk.CellRendererText()
        first_renderer.set_property("editable", True)
        first_renderer.connect("edited", self.on_murenso_first_edited)
        first_column = Gtk.TreeViewColumn("First Key", first_renderer, text=0)
        self.murenso_view.append_column(first_column)

        # Second key column
        second_renderer = Gtk.CellRendererText()
        second_renderer.set_property("editable", True)
        second_renderer.connect("edited", self.on_murenso_second_edited)
        second_column = Gtk.TreeViewColumn("Second Key", second_renderer, text=1)
        self.murenso_view.append_column(second_column)

        # Kanji column
        kanji_renderer = Gtk.CellRendererText()
        kanji_renderer.set_property("editable", True)
        kanji_renderer.connect("edited", self.on_murenso_kanji_edited)
        kanji_column = Gtk.TreeViewColumn("Kanji", kanji_renderer, text=2)
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
        # General tab
        layout = self.config.get("layout", "shin-geta")
        if isinstance(layout, dict):
            layout_type = layout.get("type", "shin-geta")
        else:
            layout_type = layout  # layout is a string
        self.layout_combo.set_active_id(layout_type)

        input_mode = self.config.get("input_mode") or {}
        if not isinstance(input_mode, dict):
            input_mode = {}
        self.hiragana_key_entry.set_text(input_mode.get("hiragana_key", "Alt_R"))
        self.direct_key_entry.set_text(input_mode.get("direct_key", "Alt_L"))

        ui = self.config.get("ui") or {}
        if not isinstance(ui, dict):
            ui = {}
        self.show_annotations_check.set_active(ui.get("show_annotations", True))
        self.page_size_spin.set_value(ui.get("candidate_window_size", 9))

        # Input tab
        sands = self.config.get("sands") or {}
        if not isinstance(sands, dict):
            sands = {}
        self.sands_enabled_check.set_active(sands.get("enabled", True))

        fp = self.config.get("forced_preedit") or {}
        if not isinstance(fp, dict):
            fp = {}
        self.forced_preedit_enabled_check.set_active(fp.get("enabled", True))
        self.forced_preedit_trigger_entry.set_text(fp.get("trigger_key", "f"))

        murenso = self.config.get("murenso") or {}
        if not isinstance(murenso, dict):
            murenso = {}
        self.murenso_enabled_check.set_active(murenso.get("enabled", True))

        # Conversion tab
        learning = self.config.get("learning") or {}
        if not isinstance(learning, dict):
            learning = {}
        self.learning_enabled_check.set_active(learning.get("enabled", True))

        conv_keys = self.config.get("conversion_keys") or {}
        if not isinstance(conv_keys, dict):
            conv_keys = {}
        self.to_katakana_entry.set_text(conv_keys.get("to_katakana", "Ctrl+K"))
        self.to_hiragana_entry.set_text(conv_keys.get("to_hiragana", "Ctrl+J"))
        self.to_ascii_entry.set_text(conv_keys.get("to_ascii", "Ctrl+L"))
        self.to_zenkaku_entry.set_text(conv_keys.get("to_zenkaku", "Ctrl+Shift+L"))

        # Dictionaries tab
        dictionaries = self.config.get("dictionaries") or {}
        if not isinstance(dictionaries, dict):
            dictionaries = {}
        for path in dictionaries.get("system", []) or []:
            self.sys_dict_store.append([path])
        for path in dictionaries.get("user", []) or []:
            self.user_dict_store.append([path])

        # Murenso tab
        self.load_murenso_mappings()


    def on_save_clicked(self, button):
        """Save button clicked"""
        # Update config from UI
        # Handle layout - ensure it's a dict
        if "layout" not in self.config:
            self.config["layout"] = {}
        if isinstance(self.config["layout"], str):
            self.config["layout"] = {"type": self.config["layout"]}
        self.config["layout"]["type"] = self.layout_combo.get_active_id()

        if "input_mode" not in self.config:
            self.config["input_mode"] = {}
        self.config["input_mode"]["hiragana_key"] = self.hiragana_key_entry.get_text()
        self.config["input_mode"]["direct_key"] = self.direct_key_entry.get_text()

        if "ui" not in self.config:
            self.config["ui"] = {}
        self.config["ui"]["show_annotations"] = self.show_annotations_check.get_active()
        self.config["ui"]["candidate_window_size"] = int(self.page_size_spin.get_value())

        if "sands" not in self.config:
            self.config["sands"] = {}
        self.config["sands"]["enabled"] = self.sands_enabled_check.get_active()

        if "forced_preedit" not in self.config:
            self.config["forced_preedit"] = {}
        self.config["forced_preedit"]["enabled"] = self.forced_preedit_enabled_check.get_active()
        self.config["forced_preedit"]["trigger_key"] = self.forced_preedit_trigger_entry.get_text()

        if "murenso" not in self.config:
            self.config["murenso"] = {}
        self.config["murenso"]["enabled"] = self.murenso_enabled_check.get_active()

        if "learning" not in self.config:
            self.config["learning"] = {}
        self.config["learning"]["enabled"] = self.learning_enabled_check.get_active()

        if "conversion_keys" not in self.config:
            self.config["conversion_keys"] = {}
        self.config["conversion_keys"]["to_katakana"] = self.to_katakana_entry.get_text()
        self.config["conversion_keys"]["to_hiragana"] = self.to_hiragana_entry.get_text()
        self.config["conversion_keys"]["to_ascii"] = self.to_ascii_entry.get_text()
        self.config["conversion_keys"]["to_zenkaku"] = self.to_zenkaku_entry.get_text()

        # Update dictionaries from UI
        if "dictionaries" not in self.config:
            self.config["dictionaries"] = {}
        sys_dicts = []
        for row in self.sys_dict_store:
            sys_dicts.append(row[0])
        self.config["dictionaries"]["system"] = sys_dicts

        user_dicts = []
        for row in self.user_dict_store:
            user_dicts.append(row[0])
        self.config["dictionaries"]["user"] = user_dicts

        # Save murenso mappings
        self.save_murenso_mappings()

        # Save to file
        self.save_config()


    # Dictionary management methods
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


    def on_add_user_dict(self, button):
        """Add user dictionary or pattern"""
        dialog = Gtk.Dialog(
            title="Add User Dictionary",
            parent=self,
            flags=0
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_border_width(10)

        label = Gtk.Label(label="Enter dictionary path or glob pattern:")
        content.pack_start(label, False, False, 0)

        entry = Gtk.Entry()
        entry.set_text("~/.config/ibus-pskk/dictionary/*.json")
        content.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            path = entry.get_text()
            if path:
                self.user_dict_store.append([path])

        dialog.destroy()


    def on_remove_user_dict(self, button):
        """Remove selected user dictionary"""
        selection = self.user_dict_view.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            model.remove(treeiter)


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
        """Load murenso mappings from file"""
        self.murenso_store.clear()

        murenso_path = os.path.expanduser(
            self.config.get("murenso", {}).get("mapping_file", "~/.config/ibus-pskk/murenso.json")
        )

        if os.path.exists(murenso_path):
            try:
                with open(murenso_path, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)

                # Convert nested dict to flat list for display
                for first_key, second_dict in mappings.items():
                    for second_key, kanji in second_dict.items():
                        self.murenso_store.append([first_key, second_key, kanji])

            except Exception as e:
                print(f"Error loading murenso mappings: {e}")


    def save_murenso_mappings(self, path=None):
        """Save murenso mappings to file"""
        if path is None:
            path = os.path.expanduser(
                self.config.get("murenso", {}).get("mapping_file", "~/.config/ibus-pskk/murenso.json")
            )

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

        except Exception as e:
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
            model.remove(treeiter)


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
        self.murenso_store[path][0] = text


    def on_murenso_second_edited(self, widget, path, text):
        """Second key cell edited"""
        self.murenso_store[path][1] = text


    def on_murenso_kanji_edited(self, widget, path, text):
        """Kanji cell edited"""
        self.murenso_store[path][2] = text


def main():
    """Run settings panel standalone"""
    win = SettingsPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
