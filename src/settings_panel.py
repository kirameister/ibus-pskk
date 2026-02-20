#!/usr/bin/env python3
"""
settings_panel.py - GUI Settings Panel for IBus-PSKK
IBus-PSKK用のGUI設定パネル

================================================================================
WHAT THIS FILE DOES / このファイルの役割
================================================================================

This is the CONFIGURATION INTERFACE for PSKK. When users want to customize
their input method, they launch this settings panel. It provides a graphical
way to modify all aspects of the IME without editing config files directly.

これはPSKKの設定インターフェース。ユーザーが入力メソッドをカスタマイズしたい時に
この設定パネルを起動する。設定ファイルを直接編集せずに、IMEの全ての面を
グラフィカルに変更できる方法を提供する。

================================================================================
HOW TO LAUNCH / 起動方法
================================================================================

There are two ways to open this panel:
このパネルを開く方法は2つ:

    1. From IBus preferences → PSKK → Preferences button
       IBus設定から → PSKK → 設定ボタン

    2. Run directly: python settings_panel.py
       直接実行: python settings_panel.py

================================================================================
PANEL STRUCTURE (TABS) / パネル構造（タブ）
================================================================================

The settings panel is organized into these tabs:
設定パネルは以下のタブで構成:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  [General] [Input] [Conversion] [System Dict] [User Dict] [Ext] [無連想] │
    └─────────────────────────────────────────────────────────────────────────┘

    1. General (一般)
       ─────────────────
       - Input layout selection (QWERTY, JIS Kana, etc.)
         入力レイアウト選択
       - Mode switch keys (Hiragana/Direct mode hotkeys)
         モード切替キー
       - UI preferences (annotations, page size, colors)
         UI設定（注釈、ページサイズ、色）

    2. Input (入力)
       ─────────────────
       - SandS (Space and Shift) feature toggle
         SandS機能のON/OFF
       - Learning mode toggle (remember user choices)
         学習モードのON/OFF
       - Simultaneous key input settings
         同時打鍵設定

    3. Conversion (変換)
       ─────────────────
       - Conversion key bindings (to hiragana, katakana, etc.)
         変換キーバインド
       - Kanchoku (direct kanji input) settings
         漢直設定
       - Bunsetsu (phrase boundary) settings
         文節設定

    4. System Dictionary (システム辞書)
       ─────────────────
       - Enable/disable system dictionaries
         システム辞書の有効/無効
       - Adjust dictionary weights (priority)
         辞書の重み（優先度）調整
       - Convert SKK dictionaries to binary format
         SKK辞書をバイナリ形式に変換

    5. User Dictionary (ユーザー辞書)
       ─────────────────
       - Manage personal dictionary files
         個人辞書ファイルの管理
       - Open the User Dictionary Editor
         ユーザー辞書エディタを開く

    6. Ext-Dictionary (拡張辞書)
       ─────────────────
       - External dictionaries in custom locations
         カスタム場所の外部辞書
       - Import SKK-JISYO format dictionaries
         SKK-JISYO形式の辞書をインポート

    7. 無連想配列 (Murenso Layout)
       ─────────────────
       - Edit Murenso (two-key combination) mappings
         無連想（2キー組み合わせ）マッピングの編集
       - Load/save custom Murenso configurations
         カスタム無連想設定の読み込み/保存

================================================================================
CONFIGURATION STORAGE / 設定の保存場所
================================================================================

All settings are stored in: ~/.config/ibus-pskk/config.json
全ての設定は以下に保存: ~/.config/ibus-pskk/config.json

The panel reads this file on startup and writes changes when "Save" is clicked.
パネルは起動時にこのファイルを読み込み、「保存」クリック時に変更を書き込む。

================================================================================
KEY CAPTURE DIALOG / キーキャプチャダイアログ
================================================================================

When configuring keybindings, a special dialog appears that:
キーバインドを設定する時、特別なダイアログが表示される:

    - Captures the actual keys you press (including modifiers)
      実際に押したキーをキャプチャ（修飾キー含む）
    - Shows a preview of the captured combination
      キャプチャした組み合わせのプレビューを表示
    - Validates that the binding is not modifier-only
      修飾キーのみのバインドでないことを検証

Example: Press Ctrl+Shift+K → Displays "Control+Shift+K"
例: Ctrl+Shift+Kを押す → 「Control+Shift+K」と表示

================================================================================
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import json
import os
import logging
logger = logging.getLogger(__name__)

import util
import user_dictionary_editor


class SettingsPanel(Gtk.Window):
    """
    GUI Settings Panel for IBus-PSKK configuration.
    IBus-PSKK設定用のGUI設定パネル。

    ============================================================================
    OVERVIEW / 概要
    ============================================================================

    This is a GTK3 window that provides a user-friendly interface for
    configuring all aspects of the PSKK input method. It extends Gtk.Window
    and uses a notebook (tabbed interface) to organize settings by category.

    これはPSKK入力メソッドの全ての面を設定するためのユーザーフレンドリーな
    インターフェースを提供するGTK3ウィンドウ。Gtk.Windowを継承し、設定を
    カテゴリ別に整理するためにノートブック（タブインターフェース）を使用。

    ============================================================================
    FEATURES / 機能
    ============================================================================

    - Enable/disable features (SandS, Murenso, Forced Preedit, Learning)
      機能の有効/無効（SandS、無連想、強制プリエディット、学習）
    - Configure mode switch keys (Hiragana ↔ Direct)
      モード切替キーの設定（ひらがな ↔ 直接入力）
    - Set conversion key bindings (to hiragana, katakana, ASCII, zenkaku)
      変換キーバインドの設定（ひらがな、カタカナ、ASCII、全角へ）
    - Manage system and user dictionaries with priority weights
      優先度の重みでシステム辞書とユーザー辞書を管理
    - Edit Murenso (two-key) mappings for direct kanji input
      漢直用の無連想（2キー）マッピングを編集
    - Import/export configuration and dictionaries
      設定と辞書のインポート/エクスポート

    ============================================================================
    KEY ATTRIBUTES / 主な属性
    ============================================================================

    config : dict
        The loaded configuration dictionary from config.json.
        config.jsonから読み込んだ設定辞書。

    kanchoku_layout : dict
        The Murenso/Kanchoku key-to-kanji mappings.
        無連想/漢直のキーから漢字へのマッピング。

    Various UI widgets (checkboxes, entries, buttons, tree views):
    各種UIウィジェット（チェックボックス、エントリ、ボタン、ツリービュー）:
        - self.*_check: Gtk.CheckButton widgets for toggles
        - self.*_entry: Gtk.Entry widgets for text input
        - self.*_button: Gtk.Button widgets for keybinding capture
        - self.*_store: Gtk.ListStore for tree view data

    ============================================================================
    LIFECYCLE / ライフサイクル
    ============================================================================

        ┌─────────────────────────────────────────────────────────────────────┐
        │  __init__()                                                         │
        │      │                                                              │
        │      ├── Load config from util.get_config_data()                    │
        │      ├── Load kanchoku layout                                       │
        │      ├── create_ui() → Build all tabs and widgets                   │
        │      ├── load_settings_to_ui() → Populate widgets with values       │
        │      └── Show warnings if config had issues                         │
        │                                                                     │
        │  User interacts with UI...                                          │
        │  ユーザーがUIを操作...                                                │
        │                                                                     │
        │  on_save_clicked()                                                  │
        │      │                                                              │
        │      ├── Read values from all widgets                               │
        │      ├── Update self.config dictionary                              │
        │      └── save_config() → Write to config.json                       │
        └─────────────────────────────────────────────────────────────────────┘

    ============================================================================
    """

    def __init__(self):
        """
        Initialize the settings panel window.
        設定パネルウィンドウを初期化。

        This constructor:
        このコンストラクタは:
            1. Creates the GTK window with title and size
               タイトルとサイズでGTKウィンドウを作成
            2. Loads current configuration from file
               ファイルから現在の設定を読み込み
            3. Builds all UI elements (tabs, widgets)
               全てのUI要素を構築（タブ、ウィジェット）
            4. Populates widgets with current settings
               現在の設定でウィジェットを設定
            5. Shows any configuration warnings to user
               設定の警告があればユーザーに表示
        """
        super().__init__(title="IBus-PSKK Settings")

        self.set_default_size(800, 600)
        self.set_border_width(10)

        # Load configuration (returns tuple of config dict and any warnings)
        # 設定を読み込み（設定辞書と警告のタプルを返す）
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

    def on_kanchoku_marker_button_clicked(self, button):
        """Show key capture dialog for kanchoku bunsetsu marker key"""
        result = self.show_key_capture_dialog("Kanchoku Bunsetsu Marker", self.kanchoku_marker_value)
        if result is not None:
            self.kanchoku_marker_value = result
            self.kanchoku_marker_button.set_label(result if result else "Not Set")

    def on_bunsetsu_cycle_key_button_clicked(self, button):
        """Show key capture dialog for bunsetsu prediction cycle key"""
        result = self.show_key_capture_dialog("Bunsetsu Prediction Cycle Key", self.bunsetsu_cycle_key_value)
        if result is not None:
            self.bunsetsu_cycle_key_value = result
            self.bunsetsu_cycle_key_button.set_label(result if result else "Not Set")

    def on_force_commit_key_button_clicked(self, button):
        """Show key capture dialog for force commit key"""
        result = self.show_key_capture_dialog("Force Commit Key", self.force_commit_key_value)
        if result is not None:
            self.force_commit_key_value = result
            self.force_commit_key_button.set_label(result if result else "Not Set")

    def on_user_dict_editor_key_button_clicked(self, button):
        """Show key capture dialog for user dictionary editor launch key.

        This keybinding requires Ctrl+Shift+<key> format to prevent accidental activation.
        """
        while True:
            result = self.show_key_capture_dialog("User Dictionary Editor Key", self.user_dict_editor_key_value)

            # User cancelled or cleared the binding
            if result is None:
                return
            if result == "":
                self.user_dict_editor_key_value = result
                self.user_dict_editor_key_button.set_label("Not Set")
                return

            # Validate: must be Ctrl+Shift+<key>
            if self._validate_ctrl_shift_key(result):
                self.user_dict_editor_key_value = result
                self.user_dict_editor_key_button.set_label(result)
                return
            else:
                # Show warning and loop back to dialog
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text="Invalid Key Binding"
                )
                dialog.format_secondary_text(
                    "The User Dictionary Editor keybinding must use both Ctrl and Shift modifiers.\n\n"
                    f"Expected format: Ctrl+Shift+<key>\n"
                    f"You entered: {result}\n\n"
                    "Please try again."
                )
                dialog.run()
                dialog.destroy()
                # Loop continues, dialog will be shown again

    def _validate_ctrl_shift_key(self, binding):
        """Validate that a keybinding is in Ctrl+Shift+<key> format.

        Args:
            binding: Key binding string (e.g., "Ctrl+Shift+R")

        Returns:
            bool: True if valid (contains both Ctrl and Shift), False otherwise
        """
        if not binding:
            return False

        parts = binding.split('+')
        has_ctrl = 'Control' in parts
        has_shift = 'Shift' in parts
        # Must have at least 3 parts: Ctrl, Shift, and a key
        has_key = len(parts) >= 3

        return has_ctrl and has_shift and has_key

    def show_key_capture_dialog(self, title, current_value):
        """
        Show dialog to capture a key press for keybinding configuration.
        キーバインド設定のためのキー入力をキャプチャするダイアログを表示。

        Displays a modal dialog that intercepts key events. The user can:
        キーイベントをインターセプトするモーダルダイアログを表示。ユーザーは:
            - Press a key/combination to set a new binding
              新しいバインドを設定するためにキー/組み合わせを押す
            - Click "Remove" to clear the binding
              「Remove」をクリックしてバインドをクリア
            - Click "Cancel" to keep the existing binding
              「Cancel」をクリックして既存のバインドを維持

        Args:
            title: Dialog title (describes which keybinding is being set).
                   ダイアログタイトル（どのキーバインドを設定中か説明）。
            current_value: Current key binding string (e.g., "Alt_R", "Ctrl+K").
                           現在のキーバインド文字列（例: "Alt_R", "Ctrl+K"）。

        Returns:
            str: The captured key combination as a "+"-joined string
                 (e.g., "Control+Shift+K"), empty string "" if removed,
                 or None if cancelled.
                 「+」で結合されたキーの組み合わせ文字列
                 （例: "Control+Shift+K"）、削除された場合は空文字列""、
                 キャンセルされた場合はNone。
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
        """
        Save configuration to the config.json file.
        設定をconfig.jsonファイルに保存。

        Writes self.config to ~/.config/ibus-pskk/config.json using
        util.save_config_data(). Shows a success or error dialog to inform
        the user of the result.

        util.save_config_data()を使用してself.configを
        ~/.config/ibus-pskk/config.jsonに書き込む。
        結果をユーザーに通知するため、成功またはエラーのダイアログを表示。

        Note: Changes take effect on the next keystroke in the IME.
        注: 変更はIMEの次のキー入力から有効になる。
        """
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
        """
        Create the main user interface structure.
        メインユーザーインターフェース構造を作成。

        Builds the complete UI hierarchy:
        完全なUI階層を構築:

            Window
            └── main_box (vertical)
                ├── notebook (tabbed container)
                │   ├── General tab      → create_general_tab()
                │   ├── Input tab        → create_input_tab()
                │   ├── Conversion tab   → create_conversion_tab()
                │   ├── System Dict tab  → create_system_dictionary_tab()
                │   ├── User Dict tab    → create_user_dictionary_tab()
                │   ├── Ext-Dict tab     → create_ext_dictionary_tab()
                │   └── Murenso tab      → create_murenso_tab()
                └── button_box (horizontal)
                    ├── Close button
                    └── Save button

        Also applies CSS for entry validation (red background on invalid input).
        エントリ検証用のCSSも適用（無効な入力時に赤背景）。
        """
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
        notebook.append_page(self.create_system_dictionary_tab(), Gtk.Label(label="System Dictionary"))
        notebook.append_page(self.create_user_dictionary_tab(), Gtk.Label(label="User Dictionary"))
        notebook.append_page(self.create_ext_dictionary_tab(), Gtk.Label(label="Ext-Dictionary"))
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
        """
        Create the General settings tab.
        一般設定タブを作成。

        Contains:
        含まれる内容:
            - Layout selection (input keyboard layout)
              レイアウト選択（入力キーボードレイアウト）
            - Mode switch keys (Hiragana/Direct hotkeys)
              モード切替キー（ひらがな/直接入力のホットキー）
            - UI preferences (annotations, page size, preedit colors)
              UI設定（注釈、ページサイズ、プリエディット色）

        Returns:
            Gtk.Box: The configured tab container.
        """
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
        """
        Create the Input settings tab.
        入力設定タブを作成。

        Contains:
        含まれる内容:
            - SandS (Space and Shift) toggle and timeout
              SandS（スペースとシフト）のON/OFFとタイムアウト
            - Learning mode toggle (remember user selections)
              学習モードのON/OFF（ユーザー選択を記憶）
            - Forced preedit mode toggle
              強制プリエディットモードのON/OFF
            - Simultaneous input settings (timing threshold)
              同時入力設定（タイミング閾値）

        Returns:
            Gtk.Box: The configured tab container.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # SandS settings
        sands_frame = Gtk.Frame(label="SandS (Space and Shift)")
        sands_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sands_box.set_border_width(10)
        sands_frame.add(sands_box)
        
        self.sands_enabled_check = Gtk.CheckButton(label="Enable SandS (Space acts as Shift when held)")
        sands_box.pack_start(self.sands_enabled_check, False, False, 0)

        marker_row = Gtk.Box(spacing=6)
        marker_row.pack_start(Gtk.Label(label="Kanchoku Bunsetsu Marker:"), False, False, 0)
        self.kanchoku_marker_button = Gtk.Button(label="Not Set")
        self.kanchoku_marker_button.connect("clicked", self.on_kanchoku_marker_button_clicked)
        marker_row.pack_start(self.kanchoku_marker_button, True, True, 0)
        sands_box.pack_start(marker_row, False, False, 0)

        self.kanchoku_marker_value = None

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
        """
        Create the Conversion settings tab.
        変換設定タブを作成。

        Contains:
        含まれる内容:
            - Conversion key bindings (to_hiragana, to_katakana, etc.)
              変換キーバインド（ひらがなへ、カタカナへ、など）
            - Kanchoku bunsetsu marker key
              漢直文節マーカーキー
            - Bunsetsu prediction cycle key
              文節予測サイクルキー
            - User dictionary editor launch key
              ユーザー辞書エディタ起動キー

        Returns:
            Gtk.Box: The configured tab container.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

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

        # Bunsetsu Prediction settings
        bunsetsu_frame = Gtk.Frame(label="Bunsetsu Prediction")
        bunsetsu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bunsetsu_box.set_border_width(10)
        bunsetsu_frame.add(bunsetsu_box)

        # Bunsetsu Prediction Cycle Key
        cycle_key_box = Gtk.Box(spacing=6)
        cycle_key_label = Gtk.Label(label="Bunsetsu Prediction Cycle Key:")
        cycle_key_box.pack_start(cycle_key_label, False, False, 0)
        self.bunsetsu_cycle_key_button = Gtk.Button(label="Not Set")
        self.bunsetsu_cycle_key_button.connect("clicked", self.on_bunsetsu_cycle_key_button_clicked)
        cycle_key_box.pack_start(self.bunsetsu_cycle_key_button, True, True, 0)
        bunsetsu_box.pack_start(cycle_key_box, False, False, 0)

        # Initialize bunsetsu prediction instance variable
        self.bunsetsu_cycle_key_value = None

        box.pack_start(bunsetsu_frame, False, False, 0)

        # Force Commit settings
        force_commit_frame = Gtk.Frame(label="Force Commit")
        force_commit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        force_commit_box.set_border_width(10)
        force_commit_frame.add(force_commit_box)

        # Force Commit Key
        force_commit_key_box = Gtk.Box(spacing=6)
        force_commit_key_label = Gtk.Label(label="Force Commit Key:")
        force_commit_key_box.pack_start(force_commit_key_label, False, False, 0)
        self.force_commit_key_button = Gtk.Button(label="Not Set")
        self.force_commit_key_button.connect("clicked", self.on_force_commit_key_button_clicked)
        force_commit_key_box.pack_start(self.force_commit_key_button, True, True, 0)
        force_commit_box.pack_start(force_commit_key_box, False, False, 0)

        # Initialize force commit instance variable
        self.force_commit_key_value = None

        box.pack_start(force_commit_frame, False, False, 0)

        return box


    def create_system_dictionary_tab(self):
        """
        Create the System Dictionary settings tab.
        システム辞書設定タブを作成。

        Contains:
        含まれる内容:
            - List of available system dictionaries with toggle and weight
              有効/無効と重みを持つ利用可能なシステム辞書のリスト
            - Refresh button to rescan dictionary directory
              辞書ディレクトリを再スキャンするリフレッシュボタン
            - Convert button to compile SKK dictionaries to binary
              SKK辞書をバイナリにコンパイルする変換ボタン

        System dictionaries are located in the package data directory.
        システム辞書はパッケージデータディレクトリにある。

        Returns:
            Gtk.Box: The configured tab container.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # Info label
        sys_info_label = Gtk.Label()
        sys_info_label.set_markup(
            "<small>Dictionary files found in /opt/ibus-pskk/dictionaries/\n"
            "Check the box to enable a dictionary for conversion.</small>"
        )
        sys_info_label.set_xalign(0)
        box.pack_start(sys_info_label, False, False, 0)

        # System dictionary list with checkboxes
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(250)
        # Store: (enabled: bool, filename: str, full_path: str, weight: int)
        self.sys_dict_store = Gtk.ListStore(bool, str, str, int)
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
        text_column.set_expand(True)
        self.sys_dict_view.append_column(text_column)

        # Weight column (editable)
        weight_renderer = Gtk.CellRendererText()
        weight_renderer.set_property("editable", True)
        weight_renderer.connect("edited", self.on_sys_dict_weight_edited)
        weight_column = Gtk.TreeViewColumn("Weight", weight_renderer, text=3)
        weight_column.set_min_width(60)
        self.sys_dict_view.append_column(weight_column)

        scroll.add(self.sys_dict_view)
        box.pack_start(scroll, True, True, 0)

        # System dictionary buttons
        sys_btn_box = Gtk.Box(spacing=6)
        refresh_btn = Gtk.Button(label="Refresh List")
        refresh_btn.connect("clicked", self.on_refresh_system_dicts)
        sys_btn_box.pack_start(refresh_btn, False, False, 0)

        convert_btn = Gtk.Button(label="Convert under $HOME")
        convert_btn.connect("clicked", self.on_convert_system_dicts)
        sys_btn_box.pack_start(convert_btn, False, False, 0)

        box.pack_start(sys_btn_box, False, False, 0)

        return box

    def create_user_dictionary_tab(self):
        """
        Create the User Dictionary settings tab.
        ユーザー辞書設定タブを作成。

        Contains:
        含まれる内容:
            - List of user dictionaries with toggle and weight
              有効/無効と重みを持つユーザー辞書のリスト
            - Refresh/Convert buttons for user dictionaries
              ユーザー辞書のリフレッシュ/変換ボタン
            - Button to open the User Dictionary Editor
              ユーザー辞書エディタを開くボタン

        User dictionaries are stored in ~/.config/ibus-pskk/user_dict/
        ユーザー辞書は ~/.config/ibus-pskk/user_dict/ に保存される。

        Returns:
            Gtk.Box: The configured tab container.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # Info label
        user_info_label = Gtk.Label()
        user_info_label.set_markup(
            "<small>Place SKK-format .txt files in <b>~/.config/ibus-pskk/dictionaries/</b>\n"
            "Then click 'Convert' to generate imported_user_dictionary.json</small>"
        )
        user_info_label.set_xalign(0)
        box.pack_start(user_info_label, False, False, 0)

        # User dictionary list (shows .txt files in dictionaries/)
        user_scroll = Gtk.ScrolledWindow()
        user_scroll.set_min_content_height(200)
        # Store: (enabled: bool, filename: str, weight: int)
        self.user_dict_store = Gtk.ListStore(bool, str, int)
        self.user_dict_view = Gtk.TreeView(model=self.user_dict_store)

        # Checkbox column
        user_toggle_renderer = Gtk.CellRendererToggle()
        user_toggle_renderer.connect("toggled", self.on_user_dict_toggled)
        user_toggle_column = Gtk.TreeViewColumn("Enable", user_toggle_renderer, active=0)
        user_toggle_column.set_min_width(60)
        self.user_dict_view.append_column(user_toggle_column)

        # Filename column
        user_renderer = Gtk.CellRendererText()
        user_column = Gtk.TreeViewColumn("SKK Source Files (.txt)", user_renderer, text=1)
        user_column.set_expand(True)
        self.user_dict_view.append_column(user_column)

        # Weight column (editable)
        user_weight_renderer = Gtk.CellRendererText()
        user_weight_renderer.set_property("editable", True)
        user_weight_renderer.connect("edited", self.on_user_dict_weight_edited)
        user_weight_column = Gtk.TreeViewColumn("Weight", user_weight_renderer, text=2)
        user_weight_column.set_min_width(60)
        self.user_dict_view.append_column(user_weight_column)

        user_scroll.add(self.user_dict_view)
        box.pack_start(user_scroll, True, True, 0)

        # User dict buttons
        user_btn_box = Gtk.Box(spacing=6)

        refresh_user_btn = Gtk.Button(label="Refresh List")
        refresh_user_btn.connect("clicked", self.on_refresh_user_dicts)
        user_btn_box.pack_start(refresh_user_btn, False, False, 0)

        convert_user_btn = Gtk.Button(label="Convert")
        convert_user_btn.connect("clicked", self.on_convert_user_dicts)
        user_btn_box.pack_start(convert_user_btn, False, False, 0)

        user_entries_btn = Gtk.Button(label="User Dictionary Entries")
        user_entries_btn.connect("clicked", self.on_open_user_dictionary_editor)
        user_btn_box.pack_start(user_entries_btn, False, False, 0)

        box.pack_start(user_btn_box, False, False, 0)

        # Keybinding for launching User Dictionary Editor
        keybind_box = Gtk.Box(spacing=6)
        keybind_label = Gtk.Label(label="Editor Launch Key Binding:")
        keybind_box.pack_start(keybind_label, False, False, 0)
        self.user_dict_editor_key_button = Gtk.Button(label="Not Set")
        self.user_dict_editor_key_button.connect("clicked", self.on_user_dict_editor_key_button_clicked)
        keybind_box.pack_start(self.user_dict_editor_key_button, False, False, 0)
        self.user_dict_editor_key_value = None
        box.pack_start(keybind_box, False, False, 0)

        return box


    def create_murenso_tab(self):
        """
        Create the Murenso (無連想) mappings tab.
        無連想マッピングタブを作成。

        WHAT IS MURENSO? / 無連想とは？
        ─────────────────────────────────
        Murenso is a method of direct kanji input using two-key combinations.
        Instead of typing readings and converting, you press two keys in
        sequence to directly input a kanji character.

        無連想は2キーの組み合わせによる漢字直接入力方式。読みを入力して変換する
        代わりに、2つのキーを順番に押して漢字を直接入力する。

        Example: Press 'a' then 'k' → outputs '日'
        例: 'a'を押してから'k'を押す → '日'を出力

        Contains:
        含まれる内容:
            - Kanchoku layout selection dropdown
              漢直レイアウト選択ドロップダウン
            - Editable tree view of all mappings (first key, second key, kanji)
              全マッピングの編集可能なツリービュー（第1キー、第2キー、漢字）
            - Search/filter fields for finding specific mappings
              特定のマッピングを見つけるための検索/フィルタフィールド
            - Load/Save buttons for custom mapping files
              カスタムマッピングファイルの読み込み/保存ボタン

        Returns:
            Gtk.Box: The configured tab container.
        """
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


    def create_ext_dictionary_tab(self):
        """
        Create the Ext-Dictionary (Extension Dictionary) settings tab.
        拡張辞書設定タブを作成。

        WHAT IS THE EXTENDED DICTIONARY? / 拡張辞書とは？
        ─────────────────────────────────────────────────────
        The extended dictionary bridges kanchoku (direct kanji input) with
        normal kana-kanji conversion. It allows users to mix both input methods
        seamlessly by creating hybrid dictionary entries.

        拡張辞書は漢直（漢字直接入力）と通常のかな漢字変換を橋渡しする。
        ハイブリッド辞書エントリを作成することで、両方の入力方式を
        シームレスに混在させることができる。

        GENERATION ALGORITHM / 生成アルゴリズム:
          1. Reads the kanchoku layout to find all produceable kanji
             漢直レイアウトを読んで生成可能な全ての漢字を取得
          2. Extracts yomi→single-kanji mappings from source dictionaries
             ソース辞書から読み→単一漢字のマッピングを抽出
          3. Substring-matches those yomi against dictionary readings
             それらの読みを辞書の読みに部分文字列マッチング
          4. Creates hybrid keys with matched yomi replaced by kanji
             マッチした読みを漢字に置換したハイブリッドキーを作成

        Contains:
        含まれる内容:
            - System dictionary source selection
              システム辞書ソースの選択
            - User dictionary source selection
              ユーザー辞書ソースの選択
            - Generate/Import buttons
              生成/インポートボタン

        Returns:
            Gtk.Box: The configured tab container.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # Info label
        ext_info_label = Gtk.Label()
        ext_info_label.set_markup(
            "<small>Select source dictionaries whose yomi→single-kanji mappings will be used\n"
            "to generate <b>extended_dictionary.json</b> (bridging kanchoku with conversion).\n"
            "Requires system/user dictionaries to have been converted first.</small>"
        )
        ext_info_label.set_xalign(0)
        box.pack_start(ext_info_label, False, False, 0)

        # ── System Dictionaries ──
        ext_sys_frame = Gtk.Frame(label="System Dictionaries")
        ext_sys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ext_sys_box.set_border_width(10)
        ext_sys_frame.add(ext_sys_box)

        ext_sys_scroll = Gtk.ScrolledWindow()
        ext_sys_scroll.set_min_content_height(120)
        # Store: (enabled: bool, display_name: str, full_path: str)
        self.ext_sys_dict_store = Gtk.ListStore(bool, str, str)
        self.ext_sys_dict_view = Gtk.TreeView(model=self.ext_sys_dict_store)

        toggle_r = Gtk.CellRendererToggle()
        toggle_r.connect("toggled", self.on_ext_sys_dict_toggled)
        col = Gtk.TreeViewColumn("Enable", toggle_r, active=0)
        col.set_min_width(60)
        self.ext_sys_dict_view.append_column(col)

        text_r = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("Dictionary File", text_r, text=1)
        col.set_expand(True)
        self.ext_sys_dict_view.append_column(col)

        ext_sys_scroll.add(self.ext_sys_dict_view)
        ext_sys_box.pack_start(ext_sys_scroll, True, True, 0)

        box.pack_start(ext_sys_frame, True, True, 0)

        # ── User Dictionaries ──
        ext_user_frame = Gtk.Frame(label="User Dictionaries")
        ext_user_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ext_user_box.set_border_width(10)
        ext_user_frame.add(ext_user_box)

        ext_user_scroll = Gtk.ScrolledWindow()
        ext_user_scroll.set_min_content_height(100)
        # Store: (enabled: bool, display_name: str, full_path: str)
        self.ext_user_dict_store = Gtk.ListStore(bool, str, str)
        self.ext_user_dict_view = Gtk.TreeView(model=self.ext_user_dict_store)

        toggle_r2 = Gtk.CellRendererToggle()
        toggle_r2.connect("toggled", self.on_ext_user_dict_toggled)
        col = Gtk.TreeViewColumn("Enable", toggle_r2, active=0)
        col.set_min_width(60)
        self.ext_user_dict_view.append_column(col)

        text_r2 = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("SKK Source Files (.txt)", text_r2, text=1)
        col.set_expand(True)
        self.ext_user_dict_view.append_column(col)

        ext_user_scroll.add(self.ext_user_dict_view)
        ext_user_box.pack_start(ext_user_scroll, True, True, 0)

        box.pack_start(ext_user_frame, True, True, 0)

        # ── Buttons ──
        ext_btn_box = Gtk.Box(spacing=6)

        refresh_ext_btn = Gtk.Button(label="Refresh List")
        refresh_ext_btn.connect("clicked", self.on_refresh_ext_dicts)
        ext_btn_box.pack_start(refresh_ext_btn, False, False, 0)

        convert_ext_btn = Gtk.Button(label="Convert")
        convert_ext_btn.connect("clicked", self.on_convert_ext_dicts)
        ext_btn_box.pack_start(convert_ext_btn, False, False, 0)

        box.pack_start(ext_btn_box, False, False, 0)

        return box


    def load_settings_to_ui(self):
        """
        Load current settings from config into UI widgets.
        設定からUIウィジェットに現在の設定を読み込む。

        This method populates all UI controls with values from self.config:
        このメソッドはself.configの値で全てのUIコントロールを設定する:

            - Dropdown menus: Sets active item based on config value
              ドロップダウンメニュー: 設定値に基づいてアクティブ項目を設定
            - Checkboxes: Sets checked state based on boolean values
              チェックボックス: ブール値に基づいてチェック状態を設定
            - Text entries: Sets text content
              テキストエントリ: テキスト内容を設定
            - Spin buttons: Sets numeric values
              スピンボタン: 数値を設定
            - Key binding buttons: Sets label to show current binding
              キーバインドボタン: 現在のバインドを表示するラベルを設定
            - Tree views: Populates list of dictionaries
              ツリービュー: 辞書のリストを設定

        Called once during __init__() after create_ui().
        create_ui()の後、__init__()で1回呼ばれる。

        Uses default_config as fallback for any missing values.
        欠落している値のフォールバックとしてdefault_configを使用。
        """
        # Load default config to use as fallback for default values
        default_config = util.get_default_config_data() or {}

        # General tab - populate layout combo with available layout files
        self.layout_combo.remove_all()

        # Search for layout JSON files in both user and system directories
        user_layouts_dir = os.path.join(util.get_user_config_dir(), 'layouts')
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

        # Load kanchoku_bunsetsu_marker
        default_marker = default_config.get("kanchoku_bunsetsu_marker", "space")
        self.kanchoku_marker_value = self.config.get("kanchoku_bunsetsu_marker", default_marker)
        self.kanchoku_marker_button.set_label(self.kanchoku_marker_value or "Not Set")

        # Conversion tab
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

        # Bunsetsu Prediction settings
        self.bunsetsu_cycle_key_value = self.config.get("bunsetsu_prediction_cycle_key",
                                                         default_config.get("bunsetsu_prediction_cycle_key", ""))
        self.bunsetsu_cycle_key_button.set_label(self.bunsetsu_cycle_key_value or "Not Set")

        # Force Commit settings
        self.force_commit_key_value = self.config.get("force_commit_key",
                                                       default_config.get("force_commit_key", ""))
        self.force_commit_key_button.set_label(self.force_commit_key_value or "Not Set")

        # User Dictionary Editor keybinding
        self.user_dict_editor_key_value = self.config.get("user_dictionary_editor_trigger",
                                                           default_config.get("user_dictionary_editor_trigger", "Ctrl+Shift+R"))
        self.user_dict_editor_key_button.set_label(self.user_dict_editor_key_value or "Not Set")

        # Dictionaries tab
        dictionaries = self.config.get("dictionaries") or {}
        if not isinstance(dictionaries, dict):
            dictionaries = {}

        # Get system dictionary weights from config
        # Support both old format (list) and new format (dict with weights)
        system_dict_config = dictionaries.get("system", {}) or {}
        if isinstance(system_dict_config, list):
            # Convert old array format to dict with default weight 1
            system_dict_weights = {path: 1 for path in system_dict_config}
        else:
            system_dict_weights = system_dict_config

        # Get user dictionary weights from config
        user_dict_config = dictionaries.get("user", {}) or {}
        if isinstance(user_dict_config, list):
            # Convert old array format to dict with default weight 1
            user_dict_weights = {path: 1 for path in user_dict_config}
        else:
            user_dict_weights = user_dict_config

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
                # Check if this dictionary is enabled in config (has a weight entry)
                enabled = full_path in system_dict_weights
                weight = system_dict_weights.get(full_path, 1)
                self.sys_dict_store.append([enabled, rel_path, full_path, weight])

        # Load user dictionaries by scanning the dictionaries/ directory for .txt files
        user_dict_dir = util.get_user_dictionaries_dir()
        if os.path.exists(user_dict_dir):
            for filename in sorted(os.listdir(user_dict_dir)):
                if filename.endswith('.txt'):
                    # Enabled if the file appears in config's user dict
                    enabled = filename in user_dict_weights
                    weight = user_dict_weights.get(filename, 1)
                    self.user_dict_store.append([enabled, filename, weight])

        # Ext-Dictionary tab - populate system and user source lists
        # System dictionaries (same directory as the Dictionaries tab)
        sys_dict_dir = os.path.join(util.get_datadir(), 'dictionaries')
        if os.path.exists(sys_dict_dir) and os.path.isdir(sys_dict_dir):
            dict_files = []
            for root, dirs, files in os.walk(sys_dict_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, sys_dict_dir)
                    dict_files.append((rel_path, full_path))
            for rel_path, full_path in sorted(dict_files):
                self.ext_sys_dict_store.append([False, rel_path, full_path])

        # User dictionaries (same directory as the Dictionaries tab)
        user_dict_dir = util.get_user_dictionaries_dir()
        if os.path.exists(user_dict_dir):
            for filename in sorted(os.listdir(user_dict_dir)):
                if filename.endswith('.txt'):
                    full_path = os.path.join(user_dict_dir, filename)
                    self.ext_user_dict_store.append([False, filename, full_path])

        # Murenso tab - populate kanchoku layout combo
        self.kanchoku_layout_combo.remove_all()

        # Search for kanchoku layout JSON files in both user and system directories
        user_kanchoku_dir = os.path.join(util.get_user_config_dir(), 'kanchoku_layouts')
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
        """
        Handle Save button click - collect UI values and persist to file.
        保存ボタンのクリックを処理 - UI値を収集しファイルに永続化。

        This is the inverse of load_settings_to_ui(): reads all widget values
        and writes them back to self.config, then calls save_config() to
        write to disk.

        これはload_settings_to_ui()の逆: 全てのウィジェット値を読み取り
        self.configに書き戻し、save_config()を呼んでディスクに書き込む。

        Args:
            button: The Gtk.Button that was clicked (unused).
                    クリックされたGtk.Button（未使用）。
        """
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
        self.config["kanchoku_bunsetsu_marker"] = self.kanchoku_marker_value or ""

        # Conversion tab
        self.config["conversion_keys"] = {
            "to_katakana": self.to_katakana_value or "",
            "to_hiragana": self.to_hiragana_value or "",
            "to_ascii": self.to_ascii_value or "",
            "to_zenkaku": self.to_zenkaku_value or ""
        }

        # Bunsetsu Prediction settings
        self.config["bunsetsu_prediction_cycle_key"] = self.bunsetsu_cycle_key_value or ""

        # Force Commit settings
        self.config["force_commit_key"] = self.force_commit_key_value or ""

        # User Dictionary Editor keybinding
        self.config["user_dictionary_editor_trigger"] = self.user_dict_editor_key_value or ""

        # Dictionaries tab
        # For both system and user dictionaries, save as {path: weight} for enabled entries only
        enabled_system_dicts = {row[2]: row[3] for row in self.sys_dict_store if row[0]}
        enabled_user_dicts = {row[1]: row[2] for row in self.user_dict_store if row[0]}
        self.config["dictionaries"] = {
            "system": enabled_system_dicts,
            "user": enabled_user_dicts
        }

        # Save config to JSON file
        config_path = os.path.join(util.get_user_config_dir(), 'config.json')
        try:
            os.makedirs(util.get_user_config_dir(), exist_ok=True)
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

    def on_sys_dict_weight_edited(self, widget, path, new_text):
        """Handle weight value edit for system dictionary"""
        try:
            weight = int(new_text)
            if weight < 1:
                raise ValueError("Weight must be at least 1")
            self.sys_dict_store[path][3] = weight
        except ValueError:
            # Show error dialog for invalid weight
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Invalid Weight"
            )
            dialog.format_secondary_text(
                f"Weight must be a positive integer (1 or greater).\n"
                f"Invalid value: '{new_text}'"
            )
            dialog.run()
            dialog.destroy()
            # Disable the entry if weight is invalid
            self.sys_dict_store[path][0] = False

    def on_user_dict_toggled(self, widget, path):
        """Handle checkbox toggle for user dictionary"""
        self.user_dict_store[path][0] = not self.user_dict_store[path][0]

    def on_user_dict_weight_edited(self, widget, path, new_text):
        """Handle weight value edit for user dictionary"""
        try:
            weight = int(new_text)
            if weight < 1:
                raise ValueError("Weight must be at least 1")
            self.user_dict_store[path][2] = weight
        except ValueError:
            # Show error dialog for invalid weight
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Invalid Weight"
            )
            dialog.format_secondary_text(
                f"Weight must be a positive integer (1 or greater).\n"
                f"Invalid value: '{new_text}'"
            )
            dialog.run()
            dialog.destroy()
            # Disable the entry if weight is invalid
            self.user_dict_store[path][0] = False

    def on_refresh_system_dicts(self, button):
        """Refresh the system dictionaries list by scanning the directory recursively"""
        # Remember currently enabled dictionaries and their weights
        enabled_dict_weights = {}
        for row in self.sys_dict_store:
            if row[0]:  # enabled
                enabled_dict_weights[row[2]] = row[3]  # full_path: weight

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
                # Check if this path was previously enabled, preserve weight
                enabled = full_path in enabled_dict_weights
                weight = enabled_dict_weights.get(full_path, 1)
                self.sys_dict_store.append([enabled, rel_path, full_path, weight])

        logger.info(f"Refreshed system dictionaries from {sys_dict_dir}")

    def on_convert_system_dicts(self, button):
        """Convert SKK dictionaries to merged system_dictionary.json under $HOME"""
        # Collect enabled dictionaries with their weights (empty dict = clear dictionary)
        source_weights = {row[2]: row[3] for row in self.sys_dict_store if row[0]}

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

        # Perform the conversion with weights
        success, output_path, stats = util.generate_system_dictionary(source_weights=source_weights)

        # Close progress dialog
        dialog.destroy()

        # Regenerate CRF feature materials after dictionary change
        if success:
            util.generate_crf_feature_materials()

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
        # Remember current enabled states and weights
        current_state = {row[1]: (row[0], row[2]) for row in self.user_dict_store}

        self.user_dict_store.clear()
        user_dict_dir = util.get_user_dictionaries_dir()

        if not os.path.exists(user_dict_dir):
            logger.info(f"User dictionaries directory not found: {user_dict_dir}")
            return

        # List all .txt files in the user dictionaries directory
        for filename in sorted(os.listdir(user_dict_dir)):
            if filename.endswith('.txt'):
                # Preserve enabled state and weight if previously set
                if filename in current_state:
                    enabled, weight = current_state[filename]
                else:
                    enabled, weight = False, 1
                self.user_dict_store.append([enabled, filename, weight])

        logger.info(f"Refreshed user dictionaries from {user_dict_dir}")

    def on_convert_user_dicts(self, button):
        """Convert user SKK dictionary files to merged imported_user_dictionary.json"""
        # Collect enabled user dictionaries with their weights (empty dict = clear dictionary)
        source_weights = {row[1]: row[2] for row in self.user_dict_store if row[0]}

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

        # Perform the conversion with weights
        success, output_path, stats = util.generate_user_dictionary(source_weights=source_weights)

        # Close progress dialog
        dialog.destroy()

        # Regenerate CRF feature materials after dictionary change
        if success:
            util.generate_crf_feature_materials()

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

    def on_open_user_dictionary_editor(self, button):
        """Open the user dictionary editor window."""
        editor = user_dictionary_editor.open_editor()
        # Make the editor modal to this settings window
        editor.set_transient_for(self)
        editor.set_modal(True)

    # Ext-dictionary management methods
    def on_ext_sys_dict_toggled(self, widget, path):
        """Handle checkbox toggle for ext-dictionary system source"""
        self.ext_sys_dict_store[path][0] = not self.ext_sys_dict_store[path][0]

    def on_ext_user_dict_toggled(self, widget, path):
        """Handle checkbox toggle for ext-dictionary user source"""
        self.ext_user_dict_store[path][0] = not self.ext_user_dict_store[path][0]

    def on_refresh_ext_dicts(self, button):
        """Refresh both system and user source lists for ext-dictionary generation"""
        # ── System dictionaries ──
        sys_prev = {row[2]: row[0] for row in self.ext_sys_dict_store}
        self.ext_sys_dict_store.clear()

        sys_dict_dir = os.path.join(util.get_datadir(), 'dictionaries')
        if os.path.exists(sys_dict_dir) and os.path.isdir(sys_dict_dir):
            dict_files = []
            for root, dirs, files in os.walk(sys_dict_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, sys_dict_dir)
                    dict_files.append((rel_path, full_path))
            for rel_path, full_path in sorted(dict_files):
                enabled = sys_prev.get(full_path, False)
                self.ext_sys_dict_store.append([enabled, rel_path, full_path])

        # ── User dictionaries ──
        user_prev = {row[2]: row[0] for row in self.ext_user_dict_store}
        self.ext_user_dict_store.clear()

        user_dict_dir = util.get_user_dictionaries_dir()
        if os.path.exists(user_dict_dir):
            for filename in sorted(os.listdir(user_dict_dir)):
                if filename.endswith('.txt'):
                    full_path = os.path.join(user_dict_dir, filename)
                    enabled = user_prev.get(full_path, False)
                    self.ext_user_dict_store.append([enabled, filename, full_path])

        logger.info("Refreshed ext-dictionary source lists")

    def on_convert_ext_dicts(self, button):
        """Generate extended_dictionary.json from selected ext-dictionary sources"""
        # Combine enabled entries from both system and user stores
        source_paths = []
        for row in self.ext_sys_dict_store:
            if row[0]:
                source_paths.append(row[2])
        for row in self.ext_user_dict_store:
            if row[0]:
                source_paths.append(row[2])

        # Show a progress message
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="Generating extended dictionary..."
        )
        dialog.format_secondary_text(
            "Please wait while the extended dictionary is being generated.\n"
            "This reads kanchoku layout, ext-dictionary sources, and system/user dictionaries."
        )
        dialog.show_all()

        while Gtk.events_pending():
            Gtk.main_iteration()

        # Perform the generation
        success, output_path, stats = util.generate_extended_dictionary(
            config=self.config,
            source_paths=source_paths
        )

        dialog.destroy()

        # Regenerate CRF feature materials after dictionary change
        if success:
            util.generate_crf_feature_materials()

        # Show result
        if success:
            result_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Generation Complete"
            )
            result_dialog.format_secondary_text(
                f"Extended dictionary generated successfully.\n\n"
                f"Output: {output_path}\n"
                f"Kanchoku kanji: {stats['kanchoku_kanji_count']:,}\n"
                f"Source files processed: {stats['files_processed']}\n"
                f"Yomi→kanji mappings: {stats['yomi_kanji_mappings']:,}\n"
                f"Dictionary entries scanned: {stats['source_entries_scanned']:,}\n"
                f"Extended readings: {stats['total_readings']:,}\n"
                f"Extended candidates: {stats['total_candidates']:,}"
            )
        else:
            result_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Generation Failed"
            )
            result_dialog.format_secondary_text(
                "Failed to generate extended dictionary.\n"
                "Check that kanchoku layout is configured and system/user dictionaries exist."
            )

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
            user_config_dir = util.get_user_config_dir()
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
        kanchoku_dir = os.path.join(util.get_user_config_dir(), 'kanchoku_layouts')
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
        kanchoku_dir = os.path.join(util.get_user_config_dir(), 'kanchoku_layouts')
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
    """
    Run the settings panel as a standalone application.
    設定パネルをスタンドアロンアプリケーションとして実行。

    This allows testing and using the settings panel without going through
    IBus preferences. Simply run: python settings_panel.py

    これによりIBus設定を経由せずに設定パネルをテスト・使用できる。
    単純に実行: python settings_panel.py
    """
    win = SettingsPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
