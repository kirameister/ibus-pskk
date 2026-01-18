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
        self.simul_candidate_char_set = set()
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
            if input_len >= 2 and type(l[3]) == int and l[3] > 0:
                self.simul_candidate_char_set.add(input_str[:-1])

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

        if input_char not in self.simul_candidate_char_set:
            self.simultaneous_reset()
            return past_pending, None

        current_time = time.perf_counter()
        time_diff_ms = (current_time - self.previous_typed_timestamp) * 1000

        # Only consider the last 2 chars of past_pending (max input length is 3)
        pending_tail = past_pending[-2:] if len(past_pending) > 2 else past_pending

        # Form the lookup key combining pending tail with new input
        lookup_key = pending_tail + input_char

        # Check if this combination exists in the map
        entry = self.simultaneous_map.get(lookup_key)

        if entry:
            simul_limit = entry.get("simul_limit_ms", 0)

            # If it's a simultaneous entry, check if within time window
            if simul_limit > 0 and time_diff_ms > simul_limit:
                # Timed out - simultaneous window expired
                entry = None
            else:
                # Valid match (non-simultaneous or within time window)
                self.previous_typed_timestamp = current_time
                return entry["output"], entry["pending"]

        # No valid combination match - try single character lookup
        entry = self.simultaneous_map.get(input_char)
        if entry:
            # Reset timing for new potential simultaneous sequence
            self.previous_typed_timestamp = current_time
            return entry["output"], entry["pending"]

        # No match found
        self.previous_typed_timestamp = current_time
        return None, None

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
