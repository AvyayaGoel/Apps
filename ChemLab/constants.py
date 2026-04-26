# -*- coding: utf-8 -*-
"""
Constants for ChemLab Application
"""
import os
import sys

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
REACTIONS_COLUMNS = ["★", "Reaction", "Type"]

COLOR_STYLE = "color: #ffffff;"

FONT = "Cambria Math"


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


ICON_NAME = "ChemLab Logo.png"
ICON_PATH = resource_path(ICON_NAME)

# Element data (symbol -> {name, atomic_number, atomic_weight})
# Replacing mendeleev dependency to avoid EXE packaging issues
ELEMENTS_DATA = {
    'H': {'name': 'Hydrogen', 'atomic_number': 1, 'atomic_weight': 1.008},
    'He': {'name': 'Helium', 'atomic_number': 2, 'atomic_weight': 4.0026},
    'Li': {'name': 'Lithium', 'atomic_number': 3, 'atomic_weight': 6.94},
    'Be': {'name': 'Beryllium', 'atomic_number': 4, 'atomic_weight': 9.0122},
    'B': {'name': 'Boron', 'atomic_number': 5, 'atomic_weight': 10.81},
    'C': {'name': 'Carbon', 'atomic_number': 6, 'atomic_weight': 12.011},
    'N': {'name': 'Nitrogen', 'atomic_number': 7, 'atomic_weight': 14.007},
    'O': {'name': 'Oxygen', 'atomic_number': 8, 'atomic_weight': 15.999},
    'F': {'name': 'Fluorine', 'atomic_number': 9, 'atomic_weight': 18.998},
    'Ne': {'name': 'Neon', 'atomic_number': 10, 'atomic_weight': 20.180},
    'Na': {'name': 'Sodium', 'atomic_number': 11, 'atomic_weight': 22.990},
    'Mg': {'name': 'Magnesium', 'atomic_number': 12, 'atomic_weight': 24.305},
    'Al': {'name': 'Aluminium', 'atomic_number': 13, 'atomic_weight': 26.982},
    'Si': {'name': 'Silicon', 'atomic_number': 14, 'atomic_weight': 28.085},
    'P': {'name': 'Phosphorus', 'atomic_number': 15, 'atomic_weight': 30.974},
    'S': {'name': 'Sulfur', 'atomic_number': 16, 'atomic_weight': 32.06},
    'Cl': {'name': 'Chlorine', 'atomic_number': 17, 'atomic_weight': 35.45},
    'Ar': {'name': 'Argon', 'atomic_number': 18, 'atomic_weight': 39.948},
    'K': {'name': 'Potassium', 'atomic_number': 19, 'atomic_weight': 39.098},
    'Ca': {'name': 'Calcium', 'atomic_number': 20, 'atomic_weight': 40.078},
    'Sc': {'name': 'Scandium', 'atomic_number': 21, 'atomic_weight': 44.956},
    'Ti': {'name': 'Titanium', 'atomic_number': 22, 'atomic_weight': 47.867},
    'V': {'name': 'Vanadium', 'atomic_number': 23, 'atomic_weight': 50.942},
    'Cr': {'name': 'Chromium', 'atomic_number': 24, 'atomic_weight': 51.996},
    'Mn': {'name': 'Manganese', 'atomic_number': 25, 'atomic_weight': 54.938},
    'Fe': {'name': 'Iron', 'atomic_number': 26, 'atomic_weight': 55.845},
    'Co': {'name': 'Cobalt', 'atomic_number': 27, 'atomic_weight': 58.933},
    'Ni': {'name': 'Nickel', 'atomic_number': 28, 'atomic_weight': 58.693},
    'Cu': {'name': 'Copper', 'atomic_number': 29, 'atomic_weight': 63.546},
    'Zn': {'name': 'Zinc', 'atomic_number': 30, 'atomic_weight': 65.38},
    'Ga': {'name': 'Gallium', 'atomic_number': 31, 'atomic_weight': 69.723},
    'Ge': {'name': 'Germanium', 'atomic_number': 32, 'atomic_weight': 72.63},
    'As': {'name': 'Arsenic', 'atomic_number': 33, 'atomic_weight': 74.922},
    'Se': {'name': 'Selenium', 'atomic_number': 34, 'atomic_weight': 78.96},
    'Br': {'name': 'Bromine', 'atomic_number': 35, 'atomic_weight': 79.904},
    'Kr': {'name': 'Krypton', 'atomic_number': 36, 'atomic_weight': 83.798},
    'Rb': {'name': 'Rubidium', 'atomic_number': 37, 'atomic_weight': 85.468},
    'Sr': {'name': 'Strontium', 'atomic_number': 38, 'atomic_weight': 87.62},
    'Y': {'name': 'Yttrium', 'atomic_number': 39, 'atomic_weight': 88.906},
    'Zr': {'name': 'Zirconium', 'atomic_number': 40, 'atomic_weight': 91.224},
    'Nb': {'name': 'Niobium', 'atomic_number': 41, 'atomic_weight': 92.906},
    'Mo': {'name': 'Molybdenum', 'atomic_number': 42, 'atomic_weight': 95.95},
    'Tc': {'name': 'Technetium', 'atomic_number': 43, 'atomic_weight': 98},
    'Ru': {'name': 'Ruthenium', 'atomic_number': 44, 'atomic_weight': 101.07},
    'Rh': {'name': 'Rhodium', 'atomic_number': 45, 'atomic_weight': 102.91},
    'Pd': {'name': 'Palladium', 'atomic_number': 46, 'atomic_weight': 106.42},
    'Ag': {'name': 'Silver', 'atomic_number': 47, 'atomic_weight': 107.87},
    'Cd': {'name': 'Cadmium', 'atomic_number': 48, 'atomic_weight': 112.41},
    'In': {'name': 'Indium', 'atomic_number': 49, 'atomic_weight': 114.82},
    'Sn': {'name': 'Tin', 'atomic_number': 50, 'atomic_weight': 118.71},
    'Sb': {'name': 'Antimony', 'atomic_number': 51, 'atomic_weight': 121.76},
    'Te': {'name': 'Tellurium', 'atomic_number': 52, 'atomic_weight': 127.60},
    'I': {'name': 'Iodine', 'atomic_number': 53, 'atomic_weight': 126.90},
    'Xe': {'name': 'Xenon', 'atomic_number': 54, 'atomic_weight': 131.29},
    'Cs': {'name': 'Cesium', 'atomic_number': 55, 'atomic_weight': 132.91},
    'Ba': {'name': 'Barium', 'atomic_number': 56, 'atomic_weight': 137.33},
    'La': {'name': 'Lanthanum', 'atomic_number': 57, 'atomic_weight': 138.91},
    'Ce': {'name': 'Cerium', 'atomic_number': 58, 'atomic_weight': 140.12},
    'Pr': {'name': 'Praseodymium', 'atomic_number': 59, 'atomic_weight': 140.91},
    'Nd': {'name': 'Neodymium', 'atomic_number': 60, 'atomic_weight': 144.24},
    'Pm': {'name': 'Promethium', 'atomic_number': 61, 'atomic_weight': 145},
    'Sm': {'name': 'Samarium', 'atomic_number': 62, 'atomic_weight': 150.36},
    'Eu': {'name': 'Europium', 'atomic_number': 63, 'atomic_weight': 151.96},
    'Gd': {'name': 'Gadolinium', 'atomic_number': 64, 'atomic_weight': 157.25},
    'Tb': {'name': 'Terbium', 'atomic_number': 65, 'atomic_weight': 158.93},
    'Dy': {'name': 'Dysprosium', 'atomic_number': 66, 'atomic_weight': 162.50},
    'Ho': {'name': 'Holmium', 'atomic_number': 67, 'atomic_weight': 164.93},
    'Er': {'name': 'Erbium', 'atomic_number': 68, 'atomic_weight': 167.26},
    'Tm': {'name': 'Thulium', 'atomic_number': 69, 'atomic_weight': 168.93},
    'Yb': {'name': 'Ytterbium', 'atomic_number': 70, 'atomic_weight': 173.05},
    'Lu': {'name': 'Lutetium', 'atomic_number': 71, 'atomic_weight': 174.97},
    'Hf': {'name': 'Hafnium', 'atomic_number': 72, 'atomic_weight': 178.49},
    'Ta': {'name': 'Tantalum', 'atomic_number': 73, 'atomic_weight': 180.95},
    'W': {'name': 'Tungsten', 'atomic_number': 74, 'atomic_weight': 183.84},
    'Re': {'name': 'Rhenium', 'atomic_number': 75, 'atomic_weight': 186.21},
    'Os': {'name': 'Osmium', 'atomic_number': 76, 'atomic_weight': 190.23},
    'Ir': {'name': 'Iridium', 'atomic_number': 77, 'atomic_weight': 192.22},
    'Pt': {'name': 'Platinum', 'atomic_number': 78, 'atomic_weight': 195.08},
    'Au': {'name': 'Gold', 'atomic_number': 79, 'atomic_weight': 196.97},
    'Hg': {'name': 'Mercury', 'atomic_number': 80, 'atomic_weight': 200.59},
    'Tl': {'name': 'Thallium', 'atomic_number': 81, 'atomic_weight': 204.38},
    'Pb': {'name': 'Lead', 'atomic_number': 82, 'atomic_weight': 207.2},
    'Bi': {'name': 'Bismuth', 'atomic_number': 83, 'atomic_weight': 208.98},
    'Po': {'name': 'Polonium', 'atomic_number': 84, 'atomic_weight': 209},
    'At': {'name': 'Astatine', 'atomic_number': 85, 'atomic_weight': 210},
    'Rn': {'name': 'Radon', 'atomic_number': 86, 'atomic_weight': 222},
    'Fr': {'name': 'Francium', 'atomic_number': 87, 'atomic_weight': 223},
    'Ra': {'name': 'Radium', 'atomic_number': 88, 'atomic_weight': 226},
    'Ac': {'name': 'Actinium', 'atomic_number': 89, 'atomic_weight': 227},
    'Th': {'name': 'Thorium', 'atomic_number': 90, 'atomic_weight': 232.04},
    'Pa': {'name': 'Protactinium', 'atomic_number': 91, 'atomic_weight': 231.04},
    'U': {'name': 'Uranium', 'atomic_number': 92, 'atomic_weight': 238.03},
    'Np': {'name': 'Neptunium', 'atomic_number': 93, 'atomic_weight': 237},
    'Pu': {'name': 'Plutonium', 'atomic_number': 94, 'atomic_weight': 244},
    'Am': {'name': 'Americium', 'atomic_number': 95, 'atomic_weight': 243},
    'Cm': {'name': 'Curium', 'atomic_number': 96, 'atomic_weight': 247},
    'Bk': {'name': 'Berkelium', 'atomic_number': 97, 'atomic_weight': 247},
    'Cf': {'name': 'Californium', 'atomic_number': 98, 'atomic_weight': 251},
    'Es': {'name': 'Einsteinium', 'atomic_number': 99, 'atomic_weight': 252},
    'Fm': {'name': 'Fermium', 'atomic_number': 100, 'atomic_weight': 257},
    'Md': {'name': 'Mendelevium', 'atomic_number': 101, 'atomic_weight': 258},
    'No': {'name': 'Nobelium', 'atomic_number': 102, 'atomic_weight': 259},
    'Lr': {'name': 'Lawrencium', 'atomic_number': 103, 'atomic_weight': 262},
    'Rf': {'name': 'Rutherfordium', 'atomic_number': 104, 'atomic_weight': 267},
    'Db': {'name': 'Dubnium', 'atomic_number': 105, 'atomic_weight': 268},
    'Sg': {'name': 'Seaborgium', 'atomic_number': 106, 'atomic_weight': 269},
    'Bh': {'name': 'Bohrium', 'atomic_number': 107, 'atomic_weight': 270},
    'Hs': {'name': 'Hassium', 'atomic_number': 108, 'atomic_weight': 277},
    'Mt': {'name': 'Meitnerium', 'atomic_number': 109, 'atomic_weight': 278},
    'Ds': {'name': 'Darmstadtium', 'atomic_number': 110, 'atomic_weight': 281},
    'Rg': {'name': 'Roentgenium', 'atomic_number': 111, 'atomic_weight': 282},
    'Cn': {'name': 'Copernicium', 'atomic_number': 112, 'atomic_weight': 285},
    'Nh': {'name': 'Nihonium', 'atomic_number': 113, 'atomic_weight': 286},
    'Fl': {'name': 'Flerovium', 'atomic_number': 114, 'atomic_weight': 289},
    'Mc': {'name': 'Moscovium', 'atomic_number': 115, 'atomic_weight': 290},
    'Lv': {'name': 'Livermorium', 'atomic_number': 116, 'atomic_weight': 293},
    'Ts': {'name': 'Tennessine', 'atomic_number': 117, 'atomic_weight': 294},
    'Og': {'name': 'Oganesson', 'atomic_number': 118, 'atomic_weight': 294},
}
