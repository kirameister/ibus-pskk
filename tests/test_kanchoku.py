#!/usr/bin/env python3
# tests/test_kanchoku.py - Unit tests for kanchoku.py

import pytest
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from kanchoku import KanchokuProcessor, MISSING_KANCHOKU_KANJI


class TestKanchokuProcessorInit:
    """Test suite for KanchokuProcessor initialization"""

    def test_init_with_valid_layout(self):
        """Test initialization with a valid nested dict layout"""
        layout = {
            'a': {'a': '亜', 'b': '以'},
            'b': {'a': '宇', 'b': '江'},
        }
        processor = KanchokuProcessor(layout)

        assert processor.layout == layout
        assert processor._first_stroke is None

    def test_init_with_empty_layout(self):
        """Test initialization with empty layout"""
        processor = KanchokuProcessor({})

        assert processor.layout == {}
        assert processor._first_stroke is None

    def test_init_with_none_layout(self):
        """Test initialization with None layout"""
        processor = KanchokuProcessor(None)

        assert processor.layout == {}
        assert processor._first_stroke is None


class TestLookupKanji:
    """Test suite for _lookup_kanji() method"""

    @pytest.fixture
    def sample_layout(self):
        """Sample kanchoku layout for testing"""
        return {
            'q': {'q': '一', 'w': '二', 'e': '三'},
            'a': {'s': '日', 'd': '月', 'f': '火'},
            'z': {'x': '水', 'c': '木', 'v': '金'},
        }

    def test_lookup_valid_combination(self, sample_layout):
        """Test looking up a valid key combination"""
        processor = KanchokuProcessor(sample_layout)

        assert processor._lookup_kanji('q', 'q') == '一'
        assert processor._lookup_kanji('q', 'w') == '二'
        assert processor._lookup_kanji('a', 's') == '日'
        assert processor._lookup_kanji('z', 'v') == '金'

    def test_lookup_invalid_first_key(self, sample_layout):
        """Test lookup with invalid first key returns placeholder"""
        processor = KanchokuProcessor(sample_layout)

        result = processor._lookup_kanji('x', 'a')

        assert result == MISSING_KANCHOKU_KANJI

    def test_lookup_invalid_second_key(self, sample_layout):
        """Test lookup with invalid second key returns placeholder"""
        processor = KanchokuProcessor(sample_layout)

        result = processor._lookup_kanji('q', 'z')  # 'z' not in 'q' row

        assert result == MISSING_KANCHOKU_KANJI

    def test_lookup_empty_string_value(self):
        """Test lookup when layout has empty string value returns placeholder"""
        layout = {
            'a': {'b': ''},  # Empty string value
        }
        processor = KanchokuProcessor(layout)

        result = processor._lookup_kanji('a', 'b')

        assert result == MISSING_KANCHOKU_KANJI

    def test_lookup_with_empty_layout(self):
        """Test lookup with empty layout returns placeholder"""
        processor = KanchokuProcessor({})

        result = processor._lookup_kanji('a', 'b')

        assert result == MISSING_KANCHOKU_KANJI


class TestProcessKey:
    """Test suite for process_key() method"""

    @pytest.fixture
    def sample_layout(self):
        """Sample kanchoku layout for testing"""
        return {
            'j': {'k': '日', 'l': '本'},
            'k': {'j': '語', 'l': '学'},
        }

    def test_first_stroke_sets_pending(self, sample_layout):
        """Test that first stroke is stored and returned as pending"""
        processor = KanchokuProcessor(sample_layout)

        output, pending, consumed = processor.process_key('j', is_pressed=True)

        assert output is None
        assert pending == 'j'
        assert consumed is True
        assert processor._first_stroke == 'j'

    def test_second_stroke_returns_kanji(self, sample_layout):
        """Test that second stroke looks up and returns kanji"""
        processor = KanchokuProcessor(sample_layout)

        # First stroke
        processor.process_key('j', is_pressed=True)

        # Second stroke
        output, pending, consumed = processor.process_key('k', is_pressed=True)

        assert output == '日'
        assert pending is None
        assert consumed is True
        assert processor._first_stroke is None  # Reset after completion

    def test_key_release_not_processed(self, sample_layout):
        """Test that key release events are not processed"""
        processor = KanchokuProcessor(sample_layout)

        # First stroke press
        processor.process_key('j', is_pressed=True)

        # First stroke release - should not change state
        output, pending, consumed = processor.process_key('j', is_pressed=False)

        assert output is None
        assert pending == 'j'  # Still waiting
        assert consumed is False
        assert processor._first_stroke == 'j'

    def test_invalid_first_stroke(self, sample_layout):
        """Test that invalid first stroke key is not consumed"""
        processor = KanchokuProcessor(sample_layout)

        output, pending, consumed = processor.process_key('x', is_pressed=True)

        assert output is None
        assert pending is None
        assert consumed is False
        assert processor._first_stroke is None

    def test_invalid_second_stroke_returns_first_stroke(self, sample_layout):
        """Test that invalid second stroke returns first stroke and doesn't consume"""
        processor = KanchokuProcessor(sample_layout)

        # Valid first stroke
        processor.process_key('j', is_pressed=True)

        # Invalid second stroke (not in layout at all)
        output, pending, consumed = processor.process_key('x', is_pressed=True)

        assert output == 'j'  # Return the first stroke
        assert pending is None
        assert consumed is False  # Key not consumed, let caller handle it
        assert processor._first_stroke is None  # Reset

    def test_complete_sequence_j_k(self, sample_layout):
        """Test complete kanchoku sequence: j -> k -> '日'"""
        processor = KanchokuProcessor(sample_layout)

        # Press j
        o1, p1, c1 = processor.process_key('j', is_pressed=True)
        assert o1 is None
        assert p1 == 'j'
        assert c1 is True

        # Release j (should not affect state)
        o2, p2, c2 = processor.process_key('j', is_pressed=False)
        assert o2 is None
        assert p2 == 'j'
        assert c2 is False

        # Press k
        o3, p3, c3 = processor.process_key('k', is_pressed=True)
        assert o3 == '日'
        assert p3 is None
        assert c3 is True

        # Release k
        o4, p4, c4 = processor.process_key('k', is_pressed=False)
        assert o4 is None
        assert p4 is None
        assert c4 is False

    def test_multiple_sequences(self, sample_layout):
        """Test multiple kanchoku sequences in succession"""
        processor = KanchokuProcessor(sample_layout)

        # First sequence: j + k -> '日'
        processor.process_key('j', is_pressed=True)
        output1, _, _ = processor.process_key('k', is_pressed=True)
        assert output1 == '日'

        # Second sequence: k + j -> '語'
        processor.process_key('k', is_pressed=True)
        output2, _, _ = processor.process_key('j', is_pressed=True)
        assert output2 == '語'

        # Third sequence: j + l -> '本'
        processor.process_key('j', is_pressed=True)
        output3, _, _ = processor.process_key('l', is_pressed=True)
        assert output3 == '本'


class TestIsWaitingForSecondStroke:
    """Test suite for is_waiting_for_second_stroke() method"""

    def test_not_waiting_initially(self):
        """Test that processor is not waiting initially"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        assert processor.is_waiting_for_second_stroke() is False

    def test_waiting_after_first_stroke(self):
        """Test that processor is waiting after first stroke"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        processor.process_key('a', is_pressed=True)

        assert processor.is_waiting_for_second_stroke() is True

    def test_not_waiting_after_second_stroke(self):
        """Test that processor is not waiting after second stroke completes"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        processor.process_key('a', is_pressed=True)
        processor.process_key('b', is_pressed=True)

        assert processor.is_waiting_for_second_stroke() is False


class TestGetFirstStroke:
    """Test suite for get_first_stroke() method"""

    def test_none_initially(self):
        """Test that get_first_stroke returns None initially"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        assert processor.get_first_stroke() is None

    def test_returns_first_stroke_when_waiting(self):
        """Test that get_first_stroke returns the pending stroke"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        processor.process_key('a', is_pressed=True)

        assert processor.get_first_stroke() == 'a'

    def test_none_after_completion(self):
        """Test that get_first_stroke returns None after completion"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        processor.process_key('a', is_pressed=True)
        processor.process_key('b', is_pressed=True)

        assert processor.get_first_stroke() is None


class TestCancel:
    """Test suite for cancel() method"""

    def test_cancel_returns_none_when_not_waiting(self):
        """Test that cancel returns None when no stroke pending"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        result = processor.cancel()

        assert result is None

    def test_cancel_returns_first_stroke_when_waiting(self):
        """Test that cancel returns the pending first stroke"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        processor.process_key('a', is_pressed=True)
        result = processor.cancel()

        assert result == 'a'
        assert processor._first_stroke is None

    def test_cancel_resets_state(self):
        """Test that cancel resets the processor state"""
        processor = KanchokuProcessor({'a': {'b': '字'}})

        processor.process_key('a', is_pressed=True)
        processor.cancel()

        assert processor.is_waiting_for_second_stroke() is False
        assert processor.get_first_stroke() is None


class TestGetValidKeys:
    """Test suite for get_valid_keys() method"""

    def test_returns_first_stroke_keys(self):
        """Test that get_valid_keys returns all first-stroke keys"""
        layout = {
            'a': {'x': '1'},
            'b': {'y': '2'},
            'c': {'z': '3'},
        }
        processor = KanchokuProcessor(layout)

        valid_keys = processor.get_valid_keys()

        assert valid_keys == {'a', 'b', 'c'}

    def test_empty_layout_returns_empty_set(self):
        """Test that empty layout returns empty set"""
        processor = KanchokuProcessor({})

        valid_keys = processor.get_valid_keys()

        assert valid_keys == set()


class TestGetSecondStrokeKeys:
    """Test suite for get_second_stroke_keys() method"""

    def test_returns_second_stroke_keys_for_valid_first(self):
        """Test that get_second_stroke_keys returns valid second strokes"""
        layout = {
            'a': {'x': '1', 'y': '2', 'z': '3'},
            'b': {'m': '4', 'n': '5'},
        }
        processor = KanchokuProcessor(layout)

        second_keys = processor.get_second_stroke_keys('a')

        assert second_keys == {'x', 'y', 'z'}

    def test_returns_empty_for_invalid_first_stroke(self):
        """Test that invalid first stroke returns empty set"""
        layout = {
            'a': {'x': '1'},
        }
        processor = KanchokuProcessor(layout)

        second_keys = processor.get_second_stroke_keys('invalid')

        assert second_keys == set()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_punctuation_keys(self):
        """Test kanchoku with punctuation keys like ; , . /"""
        layout = {
            ';': {',': '読', '.': '点'},
            ',': {';': '句', '/': '線'},
        }
        processor = KanchokuProcessor(layout)

        # Test ; + , -> 読
        processor.process_key(';', is_pressed=True)
        output, _, _ = processor.process_key(',', is_pressed=True)

        assert output == '読'

    def test_same_key_twice(self):
        """Test pressing the same key as first and second stroke"""
        layout = {
            'a': {'a': '双', 'b': '単'},
        }
        processor = KanchokuProcessor(layout)

        processor.process_key('a', is_pressed=True)
        output, _, _ = processor.process_key('a', is_pressed=True)

        assert output == '双'

    def test_unicode_kanji_values(self):
        """Test various Unicode kanji characters"""
        layout = {
            'a': {
                'a': '漢',  # Common kanji
                'b': '𠀋',  # CJK Extension B (rare kanji)
                'c': '々',  # Ideographic iteration mark
            },
        }
        processor = KanchokuProcessor(layout)

        processor.process_key('a', is_pressed=True)
        output1, _, _ = processor.process_key('a', is_pressed=True)
        assert output1 == '漢'

        processor.process_key('a', is_pressed=True)
        output2, _, _ = processor.process_key('b', is_pressed=True)
        assert output2 == '𠀋'

        processor.process_key('a', is_pressed=True)
        output3, _, _ = processor.process_key('c', is_pressed=True)
        assert output3 == '々'

    def test_rapid_sequence_simulation(self):
        """Test rapid input simulation (first key release after second key press)"""
        layout = {
            'j': {'k': '日'},
        }
        processor = KanchokuProcessor(layout)

        # Simulate: j-down, k-down (before j-up), j-up, k-up
        # This can happen with fast typing

        # j-down
        o1, p1, c1 = processor.process_key('j', is_pressed=True)
        assert p1 == 'j'

        # k-down (while j still held)
        o2, p2, c2 = processor.process_key('k', is_pressed=True)
        assert o2 == '日'  # Kanji produced

        # j-up (after kanji already produced)
        o3, p3, c3 = processor.process_key('j', is_pressed=False)
        assert o3 is None
        assert c3 is False

        # k-up
        o4, p4, c4 = processor.process_key('k', is_pressed=False)
        assert o4 is None
        assert c4 is False

    def test_state_after_invalid_second_stroke(self):
        """Test that state is properly reset after invalid second stroke"""
        layout = {
            'a': {'b': '字'},
            'c': {'d': '文'},
        }
        processor = KanchokuProcessor(layout)

        # First stroke
        processor.process_key('a', is_pressed=True)
        assert processor.is_waiting_for_second_stroke() is True

        # Invalid second stroke (not in 'a' row)
        processor.process_key('z', is_pressed=True)
        assert processor.is_waiting_for_second_stroke() is False

        # Should be able to start a new sequence
        processor.process_key('c', is_pressed=True)
        assert processor.is_waiting_for_second_stroke() is True
        assert processor.get_first_stroke() == 'c'


class TestMissingKanchokuKanji:
    """Test the MISSING_KANCHOKU_KANJI constant behavior"""

    def test_missing_kanji_constant_value(self):
        """Test that MISSING_KANCHOKU_KANJI has expected value"""
        assert MISSING_KANCHOKU_KANJI == "無"

    def test_missing_kanji_returned_for_empty_value(self):
        """Test that empty layout values return MISSING_KANCHOKU_KANJI via _lookup_kanji"""
        # Layout where a valid combo maps to empty string
        layout = {
            'a': {'b': ''},  # Empty string value
        }
        processor = KanchokuProcessor(layout)

        # Direct lookup returns MISSING_KANCHOKU_KANJI
        result = processor._lookup_kanji('a', 'b')
        assert result == MISSING_KANCHOKU_KANJI

    def test_invalid_second_stroke_returns_first_stroke(self):
        """Test that invalid second stroke returns first stroke (not MISSING_KANCHOKU_KANJI)"""
        # When second stroke is invalid, we abort the kanchoku sequence
        # and return the first stroke so it can be output normally
        layout = {
            'a': {'b': '有'},
            'c': {'d': '別'},  # 'c' is valid first stroke
        }
        processor = KanchokuProcessor(layout)

        processor.process_key('a', is_pressed=True)
        # 'c' is NOT a valid second stroke for 'a' (it's not in 'a' row)
        output, pending, consumed = processor.process_key('c', is_pressed=True)

        # Should return first stroke 'a' and NOT consume the 'c' key
        assert output == 'a'
        assert pending is None
        assert consumed is False
        # Processor should be reset
        assert processor.is_waiting_for_second_stroke() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
