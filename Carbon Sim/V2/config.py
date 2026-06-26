"""All constants, colors, valences, bond data, and UI config.

This is the foundation file. Nothing imports from other project files.
Everything here is plain data — no classes, no functions.
"""

# ── Window ──────────────────────────────────────────
WINDOW_W = 1260
WINDOW_H = 760
LEFT_TOOLBAR_W = 60
PANEL_W = 310  # wide enough for 2 columns of structure tiles in the Structures panel
CANVAS_W = WINDOW_W - LEFT_TOOLBAR_W - PANEL_W
MENU_HEIGHT = 32
FPS = 60

# ── Chemistry ─────────────────────────────────────────
VALENCES = {
    "H": 1, "He": 0,
    "Li": 1, "Be": 2, "B": 3, "C": 4, "N": 3, "O": 2, "F": 1, "Ne": 0,
    "Na": 1, "Mg": 2, "Al": 3, "Si": 4, "P": 3, "S": 2, "Cl": 1, "Ar": 0,
    "K": 1, "Ca": 2, "Sc": 3, "Ti": 4, "V": 5, "Cr": 6, "Mn": 4, "Fe": 3,
    "Co": 3, "Ni": 2, "Cu": 2, "Zn": 2, "Ga": 3, "Ge": 4, "As": 3, "Se": 2,
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

# Jmol colors (industry standard)
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

# VdW radii scaled for screen (pixels)
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

# Ideal single-bond lengths (pixels, tune to canvas)
IDEAL_SINGLE_BOND = {
    ("C", "C"): 70, ("C", "H"): 45, ("C", "O"): 65,
    ("C", "N"): 65, ("O", "H"): 50, ("N", "H"): 50,
}

BOND_ORDER_VALUE = {"S": 1, "D": 2, "T": 3, "A": 1.5, "DA": 1}

# Display glyph shown on the bond-mode button / used in bond rendering.
BOND_DISPLAY_TO_LETTER = {'━': 'S', '═': 'D', '≡': 'T', '◇': 'A', '→': 'DA'}
BOND_LETTER_TO_DISPLAY = {'S': '━', 'D': '═', 'T': '≡', 'A': '◇', 'DA': '→'}
BOND_NAME_TO_LETTER = {"single": "S", "double": "D", "triple": "T", "aromatic": "A", "dative": "DA"}

# Ordered metadata for the bond-type picker popup menu.
# order: bond order used for valence bookkeeping (aromatic uses 1.5 as a
#        practical average of alternating 1/2 bonds in a real aromatic ring;
#        dative/coordinate bonds use 1 because the donor supplies both
#        electrons but the bond still occupies one coordination site).
BOND_TYPES = [
    {'letter': 'S', 'name': 'Single', 'glyph': '━', 'order': 1, 'tooltip': 'Single bond (1 shared pair) — shortcut 1'},
    {'letter': 'D', 'name': 'Double', 'glyph': '═', 'order': 2, 'tooltip': 'Double bond (2 shared pairs) — shortcut 2'},
    {'letter': 'T', 'name': 'Triple', 'glyph': '≡', 'order': 3, 'tooltip': 'Triple bond (3 shared pairs) — shortcut 3'},
    {'letter': 'A', 'name': 'Aromatic', 'glyph': '◇', 'order': 1.5,
     'tooltip': 'Aromatic bond (delocalized, order 1.5) — e.g. benzene ring bonds — shortcut 4'},
    {'letter': 'DA', 'name': 'Dative', 'glyph': '→', 'order': 1,
     'tooltip': 'Dative / coordinate bond — donor supplies both electrons, e.g. NH3→BF3 — shortcut 5'},
]

# ── Formal Charges (electron-counting model) ───────────────
# Real chemistry, derived from first principles rather than a memorized table:
# every atom's formal charge and bond count must come from a valid electron
# count under standard Lewis-structure bookkeeping. This is the same
# information hybridization/orbital reasoning would give you, computed
# directly from valence electrons instead of deriving it through orbitals —
# same physics, O(1) arithmetic, fast enough to run on every click.
#
#   electrons_owned   = (free-atom valence electrons) - (formal charge)
#   lone_pair_electrons = electrons_owned - bonds   [must be even and >= 0]
#   shell_electrons    = 2*bonds + lone_pair_electrons
#
# A given (element, charge, bond_count) is chemically valid if a non-negative,
# even lone-pair count exists AND the resulting shell electron count doesn't
# exceed that element's octet/duet (or expanded-octet for period 3+, which can
# use d-orbitals to exceed 8 — e.g. SF6, PCl5, IF7).
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
# Hydrogen and the metals fill a 2-electron duet (helium-like) shell, not an octet.
DUET_ELEMENTS = {'H', 'Li', 'Na', 'K', 'Rb', 'Cs', 'Be', 'Mg', 'Ca', 'Sr', 'Ba'}
# Period 3+ elements can use d-orbitals to legitimately exceed the octet
# (SF6, PCl5, ClF3, IF7, ...). Capped at 12 shell electrons (6 bonds) as the
# practical real-world ceiling.
HYPERVALENT_ELEMENTS = {'P', 'S', 'Cl', 'Br', 'I', 'Si'}
# Elements without simple main-group electron counting (transition/post-
# transition metals commonly drawn with an explicit ionic charge but not
# meaningfully "octet-checked" the same way). Range used directly, no
# electron-counting structural check applied.
METAL_CHARGE_RANGE = {
    'Fe': (0, 3), 'Cu': (0, 2), 'Zn': (0, 2), 'Ag': (0, 1), 'Al': (0, 3),
    'Li': (0, 1), 'Na': (0, 1), 'K': (0, 1), 'Rb': (0, 1), 'Cs': (0, 1),
    'Be': (0, 2), 'Mg': (0, 2), 'Ca': (0, 2), 'Sr': (0, 2), 'Ba': (0, 2),
}
# Practical drawing-range fallback for any element not covered by the
# electron-counting model below (e.g. unusual/heavier metals).
ELEMENT_CHARGE_DEFAULT = (-1, 1)


def formal_charge_range(element: str) -> tuple[int, int]:
    """Coarse (min, max) formal charge for an element, used to pre-filter
    obviously-impossible charges before doing the per-bond-count check."""
    if element in METAL_CHARGE_RANGE:
        return METAL_CHARGE_RANGE[element]
    if element in GROUP_VALENCE_ELECTRONS:
        # Main-group practical drawing range: rarely more than +/-2 even for
        # hypervalent elements (e.g. I3- type anions, sulfoxide/sulfone-style
        # +2 sulfur); narrower for elements with fewer valence electrons.
        v = GROUP_VALENCE_ELECTRONS[element]
        if element in HYPERVALENT_ELEMENTS:
            return -1, 2
        if element == 'B':
            return -1, 0
        return -1, 1
    return ELEMENT_CHARGE_DEFAULT


def bonds_valid_for_charge(element: str, charge: int, bond_count: float) -> bool:
    """Electron-counting check: is there a real Lewis structure for this
    element at this formal charge using this many bonds (any order mix)?
    O(1) arithmetic — no hybridization/orbital derivation needed since this
    captures the same physical constraint (available valence electrons vs.
    octet/duet capacity) directly.
    """
    if element not in GROUP_VALENCE_ELECTRONS:
        return True  # metals / unmodeled elements: don't block on structure
    bonds = round(bond_count * 2) / 2  # tolerate aromatic's 1.5 order
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

# (element, row, column) — proper periodic table layout
PERIODIC_ELEMENTS = [
    # Period 1
    ("H", 0, 0), ("He", 0, 17),
    # Period 2
    ("Li", 1, 0), ("Be", 1, 1),
    ("B", 1, 12), ("C", 1, 13), ("N", 1, 14), ("O", 1, 15), ("F", 1, 16), ("Ne", 1, 17),
    # Period 3
    ("Na", 2, 0), ("Mg", 2, 1),
    ("Al", 2, 12), ("Si", 2, 13), ("P", 2, 14), ("S", 2, 15), ("Cl", 2, 16), ("Ar", 2, 17),
    # Period 4
    ("K", 3, 0), ("Ca", 3, 1), ("Sc", 3, 2), ("Ti", 3, 3), ("V", 3, 4), ("Cr", 3, 5), ("Mn", 3, 6),
    ("Fe", 3, 7), ("Co", 3, 8), ("Ni", 3, 9), ("Cu", 3, 10), ("Zn", 3, 11),
    ("Ga", 3, 12), ("Ge", 3, 13), ("As", 3, 14), ("Se", 3, 15), ("Br", 3, 16), ("Kr", 3, 17),
    # Period 5
    ("Rb", 4, 0), ("Sr", 4, 1), ("Y", 4, 2), ("Zr", 4, 3), ("Nb", 4, 4), ("Mo", 4, 5), ("Tc", 4, 6),
    ("Ru", 4, 7), ("Rh", 4, 8), ("Pd", 4, 9), ("Ag", 4, 10), ("Cd", 4, 11),
    ("In", 4, 12), ("Sn", 4, 13), ("Sb", 4, 14), ("Te", 4, 15), ("I", 4, 16), ("Xe", 4, 17),
    # Period 6
    ("Cs", 5, 0), ("Ba", 5, 1), ("La", 5, 2),
    ("Hf", 5, 3), ("Ta", 5, 4), ("W", 5, 5), ("Re", 5, 6), ("Os", 5, 7), ("Ir", 5, 8), ("Pt", 5, 9),
    ("Au", 5, 10), ("Hg", 5, 11), ("Tl", 5, 12), ("Pb", 5, 13), ("Bi", 5, 14), ("Po", 5, 15),
    ("At", 5, 16), ("Rn", 5, 17),
    # Period 7
    ("Fr", 6, 0), ("Ra", 6, 1), ("Ac", 6, 2),
    ("Rf", 6, 3), ("Db", 6, 4), ("Sg", 6, 5), ("Bh", 6, 6), ("Hs", 6, 7), ("Mt", 6, 8), ("Ds", 6, 9),
    ("Rg", 6, 10), ("Cn", 6, 11), ("Nh", 6, 12), ("Fl", 6, 13), ("Mc", 6, 14), ("Lv", 6, 15),
    ("Ts", 6, 16), ("Og", 6, 17),
    # Lanthanides (row 8)
    ("Ce", 8, 3), ("Pr", 8, 4), ("Nd", 8, 5), ("Pm", 8, 6), ("Sm", 8, 7), ("Eu", 8, 8),
    ("Gd", 8, 9), ("Tb", 8, 10), ("Dy", 8, 11), ("Ho", 8, 12), ("Er", 8, 13), ("Tm", 8, 14),
    ("Yb", 8, 15), ("Lu", 8, 16),
    # Actinides (row 9)
    ("Th", 9, 3), ("Pa", 9, 4), ("U", 9, 5), ("Np", 9, 6), ("Pu", 9, 7), ("Am", 9, 8),
    ("Cm", 9, 9), ("Bk", 9, 10), ("Cf", 9, 11), ("Es", 9, 12), ("Fm", 9, 13), ("Md", 9, 14),
    ("No", 9, 15), ("Lr", 9, 16),
]

MAX_HISTORY = 40
DRAG_THRESHOLD = 6

# ── Grid ──────────────────────────────────────────────
GRID_SIZE = 20
GRID_COLOR = (35, 45, 65)
GRID_MAJOR_COLOR = (55, 70, 95)
GRID_MAJOR_INTERVAL = 5
SHOW_GRID_DEFAULT = True
SNAP_TO_GRID_DEFAULT = False
SMART_JOIN_DEFAULT = True
BOND_IDEAL_LENGTH = 65  # default C-C ideal length for smart join
RDKIT_2D_BOND_LENGTH = 1.5  # RDKit's Compute2DCoords default bond-length unit; used to
# rescale ghost/placed-structure geometry into canvas pixels

# ── Chain tool ──────────────────────────────────────────
# Click-drag carbon chain builder (Edit mode, beside the bond-type button).
# Each segment is BOND_IDEAL_LENGTH long; the chain zigzags at this half-angle
# off the drag axis, alternating up/down per atom, matching the classic
# skeletal-formula zigzag look regardless of where the user actually drags.
CHAIN_SEGMENT_LENGTH = BOND_IDEAL_LENGTH
CHAIN_ZIGZAG_ANGLE_DEG = 30.0

# ── Ionic ─────────────────────────────────────────────
IONIC_DISTANCE = 140.0  # px: oppositely charged atoms within this are ionically paired

# ── Menu colors ───────────────────────────────────────
MENU_BG = (24, 26, 34)
MENU_HOVER = (45, 55, 80)
MENU_ACTIVE = (65, 75, 110)
MENU_TEXT = (235, 240, 255)
DROPDOWN_BG = (30, 36, 48)
DROPDOWN_HOVER = (55, 65, 95)
SEPARATOR = (85, 90, 105)

# ── Structure Browser panel ────────────────────────────
STRUCTURE_TILE_W = 130
STRUCTURE_TILE_THUMB_H = 64  # ~2-3 text-lines tall, lazy-rendered SVG depiction
STRUCTURE_TILE_SPACING = 8
STRUCTURE_PLACE_SCALE = 42.0  # px per SMILES coordinate unit when dropped onto canvas

# Category display order (falls back to alphabetical for any category not listed)
STRUCTURE_CATEGORY_ORDER = [
    'Functional Groups', 'Alkanes', 'Alkenes & Alkynes', 'Aromatics', 'Heterocycles',
    'Alcohols & Ethers', 'Carbonyls, Acids & Esters', 'Amines & Nitrogen Compounds',
    'Halides', 'Sulfur & Phosphorus', 'Amino Acids', 'Sugars', 'Common Solvents',
    'Pharmaceuticals', 'Vitamins', 'Nucleobases', 'Polymer Monomers',
    'Inorganic & Small Molecules', 'Fatty Acids & Lipids', 'Terpenes & Natural Products',
    'Steroids', 'Dyes & Pigments', 'Macrocycles & Crown Ethers', 'Esters & Flavor Compounds',
]

# Auto-generated prebuilt structure library for the Structure Browser panel.
# Each entry: name, category, canonical SMILES, and element counts (precomputed
# with RDKit offline so the running app never needs RDKit just to list structures).
# Formula/molecular-weight/depiction are derived lazily at use-time by structure_library.py.
PREBUILT_STRUCTURES = [
    {'name': 'Methyl', 'category': 'Functional Groups', 'smiles': 'C', 'elements': {'C': 1, 'H': 4}},
    {'name': 'Ethyl', 'category': 'Functional Groups', 'smiles': 'CC', 'elements': {'C': 2, 'H': 6}},
    {'name': 'Hydroxyl (Methanol)', 'category': 'Functional Groups', 'smiles': 'CO',
     'elements': {'C': 1, 'H': 4, 'O': 1}},
    {'name': 'Carboxylic Acid (Acetic Acid)', 'category': 'Functional Groups', 'smiles': 'CC(=O)O',
     'elements': {'C': 2, 'H': 4, 'O': 2}},
    {'name': 'Aldehyde (Acetaldehyde)', 'category': 'Functional Groups', 'smiles': 'CC=O',
     'elements': {'C': 2, 'H': 4, 'O': 1}},
    {'name': 'Amine (Methylamine)', 'category': 'Functional Groups', 'smiles': 'CN',
     'elements': {'C': 1, 'H': 5, 'N': 1}},
    {'name': 'Nitro (Nitromethane)', 'category': 'Functional Groups', 'smiles': 'C[N+](=O)[O-]',
     'elements': {'C': 1, 'H': 3, 'N': 1, 'O': 2}},
    {'name': 'Nitrile (Acetonitrile)', 'category': 'Functional Groups', 'smiles': 'CC#N',
     'elements': {'C': 2, 'H': 3, 'N': 1}},
    {'name': 'Fluoromethane', 'category': 'Functional Groups', 'smiles': 'CF', 'elements': {'C': 1, 'F': 1, 'H': 3}},
    {'name': 'Chloromethane', 'category': 'Functional Groups', 'smiles': 'CCl', 'elements': {'C': 1, 'Cl': 1, 'H': 3}},
    {'name': 'Bromomethane', 'category': 'Functional Groups', 'smiles': 'CBr', 'elements': {'Br': 1, 'C': 1, 'H': 3}},
    {'name': 'Iodomethane', 'category': 'Functional Groups', 'smiles': 'CI', 'elements': {'C': 1, 'H': 3, 'I': 1}},
    {'name': 'Ester (Methyl Acetate)', 'category': 'Functional Groups', 'smiles': 'COC(C)=O',
     'elements': {'C': 3, 'H': 6, 'O': 2}},
    {'name': 'Ketone (Acetone)', 'category': 'Functional Groups', 'smiles': 'CC(C)=O',
     'elements': {'C': 3, 'H': 6, 'O': 1}},
    {'name': 'Ether (Dimethyl Ether)', 'category': 'Functional Groups', 'smiles': 'COC',
     'elements': {'C': 2, 'H': 6, 'O': 1}},
    {'name': 'Amide (Acetamide)', 'category': 'Functional Groups', 'smiles': 'CC(N)=O',
     'elements': {'C': 2, 'H': 5, 'N': 1, 'O': 1}},
    {'name': 'Thiol (Methanethiol)', 'category': 'Functional Groups', 'smiles': 'CS',
     'elements': {'C': 1, 'H': 4, 'S': 1}},
    {'name': 'Sulfonic Acid', 'category': 'Functional Groups', 'smiles': 'CS(=O)(=O)O',
     'elements': {'C': 1, 'H': 4, 'O': 3, 'S': 1}},
    {'name': 'Isocyanate', 'category': 'Functional Groups', 'smiles': 'CN=C=O',
     'elements': {'C': 2, 'H': 3, 'N': 1, 'O': 1}},
    {'name': 'Epoxide (Ethylene Oxide)', 'category': 'Functional Groups', 'smiles': 'C1CO1',
     'elements': {'C': 2, 'H': 4, 'O': 1}},
    {'name': 'Propane', 'category': 'Alkanes', 'smiles': 'CCC', 'elements': {'C': 3, 'H': 8}},
    {'name': 'n-Butane', 'category': 'Alkanes', 'smiles': 'CCCC', 'elements': {'C': 4, 'H': 10}},
    {'name': 'Isobutane', 'category': 'Alkanes', 'smiles': 'CC(C)C', 'elements': {'C': 4, 'H': 10}},
    {'name': 'n-Pentane', 'category': 'Alkanes', 'smiles': 'CCCCC', 'elements': {'C': 5, 'H': 12}},
    {'name': 'Isopentane', 'category': 'Alkanes', 'smiles': 'CCC(C)C', 'elements': {'C': 5, 'H': 12}},
    {'name': 'Neopentane', 'category': 'Alkanes', 'smiles': 'CC(C)(C)C', 'elements': {'C': 5, 'H': 12}},
    {'name': 'n-Hexane', 'category': 'Alkanes', 'smiles': 'CCCCCC', 'elements': {'C': 6, 'H': 14}},
    {'name': '2-Methylpentane', 'category': 'Alkanes', 'smiles': 'CCCC(C)C', 'elements': {'C': 6, 'H': 14}},
    {'name': '3-Methylpentane', 'category': 'Alkanes', 'smiles': 'CCC(C)CC', 'elements': {'C': 6, 'H': 14}},
    {'name': '2,2-Dimethylbutane', 'category': 'Alkanes', 'smiles': 'CCC(C)(C)C', 'elements': {'C': 6, 'H': 14}},
    {'name': 'n-Heptane', 'category': 'Alkanes', 'smiles': 'CCCCCCC', 'elements': {'C': 7, 'H': 16}},
    {'name': 'n-Octane', 'category': 'Alkanes', 'smiles': 'CCCCCCCC', 'elements': {'C': 8, 'H': 18}},
    {'name': 'Isooctane', 'category': 'Alkanes', 'smiles': 'CC(C)CC(C)(C)C', 'elements': {'C': 8, 'H': 18}},
    {'name': 'n-Nonane', 'category': 'Alkanes', 'smiles': 'CCCCCCCCC', 'elements': {'C': 9, 'H': 20}},
    {'name': 'n-Decane', 'category': 'Alkanes', 'smiles': 'CCCCCCCCCC', 'elements': {'C': 10, 'H': 22}},
    {'name': 'n-Dodecane', 'category': 'Alkanes', 'smiles': 'CCCCCCCCCCCC', 'elements': {'C': 12, 'H': 26}},
    {'name': 'Cyclopropane', 'category': 'Alkanes', 'smiles': 'C1CC1', 'elements': {'C': 3, 'H': 6}},
    {'name': 'Cyclobutane', 'category': 'Alkanes', 'smiles': 'C1CCC1', 'elements': {'C': 4, 'H': 8}},
    {'name': 'Cyclopentane', 'category': 'Alkanes', 'smiles': 'C1CCCC1', 'elements': {'C': 5, 'H': 10}},
    {'name': 'Cyclohexane', 'category': 'Alkanes', 'smiles': 'C1CCCCC1', 'elements': {'C': 6, 'H': 12}},
    {'name': 'Cycloheptane', 'category': 'Alkanes', 'smiles': 'C1CCCCCC1', 'elements': {'C': 7, 'H': 14}},
    {'name': 'Cyclooctane', 'category': 'Alkanes', 'smiles': 'C1CCCCCCC1', 'elements': {'C': 8, 'H': 16}},
    {'name': 'Methylcyclohexane', 'category': 'Alkanes', 'smiles': 'CC1CCCCC1', 'elements': {'C': 7, 'H': 14}},
    {'name': 'Decalin', 'category': 'Alkanes', 'smiles': 'C1CCC2CCCCC2C1', 'elements': {'C': 10, 'H': 18}},
    {'name': 'Adamantane', 'category': 'Alkanes', 'smiles': 'C1CC2CC3CC1CC(C2)C3', 'elements': {'C': 11, 'H': 18}},
    {'name': 'Norbornane', 'category': 'Alkanes', 'smiles': 'C1CC2CCC1C2', 'elements': {'C': 7, 'H': 12}},
    {'name': 'Ethylene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=C', 'elements': {'C': 2, 'H': 4}},
    {'name': 'Propylene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CC', 'elements': {'C': 3, 'H': 6}},
    {'name': '1-Butene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CCC', 'elements': {'C': 4, 'H': 8}},
    {'name': 'cis-2-Butene', 'category': 'Alkenes & Alkynes', 'smiles': 'C/C=C\\C', 'elements': {'C': 4, 'H': 8}},
    {'name': 'trans-2-Butene', 'category': 'Alkenes & Alkynes', 'smiles': 'C/C=C/C', 'elements': {'C': 4, 'H': 8}},
    {'name': 'Isobutylene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=C(C)C', 'elements': {'C': 4, 'H': 8}},
    {'name': '1-Pentene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CCCC', 'elements': {'C': 5, 'H': 10}},
    {'name': '1-Hexene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CCCCC', 'elements': {'C': 6, 'H': 12}},
    {'name': '1,3-Butadiene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CC=C', 'elements': {'C': 4, 'H': 6}},
    {'name': 'Isoprene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CC(=C)C', 'elements': {'C': 5, 'H': 8}},
    {'name': 'Cyclopentene', 'category': 'Alkenes & Alkynes', 'smiles': 'C1=CCCC1', 'elements': {'C': 5, 'H': 8}},
    {'name': 'Cyclohexene', 'category': 'Alkenes & Alkynes', 'smiles': 'C1=CCCCC1', 'elements': {'C': 6, 'H': 10}},
    {'name': '1,3-Cyclohexadiene', 'category': 'Alkenes & Alkynes', 'smiles': 'C1=CCCC=C1',
     'elements': {'C': 6, 'H': 8}},
    {'name': '1,3,5-Cyclooctatriene', 'category': 'Alkenes & Alkynes', 'smiles': 'C1=CC=CCCC=C1',
     'elements': {'C': 8, 'H': 10}},
    {'name': 'Acetylene', 'category': 'Alkenes & Alkynes', 'smiles': 'C#C', 'elements': {'C': 2, 'H': 2}},
    {'name': 'Propyne', 'category': 'Alkenes & Alkynes', 'smiles': 'C#CC', 'elements': {'C': 3, 'H': 4}},
    {'name': '1-Butyne', 'category': 'Alkenes & Alkynes', 'smiles': 'C#CCC', 'elements': {'C': 4, 'H': 6}},
    {'name': '2-Butyne', 'category': 'Alkenes & Alkynes', 'smiles': 'CC#CC', 'elements': {'C': 4, 'H': 6}},
    {'name': 'Benzene', 'category': 'Aromatics', 'smiles': 'c1ccccc1', 'elements': {'C': 6, 'H': 6}},
    {'name': 'Toluene', 'category': 'Aromatics', 'smiles': 'Cc1ccccc1', 'elements': {'C': 7, 'H': 8}},
    {'name': 'o-Xylene', 'category': 'Aromatics', 'smiles': 'Cc1ccccc1C', 'elements': {'C': 8, 'H': 10}},
    {'name': 'm-Xylene', 'category': 'Aromatics', 'smiles': 'Cc1cccc(C)c1', 'elements': {'C': 8, 'H': 10}},
    {'name': 'p-Xylene', 'category': 'Aromatics', 'smiles': 'Cc1ccc(C)cc1', 'elements': {'C': 8, 'H': 10}},
    {'name': 'Ethylbenzene', 'category': 'Aromatics', 'smiles': 'CCc1ccccc1', 'elements': {'C': 8, 'H': 10}},
    {'name': 'Styrene', 'category': 'Aromatics', 'smiles': 'C=Cc1ccccc1', 'elements': {'C': 8, 'H': 8}},
    {'name': 'Cumene', 'category': 'Aromatics', 'smiles': 'CC(C)c1ccccc1', 'elements': {'C': 9, 'H': 12}},
    {'name': 'Naphthalene', 'category': 'Aromatics', 'smiles': 'c1ccc2ccccc2c1', 'elements': {'C': 10, 'H': 8}},
    {'name': 'Anthracene', 'category': 'Aromatics', 'smiles': 'c1ccc2cc3ccccc3cc2c1', 'elements': {'C': 14, 'H': 10}},
    {'name': 'Phenanthrene', 'category': 'Aromatics', 'smiles': 'c1ccc2c(c1)ccc1ccccc12',
     'elements': {'C': 14, 'H': 10}},
    {'name': 'Pyrene', 'category': 'Aromatics', 'smiles': 'c1cc2ccc3cccc4ccc(c1)c2c34', 'elements': {'C': 16, 'H': 10}},
    {'name': 'Biphenyl', 'category': 'Aromatics', 'smiles': 'c1ccc(-c2ccccc2)cc1', 'elements': {'C': 12, 'H': 10}},
    {'name': 'Phenol', 'category': 'Aromatics', 'smiles': 'Oc1ccccc1', 'elements': {'C': 6, 'H': 6, 'O': 1}},
    {'name': 'Aniline', 'category': 'Aromatics', 'smiles': 'Nc1ccccc1', 'elements': {'C': 6, 'H': 7, 'N': 1}},
    {'name': 'Benzaldehyde', 'category': 'Aromatics', 'smiles': 'O=Cc1ccccc1', 'elements': {'C': 7, 'H': 6, 'O': 1}},
    {'name': 'Benzoic Acid', 'category': 'Aromatics', 'smiles': 'O=C(O)c1ccccc1', 'elements': {'C': 7, 'H': 6, 'O': 2}},
    {'name': 'Benzonitrile', 'category': 'Aromatics', 'smiles': 'N#Cc1ccccc1', 'elements': {'C': 7, 'H': 5, 'N': 1}},
    {'name': 'Nitrobenzene', 'category': 'Aromatics', 'smiles': 'O=[N+]([O-])c1ccccc1',
     'elements': {'C': 6, 'H': 5, 'N': 1, 'O': 2}},
    {'name': 'Chlorobenzene', 'category': 'Aromatics', 'smiles': 'Clc1ccccc1', 'elements': {'C': 6, 'Cl': 1, 'H': 5}},
    {'name': 'Bromobenzene', 'category': 'Aromatics', 'smiles': 'Brc1ccccc1', 'elements': {'Br': 1, 'C': 6, 'H': 5}},
    {'name': 'Fluorobenzene', 'category': 'Aromatics', 'smiles': 'Fc1ccccc1', 'elements': {'C': 6, 'F': 1, 'H': 5}},
    {'name': 'Anisole', 'category': 'Aromatics', 'smiles': 'COc1ccccc1', 'elements': {'C': 7, 'H': 8, 'O': 1}},
    {'name': 'Catechol', 'category': 'Aromatics', 'smiles': 'Oc1ccccc1O', 'elements': {'C': 6, 'H': 6, 'O': 2}},
    {'name': 'Resorcinol', 'category': 'Aromatics', 'smiles': 'Oc1cccc(O)c1', 'elements': {'C': 6, 'H': 6, 'O': 2}},
    {'name': 'Hydroquinone', 'category': 'Aromatics', 'smiles': 'Oc1ccc(O)cc1', 'elements': {'C': 6, 'H': 6, 'O': 2}},
    {'name': 'Salicylic Acid', 'category': 'Aromatics', 'smiles': 'O=C(O)c1ccccc1O',
     'elements': {'C': 7, 'H': 6, 'O': 3}},
    {'name': 'Acetophenone', 'category': 'Aromatics', 'smiles': 'CC(=O)c1ccccc1', 'elements': {'C': 8, 'H': 8, 'O': 1}},
    {'name': 'Cinnamaldehyde', 'category': 'Aromatics', 'smiles': 'O=C/C=C/c1ccccc1',
     'elements': {'C': 9, 'H': 8, 'O': 1}},
    {'name': 'Benzyl Alcohol', 'category': 'Aromatics', 'smiles': 'OCc1ccccc1', 'elements': {'C': 7, 'H': 8, 'O': 1}},
    {'name': 'p-Cresol', 'category': 'Aromatics', 'smiles': 'Cc1ccc(O)cc1', 'elements': {'C': 7, 'H': 8, 'O': 1}},
    {'name': 'Indene', 'category': 'Aromatics', 'smiles': 'C1=Cc2ccccc2C1', 'elements': {'C': 9, 'H': 8}},
    {'name': 'Fluorene', 'category': 'Aromatics', 'smiles': 'c1ccc2c(c1)Cc1ccccc1-2', 'elements': {'C': 13, 'H': 10}},
    {'name': 'Pyridine', 'category': 'Heterocycles', 'smiles': 'c1ccncc1', 'elements': {'C': 5, 'H': 5, 'N': 1}},
    {'name': 'Pyrrole', 'category': 'Heterocycles', 'smiles': 'c1cc[nH]c1', 'elements': {'C': 4, 'H': 5, 'N': 1}},
    {'name': 'Furan', 'category': 'Heterocycles', 'smiles': 'c1ccoc1', 'elements': {'C': 4, 'H': 4, 'O': 1}},
    {'name': 'Thiophene', 'category': 'Heterocycles', 'smiles': 'c1ccsc1', 'elements': {'C': 4, 'H': 4, 'S': 1}},
    {'name': 'Imidazole', 'category': 'Heterocycles', 'smiles': 'c1c[nH]cn1', 'elements': {'C': 3, 'H': 4, 'N': 2}},
    {'name': 'Pyrazole', 'category': 'Heterocycles', 'smiles': 'c1cn[nH]c1', 'elements': {'C': 3, 'H': 4, 'N': 2}},
    {'name': 'Oxazole', 'category': 'Heterocycles', 'smiles': 'c1cocn1', 'elements': {'C': 3, 'H': 3, 'N': 1, 'O': 1}},
    {'name': 'Thiazole', 'category': 'Heterocycles', 'smiles': 'c1cscn1', 'elements': {'C': 3, 'H': 3, 'N': 1, 'S': 1}},
    {'name': 'Pyrimidine', 'category': 'Heterocycles', 'smiles': 'c1cncnc1', 'elements': {'C': 4, 'H': 4, 'N': 2}},
    {'name': 'Pyridazine', 'category': 'Heterocycles', 'smiles': 'c1ccnnc1', 'elements': {'C': 4, 'H': 4, 'N': 2}},
    {'name': 'Indole', 'category': 'Heterocycles', 'smiles': 'c1ccc2[nH]ccc2c1', 'elements': {'C': 8, 'H': 7, 'N': 1}},
    {'name': 'Quinoline', 'category': 'Heterocycles', 'smiles': 'c1ccc2ncccc2c1', 'elements': {'C': 9, 'H': 7, 'N': 1}},
    {'name': 'Isoquinoline', 'category': 'Heterocycles', 'smiles': 'c1ccc2cnccc2c1',
     'elements': {'C': 9, 'H': 7, 'N': 1}},
    {'name': 'Purine', 'category': 'Heterocycles', 'smiles': 'c1ncc2[nH]cnc2n1', 'elements': {'C': 5, 'H': 4, 'N': 4}},
    {'name': 'Benzimidazole', 'category': 'Heterocycles', 'smiles': 'c1ccc2[nH]cnc2c1',
     'elements': {'C': 7, 'H': 6, 'N': 2}},
    {'name': 'Benzofuran', 'category': 'Heterocycles', 'smiles': 'c1ccc2occc2c1', 'elements': {'C': 8, 'H': 6, 'O': 1}},
    {'name': 'Benzothiophene', 'category': 'Heterocycles', 'smiles': 'c1ccc2sccc2c1',
     'elements': {'C': 8, 'H': 6, 'S': 1}},
    {'name': 'Piperidine', 'category': 'Heterocycles', 'smiles': 'C1CCNCC1', 'elements': {'C': 5, 'H': 11, 'N': 1}},
    {'name': 'Piperazine', 'category': 'Heterocycles', 'smiles': 'C1CNCCN1', 'elements': {'C': 4, 'H': 10, 'N': 2}},
    {'name': 'Morpholine', 'category': 'Heterocycles', 'smiles': 'C1COCCN1',
     'elements': {'C': 4, 'H': 9, 'N': 1, 'O': 1}},
    {'name': 'Tetrahydrofuran', 'category': 'Heterocycles', 'smiles': 'C1CCOC1', 'elements': {'C': 4, 'H': 8, 'O': 1}},
    {'name': 'Tetrahydropyran', 'category': 'Heterocycles', 'smiles': 'C1CCOCC1',
     'elements': {'C': 5, 'H': 10, 'O': 1}},
    {'name': 'Dioxane', 'category': 'Heterocycles', 'smiles': 'C1COCCO1', 'elements': {'C': 4, 'H': 8, 'O': 2}},
    {'name': 'Pyrrolidine', 'category': 'Heterocycles', 'smiles': 'C1CCNC1', 'elements': {'C': 4, 'H': 9, 'N': 1}},
    {'name': 'Caffeine', 'category': 'Heterocycles', 'smiles': 'Cn1c(=O)c2c(ncn2C)n(C)c1=O',
     'elements': {'C': 8, 'H': 10, 'N': 4, 'O': 2}},
    {'name': 'Indolizine', 'category': 'Heterocycles', 'smiles': 'c1ccn2cccc2c1', 'elements': {'C': 8, 'H': 7, 'N': 1}},
    {'name': 'Ethanol', 'category': 'Alcohols & Ethers', 'smiles': 'CCO', 'elements': {'C': 2, 'H': 6, 'O': 1}},
    {'name': '1-Propanol', 'category': 'Alcohols & Ethers', 'smiles': 'CCCO', 'elements': {'C': 3, 'H': 8, 'O': 1}},
    {'name': 'Isopropanol', 'category': 'Alcohols & Ethers', 'smiles': 'CC(C)O', 'elements': {'C': 3, 'H': 8, 'O': 1}},
    {'name': '1-Butanol', 'category': 'Alcohols & Ethers', 'smiles': 'CCCCO', 'elements': {'C': 4, 'H': 10, 'O': 1}},
    {'name': 'tert-Butanol', 'category': 'Alcohols & Ethers', 'smiles': 'CC(C)(C)O',
     'elements': {'C': 4, 'H': 10, 'O': 1}},
    {'name': 'Ethylene Glycol', 'category': 'Alcohols & Ethers', 'smiles': 'OCCO',
     'elements': {'C': 2, 'H': 6, 'O': 2}},
    {'name': 'Propylene Glycol', 'category': 'Alcohols & Ethers', 'smiles': 'CC(O)CO',
     'elements': {'C': 3, 'H': 8, 'O': 2}},
    {'name': 'Glycerol', 'category': 'Alcohols & Ethers', 'smiles': 'OCC(O)CO', 'elements': {'C': 3, 'H': 8, 'O': 3}},
    {'name': 'Diethyl Ether', 'category': 'Alcohols & Ethers', 'smiles': 'CCOCC',
     'elements': {'C': 4, 'H': 10, 'O': 1}},
    {'name': 'Cyclohexanol', 'category': 'Alcohols & Ethers', 'smiles': 'OC1CCCCC1',
     'elements': {'C': 6, 'H': 12, 'O': 1}},
    {'name': '1,4-Butanediol', 'category': 'Alcohols & Ethers', 'smiles': 'OCCCCO',
     'elements': {'C': 4, 'H': 10, 'O': 2}},
    {'name': 'Pentaerythritol', 'category': 'Alcohols & Ethers', 'smiles': 'OCC(CO)(CO)CO',
     'elements': {'C': 5, 'H': 12, 'O': 4}},
    {'name': 'Formaldehyde', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'C=O',
     'elements': {'C': 1, 'H': 2, 'O': 1}},
    {'name': 'Propionaldehyde', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CCC=O',
     'elements': {'C': 3, 'H': 6, 'O': 1}},
    {'name': 'Methyl Ethyl Ketone', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CCC(C)=O',
     'elements': {'C': 4, 'H': 8, 'O': 1}},
    {'name': 'Cyclohexanone', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=C1CCCCC1',
     'elements': {'C': 6, 'H': 10, 'O': 1}},
    {'name': 'Formic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=CO',
     'elements': {'C': 1, 'H': 2, 'O': 2}},
    {'name': 'Propionic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CCC(=O)O',
     'elements': {'C': 3, 'H': 6, 'O': 2}},
    {'name': 'Butyric Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CCCC(=O)O',
     'elements': {'C': 4, 'H': 8, 'O': 2}},
    {'name': 'Oxalic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=C(O)C(=O)O',
     'elements': {'C': 2, 'H': 2, 'O': 4}},
    {'name': 'Malonic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=C(O)CC(=O)O',
     'elements': {'C': 3, 'H': 4, 'O': 4}},
    {'name': 'Succinic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=C(O)CCC(=O)O',
     'elements': {'C': 4, 'H': 6, 'O': 4}},
    {'name': 'Citric Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=C(O)CC(O)(CC(=O)O)C(=O)O',
     'elements': {'C': 6, 'H': 8, 'O': 7}},
    {'name': 'Lactic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CC(O)C(=O)O',
     'elements': {'C': 3, 'H': 6, 'O': 3}},
    {'name': 'Pyruvic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CC(=O)C(=O)O',
     'elements': {'C': 3, 'H': 4, 'O': 3}},
    {'name': 'Acrylic Acid', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'C=CC(=O)O',
     'elements': {'C': 3, 'H': 4, 'O': 2}},
    {'name': 'Ethyl Acetate', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CCOC(C)=O',
     'elements': {'C': 4, 'H': 8, 'O': 2}},
    {'name': 'Methyl Methacrylate', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'C=C(C)C(=O)OC',
     'elements': {'C': 5, 'H': 8, 'O': 2}},
    {'name': 'Vinyl Acetate', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'C=COC(C)=O',
     'elements': {'C': 4, 'H': 6, 'O': 2}},
    {'name': 'Acetic Anhydride', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CC(=O)OC(C)=O',
     'elements': {'C': 4, 'H': 6, 'O': 3}},
    {'name': 'Acetyl Chloride', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'CC(=O)Cl',
     'elements': {'C': 2, 'Cl': 1, 'H': 3, 'O': 1}},
    {'name': 'Phosgene', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'O=C(Cl)Cl',
     'elements': {'C': 1, 'Cl': 2, 'O': 1}},
    {'name': 'Urea', 'category': 'Carbonyls, Acids & Esters', 'smiles': 'NC(N)=O',
     'elements': {'C': 1, 'H': 4, 'N': 2, 'O': 1}},
    {'name': 'Dimethylamine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'CNC',
     'elements': {'C': 2, 'H': 7, 'N': 1}},
    {'name': 'Trimethylamine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'CN(C)C',
     'elements': {'C': 3, 'H': 9, 'N': 1}},
    {'name': 'Ethylamine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'CCN',
     'elements': {'C': 2, 'H': 7, 'N': 1}},
    {'name': 'Ethylenediamine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'NCCN',
     'elements': {'C': 2, 'H': 8, 'N': 2}},
    {'name': 'Hexamethylenediamine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'NCCCCCCN',
     'elements': {'C': 6, 'H': 16, 'N': 2}},
    {'name': 'Hydrazine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'NN', 'elements': {'H': 4, 'N': 2}},
    {'name': 'Hydroxylamine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'NO',
     'elements': {'H': 3, 'N': 1, 'O': 1}},
    {'name': 'Acrylonitrile', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'C=CC#N',
     'elements': {'C': 3, 'H': 3, 'N': 1}},
    {'name': 'N,N-Dimethylformamide', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'CN(C)C=O',
     'elements': {'C': 3, 'H': 7, 'N': 1, 'O': 1}},
    {'name': 'Nicotine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'CN1CCCC1c1cccnc1',
     'elements': {'C': 10, 'H': 14, 'N': 2}},
    {'name': 'Guanidine', 'category': 'Amines & Nitrogen Compounds', 'smiles': 'N=C(N)N',
     'elements': {'C': 1, 'H': 5, 'N': 3}},
    {'name': 'Dichloromethane', 'category': 'Halides', 'smiles': 'ClCCl', 'elements': {'C': 1, 'Cl': 2, 'H': 2}},
    {'name': 'Chloroform', 'category': 'Halides', 'smiles': 'ClC(Cl)Cl', 'elements': {'C': 1, 'Cl': 3, 'H': 1}},
    {'name': 'Carbon Tetrachloride', 'category': 'Halides', 'smiles': 'ClC(Cl)(Cl)Cl', 'elements': {'C': 1, 'Cl': 4}},
    {'name': '1,2-Dichloroethane', 'category': 'Halides', 'smiles': 'ClCCCl', 'elements': {'C': 2, 'Cl': 2, 'H': 4}},
    {'name': 'Vinyl Chloride', 'category': 'Halides', 'smiles': 'C=CCl', 'elements': {'C': 2, 'Cl': 1, 'H': 3}},
    {'name': 'Bromoethane', 'category': 'Halides', 'smiles': 'CCBr', 'elements': {'Br': 1, 'C': 2, 'H': 5}},
    {'name': 'Carbon Tetrafluoride', 'category': 'Halides', 'smiles': 'FC(F)(F)F', 'elements': {'C': 1, 'F': 4}},
    {'name': 'Freon-12', 'category': 'Halides', 'smiles': 'FC(F)(Cl)Cl', 'elements': {'C': 1, 'Cl': 2, 'F': 2}},
    {'name': 'Hexafluoroethane', 'category': 'Halides', 'smiles': 'FC(F)(F)C(F)(F)F', 'elements': {'C': 2, 'F': 6}},
    {'name': 'Iodoform', 'category': 'Halides', 'smiles': 'IC(I)I', 'elements': {'C': 1, 'H': 1, 'I': 3}},
    {'name': 'Hydrogen Sulfide', 'category': 'Sulfur & Phosphorus', 'smiles': 'S', 'elements': {'H': 2, 'S': 1}},
    {'name': 'Dimethyl Sulfide', 'category': 'Sulfur & Phosphorus', 'smiles': 'CSC',
     'elements': {'C': 2, 'H': 6, 'S': 1}},
    {'name': 'Dimethyl Sulfoxide', 'category': 'Sulfur & Phosphorus', 'smiles': 'CS(C)=O',
     'elements': {'C': 2, 'H': 6, 'O': 1, 'S': 1}},
    {'name': 'Dimethyl Sulfone', 'category': 'Sulfur & Phosphorus', 'smiles': 'CS(C)(=O)=O',
     'elements': {'C': 2, 'H': 6, 'O': 2, 'S': 1}},
    {'name': 'Sulfuric Acid Ester (Dimethyl Sulfate)', 'category': 'Sulfur & Phosphorus', 'smiles': 'COS(=O)(=O)OC',
     'elements': {'C': 2, 'H': 6, 'O': 4, 'S': 1}},
    {'name': 'Trimethyl Phosphate', 'category': 'Sulfur & Phosphorus', 'smiles': 'COP(=O)(OC)OC',
     'elements': {'C': 3, 'H': 9, 'O': 4, 'P': 1}},
    {'name': 'Phosphine', 'category': 'Sulfur & Phosphorus', 'smiles': 'P', 'elements': {'H': 3, 'P': 1}},
    {'name': 'Triphenylphosphine', 'category': 'Sulfur & Phosphorus', 'smiles': 'c1ccc(P(c2ccccc2)c2ccccc2)cc1',
     'elements': {'C': 18, 'H': 15, 'P': 1}},
    {'name': 'Glycine', 'category': 'Amino Acids', 'smiles': 'NCC(=O)O', 'elements': {'C': 2, 'H': 5, 'N': 1, 'O': 2}},
    {'name': 'Alanine', 'category': 'Amino Acids', 'smiles': 'CC(N)C(=O)O',
     'elements': {'C': 3, 'H': 7, 'N': 1, 'O': 2}},
    {'name': 'Serine', 'category': 'Amino Acids', 'smiles': 'NC(CO)C(=O)O',
     'elements': {'C': 3, 'H': 7, 'N': 1, 'O': 3}},
    {'name': 'Cysteine', 'category': 'Amino Acids', 'smiles': 'NC(CS)C(=O)O',
     'elements': {'C': 3, 'H': 7, 'N': 1, 'O': 2, 'S': 1}},
    {'name': 'Valine', 'category': 'Amino Acids', 'smiles': 'CC(C)C(N)C(=O)O',
     'elements': {'C': 5, 'H': 11, 'N': 1, 'O': 2}},
    {'name': 'Leucine', 'category': 'Amino Acids', 'smiles': 'CC(C)CC(N)C(=O)O',
     'elements': {'C': 6, 'H': 13, 'N': 1, 'O': 2}},
    {'name': 'Isoleucine', 'category': 'Amino Acids', 'smiles': 'CCC(C)C(N)C(=O)O',
     'elements': {'C': 6, 'H': 13, 'N': 1, 'O': 2}},
    {'name': 'Proline', 'category': 'Amino Acids', 'smiles': 'O=C(O)C1CCCN1',
     'elements': {'C': 5, 'H': 9, 'N': 1, 'O': 2}},
    {'name': 'Threonine', 'category': 'Amino Acids', 'smiles': 'CC(O)C(N)C(=O)O',
     'elements': {'C': 4, 'H': 9, 'N': 1, 'O': 3}},
    {'name': 'Aspartic Acid', 'category': 'Amino Acids', 'smiles': 'NC(CC(=O)O)C(=O)O',
     'elements': {'C': 4, 'H': 7, 'N': 1, 'O': 4}},
    {'name': 'Glutamic Acid', 'category': 'Amino Acids', 'smiles': 'NC(CCC(=O)O)C(=O)O',
     'elements': {'C': 5, 'H': 9, 'N': 1, 'O': 4}},
    {'name': 'Asparagine', 'category': 'Amino Acids', 'smiles': 'NC(=O)CC(N)C(=O)O',
     'elements': {'C': 4, 'H': 8, 'N': 2, 'O': 3}},
    {'name': 'Glutamine', 'category': 'Amino Acids', 'smiles': 'NC(=O)CCC(N)C(=O)O',
     'elements': {'C': 5, 'H': 10, 'N': 2, 'O': 3}},
    {'name': 'Lysine', 'category': 'Amino Acids', 'smiles': 'NCCCCC(N)C(=O)O',
     'elements': {'C': 6, 'H': 14, 'N': 2, 'O': 2}},
    {'name': 'Arginine', 'category': 'Amino Acids', 'smiles': 'N=C(N)NCCCC(N)C(=O)O',
     'elements': {'C': 6, 'H': 14, 'N': 4, 'O': 2}},
    {'name': 'Histidine', 'category': 'Amino Acids', 'smiles': 'NC(Cc1c[nH]cn1)C(=O)O',
     'elements': {'C': 6, 'H': 9, 'N': 3, 'O': 2}},
    {'name': 'Phenylalanine', 'category': 'Amino Acids', 'smiles': 'NC(Cc1ccccc1)C(=O)O',
     'elements': {'C': 9, 'H': 11, 'N': 1, 'O': 2}},
    {'name': 'Tyrosine', 'category': 'Amino Acids', 'smiles': 'NC(Cc1ccc(O)cc1)C(=O)O',
     'elements': {'C': 9, 'H': 11, 'N': 1, 'O': 3}},
    {'name': 'Tryptophan', 'category': 'Amino Acids', 'smiles': 'NC(Cc1c[nH]c2ccccc12)C(=O)O',
     'elements': {'C': 11, 'H': 12, 'N': 2, 'O': 2}},
    {'name': 'Methionine', 'category': 'Amino Acids', 'smiles': 'CSCCC(N)C(=O)O',
     'elements': {'C': 5, 'H': 11, 'N': 1, 'O': 2, 'S': 1}},
    {'name': 'Glucose', 'category': 'Sugars', 'smiles': 'OCC1OC(O)C(O)C(O)C1O', 'elements': {'C': 6, 'H': 12, 'O': 6}},
    {'name': 'Fructose', 'category': 'Sugars', 'smiles': 'OCC1(O)OCC(O)C(O)C1O', 'elements': {'C': 6, 'H': 12, 'O': 6}},
    {'name': 'Ribose', 'category': 'Sugars', 'smiles': 'OCC1OC(O)C(O)C1O', 'elements': {'C': 5, 'H': 10, 'O': 5}},
    {'name': 'Deoxyribose', 'category': 'Sugars', 'smiles': 'OCC1OC(O)CC1O', 'elements': {'C': 5, 'H': 10, 'O': 4}},
    {'name': 'Sucrose', 'category': 'Sugars', 'smiles': 'OCC1OC(OC2(CO)OC(CO)C(O)C2O)C(O)C(O)C1O',
     'elements': {'C': 12, 'H': 22, 'O': 11}},
    {'name': 'Water', 'category': 'Common Solvents', 'smiles': 'O', 'elements': {'H': 2, 'O': 1}},
    {'name': 'Hexamethylphosphoramide', 'category': 'Common Solvents', 'smiles': 'CN(C)P(=O)(N(C)C)N(C)C',
     'elements': {'C': 6, 'H': 18, 'N': 3, 'O': 1, 'P': 1}},
    {'name': 'Aspirin', 'category': 'Pharmaceuticals', 'smiles': 'CC(=O)Oc1ccccc1C(=O)O',
     'elements': {'C': 9, 'H': 8, 'O': 4}},
    {'name': 'Ibuprofen', 'category': 'Pharmaceuticals', 'smiles': 'CC(C)Cc1ccc(C(C)C(=O)O)cc1',
     'elements': {'C': 13, 'H': 18, 'O': 2}},
    {'name': 'Paracetamol', 'category': 'Pharmaceuticals', 'smiles': 'CC(=O)Nc1ccc(O)cc1',
     'elements': {'C': 8, 'H': 9, 'N': 1, 'O': 2}},
    {'name': 'Penicillin G', 'category': 'Pharmaceuticals', 'smiles': 'CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(=O)O',
     'elements': {'C': 16, 'H': 18, 'N': 2, 'O': 4, 'S': 1}},
    {'name': 'Ampicillin', 'category': 'Pharmaceuticals', 'smiles': 'CC1(C)SC2C(NC(=O)C(N)c3ccccc3)C(=O)N2C1C(=O)O',
     'elements': {'C': 16, 'H': 19, 'N': 3, 'O': 4, 'S': 1}},
    {'name': 'Diazepam', 'category': 'Pharmaceuticals', 'smiles': 'CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21',
     'elements': {'C': 16, 'Cl': 1, 'H': 13, 'N': 2, 'O': 1}},
    {'name': 'Morphine', 'category': 'Pharmaceuticals', 'smiles': 'CN1CCC23c4c5ccc(O)c4OC2C(O)C=CC3C1C5',
     'elements': {'C': 17, 'H': 19, 'N': 1, 'O': 3}},
    {'name': 'Codeine', 'category': 'Pharmaceuticals', 'smiles': 'COc1ccc2c3c1OC1C(O)C=CC4C(C2)N(C)CCC341',
     'elements': {'C': 18, 'H': 21, 'N': 1, 'O': 3}},
    {'name': 'Sildenafil', 'category': 'Pharmaceuticals',
     'smiles': 'CCCc1nn(C)c2c(N3CCN(C)CC3)nc(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)nc12',
     'elements': {'C': 27, 'H': 40, 'N': 8, 'O': 3, 'S': 1}},
    {'name': 'Atorvastatin Core', 'category': 'Pharmaceuticals',
     'smiles': 'CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(=O)O',
     'elements': {'C': 33, 'F': 1, 'H': 35, 'N': 2, 'O': 5}},
    {'name': 'Lidocaine', 'category': 'Pharmaceuticals', 'smiles': 'CCN(CC)CC(=O)Nc1c(C)cccc1C',
     'elements': {'C': 14, 'H': 22, 'N': 2, 'O': 1}},
    {'name': 'Procaine', 'category': 'Pharmaceuticals', 'smiles': 'CCN(CC)CCOC(=O)c1ccc(N)cc1',
     'elements': {'C': 13, 'H': 20, 'N': 2, 'O': 2}},
    {'name': 'Fluoxetine', 'category': 'Pharmaceuticals', 'smiles': 'CNCCC(Oc1ccc(C(F)(F)F)cc1)c1ccccc1',
     'elements': {'C': 17, 'F': 3, 'H': 18, 'N': 1, 'O': 1}},
    {'name': 'Diphenhydramine', 'category': 'Pharmaceuticals', 'smiles': 'CN(C)CCOC(c1ccccc1)c1ccccc1',
     'elements': {'C': 17, 'H': 21, 'N': 1, 'O': 1}},
    {'name': 'Albuterol', 'category': 'Pharmaceuticals', 'smiles': 'CC(C)(C)NCC(O)c1ccc(O)c(CO)c1',
     'elements': {'C': 13, 'H': 21, 'N': 1, 'O': 3}},
    {'name': 'Metformin', 'category': 'Pharmaceuticals', 'smiles': 'CN(C)C(=N)NC(=N)N',
     'elements': {'C': 4, 'H': 11, 'N': 5}},
    {'name': 'Omeprazole', 'category': 'Pharmaceuticals', 'smiles': 'COc1ccc2nc(S(=O)Cc3ncc(C)c(OC)c3C)nc-2cc1',
     'elements': {'C': 18, 'H': 19, 'N': 3, 'O': 3, 'S': 1}},
    {'name': 'Warfarin', 'category': 'Pharmaceuticals', 'smiles': 'CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O',
     'elements': {'C': 19, 'H': 16, 'O': 4}},
    {'name': 'Vitamin C (Ascorbic Acid)', 'category': 'Vitamins', 'smiles': 'O=C1OC(C(O)CO)C(O)=C1O',
     'elements': {'C': 6, 'H': 8, 'O': 6}},
    {'name': 'Vitamin B3 (Niacin)', 'category': 'Vitamins', 'smiles': 'O=C(O)c1cccnc1',
     'elements': {'C': 6, 'H': 5, 'N': 1, 'O': 2}},
    {'name': 'Vitamin B6 (Pyridoxine)', 'category': 'Vitamins', 'smiles': 'Cc1ncc(CO)c(CO)c1O',
     'elements': {'C': 8, 'H': 11, 'N': 1, 'O': 3}},
    {'name': 'Folic Acid', 'category': 'Vitamins',
     'smiles': 'Nc1nc2ncc(CNc3ccc(C(=O)NC(CCC(=O)O)C(=O)O)cc3)nc2c(=O)[nH]1',
     'elements': {'C': 19, 'H': 19, 'N': 7, 'O': 6}},
    {'name': 'Retinol (Vitamin A)', 'category': 'Vitamins', 'smiles': 'CC1=C(/C=C/C(C)=C/C=C/C(C)=C/CO)C(C)(C)CCC1',
     'elements': {'C': 20, 'H': 30, 'O': 1}},
    {'name': 'Adenine', 'category': 'Nucleobases', 'smiles': 'Nc1ncnc2[nH]cnc12', 'elements': {'C': 5, 'H': 5, 'N': 5}},
    {'name': 'Guanine', 'category': 'Nucleobases', 'smiles': 'Nc1nc2[nH]cnc2c(=O)[nH]1',
     'elements': {'C': 5, 'H': 5, 'N': 5, 'O': 1}},
    {'name': 'Cytosine', 'category': 'Nucleobases', 'smiles': 'Nc1cc[nH]c(=O)n1',
     'elements': {'C': 4, 'H': 5, 'N': 3, 'O': 1}},
    {'name': 'Thymine', 'category': 'Nucleobases', 'smiles': 'Cc1c[nH]c(=O)[nH]c1=O',
     'elements': {'C': 5, 'H': 6, 'N': 2, 'O': 2}},
    {'name': 'Uracil', 'category': 'Nucleobases', 'smiles': 'O=c1cc[nH]c(=O)[nH]1',
     'elements': {'C': 4, 'H': 4, 'N': 2, 'O': 2}},
    {'name': 'Tetrafluoroethylene (PTFE)', 'category': 'Polymer Monomers', 'smiles': 'FC(F)=C(F)F',
     'elements': {'C': 2, 'F': 4}},
    {'name': 'Caprolactam (Nylon 6)', 'category': 'Polymer Monomers', 'smiles': 'O=C1CCCCCN1',
     'elements': {'C': 6, 'H': 11, 'N': 1, 'O': 1}},
    {'name': 'Adipic Acid (Nylon 66)', 'category': 'Polymer Monomers', 'smiles': 'O=C(O)CCCCC(=O)O',
     'elements': {'C': 6, 'H': 10, 'O': 4}},
    {'name': 'Terephthalic Acid (PET)', 'category': 'Polymer Monomers', 'smiles': 'O=C(O)c1ccc(C(=O)O)cc1',
     'elements': {'C': 8, 'H': 6, 'O': 4}},
    {'name': 'Bisphenol A (Polycarbonate)', 'category': 'Polymer Monomers', 'smiles': 'CC(C)(c1ccc(O)cc1)c1ccc(O)cc1',
     'elements': {'C': 15, 'H': 16, 'O': 2}},
    {'name': 'Carbon Dioxide', 'category': 'Inorganic & Small Molecules', 'smiles': 'O=C=O',
     'elements': {'C': 1, 'O': 2}},
    {'name': 'Carbon Monoxide', 'category': 'Inorganic & Small Molecules', 'smiles': '[C-]#[O+]',
     'elements': {'C': 1, 'O': 1}},
    {'name': 'Ammonia', 'category': 'Inorganic & Small Molecules', 'smiles': 'N', 'elements': {'H': 3, 'N': 1}},
    {'name': 'Hydrogen Peroxide', 'category': 'Inorganic & Small Molecules', 'smiles': 'OO',
     'elements': {'H': 2, 'O': 2}},
    {'name': 'Nitric Acid', 'category': 'Inorganic & Small Molecules', 'smiles': 'O=[N+]([O-])O',
     'elements': {'H': 1, 'N': 1, 'O': 3}},
    {'name': 'Sulfuric Acid', 'category': 'Inorganic & Small Molecules', 'smiles': 'O=S(=O)(O)O',
     'elements': {'H': 2, 'O': 4, 'S': 1}},
    {'name': 'Phosphoric Acid', 'category': 'Inorganic & Small Molecules', 'smiles': 'O=P(O)(O)O',
     'elements': {'H': 3, 'O': 4, 'P': 1}},
    {'name': 'Hydrogen Cyanide', 'category': 'Inorganic & Small Molecules', 'smiles': 'C#N',
     'elements': {'C': 1, 'H': 1, 'N': 1}},
    {'name': 'Ozone', 'category': 'Inorganic & Small Molecules', 'smiles': 'O=[O+][O-]', 'elements': {'O': 3}},
    {'name': 'Nitrous Oxide', 'category': 'Inorganic & Small Molecules', 'smiles': '[N-]=[N+]=O',
     'elements': {'N': 2, 'O': 1}},
    {'name': 'Sulfur Dioxide', 'category': 'Inorganic & Small Molecules', 'smiles': 'O=S=O',
     'elements': {'O': 2, 'S': 1}},
    {'name': 'Boric Acid', 'category': 'Inorganic & Small Molecules', 'smiles': 'OB(O)O',
     'elements': {'B': 1, 'H': 3, 'O': 3}},
    {'name': 'Silicic Acid', 'category': 'Inorganic & Small Molecules', 'smiles': 'O[Si](O)(O)O',
     'elements': {'H': 4, 'O': 4, 'Si': 1}},
    {'name': 'Caproic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCC(=O)O',
     'elements': {'C': 6, 'H': 12, 'O': 2}},
    {'name': 'Caprylic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCC(=O)O',
     'elements': {'C': 8, 'H': 16, 'O': 2}},
    {'name': 'Capric Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCCCC(=O)O',
     'elements': {'C': 10, 'H': 20, 'O': 2}},
    {'name': 'Lauric Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCCCCCC(=O)O',
     'elements': {'C': 12, 'H': 24, 'O': 2}},
    {'name': 'Myristic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCCCCCCCC(=O)O',
     'elements': {'C': 14, 'H': 28, 'O': 2}},
    {'name': 'Palmitic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCCCCCCCCCC(=O)O',
     'elements': {'C': 16, 'H': 32, 'O': 2}},
    {'name': 'Stearic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCCCCCCCCCCCC(=O)O',
     'elements': {'C': 18, 'H': 36, 'O': 2}},
    {'name': 'Oleic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCCCCC/C=C\\CCCCCCCC(=O)O',
     'elements': {'C': 18, 'H': 34, 'O': 2}},
    {'name': 'Linoleic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CCCCC/C=C\\C/C=C\\CCCCCCCC(=O)O',
     'elements': {'C': 18, 'H': 32, 'O': 2}},
    {'name': 'Linolenic Acid', 'category': 'Fatty Acids & Lipids', 'smiles': 'CC/C=C\\C/C=C\\C/C=C\\CCCCCCCC(=O)O',
     'elements': {'C': 18, 'H': 30, 'O': 2}},
    {'name': 'Arachidonic Acid', 'category': 'Fatty Acids & Lipids',
     'smiles': 'CCCCC/C=C\\C/C=C\\C/C=C\\C/C=C\\CCCC(=O)O', 'elements': {'C': 20, 'H': 32, 'O': 2}},
    {'name': 'Glyceryl Tristearate', 'category': 'Fatty Acids & Lipids',
     'smiles': 'CCCCCCCCCCCCCCCCCC(=O)OCC(COC(=O)CCCCCCCCCCCCCCCCC)OC(=O)CCCCCCCCCCCCCCCCC',
     'elements': {'C': 57, 'H': 110, 'O': 6}},
    {'name': 'Cholesterol', 'category': 'Fatty Acids & Lipids',
     'smiles': 'CC(C)CCCC(C)C1CCC2C3CC=C4CC(O)CCC4(C)C3CCC12C', 'elements': {'C': 27, 'H': 46, 'O': 1}},
    {'name': 'Lecithin Head (Choline)', 'category': 'Fatty Acids & Lipids', 'smiles': 'C[N+](C)(C)CCO',
     'elements': {'C': 5, 'H': 14, 'N': 1, 'O': 1}},
    {'name': 'Limonene', 'category': 'Terpenes & Natural Products', 'smiles': 'C=C(C)C1CC=C(C)CC1',
     'elements': {'C': 10, 'H': 16}},
    {'name': 'Menthol', 'category': 'Terpenes & Natural Products', 'smiles': 'CC1CCC(C(C)C)C(O)C1',
     'elements': {'C': 10, 'H': 20, 'O': 1}},
    {'name': 'Camphor', 'category': 'Terpenes & Natural Products', 'smiles': 'CC12CCC(CC1=O)C2(C)C',
     'elements': {'C': 10, 'H': 16, 'O': 1}},
    {'name': 'Pinene', 'category': 'Terpenes & Natural Products', 'smiles': 'CC1=CCC2CC1C2(C)C',
     'elements': {'C': 10, 'H': 16}},
    {'name': 'Geraniol', 'category': 'Terpenes & Natural Products', 'smiles': 'CC(C)=CCCC(C)=CCO',
     'elements': {'C': 10, 'H': 18, 'O': 1}},
    {'name': 'Citral', 'category': 'Terpenes & Natural Products', 'smiles': 'CC(C)=CCCC(C)=CC=O',
     'elements': {'C': 10, 'H': 16, 'O': 1}},
    {'name': 'Eugenol', 'category': 'Terpenes & Natural Products', 'smiles': 'C=CCc1ccc(O)c(OC)c1',
     'elements': {'C': 10, 'H': 12, 'O': 2}},
    {'name': 'Vanillin', 'category': 'Terpenes & Natural Products', 'smiles': 'COc1cc(C=O)ccc1O',
     'elements': {'C': 8, 'H': 8, 'O': 3}},
    {'name': 'Thymol', 'category': 'Terpenes & Natural Products', 'smiles': 'Cc1ccc(C(C)C)c(O)c1',
     'elements': {'C': 10, 'H': 14, 'O': 1}},
    {'name': 'Carvone', 'category': 'Terpenes & Natural Products', 'smiles': 'C=C(C)C1CC=C(C)C(=O)C1',
     'elements': {'C': 10, 'H': 14, 'O': 1}},
    {'name': 'Squalene', 'category': 'Terpenes & Natural Products',
     'smiles': 'CC(C)=CCCC(C)=CCCC(C)=CCCC=C(C)CCC=C(C)CCC=C(C)C', 'elements': {'C': 30, 'H': 50}},
    {'name': 'Beta-Carotene', 'category': 'Terpenes & Natural Products',
     'smiles': 'CC1=C(/C=C/C(C)=C/C=C/C(C)=C/C=C/C=C(C)/C=C/C=C(C)/C=C/C2=C(C)CCCC2(C)C)C(C)(C)CCC1',
     'elements': {'C': 40, 'H': 56}},
    {'name': 'Testosterone', 'category': 'Steroids', 'smiles': 'CC12CCC(=O)C=C1CCC1C2CCC2(C)C(O)CCC12',
     'elements': {'C': 19, 'H': 28, 'O': 2}},
    {'name': 'Progesterone', 'category': 'Steroids', 'smiles': 'CC(=O)C1CCC2C3CCC4(C)C(=O)CCC4C3CCC12C',
     'elements': {'C': 20, 'H': 30, 'O': 2}},
    {'name': 'Estradiol', 'category': 'Steroids', 'smiles': 'CC12CCC3c4ccc(O)cc4CCC3C1CCC2O',
     'elements': {'C': 18, 'H': 24, 'O': 2}},
    {'name': 'Cortisone', 'category': 'Steroids', 'smiles': 'CC12C=CC(=O)C=C1CCC1C2C(=O)CC2(C)C1CCC2(O)C(=O)CO',
     'elements': {'C': 21, 'H': 26, 'O': 5}},
    {'name': 'Indigo', 'category': 'Dyes & Pigments', 'smiles': 'O=C1Nc2ccccc2/C1=C1\\C(=O)Nc2ccccc21',
     'elements': {'C': 16, 'H': 10, 'N': 2, 'O': 2}},
    {'name': 'Azobenzene', 'category': 'Dyes & Pigments', 'smiles': 'c1ccc(/N=N/c2ccccc2)cc1',
     'elements': {'C': 12, 'H': 10, 'N': 2}},
    {'name': 'Phenolphthalein', 'category': 'Dyes & Pigments', 'smiles': 'O=C1OC(O)(c2ccc(O)cc2)c2ccccc21',
     'elements': {'C': 14, 'H': 10, 'O': 4}},
    {'name': 'Anthraquinone', 'category': 'Dyes & Pigments', 'smiles': 'O=C1c2ccccc2C(=O)c2ccccc21',
     'elements': {'C': 14, 'H': 8, 'O': 2}},
    {'name': 'Fluorescein', 'category': 'Dyes & Pigments', 'smiles': 'O=C1OC2(c3ccc(O)cc3Oc3cc(O)ccc32)c2ccccc21',
     'elements': {'C': 20, 'H': 12, 'O': 5}},
    {'name': '18-Crown-6', 'category': 'Macrocycles & Crown Ethers', 'smiles': 'C1COCCOCCOCCOCCO1',
     'elements': {'C': 10, 'H': 20, 'O': 5}},
    {'name': '12-Crown-4', 'category': 'Macrocycles & Crown Ethers', 'smiles': 'C1COCCOCCO1',
     'elements': {'C': 6, 'H': 12, 'O': 3}},
    {'name': 'Quinoxaline', 'category': 'Heterocycles', 'smiles': 'c1ccc2nccnc2c1',
     'elements': {'C': 8, 'H': 6, 'N': 2}},
    {'name': 'Phthalazine', 'category': 'Heterocycles', 'smiles': 'c1ccc2cnncc2c1',
     'elements': {'C': 8, 'H': 6, 'N': 2}},
    {'name': 'Carbazole', 'category': 'Heterocycles', 'smiles': 'c1ccc2c(c1)[nH]c1ccccc12',
     'elements': {'C': 12, 'H': 9, 'N': 1}},
    {'name': 'Acridine', 'category': 'Heterocycles', 'smiles': 'c1ccc2nc3ccccc3cc2c1',
     'elements': {'C': 13, 'H': 9, 'N': 1}},
    {'name': 'Xanthene', 'category': 'Heterocycles', 'smiles': 'c1ccc2c(c1)Cc1ccccc1O2',
     'elements': {'C': 13, 'H': 10, 'O': 1}},
    {'name': 'Triazole', 'category': 'Heterocycles', 'smiles': 'c1cn[nH]n1', 'elements': {'C': 2, 'H': 3, 'N': 3}},
    {'name': 'Tetrazole', 'category': 'Heterocycles', 'smiles': 'c1nnn[nH]1', 'elements': {'C': 1, 'H': 2, 'N': 4}},
    {'name': 'Isoxazole', 'category': 'Heterocycles', 'smiles': 'c1cnoc1',
     'elements': {'C': 3, 'H': 3, 'N': 1, 'O': 1}},
    {'name': 'Ethyl Butyrate', 'category': 'Esters & Flavor Compounds', 'smiles': 'CCCC(=O)OCC',
     'elements': {'C': 6, 'H': 12, 'O': 2}},
    {'name': 'Isoamyl Acetate', 'category': 'Esters & Flavor Compounds', 'smiles': 'CC(=O)OCCC(C)C',
     'elements': {'C': 7, 'H': 14, 'O': 2}},
    {'name': 'Benzyl Acetate', 'category': 'Esters & Flavor Compounds', 'smiles': 'CC(=O)OCc1ccccc1',
     'elements': {'C': 9, 'H': 10, 'O': 2}},
    {'name': 'Methyl Salicylate', 'category': 'Esters & Flavor Compounds', 'smiles': 'COC(=O)c1ccccc1O',
     'elements': {'C': 8, 'H': 8, 'O': 3}},
    {'name': 'Ethyl Cinnamate', 'category': 'Esters & Flavor Compounds', 'smiles': 'CCOC(=O)/C=C/c1ccccc1',
     'elements': {'C': 11, 'H': 12, 'O': 2}},
    {'name': 'Geranyl Acetate', 'category': 'Esters & Flavor Compounds', 'smiles': 'CC(=O)OCC=C(C)CCC=C(C)C',
     'elements': {'C': 12, 'H': 20, 'O': 2}},
    {'name': 'Linalyl Acetate', 'category': 'Esters & Flavor Compounds', 'smiles': 'C=CC(C)(CCC=C(C)C)OC(C)=O',
     'elements': {'C': 12, 'H': 20, 'O': 2}},
    {'name': 'n-Undecane', 'category': 'Alkanes', 'smiles': 'CCCCCCCCCCC', 'elements': {'C': 11, 'H': 24}},
    {'name': 'n-Tridecane', 'category': 'Alkanes', 'smiles': 'CCCCCCCCCCCCC', 'elements': {'C': 13, 'H': 28}},
    {'name': 'n-Tetradecane', 'category': 'Alkanes', 'smiles': 'CCCCCCCCCCCCCC', 'elements': {'C': 14, 'H': 30}},
    {'name': '2,3-Dimethylbutane', 'category': 'Alkanes', 'smiles': 'CC(C)C(C)C', 'elements': {'C': 6, 'H': 14}},
    {'name': '3-Ethylpentane', 'category': 'Alkanes', 'smiles': 'CCC(CC)CC', 'elements': {'C': 7, 'H': 16}},
    {'name': 'Spiropentane', 'category': 'Alkanes', 'smiles': 'C1CC12CC2', 'elements': {'C': 5, 'H': 8}},
    {'name': 'Bicyclohexyl', 'category': 'Alkanes', 'smiles': 'C1CCC(C2CCCCC2)CC1', 'elements': {'C': 12, 'H': 22}},
    {'name': '2-Methyl-1-Butene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=C(C)CC', 'elements': {'C': 5, 'H': 10}},
    {'name': '3-Methyl-1-Butene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CC(C)C', 'elements': {'C': 5, 'H': 10}},
    {'name': '1-Heptene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CCCCCC', 'elements': {'C': 7, 'H': 14}},
    {'name': '1-Octene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CCCCCCC', 'elements': {'C': 8, 'H': 16}},
    {'name': 'Allene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=C=C', 'elements': {'C': 3, 'H': 4}},
    {'name': '1,5-Hexadiene', 'category': 'Alkenes & Alkynes', 'smiles': 'C=CCCC=C', 'elements': {'C': 6, 'H': 10}},
    {'name': '1-Pentyne', 'category': 'Alkenes & Alkynes', 'smiles': 'C#CCCC', 'elements': {'C': 5, 'H': 8}},
    {'name': '2-Pentyne', 'category': 'Alkenes & Alkynes', 'smiles': 'CC#CCC', 'elements': {'C': 5, 'H': 8}},
    {'name': '1-Hexyne', 'category': 'Alkenes & Alkynes', 'smiles': 'C#CCCCC', 'elements': {'C': 6, 'H': 10}},
    {'name': 'Mesitylene', 'category': 'Aromatics', 'smiles': 'Cc1cc(C)cc(C)c1', 'elements': {'C': 9, 'H': 12}},
    {'name': 'Durene', 'category': 'Aromatics', 'smiles': 'Cc1ccc(C)c(C)c1C', 'elements': {'C': 10, 'H': 14}},
    {'name': '4-Tert-Butyltoluene', 'category': 'Aromatics', 'smiles': 'Cc1ccc(C(C)(C)C)cc1',
     'elements': {'C': 11, 'H': 16}},
    {'name': 'Diphenylmethane', 'category': 'Aromatics', 'smiles': 'c1ccc(Cc2ccccc2)cc1',
     'elements': {'C': 13, 'H': 12}},
    {'name': 'Triphenylmethane', 'category': 'Aromatics', 'smiles': 'c1ccc(C(c2ccccc2)c2ccccc2)cc1',
     'elements': {'C': 19, 'H': 16}},
    {'name': '2-Naphthol', 'category': 'Aromatics', 'smiles': 'Oc1ccc2ccccc2c1', 'elements': {'C': 10, 'H': 8, 'O': 1}},
    {'name': '1-Naphthylamine', 'category': 'Aromatics', 'smiles': 'Nc1cccc2ccccc12',
     'elements': {'C': 10, 'H': 9, 'N': 1}},
    {'name': 'p-Toluidine', 'category': 'Aromatics', 'smiles': 'Cc1ccc(N)cc1', 'elements': {'C': 7, 'H': 9, 'N': 1}},
    {'name': 'p-Phenylenediamine', 'category': 'Aromatics', 'smiles': 'Nc1ccc(N)cc1',
     'elements': {'C': 6, 'H': 8, 'N': 2}},
    {'name': '4-Aminobenzoic Acid', 'category': 'Aromatics', 'smiles': 'Nc1ccc(C(=O)O)cc1',
     'elements': {'C': 7, 'H': 7, 'N': 1, 'O': 2}},
    {'name': 'Sulfanilamide', 'category': 'Aromatics', 'smiles': 'Nc1ccc(S(N)(=O)=O)cc1',
     'elements': {'C': 6, 'H': 8, 'N': 2, 'O': 2, 'S': 1}},
    {'name': 'Saccharin', 'category': 'Aromatics', 'smiles': 'O=C1NS(=O)(=O)c2ccccc21',
     'elements': {'C': 7, 'H': 5, 'N': 1, 'O': 3, 'S': 1}},
    {'name': 'Benzenesulfonic Acid', 'category': 'Aromatics', 'smiles': 'O=S(=O)(O)c1ccccc1',
     'elements': {'C': 6, 'H': 6, 'O': 3, 'S': 1}},
]
