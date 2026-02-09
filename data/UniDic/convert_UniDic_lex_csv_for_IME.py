#!/opt/ibus-pskk/venv/bin/python
"""
This script converts the lex.csv file provided as part of the UniDic project.
The script will only take the following columns from the CSV file, and store it as UniDic.csv

Columns (First column index is 1, instead of 0):
    11 --   読み	カタカナでの発音
    10 --   原型	見出し語（辞書形）
    5  --   品詞	主分類
    9  --   活用型  活用形生成 / 辞書補助
    4  --   コスト	生起コスト（低いほど優先）

How to run:
1. Download the latest UniDic src ZIP file.
2. Unzip the file.
3. Run `python convert_UniDic_lex_csv_for_IME.py /path/to/lex.csv`

The output file (UniDic.csv) will be created in the same directory as this script.
"""

import csv
import argparse
import os


# Column indices (0-based) for the fields we need
COL_COST = 3        # Column 4: コスト (generation cost)
COL_POS = 4         # Column 5: 品詞 (part of speech)
COL_CONJ_TYPE = 8   # Column 9: 活用型 (conjugation type)
COL_LEMMA = 11      # Column 11: 原型 (lemma/dictionary form)
COL_READING = 10    # Column 12: 読み (reading in katakana)


def convert_unidic_lex(input_path: str, output_path: str) -> None:
    """Convert UniDic lex.csv to a simplified format for IME use.

    Args:
        input_path: Path to the original lex.csv file
        output_path: Path to write the converted UniDic.csv file
    """
    rows_read = 0
    rows_skipped = 0

    # Dictionary to store best (lowest cost) entry for each key
    # Key: (reading, lemma, pos, conj_type)
    # Value: (cost_int, [reading, lemma, pos, conj_type, cost_str])
    best_entries = {}

    print("Reading input file...")

    with open(input_path, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)

        for row in reader:
            rows_read += 1

            # Skip rows that don't have enough columns
            if len(row) < COL_READING + 1:
                rows_skipped += 1
                continue

            # Extract the columns we need
            reading = row[COL_READING]      # 読み (katakana)
            lemma = row[COL_LEMMA]          # 原型 (dictionary form)
            pos = row[COL_POS]              # 品詞 (part of speech)
            conj_type = row[COL_CONJ_TYPE]  # 活用型 (conjugation type)
            cost_str = row[COL_COST]        # コスト (cost)

            # Parse cost as integer for comparison
            try:
                cost_int = int(cost_str)
            except ValueError:
                rows_skipped += 1
                continue

            # Deduplication key (without cost)
            key = (reading, lemma, pos, conj_type)

            # Keep entry with lowest cost
            if key not in best_entries or cost_int < best_entries[key][0]:
                best_entries[key] = (cost_int, [reading, lemma, pos, conj_type, cost_str])

    print(f"Writing output file...")

    with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)

        # Write header row
        writer.writerow(['読み', '原型', '品詞', '活用型', 'コスト'])

        # Write all unique entries
        for cost_int, row_data in best_entries.values():
            writer.writerow(row_data)

    rows_merged = rows_read - rows_skipped - len(best_entries)

    print(f"Conversion complete:")
    print(f"  Rows read:       {rows_read:,}")
    print(f"  Rows skipped:    {rows_skipped:,}")
    print(f"  Rows merged:     {rows_merged:,}")
    print(f"  Rows written:    {len(best_entries):,}")
    print(f"  Output file:     {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert UniDic lex.csv to a simplified format for IME use.'
    )
    parser.add_argument(
        'input',
        help='Path to the input lex.csv file'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Path to the output file (default: UniDic.csv in the same directory as this script)'
    )
    args = parser.parse_args()

    # Default output path: UniDic.csv in the same directory as this script
    if args.output is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, 'UniDic.csv')
    else:
        output_path = args.output

    convert_unidic_lex(args.input, output_path)


if __name__ == '__main__':
    main()
