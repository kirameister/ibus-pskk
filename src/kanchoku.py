#!/usr/bin/env python3
"""
kanchoku.py - Processor for kanchoku (漢直) direct kanji input
漢直（かんちょく）直接漢字入力プロセッサ

================================================================================
WHAT IS KANCHOKU? / 漢直とは？
================================================================================

Kanchoku (漢直, short for 漢字直接入力 "direct kanji input") is a Japanese
input method where kanji characters are typed DIRECTLY using key combinations,
WITHOUT typing the reading first.

漢直（漢字直接入力の略）は、読みを最初に入力せずに、キーの組み合わせを
使って漢字文字を直接入力する日本語入力方式。

================================================================================
HOW IT DIFFERS FROM NORMAL INPUT / 通常入力との違い
================================================================================

NORMAL JAPANESE INPUT (Kana-Kanji Conversion):
通常の日本語入力（かな漢字変換）:

    Type: "nihon" → See: "にほん" → Press Space → Choose: "日本"
    入力: "nihon" → 表示: "にほん" → スペース押す → 選択: "日本"

KANCHOKU (Direct Kanji Input):
漢直（直接漢字入力）:

    Type: "jk" → See: "日" (instantly!)
    入力: "jk" → 表示: "日"（即座に！）

    Type: "ks" → See: "本" (instantly!)
    入力: "ks" → 表示: "本"（即座に！）

================================================================================
WHY USE KANCHOKU? / なぜ漢直を使うのか？
================================================================================

ADVANTAGES / 利点:
    ✓ FASTER - No conversion step, no candidate selection
      高速 - 変換ステップなし、候補選択なし
    ✓ PRECISE - Always get the exact kanji you want
      正確 - 常に望む漢字を正確に取得
    ✓ CONSISTENT - Same keys always produce same kanji
      一貫性 - 同じキーは常に同じ漢字を生成

DISADVANTAGES / 欠点:
    ✗ LEARNING CURVE - Must memorize key combinations
      学習曲線 - キーの組み合わせを記憶する必要がある
    ✗ LIMITED COVERAGE - Can't type every possible kanji
      限られたカバレッジ - 全ての漢字を入力できるわけではない
    ✗ LAYOUT DEPENDENT - Different layouts = different combinations
      レイアウト依存 - 異なるレイアウト = 異なる組み合わせ

================================================================================
TWO-STROKE INPUT / 2ストローク入力
================================================================================

This module implements TWO-STROKE kanchoku, where each kanji requires
exactly two keystrokes:

このモジュールは2ストローク漢直を実装しており、各漢字は
正確に2つのキー入力を必要とする:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                         │
    │   FIRST STROKE           SECOND STROKE           OUTPUT                 │
    │   第1ストローク            第2ストローク            出力                  │
    │                                                                         │
    │       'j'         +           'k'          =        '日'                │
    │       ↓                        ↓                    ↓                   │
    │   (select row)           (select column)      (kanji output)           │
    │   （行を選択）             （列を選択）          （漢字出力）             │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘

Think of it like a coordinate system:
座標システムのように考える:

    - First stroke = row (which group of kanji)
      第1ストローク = 行（どの漢字グループか）
    - Second stroke = column (which kanji in that group)
      第2ストローク = 列（そのグループのどの漢字か）

================================================================================
LAYOUT FILES / レイアウトファイル
================================================================================

The key-to-kanji mappings are defined in layout files (JSON format).
Different layouts exist with different philosophies:

キーから漢字へのマッピングはレイアウトファイル（JSON形式）で定義される。
異なる哲学を持つ異なるレイアウトが存在する:

    - aki_code.json   : AKI Code layout
    - murenso.json    : Classic murenso layout
    - (custom)        : User-defined layouts

The layout is a nested dictionary:
レイアウトはネストされた辞書:

    {
      "j": {           // First stroke 'j'
        "k": "日",     // j + k = 日
        "l": "月",     // j + l = 月
        "i": "火",     // j + i = 火
        ...
      },
      "a": {           // First stroke 'a'
        "s": "本",     // a + s = 本
        ...
      },
      ...
    }

================================================================================
STATE MACHINE / 状態マシン
================================================================================

    ┌──────────────────┐                    ┌──────────────────┐
    │                  │   valid 1st key    │                  │
    │      IDLE        │ ─────────────────► │   WAITING FOR    │
    │    (待機中)       │                    │   2ND STROKE     │
    │                  │                    │ (第2ストローク待機) │
    └──────────────────┘                    └────────┬─────────┘
            ▲                                        │
            │                                        │
            │         valid 2nd key                  │
            │    ◄───────────────────────────────────┘
            │         → output kanji
            │
            │         invalid 2nd key
            │    ◄───────────────────────────────────┘
                      → return 1st key, reset

================================================================================
INTEGRATION WITH PSKK / PSKKとの統合
================================================================================

In PSKK, kanchoku works alongside normal kana-kanji conversion:
PSKKでは、漢直は通常のかな漢字変換と並行して動作する:

    - Users can switch between modes
      ユーザーはモードを切り替えられる
    - Kanchoku output can be mixed with converted text
      漢直出力は変換されたテキストと混在できる
    - Bunsetsu markers can trigger kanchoku sequences
      文節マーカーが漢直シーケンスをトリガーできる

================================================================================
"""

import logging

logger = logging.getLogger(__name__)

# Placeholder character when a key combination has no assigned kanji.
# This character (無 = "nothing/none") is displayed when a key combination
# exists in the layout but has no kanji assigned, serving as visual feedback.
# キーの組み合わせに漢字が割り当てられていない時のプレースホルダー文字。
# この文字（無 = "nothing/none"）は、キーの組み合わせがレイアウトに存在するが
# 漢字が割り当てられていない場合に表示され、視覚的フィードバックとして機能する。
MISSING_KANCHOKU_KANJI = "無"


class KanchokuProcessor:
    """
    Processor for kanchoku (漢直) two-stroke direct kanji input.
    漢直（2ストローク直接漢字入力）プロセッサ。

    ============================================================================
    OVERVIEW / 概要
    ============================================================================

    This class manages the state machine for two-stroke kanchoku input.
    It tracks whether we're waiting for a first or second stroke, and
    performs the lookup to convert key combinations to kanji.

    このクラスは2ストローク漢直入力の状態マシンを管理する。
    第1ストロークか第2ストロークを待っているかを追跡し、
    キーの組み合わせを漢字に変換するルックアップを実行する。

    ============================================================================
    TERMINOLOGY / 用語
    ============================================================================

    - Kanchoku (漢直): Direct kanji input without phonetic conversion
      漢直: 音声変換なしの直接漢字入力

    - Murenso (無連想): "No association" - another name for kanchoku
      無連想: 漢直の別名

    - Stroke (ストローク): A single key press in the sequence
      ストローク: シーケンス内の1回のキー押下

    - Layout (レイアウト): The mapping of key combinations to kanji
      レイアウト: キーの組み合わせから漢字へのマッピング

    ============================================================================
    USAGE EXAMPLE / 使用例
    ============================================================================

        >>> processor = KanchokuProcessor(layout_data)
        >>>
        >>> # First stroke - stores key, waits for second
        >>> # 第1ストローク - キーを保存し、第2を待つ
        >>> output, pending, consumed = processor.process_key('j', True)
        >>> print(output, pending, consumed)
        None 'j' True
        >>>
        >>> # Second stroke - outputs kanji
        >>> # 第2ストローク - 漢字を出力
        >>> output, pending, consumed = processor.process_key('k', True)
        >>> print(output, pending, consumed)
        '日' None True

    ============================================================================
    ATTRIBUTES / 属性
    ============================================================================

    layout : dict
        Nested dictionary mapping first_key -> second_key -> kanji.
        第1キー -> 第2キー -> 漢字 のネストされた辞書。

    _first_stroke : str or None
        The pending first stroke, or None if idle.
        待機中の第1ストローク、待機中でなければNone。

    ============================================================================
    """

    def __init__(self, kanchoku_layout):
        """
        Initialize the processor with kanchoku layout data.
        漢直レイアウトデータでプロセッサを初期化。

        Args:
            kanchoku_layout: Nested dictionary mapping first_key -> second_key -> kanji.
                             第1キー -> 第2キー -> 漢字 のネストされた辞書。
                             Structure / 構造: {'j': {'k': '日', 'l': '月', ...}, ...}
                             If None or empty, kanchoku will be effectively disabled.
                             Noneまたは空の場合、漢直は実質的に無効になる。
        """
        self.layout = kanchoku_layout if kanchoku_layout else {}
        self._first_stroke = None
        self._reset()

    def _reset(self):
        """
        Reset the processor state, clearing any pending first stroke.
        プロセッサの状態をリセットし、待機中の第1ストロークをクリア。

        Called after successful kanji output or when cancelling a sequence.
        漢字出力成功後、またはシーケンスをキャンセルする時に呼ばれる。
        """
        self._first_stroke = None

    def is_waiting_for_second_stroke(self):
        """
        Check if the processor is waiting for a second stroke.
        プロセッサが第2ストロークを待っているかチェック。

        This is useful for the engine to know whether to show a visual
        indicator that a kanchoku sequence is in progress.
        これは漢直シーケンスが進行中であることを視覚的に示すかどうか
        エンジンが判断するのに便利。

        Returns:
            bool: True if a first stroke has been entered and we're waiting
                  for the second stroke to complete the kanji input.
                  第1ストロークが入力され、漢字入力を完了するための
                  第2ストロークを待っている場合True。
        """
        return self._first_stroke is not None

    def get_first_stroke(self):
        """
        Get the current first stroke if one is pending.
        待機中の第1ストロークがあれば取得。

        Useful for displaying the pending stroke in the preedit area,
        so users know what they've typed so far.
        プリエディットエリアに待機中のストロークを表示するのに便利で、
        ユーザーがここまで何を入力したかわかるようになる。

        Returns:
            str or None: The first stroke character, or None if not waiting.
                         第1ストローク文字、待機中でなければNone。
        """
        return self._first_stroke

    def process_key(self, key_char, is_pressed):
        """
        Process a key input for kanchoku conversion.
        漢直変換のためにキー入力を処理。

        This is the main entry point for the state machine. It handles:
        これは状態マシンのメインエントリーポイント。以下を処理:

            STATE: IDLE → Key valid as first stroke?
            状態: 待機中 → キーが第1ストロークとして有効か？
                YES: Store key, return pending, move to WAITING
                     キーを保存、待機中を返す、待機状態へ移行
                NO:  Return not consumed
                     消費されていないを返す

            STATE: WAITING → Key valid as second stroke?
            状態: 待機中 → キーが第2ストロークとして有効か？
                YES: Look up kanji, output it, return to IDLE
                     漢字をルックアップ、出力、待機中に戻る
                NO:  Return first stroke (as if user typed it), return to IDLE
                     第1ストロークを返す（ユーザーが入力したかのように）、待機中に戻る

        Args:
            key_char: The input character (single lowercase letter or punctuation).
                      入力文字（単一の小文字またはパンクチュエーション）。
            is_pressed: True if key press, False if key release.
                        キー押下ならTrue、キーリリースならFalse。

        Returns:
            tuple: (output, pending, consumed)
                - output: The kanji if second stroke completes, else None.
                          第2ストロークが完了したら漢字、それ以外はNone。
                - pending: The first stroke if waiting, else None.
                           待機中なら第1ストローク、それ以外はNone。
                - consumed: True if this key was consumed by the processor.
                            このキーがプロセッサに消費されたならTrue。
        """
        # Only process key presses, not releases
        if not is_pressed:
            return None, self._first_stroke, False

        if self._first_stroke is None:
            # === FIRST STROKE ===
            # Check if this key is valid as a first stroke
            if key_char not in self.layout:
                # Key not in kanchoku layout as first stroke
                return None, None, False

            # Store as first stroke
            self._first_stroke = key_char
            logger.debug(f'Kanchoku: first stroke "{key_char}"')
            return None, key_char, True

        # === SECOND STROKE ===
        first = self._first_stroke
        second = key_char

        # Check if this key is valid as a second stroke for the current first stroke
        if first not in self.layout or second not in self.layout[first]:
            # Invalid second stroke - return the first stroke and don't consume
            self._reset()
            return first, None, False

        # Valid second stroke - look up the kanji
        kanji = self._lookup_kanji(first, second)
        logger.debug(f'Kanchoku: "{first}" + "{second}" -> "{kanji}"')

        self._reset()
        return kanji, None, True

    def _lookup_kanji(self, first_key, second_key):
        """
        Look up a kanji character from the layout.
        レイアウトから漢字文字をルックアップ。

        Performs a two-level dictionary lookup to find the kanji for
        a given key combination.
        指定されたキーの組み合わせに対する漢字を見つけるために
        2レベルの辞書ルックアップを実行。

        Args:
            first_key: The first stroke character.
                       第1ストローク文字。
            second_key: The second stroke character.
                        第2ストローク文字。

        Returns:
            str: The kanji character, or MISSING_KANCHOKU_KANJI ("無") if not found.
                 漢字文字、見つからない場合はMISSING_KANCHOKU_KANJI（"無"）。
        """
        if first_key not in self.layout:
            return MISSING_KANCHOKU_KANJI

        row = self.layout[first_key]
        if second_key not in row:
            return MISSING_KANCHOKU_KANJI

        kanji = row[second_key]
        if not kanji or kanji == "":
            return MISSING_KANCHOKU_KANJI

        return kanji

    def cancel(self):
        """
        Cancel the current kanchoku sequence and return any pending stroke.
        現在の漢直シーケンスをキャンセルし、待機中のストロークを返す。

        This is useful when the user wants to abort a kanchoku input,
        for example by pressing Escape or switching modes. The pending
        first stroke is returned so it can be handled (e.g., inserted
        as literal text or discarded).
        これはユーザーが漢直入力を中止したい時に便利で、例えばEscapeを押したり
        モードを切り替えたりする時。待機中の第1ストロークが返されるので、
        それを処理できる（例えば、リテラルテキストとして挿入するか破棄する）。

        Returns:
            str or None: The pending first stroke character, or None if none pending.
                         待機中の第1ストローク文字、待機中でなければNone。
        """
        first = self._first_stroke
        self._reset()
        return first

    def get_valid_keys(self):
        """
        Get the set of valid first-stroke keys.
        有効な第1ストロークキーのセットを取得。

        This can be used to check if a key could potentially start
        a kanchoku sequence, useful for the engine's decision-making.
        これはキーが漢直シーケンスを開始できる可能性があるかチェックするのに
        使用でき、エンジンの意思決定に便利。

        Returns:
            set: Set of characters that can be used as first strokes.
                 第1ストロークとして使用できる文字のセット。
        """
        return set(self.layout.keys())

    def get_second_stroke_keys(self, first_stroke):
        """
        Get the set of valid second-stroke keys for a given first stroke.
        指定された第1ストロークに対する有効な第2ストロークキーのセットを取得。

        This can be used to show visual feedback (e.g., highlight valid keys
        on an on-screen keyboard) after the first stroke is entered.
        これは第1ストロークが入力された後に視覚的フィードバックを表示するのに
        使用できる（例えば、画面上のキーボードで有効なキーをハイライト）。

        Args:
            first_stroke: The first stroke character.
                          第1ストローク文字。

        Returns:
            set: Set of characters that can be used as second strokes,
                 or empty set if first_stroke is invalid.
                 第2ストロークとして使用できる文字のセット、
                 first_strokeが無効な場合は空のセット。
        """
        if first_stroke not in self.layout:
            return set()
        return set(self.layout[first_stroke].keys())
