#!/usr/bin/env python3
"""
wikipedia_annotated_corpus_processor.py - Process Wikipedia Annotated Corpus KNP files

This script processes .knp files from the Wikipedia Annotated Corpus and
outputs tokenized sentences with readings, suitable for CRF training.

Source: https://github.com/ku-nlp/WikipediaAnnotatedCorpus/tree/main

USAGE:
    python wikipedia_annotated_corpus_processor.py input.knp
    python wikipedia_annotated_corpus_processor.py corpus/*.knp -o output.txt

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


def create_skk_dict_entries(sentence: list) -> list:
    """
    This function takes a list of sentence annotation and returns
    a list containing line from yomi-to-kanji in SKK format

    In terms of the retrieval of yomi-to-kanji is done in greedy manner. 
    That is, for example, if we have:
        第 だい 第 接頭辞
        2 に 2 名詞
        位 い 位 接尾辞
        の の の 助詞
    ... the following would be retrieved (without the comment at the tail):
        だい /第/
        だいに /第2/
        だいにい /第2位/
        だいにいの /第2位の/ # this is for easier typing
        に /2/
        にい /2位/
        にいの /2位の/ # this is for easier typing
        # please note that we do not add 接尾辞+助詞 combinaion
    """
    return_list = []
    previous_pos = ""
    previous_parts = dict() # dict instead of set because we'd store both yomi and kanji of previous token(s)
    for token in sentence:
        parts = token.split(" ")
        sf = parts[0]
        yomi = parts[1]
        pos = parts[3]

    return return_list


def process_sentence(sentence: list) -> str:
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
    sf_str = "#"
    for token in sentence:
        parts = token.split(" ")
        sf = parts[0]
        sf_str += " " + sf
        yomi = parts[1]
        pos = parts[3]
        if re.search("/", yomi):
            # this is a goofy implementation in order to address the multiple yomi in the corpus...
            yomi = re.sub("^.*/", "", yomi)
        if pos == "名詞" and previous_pos == "名詞":
            # this is for covering compound noun
            return_list[-1] = return_list[-1] + yomi
        elif pos == "名詞" and previous_pos == "接頭辞":
            # this is for covering things like 同+州
            return_list[-1] = re.sub("^_(.*)_$", r"\1", return_list[-1]) + yomi
        elif pos == "接尾辞" and previous_pos in ("名詞", "動詞"):
            return_list[-1] = return_list[-1] + yomi
        elif pos in ("名詞", "動詞", "形容詞", "副詞"):
            return_list.append(yomi)
        else:
            return_list.append(f"_{yomi}_")
        previous_pos = pos
    return sf_str + "\n" + " ".join(return_list)


def process_knp_file(filepath, out_f=sys.stdout):
    """Process a single .knp file and output morpheme data."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            sentence = []
            for line in f:
                line = line.strip()
                if line.startswith("#"):
                    if len(sentence) > 0:
                        out_f.write(process_sentence(sentence) + "\n")
                        sentence = []
                    continue
                if not line or line == "EOS":
                    if len(sentence) > 0:
                        out_f.write(process_sentence(sentence) + "\n")
                        sentence = []
                    continue
                # Skip metadata, bunsetsu boundaries (*), and tag boundaries (+)
                if line.startswith(("*", "+")):
                    continue
                # Print the morpheme line (Surface Reading Base POS ...)
                sentence.append(line)
            # Catch the last sentence if it wasn't triggered by # or EOS
            if len(sentence) > 0:
                out_f.write(process_sentence(sentence) + "\n")
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
    parser.add_argument("-o", "--output", help="Output filepath")

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

    out_f = sys.stdout
    if args.output:
        try:
            out_f = open(args.output, "w", encoding="utf-8")
        except Exception as e:
            print(f"Error opening output file {args.output}: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        processed_any = False
        for filepath in unique_files:
            if not filepath.endswith(".knp"):
                continue

            if not os.path.isfile(filepath):
                print(
                    f"Warning: File not found or not a file: {filepath}",
                    file=sys.stderr,
                )
                continue

            print(f"Processing {filepath} ...", file=sys.stderr)
            process_knp_file(filepath, out_f)
            processed_any = True

        if not processed_any:
            print("No .knp files were found to process.", file=sys.stderr)
    finally:
        if out_f is not sys.stdout:
            out_f.close()


if __name__ == "__main__":
    main()
