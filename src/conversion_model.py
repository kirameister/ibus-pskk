#!/usr/bin/env python3
"""
conversion_model.py - CRF-based bunsetsu segmentation model trainer and tester
CRFベースの文節セグメンテーションモデルのトレーナーとテスター

================================================================================
WHAT IS THIS MODULE FOR? / このモジュールの目的
================================================================================

This module provides a GUI for training and testing machine learning models
that predict WHERE to split Japanese text into bunsetsu (phrase units).

このモジュールは、日本語テキストを文節（フレーズ単位）に分割する場所を
予測する機械学習モデルの訓練とテストのためのGUIを提供する。

    User types:    きょうはてんきがよい
    ユーザー入力:   きょうはてんきがよい

    Model predicts: きょう|は|てんき|が|よい
    モデル予測:     きょう|は|てんき|が|よい

    Converted:      今日|は|天気|が|良い
    変換結果:       今日|は|天気|が|良い

================================================================================
WHAT IS CRF? / CRFとは？（FOR NEWCOMERS / 初心者向け）
================================================================================

CRF (Conditional Random Field) is a machine learning model well-suited for
SEQUENCE LABELING tasks - where you need to assign a label to each element
in a sequence while considering the context of neighboring elements.

CRF（条件付き確率場）は、シーケンスラベリングタスクに適した機械学習モデル -
隣接する要素のコンテキストを考慮しながら、シーケンス内の各要素に
ラベルを割り当てる必要がある場合に使用される。

WHY CRF FOR BUNSETSU SEGMENTATION? / なぜ文節分割にCRF？
─────────────────────────────────────────────────────────

Consider the input: きょうはてんきがよい

We need to decide for EACH character: "Does a bunsetsu boundary come
BEFORE this character?"

入力について考える: きょうはてんきがよい

各文字について決定する必要がある:「この文字の前に文節境界が来るか？」

    Character:  き  ょ  う  は  て  ん  き  が  よ  い
    Label:      B   I   I   B   B   I   I   B   B   I
                ↑           ↑   ↑       ↑   ↑
              Begin       Begin Begin Begin Begin
              (start of   (は is  (new    (が) (new
               sentence)   alone)  bunsetsu)    bunsetsu)

    B = Beginning of bunsetsu / 文節の開始
    I = Inside bunsetsu (continuation) / 文節の内部（継続）

CRF is perfect for this because:
CRFがこれに最適な理由:

    1. It looks at CONTEXT (neighboring characters)
       コンテキスト（隣接する文字）を見る
       → "は" after "う" likely starts a new bunsetsu
         「う」の後の「は」は新しい文節を開始する可能性が高い

    2. It considers the WHOLE SEQUENCE together
       シーケンス全体を一緒に考慮する
       → Avoids impossible label sequences (like B-B-B-B)
         不可能なラベルシーケンス（B-B-B-Bなど）を回避

    3. It's TRAINABLE from examples
       例から訓練可能
       → Feed it annotated sentences, it learns the patterns
         注釈付きの文を与えると、パターンを学習する

CRF vs OTHER APPROACHES / CRF vs 他のアプローチ:
────────────────────────────────────────────────

    RULE-BASED (ルールベース):
        "Split after particles は, が, を..."
        「助詞 は, が, を... の後で分割」
        ✗ Can't handle exceptions, new patterns
          例外、新しいパターンを処理できない

    SIMPLE CLASSIFIER (単純な分類器):
        Decide each position independently
        各位置を独立して決定
        ✗ Ignores that B must be followed by I or B
          BはIかBが続く必要があることを無視

    CRF (条件付き確率場):
        Consider context + enforce valid sequences
        コンテキストを考慮 + 有効なシーケンスを強制
        ✓ Best of both worlds
          両方の長所を併せ持つ

================================================================================
HOW CRF FEATURES WORK / CRF特徴量の仕組み
================================================================================

The model learns from FEATURES - properties of each character position:
モデルは特徴量から学習する - 各文字位置のプロパティ:

    Position 3 (は) has these features:
    位置3（は）にはこれらの特徴量がある:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  Feature                    │  Value      │  Why it helps              │
    │  特徴量                      │  値         │  なぜ役立つか               │
    ├─────────────────────────────┼─────────────┼────────────────────────────┤
    │  char=は                    │  current    │  "は" often starts bunsetsu │
    │  char[-1]=う                │  previous   │  what came before          │
    │  char[+1]=て                │  next       │  what comes after          │
    │  type=hiragana              │  char type  │  distinguishes あ vs A vs 漢 │
    │  joshi=は                   │  particle?  │  助詞 often start bunsetsu  │
    │  type_change=False          │  boundary?  │  type changes often = split│
    │  dict_start_len=4           │  dictionary │  word "てんき" starts here  │
    └─────────────────────────────┴─────────────┴────────────────────────────┘

The CRF learns weights for each feature:
CRFは各特徴量の重みを学習する:

    "If joshi=は is present, increase probability of B label by 2.5"
    「joshi=はが存在する場合、Bラベルの確率を2.5増加」

    "If char[-1]=っ (small tsu), decrease probability of B label by 1.8"
    「char[-1]=っ（促音）の場合、Bラベルの確率を1.8減少」

================================================================================
4-CLASS LABELING SYSTEM / 4クラスラベリングシステム
================================================================================

This module uses an EXTENDED labeling scheme with 4 classes:
このモジュールは4クラスの拡張ラベリングスキームを使用:

    B-L = Beginning of LOOKUP bunsetsu (needs dictionary conversion)
          LOOKUP文節の開始（辞書変換が必要）
          Example: きょう → 今日

    I-L = Inside of LOOKUP bunsetsu
          LOOKUP文節の内部

    B-P = Beginning of PASSTHROUGH bunsetsu (output as-is)
          PASSTHROUGH文節の開始（そのまま出力）
          Example: は → は (particle, no conversion needed)

    I-P = Inside of PASSTHROUGH bunsetsu
          PASSTHROUGH文節の内部

This distinction helps the IME know:
この区別はIMEが以下を知るのに役立つ:
    - Which segments need kanji conversion / どのセグメントが漢字変換が必要か
    - Which segments should pass through unchanged / どのセグメントがそのまま通過すべきか

================================================================================
TRAINING DATA FORMAT / 訓練データ形式
================================================================================

IMPORTANT: Training data must be in HIRAGANA (readings), NOT kanji!
重要: 訓練データはひらがな（読み）でなければならない、漢字ではない！

    ✓ CORRECT:  きょう _は_ てんき _が_ よい
    ✗ WRONG:    今日は 天気が 良い

Why? At inference time, the model sees the user's typed hiragana BEFORE
conversion. Training on kanji would create a domain mismatch.
なぜ？推論時、モデルは変換前にユーザーが入力したひらがなを見る。
漢字で訓練するとドメインミスマッチが発生する。

FORMAT 1: Simple (B/I only) / シンプル形式（B/Iのみ）:
─────────────────────────────────────────────────────

    きょうは てんきが よい

    (Space-separated bunsetsu, no L/P distinction)
    （スペースで区切られた文節、L/Pの区別なし）

FORMAT 2: Annotated (B-L/I-L/B-P/I-P) / 注釈付き形式:
──────────────────────────────────────────────────────

    きょう _は_ てんき _が_ よい

    Underscore (_) marks PASSTHROUGH segments:
    アンダースコア（_）はPASSTHROUGHセグメントをマーク:
        - _は_ → passthrough (particle, output as-is)
        - てんき → lookup (send to dictionary)

================================================================================
MODULE STRUCTURE / モジュール構造
================================================================================

    CONSTANTS / 定数:
        JOSHI       - Set of Japanese particles (助詞)
        JODOUSHI    - Set of auxiliary verbs (助動詞)

    FUNCTIONS / 関数:
        parse_annotated_line()   - Parse training data
        extract_char_features()  - Extract features for one character

    GUI CLASS / GUIクラス:
        ConversionModelPanel     - GTK window for training/testing

================================================================================
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import re
import os
import time
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
#
# WHAT ARE JOSHI AND JODOUSHI? / 助詞と助動詞とは？
# ─────────────────────────────────────────────────
#
# These are Japanese grammatical particles and auxiliary verbs - small words
# that attach to content words to show grammatical relationships.
# これらは日本語の文法的な助詞と助動詞 - 文法的な関係を示すために
# 内容語に付く小さな単語。
#
# WHY ARE THEY IMPORTANT FOR BUNSETSU SEGMENTATION?
# なぜ文節分割に重要か？
#
# Particles often mark bunsetsu boundaries:
# 助詞はしばしば文節境界をマークする:
#
#     きょう|は|てんき|が|よい
#           ↑       ↑
#         particle particle
#
# The CRF uses these as features: "If this position matches a known particle,
# it's likely the start of a new bunsetsu."
# CRFはこれらを特徴量として使用:「この位置が既知の助詞と一致する場合、
# 新しい文節の開始である可能性が高い」
#
# ─────────────────────────────────────────────────

JOSHI = {
    # 格助詞 (Case particles) - mark grammatical roles
    # 格助詞 - 文法的役割をマーク
    'が',      # subject marker / 主格
    'を',      # object marker / 目的格
    'に',      # direction, time, indirect object / 方向、時間、間接目的語
    'へ',      # direction / 方向
    'で',      # location of action, means / 動作の場所、手段
    'と',      # with, quotation / と一緒に、引用
    'から',    # from / から
    'より',    # from, than (comparison) / から、より（比較）
    'まで',    # until, up to / まで

    # 接続助詞 (Conjunctive particles) - connect clauses
    # 接続助詞 - 節を接続
    'て',      # te-form connector / て形接続
    'ば',      # conditional / 条件
    'けど', 'けれど', 'けれども',  # but / しかし
    'ながら',  # while / ながら
    'のに',    # although / にもかかわらず
    'ので',    # because / ので
    'たり',    # and (listing actions) / たり
    'し',      # and (listing reasons) / し

    # 副助詞 (Adverbial particles) - add nuance
    # 副助詞 - ニュアンスを追加
    'は',      # topic marker / 主題
    'も',      # also, too / も
    'こそ',    # emphasis / 強調
    'さえ',    # even / さえ
    'でも',    # even, or something / でも
    'しか',    # only (with negative) / だけ（否定と共に）
    'ばかり',  # only, just / ばかり
    'だけ',    # only / だけ
    'ほど',    # extent, about / ほど
    'くらい', 'ぐらい',  # about, approximately / くらい
    'など',    # etc., and so on / など
    'なり',    # as soon as / なり
    'やら',    # things like / やら

    # 終助詞 (Sentence-ending particles) - express emotion/question
    # 終助詞 - 感情・疑問を表現
    'か',      # question / 疑問
    'よ',      # assertion / 断定
    'ね',      # confirmation / 確認
    'な',      # prohibition, emotion / 禁止、感情
    'ぞ',      # emphasis (masculine) / 強調（男性的）
    'わ',      # emphasis (feminine) / 強調（女性的）
    'さ',      # casual assertion / カジュアルな断定

    # 連体助詞 / 並列助詞 (Attributive/Parallel particles)
    # 連体助詞・並列助詞
    'の',      # possessive, nominalizer / 所有、名詞化
    'や',      # and (non-exhaustive list) / と（非網羅的リスト）
}

JODOUSHI = {
    # 助動詞 (Auxiliary verbs) - attach to verb stems to modify meaning
    # 助動詞 - 動詞の語幹に付いて意味を修正

    # 受身・使役 (Passive/Causative)
    'れる',    # passive (ichidan) / 受身（一段）
    'られる',  # passive (godan), potential / 受身（五段）、可能
    'せる',    # causative (ichidan) / 使役（一段）
    'させる',  # causative (godan) / 使役（五段）

    # 否定・願望 (Negation/Desire)
    'ない',    # negation / 否定
    'たい',    # want to / したい

    # 過去・断定 (Past/Assertion)
    'た',      # past tense / 過去形
    'だ',      # copula (plain) / だ

    # 丁寧 (Politeness)
    'ます',    # polite verb ending / 丁寧語動詞語尾
    'です',    # polite copula / 丁寧語だ

    # 推量・意志 (Conjecture/Volition)
    'う',      # volition, conjecture (godan) / 意志、推量（五段）
    'よう',    # volition, conjecture (ichidan) / 意志、推量（一段）
    'まい',    # negative volition / 否定意志

    # その他 (Other)
    'らしい',  # seems like / らしい
}

# Maximum length of particles/auxiliaries (for efficient substring matching)
# 助詞・助動詞の最大長（効率的な部分文字列マッチングのため）
JOSHI_MAX_LEN = max(len(w) for w in JOSHI)
JODOUSHI_MAX_LEN = max(len(w) for w in JODOUSHI)


# ─── Feature extraction ──────────────────────────────────────────────
# Note: char_type, tokenize_line, add_features_per_line are imported from util
# 注: char_type, tokenize_line, add_features_per_line は util からインポート


def parse_annotated_line(line):
    """
    Parse an annotated training line into tokens and 4-class labels.
    注釈付き訓練行をトークンと4クラスラベルに解析。

    ============================================================================
    PURPOSE / 目的
    ============================================================================

    Converts human-annotated training data into the format needed by CRF:
    人間が注釈付けした訓練データをCRFが必要とする形式に変換:

        Input:  "きょう _は_ てんき _が_ よい"
        入力:   "きょう _は_ てんき _が_ よい"
                    ↓
        Output: tokens = ['き', 'ょ', 'う', 'は', 'て', 'ん', 'き', 'が', 'よ', 'い']
                tags   = ['B-L', 'I-L', 'I-L', 'B-P', 'B-L', 'I-L', 'I-L', 'B-P', 'B-L', 'I-L']

    ============================================================================
    ANNOTATION FORMAT / 注釈形式
    ============================================================================

    - Space separates bunsetsu
      スペースで文節を区切る
    - Underscore (_) marks PASSTHROUGH segments (no kanji conversion)
      アンダースコア（_）はPASSTHROUGHセグメントをマーク（漢字変換なし）

        きょう     → Lookup (L) - send to dictionary → 今日
        _は_       → Passthrough (P) - output as-is → は

    ============================================================================
    LABELS / ラベル
    ============================================================================

        B-L = Beginning of Lookup bunsetsu
              LOOKUP文節の開始
        I-L = Inside of Lookup bunsetsu
              LOOKUP文節の内部
        B-P = Beginning of Passthrough bunsetsu
              PASSTHROUGH文節の開始
        I-P = Inside of Passthrough bunsetsu
              PASSTHROUGH文節の内部

    ============================================================================
    TOKENIZATION / トークン化
    ============================================================================

    Uses util.tokenize_line() for consistency with feature extraction:
    特徴量抽出との一貫性のためutil.tokenize_line()を使用:

        - Non-ASCII: each character = one token
          非ASCII: 各文字 = 1トークン
        - ASCII: consecutive letters/digits = one token
          ASCII: 連続する文字/数字 = 1トークン

    Example / 例: "hello _は_ world"
        → tokens: ['hello', 'は', 'world']
        → tags:   ['B-L', 'B-P', 'B-L']

    ============================================================================

    Args:
        line: Annotated line with space-delimited bunsetsu.
              スペース区切りの文節を持つ注釈付き行。

    Returns:
        Tuple of (tokens, tags) where tokens is list of tokens
        and tags is list of labels (B-L, I-L, B-P, I-P).
        (tokens, tags)のタプル。tokensはトークンのリスト、
        tagsはラベル（B-L, I-L, B-P, I-P）のリスト。
    """
    line = line.strip()
    if not line:
        return [], []

    bunsetsu_list = line.split()
    tokens = []
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

        # Use tokenize_line for consistent tokenization with feature extraction
        bunsetsu_tokens = util.tokenize_line(text)

        for i, token in enumerate(bunsetsu_tokens):
            tokens.append(token)
            tags.append(f'B-{suffix}' if i == 0 else f'I-{suffix}')

    return tokens, tags


def extract_char_features(chars, i, dictionary_readings=None):
    """
    Extract CRF features for a single character at position i.
    位置iの単一文字に対するCRF特徴量を抽出。

    ============================================================================
    WHAT THIS FUNCTION DOES / この関数の役割
    ============================================================================

    For each character position, we need to extract FEATURES - properties that
    help the CRF decide whether this is a bunsetsu boundary.
    各文字位置について、CRFがこれが文節境界かどうかを決定するのに役立つ
    特徴量（プロパティ）を抽出する必要がある。

    ============================================================================
    FEATURE CATEGORIES / 特徴量カテゴリ
    ============================================================================

    1. CHARACTER IDENTITY (文字アイデンティティ):
       - The character itself: char=は
         文字自体
       - Character type: type=hiragana
         文字タイプ

    2. CONTEXT WINDOW (コンテキストウィンドウ):
       - Previous/next characters: char[-1]=う, char[+1]=て
         前後の文字
       - Bigrams: bigram[-1:0]=うは
         バイグラム
       - Type changes: type_change=True (hiragana→katakana often = boundary)
         タイプ変更（ひらがな→カタカナは境界であることが多い）

    3. BOUNDARY MARKERS (境界マーカー):
       - BOS (Beginning of Sentence) / 文頭
       - EOS (End of Sentence) / 文末

    4. LINGUISTIC FEATURES (言語特徴量):
       - Particle detection: joshi=は
         助詞検出
       - Auxiliary verb detection: jodoushi=ます
         助動詞検出

    5. DICTIONARY FEATURES (辞書特徴量):
       - Does a dictionary word START here? dict_start_len=4
         辞書の単語がここから始まるか？
       - Does a dictionary word END here? dict_end_len=3
         辞書の単語がここで終わるか？

    ============================================================================

    Args:
        chars: List of characters in the sentence.
               文中の文字のリスト。
        i: Position of the current character (0-indexed).
           現在の文字の位置（0始まり）。
        dictionary_readings: Optional set of dictionary readings for lookup.
                             ルックアップ用のオプションの辞書読みのセット。

    Returns:
        list: List of feature strings for this position.
              この位置の特徴量文字列のリスト。
    """
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


# ─── GTK Panel ────────────────────────────────────────────────────────

class ConversionModelPanel(Gtk.Window):
    """
    GTK Window for training and testing CRF bunsetsu segmentation models.
    CRF文節セグメンテーションモデルの訓練とテスト用のGTKウィンドウ。

    ============================================================================
    OVERVIEW / 概要
    ============================================================================

    This panel provides a complete workflow for:
    このパネルは以下の完全なワークフローを提供:

        1. TESTING existing models (Test tab)
           既存モデルのテスト（テストタブ）
        2. TRAINING new models (Train tab)
           新しいモデルの訓練（トレインタブ）

    ============================================================================
    TEST TAB / テストタブ
    ============================================================================

    Allows testing the trained model on arbitrary input:
    任意の入力で訓練されたモデルをテストできる:

        ┌─────────────────────────────────────────────────────────────────────┐
        │  Input: [きょうはてんきがよい                    ] [Test Prediction]│
        │                                                                     │
        │  Results:                                                           │
        │  ┌─────────┬─────────┬─────────┬─────────┬─────────┐              │
        │  │ きょう  │   は    │ てんき  │   が    │  よい   │              │
        │  │  (L)    │  (P)    │  (L)    │  (P)    │  (L)    │              │
        │  └─────────┴─────────┴─────────┴─────────┴─────────┘              │
        └─────────────────────────────────────────────────────────────────────┘

    ============================================================================
    TRAIN TAB - 3-STEP PIPELINE / トレインタブ - 3ステップパイプライン
    ============================================================================

        STEP 1: BROWSE CORPUS / コーパスを参照
        ─────────────────────────────────────
        Select a text file with annotated training data.
        注釈付き訓練データのテキストファイルを選択。

            きょう _は_ てんき _が_ よい
            わたし _は_ がくせい _です_

        STEP 2: FEATURE EXTRACT / 特徴量抽出
        ────────────────────────────────────
        Parse the corpus and extract CRF features.
        コーパスを解析してCRF特徴量を抽出。

            - Parses each line into tokens + labels
              各行をトークン + ラベルに解析
            - Extracts features for each token position
              各トークン位置の特徴量を抽出

        STEP 3: TRAIN / 訓練
        ─────────────────────
        Train the CRF model using pycrfsuite.
        pycrfsuiteを使用してCRFモデルを訓練。

            - Uses L-BFGS optimization
              L-BFGS最適化を使用
            - Outputs bunsetsu_boundary.crfsuite model file
              bunsetsu_boundary.crfsuiteモデルファイルを出力

    ============================================================================
    ATTRIBUTES / 属性
    ============================================================================

    _raw_lines : list
        Raw lines loaded from corpus file (Step 1 output).
        コーパスファイルから読み込んだ生の行（ステップ1の出力）。

    _sentences : list
        Parsed (tokens, tags) tuples (Step 2 output).
        解析された(tokens, tags)タプル（ステップ2の出力）。

    _features : list
        Extracted features per sentence (Step 2 output).
        文ごとの抽出された特徴量（ステップ2の出力）。

    _tagger : pycrfsuite.Tagger
        Loaded CRF model for testing (lazy loaded).
        テスト用に読み込まれたCRFモデル（遅延読み込み）。

    ============================================================================
    DEPENDENCIES / 依存関係
    ============================================================================

    Requires pycrfsuite for training:
    訓練にはpycrfsuiteが必要:

        pip install python-crfsuite

    If not installed, training will be unavailable (test still works if
    model file exists).
    インストールされていない場合、訓練は利用不可（モデルファイルが
    存在すればテストは動作する）。

    ============================================================================
    """

    def __init__(self):
        """
        Initialize the Conversion Model panel.
        変換モデルパネルを初期化。
        """
        super().__init__(title="Conversion Model")

        self.set_default_size(1100, 800)
        self.set_border_width(10)

        # Set up CSS styling for grid headers
        # グリッドヘッダー用のCSSスタイリングを設定
        self._setup_css()

        # State for 3-step pipeline: Browse → Feature Extract → Train
        # 3ステップパイプライン用の状態: 参照 → 特徴量抽出 → 訓練
        self._raw_lines = []      # Raw lines from corpus file (set by Browse)
        self._sentences = []      # Parsed (chars, tags) tuples (set by Feature Extract)
        self._features = []       # Extracted features per sentence (set by Feature Extract)

        # State for Test tab
        # テストタブ用の状態
        self._tagger = None       # CRF tagger (lazy loaded)
        # Pre-computed dictionary features for CRF
        # CRF用の事前計算された辞書特徴量
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
        """
        Run bunsetsu-split prediction on input text.
        入力テキストに対して文節分割予測を実行。

        This is the main test function. It:
        これはメインのテスト関数。以下を行う:
            1. Loads the CRF model (if not already loaded)
               CRFモデルを読み込む（まだ読み込まれていない場合）
            2. Extracts features from the input text
               入力テキストから特徴量を抽出
            3. Runs the CRF tagger to predict labels
               CRFタガーを実行してラベルを予測
            4. Displays results in a visual grid
               結果を視覚的なグリッドで表示

        Args:
            button: The Gtk.Button that was clicked (unused).
                    クリックされたGtk.Button（未使用）。
        """
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
            "Example: \"きょう _は_ てんき _が_ よい\"\n"
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
        """
        Open file chooser for training corpus (Step 1 of training pipeline).
        訓練コーパス用のファイル選択ダイアログを開く（訓練パイプラインのステップ1）。

        Opens a file dialog for the user to select a text file containing
        annotated training data. The file should contain one sentence per line
        with space-separated bunsetsu (and optional underscore markers for
        passthrough segments).
        注釈付き訓練データを含むテキストファイルをユーザーが選択するための
        ファイルダイアログを開く。ファイルには1行につき1文、スペースで区切られた
        文節（およびパススルーセグメント用のオプションのアンダースコアマーカー）
        が含まれている必要がある。

        On successful selection:
        選択成功時:
            - Loads file contents into self._raw_lines
              ファイル内容をself._raw_linesに読み込み
            - Shows preview in the corpus preview area
              コーパスプレビューエリアにプレビューを表示
            - Enables the "Feature Extract" button
              「特徴量抽出」ボタンを有効化

        Args:
            button: The Gtk.Button that was clicked (unused).
                    クリックされたGtk.Button（未使用）。
        """
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
        """
        Parse annotations and extract CRF features (Step 2 of training pipeline).
        注釈を解析しCRF特徴量を抽出（訓練パイプラインのステップ2）。

        This step transforms raw annotated text into the format needed by CRF:
        このステップは生の注釈付きテキストをCRFが必要とする形式に変換:

            Raw line:     "きょう _は_ てんき _が_ よい"
            生の行:        "きょう _は_ てんき _が_ よい"
                               ↓
            Tokens:       ['き', 'ょ', 'う', 'は', 'て', ...]
            トークン:      ['き', 'ょ', 'う', 'は', 'て', ...]
                               ↓
            Labels:       ['B-L', 'I-L', 'I-L', 'B-P', 'B-L', ...]
            ラベル:        ['B-L', 'I-L', 'I-L', 'B-P', 'B-L', ...]
                               ↓
            Features:     [['bias', 'char=き', 'BOS', ...], ...]
            特徴量:        [['bias', 'char=き', 'BOS', ...], ...]

        On completion:
        完了時:
            - Stores parsed data in self._sentences
              解析されたデータをself._sentencesに保存
            - Stores features in self._features
              特徴量をself._featuresに保存
            - Shows statistics in the log
              統計をログに表示
            - Enables the "Train" button
              「訓練」ボタンを有効化

        Args:
            button: The Gtk.Button that was clicked (unused).
                    クリックされたGtk.Button（未使用）。
        """
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
            if re.search('^#', line):
                continue
            chars, tags = parse_annotated_line(line)
            if chars:
                self._sentences.append((chars, tags))

        if not self._sentences:
            self._log("ERROR: No valid sentences found in corpus.")
            return

        self._log(f"Parsed {len(self._sentences):,} sentences")

        # Calculate stats
        total_tokens = sum(len(tokens) for tokens, tags in self._sentences)
        total_bunsetsu = sum(
            sum(1 for tag in tags if tag.startswith('B-'))
            for tokens, tags in self._sentences
        )
        lookup_bunsetsu = sum(
            sum(1 for tag in tags if tag == 'B-L')
            for tokens, tags in self._sentences
        )
        passthrough_bunsetsu = sum(
            sum(1 for tag in tags if tag == 'B-P')
            for tokens, tags in self._sentences
        )

        self._log(f"  Bunsetsu: {total_bunsetsu:,} ({lookup_bunsetsu:,} lookup, {passthrough_bunsetsu:,} passthrough)")
        self._log(f"  Tokens: {total_tokens:,}")
        self._log("")

        # ── Extract features ──
        self._log("Extracting features...")
        feature_start_time = time.time()
        self._features = []
        for sent_idx, (tokens, tags) in enumerate(self._sentences):
            # Pass tokens directly (already tokenized by parse_annotated_line)
            features = util.add_features_per_line(tokens, self._crf_feature_materials)

            # Validate that feature count matches label count
            if len(features) != len(tags):
                self._log(f"WARNING: Length mismatch at sentence {sent_idx + 1}:")
                self._log(f"  Features: {len(features)}, Labels: {len(tags)}")
                self._log(f"  Tokens: {tokens}")
                self._log(f"  Tags: {tags}")
                self._log("")

            self._features.append(features)

        feature_elapsed = time.time() - feature_start_time
        self._log(f"Feature extraction complete ({feature_elapsed:.2f}s)")
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
                    for token, tag, feat_dict in zip(chars, tags, features):
                        # Convert feature dict to tab-separated string
                        feat_str = '\t'.join(f'{k}={v}' for k, v in feat_dict.items())
                        f.write(f'{token}\t{tag}\t{feat_str}\n')

            self._log(f"Training data saved to: {tsv_path}")
        except Exception as e:
            self._log(f"WARNING: Failed to save training data: {e}")

        # Update stats label
        self.corpus_stats_label.set_markup(
            f"<b>{len(self._sentences):,}</b> sentences, "
            f"<b>{total_bunsetsu:,}</b> bunsetsu "
            f"(<b>{lookup_bunsetsu:,}</b> lookup, <b>{passthrough_bunsetsu:,}</b> passthrough), "
            f"<b>{total_tokens:,}</b> tokens\n"
            f"<small>Features extracted. Click 'Train' to train the model.</small>"
        )

        self._log("")
        self._log("Done. Ready for training.")

    def on_train(self, button):
        """
        Run CRF training using extracted features (Step 3 of training pipeline).
        抽出された特徴量を使用してCRF訓練を実行（訓練パイプラインのステップ3）。

        This is the final step that actually trains the CRF model:
        これはCRFモデルを実際に訓練する最終ステップ:

            1. Creates a pycrfsuite.Trainer
               pycrfsuite.Trainerを作成
            2. Feeds in all (features, labels) pairs from Step 2
               ステップ2からの全ての(特徴量, ラベル)ペアを入力
            3. Runs L-BFGS optimization to learn feature weights
               L-BFGS最適化を実行して特徴量の重みを学習
            4. Saves the trained model to bunsetsu_boundary.crfsuite
               訓練されたモデルをbunsetsu_boundary.crfsuiteに保存

        CRF Training Parameters / CRF訓練パラメータ:
            - algorithm: lbfgs (Limited-memory BFGS optimization)
              アルゴリズム: lbfgs（限定メモリBFGS最適化）
            - max_iterations: 100
              最大イテレーション: 100
            - c1: 0.1 (L1 regularization coefficient)
              c1: 0.1（L1正則化係数）
            - c2: 0.1 (L2 regularization coefficient)
              c2: 0.1（L2正則化係数）

        On completion:
        完了時:
            - Saves model to user config directory
              ユーザー設定ディレクトリにモデルを保存
            - Shows training statistics (loss, feature count, etc.)
              訓練統計を表示（損失、特徴量数など）

        Requires:
        要件:
            - pycrfsuite must be installed
              pycrfsuiteがインストールされている必要がある
            - Features must be extracted first (Step 2)
              特徴量が先に抽出されている必要がある（ステップ2）

        Args:
            button: The Gtk.Button that was clicked (unused).
                    クリックされたGtk.Button（未使用）。
        """
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
        y_train = [tags for tokens, tags in self._sentences]

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

        train_start_time = time.time()
        trainer.train(model_path)
        train_elapsed = time.time() - train_start_time

        self._log(f"Training complete ({train_elapsed:.2f}s)")
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
        self._log(f"  Training time:   {train_elapsed:.2f}s")
        self._log("")
        self._log("Done.")


def main():
    """
    Run conversion model panel as standalone application.
    変換モデルパネルをスタンドアロンアプリケーションとして実行。

    Usage / 使用方法:
        python conversion_model.py

    This allows training and testing CRF models without going through
    the main IBus settings. Useful for model development and debugging.
    これによりメインのIBus設定を経由せずにCRFモデルの訓練とテストができる。
    モデル開発とデバッグに便利。
    """
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
