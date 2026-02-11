#!/usr/bin/env python3
"""
MeCab Sentence Processor

This script processes a text file through MeCab morphological analyzer,
sentence by sentence.

Usage:
    python mecab_sentence_processor.py input.txt
    python mecab_sentence_processor.py /path/to/document.txt

Output:
    Creates two files in the same directory as the input file:
    - FILENAME_mecab_processed.txt: Full MeCab output for each sentence
    - FILENAME_extracted_vocab.txt: Extracted nouns in SKK dictionary format

Requirements:
    - MeCab command-line tool must be installed and available in PATH
"""

import argparse
import os
import re
import subprocess
import sys


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


def split_into_sentences(text: str) -> list:
    """Split text into sentences using Japanese punctuation and newlines.

    Splits on:
    - Japanese sentence-ending punctuation: 。！？
    - Full-width variants: ．！？
    - Newlines

    Args:
        text: Input text string

    Returns:
        List of sentence strings (empty strings filtered out)
    """
    # First split by newlines
    lines = text.split('\n')

    sentences = []
    for line in lines:
        # Split each line by Japanese sentence-ending punctuation
        # Keep the punctuation with the sentence by using a lookbehind pattern
        # Pattern: split after 。！？ (and full-width variants)
        parts = re.split(r'(?<=[。！？．])', line)

        for part in parts:
            stripped = part.strip()
            if stripped:
                sentences.append(stripped)

    return sentences


def run_mecab(sentence: str) -> str:
    """Run MeCab on a single sentence.

    Args:
        sentence: Input sentence string

    Returns:
        MeCab output as string

    Raises:
        RuntimeError: If MeCab command fails
    """
    try:
        result = subprocess.run(
            ['mecab'],
            input=sentence,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except FileNotFoundError:
        print("Error: MeCab command not found.", file=sys.stderr)
        print("Please install MeCab and ensure it's in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"MeCab failed: {e.stderr}")


def extract_nouns_from_mecab(mecab_output: str) -> list:
    """Extract nouns with their readings from MeCab output.

    MeCab output format (IPA dictionary):
        surface\tPOS,POS1,POS2,POS3,活用型,活用形,原形,読み,発音
        天気\t名詞,一般,*,*,*,*,天気,テンキ,テンキ

    Filters out:
        - Entries where yomi == surface (e.g., "それ /それ/")

    Args:
        mecab_output: Raw MeCab output string

    Returns:
        List of (yomi_hiragana, surface) tuples for nouns
    """
    nouns = []

    for line in mecab_output.split('\n'):
        # Skip empty lines and EOS marker
        if not line or line == 'EOS':
            continue

        # Split by tab: surface \t features
        parts = line.split('\t')
        if len(parts) != 2:
            continue

        surface = parts[0]
        features = parts[1].split(',')

        # Check if it's a noun (1st field is 名詞)
        if len(features) < 1 or features[0] != '名詞':
            continue

        # Get yomi from 8th field (index 7)
        if len(features) < 8:
            continue

        yomi_katakana = features[7]

        # Skip if yomi is empty or contains asterisk (unknown)
        if not yomi_katakana or yomi_katakana == '*':
            continue

        # Convert katakana yomi to hiragana
        yomi_hiragana = katakana_to_hiragana(yomi_katakana)

        # Skip if yomi and surface are identical (no conversion needed)
        if yomi_hiragana == surface:
            continue

        nouns.append((yomi_hiragana, surface))

    return nouns


def apply_sentence_transformations(sentence: str) -> str:
    """Apply transformations to a processed sentence.

    This function applies regex-based transformations to simplify
    the yomi/POS1/POS2 format. Currently strips POS tags, keeping only yomi.

    This is a separate function to allow future expansion of
    post-processing logic.

    Args:
        sentence: Sentence in "yomi/POS1/POS2 yomi/POS1/POS2 ..." format

    Returns:
        Transformed sentence
    """
    # Remove POS tags, keeping only yomi
    # Pattern matches: word/POS1/POS2 followed by space or end of string
    result = re.sub(r'(\S+)/\S+/\S+(?=[ ]|$)', r'\1', sentence)
    return result


def postprocess_mecab_output(mecab_output: str, sentence: str) -> str:
    """Post-process MeCab output into yomi/POS1/POS2 format.

    Transforms MeCab output from:
        surface\tPOS1,POS2,...,yomi,...
    To:
        yomi/POS1/POS2 yomi/POS1/POS2 ...

    Then applies sentence transformations (currently strips POS tags).

    Args:
        mecab_output: Raw MeCab output
        sentence: Original input sentence (for reference)

    Returns:
        Processed output string
    """
    tokens = []

    for line in mecab_output.split('\n'):
        # Skip empty lines
        if not line:
            continue

        # EOS marks end of sentence - finalize and return
        if line == 'EOS':
            break

        # Split by tab: surface \t features
        parts = line.split('\t')
        if len(parts) != 2:
            continue

        surface = parts[0]
        features = parts[1].split(',')

        # Get POS1 (index 0) and POS2 (index 1)
        pos1 = features[0] if len(features) > 0 else '*'
        pos2 = features[1] if len(features) > 1 else '*'

        # Get yomi from 8th field (index 7)
        if len(features) >= 8 and features[7] != '*':
            yomi = katakana_to_hiragana(features[7])
        else:
            # Fallback to surface if yomi not available
            yomi = surface

        # Create token in format: yomi/POS1/POS2
        token = f"{yomi}/{pos1}/{pos2}"
        tokens.append(token)

    # Join tokens with spaces
    joined = ' '.join(tokens)

    # Apply sentence transformations
    result = apply_sentence_transformations(joined)

    return result


def format_skk_entry(yomi: str, surface: str) -> str:
    """Format a yomi-surface pair as SKK dictionary entry.

    SKK format: yomi /surface/

    Args:
        yomi: Reading in hiragana
        surface: Surface form (kanji/word)

    Returns:
        SKK-formatted dictionary line
    """
    return f"{yomi} /{surface}/"


def process_file(input_path: str) -> tuple:
    """Process an entire text file through MeCab.

    Args:
        input_path: Path to input text file

    Returns:
        Tuple of (mecab_output_path, vocab_output_path)
    """
    # Read input file
    encodings = ['utf-8', 'shift_jis', 'euc-jp']
    content = None

    for encoding in encodings:
        try:
            with open(input_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        print(f"Error: Could not read {input_path} with any supported encoding.",
              file=sys.stderr)
        sys.exit(1)

    # Split into sentences
    sentences = split_into_sentences(content)
    print(f"Found {len(sentences)} sentence(s)")

    # Process each sentence through MeCab
    results = []
    all_nouns = []  # Collect all extracted nouns

    for i, sentence in enumerate(sentences):
        print(f"  Processing sentence {i + 1}/{len(sentences)}...", end='\r')

        mecab_output = run_mecab(sentence)
        processed = postprocess_mecab_output(mecab_output, sentence)

        # Extract nouns from this sentence
        nouns = extract_nouns_from_mecab(mecab_output)
        all_nouns.extend(nouns)

        # Format: original sentence, then MeCab output
        results.append(f"# {sentence}\n{processed}")

    print()  # Clear the progress line

    # Generate output paths (same directory as input)
    input_dir = os.path.dirname(os.path.abspath(input_path))
    input_basename = os.path.basename(input_path)

    # Remove extension
    if '.' in input_basename:
        name_without_ext = input_basename.rsplit('.', 1)[0]
    else:
        name_without_ext = input_basename

    # MeCab processed output
    mecab_output_filename = f"{name_without_ext}_mecab_processed.txt"
    mecab_output_path = os.path.join(input_dir, mecab_output_filename)

    with open(mecab_output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))

    # Extracted vocabulary in SKK format
    vocab_output_filename = f"{name_without_ext}_extracted_vocab.txt"
    vocab_output_path = os.path.join(input_dir, vocab_output_filename)

    # Format nouns as SKK entries (keep duplicates as requested)
    skk_entries = [format_skk_entry(yomi, surface) for yomi, surface in all_nouns]

    with open(vocab_output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(skk_entries))

    print(f"Extracted {len(all_nouns)} noun(s)")

    return mecab_output_path, vocab_output_path


def main():
    parser = argparse.ArgumentParser(
        description='Process a text file through MeCab sentence by sentence.'
    )
    parser.add_argument(
        'input_file',
        help='Path to input text file'
    )
    args = parser.parse_args()

    # Validate input file exists
    if not os.path.isfile(args.input_file):
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing: {args.input_file}")

    mecab_path, vocab_path = process_file(args.input_file)

    print(f"MeCab output: {mecab_path}")
    print(f"Vocabulary:   {vocab_path}")


if __name__ == '__main__':
    main()
