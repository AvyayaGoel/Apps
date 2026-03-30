"""CompoundLearner - Learns compound names and colors from database history."""
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


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

    def __init__(self, default_color: str = 'Unknown'):
        """
        Initialize the learner.
        
        Args:
            default_color: Fallback color when no historical data exists
        """
        self.default_color = default_color
        # name_stats[formula] -> {name: count}
        self.name_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # color_stats[(formula, state)] -> {color: count}
        self.color_stats: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def learn(self, compounds: List[dict]) -> None:
        """
        Build frequency maps from compound data.
        
        Args:
            compounds: List of compound dictionaries with keys:
                - 'formula': str (e.g., 'HCl', 'NaCl')
                - 'state': str (e.g., 'aq', 'l', 's', 'g' or '')
                - 'name': str (may be empty)
                - 'color': str (may be empty)
        """
        for compound in compounds:
            formula = compound.get('formula', '').strip()
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
                self._increment_color(formula, state, color)

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

        # Get the name with highest frequency
        name_counts = self.name_stats[formula]
        if not name_counts:
            return None

        return max(name_counts.items(), key=lambda x: x[1])[0]

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
        if key in self.color_stats and self.color_stats[key]:
            color_counts = self.color_stats[key]
            return max(color_counts.items(), key=lambda x: x[1])[0]

        # If no state-specific color, return default
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
        return bool(self.name_stats) or bool(self.color_stats)

    def clear(self) -> None:
        """Clear all learned statistics."""
        self.name_stats.clear()
        self.color_stats.clear()

    # --------------------------------------------------
    # INTERNAL UTIL
    # --------------------------------------------------
    def _increment_name(self, formula: str, name: str) -> None:
        """Increment frequency count for a (formula, name) pair."""
        self.name_stats[formula][name] += 1

    def _increment_color(self, formula: str, state: str, color: str) -> None:
        """Increment frequency count for a (formula, state, color) triple."""
        key = (formula, state)
        self.color_stats[key][color] += 1
