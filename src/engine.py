"""
engine.py - Main IBus Engine for ibus-pskk Japanese Input Method
ibus-pskk 日本語入力メソッド用 IBus エンジン本体

================================================================================
OVERVIEW / 概要
================================================================================

This is the main engine module for ibus-pskk, implementing the IBus.Engine
interface. It handles all keyboard input, manages input modes, and coordinates
multiple sub-processors for Japanese text input.

これは ibus-pskk のメインエンジンモジュールで、IBus.Engine インターフェースを
実装する。全てのキーボード入力を処理し、入力モードを管理し、日本語テキスト入力の
ための複数のサブプロセッサを調整する。

================================================================================
INPUT MODES / 入力モード
================================================================================

The engine supports two top-level input modes:
エンジンは2つのトップレベル入力モードをサポートする：

┌─────────────────────────────────────────────────────────────────────────────┐
│  MODE 'A' (Alphanumeric / 英数字モード)                                      │
│  ─────────────────────────────────────                                      │
│  All keystrokes pass through to the application unchanged.                  │
│  全てのキー入力がそのままアプリケーションに渡される。                          │
│                                                                             │
│  Use case: Typing English text, programming, etc.                           │
│  用途：英語テキストの入力、プログラミングなど                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  MODE 'あ' (Hiragana / ひらがなモード)                                       │
│  ─────────────────────────────────────                                      │
│  Keystrokes are processed through the Japanese input pipeline.              │
│  キー入力は日本語入力パイプラインで処理される。                                │
│                                                                             │
│  This mode has multiple internal states (see STATE MACHINE below).          │
│  このモードには複数の内部状態がある（下記のSTATE MACHINEを参照）。             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
STATE MACHINE IN HIRAGANA MODE / ひらがなモード内の状態機械
================================================================================

Within Hiragana mode ('あ'), there are multiple internal states that control
how text is processed and displayed:

ひらがなモード内では、テキストの処理と表示を制御する複数の内部状態がある：

┌─────────────────────────────────────────────────────────────────────────────┐
│                           STATE DIAGRAM / 状態図                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────┐                                                             │
│    │   IDLE   │  ← Initial state / 初期状態                                 │
│    │ (通常入力)│    No special mode active / 特別なモードなし                │
│    └────┬─────┘                                                             │
│         │                                                                   │
│         │ space+key                                                         │
│         ▼                                                                   │
│    ┌──────────┐    space tap    ┌────────────┐                             │
│    │ BUNSETSU │ ──────────────► │ CONVERTING │                             │
│    │ (文節入力)│                 │  (変換中)   │                             │
│    └────┬─────┘ ◄────────────── └─────┬──────┘                             │
│         │        ESC/Backspace        │ Enter/continue typing               │
│         │                             │ Enter/続けて入力                     │
│         │ space+key                   ▼                                     │
│         │                        [Commit text]                              │
│         ▼                        [テキスト確定]                              │
│    ┌──────────┐                                                             │
│    │  FORCED  │  ← For kanchoku+kana combinations                           │
│    │ PREEDIT  │    漢直＋かな組み合わせ用                                    │
│    │(強制入力)│                                                             │
│    └──────────┘                                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

STATE DESCRIPTIONS / 状態の説明:
────────────────────────────────

1. IDLE STATE (通常入力状態)
   ─────────────────────────
   - _bunsetsu_active = False
   - _in_conversion = False
   - _in_forced_preedit = False

   In this state, typed characters appear as hiragana but are NOT marked
   for kana-kanji conversion. The preedit is displayed with minimal styling
   (stealth mode) to appear as if already committed.

   この状態では、入力した文字はひらがなとして表示されるが、かな漢字変換の
   対象としてマークされない。プリエディットは最小限のスタイルで表示され
   （ステルスモード）、既に確定したかのように見える。

   Transitions / 遷移:
   - space+key → BUNSETSU (marks boundary and activates bunsetsu mode)
                 文節境界をマークして文節モードに入る
   - Enter → Commit preedit, stay in IDLE
             プリエディットを確定、IDLEのまま

2. BUNSETSU STATE (文節入力状態)
   ──────────────────────────────
   - _bunsetsu_active = True
   - _in_conversion = False

   Bunsetsu (文節) means "phrase unit" in Japanese. In this state, the
   preedit is marked as a candidate for kana-kanji conversion. Visual
   styling (underline) indicates the text is pending conversion.

   文節とは日本語の句単位を意味する。この状態では、プリエディットがかな漢字
   変換の候補としてマークされる。視覚的なスタイル（下線）がテキストが変換
   待ちであることを示す。

   Transitions / 遷移:
   - space (tap) → CONVERTING (triggers dictionary lookup)
                   辞書検索を実行して変換状態へ
   - space+key → Implicit conversion + new bunsetsu
                 暗黙変換＋新しい文節開始
   - Enter → Commit preedit as-is, return to IDLE
             プリエディットをそのまま確定、IDLEへ戻る

3. CONVERTING STATE (変換中状態)
   ─────────────────────────────
   - _in_conversion = True

   Conversion candidates are displayed in a lookup table. User can cycle
   through candidates with space or arrow keys.

   変換候補がルックアップテーブルに表示される。ユーザーはスペースまたは
   矢印キーで候補を切り替えられる。

   Transitions / 遷移:
   - space (tap) → Cycle to next candidate / 次の候補へ
   - Enter/typing → Confirm candidate, return to IDLE or continue
                    候補を確定、IDLEへ戻るか続けて入力
   - ESC/Backspace → Cancel, return to BUNSETSU with original yomi
                     キャンセル、元の読みでBUNSETSUへ戻る

4. FORCED PREEDIT STATE (強制プリエディット状態)
   ─────────────────────────────────────────────
   - _in_forced_preedit = True

   A special mode that allows combining kanchoku kanji with hiragana in
   the same preedit for conversion. This is useful when the user wants
   to type a word that contains kanji produceable by kanchoku.

   漢直漢字とひらがなを同じプリエディット内で組み合わせて変換できる特殊
   モード。漢直で入力可能な漢字を含む単語を入力したい場合に便利。

   Example use case / 使用例:
   - User wants to type "企業" (きぎょう)
     ユーザーが「企業」を入力したい
   - In forced preedit, user types kanchoku for "企" then kana for "ぎょう"
     強制プリエディットで「企」を漢直、「ぎょう」をかなで入力
   - Result: "企ぎょう" can be converted to "企業"
     結果：「企ぎょう」を「企業」に変換可能

================================================================================
MARKER KEY STATE MACHINE / マーカーキー状態機械
================================================================================

The marker key (typically Space) enables three different behaviors depending
on the subsequent key sequence. This is controlled by a separate state machine:

マーカーキー（通常はスペース）は、後続のキーシーケンスに応じて3つの異なる
動作を可能にする。これは独立した状態機械で制御される：

┌─────────────────────────────────────────────────────────────────────────────┐
│                    MarkerState Transitions / 遷移図                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  IDLE ──(space↓)──► MARKER_HELD ──(key1↓)──► FIRST_PRESSED                 │
│    ▲                     │                         │                        │
│    │                     │ (space↑ with no input)  │ (key1↑)                │
│    │                     ▼                         ▼                        │
│    │              [Space tap action]         FIRST_RELEASED                 │
│    │              - IDLE: commit+space       /          \                   │
│    │              - BUNSETSU: convert       /            \                  │
│    │              - CONVERTING: cycle      /              \                 │
│    │                                      /                \                │
│    │                            (key2↓)  /                  \ (space↑)      │
│    │                                    ▼                    ▼              │
│    │                        KANCHOKU_SECOND_PRESSED    [Decision]           │
│    │                               │                    - Bunsetsu mode     │
│    │                               │ (keys↑, space↑)   - Forced preedit    │
│    └───────────────────────────────┴─────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

THREE MARKER KEY BEHAVIORS / マーカーキーの3つの動作:
────────────────────────────────────────────────────────

1. KANCHOKU (漢直 - Direct Kanji Input)
   Sequence: space↓ → key1↓↑ → key2↓↑ → space↑
   Result: Kanji is looked up from (key1, key2) and output
   シーケンス：space↓ → key1↓↑ → key2↓↑ → space↑
   結果：(key1, key2) から漢字を検索して出力

2. BUNSETSU (文節 - Phrase Boundary)
   Sequence: space↓ → key1↓↑ → space↑
   Condition: key1 can start a bunsetsu (normal characters)
   Result: Mark bunsetsu boundary, key1 becomes start of new bunsetsu
   シーケンス：space↓ → key1↓↑ → space↑
   条件：key1 が文節を開始できる（通常の文字）
   結果：文節境界をマーク、key1 が新しい文節の開始になる

3. FORCED PREEDIT (強制プリエディット)
   Sequence: space↓ → trigger_key↓↑ → space↑
   Condition: key1 is the forced_preedit_trigger_key (default: 'f')
   Result: Enter forced preedit mode for kanchoku+kana mixing
   シーケンス：space↓ → trigger_key↓↑ → space↑
   条件：key1 が forced_preedit_trigger_key（デフォルト：'f'）
   結果：漢直＋かな混在用の強制プリエディットモードに入る

================================================================================
PREEDIT BUFFERS / プリエディットバッファ
================================================================================

The engine maintains three synchronized buffers for the preedit:
エンジンはプリエディット用に3つの同期されたバッファを維持する：

┌─────────────────────────────────────────────────────────────────────────────┐
│  _preedit_string   : Display buffer (what user sees)                        │
│                      表示バッファ（ユーザーに見えるもの）                      │
│                      Can be: hiragana, katakana, kanji, ASCII, zenkaku      │
│                      内容：ひらがな、カタカナ、漢字、ASCII、全角              │
├─────────────────────────────────────────────────────────────────────────────┤
│  _preedit_hiragana : Source for to_katakana / to_hiragana conversions       │
│                      カタカナ/ひらがな変換用のソース                          │
│                      Always hiragana (kanchoku kanji NOT included)          │
│                      常にひらがな（漢直漢字は含まない）                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  _preedit_ascii    : Source for to_ascii / to_zenkaku conversions           │
│                      ASCII/全角変換用のソース                                 │
│                      Raw ASCII keystrokes                                   │
│                      生のASCIIキーストローク                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Design Note / 設計上の注意:
In forced preedit mode, kanchoku kanji exist ONLY in _preedit_string.
Converting to katakana/ASCII will lose kanchoku kanji - this is by design.

強制プリエディットモードでは、漢直漢字は _preedit_string にのみ存在する。
カタカナ/ASCIIへの変換で漢直漢字は失われる - これは意図的な設計。

================================================================================
KEY PROCESSING PIPELINE / キー処理パイプライン
================================================================================

When a key event arrives, it flows through this pipeline:
キーイベントが到着すると、このパイプラインを通る：

  do_process_key_event()
         │
         ├─► Check enable_hiragana_key (mode toggle) / モード切替キー確認
         │
         ├─► If mode 'A': pass through / 英数モードならパススルー
         │
         └─► _process_key_event()
                   │
                   ├─► Kanchoku/Bunsetsu marker handling / 漢直/文節マーカー処理
                   │   (highest priority / 最優先)
                   │
                   ├─► Config-driven key bindings / 設定キーバインディング
                   │   (conversions, editor launch, etc.)
                   │   （変換、エディタ起動など）
                   │
                   ├─► Combo keys (Ctrl+X, etc.) → pass through
                   │   コンボキー → パススルー
                   │
                   ├─► Special keys (Enter, Backspace, ESC, arrows)
                   │   特殊キー（Enter、Backspace、ESC、矢印）
                   │
                   └─► Regular character input → SimultaneousInputProcessor
                       通常の文字入力 → 同時打鍵プロセッサ

================================================================================
SUB-PROCESSORS / サブプロセッサ
================================================================================

The engine delegates specific tasks to specialized processors:
エンジンは特定のタスクを専門のプロセッサに委譲する：

1. SimultaneousInputProcessor (simultaneous_processor.py)
   ───────────────────────────────────────────────────────
   Converts raw keystrokes to hiragana using the layout table.
   Supports simultaneous key input (e.g., 'k'+'a' pressed together → 'か').

   生のキーストロークをレイアウトテーブルを使ってひらがなに変換。
   同時打鍵入力をサポート（例：'k'+'a'同時押し→'か'）。

2. KanchokuProcessor (kanchoku.py)
   ────────────────────────────────
   Handles direct kanji input via two-key combinations.
   Example: space+j+k → '漢'

   2キーの組み合わせによる直接漢字入力を処理。
   例：space+j+k→'漢'

3. HenkanProcessor (henkan.py)
   ───────────────────────────
   Handles kana-kanji conversion using dictionary lookup.
   Supports bunsetsu-based conversion with CRF boundary prediction.

   辞書検索を使ったかな漢字変換を処理。
   CRF境界予測による文節単位の変換をサポート。

================================================================================
REFERENCES / 参考資料
================================================================================

IBus documentation:
http://lazka.github.io/pgi-docs/IBus-1.0/index.html

GTK documentation:
http://lazka.github.io/pgi-docs/Gtk-4.0/index.html

GLib documentation:
http://lazka.github.io/pgi-docs/GLib-2.0/index.html

================================================================================
"""

import util
import settings_panel
import conversion_model
import user_dictionary_editor
from simultaneous_processor import SimultaneousInputProcessor
from kanchoku import KanchokuProcessor
from henkan import HenkanProcessor

from enum import IntEnum
import json
import logging
import os
import queue

import gi
gi.require_version('IBus', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, IBus, GLib

logger = logging.getLogger(__name__)

APPLICABLE_STROKE_SET_FOR_JAPANESE = set(list('1234567890qwertyuiopasdfghjk;lzxcvbnm,./'))

KANCHOKU_KEY_SET = set(list('qwertyuiopasdfghjkl;zxcvbnm,./'))
MISSING_KANCHOKU_KANJI = '無'

# modifier mask-bit segment
STATUS_SPACE        = 0x001
#STATUS_SHIFT_L      = 0x002 # this value is currently not meant to be used directly
#STATUS_SHIFT_R      = 0x004 # this value is currently not meant to be used directly
#STATUS_CONTROL_L    = 0x008
#STATUS_CONTROL_R    = 0x010
#STATUS_ALT_L        = 0x020
#STATUS_ALT_R        = 0x040
#STATUS_SUPER_L      = 0x080
#STATUS_SUPER_R      = 0x100
#STATUS_SHIFTS       = STATUS_SHIFT_L | STATUS_SHIFT_R
#STATUS_CONTROLS     = STATUS_CONTROL_L | STATUS_CONTROL_R
#STATUS_ALTS         = STATUS_ALT_L | STATUS_ALT_R
#STATUS_SUPERS       = STATUS_SUPER_L | STATUS_SUPER_R
#STATUS_MODIFIER     = STATUS_SHIFTS  | STATUS_CONTROLS | STATUS_ALTS | STATUS_SPACE | STATUS_SUPERS

# =============================================================================
# CHARACTER CONVERSION TABLES
# =============================================================================

# Hiragana characters (ぁ to ゖ)
HIRAGANA_CHARS = (
    'ぁあぃいぅうぇえぉお'
    'かがきぎくぐけげこご'
    'さざしじすずせぜそぞ'
    'ただちぢっつづてでとど'
    'なにぬねの'
    'はばぱひびぴふぶぷへべぺほぼぽ'
    'まみむめも'
    'ゃやゅゆょよ'
    'らりるれろ'
    'ゎわゐゑをん'
    'ゔゕゖ'
)

# Katakana characters (ァ to ヶ) - same order as hiragana
KATAKANA_CHARS = (
    'ァアィイゥウェエォオ'
    'カガキギクグケゲコゴ'
    'サザシジスズセゼソゾ'
    'タダチヂッツヅテデトド'
    'ナニヌネノ'
    'ハバパヒビピフブプヘベペホボポ'
    'マミムメモ'
    'ャヤュユョヨ'
    'ラリルレロ'
    'ヮワヰヱヲン'
    'ヴヵヶ'
)

# Half-width ASCII (printable: space to tilde)
ASCII_HALFWIDTH = (
    ' !"#$%&\'()*+,-./'
    '0123456789'
    ':;<=>?@'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '[\\]^_`'
    'abcdefghijklmnopqrstuvwxyz'
    '{|}~'
)

# Full-width ASCII (Zenkaku) - same order as half-width
ASCII_FULLWIDTH = (
    '　！"＃＄％＆＇（）＊＋，－．／'
    '０１２３４５６７８９'
    '：；＜＝＞？＠'
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
    '［＼］＾＿｀'
    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    '｛｜｝～'
)

# Translation tables
HIRAGANA_TO_KATAKANA = str.maketrans(HIRAGANA_CHARS, KATAKANA_CHARS)
KATAKANA_TO_HIRAGANA = str.maketrans(KATAKANA_CHARS, HIRAGANA_CHARS)
ASCII_TO_FULLWIDTH = str.maketrans(ASCII_HALFWIDTH, ASCII_FULLWIDTH)
FULLWIDTH_TO_ASCII = str.maketrans(ASCII_FULLWIDTH, ASCII_HALFWIDTH)

NAME_TO_LOGGING_LEVEL = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


# =============================================================================
# KANCHOKU / BUNSETSU STATE MACHINE
# =============================================================================

class MarkerState(IntEnum):
    """
    State machine for kanchoku_bunsetsu_marker key sequences.

    The marker key (e.g., Space) enables three different behaviors:
    - Kanchoku: marker held → key1↓↑ → key2↓↑ → kanji output
    - Bunsetsu: marker held → key1↓↑ → marker↑ → bunsetsu boundary (if key1 can start bunsetsu)
    - Forced preedit: marker held → key1↓↑ → marker↑ → enter forced preedit (if key1 is "ん" etc.)
    """
    IDLE = 0                    # Marker not held
    MARKER_HELD = 1             # Marker pressed, waiting for first key
    FIRST_PRESSED = 2           # First key pressed (not yet released)
    FIRST_RELEASED = 3          # First key released - decision point:
                                #   key2↓ → kanchoku, marker↑ → bunsetsu/forced-preedit
    KANCHOKU_SECOND_PRESSED = 4 # Second key pressed (kanchoku confirmed)


class EnginePSKK(IBus.Engine):
    '''
    http://lazka.github.io/pgi-docs/IBus-1.0/classes/Engine.html
    '''
    __gtype_name__ = 'EnginePSKK'

    # =========================================================================
    # Initialization-related definitions
    # =========================================================================
    def __init__(self):
        super().__init__()
        # setting the initial input mode
        self._mode = 'A'  # _mode must be one of _input_mode_names
        #self._mode = 'あ'  # DEBUG I do not like to click extra...
        self._override = True
        # loading the layout
        self._layout_data = None  # raw layout JSON data
        self._simul_processor = None  # SimultaneousInputProcessor instance
        self._kanchoku_layout = dict()
        self._kanchoku_valid_first_keys = set()   # Valid first-stroke keys for pure kanchoku
        self._kanchoku_valid_seconds = dict()     # first_key -> set of valid second keys
        # SandS vars
        self._modkey_status = 0 # This is supposed to be bitwise status
        self._typing_mode = 0 # This is to indicate which state the stroke is supposed to be
        self._pressed_key_set = set()
        self._handled_config_keys = set()  # Keys handled by config bindings (to consume releases)
        self._sands_key_set = set()

        # Kanchoku / Bunsetsu state machine variables
        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None           # Raw key char for kanchoku lookup
        self._marker_keys_held = set()          # Track keys currently pressed while marker held
        self._marker_had_input = False          # True if any key was pressed during this marker hold
        self._preedit_before_marker = ''        # Preedit snapshot to restore if kanchoku
        self._in_forced_preedit = False         # True when in forced preedit mode (Case C)

        # Pure kanchoku trigger state (simpler alternative to marker-based kanchoku)
        self._pure_kanchoku_held = False        # True when pure kanchoku trigger key is held
        self._pure_kanchoku_first_key = None    # First key of two-key kanchoku sequence

        # Henkan (kana-kanji conversion) state variables
        self._bunsetsu_active = False           # True when bunsetsu mode is active (yomi input)
        self._in_conversion = False             # True when showing conversion candidates
        self._conversion_yomi = ''              # The yomi string being converted

        self._preedit_string = ''    # Display buffer (can be hiragana, katakana, ascii, or zenkaku)
        self._preedit_hiragana = ''  # Source of truth: hiragana output from simul_processor
        self._preedit_ascii = ''     # Source of truth: raw ASCII input characters
        self._converted = False  # Set True after Ctrl+K/J/L; next char input auto-commits
        self._previous_text = ''

        # This property is for confirming the kanji-kana converted string
        # LookupTable.new(page_size, cursor_pos, cursor_visible, round)
        # round=True enables wrap-around when cycling candidates
        self._lookup_table = IBus.LookupTable.new(10, 0, True, True)
        self._lookup_table.set_orientation(IBus.Orientation.VERTICAL)

        self._init_props()
        #self.register_properties(self._prop_list)

        # load configs
        self._load_configs()
        self._layout_data = util.get_layout_data(self._config)
        self._simul_processor = SimultaneousInputProcessor(self._layout_data)
        self._kanchoku_layout = self._load_kanchoku_layout()
        self._kanchoku_processor = KanchokuProcessor(self._kanchoku_layout)
        # Initialize henkan (kana-kanji conversion) processor with dictionaries
        dictionary_files = util.get_dictionary_files(self._config)
        self._henkan_processor = HenkanProcessor(dictionary_files)

        # Input mode defaults to 'A' (set in self._mode above)

        self._about_dialog = None
        self._settings_panel = None
        self._conversion_model_panel = None
        self._user_dictionary_editor = None
        self._q = queue.Queue()


    def do_focus_in(self):
        self.register_properties(self._prop_list)
        #self._update_preedit()
        # Request the initial surrounding-text in addition to the "enable" handler.
        self.get_surrounding_text()

    def do_focus_out(self):
        """
        Called when input focus leaves the engine.

        Explicitly commit any preedit/candidate before resetting state.
        This handles both normal preedit and conversion mode with lookup table.
        """
        logger.debug(f'do_focus_out: bunsetsu={self._bunsetsu_active}, '
                    f'converting={self._in_conversion}, preedit="{self._preedit_string}"')

        # Explicitly commit preedit if present
        # This is needed because IBus may not auto-commit when lookup table is visible
        if self._preedit_string:
            logger.debug(f'do_focus_out: committing "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))

        # Hide lookup table if visible
        self._lookup_table.clear()
        self.hide_lookup_table()

        # Clear preedit display
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''),
            0,
            False,
            IBus.PreeditFocusMode.CLEAR
        )

        # Reset henkan state
        self._bunsetsu_active = False
        self._in_conversion = False
        self._conversion_yomi = ''
        self._preedit_string = ''
        self._preedit_hiragana = ''
        self._preedit_ascii = ''

        # Reset marker state
        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None
        self._marker_keys_held.clear()
        self._marker_had_input = False

        # Reset pure kanchoku state
        self._pure_kanchoku_held = False
        self._pure_kanchoku_first_key = None


    def _init_props(self):
        '''
        This function is called as part of the instantiation (__init__).
        This function creates the GUI menu list (typically top-right corner).

        http://lazka.github.io/pgi-docs/IBus-1.0/classes/PropList.html
        http://lazka.github.io/pgi-docs/IBus-1.0/classes/Property.html
        '''
        logger.debug('_init_props()')
        self._prop_list = IBus.PropList()
        self._input_mode_prop = IBus.Property(
            key='InputMode',
            prop_type=IBus.PropType.MENU,
            symbol=IBus.Text.new_from_string(self._mode),
            label=IBus.Text.new_from_string(f"Input mode ({self._mode})"),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        # This is to add the options for different modes in separate function
        self._input_mode_prop.set_sub_props(self._init_input_mode_props())
        self._prop_list.append(self._input_mode_prop)
        settings_prop = IBus.Property(
            key='Settings',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("Settings..."),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(settings_prop)
        user_dict_prop = IBus.Property(
            key='UserDictionary',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("User Dictionary Editor..."),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(user_dict_prop)
        conversion_model_prop = IBus.Property(
            key='ConversionModel',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("Conversion Model..."),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(conversion_model_prop)
        prop = IBus.Property(
            key='About',
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("About PSKK..."),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        self._prop_list.append(prop)
        logger.debug('_init_props() -- end')

    def _init_input_mode_props(self):
        '''
        This is a function to produce GUI (sub) component for
        different input modes.
        This function is meant to be only called from _init_props()
        '''
        logger.debug('_init_input_mode_props()')
        props = IBus.PropList()
        self._input_mode_alpha_prop = IBus.Property(
            key='InputMode.Alphanumeric',
            prop_type=IBus.PropType.RADIO,
            label=IBus.Text.new_from_string("Alphanumeric (A)"),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.CHECKED,
            sub_props=None)
        props.append(self._input_mode_alpha_prop)
        self._input_mode_hira_prop = IBus.Property(
            key='InputMode.Hiragana',
            prop_type=IBus.PropType.RADIO,
            label=IBus.Text.new_from_string("Hiragana (あ)"),
            icon=None,
            tooltip=None,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            sub_props=None)
        props.append(self._input_mode_hira_prop)
        logger.debug('_init_input_mode_props() -- end')
        return props

    def _load_kanchoku_layout(self):
        """
        Purpose of this function is to load the kanchoku (漢直) layout
        as form of dict.
        The term "layout" may not be very accurate, but I haven't found
        a better term for this concept yet (people say "漢直配列").

        Returns:
            dict: A nested dictionary mapping first-key -> second-key -> kanji character
                  for all keys in KANCHOKU_KEY_SET

        Side effects:
            Sets self._kanchoku_valid_first_keys (set of keys that are valid first strokes)
            Sets self._kanchoku_valid_seconds (dict: first_key -> set of valid second keys)
        """
        return_dict = dict()

        # Use utility function to load the kanchoku layout JSON data
        kanchoku_layout_data = util.get_kanchoku_layout(self._config)

        if kanchoku_layout_data is None:
            logger.error('Failed to load kanchoku layout data')
            # Initialize empty structure as fallback
            self._kanchoku_valid_first_keys = set()
            self._kanchoku_valid_seconds = dict()
            for first in KANCHOKU_KEY_SET:
                return_dict[first] = dict()
                for second in KANCHOKU_KEY_SET:
                    return_dict[first][second] = MISSING_KANCHOKU_KANJI
            return return_dict

        # Extract valid first keys and their valid second keys from raw JSON data
        # This is used by pure kanchoku trigger to determine pass-through behavior
        self._kanchoku_valid_first_keys = set(kanchoku_layout_data.keys())
        self._kanchoku_valid_seconds = {
            first: set(seconds.keys())
            for first, seconds in kanchoku_layout_data.items()
        }

        # Initialize and populate the layout for all keys in KANCHOKU_KEY_SET
        for first in KANCHOKU_KEY_SET:
            return_dict[first] = dict()
            for second in KANCHOKU_KEY_SET:
                # Use the loaded data if available, otherwise use placeholder
                if first in kanchoku_layout_data and second in kanchoku_layout_data[first]:
                    return_dict[first][second] = kanchoku_layout_data[first][second]
                else:
                    return_dict[first][second] = MISSING_KANCHOKU_KANJI

        return return_dict

    def _load_configs(self):
        '''
        This function loads the necessary (and optional) configs from the config JSON file
        The logging level value would be set to WARNING, if it's absent in the config JSON.
        '''
        self._config = util.get_config_data()[0] # the 2nd element of tuple is list of warning messages
        self._logging_level = self._load_logging_level(self._config)
        logger.debug('config.json loaded')
        # loading layout should be part of (re-)loading config
        self._layout_data = util.get_layout_data(self._config)
        self._simul_processor = SimultaneousInputProcessor(self._layout_data)
        self._kanchoku_layout = self._load_kanchoku_layout()
        self._kanchoku_processor = KanchokuProcessor(self._kanchoku_layout)
        # Reload henkan processor with updated dictionary list
        dictionary_files = util.get_dictionary_files(self._config)
        self._henkan_processor = HenkanProcessor(dictionary_files)

    def _load_logging_level(self, config):
        '''
        This function sets the logging level
        which can be obtained from the config.json
        When the value is not present (or incorrect) in config.json,
        warning is used as default.
        '''
        level = 'WARNING' # default value
        if('logging_level' in config):
            level = config['logging_level']
        if(level not in NAME_TO_LOGGING_LEVEL):
            logger.warning(f'Specified logging level {level} is not recognized. Using the default WARNING level.')
            level = 'WARNING'
        logger.info(f'logging_level: {level}')
        logging.getLogger().setLevel(NAME_TO_LOGGING_LEVEL[level])
        return level
    # =========================================================================
    # End of Initialization-related definitions
    # =========================================================================

    # =========================================================================
    # GUI-related definitions
    # =========================================================================
    def _show_about_dialog(self):
        if self._about_dialog:
          self._about_dialog.present()
          return False  # Don't repeat this idle callback

        dialog = Gtk.AboutDialog()
        dialog.set_program_name("PSKK")
        dialog.set_copyright("Copyright 2021-2026 Akira K.")
        dialog.set_authors(["Akira K."])
        dialog.set_documenters(["Akira K."])
        dialog.set_website("file://" + os.path.join(util.get_datadir(), "help/index.html"))
        dialog.set_website_label("Introduction to PSKK")
        dialog.set_logo_icon_name(util.get_package_name())
        dialog.set_default_icon_name(util.get_package_name())
        dialog.set_version(util.get_version())
        dialog.set_comments("config files location : ${HOME}/.config/ibus-pskk")

        # Make dialog modal and keep it on top
        dialog.set_modal(True)
        dialog.set_keep_above(True)

        dialog.connect("response", self.about_response_callback)
        self._about_dialog = dialog
        dialog.show()

        return False  # Don't repeat this idle callback

    def _show_settings_panel(self):
        if self._settings_panel:
            self._settings_panel.present()
            return False  # Don't repeat this idle callback

        panel = settings_panel.SettingsPanel()
        panel.connect("destroy", self.settings_panel_closed_callback)
        self._settings_panel = panel
        panel.show_all()

        return False  # Don't repeat this idle callback

    def _show_conversion_model_panel(self):
        if self._conversion_model_panel:
            self._conversion_model_panel.present()
            return False  # Don't repeat this idle callback

        panel = conversion_model.ConversionModelPanel()
        panel.connect("destroy", self.conversion_model_panel_closed_callback)
        self._conversion_model_panel = panel
        panel.show_all()

        return False  # Don't repeat this idle callback

    def _show_user_dictionary_editor(self):
        if self._user_dictionary_editor:
            self._user_dictionary_editor.present()
            return False  # Don't repeat this idle callback

        editor = user_dictionary_editor.open_editor()
        editor.connect("destroy", self.user_dictionary_editor_closed_callback)
        self._user_dictionary_editor = editor

        return False  # Don't repeat this idle callback

    def do_property_activate(self, prop_name, state):
        logger.info(f'property_activate({prop_name}, {state})')
        if prop_name == 'Settings':
            # Schedule settings panel creation on the main loop
            GLib.idle_add(self._show_settings_panel)
            return
        elif prop_name == 'UserDictionary':
            # Schedule user dictionary editor creation on the main loop
            GLib.idle_add(self._show_user_dictionary_editor)
            return
        elif prop_name == 'ConversionModel':
            # Schedule conversion model panel creation on the main loop
            GLib.idle_add(self._show_conversion_model_panel)
            return
        elif prop_name == 'About':
            # Schedule dialog creation on the main loop
            GLib.idle_add(self._show_about_dialog)
            return
        elif prop_name.startswith('InputMode.'):
            if state == IBus.PropState.CHECKED:
                # We only support direct input and Hiragana. Nothing else..
                mode = {
                    'InputMode.Alphanumeric': 'A',
                    'InputMode.Hiragana': 'あ',
                }.get(prop_name, 'A')
                self._commit_string()
                self._mode = mode
                self._update_input_mode()


    def about_response_callback(self, dialog, response):
        dialog.destroy()
        self._about_dialog = None

    def settings_panel_closed_callback(self, panel):
        self._settings_panel = None

    def conversion_model_panel_closed_callback(self, panel):
        self._conversion_model_panel = None

    def user_dictionary_editor_closed_callback(self, editor):
        self._user_dictionary_editor = None

    def _update_input_mode(self):
        self._input_mode_prop.set_symbol(IBus.Text.new_from_string(self._mode))
        self._input_mode_prop.set_label(IBus.Text.new_from_string("Input mode (" + self._mode + ")"))
        self.update_property(self._input_mode_prop)
        # Update sub-property radio button states so menu selection reflects current mode
        if self._mode == 'A':
            self._input_mode_alpha_prop.set_state(IBus.PropState.CHECKED)
            self._input_mode_hira_prop.set_state(IBus.PropState.UNCHECKED)
        else:
            self._input_mode_alpha_prop.set_state(IBus.PropState.UNCHECKED)
            self._input_mode_hira_prop.set_state(IBus.PropState.CHECKED)
        self.update_property(self._input_mode_alpha_prop)
        self.update_property(self._input_mode_hira_prop)

    # =========================================================================
    # KEY EVENT PROCESSING
    # =========================================================================

    def do_process_key_event(self, keyval, keycode, state):
        """
        Main entry point for handling keyboard input from IBus.

        Args:
            keyval: The key value (e.g., ord('a'), IBus.KEY_BackSpace)
            keycode: The hardware keycode
            state: Modifier state (Shift, Ctrl, etc. and RELEASE_MASK)

        Returns:
            True if we handled the key, False to pass through to application
        """
        # Determine if this is a key press or release
        is_pressed = not (state & IBus.ModifierType.RELEASE_MASK)

        # Check enable_hiragana_key BEFORE mode check (must work from any mode)
        key_name = IBus.keyval_name(keyval)
        logger.debug(f'do_process_key_event: key_name={key_name}, mode={self._mode}, is_pressed={is_pressed}')
        if key_name and self._check_enable_hiragana_key(key_name, state, is_pressed):
            return True

        # Alphanumeric mode: pass everything through (except enable_hiragana_key above)
        if self._mode == 'A':
            return False

        # Process the key event
        result = self._process_key_event(keyval, keycode, state, is_pressed)

        # Update SandS (Space as modifier) tracking
        self._update_sands_status(keyval, is_pressed)

        return result

    def _process_key_event(self, keyval, keycode, state, is_pressed):
        """
        Intermediate handler for key events (non-Alphanumeric mode).

        This function handles:
        - Modifier key press/release (SandS, etc.)
        - Special keys (Enter, Backspace, Escape) with conditional handling
        - Regular character input via SimultaneousInputProcessor

        Args:
            keyval: The key value
            keycode: The hardware keycode
            state: Modifier state
            is_pressed: True if key press, False if key release

        Returns:
            True if we handled the key, False to pass through
        """
        logger.debug(f'_process_key_event: keyval={keyval}, keycode={keycode}, '
                     f'state={state}, is_pressed={is_pressed}')

        # Get key name for all key types (e.g., "a", "Henkan", "Alt_R", "F1")
        key_name = IBus.keyval_name(keyval)
        if not key_name:
            return False

        # =====================================================================
        # KANCHOKU / BUNSETSU MARKER HANDLING (highest priority)
        # =====================================================================
        # Must be checked before other bindings since the marker key (e.g., Space)
        # triggers a state machine that consumes subsequent key events.
        if self._handle_kanchoku_bunsetsu_marker(key_name, keyval, state, is_pressed):
            return True

        # =====================================================================
        # PURE KANCHOKU TRIGGER (alternative kanchoku input)
        # =====================================================================
        # Simpler kanchoku input that doesn't involve bunsetsu marking.
        # Keys not in kanchoku layout pass through (e.g., Alt+Tab works normally).
        if self._handle_pure_kanchoku(key_name, keyval, state, is_pressed):
            return True

        # =====================================================================
        # CONFIG-DRIVEN KEY BINDINGS (checked first, for all key types)
        # =====================================================================

        # Define modifier key names (already tracked by IBus via 'state' parameter)
        modifier_key_names = {
            'Control_L', 'Control_R', 'Shift_L', 'Shift_R',
            'Alt_L', 'Alt_R', 'Super_L', 'Super_R'
        }

        # Update pressed key set (non-modifier keys only)
        # Modifiers are excluded because IBus tracks them via 'state' bitmask.
        if key_name not in modifier_key_names:
            if is_pressed:
                self._pressed_key_set.add(key_name)
            else:
                self._pressed_key_set.discard(key_name)

        # Check config-driven key bindings (enable/disable hiragana, conversions)
        # Called for both press and release to properly consume the entire key sequence
        if self._check_config_key_bindings(key_name, state, is_pressed):
            return True

        # Pass through unrecognized combo-keys (e.g. Ctrl+0, Ctrl+C, Alt+F4)
        # so the application can handle them.  Shift is excluded since it is
        # part of normal typing (Shift+a → 'A').
        combo_mask = (IBus.ModifierType.CONTROL_MASK |
                      IBus.ModifierType.MOD1_MASK |
                      IBus.ModifierType.SUPER_MASK)
        if state & combo_mask and key_name not in modifier_key_names:
            # Before passing through the combo-key back to IBus, commit the preedit buffer.
            self._commit_string()
            self._in_forced_preedit = False
            self._bunsetsu_active = False
            self._in_conversion = False
            self._conversion_yomi = ''
            self._lookup_table.clear()
            self.hide_lookup_table()
            return False

        # =====================================================================
        # SPECIAL KEY HANDLING
        # =====================================================================

        # Handle special keys only on key press
        if is_pressed:
            # Enter key - confirm conversion or commit preedit
            if keyval == IBus.KEY_Return or keyval == IBus.KEY_KP_Enter:
                if self._in_conversion:
                    logger.debug('Enter pressed in CONVERTING: confirming')
                    self._confirm_conversion()
                    return True
                elif self._in_forced_preedit and self._preedit_string:
                    # Forced preedit: commit and consume Enter (Action 2)
                    logger.debug('Enter pressed in FORCED_PREEDIT: committing')
                    self._commit_string()
                    self._in_forced_preedit = False
                    return True
                elif self._bunsetsu_active and self._preedit_string:
                    # Bunsetsu mode: commit and consume Enter
                    logger.debug('Enter pressed in BUNSETSU: committing')
                    self._commit_string()
                    self._bunsetsu_active = False
                    return True
                elif self._preedit_string:
                    # IDLE mode with preedit: commit and pass Enter through
                    logger.debug('Enter pressed in IDLE with preedit: committing and passing through')
                    self._commit_string()
                    return False  # Pass Enter to application
                return False  # No preedit, pass through

            # Arrow keys for candidate cycling (only in CONVERTING state)
            if self._in_conversion:
                if keyval == IBus.KEY_Down or keyval == IBus.KEY_KP_Down:
                    logger.debug('Down arrow in CONVERTING: next candidate')
                    self._cycle_candidate()
                    return True
                elif keyval == IBus.KEY_Up or keyval == IBus.KEY_KP_Up:
                    logger.debug('Up arrow in CONVERTING: previous candidate')
                    self._cycle_candidate_backward()
                    return True
                elif keyval == IBus.KEY_Right or keyval == IBus.KEY_KP_Right:
                    # Right arrow: move to next bunsetsu (bunsetsu mode only)
                    if self._henkan_processor.is_bunsetsu_mode():
                        self._henkan_processor.next_bunsetsu()
                        self._update_preedit()  # Update display with new selection
                        logger.debug(f'Right arrow: moved to bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
                        return True
                    return False  # Pass through in whole-word mode
                elif keyval == IBus.KEY_Left or keyval == IBus.KEY_KP_Left:
                    # Left arrow: move to previous bunsetsu (bunsetsu mode only)
                    if self._henkan_processor.is_bunsetsu_mode():
                        self._henkan_processor.previous_bunsetsu()
                        self._update_preedit()  # Update display with new selection
                        logger.debug(f'Left arrow: moved to bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
                        return True
                    return False  # Pass through in whole-word mode

            # Arrow keys in IDLE mode: commit preedit and pass through
            if keyval in (IBus.KEY_Left, IBus.KEY_KP_Left,
                          IBus.KEY_Right, IBus.KEY_KP_Right,
                          IBus.KEY_Up, IBus.KEY_KP_Up,
                          IBus.KEY_Down, IBus.KEY_KP_Down):
                if self._preedit_string:
                    self._commit_string()
                return False

            # Tab key: commit preedit before passing through to avoid
            # preedit text appearing in both old and new focused fields
            if keyval in (IBus.KEY_Tab, IBus.KEY_ISO_Left_Tab):
                if self._preedit_string:
                    self._commit_string()
                return False

            # Escape / Delete - cancel conversion or clear preedit
            if keyval == IBus.KEY_Escape or keyval == IBus.KEY_Delete:
                if self._in_conversion:
                    logger.debug('Escape/Delete in CONVERTING: cancelling, reverting to yomi')
                    self._cancel_conversion()
                    return True
                elif self._preedit_string:
                    # Clear preedit
                    self._reset_henkan_state()
                    return True
                return False

            # Backspace - delete character or cancel conversion
            if keyval == IBus.KEY_BackSpace:
                if self._in_conversion:
                    # Cancel conversion and go back to yomi
                    logger.debug('Backspace in CONVERTING: reverting to yomi')
                    self._cancel_conversion()
                    return True
                elif self._preedit_string:
                    # Delete last character from all preedit buffers.
                    # Each buffer is trimmed by 1 character independently:
                    # - _preedit_string: display buffer (hiragana/katakana/etc.)
                    # - _preedit_hiragana: source for to_katakana/to_hiragana
                    # - _preedit_ascii: source for to_ascii/to_zenkaku
                    #
                    # The ASCII buffer uses a "mental model" approach: users who want
                    # ASCII output think in terms of keystrokes, not hiragana. So we
                    # simply remove the last keystroke, trusting that the user knows
                    # what they typed and what they're deleting.
                    self._preedit_string = self._preedit_string[:-1]
                    self._preedit_hiragana = self._preedit_hiragana[:-1]
                    if self._preedit_ascii:
                        self._preedit_ascii = self._preedit_ascii[:-1]
                    self._update_preedit()
                    return True
                return False

        # =====================================================================
        # REGULAR CHARACTER INPUT (simultaneous typing)
        # =====================================================================

        # Only process printable ASCII characters (0x20 space to 0x7e tilde)
        if keyval < 0x20 or keyval > 0x7e:
            return False

        # If in CONVERTING state and typing a new character, confirm and continue
        if is_pressed and self._in_conversion:
            logger.debug(f'Char input in CONVERTING: confirming and adding "{chr(keyval)}"')
            # Commit the selected candidate
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))
            # Reset state - new char confirms conversion and exits forced preedit
            self._in_conversion = False
            self._in_forced_preedit = False  # Exit forced preedit mode (Action 1)
            self._conversion_yomi = ''
            self._lookup_table.clear()
            self.hide_lookup_table()
            # Clear preedit for new input
            self._preedit_string = ''
            self._preedit_hiragana = ''
            self._preedit_ascii = ''
            # Continue to process the new character below

        # If preedit was converted (e.g., to katakana via Ctrl+K), commit it
        # before starting fresh input. Unlike _in_conversion, this flag does NOT
        # affect Escape/Enter/arrow behavior (they treat it as normal IDLE preedit).
        elif is_pressed and self._converted:
            logger.debug(f'Char input after conversion: committing "{self._preedit_string}"')
            self._commit_string()
            # Continue to process the new character below

        # Convert keyval to character for simultaneous processor
        input_char = chr(keyval)

        # Accumulate ASCII input on key press (source of truth for to_ascii/to_zenkaku)
        if is_pressed:
            self._preedit_ascii += input_char

        # Get output from simultaneous processor
        # Pass current display buffer (hiragana + pending) for lookup
        output, pending = self._simul_processor.get_layout_output(
            self._preedit_string, input_char, is_pressed
        )

        logger.debug(f'Processor result: output="{output}", pending="{pending}"')

        # Update hiragana buffer (source of truth for to_katakana/to_hiragana)
        # output includes accumulated hiragana via dropped_prefix mechanism
        self._preedit_hiragana = output if output else ''

        # Build display buffer: hiragana output + pending ASCII
        new_preedit = self._preedit_hiragana + (pending if pending else '')
        self._preedit_string = new_preedit
        self._update_preedit()

        return True

    # =========================================================================
    # CONFIG-DRIVEN KEY BINDINGS
    # =========================================================================

    def _check_config_key_bindings(self, key_name, state, is_pressed):
        """
        Check if the current key event matches any config-driven key binding.

        Checks in order:
        1. enable_hiragana_key - switch to hiragana mode
        2. disable_hiragana_key - switch to direct/alphanumeric mode
        3. conversion_keys - convert preedit (to_katakana, to_hiragana, etc.)

        Args:
            key_name: The key name from IBus.keyval_name() (e.g., "a", "Henkan", "F1")
            state: Modifier state bitmask from IBus
            is_pressed: True if key press, False if key release

        Returns:
            True if key was handled (caller should return), False otherwise
        """
        # Check enable_hiragana_key
        if self._check_enable_hiragana_key(key_name, state, is_pressed):
            return True

        # Check disable_hiragana_key
        if self._check_disable_hiragana_key(key_name, state, is_pressed):
            self._commit_string()  # Commit and clear preedit before switching mode
            return True

        # Check conversion_keys
        if self._check_conversion_keys(key_name, state, is_pressed):
            return True

        # Check bunsetsu_prediction_cycle_key
        if self._check_bunsetsu_prediction_key(key_name, state, is_pressed):
            return True

        # Check user_dictionary_editor_trigger
        if self._check_user_dictionary_editor_key(key_name, state, is_pressed):
            return True

        # Check force_commit_key
        if self._check_force_commit_key(key_name, state, is_pressed):
            return True

        return False

    def _parse_key_binding(self, binding_str):
        """
        Parse a key binding string like "Ctrl+K" or "Henkan" into components.

        Args:
            binding_str: Key binding string (e.g., "k", "Ctrl+K", "Henkan", "Ctrl+Shift+L")

        Returns:
            tuple: (main_key, required_modifiers_mask) or (None, 0) if invalid
        """
        if not binding_str:
            return None, 0

        parts = binding_str.split('+')
        main_key = parts[-1]  # Last part is the main key

        modifiers = 0
        for part in parts[:-1]:
            part_lower = part.lower()
            if part_lower in ('ctrl', 'control'):
                modifiers |= IBus.ModifierType.CONTROL_MASK
            elif part_lower == 'shift':
                modifiers |= IBus.ModifierType.SHIFT_MASK
            elif part_lower == 'alt':
                modifiers |= IBus.ModifierType.MOD1_MASK
            elif part_lower == 'super':
                modifiers |= IBus.ModifierType.SUPER_MASK

        return main_key, modifiers

    def _matches_key_binding(self, key_name, state, binding_str):
        """
        Check if key_name + state matches a key binding string.

        Args:
            key_name: The key name from IBus.keyval_name()
            state: Modifier state bitmask from IBus
            binding_str: Key binding string from config (e.g., "Ctrl+K", "Henkan")

        Returns:
            True if the input matches the binding exactly
        """
        main_key, required_mods = self._parse_key_binding(binding_str)
        if main_key is None:
            return False

        # Check main key matches (case-insensitive for single letters)
        if len(main_key) == 1 and len(key_name) == 1:
            if main_key.lower() != key_name.lower():
                return False
        else:
            # For special keys like "Henkan", exact match required
            if main_key != key_name:
                return False

        # Check required modifiers (exact match)
        mod_mask = (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK |
                    IBus.ModifierType.MOD1_MASK | IBus.ModifierType.SUPER_MASK)
        current_mods = state & mod_mask

        return current_mods == required_mods

    def _matches_any_key_binding(self, key_name, state, bindings):
        """
        Check if key_name + state matches any binding in a list.
        key_name + state がリスト内のいずれかのバインディングに一致するか確認。

        Args:
            key_name: The key name from IBus.keyval_name()
            state: Modifier state bitmask from IBus
            bindings: List of key binding strings (e.g., ["Ctrl+K", "Ctrl+Shift+K"])

        Returns:
            str or None: The matched binding string, or None if no match
        """
        for binding in bindings:
            if self._matches_key_binding(key_name, state, binding):
                return binding
        return None

    def _check_enable_hiragana_key(self, key_name, state, is_pressed):
        """
        Check and handle enable_hiragana_key binding.

        Switches mode to hiragana ('あ') when the configured key is pressed.
        """
        bindings = self._config.get('enable_hiragana_key', [])

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check if any binding matches
        matched = self._matches_any_key_binding(key_name, state, bindings)
        if matched:
            logger.debug(f'enable_hiragana_key matched: {matched}')
            self._mode = 'あ'
            self._update_input_mode()  # Update IBus icon
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _check_disable_hiragana_key(self, key_name, state, is_pressed):
        """
        Check and handle disable_hiragana_key binding.

        Switches mode to alphanumeric ('A') when the configured key is pressed.
        If in CONVERTING state, commits the selected candidate first.
        If in BUNSETSU_ACTIVE state, commits the preedit as-is.
        """
        bindings = self._config.get('disable_hiragana_key', [])

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check if any binding matches
        matched = self._matches_any_key_binding(key_name, state, bindings)
        if matched:
            logger.debug(f'disable_hiragana_key matched: {matched}')

            # If in CONVERTING state, commit the selected candidate
            if self._in_conversion:
                logger.debug('disable_hiragana_key in CONVERTING: committing candidate')
                self._confirm_conversion()
            elif self._bunsetsu_active or self._preedit_string:
                # Commit any preedit as-is (no conversion)
                logger.debug('disable_hiragana_key with preedit: committing')
                self._commit_string()

            self._mode = 'A'
            self._update_input_mode()  # Update IBus icon
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _check_conversion_keys(self, key_name, state, is_pressed):
        """
        Check and handle conversion_keys bindings.

        Converts the preedit string to different character representations:
        - to_katakana: Convert to katakana
        - to_hiragana: Convert to hiragana
        - to_ascii: Convert to ASCII/romaji
        - to_zenkaku: Convert to full-width characters
        """
        conversion_keys = self._config.get('conversion_keys', {})
        if not isinstance(conversion_keys, dict):
            return False

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check each conversion key binding
        # When preedit is empty, let the key pass through to the application
        # (e.g., Ctrl+L should reach the browser to select the URL bar)
        if not self._preedit_string:
            return False

        for conversion_type, bindings in conversion_keys.items():
            matched = self._matches_any_key_binding(key_name, state, bindings)
            if matched:
                logger.debug(f'conversion_key matched: {conversion_type} = {matched}')
                self._handle_conversion(conversion_type)
                self._handled_config_keys.add(key_name)
                return True

        return False

    def _check_bunsetsu_prediction_key(self, key_name, state, is_pressed):
        """
        Check and handle bunsetsu_prediction_cycle_key binding.

        This key cycles through N-best bunsetsu prediction candidates.
        """
        bindings = self._config.get('bunsetsu_prediction_cycle_key', [])
        if not bindings:
            return False

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # On press: check if any binding matches
        matched = self._matches_any_key_binding(key_name, state, bindings)
        if matched:
            logger.debug(f'bunsetsu_prediction_cycle_key matched: {matched}')
            self._cycle_bunsetsu_prediction()
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _check_user_dictionary_editor_key(self, key_name, state, is_pressed):
        """
        Check and handle user_dictionary_editor_trigger binding.

        Opens the User Dictionary Editor with the current preedit as the reading.
        Only activates when preedit is non-empty.
        """
        bindings = self._config.get('user_dictionary_editor_trigger', [])
        if not bindings:
            return False

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # Only activate when preedit is non-empty
        if not self._preedit_string:
            return False

        # On press: check if any binding matches
        matched = self._matches_any_key_binding(key_name, state, bindings)
        if matched:
            logger.debug(f'user_dictionary_editor_trigger matched: {matched}')
            self._open_user_dictionary_editor_with_preedit()
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _check_force_commit_key(self, key_name, state, is_pressed):
        """
        Check and handle force_commit_key binding.
        force_commit_key バインディングを確認し処理

        Commits the current preedit as-is (hiragana/katakana/ASCII) without
        performing kanji conversion. If the buffer is empty, returns False
        to pass the key through to the application.

        現在のプリエディット（ひらがな/カタカナ/ASCII）を漢字変換せずに
        そのまま確定します。バッファが空の場合は False を返し、キーを
        アプリケーションに渡します。
        """
        bindings = self._config.get('force_commit_key', [])
        if not bindings:
            return False

        # On release: consume if this key was handled on press
        if not is_pressed:
            if key_name in self._handled_config_keys:
                self._handled_config_keys.discard(key_name)
                return True
            return False

        # If preedit is empty, pass through to application
        if not self._preedit_string:
            return False

        # On press: check if any binding matches
        matched = self._matches_any_key_binding(key_name, state, bindings)
        if matched:
            logger.debug(f'force_commit_key matched: {matched}')
            self._commit_string()
            self._reset_henkan_state()  # Clear conversion state flags
            self._handled_config_keys.add(key_name)
            return True

        return False

    def _handle_pure_kanchoku(self, key_name, keyval, state, is_pressed):
        """
        Handle pure kanchoku trigger key for simplified kanji input.
        純粋な漢直トリガーキーによる簡易漢字入力を処理

        This is a simpler alternative to the marker-based kanchoku that doesn't
        involve bunsetsu marking or forced preedit mode. While the trigger key
        is held, two-key kanchoku sequences are captured and converted to kanji.

        マーカーベースの漢直の代替として、文節マークや強制プリエディットモードを
        伴わない、より単純な漢直入力方法。トリガーキーを押している間、2キーの
        漢直シーケンスがキャプチャされ、漢字に変換される。

        Key behaviors:
        - Keys defined in kanchoku layout: captured for kanchoku sequence
        - Keys NOT in layout: passed through (e.g., Alt+Tab works normally)
        - Incomplete sequences on trigger release: silent reset
        - Continuous input: multiple kanchoku pairs while trigger held

        Args:
            key_name: Key name from IBus.keyval_name()
            keyval: Key value
            state: Modifier key state bitmask from IBus
            is_pressed: True if key press, False if key release

        Returns:
            bool: True if key was consumed, False to pass through
        """
        trigger_keys = self._config.get('kanchoku_pure_trigger_key', [])
        if not trigger_keys:
            return False

        # Ensure trigger_keys is a list (defensive check)
        if isinstance(trigger_keys, str):
            trigger_keys = [trigger_keys]

        # Check if this is the trigger key itself (match by key name only, ignoring state)
        # This is necessary because pressing a modifier key like Alt_L immediately sets
        # MOD1_MASK in state, which would cause _matches_key_binding to fail.
        #
        # Also handle the case where user configures "Alt" but presses "Alt_R" or "Alt_L":
        # Strip _L/_R suffix from key_name before comparing.
        key_name_normalized = key_name.lower()
        if key_name_normalized.endswith('_l') or key_name_normalized.endswith('_r'):
            key_name_base = key_name_normalized[:-2]  # Remove _L or _R
        else:
            key_name_base = key_name_normalized

        is_trigger = any(
            key_name_base == tk.split('+')[-1].lower() or
            key_name_normalized == tk.split('+')[-1].lower()
            for tk in trigger_keys
        )

        logger.debug(f'Pure kanchoku: key={key_name} (base={key_name_base}), triggers={trigger_keys}, '
                     f'is_trigger={is_trigger}, held={self._pure_kanchoku_held}')

        if is_trigger:
            if is_pressed:
                self._pure_kanchoku_held = True
                self._pure_kanchoku_first_key = None
                logger.debug(f'Pure kanchoku trigger pressed, valid_first_keys={len(self._kanchoku_valid_first_keys)}')
            else:
                # Released - silent reset
                if self._pure_kanchoku_first_key:
                    logger.debug(f'Pure kanchoku incomplete sequence, silent reset (first_key was: {self._pure_kanchoku_first_key})')
                self._pure_kanchoku_held = False
                self._pure_kanchoku_first_key = None
            return True

        # If trigger not held, don't interfere
        if not self._pure_kanchoku_held:
            return False

        # Ignore key releases while in pure kanchoku mode
        if not is_pressed:
            return True

        # Convert keyval to lowercase character for lookup
        if keyval < 0x20 or keyval > 0x7e:
            # Non-printable key - pass through
            return False

        key_char = chr(keyval).lower()

        # Check if we have a first key yet
        if self._pure_kanchoku_first_key is None:
            # First key of sequence
            if key_char in self._kanchoku_valid_first_keys:
                # Valid first stroke - capture it
                self._pure_kanchoku_first_key = key_char
                logger.debug(f'Pure kanchoku first key: {key_char}')
                return True
            else:
                # Not a valid first stroke - pass through
                logger.debug(f'Pure kanchoku: {key_char} not in layout, passing through')
                return False
        else:
            # Second key of sequence
            first_key = self._pure_kanchoku_first_key
            valid_seconds = self._kanchoku_valid_seconds.get(first_key, set())

            if key_char in valid_seconds:
                # Valid second stroke - emit kanji
                kanji = self._kanchoku_processor._lookup_kanji(first_key, key_char)
                if kanji and kanji != MISSING_KANCHOKU_KANJI:
                    logger.debug(f'Pure kanchoku: {first_key}+{key_char} → {kanji}')
                    self._emit_kanchoku_output(kanji)
                else:
                    logger.debug(f'Pure kanchoku: {first_key}+{key_char} → no kanji found')
            else:
                # Invalid second stroke - silent reset (consume key)
                logger.debug(f'Pure kanchoku: {key_char} not valid second for {first_key}, silent reset')

            # Reset first key for next sequence (whether successful or not)
            self._pure_kanchoku_first_key = None
            return True

    def _open_user_dictionary_editor_with_preedit(self):
        """
        Open the User Dictionary Editor with current preedit as the reading.

        This is triggered by user_dictionary_editor_trigger keybinding.
        Before opening:
        1. Hide lookup table if in conversion mode
        2. Clear preedit buffer and reset to IDLE mode
        3. Launch editor with preedit pre-filled as reading
        """
        # Save the preedit value before clearing
        reading = self._preedit_string
        logger.debug(f'Opening user dictionary editor with reading: "{reading}"')

        # Hide lookup table if visible (conversion mode)
        if self._in_conversion:
            self._lookup_table.clear()
            self.hide_lookup_table()

        # Reset to IDLE mode (clear all state flags)
        self._reset_henkan_state()

        # Launch editor with prefilled reading (on main loop)
        GLib.idle_add(self._show_user_dictionary_editor_with_reading, reading)

    def _show_user_dictionary_editor_with_reading(self, reading):
        """Show user dictionary editor with pre-filled reading (idle callback)."""
        if self._user_dictionary_editor:
            # If already open, just bring to front and update reading
            self._user_dictionary_editor.present()
            self._user_dictionary_editor.reading_entry.set_text(reading)
            self._user_dictionary_editor.reading_entry.grab_focus()
            return False

        editor = user_dictionary_editor.open_editor(prefill_reading=reading)
        editor.connect("destroy", self.user_dictionary_editor_closed_callback)
        self._user_dictionary_editor = editor

        return False  # Don't repeat this idle callback

    def _cycle_bunsetsu_prediction(self):
        """
        Cycle to the next N-best bunsetsu prediction candidate.

        This is triggered by bunsetsu_prediction_cycle_key and cycles through:
        - Whole-word dictionary match (if available)
        - CRF N-best #1 (if multi-bunsetsu)
        - CRF N-best #2 (if multi-bunsetsu)
        - ... and wraps around
        """
        if not self._in_conversion:
            logger.debug('_cycle_bunsetsu_prediction: not in conversion mode')
            return

        # Cycle to next prediction
        changed = self._henkan_processor.cycle_bunsetsu_prediction()
        if not changed:
            logger.debug('_cycle_bunsetsu_prediction: no change (no predictions available)')
            return

        # Update preedit with new prediction
        self._preedit_string = self._henkan_processor.get_display_surface()
        self._update_preedit()

        # Update lookup table if not in bunsetsu mode (whole-word mode has lookup table)
        if not self._henkan_processor.is_bunsetsu_mode():
            # Back to whole-word mode - restore lookup table
            self._lookup_table.set_cursor_pos(0)
            self.update_lookup_table(self._lookup_table, True)
        else:
            # In bunsetsu mode - hide whole-word lookup table
            self.hide_lookup_table()

        logger.debug(f'_cycle_bunsetsu_prediction: bunsetsu_mode={self._henkan_processor.is_bunsetsu_mode()}, '
                    f'surface="{self._preedit_string}"')

    def _handle_conversion(self, conversion_type):
        """
        Perform the actual conversion of preedit string.

        Uses source-of-truth buffers:
        - _preedit_hiragana: for to_katakana and to_hiragana
        - _preedit_ascii: for to_ascii and to_zenkaku

        Note: Each buffer is trimmed independently on backspace. The ASCII buffer
        follows a "mental model" approach where each backspace removes one keystroke,
        so conversions remain available even after deletions.

        Args:
            conversion_type: One of 'to_katakana', 'to_hiragana', 'to_ascii', 'to_zenkaku'
        """
        if not self._preedit_string:
            return

        original = self._preedit_string

        if conversion_type == 'to_katakana':
            # Convert hiragana source to katakana
            self._preedit_string = self._preedit_hiragana.translate(HIRAGANA_TO_KATAKANA)
        elif conversion_type == 'to_hiragana':
            # Use hiragana source directly
            self._preedit_string = self._preedit_hiragana
        elif conversion_type == 'to_ascii':
            # Use ASCII source directly
            self._preedit_string = self._preedit_ascii
        elif conversion_type == 'to_zenkaku':
            # Convert ASCII source to full-width
            self._preedit_string = self._preedit_ascii.translate(ASCII_TO_FULLWIDTH)
        else:
            logger.warning(f'Unknown conversion type: {conversion_type}')
            return

        # Exit bunsetsu/conversion/forced-preedit mode when doing character conversion
        # (user explicitly wants katakana/hiragana/ascii/zenkaku, not kanji)
        if self._in_conversion:
            self._in_conversion = False
            self._henkan_processor.reset()
            self.hide_lookup_table()
            logger.debug(f'Exited conversion mode for {conversion_type}')

        # Also exit bunsetsu/forced-preedit modes - user is done with these modes
        # after explicitly converting to katakana/hiragana/etc.
        if self._bunsetsu_active:
            self._bunsetsu_active = False
            logger.debug(f'Exited bunsetsu mode for {conversion_type}')
        if self._in_forced_preedit:
            self._in_forced_preedit = False
            logger.debug(f'Exited forced preedit mode for {conversion_type}')

        # Mark as converted so the next character input auto-commits this preedit.
        # Escape/Enter/arrow keys ignore this flag and treat it as normal IDLE preedit.
        self._converted = True

        logger.debug(f'Conversion {conversion_type}: "{original}" → "{self._preedit_string}"')
        self._update_preedit()

    # =========================================================================
    # SANDS (SPACE AND SHIFT) TRACKING
    # =========================================================================

    def _update_sands_status(self, keyval, is_pressed):
        """
        Update self._modkey_status for SandS (Space and Shift) feature.

        SandS allows Space to act as a modifier (Shift) when held and pressed
        with another key, while still producing a space when tapped alone.

        IBus doesn't track Space as a modifier, so we need custom tracking.
        Other modifiers (Ctrl, Shift, Alt, Super) are already tracked by IBus
        via the 'state' parameter.

        Args:
            keyval: The key value
            is_pressed: True if key press, False if key release
        """
        if keyval != IBus.KEY_space:
            return

        if is_pressed:
            self._modkey_status |= STATUS_SPACE
        else:
            self._modkey_status &= ~STATUS_SPACE

        logger.debug(f'SandS status: space_held={bool(self._modkey_status & STATUS_SPACE)}')

    # =========================================================================
    # KANCHOKU / BUNSETSU MARKER HANDLING
    # =========================================================================

    def _handle_kanchoku_bunsetsu_marker(self, key_name, keyval, state, is_pressed):
        """
        Handle kanchoku_bunsetsu_marker key (Space) and related sequences.
        漢直・文節マーカーキー（スペース）と関連シーケンスの処理

        ─────────────────────────────────────────────────────────────────────────
        PURPOSE / 目的
        ─────────────────────────────────────────────────────────────────────────
        This is the core entry point for the marker key state machine. The marker
        key (typically Space) enables three different behaviors depending on
        what keys are pressed while it's held down:

        これはマーカーキー状態機械の中核エントリーポイントである。マーカーキー
        （通常はスペース）は、押し続けている間にどのキーが押されるかによって
        3つの異なる動作を可能にする：

        ─────────────────────────────────────────────────────────────────────────
        THREE BEHAVIORS / 3つの動作
        ─────────────────────────────────────────────────────────────────────────

        Case A: KANCHOKU (漢直 - Direct Kanji Input)
        ─────────────────────────────────────────────
        Sequence: marker↓ → key1↓↑ → key2↓↑ → marker↑
        Result:   Lookup kanji from (key1, key2) pair, output to preedit
        シーケンス：marker↓ → key1↓↑ → key2↓↑ → marker↑
        結果：(key1, key2)ペアから漢字を検索し、プリエディットに出力

        Case B: BUNSETSU (文節 - Phrase Boundary)
        ─────────────────────────────────────────
        Sequence: marker↓ → key1↓↑ → marker↑
        Condition: key1 can start a bunsetsu (normal characters)
        Result:   Mark bunsetsu boundary, key1 becomes start of new bunsetsu
        シーケンス：marker↓ → key1↓↑ → marker↑
        条件：key1が文節を開始できる（通常文字）
        結果：文節境界をマーク、key1が新しい文節の開始になる

        Case C: FORCED PREEDIT (強制プリエディット)
        ────────────────────────────────────────────
        Sequence: marker↓ → trigger_key↓↑ → marker↑
        Condition: key1 == forced_preedit_trigger_key (default: 'f')
        Result:   Enter forced preedit mode for kanchoku+kana mixing
        シーケンス：marker↓ → trigger_key↓↑ → marker↑
        条件：key1 == forced_preedit_trigger_key（デフォルト：'f'）
        結果：漢直＋かな混在用の強制プリエディットモードに入る

        ─────────────────────────────────────────────────────────────────────────
        STATE MACHINE / 状態機械
        ─────────────────────────────────────────────────────────────────────────
        IDLE → (marker↓) → MARKER_HELD → (key1↓) → FIRST_PRESSED
                                                       ↓ (key1↑)
                                              FIRST_RELEASED
                                               /           \\
                                    (key2↓)  /             \\ (marker↑)
                                            ↓               ↓
                           KANCHOKU_SECOND_PRESSED    [Decision]
                                   ↓                  Case B or C
                           (keys↑, marker↑) → IDLE

        Args:
            key_name: IBus.keyval_name()から取得したキー名
            keyval: キー値
            state: IBusからの修飾キー状態ビットマスク
            is_pressed: キー押下ならTrue、離上ならFalse

        Returns:
            bool: キーが消費された場合True、そうでなければFalse
        """
        marker_bindings = self._config.get('kanchoku_bunsetsu_marker', [])
        if not marker_bindings:
            return False

        matched_binding = self._matches_any_key_binding(key_name, state, marker_bindings)
        is_marker_key = matched_binding is not None

        # === MARKER KEY HANDLING ===
        if is_marker_key:
            return self._handle_marker_key_event(is_pressed)

        # === OTHER KEYS WHILE MARKER HELD ===
        if self._marker_state != MarkerState.IDLE:
            return self._handle_key_while_marker_held(key_name, keyval, is_pressed)

        return False

    def _handle_marker_key_event(self, is_pressed):
        """
        Handle press/release of the marker key itself.
        マーカーキー自体の押下/離上を処理

        ─────────────────────────────────────────────────────────────────────────
        ON PRESS / 押下時
        ─────────────────────────────────────────────────────────────────────────
        Behavior depends on current henkan state:
        動作は現在の変換状態に依存する：

        ┌────────────────┬───────────────────────────────────────────────────────┐
        │ State / 状態    │ Behavior / 動作                                       │
        ├────────────────┼───────────────────────────────────────────────────────┤
        │ CONVERTING     │ Save candidate, wait for tap vs space+key判定         │
        │ 変換中          │ 候補を保存、タップ vs space+key を待つ                 │
        ├────────────────┼───────────────────────────────────────────────────────┤
        │ BUNSETSU       │ Save yomi for potential implicit conversion           │
        │ 文節入力        │ 暗黙変換用に読みを保存                                 │
        ├────────────────┼───────────────────────────────────────────────────────┤
        │ FORCED_PREEDIT │ Save preedit (may contain kanchoku kanji)             │
        │ 強制入力        │ プリエディットを保存（漢直漢字を含む可能性あり）        │
        ├────────────────┼───────────────────────────────────────────────────────┤
        │ IDLE           │ Commit any existing preedit, start fresh              │
        │ 通常           │ 既存のプリエディットを確定、新規開始                    │
        └────────────────┴───────────────────────────────────────────────────────┘

        ─────────────────────────────────────────────────────────────────────────
        ON RELEASE / 離上時
        ─────────────────────────────────────────────────────────────────────────
        Depends on state at release time:
        離上時の状態による：

        ┌────────────────────┬─────────────────────────────────────────────────────┐
        │ State / 状態        │ Action / 動作                                       │
        ├────────────────────┼─────────────────────────────────────────────────────┤
        │ MARKER_HELD        │ Space tap: commit+space or cycle candidate          │
        │ (no key pressed)   │ スペースタップ: 確定+空白 または候補切替             │
        ├────────────────────┼─────────────────────────────────────────────────────┤
        │ FIRST_RELEASED     │ Decision: bunsetsu or forced preedit                │
        │ (key1 was pressed) │ 判定: 文節 または 強制プリエディット                 │
        ├────────────────────┼─────────────────────────────────────────────────────┤
        │ KANCHOKU_SECOND_   │ Kanchoku completed, just cleanup                    │
        │ PRESSED            │ 漢直完了、クリーンアップのみ                         │
        ├────────────────────┼─────────────────────────────────────────────────────┤
        │ FIRST_PRESSED      │ Key still held: treat as bunsetsu                   │
        │ (key1 still held)  │ キーがまだ押されている: 文節として扱う               │
        └────────────────────┴─────────────────────────────────────────────────────┘

        Returns:
            bool: True (マーカーキーは常に消費される)
        """
        if is_pressed:
            # Behavior on marker press depends on current henkan state
            if self._in_conversion:
                # CONVERTING state: prepare for potential space+key (new bunsetsu)
                # DON'T change _in_conversion yet - wait for release to know if tap or space+key
                # DON'T clear preedit - keep candidate visible so it can be committed
                # directly when we confirm it's space+key (in MARKER_HELD key-press handler)
                self._preedit_before_marker = self._preedit_string
                # Note: Keep _in_conversion = True so tap can cycle candidates
                logger.debug(f'Marker pressed in CONVERTING: candidate "{self._preedit_string}"')
            elif self._bunsetsu_active or self._in_forced_preedit:
                # BUNSETSU_ACTIVE or FORCED_PREEDIT: save current yomi for potential implicit conversion
                self._preedit_before_marker = self._preedit_string
                logger.debug(f'Marker pressed in BUNSETSU/FORCED_PREEDIT: saved yomi "{self._preedit_before_marker}"')
            else:
                # IDLE state: commit any existing preedit before starting marker sequence
                self._commit_string()
                self._preedit_before_marker = ''

            self._marker_state = MarkerState.MARKER_HELD
            self._marker_first_key = None
            self._marker_keys_held.clear()
            self._marker_had_input = False
            logger.debug('Marker pressed: entering MARKER_HELD state')
            return True

        # Marker released
        logger.debug(f'Marker released in state: {self._marker_state.name}, '
                    f'bunsetsu_active={self._bunsetsu_active}, in_conversion={self._in_conversion}')

        if self._marker_state == MarkerState.MARKER_HELD:
            if self._marker_had_input:
                # Keys were pressed during this space hold (e.g. kanchoku completed
                # and returned to MARKER_HELD). This is NOT a tap — just release cleanly.
                logger.debug('Space released after input (not a tap), no action')
            elif self._in_conversion:
                # CONVERTING state: cycle to next candidate
                logger.debug('Space tap in CONVERTING: cycling candidate')
                self._cycle_candidate()
            elif self._bunsetsu_active or self._in_forced_preedit:
                # BUNSETSU_ACTIVE or FORCED_PREEDIT state: trigger conversion
                logger.debug('Space tap in BUNSETSU/FORCED_PREEDIT: triggering conversion')
                self._trigger_conversion()
            else:
                # IDLE state: commit preedit + output space
                logger.debug('Space tap in IDLE: committing preedit + space')
                self._commit_string()
                self.commit_text(IBus.Text.new_from_string(' '))
        elif self._marker_state == MarkerState.FIRST_RELEASED:
            # Decision point: was this bunsetsu or forced preedit?
            self._handle_marker_release_decision()
        elif self._marker_state == MarkerState.KANCHOKU_SECOND_PRESSED:
            # Kanchoku was completed, just clean up
            pass
        elif self._marker_state == MarkerState.FIRST_PRESSED:
            # First key is still held when marker released - this is bunsetsu mode
            # (User typed quickly: space down → key down → space up → key up)
            # Treat this the same as FIRST_RELEASED - activate bunsetsu mode
            logger.debug('Marker released while first key held: treating as bunsetsu')
            self._handle_marker_release_decision()

        self._marker_state = MarkerState.IDLE
        self._marker_first_key = None
        self._marker_keys_held.clear()
        return True

    def _handle_marker_release_decision(self):
        """
        Handle the decision when marker is released after first key was pressed.
        最初のキーが押された後にマーカーが離された時の判定処理

        ─────────────────────────────────────────────────────────────────────────
        CONTEXT / コンテキスト
        ─────────────────────────────────────────────────────────────────────────
        This is called when the user did: space↓ → key1↓↑ → space↑
        The function decides between Case B (bunsetsu) and Case C (forced preedit).
        (Case A / kanchoku is already handled before this point if key2 was pressed)

        この関数は以下のシーケンスで呼ばれる: space↓ → key1↓↑ → space↑
        Case B（文節）と Case C（強制プリエディット）を判定する。
        （Case A / 漢直は key2 が押された時点で既に処理済み）

        ─────────────────────────────────────────────────────────────────────────
        PROCESSING STEPS / 処理ステップ
        ─────────────────────────────────────────────────────────────────────────

        Step 1: Handle forced-preedit stripping / 強制プリエディットのストリッピング
        ─────────────────────────────────────────────────────────────────────────
        In forced-preedit mode, the old content wasn't cleared at key press
        (to keep kanchoku visible). We strip the old content here.

        強制プリエディットモードでは、漢直を表示し続けるために
        キー押下時に古いコンテンツがクリアされていない。ここでストリップする。

        IMPORTANT DESIGN NOTE / 重要な設計上の注意:
        Kanchoku kanji exist ONLY in _preedit_string, NOT in _preedit_hiragana
        or _preedit_ascii. Converting to katakana/ASCII will lose kanchoku kanji.
        This is by design - users understand that kanchoku bypasses the buffer system.

        漢直漢字は _preedit_string にのみ存在し、_preedit_hiragana や
        _preedit_ascii には存在しない。カタカナ/ASCIIへの変換で漢直漢字は失われる。
        これは意図的な設計 - ユーザーは漢直がバッファシステムをバイパスすることを理解している。

        Step 2: Implicit conversion / 暗黙変換
        ─────────────────────────────────────────────────────────────────────────
        If in BUNSETSU or FORCED_PREEDIT mode, convert the saved yomi and commit
        the first candidate. This is "implicit conversion" - the user doesn't
        need to explicitly press space to convert; simply starting a new bunsetsu
        with space+key triggers conversion of the previous bunsetsu.

        BUNSETSU または FORCED_PREEDIT モードの場合、保存された読みを変換し
        最初の候補を確定する。これが「暗黙変換」- ユーザーは明示的にスペースを
        押して変換する必要がない。単に space+key で新しい文節を開始するだけで
        前の文節が変換される。

        Step 3: Decision / 判定
        ─────────────────────────────────────────────────────────────────────────
        - If key1 == forced_preedit_trigger_key → Enter forced preedit (Case C)
        - Otherwise → Start new bunsetsu (Case B)

        - key1 == forced_preedit_trigger_key → 強制プリエディットに入る（Case C）
        - それ以外 → 新しい文節を開始（Case B）
        """
        # Save the new bunsetsu content that was typed during space+key
        new_bunsetsu_preedit = self._preedit_string
        new_bunsetsu_hiragana = self._preedit_hiragana
        new_bunsetsu_ascii = self._preedit_ascii

        # For forced-preedit mode, the old content wasn't cleared at key press
        # (to keep kanchoku working), so we need to strip it here.
        # Note: Kanchoku letters exist only in _preedit_string, not in _preedit_hiragana
        # or _preedit_ascii. This is by design - converting to katakana/ascii/zenkaku
        # will exclude kanchoku letters since those conversions use the respective buffers.
        if self._in_forced_preedit and self._preedit_before_marker:
            old_preedit = self._preedit_before_marker
            if new_bunsetsu_preedit.startswith(old_preedit):
                new_bunsetsu_preedit = new_bunsetsu_preedit[len(old_preedit):]
                # The stripped content is the new hiragana typed during space+key
                new_bunsetsu_hiragana = new_bunsetsu_preedit
                # For ascii, take last N chars where N = length of new hiragana
                new_len = len(new_bunsetsu_preedit)
                new_bunsetsu_ascii = new_bunsetsu_ascii[-new_len:] if new_len > 0 else ''

        # Commit previous bunsetsu content via implicit conversion
        if self._bunsetsu_active or self._in_forced_preedit:
            # In BUNSETSU_ACTIVE or FORCED_PREEDIT: perform implicit conversion on the saved yomi
            yomi = self._preedit_before_marker
            if yomi:
                candidates = self._henkan_processor.convert(yomi)
                if candidates:
                    surface = candidates[0]['surface']
                    logger.debug(f'Implicit conversion: "{yomi}" → "{surface}"')
                    self.commit_text(IBus.Text.new_from_string(surface))
                else:
                    logger.debug(f'No candidates for implicit conversion, committing yomi: "{yomi}"')
                    self.commit_text(IBus.Text.new_from_string(yomi))

        # Reset henkan state but preserve the new bunsetsu content
        self._bunsetsu_active = False
        self._in_conversion = False
        self._in_forced_preedit = False  # Exit forced preedit when starting new bunsetsu
        self._conversion_yomi = ''
        self._lookup_table.clear()
        self.hide_lookup_table()

        # Restore the new bunsetsu content
        self._preedit_string = new_bunsetsu_preedit
        self._preedit_hiragana = new_bunsetsu_hiragana
        self._preedit_ascii = new_bunsetsu_ascii

        forced_preedit_keys = self._config.get('forced_preedit_trigger_key', [])

        if self._marker_first_key in forced_preedit_keys:
            # Case (C): Forced preedit mode
            # Clear the tentative output (e.g., "ん") since it's not part of bunsetsu
            self._preedit_string = ''
            self._preedit_hiragana = ''
            self._preedit_ascii = ''
            self._update_preedit()
            self._in_forced_preedit = True
            logger.debug('Entering forced preedit mode (Case C)')
        else:
            # Case (B): Bunsetsu marking - start new bunsetsu
            # Keep the tentative output (e.g., "い") and mark boundary
            self._mark_bunsetsu_boundary()
            self._update_preedit()
            logger.debug(f'Bunsetsu started with "{self._preedit_string}" (Case B)')

    def _handle_key_while_marker_held(self, key_name, keyval, is_pressed):
        """
        Handle key events while marker (Space) is held.
        マーカー（スペース）が押されている間のキーイベントを処理

        ─────────────────────────────────────────────────────────────────────────
        STATE MACHINE LOGIC / 状態機械ロジック
        ─────────────────────────────────────────────────────────────────────────

        ┌─────────────────────┐
        │     MARKER_HELD     │ Space is held, waiting for first key
        │    （マーカー保持）   │ スペースが押されている、最初のキーを待つ
        └──────────┬──────────┘
                   │ key1↓
                   ▼
        ┌─────────────────────┐
        │    FIRST_PRESSED    │ First key pressed, waiting for release
        │   （1キー目押下）    │ 1キー目押下、離上を待つ
        └──────────┬──────────┘
                   │ key1↑ (all keys released)
                   ▼
        ┌─────────────────────┐
        │   FIRST_RELEASED    │ Decision point: key2↓→kanchoku, space↑→bunsetsu
        │   （1キー目離上）    │ 判定点: key2↓→漢直, space↑→文節
        └──────────┬──────────┘
                   │ key2↓
                   ▼
        ┌─────────────────────┐
        │ KANCHOKU_SECOND_    │ Kanchoku confirmed, output kanji
        │ PRESSED（漢直確定）  │ 漢直確定、漢字を出力
        └─────────────────────┘

        ─────────────────────────────────────────────────────────────────────────
        SPECIAL HANDLING BY STATE / 状態別の特殊処理
        ─────────────────────────────────────────────────────────────────────────

        MARKER_HELD + key1↓:
        ────────────────────
        • If CONVERTING: Commit current candidate immediately (space+key confirms)
          変換中: 現在の候補を即座に確定（space+key で確定）
        • If BUNSETSU: Perform implicit conversion immediately (no visual gap)
          文節入力: 暗黙変換を即座に実行（視覚的な隙間なし）
        • If FORCED_PREEDIT: Keep preedit visible (kanchoku needs to see it)
          強制入力: プリエディットを表示し続ける（漢直が必要とする）
        • If IDLE: Save preedit for potential restoration
          通常: 潜在的な復元のためにプリエディットを保存

        FIRST_RELEASED + key2↓:
        ────────────────────────
        • Kanchoku blocking rule: In normal bunsetsu mode, kanchoku is BLOCKED.
          漢直ブロッキングルール: 通常文節モードでは漢直はブロックされる。
        • Only in forced-preedit mode can kanchoku be used within preedit.
          強制プリエディットモードでのみ、プリエディット内で漢直が使用可能。

        Args:
            key_name: IBus.keyval_name()から取得したキー名
            keyval: キー値
            is_pressed: キー押下ならTrue、離上ならFalse

        Returns:
            bool: キーが消費された場合True、そうでなければFalse
        """
        # Only process printable ASCII characters
        if keyval < 0x20 or keyval > 0x7e:
            return False

        key_char = chr(keyval).lower()

        if self._marker_state == MarkerState.MARKER_HELD:
            # Waiting for first key
            if is_pressed:
                self._marker_first_key = key_char
                self._marker_keys_held.add(key_char)
                self._marker_had_input = True

                # If in CONVERTING state, now we know it's space+key (not a tap),
                # so commit the current candidate directly and exit conversion mode
                if self._in_conversion:
                    logger.debug(f'Committing candidate for new bunsetsu: "{self._preedit_string}"')
                    self.commit_text(IBus.Text.new_from_string(self._preedit_string))
                    self._preedit_string = ''
                    self._preedit_hiragana = ''
                    self._preedit_ascii = ''
                    self._preedit_before_marker = ''  # Clear to prevent double commit in release handler
                    self._in_conversion = False
                    self._lookup_table.clear()
                    self.hide_lookup_table()
                elif self._bunsetsu_active:
                    # BUNSETSU state: perform implicit conversion immediately
                    # so the converted text is committed without visual gap
                    yomi = self._preedit_string
                    if yomi:
                        candidates = self._henkan_processor.convert(yomi)
                        if candidates:
                            surface = candidates[0]['surface']
                            logger.debug(f'Immediate implicit conversion: "{yomi}" → "{surface}"')
                            self.commit_text(IBus.Text.new_from_string(surface))
                        else:
                            logger.debug(f'No candidates, committing yomi: "{yomi}"')
                            self.commit_text(IBus.Text.new_from_string(yomi))
                    # Clear preedit for fresh start with new bunsetsu
                    self._preedit_string = ''
                    self._preedit_hiragana = ''
                    self._preedit_ascii = ''
                    self._preedit_before_marker = ''  # Clear to prevent double commit in release handler
                    self._bunsetsu_active = False
                elif self._in_forced_preedit:
                    # FORCED_PREEDIT state: save preedit for conversion on release.
                    # DO NOT clear buffers here - kanchoku needs the preedit to stay visible.
                    # The old content will be stripped in _handle_marker_release_decision().
                    self._preedit_before_marker = self._preedit_string
                else:
                    # IDLE state: commit any existing preedit (e.g., from prior kanchoku)
                    # before starting a new bunsetsu sequence. This ensures kanchoku kanji
                    # are committed and don't get mixed into the new bunsetsu.
                    if self._preedit_string:
                        logger.debug(f'Committing prior preedit before new bunsetsu: "{self._preedit_string}"')
                        self.commit_text(IBus.Text.new_from_string(self._preedit_string))
                        self._preedit_string = ''
                        self._preedit_hiragana = ''
                        self._preedit_ascii = ''
                    self._preedit_before_marker = ''

                # Let simultaneous processor handle this key (tentative output)
                self._process_simultaneous_input(keyval, is_pressed)
                self._marker_state = MarkerState.FIRST_PRESSED
                logger.debug(f'First key pressed: "{key_char}" → FIRST_PRESSED')
            else:
                # Key release while waiting for first key - this can happen when user
                # releases a key from previous input after pressing marker (space).
                # Process the release to finalize the character in simultaneous processor.
                logger.debug(f'Key released in MARKER_HELD (prior input): "{key_char}"')
                self._process_simultaneous_input(keyval, is_pressed)
                # Update saved preedit to include the finalized character
                self._preedit_before_marker = self._preedit_string
            return True

        elif self._marker_state == MarkerState.FIRST_PRESSED:
            # First key is pressed, waiting for release
            if is_pressed:
                # Another key pressed while first is held (could be simultaneous)
                self._marker_keys_held.add(key_char)
                self._process_simultaneous_input(keyval, is_pressed)
            else:
                # A key released
                self._marker_keys_held.discard(key_char)
                self._process_simultaneous_input(keyval, is_pressed)
                if len(self._marker_keys_held) == 0:
                    # All keys released - transition to decision point
                    self._marker_state = MarkerState.FIRST_RELEASED
                    logger.debug('All keys released → FIRST_RELEASED (decision point)')
            return True

        elif self._marker_state == MarkerState.FIRST_RELEASED:
            # Decision point: waiting for key2 (kanchoku) or marker release (bunsetsu)
            if is_pressed:
                # Check if kanchoku is allowed in current state
                # Kanchoku is BLOCKED in normal bunsetsu mode (but allowed in forced preedit)
                if self._bunsetsu_active and not self._in_forced_preedit:
                    # In normal bunsetsu mode - kanchoku is NOT allowed
                    # Ignore this key press and stay in FIRST_RELEASED state
                    logger.debug(f'Kanchoku blocked in bunsetsu mode, ignoring key: "{key_char}"')
                    return True

                # Second key pressed - this is KANCHOKU (Case A)!
                logger.debug(f'Second key pressed: "{key_char}" → KANCHOKU')
                # Undo the tentative simultaneous output
                self._preedit_string = self._preedit_before_marker
                # Clear hiragana/ascii buffers to prevent stale data from affecting
                # subsequent input. Kanchoku kanji only exist in _preedit_string.
                self._preedit_hiragana = ''
                self._preedit_ascii = ''
                # Look up and emit kanchoku kanji
                kanji = self._kanchoku_processor._lookup_kanji(self._marker_first_key, key_char)
                self._emit_kanchoku_output(kanji)
                self._marker_keys_held.add(key_char)
                self._marker_state = MarkerState.KANCHOKU_SECOND_PRESSED
            return True

        elif self._marker_state == MarkerState.KANCHOKU_SECOND_PRESSED:
            # Second key pressed, waiting for release (then ready for another kanchoku)
            if is_pressed:
                # Another key while second is held - ignore or handle as needed
                pass
            else:
                # Key released
                self._marker_keys_held.discard(key_char)
                if len(self._marker_keys_held) == 0:
                    # Ready for another kanchoku sequence
                    self._marker_state = MarkerState.MARKER_HELD
                    self._marker_first_key = None
                    self._preedit_before_marker = self._preedit_string
                    logger.debug('Kanchoku complete, ready for next → MARKER_HELD')
            return True

        return False

    def _process_simultaneous_input(self, keyval, is_pressed):
        """
        Process a key through the simultaneous input processor.
        同時打鍵プロセッサを通してキーを処理

        ─────────────────────────────────────────────────────────────────────────
        PURPOSE / 目的
        ─────────────────────────────────────────────────────────────────────────
        During marker-held sequences (space+key), we need to provide immediate
        visual feedback to the user. This function passes the key through the
        simultaneous input processor to generate "tentative output".

        マーカー保持シーケンス（space+key）中、ユーザーに即座の視覚的フィードバックを
        提供する必要がある。この関数はキーを同時打鍵プロセッサに渡して
        「仮出力」を生成する。

        ─────────────────────────────────────────────────────────────────────────
        TENTATIVE OUTPUT / 仮出力
        ─────────────────────────────────────────────────────────────────────────
        The output is "tentative" because:
        出力が「仮」である理由:

        • If this becomes a BUNSETSU (space+key1+space↑):
          - The tentative output is KEPT as the start of the new bunsetsu
          - 仮出力は新しい文節の開始として保持される

        • If this becomes KANCHOKU (space+key1+key2):
          - The tentative output is DISCARDED and replaced with kanji
          - 仮出力は破棄され、漢字で置き換えられる

        Example / 例:
        - User types: space↓ → 'i'↓
        - Tentative output: "い"
        - If 'j'↓ follows: discard "い", output kanchoku kanji for ('i','j')
        - If space↑ follows: keep "い" as bunsetsu start
        """
        if keyval < 0x20 or keyval > 0x7e:
            return

        input_char = chr(keyval)

        # Get output from simultaneous processor
        output, pending = self._simul_processor.get_layout_output(
            self._preedit_string, input_char, is_pressed
        )

        logger.debug(f'Simultaneous processor: output="{output}", pending="{pending}"')

        # Update preedit with simultaneous output
        self._preedit_hiragana = output if output else ''
        new_preedit = self._preedit_hiragana + (pending if pending else '')
        self._preedit_string = new_preedit
        self._update_preedit()

    def _mark_bunsetsu_boundary(self):
        """
        Mark the start of a bunsetsu (phrase) for kana-kanji conversion.
        文節（句）の開始をかな漢字変換用にマーク

        ─────────────────────────────────────────────────────────────────────────
        WHAT IS BUNSETSU? / 文節とは？
        ─────────────────────────────────────────────────────────────────────────
        A bunsetsu (文節) is a minimal meaningful phrase unit in Japanese,
        typically consisting of a content word (名詞, 動詞, etc.) plus any
        attached particles (助詞) or auxiliary verbs (助動詞).

        文節とは日本語における最小の意味のある句単位で、通常は内容語
        （名詞、動詞など）に付属する助詞や助動詞を含む。

        Examples / 例:
        • "今日は" (きょうは) - noun + particle
        • "食べました" (たべました) - verb + auxiliary verb
        • "美しい" (うつくしい) - adjective

        ─────────────────────────────────────────────────────────────────────────
        EFFECT / 効果
        ─────────────────────────────────────────────────────────────────────────
        Sets _bunsetsu_active = True, which:
        _bunsetsu_active = True を設定、これにより:

        1. Changes preedit styling (underline to indicate pending conversion)
           プリエディットのスタイル変更（下線で変換待ちを示す）
        2. Enables conversion via space tap
           スペースタップで変換を有効化
        3. Enables implicit conversion via space+key
           space+key で暗黙変換を有効化
        """
        self._bunsetsu_active = True
        self._conversion_yomi = ''  # Will be populated from preedit when conversion triggers
        logger.debug(f'Bunsetsu started. Current preedit: "{self._preedit_string}"')

    def _emit_kanchoku_output(self, kanji):
        """
        Output a kanji from kanchoku (direct kanji) input.
        漢直（直接漢字入力）からの漢字を出力

        ─────────────────────────────────────────────────────────────────────────
        WHAT IS KANCHOKU? / 漢直とは？
        ─────────────────────────────────────────────────────────────────────────
        Kanchoku (漢直) is a direct kanji input method where each kanji is
        mapped to a two-key combination. The user holds the marker key (Space)
        and types two keys to produce a kanji directly, bypassing kana input.

        漢直とは各漢字が2キーの組み合わせにマッピングされる直接漢字入力方式。
        ユーザーはマーカーキー（スペース）を押しながら2キーを打つことで、
        かな入力をバイパスして直接漢字を生成する。

        Example / 例: space+j+k → "漢"

        ─────────────────────────────────────────────────────────────────────────
        BUFFER BEHAVIOR / バッファの動作
        ─────────────────────────────────────────────────────────────────────────
        IMPORTANT: Kanchoku kanji are added ONLY to _preedit_string.
        They are NOT added to _preedit_hiragana or _preedit_ascii.

        重要: 漢直漢字は _preedit_string にのみ追加される。
        _preedit_hiragana や _preedit_ascii には追加されない。

        This means:
        これは以下を意味する:
        • Converting to katakana (Ctrl+K) will lose kanchoku kanji
          カタカナ変換（Ctrl+K）で漢直漢字は失われる
        • Converting to ASCII (Ctrl+J) will lose kanchoku kanji
          ASCII変換（Ctrl+J）で漢直漢字は失われる
        • This is by design - users understand kanchoku bypasses conversion
          これは意図的 - ユーザーは漢直が変換をバイパスすることを理解している
        """
        logger.debug(f'Kanchoku output: "{kanji}"')
        self._preedit_string += kanji
        self._update_preedit()

    # =========================================================================
    # HENKAN (KANA-KANJI CONVERSION) METHODS
    # =========================================================================

    def _trigger_conversion(self):
        """
        Trigger kana-kanji conversion on the current preedit (yomi).
        現在のプリエディット（読み）のかな漢字変換を実行

        ─────────────────────────────────────────────────────────────────────────
        WHEN CALLED / 呼び出しタイミング
        ─────────────────────────────────────────────────────────────────────────
        Called when space is tapped in BUNSETSU_ACTIVE or FORCED_PREEDIT state.
        Uses HenkanProcessor to look up candidates and convert the preedit
        to the first (highest priority) candidate.

        BUNSETSU_ACTIVE または FORCED_PREEDIT 状態でスペースをタップした時に呼ばれる。
        HenkanProcessor を使って候補を検索し、プリエディットを最初の
        （最高優先度の）候補に変換する。

        ─────────────────────────────────────────────────────────────────────────
        CONVERSION MODES / 変換モード
        ─────────────────────────────────────────────────────────────────────────

        Whole-word mode (単語変換モード):
        ────────────────────────────────
        When a dictionary match is found for the entire yomi.
        読み全体に対して辞書マッチが見つかった場合。

        Example / 例: "かんじ" → [漢字, 感じ, 幹事, ...]
                     First candidate displayed, lookup table hidden.
                     最初の候補が表示され、ルックアップテーブルは非表示。

        Bunsetsu mode (文節変換モード):
        ───────────────────────────────
        When no exact match exists, CRF predicts bunsetsu boundaries.
        Each bunsetsu is converted independently with its own candidates.

        完全一致がない場合、CRFが文節境界を予測する。
        各文節は独立して変換され、それぞれの候補を持つ。

        Example / 例: "きょうはいいてんきですね"
                     → ["今日", "は", "いい", "天気", "です", "ね"]
                     Each bunsetsu can be cycled independently.
                     各文節は独立して切り替え可能。

        ─────────────────────────────────────────────────────────────────────────
        LOOKUP TABLE BEHAVIOR / ルックアップテーブルの動作
        ─────────────────────────────────────────────────────────────────────────
        The lookup table is NOT shown on first conversion (this differs from
        traditional SKK/ATOK). It only appears on 2nd space press via _cycle_candidate.
        This provides a cleaner UX for single-candidate words.

        ルックアップテーブルは最初の変換では表示されない（従来のSKK/ATOKとは異なる）。
        _cycle_candidate 経由で2回目のスペース押下時にのみ表示される。
        これは単一候補の単語に対してよりクリーンなUXを提供する。
        """
        if not self._preedit_string:
            logger.debug('_trigger_conversion: empty preedit, nothing to convert')
            return

        # Use hiragana as yomi for conversion
        self._conversion_yomi = self._preedit_hiragana if self._preedit_hiragana else self._preedit_string
        logger.debug(f'_trigger_conversion: yomi="{self._conversion_yomi}"')

        # Get candidates from HenkanProcessor
        # This will automatically enter bunsetsu mode if no dictionary match
        candidates = self._henkan_processor.convert(self._conversion_yomi)

        if not candidates:
            # No candidates found - keep yomi as-is
            logger.debug('_trigger_conversion: no candidates found')
            return

        # Enter conversion mode
        self._in_conversion = True
        self._bunsetsu_active = False

        # Check if we're in bunsetsu mode (automatic fallback when no dictionary match)
        if self._henkan_processor.is_bunsetsu_mode():
            # Bunsetsu mode: display combined surface, hide lookup table
            self._preedit_string = self._henkan_processor.get_display_surface()
            self._update_preedit()
            self.hide_lookup_table()
            logger.debug(f'_trigger_conversion: bunsetsu mode, surface="{self._preedit_string}", '
                        f'{self._henkan_processor.get_bunsetsu_count()} bunsetsu')
        else:
            # Whole-word mode: populate and show lookup table
            self._lookup_table.clear()
            for candidate in candidates:
                self._lookup_table.append_candidate(
                    IBus.Text.new_from_string(candidate['surface'])
                )

            self._preedit_string = candidates[0]['surface']
            self._update_preedit()

            # Don't show lookup table on first conversion
            # Lookup table will be shown on 2nd space (in _cycle_candidate)
            self.hide_lookup_table()
            logger.debug(f'_trigger_conversion: {len(candidates)} candidate(s), lookup table hidden')

    def _cycle_candidate(self):
        """
        Cycle to the next conversion candidate.
        次の変換候補に切り替え

        ─────────────────────────────────────────────────────────────────────────
        WHEN CALLED / 呼び出しタイミング
        ─────────────────────────────────────────────────────────────────────────
        • Space tap in CONVERTING state (2nd+ space press)
          変換中状態でのスペースタップ（2回目以降のスペース押下）
        • Down arrow in CONVERTING state
          変換中状態での下矢印キー

        ─────────────────────────────────────────────────────────────────────────
        BEHAVIOR BY MODE / モード別の動作
        ─────────────────────────────────────────────────────────────────────────

        Whole-word mode / 単語変換モード:
        ─────────────────────────────────
        Cycles through the lookup table sequentially:
        [漢字] → [感じ] → [幹事] → [漢字] → ...
        Shows lookup table after first cycle.

        ルックアップテーブルを順に切り替え:
        最初のサイクル後にルックアップテーブルを表示。

        Bunsetsu mode / 文節変換モード:
        ─────────────────────────────────
        Cycles candidates for the CURRENTLY SELECTED bunsetsu only.
        Other bunsetsu remain unchanged.

        現在選択中の文節の候補のみを切り替え。
        他の文節は変更されない。

        Use Left/Right arrows to move between bunsetsu.
        文節間の移動には左右矢印キーを使用。
        """
        if not self._in_conversion:
            return

        if self._henkan_processor.is_bunsetsu_mode():
            # Bunsetsu mode: cycle candidates for selected bunsetsu
            new_candidate = self._henkan_processor.next_bunsetsu_candidate()
            if new_candidate:
                # Update combined display surface
                self._preedit_string = self._henkan_processor.get_display_surface()
                self._update_preedit()
                logger.debug(f'_cycle_candidate (bunsetsu): selected "{new_candidate["surface"]}" '
                           f'for bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
            else:
                # Passthrough bunsetsu has no alternatives
                logger.debug('_cycle_candidate (bunsetsu): passthrough bunsetsu, no alternatives')
        else:
            # Whole-word mode: use lookup table
            self._lookup_table.cursor_down()

            cursor_pos = self._lookup_table.get_cursor_pos()
            candidate = self._lookup_table.get_candidate(cursor_pos)
            if candidate:
                self._preedit_string = candidate.get_text()
                self._update_preedit()
                # Show lookup table if multiple candidates
                if self._lookup_table.get_number_of_candidates() > 1:
                    self.update_lookup_table(self._lookup_table, True)
                logger.debug(f'_cycle_candidate: selected "{self._preedit_string}" (index {cursor_pos})')

    def _cycle_candidate_backward(self):
        """
        Cycle to the previous conversion candidate.

        Called when Up arrow is pressed in CONVERTING state.
        In bunsetsu mode, cycles candidates backward for the currently selected bunsetsu.
        """
        if not self._in_conversion:
            return

        if self._henkan_processor.is_bunsetsu_mode():
            # Bunsetsu mode: cycle candidates backward for selected bunsetsu
            new_candidate = self._henkan_processor.previous_bunsetsu_candidate()
            if new_candidate:
                # Update combined display surface
                self._preedit_string = self._henkan_processor.get_display_surface()
                self._update_preedit()
                logger.debug(f'_cycle_candidate_backward (bunsetsu): selected "{new_candidate["surface"]}" '
                           f'for bunsetsu {self._henkan_processor.get_selected_bunsetsu_index()}')
            else:
                # Passthrough bunsetsu has no alternatives
                logger.debug('_cycle_candidate_backward (bunsetsu): passthrough bunsetsu, no alternatives')
        else:
            # Whole-word mode: use lookup table
            self._lookup_table.cursor_up()

            cursor_pos = self._lookup_table.get_cursor_pos()
            candidate = self._lookup_table.get_candidate(cursor_pos)
            if candidate:
                self._preedit_string = candidate.get_text()
                self._update_preedit()
                # Show lookup table if multiple candidates
                if self._lookup_table.get_number_of_candidates() > 1:
                    self.update_lookup_table(self._lookup_table, True)
                logger.debug(f'_cycle_candidate_backward: selected "{self._preedit_string}" (index {cursor_pos})')

    def _cancel_conversion(self):
        """
        Cancel conversion and revert to the original yomi.

        Called when Escape or Backspace is pressed in CONVERTING state.

        Behavior differs based on mode:
        - Normal bunsetsu: Revert to yomi and stay in bunsetsu mode for editing
        - Forced preedit: Exit entirely (Escape cancels forced preedit completely)
        """
        if not self._in_conversion:
            return

        if self._in_forced_preedit:
            # In forced preedit mode: Escape exits entirely (per user spec)
            logger.debug('_cancel_conversion: exiting forced preedit mode entirely')
            self._reset_henkan_state()
        else:
            # Normal bunsetsu: revert to yomi and stay in bunsetsu mode
            self._preedit_string = self._conversion_yomi
            self._preedit_hiragana = self._conversion_yomi
            self._in_conversion = False
            self._bunsetsu_active = True  # Go back to bunsetsu mode
            self._lookup_table.clear()
            self.hide_lookup_table()
            self._update_preedit()
            logger.debug(f'_cancel_conversion: reverted to yomi "{self._conversion_yomi}"')

    def _confirm_conversion(self):
        """
        Confirm the currently selected conversion candidate.

        Commits the selected candidate and resets henkan state.
        """
        if self._in_conversion and self._preedit_string:
            logger.debug(f'_confirm_conversion: committing "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))

        # Reset all henkan state
        self._reset_henkan_state()

    def _commit_with_implicit_conversion(self):
        """
        Perform implicit conversion and commit.

        Called when user performs an action that should commit the current state:
        - In BUNSETSU_ACTIVE: convert and commit first candidate
        - In CONVERTING: commit the currently selected candidate

        This implements "Option B" behavior where space+key implicitly
        converts and commits before starting a new action.
        """
        if self._in_conversion:
            # Already in conversion - commit the selected candidate
            logger.debug(f'_commit_with_implicit_conversion: committing selected "{self._preedit_string}"')
            self.commit_text(IBus.Text.new_from_string(self._preedit_string))
        elif self._bunsetsu_active:
            # In bunsetsu mode - perform conversion and commit first candidate
            yomi = self._preedit_hiragana if self._preedit_hiragana else self._preedit_string
            if yomi:
                candidates = self._henkan_processor.convert(yomi)
                if candidates:
                    # Commit first candidate
                    surface = candidates[0]['surface']
                    logger.debug(f'_commit_with_implicit_conversion: converting "{yomi}" → "{surface}"')
                    self.commit_text(IBus.Text.new_from_string(surface))
                else:
                    # No candidates - commit yomi as-is
                    logger.debug(f'_commit_with_implicit_conversion: no candidates, committing yomi "{yomi}"')
                    self.commit_text(IBus.Text.new_from_string(yomi))

        # Reset henkan state
        self._reset_henkan_state()

    def _reset_henkan_state(self):
        """
        Reset all henkan-related state variables.

        Called after conversion is confirmed or cancelled.
        """
        self._bunsetsu_active = False
        self._in_conversion = False
        self._in_forced_preedit = False
        self._converted = False
        self._conversion_yomi = ''
        self._preedit_string = ''
        self._preedit_hiragana = ''
        self._preedit_ascii = ''
        self._lookup_table.clear()
        self.hide_lookup_table()
        self._update_preedit()
        logger.debug('_reset_henkan_state: state cleared')

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _commit_string(self):
        """
        Commit preedit to the application and clear all buffers.
        プリエディットをアプリケーションに確定し、全バッファをクリア

        ─────────────────────────────────────────────────────────────────────────
        IMPORTANT: ORDER OF OPERATIONS / 重要: 操作順序
        ─────────────────────────────────────────────────────────────────────────
        The preedit display is cleared BEFORE calling commit_text(). This is
        critical to avoid a race condition:

        プリエディット表示は commit_text() 呼び出し前にクリアされる。
        これは競合状態を避けるために重要:

        1. commit_text() does not auto-clear COMMIT-mode preedit
           commit_text() は COMMIT モードのプリエディットを自動クリアしない
        2. A forwarded key event (return False) could arrive at the client
           before the preedit-clear signal
           転送されたキーイベント（return False）がプリエディットクリア
           シグナルより前にクライアントに届く可能性がある
        3. This could cause the client to auto-commit preedit (double output)
           これによりクライアントがプリエディットを自動確定する可能性（二重出力）

        ─────────────────────────────────────────────────────────────────────────
        BUFFERS CLEARED / クリアされるバッファ
        ─────────────────────────────────────────────────────────────────────────
        • _preedit_string: Display buffer / 表示バッファ
        • _preedit_hiragana: Hiragana source / ひらがなソース
        • _preedit_ascii: ASCII source / ASCIIソース
        • _converted: Conversion flag / 変換フラグ
        """
        if self._preedit_string:
            logger.debug(f'Committing: "{self._preedit_string}"')
            # Save the text to commit before clearing buffers
            text_to_commit = self._preedit_string
            # Clear preedit display FIRST to avoid race condition:
            # commit_text() does not auto-clear the COMMIT-mode preedit,
            # so a forwarded key event (return False) could arrive at the
            # client before the preedit-clear signal, causing the client
            # to auto-commit the preedit as well (double output).
            self._preedit_string = ""
            self._preedit_hiragana = ""
            self._preedit_ascii = ""
            self._converted = False
            self._update_preedit()
            self.commit_text(IBus.Text.new_from_string(text_to_commit))

    def _parse_hex_color(self, color_str):
        """
        Parse a hex color string to an integer value for IBus attributes.

        Args:
            color_str: Color string in format "0xRRGGBB" or "RRGGBB"

        Returns:
            int: Color value as integer, or None if parsing fails
        """
        if not color_str:
            return None
        try:
            # Strip "0x" or "0X" prefix if present
            color_str = color_str.strip()
            if color_str.lower().startswith('0x'):
                color_str = color_str[2:]
            return int(color_str, 16)
        except (ValueError, AttributeError):
            logger.warning(f'Failed to parse color value: {color_str}')
            return None

    def _update_preedit(self):
        """
        Update the preedit display in the application.
        アプリケーション内のプリエディット表示を更新

        ─────────────────────────────────────────────────────────────────────────
        WHAT IS PREEDIT? / プリエディットとは？
        ─────────────────────────────────────────────────────────────────────────
        The preedit is the text being composed before it's committed to the
        application. In Japanese IMEs, this is typically hiragana that hasn't
        been converted or is waiting for conversion.

        プリエディットは、アプリケーションに確定される前に構成中のテキスト。
        日本語IMEでは、通常、変換されていない、または変換待ちのひらがな。

        ─────────────────────────────────────────────────────────────────────────
        VISUAL STYLES BY STATE / 状態別の視覚スタイル
        ─────────────────────────────────────────────────────────────────────────

        ┌─────────────────┬───────────────────────────────────────────────────────┐
        │ State / 状態     │ Styling / スタイル                                    │
        ├─────────────────┼───────────────────────────────────────────────────────┤
        │ IDLE (stealth)  │ No styling - appears as committed text                │
        │ 通常（ステルス） │ スタイルなし - 確定済みテキストのように見える          │
        ├─────────────────┼───────────────────────────────────────────────────────┤
        │ BUNSETSU        │ Single underline + background color                   │
        │ 文節入力         │ 単線下線 + 背景色                                     │
        ├─────────────────┼───────────────────────────────────────────────────────┤
        │ CONVERTING      │ Selected: double underline + background              │
        │ (bunsetsu mode) │ Non-selected: single underline                        │
        │ 変換中（文節）   │ 選択中: 二重下線 + 背景、非選択: 単線下線             │
        ├─────────────────┼───────────────────────────────────────────────────────┤
        │ CONVERTING      │ Single underline + foreground/background colors       │
        │ (whole-word)    │                                                       │
        │ 変換中（単語）   │ 単線下線 + 前景/背景色                                │
        └─────────────────┴───────────────────────────────────────────────────────┘

        ─────────────────────────────────────────────────────────────────────────
        STEALTH MODE / ステルスモード
        ─────────────────────────────────────────────────────────────────────────
        In IDLE mode with logging level above DEBUG, the preedit has NO visual
        styling (UNDERLINE_NONE). This makes the text appear as if it's already
        committed, providing a less intrusive typing experience. This is called
        "stealth preedit".

        IDLEモードでログレベルがDEBUGより上の場合、プリエディットは視覚スタイル
        なし（UNDERLINE_NONE）になる。これによりテキストは既に確定されたように
        見え、より邪魔にならない入力体験を提供する。これを「ステルスプリエディット」
        と呼ぶ。

        In DEBUG mode, underline is always shown for development visibility.
        DEBUGモードでは、開発時の可視性のため常に下線が表示される。
        """
        if self._preedit_string:
            preedit_text = IBus.Text.new_from_string(self._preedit_string)
            attrs = IBus.AttrList()
            preedit_len = len(self._preedit_string)

            # In IDLE mode (not bunsetsu, forced-preedit, or conversion) with
            # log-level above DEBUG, render the preedit without any visual
            # styling so it appears as if already committed.  In DEBUG mode
            # the underline/background is kept for development visibility.
            is_idle = (not self._bunsetsu_active
                       and not self._in_forced_preedit
                       and not self._in_conversion)
            stealth = is_idle and self._logging_level != 'DEBUG'

            # Check if we're in bunsetsu mode for special display handling
            in_bunsetsu_mode = (self._in_conversion and
                               self._henkan_processor.is_bunsetsu_mode())

            if stealth:
                # Explicitly set UNDERLINE_NONE to override the default
                # preedit underline that GTK/IBus clients add automatically.
                attrs.append(IBus.Attribute.new(
                    IBus.AttrType.UNDERLINE,
                    IBus.AttrUnderline.NONE,
                    0,
                    preedit_len
                ))
                logger.debug('Stealth preedit: no styling in IDLE mode')
            elif in_bunsetsu_mode:
                # Bunsetsu mode: show selected bunsetsu with double underline,
                # non-selected bunsetsu with single underline
                bunsetsu_segments = self._henkan_processor.get_display_surface_with_selection()
                pos = 0
                for surface, is_selected in bunsetsu_segments:
                    segment_len = len(surface)
                    if segment_len == 0:
                        continue

                    # Set underline style based on selection
                    underline_style = (IBus.AttrUnderline.DOUBLE if is_selected
                                      else IBus.AttrUnderline.SINGLE)
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.UNDERLINE,
                        underline_style,
                        pos,
                        pos + segment_len
                    ))

                    # Apply background color to selected bunsetsu for better visibility
                    if is_selected:
                        selected_bg = self._parse_hex_color(
                            self._config.get('preedit_background_color', '0xd1eaff')
                        )
                        if selected_bg is not None:
                            attrs.append(IBus.Attribute.new(
                                IBus.AttrType.BACKGROUND,
                                selected_bg,
                                pos,
                                pos + segment_len
                            ))

                    pos += segment_len

                logger.debug(f'Bunsetsu mode preedit: {len(bunsetsu_segments)} segments, '
                           f'selected={self._henkan_processor.get_selected_bunsetsu_index()}')
            elif self._config.get('use_ibus_hint_colors', False):
                # Use IBus AttrType.HINT for theme-based styling (requires IBus >= 1.5.33)
                # AttrPreedit.WHOLE (1) indicates the entire preedit text
                try:
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.HINT,
                        1,  # IBus.AttrPreedit.WHOLE
                        0,
                        preedit_len
                    ))
                    logger.debug('Using IBus HINT styling for preedit')
                except Exception as e:
                    logger.warning(f'Failed to apply HINT attribute (IBus >= 1.5.33 required): {e}')
                    # Fall back to underline
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.UNDERLINE,
                        IBus.AttrUnderline.SINGLE,
                        0,
                        preedit_len
                    ))
            else:
                # Use explicit foreground and background colors from config
                fg_color = self._parse_hex_color(
                    self._config.get('preedit_foreground_color', '0x000000')
                )
                bg_color = self._parse_hex_color(
                    self._config.get('preedit_background_color', '0xd1eaff')
                )

                # Add foreground color attribute
                if fg_color is not None:
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.FOREGROUND,
                        fg_color,
                        0,
                        preedit_len
                    ))

                # Add background color attribute
                if bg_color is not None:
                    attrs.append(IBus.Attribute.new(
                        IBus.AttrType.BACKGROUND,
                        bg_color,
                        0,
                        preedit_len
                    ))

                # Also add underline for better visibility
                attrs.append(IBus.Attribute.new(
                    IBus.AttrType.UNDERLINE,
                    IBus.AttrUnderline.SINGLE,
                    0,
                    preedit_len
                ))
                # Seeing this line in the log file seemed to be just too much -- commenting out
                #logger.debug(f'Using explicit preedit colors: fg=0x{fg_color:06x}, bg=0x{bg_color:06x}')

            preedit_text.set_attributes(attrs)

            # Use COMMIT mode so preedit is committed on focus change (e.g., clicking elsewhere)
            self.update_preedit_text_with_mode(
                preedit_text,
                preedit_len,  # cursor at end
                True,  # visible
                IBus.PreeditFocusMode.COMMIT
            )
        else:
            # Hide preedit when empty
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(''),
                0,
                False,  # not visible
                IBus.PreeditFocusMode.CLEAR
            )

