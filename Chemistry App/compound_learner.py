"""CompoundLearner - Learns compound names and colors from database history."""
import logging
import re
from typing import Dict, List, Optional, Tuple
from constants import DEFAULT_COLOR, SUBSCRIPT_MAP


class CompoundLearner:
    """
    Learns compound name and color mappings from database compounds.
    
    Name learning (state-agnostic):
        - For a given formula (e.g., 'HCl'), finds the most frequently used name
        - Same name regardless of state (aq, l, s, g)
    
    Color learning (state-aware):
        - For a given (formula, state) pair, finds the most frequently used color
        - Colors may differ based on state (e.g., CuSO4(aq) vs CuSO4(s))
        - Falls back to default color if no data
    """

    def __init__(self):
        """
        Initialize the learner.
        """
        self.default_color = DEFAULT_COLOR
        # name_stats[formula] -> {name: count}
        self.name_stats: Dict[str, Dict[str, int]] = {}
        # color_stats[(formula, state)] -> {color: count}
        self.color_stats: Dict[Tuple[str, str], Dict[str, int]] = {}

    def learn(self, compounds: List[dict]) -> None:
        """
        Build frequency maps from compound data.
        
        Args:
            compounds: List of compound dictionaries with keys:
                - 'formula': str (e.g., 'HCl', 'NaCl')
                - 'state': str (e.g., 'aq', 'l', 's', 'g' or '')
                - 'name': str (maybe empty)
                - 'color': str (maybe empty)
        """
        for compound in compounds:
            formula = compound.get('formula', '').strip()
            formula = re.sub(r'^\d+','', formula)
            formula.translate(SUBSCRIPT_MAP)
            state = compound.get('state', '').strip()
            name = compound.get('name', '').strip()
            color = compound.get('color', '').strip()

            if not formula:
                continue

            # Learn name (state-agnostic) - only if name is non-empty
            if name:
                self._increment_name(formula, name)

            # Learn color (state-aware) - only if color is non-empty and state exists
            if color and state:
                logging.info(f"[LEARNER] Learning color: formula={formula!r}, state={state!r}, color={color!r}")
                self._increment_color(formula, state, color)
            elif color and not state:
                logging.info(f"[LEARNER] Skipping color learning (no state): formula={formula!r}, color={color!r}")

    def get_name(self, formula: str) -> Optional[str]:
        """
        Get the most frequently used name for a compound formula.
        
        Args:
            formula: Compound formula (e.g., 'HCl')
            
        Returns:
            Most common name or None if no data
        """
        formula = formula.strip()
        
        if formula not in self.name_stats:
            return None

        # Get the name with the highest frequency
        name_counts = self.name_stats[formula]
        
        if not name_counts:
            return None

        result = max(name_counts.items(), key=lambda x: x[1])[0]
        return result

    def get_color(self, formula: str, state: str = '') -> str:
        """
        Get the most frequently used color for a compound.
        
        Args:
            formula: Compound formula (e.g., 'CuSO4')
            state: State symbol (e.g., 'aq', 's', 'l', 'g') - may be empty
            
        Returns:
            Most common color for (formula, state) or default_color if no data
        """
        formula = formula.strip()
        state = state.strip()

        # Try to get color for specific (formula, state)
        key = (formula, state)
        logging.info(f"[LEARNER] Looking up color for key={key}")
        logging.info(f"[LEARNER] color_stats has {len(self.color_stats)} entries")
        if self.color_stats:
            logging.info(f"[LEARNER] color_stats keys: {list(self.color_stats.keys())[:10]}")  # Show first 10
        
        if key in self.color_stats and self.color_stats[key]:
            color_counts = self.color_stats[key]
            result = max(color_counts.items(), key=lambda x: x[1])[0]
            logging.info(f"[LEARNER] Found color stats for key={key}: {color_counts}, returning={result!r}")
            return result

        # If no state-specific color, return default
        logging.info(f"[LEARNER] No color found for key={key}, returning default={self.default_color!r}")
        return self.default_color

    def get_all_name_suggestions(self, formula: str, max_results: int = 3) -> List[Tuple[str, int]]:
        """
        Get all name suggestions for a formula, sorted by frequency.
        
        Args:
            formula: Compound formula
            max_results: Maximum number of suggestions to return
            
        Returns:
            List of (name, count) tuples sorted by count descending
        """
        formula = formula.strip()
        if formula not in self.name_stats:
            return []

        name_counts = self.name_stats[formula]
        sorted_names = sorted(name_counts.items(), key=lambda x: (-x[1], x[0]))
        return sorted_names[:max_results]

    def get_all_color_suggestions(self, formula: str, state: str = '', max_results: int = 3) -> List[Tuple[str, int]]:
        """
        Get all color suggestions for a (formula, state), sorted by frequency.
        
        Args:
            formula: Compound formula
            state: State symbol
            max_results: Maximum number of suggestions to return
            
        Returns:
            List of (color, count) tuples sorted by count descending
        """
        formula = formula.strip()
        state = state.strip()

        key = (formula, state)
        if key not in self.color_stats:
            return []

        color_counts = self.color_stats[key]
        sorted_colors = sorted(color_counts.items(), key=lambda x: (-x[1], x[0]))
        return sorted_colors[:max_results]

    def has_data(self) -> bool:
        """Check if learner has any data."""
        # Check if any formula has name entries
        for name_dict in self.name_stats.values():
            if name_dict:
                return True
        # Check if any (formula, state) has color entries
        for color_dict in self.color_stats.values():
            if color_dict:
                return True
        return False

    def clear(self) -> None:
        """Clear all learned statistics."""
        self.name_stats.clear()
        self.color_stats.clear()

    # --------------------------------------------------
    # INTERNAL UTIL
    # --------------------------------------------------
    def _increment_name(self, formula: str, name: str) -> None:
        """Increment frequency count for a (formula, name) pair."""
        if formula not in self.name_stats:
            self.name_stats[formula] = {}
        if name not in self.name_stats[formula]:
            self.name_stats[formula][name] = 0
        self.name_stats[formula][name] += 1

    def _increment_color(self, formula: str, state: str, color: str) -> None:
        """Increment frequency count for a (formula, state, color) triple."""
        key = (formula, state)
        if key not in self.color_stats:
            self.color_stats[key] = {}
        if color not in self.color_stats[key]:
            self.color_stats[key][color] = 0
        self.color_stats[key][color] += 1
