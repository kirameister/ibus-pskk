import codecs
import json
import math
import os
from gi.repository import GLib
import logging

import katsuyou

logger = logging.getLogger(__name__)


# ─── Character Classification and Tokenization ────────────────────────

def char_type(c):
    """Classify a character into its Unicode block type.

    Args:
        c: A single character

    Returns:
        One of: 'hiragana', 'katakana', 'kanji', 'ascii', 'other'
    """
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


def katakana_to_hiragana(text):
    """Convert katakana characters to hiragana.

    Args:
        text: Input string (may contain katakana, hiragana, or other characters)

    Returns:
        String with katakana converted to hiragana (other characters unchanged)
    """
    result = []
    for c in text:
        cp = ord(c)
        # Katakana range: 0x30A1 (ァ) to 0x30F6 (ヶ)
        # Hiragana range: 0x3041 (ぁ) to 0x3096 (ゖ)
        # Offset: 0x60 (96)
        if 0x30A1 <= cp <= 0x30F6:
            result.append(chr(cp - 0x60))
        else:
            result.append(c)
    return ''.join(result)


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


# ─── CRF Feature Extraction ───────────────────────────────────────────

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


def add_feature_char(tokens):
    """Add character identity feature: the token string itself.

    This is intentionally a simple pass-through so that it can be
    individually enabled or disabled as a feature via user config.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of token strings (same length and content as input)

    Example:
        add_feature_char(['き', 'ょ', 'う', 'sunny'])
        → ['き', 'ょ', 'う', 'sunny']
    """
    return list(tokens)


def add_feature_char_left(tokens):
    """Add left-adjacent character feature: the token to the left of each position.

    The first token has no left neighbor, so 'BOS' (Beginning Of Sequence)
    is used as a sentinel value.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of strings (same length as tokens)

    Example:
        add_feature_char_left(['き', 'ょ', 'う'])
        → ['BOS', 'き', 'ょ']
    """
    if not tokens:
        return []
    return ['BOS'] + list(tokens[:-1])


def add_feature_char_right(tokens):
    """Add right-adjacent character feature: the token to the right of each position.

    The last token has no right neighbor, so 'EOS' (End Of Sequence)
    is used as a sentinel value.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of strings (same length as tokens)

    Example:
        add_feature_char_right(['き', 'ょ', 'う'])
        → ['ょ', 'う', 'EOS']
    """
    if not tokens:
        return []
    return list(tokens[1:]) + ['EOS']


def add_feature_bigram_left(tokens):
    """Add left bigram feature: the current token paired with its left neighbor.

    Each element is a space-separated string of the left neighbor and the
    current token.  The first token uses 'BOS' as its left neighbor.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of strings (same length as tokens)

    Example:
        add_feature_bigram_left(['き', 'ょ', 'う'])
        → ['BOS き', 'き ょ', 'ょ う']
    """
    if not tokens:
        return []
    left = ['BOS'] + list(tokens[:-1])
    return [f'{l} {t}' for l, t in zip(left, tokens)]


def add_feature_bigram_right(tokens):
    """Add right bigram feature: the current token paired with its right neighbor.

    Each element is a space-separated string of the current token and the
    right neighbor.  The last token uses 'EOS' as its right neighbor.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of strings (same length as tokens)

    Example:
        add_feature_bigram_right(['き', 'ょ', 'う'])
        → ['き ょ', 'ょ う', 'う EOS']
    """
    if not tokens:
        return []
    right = list(tokens[1:]) + ['EOS']
    return [f'{t} {r}' for t, r in zip(tokens, right)]


def add_feature_trigram_left(tokens):
    """Add left trigram feature: two left neighbors plus the current token.

    Each element is a space-separated string of the two left neighbors
    and the current token. Uses 'BOS' for positions before the start.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of strings (same length as tokens)

    Example:
        add_feature_trigram_left(['あ', 'い', 'う', 'え'])
        → ['BOS BOS あ', 'BOS あ い', 'あ い う', 'い う え']
    """
    if not tokens:
        return []
    # Prepend two BOS markers
    left2 = ['BOS', 'BOS'] + list(tokens[:-2]) if len(tokens) > 2 else ['BOS'] * len(tokens)
    left1 = ['BOS'] + list(tokens[:-1])

    # Handle edge cases for short sequences
    if len(tokens) == 1:
        return ['BOS BOS ' + tokens[0]]
    elif len(tokens) == 2:
        return ['BOS BOS ' + tokens[0], 'BOS ' + tokens[0] + ' ' + tokens[1]]

    return [f'{l2} {l1} {t}' for l2, l1, t in zip(left2, left1, tokens)]


def add_feature_trigram_right(tokens):
    """Add right trigram feature: current token plus two right neighbors.

    Each element is a space-separated string of the current token and
    the two right neighbors. Uses 'EOS' for positions after the end.

    Args:
        tokens: List of tokens from tokenize_line()

    Returns:
        List of strings (same length as tokens)

    Example:
        add_feature_trigram_right(['あ', 'い', 'う', 'え'])
        → ['あ い う', 'い う え', 'う え EOS', 'え EOS EOS']
    """
    if not tokens:
        return []
    # Append two EOS markers
    right1 = list(tokens[1:]) + ['EOS']
    right2 = list(tokens[2:]) + ['EOS', 'EOS'] if len(tokens) > 2 else ['EOS'] * len(tokens)

    # Handle edge cases for short sequences
    if len(tokens) == 1:
        return [tokens[0] + ' EOS EOS']
    elif len(tokens) == 2:
        return [tokens[0] + ' ' + tokens[1] + ' EOS', tokens[1] + ' EOS EOS']

    return [f'{t} {r1} {r2}' for t, r1, r2 in zip(tokens, right1, right2)]


def add_feature_dict_max_kl_start(tokens, materials):
    """Add feature: max dictionary yomi key length starting with this token.

    For each token, looks up the longest yomi key in the dictionary that
    starts with this character. Returns the length as a string.

    Args:
        tokens: List of tokens from tokenize_line()
        materials: Dict from load_crf_feature_materials()

    Returns:
        List of string values (same length as tokens)

    Example:
        # If longest yomi starting with 'き' is 'きょうかしょ' (6 chars):
        add_feature_dict_max_kl_start(['き', 'ょ', 'う'], materials)
        → ['6', '3', '5']
    """
    lookup = materials.get('max_key_len_starting_with', {})
    return [str(lookup.get(t, 0)) for t in tokens]


def add_feature_dict_max_kl_end(tokens, materials):
    """Add feature: max dictionary yomi key length ending with this token.

    For each token, looks up the longest yomi key in the dictionary that
    ends with this character. Returns the length as a string.

    Args:
        tokens: List of tokens from tokenize_line()
        materials: Dict from load_crf_feature_materials()

    Returns:
        List of string values (same length as tokens)
    """
    lookup = materials.get('max_key_len_ending_with', {})
    return [str(lookup.get(t, 0)) for t in tokens]


def add_feature_dict_entry_ct_start(tokens, materials):
    """Add feature: log-bucketed count of kanji entries for yomi keys starting with this token.

    Raw counts are stored in the materials JSON. This function applies
    int(log2(count + 1)) to compress large counts into small integers
    suitable as CRF feature values.

    Args:
        tokens: List of tokens from tokenize_line()
        materials: Dict from load_crf_feature_materials()

    Returns:
        List of string values (same length as tokens)
    """
    lookup = materials.get('dict_entry_count_starting_with', {})
    return [str(int(math.log2(lookup.get(t, 0) + 1))) for t in tokens]


def add_feature_dict_entry_ct_end(tokens, materials):
    """Add feature: log-bucketed count of kanji entries for yomi keys ending with this token.

    Raw counts are stored in the materials JSON. This function applies
    int(log2(count + 1)) to compress large counts into small integers
    suitable as CRF feature values.

    Args:
        tokens: List of tokens from tokenize_line()
        materials: Dict from load_crf_feature_materials()

    Returns:
        List of string values (same length as tokens)
    """
    lookup = materials.get('dict_entry_count_ending_with', {})
    return [str(int(math.log2(lookup.get(t, 0) + 1))) for t in tokens]


def add_features_per_line(line_or_tokens, dict_materials=None):
    """Extract features for each token in a line.

    This is a wrapper function that:
    1. Tokenizes the line (or uses pre-tokenized list)
    2. Calls various feature sub-functions
    3. Combines all features into a list of dicts (one per token)

    Args:
        line_or_tokens: Either:
            - Input string (will be tokenized using tokenize_line)
            - Pre-tokenized list of tokens (used directly)
        dict_materials: Optional dict from load_crf_feature_materials().
                        If provided, dictionary-derived features are included.
                        If None, they are skipped (graceful fallback).

    Returns:
        List of dicts, where each dict contains features for one token.
        Example:
        [
            {'char': 'き', 'ctype': 'hira', 'dict_max_kl_s': '6', ...},
            ...
        ]
    """
    # Accept either string or pre-tokenized list
    if isinstance(line_or_tokens, list):
        tokens = line_or_tokens
    else:
        tokens = tokenize_line(line_or_tokens)
    n = len(tokens)

    if n == 0:
        return []

    # Initialize feature list (one dict per token)
    features = [{} for _ in range(n)]

    # Call feature sub-functions and merge results
    # Each sub-function returns a list of values (one per token)

    # Character identity feature: the token itself
    char_values = add_feature_char(tokens)
    for i, val in enumerate(char_values):
        features[i]['char'] = val

    # Left-adjacent character feature
    char_left_values = add_feature_char_left(tokens)
    for i, val in enumerate(char_left_values):
        features[i]['char_left'] = val

    # Right-adjacent character feature
    char_right_values = add_feature_char_right(tokens)
    for i, val in enumerate(char_right_values):
        features[i]['char_right'] = val

    # Left bigram feature: "left_token current_token"
    bigram_left_values = add_feature_bigram_left(tokens)
    for i, val in enumerate(bigram_left_values):
        features[i]['bigram_left'] = val

    # Right bigram feature: "current_token right_token"
    bigram_right_values = add_feature_bigram_right(tokens)
    for i, val in enumerate(bigram_right_values):
        features[i]['bigram_right'] = val

    # Left trigram feature: "left2 left1 current"
    trigram_left_values = add_feature_trigram_left(tokens)
    for i, val in enumerate(trigram_left_values):
        features[i]['trigram_left'] = val

    # Right trigram feature: "current right1 right2"
    trigram_right_values = add_feature_trigram_right(tokens)
    for i, val in enumerate(trigram_right_values):
        features[i]['trigram_right'] = val

    # Character type feature: 'hira' or 'non-hira'
    ctype_values = add_feature_ctype(tokens)
    for i, val in enumerate(ctype_values):
        features[i]['ctype'] = val

    # Dictionary-derived features (only if materials are provided)
    if dict_materials:
        max_kl_s = add_feature_dict_max_kl_start(tokens, dict_materials)
        for i, val in enumerate(max_kl_s):
            features[i]['dict_max_kl_s'] = val

        max_kl_e = add_feature_dict_max_kl_end(tokens, dict_materials)
        for i, val in enumerate(max_kl_e):
            features[i]['dict_max_kl_e'] = val

        entry_ct_s = add_feature_dict_entry_ct_start(tokens, dict_materials)
        for i, val in enumerate(entry_ct_s):
            features[i]['dict_entry_ct_s'] = val

        entry_ct_e = add_feature_dict_entry_ct_end(tokens, dict_materials)
        for i, val in enumerate(entry_ct_e):
            features[i]['dict_entry_ct_e'] = val

    return features


# ─── CRF N-best Viterbi ───────────────────────────────────────────────

def crf_compute_emission_scores(features, state_features, labels):
    """Compute emission scores for each position and label.

    Args:
        features: List of feature dicts (one per position), from add_features_per_line()
        state_features: Dict of (feature_string, label) → weight from tagger.info()
        labels: List of label strings (e.g., ['B-L', 'I-L', 'B-P', 'I-P'])

    Returns:
        2D list: emission[t][label_idx] = score for label at position t
    """
    n_positions = len(features)
    n_labels = len(labels)
    label_to_idx = {label: i for i, label in enumerate(labels)}

    # Initialize emission scores to 0
    emission = [[0.0] * n_labels for _ in range(n_positions)]

    for t, feat_dict in enumerate(features):
        for key, value in feat_dict.items():
            # Build feature string in CRFsuite format: "key:value"
            feat_str = f"{key}:{value}"
            for label in labels:
                weight = state_features.get((feat_str, label), 0.0)
                if weight != 0.0:
                    emission[t][label_to_idx[label]] += weight

    return emission


def crf_nbest_viterbi(emission, transitions, labels, n_best=5):
    """Run N-best Viterbi algorithm to find top-N label sequences.

    Args:
        emission: 2D list emission[t][label_idx] = emission score
        transitions: Dict of (from_label, to_label) → weight
        labels: List of label strings
        n_best: Number of best sequences to return

    Returns:
        List of (labels_list, score) tuples, sorted by score descending.
        Each labels_list is a list of label strings for each position.
    """
    n_positions = len(emission)
    n_labels = len(labels)

    if n_positions == 0:
        return []

    # Build transition matrix: trans[from_idx][to_idx] = score
    trans = [[0.0] * n_labels for _ in range(n_labels)]
    for i, from_label in enumerate(labels):
        for j, to_label in enumerate(labels):
            trans[i][j] = transitions.get((from_label, to_label), 0.0)

    # DP table: dp[t][label_idx] = list of (score, backpointer) tuples
    # where backpointer = (prev_label_idx, prev_rank) or None for t=0
    # We keep top N entries per cell
    dp = [[[] for _ in range(n_labels)] for _ in range(n_positions)]

    # Initialize t=0: emission score only, no transition
    for label_idx in range(n_labels):
        score = emission[0][label_idx]
        dp[0][label_idx].append((score, None))

    # Forward pass
    for t in range(1, n_positions):
        for curr_label in range(n_labels):
            # Collect all candidates from previous position
            candidates = []
            for prev_label in range(n_labels):
                for rank, (prev_score, _) in enumerate(dp[t-1][prev_label]):
                    # Score = previous path score + transition + emission
                    score = prev_score + trans[prev_label][curr_label] + emission[t][curr_label]
                    candidates.append((score, (prev_label, rank)))

            # Sort by score descending and keep top N
            candidates.sort(key=lambda x: x[0], reverse=True)
            dp[t][curr_label] = candidates[:n_best]

    # Collect final candidates from all labels at last position
    final_candidates = []
    for label_idx in range(n_labels):
        for rank, (score, backptr) in enumerate(dp[n_positions-1][label_idx]):
            final_candidates.append((score, label_idx, rank))

    # Sort by score descending and keep top N
    final_candidates.sort(key=lambda x: x[0], reverse=True)
    final_candidates = final_candidates[:n_best]

    # Backtrack to recover label sequences
    results = []
    for final_score, final_label, final_rank in final_candidates:
        # Reconstruct path by backtracking
        path = [final_label]
        curr_label = final_label
        curr_rank = final_rank

        for t in range(n_positions - 1, 0, -1):
            _, backptr = dp[t][curr_label][curr_rank]
            if backptr is None:
                break
            prev_label, prev_rank = backptr
            path.append(prev_label)
            curr_label = prev_label
            curr_rank = prev_rank

        # Reverse to get path from start to end
        path.reverse()

        # Convert indices to label strings
        label_sequence = [labels[idx] for idx in path]
        results.append((label_sequence, final_score))

    return results


def crf_nbest_predict(tagger, input_text, n_best=5, dict_materials=None):
    """Run N-best CRF prediction on input text.

    This is the main entry point for N-best bunsetsu prediction.

    Args:
        tagger: pycrfsuite.Tagger with model already opened
        input_text: Input string (hiragana text to segment)
        n_best: Number of best sequences to return
        dict_materials: Optional dict from load_crf_feature_materials().
                        Passed through to add_features_per_line().

    Returns:
        List of (labels_list, score) tuples, sorted by score descending.
        Each labels_list is a list of label strings (e.g., ['B-L', 'I-L', 'B-P', ...])
        for each token in the input.

        Returns empty list if input is empty or has no tokens.
    """
    # Get model information
    info = tagger.info()
    labels = tagger.labels()
    state_features = info.state_features
    transitions = info.transitions

    # Tokenize and extract features
    tokens = tokenize_line(input_text)
    if not tokens:
        return []

    features = add_features_per_line(input_text, dict_materials)

    # Compute emission scores
    emission = crf_compute_emission_scores(features, state_features, labels)

    # Run N-best Viterbi
    results = crf_nbest_viterbi(emission, transitions, labels, n_best)

    return results


def get_crf_model_path():
    """Return the canonical path to the bunsetsu CRF model file.

    Returns:
        str: Path to bunsetsu.crfsuite in the user config directory
    """
    return os.path.join(get_user_config_dir(), 'bunsetsu.crfsuite')


def load_crf_tagger(model_path=None):
    """Load a CRF tagger from the model file.

    Args:
        model_path: Path to .crfsuite model file. If None, uses default path
                   from get_crf_model_path().

    Returns:
        pycrfsuite.Tagger if successful, None otherwise.
        Returns None if:
        - pycrfsuite is not installed
        - model file doesn't exist
        - model loading fails
    """
    try:
        import pycrfsuite
    except ImportError:
        logger.warning('pycrfsuite not installed. CRF tagger unavailable.')
        return None

    if model_path is None:
        model_path = get_crf_model_path()

    if not os.path.exists(model_path):
        logger.debug(f'CRF model file not found: {model_path}')
        return None

    try:
        tagger = pycrfsuite.Tagger()
        tagger.open(model_path)
        logger.info(f'Loaded CRF model from: {model_path}')
        return tagger
    except Exception as e:
        logger.error(f'Failed to load CRF model: {e}')
        return None


def labels_to_bunsetsu(tokens, labels):
    """Convert a sequence of tokens and CRF labels into bunsetsu segments.

    This function takes character-level tokens and their predicted labels
    (B-L, I-L, B-P, I-P or simple B, I) and groups them into bunsetsu
    (phrase units).

    Args:
        tokens: List of characters/tokens
        labels: List of predicted labels. Supported formats:
                - 4-class: B-L, I-L, B-P, I-P (Lookup vs Passthrough)
                - 2-class: B, I (simple boundary detection)

    Returns:
        list: List of (text, label) tuples where:
              - text: The bunsetsu text (joined tokens)
              - label: The full starting label of the bunsetsu (e.g., 'B-L', 'B-P', 'B')
              For simple B/I labels without type suffix, the label is 'B'.

    Example:
        >>> labels_to_bunsetsu(['き','ょ','う','は'], ['B-L','I-L','I-L','B-P'])
        [('きょう', 'B-L'), ('は', 'B-P')]

        >>> labels_to_bunsetsu(['き','ょ','う','は'], ['B','I','I','B'])
        [('きょう', 'B'), ('は', 'B')]

        # Consecutive Lookup bunsetsu are correctly separated:
        >>> labels_to_bunsetsu(
        ...     ['き','ぎ','ょ','う','し','ゅ','う','え','き'],
        ...     ['B-L','I-L','I-L','I-L','B-L','I-L','I-L','I-L','I-L'])
        [('きぎょう', 'B-L'), ('しゅうえき', 'B-L')]
    """
    if not tokens or not labels:
        return []

    bunsetsu_list = []
    current_bunsetsu = []
    current_label = None

    for token, label in zip(tokens, labels):
        # CRFsuite doesn't enforce BIO constraints, so the first label
        # may be 'I' instead of 'B'.  Treat a leading 'I' as 'B' since
        # there is no preceding bunsetsu to continue.
        if label.startswith('B') or current_label is None:
            # Start new bunsetsu - first flush the current one
            if current_bunsetsu:
                text = ''.join(current_bunsetsu)
                bunsetsu_list.append((text, current_label))

            # Start new bunsetsu
            current_bunsetsu = [token]
            # Promote I→B when forced (keep suffix like -L/-P intact)
            if label.startswith('I'):
                current_label = 'B' + label[1:]
            else:
                current_label = label
        else:
            # Continue current bunsetsu
            current_bunsetsu.append(token)

    # Flush last bunsetsu
    if current_bunsetsu:
        text = ''.join(current_bunsetsu)
        bunsetsu_list.append((text, current_label))

    return bunsetsu_list


def get_package_name():
    '''
    returns 'ibus-pskk'
    '''
    return 'ibus-pskk'


def get_version():
    return '0.0.1'


def get_datadir():
    '''
    Return the path to the data directory under user-independent (central)
    location (= not under the HOME)
    '''
    try:
        # Try to import the auto-generated paths from installation
        from . import paths
        return paths.INSTALL_ROOT
    except ImportError:
        # Fallback for development environment
        return '/opt/ibus-pskk'


def get_default_config_path():
    '''
    Return the path to the default config file in the system installation.
    This is the config.json that gets copied to user's home on first run.
    '''
    return os.path.join(get_datadir(), 'config.json')


def get_localedir():
    return '/usr/local/share/locale'


def get_user_config_dir():
    '''
    Return the path to the config directory under $HOME.
    Typically, it would be $HOME/.config/ibus-pskk
    '''
    return os.path.join(GLib.get_user_config_dir(), get_package_name())


def get_homedir():
    '''
    Return the path to the $HOME directory.
    '''
    return GLib.get_home_dir()


def get_config_data():
    '''
    This function is to load the config JSON file from the HOME/.config/ibus-pskk
    When the file is not present (e.g., after initial installation), it will copy
    the deafult config.json from the central location.

    Returns:
        tuple: (config_data, warnings_string) where warnings_string is empty if no warnings
    '''
    configfile_path = os.path.join(get_user_config_dir(), 'config.json')
    default_config_path = get_default_config_path()
    default_config = json.load(codecs.open(default_config_path))
    warnings = ""

    if(not os.path.exists(configfile_path)):
        warning_msg = f'config.json is not found under {get_user_config_dir()} . Copying the default config.json from {default_config_path} ..'
        logger.warning(warning_msg)
        warnings = warning_msg
        with open(configfile_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False)
        return(default_config, warnings)
    try:
        config_data = json.load(codecs.open(configfile_path))
    except json.decoder.JSONDecodeError as e:
        logger.error(f'Error loading the config.json under {get_user_config_dir()}')
        logger.error(e)
        logger.error(f'Using (but not copying) the default config.json from {default_config_path} ..')
        return get_default_config_data(), warnings

    for k in default_config:
        if k not in config_data:
            warning_msg = f'The key "{k}" was not found in the config.json under {get_user_config_dir()} . Copying the default key-value'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            config_data[k] = default_config[k]
        if type(config_data[k]) != type(default_config[k]):
            warning_msg = f'Type mismatch found for the key "{k}" between config.json under {get_user_config_dir()} and default config.json. Replacing the value of this key with the value in default config.json'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            config_data[k] = default_config[k]

    # Deep validation for nested structures like "dictionaries"
    if "dictionaries" in config_data and isinstance(config_data["dictionaries"], dict):
        dictionaries = config_data["dictionaries"]
        default_dictionaries = default_config.get("dictionaries", {"system": {}, "user": {}})
        needs_fix = False

        # Ensure "system" key exists and is a dict (or list for backwards compatibility)
        if "system" not in dictionaries:
            needs_fix = True
        elif not isinstance(dictionaries["system"], (dict, list)):
            warning_msg = f'The "dictionaries.system" key has invalid type (expected dict or list). Resetting to default.'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            dictionaries["system"] = default_dictionaries.get("system", {})

        # Ensure "user" key exists and is a dict (or list for backwards compatibility)
        if "user" not in dictionaries:
            needs_fix = True
        elif not isinstance(dictionaries["user"], (dict, list)):
            warning_msg = f'The "dictionaries.user" key has invalid type (expected dict or list). Resetting to default.'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            dictionaries["user"] = default_dictionaries.get("user", {})

        if needs_fix:
            warning_msg = f'The "dictionaries" key is missing required sub-keys (system/user). Adding defaults.'
            logger.warning(warning_msg)
            warnings += ("\n" if warnings else "") + warning_msg
            if "system" not in dictionaries:
                dictionaries["system"] = default_dictionaries.get("system", {})
            if "user" not in dictionaries:
                dictionaries["user"] = default_dictionaries.get("user", {})

    return config_data, warnings


def save_config_data(config_data):
    '''
    Save config data to the user config directory.

    Args:
        config_data: Dictionary containing configuration data to save

    Returns:
        bool: True if save was successful, False otherwise
    '''
    configfile_path = os.path.join(get_user_config_dir(), 'config.json')

    try:
        # Ensure the config directory exists
        os.makedirs(get_user_config_dir(), exist_ok=True)

        # Write the config file with proper formatting
        with open(configfile_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        logger.info(f'Configuration saved successfully to {configfile_path}')
        return True
    except Exception as e:
        logger.error(f'Error saving config.json to {configfile_path}')
        logger.error(e)
        return False


def get_default_config_data():
    default_config_path = get_default_config_path()
    if not os.path.exists(default_config_path):
        logger.error(f'config.json is not found under {get_default_config_path()}. Please check that installation was done without problem!')
        return None
    default_config = json.load(codecs.open(default_config_path))
    return default_config


def get_layout_data(config):
    layout_file_name = config['layout']
    layout_file_path = ''
    if os.path.exists(os.path.join(get_user_config_dir(), 'layouts', layout_file_name)):
        layout_file_path = os.path.join(get_user_config_dir(), 'layouts', layout_file_name)
    elif os.path.exists(os.path.join(get_datadir(), 'layouts', layout_file_name)):
        layout_file_path = os.path.join(get_datadir(), 'layouts', layout_file_name)
    else:
        layout_file_path = os.path.join(get_datadir(), 'layouts', 'shingeta.json')
    try:
        with open(layout_file_path) as layout_json:
            return json.load(layout_json)
    except: 
        logger.error(f'Error in loading layout file: {layout_file_path}')
    return None


def get_kanchoku_layout(config):
    kanchoku_layout_file_name = config['kanchoku_layout']
    kanchoku_layout_file_path = ''
    if os.path.exists(os.path.join(get_user_config_dir(), 'kanchoku_layouts', kanchoku_layout_file_name)):
        kanchoku_layout_file_path = os.path.join(get_user_config_dir(), 'kanchoku_layouts', kanchoku_layout_file_name)
    elif os.path.exists(os.path.join(get_user_config_dir(), kanchoku_layout_file_name)):
        kanchoku_layout_file_path = os.path.join(get_user_config_dir(), kanchoku_layout_file_name)
    elif os.path.exists(os.path.join(get_datadir(), 'kanchoku_layouts', kanchoku_layout_file_name)):
        kanchoku_layout_file_path = os.path.join(get_datadir(), 'kanchoku_layouts', kanchoku_layout_file_name)
    else:
        kanchoku_layout_file_path = os.path.join(get_datadir(), 'kanchoku_layouts', 'aki_code.json')
    try:
        with open(kanchoku_layout_file_path) as kanchoku_layout_json:
            return json.load(kanchoku_layout_json)
    except:
        logger.error(f'Error in loading kanchoku_layout file: {kanchoku_layout_file_path}')
    return None


def get_user_dictionaries_dir():
    """
    Return the path to the user dictionaries directory.
    Typically: $HOME/.config/ibus-pskk/dictionaries/
    """
    return os.path.join(get_user_config_dir(), 'dictionaries')


def get_dictionary_files(config=None):
    """
    Obtain the list of JSON dictionary file paths to be used for kana-kanji conversion.

    The returned list contains:
    1. system_dictionary.json (generated from system SKK dictionaries)
    2. user_dictionary.json (generated from user SKK files in dictionaries/)

    Args:
        config: Configuration dictionary. If None, will be loaded via get_config_data().
                (Currently unused, kept for API compatibility)

    Returns:
        list: List of absolute paths to JSON dictionary files that exist.
              Returns empty list if no dictionaries are found.
    """
    dictionary_files = []
    config_dir = get_user_config_dir()

    # 1. Check for system_dictionary.json
    system_dict_path = os.path.join(config_dir, 'system_dictionary.json')
    if os.path.exists(system_dict_path):
        dictionary_files.append(system_dict_path)
        logger.debug(f'Found system dictionary: {system_dict_path}')
    else:
        logger.debug(f'System dictionary not found: {system_dict_path}')

    # 2. Check for user_dictionary.json
    user_dict_path = os.path.join(config_dir, 'user_dictionary.json')
    if os.path.exists(user_dict_path):
        dictionary_files.append(user_dict_path)
        logger.debug(f'Found user dictionary: {user_dict_path}')
    else:
        logger.debug(f'User dictionary not found: {user_dict_path}')

    # 3. Check for extended_dictionary.json
    ext_dict_path = os.path.join(config_dir, 'extended_dictionary.json')
    if os.path.exists(ext_dict_path):
        dictionary_files.append(ext_dict_path)
        logger.debug(f'Found extended dictionary: {ext_dict_path}')
    else:
        logger.debug(f'Extended dictionary not found: {ext_dict_path}')

    # Log with appropriate level based on whether dictionaries were found
    if dictionary_files:
        logger.info(f'Dictionary files to use: {len(dictionary_files)} file(s)')
    else:
        logger.warning(f'No dictionary files found in {config_dir} - '
                      f'run "just generate-dictionaries" to create them')
    return dictionary_files


def generate_crf_feature_materials(output_path=None):
    """Pre-compute dictionary-derived CRF feature materials and save as JSON.

    Loads all dictionary JSON files (system, user, extended), merges them,
    and computes per-character statistics used as CRF features for bunsetsu
    boundary prediction.

    The output JSON contains four dicts keyed by single characters:
      - max_key_len_starting_with: longest yomi key starting with this char
      - max_key_len_ending_with: longest yomi key ending with this char
      - dict_entry_count_starting_with: total kanji entries across all yomi
            keys starting with this char
      - dict_entry_count_ending_with: total kanji entries across all yomi
            keys ending with this char

    Args:
        output_path: Where to write the JSON. Defaults to
                     ~/.config/ibus-pskk/crf_feature_materials.json

    Returns:
        str: Path to the written JSON file, or None on failure.
    """
    if output_path is None:
        output_path = os.path.join(get_user_config_dir(),
                                   'crf_feature_materials.json')

    # Load and merge all dictionaries (same logic as HenkanProcessor)
    dictionary_files = get_dictionary_files()
    merged = {}
    for file_path in dictionary_files:
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            for reading, candidates in data.items():
                if not isinstance(candidates, dict):
                    continue
                if reading not in merged:
                    merged[reading] = {}
                for candidate, count in candidates.items():
                    if not isinstance(count, (int, float)):
                        count = 1
                    if candidate in merged[reading]:
                        merged[reading][candidate] += count
                    else:
                        merged[reading][candidate] = count
        except Exception as e:
            logger.error(f'Failed to load dictionary for CRF materials: '
                         f'{file_path} - {e}')

    # Compute per-character statistics
    max_kl_start = {}
    max_kl_end = {}
    entry_ct_start = {}
    entry_ct_end = {}

    for yomi, candidates in merged.items():
        if not yomi:
            continue
        yomi_len = len(yomi)
        num_entries = len(candidates)
        first_char = yomi[0]
        last_char = yomi[-1]

        # Max key length
        if yomi_len > max_kl_start.get(first_char, 0):
            max_kl_start[first_char] = yomi_len
        if yomi_len > max_kl_end.get(last_char, 0):
            max_kl_end[last_char] = yomi_len

        # Entry counts
        entry_ct_start[first_char] = entry_ct_start.get(first_char, 0) + num_entries
        entry_ct_end[last_char] = entry_ct_end.get(last_char, 0) + num_entries

    materials = {
        'max_key_len_starting_with': max_kl_start,
        'max_key_len_ending_with': max_kl_end,
        'dict_entry_count_starting_with': entry_ct_start,
        'dict_entry_count_ending_with': entry_ct_end,
    }

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(materials, f, ensure_ascii=False, indent=2)
        logger.info(f'CRF feature materials written: {output_path} '
                    f'({len(max_kl_start)} chars)')
        return output_path
    except Exception as e:
        logger.error(f'Failed to write CRF feature materials: {e}')
        return None


def load_crf_feature_materials(path=None):
    """Load pre-computed CRF feature materials from JSON.

    Args:
        path: Path to the JSON file. Defaults to
              ~/.config/ibus-pskk/crf_feature_materials.json

    Returns:
        dict: The materials dict with 4 sub-dicts, or empty dict if
              the file is missing or invalid.
    """
    if path is None:
        path = os.path.join(get_user_config_dir(),
                            'crf_feature_materials.json')
    if not os.path.exists(path):
        logger.debug(f'CRF feature materials not found: {path}')
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            logger.info(f'Loaded CRF feature materials: {path}')
            return data
        logger.warning(f'Invalid CRF feature materials format: {path}')
        return {}
    except Exception as e:
        logger.error(f'Failed to load CRF feature materials: {path} - {e}')
        return {}


def get_skk_dicts_dir():
    """
    Return the path to the system SKK dictionaries directory.
    Typically: /opt/ibus-pskk/dictionaries/skk_dict/
    """
    return os.path.join(get_datadir(), 'dictionaries', 'skk_dict')


def parse_skk_dictionary_line(line):
    """
    Parse a single line from an SKK dictionary file.

    SKK format: reading /candidate1/candidate2/.../
    Example: あやこ /亜矢子/彩子/

    Args:
        line: A single line from the SKK dictionary

    Returns:
        tuple: (reading, candidates_list) or (None, None) if line is invalid/comment
    """
    # Skip empty lines and comments
    line = line.strip()
    if not line or line.startswith(';'):
        return None, None

    # Split on first space to separate reading from candidates
    parts = line.split(' ', 1)
    if len(parts) != 2:
        return None, None

    reading = parts[0]
    candidates_part = parts[1]

    # Parse candidates: /candidate1/candidate2/.../
    # Remove leading and trailing slashes, then split
    candidates_part = candidates_part.strip('/')
    if not candidates_part:
        return None, None

    # Split by '/' and filter out empty strings
    # Also handle annotations in SKK format: candidate;annotation
    candidates = []
    for candidate in candidates_part.split('/'):
        if candidate:
            # Remove annotation if present (e.g., "候補;注釈" -> "候補")
            candidate_surface = candidate.split(';')[0]
            if candidate_surface:
                candidates.append(candidate_surface)

    if not candidates:
        return None, None

    return reading, candidates


def convert_skk_to_json(skk_file_path, json_file_path=None):
    """
    Convert an SKK dictionary file to JSON format.

    Args:
        skk_file_path: Path to the SKK dictionary file
        json_file_path: Path for the output JSON file.
                       If None, will be auto-generated in user dictionaries dir.

    Returns:
        tuple: (success: bool, output_path: str or None, entry_count: int)
    """
    if not os.path.exists(skk_file_path):
        logger.error(f'SKK dictionary file not found: {skk_file_path}')
        return False, None, 0

    # Determine output path
    if json_file_path is None:
        # Create output path in user dictionaries directory
        dict_dir = get_user_dictionaries_dir()
        os.makedirs(dict_dir, exist_ok=True)

        # Use same filename but with .json extension
        base_name = os.path.basename(skk_file_path)
        # Remove common SKK extensions if present
        for ext in ['.utf8', '.txt', '.dic', '.SKK']:
            if base_name.endswith(ext):
                base_name = base_name[:-len(ext)]
                break
        json_file_path = os.path.join(dict_dir, base_name + '.json')

    # Parse SKK dictionary
    dictionary = {}
    entry_count = 0

    # Try different encodings (SKK dictionaries are typically EUC-JP or UTF-8)
    encodings = ['utf-8', 'euc-jp', 'shift-jis']
    file_content = None

    for encoding in encodings:
        try:
            with open(skk_file_path, 'r', encoding=encoding) as f:
                file_content = f.readlines()
            logger.debug(f'Successfully read {skk_file_path} with encoding {encoding}')
            break
        except UnicodeDecodeError:
            continue

    if file_content is None:
        logger.error(f'Failed to read {skk_file_path} with any supported encoding')
        return False, None, 0

    # Process each line
    for line in file_content:
        reading, candidates = parse_skk_dictionary_line(line)
        if reading and candidates:
            if reading in dictionary:
                # Merge candidates, incrementing count for existing ones
                existing = dictionary[reading]
                for candidate in candidates:
                    if candidate in existing:
                        existing[candidate] += 1
                    else:
                        existing[candidate] = 1
            else:
                # Initialize each candidate with count of 1
                dictionary[reading] = {candidate: 1 for candidate in candidates}
            entry_count += 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

    # Write JSON file
    try:
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f'Converted SKK dictionary to JSON: {json_file_path} ({entry_count} entries)')
        return True, json_file_path, entry_count
    except Exception as e:
        logger.error(f'Failed to write JSON dictionary: {e}')
        return False, None, 0


def convert_all_skk_dictionaries():
    """
    Convert all SKK dictionaries from the system directory to JSON format
    in the user dictionaries directory.

    Returns:
        list: List of tuples (filename, success, entry_count) for each file processed
    """
    skk_dir = get_skk_dicts_dir()
    results = []

    if not os.path.exists(skk_dir):
        logger.warning(f'SKK dictionaries directory not found: {skk_dir}')
        return results

    # Process all files in the SKK dictionaries directory
    for filename in os.listdir(skk_dir):
        skk_path = os.path.join(skk_dir, filename)
        if os.path.isfile(skk_path):
            success, output_path, entry_count = convert_skk_to_json(skk_path)
            results.append((filename, success, entry_count))

    return results


def generate_system_dictionary(output_path=None, source_weights=None):
    """
    Generate a merged system dictionary from SKK dictionary files.

    Reads SKK-format dictionary files and merges them into a single JSON file.
    The value for each candidate is the weighted occurrence count across all source files.

    SKK format: reading /candidate1/candidate2/.../
    Example: あい /愛/相/藍/

    Output JSON format: {reading: {candidate: count}}
    Example: {"あい": {"愛": 3, "相": 2, "藍": 1}}

    Higher count = appears in more dictionaries = should be ranked higher.

    Args:
        output_path: Path for the output JSON file.
                    If None, defaults to ~/.config/ibus-pskk/system_dictionary.json
        source_weights: Dict mapping full file paths to weight multipliers.
                       If None, all files in system dicts directory are used with weight 1.

    Returns:
        tuple: (success: bool, output_path: str or None, stats: dict)
               stats contains 'files_processed', 'total_readings', 'total_candidates',
               'okurigana_entries_expanded'
    """
    sys_dict_dir = get_skk_dicts_dir()
    stats = {
        'files_processed': 0,
        'total_readings': 0,
        'total_candidates': 0,
        'okurigana_entries_expanded': 0,
    }

    # Determine output path (system_dictionary.json goes in config dir)
    if output_path is None:
        config_dir = get_user_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        output_path = os.path.join(config_dir, 'system_dictionary.json')

    # If no weights specified, scan all files in the directory with weight 1
    if source_weights is None:
        if not os.path.exists(sys_dict_dir):
            logger.warning(f'System dictionaries directory not found: {sys_dict_dir}')
            return False, None, stats
        source_weights = {}
        for filename in os.listdir(sys_dict_dir):
            file_path = os.path.join(sys_dict_dir, filename)
            if os.path.isfile(file_path):
                source_weights[file_path] = 1

    # Merged dictionary: {reading: {candidate: weighted_count}}
    merged_dictionary = {}

    # Process each SKK dictionary file
    for file_path, weight_multiplier in source_weights.items():
        if not os.path.isfile(file_path):
            logger.warning(f'Dictionary file not found: {file_path}')
            continue

        # Try different encodings (SKK files may use various encodings)
        encodings = ['utf-8', 'euc-jp', 'shift-jis']
        file_content = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    file_content = f.readlines()
                logger.debug(f'Successfully read {file_path} with encoding {encoding}')
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            logger.warning(f'Failed to read {file_path} with any supported encoding, skipping')
            continue

        # Track candidates seen in this file to avoid double-counting within same file
        seen_in_this_file = {}  # {reading: set(candidates)}
        entries_added = 0

        # Process each line
        for line in file_content:
            reading, candidates = parse_skk_dictionary_line(line)
            if not reading or not candidates:
                continue

            # Check if this is an okurigana entry (reading ends with alphabet)
            if katsuyou.is_skk_okurigana_entry(reading):
                # Expand okurigana entry into all conjugated forms
                for candidate in candidates:
                    expanded = katsuyou.expand_skk_okurigana(
                        reading, candidate, weight_multiplier
                    )
                    if expanded:
                        stats['okurigana_entries_expanded'] += 1
                        for conj_reading, conj_surface, count in expanded:
                            # Track to avoid double-counting
                            if conj_reading not in seen_in_this_file:
                                seen_in_this_file[conj_reading] = set()
                            if conj_surface in seen_in_this_file[conj_reading]:
                                continue
                            seen_in_this_file[conj_reading].add(conj_surface)

                            # Add to merged dictionary
                            if conj_reading not in merged_dictionary:
                                merged_dictionary[conj_reading] = {}
                            if conj_surface in merged_dictionary[conj_reading]:
                                merged_dictionary[conj_reading][conj_surface] += count
                            else:
                                merged_dictionary[conj_reading][conj_surface] = count
                                entries_added += 1
            else:
                # Regular entry (no okurigana expansion needed)
                # Initialize tracking for this reading if needed
                if reading not in seen_in_this_file:
                    seen_in_this_file[reading] = set()

                # Initialize merged entry if needed
                if reading not in merged_dictionary:
                    merged_dictionary[reading] = {}

                # Add candidates, incrementing by weight (only once per file)
                for candidate in candidates:
                    if candidate not in seen_in_this_file[reading]:
                        seen_in_this_file[reading].add(candidate)
                        if candidate in merged_dictionary[reading]:
                            merged_dictionary[reading][candidate] += weight_multiplier
                        else:
                            merged_dictionary[reading][candidate] = weight_multiplier
                            entries_added += 1

        stats['files_processed'] += 1
        logger.debug(f'Processed {os.path.basename(file_path)}: {entries_added} new entries')

    # Calculate stats
    stats['total_readings'] = len(merged_dictionary)
    stats['total_candidates'] = sum(len(candidates) for candidates in merged_dictionary.values())

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f'Generated system dictionary: {output_path}')
        logger.info(f'Stats: {stats["files_processed"]} files, {stats["total_readings"]} readings, '
                   f'{stats["total_candidates"]} candidates, '
                   f'{stats["okurigana_entries_expanded"]} okurigana entries expanded')
        return True, output_path, stats
    except Exception as e:
        logger.error(f'Failed to write system dictionary: {e}')
        return False, None, stats


def generate_user_dictionary(output_path=None, source_weights=None):
    """
    Generate a merged user dictionary from SKK-format files in the user dictionaries directory.

    Reads SKK-format text files from ~/.config/ibus-pskk/dictionaries/ and merges them
    into a single JSON file. The value for each candidate is the weighted occurrence count.

    SKK format: reading /candidate1/candidate2/.../
    Example: あい /愛/相/

    Output JSON format: {reading: {candidate: count}}
    Example: {"あい": {"愛": 3, "相": 2}}

    Higher count = appears in more files = should be ranked higher.

    Args:
        output_path: Path for the output JSON file.
                    If None, defaults to ~/.config/ibus-pskk/user_dictionary.json
        source_weights: Dict mapping filenames to integer weights.
                       If None, all .txt files in dictionaries/ are used with weight 1.

    Returns:
        tuple: (success: bool, output_path: str or None, stats: dict)
               stats contains 'files_processed', 'total_readings', 'total_candidates'
    """
    user_dict_dir = get_user_dictionaries_dir()
    stats = {'files_processed': 0, 'total_readings': 0, 'total_candidates': 0}

    if not os.path.exists(user_dict_dir):
        logger.info(f'User dictionaries directory not found: {user_dict_dir}')
        # Create the directory for user convenience
        os.makedirs(user_dict_dir, exist_ok=True)
        logger.info(f'Created user dictionaries directory: {user_dict_dir}')
        return True, None, stats  # Success but no files to process

    # Determine output path (user_dictionary.json goes in config dir)
    if output_path is None:
        config_dir = get_user_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        output_path = os.path.join(config_dir, 'user_dictionary.json')

    # If no weights specified, scan all .txt files with weight 1
    if source_weights is None:
        source_weights = {}
        for filename in os.listdir(user_dict_dir):
            if filename.endswith('.txt'):
                source_weights[filename] = 1

    # First pass: count weighted occurrences
    # {reading: {candidate: weighted_count}}
    occurrence_counts = {}

    # Process each file in the user dictionaries directory
    for filename, weight in source_weights.items():
        file_path = os.path.join(user_dict_dir, filename)
        if not os.path.isfile(file_path):
            logger.warning(f'User dictionary file not found: {file_path}')
            continue

        # Try different encodings (SKK files may use various encodings)
        encodings = ['utf-8', 'euc-jp', 'shift-jis']
        file_content = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    file_content = f.readlines()
                logger.debug(f'Successfully read {file_path} with encoding {encoding}')
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            logger.warning(f'Failed to read {file_path} with any supported encoding, skipping')
            continue

        # Track candidates seen in this file to avoid double-counting within same file
        seen_in_this_file = {}  # {reading: set(candidates)}

        # Process each line
        for line in file_content:
            reading, candidates = parse_skk_dictionary_line(line)
            if not reading or not candidates:
                continue

            # Initialize tracking for this reading if needed
            if reading not in seen_in_this_file:
                seen_in_this_file[reading] = set()

            # Initialize occurrence entry if needed
            if reading not in occurrence_counts:
                occurrence_counts[reading] = {}

            # Add candidates, incrementing by weight (only once per file)
            for candidate in candidates:
                if candidate not in seen_in_this_file[reading]:
                    seen_in_this_file[reading].add(candidate)
                    if candidate in occurrence_counts[reading]:
                        occurrence_counts[reading][candidate] += weight
                    else:
                        occurrence_counts[reading][candidate] = weight

        stats['files_processed'] += 1
        logger.debug(f'Processed user dictionary: {filename} with weight {weight}')

    # Output format: {reading: {candidate: weighted_count}}
    # Higher count = appears in more files = should be ranked higher
    merged_dictionary = occurrence_counts

    # Calculate stats
    stats['total_readings'] = len(merged_dictionary)
    stats['total_candidates'] = sum(len(candidates) for candidates in merged_dictionary.values())


    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f'Generated user dictionary: {output_path}')
        logger.info(f'Stats: {stats["files_processed"]} files, {stats["total_readings"]} readings, {stats["total_candidates"]} candidates')
        return True, output_path, stats
    except Exception as e:
        logger.error(f'Failed to write user dictionary: {e}')
        return False, None, stats


def generate_extended_dictionary(config=None, source_paths=None):
    """
    Generate an extended dictionary by bridging kanchoku kanji with dictionary-based
    conversion via substring matching.

    Algorithm:
      1. Read the kanchoku layout → set of kanji produceable by kanchoku.
      2. Read the specified source dictionaries (SKK-format) → build
         yomi→single-kanji mappings, keeping only kanji that are in the kanchoku set.
      3. Load the already-generated system_dictionary.json and user_dictionary.json.
      4. For each entry in the combined dictionaries, check whether the reading
         contains a yomi from step 2 as a substring.  When a match is found AND
         the corresponding kanji appears in at least one candidate, create a new
         entry whose key has the matched yomi replaced by the kanji.
         NOTE: When a substring appears more than once in a reading (e.g. "いち"
         in "いちいち"), entries are generated for ALL occurrence positions.
         This behavior may change in the future.

    Args:
        config: Configuration dictionary (needed for kanchoku_layout).
                If None, will be loaded via get_config_data().
        source_paths: List of full file paths to SKK-format source dictionaries.
                     If None, no source files are processed (empty output).

    Returns:
        tuple: (success: bool, output_path: str or None, stats: dict)
               stats contains 'files_processed', 'yomi_kanji_mappings',
               'kanchoku_kanji_count', 'source_entries_scanned',
               'total_readings', 'total_candidates'
    """
    stats = {
        'files_processed': 0,
        'yomi_kanji_mappings': 0,
        'kanchoku_kanji_count': 0,
        'source_entries_scanned': 0,
        'total_readings': 0,
        'total_candidates': 0,
    }

    # Load config if not provided
    if config is None:
        config, _ = get_config_data()

    # Output path is hardcoded alongside system/user dictionaries
    config_dir = get_user_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    output_path = os.path.join(config_dir, 'extended_dictionary.json')

    # ── Step 1: Read kanchoku layout → set of produceable kanji ──
    kanchoku_layout = get_kanchoku_layout(config)
    if not kanchoku_layout:
        logger.error('Cannot generate extended dictionary: no kanchoku layout loaded')
        return False, None, stats

    kanchoku_kanji = set()
    for first_key, second_dict in kanchoku_layout.items():
        if isinstance(second_dict, dict):
            for second_key, kanji in second_dict.items():
                kanchoku_kanji.add(kanji)

    stats['kanchoku_kanji_count'] = len(kanchoku_kanji)
    logger.info(f'Extended dict generation: {len(kanchoku_kanji)} unique kanji from kanchoku layout')

    # ── Step 2: Read source dictionaries → yomi→single-kanji mappings ──
    # Only keep candidates that are a single character AND present in kanchoku_kanji.
    yomi_to_kanji = {}  # {yomi: set(kanji_chars)}

    if source_paths is None:
        source_paths = []

    for file_path in source_paths:
        if not os.path.isfile(file_path):
            logger.warning(f'Ext-dictionary source file not found: {file_path}')
            continue

        # Try different encodings
        encodings = ['utf-8', 'euc-jp', 'shift-jis']
        file_content = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    file_content = f.readlines()
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            logger.warning(f'Failed to read {file_path} with any supported encoding, skipping')
            continue

        for line in file_content:
            reading, candidates = parse_skk_dictionary_line(line)
            if not reading or not candidates:
                continue
            for candidate in candidates:
                if len(candidate) == 1 and candidate in kanchoku_kanji:
                    if reading not in yomi_to_kanji:
                        yomi_to_kanji[reading] = set()
                    yomi_to_kanji[reading].add(candidate)

        stats['files_processed'] += 1

    stats['yomi_kanji_mappings'] = sum(len(v) for v in yomi_to_kanji.values())
    logger.info(f'Extended dict generation: {stats["yomi_kanji_mappings"]} yomi→kanji mappings from {stats["files_processed"]} source files')

    # ── Step 3: Load system_dictionary.json and user_dictionary.json ──
    combined_dict = {}  # {reading: {candidate: count}}

    for dict_filename in ['system_dictionary.json', 'user_dictionary.json']:
        dict_path = os.path.join(config_dir, dict_filename)
        if not os.path.exists(dict_path):
            logger.debug(f'Dictionary not found for ext-dict generation: {dict_path}')
            continue
        try:
            with open(dict_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for reading, candidates in data.items():
                if not isinstance(candidates, dict):
                    continue
                if reading not in combined_dict:
                    combined_dict[reading] = {}
                for candidate, entry in candidates.items():
                    # Entry format: count (int) - higher count = better
                    # For legacy format {"POS": ..., "cost": ...}, convert to count
                    if isinstance(entry, dict):
                        count = -entry.get("cost", 0)  # Negate cost to get count
                    else:
                        count = entry if isinstance(entry, (int, float)) else 1
                    # Keep the higher count when merging (higher = better)
                    if candidate not in combined_dict[reading]:
                        combined_dict[reading][candidate] = count
                    else:
                        existing_count = combined_dict[reading][candidate]
                        if count > existing_count:
                            combined_dict[reading][candidate] = count
        except Exception as e:
            logger.warning(f'Failed to load {dict_path} for ext-dict generation: {e}')

    stats['source_entries_scanned'] = len(combined_dict)
    logger.info(f'Extended dict generation: {len(combined_dict)} entries from system/user dictionaries')

    # ── Step 4: Substring matching and replacement ──
    extended_dict = {}  # {new_reading: {candidate: count}}

    for reading, candidates in combined_dict.items():
        for yomi, kanji_set in yomi_to_kanji.items():
            # Find ALL occurrence positions of yomi in reading.
            # NOTE: This generates entries for every occurrence, including when
            # a substring appears multiple times.  This behavior may change
            # in the future.
            positions = []
            start = 0
            while True:
                pos = reading.find(yomi, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1  # Allow overlapping matches

            if not positions:
                continue

            for pos in positions:
                for kanji in kanji_set:
                    # Only create an entry if the kanji actually appears
                    # in at least one candidate of the original entry.
                    # Skip single-character candidates — those are already
                    # directly produceable via kanchoku and would be noise.
                    matching_candidates = {
                        c: count for c, count in candidates.items() if kanji in c and len(c) > 1
                    }
                    if not matching_candidates:
                        continue

                    # Build new reading: replace the matched yomi with kanji
                    new_reading = reading[:pos] + kanji + reading[pos + len(yomi):]

                    # Merge into extended dictionary
                    if new_reading not in extended_dict:
                        extended_dict[new_reading] = {}
                    for candidate, count in matching_candidates.items():
                        # Keep entry with higher count (higher = better)
                        if candidate not in extended_dict[new_reading]:
                            extended_dict[new_reading][candidate] = count
                        else:
                            existing_count = extended_dict[new_reading][candidate]
                            if count > existing_count:
                                extended_dict[new_reading][candidate] = count

    # Calculate output stats
    stats['total_readings'] = len(extended_dict)
    stats['total_candidates'] = sum(len(c) for c in extended_dict.values())
    logger.info(f'Extended dict generation: {stats["total_readings"]} readings, {stats["total_candidates"]} candidates')

    # Write output
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(extended_dict, f, ensure_ascii=False, indent=2)
        logger.info(f'Generated extended dictionary: {output_path}')
        return True, output_path, stats
    except Exception as e:
        logger.error(f'Failed to write extended dictionary: {e}')
        return False, None, stats
