"""
Utility functions for formula operations (PyQt6 version).
Updated for FormulaEntry / FormulaCollection class structure.
No backward compatibility.
"""

import json
import logging
import os
from typing import Dict, List, Any

from formula_entry import FormulaCollection


class FormulaUtils:
    """Utility class for formula-related operations."""

    # Default configuration constants
    DEFAULT_CONFIG = {
        "backups": True,
        "suggestions": True,
        "suggestion_strictness": "Balanced",
        "max_suggestions": 3,
        "macros": [],
        "always_on_top": False,
        "subject_colors": {
            "Physics": "#5dade2",
            "Chemistry": "#58d68d",
            "Maths": "#af7ac5"
        }
    }

    @staticmethod
    def load_config(config_file: str) -> Dict[str, Any]:
        """
        Load configuration from file or create default if missing.

        Args:
            config_file: Path to configuration file

        Returns:
            Configuration dictionary
        """
        if not os.path.exists(config_file):
            with open(config_file, 'w') as f:
                json.dump(FormulaUtils.DEFAULT_CONFIG, f, indent=4)
            return FormulaUtils.DEFAULT_CONFIG.copy()

        try:
            with open(config_file) as f:
                cfg = json.load(f)
                merged_config = FormulaUtils.DEFAULT_CONFIG.copy()
                merged_config.update(cfg)
                return merged_config
        except (json.JSONDecodeError, KeyError) as e:
            logging.exception(f"Config file corrupted: {e}")
            return FormulaUtils.DEFAULT_CONFIG.copy()

    @staticmethod
    def save_config(
            config_file: str,
            enable_backups: bool,
            enable_suggestions: bool,
            suggestion_strictness: str,
            max_suggestions: int,
            user_macros: List,
            always_on_top: bool,
            subject_colors: Dict[str, str]
    ) -> None:
        """
        Save current configuration to file.
        """
        config = {
            "backups": enable_backups,
            "suggestions": enable_suggestions,
            "suggestion_strictness": suggestion_strictness,
            "max_suggestions": max_suggestions,
            "macros": user_macros,
            "always_on_top": always_on_top,
            "subject_colors": subject_colors
        }

        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logging.exception(f"Failed to save config: {e}")

    @staticmethod
    def load_tip_state(tip_file: str) -> Dict[str, Any]:
        """
        Load tip state from file.
        """
        if os.path.exists(tip_file):
            try:
                with open(tip_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.exception(f"Failed to load tip state: {e}")

        return {
            "show_tips": True,
            "last_seen": {}
        }

    @staticmethod
    def save_tip_state(tip_file: str, tip_state: Dict[str, Any]) -> None:
        """
        Save tip state to file.
        """
        try:
            with open(tip_file, "w") as f:
                json.dump(tip_state, f, indent=4)
        except Exception as e:
            logging.exception(f"Failed to save tip state: {e}")

    @staticmethod
    def calculate_formula_statistics(master_data: FormulaCollection) -> tuple[Dict[str, int], set, bool]:
        stats = master_data.subject_counts()
        # Ensure the three default subjects exist even if count is 0
        for subj in ("Maths", "Physics", "Chemistry"):
            stats.setdefault(subj, 0)

        other_subjects = master_data.subjects() - {"Maths", "Physics", "Chemistry"}
        var_overload = master_data.max_variables_in_one() >= 5

        return stats, other_subjects, var_overload

    @staticmethod
    def find_oldest_backup_slot(backup_slots: List[str]) -> str:
        """
        Find the oldest backup slot for rotation.
        """
        oldest_file = backup_slots[0]
        oldest_time = float('inf')

        for slot in backup_slots:
            if not os.path.exists(slot):
                return slot

            mtime = os.path.getmtime(slot)
            if mtime < oldest_time:
                oldest_time = mtime
                oldest_file = slot

        return oldest_file

    @staticmethod
    def validate_formula_data(
            formula_text: str,
            field: str,
            topic: str = ""
    ) -> tuple[bool, str]:
        """
        Validate formula entry data.
        """
        formula_text = formula_text.strip()

        if not formula_text:
            return False, "Formula cannot be empty."

        if len(formula_text) < 2:
            return False, "Formula seems too short. Please enter a complete formula."

        if not field or not field.strip():
            return False, "Please select a Field/Subject."

        if topic and not topic.strip():
            return False, "Topic cannot be empty if specified."

        return True, ""
