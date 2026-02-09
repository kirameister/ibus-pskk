#!/usr/bin/env python3
"""
Tests for the katsuyou (活用) conjugation module.

Tests cover:
- Stem extraction for all verb/adjective types
- Basic conjugation forms (未然形, 連用形, 終止形, 仮定形, 命令形)
- Compound forms (て形, た形, ない形, ます形, etc.)
- Irregular verbs (する, 来る, 行く)
- Cost penalty calculations
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import katsuyou


class TestIsConjugatable:
    """Tests for is_conjugatable() function."""

    def test_godan_verbs_are_conjugatable(self):
        """五段動詞 should be conjugatable."""
        assert katsuyou.is_conjugatable("五段-カ行") is True
        assert katsuyou.is_conjugatable("五段-ガ行") is True
        assert katsuyou.is_conjugatable("五段-サ行") is True
        assert katsuyou.is_conjugatable("五段-タ行") is True
        assert katsuyou.is_conjugatable("五段-ナ行") is True
        assert katsuyou.is_conjugatable("五段-バ行") is True
        assert katsuyou.is_conjugatable("五段-マ行") is True
        assert katsuyou.is_conjugatable("五段-ラ行") is True
        assert katsuyou.is_conjugatable("五段-ワア行") is True

    def test_ichidan_verbs_are_conjugatable(self):
        """一段動詞 should be conjugatable."""
        assert katsuyou.is_conjugatable("下一段-バ行") is True
        assert katsuyou.is_conjugatable("下一段-カ行") is True
        assert katsuyou.is_conjugatable("上一段-マ行") is True
        assert katsuyou.is_conjugatable("上一段-カ行") is True

    def test_irregular_verbs_are_conjugatable(self):
        """変格動詞 should be conjugatable."""
        assert katsuyou.is_conjugatable("サ行変格") is True
        assert katsuyou.is_conjugatable("カ行変格") is True

    def test_adjectives_are_conjugatable(self):
        """形容詞 should be conjugatable."""
        assert katsuyou.is_conjugatable("形容詞") is True

    def test_non_conjugating_types(self):
        """Non-conjugating types should return False."""
        assert katsuyou.is_conjugatable("*") is False
        assert katsuyou.is_conjugatable("") is False
        assert katsuyou.is_conjugatable(None) is False

    def test_classical_forms_not_conjugatable_by_default(self):
        """文語 forms should return False (disabled by default)."""
        assert katsuyou.is_conjugatable("文語四段-カ行") is False
        assert katsuyou.is_conjugatable("文語下二段-カ行") is False


class TestGetRow:
    """Tests for get_row() function."""

    def test_extracts_row_from_godan(self):
        assert katsuyou.get_row("五段-カ行") == "カ行"
        assert katsuyou.get_row("五段-ラ行") == "ラ行"

    def test_extracts_row_from_ichidan(self):
        assert katsuyou.get_row("下一段-バ行") == "バ行"
        assert katsuyou.get_row("上一段-マ行") == "マ行"

    def test_returns_full_type_if_no_dash(self):
        assert katsuyou.get_row("形容詞") == "形容詞"
        assert katsuyou.get_row("サ行変格") == "サ行変格"


class TestExtractStem:
    """Tests for extract_stem() function."""

    def test_godan_ka_stem(self):
        """五段-カ行: 書く → 書"""
        stem_r, stem_l = katsuyou.extract_stem("かく", "書く", "五段-カ行")
        assert stem_r == "か"
        assert stem_l == "書"

    def test_godan_ga_stem(self):
        """五段-ガ行: 泳ぐ → 泳"""
        stem_r, stem_l = katsuyou.extract_stem("およぐ", "泳ぐ", "五段-ガ行")
        assert stem_r == "およ"
        assert stem_l == "泳"

    def test_godan_sa_stem(self):
        """五段-サ行: 話す → 話"""
        stem_r, stem_l = katsuyou.extract_stem("はなす", "話す", "五段-サ行")
        assert stem_r == "はな"
        assert stem_l == "話"

    def test_ichidan_stem(self):
        """下一段-バ行: 食べる → 食べ"""
        stem_r, stem_l = katsuyou.extract_stem("たべる", "食べる", "下一段-バ行")
        assert stem_r == "たべ"
        assert stem_l == "食べ"

    def test_kamiichidan_stem(self):
        """上一段-マ行: 見る → 見"""
        stem_r, stem_l = katsuyou.extract_stem("みる", "見る", "上一段-マ行")
        assert stem_r == "み"
        assert stem_l == "見"

    def test_suru_stem(self):
        """サ行変格: 愛する → 愛す"""
        stem_r, stem_l = katsuyou.extract_stem("あいする", "愛する", "サ行変格")
        assert stem_r == "あい"
        assert stem_l == "愛"

    def test_kuru_stem(self):
        """カ行変格: 来る → 来"""
        stem_r, stem_l = katsuyou.extract_stem("くる", "来る", "カ行変格")
        assert stem_r == ""
        assert stem_l == "来"

    def test_keiyoushi_stem(self):
        """形容詞: 赤い → 赤"""
        stem_r, stem_l = katsuyou.extract_stem("あかい", "赤い", "形容詞")
        assert stem_r == "あか"
        assert stem_l == "赤"


class TestGodanConjugation:
    """Tests for 五段動詞 conjugation."""

    def test_ka_row_basic_forms(self):
        """五段-カ行 basic conjugations."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)
        forms = {(r, s) for r, s, c in results}

        # Basic forms
        assert ("かく", "書く") in forms      # 終止形
        assert ("かき", "書き") in forms      # 連用形
        assert ("かか", "書か") in forms      # 未然形
        assert ("かけ", "書け") in forms      # 仮定形/命令形

    def test_ka_row_te_ta_onbin(self):
        """五段-カ行 音便 (イ音便)."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("かいて", "書いて") in forms  # て形 (イ音便)
        assert ("かいた", "書いた") in forms  # た形 (イ音便)

    def test_ga_row_te_ta_onbin(self):
        """五段-ガ行 音便 (イ音便 with voicing)."""
        results = katsuyou.generate_conjugations("およぐ", "泳ぐ", "動詞", "五段-ガ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("およいで", "泳いで") in forms  # て形
        assert ("およいだ", "泳いだ") in forms  # た形

    def test_sa_row_te_ta(self):
        """五段-サ行 て形/た形 (no euphonic change)."""
        results = katsuyou.generate_conjugations("はなす", "話す", "動詞", "五段-サ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("はなして", "話して") in forms
        assert ("はなした", "話した") in forms

    def test_ta_row_sokuonbin(self):
        """五段-タ行 促音便."""
        results = katsuyou.generate_conjugations("もつ", "持つ", "動詞", "五段-タ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("もって", "持って") in forms
        assert ("もった", "持った") in forms

    def test_na_row_hatsuonbin(self):
        """五段-ナ行 撥音便."""
        results = katsuyou.generate_conjugations("しぬ", "死ぬ", "動詞", "五段-ナ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("しんで", "死んで") in forms
        assert ("しんだ", "死んだ") in forms

    def test_ba_row_hatsuonbin(self):
        """五段-バ行 撥音便."""
        results = katsuyou.generate_conjugations("あそぶ", "遊ぶ", "動詞", "五段-バ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あそんで", "遊んで") in forms
        assert ("あそんだ", "遊んだ") in forms

    def test_ma_row_hatsuonbin(self):
        """五段-マ行 撥音便."""
        results = katsuyou.generate_conjugations("よむ", "読む", "動詞", "五段-マ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("よんで", "読んで") in forms
        assert ("よんだ", "読んだ") in forms

    def test_ra_row_sokuonbin(self):
        """五段-ラ行 促音便."""
        results = katsuyou.generate_conjugations("とる", "取る", "動詞", "五段-ラ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("とって", "取って") in forms
        assert ("とった", "取った") in forms

    def test_waa_row_sokuonbin(self):
        """五段-ワア行 促音便."""
        results = katsuyou.generate_conjugations("あう", "会う", "動詞", "五段-ワア行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あって", "会って") in forms
        assert ("あった", "会った") in forms

    def test_godan_compound_forms(self):
        """五段 compound forms (ない形, ます形, etc.)."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("かかない", "書かない") in forms    # ない形
        assert ("かきます", "書きます") in forms    # ます形
        assert ("かけば", "書けば") in forms        # ば形
        assert ("かきたい", "書きたい") in forms    # たい形
        assert ("かかれる", "書かれる") in forms    # 受身/可能形
        assert ("かかせる", "書かせる") in forms    # 使役形


class TestIkuSpecialCase:
    """Tests for 行く special conjugation."""

    def test_iku_te_ta_forms(self):
        """行く has special て形/た形 (not *いいて but いって)."""
        results = katsuyou.generate_conjugations("いく", "行く", "動詞", "五段-カ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("いって", "行って") in forms  # Special て形
        assert ("いった", "行った") in forms  # Special た形
        # Should NOT have regular イ音便
        assert ("いいて", "行いて") not in forms
        assert ("いいた", "行いた") not in forms


class TestIchidanConjugation:
    """Tests for 一段動詞 conjugation."""

    def test_shimoichidan_basic_forms(self):
        """下一段 basic conjugations."""
        results = katsuyou.generate_conjugations("たべる", "食べる", "動詞", "下一段-バ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("たべる", "食べる") in forms   # 終止形
        assert ("たべ", "食べ") in forms       # 連用形
        assert ("たべれ", "食べれ") in forms   # 仮定形
        assert ("たべろ", "食べろ") in forms   # 命令形-ろ
        assert ("たべよ", "食べよ") in forms   # 命令形-よ

    def test_shimoichidan_te_ta(self):
        """下一段 て形/た形."""
        results = katsuyou.generate_conjugations("たべる", "食べる", "動詞", "下一段-バ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("たべて", "食べて") in forms
        assert ("たべた", "食べた") in forms

    def test_shimoichidan_compound_forms(self):
        """下一段 compound forms."""
        results = katsuyou.generate_conjugations("たべる", "食べる", "動詞", "下一段-バ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("たべない", "食べない") in forms    # ない形
        assert ("たべます", "食べます") in forms    # ます形
        assert ("たべれば", "食べれば") in forms    # ば形
        assert ("たべたい", "食べたい") in forms    # たい形
        assert ("たべられる", "食べられる") in forms  # 受身/可能形
        assert ("たべさせる", "食べさせる") in forms  # 使役形

    def test_kamiichidan_basic_forms(self):
        """上一段 basic conjugations."""
        results = katsuyou.generate_conjugations("みる", "見る", "動詞", "上一段-マ行", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("みる", "見る") in forms
        assert ("み", "見") in forms
        assert ("みて", "見て") in forms
        assert ("みた", "見た") in forms


class TestSuruConjugation:
    """Tests for サ行変格 (する) conjugation."""

    def test_suru_basic_forms(self):
        """する verb basic conjugations."""
        results = katsuyou.generate_conjugations("あいする", "愛する", "動詞", "サ行変格", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あいする", "愛する") in forms   # 終止形
        assert ("あいし", "愛し") in forms       # 連用形
        assert ("あいさ", "愛さ") in forms       # 未然形 (さ)
        assert ("あいせ", "愛せ") in forms       # 未然形 (せ)
        assert ("あいすれ", "愛すれ") in forms   # 仮定形

    def test_suru_te_ta(self):
        """する verb て形/た形."""
        results = katsuyou.generate_conjugations("あいする", "愛する", "動詞", "サ行変格", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あいして", "愛して") in forms
        assert ("あいした", "愛した") in forms

    def test_suru_compound_forms(self):
        """する verb compound forms."""
        results = katsuyou.generate_conjugations("あいする", "愛する", "動詞", "サ行変格", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あいしない", "愛しない") in forms
        assert ("あいします", "愛します") in forms
        assert ("あいすれば", "愛すれば") in forms
        assert ("あいしたい", "愛したい") in forms
        assert ("あいされる", "愛される") in forms
        assert ("あいさせる", "愛させる") in forms

    def test_suru_imperative_forms(self):
        """する verb imperative forms."""
        results = katsuyou.generate_conjugations("あいする", "愛する", "動詞", "サ行変格", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あいしろ", "愛しろ") in forms
        assert ("あいせよ", "愛せよ") in forms


class TestKuruConjugation:
    """Tests for カ行変格 (来る) conjugation."""

    def test_kuru_reading_changes(self):
        """来る has reading changes depending on form."""
        results = katsuyou.generate_conjugations("くる", "来る", "動詞", "カ行変格", 5000)
        forms = {(r, s) for r, s, c in results}

        # 終止形: くる
        assert ("くる", "来る") in forms

        # 連用形: き
        assert ("き", "来") in forms
        assert ("きて", "来て") in forms
        assert ("きた", "来た") in forms
        assert ("きます", "来ます") in forms

        # 未然形: こ
        assert ("こ", "来") in forms
        assert ("こない", "来ない") in forms

        # 仮定形: くれ
        assert ("くれ", "来れ") in forms
        assert ("くれば", "来れば") in forms

        # 命令形: こい
        assert ("こい", "来い") in forms


class TestKeiyoushiConjugation:
    """Tests for 形容詞 (い-adjective) conjugation."""

    def test_keiyoushi_basic_forms(self):
        """形容詞 basic conjugations."""
        results = katsuyou.generate_conjugations("あかい", "赤い", "形容詞", "形容詞", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あかい", "赤い") in forms      # 終止形/連体形
        assert ("あかく", "赤く") in forms      # 連用形
        assert ("あかけれ", "赤けれ") in forms  # 仮定形

    def test_keiyoushi_te_ta(self):
        """形容詞 て形/た形."""
        results = katsuyou.generate_conjugations("あかい", "赤い", "形容詞", "形容詞", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あかくて", "赤くて") in forms
        assert ("あかかった", "赤かった") in forms

    def test_keiyoushi_compound_forms(self):
        """形容詞 compound forms."""
        results = katsuyou.generate_conjugations("あかい", "赤い", "形容詞", "形容詞", 5000)
        forms = {(r, s) for r, s, c in results}

        assert ("あかくない", "赤くない") in forms  # ない形
        assert ("あかければ", "赤ければ") in forms  # ば形


class TestCostPenalties:
    """Tests for cost penalty calculations."""

    def test_base_form_no_penalty(self):
        """終止形 should have no cost penalty."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)

        # Find 終止形
        for r, s, c in results:
            if r == "かく" and s == "書く":
                assert c == 5000
                break

    def test_basic_forms_have_penalty(self):
        """連用形, 未然形, etc. should have penalty of 50."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)

        # Find 連用形
        for r, s, c in results:
            if r == "かき" and s == "書き":
                assert c == 5050
                break

    def test_te_ta_forms_penalty(self):
        """て形/た形 should have penalty of 100."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)

        for r, s, c in results:
            if r == "かいて" and s == "書いて":
                assert c == 5100
                break

    def test_compound_forms_penalty(self):
        """Compound forms (ない形, ます形) should have penalty of 150."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)

        for r, s, c in results:
            if r == "かかない" and s == "書かない":
                assert c == 5150
                break

    def test_derived_forms_penalty(self):
        """Derived forms (られる形, させる形) should have penalty of 200."""
        results = katsuyou.generate_conjugations("かく", "書く", "動詞", "五段-カ行", 5000)

        for r, s, c in results:
            if r == "かかれる" and s == "書かれる":
                assert c == 5200
                break


class TestNonConjugatable:
    """Tests for non-conjugatable entries."""

    def test_non_conjugatable_returns_base_only(self):
        """Non-conjugatable types should return only the base form."""
        results = katsuyou.generate_conjugations("にほん", "日本", "名詞", "*", 5000)

        assert len(results) == 1
        assert results[0] == ("にほん", "日本", 5000)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
