#!/usr/bin/env python3
# katsuyou.py - Japanese verb/adjective conjugation (活用) module
#
# This module generates conjugated forms of Japanese verbs and adjectives
# from their dictionary form (終止形) for use in IME dictionary expansion.

"""
Japanese Conjugation (活用) Module

Generates all conjugated forms for verbs and adjectives based on their
活用型 (conjugation type) from UniDic.

Supported conjugation types:
- 五段動詞 (Godan verbs): カ行, ガ行, サ行, タ行, ナ行, バ行, マ行, ラ行, ワア行
- 一段動詞 (Ichidan verbs): 上一段-*, 下一段-*
- 変格動詞 (Irregular verbs): サ行変格 (する), カ行変格 (来る)
- 形容詞 (i-adjectives)

Generated forms include:
- Basic forms: 未然形, 連用形, 終止形, 連体形, 仮定形, 命令形
- Compound forms: て形, た形, ない形, ます形, ば形, たい形, られる形, させる形
"""

import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Cost Penalties
# ============================================================================
# Conjugated forms have slightly higher cost than base form to prefer
# dictionary form when both readings match.

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
# Stem Extraction Rules
# ============================================================================
# Maps 活用型 to the suffix to remove from dictionary form to get the stem.

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
# 五段動詞 Conjugation Suffixes
# ============================================================================
# For 五段 verbs, different rows (行) have different suffix patterns based on
# the Japanese vowel system (あ段, い段, う段, え段, お段).

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
# 一段動詞 Conjugation Suffixes
# ============================================================================
# 一段 verbs (both 上一段 and 下一段) have simpler conjugation - just add
# suffixes to the stem (obtained by removing る).

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
# 形容詞 Conjugation Suffixes
# ============================================================================
# い-adjectives conjugate by replacing い with various suffixes.

KEIYOUSHI_SUFFIXES = {
    "連用形": "く",         # 赤く
    "終止形": "い",         # 赤い
    "連体形": "い",         # 赤い-とき
    "仮定形": "けれ",       # 赤けれ-ば
    "て形": "くて",         # 赤くて
    "た形": "かった",       # 赤かった
}


# ============================================================================
# Special Verb Handling
# ============================================================================
# Some verbs have irregular conjugation patterns.

# 行く has special て形/た形 (not *行いて but 行って)
SPECIAL_TE_TA = {
    "いく": ("いって", "いった"),
    "ゆく": ("ゆって", "ゆった"),  # Alternative reading of 行く
}


# ============================================================================
# Core Functions
# ============================================================================

def is_conjugatable(conj_type: str) -> bool:
    """
    Check if a 活用型 should be conjugated.

    Args:
        conj_type: The conjugation type from UniDic (e.g., "五段-カ行", "*")

    Returns:
        True if the type can be conjugated, False otherwise.
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

    Args:
        reading: Hiragana reading of the dictionary form (e.g., "たべる")
        lemma: Surface form / kanji (e.g., "食べる")
        pos: Part of speech (e.g., "動詞")
        conj_type: Conjugation type (e.g., "下一段-バ行")
        base_cost: Cost from the dictionary

    Returns:
        List of tuples: [(conj_reading, conj_surface, cost), ...]
        Each tuple represents one conjugated form.
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
# Conjugation Handlers
# ============================================================================

def _conjugate_godan(reading: str, lemma: str, conj_type: str,
                     base_cost: float) -> list:
    """
    Generate conjugations for 五段動詞.

    五段 verbs conjugate by changing the final kana according to the
    vowel row (あ段, い段, う段, え段, お段).
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

    する verbs are irregular with multiple stem forms:
    - し (連用形): 愛し-ます, 愛し-て, 愛し-た
    - さ/せ (未然形): 愛さ-ない, 愛せ-ない (alternative)
    - すれ (仮定形): 愛すれ-ば
    - しろ/せよ (命令形): 愛しろ, 愛せよ
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

    来る is highly irregular - the reading changes depending on the form:
    - く (終止形/連体形): 来る (くる)
    - き (連用形): 来 (き), 来ます, 来て, 来た
    - こ (未然形): 来ない (こない)
    - くれ (仮定形): 来れば (くれば)
    - こい (命令形): 来い (こい)
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
# SKK Okurigana Expansion
# ============================================================================
# Maps SKK's trailing alphabet (okurigana marker) to conjugation parameters.
#
# In SKK dictionaries, entries like "かk /書/" use an alphabet suffix to
# indicate the conjugation class. This allows the dictionary to store only
# the stem while the user types the full okurigana.

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
