#!/usr/bin/env python3
"""
MeCab Sentence Processor for CRF Training Data

This script processes text files (e.g., from aozora_bunko_retrieval.py) and:
1. Splits text into sentences (on Japanese punctuation + newlines)
2. Runs MeCab morphological analysis on each sentence
3. Outputs one line per sentence with morphemes as "surface/POS"

Usage:
    python mecab_sentence_processor.py input.txt
    python mecab_sentence_processor.py input.txt -o output.txt

Output format:
    今日/名詞 は/助詞 天気/名詞 が/助詞 良い/形容詞 。/記号

Note: POS values may require post-processing in a subsequent step.
"""

import argparse
import os
import re
import sys

try:
    import MeCab
    HAS_MECAB = True
except ImportError:
    HAS_MECAB = False


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
    """Process a single sentence with MeCab.

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


def process_file(input_path: str, output_path: str) -> None:
    """Process a text file with MeCab.

    Args:
        input_path: Path to input text file
        output_path: Path to output file
    """
    if not HAS_MECAB:
        print("Error: 'mecab-python3' library is required.")
        print("Install with: pip install mecab-python3")
        print("Also ensure MeCab is installed on your system.")
        sys.exit(1)

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

    # Process each sentence
    print("Processing with MeCab...")
    output_lines = []
    total_morphemes = 0

    for sentence in sentences:
        line, morpheme_count = process_sentence_with_mecab(tagger, sentence)
        if line:  # Only add non-empty lines
            output_lines.append(line)
            total_morphemes += morpheme_count

    # Write output
    print(f"Writing: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
        f.write('\n')  # Trailing newline

    print(f"\nProcessing complete:")
    print(f"  Sentences:  {len(output_lines):,}")
    print(f"  Morphemes:  {total_morphemes:,}")
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
        help='Path to input text file (UTF-8)'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Path to output file (default: <input>_mecab.txt in same directory as script)'
    )
    args = parser.parse_args()

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_basename = os.path.basename(args.input)
        base, ext = os.path.splitext(input_basename)
        output_filename = f"{base}_mecab{ext}"
        output_path = os.path.join(script_dir, output_filename)

    process_file(args.input, output_path)


if __name__ == '__main__':
    main()
