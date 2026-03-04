#!/usr/bin/env python3
"""
https://github.com/ku-nlp/WikipediaAnnotatedCorpus/tree/main

Example KNP format:
# S-ID:SOME_INFORMATION
* 1D
+ 1D
今日 きょう キョウ 名詞 6 普通名詞 1 * 0 * 0 NIL
は は は 助詞 9 副助詞 2 * 0 * 0 NIL
、 、 、 特殊 1 読点 2 * 0 * 0 NIL
"""

import argparse
import glob
import os
import re
import sys


def process_sentence(sentence:list) -> str:
    """
    This function takes a list of sentence annotation and returns
    a string, which is to be used for CRF model training.

    Example input:
        今日 きょう キョウ 名詞 6 普通名詞 1 * 0 * 0 NIL
        は は は 助詞 9 副助詞 2 * 0 * 0 NIL

    Output:
        きょう _は_
    """
    return_list = []
    previous_pos = ""
    for token in sentence:
        parts = token.split(' ')
        yomi = parts[1]
        pos = parts[3]
        if re.search('/', yomi):
            yomi = re.sub('^.*/', '', yomi)
        if pos in ('名詞', '動詞', '形容詞', '副詞'):
            return_list.append(yomi)
            previous_pos = pos
        elif pos == "接尾辞" and previous_pos in ('名詞', '動詞'):
            return_list[-1] = return_list[-1] + yomi
            previous_pos = pos
        else:
            return_list.append(f'_{yomi}_')
            previous_pos = pos
    return " ".join(return_list)


def process_knp_file(filepath):
    """Process a single .knp file and output morpheme data."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            sentence = []
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    if len(sentence) > 0:
                        process_sentence(sentence)
                        sentence = []
                    continue
                if not line or line == "EOS":
                    continue
                # Skip metadata, bunsetsu boundaries (*), and tag boundaries (+)
                if line.startswith(("*", "+")):
                    continue
                # Print the morpheme line (Surface Reading Base POS ...)
                sentence.append(line)
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Process Wikipedia Annotated Corpus KNP files."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Path(s) or wildcard(s) to .knp files (e.g., corpus/*.knp)",
    )

    args = parser.parse_args()

    # Collect all files matching the paths/wildcards
    source_files = []
    for p in args.paths:
        matches = glob.glob(p)
        if not matches:
            # If it's not a wildcard and doesn't exist, we'll catch it in the loop
            source_files.append(p)
        else:
            source_files.extend(matches)

    # Sort and remove duplicates
    unique_files = sorted(set(source_files))

    processed_any = False
    for filepath in unique_files:
        if not filepath.endswith(".knp"):
            continue

        if not os.path.isfile(filepath):
            print(f"Warning: File not found or not a file: {filepath}", file=sys.stderr)
            continue

        print(f'Processing {filepath} ...')
        process_knp_file(filepath)
        processed_any = True

    if not processed_any:
        print("No .knp files were found to process.", file=sys.stderr)


if __name__ == "__main__":
    main()
