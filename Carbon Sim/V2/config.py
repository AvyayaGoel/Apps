"""App constants: colors, radii, valences, bond data, window sizes, grid, etc."""
import os
import sys

WINDOW_W = 1260
WINDOW_H = 760
LEFT_TOOLBAR_W = 60
PANEL_W = 310
CANVAS_W = WINDOW_W - LEFT_TOOLBAR_W - PANEL_W
MENU_HEIGHT = 32
FPS = 60
STATUS_LABEL_STYLE = 'color: #8ca0c0; font-size: 12px; padding: 2px 8px;'
RECENT_ELEMENTS_SETTINGS_KEY = 'recentElements'


def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


ICON_PATH = resource_path("Carbon-Sim-Icon.ico")

VALENCES = {
    "H": 1, "He": 0,
    "Li": 1, "Be": 2, "B": 3, "C": 4, "N": 3, "O": 2, "F": 1, "Ne": 0,
    "Na": 1, "Mg": 2, "Al": 3, "Si": 4, "P": 5, "S": 6, "Cl": 1, "Ar": 0,
    "K": 1, "Ca": 2, "Sc": 3, "Ti": 4, "V": 5, "Cr": 6, "Mn": 4, "Fe": 3,
    "Co": 3, "Ni": 2, "Cu": 2, "Zn": 2, "Ga": 3, "Ge": 4, "As": 3, "Se": 4,
    "Br": 1, "Kr": 0,
    "Rb": 1, "Sr": 2, "Y": 3, "Zr": 4, "Nb": 5, "Mo": 6, "Tc": 7, "Ru": 4,
    "Rh": 3, "Pd": 2, "Ag": 1, "Cd": 2, "In": 3, "Sn": 4, "Sb": 3, "Te": 2,
    "I": 1, "Xe": 0,
    "Cs": 1, "Ba": 2, "La": 3, "Ce": 3, "Pr": 3, "Nd": 3, "Pm": 3, "Sm": 3,
    "Eu": 3, "Gd": 3, "Tb": 3, "Dy": 3, "Ho": 3, "Er": 3, "Tm": 3, "Yb": 3,
    "Lu": 3, "Hf": 4, "Ta": 5, "W": 6, "Re": 7, "Os": 4, "Ir": 3, "Pt": 2,
    "Au": 1, "Hg": 2, "Tl": 3, "Pb": 4, "Bi": 3, "Po": 2, "At": 1, "Rn": 0,
    "Fr": 1, "Ra": 2, "Ac": 3, "Th": 4, "Pa": 5, "U": 6, "Np": 5, "Pu": 4,
    "Am": 3, "Cm": 3, "Bk": 3, "Cf": 3, "Es": 3, "Fm": 3, "Md": 3, "No": 3,
    "Lr": 3, "Rf": 4, "Db": 5, "Sg": 6, "Bh": 7, "Hs": 4, "Mt": 3, "Ds": 2,
    "Rg": 1, "Cn": 2, "Nh": 3, "Fl": 4, "Mc": 3, "Lv": 2, "Ts": 1, "Og": 0,
}

COLORS = {
    "H": (255, 255, 255), "He": (217, 255, 255),
    "Li": (204, 128, 255), "Be": (194, 255, 0),
    "B": (255, 181, 181), "C": (144, 144, 144),
    "N": (48, 80, 248), "O": (255, 13, 13),
    "F": (144, 224, 80), "Ne": (179, 227, 245),
    "Na": (171, 92, 242), "Mg": (138, 255, 0),
    "Al": (191, 166, 166), "Si": (240, 200, 160),
    "P": (255, 128, 0), "S": (255, 255, 48),
    "Cl": (31, 240, 31), "Ar": (128, 209, 227),
    "K": (143, 63, 220), "Ca": (61, 255, 0),
    "Sc": (230, 230, 230), "Ti": (191, 194, 199),
    "V": (166, 166, 171), "Cr": (138, 153, 199),
    "Mn": (156, 122, 199), "Fe": (224, 102, 51),
    "Co": (240, 144, 160), "Ni": (80, 208, 80),
    "Cu": (200, 128, 51), "Zn": (125, 128, 176),
    "Ga": (194, 143, 143), "Ge": (102, 143, 143),
    "As": (189, 128, 227), "Se": (255, 161, 0),
    "Br": (165, 42, 42), "Kr": (148, 224, 224),
    "Rb": (112, 46, 176), "Sr": (0, 255, 0),
    "Y": (148, 255, 255), "Zr": (148, 224, 224),
    "Nb": (115, 194, 201), "Mo": (84, 181, 181),
    "Tc": (59, 158, 158), "Ru": (36, 143, 143),
    "Rh": (10, 125, 140), "Pd": (0, 105, 133),
    "Ag": (192, 192, 192), "Cd": (255, 217, 143),
    "In": (166, 117, 115), "Sn": (102, 128, 128),
    "Sb": (158, 99, 181), "Te": (212, 122, 0),
    "I": (148, 0, 148), "Xe": (148, 205, 205),
    "Cs": (87, 23, 140), "Ba": (0, 201, 0),
    "La": (112, 212, 255), "Ce": (255, 255, 199),
    "Pr": (217, 255, 199), "Nd": (199, 255, 199),
    "Pm": (163, 255, 199), "Sm": (143, 255, 199),
    "Eu": (97, 255, 199), "Gd": (69, 255, 199),
    "Tb": (48, 255, 199), "Dy": (31, 255, 199),
    "Ho": (0, 255, 156), "Er": (0, 230, 117),
    "Tm": (0, 212, 82), "Yb": (0, 191, 56),
    "Lu": (0, 171, 36), "Hf": (77, 194, 255),
    "Ta": (77, 166, 255), "W": (33, 148, 214),
    "Re": (38, 125, 171), "Os": (38, 102, 150),
    "Ir": (23, 84, 135), "Pt": (208, 208, 224),
    "Au": (255, 209, 35), "Hg": (184, 184, 208),
    "Tl": (166, 84, 77), "Pb": (87, 89, 97),
    "Bi": (158, 79, 181), "Po": (171, 92, 0),
    "At": (117, 79, 69), "Rn": (66, 130, 150),
    "Fr": (66, 0, 102), "Ra": (0, 125, 0),
    "Ac": (112, 171, 250), "Th": (0, 186, 255),
    "Pa": (0, 161, 255), "U": (0, 143, 255),
    "Np": (0, 128, 255), "Pu": (0, 107, 255),
    "Am": (84, 92, 242), "Cm": (120, 92, 227),
    "Bk": (138, 79, 227), "Cf": (161, 54, 212),
    "Es": (179, 31, 212), "Fm": (179, 31, 186),
    "Md": (179, 13, 166), "No": (189, 13, 135),
    "Lr": (199, 0, 102), "Rf": (204, 0, 89),
    "Db": (209, 0, 79), "Sg": (217, 0, 69),
    "Bh": (224, 0, 56), "Hs": (230, 0, 46),
    "Mt": (235, 0, 38), "Ds": (255, 0, 25),
    "Rg": (255, 0, 16), "Cn": (255, 0, 5),
    "Nh": (250, 0, 0), "Fl": (240, 0, 0),
    "Mc": (230, 0, 0), "Lv": (220, 0, 0),
    "Ts": (210, 0, 0), "Og": (200, 0, 0),
}

RADIUS = {
    "H": 10, "He": 16,
    "Li": 20, "Be": 20, "B": 22, "C": 22, "N": 22, "O": 22, "F": 22, "Ne": 16,
    "Na": 25, "Mg": 25, "Al": 25, "Si": 25, "P": 25, "S": 25, "Cl": 25, "Ar": 20,
    "K": 30, "Ca": 30, "Sc": 28, "Ti": 28, "V": 28, "Cr": 28, "Mn": 28, "Fe": 28,
    "Co": 28, "Ni": 28, "Cu": 28, "Zn": 28, "Ga": 26, "Ge": 26, "As": 26, "Se": 26,
    "Br": 26, "Kr": 26,
    "Rb": 30, "Sr": 30, "Y": 28, "Zr": 28, "Nb": 28, "Mo": 28, "Tc": 28, "Ru": 28,
    "Rh": 28, "Pd": 28, "Ag": 28, "Cd": 28, "In": 28, "Sn": 28, "Sb": 28, "Te": 28,
    "I": 26, "Xe": 26,
    "Cs": 32, "Ba": 32, "La": 30, "Ce": 30, "Pr": 30, "Nd": 30, "Pm": 30, "Sm": 30,
    "Eu": 30, "Gd": 30, "Tb": 30, "Dy": 30, "Ho": 30, "Er": 30, "Tm": 30, "Yb": 30,
    "Lu": 30, "Hf": 28, "Ta": 28, "W": 28, "Re": 28, "Os": 28, "Ir": 28, "Pt": 28,
    "Au": 28, "Hg": 28, "Tl": 28, "Pb": 28, "Bi": 28, "Po": 28, "At": 28, "Rn": 28,
    "Fr": 32, "Ra": 32, "Ac": 30, "Th": 30, "Pa": 30, "U": 30, "Np": 30, "Pu": 30,
    "Am": 30, "Cm": 30, "Bk": 30, "Cf": 30, "Es": 30, "Fm": 30, "Md": 30, "No": 30,
    "Lr": 30, "Rf": 28, "Db": 28, "Sg": 28, "Bh": 28, "Hs": 28, "Mt": 28, "Ds": 28,
    "Rg": 28, "Cn": 28, "Nh": 28, "Fl": 28, "Mc": 28, "Lv": 28, "Ts": 28, "Og": 28,
}

IDEAL_SINGLE_BOND = {
    ("C", "C"): 70, ("C", "H"): 45, ("C", "O"): 65,
    ("C", "N"): 65, ("O", "H"): 50, ("N", "H"): 50,
}

BOND_ORDER_VALUE = {"S": 1, "D": 2, "T": 3, "A": 1.5, "DA": 1}
BOND_DISPLAY_TO_LETTER = {'━': 'S', '═': 'D', '≡': 'T', '◇': 'A', '→': 'DA'}
BOND_LETTER_TO_DISPLAY = {'S': '━', 'D': '═', 'T': '≡', 'A': '◇', 'DA': '→'}
BOND_NAME_TO_LETTER = {"single": "S", "double": "D", "triple": "T", "aromatic": "A", "dative": "DA"}

BOND_TYPES = [
    {'letter': 'S', 'name': 'Single', 'glyph': '━', 'order': 1, 'tooltip': 'Single bond (1 shared pair) — shortcut 1'},
    {'letter': 'D', 'name': 'Double', 'glyph': '═', 'order': 2, 'tooltip': 'Double bond (2 shared pairs) — shortcut 2'},
    {'letter': 'T', 'name': 'Triple', 'glyph': '≡', 'order': 3, 'tooltip': 'Triple bond (3 shared pairs) — shortcut 3'},
    {'letter': 'A', 'name': 'Aromatic', 'glyph': '◇', 'order': 1.5,
     'tooltip': 'Aromatic bond (delocalized, order 1.5) — e.g. benzene ring bonds — shortcut 4'},
    {'letter': 'DA', 'name': 'Dative', 'glyph': '→', 'order': 1,
     'tooltip': 'Dative / coordinate bond — donor supplies both electrons, e.g. NH3→BF3 — shortcut 5'},
]

GROUP_VALENCE_ELECTRONS = {
    'H': 1,
    'Li': 1, 'Na': 1, 'K': 1, 'Rb': 1, 'Cs': 1,
    'Be': 2, 'Mg': 2, 'Ca': 2, 'Sr': 2, 'Ba': 2,
    'B': 3, 'Al': 3,
    'C': 4, 'Si': 4,
    'N': 5, 'P': 5,
    'O': 6, 'S': 6,
    'F': 7, 'Cl': 7, 'Br': 7, 'I': 7,
}
DUET_ELEMENTS = {'H', 'Li', 'Na', 'K', 'Rb', 'Cs', 'Be', 'Mg', 'Ca', 'Sr', 'Ba'}
HYPERVALENT_ELEMENTS = {'P', 'S', 'Cl', 'Br', 'I', 'Si'}
METAL_CHARGE_RANGE = {
    'Fe': (0, 3), 'Cu': (0, 2), 'Zn': (0, 2), 'Ag': (0, 1), 'Al': (0, 3),
    'Li': (0, 1), 'Na': (0, 1), 'K': (0, 1), 'Rb': (0, 1), 'Cs': (0, 1),
    'Be': (0, 2), 'Mg': (0, 2), 'Ca': (0, 2), 'Sr': (0, 2), 'Ba': (0, 2),
}
ELEMENT_CHARGE_DEFAULT = (-1, 1)


def formal_charge_range(element: str) -> tuple[int, int]:
    if element in METAL_CHARGE_RANGE:
        return METAL_CHARGE_RANGE[element]
    if element in GROUP_VALENCE_ELECTRONS:
        if element in HYPERVALENT_ELEMENTS:
            return -1, 2
        if element == 'B':
            return -1, 0
        return -1, 1
    return ELEMENT_CHARGE_DEFAULT


def bonds_valid_for_charge(element: str, charge: int, bond_count: float) -> bool:
    if element not in GROUP_VALENCE_ELECTRONS:
        return True
    bonds = round(bond_count * 2) / 2
    valence_electrons = GROUP_VALENCE_ELECTRONS[element]
    electrons_owned = valence_electrons - charge
    lone_pair_electrons = electrons_owned - bonds
    if lone_pair_electrons < 0 or (lone_pair_electrons * 2) % 2 != 0:
        return False
    shell_electrons = 2 * bonds + lone_pair_electrons
    target = 2 if element in DUET_ELEMENTS else 8
    if element in HYPERVALENT_ELEMENTS:
        return shell_electrons <= 12
    return shell_electrons <= target


VISIBLE_ELEMENTS = ["H", "C", "N", "O", "S", "Cl", "I"]

PERIODIC_ELEMENTS = [
    ("H", 0, 0), ("He", 0, 17),
    ("Li", 1, 0), ("Be", 1, 1),
    ("B", 1, 12), ("C", 1, 13), ("N", 1, 14), ("O", 1, 15), ("F", 1, 16), ("Ne", 1, 17),
    ("Na", 2, 0), ("Mg", 2, 1),
    ("Al", 2, 12), ("Si", 2, 13), ("P", 2, 14), ("S", 2, 15), ("Cl", 2, 16), ("Ar", 2, 17),
    ("K", 3, 0), ("Ca", 3, 1), ("Sc", 3, 2), ("Ti", 3, 3), ("V", 3, 4), ("Cr", 3, 5), ("Mn", 3, 6),
    ("Fe", 3, 7), ("Co", 3, 8), ("Ni", 3, 9), ("Cu", 3, 10), ("Zn", 3, 11),
    ("Ga", 3, 12), ("Ge", 3, 13), ("As", 3, 14), ("Se", 3, 15), ("Br", 3, 16), ("Kr", 3, 17),
    ("Rb", 4, 0), ("Sr", 4, 1), ("Y", 4, 2), ("Zr", 4, 3), ("Nb", 4, 4), ("Mo", 4, 5), ("Tc", 4, 6),
    ("Ru", 4, 7), ("Rh", 4, 8), ("Pd", 4, 9), ("Ag", 4, 10), ("Cd", 4, 11),
    ("In", 4, 12), ("Sn", 4, 13), ("Sb", 4, 14), ("Te", 4, 15), ("I", 4, 16), ("Xe", 4, 17),
    ("Cs", 5, 0), ("Ba", 5, 1), ("La", 5, 2),
    ("Hf", 5, 3), ("Ta", 5, 4), ("W", 5, 5), ("Re", 5, 6), ("Os", 5, 7), ("Ir", 5, 8), ("Pt", 5, 9),
    ("Au", 5, 10), ("Hg", 5, 11), ("Tl", 5, 12), ("Pb", 5, 13), ("Bi", 5, 14), ("Po", 5, 15),
    ("At", 5, 16), ("Rn", 5, 17),
    ("Fr", 6, 0), ("Ra", 6, 1), ("Ac", 6, 2),
    ("Rf", 6, 3), ("Db", 6, 4), ("Sg", 6, 5), ("Bh", 6, 6), ("Hs", 6, 7), ("Mt", 6, 8), ("Ds", 6, 9),
    ("Rg", 6, 10), ("Cn", 6, 11), ("Nh", 6, 12), ("Fl", 6, 13), ("Mc", 6, 14), ("Lv", 6, 15),
    ("Ts", 6, 16), ("Og", 6, 17),
    ("Ce", 8, 3), ("Pr", 8, 4), ("Nd", 8, 5), ("Pm", 8, 6), ("Sm", 8, 7), ("Eu", 8, 8),
    ("Gd", 8, 9), ("Tb", 8, 10), ("Dy", 8, 11), ("Ho", 8, 12), ("Er", 8, 13), ("Tm", 8, 14),
    ("Yb", 8, 15), ("Lu", 8, 16),
    ("Th", 9, 3), ("Pa", 9, 4), ("U", 9, 5), ("Np", 9, 6), ("Pu", 9, 7), ("Am", 9, 8),
    ("Cm", 9, 9), ("Bk", 9, 10), ("Cf", 9, 11), ("Es", 9, 12), ("Fm", 9, 13), ("Md", 9, 14),
    ("No", 9, 15), ("Lr", 9, 16),
]

MAX_HISTORY = 40
DRAG_THRESHOLD = 6
GRID_SIZE = 20
GRID_COLOR = (35, 45, 65)
GRID_MAJOR_COLOR = (55, 70, 95)
GRID_MAJOR_INTERVAL = 5
SHOW_GRID_DEFAULT = True
SNAP_TO_GRID_DEFAULT = False
SMART_JOIN_DEFAULT = True
BOND_IDEAL_LENGTH = 65
NUDGE_STEP = 1
NUDGE_STEP_SHIFT_MULTIPLIER = 10
RDKIT_2D_BOND_LENGTH = 1.5
CHAIN_SEGMENT_LENGTH = BOND_IDEAL_LENGTH
CHAIN_ZIGZAG_ANGLE_DEG = 30.0
IONIC_DISTANCE = 140.0
NAME_RESOLUTION_DEBOUNCE_MS = 600
MENU_BG = (24, 26, 34)
MENU_HOVER = (45, 55, 80)
MENU_ACTIVE = (65, 75, 110)
MENU_TEXT = (235, 240, 255)
DROPDOWN_BG = (30, 36, 48)
DROPDOWN_HOVER = (55, 65, 95)
SEPARATOR = (85, 90, 105)
STRUCTURE_TILE_W = 130
STRUCTURE_TILE_THUMB_H = 64
STRUCTURE_TILE_SPACING = 8
STRUCTURE_PLACE_SCALE = 42.0
