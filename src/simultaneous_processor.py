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
        self.layout_data = layout_data # this is raw-loaded data
        self.simultaneous_map = dict() # this is the parsed and modified dictionary
        self.simul_candidate_char_set = set()
        self.max_simul_limit_ms = 0 # this is to identify the max limit of simul-typing -- passed this limit, there is no simul-typing

        self._build_simultaneous_map()

    def _build_simultaneous_map(self):
        """
        Build internal mapping for simultaneous input detection
        from the layout data.
        """
        if not self.layout_data:
            logger.warning("No layout data provided")
            return

        # Extract simultaneous input definitions from layout
        for l in self.layout_data:
            # l is a list where the 0th element is input
            input_len = len(l[0])
            input_str = l[0]
            list_values = dict()
            if(input_len == 0):
                logger.warning('input str len == 0 detected; skipping..')
                continue
            if(input_len > 3):
                logger.warning(f'len of input str is bigger than 3; skipping.. : {l}')
                continue
            list_values["output"] = str(l[1])
            list_values["pending"] = str(l[2])
            if(len(l) == 4 and type(l[3]) == int): # this entry is about simultaneous input
                self.max_simul_limit_ms = max(l[3], self.max_simul_limit_ms)
                list_values["simul_limit_ms"] = l[3]
            else:
                list_values["simul_limit_ms"] = 0
            self.simultaneous_map[input_str] = list_values
            #logger.debug(f'_load_layout -- layout element added {input_str} => {list_values}')
            if(input_len >= 2):
                self.simul_candidate_char_set.add(input_str[:-1])

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
