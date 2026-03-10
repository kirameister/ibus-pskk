#!/usr/bin/env python3
# tests/test_simultaneous_processor.py - Unit tests for simultaneous_processor.py

import pytest
import os
import sys
from unittest.mock import patch, PropertyMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from simultaneous_processor import SimultaneousInputProcessor


class TestBuildSimultaneousMap:
    """Test suite for _build_simultaneous_map() method"""

    def test_empty_layout_data(self):
        """Test that empty layout data results in empty map"""
        processor = SimultaneousInputProcessor([])
        # Should not crash, simultaneous_map should not be set (or empty)
        assert not hasattr(processor, 'simultaneous_map') or processor.simultaneous_map == []

    def test_none_layout_data(self):
        """Test that None layout data is handled gracefully"""
        processor = SimultaneousInputProcessor(None)
        assert not hasattr(processor, 'simultaneous_map') or processor.simultaneous_map is None

    def test_single_char_entries(self):
        """Test layout with single-character entries"""
        layout = [
            ["a", "あ", ""],       # input, output, pending
            ["i", "い", ""],
            ["u", "う", ""],
        ]
        processor = SimultaneousInputProcessor(layout)

        # Should have 1 bucket (for length-1 keys)
        assert len(processor.simultaneous_map) == 1
        assert "a" in processor.simultaneous_map[0]
        assert processor.simultaneous_map[0]["a"]["output"] == "あ"
        assert processor.simultaneous_map[0]["a"]["pending"] == ""

    def test_multi_char_entries(self):
        """Test layout with multi-character entries"""
        layout = [
            ["a", "あ", ""],
            ["ka", "か", ""],
            ["kya", "きゃ", ""],
        ]
        processor = SimultaneousInputProcessor(layout)

        # Should have 3 buckets (for length 1, 2, 3)
        assert len(processor.simultaneous_map) == 3
        assert "a" in processor.simultaneous_map[0]      # length-1
        assert "ka" in processor.simultaneous_map[1]     # length-2
        assert "kya" in processor.simultaneous_map[2]    # length-3

    def test_simultaneous_entry_with_timing(self):
        """Test that simultaneous entries store simul_limit_ms correctly"""
        layout = [
            ["a", "あ", ""],
            ["jk", "じゅ", "", 50],  # simultaneous entry with 50ms limit
        ]
        processor = SimultaneousInputProcessor(layout)

        # Regular entry should have None (no timing)
        assert processor.simultaneous_map[0]["a"]["simul_limit_ms"] is None

        # Simultaneous entry should have the timing value
        assert processor.simultaneous_map[1]["jk"]["simul_limit_ms"] == 50

    def test_max_simul_limit_ms_tracked(self):
        """Test that max_simul_limit_ms tracks the highest timing value"""
        layout = [
            ["jk", "じゅ", "", 50],
            ["df", "だ", "", 80],
            ["as", "あ", "", 30],
        ]
        processor = SimultaneousInputProcessor(layout)

        assert processor.max_simul_limit_ms == 80

    def test_empty_input_string_skipped(self):
        """Test that entries with empty input string are skipped"""
        layout = [
            ["", "empty", ""],  # should be skipped
            ["a", "あ", ""],
        ]
        processor = SimultaneousInputProcessor(layout)

        # Should only have the "a" entry
        assert len(processor.simultaneous_map) == 1
        assert "a" in processor.simultaneous_map[0]


class TestGetLayoutOutput:
    """Test suite for get_layout_output() method"""

    @pytest.fixture
    def simple_romaji_layout(self):
        """Simple romaji layout for testing"""
        return [
            ["a", "あ", ""],
            ["i", "い", ""],
            ["ka", "か", ""],
            ["ki", "き", ""],
            ["k", "", "k"],  # k alone waits for vowel
        ]

    @pytest.fixture
    def simultaneous_layout(self):
        """Layout with simultaneous input entries"""
        return [
            ["a", "あ", ""],
            ["k", "", "k"],
            ["ka", "か", ""],
            ["jk", "じゅ", "", 50],  # simultaneous: j+k within 50ms
            ["df", "だ", "", 50],    # simultaneous: d+f within 50ms
        ]

    def test_key_release_returns_pending_unchanged(self, simple_romaji_layout):
        """Test that key release returns past_pending and resets timing"""
        processor = SimultaneousInputProcessor(simple_romaji_layout)

        output, pending = processor.get_layout_output("abc", "x", is_pressed=False)

        assert output == "abc"
        assert pending is None

    def test_single_char_romaji_match(self, simple_romaji_layout):
        """Test simple single-character romaji lookup"""
        processor = SimultaneousInputProcessor(simple_romaji_layout)

        output, pending = processor.get_layout_output("", "a", is_pressed=True)

        assert output == "あ"
        assert pending == ""

    def test_multi_char_romaji_match(self, simple_romaji_layout):
        """Test multi-character romaji lookup (e.g., 'ka' -> 'か')"""
        processor = SimultaneousInputProcessor(simple_romaji_layout)

        # Simulate: past_pending="k", input="a" -> lookup "ka"
        output, pending = processor.get_layout_output("k", "a", is_pressed=True)

        assert output == "か"
        assert pending == ""

    def test_pending_char_waiting_for_vowel(self, simple_romaji_layout):
        """Test that 'k' alone returns pending='k' waiting for vowel"""
        processor = SimultaneousInputProcessor(simple_romaji_layout)

        output, pending = processor.get_layout_output("", "k", is_pressed=True)

        assert output == ""
        assert pending == "k"

    def test_no_match_returns_input_as_output(self, simple_romaji_layout):
        """Test that unmatched input is returned as output"""
        processor = SimultaneousInputProcessor(simple_romaji_layout)

        # "x" is not in the layout
        output, pending = processor.get_layout_output("", "x", is_pressed=True)

        assert output == "x"
        assert pending is None

    def test_simultaneous_within_time_window(self, simultaneous_layout):
        """Test simultaneous input when typed within time limit"""
        processor = SimultaneousInputProcessor(simultaneous_layout)

        # Mock time to simulate fast typing (within 50ms)
        with patch('time.perf_counter') as mock_time:
            # First key press at t=0
            mock_time.return_value = 0.0
            processor.previous_typed_timestamp = 0.0

            # Second key press at t=0.030 (30ms later, within 50ms limit)
            mock_time.return_value = 0.030
            output, pending = processor.get_layout_output("j", "k", is_pressed=True)

        assert output == "じゅ"
        assert pending == ""

    def test_simultaneous_timed_out_falls_back(self, simultaneous_layout):
        """Test simultaneous input falls back when timed out"""
        processor = SimultaneousInputProcessor(simultaneous_layout)

        # Mock time to simulate slow typing (>50ms)
        with patch('time.perf_counter') as mock_time:
            # First key press at t=0
            mock_time.return_value = 0.0
            processor.previous_typed_timestamp = 0.0

            # Second key press at t=0.100 (100ms later, exceeds 50ms limit)
            mock_time.return_value = 0.100
            output, pending = processor.get_layout_output("j", "k", is_pressed=True)

        # Should NOT match "jk" simultaneous entry
        # Should fall back to just "k" which is "", "k" (pending)
        # And "j" becomes dropped_prefix added to output
        assert output == "j"
        assert pending == "k"

    def test_dropped_prefix_included_in_output(self):
        """Test that dropped prefix is included when falling back to shorter keys"""
        layout = [
            ["a", "あ", ""],
            ["c", "っ", ""],  # only "c" is defined, not "bc" or "abc"
        ]
        processor = SimultaneousInputProcessor(layout)

        # past_pending="ab", input="c"
        # "abc" not found, "bc" not found, "c" found
        # dropped_prefix = "ab"
        output, pending = processor.get_layout_output("ab", "c", is_pressed=True)

        assert output == "abっ"  # "ab" + "っ"
        assert pending == ""

    def test_long_pending_uses_max_tail_len(self):
        """Test that very long past_pending is handled efficiently"""
        layout = [
            ["a", "あ", ""],
            ["xa", "特", ""],  # only up to 2-char keys
        ]
        processor = SimultaneousInputProcessor(layout)

        # Very long past_pending, but layout only has up to 2-char keys
        # Should only try "za" and "a", not "yza", "xyza", etc.
        output, pending = processor.get_layout_output("xyz", "a", is_pressed=True)

        # "xyza" not found, "yza" not found (not tried due to max_tail_len)
        # "za" not found, "a" found -> output="xyz" + "あ"
        assert output == "xyzあ"
        assert pending == ""

    def test_fallback_chain_with_multiple_lengths(self):
        """Test the full fallback chain from longest to shortest"""
        layout = [
            ["c", "C", ""],
            ["bc", "BC", ""],
            # "abc" is NOT defined
        ]
        processor = SimultaneousInputProcessor(layout)

        # past_pending="ab", input="c"
        # Try "abc" -> not found
        # Try "bc" -> found! output="BC", dropped_prefix="a"
        output, pending = processor.get_layout_output("ab", "c", is_pressed=True)

        assert output == "aBC"  # "a" + "BC"
        assert pending == ""


class TestSimultaneousReset:
    """Test suite for simultaneous_reset() method"""

    def test_reset_offsets_timestamp_backward(self):
        """Test that reset moves timestamp backward by max_simul_limit_ms"""
        layout = [
            ["jk", "じゅ", "", 50],
        ]
        processor = SimultaneousInputProcessor(layout)

        # Set a known timestamp
        processor.previous_typed_timestamp = 1000.0

        processor.simultaneous_reset()

        # Should be offset backward by max_simul_limit_ms * 1000 (50 * 1000 = 50000)
        expected = 1000.0 - (50 * 1000)
        assert processor.previous_typed_timestamp == expected


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_past_pending(self):
        """Test with empty past_pending string"""
        layout = [
            ["a", "あ", ""],
        ]
        processor = SimultaneousInputProcessor(layout)

        output, pending = processor.get_layout_output("", "a", is_pressed=True)

        assert output == "あ"
        assert pending == ""

    def test_single_char_past_pending(self):
        """Test with single-character past_pending"""
        layout = [
            ["a", "あ", ""],
            ["ka", "か", ""],
        ]
        processor = SimultaneousInputProcessor(layout)

        output, pending = processor.get_layout_output("k", "a", is_pressed=True)

        assert output == "か"
        assert pending == ""

    def test_layout_with_only_long_keys(self):
        """Test layout that only has long keys (no single-char fallback)"""
        layout = [
            ["abc", "長", ""],
        ]
        processor = SimultaneousInputProcessor(layout)

        # Single char "x" won't match anything
        output, pending = processor.get_layout_output("", "x", is_pressed=True)

        assert output == "x"
        assert pending is None

    def test_pending_preserved_through_chain(self):
        """Test that entry's pending value is returned correctly"""
        layout = [
            ["k", "", "k"],      # k waits, pending="k"
            ["ka", "か", ""],    # ka outputs, pending=""
            ["ky", "", "ky"],   # ky waits, pending="ky"
        ]
        processor = SimultaneousInputProcessor(layout)

        # Type "k" -> should wait
        output, pending = processor.get_layout_output("", "k", is_pressed=True)
        assert output == ""
        assert pending == "k"

        # Type "y" with past_pending="k" -> should wait for "kya", "kyu", etc.
        output, pending = processor.get_layout_output("k", "y", is_pressed=True)
        assert output == ""
        assert pending == "ky"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
