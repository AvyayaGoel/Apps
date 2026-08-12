"""
Formula Data Model
Replaces the old Dict[int, dict] master_data structure with a proper class.
No backward compatibility — clean break.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Iterator

from constants import ALL_SUBJECTS, ALL_TOPICS, ALL_SUB_TOPICS


@dataclass
class Variable:
    """A single variable definition in a formula."""
    symbol: str
    name: str
    unit: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict for database/export."""
        return {"symbol": self.symbol, "name": self.name, "unit": self.unit}

    @classmethod
    def from_dict(cls, d: dict) -> "Variable":
        """Create from dict (e.g., from database)."""
        return cls(
            symbol=d.get("symbol", ""),
            name=d.get("name", ""),
            unit=d.get("unit", "")
        )


@dataclass
class FormulaEntry:
    """
    A single formula entry. Replaces the old dict structure:
        {
            "main_info": [id, formula, subject, topic, sub_topic, notes],
            "variables": [...],
            "tags": [...],
            "_db_id": ...
        }
    """
    display_id: int
    formula_text: str
    subject: str
    topic: str
    sub_topic: str = "_GENERAL_"
    notes: str = ""
    variables: List[Variable] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    db_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # ── Derived / Computed Properties ──

    @property
    def var_count(self) -> int:
        """Number of defined variables."""
        return len(self.variables)

    @property
    def has_notes(self) -> bool:
        """True if notes exist and are non-empty."""
        return bool(self.notes and self.notes.strip())

    @property
    def display_sub_topic(self) -> str:
        """Human-readable sub-topic (replaces _GENERAL_)."""
        return "General" if self.sub_topic == "_GENERAL_" else self.sub_topic

    # ── Search / Filter Helpers ──

    def matches_search(self, query: str) -> bool:
        """Check if this formula matches a search query."""
        query = query.lower()
        haystack = f"{self.display_id} {self.formula_text} {self.subject} {self.topic} {self.sub_topic}"
        haystack += " " + " ".join(self.tags)
        return query in haystack.lower()

    def matches_filters(self, subject: str, topic: str, sub_topic: str) -> bool:
        """Check if formula matches dropdown filters."""
        if subject and subject != ALL_SUBJECTS and self.subject != subject:
            return False
        if topic and topic != ALL_TOPICS and self.topic != topic:
            return False
        if sub_topic and sub_topic != ALL_SUB_TOPICS and self.sub_topic != sub_topic:
            return False
        return True

    # ── Serialization ──

    @classmethod
    def from_db_row(cls, row: dict, db_id: int, tags: List[str]) -> "FormulaEntry":
        """
        Build from a database row dict (as returned by DatabaseManager).
        The row dict has keys: id, display_num, formula_text, field, topic, sub_topic, notes, variables
        """
        variables = [Variable.from_dict(v) for v in row.get("variables", [])]
        return cls(
            display_id=row["id"],
            formula_text=row["formula_text"],
            subject=row["field"],
            topic=row["topic"],
            sub_topic=row.get("sub_topic", "_GENERAL_"),
            notes=row.get("notes", ""),
            variables=variables,
            tags=tags.copy(),
            db_id=db_id,
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )

    @classmethod
    def from_dialog_result(cls, result: dict, display_id: int, db_id: int) -> "FormulaEntry":
        """Build from FormulaDialog result dict."""
        variables = [
            Variable(v["symbol"], v["name"], v.get("unit", ""))
            for v in result.get("variables", [])
        ]
        return cls(
            display_id=display_id,
            formula_text=result["formula"],
            subject=result["field"],
            topic=result["topic"],
            sub_topic=result.get("sub_topic", "_GENERAL_"),
            notes=result.get("notes", ""),
            variables=variables,
            tags=result.get("tags", []).copy(),
            db_id=db_id,
        )


class FormulaCollection:
    """
    Container for all formula entries. Replaces Dict[int, dict].
    Provides dict-like access while being a proper class.
    """

    def __init__(self):
        self._entries: Dict[int, FormulaEntry] = {}

    # ── Dict-like Interface ──

    def __getitem__(self, display_id: int) -> FormulaEntry:
        return self._entries[display_id]

    def __setitem__(self, display_id: int, entry: FormulaEntry) -> None:
        self._entries[display_id] = entry

    def __delitem__(self, display_id: int) -> None:
        del self._entries[display_id]

    def __contains__(self, display_id: int) -> bool:
        return display_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[int]:
        return iter(self._entries)

    def keys(self):
        return self._entries.keys()

    def values(self) -> Iterator[FormulaEntry]:
        return iter(self._entries.values())

    def items(self):
        return self._entries.items()

    def get(self, display_id: int, default=None) -> Optional[FormulaEntry]:
        return self._entries.get(display_id, default)

    def clear(self) -> None:
        self._entries.clear()

    # ── Bulk Operations ──

    def add(self, entry: FormulaEntry) -> None:
        """Add or replace an entry by its display_id."""
        self._entries[entry.display_id] = entry

    def remove(self, display_id: int) -> bool:
        """Remove entry by display_id. Returns True if removed."""
        if display_id in self._entries:
            del self._entries[display_id]
            return True
        return False

    def sorted_ids(self) -> List[int]:
        """Return display IDs sorted numerically."""
        return sorted(self._entries.keys(), key=lambda x: int(x))

    # ── Filtered Queries ──

    def filter(self, search: str = "", subject: str = "", topic: str = "", sub_topic: str = "") -> List[int]:
        """Return display IDs matching all active filters."""
        results = []
        for display_id, entry in self._entries.items():
            if search and not entry.matches_search(search):
                continue
            if not entry.matches_filters(subject, topic, sub_topic):
                continue
            results.append(display_id)
        return sorted(results, key=lambda x: int(x))

    # ── Aggregation ──

    def subjects(self) -> set:
        """All unique subjects."""
        return {e.subject for e in self._entries.values()}

    def topics_by_subject(self) -> Dict[str, set]:
        """Map subject -> set of topics."""
        result: Dict[str, set] = {}
        for e in self._entries.values():
            result.setdefault(e.subject, set()).add(e.topic)
        return result

    def subtopics_by_topic(self) -> Dict[tuple, set]:
        """Map (subject, topic) -> set of sub-topics."""
        result: Dict[tuple, set] = {}
        for e in self._entries.values():
            result.setdefault((e.subject, e.topic), set()).add(e.sub_topic)
        return result

    def subject_counts(self) -> Dict[str, int]:
        """Count formulas per subject."""
        result: Dict[str, int] = {}
        for e in self._entries.values():
            result[e.subject] = result.get(e.subject, 0) + 1
        return result

    def topic_counts(self) -> Dict[str, int]:
        """Count formulas per topic."""
        result: Dict[str, int] = {}
        for e in self._entries.values():
            result[e.topic] = result.get(e.topic, 0) + 1
        return result

    def subtopic_counts(self) -> Dict[str, int]:
        """Count formulas per sub-topic."""
        result: Dict[str, int] = {}
        for e in self._entries.values():
            result[e.sub_topic] = result.get(e.sub_topic, 0) + 1
        return result

    def unique_symbols(self) -> set:
        """All unique variable symbols across all formulas."""
        symbols = set()
        for e in self._entries.values():
            for v in e.variables:
                symbols.add(v.symbol)
        return symbols

    def variable_counts_per_formula(self) -> set:
        """Set of variable counts (for Prime Collector award)."""
        return {e.var_count for e in self._entries.values()}

    def total_variables(self) -> int:
        """Total variable definitions across all formulas."""
        return sum(e.var_count for e in self._entries.values())

    def max_variables_in_one(self) -> int:
        """Maximum variables in a single formula."""
        if not self._entries:
            return 0
        return max(e.var_count for e in self._entries.values())

    def formulas_with_subject(self, subject: str) -> List[FormulaEntry]:
        """All formulas in a given subject."""
        return [e for e in self._entries.values() if e.subject == subject]

    def formulas_with_topic(self, topic: str) -> List[FormulaEntry]:
        """All formulas in a given topic."""
        return [e for e in self._entries.values() if e.topic == topic]

    def deep_subtopics(self) -> Dict[str, int]:
        """Sub-topics with 5+ formulas. Returns {sub_topic: count}."""
        counts: Dict[str, int] = {}
        for e in self._entries.values():
            counts[e.sub_topic] = counts.get(e.sub_topic, 0) + 1
        return {k: v for k, v in counts.items() if v >= 5}
