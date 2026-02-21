#!/usr/bin/env python3
"""
henkan.py - Kana to Kanji conversion (変換) processor
かな漢字変換プロセッサ

================================================================================
WHAT THIS FILE DOES / このファイルの役割
================================================================================

This is the CORE CONVERSION ENGINE of PSKK. When you type hiragana and press
the conversion key, THIS module decides what kanji candidates to show.

これはPSKKのコア変換エンジン。ひらがなを入力して変換キーを押すと、
このモジュールがどの漢字候補を表示するかを決定する。

    User types:     へんかん
    ユーザー入力:    へんかん
                       ↓
    HenkanProcessor → Dictionary lookup → [変換, 返還, 編纂, ...]
                       ↓
    User sees:      変換 (best match)
    ユーザー表示:    変換（最良のマッチ）

================================================================================
TWO CONVERSION MODES / 2つの変換モード
================================================================================

This module supports TWO conversion modes:

このモジュールは2つの変換モードをサポート:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                         │
    │  MODE 1: WHOLE-WORD MODE (全語モード)                                    │
    │  ─────────────────────────────────────────────────────────────────────   │
    │                                                                         │
    │  Input: へんかん → Dictionary lookup → [変換, 返還, ...]                 │
    │                                                                         │
    │  Used when: Dictionary has an exact match for the full input            │
    │  使用時:    辞書が入力全体に対して完全一致を持つ場合                        │
    │                                                                         │
    │  Simple, fast, works for most single words.                             │
    │  シンプル、高速、ほとんどの単語で動作。                                    │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                         │
    │  MODE 2: BUNSETSU MODE (文節モード)                                      │
    │  ─────────────────────────────────────────────────────────────────────   │
    │                                                                         │
    │  Input: きょうはてんきがよい                                              │
    │         ↓ (No dictionary match for full string)                         │
    │         ↓ (文字列全体に辞書マッチなし)                                    │
    │                                                                         │
    │  CRF predicts: きょう|は|てんき|が|よい                                   │
    │                  ↓     ↓    ↓    ↓   ↓                                  │
    │  Lookup:       今日   は  天気   が  良い                                │
    │                  ↓     ↓    ↓    ↓   ↓                                  │
    │  Result:       今日は天気が良い                                          │
    │                                                                         │
    │  Used when: Dictionary has NO match for full input                      │
    │  使用時:    辞書が入力全体に対してマッチを持たない場合                      │
    │                                                                         │
    │  Falls back to CRF-based segmentation for multi-word phrases.           │
    │  複数単語のフレーズにはCRFベースのセグメンテーションにフォールバック。      │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘

================================================================================
HOW CRF INTERACTION WORKS / CRF連携の仕組み
================================================================================

When whole-word mode fails (no dictionary match), the processor uses the
CRF model to segment the input into bunsetsu (phrase units):

全語モードが失敗した場合（辞書マッチなし）、プロセッサはCRFモデルを使用して
入力を文節（フレーズ単位）にセグメント化する:

    STEP 1: FEATURE EXTRACTION (特徴量抽出)
    ───────────────────────────────────────

        Input: きょうはてんきがよい
               ↓
        For each character position, extract features:
        各文字位置について、特徴量を抽出:

        Position 0 (き): ['char=き', 'type=hiragana', 'BOS', ...]
        Position 1 (ょ): ['char=ょ', 'char[-1]=き', ...]
        Position 2 (う): ['char=う', 'char[-1]=ょ', ...]
        Position 3 (は): ['char=は', 'joshi=は', ...]  ← particle detected!
        ...

    STEP 2: CRF PREDICTION (CRF予測)
    ─────────────────────────────────

        Features → CRF Model → Labels
        特徴量    → CRFモデル → ラベル

        Labels: B-L, I-L, I-L, B-P, B-L, I-L, I-L, B-P, B-L, I-L
                ↓
        Bunsetsu: [きょう(L), は(P), てんき(L), が(P), よい(L)]
                      ↑         ↑         ↑        ↑       ↑
                   Lookup  Passthrough Lookup  Passthrough Lookup

    STEP 3: DICTIONARY LOOKUP PER BUNSETSU (文節ごとの辞書検索)
    ────────────────────────────────────────────────────────────

        きょう (L) → Dictionary → [今日, 京, 教, ...]
        は (P)     → Passthrough → は (no conversion)
        てんき (L) → Dictionary → [天気, 転機, 電気, ...]
        が (P)     → Passthrough → が (no conversion)
        よい (L)   → Dictionary → [良い, 酔い, 宵, ...]

    STEP 4: COMBINE RESULTS (結果の結合)
    ─────────────────────────────────────

        今日 + は + 天気 + が + 良い = 今日は天気が良い

================================================================================
N-BEST PREDICTIONS / N-Best予測
================================================================================

The CRF provides N-best predictions (multiple possible segmentations):
CRFはN-best予測（複数の可能なセグメンテーション）を提供:

    N-Best #1: きょう|は|てんき|が|よい (score: -2.34)
    N-Best #2: きょうは|てんき|が|よい (score: -3.12)
    N-Best #3: きょう|は|てんきが|よい (score: -3.45)
    ...

Users can cycle through these predictions using the bunsetsu_cycle key.
ユーザーはbunsetsu_cycleキーを使用してこれらの予測を循環できる。

================================================================================
CANDIDATE NAVIGATION / 候補ナビゲーション
================================================================================

In bunsetsu mode, users can:
文節モードでは、ユーザーは以下が可能:

    - Left/Right arrows: Select which bunsetsu to edit
      左右矢印: 編集する文節を選択
    - Up/Down arrows: Cycle candidates for the selected bunsetsu
      上下矢印: 選択された文節の候補を循環
    - Tab/Shift+Tab: Cycle through N-best segmentation predictions
      Tab/Shift+Tab: N-bestセグメンテーション予測を循環

    Example / 例:
        Current: [今日] は [天気] が [良い]
                  ↑ selected / 選択中

        Press Down: [京] は [天気] が [良い]  (changed 今日→京)
        Press Right: [今日] は [天気] が [良い]
                              ↑ selected / 選択中

================================================================================
THREAD SAFETY / スレッドセーフティ
================================================================================

Dictionary loading happens in a BACKGROUND THREAD to avoid blocking the UI:
辞書の読み込みはUIをブロックしないようにバックグラウンドスレッドで行われる:

    Main thread             Background thread
    メインスレッド           バックグラウンドスレッド
    ─────────────────────────────────────────────────
    HenkanProcessor()  ──►  Start loading dictionaries
                            辞書の読み込みを開始
         │
         ▼
    convert("へんかん")     [Still loading...]
         │                  [読み込み中...]
         ▼
    Passthrough (return     ────►  Loading complete!
    input as-is until              読み込み完了！
    ready)
         │
         ▼
    convert("へんかん")     [Ready - use dictionary]
         │                  [準備完了 - 辞書を使用]
         ▼
    [変換, 返還, ...]

The _lock ensures thread-safe access to the dictionary during loading.
_lockは読み込み中の辞書への安全なアクセスを保証する。

================================================================================
DICTIONARY FORMAT / 辞書形式
================================================================================

Dictionaries are JSON files with this structure:
辞書は以下の構造を持つJSONファイル:

    {
      "reading": {
        "candidate1": count,
        "candidate2": count,
        ...
      },
      ...
    }

Example / 例:

    {
      "へんかん": {
        "変換": 100,
        "返還": 50,
        "編纂": 10
      },
      "きょう": {
        "今日": 200,
        "京": 80,
        "教": 40
      }
    }

Higher count = higher priority (shown first in candidate list).
高いカウント = 高い優先度（候補リストで最初に表示）。

================================================================================
"""

import logging
import os
import threading

import orjson

import util

logger = logging.getLogger(__name__)


class HenkanProcessor:
    """
    Processor for kana-to-kanji conversion (かな漢字変換).
    かな漢字変換プロセッサ。

    ============================================================================
    OVERVIEW / 概要
    ============================================================================

    This class is the main conversion engine. It handles:
    このクラスはメイン変換エンジン。以下を担当:

        1. Loading and merging multiple dictionaries
           複数の辞書の読み込みとマージ
        2. Whole-word dictionary lookup
           全語辞書検索
        3. CRF-based bunsetsu segmentation (fallback)
           CRFベースの文節セグメンテーション（フォールバック）
        4. Candidate navigation (next/previous)
           候補ナビゲーション（次/前）
        5. Bunsetsu-level navigation and candidate cycling
           文節レベルのナビゲーションと候補循環

    ============================================================================
    CONVERSION FLOW / 変換フロー
    ============================================================================

        ┌─────────────────────────────────────────────────────────────────────┐
        │  convert(reading)                                                   │
        │  変換(読み)                                                          │
        │      │                                                              │
        │      ▼                                                              │
        │  Dictionary has match?  ──YES──►  WHOLE-WORD MODE                   │
        │  辞書にマッチあり？                  全語モード                        │
        │      │                              Return sorted candidates        │
        │      │NO                            ソートされた候補を返す             │
        │      ▼                                                              │
        │  CRF predict bunsetsu  ──►  BUNSETSU MODE                           │
        │  CRF文節予測                 文節モード                               │
        │                              Segment, lookup each, combine          │
        │                              セグメント、各々検索、結合               │
        └─────────────────────────────────────────────────────────────────────┘

    ============================================================================
    STATE MANAGEMENT / 状態管理
    ============================================================================

    The processor maintains state for the current conversion:
    プロセッサは現在の変換の状態を維持:

    WHOLE-WORD MODE STATE / 全語モード状態:
        _candidates          : List of candidate dicts
                               候補辞書のリスト
        _selected_index      : Currently selected candidate index
                               現在選択されている候補のインデックス

    BUNSETSU MODE STATE / 文節モード状態:
        _bunsetsu_mode       : Whether in bunsetsu mode
                               文節モードかどうか
        _bunsetsu_predictions: N-best CRF predictions
                               N-best CRF予測
        _bunsetsu_candidates : Per-bunsetsu candidate lists
                               文節ごとの候補リスト
        _bunsetsu_selected_indices: Per-bunsetsu selected indices
                                    文節ごとの選択インデックス
        _selected_bunsetsu_index: Which bunsetsu is being edited
                                  編集中の文節

    Call reset() to clear all state when starting a new conversion.
    新しい変換を開始する時はreset()を呼んで全ての状態をクリア。

    ============================================================================
    THREAD SAFETY / スレッドセーフティ
    ============================================================================

    Dictionary loading happens in a background thread:
    辞書の読み込みはバックグラウンドスレッドで行われる:

        - Use is_ready() to check if loading is complete
          is_ready()を使用して読み込みが完了したかチェック
        - Before ready, convert() returns passthrough (input as-is)
          準備完了前、convert()はパススルー（入力をそのまま）を返す
        - _lock protects dictionary access during loading
          _lockは読み込み中の辞書アクセスを保護

    ============================================================================
    """

    def __init__(self, dictionary_files=None):
        """
        Initialize the HenkanProcessor.
        HenkanProcessorを初期化。

        Dictionary loading happens in a BACKGROUND THREAD to avoid blocking
        the main thread. This ensures the IME starts quickly even with
        large dictionaries.
        辞書の読み込みはメインスレッドをブロックしないようにバックグラウンド
        スレッドで行われる。これにより大きな辞書でもIMEが素早く起動する。

        Use is_ready() to check if loading is complete.
        Before loading completes, convert() returns passthrough (input as-is).
        読み込みが完了したかはis_ready()でチェック。
        読み込み完了前、convert()はパススルー（入力をそのまま）を返す。

        Args:
            dictionary_files: List of paths to dictionary JSON files.
                              辞書JSONファイルへのパスのリスト。
                              Files are loaded in order; later files can
                              add new entries or increase counts for existing ones.
                              ファイルは順番に読み込まれる; 後のファイルは
                              新しいエントリを追加したり既存のカウントを増加できる。
        """
        # ─── Thread Safety ───
        # Lock for thread-safe access to _dictionary during background loading
        self._lock = threading.Lock()
        self._ready = False  # Set to True when background loading completes

        # Merged dictionary: {reading: {candidate: {"POS": str, "cost": float}}}
        self._dictionary = {}
        self._candidates = []    # Current conversion candidates (whole-word mode)
        self._selected_index = 0 # Currently selected candidate index (whole-word mode)
        self._dictionary_count = 0  # Number of successfully loaded dictionaries

        # CRF tagger for bunsetsu prediction (lazy loaded)
        self._tagger = None
        # Pre-computed dictionary features for CRF (loaded in background)
        self._crf_feature_materials = {}

        # ─── Bunsetsu Mode State ───
        # Bunsetsu mode allows multi-bunsetsu conversion when:
        # 1. No dictionary match for full yomi (automatic fallback)
        # 2. User presses bunsetsu_prediction_cycle_key (manual switch)
        self._bunsetsu_mode = False
        self._current_yomi = ''  # The yomi being converted
        self._has_whole_word_match = False  # Whether dictionary has full yomi match

        # N-best bunsetsu predictions (filtered to multi-bunsetsu only)
        # Each entry: (bunsetsu_list, score) where bunsetsu_list is [(text, label), ...]
        self._bunsetsu_predictions = []
        self._bunsetsu_prediction_index = 0  # Current N-best index

        # Per-bunsetsu candidate state (for the current bunsetsu prediction)
        # _bunsetsu_candidates[i] = list of candidate dicts for bunsetsu i
        # _bunsetsu_selected_indices[i] = selected candidate index for bunsetsu i
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []
        self._selected_bunsetsu_index = 0  # Which bunsetsu is selected for navigation

        # Start background loading thread
        if dictionary_files:
            self._dictionary_files = dictionary_files
            thread = threading.Thread(target=self._background_load, daemon=True)
            thread.start()
        else:
            self._dictionary_files = []
            self._ready = True  # No files to load, immediately ready

    def _background_load(self):
        """
        Background thread: load dictionaries and CRF feature materials.

        This runs in a separate thread to avoid blocking the main UI thread.
        Sets _ready = True when complete.
        """
        try:
            # Load CRF feature materials (reads JSON file)
            materials = util.load_crf_feature_materials()

            # Load dictionaries (reads multiple JSON files)
            self._load_dictionaries(self._dictionary_files)

            # Atomic assignment of materials after dictionaries are loaded
            with self._lock:
                self._crf_feature_materials = materials
                self._ready = True

            logger.info('HenkanProcessor background loading complete')

        except Exception as e:
            logger.error(f'HenkanProcessor background loading failed: {e}')
            # Mark as ready anyway so we don't block forever
            with self._lock:
                self._ready = True

    def is_ready(self):
        """
        Check if background loading is complete.

        Returns:
            bool: True if dictionaries are loaded and ready for conversion
        """
        with self._lock:
            return self._ready

    def _load_dictionaries(self, dictionary_files):
        """
        Load and merge multiple dictionary files.

        Each dictionary file is a JSON object mapping readings to candidates:
            {"reading": {"candidate1": {"POS": "品詞", "cost": cost1}, ...}}

        When merging, the entry with lower cost is kept for duplicate candidates.
        If no files exist or all fail to load, the dictionary remains empty
        and conversions will fall back to passthrough mode.

        Args:
            dictionary_files: List of paths to dictionary JSON files (may be empty)
        """
        if not dictionary_files:
            logger.info('No dictionary files provided - conversion will use passthrough mode')
            return

        for file_path in dictionary_files:
            if not os.path.exists(file_path):
                logger.warning(f'Dictionary file not found: {file_path}')
                continue

            try:
                with open(file_path, 'rb') as f:
                    data = orjson.loads(f.read())

                if not isinstance(data, dict):
                    logger.warning(f'Invalid dictionary format (expected dict): {file_path}')
                    continue

                # Merge into main dictionary
                entries_added = 0
                for reading, candidates in data.items():
                    if not isinstance(candidates, dict):
                        continue

                    if reading not in self._dictionary:
                        self._dictionary[reading] = {}

                    for candidate, entry in candidates.items():
                        # Entry format: count (int) - higher count = better candidate
                        # For legacy format {"POS": ..., "cost": ...}, convert to count
                        if isinstance(entry, dict):
                            # Legacy format - convert cost to count (negate so lower cost = higher count)
                            count = -entry.get("cost", 0)
                        else:
                            # New format - entry is the count directly
                            count = entry if isinstance(entry, (int, float)) else 1

                        if candidate in self._dictionary[reading]:
                            # Keep entry with higher count (better candidate)
                            existing_count = self._dictionary[reading][candidate]
                            if count > existing_count:
                                self._dictionary[reading][candidate] = count
                        else:
                            self._dictionary[reading][candidate] = count
                        entries_added += 1

                self._dictionary_count += 1
                logger.info(f'Loaded dictionary: {file_path} ({entries_added} candidate entries)')

            except orjson.JSONDecodeError as e:
                logger.error(f'Failed to parse dictionary JSON: {file_path} - {e}')
            except Exception as e:
                logger.error(f'Failed to load dictionary: {file_path} - {e}')

        # Summary logging with appropriate level
        if self._dictionary_count == 0:
            logger.warning('No dictionaries loaded - conversion will use passthrough mode')
        else:
            logger.info(f'HenkanProcessor initialized with {self._dictionary_count} dictionaries, '
                       f'{len(self._dictionary)} readings')

    def convert(self, reading):
        """
        Convert a kana reading to kanji candidates.
        かなの読みを漢字候補に変換。

        This is the MAIN ENTRY POINT for conversion. It implements the
        two-mode conversion strategy:
        これは変換のメインエントリーポイント。2モード変換戦略を実装:

            ┌─────────────────────────────────────────────────────────────────┐
            │  convert("へんかん")                                             │
            │      │                                                          │
            │      ▼                                                          │
            │  Dictionary lookup: "へんかん" in dictionary?                    │
            │      │                                                          │
            │      ├──YES──►  Return [変換, 返還, ...] (whole-word mode)       │
            │      │                                                          │
            │      └──NO───►  CRF predict → bunsetsu mode                     │
            │                 [今日|は|天気|が|良い]                            │
            └─────────────────────────────────────────────────────────────────┘

        If background loading is not complete, returns the reading as-is
        (passthrough mode) to avoid blocking.
        バックグラウンド読み込みが完了していない場合、ブロックを避けるため
        読みをそのまま返す（パススルーモード）。

        Args:
            reading: The kana string to convert (e.g., "へんかん").
                     変換するかな文字列（例: "へんかん"）。

        Returns:
            list: List of conversion candidates, each being a dict with:
                  変換候補のリスト、各々は以下を持つ辞書:
                  - 'surface': The converted text (e.g., "変換")
                               変換されたテキスト（例: "変換"）
                  - 'reading': The original reading (e.g., "へんかん")
                               元の読み（例: "へんかん"）
                  - 'count': Conversion priority (higher is better)
                             変換優先度（高いほど良い）

                  In bunsetsu mode, the candidates list contains a single entry
                  with the combined surface from all bunsetsu.
                  文節モードでは、候補リストには全文節からの結合サーフェスを
                  持つ単一のエントリが含まれる。
        """
        # Reset state
        self._candidates = []
        self._selected_index = 0
        self._current_yomi = reading
        self._bunsetsu_mode = False
        self._bunsetsu_predictions = []
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []
        self._selected_bunsetsu_index = 0

        # Check if background loading is complete
        if not self.is_ready():
            # Not ready yet - return passthrough
            logger.debug(f'HenkanProcessor.convert("{reading}") → not ready, passthrough')
            self._candidates.append({
                'surface': reading,
                'reading': reading,
                'cost': 0,
                'passthrough': True
            })
            return self._candidates

        # Lock protects dictionary access (though is_ready() already ensures loading is complete)
        with self._lock:
            has_match = reading in self._dictionary
            candidates_dict = self._dictionary.get(reading, {}).copy() if has_match else {}

        if has_match:
            # Whole-word dictionary match found
            self._has_whole_word_match = True
            # Sort by count (descending) - higher count = better candidate
            sorted_candidates = sorted(
                candidates_dict.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for surface, count in sorted_candidates:
                self._candidates.append({
                    'surface': surface,
                    'reading': reading,
                    'count': count
                })
            logger.debug(f'HenkanProcessor.convert("{reading}") → {len(self._candidates)} candidates')
        else:
            # No dictionary match - try bunsetsu-based conversion
            self._has_whole_word_match = False
            logger.debug(f'HenkanProcessor.convert("{reading}") → no match, trying bunsetsu mode')

            # Get CRF predictions and filter to multi-bunsetsu only
            predictions = self.predict_bunsetsu(reading)
            self._bunsetsu_predictions = [
                p for p in predictions if self._is_multi_bunsetsu(p[0])
            ]

            if self._bunsetsu_predictions:
                # Initialize bunsetsu mode with first prediction
                self._init_bunsetsu_mode(0)

                # Return a single candidate entry representing the bunsetsu result
                # (the actual surface is constructed from per-bunsetsu selections)
                self._candidates.append({
                    'surface': self.get_display_surface(),
                    'reading': reading,
                    'cost': 0,
                    'bunsetsu_mode': True
                })
                logger.debug(f'HenkanProcessor.convert("{reading}") → bunsetsu mode with '
                           f'{len(self._bunsetsu_predictions)} predictions')
            else:
                # No bunsetsu predictions available - return reading as-is
                self._candidates.append({
                    'surface': reading,
                    'reading': reading,
                    'cost': 0
                })
                logger.debug(f'HenkanProcessor.convert("{reading}") → no bunsetsu predictions, '
                           f'returning reading')

        return self._candidates

    def get_candidates(self):
        """
        Get the current list of conversion candidates.

        Returns:
            list: List of candidate dictionaries
        """
        return self._candidates

    def select_candidate(self, index):
        """
        Select a candidate by index.

        Args:
            index: The index of the candidate to select

        Returns:
            dict or None: The selected candidate, or None if index is invalid
        """
        if 0 <= index < len(self._candidates):
            self._selected_index = index
            return self._candidates[index]
        return None

    def get_selected_candidate(self):
        """
        Get the currently selected candidate.

        Returns:
            dict or None: The selected candidate, or None if no candidates
        """
        if self._candidates and 0 <= self._selected_index < len(self._candidates):
            return self._candidates[self._selected_index]
        return None

    def next_candidate(self):
        """
        Move to the next candidate in the list.

        Returns:
            dict or None: The new selected candidate, or None if no candidates
        """
        if self._candidates:
            self._selected_index = (self._selected_index + 1) % len(self._candidates)
            return self._candidates[self._selected_index]
        return None

    def previous_candidate(self):
        """
        Move to the previous candidate in the list.

        Returns:
            dict or None: The new selected candidate, or None if no candidates
        """
        if self._candidates:
            self._selected_index = (self._selected_index - 1) % len(self._candidates)
            return self._candidates[self._selected_index]
        return None

    def reset(self):
        """
        Reset the processor state, clearing candidates and selection.

        This clears both whole-word mode and bunsetsu mode state.
        """
        # Whole-word mode state
        self._candidates = []
        self._selected_index = 0

        # Bunsetsu mode state
        self._bunsetsu_mode = False
        self._current_yomi = ''
        self._has_whole_word_match = False
        self._bunsetsu_predictions = []
        self._bunsetsu_prediction_index = 0
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []
        self._selected_bunsetsu_index = 0

    def get_dictionary_stats(self):
        """
        Get statistics about loaded dictionaries.

        Returns:
            dict: Dictionary containing:
                  - 'dictionary_count': Number of loaded dictionary files
                  - 'reading_count': Total number of unique readings
                  - 'candidate_count': Total number of candidate entries
                  - 'ready': Whether background loading is complete
        """
        with self._lock:
            ready = self._ready
            reading_count = len(self._dictionary)
            candidate_count = sum(len(candidates) for candidates in self._dictionary.values())
            dict_count = self._dictionary_count

        return {
            'dictionary_count': dict_count,
            'reading_count': reading_count,
            'candidate_count': candidate_count,
            'ready': ready
        }

    # ─── CRF Bunsetsu Prediction ──────────────────────────────────────────
    # CRF文節予測

    def _load_tagger(self):
        """
        Lazy load the CRF tagger for bunsetsu prediction.
        文節予測用のCRFタガーを遅延読み込み。

        The CRF model file (bunsetsu_boundary.crfsuite) is loaded only when
        needed, to avoid slowing down startup for users who only use
        whole-word conversion.

        CRFモデルファイル（bunsetsu_boundary.crfsuite）は必要な時にのみ
        読み込まれ、全語変換のみを使用するユーザーの起動を遅らせない。

        Returns:
            bool: True if tagger is available, False otherwise.
                  タガーが利用可能ならTrue、それ以外はFalse。
        """
        if self._tagger is not None:
            return True

        self._tagger = util.load_crf_tagger()
        return self._tagger is not None

    def predict_bunsetsu(self, input_text, n_best=5):
        """
        Predict bunsetsu segmentation using CRF N-best Viterbi.
        CRF N-best Viterbiを使用して文節セグメンテーションを予測。

        ============================================================================
        HOW THIS WORKS / これの仕組み
        ============================================================================

        This is the KEY INTEGRATION POINT between henkan.py and the CRF model.
        これはhenkan.pyとCRFモデルの間のキー統合ポイント。

            Input: きょうはてんきがよい
            入力:  きょうはてんきがよい
                   ↓
            1. Extract features for each character
               各文字の特徴量を抽出
                   ↓
            2. CRF N-best Viterbi prediction
               CRF N-best Viterbi予測
                   ↓
            3. Convert label sequences to bunsetsu lists
               ラベルシーケンスを文節リストに変換
                   ↓
            Output: [('きょう', 'B-L'), ('は', 'B-P'), ...]
            出力:   [('きょう', 'B-L'), ('は', 'B-P'), ...]

        ============================================================================
        LABEL MEANINGS / ラベルの意味
        ============================================================================

            B-L = Beginning of Lookup bunsetsu (needs dictionary conversion)
                  LOOKUP文節の開始（辞書変換が必要）
            I-L = Inside of Lookup bunsetsu
                  LOOKUP文節の内部
            B-P = Beginning of Passthrough bunsetsu (output as-is)
                  PASSTHROUGH文節の開始（そのまま出力）
            I-P = Inside of Passthrough bunsetsu
                  PASSTHROUGH文節の内部

        ============================================================================

        Args:
            input_text: Hiragana input string to segment.
                        セグメント化するひらがな入力文字列。
            n_best: Number of top predictions to return (default: 5).
                    返すトップ予測の数（デフォルト: 5）。

        Returns:
            list: List of N-best predictions, each being a tuple of:
                  (bunsetsu_list, score)
                  N-best予測のリスト、各々は以下のタプル:
                  (bunsetsu_list, score)

                  bunsetsu_list is a list of (text, label) tuples:
                  bunsetsu_listは(text, label)タプルのリスト:
                      - text: The bunsetsu text / 文節テキスト
                      - label: 'B-L' (Lookup) or 'B-P' (Passthrough)

                  score is the CRF log-probability (more negative = less likely)
                  scoreはCRF対数確率（より負 = より可能性が低い）

        Example / 例:
            >>> processor.predict_bunsetsu("きょうはてんきがよい", n_best=3)
            [
                ([('きょう', 'B-L'), ('は', 'B-P'), ('てんき', 'B-L'), ('が', 'B-P'), ('よい', 'B-L')], -2.34),
                ([('きょうは', 'B-L'), ('てんき', 'B-L'), ('が', 'B-P'), ('よい', 'B-L')], -3.12),
                ...
            ]
        """
        if not input_text:
            return []

        if not self._load_tagger():
            logger.debug('CRF tagger not available for bunsetsu prediction')
            return []

        # Run N-best Viterbi prediction
        nbest_results = util.crf_nbest_predict(self._tagger, input_text, n_best=n_best,
                                               dict_materials=self._crf_feature_materials)

        # Convert label sequences to bunsetsu lists
        output = []
        tokens = util.tokenize_line(input_text)

        for labels, score in nbest_results:
            bunsetsu_list = util.labels_to_bunsetsu(tokens, labels)
            output.append((bunsetsu_list, score))

        return output

    # ─── Bunsetsu Mode Methods ────────────────────────────────────────────
    # 文節モードメソッド

    def _lookup_bunsetsu_candidates(self, bunsetsu_text):
        """
        Look up dictionary candidates for a single bunsetsu.
        単一の文節に対する辞書候補を検索。

        This is called for each "Lookup" bunsetsu identified by the CRF.
        Passthrough bunsetsu (particles) skip this and keep their text as-is.

        これはCRFによって識別された各「Lookup」文節に対して呼ばれる。
        Passthrough文節（助詞）はこれをスキップし、テキストをそのまま保持する。

        Args:
            bunsetsu_text: The bunsetsu yomi to look up.
                           検索する文節の読み。

        Returns:
            list: List of candidate dicts with 'surface', 'reading', 'count'.
                  If no match found, returns list with original text as surface
                  (marked as passthrough).
                  'surface', 'reading', 'count'を持つ候補辞書のリスト。
                  マッチが見つからない場合、元のテキストをsurfaceとして返す
                  （passthroughとしてマーク）。
        """
        candidates = []

        # Lock protects dictionary access
        with self._lock:
            has_match = bunsetsu_text in self._dictionary
            candidates_dict = self._dictionary.get(bunsetsu_text, {}).copy() if has_match else {}

        if has_match:
            # Sort by count (descending) - higher count = better candidate
            sorted_candidates = sorted(
                candidates_dict.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for surface, count in sorted_candidates:
                candidates.append({
                    'surface': surface,
                    'reading': bunsetsu_text,
                    'count': count
                })
        else:
            # No dictionary match - return original text
            candidates.append({
                'surface': bunsetsu_text,
                'reading': bunsetsu_text,
                'count': 0,
                'passthrough': True
            })

        return candidates

    def _is_multi_bunsetsu(self, bunsetsu_list):
        """
        Check if a bunsetsu prediction has multiple bunsetsu.

        Single-bunsetsu predictions are skipped because they're equivalent
        to whole-word lookup.

        Args:
            bunsetsu_list: List of (text, label) tuples

        Returns:
            bool: True if there are 2+ bunsetsu
        """
        return len(bunsetsu_list) >= 2

    def _init_bunsetsu_mode(self, prediction_index):
        """
        Initialize bunsetsu mode state for a given prediction index.
        指定された予測インデックスに対して文節モード状態を初期化。

        This sets up the per-bunsetsu candidates and selection state.
        When entering bunsetsu mode, this method:
        これは文節ごとの候補と選択状態を設定する。
        文節モードに入る時、このメソッドは:

            1. Gets the bunsetsu list from the N-best prediction
               N-best予測から文節リストを取得
            2. For each bunsetsu:
               各文節について:
                   - Lookup bunsetsu: Get dictionary candidates
                     Lookup文節: 辞書候補を取得
                   - Passthrough bunsetsu: Keep as-is (no alternatives)
                     Passthrough文節: そのまま保持（代替なし）
            3. Initializes selection indices (first candidate for each)
               選択インデックスを初期化（各々の最初の候補）

        Args:
            prediction_index: Index into _bunsetsu_predictions.
                              _bunsetsu_predictionsへのインデックス。
        """
        if not self._bunsetsu_predictions:
            return

        if prediction_index < 0 or prediction_index >= len(self._bunsetsu_predictions):
            return

        self._bunsetsu_prediction_index = prediction_index
        bunsetsu_list, score = self._bunsetsu_predictions[prediction_index]

        # Look up candidates for each bunsetsu
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []

        for text, label in bunsetsu_list:
            is_lookup = label.endswith('-L') or label == 'B'
            if is_lookup:
                # Lookup bunsetsu: get dictionary candidates
                candidates = self._lookup_bunsetsu_candidates(text)
            else:
                # Passthrough bunsetsu: keep as-is (no alternative candidates)
                candidates = [{
                    'surface': text,
                    'reading': text,
                    'cost': 0,
                    'passthrough': True  # Mark as passthrough
                }]

            self._bunsetsu_candidates.append(candidates)
            self._bunsetsu_selected_indices.append(0)  # Select first candidate

        # Select first bunsetsu for navigation
        self._selected_bunsetsu_index = 0
        self._bunsetsu_mode = True

        logger.debug(f'Initialized bunsetsu mode: {len(bunsetsu_list)} bunsetsu, '
                    f'prediction #{prediction_index + 1}')

    def is_bunsetsu_mode(self):
        """
        Check if currently in bunsetsu mode.

        Returns:
            bool: True if in bunsetsu mode
        """
        return self._bunsetsu_mode

    def get_bunsetsu_count(self):
        """
        Get the number of bunsetsu in current prediction.

        Returns:
            int: Number of bunsetsu, or 0 if not in bunsetsu mode
        """
        if not self._bunsetsu_mode:
            return 0
        return len(self._bunsetsu_candidates)

    def get_selected_bunsetsu_index(self):
        """
        Get the index of the currently selected bunsetsu.

        Returns:
            int: Selected bunsetsu index
        """
        return self._selected_bunsetsu_index

    def cycle_bunsetsu_prediction(self):
        """
        Cycle to the next bunsetsu prediction (N-best cycling).
        次の文節予測に循環（N-best循環）。

        This allows users to try different segmentations from the CRF.
        これによりユーザーはCRFからの異なるセグメンテーションを試せる。

        Cycling order / 循環順序:
            1. Whole-word dictionary match (if available)
               全語辞書マッチ（利用可能な場合）
            2. CRF N-best #1 (if multi-bunsetsu)
               CRF N-best #1（複数文節の場合）
            3. CRF N-best #2 (if multi-bunsetsu)
               CRF N-best #2（複数文節の場合）
            ... and wraps around to #1
               ...そして#1に戻る

        Example / 例:
            Input: きょうはてんきがよい

            [Tab] → 今日は天気が良い (whole-word if available)
            [Tab] → 今日|は|天気|が|良い (N-best #1)
            [Tab] → 今日は|天気|が|良い (N-best #2, different segmentation)
            [Tab] → (back to start)

        Returns:
            bool: True if mode changed, False otherwise.
                  モードが変更されたらTrue、それ以外はFalse。
        """
        if not self._current_yomi:
            return False

        # If we have no bunsetsu predictions yet, try to get them
        if not self._bunsetsu_predictions:
            predictions = self.predict_bunsetsu(self._current_yomi)
            # Filter to multi-bunsetsu only
            self._bunsetsu_predictions = [
                p for p in predictions if self._is_multi_bunsetsu(p[0])
            ]

        # Calculate total options (whole-word match counts as option 0 if available)
        total_options = len(self._bunsetsu_predictions)
        if self._has_whole_word_match:
            total_options += 1

        if total_options == 0:
            # No options available
            return False

        if self._has_whole_word_match:
            # Options: -1 = whole-word, 0..n-1 = bunsetsu predictions
            if not self._bunsetsu_mode:
                # Currently in whole-word mode, switch to bunsetsu #0
                if self._bunsetsu_predictions:
                    self._init_bunsetsu_mode(0)
                    return True
            else:
                # Currently in bunsetsu mode
                next_idx = self._bunsetsu_prediction_index + 1
                if next_idx >= len(self._bunsetsu_predictions):
                    # Wrap around to whole-word mode
                    self._bunsetsu_mode = False
                    self._selected_index = 0
                    logger.debug('Cycled back to whole-word mode')
                    return True
                else:
                    # Go to next bunsetsu prediction
                    self._init_bunsetsu_mode(next_idx)
                    return True
        else:
            # No whole-word match, only bunsetsu predictions
            if not self._bunsetsu_predictions:
                return False

            if not self._bunsetsu_mode:
                # Not yet in bunsetsu mode, initialize
                self._init_bunsetsu_mode(0)
                return True
            else:
                # Cycle through bunsetsu predictions
                next_idx = (self._bunsetsu_prediction_index + 1) % len(self._bunsetsu_predictions)
                self._init_bunsetsu_mode(next_idx)
                return True

        return False

    def select_bunsetsu(self, index):
        """
        Select a bunsetsu for candidate navigation.

        Args:
            index: Bunsetsu index to select

        Returns:
            bool: True if selection changed, False otherwise
        """
        if not self._bunsetsu_mode:
            return False
        if index < 0 or index >= len(self._bunsetsu_candidates):
            return False

        self._selected_bunsetsu_index = index
        return True

    def next_bunsetsu(self):
        """
        Move selection to the next bunsetsu (right arrow).

        Returns:
            bool: True if selection changed, False otherwise
        """
        if not self._bunsetsu_mode:
            return False

        count = len(self._bunsetsu_candidates)
        if count == 0:
            return False

        new_index = (self._selected_bunsetsu_index + 1) % count
        self._selected_bunsetsu_index = new_index
        return True

    def previous_bunsetsu(self):
        """
        Move selection to the previous bunsetsu (left arrow).

        Returns:
            bool: True if selection changed, False otherwise
        """
        if not self._bunsetsu_mode:
            return False

        count = len(self._bunsetsu_candidates)
        if count == 0:
            return False

        new_index = (self._selected_bunsetsu_index - 1) % count
        self._selected_bunsetsu_index = new_index
        return True

    def next_bunsetsu_candidate(self):
        """
        Cycle to next candidate for the currently selected bunsetsu.

        Returns:
            dict or None: The new selected candidate, or None if not applicable
        """
        if not self._bunsetsu_mode:
            return None

        idx = self._selected_bunsetsu_index
        if idx < 0 or idx >= len(self._bunsetsu_candidates):
            return None

        candidates = self._bunsetsu_candidates[idx]
        if not candidates or candidates[0].get('passthrough', False):
            # Passthrough bunsetsu has no alternatives
            return None

        # Cycle to next candidate
        current = self._bunsetsu_selected_indices[idx]
        new_idx = (current + 1) % len(candidates)
        self._bunsetsu_selected_indices[idx] = new_idx

        return candidates[new_idx]

    def previous_bunsetsu_candidate(self):
        """
        Cycle to previous candidate for the currently selected bunsetsu.

        Returns:
            dict or None: The new selected candidate, or None if not applicable
        """
        if not self._bunsetsu_mode:
            return None

        idx = self._selected_bunsetsu_index
        if idx < 0 or idx >= len(self._bunsetsu_candidates):
            return None

        candidates = self._bunsetsu_candidates[idx]
        if not candidates or candidates[0].get('passthrough', False):
            # Passthrough bunsetsu has no alternatives
            return None

        # Cycle to previous candidate
        current = self._bunsetsu_selected_indices[idx]
        new_idx = (current - 1) % len(candidates)
        self._bunsetsu_selected_indices[idx] = new_idx

        return candidates[new_idx]

    def get_display_surface(self):
        """
        Get the combined display surface for the current conversion.
        現在の変換の結合表示サーフェスを取得。

        In whole-word mode / 全語モード:
            Returns the selected candidate's surface.
            選択された候補のサーフェスを返す。
            Example: "変換"

        In bunsetsu mode / 文節モード:
            Returns all bunsetsu surfaces concatenated.
            全ての文節サーフェスを連結して返す。
            Example: "今日" + "は" + "天気" + "が" + "良い" = "今日は天気が良い"

        Returns:
            str: The display surface string.
                 表示サーフェス文字列。
        """
        if not self._bunsetsu_mode:
            # Whole-word mode
            candidate = self.get_selected_candidate()
            return candidate['surface'] if candidate else ''

        # Bunsetsu mode: concatenate all selected surfaces
        parts = []
        for i, candidates in enumerate(self._bunsetsu_candidates):
            if not candidates:
                continue
            selected_idx = self._bunsetsu_selected_indices[i]
            if 0 <= selected_idx < len(candidates):
                parts.append(candidates[selected_idx]['surface'])

        return ''.join(parts)

    def get_display_surface_with_selection(self):
        """
        Get the display surface with selection markers for preedit display.
        プリエディット表示用の選択マーカー付き表示サーフェスを取得。

        This is used by the engine to render the preedit with visual
        highlighting of the currently selected bunsetsu.
        これはエンジンが現在選択されている文節の視覚的ハイライト付きで
        プリエディットをレンダリングするために使用される。

        In whole-word mode / 全語モード:
            Returns single tuple with the surface, always selected.
            サーフェスを持つ単一のタプルを返す、常に選択状態。
            Example: [("変換", True)]

        In bunsetsu mode / 文節モード:
            Returns each bunsetsu with its selection state.
            各文節とその選択状態を返す。
            Example: [("今日", True), ("は", False), ("天気", False), ...]
                       ↑ selected / 選択中

        Returns:
            list: List of (text, is_selected) tuples for each bunsetsu.
                  各文節の(text, is_selected)タプルのリスト。
        """
        if not self._bunsetsu_mode:
            # Whole-word mode
            candidate = self.get_selected_candidate()
            surface = candidate['surface'] if candidate else ''
            return [(surface, True)]

        # Bunsetsu mode: return each bunsetsu with selection state
        result = []
        for i, candidates in enumerate(self._bunsetsu_candidates):
            if not candidates:
                continue
            selected_idx = self._bunsetsu_selected_indices[i]
            if 0 <= selected_idx < len(candidates):
                surface = candidates[selected_idx]['surface']
                is_selected = (i == self._selected_bunsetsu_index)
                result.append((surface, is_selected))

        return result
