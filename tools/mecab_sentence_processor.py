#!/usr/bin/env python3
"""
mecab_sentence_processor.py - Process Japanese text through MeCab analyzer
MeCab形態素解析器を使用して日本語テキストを処理

================================================================================
IMPORTANT: MECAB INSTALLATION REQUIRED / 重要: MECABのインストールが必要
================================================================================

This script requires MeCab to be installed on your system!
このスクリプトはシステムにMeCabがインストールされている必要があります！

INSTALLATION / インストール:
─────────────────────────────

Linux (Debian/Ubuntu):
    sudo apt-get install mecab mecab-ipadic-utf8 libmecab-dev

Linux (Arch):
    sudo pacman -S mecab mecab-ipadic

macOS (Homebrew):
    brew install mecab mecab-ipadic

Windows:
    Download from: https://taku910.github.io/mecab/
    Or use: pip install mecab-python3  (includes bundled MeCab)

VERIFY INSTALLATION / インストール確認:
────────────────────────────────────────
    $ echo "今日は天気がいい" | mecab
    今日    名詞,副詞可能,*,*,*,*,今日,キョウ,キョー
    は      助詞,係助詞,*,*,*,*,は,ハ,ワ
    天気    名詞,一般,*,*,*,*,天気,テンキ,テンキ
    ...

================================================================================
WHAT IS MECAB? / MeCabとは？
================================================================================

MeCab is the de facto standard MORPHOLOGICAL ANALYZER for Japanese.
MeCabは日本語の事実上の標準的な形態素解析器。

WHAT IS MORPHOLOGICAL ANALYSIS? / 形態素解析とは？
──────────────────────────────────────────────────

In English, words are separated by spaces:
英語では、単語はスペースで区切られている:

    "I love sushi" → ["I", "love", "sushi"]  (trivial to split)

In Japanese, there are NO SPACES between words:
日本語では、単語間にスペースがない:

    "私は寿司が好きです" → ???

Morphological analysis FINDS THE WORD BOUNDARIES:
形態素解析が単語境界を見つける:

    "私は寿司が好きです"
        ↓ MeCab
    ["私", "は", "寿司", "が", "好き", "です"]
      │     │     │      │     │      │
      └─────┴─────┴──────┴─────┴──────┘
      Each word identified with:
      各単語に以下が識別される:
        • Part of Speech (品詞)
        • Reading (読み)
        • Base form (原形)

================================================================================
WHY THIS SCRIPT? / このスクリプトの目的
================================================================================

This script processes Japanese text and extracts:
このスクリプトは日本語テキストを処理し、以下を抽出:

1. TOKENIZED SENTENCES with readings / 読み付きのトークン化された文
   ─────────────────────────────────────────────────────────────────
   Input:  今日は天気がいい
   Output: きょう _は/助詞/係助詞 てんき _が/助詞/格助詞 いい

   This format is useful for:
   この形式は以下に有用:
   • CRF training data (bunsetsu boundary prediction)
     CRF訓練データ（文節境界予測）
   • Analyzing word frequency patterns
     単語頻度パターンの分析

2. EXTRACTED VOCABULARY in SKK format / SKK形式で抽出された語彙
   ─────────────────────────────────────────────────────────────────
   Nouns are extracted with their readings:
   名詞が読みとともに抽出される:

       てんき /天気/
       きょう /今日/

   These can be added to IME dictionaries.
   これらはIME辞書に追加できる。

================================================================================
MECAB OUTPUT FORMAT / MeCab出力形式
================================================================================

MeCab outputs one token per line in this format:
MeCabは1行に1トークンをこの形式で出力:

    表層形\t品詞,品詞細分類1,品詞細分類2,品詞細分類3,活用型,活用形,原形,読み,発音

Example / 例:
    天気\t名詞,一般,*,*,*,*,天気,テンキ,テンキ
    │     │     │                    │
    │     │     │                    └── Reading in katakana (カタカナの読み)
    │     │     └── Subcategories (* = none)
    │     └── Part of Speech (品詞)
    └── Surface form (表層形)

This script converts the reading from KATAKANA to HIRAGANA because:
このスクリプトは読みをカタカナからひらがなに変換する理由:
• IME input is typically in hiragana / IME入力は通常ひらがな
• Dictionary lookups use hiragana / 辞書検索はひらがなを使用

================================================================================
STANDALONE SCRIPT / スタンドアロンスクリプト
================================================================================

This is a STANDALONE UTILITY for preparing training/testing data.
It is NOT required for the IME to function.

これは訓練/テストデータを準備するためのスタンドアロンユーティリティ。
IMEの動作には不要。

================================================================================
USAGE / 使用方法
================================================================================

FILE PROCESSING MODE / ファイル処理モード:
───────────────────────────────────────────
    python mecab_sentence_processor.py input.txt

    Creates:
    作成されるファイル:
    • input_mecab_processed.txt  - Tokenized sentences with readings
                                   読み付きトークン化された文
    • input_extracted_vocab.txt  - Nouns in SKK dictionary format
                                   SKK辞書形式の名詞

TEST MODE / テストモード:
─────────────────────────
    # Quick test / クイックテスト
    python mecab_sentence_processor.py -t "今日は天気がいい"

    # Verbose (show all processing steps) / 詳細表示
    python mecab_sentence_processor.py -t "今日は天気がいい" -v

================================================================================
TYPICAL WORKFLOW / 典型的なワークフロー
================================================================================

1. Get Japanese text (e.g., from Aozora Bunko)
   日本語テキストを取得（例：青空文庫から）

2. Run this script to tokenize and extract vocabulary
   このスクリプトを実行してトークン化と語彙抽出

3. Use output for CRF training or dictionary building
   出力をCRF訓練または辞書構築に使用

================================================================================
"""

import argparse
import os
import re
import subprocess
import sys


def katakana_to_hiragana(text: str) -> str:
    """
    Convert katakana characters to hiragana.
    カタカナ文字をひらがなに変換

    ─────────────────────────────────────────────────────────────────────────
    WHY THIS CONVERSION? / なぜこの変換？
    ─────────────────────────────────────────────────────────────────────────

    MeCab outputs readings in KATAKANA (e.g., テンキ for 天気).
    But IME dictionaries and user input use HIRAGANA (てんき).

    MeCabは読みをカタカナで出力（例：天気→テンキ）。
    しかしIME辞書とユーザー入力はひらがなを使用（てんき）。

    ─────────────────────────────────────────────────────────────────────────
    UNICODE TRICK / Unicodeのトリック
    ─────────────────────────────────────────────────────────────────────────

    In Unicode, hiragana and katakana are laid out in parallel:
    Unicodeでは、ひらがなとカタカナは並行して配置されている:

        Katakana: ァアィイ... (U+30A1 to U+30F6)
        Hiragana: ぁあぃい... (U+3041 to U+3096)

    The offset is exactly 0x60 (96), so conversion is simple subtraction!
    オフセットはちょうど0x60（96）なので、変換は単純な減算！

        カ (U+30AB) - 0x60 = か (U+304B)

    Args:
        text: Input string (katakana, hiragana, or mixed)
              入力文字列（カタカナ、ひらがな、または混在）

    Returns:
        String with katakana → hiragana (other characters unchanged)
        カタカナ→ひらがな変換済み文字列（他の文字は変更なし）
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
    """
    Split text into sentences using Japanese punctuation.
    日本語の句読点を使用してテキストを文に分割

    ─────────────────────────────────────────────────────────────────────────
    JAPANESE SENTENCE BOUNDARIES / 日本語の文境界
    ─────────────────────────────────────────────────────────────────────────

    Unlike English (which uses . ? !), Japanese uses different punctuation:
    英語（. ? ! を使用）と異なり、日本語は異なる句読点を使用:

    • 。(maru) - Period / 句点
    • ！(full-width !) - Exclamation / 感嘆符
    • ？(full-width ?) - Question / 疑問符

    This function splits on these AND newlines (paragraph breaks).
    この関数はこれらと改行（段落区切り）で分割する。

    ─────────────────────────────────────────────────────────────────────────
    WHY SENTENCE-BY-SENTENCE? / なぜ文ごとに？
    ─────────────────────────────────────────────────────────────────────────

    Processing sentence-by-sentence is important because:
    文ごとの処理が重要な理由:

    1. MeCab performs better on shorter, coherent units
       MeCabは短く一貫した単位でより良く機能する

    2. Easier to debug and inspect output
       デバッグと出力の検査が容易

    3. Memory-efficient for large texts
       大きなテキストでメモリ効率が良い

    Args:
        text: Input text (may be multiple paragraphs)
              入力テキスト（複数の段落の可能性あり）

    Returns:
        List of sentences (empty strings filtered out)
        文のリスト（空文字列は除外）
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
    """
    Run MeCab on a single sentence via subprocess.
    サブプロセス経由でMeCabを単一の文に対して実行

    ─────────────────────────────────────────────────────────────────────────
    HOW IT WORKS / 動作の仕組み
    ─────────────────────────────────────────────────────────────────────────

    This function:
    この関数は:

    1. Pipes the sentence to MeCab's stdin
       文をMeCabのstdinにパイプ

    2. Captures MeCab's stdout (the analysis)
       MeCabのstdout（解析結果）をキャプチャ

    3. Returns the raw output for further processing
       さらなる処理のために生の出力を返す

    Equivalent to shell command:
    シェルコマンドと等価:

        echo "今日は天気がいい" | mecab

    ─────────────────────────────────────────────────────────────────────────
    ERROR HANDLING / エラー処理
    ─────────────────────────────────────────────────────────────────────────

    If MeCab is not installed, this function prints helpful error
    messages and exits. This is better than cryptic Python exceptions.

    MeCabがインストールされていない場合、この関数は有用なエラー
    メッセージを出力して終了する。これは不可解なPython例外より良い。

    Args:
        sentence: 入力文字列

    Returns:
        MeCab output (one token per line, ending with "EOS")
        MeCab出力（1行に1トークン、"EOS"で終了）

    Raises:
        RuntimeError: If MeCab returns non-zero exit code
                      MeCabが非ゼロの終了コードを返した場合
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
    """
    Extract nouns with their readings from MeCab output.
    MeCab出力から名詞とその読みを抽出

    ─────────────────────────────────────────────────────────────────────────
    WHY EXTRACT NOUNS? / なぜ名詞を抽出？
    ─────────────────────────────────────────────────────────────────────────

    Nouns are the most valuable for IME dictionaries because:
    名詞がIME辞書に最も価値がある理由:

    • They carry the most semantic meaning / 最も意味的な意味を持つ
    • They're the most likely to need kanji conversion / 漢字変換が最も必要
    • Verbs/adjectives are better handled by conjugation rules
      動詞/形容詞は活用ルールで処理する方が良い

    ─────────────────────────────────────────────────────────────────────────
    MECAB OUTPUT FORMAT / MeCab出力形式
    ─────────────────────────────────────────────────────────────────────────

    MeCab (with IPA dictionary) outputs:
    MeCab（IPA辞書使用時）の出力:

        天気\t名詞,一般,*,*,*,*,天気,テンキ,テンキ
        │     │    │          │    │
        │     │    │          │    └── Reading (index 7) 読み
        │     │    │          └── Base form (index 6) 原形
        │     │    └── Subcategory 品詞細分類
        │     └── POS = "名詞" (noun) 品詞
        └── Surface form 表層形

    We extract entries where:
    以下の条件を満たすエントリを抽出:
    • POS (index 0) = "名詞" / 品詞が「名詞」
    • Reading (index 7) exists and ≠ "*" / 読み（index 7）が存在し"*"でない
    • Reading ≠ surface (to avoid useless "それ /それ/")
      読み≠表層形（無用な「それ /それ/」を避けるため）

    Args:
        mecab_output: Raw MeCab output (multi-line string)
                      MeCab生出力（複数行文字列）

    Returns:
        List of (hiragana_reading, surface) tuples
        (ひらがな読み, 表層形) タプルのリスト
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
    """
    Apply transformations to a processed sentence.
    処理された文に変換を適用

    ─────────────────────────────────────────────────────────────────────────
    PURPOSE / 目的
    ─────────────────────────────────────────────────────────────────────────

    This function post-processes the yomi/POS1/POS2 format to create
    output suitable for CRF training or other analysis.

    この関数は yomi/POS1/POS2 形式を後処理し、CRF訓練やその他の分析に
    適した出力を作成する。

    ─────────────────────────────────────────────────────────────────────────
    TRANSFORMATIONS / 変換
    ─────────────────────────────────────────────────────────────────────────

    1. MARK PARTICLES (助詞) with underscore prefix:
       助詞をアンダースコア接頭辞でマーク:

       は/助詞/係助詞 → _は/助詞/係助詞

       Why? Particles often mark bunsetsu (phrase) boundaries.
       なぜ？助詞はしばしば文節境界をマークする。

    2. STRIP POS TAGS, keeping only readings:
       品詞タグを除去し、読みのみを保持:

       きょう/名詞/副詞可能 → きょう

       This creates a simpler format for some training scenarios.
       これにより一部の訓練シナリオ向けのよりシンプルな形式になる。

    Args:
        sentence: "yomi/POS1/POS2 yomi/POS1/POS2 ..." format
                  「yomi/POS1/POS2 yomi/POS1/POS2 ...」形式

    Returns:
        Transformed sentence (readings with particle markers)
        変換された文（助詞マーカー付きの読み）
    """
    # Consider joshi 助詞 as a special-case => marker
    sentence = re.sub(r'(\S+/助詞/\S+(?=[ ]|$))', r'_\1', sentence)
    # Remove POS tags, keeping only yomi
    # Pattern matches: word/POS1/POS2 followed by space or end of string
    result = re.sub(r'(\S+)/\S+/\S+(?=[ ]|$)', r'\1', sentence)
    return result


def postprocess_mecab_output(mecab_output: str, sentence: str) -> str:
    """
    Post-process MeCab output into yomi/POS1/POS2 format.
    MeCab出力を yomi/POS1/POS2 形式に後処理

    ─────────────────────────────────────────────────────────────────────────
    TRANSFORMATION PIPELINE / 変換パイプライン
    ─────────────────────────────────────────────────────────────────────────

    Step 1: Parse MeCab output / MeCab出力を解析
    ─────────────────────────────────────────────
        Input:  天気\t名詞,一般,*,*,*,*,天気,テンキ,テンキ
        Output: てんき/名詞/一般

    Step 2: Join tokens with spaces / トークンをスペースで結合
    ─────────────────────────────────────────────────────────────
        きょう/名詞/副詞可能 は/助詞/係助詞 てんき/名詞/一般 ...

    Step 3: Apply transformations / 変換を適用
    ──────────────────────────────────────────
        きょう _は てんき ...

    ─────────────────────────────────────────────────────────────────────────
    OUTPUT USE CASES / 出力の用途
    ─────────────────────────────────────────────────────────────────────────

    The output format is designed for:
    出力形式は以下の用途に設計:

    • CRF training data for bunsetsu segmentation
      文節分割のためのCRF訓練データ
    • Analyzing sentence structure patterns
      文構造パターンの分析
    • Building N-gram models
      N-gramモデルの構築

    Args:
        mecab_output: MeCab生出力
        sentence: 元の入力文（参照用）

    Returns:
        Processed output (space-separated readings with markers)
        処理済み出力（スペース区切りの読みとマーカー）
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
    """
    Format a yomi-surface pair as SKK dictionary entry.
    読み-表層形ペアをSKK辞書エントリにフォーマット

    ─────────────────────────────────────────────────────────────────────────
    SKK DICTIONARY FORMAT / SKK辞書形式
    ─────────────────────────────────────────────────────────────────────────

    SKK dictionaries use a simple, human-readable format:
    SKK辞書はシンプルで人間が読める形式を使用:

        yomi /candidate1/candidate2/.../

    Example / 例:
        てんき /天気/
        きょう /今日/京/教/

    This format is:
    この形式は:
    • Easy to grep/edit / grep/編集が容易
    • Widely used in Japanese IME ecosystems
      日本語IMEエコシステムで広く使用
    • Compatible with SKK, PSKK, and other tools
      SKK、PSKK、その他のツールと互換性あり

    Args:
        yomi: ひらがなの読み
        surface: 表層形（漢字/単語）

    Returns:
        SKK-formatted line: "yomi /surface/"
        SKK形式の行: "yomi /surface/"
    """
    return f"{yomi} /{surface}/"


def process_file(input_path: str) -> tuple:
    """
    Process an entire text file through MeCab.
    テキストファイル全体をMeCabで処理

    ─────────────────────────────────────────────────────────────────────────
    PROCESSING STEPS / 処理ステップ
    ─────────────────────────────────────────────────────────────────────────

    1. READ input file (tries multiple encodings)
       入力ファイルを読み込み（複数のエンコーディングを試行）

    2. SPLIT into sentences
       文に分割

    3. For each sentence / 各文に対して:
       a. Run MeCab / MeCabを実行
       b. Extract nouns / 名詞を抽出
       c. Post-process output / 出力を後処理

    4. WRITE two output files:
       2つの出力ファイルを書き込み:

       • FILENAME_mecab_processed.txt
         Full processed output with original sentences
         元の文を含む完全な処理済み出力

       • FILENAME_extracted_vocab.txt
         Extracted nouns in SKK format
         SKK形式で抽出された名詞

    ─────────────────────────────────────────────────────────────────────────
    OUTPUT FILE LOCATION / 出力ファイルの場所
    ─────────────────────────────────────────────────────────────────────────

    Output files are created in the SAME DIRECTORY as the input file.
    出力ファイルは入力ファイルと同じディレクトリに作成される。

        /path/to/novel.txt
            ↓
        /path/to/novel_mecab_processed.txt
        /path/to/novel_extracted_vocab.txt

    Args:
        input_path: 入力テキストファイルのパス

    Returns:
        Tuple of (mecab_output_path, vocab_output_path)
        (mecab出力パス, 語彙出力パス) のタプル
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


def test_sentence(sentence: str, verbose: bool = False):
    """
    Test processing on a single sentence (interactive debugging).
    単一の文で処理をテスト（対話的デバッグ用）

    ─────────────────────────────────────────────────────────────────────────
    PURPOSE / 目的
    ─────────────────────────────────────────────────────────────────────────

    This function is for TESTING and DEBUGGING the processing pipeline.
    Use it to understand how MeCab analyzes specific sentences.

    この関数は処理パイプラインのテストとデバッグ用。
    MeCabが特定の文をどのように解析するか理解するために使用。

    ─────────────────────────────────────────────────────────────────────────
    EXAMPLE OUTPUT / 出力例
    ─────────────────────────────────────────────────────────────────────────

    Normal mode / 通常モード:
    ─────────────────────────
        $ python mecab_sentence_processor.py -t "今日は天気がいい"

        Input: 今日は天気がいい

        === Processed output ===
        きょう _は てんき _が いい

    Verbose mode / 詳細モード:
    ───────────────────────────
        $ python mecab_sentence_processor.py -t "今日は天気がいい" -v

        Input: 今日は天気がいい

        === Raw MeCab output ===
        今日    名詞,副詞可能,*,*,*,*,今日,キョウ,キョー
        は      助詞,係助詞,*,*,*,*,は,ハ,ワ
        ...

        === Intermediate (yomi/POS1/POS2) ===
        きょう/名詞/副詞可能 は/助詞/係助詞 ...

        === Processed output ===
        きょう _は てんき _が いい

    Args:
        sentence: 入力文
        verbose: Trueなら中間ステップを表示
    """
    print(f"Input: {sentence}")
    print()

    # Run MeCab
    mecab_output = run_mecab(sentence)

    if verbose:
        print("=== Raw MeCab output ===")
        print(mecab_output)

    # Build intermediate yomi/POS1/POS2 format (before transformation)
    tokens = []
    for line in mecab_output.split('\n'):
        if not line or line == 'EOS':
            continue
        parts = line.split('\t')
        if len(parts) != 2:
            continue
        surface = parts[0]
        features = parts[1].split(',')
        pos1 = features[0] if len(features) > 0 else '*'
        pos2 = features[1] if len(features) > 1 else '*'
        if len(features) >= 8 and features[7] != '*':
            yomi = katakana_to_hiragana(features[7])
        else:
            yomi = surface
        tokens.append(f"{yomi}/{pos1}/{pos2}")

    intermediate = ' '.join(tokens)

    if verbose:
        print("=== Intermediate (yomi/POS1/POS2) ===")
        print(intermediate)
        print()

    # Apply transformations
    processed = postprocess_mecab_output(mecab_output, sentence)

    print("=== Processed output ===")
    print(processed)


def main():
    parser = argparse.ArgumentParser(
        description='Process a text file through MeCab sentence by sentence.'
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default=None,
        help='Path to input text file'
    )
    parser.add_argument(
        '-t', '--test',
        metavar='SENTENCE',
        help='Test mode: process a single sentence and print result to stdout'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output (show intermediate processing steps in test mode)'
    )
    args = parser.parse_args()

    # Test mode
    if args.test:
        test_sentence(args.test, verbose=args.verbose)
        return

    # File processing mode
    if not args.input_file:
        parser.print_help()
        print("\nError: Either input_file or --test is required.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.input_file):
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing: {args.input_file}")

    mecab_path, vocab_path = process_file(args.input_file)

    print(f"MeCab output: {mecab_path}")
    print(f"Vocabulary:   {vocab_path}")


if __name__ == '__main__':
    main()
