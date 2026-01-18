#!/usr/bin/env python3
# simultaneous_processor.py - Processor for simultaneous key input detection

import logging
import time

logger = logging.getLogger(__name__)


class SimultaneousInputProcessor:
    """
    Processor for detecting and handling simultaneous key input.

    This class is initialized with layout data and checks if a given
    input entry should trigger simultaneous input processing.
    """

    def __init__(self, layout_data):
        """
        Initialize the processor with layout data.

        Args:
            layout_data: Dictionary containing the layout configuration,
                         loaded from a layout JSON file.
        """
        self.layout_data = layout_data # this is raw-loaded data
        self.max_simul_limit_ms = 0 # this is to identify the max limit of simul-typing -- passed this limit, there is no simul-typing

        self._build_simultaneous_map()
        self.simultaneous_reset() # this is sort of an initialization

    def _build_simultaneous_map(self):
        """
        Build internal mapping for simultaneous input detection
        from the layout data.
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
                list_values["simul_limit_ms"] = -1 # Negative value in this case means that the layout has nothing to do with simul-typing; it works like normal romaji input
            self.simultaneous_map[input_len - 1][input_str] = list_values

    def simultaneous_reset(self):
        """
        Offset the internal previous_typed_timestamp backward
        The purpuse is that the following stroke will not be
        part of the simul-input
        """
        self.previous_typed_timestamp -= (self.max_simul_limit_ms) * 1000

    def get_layout_output(self, past_pending, input_char, is_pressed):
        """
        Return the output of the layer given the previous pending value
        and new keyval char input.

        Args:
            past_pending: Pending string from previous call
            input_char: New input keyval char
            is_pressed: True if key press, False if key release

        Returns:
            Tuple of (output, pending) strings, or (None, None) if no match.
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
            # tail_len=2: "ab"[-2:] + "c" = "abc"
            # tail_len=1: "ab"[-1:] + "c" = "bc"
            # tail_len=0: "" + "c" = "c"
            pending_tail = past_pending[-tail_len:] if tail_len > 0 else ""
            lookup_key = pending_tail + input_char

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
                    self.previous_typed_timestamp = current_time
                    return entry['output'], entry['pending']
                else:
                    # Timed out - don't use this entry, try shorter key
                    continue
            else:
                # This is a REGULAR romaji entry (no timing requirement)
                self.previous_typed_timestamp = current_time
                return entry["output"], entry["pending"]

        # No match found at any length - return everything as output, clear pending
        self.previous_typed_timestamp = current_time
        return past_pending + input_char, None

    def get_simultaneous_output(self, input_entry):
        """
        Get the output for a simultaneous input entry.

        Args:
            input_entry: The input entry to look up

        Returns:
            The output value if found, None otherwise.
        """
        if not self.simultaneous_map:
            return None

        return self.simultaneous_map.get(input_entry)
