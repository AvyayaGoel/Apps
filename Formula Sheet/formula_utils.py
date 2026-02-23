"""
Utility functions for formula operations extracted from Sheet class.
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
    def extract_formula_params(main_info: List[str], variables: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Extract parameters for database operations from formula data.
        
        Args:
            main_info: List containing formula metadata [id, formula_text, field, topic, sub_topic]
            variables: List of variable dictionaries with 'symbol', 'name', 'unit' keys
            
        Returns:
            Dictionary with parameters ready for database operations
        """
        return {
            'formula_text': main_info[1],
            'field': main_info[2],
            'topic': main_info[3],
            'sub_topic': main_info[4] if len(main_info) > 4 else "_GENERAL_",
            'variables': variables
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
    def save_config(config_file: str, theme: str, auto_save_delay: int, enable_backups: bool,
                    enable_suggestions: bool, suggestion_strictness: str, max_suggestions: int,
                    user_macros: List, always_on_top: bool, subject_colors: Dict[str, str]) -> None:
        """
        Save current configuration to file.
        
        Args:
            config_file: Path to configuration file
            theme: Current theme name
            auto_save_delay: Auto-save delay in milliseconds
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
            "delay": auto_save_delay,
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
    def get_awards_list(stats: Dict[str, int], other_subjects: set, var_overload: bool) -> List[Tuple[str, str, bool]]:
        """
        Get list of awards with their unlock status.
        
        Args:
            stats: Subject statistics
            other_subjects: Set of other subjects
            var_overload: Whether variable overload award is unlocked
            
        Returns:
            List of (title, description, unlocked) tuples
        """
        awards = []

        # Add threshold-based awards
        for key, (title, desc) in FormulaUtils.AWARD_THRESHOLDS.items():
            subject, count = key.split('_')
            count = int(count)
            subject_key = subject.capitalize()
            unlocked = stats.get(subject_key, 0) >= count
            awards.append((title, desc, unlocked))

        # Add special awards
        awards.extend([
            ("Variable Wrangler", "Save a formula with 5+ defined variables.", var_overload),
            ("The Pioneer", "Have 1 more subject other than Maths, Chemistry And Physics", len(other_subjects) == 1),
            ("The Rocketeer", "Have 2 more subject other than Maths, Chemistry And Physics", len(other_subjects) == 2),
        ])

        return awards

    @staticmethod
    def renumber_database(master_data: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        Renumber database entries sequentially starting from 1.
        
        Args:
            master_data: Current master data dictionary
            
        Returns:
            Renumbered master data dictionary
        """
        new_master = {}
        for index, old_id in enumerate(sorted(master_data.keys()), start=1):
            data = master_data[old_id].copy()
            data["main_info"][0] = index
            new_master[index] = data
        return new_master

    @staticmethod
    def get_milestone_bootstyle(milestone_count: int, default_bootstyle: str = "info") -> str:
        """
        Get appropriate bootstyle for milestone count based on thresholds.
        
        Args:
            milestone_count: The milestone count
            default_bootstyle: Default bootstyle to use
            
        Returns:
            Bootstyle string
        """
        if milestone_count >= 1000:
            return "warning"
        elif milestone_count >= 900:
            return "primary"
        elif milestone_count >= 800:
            return "info"
        elif milestone_count >= 700:
            return "secondary"
        elif milestone_count >= 600:
            return "success"
        elif milestone_count >= 500:
            return "info"
        else:
            return default_bootstyle

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
    def extract_subjects_from_data(master_data: Dict[int, Dict]) -> set:
        """
        Extract all unique subjects from master data.
        
        Args:
            master_data: Dictionary containing all formula data
            
        Returns:
            Set of unique subjects
        """
        return {d['main_info'][2] for d in master_data.values() if d['main_info'][2]}

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
