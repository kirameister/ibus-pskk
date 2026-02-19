#!/usr/bin/env python3
"""
katsuyou.py - Japanese verb/adjective conjugation (活用) module
日本語動詞・形容詞の活用モジュール

================================================================================
WHY THIS MODULE EXISTS / このモジュールが存在する理由
================================================================================

PROBLEM / 問題:
───────────────
In Japanese, verbs and adjectives change their endings depending on how
they're used in a sentence. For example, the verb "書く" (kaku, "to write"):

日本語では、動詞や形容詞が文中の使われ方によって語尾が変化する。
例えば、動詞「書く」(kaku, "to write"):

    書く (kaku)     → I write / will write     辞書形（基本形）
    書いた (kaita)   → I wrote                  過去形
    書いて (kaite)   → writing / please write   て形
    書かない (kakanai) → I don't write          否定形
    書きます (kakimasu) → I write (polite)      丁寧形

If the IME dictionary only contains "かく→書く", the user would have to:
もしIME辞書に「かく→書く」しかなければ、ユーザーは:

    1. Type "かく" and convert to "書く"
       「かく」と入力して「書く」に変換
    2. Delete "く" and type the new ending
       「く」を削除して新しい語尾を入力

This is slow and frustrating!
これは遅くてイライラする！

SOLUTION / 解決策:
──────────────────
This module automatically generates ALL conjugated forms from the dictionary
form, so users can type any form directly:

このモジュールは辞書形から全ての活用形を自動生成するので、
ユーザーは任意の形を直接入力できる:

    かいた → 書いた ✓  (no manual editing needed / 手動編集不要)
    かいて → 書いて ✓
    かかない → 書かない ✓
    かきます → 書きます ✓

================================================================================
WHAT IS CONJUGATION? / 活用とは？
================================================================================

Think of conjugation like verb endings in English:
活用は英語の動詞の語尾のようなもの:

    English: walk → walked, walking, walks
    Japanese: 書く → 書いた, 書いて, 書き

But Japanese conjugation is MORE complex because:
しかし日本語の活用はより複雑:

1. MORE FORMS: Japanese has ~15 distinct forms per verb
   より多くの形: 日本語は動詞ごとに約15の異なる形がある

2. MULTIPLE VERB TYPES: Different verbs conjugate differently
   複数の動詞タイプ: 異なる動詞は異なる活用をする

3. SOUND CHANGES: Some conjugations change sounds (音便)
   音の変化: 一部の活用は音が変わる（音便）

================================================================================
VERB TYPES (FOR NON-LINGUISTS) / 動詞タイプ（非言語学者向け）
================================================================================

Japanese verbs are grouped by HOW they conjugate:
日本語動詞は活用の仕方でグループ分けされる:

┌─────────────────────────────────────────────────────────────────────────────┐
│ TYPE 1: 五段動詞 (Godan / "5-row" verbs)                                    │
│ ────────────────────────────────────────                                    │
│ The MAJORITY of Japanese verbs. The ending cycles through 5 vowel sounds.  │
│ 日本語動詞の大多数。語尾が5つの母音を巡る。                                   │
│                                                                             │
│ Example / 例: 書く (kaku)                                                   │
│   書か (kaka) ← あ段 (a-row)                                                │
│   書き (kaki) ← い段 (i-row)                                                │
│   書く (kaku) ← う段 (u-row) ← dictionary form / 辞書形                     │
│   書け (kake) ← え段 (e-row)                                                │
│   書こ (kako) ← お段 (o-row)                                                │
│                                                                             │
│ Godan verbs are further classified by their final consonant:                │
│ 五段動詞は最後の子音でさらに分類される:                                       │
│   カ行: 書く(kak-u), ガ行: 泳ぐ(oyog-u), サ行: 話す(hanas-u), etc.          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TYPE 2: 一段動詞 (Ichidan / "1-row" verbs)                                  │
│ ────────────────────────────────────────                                    │
│ SIMPLER conjugation - just drop る and add suffix.                          │
│ より単純な活用 - るを落として接尾辞を追加。                                   │
│                                                                             │
│ Example / 例: 食べる (taberu, "to eat")                                     │
│   食べ (tabe) + ない → 食べない (don't eat)                                  │
│   食べ (tabe) + ます → 食べます (eat, polite)                                │
│   食べ (tabe) + た → 食べた (ate)                                           │
│                                                                             │
│ All ichidan verbs end in る, but NOT all る-ending verbs are ichidan!      │
│ 全ての一段動詞は「る」で終わるが、「る」で終わる全ての動詞が一段ではない！     │
│   食べる (taberu) → ichidan (食べ + る)                                     │
│   取る (toru) → godan! (とr + う, not と + る)                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TYPE 3: 変格動詞 (Irregular verbs) - Only 2 verbs!                          │
│ ──────────────────────────────────────────────────                          │
│                                                                             │
│ する (suru, "to do") - The most common verb, highly irregular               │
│   し, さ, せ, す, すれ, しろ (multiple stems!)                               │
│                                                                             │
│ 来る (kuru, "to come") - Changes reading completely!                        │
│   く, き, こ (vowel changes in the reading)                                 │
│   来る (kuru) → 来た (kita) → 来ない (konai)                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TYPE 4: 形容詞 (i-adjectives)                                               │
│ ─────────────────────────────                                               │
│ Adjectives ending in い also conjugate!                                     │
│ 「い」で終わる形容詞も活用する！                                              │
│                                                                             │
│ Example / 例: 赤い (akai, "red")                                            │
│   赤く (akaku) → adverb form ("redly", used with verbs)                     │
│   赤かった (akakatta) → past tense ("was red")                              │
│   赤くない (akakunai) → negative ("not red")                                │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
CONJUGATION FORMS (PRACTICAL GUIDE) / 活用形（実用ガイド）
================================================================================

Instead of grammatical names, here's what each form DOES:
文法用語の代わりに、各形が何をするか:

┌──────────────┬────────────────────────────────────────────────────────────┐
│ Form Name    │ What it means / Used for                                   │
│ 形の名前      │ 意味 / 用途                                                 │
├──────────────┼────────────────────────────────────────────────────────────┤
│ 終止形       │ Dictionary form. "I do X" / "X happens"                    │
│ (しゅうしけい) │ 辞書形。「Xする」「Xが起こる」                              │
│              │ 書く = (I) write                                           │
├──────────────┼────────────────────────────────────────────────────────────┤
│ た形         │ Past tense. "I did X"                                      │
│ (たけい)      │ 過去形。「Xした」                                           │
│              │ 書いた = (I) wrote                                         │
├──────────────┼────────────────────────────────────────────────────────────┤
│ て形         │ Connecting form. "do X and...", "please do X"              │
│ (てけい)      │ 接続形。「Xして...」「Xしてください」                        │
│              │ 書いて = write and... / please write                       │
├──────────────┼────────────────────────────────────────────────────────────┤
│ ない形       │ Negative. "I don't do X"                                   │
│ (ないけい)    │ 否定形。「Xしない」                                         │
│              │ 書かない = (I) don't write                                 │
├──────────────┼────────────────────────────────────────────────────────────┤
│ ます形       │ Polite form. "I do X" (formal speech)                      │
│ (ますけい)    │ 丁寧形。「Xします」（丁寧語）                                │
│              │ 書きます = (I) write (polite)                              │
├──────────────┼────────────────────────────────────────────────────────────┤
│ ば形         │ Conditional. "If X happens"                                │
│ (ばけい)      │ 条件形。「Xすれば」                                         │
│              │ 書けば = if (I) write                                      │
├──────────────┼────────────────────────────────────────────────────────────┤
│ たい形       │ Desire. "I want to do X"                                   │
│ (たいけい)    │ 願望形。「Xしたい」                                         │
│              │ 書きたい = (I) want to write                               │
├──────────────┼────────────────────────────────────────────────────────────┤
│ 命令形       │ Command. "Do X!"                                           │
│ (めいれいけい) │ 命令形。「Xしろ！」                                         │
│              │ 書け = Write!                                              │
├──────────────┼────────────────────────────────────────────────────────────┤
│ られる形     │ Passive/Potential. "X is done" or "can do X"               │
│ (られるけい)  │ 受身/可能形。「Xされる」「Xできる」                          │
│              │ 書かれる = is written / 食べられる = can eat               │
├──────────────┼────────────────────────────────────────────────────────────┤
│ させる形     │ Causative. "Make someone do X"                             │
│ (させるけい)  │ 使役形。「Xさせる」                                         │
│              │ 書かせる = make (someone) write                            │
└──────────────┴────────────────────────────────────────────────────────────┘

================================================================================
SOUND CHANGES (音便) / EUPHONIC CHANGES
================================================================================

Some conjugations change sounds to make pronunciation easier:
一部の活用は発音を容易にするために音が変わる:

書く (kaku) → 書いて (kaite)  NOT *書きて (kakite)
     └───────────────────────────────┘
     き→い: This is called イ音便 (i-onbin)
            「イ音便」と呼ばれる

泳ぐ (oyogu) → 泳いで (oyoide)  NOT *泳ぎて (oyogite)
読む (yomu)  → 読んで (yonde)   NOT *読みて (yomite)
     └──────────────────────────────────────────┘
     These are different types of 音便 depending on the consonant
     子音によって異なるタイプの音便

This module handles all these sound changes automatically!
このモジュールはこれらの音変化を全て自動処理！

================================================================================
HOW THIS MODULE FITS IN THE IME / IMEにおけるこのモジュールの役割
================================================================================

    Dictionary Entry         This Module              IME Search
    辞書エントリ              このモジュール            IME検索
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │ かく → 書く  │ ──────► │ Generate    │ ──────► │ かいた→書いた│
    │ (base form) │         │ conjugations│         │ かいて→書いて│
    │ （基本形）   │         │ (活用生成)   │         │ かかない→... │
    └─────────────┘         └─────────────┘         └─────────────┘

The expanded dictionary allows direct lookup of ANY conjugated form!
展開された辞書により、任意の活用形を直接検索可能！

================================================================================
"""

import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Cost Penalties / コストペナルティ
# ============================================================================
# WHY COSTS? / なぜコスト？
# ─────────────────────────
# When multiple dictionary entries have the same reading, the IME must
# decide which one to show first. Lower cost = higher priority.
#
# 複数の辞書エントリが同じ読みを持つ場合、IMEはどれを最初に表示するか
# 決める必要がある。低いコスト = 高い優先度。
#
# Example / 例:
#   Reading "かく" matches both:
#   読み「かく」は両方にマッチ:
#     - 書く (終止形, cost +0) → appears first / 最初に表示
#     - 書か (未然形, cost +50) → appears later / 後で表示
#
# RATIONALE / 根拠:
# ─────────────────
# - 終止形/連体形 (cost 0): Dictionary form, most commonly typed
#   辞書形、最も頻繁に入力される
# - 連用形/未然形 (cost 50): Common but less than dictionary form
#   よく使われるが辞書形ほどではない
# - て形/た形 (cost 100): Very common in speech, but has sound changes
#   会話でよく使われるが、音便がある
# - Compound forms (cost 150+): Less frequently typed as-is
#   そのまま入力されることは少ない

COST_PENALTIES = {
    "終止形": 0,
    "連体形": 0,
    "連用形": 50,
    "未然形": 50,
    "仮定形": 50,
    "命令形": 50,
    "て形": 100,
    "た形": 100,
    "ない形": 150,
    "ます形": 150,
    "ば形": 150,
    "たい形": 150,
    "られる形": 200,
    "れる形": 200,
    "させる形": 200,
    "せる形": 200,
}


# ============================================================================
# Stem Extraction Rules / 語幹抽出ルール
# ============================================================================
# WHAT IS A STEM? / 語幹とは？
# ────────────────────────────
# The stem is the unchanging part of a word. Conjugation = stem + suffix.
# 語幹は単語の変化しない部分。活用 = 語幹 + 接尾辞。
#
# Example / 例:
#   書く (kaku) → stem = 書 (ka-), suffix = く (ku)
#   書かない (kakanai) = 書 (ka-) + か (ka) + ない (nai)
#          stem ──────┘     └── suffix changes!
#
# To get the stem from dictionary form:
# 辞書形から語幹を得るには:
#   1. Look up what suffix to remove (based on verb type)
#      どの接尾辞を削除するか検索（動詞タイプに基づく）
#   2. Remove it from the end
#      末尾から削除
#
# Maps conjugation type → suffix to remove / 活用型 → 削除する接尾辞

GODAN_STEM_SUFFIXES = {
    "五段-カ行": "く",
    "五段-ガ行": "ぐ",
    "五段-サ行": "す",
    "五段-タ行": "つ",
    "五段-ナ行": "ぬ",
    "五段-バ行": "ぶ",
    "五段-マ行": "む",
    "五段-ラ行": "る",
    "五段-ワア行": "う",
}

# 一段動詞 all end in る
ICHIDAN_STEM_SUFFIX = "る"

# 形容詞 end in い
KEIYOUSHI_STEM_SUFFIX = "い"


# ============================================================================
# 五段動詞 Conjugation Suffixes / 五段動詞の活用接尾辞
# ============================================================================
# HOW 五段 CONJUGATION WORKS / 五段活用の仕組み
# ──────────────────────────────────────────────
# The final consonant stays the same, but the vowel cycles through
# the 5 vowel sounds (あ, い, う, え, お). This is why it's called "5-row".
#
# 最後の子音は同じままだが、母音が5つの母音（あ、い、う、え、お）を巡る。
# これが「五段」と呼ばれる理由。
#
# Example with 書く (kak-u) / 書く (kak-u) の例:
#
#    Vowel Row    Suffix    Full Form    Meaning
#    母音段        接尾辞    完全形       意味
#    ─────────    ──────    ─────────    ───────────────────────
#    あ段 (a)     か        書か         (negative stem) 〜ない
#    い段 (i)     き        書き         (polite stem) 〜ます
#    う段 (u)     く        書く         dictionary form / 辞書形
#    え段 (e)     け        書け         conditional/imperative
#    お段 (o)     こ        書こ         volitional 〜う
#
# SOUND CHANGES (音便) / 音便
# ─────────────────────────────
# て形 and た形 have special sound changes for easier pronunciation:
# て形とた形は発音を容易にするための特殊な音変化がある:
#
#    Verb Type    Expected    Actual      Name
#    動詞タイプ    期待される   実際        名前
#    ─────────    ────────    ──────      ───────────
#    カ行 (k)     書きて      書いて      イ音便
#    ガ行 (g)     泳ぎて      泳いで      イ音便 (voiced)
#    タ/ラ/ワ行   持ちて      持って      促音便 (small っ)
#    ナ/バ/マ行   読みて      読んで      撥音便 (ん)

GODAN_SUFFIXES = {
    "カ行": {
        "未然形": "か",      # 書か-ない
        "連用形": "き",      # 書き-ます
        "終止形": "く",      # 書く
        "連体形": "く",      # 書く-とき
        "仮定形": "け",      # 書け-ば
        "命令形": "け",      # 書け
        "て形": "いて",      # 書いて (音便)
        "た形": "いた",      # 書いた (音便)
    },
    "ガ行": {
        "未然形": "が",      # 泳が-ない
        "連用形": "ぎ",      # 泳ぎ-ます
        "終止形": "ぐ",      # 泳ぐ
        "連体形": "ぐ",      # 泳ぐ-とき
        "仮定形": "げ",      # 泳げ-ば
        "命令形": "げ",      # 泳げ
        "て形": "いで",      # 泳いで (音便)
        "た形": "いだ",      # 泳いだ (音便)
    },
    "サ行": {
        "未然形": "さ",      # 話さ-ない
        "連用形": "し",      # 話し-ます
        "終止形": "す",      # 話す
        "連体形": "す",      # 話す-とき
        "仮定形": "せ",      # 話せ-ば
        "命令形": "せ",      # 話せ
        "て形": "して",      # 話して
        "た形": "した",      # 話した
    },
    "タ行": {
        "未然形": "た",      # 持た-ない
        "連用形": "ち",      # 持ち-ます
        "終止形": "つ",      # 持つ
        "連体形": "つ",      # 持つ-とき
        "仮定形": "て",      # 持て-ば
        "命令形": "て",      # 持て
        "て形": "って",      # 持って (促音便)
        "た形": "った",      # 持った (促音便)
    },
    "ナ行": {
        "未然形": "な",      # 死な-ない
        "連用形": "に",      # 死に-ます
        "終止形": "ぬ",      # 死ぬ
        "連体形": "ぬ",      # 死ぬ-とき
        "仮定形": "ね",      # 死ね-ば
        "命令形": "ね",      # 死ね
        "て形": "んで",      # 死んで (撥音便)
        "た形": "んだ",      # 死んだ (撥音便)
    },
    "バ行": {
        "未然形": "ば",      # 遊ば-ない
        "連用形": "び",      # 遊び-ます
        "終止形": "ぶ",      # 遊ぶ
        "連体形": "ぶ",      # 遊ぶ-とき
        "仮定形": "べ",      # 遊べ-ば
        "命令形": "べ",      # 遊べ
        "て形": "んで",      # 遊んで (撥音便)
        "た形": "んだ",      # 遊んだ (撥音便)
    },
    "マ行": {
        "未然形": "ま",      # 読ま-ない
        "連用形": "み",      # 読み-ます
        "終止形": "む",      # 読む
        "連体形": "む",      # 読む-とき
        "仮定形": "め",      # 読め-ば
        "命令形": "め",      # 読め
        "て形": "んで",      # 読んで (撥音便)
        "た形": "んだ",      # 読んだ (撥音便)
    },
    "ラ行": {
        "未然形": "ら",      # 取ら-ない
        "連用形": "り",      # 取り-ます
        "終止形": "る",      # 取る
        "連体形": "る",      # 取る-とき
        "仮定形": "れ",      # 取れ-ば
        "命令形": "れ",      # 取れ
        "て形": "って",      # 取って (促音便)
        "た形": "った",      # 取った (促音便)
    },
    "ワア行": {
        "未然形": "わ",      # 会わ-ない
        "連用形": "い",      # 会い-ます
        "終止形": "う",      # 会う
        "連体形": "う",      # 会う-とき
        "仮定形": "え",      # 会え-ば
        "命令形": "え",      # 会え
        "て形": "って",      # 会って (促音便)
        "た形": "った",      # 会った (促音便)
    },
}


# ============================================================================
# 一段動詞 Conjugation Suffixes / 一段動詞の活用接尾辞
# ============================================================================
# WHY "一段" (ONE-ROW)? / なぜ「一段」？
# ─────────────────────────────────────
# Unlike 五段 verbs that cycle through 5 vowels, 一段 verbs use only ONE
# vowel row - specifically, the stem always ends in the same vowel (い or え).
#
# 5つの母音を巡る五段動詞と異なり、一段動詞は1つの母音段のみを使う。
# 具体的には、語幹が常に同じ母音（い または え）で終わる。
#
# TWO SUBTYPES / 2つのサブタイプ:
# ───────────────────────────────
#   上一段 (kami-ichidan): stem ends in い-sound (before る)
#   上一段: 語幹が「い」の音で終わる（るの前）
#     Example / 例: 見る (mi-ru), 起きる (oki-ru)
#
#   下一段 (shimo-ichidan): stem ends in え-sound (before る)
#   下一段: 語幹が「え」の音で終わる（るの前）
#     Example / 例: 食べる (tabe-ru), 寝る (ne-ru)
#
# CONJUGATION IS SIMPLE / 活用は単純:
# ────────────────────────────────────
# Just remove る and add the suffix. No sound changes needed!
# るを削除して接尾辞を追加するだけ。音変化は不要！
#
#   食べる (taberu) → 食べ (tabe) + ない → 食べない
#   食べる (taberu) → 食べ (tabe) + ます → 食べます
#   食べる (taberu) → 食べ (tabe) + た → 食べた

ICHIDAN_SUFFIXES = {
    "未然形": "",           # 食べ-
    "連用形": "",           # 食べ-ます
    "終止形": "る",         # 食べる
    "連体形": "る",         # 食べる-とき
    "仮定形": "れ",         # 食べれ-ば
    "命令形_ろ": "ろ",      # 食べろ
    "命令形_よ": "よ",      # 食べよ
    "て形": "て",           # 食べて
    "た形": "た",           # 食べた
}


# ============================================================================
# 形容詞 Conjugation Suffixes / 形容詞の活用接尾辞
# ============================================================================
# ADJECTIVES CONJUGATE TOO! / 形容詞も活用する！
# ──────────────────────────────────────────────
# Unlike English adjectives ("red", "big") which never change, Japanese
# い-adjectives change their endings just like verbs.
#
# 変化しない英語の形容詞（"red"、"big"）と違い、日本語のい形容詞は
# 動詞と同様に語尾が変化する。
#
# Example with 赤い (akai, "red") / 赤い の例:
#
#   Form          Japanese      English
#   形            日本語        英語
#   ───────────   ──────────    ────────────────────────────
#   Base / 基本   赤い          (is) red
#   Adverb / 副詞  赤く          redly (becomes red)
#   Past / 過去   赤かった      was red
#   Negative      赤くない      is not red
#   Conditional   赤ければ      if (it is) red
#   て-form       赤くて        (is) red and...
#
# NOTE: な-adjectives (like 静か, 綺麗) conjugate differently and are
# handled elsewhere. This module only handles い-adjectives.
#
# 注意: な形容詞（静か、綺麗など）は異なる活用をし、別の場所で処理される。
# このモジュールはい形容詞のみを処理する。

KEIYOUSHI_SUFFIXES = {
    "連用形": "く",         # 赤く
    "終止形": "い",         # 赤い
    "連体形": "い",         # 赤い-とき
    "仮定形": "けれ",       # 赤けれ-ば
    "て形": "くて",         # 赤くて
    "た形": "かった",       # 赤かった
}


# ============================================================================
# Special Verb Handling / 特殊動詞の処理
# ============================================================================
# EXCEPTIONS TO THE RULES / ルールの例外
# ───────────────────────────────────────
# Even within verb categories, some verbs have irregular forms.
# 動詞カテゴリ内でも、一部の動詞は不規則な形を持つ。
#
# 行く (iku, "to go") is a カ行 五段 verb, BUT:
# 行く は カ行 五段動詞だが:
#
#   Expected (if regular):  行く → 行きて (*iki-te)  ← WRONG!
#   期待される（規則的なら）: 行く → 行きて ← 間違い！
#
#   Actual:                行く → 行って (it-te)    ← CORRECT
#   実際:                  行く → 行って ← 正しい

# 行く has special て形/た形 (not *行いて but 行って)
SPECIAL_TE_TA = {
    "いく": ("いって", "いった"),
    "ゆく": ("ゆって", "ゆった"),  # Alternative reading of 行く
}


# ============================================================================
# Core Functions / コア関数
# ============================================================================
# These functions form the main API of this module.
# これらの関数がこのモジュールのメインAPIを構成する。


def is_conjugatable(conj_type: str) -> bool:
    """
    Check if a conjugation type should be expanded.
    活用型を展開すべきかチェック

    ─────────────────────────────────────────────────────────────────────────
    PURPOSE / 目的
    ─────────────────────────────────────────────────────────────────────────
    Not all dictionary entries can be conjugated. This function filters:
    全ての辞書エントリが活用できるわけではない。この関数はフィルタリング:

    YES (can conjugate) / はい（活用可能）:
    • 五段-カ行, 五段-ガ行, etc. → Godan verbs
    • 上一段-*, 下一段-* → Ichidan verbs
    • サ行変格, カ行変格 → Irregular verbs
    • 形容詞 → i-adjectives

    NO (skip) / いいえ（スキップ）:
    • "*" → No conjugation info (nouns, particles, etc.)
    • 文語* → Classical Japanese (not supported yet)
    • Empty string → Invalid entry

    Args:
        conj_type: The conjugation type string from dictionary
                   辞書からの活用型文字列
                   (e.g., "五段-カ行", "下一段-バ行", "*")

    Returns:
        True if expandable, False if should be skipped
        展開可能ならTrue、スキップすべきならFalse
    """
    if not conj_type or conj_type == "*":
        return False

    # Check for known conjugatable patterns
    if conj_type in GODAN_STEM_SUFFIXES:
        return True
    if conj_type.startswith("上一段-") or conj_type.startswith("下一段-"):
        return True
    if conj_type in ("サ行変格", "カ行変格"):
        return True
    if conj_type == "形容詞":
        return True

    # Classical forms (文語) - supported but lower priority
    if conj_type.startswith("文語"):
        return False  # Skip for now, can enable later

    return False


def get_row(conj_type: str) -> str:
    """
    Extract the row (行) from a conjugation type.

    Args:
        conj_type: e.g., "五段-カ行", "下一段-バ行"

    Returns:
        The row name, e.g., "カ行", "バ行"
    """
    if "-" in conj_type:
        return conj_type.split("-", 1)[1]
    return conj_type


def extract_stem(reading: str, lemma: str, conj_type: str) -> tuple:
    """
    Extract the stem from dictionary form by removing the appropriate suffix.

    Args:
        reading: Hiragana reading (e.g., "たべる")
        lemma: Surface form / kanji (e.g., "食べる")
        conj_type: Conjugation type (e.g., "下一段-バ行")

    Returns:
        Tuple of (reading_stem, lemma_stem)
    """
    # 五段動詞
    if conj_type in GODAN_STEM_SUFFIXES:
        suffix = GODAN_STEM_SUFFIXES[conj_type]
        if reading.endswith(suffix):
            return reading[:-len(suffix)], lemma[:-1] if lemma else ""

    # 一段動詞
    if conj_type.startswith("上一段-") or conj_type.startswith("下一段-"):
        if reading.endswith(ICHIDAN_STEM_SUFFIX):
            return reading[:-1], lemma[:-1] if lemma else ""

    # サ行変格 (する verbs)
    if conj_type == "サ行変格":
        if reading.endswith("する"):
            return reading[:-2], lemma[:-2] if lemma and len(lemma) >= 2 else ""
        if reading.endswith("ずる"):
            return reading[:-2], lemma[:-2] if lemma and len(lemma) >= 2 else ""

    # カ行変格 (来る)
    if conj_type == "カ行変格":
        if reading.endswith("くる"):
            return reading[:-2], lemma[:-1] if lemma else ""

    # 形容詞
    if conj_type == "形容詞":
        if reading.endswith(KEIYOUSHI_STEM_SUFFIX):
            return reading[:-1], lemma[:-1] if lemma else ""

    # Fallback: return as-is
    return reading, lemma


def generate_conjugations(reading: str, lemma: str, pos: str, conj_type: str,
                          base_cost: float) -> list:
    """
    Generate all conjugated forms for a given dictionary entry.
    辞書エントリの全活用形を生成

    ─────────────────────────────────────────────────────────────────────────
    THIS IS THE MAIN ENTRY POINT / これがメインエントリーポイント
    ─────────────────────────────────────────────────────────────────────────

    Input (single entry) / 入力（単一エントリ）:
    ─────────────────────────────────────────────
        reading = "たべる"
        lemma = "食べる"
        conj_type = "下一段-バ行"

    Output (multiple entries) / 出力（複数エントリ）:
    ──────────────────────────────────────────────────
        [
            ("たべる", "食べる", 5000),      # 終止形 (base)
            ("たべ", "食べ", 5050),          # 連用形
            ("たべた", "食べた", 5100),      # た形 (past)
            ("たべて", "食べて", 5100),      # て形
            ("たべない", "食べない", 5150),  # ない形 (negative)
            ("たべます", "食べます", 5150),  # ます形 (polite)
            ... (10+ more forms)
        ]

    ─────────────────────────────────────────────────────────────────────────
    HOW IT WORKS / 動作の仕組み
    ─────────────────────────────────────────────────────────────────────────

    1. Identify verb type from conj_type
       conj_type から動詞タイプを特定

    2. Dispatch to appropriate handler:
       適切なハンドラに振り分け:
       - 五段-* → _conjugate_godan()
       - 一段-* → _conjugate_ichidan()
       - サ行変格 → _conjugate_suru()
       - カ行変格 → _conjugate_kuru()
       - 形容詞 → _conjugate_keiyoushi()

    3. Handler extracts stem and generates all forms
       ハンドラが語幹を抽出し全ての形を生成

    Args:
        reading: ひらがな読み (例: "たべる")
        lemma: 表層形/漢字 (例: "食べる")
        pos: 品詞 (例: "動詞") - currently unused but kept for API compatibility
        conj_type: 活用型 (例: "下一段-バ行")
        base_cost: 辞書からのコスト

    Returns:
        List of (読み, 表層形, コスト) タプルのリスト
        各タプルは1つの活用形を表す
    """
    if not is_conjugatable(conj_type):
        return [(reading, lemma, base_cost)]

    # 五段動詞
    if conj_type in GODAN_STEM_SUFFIXES:
        return _conjugate_godan(reading, lemma, conj_type, base_cost)

    # 一段動詞
    if conj_type.startswith("上一段-") or conj_type.startswith("下一段-"):
        return _conjugate_ichidan(reading, lemma, conj_type, base_cost)

    # サ行変格
    if conj_type == "サ行変格":
        return _conjugate_suru(reading, lemma, base_cost)

    # カ行変格
    if conj_type == "カ行変格":
        return _conjugate_kuru(reading, lemma, base_cost)

    # 形容詞
    if conj_type == "形容詞":
        return _conjugate_keiyoushi(reading, lemma, base_cost)

    # Fallback
    return [(reading, lemma, base_cost)]


# ============================================================================
# Conjugation Handlers / 活用ハンドラ
# ============================================================================
# Each handler is specialized for a specific verb/adjective type.
# Each follows the same pattern:
#   1. Extract stem from dictionary form / 辞書形から語幹を抽出
#   2. Generate basic forms / 基本形を生成
#   3. Generate compound forms (て形+auxiliary, etc.) / 複合形を生成
#   4. Return list of (reading, surface, cost) tuples / タプルのリストを返す


def _conjugate_godan(reading: str, lemma: str, conj_type: str,
                     base_cost: float) -> list:
    """
    Generate conjugations for 五段動詞 (5-row verbs).
    五段動詞の活用を生成

    ─────────────────────────────────────────────────────────────────────────
    PROCESS / 処理
    ─────────────────────────────────────────────────────────────────────────

    Example with 書く (kaku, "to write") / 書く の例:

    Step 1: Identify row from conj_type
    ステップ1: conj_type から行を特定
        "五段-カ行" → "カ行" (k-row)

    Step 2: Extract stem by removing final hiragana
    ステップ2: 最後のひらがなを削除して語幹を抽出
        書く → 書 (ka-)

    Step 3: Add suffixes from GODAN_SUFFIXES[row]
    ステップ3: GODAN_SUFFIXES[row] から接尾辞を追加
        書 + か → 書か (未然形)
        書 + き → 書き (連用形)
        書 + く → 書く (終止形)
        ...

    Step 4: Handle sound changes for て形/た形
    ステップ4: て形/た形の音便を処理
        書 + いて → 書いて (NOT 書きて)

    Step 5: Generate compound forms
    ステップ5: 複合形を生成
        書かない, 書きます, 書けば, etc.
    """
    results = []
    row = get_row(conj_type)
    suffixes = GODAN_SUFFIXES.get(row, {})

    if not suffixes:
        return [(reading, lemma, base_cost)]

    # Extract stem
    stem_r, stem_l = extract_stem(reading, lemma, conj_type)

    # Check for special verbs (行く)
    is_special = reading in SPECIAL_TE_TA

    # Generate basic forms
    for form_name, suffix in suffixes.items():
        # Handle special て形/た形 for 行く
        if is_special and form_name in ("て形", "た形"):
            special_te, special_ta = SPECIAL_TE_TA[reading]
            if form_name == "て形":
                conj_r = special_te
                conj_l = stem_l + "って"
            else:
                conj_r = special_ta
                conj_l = stem_l + "った"
        else:
            conj_r = stem_r + suffix
            conj_l = stem_l + suffix

        cost = base_cost + COST_PENALTIES.get(form_name, 100)
        results.append((conj_r, conj_l, cost))

    # Generate compound forms

    # ない形 (未然形 + ない)
    mizen_suffix = suffixes.get("未然形", "")
    results.append((
        stem_r + mizen_suffix + "ない",
        stem_l + mizen_suffix + "ない",
        base_cost + COST_PENALTIES["ない形"]
    ))

    # ます形 (連用形 + ます)
    renyo_suffix = suffixes.get("連用形", "")
    results.append((
        stem_r + renyo_suffix + "ます",
        stem_l + renyo_suffix + "ます",
        base_cost + COST_PENALTIES["ます形"]
    ))

    # ば形 (仮定形 + ば)
    katei_suffix = suffixes.get("仮定形", "")
    results.append((
        stem_r + katei_suffix + "ば",
        stem_l + katei_suffix + "ば",
        base_cost + COST_PENALTIES["ば形"]
    ))

    # たい形 (連用形 + たい)
    results.append((
        stem_r + renyo_suffix + "たい",
        stem_l + renyo_suffix + "たい",
        base_cost + COST_PENALTIES["たい形"]
    ))

    # 受身/可能形 (未然形 + れる) for 五段
    results.append((
        stem_r + mizen_suffix + "れる",
        stem_l + mizen_suffix + "れる",
        base_cost + COST_PENALTIES["れる形"]
    ))

    # 使役形 (未然形 + せる) for 五段
    results.append((
        stem_r + mizen_suffix + "せる",
        stem_l + mizen_suffix + "せる",
        base_cost + COST_PENALTIES["せる形"]
    ))

    return results


def _conjugate_ichidan(reading: str, lemma: str, conj_type: str,
                       base_cost: float) -> list:
    """
    Generate conjugations for 一段動詞 (上一段 and 下一段).

    一段 verbs have simpler conjugation - the stem is obtained by
    removing る, and suffixes are directly attached.
    """
    results = []

    # Extract stem (remove る)
    stem_r, stem_l = extract_stem(reading, lemma, conj_type)

    # Generate basic forms
    for form_name, suffix in ICHIDAN_SUFFIXES.items():
        conj_r = stem_r + suffix
        conj_l = stem_l + suffix

        # Normalize form name for cost lookup
        cost_key = form_name.split("_")[0] if "_" in form_name else form_name
        cost = base_cost + COST_PENALTIES.get(cost_key, 100)
        results.append((conj_r, conj_l, cost))

    # Generate compound forms

    # ない形 (stem + ない)
    results.append((
        stem_r + "ない",
        stem_l + "ない",
        base_cost + COST_PENALTIES["ない形"]
    ))

    # ます形 (stem + ます)
    results.append((
        stem_r + "ます",
        stem_l + "ます",
        base_cost + COST_PENALTIES["ます形"]
    ))

    # ば形 (仮定形 + ば)
    results.append((
        stem_r + "れば",
        stem_l + "れば",
        base_cost + COST_PENALTIES["ば形"]
    ))

    # たい形 (stem + たい)
    results.append((
        stem_r + "たい",
        stem_l + "たい",
        base_cost + COST_PENALTIES["たい形"]
    ))

    # 受身/可能形 (stem + られる) for 一段
    results.append((
        stem_r + "られる",
        stem_l + "られる",
        base_cost + COST_PENALTIES["られる形"]
    ))

    # 使役形 (stem + させる) for 一段
    results.append((
        stem_r + "させる",
        stem_l + "させる",
        base_cost + COST_PENALTIES["させる形"]
    ))

    return results


def _conjugate_suru(reading: str, lemma: str, base_cost: float) -> list:
    """
    Generate conjugations for サ行変格 (する verbs).
    サ行変格（する動詞）の活用を生成

    ─────────────────────────────────────────────────────────────────────────
    THE MOST COMMON IRREGULAR VERB / 最も一般的な不規則動詞
    ─────────────────────────────────────────────────────────────────────────

    する ("to do") is the second most frequent verb in Japanese (after いる/ある).
    Almost any noun can become a verb by adding する:
    する（「〜をする」）は日本語で2番目に頻繁な動詞（いる/あるの次）。
    ほとんどの名詞はするを追加して動詞になれる:

        勉強 (study) + する → 勉強する (to study)
        運動 (exercise) + する → 運動する (to exercise)
        愛 (love) + する → 愛する (to love)

    ─────────────────────────────────────────────────────────────────────────
    WHY IT'S IRREGULAR / なぜ不規則か
    ─────────────────────────────────────────────────────────────────────────

    Unlike regular verbs with ONE stem, する has MULTIPLE stems:
    1つの語幹を持つ規則動詞と異なり、するは複数の語幹を持つ:

        し  → します, して, した (i-stem)
        さ  → さない (a-stem, primary negative)
        せ  → せない (e-stem, alternative negative)
        す  → する, すれば (u-stem)
        しろ/せよ → commands (two options!)

    This handler generates ALL these irregular forms.
    このハンドラはこれらの不規則形を全て生成する。
    """
    results = []

    # Extract stem (remove する or ずる)
    if reading.endswith("する"):
        stem_r = reading[:-2]
        stem_l = lemma[:-2] if lemma and len(lemma) >= 2 else ""
        is_zuru = False
    elif reading.endswith("ずる"):
        stem_r = reading[:-2]
        stem_l = lemma[:-2] if lemma and len(lemma) >= 2 else ""
        is_zuru = True
    else:
        return [(reading, lemma, base_cost)]

    # 終止形 / 連体形
    if is_zuru:
        results.append((stem_r + "ずる", stem_l + "ずる", base_cost))
    else:
        results.append((stem_r + "する", stem_l + "する", base_cost))

    # 連用形 (し)
    results.append((stem_r + "し", stem_l + "し",
                   base_cost + COST_PENALTIES["連用形"]))

    # 未然形 (さ) - primary
    results.append((stem_r + "さ", stem_l + "さ",
                   base_cost + COST_PENALTIES["未然形"]))

    # 未然形 (せ) - alternative (used with られる, etc.)
    results.append((stem_r + "せ", stem_l + "せ",
                   base_cost + COST_PENALTIES["未然形"]))

    # 仮定形 (すれ)
    results.append((stem_r + "すれ", stem_l + "すれ",
                   base_cost + COST_PENALTIES["仮定形"]))

    # 命令形 (しろ / せよ)
    results.append((stem_r + "しろ", stem_l + "しろ",
                   base_cost + COST_PENALTIES["命令形"]))
    results.append((stem_r + "せよ", stem_l + "せよ",
                   base_cost + COST_PENALTIES["命令形"]))

    # て形 / た形
    results.append((stem_r + "して", stem_l + "して",
                   base_cost + COST_PENALTIES["て形"]))
    results.append((stem_r + "した", stem_l + "した",
                   base_cost + COST_PENALTIES["た形"]))

    # ない形
    results.append((stem_r + "しない", stem_l + "しない",
                   base_cost + COST_PENALTIES["ない形"]))

    # ます形
    results.append((stem_r + "します", stem_l + "します",
                   base_cost + COST_PENALTIES["ます形"]))

    # ば形
    results.append((stem_r + "すれば", stem_l + "すれば",
                   base_cost + COST_PENALTIES["ば形"]))

    # たい形
    results.append((stem_r + "したい", stem_l + "したい",
                   base_cost + COST_PENALTIES["たい形"]))

    # 受身形 (される)
    results.append((stem_r + "される", stem_l + "される",
                   base_cost + COST_PENALTIES["られる形"]))

    # 使役形 (させる)
    results.append((stem_r + "させる", stem_l + "させる",
                   base_cost + COST_PENALTIES["させる形"]))

    return results


def _conjugate_kuru(reading: str, lemma: str, base_cost: float) -> list:
    """
    Generate conjugations for カ行変格 (来る).
    カ行変格（来る）の活用を生成

    ─────────────────────────────────────────────────────────────────────────
    THE MOST IRREGULAR VERB IN JAPANESE / 日本語で最も不規則な動詞
    ─────────────────────────────────────────────────────────────────────────

    来る ("to come") is unique because the READING itself changes!
    来る（「来る」）は読み自体が変わるという点でユニーク！

    Compare with regular verbs:
    規則動詞と比較:

        書く: かく → かか, かき, かく, かけ (consonant stays "k")
                    子音は "k" のまま

        来る: くる → こ, き, くる, くれ (vowel changes completely!)
                    母音が完全に変わる！

    ─────────────────────────────────────────────────────────────────────────
    READING CHANGES / 読みの変化
    ─────────────────────────────────────────────────────────────────────────

        Form          Reading    Kanji     Meaning
        形            読み       漢字      意味
        ───────────   ────────   ──────    ───────────────
        終止形        くる       来る      (will) come
        連用形        き         来        come + (auxiliary)
        未然形        こ         来        come + ない
        仮定形        くれ       来れ      if come
        命令形        こい       来い      Come!

    Notice: The KANJI stays the same (来), but the reading changes!
    注意: 漢字は同じ（来）だが、読みが変わる！

    This is a major source of difficulty for Japanese learners.
    これは日本語学習者にとって大きな難点。
    """
    results = []

    # Extract stem (the kanji part before る)
    if reading.endswith("くる"):
        prefix_r = reading[:-2]
        prefix_l = lemma[:-1] if lemma else ""  # 来
    else:
        return [(reading, lemma, base_cost)]

    # 終止形 / 連体形 (くる)
    results.append((prefix_r + "くる", prefix_l + "る",
                   base_cost + COST_PENALTIES["終止形"]))

    # 連用形 (き)
    results.append((prefix_r + "き", prefix_l,
                   base_cost + COST_PENALTIES["連用形"]))

    # 未然形 (こ)
    results.append((prefix_r + "こ", prefix_l,
                   base_cost + COST_PENALTIES["未然形"]))

    # 仮定形 (くれ)
    results.append((prefix_r + "くれ", prefix_l + "れ",
                   base_cost + COST_PENALTIES["仮定形"]))

    # 命令形 (こい)
    results.append((prefix_r + "こい", prefix_l + "い",
                   base_cost + COST_PENALTIES["命令形"]))

    # て形 (きて)
    results.append((prefix_r + "きて", prefix_l + "て",
                   base_cost + COST_PENALTIES["て形"]))

    # た形 (きた)
    results.append((prefix_r + "きた", prefix_l + "た",
                   base_cost + COST_PENALTIES["た形"]))

    # ない形 (こない)
    results.append((prefix_r + "こない", prefix_l + "ない",
                   base_cost + COST_PENALTIES["ない形"]))

    # ます形 (きます)
    results.append((prefix_r + "きます", prefix_l + "ます",
                   base_cost + COST_PENALTIES["ます形"]))

    # ば形 (くれば)
    results.append((prefix_r + "くれば", prefix_l + "れば",
                   base_cost + COST_PENALTIES["ば形"]))

    # たい形 (きたい)
    results.append((prefix_r + "きたい", prefix_l + "たい",
                   base_cost + COST_PENALTIES["たい形"]))

    # 受身形 (こられる)
    results.append((prefix_r + "こられる", prefix_l + "られる",
                   base_cost + COST_PENALTIES["られる形"]))

    # 使役形 (こさせる)
    results.append((prefix_r + "こさせる", prefix_l + "させる",
                   base_cost + COST_PENALTIES["させる形"]))

    return results


def _conjugate_keiyoushi(reading: str, lemma: str, base_cost: float) -> list:
    """
    Generate conjugations for 形容詞 (い-adjectives).

    い-adjectives conjugate by replacing the final い with various suffixes.
    """
    results = []

    # Extract stem (remove い)
    if reading.endswith("い"):
        stem_r = reading[:-1]
        stem_l = lemma[:-1] if lemma else ""
    else:
        return [(reading, lemma, base_cost)]

    # Generate forms
    for form_name, suffix in KEIYOUSHI_SUFFIXES.items():
        conj_r = stem_r + suffix
        conj_l = stem_l + suffix
        cost = base_cost + COST_PENALTIES.get(form_name, 100)
        results.append((conj_r, conj_l, cost))

    # ない形 (連用形 + ない): 赤くない
    results.append((stem_r + "くない", stem_l + "くない",
                   base_cost + COST_PENALTIES["ない形"]))

    # ば形 (仮定形 + ば): 赤ければ
    results.append((stem_r + "ければ", stem_l + "ければ",
                   base_cost + COST_PENALTIES["ば形"]))

    return results


# ============================================================================
# SKK Okurigana Expansion / SKK送り仮名展開
# ============================================================================
# WHAT IS SKK? / SKKとは？
# ─────────────────────────
# SKK (Simple Kana to Kanji conversion) is a Japanese IME with a unique
# approach: it uses a compact dictionary format where conjugatable words
# store only the STEM with an alphabet suffix indicating verb type.
#
# SKK（シンプルかな漢字変換）は独自のアプローチを持つ日本語IME。
# 活用可能な単語は語幹のみを保存し、アルファベット接尾辞で動詞タイプを示す。
#
# EXAMPLE / 例:
# ─────────────
#   SKK entry:     かk /書/
#                  └─┬─┘ └─┘
#                    │    └── kanji stem (書)
#                    └─────── reading stem (か) + verb class (k = カ行五段)
#
#   This single entry expands to ALL forms:
#   この単一エントリが全ての形に展開される:
#
#   かく → 書く, かき → 書き, かいた → 書いた, かかない → 書かない, ...
#
# WHY THIS DESIGN? / なぜこの設計？
# ──────────────────────────────────
# 1. COMPACT: Store one entry instead of 15+ conjugated forms
#    コンパクト: 15以上の活用形の代わりに1エントリを保存
#
# 2. CONSISTENT: All forms are generated from the same rules
#    一貫性: 全ての形が同じルールから生成される
#
# 3. MAINTAINABLE: Fix a bug once, all forms are fixed
#    保守性: バグを一度修正すれば全ての形が修正される
#
# SUFFIX MEANING / 接尾辞の意味:
# ──────────────────────────────
#   k → カ行五段 (書く, 聞く)
#   g → ガ行五段 (泳ぐ, 急ぐ)
#   s → サ行五段 (話す, 出す)
#   t → タ行五段 (持つ, 勝つ)
#   n → ナ行五段 (死ぬ) - only one verb!
#   b → バ行五段 (遊ぶ, 飛ぶ)
#   m → マ行五段 (読む, 住む)
#   r → ラ行五段 (取る, 走る)
#   w/u → ワア行五段 (会う, 買う)
#   i → 形容詞 (赤い, 悪い)

# Maps SKK suffix → (終止形 hiragana suffix, conjugation type)
SKK_OKURIGANA_MAP = {
    # 五段動詞
    "k": ("く", "五段-カ行"),
    "g": ("ぐ", "五段-ガ行"),
    "s": ("す", "五段-サ行"),
    "t": ("つ", "五段-タ行"),
    "n": ("ぬ", "五段-ナ行"),
    "b": ("ぶ", "五段-バ行"),
    "m": ("む", "五段-マ行"),
    "r": ("る", "五段-ラ行"),
    "w": ("う", "五段-ワア行"),
    "u": ("う", "五段-ワア行"),  # Alternative notation
    # 形容詞
    "i": ("い", "形容詞"),
}


def expand_skk_okurigana(reading: str, kanji: str, base_count: int = 1) -> list:
    """
    Expand an SKK okurigana entry into all conjugated forms.

    Takes an SKK-style entry where the reading ends with an alphabet character
    indicating the conjugation class, and generates all conjugated forms.

    Args:
        reading: SKK reading with trailing alphabet (e.g., "かk", "わるi")
        kanji: Kanji stem without okurigana (e.g., "書", "悪")
        base_count: The count/weight value to use for generated entries

    Returns:
        List of tuples: [(full_reading, full_kanji, count), ...]
        Each tuple represents one conjugated form.

        Returns empty list if the reading doesn't end with a recognized
        okurigana marker or if conjugation fails.

    Example:
        >>> expand_skk_okurigana("かk", "書", 1)
        [
            ("かく", "書く", 1),      # 終止形
            ("かき", "書き", 1),      # 連用形
            ("かか", "書か", 1),      # 未然形
            ("かけ", "書け", 1),      # 仮定形/命令形
            ("かいて", "書いて", 1),  # て形
            ("かいた", "書いた", 1),  # た形
            ...
        ]

        >>> expand_skk_okurigana("わるi", "悪", 1)
        [
            ("わるい", "悪い", 1),      # 終止形
            ("わるく", "悪く", 1),      # 連用形
            ("わるかった", "悪かった", 1),  # た形
            ...
        ]
    """
    if not reading or len(reading) < 2:
        return []

    # Check if reading ends with an okurigana marker
    suffix = reading[-1]
    if suffix not in SKK_OKURIGANA_MAP:
        return []

    # Get conjugation info
    kana_suffix, conj_type = SKK_OKURIGANA_MAP[suffix]

    # Build the dictionary form (終止形)
    stem_r = reading[:-1]  # Remove alphabet suffix
    dict_reading = stem_r + kana_suffix
    dict_surface = kanji + kana_suffix

    # Determine POS based on conjugation type
    if conj_type == "形容詞":
        pos = "形容詞"
    else:
        pos = "動詞"

    # Use existing conjugation logic (cost-based → count-based conversion)
    # In the original katsuyou, lower cost = better. For SKK, we use counts.
    # We'll use base_count for all forms (can be refined later with penalties).
    raw_results = generate_conjugations(
        reading=dict_reading,
        lemma=dict_surface,
        pos=pos,
        conj_type=conj_type,
        base_cost=0  # We'll ignore costs and use base_count
    )

    # Convert to (reading, surface, count) format
    results = []
    seen = set()  # Deduplicate identical readings
    for conj_reading, conj_surface, _cost in raw_results:
        key = (conj_reading, conj_surface)
        if key not in seen:
            seen.add(key)
            results.append((conj_reading, conj_surface, base_count))

    return results


def is_skk_okurigana_entry(reading: str) -> bool:
    """
    Check if a reading is an SKK okurigana entry (ends with alphabet marker).

    Args:
        reading: The reading string to check

    Returns:
        True if the reading ends with a recognized okurigana marker
    """
    if not reading or len(reading) < 2:
        return False
    return reading[-1] in SKK_OKURIGANA_MAP
