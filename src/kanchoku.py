#!/usr/bin/env python3
# kanchoku.py - Processor for kanchoku (漢直) direct kanji input

import logging

logger = logging.getLogger(__name__)

# Placeholder character when a key combination has no assigned kanji
MISSING_KANCHOKU_KANJI = '無'


class KanchokuProcessor:
    """
    Processor for kanchoku (漢直) two-stroke direct kanji input.

    Kanchoku is a Japanese input method where kanji are entered directly
    by pressing two keys in sequence. The first key selects a "row" and
    the second key selects a specific character within that row.

    This is also known as "murenso" (無連想) input - meaning "no association"
    because unlike romaji input, there's no phonetic relationship between
    the keys pressed and the resulting kanji.

    Example:
        - Press 'j' then 'k' -> outputs '日' (depending on layout)
        - Press 'a' then 's' -> outputs '本' (depending on layout)
    """

    def __init__(self, kanchoku_layout):
        """
        Initialize the processor with kanchoku layout data.

        Args:
            kanchoku_layout: Nested dictionary mapping first_key -> second_key -> kanji.
                            Structure: {'j': {'k': '日', 'l': '月', ...}, ...}
        """
        self.layout = kanchoku_layout if kanchoku_layout else {}
        self._first_stroke = None
        self._reset()

    def _reset(self):
        """Reset the processor state, clearing any pending first stroke."""
        self._first_stroke = None

    def is_waiting_for_second_stroke(self):
        """
        Check if the processor is waiting for a second stroke.

        Returns:
            bool: True if a first stroke has been entered and we're waiting
                  for the second stroke to complete the kanji input.
        """
        return self._first_stroke is not None

    def get_first_stroke(self):
        """
        Get the current first stroke if one is pending.

        Returns:
            str or None: The first stroke character, or None if not waiting.
        """
        return self._first_stroke

    def process_key(self, key_char, is_pressed):
        """
        Process a key input for kanchoku conversion.

        This method handles the two-stroke kanchoku input sequence:
        1. First stroke: Store the key and return it as pending
        2. Second stroke: Look up the kanji and return it as output

        Args:
            key_char: The input character (single lowercase letter or punctuation)
            is_pressed: True if key press, False if key release

        Returns:
            tuple: (output, pending, consumed)
                - output: The kanji character if second stroke completes a combo,
                         or None if still waiting
                - pending: The first stroke character if waiting for second stroke,
                          or None if not in kanchoku sequence
                - consumed: True if this key was consumed by the processor
        """
        # Only process key presses, not releases
        if not is_pressed:
            return None, self._first_stroke, False

        # Check if this key is valid for kanchoku input
        if key_char not in self.layout:
            # Key not in kanchoku layout
            if self._first_stroke is not None:
                # We had a first stroke pending but second stroke is invalid
                # Return the first stroke as output and don't consume this key
                first = self._first_stroke
                self._reset()
                return first, None, False
            return None, None, False

        if self._first_stroke is None:
            # This is the first stroke
            self._first_stroke = key_char
            logger.debug(f'Kanchoku: first stroke "{key_char}"')
            return None, key_char, True

        # This is the second stroke - look up the kanji
        first = self._first_stroke
        second = key_char

        kanji = self._lookup_kanji(first, second)
        logger.debug(f'Kanchoku: "{first}" + "{second}" -> "{kanji}"')

        self._reset()
        return kanji, None, True

    def _lookup_kanji(self, first_key, second_key):
        """
        Look up a kanji character from the layout.

        Args:
            first_key: The first stroke character
            second_key: The second stroke character

        Returns:
            str: The kanji character, or MISSING_KANCHOKU_KANJI if not found
        """
        if first_key not in self.layout:
            return MISSING_KANCHOKU_KANJI

        row = self.layout[first_key]
        if second_key not in row:
            return MISSING_KANCHOKU_KANJI

        kanji = row[second_key]
        if not kanji or kanji == '':
            return MISSING_KANCHOKU_KANJI

        return kanji

    def cancel(self):
        """
        Cancel the current kanchoku sequence and return any pending stroke.

        This is useful when the user wants to abort a kanchoku input,
        for example by pressing Escape or switching modes.

        Returns:
            str or None: The pending first stroke character, or None if none pending
        """
        first = self._first_stroke
        self._reset()
        return first

    def get_valid_keys(self):
        """
        Get the set of valid first-stroke keys.

        Returns:
            set: Set of characters that can be used as first strokes
        """
        return set(self.layout.keys())

    def get_second_stroke_keys(self, first_stroke):
        """
        Get the set of valid second-stroke keys for a given first stroke.

        Args:
            first_stroke: The first stroke character

        Returns:
            set: Set of characters that can be used as second strokes,
                 or empty set if first_stroke is invalid
        """
        if first_stroke not in self.layout:
            return set()
        return set(self.layout[first_stroke].keys())
