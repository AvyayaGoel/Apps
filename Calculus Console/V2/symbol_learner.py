"""
Symbol Learning & Suggestion Engine (PyQt6 version)
Learns symbol → (name, unit) mappings from formula data.
"""

from typing import Dict, List, Tuple


class SymbolLearner:
    """
    Learns symbol → (name, unit) mappings from formula data.

    Hierarchy:
        Subject
          └─ Topic
              └─ Sub-Topic

    Also maintains _GLOBAL_ fallbacks at:
        - topic level
        - subject level
    """

    def __init__(self):
        self.symbol_stats: Dict = {}

    # --------------------------------------------------
    # LEARNING
    # --------------------------------------------------
    def learn(self, master_data: Dict[int, dict]) -> None:
        """
        Build symbol frequency maps from master_data.
        Reads only needed fields — never mutates the input data.
        """
        self.symbol_stats.clear()

        for data in master_data.values():
            mi = data.get("main_info", [])
            if len(mi) < 4:
                continue

            subj = mi[2]
            topic = mi[3]
            # sub_topic at index 4, fallback to _GENERAL_ if missing/empty
            sub_topic = mi[4] if len(mi) > 4 and mi[4] else "_GENERAL_"

            subject_map = self.symbol_stats.setdefault(subj, {"_GLOBAL_": {}})
            topic_map = subject_map.setdefault(topic, {"_GLOBAL_": {}})
            subtopic_map = topic_map.setdefault(sub_topic, {})

            for var in data.get("variables", []):
                sym = var["symbol"]
                pair = (var["name"], var["unit"])

                # 1️⃣ Sub-topic specific
                self._increment(subtopic_map, sym, pair)

                # 2️⃣ Topic-wide fallback
                self._increment(topic_map["_GLOBAL_"], sym, pair)

                # 3️⃣ Subject-wide fallback
                self._increment(subject_map["_GLOBAL_"], sym, pair)

    # --------------------------------------------------
    # QUERYING
    # --------------------------------------------------
    def all_matches(
            self,
            subject: str,
            topic: str,
            sub_topic: str,
            symbol: str,
            min_confidence: int = 1,
            max_results: int = 5
    ) -> List[Tuple[str, str]]:
        """
        Get ALL possible matches for a symbol across the hierarchy.
        Returns up to max_results best matches sorted by confidence.
        """

        def all_from(symbol_bucket: dict, min_conf: int):
            """Return ALL matches from bucket sorted by confidence (highest first)"""
            if symbol not in symbol_bucket:
                return []
            matches = [(pair, conf) for pair, conf in symbol_bucket[symbol].items() if conf >= min_conf]
            # Sort by confidence descending, then by pair for consistency
            matches.sort(key=lambda x: (-x[1], x[0]))
            return [pair for pair, conf in matches]

        def add_matches_from_bucket(symbol_bucket, matches_list, seen_set):
            """Helper to add matches from a bucket, avoiding duplicates"""
            for match in all_from(symbol_bucket, min_confidence):
                if match not in seen_set:
                    matches_list.append(match)
                    seen_set.add(match)

        subject_map = self.symbol_stats.get(subject)
        if not subject_map:
            return []

        all_matches = []
        seen = set()  # Avoid duplicates

        # Define search hierarchy in order of priority
        search_buckets = []

        topic_map = subject_map.get(topic)
        if topic_map:
            # 1️⃣ Sub-topic
            sub_map = topic_map.get(sub_topic)
            if sub_map:
                search_buckets.append(sub_map)

            # 2️⃣ Topic global
            topic_global = topic_map.get("_GLOBAL_", {})
            if topic_global:
                search_buckets.append(topic_global)

        # 3️⃣ Subject global
        subject_global = subject_map.get("_GLOBAL_", {})
        if subject_global:
            search_buckets.append(subject_global)

        # Process all buckets
        for bucket in search_buckets:
            add_matches_from_bucket(bucket, all_matches, seen)

        return all_matches[:max_results]  # Return top matches up to max_results

    # --------------------------------------------------
    # INTERNAL UTIL
    # --------------------------------------------------
    @staticmethod
    def _increment(bucket: dict, symbol: str, pair: Tuple[str, str]) -> None:
        bucket.setdefault(symbol, {})
        bucket[symbol][pair] = bucket[symbol].get(pair, 0) + 1
