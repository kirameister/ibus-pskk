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


# ─── Tokenization and Feature Extraction (New Modular System) ─────────

def tokenize_line(line):
    """Tokenize a line with mixed ASCII/non-ASCII handling.

    Tokenization rules:
    - Non-ASCII characters (hiragana, kanji, etc.): each character is a token
    - ASCII words (consecutive letters/digits): each word is a single token
    - Spaces are skipped (used only as delimiters)
    - ASCII punctuation: each is a separate token

    Example: "きょうは sunny day"
      → ['き', 'ょ', 'う', 'は', 'sunny', 'day']

    Example: "きょうはsunny"
      → ['き', 'ょ', 'う', 'は', 'sunny']

    Args:
        line: Input string (underscores should already be stripped)

    Returns:
        List of tokens
    """
    tokens = []
    ascii_buffer = []

    def flush_ascii_buffer():
        """Flush accumulated ASCII characters as a single token."""
        if ascii_buffer:
            tokens.append(''.join(ascii_buffer))
            ascii_buffer.clear()

    for c in line:
        if c.isascii() and c.isalnum():
            # ASCII letter or digit: accumulate into buffer
            ascii_buffer.append(c)
        elif c == ' ':
            # Space: flush buffer but skip the space itself
            flush_ascii_buffer()
        else:
            # Non-ASCII or ASCII punctuation: flush buffer first
            flush_ascii_buffer()
            # Add current character as its own token
            tokens.append(c)

    # Flush any remaining ASCII buffer
    flush_ascii_buffer()

    return tokens


def add_features_per_line(line):
    """Extract features for each token in a line.

    This is a wrapper function that:
    1. Tokenizes the line (handling mixed ASCII/non-ASCII)
    2. Calls various feature sub-functions
    3. Combines all features into a list of dicts (one per token)

    Args:
        line: Input string (underscores should already be stripped)

    Returns:
        List of dicts, where each dict contains features for one token.
        Example:
        [
            {'char': 'き', 'prev_char': None, 'next_char': 'ょ', ...},
            {'char': 'ょ', 'prev_char': 'き', 'next_char': 'う', ...},
            ...
        ]
    """
    tokens = tokenize_line(line)
    n = len(tokens)

    if n == 0:
        return []

    # Initialize feature list (one dict per token)
    features = [{} for _ in range(n)]

    # Call feature sub-functions and merge results
    # Each sub-function returns a list of values (one per token)

    # Character type feature: 'hira' or 'non-hira'
    ctype_values = add_feature_ctype(tokens)
    for i, val in enumerate(ctype_values):
        features[i]['ctype'] = val

    # TODO: Add more feature sub-functions here
    # Example:
    #   char_values = add_feature_char(tokens)
    #   for i, val in enumerate(char_values):
    #       features[i]['char'] = val

    return features


# ─── Feature Sub-functions ────────────────────────────────────────────
# Each function takes a list of tokens and returns a list of feature values
# (one value per token). The wrapper add_features_per_line() calls these
# and combines the results into feature dicts.

def add_feature_ctype(tokens):
    """Add character type feature: 'hira' or 'non-hira'.

    A token is classified as 'hira' only if it is a single hiragana character.
    All other tokens (multi-char, kanji, katakana, ASCII, etc.) are 'non-hira'.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of 'hira' or 'non-hira' strings (same length as tokens)

    Example:
        add_feature_ctype(['き', 'ょ', 'う', 'sunny'])
        → ['hira', 'hira', 'hira', 'non-hira']

        add_feature_ctype(['今', 'は', 'hello'])
        → ['non-hira', 'hira', 'non-hira']
    """
    result = []
    for token in tokens:
        if len(token) == 1 and char_type(token) == 'hiragana':
            result.append('hira')
        else:
            result.append('non-hira')
    return result


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

        # State for 3-step pipeline: Browse → Feature Extract → Train
        self._raw_lines = []      # Raw lines from corpus file (set by Browse)
        self._sentences = []      # Parsed (chars, tags) tuples (set by Feature Extract)
        self._features = []       # Extracted features per sentence (set by Feature Extract)

        # State for Test tab
        self._tagger = None       # CRF tagger (lazy loaded)

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

    def _load_tagger(self):
        """Lazy load the CRF tagger. Returns True if successful."""
        if self._tagger is not None:
            return True

        if not HAS_CRFSUITE:
            return False

        model_path = get_model_path()
        if not os.path.exists(model_path):
            return False

        try:
            self._tagger = pycrfsuite.Tagger()
            self._tagger.open(model_path)
            logger.info(f'Loaded CRF model from: {model_path}')
            return True
        except Exception as e:
            logger.error(f'Failed to load CRF model: {e}')
            self._tagger = None
            return False

    def on_test_prediction(self, button):
        """Run bunsetsu-split prediction on input text."""
        # Load model if not already loaded
        if not self._load_tagger():
            dialog = Gtk.MessageDialog(
                transient_for=self, flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Failed to load model",
            )
            dialog.format_secondary_text(
                "Could not load the CRF model. Make sure you have trained a model first."
            )
            dialog.run()
            dialog.destroy()
            return

        # Get input text
        input_text = self.test_input_entry.get_text().strip()
        if not input_text:
            return

        # Tokenize and extract features
        tokens = tokenize_line(input_text)
        if not tokens:
            return

        features = add_features_per_line(input_text)

        # Run 1-best Viterbi prediction
        self._tagger.set(features)
        predicted_tags = self._tagger.tag()
        probability = self._tagger.probability(predicted_tags)

        # Segment tokens into bunsetsu based on predicted tags
        bunsetsu_list = self._segment_by_tags(tokens, predicted_tags)

        # Update first tab with 1-best result
        tab_label = self._result_tab_labels[0]
        tab_content = self._result_tab_contents[0]
        tab_label.set_text(f"#1 ({probability:.3f})")

        # Clear existing content
        for child in tab_content.get_children():
            tab_content.remove(child)

        # Build result display
        result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Input display
        input_label = Gtk.Label()
        input_label.set_markup(f"<b>Input:</b> {GLib.markup_escape_text(input_text)}")
        input_label.set_xalign(0)
        result_box.pack_start(input_label, False, False, 0)

        # Segmented result with visual bunsetsu markers
        segmented_text = ' | '.join(bunsetsu_list)
        segment_label = Gtk.Label()
        segment_label.set_markup(f"<b>Segmented:</b> {GLib.markup_escape_text(segmented_text)}")
        segment_label.set_xalign(0)
        result_box.pack_start(segment_label, False, False, 0)

        # Probability
        prob_label = Gtk.Label()
        prob_label.set_markup(f"<b>Probability:</b> {probability:.6f}")
        prob_label.set_xalign(0)
        result_box.pack_start(prob_label, False, False, 0)

        # Detailed token-tag view
        detail_frame = Gtk.Frame(label="Token Details")
        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        detail_box.set_border_width(6)

        # Header
        header = Gtk.Label()
        header.set_markup("<tt><b>Token\tTag\tType</b></tt>")
        header.set_xalign(0)
        detail_box.pack_start(header, False, False, 0)

        # Token rows
        for token, tag in zip(tokens, predicted_tags):
            ctype = 'hira' if (len(token) == 1 and char_type(token) == 'hiragana') else 'non-hira'
            row = Gtk.Label()
            row.set_markup(f"<tt>{GLib.markup_escape_text(token)}\t{tag}\t{ctype}</tt>")
            row.set_xalign(0)
            detail_box.pack_start(row, False, False, 0)

        detail_frame.add(detail_box)
        result_box.pack_start(detail_frame, False, False, 0)

        tab_content.pack_start(result_box, False, False, 0)

        # Update remaining tabs (N-Best not directly supported by pycrfsuite)
        for i in range(1, len(self._result_tab_labels)):
            tab_label = self._result_tab_labels[i]
            tab_content = self._result_tab_contents[i]
            tab_label.set_text(f"#{i+1} (-.---)")

            for child in tab_content.get_children():
                tab_content.remove(child)

            notice = Gtk.Label()
            notice.set_markup(
                "<i>N-Best decoding not directly supported by pycrfsuite.\n"
                "Only 1-best Viterbi result is available.</i>"
            )
            notice.set_xalign(0)
            notice.set_yalign(0)
            tab_content.pack_start(notice, False, False, 0)

        self.results_notebook.show_all()

    def _segment_by_tags(self, tokens, tags):
        """Segment tokens into bunsetsu based on predicted B-/I- tags.

        Args:
            tokens: List of tokens
            tags: List of predicted tags (B-L, I-L, B-P, I-P, or B, I)

        Returns:
            List of bunsetsu strings, each annotated with type if available.
            E.g., ['きょう[L]', 'は[P]', 'てんき[L]', 'が[P]', 'よい[L]']
        """
        if not tokens or not tags:
            return []

        bunsetsu_list = []
        current_bunsetsu = []
        current_type = None

        for token, tag in zip(tokens, tags):
            if tag.startswith('B'):
                # Start new bunsetsu
                if current_bunsetsu:
                    # Finish previous bunsetsu
                    text = ''.join(current_bunsetsu)
                    if current_type:
                        text = f"{text}[{current_type}]"
                    bunsetsu_list.append(text)
                current_bunsetsu = [token]
                # Extract type from tag (B-L -> L, B-P -> P, B -> None)
                if '-' in tag:
                    current_type = tag.split('-')[1]
                else:
                    current_type = None
            else:
                # Continue current bunsetsu
                current_bunsetsu.append(token)

        # Finish last bunsetsu
        if current_bunsetsu:
            text = ''.join(current_bunsetsu)
            if current_type:
                text = f"{text}[{current_type}]"
            bunsetsu_list.append(text)

        return bunsetsu_list

    def create_test_tab(self):
        """Create Test tab"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)

        # ── Input Section ──
        input_frame = Gtk.Frame(label="Input Sentence")
        input_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        input_box.set_border_width(10)
        input_frame.add(input_box)

        input_info = Gtk.Label()
        input_info.set_markup(
            "<small>Enter a sentence in hiragana to test bunsetsu segmentation prediction.</small>"
        )
        input_info.set_xalign(0)
        input_box.pack_start(input_info, False, False, 0)

        self.test_input_entry = Gtk.Entry()
        self.test_input_entry.set_placeholder_text("e.g., きょうはてんきがよい")
        input_box.pack_start(self.test_input_entry, False, False, 0)

        box.pack_start(input_frame, False, False, 0)

        # ── Test Button ──
        self.test_predict_btn = Gtk.Button(label="Test Bunsetsu-split prediction")
        self.test_predict_btn.connect("clicked", self.on_test_prediction)
        # Disable if no model exists
        if not os.path.exists(get_model_path()):
            self.test_predict_btn.set_sensitive(False)
            self.test_predict_btn.set_tooltip_text("No trained model found. Train a model first.")
        box.pack_start(self.test_predict_btn, False, False, 0)

        # ── N-Best Results (nested notebook) ──
        self.results_notebook = Gtk.Notebook()
        self.results_notebook.set_scrollable(True)

        # Pre-create N tabs based on config
        config, _ = util.get_config_data()
        n_best_count = config.get('bunsetsu_prediction_n_best', 5)

        self._result_tab_labels = []  # Store label widgets for updating later
        self._result_tab_contents = []  # Store content boxes for updating later

        for i in range(n_best_count):
            # Tab label
            tab_label = Gtk.Label(label=f"#{i+1} (0.000)")
            self._result_tab_labels.append(tab_label)

            # Tab content (placeholder for now)
            tab_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            tab_content.set_border_width(10)
            placeholder = Gtk.Label(label="(Enter a sentence and click the button above)")
            tab_content.pack_start(placeholder, True, True, 0)
            self._result_tab_contents.append(tab_content)

            self.results_notebook.append_page(tab_content, tab_label)

        box.pack_start(self.results_notebook, True, True, 0)

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

        # ── Feature Extraction Button ──
        extract_btn = Gtk.Button(label="Feature Extraction")
        extract_btn.connect("clicked", self.on_feature_extract)
        box.pack_start(extract_btn, False, False, 0)

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
        """Load corpus file and show basic stats (step 1 of pipeline)."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._raw_lines = f.readlines()
        except Exception as e:
            self.corpus_stats_label.set_text(f"Error reading file: {e}")
            self._raw_lines = []
            return

        # Clear previous pipeline state
        self._sentences = []
        self._features = []

        # Calculate basic stats (without parsing)
        line_count = len([l for l in self._raw_lines if l.strip()])
        total_chars = sum(len(l.strip()) for l in self._raw_lines)

        self.corpus_stats_label.set_markup(
            f"<b>{line_count:,}</b> lines loaded, "
            f"<b>{total_chars:,}</b> characters\n"
            f"<small>Click 'Feature Extraction' to parse and extract features.</small>"
        )

    def on_feature_extract(self, button):
        """Parse annotations and extract features (step 2 of pipeline)."""
        if not self._raw_lines:
            self._log("ERROR: No corpus loaded. Click 'Browse' first.")
            return

        self.log_buffer.set_text('')  # Clear log
        self._log("=== Feature Extraction ===")
        self._log("")

        # ── Parse annotations ──
        self._log("Parsing annotations...")
        self._sentences = []
        for line in self._raw_lines:
            chars, tags = parse_annotated_line(line)
            if chars:
                self._sentences.append((chars, tags))

        if not self._sentences:
            self._log("ERROR: No valid sentences found in corpus.")
            return

        self._log(f"Parsed {len(self._sentences):,} sentences")

        # Calculate stats
        total_chars = sum(len(chars) for chars, tags in self._sentences)
        total_bunsetsu = sum(
            sum(1 for tag in tags if tag.startswith('B-'))
            for chars, tags in self._sentences
        )
        lookup_bunsetsu = sum(
            sum(1 for tag in tags if tag == 'B-L')
            for chars, tags in self._sentences
        )
        passthrough_bunsetsu = sum(
            sum(1 for tag in tags if tag == 'B-P')
            for chars, tags in self._sentences
        )

        self._log(f"  Bunsetsu: {total_bunsetsu:,} ({lookup_bunsetsu:,} lookup, {passthrough_bunsetsu:,} passthrough)")
        self._log(f"  Characters: {total_chars:,}")
        self._log("")

        # ── Extract features ──
        self._log("Extracting features...")
        self._features = []
        for chars, tags in self._sentences:
            # Join chars to form the line for tokenization
            line_text = ''.join(chars)
            features = add_features_per_line(line_text)
            self._features.append(features)

        self._log(f"Feature extraction complete")
        self._log("")

        # ── Dump to TSV (always, as intermediate file) ──
        tsv_path = os.path.join(util.get_user_config_dir(), 'crf_model_training_data.tsv')
        try:
            with open(tsv_path, 'w', encoding='utf-8') as f:
                for sent_idx, ((chars, tags), features) in enumerate(zip(self._sentences, self._features)):
                    # Blank line before sentence marker (except first sentence)
                    if sent_idx > 0:
                        f.write('\n')
                    f.write(f'# Sentence {sent_idx + 1}\n')

                    # Write each token with its tag and features
                    for char, tag, feat_dict in zip(chars, tags, features):
                        # Convert feature dict to tab-separated string
                        feat_str = '\t'.join(f'{k}={v}' for k, v in feat_dict.items())
                        f.write(f'{char}\t{tag}\t{feat_str}\n')

            self._log(f"Training data saved to: {tsv_path}")
        except Exception as e:
            self._log(f"WARNING: Failed to save training data: {e}")

        # Update stats label
        self.corpus_stats_label.set_markup(
            f"<b>{len(self._sentences):,}</b> sentences, "
            f"<b>{total_bunsetsu:,}</b> bunsetsu "
            f"(<b>{lookup_bunsetsu:,}</b> lookup, <b>{passthrough_bunsetsu:,}</b> passthrough), "
            f"<b>{total_chars:,}</b> characters\n"
            f"<small>Features extracted. Click 'Train' to train the model.</small>"
        )

        self._log("")
        self._log("Done. Ready for training.")

    def on_train(self, button):
        """Run CRF training using extracted features (step 3 of pipeline)."""
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

        # Check if features have been extracted
        if not self._sentences or not self._features:
            self._log("ERROR: No features extracted. Click 'Feature Extraction' first.")
            return

        model_path = get_model_path()

        self.log_buffer.set_text('')  # Clear log
        self._log("=== CRF Bunsetsu Segmentation Training ===")
        self._log("")
        self._log(f"Using {len(self._sentences):,} sentences with pre-extracted features")
        self._log("")

        # ── Prepare training data ──
        # X_train: list of feature sequences (each is a list of feature dicts)
        # y_train: list of tag sequences
        X_train = self._features
        y_train = [tags for chars, tags in self._sentences]

        total_tokens = sum(len(seq) for seq in X_train)
        self._log(f"Total tokens: {total_tokens:,}")

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
        self._log(f"  Sentences:       {len(self._sentences):,}")
        self._log(f"  Tokens:          {total_tokens:,}")
        self._log("")
        self._log("Done.")


def main():
    """Run conversion model panel standalone"""
    # Configure logging from user config
    config, _ = util.get_config_data()
    level_name = config.get('logging_level', 'WARNING').upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)-8s %(message)s')

    win = ConversionModelPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
