#!/usr/bin/env python3
"""
crf_core.py - Core CRF training and feature extraction logic
CRFの訓練と特徴量抽出のコアロジック

================================================================================
PURPOSE / 目的
================================================================================

This module provides the core logic for CRF-based bunsetsu segmentation,
separated from any GUI dependencies. It can be used by:

このモジュールはCRFベースの文節セグメンテーションのコアロジックを提供し、
GUIへの依存から分離されている。以下で使用可能:

    1. The GTK settings panel (conversion_model.py)
       GTK設定パネル
    2. CLI tools for power users (crf_train_cli.py)
       パワーユーザー向けCLIツール
    3. Automated training pipelines
       自動訓練パイプライン

================================================================================
ARCHITECTURE / アーキテクチャ
================================================================================

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                           crf_core.py                                   │
    │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
    │   │   Constants     │  │   Parsing       │  │   Training          │   │
    │   │   JOSHI         │  │   parse_line()  │  │   train_model()     │   │
    │   │   JODOUSHI      │  │   extract_*()   │  │   load_corpus()     │   │
    │   └─────────────────┘  └─────────────────┘  └─────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────┘
                    ↑                                       ↑
        ┌───────────┴───────────┐               ┌──────────┴──────────┐
        │  conversion_model.py  │               │  crf_train_cli.py   │
        │       (GUI)           │               │       (CLI)         │
        └───────────────────────┘               └─────────────────────┘

================================================================================
"""

import os
import re
import time
import logging

logger = logging.getLogger(__name__)

# Import utility functions
import util

# Check for pycrfsuite availability
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


# ═══════════════════════════════════════════════════════════════════════════════
# PARSING FUNCTIONS / 解析関数
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# CORPUS LOADING / コーパス読み込み
# ═══════════════════════════════════════════════════════════════════════════════

def load_corpus(path):
    """
    Load and parse a training corpus file.
    訓練コーパスファイルを読み込み解析。

    Args:
        path: Path to the corpus file.
              コーパスファイルへのパス。

    Returns:
        Tuple of (sentences, stats) where:
        (sentences, stats)のタプル:
            - sentences: List of (tokens, tags) tuples
              sentences: (tokens, tags)タプルのリスト
            - stats: Dictionary with corpus statistics
              stats: コーパス統計の辞書

    Raises:
        FileNotFoundError: If corpus file doesn't exist
        IOError: If file cannot be read
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Corpus file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    sentences = []
    for line in raw_lines:
        # Skip comments
        if re.search('^#', line):
            continue
        tokens, tags = parse_annotated_line(line)
        if tokens:
            sentences.append((tokens, tags))

    # Calculate statistics
    total_tokens = sum(len(tokens) for tokens, tags in sentences)
    total_bunsetsu = sum(
        sum(1 for tag in tags if tag.startswith('B-'))
        for tokens, tags in sentences
    )
    lookup_bunsetsu = sum(
        sum(1 for tag in tags if tag == 'B-L')
        for tokens, tags in sentences
    )
    passthrough_bunsetsu = sum(
        sum(1 for tag in tags if tag == 'B-P')
        for tokens, tags in sentences
    )

    stats = {
        'line_count': len([l for l in raw_lines if l.strip()]),
        'sentence_count': len(sentences),
        'total_tokens': total_tokens,
        'total_bunsetsu': total_bunsetsu,
        'lookup_bunsetsu': lookup_bunsetsu,
        'passthrough_bunsetsu': passthrough_bunsetsu,
    }

    return sentences, stats


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE EXTRACTION PIPELINE / 特徴量抽出パイプライン
# ═══════════════════════════════════════════════════════════════════════════════

def extract_features(sentences, crf_feature_materials=None, progress_callback=None):
    """
    Extract CRF features for all sentences.
    全文の CRF 特徴量を抽出。

    Args:
        sentences: List of (tokens, tags) tuples from load_corpus().
                   load_corpus()からの(tokens, tags)タプルのリスト。
        crf_feature_materials: Pre-computed dictionary features (optional).
                               事前計算された辞書特徴量（オプション）。
        progress_callback: Optional callback(current, total) for progress updates.
                           進捗更新用のオプションコールバック(current, total)。

    Returns:
        List of feature sequences (one per sentence).
        特徴量シーケンスのリスト（文ごとに1つ）。
    """
    if crf_feature_materials is None:
        crf_feature_materials = util.load_crf_feature_materials()

    features = []
    total = len(sentences)

    for idx, (tokens, tags) in enumerate(sentences):
        # Pass tokens directly (already tokenized by parse_annotated_line)
        feat_seq = util.add_features_per_line(tokens, crf_feature_materials)
        features.append(feat_seq)

        if progress_callback and (idx + 1) % 100 == 0:
            progress_callback(idx + 1, total)

    return features


def save_training_data_tsv(sentences, features, output_path):
    """
    Save training data to TSV file for inspection.
    訓練データをTSVファイルに保存して検査用に。

    Args:
        sentences: List of (tokens, tags) tuples.
                   (tokens, tags)タプルのリスト。
        features: List of feature sequences.
                  特徴量シーケンスのリスト。
        output_path: Path to output TSV file.
                     出力TSVファイルへのパス。
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for sent_idx, ((tokens, tags), feat_seq) in enumerate(zip(sentences, features)):
            # Blank line before sentence marker (except first sentence)
            if sent_idx > 0:
                f.write('\n')
            f.write(f'# Sentence {sent_idx + 1}\n')

            # Write each token with its tag and features
            for token, tag, feat_dict in zip(tokens, tags, feat_seq):
                # Convert feature dict to tab-separated string
                feat_str = '\t'.join(f'{k}={v}' for k, v in feat_dict.items())
                f.write(f'{token}\t{tag}\t{feat_str}\n')


def load_training_data_tsv(input_path):
    """
    Load training data from a TSV file previously saved by save_training_data_tsv().
    save_training_data_tsv()で保存されたTSVファイルから訓練データを読み込み。

    This enables the two-step training workflow:
    これにより2ステップ訓練ワークフローが可能:
        1. Extract features → save to TSV (inspect if needed)
           特徴量抽出 → TSVに保存（必要に応じて検査）
        2. Load from TSV → train model
           TSVから読み込み → モデル訓練

    Args:
        input_path: Path to the TSV file.
                    TSVファイルへのパス。

    Returns:
        Tuple of (sentences, features) where:
        (sentences, features)のタプル:
            - sentences: List of (tokens, tags) tuples
            - features: List of feature sequences (list of dicts)

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file format is invalid.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"TSV file not found: {input_path}")

    sentences = []
    features = []

    current_tokens = []
    current_tags = []
    current_features = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            # Skip empty lines (sentence boundaries)
            if not line:
                if current_tokens:
                    sentences.append((current_tokens, current_tags))
                    features.append(current_features)
                    current_tokens = []
                    current_tags = []
                    current_features = []
                continue

            # Skip comment lines (sentence markers like "# Sentence 1")
            if line.startswith('#'):
                continue

            # Parse data line: token\ttag\tfeature1=value1\tfeature2=value2\t...
            parts = line.split('\t')
            if len(parts) < 2:
                continue  # Skip malformed lines

            token = parts[0]
            tag = parts[1]

            # Parse features (key=value pairs)
            feat_dict = {}
            for feat_str in parts[2:]:
                if '=' in feat_str:
                    key, value = feat_str.split('=', 1)
                    feat_dict[key] = value

            current_tokens.append(token)
            current_tags.append(tag)
            current_features.append(feat_dict)

    # Don't forget the last sentence
    if current_tokens:
        sentences.append((current_tokens, current_tags))
        features.append(current_features)

    if not sentences:
        raise ValueError(f"No valid training data found in: {input_path}")

    return sentences, features


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING / 訓練
# ═══════════════════════════════════════════════════════════════════════════════

class TrainingResult:
    """
    Result of CRF training.
    CRF訓練の結果。
    """
    def __init__(self):
        self.success = False
        self.model_path = None
        self.training_time = 0.0
        self.model_size = 0
        self.sentence_count = 0
        self.token_count = 0
        self.last_iteration = None
        self.loss = None
        self.feature_count = None
        self.error_message = None


def train_model(sentences, features, model_path=None, params=None, progress_callback=None):
    """
    Train a CRF model using extracted features.
    抽出された特徴量を使用してCRFモデルを訓練。

    ============================================================================
    TRAINING PROCESS / 訓練プロセス
    ============================================================================

    1. Creates a pycrfsuite.Trainer
       pycrfsuite.Trainerを作成
    2. Feeds in all (features, labels) pairs
       全ての(特徴量, ラベル)ペアを入力
    3. Runs L-BFGS optimization to learn feature weights
       L-BFGS最適化を実行して特徴量の重みを学習
    4. Saves the trained model
       訓練されたモデルを保存

    ============================================================================

    Args:
        sentences: List of (tokens, tags) tuples.
                   (tokens, tags)タプルのリスト。
        features: List of feature sequences.
                  特徴量シーケンスのリスト。
        model_path: Output path for the model (default: from util).
                    モデルの出力パス（デフォルト: utilから）。
        params: CRF training parameters (optional).
                CRF訓練パラメータ（オプション）。
        progress_callback: Optional callback(message) for progress updates.
                           進捗更新用のオプションコールバック(message)。

    Returns:
        TrainingResult with training statistics.
        訓練統計を含むTrainingResult。
    """
    result = TrainingResult()

    if not HAS_CRFSUITE:
        result.error_message = "pycrfsuite not installed. Install with: pip install python-crfsuite"
        return result

    if not sentences or not features:
        result.error_message = "No training data provided"
        return result

    if model_path is None:
        model_path = util.get_crf_model_path()

    # Default parameters
    if params is None:
        params = {
            'c1': 1.0,        # L1 regularization
            'c2': 1e-3,       # L2 regularization
            'max_iterations': 100,
            'feature.possible_transitions': True,
        }

    # Prepare training data
    X_train = features
    y_train = [tags for tokens, tags in sentences]

    result.sentence_count = len(sentences)
    result.token_count = sum(len(seq) for seq in X_train)

    if progress_callback:
        progress_callback(f"Training CRF model with {result.sentence_count:,} sentences, {result.token_count:,} tokens...")

    # Create trainer and add data
    trainer = pycrfsuite.Trainer(verbose=False)
    for xseq, yseq in zip(X_train, y_train):
        trainer.append(xseq, yseq)

    trainer.set_params(params)

    # Train
    train_start_time = time.time()
    trainer.train(model_path)
    result.training_time = time.time() - train_start_time

    # Collect results
    result.success = True
    result.model_path = model_path
    result.model_size = os.path.getsize(model_path)

    info = trainer.logparser.last_iteration
    if info:
        result.last_iteration = info.get('num')
        result.loss = info.get('loss')
        result.feature_count = info.get('feature_count')

    if progress_callback:
        progress_callback(f"Training complete in {result.training_time:.2f}s")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTING / テスト
# ═══════════════════════════════════════════════════════════════════════════════

def test_prediction(input_text, model_path=None, n_best=5):
    """
    Test bunsetsu segmentation on input text.
    入力テキストで文節セグメンテーションをテスト。

    Args:
        input_text: Hiragana text to segment.
                    セグメントするひらがなテキスト。
        model_path: Path to CRF model (default: from util).
                    CRFモデルへのパス（デフォルト: utilから）。
        n_best: Number of best predictions to return.
                返す最良予測の数。

    Returns:
        List of (labels, score) tuples, sorted by score descending.
        スコア降順でソートされた(labels, score)タプルのリスト。

    Raises:
        FileNotFoundError: If model file doesn't exist.
    """
    if model_path is None:
        model_path = util.get_crf_model_path()

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    tagger = util.load_crf_tagger()
    if tagger is None:
        raise RuntimeError("Failed to load CRF tagger")

    crf_feature_materials = util.load_crf_feature_materials()
    results = util.crf_nbest_predict(tagger, input_text, n_best=n_best,
                                     dict_materials=crf_feature_materials)

    return results


def format_bunsetsu_output(tokens, labels, markup=False):
    """
    Format segmented bunsetsu for display.
    表示用にセグメントされた文節をフォーマット。

    Args:
        tokens: List of tokens.
                トークンのリスト。
        labels: List of predicted labels.
                予測されたラベルのリスト。
        markup: If True, return with markup (bold for lookup).
                Trueの場合、マークアップ付きで返す（ルックアップは太字）。

    Returns:
        Formatted string with bunsetsu separated by spaces.
        スペースで区切られた文節のフォーマット済み文字列。
    """
    bunsetsu_list = util.labels_to_bunsetsu(tokens, labels)
    if not bunsetsu_list:
        return ""

    if markup:
        parts = []
        for text, label in bunsetsu_list:
            is_lookup = label.endswith('-L') or label == 'B'
            if is_lookup:
                parts.append(f"**{text}**")
            else:
                parts.append(text)
        return ' '.join(parts)
    else:
        return ' '.join(text for text, label in bunsetsu_list)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING PIPELINES / 訓練パイプライン
# ═══════════════════════════════════════════════════════════════════════════════

def run_feature_extraction(corpus_path, output_path=None, progress_callback=None):
    """
    Run feature extraction pipeline: regenerate dictionary features → load corpus → extract → save TSV.
    特徴量抽出パイプラインを実行: 辞書特徴量再生成 → コーパス読み込み → 抽出 → TSV保存。

    This is Step 1 of the two-step training workflow. It extracts features
    and saves them to a human-readable TSV file for inspection before training.
    これは2ステップ訓練ワークフローのステップ1。特徴量を抽出し
    人間が読めるTSVファイルに保存して、訓練前に検査できるようにする。

    IMPORTANT: This function regenerates crf_feature_materials.json from all
    dictionaries (system, user, extended) to ensure dictionary changes are
    reflected in the extracted features.
    重要: この関数は全ての辞書（システム、ユーザー、拡張）から
    crf_feature_materials.jsonを再生成し、辞書の変更が抽出された特徴量に
    反映されることを保証する。

    Args:
        corpus_path: Path to the training corpus file.
                     訓練コーパスファイルへのパス。
        output_path: Path to save extracted features TSV (default: auto).
                     抽出された特徴量TSVの保存パス（デフォルト: 自動）。
        progress_callback: Optional callback(message) for progress updates.
                           進捗更新用のオプションコールバック(message)。

    Returns:
        Tuple of (output_path, stats) where output_path is the path to the
        saved TSV file and stats is the corpus statistics dictionary.
        (output_path, stats)のタプル。output_pathは保存されたTSVファイルの
        パス、statsはコーパス統計辞書。
    """
    # Step 0: Regenerate dictionary-derived CRF features
    # This ensures any changes to extended_dictionary.json, user_dictionary.json, etc.
    # are reflected in the extracted features
    if progress_callback:
        progress_callback("Regenerating dictionary features (crf_feature_materials.json)...")

    materials_path = util.generate_crf_feature_materials()
    if materials_path:
        if progress_callback:
            progress_callback(f"Dictionary features updated: {materials_path}")
    else:
        if progress_callback:
            progress_callback("Warning: Failed to regenerate dictionary features, using existing file")

    # Step 1: Load corpus
    if progress_callback:
        progress_callback("Loading corpus...")

    sentences, stats = load_corpus(corpus_path)

    if progress_callback:
        progress_callback(f"Loaded {stats['sentence_count']:,} sentences, {stats['total_tokens']:,} tokens")

    # Step 2: Extract features (using freshly regenerated dictionary features)
    if progress_callback:
        progress_callback("Extracting features...")

    crf_feature_materials = util.load_crf_feature_materials()
    features = extract_features(sentences, crf_feature_materials)

    if progress_callback:
        progress_callback("Feature extraction complete")

    # Determine output path (aligned with conversion_model.py)
    if output_path is None:
        output_path = os.path.join(util.get_user_config_dir(), 'crf_model_training_data.tsv')

    # Save to TSV (human-readable and reloadable)
    save_training_data_tsv(sentences, features, output_path)
    if progress_callback:
        progress_callback(f"Features saved to: {output_path}")

    return output_path, stats


def run_training_from_features(features_path, model_path=None, progress_callback=None):
    """
    Run training from pre-extracted features: load TSV → train.
    事前抽出された特徴量から訓練を実行: TSV読み込み → 訓練。

    This is Step 2 of the two-step training workflow. It loads previously
    extracted features from a TSV file and trains a CRF model.
    これは2ステップ訓練ワークフローのステップ2。以前に抽出された
    特徴量をTSVファイルから読み込み、CRFモデルを訓練する。

    Args:
        features_path: Path to the extracted features TSV file.
                       抽出された特徴量のTSVファイルへのパス。
        model_path: Output path for the model (default: auto).
                    モデルの出力パス（デフォルト: 自動）。
        progress_callback: Optional callback(message) for progress updates.
                           進捗更新用のオプションコールバック(message)。

    Returns:
        Tuple of (result, stats) where result is TrainingResult and stats is
        a basic statistics dictionary.
        (result, stats)のタプル。resultはTrainingResult、statsは基本統計辞書。
    """
    # Load pre-extracted features from TSV
    if progress_callback:
        progress_callback(f"Loading features from: {features_path}")

    sentences, features = load_training_data_tsv(features_path)

    # Calculate basic stats from loaded data
    stats = {
        'sentence_count': len(sentences),
        'total_tokens': sum(len(tokens) for tokens, tags in sentences),
    }

    if progress_callback:
        progress_callback(f"Loaded {stats['sentence_count']:,} sentences with pre-extracted features")

    # Train model
    result = train_model(sentences, features, model_path, progress_callback=progress_callback)

    return result, stats


def run_training_pipeline(corpus_path, model_path=None, progress_callback=None):
    """
    Run the complete training pipeline: regenerate dict features → load → extract → train (one-shot).
    完全な訓練パイプラインを実行: 辞書特徴量再生成 → 読み込み → 抽出 → 訓練（ワンショット）。

    This is a convenience function that runs all steps in sequence.
    For more control, use run_feature_extraction() followed by
    run_training_from_features().
    これは全ステップを順番に実行する便利な関数。
    より制御したい場合は、run_feature_extraction()の後に
    run_training_from_features()を使用する。

    IMPORTANT: This function regenerates crf_feature_materials.json from all
    dictionaries (system, user, extended) to ensure dictionary changes are
    reflected in the training.
    重要: この関数は全ての辞書（システム、ユーザー、拡張）から
    crf_feature_materials.jsonを再生成し、辞書の変更が訓練に
    反映されることを保証する。

    Args:
        corpus_path: Path to the training corpus file.
                     訓練コーパスファイルへのパス。
        model_path: Output path for the model (optional).
                    モデルの出力パス（オプション）。
        progress_callback: Optional callback(message) for progress updates.
                           進捗更新用のオプションコールバック(message)。

    Returns:
        Tuple of (result, stats) where result is TrainingResult and stats is
        corpus statistics dictionary.
        (result, stats)のタプル。resultはTrainingResult、statsはコーパス統計辞書。
    """
    # Step 0: Regenerate dictionary-derived CRF features
    if progress_callback:
        progress_callback("Regenerating dictionary features (crf_feature_materials.json)...")

    materials_path = util.generate_crf_feature_materials()
    if materials_path:
        if progress_callback:
            progress_callback(f"Dictionary features updated: {materials_path}")
    else:
        if progress_callback:
            progress_callback("Warning: Failed to regenerate dictionary features, using existing file")

    # Step 1: Load corpus
    if progress_callback:
        progress_callback("Loading corpus...")

    sentences, stats = load_corpus(corpus_path)

    if progress_callback:
        progress_callback(f"Loaded {stats['sentence_count']:,} sentences, {stats['total_tokens']:,} tokens")

    # Step 2: Extract features (using freshly regenerated dictionary features)
    if progress_callback:
        progress_callback("Extracting features...")

    crf_feature_materials = util.load_crf_feature_materials()
    features = extract_features(sentences, crf_feature_materials)

    if progress_callback:
        progress_callback("Feature extraction complete")

    # Save TSV for reference/debugging
    tsv_path = os.path.join(util.get_user_config_dir(), 'crf_model_training_data.tsv')
    save_training_data_tsv(sentences, features, tsv_path)
    if progress_callback:
        progress_callback(f"Training data saved to: {tsv_path}")

    # Step 3: Train model
    result = train_model(sentences, features, model_path, progress_callback=progress_callback)

    return result, stats
