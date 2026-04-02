"""
Constants for ChemLab Application
"""
import sys
import os
# Arrow types for reaction detection
ARROWS = ['→', '←', '⇌', '⇋', '↔', '->', '<-', '<=>', '=>', '<->']

# Subscript mapping for number conversion
SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
SUBSCRIPT_DIGITS = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', 
                   '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'}

# Mapping for keyboard arrows to Unicode arrows
ARROW_MAP = {
    '->': '→',
    '<-': '←',
    '<=>': '⇌',
    '=>': '⇒',
    '<->': '↔'
}

# Subscript mapping for display (numbers to Unicode subscripts)
SUBSCRIPT_DISPLAY_MAP = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")

# Common reaction types for combobox
COMMON_REACTION_TYPES = [
    "Combustion",
    "Synthesis", 
    "Decomposition",
    "Single Replacement",
    "Double Replacement",
    "Neutralization",
    "Redox",
    "Precipitation",
    "Acid-Base",
    "Oxidation-Reduction"
]

# Default values
DEFAULT_COLOR = 'colorless'
DEFAULT_REACTION_TYPE = 'Unknown'

# State symbols mapping (abbreviation -> full name)
STATE_SYMBOLS = {'s', 'l', 'g', 'aq', 'ppt', '↑', '↓'}
STATE_NAMES = {
    's': 'Solid',
    'l': 'Liquid',
    'g': 'Gaseous',
    'aq': 'Aqueous',
    'ppt': 'Precipitate',
    '↑': 'Gaseous',
    '↓': 'Precipitate'
}
# Reverse mapping for saving (full name -> abbreviation)
STATE_ABBREVIATIONS = {v: k for k, v in STATE_NAMES.items()}

# Regex pattern for matching state symbols at end of formula
STATE_SYMBOL_PATTERN = r'\((s|l|g|aq|ppt|↑|↓)\)$'

ADD_REACTION_BTN_TEXT = "➕ Add Reaction"

# Table column indices
COMPOUNDS_COLUMNS = ["Compound Formula", "Type", "Name", "Color", "State", "Notes"]
ELEMENTS_COLUMNS = ["Element Symbol", "Element Name", "Atomic Number"]
REACTIONS_COLUMNS = ["Reaction", "Type"]

# Editable compound columns (0-based index)
EDITABLE_COMPOUND_COLUMNS = [2, 3, 4, 5]  # name, color, state, notes

COLOR_STYLE = "color: #ffffff;"

FONT = "Cambria Math"


def get_icon_path():
    """Get the correct icon path for both development and packaged environments"""
    # Check if running in PyInstaller environment
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle - use getattr to safely access _MEIPASS
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            return os.path.join(meipass, ICON_NAME)
        else:
            # Fallback if _MEIPASS is not available
            return ICON_NAME
    else:
        # Running in development environment
        return ICON_NAME

ICON_NAME = "ChemLab Logo.png"
ICON_PATH = get_icon_path()
