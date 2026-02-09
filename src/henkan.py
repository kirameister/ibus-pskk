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
            "reading": {
                "candidate1": {"POS": "品詞", "cost": cost1},
                "candidate2": {"POS": "品詞", "cost": cost2},
                ...
            },
            ...
        }
    where cost represents the priority (lower cost = better candidate).
    """

    def __init__(self, dictionary_files=None):
        """
        Initialize the HenkanProcessor.

        Args:
            dictionary_files: List of paths to dictionary JSON files.
                             Files are loaded in order; later files can
                             add new entries or increase counts for existing ones.
        """
        # Merged dictionary: {reading: {candidate: {"POS": str, "cost": float}}}
        self._dictionary = {}
        self._candidates = []    # Current conversion candidates (whole-word mode)
        self._selected_index = 0 # Currently selected candidate index (whole-word mode)
        self._dictionary_count = 0  # Number of successfully loaded dictionaries

        # CRF tagger for bunsetsu prediction (lazy loaded)
        self._tagger = None
        # Pre-computed dictionary features for CRF (loaded once)
        self._crf_feature_materials = util.load_crf_feature_materials()

        # ─── Bunsetsu Mode State ───
        # Bunsetsu mode allows multi-bunsetsu conversion when:
        # 1. No dictionary match for full yomi (automatic fallback)
        # 2. User presses bunsetsu_prediction_cycle_key (manual switch)
        self._bunsetsu_mode = False
        self._current_yomi = ''  # The yomi being converted
        self._has_whole_word_match = False  # Whether dictionary has full yomi match

        # N-best bunsetsu predictions (filtered to multi-bunsetsu only)
        # Each entry: (bunsetsu_list, score) where bunsetsu_list is [(text, label), ...]
        self._bunsetsu_predictions = []
        self._bunsetsu_prediction_index = 0  # Current N-best index

        # Per-bunsetsu candidate state (for the current bunsetsu prediction)
        # _bunsetsu_candidates[i] = list of candidate dicts for bunsetsu i
        # _bunsetsu_selected_indices[i] = selected candidate index for bunsetsu i
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []
        self._selected_bunsetsu_index = 0  # Which bunsetsu is selected for navigation

        if dictionary_files:
            self._load_dictionaries(dictionary_files)

    def _load_dictionaries(self, dictionary_files):
        """
        Load and merge multiple dictionary files.

        Each dictionary file is a JSON object mapping readings to candidates:
            {"reading": {"candidate1": {"POS": "品詞", "cost": cost1}, ...}}

        When merging, the entry with lower cost is kept for duplicate candidates.

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

                    for candidate, entry in candidates.items():
                        # Entry should be {"POS": str, "cost": float}
                        if not isinstance(entry, dict):
                            # Handle legacy format (bare cost value)
                            entry = {"POS": "名詞", "cost": entry if isinstance(entry, (int, float)) else 0}

                        if candidate in self._dictionary[reading]:
                            # Keep entry with lower cost (better candidate)
                            existing_cost = self._dictionary[reading][candidate].get("cost", 0)
                            new_cost = entry.get("cost", 0)
                            if new_cost < existing_cost:
                                self._dictionary[reading][candidate] = entry
                        else:
                            self._dictionary[reading][candidate] = entry
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

        If a dictionary match exists for the full reading, returns those candidates
        (whole-word mode). If no match exists, automatically falls back to
        bunsetsu-based conversion using CRF prediction.

        Args:
            reading: The kana string to convert (e.g., "へんかん")

        Returns:
            list: List of conversion candidates, each being a dict with:
                  - 'surface': The converted text (e.g., "変換")
                  - 'reading': The original reading (e.g., "へんかん")
                  - 'cost': Conversion cost/priority (lower is better)

                  In bunsetsu mode, the candidates list contains a single entry
                  with the combined surface from all bunsetsu.
        """
        # Reset state
        self._candidates = []
        self._selected_index = 0
        self._current_yomi = reading
        self._bunsetsu_mode = False
        self._bunsetsu_predictions = []
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []
        self._selected_bunsetsu_index = 0

        if reading in self._dictionary:
            # Whole-word dictionary match found
            self._has_whole_word_match = True
            candidates_dict = self._dictionary[reading]
            # Sort by cost (ascending) - lower cost = better candidate
            sorted_candidates = sorted(
                candidates_dict.items(),
                key=lambda x: x[1].get("cost", 0),
                reverse=False
            )
            for surface, entry in sorted_candidates:
                self._candidates.append({
                    'surface': surface,
                    'reading': reading,
                    'cost': entry.get("cost", 0),
                    'POS': entry.get("POS", "")
                })
            logger.debug(f'HenkanProcessor.convert("{reading}") → {len(self._candidates)} candidates')
        else:
            # No dictionary match - try bunsetsu-based conversion
            self._has_whole_word_match = False
            logger.debug(f'HenkanProcessor.convert("{reading}") → no match, trying bunsetsu mode')

            # Get CRF predictions and filter to multi-bunsetsu only
            predictions = self.predict_bunsetsu(reading)
            self._bunsetsu_predictions = [
                p for p in predictions if self._is_multi_bunsetsu(p[0])
            ]

            if self._bunsetsu_predictions:
                # Initialize bunsetsu mode with first prediction
                self._init_bunsetsu_mode(0)

                # Return a single candidate entry representing the bunsetsu result
                # (the actual surface is constructed from per-bunsetsu selections)
                self._candidates.append({
                    'surface': self.get_display_surface(),
                    'reading': reading,
                    'cost': 0,
                    'bunsetsu_mode': True
                })
                logger.debug(f'HenkanProcessor.convert("{reading}") → bunsetsu mode with '
                           f'{len(self._bunsetsu_predictions)} predictions')
            else:
                # No bunsetsu predictions available - return reading as-is
                self._candidates.append({
                    'surface': reading,
                    'reading': reading,
                    'cost': 0
                })
                logger.debug(f'HenkanProcessor.convert("{reading}") → no bunsetsu predictions, '
                           f'returning reading')

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

        This clears both whole-word mode and bunsetsu mode state.
        """
        # Whole-word mode state
        self._candidates = []
        self._selected_index = 0

        # Bunsetsu mode state
        self._bunsetsu_mode = False
        self._current_yomi = ''
        self._has_whole_word_match = False
        self._bunsetsu_predictions = []
        self._bunsetsu_prediction_index = 0
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []
        self._selected_bunsetsu_index = 0

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
        nbest_results = util.crf_nbest_predict(self._tagger, input_text, n_best=n_best,
                                               dict_materials=self._crf_feature_materials)

        # Convert label sequences to bunsetsu lists
        output = []
        tokens = util.tokenize_line(input_text)

        for labels, score in nbest_results:
            bunsetsu_list = util.labels_to_bunsetsu(tokens, labels)
            output.append((bunsetsu_list, score))

        return output

    # ─── Bunsetsu Mode Methods ────────────────────────────────────────────

    def _lookup_bunsetsu_candidates(self, bunsetsu_text):
        """
        Look up dictionary candidates for a single bunsetsu.

        Args:
            bunsetsu_text: The bunsetsu yomi to look up

        Returns:
            list: List of candidate dicts with 'surface', 'reading', 'cost'.
                  If no match found, returns list with original text as surface.
        """
        candidates = []

        if bunsetsu_text in self._dictionary:
            candidates_dict = self._dictionary[bunsetsu_text]
            # Sort by cost (ascending) - lower cost = better candidate
            sorted_candidates = sorted(
                candidates_dict.items(),
                key=lambda x: x[1].get("cost", 0),
                reverse=False
            )
            for surface, entry in sorted_candidates:
                candidates.append({
                    'surface': surface,
                    'reading': bunsetsu_text,
                    'cost': entry.get("cost", 0),
                    'POS': entry.get("POS", "")
                })
        else:
            # No dictionary match - return original text
            candidates.append({
                'surface': bunsetsu_text,
                'reading': bunsetsu_text,
                'cost': 0
            })

        return candidates

    def _is_multi_bunsetsu(self, bunsetsu_list):
        """
        Check if a bunsetsu prediction has multiple bunsetsu.

        Single-bunsetsu predictions are skipped because they're equivalent
        to whole-word lookup.

        Args:
            bunsetsu_list: List of (text, label) tuples

        Returns:
            bool: True if there are 2+ bunsetsu
        """
        return len(bunsetsu_list) >= 2

    def _init_bunsetsu_mode(self, prediction_index):
        """
        Initialize bunsetsu mode state for a given prediction index.

        This sets up the per-bunsetsu candidates and selection state.

        Args:
            prediction_index: Index into _bunsetsu_predictions
        """
        if not self._bunsetsu_predictions:
            return

        if prediction_index < 0 or prediction_index >= len(self._bunsetsu_predictions):
            return

        self._bunsetsu_prediction_index = prediction_index
        bunsetsu_list, score = self._bunsetsu_predictions[prediction_index]

        # Look up candidates for each bunsetsu
        self._bunsetsu_candidates = []
        self._bunsetsu_selected_indices = []

        for text, label in bunsetsu_list:
            is_lookup = label.endswith('-L') or label == 'B'
            if is_lookup:
                # Lookup bunsetsu: get dictionary candidates
                candidates = self._lookup_bunsetsu_candidates(text)
            else:
                # Passthrough bunsetsu: keep as-is (no alternative candidates)
                candidates = [{
                    'surface': text,
                    'reading': text,
                    'cost': 0,
                    'passthrough': True  # Mark as passthrough
                }]

            self._bunsetsu_candidates.append(candidates)
            self._bunsetsu_selected_indices.append(0)  # Select first candidate

        # Select first bunsetsu for navigation
        self._selected_bunsetsu_index = 0
        self._bunsetsu_mode = True

        logger.debug(f'Initialized bunsetsu mode: {len(bunsetsu_list)} bunsetsu, '
                    f'prediction #{prediction_index + 1}')

    def is_bunsetsu_mode(self):
        """
        Check if currently in bunsetsu mode.

        Returns:
            bool: True if in bunsetsu mode
        """
        return self._bunsetsu_mode

    def get_bunsetsu_count(self):
        """
        Get the number of bunsetsu in current prediction.

        Returns:
            int: Number of bunsetsu, or 0 if not in bunsetsu mode
        """
        if not self._bunsetsu_mode:
            return 0
        return len(self._bunsetsu_candidates)

    def get_selected_bunsetsu_index(self):
        """
        Get the index of the currently selected bunsetsu.

        Returns:
            int: Selected bunsetsu index
        """
        return self._selected_bunsetsu_index

    def get_bunsetsu_info(self, index):
        """
        Get information about a specific bunsetsu.

        Args:
            index: Bunsetsu index

        Returns:
            dict or None: Dictionary with 'text', 'label', 'candidates',
                         'selected_index', 'is_passthrough', or None if invalid
        """
        if not self._bunsetsu_mode:
            return None
        if index < 0 or index >= len(self._bunsetsu_candidates):
            return None

        bunsetsu_list, _ = self._bunsetsu_predictions[self._bunsetsu_prediction_index]
        text, label = bunsetsu_list[index]
        candidates = self._bunsetsu_candidates[index]
        selected_idx = self._bunsetsu_selected_indices[index]
        is_passthrough = candidates[0].get('passthrough', False) if candidates else False

        return {
            'text': text,
            'label': label,
            'candidates': candidates,
            'selected_index': selected_idx,
            'is_passthrough': is_passthrough
        }

    def cycle_bunsetsu_prediction(self):
        """
        Cycle to the next bunsetsu prediction.

        This cycles through:
        1. Whole-word dictionary match (if available)
        2. CRF N-best #1 (if multi-bunsetsu)
        3. CRF N-best #2 (if multi-bunsetsu)
        ... and wraps around.

        Returns:
            bool: True if mode changed, False otherwise
        """
        if not self._current_yomi:
            return False

        # If we have no bunsetsu predictions yet, try to get them
        if not self._bunsetsu_predictions:
            predictions = self.predict_bunsetsu(self._current_yomi)
            # Filter to multi-bunsetsu only
            self._bunsetsu_predictions = [
                p for p in predictions if self._is_multi_bunsetsu(p[0])
            ]

        # Calculate total options (whole-word match counts as option 0 if available)
        total_options = len(self._bunsetsu_predictions)
        if self._has_whole_word_match:
            total_options += 1

        if total_options == 0:
            # No options available
            return False

        if self._has_whole_word_match:
            # Options: -1 = whole-word, 0..n-1 = bunsetsu predictions
            if not self._bunsetsu_mode:
                # Currently in whole-word mode, switch to bunsetsu #0
                if self._bunsetsu_predictions:
                    self._init_bunsetsu_mode(0)
                    return True
            else:
                # Currently in bunsetsu mode
                next_idx = self._bunsetsu_prediction_index + 1
                if next_idx >= len(self._bunsetsu_predictions):
                    # Wrap around to whole-word mode
                    self._bunsetsu_mode = False
                    self._selected_index = 0
                    logger.debug('Cycled back to whole-word mode')
                    return True
                else:
                    # Go to next bunsetsu prediction
                    self._init_bunsetsu_mode(next_idx)
                    return True
        else:
            # No whole-word match, only bunsetsu predictions
            if not self._bunsetsu_predictions:
                return False

            if not self._bunsetsu_mode:
                # Not yet in bunsetsu mode, initialize
                self._init_bunsetsu_mode(0)
                return True
            else:
                # Cycle through bunsetsu predictions
                next_idx = (self._bunsetsu_prediction_index + 1) % len(self._bunsetsu_predictions)
                self._init_bunsetsu_mode(next_idx)
                return True

        return False

    def select_bunsetsu(self, index):
        """
        Select a bunsetsu for candidate navigation.

        Args:
            index: Bunsetsu index to select

        Returns:
            bool: True if selection changed, False otherwise
        """
        if not self._bunsetsu_mode:
            return False
        if index < 0 or index >= len(self._bunsetsu_candidates):
            return False

        self._selected_bunsetsu_index = index
        return True

    def next_bunsetsu(self):
        """
        Move selection to the next bunsetsu (right arrow).

        Returns:
            bool: True if selection changed, False otherwise
        """
        if not self._bunsetsu_mode:
            return False

        count = len(self._bunsetsu_candidates)
        if count == 0:
            return False

        new_index = (self._selected_bunsetsu_index + 1) % count
        self._selected_bunsetsu_index = new_index
        return True

    def previous_bunsetsu(self):
        """
        Move selection to the previous bunsetsu (left arrow).

        Returns:
            bool: True if selection changed, False otherwise
        """
        if not self._bunsetsu_mode:
            return False

        count = len(self._bunsetsu_candidates)
        if count == 0:
            return False

        new_index = (self._selected_bunsetsu_index - 1) % count
        self._selected_bunsetsu_index = new_index
        return True

    def next_bunsetsu_candidate(self):
        """
        Cycle to next candidate for the currently selected bunsetsu.

        Returns:
            dict or None: The new selected candidate, or None if not applicable
        """
        if not self._bunsetsu_mode:
            return None

        idx = self._selected_bunsetsu_index
        if idx < 0 or idx >= len(self._bunsetsu_candidates):
            return None

        candidates = self._bunsetsu_candidates[idx]
        if not candidates or candidates[0].get('passthrough', False):
            # Passthrough bunsetsu has no alternatives
            return None

        # Cycle to next candidate
        current = self._bunsetsu_selected_indices[idx]
        new_idx = (current + 1) % len(candidates)
        self._bunsetsu_selected_indices[idx] = new_idx

        return candidates[new_idx]

    def previous_bunsetsu_candidate(self):
        """
        Cycle to previous candidate for the currently selected bunsetsu.

        Returns:
            dict or None: The new selected candidate, or None if not applicable
        """
        if not self._bunsetsu_mode:
            return None

        idx = self._selected_bunsetsu_index
        if idx < 0 or idx >= len(self._bunsetsu_candidates):
            return None

        candidates = self._bunsetsu_candidates[idx]
        if not candidates or candidates[0].get('passthrough', False):
            # Passthrough bunsetsu has no alternatives
            return None

        # Cycle to previous candidate
        current = self._bunsetsu_selected_indices[idx]
        new_idx = (current - 1) % len(candidates)
        self._bunsetsu_selected_indices[idx] = new_idx

        return candidates[new_idx]

    def get_display_surface(self):
        """
        Get the combined display surface for the current conversion.

        In whole-word mode: returns the selected candidate's surface.
        In bunsetsu mode: returns all bunsetsu surfaces concatenated.

        Returns:
            str: The display surface string
        """
        if not self._bunsetsu_mode:
            # Whole-word mode
            candidate = self.get_selected_candidate()
            return candidate['surface'] if candidate else ''

        # Bunsetsu mode: concatenate all selected surfaces
        parts = []
        for i, candidates in enumerate(self._bunsetsu_candidates):
            if not candidates:
                continue
            selected_idx = self._bunsetsu_selected_indices[i]
            if 0 <= selected_idx < len(candidates):
                parts.append(candidates[selected_idx]['surface'])

        return ''.join(parts)

    def get_display_surface_with_selection(self):
        """
        Get the display surface with selection markers for preedit display.

        Returns:
            list: List of (text, is_selected) tuples for each bunsetsu.
                  In whole-word mode, returns single tuple with the surface.
        """
        if not self._bunsetsu_mode:
            # Whole-word mode
            candidate = self.get_selected_candidate()
            surface = candidate['surface'] if candidate else ''
            return [(surface, True)]

        # Bunsetsu mode: return each bunsetsu with selection state
        result = []
        for i, candidates in enumerate(self._bunsetsu_candidates):
            if not candidates:
                continue
            selected_idx = self._bunsetsu_selected_indices[i]
            if 0 <= selected_idx < len(candidates):
                surface = candidates[selected_idx]['surface']
                is_selected = (i == self._selected_bunsetsu_index)
                result.append((surface, is_selected))

        return result
