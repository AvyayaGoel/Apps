"""
Symbol Learning & Suggestion Engine (PyQt6 version)
Learns symbol → (name, unit) mappings from formula data.
Features:
  • Per‑base pattern mining: finds the changing subscript in names
  • Position‑based replacement to handle duplicate numbers
  • Preserves '-' as a valid unit
  • Duplicate suggestions collapsed with best unit
  • Dual Subscript Parsing (ASCII 'c3', Unicode 'c₃', explicit 'c_3')
  • Live context from the current formula dialog
  • Session‑context boosting (accepted suggestions strengthen local bias)
"""

import re
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from constants import NO_DIMENSION_UNITS
from formula_entry import FormulaCollection

# ── Subscript Helpers ─────────────────────────────────────────────

SUBSCRIPT_CHARS = "₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₕₖₗₘₙₚₛₜ"
SUB_TO_NORMAL = str.maketrans(SUBSCRIPT_CHARS, "0123456789aeoxhklmnpst")
NORMAL_TO_SUB = str.maketrans("0123456789aeoxhklmnpst", SUBSCRIPT_CHARS)


def extract_subscript_pattern(symbol: str) -> Optional[Tuple[str, str]]:
    """
    Splits symbol into (base, normalized_subscript).
    Handles:
      • ASCII/Unicode digits: 'v1', 'v₁', 'v10' -> ('v', '10')
      • Explicit subscripts: 'F_x', 'v_in' -> ('F', 'x'), ('v', 'in')
      • Letter/Word subscripts: 'Fₓ', 'Tₘₐₓ' -> ('F', 'x'), ('T', 'max')
    """
    if not symbol:
        return None

    # 1. Explicit underscore notation ('F_x', 'v_in', 'c_3')
    if "_" in symbol:
        parts = symbol.rsplit("_", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1].translate(SUB_TO_NORMAL)

    # 2. Unicode subscript characters ('v₁', 'Fₓ')
    sub_chars_pattern = f"[{re.escape(SUBSCRIPT_CHARS)}]+"
    match = re.match(rf'^(.+?)({sub_chars_pattern})$', symbol)
    if match:
        base, sub_raw = match.groups()
        return base, sub_raw.translate(SUB_TO_NORMAL)

    # 3. Trailing numbers or letter modifiers ('v1', 'c3', 'Fx')
    match = re.match(r'^([a-zA-Z\u0370-\u03ff]+)(\d+|[a-zA-Z])$', symbol)
    if match:
        base, sub = match.groups()
        if base and sub:
            return base, sub

    return None


def apply_template(template: str, subscript: str, use_unicode: bool = False) -> str:
    """Replace {n} with subscript, converting to Unicode if use_unicode is True."""
    if not template:
        return ""
    if use_unicode:
        subscript = subscript.translate(NORMAL_TO_SUB)  # convert "1" -> "₁"
    return template.replace("{n}", subscript)


def normalize_unit(unit: str) -> str:
    """
    Normalise unit for consistency, but preserve '-' as a valid unit.
    Returns the stripped unit, or empty string if it's a known dimensionless marker
    (except '-' which we keep).
    """
    if not unit:
        return ""
    stripped = unit.strip()
    if stripped == "-":
        return "-"
    if stripped.lower() in NO_DIMENSION_UNITS:
        return ""
    return stripped


# ── Internal Structures ───────────────────────────────────────────

@dataclass
class VariableEntry:
    symbol: str
    name: str
    unit: str


@dataclass
class _MatchCandidate:
    name: str
    unit: str
    base_confidence: int
    source_subject: str
    source_topic: str
    source_sub_topic: str
    match_type: str  # "exact_subtopic" | "exact_topic_global" | "exact_subject_global" | "pattern"


@dataclass
class SubscriptPattern:
    base: str
    name_template: Optional[str]
    unit_template: Optional[str]
    example_count: int
    subscripts_seen: Set[str]
    use_unicode: bool = False


# ── Main Learner ──────────────────────────────────────────────────

class SymbolLearner:
    """
    Learns symbol → (name, unit) mappings.
    """

    def __init__(self):
        self.symbol_stats: Dict = {}
        self.db_variables: List[VariableEntry] = []

        # Session context
        self._session_biases: Dict[Tuple[str, str, str], float] = defaultdict(float)
        self._last_query_results: Dict[Tuple[str, str], Tuple[str, str, str, int]] = {}
        self._last_query_context: Tuple[str, str, str] = ("", "", "")

    # ================================================================
    # SESSION LIFECYCLE
    # ================================================================

    def start_session(self, subject: str = "", topic: str = "", sub_topic: str = "") -> None:
        self._session_biases.clear()
        self._last_query_results.clear()
        self._last_query_context = (subject, topic, sub_topic)

    def record_acceptance(self, name: str, unit: str) -> None:
        key = (name, unit)
        if key in self._last_query_results:
            src_subj, src_topic, src_subtopic, _conf = self._last_query_results[key]
        else:
            src_subj, src_topic, src_subtopic = self._last_query_context

        self._session_biases[(src_subj, src_topic, src_subtopic)] += 0.60
        self._session_biases[(src_subj, src_topic, "_GLOBAL_")] += 0.30
        self._session_biases[(src_subj, "_GLOBAL_", "_GLOBAL_")] += 0.10

    # ================================================================
    # LEARNING
    # ================================================================

    def learn(self, master_data: FormulaCollection) -> None:
        self.symbol_stats.clear()
        self.db_variables.clear()

        for entry in master_data.values():
            subj = entry.subject
            topic = entry.topic
            sub_topic = entry.sub_topic if entry.sub_topic else "_GENERAL_"

            subject_map = self.symbol_stats.setdefault(subj, {"_GLOBAL_": {}})
            topic_map = subject_map.setdefault(topic, {"_GLOBAL_": {}})
            subtopic_map = topic_map.setdefault(sub_topic, {})

            for var in entry.variables:
                sym = var.symbol
                norm_unit = normalize_unit(var.unit)
                pair = (var.name, norm_unit)

                self._increment(subtopic_map, sym, pair)
                self._increment(topic_map["_GLOBAL_"], sym, pair)
                self._increment(subject_map["_GLOBAL_"], sym, pair)

                self.db_variables.append(VariableEntry(sym, var.name, norm_unit))

    # ================================================================
    # PATTERN MINING (Per-base)
    # ================================================================

    @staticmethod
    def _extract_template(values: List[str], subscripts: List[str]) -> Optional[Tuple[str, bool]]:
        """
        Returns (template, use_unicode) by finding the position of the
        subscript string (as a whole) in each name.
        Preserves the original name format; only normalizes for substring search.
        """
        if len(values) < 2 or len(values) != len(subscripts):
            return None

        # 1. Convert the subscript strings to normal digits (for searching in the normalized name)
        norm_subscripts = [s.translate(SUB_TO_NORMAL) for s in subscripts]

        # 2. For each name, create a normalized version for search (but keep original for output)
        norm_values = [v.translate(SUB_TO_NORMAL) for v in values]

        # 3. Use the first name to find all possible positions of the first normalized subscript
        first_val = norm_values[0]
        first_sub = norm_subscripts[0]
        positions = []
        start = 0
        while True:
            idx = first_val.find(first_sub, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + len(first_sub)

        if not positions:
            return None

        # 4. Try each position – check if the template works for ALL examples
        for pos in positions:
            template = values[0][:pos] + "{n}" + values[0][pos + len(first_sub):]

            valid = True
            for i in range(1, len(values)):
                expected = template.replace("{n}", subscripts[i])
                if expected != values[i]:
                    expected_norm = template.replace("{n}", norm_subscripts[i])
                    if expected_norm != values[i]:
                        valid = False
                        break

            if valid:
                use_unicode = False
                if pos < len(values[0]):
                    orig_char = values[0][pos]
                    if orig_char in SUBSCRIPT_CHARS:
                        use_unicode = True
                return template, use_unicode

        prefix = ""
        for i, chars in enumerate(zip(*values)):
            if all(c == chars[0] for c in chars):
                prefix += chars[0]
            else:
                break

        rev_values = [v[::-1] for v in values]
        rev_prefix = ""
        for i, chars in enumerate(zip(*rev_values)):
            if all(c == chars[0] for c in chars):
                rev_prefix += chars[0]
            else:
                break
        suffix = rev_prefix[::-1]

        if len(prefix) + len(suffix) >= len(values[0]):
            return None

        template = prefix + "{n}" + suffix
        use_unicode = False
        if len(prefix) < len(values[0]):
            if values[0][len(prefix)] in SUBSCRIPT_CHARS:
                use_unicode = True
        return template, use_unicode

    def _mine_patterns(self, variables: List[VariableEntry]) -> Dict[str, SubscriptPattern]:
        groups: Dict[str, List[Tuple[str, VariableEntry]]] = defaultdict(list)

        for v in variables:
            pat = extract_subscript_pattern(v.symbol)
            if pat:
                base, sub = pat
                if base:
                    groups[base].append((sub, v))

        patterns: Dict[str, SubscriptPattern] = {}
        for base, items in groups.items():
            if len(items) < 2:
                continue

            subscripts = [sub for sub, _ in items]
            names = [v.name for _, v in items]
            units = [v.unit for _, v in items]

            name_template_info = self._extract_template(names, subscripts)
            if name_template_info is None:
                continue
            name_template, use_unicode = name_template_info

            unit_template = self._extract_template(units, subscripts)
            if unit_template is None:
                unit_counter = Counter(units)
                most_common = unit_counter.most_common()
                if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                    for unit, _ in most_common:
                        if unit and unit != "":
                            unit_template = unit
                            break
                    else:
                        unit_template = most_common[0][0]
                else:
                    unit_template = most_common[0][0]

            patterns[base] = SubscriptPattern(
                base=base,
                name_template=name_template,
                unit_template=unit_template,
                example_count=len(items),
                subscripts_seen=set(subscripts),
                use_unicode=use_unicode
            )

        return patterns

    # ================================================================
    # SCORING
    # ================================================================

    def _compute_boost(self, src_subj: str, src_topic: str, src_subtopic: str) -> float:
        bias = 1.0
        bias += self._session_biases.get((src_subj, src_topic, src_subtopic), 0.0)
        bias += self._session_biases.get((src_subj, src_topic, "_GLOBAL_"), 0.0) * 0.5
        bias += self._session_biases.get((src_subj, "_GLOBAL_", "_GLOBAL_"), 0.0) * 0.25
        return bias

    # ================================================================
    # QUERYING
    # ================================================================

    def all_matches(
            self,
            subject: str,
            topic: str,
            sub_topic: str,
            symbol: str,
            min_confidence: int = 1,
            max_results: int = 5,
            live_variables: Optional[List[dict]] = None
    ) -> List[Tuple[str, str]]:
        self._last_query_context = (subject, topic, sub_topic)

        candidates: List[_MatchCandidate] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        def add_exact(bucket, src_subj, src_topic, src_subtopic, match_type):
            if symbol not in bucket:
                return
            for (name, unit), conf in bucket[symbol].items():
                if conf < min_confidence:
                    continue
                pair = (name, unit)
                if pair in seen_pairs:
                    for c in candidates:
                        if c.name == name and c.unit == unit:
                            c.base_confidence += conf
                            break
                    continue
                seen_pairs.add(pair)
                candidates.append(_MatchCandidate(
                    name=name, unit=unit, base_confidence=conf,
                    source_subject=src_subj, source_topic=src_topic,
                    source_sub_topic=src_subtopic, match_type=match_type
                ))

        # 1. Exact matches from hierarchy (unchanged)
        subject_map = self.symbol_stats.get(subject)
        if subject_map:
            topic_map = subject_map.get(topic)
            if topic_map:
                sub_map = topic_map.get(sub_topic)
                if sub_map:
                    add_exact(sub_map, subject, topic, sub_topic, "exact_subtopic")
                add_exact(topic_map.get("_GLOBAL_", {}), subject, topic, "_GLOBAL_", "exact_topic_global")
            add_exact(subject_map.get("_GLOBAL_", {}), subject, "_GLOBAL_", "_GLOBAL_", "exact_subject_global")

        # 2. Pattern matches — ONLY from live variables, never from database
        if live_variables and len(live_variables) > 0:
            # Build live entries
            live_entries: List[VariableEntry] = []
            for v in live_variables:
                norm_unit = normalize_unit(v.get("unit", ""))
                live_entries.append(VariableEntry(
                    symbol=v.get("symbol", ""),
                    name=v.get("name", ""),
                    unit=norm_unit
                ))

            pat = extract_subscript_pattern(symbol)
            typed_base = pat[0] if pat else None

            if typed_base:
                # Filter live entries with the same base
                live_for_base = [
                    e for e in live_entries
                    if extract_subscript_pattern(e.symbol) and extract_subscript_pattern(e.symbol)[0] == typed_base
                ]
                # Only generate a pattern if we have at least 2 examples
                if len(live_for_base) >= 2:
                    patterns = self._mine_patterns(live_for_base)
                    if pat and len(candidates) < max_results:
                        base, sub = pat
                        if base in patterns:
                            pattern = patterns[base]
                            if pattern.example_count >= 2:
                                inferred_name = apply_template(pattern.name_template, sub, pattern.use_unicode)
                                inferred_unit = apply_template(pattern.unit_template, sub, pattern.use_unicode)
                                if inferred_name and inferred_name.strip():
                                    pair = (inferred_name, inferred_unit)
                                    if pair not in seen_pairs:
                                        seen_pairs.add(pair)
                                        candidates.append(_MatchCandidate(
                                            name=inferred_name, unit=inferred_unit,
                                            base_confidence=1,
                                            source_subject=subject, source_topic=topic,
                                            source_sub_topic=sub_topic, match_type="pattern"
                                        ))

        # 3. Score, sort, cache provenance (unchanged)
        scored = []
        for c in candidates:
            boost = self._compute_boost(c.source_subject, c.source_topic, c.source_sub_topic)
            final_score = c.base_confidence * boost
            scored.append((final_score, c))

        scored.sort(key=lambda x: (-x[0], x[1].name))

        self._last_query_results = {
            (c.name, c.unit): (c.source_subject, c.source_topic, c.source_sub_topic, c.base_confidence)
            for _, c in scored
        }

        return [(c.name, c.unit) for _, c in scored[:max_results]]

    # ================================================================
    # INTERNAL UTIL
    # ================================================================

    @staticmethod
    def _increment(bucket: dict, key: str, pair: Tuple[str, str]) -> None:
        bucket.setdefault(key, {})
        bucket[key][pair] = bucket[key].get(pair, 0) + 1
