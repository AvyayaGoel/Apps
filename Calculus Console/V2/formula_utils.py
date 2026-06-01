"""
Utility functions for formula operations (PyQt6 version).
"""

import json
import logging
import os
from typing import Dict, List, Any, Tuple


class FormulaUtils:
    """Utility class for formula-related operations."""

    # Default configuration constants
    DEFAULT_CONFIG = {
        "theme": "darkly",
        "delay": 5000,
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

    AWARD_THRESHOLDS = {
        "chemistry_10": ("The Alchemist", "Save 10 Chemistry formulas."),
        "physics_10": ("The Physicist", "Save 10 Physics formulas."),
        "maths_10": ("Alegbra Learner", "Save 10 Maths formulas."),
        "chemistry_25": ("Chemistry Learner", "Save 25 Chemistry formulas."),
        "physics_25": ("The Junior-Engineer", "Save 25 Physics formulas."),
        "maths_25": ("Maths Explorer", "Save 25 Maths formulas."),
        "chemistry_50": ("The Chemist", "Save 50 Chemistry formulas."),
        "physics_50": ("The Engineer", "Save 50 Physics formulas."),
        "maths_50": ("Maths Expert", "Save 50 Maths formulas."),
        "physics_100": ("Einstein", "Save 100 Physics Formulas"),
        "maths_100": ("The Mathematician", "Save 100 Maths Formulas"),
        "maths_150": ("Maths God", "Save 150 Maths Formulas"),
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
            # Create default if missing
            with open(config_file, 'w') as f:
                json.dump(FormulaUtils.DEFAULT_CONFIG, f, indent=4)
            return FormulaUtils.DEFAULT_CONFIG.copy()

        try:
            with open(config_file) as f:
                cfg = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_config = FormulaUtils.DEFAULT_CONFIG.copy()
                merged_config.update(cfg)
                return merged_config
        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"Config file corrupted: {e}")
            # Return default config if corrupted
            return FormulaUtils.DEFAULT_CONFIG.copy()

    @staticmethod
    def save_config(config_file: str, theme: str, enable_backups: bool,
                    enable_suggestions: bool, suggestion_strictness: str, max_suggestions: int,
                    user_macros: List, always_on_top: bool, subject_colors: Dict[str, str]) -> None:
        """
        Save current configuration to file.

        Args:
            config_file: Path to configuration file
            theme: Current theme name
            enable_backups: Whether backups are enabled
            enable_suggestions: Whether suggestions are enabled
            suggestion_strictness: Suggestion strictness level
            max_suggestions: Maximum number of suggestions to show
            user_macros: User-defined macros
            always_on_top: Whether window is always on top
            subject_colors: Subject color mapping
        """
        config = {
            "theme": theme,
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
            logging.error(f"Failed to save config: {e}")

    @staticmethod
    def load_tip_state(tip_file: str) -> Dict[str, Any]:
        """
        Load tip state from file.

        Args:
            tip_file: Path to tip state file

        Returns:
            Tip state dictionary
        """
        if os.path.exists(tip_file):
            try:
                with open(tip_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Failed to load tip state: {e}")

        # Return default tip state
        return {
            "show_tips": True,
            "last_seen": {}
        }

    @staticmethod
    def save_tip_state(tip_file: str, tip_state: Dict[str, Any]) -> None:
        """
        Save tip state to file.

        Args:
            tip_file: Path to tip state file
            tip_state: Current tip state
        """
        try:
            with open(tip_file, "w") as f:
                json.dump(tip_state, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save tip state: {e}")

    @staticmethod
    def calculate_formula_statistics(master_data: Dict[int, Dict]) -> Tuple[Dict[str, int], set, bool]:
        """
        Calculate statistics about formulas for awards and analysis.

        Args:
            master_data: Dictionary containing all formula data

        Returns:
            Tuple of (stats_dict, other_subjects_set, var_overload_bool)
        """
        stats = {"Maths": 0, "Physics": 0, "Chemistry": 0}
        other_subjects = set()
        var_overload = False

        for entry in master_data.values():
            # Check for variable overload (5+ variables)
            if len(entry.get("variables", [])) >= 5:
                var_overload = True

            # Count subjects
            subj = entry["main_info"][2]
            if subj in stats:
                stats[subj] += 1
            elif subj:
                other_subjects.add(subj)

        return stats, other_subjects, var_overload

    @staticmethod
    def find_oldest_backup_slot(backup_slots: List[str]) -> str:
        """
        Find the oldest backup slot for rotation.

        Args:
            backup_slots: List of backup slot file paths

        Returns:
            Path to the oldest backup slot
        """
        oldest_file = backup_slots[0]
        oldest_time = float('inf')

        for slot in backup_slots:
            if not os.path.exists(slot):
                return slot  # Use empty slot first

            mtime = os.path.getmtime(slot)
            if mtime < oldest_time:
                oldest_time = mtime
                oldest_file = slot

        return oldest_file

    @staticmethod
    def validate_formula_data(formula_text: str, field: str, topic: str = "", variable_unit: str = "") -> Tuple[
        bool, str]:
        """
        Validate formula entry data with improved rules.

        Args:
            formula_text: Formula text to validate
            field: Field/subject to validate
            topic: Topic to validate (optional but recommended)
            variable_unit: Variable unit to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Formula text validation - be less strict about structure
        formula_text = formula_text.strip()

        if not formula_text:
            return False, "Formula cannot be empty."

        # Only check for obviously invalid content
        if len(formula_text) < 2:
            return False, "Formula seems too short. Please enter a complete formula."

        # Field validation - always required
        if not field or not field.strip():
            return False, "Please select a Field/Subject."

        # Topic validation - recommended but not strictly required
        if topic and not topic.strip():
            return False, "Topic cannot be empty if specified."

        # Variable validation - only check if variables are being used
        if variable_unit and variable_unit.strip() and variable_unit == "Unit":
            return False, "Please enter a valid Variable unit."

        return True, ""
