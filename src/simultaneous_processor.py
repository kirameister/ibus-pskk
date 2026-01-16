#!/usr/bin/env python3
# simultaneous_processor.py - Processor for simultaneous key input detection

import logging

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
        self.layout_data = layout_data
        self._build_simultaneous_map()

    def _build_simultaneous_map(self):
        """
        Build internal mapping for simultaneous input detection
        from the layout data.
        """
        self.simultaneous_map = {}

        if not self.layout_data:
            logger.warning("No layout data provided")
            return

        # Extract simultaneous input definitions from layout
        if "simultaneous" in self.layout_data:
            self.simultaneous_map = self.layout_data["simultaneous"]

    def is_simultaneous_trigger(self, input_entry):
        """
        Check if the given input entry should trigger simultaneous input.

        Args:
            input_entry: The input entry to check (e.g., a key or key combination)

        Returns:
            bool: True if the input should trigger simultaneous processing,
                  False otherwise.
        """
        if not self.simultaneous_map:
            return False

        return input_entry in self.simultaneous_map

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
