#!/usr/bin/env python3
# henkan.py - Kana to Kanji conversion (変換) processor

import json
import logging
import os

import util

logger = logging.getLogger(__name__)


class HenkanProcessor:
    """
    Processor for kana-to-kanji conversion (かな漢字変換).

    This class handles the conversion of kana strings (or kana+kanji strings)
    into 漢字かな混じり (kanji-kana mixed) text based on dictionary entries.

    The conversion operates on bunsetsu (文節) units - meaningful phrase
    boundaries in Japanese text.

    Dictionary format (JSON):
        {
            "reading": {"candidate1": count1, "candidate2": count2, ...},
            ...
        }
    where count represents the frequency/priority (higher is better).
    """

    def __init__(self, dictionary_files=None):
        """
        Initialize the HenkanProcessor.

        Args:
            dictionary_files: List of paths to dictionary JSON files.
                             Files are loaded in order; later files can
                             add new entries or increase counts for existing ones.
        """
        # Merged dictionary: {reading: {candidate: count}}
        self._dictionary = {}
        self._candidates = []    # Current conversion candidates
        self._selected_index = 0 # Currently selected candidate index
        self._dictionary_count = 0  # Number of successfully loaded dictionaries

        # CRF tagger for bunsetsu prediction (lazy loaded)
        self._tagger = None

        if dictionary_files:
            self._load_dictionaries(dictionary_files)

    def _load_dictionaries(self, dictionary_files):
        """
        Load and merge multiple dictionary files.

        Each dictionary file is a JSON object mapping readings to candidates:
            {"reading": {"candidate1": count1, "candidate2": count2}}

        When merging, counts are summed for duplicate candidates.

        Args:
            dictionary_files: List of paths to dictionary JSON files
        """
        for file_path in dictionary_files:
            if not os.path.exists(file_path):
                logger.warning(f'Dictionary file not found: {file_path}')
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if not isinstance(data, dict):
                    logger.warning(f'Invalid dictionary format (expected dict): {file_path}')
                    continue

                # Merge into main dictionary
                entries_added = 0
                for reading, candidates in data.items():
                    if not isinstance(candidates, dict):
                        continue

                    if reading not in self._dictionary:
                        self._dictionary[reading] = {}

                    for candidate, count in candidates.items():
                        if not isinstance(count, (int, float)):
                            count = 1
                        if candidate in self._dictionary[reading]:
                            self._dictionary[reading][candidate] += count
                        else:
                            self._dictionary[reading][candidate] = count
                        entries_added += 1

                self._dictionary_count += 1
                logger.info(f'Loaded dictionary: {file_path} ({entries_added} candidate entries)')

            except json.JSONDecodeError as e:
                logger.error(f'Failed to parse dictionary JSON: {file_path} - {e}')
            except Exception as e:
                logger.error(f'Failed to load dictionary: {file_path} - {e}')

        logger.info(f'HenkanProcessor initialized with {self._dictionary_count} dictionaries, '
                   f'{len(self._dictionary)} readings')

    def convert(self, reading):
        """
        Convert a kana reading to kanji candidates.

        Args:
            reading: The kana string to convert (e.g., "へんかん")

        Returns:
            list: List of conversion candidates, each being a dict with:
                  - 'surface': The converted text (e.g., "変換")
                  - 'reading': The original reading (e.g., "へんかん")
                  - 'cost': Conversion cost/priority (lower is better)

                  Returns list with original reading if no candidates found.
        """
        self._candidates = []
        self._selected_index = 0

        if reading in self._dictionary:
            candidates_dict = self._dictionary[reading]
            # Sort by count (descending) - higher count = lower cost = better candidate
            sorted_candidates = sorted(
                candidates_dict.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for surface, count in sorted_candidates:
                # Cost is inverse of count (higher count = lower cost)
                cost = 1.0 / (count + 1)
                self._candidates.append({
                    'surface': surface,
                    'reading': reading,
                    'cost': cost
                })
            logger.debug(f'HenkanProcessor.convert("{reading}") → {len(self._candidates)} candidates')
        else:
            # No dictionary match - return reading as-is
            self._candidates.append({
                'surface': reading,
                'reading': reading,
                'cost': 0
            })
            logger.debug(f'HenkanProcessor.convert("{reading}") → no match, returning reading')

        return self._candidates

    def get_candidates(self):
        """
        Get the current list of conversion candidates.

        Returns:
            list: List of candidate dictionaries
        """
        return self._candidates

    def select_candidate(self, index):
        """
        Select a candidate by index.

        Args:
            index: The index of the candidate to select

        Returns:
            dict or None: The selected candidate, or None if index is invalid
        """
        if 0 <= index < len(self._candidates):
            self._selected_index = index
            return self._candidates[index]
        return None

    def get_selected_candidate(self):
        """
        Get the currently selected candidate.

        Returns:
            dict or None: The selected candidate, or None if no candidates
        """
        if self._candidates and 0 <= self._selected_index < len(self._candidates):
            return self._candidates[self._selected_index]
        return None

    def next_candidate(self):
        """
        Move to the next candidate in the list.

        Returns:
            dict or None: The new selected candidate, or None if no candidates
        """
        if self._candidates:
            self._selected_index = (self._selected_index + 1) % len(self._candidates)
            return self._candidates[self._selected_index]
        return None

    def previous_candidate(self):
        """
        Move to the previous candidate in the list.

        Returns:
            dict or None: The new selected candidate, or None if no candidates
        """
        if self._candidates:
            self._selected_index = (self._selected_index - 1) % len(self._candidates)
            return self._candidates[self._selected_index]
        return None

    def reset(self):
        """
        Reset the processor state, clearing candidates and selection.
        """
        self._candidates = []
        self._selected_index = 0

    def get_dictionary_stats(self):
        """
        Get statistics about loaded dictionaries.

        Returns:
            dict: Dictionary containing:
                  - 'dictionary_count': Number of loaded dictionary files
                  - 'reading_count': Total number of unique readings
                  - 'candidate_count': Total number of candidate entries
        """
        candidate_count = sum(len(candidates) for candidates in self._dictionary.values())
        return {
            'dictionary_count': self._dictionary_count,
            'reading_count': len(self._dictionary),
            'candidate_count': candidate_count
        }

    # ─── CRF Bunsetsu Prediction ──────────────────────────────────────────

    def _load_tagger(self):
        """
        Lazy load the CRF tagger for bunsetsu prediction.

        Returns:
            bool: True if tagger is available, False otherwise
        """
        if self._tagger is not None:
            return True

        self._tagger = util.load_crf_tagger()
        return self._tagger is not None

    def predict_bunsetsu(self, input_text, n_best=5):
        """
        Predict bunsetsu segmentation using CRF N-best Viterbi.

        This method segments the input text into bunsetsu (phrase units),
        identifying which segments should be sent to dictionary lookup
        (Lookup bunsetsu) and which should be passed through as-is
        (Passthrough bunsetsu, typically particles like は、が、を).

        Args:
            input_text: Hiragana input string to segment
            n_best: Number of top predictions to return (default: 5)

        Returns:
            list: List of N-best predictions, each being a tuple of:
                  (bunsetsu_list, score)
                  where bunsetsu_list is a list of (text, label) tuples:
                      - text: The bunsetsu text
                      - label: The full CRF label ('B-L' for Lookup, 'B-P' for Passthrough)
                  To check bunsetsu type: label.endswith('-L') for Lookup,
                  label.endswith('-P') for Passthrough.
                  Returns empty list if tagger is unavailable or input is empty.

        Example:
            >>> processor.predict_bunsetsu("きょうはてんきがよい", n_best=3)
            [
                ([('きょう', 'B-L'), ('は', 'B-P'), ('てんき', 'B-L'), ('が', 'B-P'), ('よい', 'B-L')], -2.34),
                ([('きょうは', 'B-L'), ('てんき', 'B-L'), ('が', 'B-P'), ('よい', 'B-L')], -3.12),
                ...
            ]

            # Consecutive Lookup bunsetsu (e.g., 企業収益 = きぎょうしゅうえき):
            >>> processor.predict_bunsetsu("きぎょうしゅうえき", n_best=1)
            [
                ([('きぎょう', 'B-L'), ('しゅうえき', 'B-L')], -1.56),
            ]
        """
        if not input_text:
            return []

        if not self._load_tagger():
            logger.debug('CRF tagger not available for bunsetsu prediction')
            return []

        # Run N-best Viterbi prediction
        nbest_results = util.crf_nbest_predict(self._tagger, input_text, n_best=n_best)

        # Convert label sequences to bunsetsu lists
        output = []
        tokens = util.tokenize_line(input_text)

        for labels, score in nbest_results:
            bunsetsu_list = util.labels_to_bunsetsu(tokens, labels)
            output.append((bunsetsu_list, score))

        return output
