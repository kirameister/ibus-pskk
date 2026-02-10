#!/usr/bin/env python3
# tests/test_skk_dictionary.py - Unit tests for SKK dictionary conversion functions

import pytest
import os
import sys
import json
import tempfile
import shutil

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from util import (
    parse_skk_dictionary_line,
    convert_skk_to_json,
    convert_all_skk_dictionaries,
    generate_system_dictionary,
    get_user_dictionaries_dir,
    get_skk_dicts_dir,
)


class TestParseSkkDictionaryLine:
    """Test suite for parse_skk_dictionary_line() function"""

    def test_simple_entry(self):
        """Test parsing a simple SKK entry with single candidate"""
        reading, candidates = parse_skk_dictionary_line("あい /愛/")
        assert reading == "あい"
        assert candidates == ["愛"]

    def test_multiple_candidates(self):
        """Test parsing an entry with multiple candidates"""
        reading, candidates = parse_skk_dictionary_line("あやこ /亜矢子/彩子/")
        assert reading == "あやこ"
        assert candidates == ["亜矢子", "彩子"]

    def test_many_candidates(self):
        """Test parsing an entry with many candidates"""
        reading, candidates = parse_skk_dictionary_line("へんかん /変換/返還/編纂/偏関/")
        assert reading == "へんかん"
        assert candidates == ["変換", "返還", "編纂", "偏関"]

    def test_comment_line(self):
        """Test that comment lines are skipped"""
        reading, candidates = parse_skk_dictionary_line(";; This is a comment")
        assert reading is None
        assert candidates is None

    def test_empty_line(self):
        """Test that empty lines are skipped"""
        reading, candidates = parse_skk_dictionary_line("")
        assert reading is None
        assert candidates is None

    def test_whitespace_only_line(self):
        """Test that whitespace-only lines are skipped"""
        reading, candidates = parse_skk_dictionary_line("   \t  ")
        assert reading is None
        assert candidates is None

    def test_annotation_stripped(self):
        """Test that annotations (;annotation) are stripped from candidates"""
        reading, candidates = parse_skk_dictionary_line("あい /愛;名詞/相;副詞/")
        assert reading == "あい"
        assert candidates == ["愛", "相"]

    def test_mixed_annotation_and_plain(self):
        """Test entry with both annotated and plain candidates"""
        reading, candidates = parse_skk_dictionary_line("かく /書く/描く;絵を描く/核/")
        assert reading == "かく"
        assert candidates == ["書く", "描く", "核"]

    def test_no_trailing_slash(self):
        """Test entry without trailing slash (should still work)"""
        reading, candidates = parse_skk_dictionary_line("てすと /テスト")
        assert reading == "てすと"
        assert candidates == ["テスト"]

    def test_hiragana_reading_kanji_candidates(self):
        """Test typical hiragana reading with kanji candidates"""
        reading, candidates = parse_skk_dictionary_line("にほん /日本/二本/")
        assert reading == "にほん"
        assert candidates == ["日本", "二本"]

    def test_katakana_candidate(self):
        """Test entry with katakana candidate"""
        reading, candidates = parse_skk_dictionary_line("こんぴゅーた /コンピュータ/コンピューター/")
        assert reading == "こんぴゅーた"
        assert candidates == ["コンピュータ", "コンピューター"]

    def test_invalid_format_no_space(self):
        """Test that lines without space separator are rejected"""
        reading, candidates = parse_skk_dictionary_line("nospace/候補/")
        assert reading is None
        assert candidates is None

    def test_empty_candidates(self):
        """Test that entries with empty candidates are rejected"""
        reading, candidates = parse_skk_dictionary_line("からっぽ //")
        assert reading is None
        assert candidates is None

    def test_single_slash_only(self):
        """Test that entries with only slashes are rejected"""
        reading, candidates = parse_skk_dictionary_line("bad /")
        assert reading is None
        assert candidates is None


class TestConvertSkkToJson:
    """Test suite for convert_skk_to_json() function"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_convert_simple_file(self, temp_dir):
        """Test converting a simple SKK dictionary file"""
        # Create test SKK file
        skk_content = """;; Test dictionary
あい /愛/相/
かく /書く/描く/
"""
        skk_path = os.path.join(temp_dir, "test.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write(skk_content)

        # Convert
        json_path = os.path.join(temp_dir, "output.json")
        success, output_path, entry_count = convert_skk_to_json(skk_path, json_path)

        assert success is True
        assert output_path == json_path
        assert entry_count == 2

        # Verify JSON content
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["あい"] == {"愛": 1, "相": 1}
        assert data["かく"] == {"書く": 1, "描く": 1}

    def test_convert_with_comments(self, temp_dir):
        """Test that comments are properly skipped"""
        skk_content = """;; SKK-JISYO
;; -*- coding: utf-8 -*-
;; okuri-ari entries
たべr /食べ/
;; okuri-nasi entries
たべもの /食べ物/
"""
        skk_path = os.path.join(temp_dir, "test.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write(skk_content)

        json_path = os.path.join(temp_dir, "output.json")
        success, output_path, entry_count = convert_skk_to_json(skk_path, json_path)

        assert success is True
        assert entry_count == 2

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert "たべr" in data
        assert "たべもの" in data

    def test_merge_duplicate_readings(self, temp_dir):
        """Test that duplicate readings are merged"""
        skk_content = """あい /愛/
あい /相/藍/
"""
        skk_path = os.path.join(temp_dir, "test.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write(skk_content)

        json_path = os.path.join(temp_dir, "output.json")
        success, _, _ = convert_skk_to_json(skk_path, json_path)

        assert success is True

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Should have all three candidates merged, each with count 1
        assert data["あい"] == {"愛": 1, "相": 1, "藍": 1}

    def test_merge_increments_count(self, temp_dir):
        """Test that merging increments count for duplicate candidates"""
        skk_content = """あい /愛/相/
あい /愛/藍/
"""
        skk_path = os.path.join(temp_dir, "test.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write(skk_content)

        json_path = os.path.join(temp_dir, "output.json")
        convert_skk_to_json(skk_path, json_path)

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # "愛" appears in both lines, so count should be 2
        assert data["あい"]["愛"] == 2
        # "相" and "藍" appear only once each
        assert data["あい"]["相"] == 1
        assert data["あい"]["藍"] == 1
        assert len(data["あい"]) == 3  # 愛, 相, 藍

    def test_auto_generate_output_path(self, temp_dir, monkeypatch):
        """Test that output path is auto-generated when not specified"""
        # Create test SKK file
        skk_content = "てすと /テスト/"
        skk_path = os.path.join(temp_dir, "SKK-JISYO.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write(skk_content)

        # Mock get_user_dictionaries_dir to use temp directory
        dict_dir = os.path.join(temp_dir, "dictionaries")
        monkeypatch.setattr('util.get_user_dictionaries_dir', lambda: dict_dir)

        success, output_path, _ = convert_skk_to_json(skk_path)

        assert success is True
        assert output_path == os.path.join(dict_dir, "SKK-JISYO.json")
        assert os.path.exists(output_path)

    def test_nonexistent_file(self):
        """Test handling of non-existent input file"""
        success, output_path, entry_count = convert_skk_to_json("/nonexistent/path.utf8")

        assert success is False
        assert output_path is None
        assert entry_count == 0

    def test_empty_file(self, temp_dir):
        """Test converting an empty file"""
        skk_path = os.path.join(temp_dir, "empty.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write("")

        json_path = os.path.join(temp_dir, "output.json")
        success, output_path, entry_count = convert_skk_to_json(skk_path, json_path)

        assert success is True
        assert entry_count == 0

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data == {}

    def test_comments_only_file(self, temp_dir):
        """Test converting a file with only comments"""
        skk_content = """;; Just comments
;; No actual entries
;; End of file
"""
        skk_path = os.path.join(temp_dir, "comments.utf8")
        with open(skk_path, 'w', encoding='utf-8') as f:
            f.write(skk_content)

        json_path = os.path.join(temp_dir, "output.json")
        success, _, entry_count = convert_skk_to_json(skk_path, json_path)

        assert success is True
        assert entry_count == 0

    def test_strips_common_extensions(self, temp_dir, monkeypatch):
        """Test that common SKK extensions are stripped from output filename"""
        dict_dir = os.path.join(temp_dir, "dictionaries")
        monkeypatch.setattr('util.get_user_dictionaries_dir', lambda: dict_dir)

        test_cases = [
            ("SKK-JISYO.utf8", "SKK-JISYO.json"),
            ("mydict.txt", "mydict.json"),
            ("test.dic", "test.json"),
            ("sample.SKK", "sample.json"),
        ]

        for input_name, expected_output in test_cases:
            skk_path = os.path.join(temp_dir, input_name)
            with open(skk_path, 'w', encoding='utf-8') as f:
                f.write("あ /亜/")

            success, output_path, _ = convert_skk_to_json(skk_path)
            assert os.path.basename(output_path) == expected_output, f"Failed for {input_name}"

            # Clean up for next iteration
            os.remove(output_path)


class TestConvertAllSkkDictionaries:
    """Test suite for convert_all_skk_dictionaries() function"""

    @pytest.fixture
    def temp_dirs(self, monkeypatch):
        """Create temporary directories for SKK and user dictionaries"""
        temp_base = tempfile.mkdtemp()
        skk_dir = os.path.join(temp_base, "skk_dicts")
        dict_dir = os.path.join(temp_base, "dictionaries")
        os.makedirs(skk_dir)

        monkeypatch.setattr('util.get_skk_dicts_dir', lambda: skk_dir)
        monkeypatch.setattr('util.get_user_dictionaries_dir', lambda: dict_dir)

        yield {'base': temp_base, 'skk': skk_dir, 'dict': dict_dir}
        shutil.rmtree(temp_base)

    def test_convert_multiple_files(self, temp_dirs):
        """Test batch conversion of multiple SKK files"""
        # Create test files
        with open(os.path.join(temp_dirs['skk'], "dict1.utf8"), 'w', encoding='utf-8') as f:
            f.write("あい /愛/\n")
        with open(os.path.join(temp_dirs['skk'], "dict2.utf8"), 'w', encoding='utf-8') as f:
            f.write("かく /書く/\nよむ /読む/\n")

        results = convert_all_skk_dictionaries()

        assert len(results) == 2
        # Check that both files were processed
        filenames = [r[0] for r in results]
        assert "dict1.utf8" in filenames
        assert "dict2.utf8" in filenames
        # Check success and entry counts
        for filename, success, entry_count in results:
            assert success is True
            if filename == "dict1.utf8":
                assert entry_count == 1
            elif filename == "dict2.utf8":
                assert entry_count == 2

    def test_empty_skk_directory(self, temp_dirs):
        """Test handling of empty SKK directory"""
        results = convert_all_skk_dictionaries()
        assert results == []

    def test_nonexistent_skk_directory(self, monkeypatch):
        """Test handling when SKK directory doesn't exist"""
        monkeypatch.setattr('util.get_skk_dicts_dir', lambda: "/nonexistent/path")

        results = convert_all_skk_dictionaries()
        assert results == []

    def test_skip_subdirectories(self, temp_dirs):
        """Test that subdirectories are skipped"""
        # Create a file and a subdirectory
        with open(os.path.join(temp_dirs['skk'], "valid.utf8"), 'w', encoding='utf-8') as f:
            f.write("あ /亜/\n")
        os.makedirs(os.path.join(temp_dirs['skk'], "subdir"))

        results = convert_all_skk_dictionaries()

        # Only the file should be processed
        assert len(results) == 1
        assert results[0][0] == "valid.utf8"


class TestGenerateSystemDictionary:
    """Test suite for generate_system_dictionary() function

    Note: generate_system_dictionary() now processes SKK-format dictionary files.
    SKK format: reading /candidate1/candidate2/.../

    Output JSON format: {reading: {candidate: count}}
    The count represents how many times a candidate appears across all source files.
    """

    @pytest.fixture
    def temp_dirs(self, monkeypatch):
        """Create temporary directories for SKK dicts and output dictionaries"""
        temp_base = tempfile.mkdtemp()
        skk_dir = os.path.join(temp_base, "skk_dicts")
        dict_dir = os.path.join(temp_base, "dictionaries")
        os.makedirs(skk_dir)
        os.makedirs(dict_dir)

        monkeypatch.setattr('util.get_skk_dicts_dir', lambda: skk_dir)
        monkeypatch.setattr('util.get_user_config_dir', lambda: dict_dir)

        yield {'base': temp_base, 'skk': skk_dir, 'dict': dict_dir}
        shutil.rmtree(temp_base)

    def test_merge_multiple_files(self, temp_dirs):
        """Test merging multiple SKK files into one with occurrence counts"""
        # Create two SKK files with overlapping entries
        with open(os.path.join(temp_dirs['skk'], "dict1"), 'w', encoding='utf-8') as f:
            f.write("あい /愛/相/\n")
            f.write("にほん /日本/\n")
        with open(os.path.join(temp_dirs['skk'], "dict2"), 'w', encoding='utf-8') as f:
            f.write("あい /愛/藍/\n")  # 愛 appears again, count should be 2
            f.write("せかい /世界/\n")

        success, output_path, stats = generate_system_dictionary()

        assert success is True
        assert output_path == os.path.join(temp_dirs['dict'], 'system_dictionary.json')
        assert stats['files_processed'] == 2
        assert stats['total_readings'] == 3  # あい, にほん, せかい

        # Verify merged content
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # "愛" appears in both files, count should be 2
        assert data["あい"]["愛"] == 2
        # Other entries appear once
        assert data["あい"]["相"] == 1
        assert data["あい"]["藍"] == 1
        assert data["にほん"]["日本"] == 1
        assert data["せかい"]["世界"] == 1

    def test_no_double_count_within_file(self, temp_dirs):
        """Test that duplicate entries in same file are counted only once"""
        # Create a file where same reading/candidate appears on multiple lines
        with open(os.path.join(temp_dirs['skk'], "dict"), 'w', encoding='utf-8') as f:
            f.write("あい /愛/\n")
            f.write("あい /愛/相/\n")  # 愛 appears again, but same file so count = 1

        success, output_path, stats = generate_system_dictionary()

        assert success is True

        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Within same file, duplicates should count only once
        assert data["あい"]["愛"] == 1
        assert data["あい"]["相"] == 1

    def test_count_across_files(self, temp_dirs):
        """Test that entries from multiple files are counted correctly"""
        # Create three files, each containing "愛"
        for i in range(3):
            with open(os.path.join(temp_dirs['skk'], f"dict{i}"), 'w', encoding='utf-8') as f:
                f.write("あい /愛/\n")

        success, output_path, stats = generate_system_dictionary()

        assert success is True
        assert stats['files_processed'] == 3

        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 愛 appears in all 3 files, count should be 3
        assert data["あい"]["愛"] == 3

    def test_custom_output_path(self, temp_dirs):
        """Test specifying a custom output path"""
        with open(os.path.join(temp_dirs['skk'], "dict"), 'w', encoding='utf-8') as f:
            f.write("てすと /テスト/\n")

        custom_path = os.path.join(temp_dirs['base'], 'custom', 'output.json')
        success, output_path, stats = generate_system_dictionary(output_path=custom_path)

        assert success is True
        assert output_path == custom_path
        assert os.path.exists(custom_path)

    def test_empty_skk_directory(self, temp_dirs):
        """Test handling of empty SKK directory"""
        success, output_path, stats = generate_system_dictionary()

        assert success is True
        assert stats['files_processed'] == 0
        assert stats['total_readings'] == 0

        # Should still create an empty JSON file
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data == {}

    def test_nonexistent_skk_directory(self, monkeypatch):
        """Test handling when SKK directory doesn't exist"""
        monkeypatch.setattr('util.get_skk_dicts_dir', lambda: "/nonexistent/path")

        success, output_path, stats = generate_system_dictionary()

        assert success is False
        assert output_path is None
        assert stats['files_processed'] == 0

    def test_stats_accuracy(self, temp_dirs):
        """Test that statistics are accurate"""
        with open(os.path.join(temp_dirs['skk'], "dict"), 'w', encoding='utf-8') as f:
            f.write("あい /愛/相/藍/\n")  # 3 candidates for あい
            f.write("にほん /日本/二本/\n")  # 2 candidates for にほん

        success, output_path, stats = generate_system_dictionary()

        assert success is True
        assert stats['files_processed'] == 1
        assert stats['total_readings'] == 2  # あい, にほん
        assert stats['total_candidates'] == 5  # 3 + 2


class TestEdgeCases:
    """Test edge cases and special scenarios"""

    def test_unicode_preservation(self):
        """Test that various Unicode characters are preserved"""
        # Test with various Japanese characters
        test_cases = [
            ("ひらがな /平仮名/", "ひらがな", ["平仮名"]),
            ("カタカナ /片仮名/", "カタカナ", ["片仮名"]),
            ("きごう /★/☆/♪/", "きごう", ["★", "☆", "♪"]),
            ("かおもじ /(^_^)/(T_T)/", "かおもじ", ["(^_^)", "(T_T)"]),
        ]

        for line, expected_reading, expected_candidates in test_cases:
            reading, candidates = parse_skk_dictionary_line(line)
            assert reading == expected_reading
            assert candidates == expected_candidates

    def test_long_entry(self):
        """Test parsing an entry with many candidates"""
        # Create a line with 20 candidates
        candidates_list = [f"候補{i}" for i in range(20)]
        candidates_str = "/".join(candidates_list)
        line = f"ながい /{candidates_str}/"

        reading, candidates = parse_skk_dictionary_line(line)
        assert reading == "ながい"
        assert len(candidates) == 20
        assert candidates == candidates_list

    def test_special_characters_in_reading(self):
        """Test reading with special characters (okuri-ari format)"""
        # SKK uses trailing characters for okurigana
        reading, candidates = parse_skk_dictionary_line("たべr /食べ/")
        assert reading == "たべr"
        assert candidates == ["食べ"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
