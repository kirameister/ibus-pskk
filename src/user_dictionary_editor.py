#!/usr/bin/env python3
# user_dictionary_editor.py - GUI for managing user dictionary entries
#
# This module provides a GTK-based editor for the user_dictionary.json file,
# allowing users to add, view, edit, and delete kana-to-kanji mappings.
#
# Can be run standalone or imported for use with keybindings.

import json
import logging
import os
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

# Setup logging
logger = logging.getLogger(__name__)


def get_user_dictionary_path():
    """Get the path to user_dictionary.json in the config directory."""
    config_dir = os.path.join(os.path.expanduser('~'), '.config', 'ibus-pskk')
    return os.path.join(config_dir, 'user_dictionary.json')


def load_user_dictionary(path=None):
    """
    Load user dictionary from JSON file.

    Args:
        path: Path to dictionary file. If None, uses default location.

    Returns:
        dict: Dictionary data {reading: {candidate: count, ...}, ...}
    """
    if path is None:
        path = get_user_dictionary_path()

    if not os.path.exists(path):
        logger.info(f'User dictionary not found, returning empty dict: {path}')
        return {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning(f'Invalid user dictionary format, returning empty dict')
            return {}
        return data
    except json.JSONDecodeError as e:
        logger.error(f'Failed to parse user dictionary: {e}')
        return {}
    except Exception as e:
        logger.error(f'Failed to load user dictionary: {e}')
        return {}


def save_user_dictionary(data, path=None):
    """
    Save user dictionary to JSON file.

    Args:
        data: Dictionary data to save
        path: Path to dictionary file. If None, uses default location.

    Returns:
        bool: True if successful, False otherwise
    """
    if path is None:
        path = get_user_dictionary_path()

    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f'Saved user dictionary: {path}')
        return True
    except Exception as e:
        logger.error(f'Failed to save user dictionary: {e}')
        return False


def add_entry(reading, candidate, count=1, data=None, path=None):
    """
    Add a single entry to the user dictionary.

    This function can be called programmatically (e.g., from keybindings).

    Args:
        reading: The kana reading (e.g., "あい")
        candidate: The kanji candidate (e.g., "愛")
        count: Initial count/weight for the entry (default: 1)
        data: Existing dictionary data. If None, will be loaded from file.
        path: Path to dictionary file. If None, uses default location.

    Returns:
        tuple: (success: bool, data: dict) - Updated dictionary data
    """
    if data is None:
        data = load_user_dictionary(path)

    if not reading or not candidate:
        logger.warning('Cannot add entry: reading and candidate are required')
        return False, data

    # Add or update the entry
    if reading not in data:
        data[reading] = {}

    # If candidate already exists, increment count; otherwise add with given count
    if candidate in data[reading]:
        data[reading][candidate] += count
        logger.info(f'Updated entry: {reading} → {candidate} (count: {data[reading][candidate]})')
    else:
        data[reading][candidate] = count
        logger.info(f'Added entry: {reading} → {candidate} (count: {count})')

    # Save immediately
    success = save_user_dictionary(data, path)
    return success, data


def remove_entry(reading, candidate, data=None, path=None):
    """
    Remove a single entry from the user dictionary.

    Args:
        reading: The kana reading
        candidate: The kanji candidate to remove
        data: Existing dictionary data. If None, will be loaded from file.
        path: Path to dictionary file. If None, uses default location.

    Returns:
        tuple: (success: bool, data: dict) - Updated dictionary data
    """
    if data is None:
        data = load_user_dictionary(path)

    if reading not in data or candidate not in data[reading]:
        logger.warning(f'Entry not found: {reading} → {candidate}')
        return False, data

    del data[reading][candidate]
    logger.info(f'Removed entry: {reading} → {candidate}')

    # Remove reading key if no candidates left
    if not data[reading]:
        del data[reading]

    success = save_user_dictionary(data, path)
    return success, data


class UserDictionaryEditor(Gtk.Window):
    """
    GTK Window for editing the user dictionary.

    Provides a GUI for viewing, adding, editing, and deleting
    kana-to-kanji entries in user_dictionary.json.
    """

    def __init__(self, prefill_reading=None, prefill_candidate=None):
        """
        Initialize the dictionary editor window.

        Args:
            prefill_reading: Optional reading to pre-fill in the add form
            prefill_candidate: Optional candidate to pre-fill (e.g., from clipboard)
        """
        super().__init__(title="User Dictionary Editor")
        self.set_default_size(500, 400)
        self.set_border_width(10)

        # Load dictionary data
        self.dictionary_path = get_user_dictionary_path()
        self.data = load_user_dictionary(self.dictionary_path)

        # Track if changes were made
        self.modified = False

        # Build UI
        self._build_ui()

        # Pre-fill if provided
        if prefill_reading:
            self.reading_entry.set_text(prefill_reading)
        if prefill_candidate:
            self.candidate_entry.set_text(prefill_candidate)
            # Focus on add button if both are pre-filled
            if prefill_reading:
                self.add_button.grab_focus()

        # Populate the list
        self._refresh_list()

        # Connect window close
        self.connect('delete-event', self._on_close)

        # Connect ESC key to close window
        self.connect('key-press-event', self._on_key_press)

    def _on_key_press(self, widget, event):
        """Handle key press events."""
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _build_ui(self):
        """Build the window UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        # === Add Entry Section ===
        add_frame = Gtk.Frame(label="Add New Entry")
        add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_box.set_border_width(10)
        add_frame.add(add_box)

        # Reading input
        reading_label = Gtk.Label(label="Reading:")
        add_box.pack_start(reading_label, False, False, 0)

        self.reading_entry = Gtk.Entry()
        self.reading_entry.set_placeholder_text("かな")
        self.reading_entry.set_width_chars(15)
        self.reading_entry.connect('activate', self._on_add_clicked)
        add_box.pack_start(self.reading_entry, True, True, 0)

        # Arrow label
        arrow_label = Gtk.Label(label="→")
        add_box.pack_start(arrow_label, False, False, 5)

        # Candidate input
        candidate_label = Gtk.Label(label="Kanji:")
        add_box.pack_start(candidate_label, False, False, 0)

        self.candidate_entry = Gtk.Entry()
        self.candidate_entry.set_placeholder_text("漢字")
        self.candidate_entry.set_width_chars(15)
        self.candidate_entry.connect('activate', self._on_add_clicked)
        add_box.pack_start(self.candidate_entry, True, True, 0)

        # Add button
        self.add_button = Gtk.Button(label="Add")
        self.add_button.connect('clicked', self._on_add_clicked)
        add_box.pack_start(self.add_button, False, False, 0)

        main_box.pack_start(add_frame, False, False, 0)

        # === Entry List Section ===
        list_frame = Gtk.Frame(label="Dictionary Entries")
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        list_box.set_border_width(10)
        list_frame.add(list_box)

        # Search box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_label = Gtk.Label(label="Search:")
        search_box.pack_start(search_label, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Filter by reading or kanji...")
        self.search_entry.connect('changed', self._on_search_changed)
        search_box.pack_start(self.search_entry, True, True, 0)

        clear_button = Gtk.Button(label="Clear")
        clear_button.connect('clicked', lambda w: self.search_entry.set_text(''))
        search_box.pack_start(clear_button, False, False, 0)

        list_box.pack_start(search_box, False, False, 0)

        # TreeView for entries
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(200)

        # ListStore: reading, candidate, count
        self.store = Gtk.ListStore(str, str, int)
        self.filter = self.store.filter_new()
        self.filter.set_visible_func(self._filter_func)

        self.tree = Gtk.TreeView(model=self.filter)
        self.tree.set_headers_visible(True)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        # Columns
        renderer = Gtk.CellRendererText()
        col_reading = Gtk.TreeViewColumn("Reading", renderer, text=0)
        col_reading.set_sort_column_id(0)
        col_reading.set_resizable(True)
        col_reading.set_min_width(100)
        self.tree.append_column(col_reading)

        col_candidate = Gtk.TreeViewColumn("Kanji", renderer, text=1)
        col_candidate.set_sort_column_id(1)
        col_candidate.set_resizable(True)
        col_candidate.set_min_width(100)
        self.tree.append_column(col_candidate)

        col_count = Gtk.TreeViewColumn("Count", renderer, text=2)
        col_count.set_sort_column_id(2)
        col_count.set_min_width(60)
        self.tree.append_column(col_count)

        scroll.add(self.tree)
        list_box.pack_start(scroll, True, True, 0)

        # Entry count label
        self.count_label = Gtk.Label()
        self.count_label.set_xalign(0)
        list_box.pack_start(self.count_label, False, False, 0)

        # Button box for list actions
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        delete_button = Gtk.Button(label="Delete Selected")
        delete_button.connect('clicked', self._on_delete_clicked)
        button_box.pack_start(delete_button, False, False, 0)

        # Spacer
        button_box.pack_start(Gtk.Label(), True, True, 0)

        refresh_button = Gtk.Button(label="Refresh")
        refresh_button.connect('clicked', lambda w: self._refresh_list())
        button_box.pack_start(refresh_button, False, False, 0)

        list_box.pack_start(button_box, False, False, 0)

        main_box.pack_start(list_frame, True, True, 0)

        # === Bottom buttons ===
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # File path info
        path_label = Gtk.Label()
        path_label.set_markup(f"<small>{self.dictionary_path}</small>")
        path_label.set_xalign(0)
        path_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        bottom_box.pack_start(path_label, True, True, 0)

        close_button = Gtk.Button(label="Close")
        close_button.connect('clicked', lambda w: self.close())
        bottom_box.pack_end(close_button, False, False, 0)

        main_box.pack_start(bottom_box, False, False, 0)

    def _refresh_list(self):
        """Reload data from file and refresh the TreeView."""
        self.data = load_user_dictionary(self.dictionary_path)
        self.store.clear()

        total_entries = 0
        for reading, candidates in sorted(self.data.items()):
            if isinstance(candidates, dict):
                for candidate, count in sorted(candidates.items()):
                    self.store.append([reading, candidate, count])
                    total_entries += 1

        self._update_count_label(total_entries)

    def _update_count_label(self, total=None):
        """Update the entry count label."""
        if total is None:
            total = len(self.store)
        visible = len(self.filter)
        if visible == total:
            self.count_label.set_text(f"{total} entries")
        else:
            self.count_label.set_text(f"Showing {visible} of {total} entries")

    def _filter_func(self, model, iter, data=None):
        """Filter function for the TreeView."""
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True

        reading = model[iter][0].lower()
        candidate = model[iter][1].lower()
        return search_text in reading or search_text in candidate

    def _on_search_changed(self, entry):
        """Handle search text change."""
        self.filter.refilter()
        self._update_count_label(len(self.store))

    def _on_add_clicked(self, widget):
        """Handle add button click."""
        reading = self.reading_entry.get_text().strip()
        candidate = self.candidate_entry.get_text().strip()

        if not reading:
            self._show_error("Please enter a reading (kana).")
            self.reading_entry.grab_focus()
            return

        if not candidate:
            self._show_error("Please enter a kanji candidate.")
            self.candidate_entry.grab_focus()
            return

        # Add the entry
        success, self.data = add_entry(reading, candidate, count=1,
                                        data=self.data, path=self.dictionary_path)

        if success:
            # Set search field to the reading so user can see the added entry
            self.search_entry.set_text(reading)

            # Clear inputs
            self.reading_entry.set_text('')
            self.candidate_entry.set_text('')
            self.reading_entry.grab_focus()

            # Refresh list
            self._refresh_list()
            self.modified = True
        else:
            self._show_error("Failed to add entry. Check the log for details.")

    def _on_delete_clicked(self, widget):
        """Handle delete button click."""
        selection = self.tree.get_selection()
        model, paths = selection.get_selected_rows()

        if not paths:
            self._show_error("Please select entries to delete.")
            return

        # Confirm deletion
        count = len(paths)
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete {count} selected entry(s)?"
        )
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        # Collect entries to delete (need to get from filter model)
        to_delete = []
        for path in paths:
            iter = model.get_iter(path)
            reading = model.get_value(iter, 0)
            candidate = model.get_value(iter, 1)
            to_delete.append((reading, candidate))

        # Delete entries
        for reading, candidate in to_delete:
            success, self.data = remove_entry(reading, candidate,
                                               data=self.data, path=self.dictionary_path)

        self._refresh_list()
        self.modified = True

    def _on_close(self, widget, event):
        """Handle window close."""
        # Just close, changes are saved immediately
        return False

    def _show_error(self, message):
        """Show an error dialog."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()


def open_editor(prefill_reading=None, prefill_candidate=None, check_clipboard=True):
    """
    Open the dictionary editor window.

    This function can be called from keybindings or other parts of the IME.

    Args:
        prefill_reading: Optional reading to pre-fill
        prefill_candidate: Optional candidate to pre-fill (e.g., from clipboard)
        check_clipboard: If True and prefill_candidate is None, check clipboard
                        for candidate text (default: True)

    Returns:
        UserDictionaryEditor: The editor window instance
    """
    # Auto-fill candidate from clipboard if not provided
    if prefill_candidate is None and check_clipboard:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard_text = clipboard.wait_for_text()
        if clipboard_text and clipboard_text.strip():
            prefill_candidate = clipboard_text.strip()
            logger.info(f'Pre-filled candidate from clipboard: "{prefill_candidate}"')

    editor = UserDictionaryEditor(
        prefill_reading=prefill_reading,
        prefill_candidate=prefill_candidate
    )
    editor.show_all()
    return editor


def register_from_clipboard(reading):
    """
    Register a new entry using clipboard content as the candidate.

    This is the "Option 3" workflow:
    1. User copies kanji from somewhere
    2. User has a reading in preedit
    3. User presses keybinding
    4. Entry is registered automatically

    Args:
        reading: The kana reading to register

    Returns:
        tuple: (success: bool, candidate: str or None)
    """
    if not reading:
        logger.warning('Cannot register from clipboard: no reading provided')
        return False, None

    # Get clipboard content
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    candidate = clipboard.wait_for_text()

    if not candidate:
        logger.warning('Cannot register from clipboard: clipboard is empty')
        return False, None

    candidate = candidate.strip()
    if not candidate:
        logger.warning('Cannot register from clipboard: clipboard contains only whitespace')
        return False, None

    # Add the entry
    success, _ = add_entry(reading, candidate)
    return success, candidate if success else None


def main():
    """Main entry point for standalone execution."""
    # Setup logging for standalone mode
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Check for command-line arguments
    prefill_reading = None
    prefill_candidate = None

    if len(sys.argv) > 1:
        prefill_reading = sys.argv[1]
    if len(sys.argv) > 2:
        prefill_candidate = sys.argv[2]

    # Create and show editor
    editor = open_editor(prefill_reading, prefill_candidate)
    editor.connect('destroy', Gtk.main_quit)

    Gtk.main()


if __name__ == '__main__':
    main()
