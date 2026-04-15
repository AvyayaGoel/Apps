"""CompoundLearner - Learns compound names and colors from database history + PubChem."""
import json
import logging
import re
import threading
from typing import Dict, List, Optional, Tuple
from urllib import request, parse

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

    def __init__(self, db=None):
        """
        Initialize the learner.
        
        Args:
            db: Optional ChemLabDatabase for saved compound lookups
        """
        self.default_color = DEFAULT_COLOR
        self.db = db
        # name_stats[formula] -> {name: count} (from user entries)
        self.name_stats: Dict[str, Dict[str, int]] = {}
        # color_stats[(formula, state)] -> {color: count}
        self.color_stats: Dict[Tuple[str, str], Dict[str, int]] = {}
        # PubChem cache: formula -> name (auto-looked up compounds)
        self._pubchem_cache: Dict[str, str] = {}
        # Track formulas currently being looked up to avoid duplicates
        self._pending_lookups: set = set()
        # Lock for thread-safe cache updates
        self._cache_lock = threading.Lock()

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
            formula = re.sub(r'^\d+', '', formula)
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
                self._increment_color(formula, state, color)

    def get_name(self, formula: str) -> Optional[str]:
        """
        Get the most frequently used name for a compound formula.
        Priority: 1) User-learned names, 2) Cached PubChem lookup, 3) Auto-fetch from PubChem
        
        Args:
            formula: Compound formula (e.g., 'HCl')
            
        Returns:
            Most common name or None if no data (user should enter manually)
        """
        formula = formula.strip()
        if not formula:
            return None

        # Priority 1: User's given names (highest priority)
        if formula in self.name_stats and self.name_stats[formula]:
            name_counts = self.name_stats[formula]
            result = max(name_counts.items(), key=lambda x: x[1])[0]
            return result

        # Priority 2: Check database saved compounds
        if self.db:
            try:
                saved = self.db.get_compound_by_formula(formula)
                if saved and saved.get('common_name'):
                    return saved['common_name']
            except Exception as e:
                logging.error(f"DB lookup failed for {formula}: {e}")

        # Priority 3: Check in-memory PubChem cache
        with self._cache_lock:
            if formula in self._pubchem_cache:
                return self._pubchem_cache[formula]

        # Priority 4: Trigger async PubChem lookup
        self._lookup_pubchem_async(formula)
        
        # Return None for now - will be populated on next call after lookup completes
        return None

    def _lookup_pubchem_async(self, formula: str):
        """Start background thread to lookup formula on PubChem."""
        if formula in self._pending_lookups:
            return  # Already looking this up
        
        self._pending_lookups.add(formula)
        thread = threading.Thread(target=self._fetch_pubchem, args=(formula,), daemon=True)
        thread.start()

    def _fetch_pubchem(self, formula: str):
        """Fetch compound name from PubChem API (runs in background thread)."""
        try:
            # Search by molecular formula
            encoded_formula = parse.quote(formula)
            search_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastformula/{encoded_formula}/cids/JSON"

            req = request.Request(search_url, headers={'User-Agent': 'ChemLab/1.0'})
            with request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())

            if 'IdentifierList' not in data or 'CID' not in data['IdentifierList']:
                return  # Not found

            # Get first CID (most common compound)
            cid = data['IdentifierList']['CID'][0]

            # Get name - try Title first (better common names), fallback to IUPACName
            props_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/Title,IUPACName/JSON"
            req2 = request.Request(props_url, headers={'User-Agent': 'ChemLab/1.0'})
            with request.urlopen(req2, timeout=8) as response2:
                props_data = json.loads(response2.read().decode())

            if 'PropertyTable' in props_data and 'Properties' in props_data['PropertyTable']:
                props = props_data['PropertyTable']['Properties'][0]
                # Try Title first (gives "Sodium Sulfate" instead of "Disodium;Sulfate")
                compound_name = props.get('Title')
                iupac_name = props.get('IUPACName')
                
                if not compound_name and iupac_name:
                    # Fallback to IUPAC if Title not available
                    compound_name = iupac_name
                
                if compound_name:
                    # Clean up the name - fix common formatting issues
                    formatted_name = self._clean_compound_name(compound_name)
                    
                    with self._cache_lock:
                        self._pubchem_cache[formula] = formatted_name
                    
                    # Also save to database for persistence
                    if self.db:
                        try:
                            self.db.add_compound_name(
                                formula=formula,
                                common_name=formatted_name[:50],  # Truncate for display
                                iupac_name=iupac_name or compound_name,
                                cid=cid
                            )
                        except Exception as e:
                            logging.error(f"Failed to cache {formula} in DB: {e}")

        except Exception as e:
            logging.debug(f"PubChem lookup failed for {formula}: {e}")
        finally:
            self._pending_lookups.discard(formula)

    @staticmethod
    def _clean_compound_name(name: str) -> str:
        """Clean up compound name from PubChem - fix formatting issues."""
        if not name:
            return name
        
        # Replace semicolons with spaces (e.g., "Disodium;Sulfate" -> "Disodium Sulfate")
        name = name.replace(';', ' ')
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Proper capitalization: first letter of each word capitalized
        name = name.title()
        
        return name.strip()

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
            result = max(color_counts.items(), key=lambda x: x[1])[0]
            return result

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
