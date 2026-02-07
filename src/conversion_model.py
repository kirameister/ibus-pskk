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
# Note: char_type, tokenize_line, add_features_per_line are imported from util

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
    ct = util.char_type(c)
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
            f'type[-1]={util.char_type(chars[i-1])}',
            f'bigram[-1:0]={chars[i-1]}{c}',
            f'type_change={util.char_type(chars[i-1]) != ct}',
        ])
    else:
        features.append('BOS')

    if i >= 2:
        features.extend([
            f'char[-2]={chars[i-2]}',
            f'type[-2]={util.char_type(chars[i-2])}',
        ])

    if i < n - 1:
        features.extend([
            f'char[+1]={chars[i+1]}',
            f'type[+1]={util.char_type(chars[i+1])}',
            f'bigram[0:+1]={c}{chars[i+1]}',
        ])
    else:
        features.append('EOS')

    if i < n - 2:
        features.extend([
            f'char[+2]={chars[i+2]}',
            f'type[+2]={util.char_type(chars[i+2])}',
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


# Note: Use util.get_crf_model_path() for the canonical model path


# ─── GTK Panel ────────────────────────────────────────────────────────

class ConversionModelPanel(Gtk.Window):
    def __init__(self):
        super().__init__(title="Conversion Model")

        self.set_default_size(920, 600)
        self.set_border_width(10)

        # Set up CSS styling for grid headers
        self._setup_css()

        # State for 3-step pipeline: Browse → Feature Extract → Train
        self._raw_lines = []      # Raw lines from corpus file (set by Browse)
        self._sentences = []      # Parsed (chars, tags) tuples (set by Feature Extract)
        self._features = []       # Extracted features per sentence (set by Feature Extract)

        # State for Test tab
        self._tagger = None       # CRF tagger (lazy loaded)
        # Pre-computed dictionary features for CRF
        self._crf_feature_materials = util.load_crf_feature_materials()

        # Create UI
        notebook = Gtk.Notebook()
        notebook.append_page(self.create_test_tab(), Gtk.Label(label="Test"))
        notebook.append_page(self.create_train_tab(), Gtk.Label(label="Train"))
        self.add(notebook)

        # Connect Esc key to close window
        self.connect("key-press-event", self.on_key_press)

        # Set initial focus to input field for immediate typing
        # (must be done after window is mapped/shown)
        self.connect("map", self._on_window_map)

    def _on_window_map(self, widget):
        """Called when window becomes visible. Set focus to input field."""
        self.test_input_entry.grab_focus()

    def _setup_css(self):
        """Set up CSS styling for the window."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .grid-header {
                background-color: #d0d0d0;
                padding: 4px 8px;
            }
            .grid-corner {
                background-color: #d0d0d0;
            }
            notebook > stack {
                padding: 0;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_key_press(self, widget, event):
        """Handle key press events"""
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True

        # Arrow key navigation for N-best results
        if event.keyval == Gdk.KEY_Down:
            current = self.results_notebook.get_current_page()
            n_pages = self.results_notebook.get_n_pages()
            if current < n_pages - 1:
                self.results_notebook.set_current_page(current + 1)
            return True

        if event.keyval == Gdk.KEY_Up:
            current = self.results_notebook.get_current_page()
            if current > 0:
                self.results_notebook.set_current_page(current - 1)
            return True

        return False

    def _load_tagger(self):
        """Lazy load the CRF tagger. Returns True if successful."""
        if self._tagger is not None:
            return True

        self._tagger = util.load_crf_tagger()
        return self._tagger is not None

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

        # Tokenize input
        tokens = util.tokenize_line(input_text)
        if not tokens:
            return

        # Run N-best Viterbi prediction
        n_best_count = len(self._result_tab_labels)
        nbest_results = util.crf_nbest_predict(self._tagger, input_text, n_best=n_best_count,
                                               dict_materials=self._crf_feature_materials)

        # Extract features for display (same as what CRF uses internally)
        token_features = util.add_features_per_line(input_text, self._crf_feature_materials)

        # Get model info for emission score computation
        info = self._tagger.info()
        model_labels = self._tagger.labels()
        state_features = info.state_features

        # Compute emission scores: emission[t][label_idx] = score
        emission = util.crf_compute_emission_scores(token_features, state_features, model_labels)

        # Store results for tab switching
        self._nbest_results = nbest_results
        self._current_tokens = tokens
        self._current_features = token_features
        self._model_labels = model_labels
        self._state_features = state_features
        self._emission_scores = emission

        # Feature keys to display (in order)
        self._feature_keys = [
            "char", "char_left", "char_right",
            "bigram_left", "bigram_right",
            "dict_max_kl_s", "dict_max_kl_e",
            "dict_entry_ct_s", "dict_entry_ct_e",
        ]

        # Get transition scores from model
        transitions = info.transitions

        # Check if DEBUG logging is enabled
        is_debug = logger.isEnabledFor(logging.DEBUG)

        # Build row headers:
        # 1. Label (predicted)
        # 2. Transition scores (M rows for Option C, M×M for Option A in DEBUG)
        # 3. Emission scores for each model label (e.g., emit_B-L, emit_I-L, ...)
        # 4. Feature values
        # 5. Feature weights (contribution to predicted label) - DEBUG only
        emission_headers = [f"emit_{lbl}" for lbl in model_labels]

        if is_debug:
            # Option A: All M×M transitions + feature weights
            trans_headers = [f"tr_{fr}→{to}" for fr in model_labels for to in model_labels]
            weight_headers = [f"{key}_w" for key in self._feature_keys]
        else:
            # Option C: Only M transitions from previous predicted label, no weights
            trans_headers = [f"tr_prev→{to}" for to in model_labels]
            weight_headers = []

        row_headers = ["Label"] + trans_headers + emission_headers + self._feature_keys + weight_headers

        # Build interleaved column headers: [t0, t0→t1, t1, t1→t2, t2, ...]
        col_headers = []
        col_types = []  # Track whether each column is 'token' or 'trans'
        for i, token in enumerate(tokens):
            col_headers.append(token)
            col_types.append('token')
            if i < len(tokens) - 1:
                col_headers.append(f"→")
                col_types.append('trans')

        # Store for use in _update_result_grid
        self._transitions = transitions
        self._col_types = col_types
        self._is_debug = is_debug
        self._trans_headers = trans_headers

        # Rebuild grids for all tabs with new columns (tokens + transitions interleaved)
        for tab_idx in range(n_best_count):
            self._rebuild_result_grid(
                tab_index=tab_idx,
                num_cols=len(col_headers),
                row_headers=row_headers,
                col_headers=col_headers
            )

        # Update all tabs with N-best results
        for tab_idx in range(n_best_count):
            if tab_idx < len(nbest_results):
                labels, score = nbest_results[tab_idx]
                self._result_tab_labels[tab_idx].set_text(f"#{tab_idx+1} ({score:.3f})")
                self._update_result_grid(tab_idx, tokens, labels)
            else:
                # No result for this tab
                self._result_tab_labels[tab_idx].set_text(f"#{tab_idx+1} (-.---)")
                # Leave cells with default "-" values

        self.results_notebook.show_all()

    def _update_result_grid(self, tab_idx, tokens, labels):
        """Update the cell values in a result grid for a specific tab.

        Args:
            tab_idx: Index of the tab to update
            tokens: List of tokens
            labels: List of predicted labels for this N-best result
        """
        # Update bunsetsu preview label
        bunsetsu_markup = self._format_bunsetsu_markup(tokens, labels)
        self._result_bunsetsu_labels[tab_idx].set_markup(bunsetsu_markup)

        # Update grid cells
        cell_labels = self._result_cell_labels[tab_idx]
        n_trans_rows = len(self._trans_headers)
        n_emission_rows = len(self._model_labels)
        n_feature_rows = len(self._feature_keys)

        # Calculate row offsets (transition rows now come first after Label)
        row_label = 0
        row_trans_start = 1
        row_emission_start = row_trans_start + n_trans_rows
        row_feature_start = row_emission_start + n_emission_rows
        row_weight_start = row_feature_start + n_feature_rows  # Only used in DEBUG mode

        token_idx = 0  # Index into tokens/labels arrays
        trans_idx = 0  # Index for transitions (0 = between token 0 and 1)

        for col_idx, col_type in enumerate(self._col_types):
            if col_type == 'token':
                # Token column: show label, emissions, features, weights
                pred_label = labels[token_idx]

                # Row 0: Label (predicted tag)
                cell_labels[row_label][col_idx].set_text(pred_label)

                # Emission scores for each label
                if hasattr(self, '_emission_scores') and token_idx < len(self._emission_scores):
                    for label_idx in range(n_emission_rows):
                        score = self._emission_scores[token_idx][label_idx]
                        cell_labels[row_emission_start + label_idx][col_idx].set_text(f"{score:.2f}")

                # Feature values
                if hasattr(self, '_current_features') and token_idx < len(self._current_features):
                    feat_dict = self._current_features[token_idx]
                    for feat_idx, key in enumerate(self._feature_keys):
                        value = feat_dict.get(key, "-")
                        cell_labels[row_feature_start + feat_idx][col_idx].set_text(str(value))

                # Feature weights for the predicted label (DEBUG only)
                if self._is_debug and hasattr(self, '_state_features') and token_idx < len(self._current_features):
                    feat_dict = self._current_features[token_idx]
                    for feat_idx, key in enumerate(self._feature_keys):
                        value = feat_dict.get(key)
                        if value is not None:
                            feat_str = f"{key}:{value}"
                            weight = self._state_features.get((feat_str, pred_label), 0.0)
                            cell_labels[row_weight_start + feat_idx][col_idx].set_text(f"{weight:.2f}")
                        else:
                            cell_labels[row_weight_start + feat_idx][col_idx].set_text("-")

                # Transition rows are empty for token columns
                for trans_row in range(n_trans_rows):
                    cell_labels[row_trans_start + trans_row][col_idx].set_text("")

                token_idx += 1

            else:  # col_type == 'trans'
                # Transition column: show transition scores, empty for other rows
                prev_label = labels[trans_idx]

                # Empty cells for non-transition rows
                cell_labels[row_label][col_idx].set_text("")
                for i in range(n_emission_rows):
                    cell_labels[row_emission_start + i][col_idx].set_text("")
                for i in range(n_feature_rows):
                    cell_labels[row_feature_start + i][col_idx].set_text("")
                # Weight rows only exist in DEBUG mode
                if self._is_debug:
                    for i in range(n_feature_rows):
                        cell_labels[row_weight_start + i][col_idx].set_text("")

                # Transition scores
                if self._is_debug:
                    # Option A: All M×M transitions
                    trans_row = 0
                    for from_label in self._model_labels:
                        for to_label in self._model_labels:
                            score = self._transitions.get((from_label, to_label), 0.0)
                            cell_labels[row_trans_start + trans_row][col_idx].set_text(f"{score:.2f}")
                            trans_row += 1
                else:
                    # Option C: Only M transitions from previous predicted label
                    for to_idx, to_label in enumerate(self._model_labels):
                        score = self._transitions.get((prev_label, to_label), 0.0)
                        cell_labels[row_trans_start + to_idx][col_idx].set_text(f"{score:.2f}")

                trans_idx += 1

    def _format_bunsetsu_markup(self, tokens, labels):
        """Format bunsetsu split with Pango markup.

        Lookup bunsetsu (B-L/I-L) are shown in bold.
        Passthrough bunsetsu (B-P/I-P) are shown in normal text.
        Bunsetsu are separated by spaces.

        Example: tokens=['き','ょ','う','は'], labels=['B-L','I-L','I-L','B-P']
          → "<b>きょう</b> は"

        Args:
            tokens: List of tokens
            labels: List of predicted labels

        Returns:
            Pango markup string
        """
        bunsetsu_list = util.labels_to_bunsetsu(tokens, labels)
        if not bunsetsu_list:
            return ""

        parts = []
        for text, label in bunsetsu_list:
            escaped = GLib.markup_escape_text(text)
            # Lookup bunsetsu (B-L or simple B) shown in bold
            # Passthrough bunsetsu (B-P) shown in normal text
            is_lookup = label.endswith('-L') or label == 'B'
            if is_lookup:
                parts.append(f"<b>{escaped}</b>")
            else:
                parts.append(escaped)

        return ' '.join(parts)

    def _create_result_grid(self, num_cols=3, row_headers=None, col_headers=None):
        """Create a grid for displaying prediction results.

        Args:
            num_cols: Number of data columns (excluding row header column)
            row_headers: List of row header strings (default: ["Label", "Score", "Feature"])
            col_headers: List of column header strings (default: ["Token1", "Token2", ...])

        Returns:
            Tuple of (grid, cell_labels) where cell_labels is a 2D list of Gtk.Label
            widgets for the data cells (excluding headers).
        """
        if row_headers is None:
            row_headers = ["Label", "Score", "Feature"]
        if col_headers is None:
            col_headers = [f"Token{i+1}" for i in range(num_cols)]

        num_rows = len(row_headers)

        grid = Gtk.Grid()
        grid.set_column_spacing(1)  # Minimal spacing for seamless header look
        grid.set_row_spacing(1)
        grid.set_column_homogeneous(False)
        grid.set_row_homogeneous(False)
        grid.set_margin_start(0)
        grid.set_margin_top(0)

        # Top-left corner cell (empty, with background)
        corner_box = Gtk.EventBox()
        corner_box.get_style_context().add_class("grid-corner")
        corner_label = Gtk.Label(label="")
        corner_box.add(corner_label)
        grid.attach(corner_box, 0, 0, 1, 1)

        # Column headers (row 0, columns 1..n)
        for col_idx, header in enumerate(col_headers):
            header_box = Gtk.EventBox()
            header_box.get_style_context().add_class("grid-header")
            label = Gtk.Label()
            label.set_markup(f"<b>{GLib.markup_escape_text(header)}</b>")
            label.set_xalign(0.5)
            header_box.add(label)
            grid.attach(header_box, col_idx + 1, 0, 1, 1)

        # Row headers (column 0, rows 1..n)
        for row_idx, header in enumerate(row_headers):
            header_box = Gtk.EventBox()
            header_box.get_style_context().add_class("grid-header")
            label = Gtk.Label()
            label.set_markup(f"<b>{GLib.markup_escape_text(header)}</b>")
            label.set_xalign(1.0)  # Right-align row headers
            header_box.add(label)
            grid.attach(header_box, 0, row_idx + 1, 1, 1)

        # Data cells (rows 1..n, columns 1..n)
        cell_labels = []
        for row_idx in range(num_rows):
            row_labels = []
            for col_idx in range(len(col_headers)):
                label = Gtk.Label(label="-")
                label.set_xalign(0.5)
                label.set_margin_start(8)
                label.set_margin_end(8)
                label.set_margin_top(4)
                label.set_margin_bottom(4)
                grid.attach(label, col_idx + 1, row_idx + 1, 1, 1)
                row_labels.append(label)
            cell_labels.append(row_labels)

        return grid, cell_labels

    def _rebuild_result_grid(self, tab_index, num_cols, row_headers, col_headers):
        """Rebuild the grid for a specific tab with new dimensions.

        Args:
            tab_index: Index of the tab to rebuild
            num_cols: Number of data columns
            row_headers: List of row header strings
            col_headers: List of column header strings
        """
        # Get the scrolled window containing the grid
        # (index 1 because index 0 is the bunsetsu preview label)
        tab_content = self._result_tab_contents[tab_index]
        scroll = tab_content.get_children()[1]  # Second child is the ScrolledWindow

        # Remove old grid
        old_grid = self._result_grids[tab_index]
        scroll.remove(old_grid)

        # Create new grid
        new_grid, new_cell_labels = self._create_result_grid(
            num_cols=num_cols,
            row_headers=row_headers,
            col_headers=col_headers
        )
        scroll.add(new_grid)
        new_grid.show_all()

        # Update references
        self._result_grids[tab_index] = new_grid
        self._result_cell_labels[tab_index] = new_cell_labels

    def on_result_tab_switched(self, notebook, page, page_num):
        """Handle tab switch in results notebook.

        This will update the cell values based on the selected N-best result.
        For now, this is a placeholder - actual implementation will come later
        when we store prediction results for each N-best.
        """
        # TODO: Update cell values based on which N-best result is selected
        # For now, the grid already shows the values set during prediction
        pass

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
        self.test_input_entry.connect("activate", self.on_test_prediction)
        input_box.pack_start(self.test_input_entry, False, False, 0)

        box.pack_start(input_frame, False, False, 0)

        # ── Test Button ──
        self.test_predict_btn = Gtk.Button(label="Test Bunsetsu-split prediction")
        self.test_predict_btn.connect("clicked", self.on_test_prediction)
        # Disable if no model exists
        if not os.path.exists(util.get_crf_model_path()):
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
        self._result_grids = []  # Store grid widgets for each tab
        self._result_cell_labels = []  # Store cell label widgets for each tab (2D list)
        self._result_bunsetsu_labels = []  # Store bunsetsu preview labels for each tab

        for i in range(n_best_count):
            # Tab label
            tab_label = Gtk.Label(label=f"#{i+1} (0.000)")
            self._result_tab_labels.append(tab_label)

            # Tab content with scrollable grid
            tab_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

            # Bunsetsu preview label (above the grid)
            bunsetsu_label = Gtk.Label()
            bunsetsu_label.set_markup("<i>(Enter a sentence and click the button above)</i>")
            bunsetsu_label.set_xalign(0)
            bunsetsu_label.set_margin_start(8)
            bunsetsu_label.set_margin_top(4)
            bunsetsu_label.set_margin_bottom(4)
            tab_content.pack_start(bunsetsu_label, False, False, 0)
            self._result_bunsetsu_labels.append(bunsetsu_label)

            # Create scrolled window for the grid
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.set_shadow_type(Gtk.ShadowType.NONE)  # Remove any shadow/border

            # Create the default 4x4 grid
            grid, cell_labels = self._create_result_grid()
            scroll.add(grid)
            tab_content.pack_start(scroll, True, True, 0)

            self._result_tab_contents.append(tab_content)
            self._result_grids.append(grid)
            self._result_cell_labels.append(cell_labels)

            self.results_notebook.append_page(tab_content, tab_label)

        # Connect tab switch signal for updating values
        self.results_notebook.connect("switch-page", self.on_result_tab_switched)

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
            features = util.add_features_per_line(line_text, self._crf_feature_materials)
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

        model_path = util.get_crf_model_path()

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
