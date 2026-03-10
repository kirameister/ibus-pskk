#!/usr/bin/env python3
"""
simultaneous_processor.py - Processor for simultaneous key input detection
同時打鍵入力検出プロセッサ

================================================================================
OVERVIEW / 概要
================================================================================

This module handles "simultaneous input" (同時打鍵) - a Japanese input method
technique where two keys pressed together within a short time window produce
a different output than if typed sequentially.

このモジュールは「同時打鍵」を処理する。これは短い時間窓内に2つのキーを
同時に押すと、順次入力した場合とは異なる出力を生成する日本語入力技法。

================================================================================
WHAT IS SIMULTANEOUS INPUT? / 同時打鍵とは？
================================================================================

Traditional romaji input requires typing characters in sequence:
伝統的なローマ字入力は文字を順に入力する必要がある:

    "k" → (pending "k") → "a" → "か"

Simultaneous input allows pressing keys at nearly the same time:
同時打鍵ではほぼ同時にキーを押せる:

    "j" + "k" (within 50ms) → "か"

This is faster and more ergonomic because:
これは高速で人間工学的である理由:

• Reduces total keystrokes / 総キーストローク数の削減
• Allows chording (like playing piano) / コード入力が可能（ピアノ演奏のように）
• Better utilizes both hands / 両手をより活用

================================================================================
HOW IT WORKS / 動作原理
================================================================================

The processor maintains a "pending" buffer and tracks keystroke timestamps:
プロセッサは「保留」バッファを維持し、キーストロークのタイムスタンプを追跡:

    Time →  0ms        30ms       80ms
            ↓          ↓          ↓
    Keys:   j↓         k↓         k↑,j↑
            │          │
            │          └─ "jk" within 50ms → simultaneous!
            └─ pending="j"

LOOKUP STRATEGY / ルックアップ戦略:
───────────────────────────────────
When a new key arrives, the processor tries to match:
新しいキーが到着すると、プロセッサは以下を順に試す:

1. Longest possible combination (past_pending + input_char)
   最長の可能な組み合わせ
2. If no match or timed out, try shorter combinations
   マッチなしまたはタイムアウトの場合、より短い組み合わせを試す
3. Fall back to single character if nothing else matches
   他に何もマッチしない場合、単一文字にフォールバック

================================================================================
LAYOUT DATA FORMAT / レイアウトデータ形式
================================================================================

The layout data is a list of entries, each being a list:
レイアウトデータはエントリのリスト、各エントリもリスト:

    [input_str, output_str, pending_str]           # Regular romaji
    [input_str, output_str, pending_str, time_ms]  # Simultaneous input

Examples / 例:
    ["k", "", "k"]           # "k" alone → pending "k"
    ["ka", "か", ""]          # "ka" → output "か", clear pending
    ["jk", "か", "", 50]      # "jk" within 50ms → output "か" (simultaneous)

================================================================================
DATA STRUCTURE / データ構造
================================================================================

The simultaneous_map is organized by input length for O(1) lookup:
simultaneous_map は O(1) ルックアップのために入力長で整理:

    simultaneous_map[0] = {"a": {...}, "k": {...}}   # length-1 entries
    simultaneous_map[1] = {"ka": {...}, "jk": {...}} # length-2 entries
    simultaneous_map[2] = {"kya": {...}}             # length-3 entries

Each entry contains:
各エントリには以下が含まれる:

    {
        "output": str,           # Characters to output / 出力する文字
        "pending": str,          # New pending buffer / 新しい保留バッファ
        "simul_limit_ms": int    # Time window in ms (None for regular romaji)
                                 # 時間窓（ミリ秒、通常ローマ字はNone）
    }

================================================================================
"""

import logging
import time

logger = logging.getLogger(__name__)


class SimultaneousInputProcessor:
    """
    Processor for detecting and handling simultaneous key input.
    同時打鍵入力を検出・処理するプロセッサ

    ─────────────────────────────────────────────────────────────────────────────
    RESPONSIBILITIES / 責務
    ─────────────────────────────────────────────────────────────────────────────
    1. Parse layout data and build efficient lookup structures
       レイアウトデータを解析し、効率的なルックアップ構造を構築
    2. Track timing between keystrokes
       キーストローク間のタイミングを追跡
    3. Determine if key combinations should be treated as simultaneous
       キーの組み合わせを同時入力として扱うべきか判定
    4. Return appropriate output and pending strings
       適切な出力と保留文字列を返す

    ─────────────────────────────────────────────────────────────────────────────
    USAGE / 使用方法
    ─────────────────────────────────────────────────────────────────────────────
    processor = SimultaneousInputProcessor(layout_data)

    # On each key event:
    output, pending = processor.get_layout_output(past_pending, char, is_pressed)

    # output: Characters to display (may include dropped prefix)
    #         表示する文字（ドロップされた接頭辞を含む場合あり）
    # pending: Buffer for next lookup (e.g., "k" waiting for "a")
    #          次回ルックアップ用のバッファ（例: "a"を待つ"k"）

    ─────────────────────────────────────────────────────────────────────────────
    INSTANCE VARIABLES / インスタンス変数
    ─────────────────────────────────────────────────────────────────────────────
    • layout_data: Raw layout configuration / 生のレイアウト設定
    • simultaneous_map: List of dicts indexed by input length
                        入力長でインデックスされた辞書のリスト
    • max_simul_limit_ms: Maximum time window across all entries
                          全エントリ中の最大時間窓
    • previous_typed_timestamp: Timestamp of last keystroke (for timing)
                                最後のキーストロークのタイムスタンプ
    """

    def __init__(self, layout_data):
        """
        Initialize the processor with layout data.
        レイアウトデータでプロセッサを初期化

        Args:
            layout_data: List of layout entries from JSON file.
                         Each entry: [input, output, pending] or
                                     [input, output, pending, time_ms]
                         JSONファイルからのレイアウトエントリのリスト
                         各エントリ: [入力, 出力, 保留] または
                                    [入力, 出力, 保留, 時間ms]

        Note / 注意:
            The timestamp is initialized with a large backward offset so
            the first keystroke won't be incorrectly treated as part of
            a simultaneous combination.

            タイムスタンプは大きな負のオフセットで初期化される。これにより
            最初のキーストロークが誤って同時入力の一部として扱われない。
        """
        self.layout_data = layout_data # this is raw-loaded data
        self.max_simul_limit_ms = 0 # this is to identify the max limit of simul-typing -- passed this limit, there is no simul-typing

        self._build_simultaneous_map()
        # Initialize timestamp with offset so first keystroke won't be treated as simultaneous
        self.previous_typed_timestamp = time.perf_counter() - (self.max_simul_limit_ms * 1000)

    def _build_simultaneous_map(self):
        """
        Build internal mapping for simultaneous input detection.
        同時入力検出用の内部マッピングを構築

        ─────────────────────────────────────────────────────────────────────────
        DATA STRUCTURE DESIGN / データ構造設計
        ─────────────────────────────────────────────────────────────────────────
        Instead of a flat dictionary, we use a list of dictionaries indexed
        by input string length. This enables O(1) lookup when we know the
        exact key length we're searching for.

        フラットな辞書の代わりに、入力文字列長でインデックスされた辞書の
        リストを使用。検索するキー長が分かっている場合、O(1)ルックアップが可能。

        Structure / 構造:
        ─────────────────
            simultaneous_map = [
                {"a": {...}, "k": {...}, ...},     # index 0: length-1 keys
                {"ka": {...}, "jk": {...}, ...},   # index 1: length-2 keys
                {"kya": {...}, ...},               # index 2: length-3 keys
                ...
            ]

        Why this design? / なぜこの設計？
        ─────────────────────────────────
        When processing input, we try keys from longest to shortest:
        入力処理時、最長から最短の順にキーを試す:

        1. "abc" (length 3) → simultaneous_map[2].get("abc")
        2. "bc"  (length 2) → simultaneous_map[1].get("bc")
        3. "c"   (length 1) → simultaneous_map[0].get("c")

        This is faster than iterating through a flat dict filtering by length.
        これは長さでフィルタリングしながらフラット辞書を反復するより高速。

        ─────────────────────────────────────────────────────────────────────────
        ENTRY VALUE FORMAT / エントリ値の形式
        ─────────────────────────────────────────────────────────────────────────
        Each entry value is a dict:
        各エントリ値は辞書:

            {
                "output": "か",        # Characters to emit / 出力する文字
                "pending": "",         # New pending buffer / 新しい保留バッファ
                "simul_limit_ms": 50   # Time window (None=regular romaji)
                                       # 時間窓（None=通常ローマ字）
            }
        """
        if not self.layout_data:
            logger.warning("No layout data provided")
            return

        # First pass: find max input length
        max_input_len = 0
        for l in self.layout_data:
            input_len = len(l[0])
            if input_len > 0:
                max_input_len = max(max_input_len, input_len)

        # Initialize simultaneous_map as list of empty dicts
        self.simultaneous_map = [{} for _ in range(max_input_len)]

        # Second pass: populate the dicts
        for l in self.layout_data:
            input_len = len(l[0])
            input_str = l[0]
            if input_len == 0:
                logger.warning('input str len == 0 detected; skipping..')
                continue
            list_values = dict()
            list_values["output"] = str(l[1])
            list_values["pending"] = str(l[2])
            if len(l) == 4 and type(l[3]) == int:  # this entry is about simultaneous input
                self.max_simul_limit_ms = max(l[3], self.max_simul_limit_ms)
                list_values["simul_limit_ms"] = l[3]
            else:
                list_values["simul_limit_ms"] = None # None value in this case means that the layout has nothing to do with simul-typing; it works like normal romaji input
            self.simultaneous_map[input_len - 1][input_str] = list_values

    def simultaneous_reset(self):
        """
        Reset the timing window so next keystroke starts fresh.
        タイミング窓をリセットし、次のキーストロークを新規開始に

        ─────────────────────────────────────────────────────────────────────────
        WHEN TO CALL / 呼び出しタイミング
        ─────────────────────────────────────────────────────────────────────────
        Called on key release events. This ensures that:
        キーリリースイベントで呼ばれる。これにより:

        • The next key press won't be combined with the previous release
          次のキー押下が前のリリースと組み合わされない
        • Each press-release cycle is treated as a distinct input
          各押下-リリースサイクルが個別の入力として扱われる

        Example / 例:
        ─────────────
            j↓ (t=0ms) → j↑ (t=30ms) → [reset] → k↓ (t=100ms)
                                                  └─ NOT combined with "j"
                                                     "j"と組み合わされない
        """
        self.previous_typed_timestamp -= (self.max_simul_limit_ms) * 1000

    def get_layout_output(self, past_pending, input_char, is_pressed):
        """
        Process a keystroke and return output + new pending buffer.
        キーストロークを処理し、出力と新しい保留バッファを返す

        ─────────────────────────────────────────────────────────────────────────
        ALGORITHM OVERVIEW / アルゴリズム概要
        ─────────────────────────────────────────────────────────────────────────

        On key RELEASE / キーリリース時:
        ──────────────────────────────────
        Reset timing window and return past_pending unchanged.
        タイミング窓をリセットし、past_pending を変更せずに返す。

        On key PRESS / キー押下時:
        ───────────────────────────
        Try to match from longest to shortest combination:
        最長から最短の組み合わせを順に試す:

            past_pending = "ab", input_char = "c"

            Step 1: Try "abc" (full: past_pending + input_char)
                    "abc"を試す（全体: past_pending + input_char）
            Step 2: If no match, try "bc" (last 1 char + input)
                    マッチなしなら"bc"を試す（最後の1文字 + 入力）
            Step 3: If no match, try "c" (just input_char)
                    マッチなしなら"c"を試す（input_charのみ）

        ─────────────────────────────────────────────────────────────────────────
        TIMING CHECK / タイミングチェック
        ─────────────────────────────────────────────────────────────────────────
        For simultaneous entries (those with simul_limit_ms):
        同時入力エントリ（simul_limit_msを持つもの）の場合:

            If time_diff_ms < simul_limit_ms:
                → Use this entry (simultaneous match!) / このエントリを使用
            Else:
                → Skip, try shorter key / スキップして短いキーを試す

        Regular romaji entries (simul_limit_ms = None) always match.
        通常ローマ字エントリ（simul_limit_ms = None）は常にマッチ。

        ─────────────────────────────────────────────────────────────────────────
        DROPPED PREFIX / ドロップされた接頭辞
        ─────────────────────────────────────────────────────────────────────────
        When matching a shorter key, we must preserve the unused prefix:
        短いキーにマッチした場合、使用されなかった接頭辞を保持する必要がある:

            past_pending = "ab", input_char = "c"
            Match "c" only → dropped_prefix = "ab"
            Output = "ab" + entry["output"]

        This ensures characters aren't lost when falling back to shorter keys.
        これにより短いキーにフォールバックしても文字が失われない。

        Args:
            past_pending: 前回の保留文字列
            input_char: 新しい入力文字
            is_pressed: キー押下ならTrue、リリースならFalse

        Returns:
            Tuple[str, str]: (output, pending)
            - output: Characters to display (includes any dropped prefix)
                      表示する文字（ドロップされた接頭辞を含む）
            - pending: Buffer for next call (e.g., "k" waiting for "a")
                       次回呼び出し用バッファ（例: "a"を待つ"k"）
        """
        # On key release, reset simultaneous window and return past_pending unchanged
        if not is_pressed:
            self.simultaneous_reset()
            return past_pending, None

        current_time = time.perf_counter()
        time_diff_ms = (current_time - self.previous_typed_timestamp) * 1000

        # ============================================================
        # LOOKUP STRATEGY: Try longest key first, then fall back to shorter keys
        # ============================================================
        #
        # Example: past_pending="ab", input_char="c"
        #   1. Try "abc" (full combination)
        #   2. If no match or timed out, try "bc" (last 1 char of past_pending + input)
        #   3. If still no match, try "c" (just input_char)
        #
        # Why? Simultaneous typing "jk" within 50ms should produce a special output.
        # But if typed slowly (>50ms), we should fall back to processing "k" alone.
        #
        # self.simultaneous_map structure:
        #   - List of dicts, where index i contains entries with key length (i + 1)
        #   - simultaneous_map[0] = {"a": {...}, "b": {...}}  # length-1 keys
        #   - simultaneous_map[1] = {"ab": {...}, "jk": {...}}  # length-2 keys
        #   - simultaneous_map[2] = {"abc": {...}}  # length-3 keys
        # ============================================================

        # Calculate max useful tail length to avoid unnecessary iterations
        # (no point trying keys longer than what the layout supports)
        max_tail_len = min(len(past_pending), len(self.simultaneous_map) - 1)

        # Try keys from longest to shortest
        for tail_len in range(max_tail_len, -1, -1):
            # Build lookup key: take last 'tail_len' chars from past_pending + input_char
            # tail_len=2: "ab"[-2:] + "c" = "abc", dropped_prefix = ""
            # tail_len=1: "ab"[-1:] + "c" = "bc",  dropped_prefix = "a"
            # tail_len=0: "" + "c" = "c",          dropped_prefix = "ab"
            pending_tail = past_pending[-tail_len:] if tail_len > 0 else ""
            lookup_key = pending_tail + input_char

            # The prefix we're NOT using - must be included in output if we match
            dropped_prefix = past_pending[:-tail_len] if tail_len > 0 else past_pending

            # Direct index into the correct bucket based on key length
            key_idx = len(lookup_key) - 1
            entry = self.simultaneous_map[key_idx].get(lookup_key, None)

            if not entry:
                continue  # no match at this length, try shorter

            # Found an entry - check if it's simultaneous or regular romaji
            simul_limit = entry.get("simul_limit_ms", None)

            if simul_limit and simul_limit > 0:
                # This is a SIMULTANEOUS entry - must be typed within time limit
                if time_diff_ms < simul_limit:
                    # Within time window - use this simultaneous combo
                    # Prepend dropped_prefix to output so we don't lose those chars
                    self.previous_typed_timestamp = current_time
                    return dropped_prefix + entry['output'], entry['pending']
                else:
                    # Timed out - don't use this entry, try shorter key
                    continue
            else:
                # This is a REGULAR romaji entry (no timing requirement)
                # Prepend dropped_prefix to output so we don't lose those chars
                self.previous_typed_timestamp = current_time
                return dropped_prefix + entry["output"], entry["pending"]

        # No match found at any length - return everything as output, clear pending
        self.previous_typed_timestamp = current_time
        return past_pending + input_char, None

