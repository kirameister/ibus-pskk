#!/usr/bin/env python3
# ui/conversion_model.py - Conversion Model Panel for IBus-PSKK
"""
CRF-based bunsetsu (文節) segmentation model trainer and tester.

This module trains a Conditional Random Field model to predict bunsetsu
boundaries in Japanese text. The model uses character-level features
including character identity, character type, surrounding context,
particle/auxiliary verb detection, and dictionary lookups.

IMPORTANT: Training Data Format
-------------------------------
Training data must be in HIRAGANA (yomi/reading), not kanji-kana mixture.
This is because at inference time, the model receives the user's typed
hiragana input (before kana-to-kanji conversion), so training on kanji
would create a domain mismatch.

Two annotation formats are supported:

1. Simple format (B/I labels only):
   Space-delimited bunsetsu, no type distinction.

       きょうは てんきが よい

   Use parse_training_line() for this format.

2. Annotated format (B-L/I-L/B-P/I-P labels):
   Space-delimited bunsetsu with underscore markers for passthrough segments.
   Bunsetsu starting or ending with '_' are Passthrough (output as-is).
   Bunsetsu without '_' are Lookup (send to dictionary for conversion).

       きょう _は_ てんき _が_ よい

   Labels:
     B-L = Beginning of Lookup bunsetsu (needs kana→kanji conversion)
     I-L = Inside of Lookup bunsetsu
     B-P = Beginning of Passthrough bunsetsu (output as-is, e.g., particles)
     I-P = Inside of Passthrough bunsetsu

   Use parse_annotated_line() for this format.

Incorrect format (kanji - do NOT use):
    今日は 天気が 良い

If you have a kanji-annotated corpus, convert it to readings first
using the dictionary or a morphological analyzer like MeCab.
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

try:
    import pycrfsuite
    HAS_CRFSUITE = True
except ImportError:
    HAS_CRFSUITE = False
    logger.warning('pycrfsuite not installed. Training will be unavailable.')


# ─── 助詞 / 助動詞 sets ──────────────────────────────────────────────

JOSHI = {
    # 格助詞
    'が', 'を', 'に', 'へ', 'で', 'と', 'から', 'より', 'まで',
    # 接続助詞
    'て', 'ば', 'けど', 'けれど', 'けれども', 'ながら', 'のに', 'ので', 'たり', 'し',
    # 副助詞
    'は', 'も', 'こそ', 'さえ', 'でも', 'しか', 'ばかり', 'だけ', 'ほど',
    'くらい', 'ぐらい', 'など', 'なり', 'やら',
    # 終助詞
    'か', 'よ', 'ね', 'な', 'ぞ', 'わ', 'さ',
    # 連体助詞 / 並列助詞
    'の', 'や',
}

JODOUSHI = {
    'れる', 'られる', 'せる', 'させる',
    'ない', 'たい', 'た', 'だ',
    'ます', 'です',
    'う', 'よう', 'まい',
    'らしい',
}

JOSHI_MAX_LEN = max(len(w) for w in JOSHI)
JODOUSHI_MAX_LEN = max(len(w) for w in JODOUSHI)


# ─── Feature extraction ──────────────────────────────────────────────

def char_type(c):
    """Classify a character into its Unicode block type."""
    cp = ord(c)
    if 0x3040 <= cp <= 0x309F:
        return 'hiragana'
    elif 0x30A0 <= cp <= 0x30FF:
        return 'katakana'
    elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
        return 'kanji'
    elif 0x0020 <= cp <= 0x007E:
        return 'ascii'
    else:
        return 'other'


def parse_training_line(line):
    """Parse a space-delimited line into characters and BI tags.

    IMPORTANT: Training data must be in hiragana (yomi/reading), not kanji,
    because the model will be applied to hiragana input at inference time.

    Example: "きょうは てんきが よい"
      → chars: ['き', 'ょ', 'う', 'は', 'て', 'ん', 'き', 'が', 'よ', 'い']
      → tags:  ['B',  'I',  'I',  'I',  'B',  'I',  'I',  'I',  'B',  'I']

    Each space marks a bunsetsu boundary. The first character of each
    bunsetsu is tagged 'B' (begin), all others are tagged 'I' (inside).
    """
    line = line.strip()
    if not line:
        return [], []

    bunsetsu_list = line.split()
    chars = []
    tags = []
    for bunsetsu in bunsetsu_list:
        for i, c in enumerate(bunsetsu):
            chars.append(c)
            tags.append('B' if i == 0 else 'I')
    return chars, tags


def parse_annotated_line(line):
    """Parse an annotated line into characters and 4-class labels.

    Annotation format: Space-delimited bunsetsu with underscore markers.
    Bunsetsu starting or ending with '_' are Passthrough (no dictionary lookup).
    Bunsetsu without '_' are Lookup (send to dictionary for conversion).

    Labels:
        B-L = Beginning of Lookup bunsetsu (needs kana→kanji conversion)
        I-L = Inside of Lookup bunsetsu
        B-P = Beginning of Passthrough bunsetsu (output as-is)
        I-P = Inside of Passthrough bunsetsu

    Example: "きょう _は_ てんき _が_ よい"
      → chars: ['き', 'ょ', 'う', 'は', 'て', 'ん', 'き', 'が', 'よ', 'い']
      → tags:  ['B-L', 'I-L', 'I-L', 'B-P', 'B-L', 'I-L', 'I-L', 'B-P', 'B-L', 'I-L']

    Multi-char passthrough example: "いく _から_"
      → chars: ['い', 'く', 'か', 'ら']
      → tags:  ['B-L', 'I-L', 'B-P', 'I-P']

    Args:
        line: Annotated line with space-delimited bunsetsu

    Returns:
        Tuple of (chars, tags) where chars is list of characters
        and tags is list of labels (B-L, I-L, B-P, I-P)
    """
    line = line.strip()
    if not line:
        return [], []

    bunsetsu_list = line.split()
    chars = []
    tags = []

    for bunsetsu in bunsetsu_list:
        # Check if this bunsetsu is marked as passthrough
        is_passthrough = bunsetsu.startswith('_') or bunsetsu.endswith('_')

        # Strip underscore markers to get actual text
        text = bunsetsu.strip('_')

        if not text:
            # Edge case: bunsetsu was just underscores, skip
            continue

        # Determine label suffix based on type
        suffix = 'P' if is_passthrough else 'L'

        for i, c in enumerate(text):
            chars.append(c)
            tags.append(f'B-{suffix}' if i == 0 else f'I-{suffix}')

    return chars, tags


def extract_char_features(chars, i, dictionary_readings=None):
    """Extract CRF features for a single character at position i."""
    c = chars[i]
    ct = char_type(c)
    n = len(chars)
    features = [
        'bias',
        f'char={c}',
        f'type={ct}',
    ]

    # ── Character identity window [-2, +2] ──
    if i >= 1:
        features.extend([
            f'char[-1]={chars[i-1]}',
            f'type[-1]={char_type(chars[i-1])}',
            f'bigram[-1:0]={chars[i-1]}{c}',
            f'type_change={char_type(chars[i-1]) != ct}',
        ])
    else:
        features.append('BOS')

    if i >= 2:
        features.extend([
            f'char[-2]={chars[i-2]}',
            f'type[-2]={char_type(chars[i-2])}',
        ])

    if i < n - 1:
        features.extend([
            f'char[+1]={chars[i+1]}',
            f'type[+1]={char_type(chars[i+1])}',
            f'bigram[0:+1]={c}{chars[i+1]}',
        ])
    else:
        features.append('EOS')

    if i < n - 2:
        features.extend([
            f'char[+2]={chars[i+2]}',
            f'type[+2]={char_type(chars[i+2])}',
        ])

    # ── 助詞 / 助動詞 (substrings ending at position i) ──
    for length in range(1, min(i + 1, JOSHI_MAX_LEN) + 1):
        substr = ''.join(chars[i - length + 1:i + 1])
        if substr in JOSHI:
            features.append(f'joshi={substr}')
        if length <= JODOUSHI_MAX_LEN and substr in JODOUSHI:
            features.append(f'jodoushi={substr}')

    # ── Dictionary lookup ──
    if dictionary_readings:
        # Check if any dictionary reading starts at this position
        for length in range(2, min(n - i, 10) + 1):
            substr = ''.join(chars[i:i + length])
            if substr in dictionary_readings:
                features.append(f'dict_start_len={length}')
                break

        # Check if any dictionary reading ends at this position
        for length in range(2, min(i + 1, 10) + 1):
            substr = ''.join(chars[i - length + 1:i + 1])
            if substr in dictionary_readings:
                features.append(f'dict_end_len={length}')
                break

    return features


def extract_features(chars, dictionary_readings=None):
    """Extract CRF features for an entire character sequence."""
    return [extract_char_features(chars, i, dictionary_readings)
            for i in range(len(chars))]


# ─── Dictionary reading loader ────────────────────────────────────────

def load_dictionary_readings():
    """Load all readings (keys) from system/user dictionaries as a set."""
    readings = set()
    config_dir = util.get_user_config_dir()
    for filename in ['system_dictionary.json', 'user_dictionary.json']:
        path = os.path.join(config_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            readings.update(data.keys())
            logger.info(f'Loaded {len(data)} readings from {filename}')
        except Exception as e:
            logger.warning(f'Failed to load {path}: {e}')
    return readings


def get_model_path():
    """Return the canonical path to the bunsetsu CRF model file."""
    return os.path.join(util.get_user_config_dir(), 'bunsetsu.crfsuite')


# ─── GTK Panel ────────────────────────────────────────────────────────

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

        # ── Training Corpus ──
        corpus_frame = Gtk.Frame(label="Training Corpus")
        corpus_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        corpus_box.set_border_width(10)
        corpus_frame.add(corpus_box)

        corpus_info = Gtk.Label()
        corpus_info.set_markup(
            "<small>Space-delimited bunsetsu in <b>hiragana</b>, one sentence per line.\n"
            "Example: \"きょうは てんきが よい\"\n"
            "(Use hiragana because the model predicts boundaries on yomi input.)</small>"
        )
        corpus_info.set_xalign(0)
        corpus_box.pack_start(corpus_info, False, False, 0)

        corpus_row = Gtk.Box(spacing=6)
        self.corpus_path_entry = Gtk.Entry()
        self.corpus_path_entry.set_placeholder_text("Path to training corpus file...")
        corpus_row.pack_start(self.corpus_path_entry, True, True, 0)

        browse_corpus_btn = Gtk.Button(label="Browse")
        browse_corpus_btn.connect("clicked", self.on_browse_corpus)
        corpus_row.pack_start(browse_corpus_btn, False, False, 0)

        corpus_box.pack_start(corpus_row, False, False, 0)

        self.corpus_stats_label = Gtk.Label()
        self.corpus_stats_label.set_xalign(0)
        corpus_box.pack_start(self.corpus_stats_label, False, False, 0)

        box.pack_start(corpus_frame, False, False, 0)

        # ── Train Button ──
        train_btn = Gtk.Button(label="Train")
        train_btn.connect("clicked", self.on_train)
        box.pack_start(train_btn, False, False, 0)

        # ── Training Log ──
        log_frame = Gtk.Frame(label="Training Log")
        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        log_box.set_border_width(10)
        log_frame.add(log_box)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(200)
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        log_scroll.add(self.log_view)
        log_box.pack_start(log_scroll, True, True, 0)

        box.pack_start(log_frame, True, True, 0)

        return box

    # ── Callbacks ─────────────────────────────────────────────────────

    def _log(self, text):
        """Append a line to the training log view."""
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text + '\n')
        # Auto-scroll to bottom
        mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
        self.log_view.scroll_mark_onscreen(mark)
        self.log_buffer.delete_mark(mark)
        # Flush GTK events so the UI updates
        while Gtk.events_pending():
            Gtk.main_iteration()

    def on_browse_corpus(self, button):
        """Open file chooser for training corpus"""
        dialog = Gtk.FileChooserDialog(
            title="Select Training Corpus",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        txt_filter = Gtk.FileFilter()
        txt_filter.set_name("Text files")
        txt_filter.add_pattern("*.txt")
        dialog.add_filter(txt_filter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name("All files")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            self.corpus_path_entry.set_text(path)
            self._preview_corpus(path)
        dialog.destroy()

    def _preview_corpus(self, path):
        """Load corpus and show stats."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.corpus_stats_label.set_text(f"Error reading file: {e}")
            return

        sentence_count = 0
        total_chars = 0
        total_bunsetsu = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            bunsetsu_list = line.split()
            sentence_count += 1
            total_bunsetsu += len(bunsetsu_list)
            total_chars += sum(len(b) for b in bunsetsu_list)

        self.corpus_stats_label.set_markup(
            f"<b>{sentence_count:,}</b> sentences, "
            f"<b>{total_bunsetsu:,}</b> bunsetsu, "
            f"<b>{total_chars:,}</b> characters"
        )

    def on_train(self, button):
        """Run CRF training on the loaded corpus."""
        if not HAS_CRFSUITE:
            dialog = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="pycrfsuite not installed",
            )
            dialog.format_secondary_text(
                "Install with: pip install python-crfsuite"
            )
            dialog.run()
            dialog.destroy()
            return

        corpus_path = self.corpus_path_entry.get_text().strip()
        model_path = get_model_path()

        if not corpus_path or not os.path.exists(corpus_path):
            self._log("ERROR: No valid corpus file selected.")
            return

        self.log_buffer.set_text('')  # Clear log
        self._log("=== CRF Bunsetsu Segmentation Training ===")
        self._log("")

        # ── Load corpus ──
        self._log(f"Loading corpus: {corpus_path}")
        try:
            with open(corpus_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self._log(f"ERROR: Failed to read corpus: {e}")
            return

        sentences = []
        for line in lines:
            chars, tags = parse_training_line(line)
            if chars:
                sentences.append((chars, tags))

        self._log(f"Parsed {len(sentences):,} sentences")

        if not sentences:
            self._log("ERROR: No valid sentences found in corpus.")
            return

        # ── Load dictionary readings ──
        self._log("Loading dictionary readings for feature extraction...")
        dictionary_readings = load_dictionary_readings()
        self._log(f"Loaded {len(dictionary_readings):,} dictionary readings")

        # ── Extract features ──
        self._log("Extracting features...")
        X_train = []
        y_train = []
        for chars, tags in sentences:
            X_train.append(extract_features(chars, dictionary_readings))
            y_train.append(tags)

        total_tokens = sum(len(seq) for seq in X_train)
        self._log(f"Feature extraction complete: {total_tokens:,} tokens")

        # ── Train CRF ──
        self._log("")
        self._log("Training CRF model (L-BFGS)...")
        self._log("This may take a while for large corpora.")
        self._log("")

        trainer = pycrfsuite.Trainer(verbose=False)
        for xseq, yseq in zip(X_train, y_train):
            trainer.append(xseq, yseq)

        trainer.set_params({
            'c1': 1.0,        # L1 regularization
            'c2': 1e-3,       # L2 regularization
            'max_iterations': 100,
            'feature.possible_transitions': True,
        })

        trainer.train(model_path)

        self._log("Training complete.")
        self._log(f"Model saved to: {model_path}")
        self._log("")

        # ── Show training summary ──
        self._log("--- Training Summary ---")
        info = trainer.logparser.last_iteration
        if info:
            self._log(f"  Last iteration:  {info.get('num', '?')}")
            self._log(f"  Loss:            {info.get('loss', '?')}")
            self._log(f"  Feature count:   {info.get('feature_count', '?')}")

        model_size = os.path.getsize(model_path)
        self._log(f"  Model file size: {model_size:,} bytes")
        self._log(f"  Sentences:       {len(sentences):,}")
        self._log(f"  Tokens:          {total_tokens:,}")
        self._log("")
        self._log("Done.")


def main():
    """Run conversion model panel standalone"""
    win = ConversionModelPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
