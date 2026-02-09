#!/usr/bin/env python3
"""
MeCab Sentence Processor for CRF Training Data

This script processes text files (e.g., from aozora_bunko_retrieval.py) and:
1. Splits text into sentences (on Japanese punctuation + newlines)
2. Runs MeCab morphological analysis on each sentence
3. Extracts hiragana readings and performs dictionary-based optimal segmentation
   using a Viterbi/DP approach that prefers longer dictionary matches
4. Outputs one line per sentence with segments as "reading/POS"

POS Normalization:
    動詞, 助動詞     → 動
    形容詞, 形状詞, 副詞 → 形
    名詞           → 名
    その他          → 他

Usage:
    python mecab_sentence_processor.py input.txt
    python mecab_sentence_processor.py input.txt -o output.txt
    python mecab_sentence_processor.py input.txt -d /path/to/dict/dir

Test/Debug mode (single sentence with verbose output):
    python mecab_sentence_processor.py -t "今日は天気が良い"

Output format (surface/POS with original kanji):
    今日/名 は/他 天気/名 が/他 良い/形

The script loads dictionaries from ~/.config/ibus-pskk/ (or specified directory)
to perform optimal segmentation based on known vocabulary.
"""

import argparse
import json
import os
import re
import sys

try:
    import MeCab
    HAS_MECAB = True
except ImportError:
    HAS_MECAB = False


# ============================================================================
# Scoring Parameters for Viterbi Segmentation
# ============================================================================
# These can be tuned later for optimal segmentation behavior
LENGTH_BONUS = 2  # Bonus multiplier for match length
WORD_BONUS = 2    # Fixed bonus for finding a dictionary match


# ============================================================================
# POS Normalization Rules (order matters - first match wins)
# ============================================================================
# Each rule is a tuple of (set of MeCab POS values, normalized POS string)
# Rules are applied in order; first matching rule wins
POS_NORMALIZATION_RULES = [
    ({"動詞", "助動詞"}, "動"),
    ({"形容詞", "形状詞", "副詞"}, "形"),
    ({"名詞"}, "名"),
]
DEFAULT_POS = "他"  # Used when no rule matches


# ============================================================================
# Dictionary Loading and Merging
# ============================================================================

def get_default_dictionary_dir() -> str:
    """Get the default dictionary directory path.

    Returns:
        Path to ~/.config/ibus-pskk/
    """
    home = os.path.expanduser("~")
    return os.path.join(home, ".config", "ibus-pskk")


def load_dictionary(dict_path: str) -> dict:
    """Load a single dictionary JSON file.

    Args:
        dict_path: Path to dictionary JSON file

    Returns:
        Dictionary mapping reading -> {candidate -> {"POS": str, "cost": float}}
        Returns empty dict if file doesn't exist or has errors.
    """
    if not os.path.exists(dict_path):
        return {}

    try:
        with open(dict_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load dictionary {dict_path}: {e}", file=sys.stderr)
        return {}


def merge_dictionaries(dict1: dict, dict2: dict) -> dict:
    """Merge two dictionaries, keeping the entry with lower cost for duplicates.

    Args:
        dict1: First dictionary
        dict2: Second dictionary

    Returns:
        Merged dictionary
    """
    merged = {}

    # Add all entries from dict1
    for reading, candidates in dict1.items():
        if reading not in merged:
            merged[reading] = {}
        for candidate, entry in candidates.items():
            if isinstance(entry, dict):
                cost = entry.get("cost", 0)
            else:
                cost = entry  # Legacy format
            if candidate not in merged[reading]:
                merged[reading][candidate] = cost
            else:
                merged[reading][candidate] = min(merged[reading][candidate], cost)

    # Add entries from dict2
    for reading, candidates in dict2.items():
        if reading not in merged:
            merged[reading] = {}
        for candidate, entry in candidates.items():
            if isinstance(entry, dict):
                cost = entry.get("cost", 0)
            else:
                cost = entry
            if candidate not in merged[reading]:
                merged[reading][candidate] = cost
            else:
                merged[reading][candidate] = min(merged[reading][candidate], cost)

    return merged


def load_combined_dictionary(dict_dir: str = None) -> dict:
    """Load and merge system_dictionary.json and user_dictionary.json.

    Args:
        dict_dir: Directory containing dictionaries. Defaults to ~/.config/ibus-pskk/

    Returns:
        Merged dictionary mapping reading -> {candidate -> cost}
    """
    if dict_dir is None:
        dict_dir = get_default_dictionary_dir()

    system_dict_path = os.path.join(dict_dir, "system_dictionary.json")
    user_dict_path = os.path.join(dict_dir, "user_dictionary.json")

    system_dict = load_dictionary(system_dict_path)
    user_dict = load_dictionary(user_dict_path)

    merged = merge_dictionaries(system_dict, user_dict)

    print(f"Loaded dictionary: {len(merged):,} readings")
    return merged


def build_reading_set(dictionary: dict) -> set:
    """Build a set of all dictionary readings for fast lookup.

    Args:
        dictionary: The merged dictionary

    Returns:
        Set of all reading strings (hiragana keys)
    """
    return set(dictionary.keys())


# ============================================================================
# Katakana to Hiragana Conversion
# ============================================================================

def katakana_to_hiragana(text: str) -> str:
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


# ============================================================================
# POS Normalization
# ============================================================================

def normalize_pos_for_segment(pos: str) -> str:
    """Normalize a MeCab POS to simplified POS using configured rules.

    Rules are applied in order; first matching rule wins.

    Args:
        pos: MeCab POS string (e.g., "動詞", "名詞", "助詞")

    Returns:
        Normalized POS string ("動", "形", "名", or "他")
    """
    for pos_set, normalized in POS_NORMALIZATION_RULES:
        if pos in pos_set:
            return normalized
    return DEFAULT_POS


# ============================================================================
# MeCab Yomi Extraction
# ============================================================================

def is_katakana_string(text: str) -> bool:
    """Check if a string consists entirely of katakana (and common extensions).

    Args:
        text: String to check

    Returns:
        True if the string is pure katakana (including ー and ・)
    """
    if not text:
        return False
    for c in text:
        cp = ord(c)
        # Katakana range: 0x30A0 (゠) to 0x30FF (ヿ)
        # Also allow ー (prolonged sound mark) and some punctuation
        if not (0x30A0 <= cp <= 0x30FF or c in 'ー・'):
            return False
    return True


def find_reading_in_features(features: list, surface: str) -> str:
    """Find the katakana reading from MeCab feature fields.

    Different MeCab dictionaries have different field orders:
    - IPA dict: 品詞,細分類1,細分類2,細分類3,活用型,活用形,原形,読み,発音
                Index 7 = 読み (reading), Index 8 = 発音 (pronunciation)
    - UniDic:   品詞1,...,語彙素読み(6),語彙素(7),書字形(8),発音形出現形(9),...
                Index 6 = lemma reading, Index 9 = surface form reading
                For conjugated words, index 9 has the correct surface reading

    This function searches for a pure katakana field that represents the reading.
    Priority is given to surface form reading positions over lemma reading positions.

    Args:
        features: List of MeCab feature fields
        surface: The surface form (fallback)

    Returns:
        The reading string (may be katakana or the surface as fallback)
    """
    # Reading field positions ordered by priority:
    # - Index 17: UniDic 仮名形出現形 - kana representation of surface form
    #             This gives correct readings for BOTH:
    #             - Particles: は→ハ (not ワ which is pronunciation)
    #             - Conjugated forms: で→デ (not ダ which is lemma)
    # - Index 7, 8: IPA dict reading positions (読み, 発音)
    # - Index 9: UniDic 発音形出現形 - phonetic pronunciation (は→ワ, not ideal)
    # - Index 6: UniDic 語彙素読み - lemma reading (で→ダ, not ideal for conjugated)
    # - Others: fallback positions
    reading_positions = [17, 7, 8, 19, 9, 6, 10, 11, 20, 21, 24]

    for idx in reading_positions:
        if idx < len(features):
            field = features[idx]
            if field and field != '*' and is_katakana_string(field):
                return field

    # If no katakana reading found, fall back to surface
    return surface


def extract_yomi_from_mecab(tagger, sentence: str) -> str:
    """Extract the full hiragana reading of a sentence using MeCab.

    MeCab outputs readings in katakana. This function extracts them
    and converts to hiragana.

    Args:
        tagger: MeCab tagger instance
        sentence: Input sentence

    Returns:
        The sentence reading in hiragana (concatenated morpheme readings)
    """
    node = tagger.parseToNode(sentence)
    readings = []

    while node:
        if node.surface:
            features = node.feature.split(',')
            reading = find_reading_in_features(features, node.surface)
            readings.append(katakana_to_hiragana(reading))
        node = node.next

    return ''.join(readings)


def extract_morphemes_with_positions(tagger, sentence: str) -> list:
    """Extract morphemes with their positions in the hiragana reading.

    This function tracks where each morpheme's reading starts and ends
    in the concatenated hiragana string, enabling position-to-POS mapping
    and surface form recovery.

    Args:
        tagger: MeCab tagger instance
        sentence: Input sentence

    Returns:
        List of (start_pos, end_pos, hiragana_reading, pos, surface) tuples
        where positions are indices in the concatenated hiragana reading.
    """
    node = tagger.parseToNode(sentence)
    morphemes = []
    current_pos = 0

    while node:
        if node.surface:
            features = node.feature.split(',')
            pos = features[0]  # Main POS category (品詞)
            surface = node.surface  # Original surface form (with kanji)

            # Get reading using robust field detection
            reading = katakana_to_hiragana(find_reading_in_features(features, node.surface))

            start = current_pos
            end = current_pos + len(reading)
            morphemes.append((start, end, reading, pos, surface))
            current_pos = end

        node = node.next

    return morphemes


def get_pos_at_position(morphemes: list, position: int) -> str:
    """Find the POS of the morpheme containing the given position.

    Args:
        morphemes: List of (start, end, reading, pos, surface) tuples
        position: Character position in the hiragana reading

    Returns:
        POS string of the morpheme at that position, or empty string if not found
    """
    for start, end, reading, pos, surface in morphemes:
        if start <= position < end:
            return pos
    return ""  # Should not happen if position is valid


def get_surface_for_segment(morphemes: list, seg_start: int, seg_end: int) -> str:
    """Get the original surface text for a segment defined by reading positions.

    This function maps a segment (defined by positions in the hiragana reading)
    back to the corresponding original surface text (with kanji).

    Args:
        morphemes: List of (start, end, reading, pos, surface) tuples
        seg_start: Start position of segment in hiragana reading
        seg_end: End position of segment in hiragana reading

    Returns:
        The corresponding surface text. If the segment aligns with morpheme
        boundaries, returns concatenated surfaces. For partial morpheme
        coverage, returns the reading (hiragana) for that portion.
    """
    result_parts = []
    current_pos = seg_start

    while current_pos < seg_end:
        # Find the morpheme containing current_pos
        found = False
        for m_start, m_end, m_reading, m_pos, m_surface in morphemes:
            if m_start <= current_pos < m_end:
                found = True
                # Check if segment covers this morpheme completely or partially
                if current_pos == m_start and seg_end >= m_end:
                    # Segment covers entire morpheme (or more)
                    result_parts.append(m_surface)
                    current_pos = m_end
                else:
                    # Partial coverage - use hiragana reading for this portion
                    # Calculate how much of this morpheme is covered
                    portion_start = current_pos - m_start
                    portion_end = min(seg_end, m_end) - m_start
                    result_parts.append(m_reading[portion_start:portion_end])
                    current_pos = m_start + portion_end
                break

        if not found:
            # Should not happen, but fallback to advancing by 1
            current_pos += 1

    return ''.join(result_parts)


# ============================================================================
# Dictionary-Based Optimal Segmentation (Viterbi/DP)
# ============================================================================

def find_longest_match_length(sentence: str, start_idx: int, reading_set: set,
                               max_len: int = 20) -> int:
    """Find the length of the longest dictionary match starting at start_idx.

    Args:
        sentence: The hiragana sentence string
        start_idx: Starting index to search from
        reading_set: Set of dictionary readings for fast lookup
        max_len: Maximum match length to check (optimization)

    Returns:
        Length of the longest match, or 0 if no match found
    """
    longest = 0
    remaining = len(sentence) - start_idx

    # Check substrings of decreasing length for efficiency
    for length in range(min(max_len, remaining), 0, -1):
        substring = sentence[start_idx:start_idx + length]
        if substring in reading_set:
            longest = length
            break  # Found longest, no need to check shorter

    return longest


def calculate_local_scores(sentence: str, reading_set: set,
                           length_bonus: float = LENGTH_BONUS,
                           word_bonus: float = WORD_BONUS) -> list:
    """Calculate local scores for each position in the sentence.

    For each position i:
    - If a dictionary match exists starting at i:
      score[i] = length_bonus * longest_match_length + word_bonus
    - Otherwise: score[i] = 0

    Args:
        sentence: The hiragana sentence string
        reading_set: Set of dictionary readings
        length_bonus: Multiplier for match length
        word_bonus: Fixed bonus for any match

    Returns:
        List of (score, longest_match_length) tuples for each position
    """
    n = len(sentence)
    scores = []

    for i in range(n):
        match_len = find_longest_match_length(sentence, i, reading_set)
        if match_len > 0:
            score = length_bonus * match_len + word_bonus
        else:
            score = 0
        scores.append((score, match_len))

    return scores


def viterbi_segment(sentence: str, reading_set: set,
                    length_bonus: float = LENGTH_BONUS,
                    word_bonus: float = WORD_BONUS) -> list:
    """Segment a hiragana sentence using Viterbi/DP for optimal word boundaries.

    Finds the segmentation that maximizes the sum of local scores,
    preferring longer dictionary matches and fewer segments.

    Args:
        sentence: The hiragana sentence string
        reading_set: Set of dictionary readings
        length_bonus: Multiplier for match length
        word_bonus: Fixed bonus for any match

    Returns:
        List of segmented words (hiragana strings)
    """
    n = len(sentence)
    if n == 0:
        return []

    # Calculate local scores for each position
    local_scores = calculate_local_scores(sentence, reading_set, length_bonus, word_bonus)

    # dp[i] = (best_score_to_reach_i, previous_position)
    # We want to find the best path from position 0 to position n
    INF = float('-inf')
    dp = [(INF, -1) for _ in range(n + 1)]
    dp[0] = (0, -1)  # Start position with score 0

    for i in range(n):
        if dp[i][0] == INF:
            continue  # Can't reach this position

        current_score = dp[i][0]
        local_score, match_len = local_scores[i]

        if match_len > 0:
            # We have a dictionary match - jump by match_len
            next_pos = i + match_len
            new_score = current_score + local_score
            if new_score > dp[next_pos][0]:
                dp[next_pos] = (new_score, i)

        # Always allow single character fallback (score = 0 for this segment)
        # This ensures we can always reach the end
        next_pos = i + 1
        new_score = current_score + 0  # No bonus for single char fallback
        if new_score > dp[next_pos][0]:
            dp[next_pos] = (new_score, i)

    # Backtrack to find the optimal segmentation
    segments = []
    pos = n
    while pos > 0:
        prev_pos = dp[pos][1]
        if prev_pos == -1:
            # Should not happen if DP is correct
            break
        segment = sentence[prev_pos:pos]
        segments.append(segment)
        pos = prev_pos

    segments.reverse()
    return segments


def segment_sentence(sentence: str, reading_set: set) -> list:
    """High-level function to segment a hiragana sentence.

    Args:
        sentence: Hiragana sentence string
        reading_set: Set of dictionary readings

    Returns:
        List of segmented words
    """
    return viterbi_segment(sentence, reading_set)


def segment_sentence_with_pos(hiragana_reading: str, reading_set: set,
                               morphemes: list) -> list:
    """Segment a hiragana sentence, map back to surface forms, and add POS.

    The segmentation is performed on the hiragana reading (for dictionary lookup),
    then each segment is mapped back to the original surface text (with kanji).
    POS is determined by looking at the leftmost character's morpheme.

    Args:
        hiragana_reading: Full hiragana reading of the sentence
        reading_set: Set of dictionary readings
        morphemes: List of (start, end, reading, pos, surface) from MeCab

    Returns:
        List of "surface/POS" strings (e.g., ["今日/名", "は/他", "良い/形"])
    """
    segments = viterbi_segment(hiragana_reading, reading_set)

    result = []
    current_pos = 0

    for segment in segments:
        seg_start = current_pos
        seg_end = current_pos + len(segment)

        # Get POS of the leftmost character in this segment
        mecab_pos = get_pos_at_position(morphemes, seg_start)
        normalized_pos = normalize_pos_for_segment(mecab_pos)

        # Get the original surface form (with kanji) for this segment
        surface = get_surface_for_segment(morphemes, seg_start, seg_end)

        result.append(f"{surface}/{normalized_pos}")
        current_pos = seg_end

    return result


def split_into_sentences(text: str) -> list:
    """Split text into sentences based on Japanese punctuation and newlines.

    Args:
        text: Input text

    Returns:
        List of sentences (non-empty strings)
    """
    # Split on Japanese sentence-ending punctuation (keeping the punctuation)
    # and also on newlines
    # The regex splits after 。！？ or on newlines
    parts = re.split(r'(?<=[。！？])|(?:\r?\n)+', text)

    # Filter out empty strings and whitespace-only strings
    sentences = [s.strip() for s in parts if s and s.strip()]

    return sentences


def process_sentence_with_mecab(tagger, sentence: str) -> tuple:
    """Process a single sentence with MeCab (legacy, without dictionary segmentation).

    Args:
        tagger: MeCab tagger instance
        sentence: Input sentence

    Returns:
        Tuple of (formatted_line, morpheme_count)
    """
    node = tagger.parseToNode(sentence)
    morphemes = []

    while node:
        # Skip BOS (beginning of sentence) and EOS (end of sentence) nodes
        if node.surface:
            features = node.feature.split(',')
            pos = features[0]  # Main POS category (品詞)
            morphemes.append(f"{node.surface}/{pos}")
        node = node.next

    return ' '.join(morphemes), len(morphemes)


def process_sentence_full(tagger, sentence: str, reading_set: set) -> tuple:
    """Process a sentence with MeCab + dictionary-based Viterbi segmentation.

    This function:
    1. Extracts morphemes and their positions from MeCab
    2. Gets the full hiragana reading
    3. Segments using Viterbi/DP with dictionary lookup
    4. Adds POS information based on leftmost character of each segment

    Args:
        tagger: MeCab tagger instance
        sentence: Input sentence
        reading_set: Set of dictionary readings for segmentation

    Returns:
        Tuple of (formatted_line, segment_count)
        formatted_line is space-separated "segment/POS" strings
    """
    # Get morphemes with position information
    morphemes = extract_morphemes_with_positions(tagger, sentence)

    if not morphemes:
        return '', 0

    # Get full hiragana reading
    full_reading = ''.join(reading for _, _, reading, _ in morphemes)

    if not full_reading:
        return '', 0

    # Segment with POS
    segments_with_pos = segment_sentence_with_pos(full_reading, reading_set, morphemes)

    return ' '.join(segments_with_pos), len(segments_with_pos)


def test_sentence(sentence: str, dict_dir: str = None) -> None:
    """Test processing a single sentence with verbose output showing all steps.

    This is a debug function that shows:
    1. Original MeCab morpheme analysis
    2. Morphemes with position mapping
    3. Full hiragana reading
    4. Viterbi/DP segmentation result
    5. Final output with POS

    Args:
        sentence: Input sentence to test
        dict_dir: Directory containing dictionaries (default: ~/.config/ibus-pskk/)
    """
    if not HAS_MECAB:
        print("Error: 'mecab-python3' library is required.")
        sys.exit(1)

    print("=" * 60)
    print("TEST MODE: Processing single sentence")
    print("=" * 60)

    # Step 0: Show input
    print(f"\n[0] INPUT SENTENCE:")
    print(f"    {sentence}")

    # Load dictionary
    print(f"\n[1] LOADING DICTIONARY...")
    dictionary = load_combined_dictionary(dict_dir)
    reading_set = build_reading_set(dictionary)
    print(f"    Loaded {len(reading_set):,} unique readings")

    # Initialize MeCab
    tagger = MeCab.Tagger()

    # Step 1: Show raw MeCab output with reading detection
    print(f"\n[2] RAW MECAB OUTPUT (with reading detection):")
    node = tagger.parseToNode(sentence)
    while node:
        if node.surface:
            features = node.feature.split(',')
            detected_reading = find_reading_in_features(features, node.surface)
            is_fallback = not is_katakana_string(detected_reading)
            fallback_marker = " (fallback to surface)" if is_fallback else ""
            print(f"    {node.surface}\t→ {detected_reading}{fallback_marker}")
            print(f"        features: {node.feature[:80]}{'...' if len(node.feature) > 80 else ''}")
        node = node.next

    # Step 2: Extract morphemes with positions
    print(f"\n[3] MORPHEMES WITH POSITION MAPPING:")
    morphemes = extract_morphemes_with_positions(tagger, sentence)
    print(f"    {'Start':>5} {'End':>5}  {'Reading':<10} {'Surface':<8} {'POS'}")
    print(f"    {'-'*5} {'-'*5}  {'-'*10} {'-'*8} {'-'*12}")
    for start, end, reading, pos, surface in morphemes:
        print(f"    {start:>5} {end:>5}  {reading:<10} {surface:<8} {pos}")

    # Step 3: Show full hiragana reading
    full_reading = ''.join(reading for _, _, reading, _, _ in morphemes)
    print(f"\n[4] FULL HIRAGANA READING:")
    print(f"    {full_reading}")

    # Step 4: Show Viterbi segmentation (without POS)
    print(f"\n[5] VITERBI/DP SEGMENTATION (on reading):")
    segments = viterbi_segment(full_reading, reading_set)
    print(f"    Segments: {segments}")
    print(f"    Joined:   {' | '.join(segments)}")

    # Step 5: Show surface mapping and POS assignment for each segment
    print(f"\n[6] SURFACE MAPPING + POS ASSIGNMENT:")
    current_pos = 0
    for segment in segments:
        seg_start = current_pos
        seg_end = current_pos + len(segment)
        mecab_pos = get_pos_at_position(morphemes, seg_start)
        normalized = normalize_pos_for_segment(mecab_pos)
        surface = get_surface_for_segment(morphemes, seg_start, seg_end)
        print(f"    reading '{segment}' [{seg_start}:{seg_end}] → surface '{surface}' → POS: {mecab_pos} → {normalized}")
        current_pos = seg_end

    # Step 6: Show final output
    print(f"\n[7] FINAL OUTPUT:")
    segments_with_pos = segment_sentence_with_pos(full_reading, reading_set, morphemes)
    print(f"    {' '.join(segments_with_pos)}")

    print("\n" + "=" * 60)


def process_file(input_path: str, output_path: str, dict_dir: str = None) -> None:
    """Process a text file with MeCab and dictionary-based segmentation.

    Args:
        input_path: Path to input text file
        output_path: Path to output file
        dict_dir: Directory containing dictionaries (default: ~/.config/ibus-pskk/)
    """
    if not HAS_MECAB:
        print("Error: 'mecab-python3' library is required.")
        print("Install with: pip install mecab-python3")
        print("Also ensure MeCab is installed on your system.")
        sys.exit(1)

    # Load dictionary for segmentation
    print("Loading dictionary...")
    dictionary = load_combined_dictionary(dict_dir)
    reading_set = build_reading_set(dictionary)
    print(f"Dictionary ready: {len(reading_set):,} unique readings")

    print(f"Reading: {input_path}")

    # Read input file
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Split into sentences
    print("Splitting into sentences...")
    sentences = split_into_sentences(text)
    print(f"Found {len(sentences):,} sentences")

    # Initialize MeCab tagger
    tagger = MeCab.Tagger()

    # Process each sentence with dictionary-based segmentation
    print("Processing with MeCab + dictionary segmentation...")
    output_lines = []
    total_segments = 0

    for sentence in sentences:
        line, segment_count = process_sentence_full(tagger, sentence, reading_set)
        if line:  # Only add non-empty lines
            output_lines.append(line)
            total_segments += segment_count

    # Write output
    print(f"Writing: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
        f.write('\n')  # Trailing newline

    print(f"\nProcessing complete:")
    print(f"  Sentences:  {len(output_lines):,}")
    print(f"  Segments:   {total_segments:,}")
    print(f"  Output:     {output_path}")


def get_output_path(input_path: str) -> str:
    """Generate default output path by adding _mecab suffix.

    Args:
        input_path: Input file path

    Returns:
        Output file path (e.g., "input.txt" -> "input_mecab.txt")
    """
    base, ext = os.path.splitext(input_path)
    return f"{base}_mecab{ext}"


def main():
    parser = argparse.ArgumentParser(
        description='Process text files with MeCab for CRF training data.'
    )
    parser.add_argument(
        'input',
        nargs='?',
        default=None,
        help='Path to input text file (UTF-8)'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Path to output file (default: <input>_mecab.txt in same directory as script)'
    )
    parser.add_argument(
        '-d', '--dict-dir',
        default=None,
        help='Directory containing dictionaries (default: ~/.config/ibus-pskk/)'
    )
    parser.add_argument(
        '-t', '--test',
        default=None,
        metavar='SENTENCE',
        help='Test mode: process a single sentence and show all intermediate steps'
    )
    args = parser.parse_args()

    # Test mode: process single sentence with verbose output
    if args.test:
        test_sentence(args.test, args.dict_dir)
        return

    # Normal mode: require input file
    if not args.input:
        parser.error("the following arguments are required: input (or use --test for single sentence)")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_basename = os.path.basename(args.input)
        base, ext = os.path.splitext(input_basename)
        output_filename = f"{base}_mecab{ext}"
        output_path = os.path.join(script_dir, output_filename)

    process_file(args.input, output_path, args.dict_dir)


if __name__ == '__main__':
    main()
