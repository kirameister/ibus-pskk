#!/usr/bin/env python3
"""
user_dictionary_editor.py - GUI for managing user dictionary entries
ユーザー辞書エントリを管理するためのGUI

================================================================================
WHAT THIS FILE DOES / このファイルの役割
================================================================================

This module provides a GTK-based editor for the user_dictionary.json file.
It allows users to add, view, edit, and delete kana-to-kanji mappings that
personalize their input method experience.

このモジュールはuser_dictionary.jsonファイル用のGTKベースのエディタを提供する。
ユーザーは入力メソッドの体験を個人化するために、かな漢字マッピングの
追加、表示、編集、削除ができる。

================================================================================
WHY USER DICTIONARIES? / なぜユーザー辞書が必要か？
================================================================================

System dictionaries contain common words, but they can't know:
システム辞書は一般的な単語を含むが、以下は知らない:

    - Your name and the names of people you write to
      あなたの名前やよく書く人の名前
    - Technical terms specific to your work
      あなたの仕事に固有の専門用語
    - Slang or neologisms you frequently use
      よく使うスラングや新語
    - Unusual readings for kanji in proper nouns
      固有名詞での漢字の特殊な読み

The user dictionary fills this gap by storing YOUR personal word choices.
ユーザー辞書はあなた個人の単語選択を保存してこのギャップを埋める。

================================================================================
HOW TO USE / 使用方法
================================================================================

There are THREE ways to use this module:
このモジュールを使う方法は3つ:

    1. STANDALONE MODE (スタンドアロンモード)
       ─────────────────────────────────────────
       Run directly from command line:
       コマンドラインから直接実行:

           python user_dictionary_editor.py [reading] [candidate]

       Example: python user_dictionary_editor.py "たなか" "田中"
       例: python user_dictionary_editor.py "たなか" "田中"

    2. FROM SETTINGS PANEL (設定パネルから)
       ─────────────────────────────────────────
       Open Settings → User Dictionary tab → "Open Editor" button
       設定を開く → ユーザー辞書タブ → 「エディタを開く」ボタン

    3. VIA KEYBINDING (キーバインド経由)
       ─────────────────────────────────────────
       Press the configured hotkey (e.g., Ctrl+Shift+R) while typing.
       入力中に設定されたホットキー（例: Ctrl+Shift+R）を押す。
       - If you have text in clipboard, it becomes the candidate
         クリップボードにテキストがあれば、それが候補になる
       - The current preedit becomes the reading
         現在のプリエディットが読みになる

================================================================================
DATA FORMAT / データ形式
================================================================================

The user dictionary is stored as JSON in:
ユーザー辞書は以下にJSONとして保存:

    ~/.config/ibus-pskk/user_dictionary.json

Format:
形式:
    {
      "reading1": {
        "candidate1": count,
        "candidate2": count,
        ...
      },
      "reading2": {
        ...
      }
    }

Example:
例:
    {
      "たなか": {
        "田中": 5,
        "棚下": 1
      },
      "ひろし": {
        "博": 3,
        "宏": 2
      }
    }

The "count" value represents usage frequency - higher counts mean the
candidate appears earlier in the suggestion list.
「count」値は使用頻度を表す - 高いカウントは候補が提案リストの上位に表示される。

================================================================================
MODULE STRUCTURE / モジュール構造
================================================================================

    UTILITY FUNCTIONS (standalone-safe):
    ユーティリティ関数（スタンドアロン安全）:
        - get_user_dictionary_path()  → Get default file path
        - load_user_dictionary()      → Load from JSON
        - save_user_dictionary()      → Save to JSON
        - add_entry()                 → Add a single entry
        - remove_entry()              → Remove a single entry

    GUI CLASS:
    GUIクラス:
        - UserDictionaryEditor       → GTK window for editing

    INTEGRATION FUNCTIONS (for use from IME):
    統合関数（IMEからの使用用）:
        - open_editor()              → Open editor window
        - register_from_clipboard()  → Quick registration workflow

================================================================================
"""

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
    """
    Get the path to user_dictionary.json in the config directory.
    設定ディレクトリ内のuser_dictionary.jsonへのパスを取得。

    Returns:
        str: Full path to the user dictionary file.
             ユーザー辞書ファイルへのフルパス。
             Example: "/home/user/.config/ibus-pskk/user_dictionary.json"
    """
    config_dir = os.path.join(os.path.expanduser('~'), '.config', 'ibus-pskk')
    return os.path.join(config_dir, 'user_dictionary.json')


def load_user_dictionary(path=None):
    """
    Load user dictionary from JSON file.
    JSONファイルからユーザー辞書を読み込む。

    Reads the user dictionary file and returns its contents as a nested dict.
    Handles missing files gracefully by returning an empty dict.
    ユーザー辞書ファイルを読み取り、内容をネストされた辞書として返す。
    ファイルが見つからない場合は空の辞書を返して適切に処理する。

    Args:
        path: Path to dictionary file. If None, uses default location.
              辞書ファイルへのパス。Noneの場合はデフォルトの場所を使用。

    Returns:
        dict: Dictionary data in format {reading: {candidate: count, ...}, ...}
              形式 {読み: {候補: カウント, ...}, ...} の辞書データ

    Example:
        >>> data = load_user_dictionary()
        >>> data
        {'たなか': {'田中': 5, '棚下': 1}}
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
    ユーザー辞書をJSONファイルに保存。

    Writes the dictionary data to a JSON file with UTF-8 encoding.
    Creates the parent directory if it doesn't exist.
    辞書データをUTF-8エンコーディングでJSONファイルに書き込む。
    親ディレクトリが存在しない場合は作成する。

    Args:
        data: Dictionary data to save (nested dict format).
              保存する辞書データ（ネストされた辞書形式）。
        path: Path to dictionary file. If None, uses default location.
              辞書ファイルへのパス。Noneの場合はデフォルトの場所を使用。

    Returns:
        bool: True if successful, False otherwise.
              成功時True、それ以外False。
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
    ユーザー辞書に単一エントリを追加。

    This function can be called programmatically (e.g., from keybindings)
    to register new words without opening the GUI editor.
    この関数はプログラムから（例えばキーバインドから）呼び出して、
    GUIエディタを開かずに新しい単語を登録できる。

    If the entry already exists, its count is incremented rather than
    creating a duplicate.
    エントリが既に存在する場合、重複を作成せずにカウントが増加される。

    Args:
        reading: The kana reading (e.g., "あい").
                 かなの読み（例: "あい"）。
        candidate: The kanji candidate (e.g., "愛").
                   漢字の候補（例: "愛"）。
        count: Initial count/weight for the entry (default: 1).
               エントリの初期カウント/重み（デフォルト: 1）。
        data: Existing dictionary data. If None, will be loaded from file.
              既存の辞書データ。Noneの場合はファイルから読み込む。
        path: Path to dictionary file. If None, uses default location.
              辞書ファイルへのパス。Noneの場合はデフォルトの場所を使用。

    Returns:
        tuple: (success: bool, data: dict) - Success flag and updated data.
               (成功: bool, データ: dict) - 成功フラグと更新されたデータ。

    Example:
        >>> success, data = add_entry("たなか", "田中")
        >>> success
        True
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
    ユーザー辞書から単一エントリを削除。

    Removes a specific reading→candidate mapping. If the reading has no
    more candidates after removal, the reading key itself is also deleted.
    特定の読み→候補マッピングを削除する。削除後に読みに候補がなくなった場合、
    読みのキー自体も削除される。

    Args:
        reading: The kana reading.
                 かなの読み。
        candidate: The kanji candidate to remove.
                   削除する漢字の候補。
        data: Existing dictionary data. If None, will be loaded from file.
              既存の辞書データ。Noneの場合はファイルから読み込む。
        path: Path to dictionary file. If None, uses default location.
              辞書ファイルへのパス。Noneの場合はデフォルトの場所を使用。

    Returns:
        tuple: (success: bool, data: dict) - Success flag and updated data.
               (成功: bool, データ: dict) - 成功フラグと更新されたデータ。
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
    ユーザー辞書を編集するためのGTKウィンドウ。

    ============================================================================
    OVERVIEW / 概要
    ============================================================================

    Provides a graphical interface for managing user_dictionary.json.
    Users can add, view, search, edit counts, and delete entries without
    manually editing the JSON file.

    user_dictionary.jsonを管理するためのグラフィカルインターフェースを提供。
    ユーザーはJSONファイルを手動で編集せずに、エントリの追加、表示、
    検索、カウント編集、削除ができる。

    ============================================================================
    WINDOW LAYOUT / ウィンドウレイアウト
    ============================================================================

        ┌─────────────────────────────────────────────────────────────────────┐
        │  User Dictionary Editor                                    [─][□][×]│
        ├─────────────────────────────────────────────────────────────────────┤
        │  ┌─ Add New Entry ────────────────────────────────────────────────┐ │
        │  │  Reading: [かな入力  ] → Kanji: [漢字入力  ]  [Add]            │ │
        │  └────────────────────────────────────────────────────────────────┘ │
        │  ┌─ Dictionary Entries ───────────────────────────────────────────┐ │
        │  │  Search: [フィルタ入力...                        ] [Clear]     │ │
        │  │  ┌────────────┬────────────┬───────┐                          │ │
        │  │  │ Reading    │ Kanji      │ Count │  ← Sortable columns      │ │
        │  │  ├────────────┼────────────┼───────┤                          │ │
        │  │  │ たなか     │ 田中       │   5   │  ← Count is editable     │ │
        │  │  │ たなか     │ 棚下       │   1   │                          │ │
        │  │  │ ひろし     │ 博         │   3   │                          │ │
        │  │  └────────────┴────────────┴───────┘                          │ │
        │  │  5 entries                                                     │ │
        │  │  [Delete Selected]                              [Refresh]      │ │
        │  └────────────────────────────────────────────────────────────────┘ │
        │  ~/.config/ibus-pskk/user_dictionary.json                  [Close]  │
        └─────────────────────────────────────────────────────────────────────┘

    ============================================================================
    FEATURES / 機能
    ============================================================================

    - ADD ENTRIES: Type reading and kanji, press Enter or click Add
      エントリ追加: 読みと漢字を入力し、Enterを押すか追加をクリック

    - SEARCH/FILTER: Type in search box to filter displayed entries
      検索/フィルタ: 検索ボックスに入力して表示エントリをフィルタ

    - EDIT COUNT: Click on the count cell to edit priority/weight
      カウント編集: カウントセルをクリックして優先度/重みを編集

    - DELETE: Select rows (Ctrl+click for multiple) and click Delete
      削除: 行を選択（複数はCtrl+クリック）して削除をクリック

    - SORT: Click column headers to sort by reading, kanji, or count
      ソート: 列ヘッダーをクリックして読み、漢字、カウントでソート

    ============================================================================
    ATTRIBUTES / 属性
    ============================================================================

    dictionary_path : str
        Full path to the user_dictionary.json file.
        user_dictionary.jsonファイルへのフルパス。

    data : dict
        In-memory copy of the dictionary data.
        辞書データのメモリ内コピー。

    modified : bool
        Whether changes have been made (for potential future use).
        変更が行われたかどうか（将来の使用のため）。

    store : Gtk.ListStore
        The data model backing the TreeView.
        TreeViewをバックするデータモデル。

    ============================================================================
    """

    def __init__(self, prefill_reading=None, prefill_candidate=None):
        """
        Initialize the dictionary editor window.
        辞書エディタウィンドウを初期化。

        Creates the window, loads dictionary data, builds the UI, and
        optionally pre-fills the add form with provided values.
        ウィンドウを作成し、辞書データを読み込み、UIを構築し、
        オプションで提供された値で追加フォームを事前入力する。

        Args:
            prefill_reading: Optional reading to pre-fill in the add form.
                             追加フォームに事前入力するオプションの読み。
            prefill_candidate: Optional candidate to pre-fill (e.g., from clipboard).
                               事前入力するオプションの候補（例: クリップボードから）。
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
            # Focus on candidate entry with text selected, so user can
            # easily replace clipboard content by typing
            self.candidate_entry.grab_focus()
            self.candidate_entry.select_region(0, -1)  # Select all text
        elif prefill_reading:
            # Reading is pre-filled but not candidate: focus on candidate entry
            # so user can type the kanji directly
            self.candidate_entry.grab_focus()

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
        """
        Build the window UI components.
        ウィンドウのUIコンポーネントを構築。

        Creates the following structure:
        以下の構造を作成:
            - Add Entry frame (reading/candidate inputs + Add button)
              エントリ追加フレーム（読み/候補入力 + 追加ボタン）
            - Entry List frame (search box + TreeView + action buttons)
              エントリリストフレーム（検索ボックス + ツリービュー + アクションボタン）
            - Bottom bar (file path display + Close button)
              下部バー（ファイルパス表示 + 閉じるボタン）
        """
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

        # Count column is editable
        count_renderer = Gtk.CellRendererText()
        count_renderer.set_property('editable', True)
        count_renderer.connect('edited', self._on_count_edited)
        col_count = Gtk.TreeViewColumn("Count", count_renderer, text=2)
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
        """
        Reload data from file and refresh the TreeView.
        ファイルからデータを再読み込みしTreeViewを更新。

        Called after add/delete operations to ensure the display is in sync
        with the file. Also updates the entry count label.
        追加/削除操作後に呼ばれ、表示がファイルと同期していることを確認。
        エントリカウントラベルも更新する。
        """
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
        """
        Handle add button click or Enter key in entry fields.
        追加ボタンのクリックまたはエントリフィールドでのEnterキーを処理。

        Validates inputs, adds the entry to the dictionary, saves to file,
        and refreshes the display. After successful add, sets the search
        filter to show the newly added entry.
        入力を検証し、エントリを辞書に追加し、ファイルに保存し、表示を更新する。
        追加が成功したら、新しく追加されたエントリを表示するように検索フィルタを設定。
        """
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
        """
        Handle delete button click.
        削除ボタンのクリックを処理。

        Gets selected rows, shows confirmation dialog, then deletes each
        selected entry and refreshes the display. Supports multi-selection.
        選択された行を取得し、確認ダイアログを表示し、選択された各エントリを
        削除して表示を更新する。複数選択をサポート。
        """
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

    def _on_count_edited(self, renderer, path, new_text):
        """
        Handle count cell edit in the TreeView.
        TreeViewでのカウントセル編集を処理。

        Validates the new count (must be positive integer), updates the
        in-memory data, saves to file, and updates the display.
        新しいカウントを検証（正の整数でなければならない）し、メモリ内データを
        更新し、ファイルに保存し、表示を更新する。

        Higher counts make candidates appear earlier in suggestions.
        高いカウントは候補が提案の上位に表示されるようにする。

        Args:
            renderer: The CellRenderer (unused).
            path: Tree path to the edited cell.
            new_text: The user's input text.
        """
        # Validate: must be a positive integer
        try:
            new_count = int(new_text)
            if new_count < 1:
                self._show_error("Count must be at least 1.")
                return
        except ValueError:
            self._show_error("Please enter a valid number.")
            return

        # Get the row from the filter model, then convert to store path
        filter_iter = self.filter.get_iter(path)
        store_iter = self.filter.convert_iter_to_child_iter(filter_iter)

        # Get reading and candidate from store
        reading = self.store.get_value(store_iter, 0)
        candidate = self.store.get_value(store_iter, 1)

        # Update the data structure
        if reading in self.data and candidate in self.data[reading]:
            self.data[reading][candidate] = new_count

            # Save to file
            if save_user_dictionary(self.data, self.dictionary_path):
                # Update the store (display)
                self.store.set_value(store_iter, 2, new_count)
                self.modified = True
                logger.info(f'Updated count: {reading} → {candidate} = {new_count}')
            else:
                self._show_error("Failed to save changes.")

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
    辞書エディタウィンドウを開く。

    This is the primary function for launching the editor from other parts
    of the IME (e.g., from a keybinding or the settings panel).
    これはIMEの他の部分（例えばキーバインドや設定パネルから）から
    エディタを起動するための主要な関数。

    If check_clipboard is True and no candidate is provided, automatically
    checks the clipboard for text to use as the candidate.
    check_clipboardがTrueで候補が提供されていない場合、自動的に
    クリップボードのテキストを候補として使用するかチェックする。

    Args:
        prefill_reading: Optional reading to pre-fill in the add form.
                         追加フォームに事前入力するオプションの読み。
        prefill_candidate: Optional candidate to pre-fill.
                           事前入力するオプションの候補。
        check_clipboard: If True and prefill_candidate is None, check clipboard
                         for candidate text (default: True).
                         Trueでprefill_candidateがNoneの場合、クリップボードを
                         候補テキストとしてチェック（デフォルト: True）。

    Returns:
        UserDictionaryEditor: The editor window instance.
                              エディタウィンドウのインスタンス。

    Example (from keybinding handler):
        >>> editor = open_editor(prefill_reading=current_preedit)
        >>> editor.show_all()
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


def main():
    """
    Main entry point for standalone execution.
    スタンドアロン実行のメインエントリーポイント。

    Usage / 使用方法:
        python user_dictionary_editor.py [reading] [candidate]

    Examples / 例:
        python user_dictionary_editor.py                    # Open empty editor
        python user_dictionary_editor.py "たなか"           # Pre-fill reading
        python user_dictionary_editor.py "たなか" "田中"    # Pre-fill both
    """
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
