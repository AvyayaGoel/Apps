import json
import math
import os
import sys
import threading
import time
import urllib.parse
from collections import defaultdict
from tkinter import Tk

import pygame
from rdkit import RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem import rdCoordGen

RDLogger.logger().setLevel(RDLogger.CRITICAL)

pygame.init()

FONT = pygame.font.SysFont("Arial", 16)
BIG_FONT = pygame.font.SysFont("Arial", 20, bold=True)

W, H = 1200, 760
PANEL_W = 260
CANVAS_W = W - PANEL_W
FPS = 60
pygame.key.set_repeat(300, 30)
screen = pygame.display.set_mode((W, H))
pygame.scrap.init()  # This starts the clipboard engine
clipboard_data = pygame.scrap.get_text()  # This grabs the text properly
clock = pygame.time.Clock()


def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(".."))
    return os.path.join(base_path, relative_path)


# 3. Load and set the icon
try:
    icon_path = get_resource_path("Carbon-Sim-Icon.png")
    icon_image = pygame.image.load(icon_path)
    pygame.display.set_icon(icon_image)
except Exception as e:
    print(f"Could not load icon: {e}")
pygame.display.set_caption("Carbon Simulator - Loading...")

# --- Chemistry data ---

VALENCES = {
    "H": 1, "He": 0,
    "Li": 1, "Be": 2, "B": 3, "C": 4, "N": 3, "O": 2, "F": 1, "Ne": 0,
    "Na": 1, "Mg": 2, "Al": 3, "Si": 4, "P": 3, "S": 2, "Cl": 1, "Ar": 0,
    "K": 1, "Ca": 2,
    "Ti": 4, "Cr": 6, "Fe": 2, "Ni": 2, "Cu": 2, "Zn": 2,
    "Br": 1, "I": 1
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
    "Ti": (191, 194, 199), "Cr": (138, 153, 199),
    "Fe": (224, 102, 51), "Ni": (80, 208, 80),
    "Cu": (200, 128, 51), "Zn": (125, 128, 176),
    "Br": (165, 42, 42), "I": (148, 0, 148)
}

# VdW radii scaled for screen (ideal for pygame)
RADIUS = {
    "H": 10, "He": 16,
    "Li": 20, "Be": 20, "B": 22, "C": 22, "N": 22, "O": 22, "F": 22, "Ne": 16,
    "Na": 25, "Mg": 25, "Al": 25, "Si": 25, "P": 25, "S": 25, "Cl": 25, "Ar": 20,
    "K": 30, "Ca": 30,
    "Ti": 28, "Cr": 28, "Fe": 28, "Ni": 28, "Cu": 28, "Zn": 28,
    "Br": 26, "I": 26
}

# ideal single-bond lengths (pixels, tune to canvas)
IDEAL_SINGLE_BOND = {
    ('C', 'C'): 70,
    ('C', 'H'): 45,
    ('C', 'O'): 65,
    ('C', 'N'): 65,
    ('O', 'H'): 50,
    ('N', 'H'): 50,
}


def ideal_bond_length(a, b, order=1):
    key = (a, b)
    if key not in IDEAL_SINGLE_BOND:
        key = (b, a)
    base = IDEAL_SINGLE_BOND.get(key, 60)
    return base * (0.95 - 0.03 * (order - 1))


BOND_ORDER_VALUE = {
    "S": 1,
    "D": 2,
    "T": 3
}

double_to_letter = {
    1.0: 'S',
    2.0: 'D',
    3.0: 'T'
}
BOND_NAME_TO_LETTER = {
    "single": "S",
    "double": "D",
    "triple": "T"
}

# state
atoms = []  # each: {'id', 'x','y','element', 'auto':bool(optional)}
bonds = []  # list of {"a1": id1, "a2": id2, "type": int}
next_id = 1
display_name = ""

selected_element = 'C'
auto_bond = True
smart_join = True  # NEW: smart join toggle
threshold = 100  # px
bond_creating = None  # stores atom id when dragging to create a bond
clicked_atom_id = None
is_dragging = False
last_name_compute_time = 0
NAME_COMPUTE_INTERVAL = 0.05
name_lock = threading.Lock()
progress = 0
JUST_OPENED_NAME_INPUT = False
app_state = "loading"
opacity = 255
loading_build = False
build_progress = 0.0
UI_RECTS = {}
TOOL_MODE = "select"

BOND_MENU_OPEN = False
BOND_MODE = "S"  # options: single/double/triple
BOND_BUTTON_RECT = None
BOND_MENU_RECTS = {}

# ===== PAN & ZOOM =====
CAMERA_X = 0
CAMERA_Y = 0
ZOOM = 1.0
MIN_ZOOM = 0.4
MAX_ZOOM = 2.5
PAN_ACTIVE = False
PAN_BUTTON = 2

BUILD_OVERLAY_ACTIVE = False
BUILD_OVERLAY_START = 0

# ============================================================
# MENU SYSTEM GLOBALS (Final Unified)
# ============================================================
MENU_HEIGHT = 32

MENU_ITEMS = ["File", "Edit", "View", "Help"]
MENU_RECTS = {}
DROPDOWN_RECTS = {}

MENU_ACTIVE = None
MENU_HOVER_ITEM = None

ABOUT_OPEN = False
ABOUT_CLOSE_RECT = pygame.Rect(0, 0, 0, 0)

font_menu = pygame.font.SysFont("Segoe UI", 16)

MENU_BG = (24, 26, 34)
MENU_HOVER = (45, 55, 80)
MENU_ACTIVE_BG = (65, 75, 110)
MENU_TEXT = (235, 240, 255)

DROPDOWN_BG = (30, 36, 48)
DROPDOWN_HOVER = (55, 65, 95)

SEPARATOR_COLOR = (85, 90, 105)

DROPDOWN_CONTENT = {
    "File": [
        ("New", "Ctrl + N"),
        ("Open", "Ctrl + O"),
        ("Save", "Ctrl + S"),
        ("Save As", "Ctrl + Shift + S"),
        ("Exit", None)
    ],
    "Edit": [
        ("Undo", "Ctrl + Z"),
        ("Redo", "Ctrl + Y"),
        ("Cut", None),
        ("Copy", None),
        ("Paste", None),
        ("Delete", "Del"),
        ("Select All", "Ctrl + A")
    ],
    "View": [
        ("Center Molecule", None),
        ("Reset Zoom", "Ctrl + R"),
    ],
    "Help": [
        ("Help", "H"),
        ("About", None)
    ]
}

PERIODIC_PANEL_OPEN = False
PERIODIC_PANEL_RECTS = {}
SELECTED_FROM_PERIODIC = None

# Recommended subset: (compact but useful)
PERIODIC_ELEMENTS = [
    "H", "He",
    "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
    "K", "Ca", "Ti", "Cr", "Fe", "Ni", "Cu", "Zn",
    "Br", "I"
]

VISIBLE_ELEMENTS = ["H", "C", "N", "O", "S", "Cl", "I"]

# Use a new Rect for the Clear-Up button, maybe below the old one
CLEAR_UP_RECT = pygame.Rect(CANVAS_W - 190, H - 110, 150, 40)  # 50px higher
show_help = False

# dragging / clicking logic
dragging_id = None
drag_offset = (0, 0)
mouse_down_pos = None
mouse_down_time = 0
last_click_time = 0
double_click_interval = 0.35  # seconds
compute_name_requested = True  # initially True to compute the first name
delete_dragging = False
DRAG_THRESHOLD = 6  # pixels — if moved more than this, it's a drag not a click
MARQUEE_ACTIVE = False
MARQUEE_START = (0, 0)
MARQUEE_END = (0, 0)

SELECTED_ATOMS = set()
SELECTED_BONDS = set()

# global formula/mass shown in UI
GLOBAL_FORMULA = ""
GLOBAL_MASS = 0.0

NAME_INPUT_OPEN = False
name_input_buffer = ""
name_input_cursor = 0
cursor_visible = True
last_cursor_toggle = 0
name_input_lines = []
name_input_scroll = 0
name_input_scrollbar_visible = False
name_input_scrollbar_dragging = False
name_input_scrollbar_drag_offset = 0
NAME_INPUT_SCROLLBAR_RECT = None
LAST_SAVE_PATH = None

# functional group UI state
fg_panel_active = False
fg_panel_carbon_id = None

# functional group panel (scrolling)
fg_scroll = 0
FG_PANEL_HEIGHT = 140  # visible height of the FG panel box
FG_BUTTON_HEIGHT = 30  # height of each FG button

# add ALL functional groups here
FG_OPTIONS = [
    "methyl", "ethyl",
    "hydroxy", "carboxyl", "aldehyde",
    "amino", "nitro", "cyano",
    "fluoro", "chloro", "bromo", "iodo",
    "ester"
]
fg_selection = None  # 'methyl', 'ethyl', 'hydroxy', 'carboxyl', 'aldehyde'
dragging_group = set()
drag_offsets = {}

BIG_FONT = pygame.font.SysFont("Arial", 26, bold=True)
FONT = pygame.font.SysFont("Arial", 16)
SMALL_FONT = pygame.font.SysFont("Arial", 20)
TINY_FONT = pygame.font.SysFont("Arial", 12)

try:
    erase_path = os.path.join(os.path.dirname(__file__), "erase.png")
    _erase_img = pygame.image.load(erase_path).convert_alpha()
    ERASE_ICON = pygame.transform.smoothscale(_erase_img, (24, 24))
except Exception as e:
    print("Erase icon load failed:", e)
    ERASE_ICON = None

try:
    select_path = os.path.join(os.path.dirname(__file__), "cursor.png")
    _select_img = pygame.image.load(select_path).convert_alpha()
    SELECT_ICON = pygame.transform.smoothscale(_select_img, (24, 24))
except Exception as e:
    print("Select icon load failed:", e)
    SELECT_ICON = None

try:
    broom_path = os.path.join(os.path.dirname(__file__), "broom.png")
    # Load and scale the icon
    _broom_img = pygame.image.load(broom_path).convert_alpha()
    BROOM_ICON = pygame.transform.smoothscale(_broom_img, (28, 28))  # Slightly bigger icon
except Exception as e:
    print("Broom icon load failed:", e)
    BROOM_ICON = None  # Fallback to None if file is missing
ui_ready = False


def world_to_screen(x, y):
    """Convert world/camera coordinates to screen (canvas) coordinates."""
    sx = (x - CAMERA_X) * ZOOM
    sy = (y - CAMERA_Y) * ZOOM
    return sx, sy


def screen_to_world(sx, sy):
    """Convert screen (canvas) coords into world coords (for hit tests & placing atoms)."""
    wx = sx / ZOOM + CAMERA_X
    wy = sy / ZOOM + CAMERA_Y
    return wx, wy


def get_atom(atom_id):
    """Return atom dict for given id (or None)."""
    return next((a for a in atoms if a['id'] == atom_id), None)


def prepare_ui():
    global ui_ready, progress
    # pretend there are multiple loading steps
    steps = 10
    for i in range(steps):
        time.sleep(0.2)  # simulate heavy work
        progress = (i + 1) / steps
    ui_ready = True


# helper geometry & search
def dist(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def hit_atom_at(pos):
    sx, sy = pos

    for a in reversed(atoms):
        r = RADIUS.get(a['element'], 12) * ZOOM
        ax = (a['x'] - CAMERA_X) * ZOOM
        ay = (a['y'] - CAMERA_Y) * ZOOM

        if (sx - ax) ** 2 + (sy - ay) ** 2 <= (r + 6) ** 2:
            return a
    return None


def count_bond_usage():
    usage = defaultdict(int)
    for bond in bonds:
        ida = bond['a1']
        idb = bond['a2']
        order = bond['type']
        usage[ida] += order
        usage[idb] += order
    return usage


def show_loading_until_ready():
    global opacity
    global app_state

    fade_out = False
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

        screen.fill((15, 18, 24))

        # Text
        txt = FONT.render("Loading UI...", True, (200, 200, 255))
        rect = txt.get_rect(center=(W // 2, H // 2 - 60))
        screen.blit(txt, rect)

        # Progress bar outline
        bar_w, bar_h = 400, 25
        bar_x = W // 2 - bar_w // 2
        bar_y = H // 2

        pygame.draw.rect(screen, (80, 80, 120), (bar_x, bar_y, bar_w, bar_h), 3)

        # Progress bar fill
        fill_w = int(bar_w * progress)
        pygame.draw.rect(screen, (120, 160, 255), (bar_x, bar_y, fill_w, bar_h))

        # Fade out once ready
        if fade_out:
            overlay = pygame.Surface((W, H))
            overlay.set_alpha(opacity)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

            opacity -= 10
            if opacity <= 0:
                return

        # Trigger fade
        if ui_ready and not fade_out:
            fade_out = True

        app_state = "main"

        pygame.display.flip()
        clock.tick(60)


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Distance from point (px,py) to segment (x1,y1)-(x2,y2)"""
    vx = x2 - x1
    vy = y2 - y1
    wx = px - x1
    wy = py - y1
    vlen2 = vx * vx + vy * vy
    if vlen2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / vlen2))
    projx = x1 + t * vx
    projy = y1 + t * vy
    return math.hypot(px - projx, py - projy)


def hit_bond_at(pos, threshold=8):
    """Detects ANY bond type with dynamic segment counts."""
    mx, my = pos

    for i, b in enumerate(bonds):
        A = get_atom(b['a1'])
        B = get_atom(b['a2'])
        if not A or not B:
            continue

        # convert atoms to screen coords
        ax, ay = world_to_screen(A['x'], A['y'])
        bx, by = world_to_screen(B['x'], B['y'])

        dx = bx - ax
        dy = by - ay
        d = math.hypot(dx, dy)
        if d == 0:
            continue

        nx = -dy / d
        ny = dx / d

        btype = str(b.get("type", "S"))

        # ---- 1) Straight bonds (S, D, T, bold) ----
        if btype in ("S", "D", "T"):
            order = BOND_ORDER_VALUE.get(btype, 1)
            spacing = 6
            for o in range(order):
                off = (o - (order - 1) / 2) * spacing
                x1 = ax + nx * off
                y1 = ay + ny * off
                x2 = bx + nx * off
                y2 = by + ny * off
                if point_to_segment_distance(mx, my, x1, y1, x2, y2) <= threshold:
                    return i, b

    return None


def show_build_overlay(duration=2.3):
    # Step 1: capture whatever is currently on screen
    base_frame = screen.copy()

    start = time.time()
    angle = 0
    radius = 35

    while time.time() - start < duration:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

        # Step 2: redraw the saved frame
        screen.blit(base_frame, (0, 0))

        # Step 3: transparent dim layer
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))  # 120 alpha = still see background
        screen.blit(overlay, (0, 0))
        # Step 4: text
        text = FONT.render("Building molecule...", True, (240, 240, 255))
        screen.blit(text, text.get_rect(center=(W // 2, H // 2 - 50)))

        # Step 5: orbiting dot animation
        cx, cy = W // 2, H // 2 + 20
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)

        pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), 6)
        pygame.draw.circle(screen, (200, 200, 255), (cx, cy), 12, width=2)

        angle += 0.15
        pygame.display.flip()
        clock.tick(60)


def threaded_build(name):
    global loading_build, build_progress

    loading_build = True
    build_progress = 0.0

    # Fake progress bar while RDKit works
    # (RDKit has no real progress callbacks)
    for i in range(5):
        time.sleep(0.25)
        build_progress = (i + 1) / 5

    # Now actually build the molecule
    build_from_name(name)

    loading_build = False


def sanitize_text(s):
    # Remove null characters + any other problematic control chars
    return ''.join(ch for ch in s if ch >= ' ' and ch != '\x00')


def handle_name_input_event(event):
    global name_input_buffer, name_input_cursor, NAME_INPUT_OPEN, name_input_scrollbar_visible, name_input_scrollbar_dragging, name_input_scroll
    global name_input_lines, BUILD_BTN_RECT, JUST_OPENED_NAME_INPUT, name_input_scrollbar_drag_offset

    if JUST_OPENED_NAME_INPUT:
        JUST_OPENED_NAME_INPUT = False
        return True
        # ---------------------------------------------
    # CLICKING INSIDE THE TEXT AREA (cursor move)
    # ---------------------------------------------
    if NAME_INPUT_OPEN and event.type == pygame.MOUSEBUTTONDOWN:
        mx, my = event.pos

        # must match layout in draw_name_input_overlay()
        box_w = int(W * 0.55)
        box_h = int(H * 0.55)
        box_x = (W - box_w) // 2
        box_y = (H - box_h) // 2

        tx = box_x + 20
        ty = box_y + 70
        tw = box_w - 40
        th = box_h - 150

        # Check if "Build" button was clicked
        if BUILD_BTN_RECT and BUILD_BTN_RECT.collidepoint(mx, my):
            NAME_INPUT_OPEN = False
            start_build_from_name(name_input_buffer)
            show_build_overlay()
            return True

        # Check if scrollbar was clicked
        if name_input_scrollbar_visible and NAME_INPUT_SCROLLBAR_RECT and NAME_INPUT_SCROLLBAR_RECT.collidepoint(mx, my):
            name_input_scrollbar_dragging = True
            name_input_scrollbar_drag_offset = my - NAME_INPUT_SCROLLBAR_RECT.y
            return True

        # Clicking inside textbox moves cursor
        if tx <= mx <= tx + tw and ty <= my <= ty + th:

            font = pygame.font.SysFont("Arial", 22)
            line_h = font.get_height() + 4

            # Recompute lines with proper scrollbar detection
            box_w = int(W * 0.55)
            scrollbar_width = 16
            
            # First compute with full width to check if scrollbar needed
            recompute_name_input_lines(box_w - 40)
            th = int(H * 0.55) - 150  # text height from draw function
            visible_lines = th // line_h
            total_lines = len(name_input_lines)
            scrollbar_needed = total_lines > visible_lines
            
            # Recompute with correct width if scrollbar is needed
            if scrollbar_needed:
                text_width = box_w - 40 - scrollbar_width
                recompute_name_input_lines(text_width)
            else:
                text_width = box_w - 40

            # ------------------------------
            # 1. Rebuild absolute line index map
            # ------------------------------
            global line_index_map
            line_index_map = []

            pos = 0
            for line in name_input_lines:
                line_index_map.append((pos, pos + len(line)))
                pos += len(line)

            # ------------------------------
            # 2. Determine clicked line (account for scroll offset)
            # ------------------------------
            clicked_line = (my - ty) // line_h + name_input_scroll

            if not name_input_lines:
                # Handle empty buffer - set cursor to position 0
                name_input_cursor = 0
                return True

            if clicked_line < 0:
                clicked_line = 0
            if clicked_line >= len(name_input_lines):
                clicked_line = len(name_input_lines) - 1

            line = name_input_lines[clicked_line]
            start, _ = line_index_map[clicked_line]

            # ------------------------------
            # 3. Determine clicked column
            # ------------------------------
            rel_x = mx - tx

            col = 0
            # Find the character position that matches the click position
            for i in range(len(line) + 1):
                char_width = font.size(line[:i])[0]
                if char_width >= rel_x:
                    col = i
                    break
                # If this is the last iteration, and we still haven't found a match,
                # the cursor should be at the end of the line
                if i == len(line):
                    col = len(line)

            # ------------------------------
            # 4. Set final cursor position
            # ------------------------------
            name_input_cursor = start + col

            return True

    # ---------------------------------------------
    # KEYBOARD INPUT
    # ---------------------------------------------
    if event.type == pygame.KEYDOWN:

        # Escape closes overlay
        if event.key == pygame.K_ESCAPE:
            NAME_INPUT_OPEN = False
            return True

        # Delete key should not be handled by name input
        if event.key == pygame.K_DELETE:
            return False  # Let main handler process delete key

        if event.key == pygame.K_RETURN:
            NAME_INPUT_OPEN = False
            start_build_from_name(name_input_buffer)
            show_build_overlay()
            return True

        # Backspace
        if event.key == pygame.K_BACKSPACE:
            if name_input_cursor > 0:
                name_input_buffer = (
                        name_input_buffer[:name_input_cursor - 1] +
                        name_input_buffer[name_input_cursor:]
                )
                name_input_cursor -= 1
            return True

        # Arrow Up: move to previous line
        if event.key == pygame.K_UP:
            # Compute with proper scrollbar detection
            box_w = int(W * 0.55)
            scrollbar_width = 16
            
            # First compute with full width to check if scrollbar needed
            recompute_name_input_lines(box_w - 40)
            line_h = pygame.font.SysFont("Arial", 22).get_height() + 4
            th = int(H * 0.55) - 150
            visible_lines = th // line_h
            total_lines = len(name_input_lines)
            scrollbar_needed = total_lines > visible_lines
            
            # Recompute with correct width if scrollbar is needed
            if scrollbar_needed:
                text_width = box_w - 40 - scrollbar_width
                recompute_name_input_lines(text_width)
            font = pygame.font.SysFont("Arial", 22)

            # Determine cursor's current line + visual position
            pos = 0
            line_index = 0
            visual_offset = 0  # pixel position from start of line
            
            for i, line in enumerate(name_input_lines):
                if pos <= name_input_cursor <= pos + len(line):
                    line_index = i
                    char_offset = name_input_cursor - pos
                    # Calculate visual width of characters before cursor
                    visual_offset = font.size(line[:char_offset])[0]
                    break
                pos += len(line)

            # If not first line, move up
            if line_index > 0:
                prev_line = name_input_lines[line_index - 1]
                
                # Find character position in prev line that matches visual position
                best_char_pos = 0
                for i in range(len(prev_line) + 1):
                    char_width = font.size(prev_line[:i])[0]
                    if char_width >= visual_offset:
                        best_char_pos = i
                        break
                    # If we reach the end and still haven't found a match,
                    # cursor should be at the end of the line
                    if i == len(prev_line):
                        best_char_pos = len(prev_line)
                
                # compute new global index
                new_pos = sum(len(name_input_lines[i]) for i in range(line_index - 1))
                name_input_cursor = new_pos + best_char_pos

            return True

        # Arrow Down: move to next line
        if event.key == pygame.K_DOWN:
            # Compute with proper scrollbar detection
            box_w = int(W * 0.55)
            scrollbar_width = 16
            
            # First compute with full width to check if scrollbar needed
            recompute_name_input_lines(box_w - 40)
            line_h = pygame.font.SysFont("Arial", 22).get_height() + 4
            th = int(H * 0.55) - 150
            visible_lines = th // line_h
            total_lines = len(name_input_lines)
            scrollbar_needed = total_lines > visible_lines
            
            # Recompute with correct width if scrollbar is needed
            if scrollbar_needed:
                text_width = box_w - 40 - scrollbar_width
                recompute_name_input_lines(text_width)
            font = pygame.font.SysFont("Arial", 22)

            # Determine cursor's current line + visual position
            pos = 0
            line_index = 0
            visual_offset = 0  # pixel position from start of line
            
            for i, line in enumerate(name_input_lines):
                if pos <= name_input_cursor <= pos + len(line):
                    line_index = i
                    char_offset = name_input_cursor - pos
                    # Calculate visual width of characters before cursor
                    visual_offset = font.size(line[:char_offset])[0]
                    break
                pos += len(line)

            if line_index < len(name_input_lines) - 1:
                next_line = name_input_lines[line_index + 1]
                
                # Find character position in next line that matches visual position
                best_char_pos = 0
                for i in range(len(next_line) + 1):
                    char_width = font.size(next_line[:i])[0]
                    if char_width >= visual_offset:
                        best_char_pos = i
                        break
                    # If we reach the end and still haven't found a match,
                    # cursor should be at the end of the line
                    if i == len(next_line):
                        best_char_pos = len(next_line)

                new_pos = sum(len(name_input_lines[i]) for i in range(line_index + 1))
                name_input_cursor = new_pos + best_char_pos

            return True

        # Arrow Left
        if event.key == pygame.K_LEFT:
            name_input_cursor = max(0, name_input_cursor - 1)
            return True

        # Arrow Right
        if event.key == pygame.K_RIGHT:
            name_input_cursor = min(len(name_input_buffer), name_input_cursor + 1)
            return True

        if event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
            try:
                # Get clipboard text properly
                clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                if clip:
                    # Handle both string and bytes
                    if isinstance(clip, bytes):
                        text = clip.decode('utf-8', errors='ignore')
                    else:
                        text = clip
                    text = text.replace("\r", "")
                    text = sanitize_text(text)
                    name_input_buffer = (
                            name_input_buffer[:name_input_cursor] +
                            text +
                            name_input_buffer[name_input_cursor:]
                    )
                    name_input_cursor += len(text)
            except Exception as e:
                # Optional: uncomment for debugging
                print(f"Paste error: {e}")
                pass
            return True

    # ---------------------------------------------
    # MOUSE BUTTON RELEASE FOR SCROLLBAR
    # ---------------------------------------------
    if event.type == pygame.MOUSEBUTTONUP and name_input_scrollbar_dragging:
        name_input_scrollbar_dragging = False
        name_input_scrollbar_drag_offset = 0
        return True

    # ---------------------------------------------
    # TEXT INPUT FOR NORMAL TYPING
    # ---------------------------------------------
    if event.type == pygame.TEXTINPUT:
        txt = event.text
        name_input_buffer = (
                name_input_buffer[:name_input_cursor] +
                txt +
                name_input_buffer[name_input_cursor:]
        )
        name_input_cursor += len(txt)
        
        # Auto-scroll to keep cursor visible
        if name_input_scrollbar_visible:
            box_w = int(W * 0.55)
            scrollbar_width = 16
            
            # First compute with full width to check if scrollbar needed
            recompute_name_input_lines(box_w - 40)
            line_h = pygame.font.SysFont("Arial", 22).get_height() + 4
            th = int(H * 0.55) - 150
            visible_lines = th // line_h
            total_lines = len(name_input_lines)
            scrollbar_needed = total_lines > visible_lines
            
            # Recompute with correct width if scrollbar is needed
            if scrollbar_needed:
                text_width = box_w - 40 - scrollbar_width
                recompute_name_input_lines(text_width)
            
            # Find which line the cursor is on
            pos = 0
            cursor_line = 0
            for i, line in enumerate(name_input_lines):
                if pos <= name_input_cursor <= pos + len(line):
                    cursor_line = i
                    break
                pos += len(line)
            
            # Scroll if cursor is outside visible range
            if cursor_line < name_input_scroll:
                name_input_scroll = cursor_line
            elif cursor_line >= name_input_scroll + visible_lines:
                name_input_scroll = cursor_line - visible_lines + 1
        
        return True

    # ---------------------------------------------
    # MOUSE MOTION FOR SCROLLBAR DRAGGING
    # ---------------------------------------------
    if event.type == pygame.MOUSEMOTION and name_input_scrollbar_dragging:
        mx, my = event.pos
        if NAME_INPUT_SCROLLBAR_RECT:
            # Calculate new scroll position based on mouse position
            line_height = pygame.font.SysFont("Arial", 22).get_height() + 4
            box_h = int(H * 0.55)
            th = box_h - 150
            visible_lines = th // line_height
            total_lines = len(name_input_lines)
            max_scroll = max(0, total_lines - visible_lines)
            
            if max_scroll > 0:
                scrollbar_y = NAME_INPUT_SCROLLBAR_RECT.y - name_input_scrollbar_drag_offset
                scrollbar_height = th
                
                # Map mouse position to scroll value
                relative_pos = my - scrollbar_y
                scroll_ratio = max(0, min(1, relative_pos / scrollbar_height))
                name_input_scroll = int(scroll_ratio * max_scroll)
        return True

    return False


# --- Insert this new function before clear_up_molecule() ---

def draw_full_scene_for_animation():
    """Redraws the entire screen (canvas + UI) to maintain context during animation."""
    global PERIODIC_PANEL_OPEN, show_help, NAME_INPUT_OPEN

    # 1. Draw the canvas (molecule and background)
    draw_canvas()

    # 2. Draw the main persistent UI elements (Menu and Left Toolbar)
    # This is crucial for keeping the UI from disappearing
    draw_menu_bar()
    draw_left_toolbar()

    # 3. Draw conditional overlays (if active)
    # These must be redrawn to prevent flicker/disappearance
    if PERIODIC_PANEL_OPEN:
        draw_periodic_panel()
    if show_help:
        draw_help_overlay(screen, FONT)
    if NAME_INPUT_OPEN:
        draw_name_input_overlay()


# -----------------------------------------------------------

def clear_up_molecule():
    global atoms, bonds, next_id, CAMERA_X, CAMERA_Y, ZOOM

    if not atoms:
        print("Cannot clear-up an empty canvas.")
        return

    # 1. Build RDKit molecule
    try:
        mol = Chem.RWMol()
        sim_id_to_idx = {}

        for a in atoms:
            at = Chem.Atom(a['element'])
            at.SetFormalCharge(a.get('formal_charge', 0))
            idx = mol.AddAtom(at)
            sim_id_to_idx[a['id']] = idx

        for b in bonds:
            a1 = sim_id_to_idx[b['a1']]
            a2 = sim_id_to_idx[b['a2']]
            bt = {
                "S": Chem.BondType.SINGLE,
                "D": Chem.BondType.DOUBLE,
                "T": Chem.BondType.TRIPLE
            }[b['type']]

            mol.AddBond(a1, a2, bt)

        rd_mol = mol.GetMol()
        rd_mol.UpdatePropertyCache()
        Chem.SanitizeMol(rd_mol)

    except Exception as e:
        print("Error building RDKit molecule:", e)
        return

    rd_mol = Chem.AddHs(rd_mol)
    rdCoordGen.AddCoords(rd_mol)
    center_x = (CANVAS_W / 2) - CAMERA_X / ZOOM
    center_y = (H / 2) - CAMERA_Y / ZOOM

    new_atoms, new_bonds, final_id = rdkit_mol_to_simulator_data_optimized(
        rd_mol,
        center_x,
        center_y
    )

    atoms = new_atoms
    bonds = new_bonds
    next_id = final_id
    reload()


def update_window_title():
    if LAST_SAVE_PATH:
        name = LAST_SAVE_PATH.replace("\\", "/").split("/")[-1]
        pygame.display.set_caption(f"Carbon Simulator — {name}")
    else:
        pygame.display.set_caption("Carbon Simulator — Untitled")


def reload():
    global ZOOM, CAMERA_X, CAMERA_Y
    ZOOM = 1.0
    CAMERA_X = 0
    CAMERA_Y = 0
    if atoms:
        cx = sum(a['x'] for a in atoms) / len(atoms)
        cy = sum(a['y'] for a in atoms) / len(atoms)
        CAMERA_X = cx - CANVAS_W / (2 * ZOOM)
        CAMERA_Y = cy - H / (2 * ZOOM)


def rdkit_mol_to_simulator_data_optimized(rdkit_mol, center_x, center_y):
    """
    Converts a fully processed RDKit molecule back to simulator format,
    calculating new unique IDs and centering the structure.
    """
    global next_id
    new_atoms = []
    new_bonds = []
    rd_idx_to_sim_id = {}
    current_id = next_id

    # RDKit coordinates are relative; we need to scale and center them.
    conf = rdkit_mol.GetConformer(0)

    # Find the geometric center of the RDKit coordinates
    sum_x = sum(conf.GetAtomPosition(i).x for i in range(rdkit_mol.GetNumAtoms()))
    sum_y = sum(conf.GetAtomPosition(i).y for i in range(rdkit_mol.GetNumAtoms()))
    mol_center_x = sum_x / rdkit_mol.GetNumAtoms()
    mol_center_y = sum_y / rdkit_mol.GetNumAtoms()

    # Scaling factor (adjusts Ångströms to your pixel scale, e.g., 60 pixels/bond)
    # A standard RDKit bond is ~1.5 Ångströms. Your C-C bond is ~70 pixels.
    # Scale factor = 70 / 1.5 = 46.6
    PIXEL_SCALE = 65.0

    # 1. Process Atoms
    for i, atom in enumerate(rdkit_mol.GetAtoms()):
        pos = conf.GetAtomPosition(i)

        # Calculate new Pygame coordinates: Scale, shift to center (0,0), then translate to canvas center
        x = ((pos.x - mol_center_x) * PIXEL_SCALE) + center_x
        y = ((pos.y - mol_center_y) * PIXEL_SCALE) + center_y

        new_atoms.append({
            'id': current_id,
            'x': x,
            'y': y,
            'element': atom.GetSymbol(),
            'formal_charge': atom.GetFormalCharge()
        })
        rd_idx_to_sim_id[i] = current_id
        current_id += 1

    # 2. Process Bonds
    for bond in rdkit_mol.GetBonds():
        a1_idx = bond.GetBeginAtomIdx()
        a2_idx = bond.GetEndAtomIdx()
        bt = bond.GetBondType()
        if bt == Chem.BondType.TRIPLE:
            bond_type = 'T'
        elif bt == Chem.BondType.DOUBLE:
            bond_type = 'D'
        else:
            bond_type = 'S'  # Catch-all for single/aromatic/etc.

        new_bonds.append({
            'a1': rd_idx_to_sim_id[a1_idx],
            'a2': rd_idx_to_sim_id[a2_idx],
            'type': bond_type
        })

    return new_atoms, new_bonds, current_id


def recompute_name_input_lines(max_width=None):
    global name_input_lines, name_input_buffer

    font = pygame.font.SysFont("Arial", 22)

    # Use provided max_width or calculate default
    if max_width is None:
        box_w = int(W * 0.55)
        max_width = box_w - 40

    wrapped = []
    current = ""

    for char in name_input_buffer:
        test = current + char
        if font.size(test)[0] <= max_width:
            current = test
        else:
            wrapped.append(current)
            current = char

    if current:
        wrapped.append(current)

    name_input_lines = wrapped


def draw_name_input_overlay():
    global name_input_buffer, name_input_cursor, name_input_lines, name_input_scroll
    global line_index_map, cursor_visible, last_cursor_toggle
    line_index_map = []  # list of (start_index, end_index)

    # 1. BLUR THE BACKGROUND (cheap box-blur imitation)
    background = screen.copy()
    scale = 0.25
    small = pygame.transform.smoothscale(background, (int(W * scale), int(H * scale)))
    blur = pygame.transform.smoothscale(small, (W, H))
    screen.blit(blur, (0, 0))

    # 2. DARK TRANSLUCENT OVERLAY
    tint = pygame.Surface((W, H), pygame.SRCALPHA)
    tint.fill((0, 0, 0, 140))
    screen.blit(tint, (0, 0))

    # 3. CENTERED BOX
    box_w = int(W * 0.55)
    box_h = int(H * 0.55)
    box_x = (W - box_w) // 2
    box_y = (H - box_h) // 2

    # underlying translucent panel
    panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    panel.fill((20, 28, 40, 220))
    screen.blit(panel, (box_x, box_y))

    pygame.draw.rect(screen, (100, 120, 150), (box_x, box_y, box_w, box_h), 3, border_radius=14)

    # 4. TITLE
    title_font = pygame.font.SysFont("Arial", 30, bold=True)
    title_surf = title_font.render("Enter IUPAC Name", True, (240, 240, 255))
    screen.blit(title_surf, (box_x + 20, box_y + 18))

    # 5. TEXT INPUT AREA
    scrollbar_width = 16
    tx = box_x + 20
    ty = box_y + 70
    tw = box_w - 40  # Full width initially
    th = box_h - 150

    # Calculate if scrollbar is needed first
    font = pygame.font.SysFont("Arial", 22)
    # First compute with full width to check if scrollbar needed
    recompute_name_input_lines(box_w - 40)
    line_height = font.get_height() + 4
    visible_lines = th // line_height
    total_lines = len(name_input_lines)
    name_input_scrollbar_visible = total_lines > visible_lines
    
    # Adjust text width if scrollbar is visible
    if name_input_scrollbar_visible:
        tw = box_w - 40 - scrollbar_width  # Make space for scrollbar
        # Recompute lines with reduced width
        recompute_name_input_lines(tw)
        # Recalculate visible lines with new wrapping
        total_lines = len(name_input_lines)
        visible_lines = th // line_height
        name_input_scrollbar_visible = total_lines > visible_lines

    pygame.draw.rect(screen, (10, 18, 28), (tx - 5, ty - 5, tw + 10, th + 10), border_radius=10)
    pygame.draw.rect(screen, (80, 100, 130), (tx - 5, ty - 5, tw + 10, th + 10), 2, border_radius=10)

    # 6. Draw wrapped text with scrolling
    # Clamp scroll value
    max_scroll = max(0, total_lines - visible_lines)
    name_input_scroll = min(name_input_scroll, max_scroll)
    
    # Auto-scroll to keep cursor visible
    cursor_line = 0
    pos = 0
    for i, line in enumerate(name_input_lines):
        if pos <= name_input_cursor <= pos + len(line):
            cursor_line = i
            break
        pos += len(line)
    
    # Scroll to cursor if needed
    if cursor_line < name_input_scroll:
        name_input_scroll = cursor_line
    elif cursor_line >= name_input_scroll + visible_lines:
        name_input_scroll = cursor_line - visible_lines + 1
    
    # Re-clamp after auto-scroll
    name_input_scroll = min(name_input_scroll, max_scroll)
    
    cursor_x = cursor_y = None
    y = ty
    pos = 0
    
    # Draw visible lines only
    start_line = name_input_scroll
    end_line = min(start_line + visible_lines, total_lines)
    
    for line_idx in range(start_line, end_line):
        line = name_input_lines[line_idx]
        
        # Calculate actual position in buffer for this line
        actual_pos = 0
        for i in range(line_idx):
            actual_pos += len(name_input_lines[i])
        
        surf = font.render(line, True, (240, 240, 255))
        screen.blit(surf, (tx, y))
        
        if actual_pos <= name_input_cursor <= actual_pos + len(line):
            cx = tx + font.size(line[:name_input_cursor - actual_pos])[0]
            cy = y
            cursor_x, cursor_y = cx, cy
        
        y += line_height

    # Cursor with blinking
    if cursor_x is not None:
        # Blink cursor every 0.5 seconds
        current_time = time.time()
        if current_time - last_cursor_toggle >= 0.5:
            cursor_visible = not cursor_visible
            last_cursor_toggle = current_time
        
        if cursor_visible:
            pygame.draw.line(
                screen,
                (255, 255, 255),
                (cursor_x, cursor_y),
                (cursor_x, cursor_y + font.get_height()),
                2
            )
    
    # 7. Draw scrollbar if needed (draw on top of text)
    if name_input_scrollbar_visible:
        scrollbar_x = tx + tw + 6
        scrollbar_y = ty
        scrollbar_height = th
        
        # Draw scrollbar track (on top)
        pygame.draw.rect(screen, (40, 50, 70), 
                       (scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height), 
                       border_radius=8)
        pygame.draw.rect(screen, (80, 100, 130), 
                       (scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height), 1, 
                       border_radius=8)
        
        # Calculate scrollbar thumb size and position
        if total_lines > 0:
            thumb_height = max(20, int(scrollbar_height * visible_lines / total_lines))
            max_thumb_y = scrollbar_height - thumb_height
            thumb_y = int((name_input_scroll / max_scroll) * max_thumb_y) if max_scroll > 0 else 0
        else:
            thumb_height = scrollbar_height
            thumb_y = 0
        
        # Draw scrollbar thumb (on top)
        thumb_rect = pygame.Rect(scrollbar_x, scrollbar_y + thumb_y, scrollbar_width, thumb_height)
        pygame.draw.rect(screen, (100, 120, 150), thumb_rect, border_radius=6)
        pygame.draw.rect(screen, (140, 160, 190), thumb_rect, 1, border_radius=6)
        
        # Store scrollbar rect for mouse interaction
        global NAME_INPUT_SCROLLBAR_RECT
        NAME_INPUT_SCROLLBAR_RECT = thumb_rect

    global BUILD_BTN_RECT

    btn_w = 160
    btn_h = 45
    btn_x = box_x + (box_w - btn_w) // 2
    btn_y = box_y + box_h - btn_h - 20  # 20px above bottom edge

    BUILD_BTN_RECT = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    pygame.draw.rect(screen, (60, 110, 160), BUILD_BTN_RECT, border_radius=10)
    pygame.draw.rect(screen, (120, 160, 210), BUILD_BTN_RECT, 3, border_radius=10)

    btn_font = pygame.font.SysFont("Arial", 24, bold=True)
    btn_surf = btn_font.render("Build", True, (230, 240, 255))
    screen.blit(btn_surf, (
        btn_x + (btn_w - btn_surf.get_width()) // 2,
        btn_y + (btn_h - btn_surf.get_height()) // 2
    ))


def draw_help_overlay(screen, font, fade_alpha=220):
    WIDTH, _ = screen.get_size()

    # === CONFIG ===
    overlay_w = 500
    overlay_h = 500
    corner_radius = 16  # rounded corners
    shadow_offset = 6  # shadow distance
    shadow_alpha = 120  # shadow darkness
    glass_alpha = 170  # frosted-glass transparency

    # === Draw shadow ===
    shadow = pygame.Surface((overlay_w, overlay_h), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow,
        (0, 0, 0, shadow_alpha),
        (0, 0, overlay_w, overlay_h),
        border_radius=corner_radius
    )
    screen.blit(shadow, ((WIDTH - overlay_w) // 2 + shadow_offset,
                         100 + shadow_offset))

    # === Glass panel base ===
    overlay = pygame.Surface((overlay_w, overlay_h), pygame.SRCALPHA)
    pygame.draw.rect(
        overlay,
        (20, 20, 30, glass_alpha),  # slightly bluish transparent dark
        (0, 0, overlay_w, overlay_h),
        border_radius=corner_radius
    )

    # Position near top, centered
    x = (WIDTH - overlay_w) // 2
    y = 100

    # === Column content ===
    col1 = [
        ("=== Help / Controls ===", (110, 170, 255)),
        "",
        ("Left Click  - Add(E) / Delete(D)", None),
        ("Right Click - Bond(E) / Marquee(S)", None),
        ("Drag        - Move atom(S)", None),
        ("Scroll      - Zoom", None),
        "",
        ("Bond Types:", (255, 210, 110)),
        "1 - Single",
        "2 - Double",
        "3 - Triple",
        "",
        ("Modes:", (255, 210, 110)),
        "S - Select Mode",
        "E - Edit Mode",
        "D - Delete Mode",
    ]

    col2 = [
        ("Shortcuts:", (110, 255, 180)),
        "Ctrl+Z - Undo",
        "Ctrl+Y - Redo",
        "Ctrl+V - Paste (in build-from-name)",
        "Ctrl+S - Save As",
        "Ctrl+O - Open File",
        "C      - Clear Scene",
        "N      - Make from Name",
        "H      - Toggle Help",

        "",
        ("Tips:", (110, 255, 180)),
        "- Zoom in for precision",
        "- Select Mode moves groups",
        "- Use Undo often",
    ]

    # Column positions
    col1_x = 20
    col2_x = overlay_w // 2 + 20

    # Fade alpha applied to entire overlay (for animation)
    overlay.set_alpha(fade_alpha)

    # === Draw Column 1 ===
    ty = 20
    for item in col1:
        if isinstance(item, tuple):
            text, color = item
            color = color or (255, 255, 255)
        else:
            text, color = item, (255, 255, 255)

        txt = font.render(text, True, color)
        overlay.blit(txt, (col1_x, ty))
        ty += 28

    # === Draw Column 2 ===
    ty = 20
    for item in col2:
        if isinstance(item, tuple):
            text, color = item
            color = color or (255, 255, 255)
        else:
            text, color = item, (255, 255, 255)

        txt = font.render(text, True, color)
        overlay.blit(txt, (col2_x, ty))
        ty += 28

    # Final blit
    screen.blit(overlay, (x, y))


def start_build_from_name(name):
    global building_state, loading_alpha, loading_tick
    building_state = "loading"
    loading_alpha = 0
    loading_tick = 0
    thread = threading.Thread(target=threaded_build, args=(name,))
    thread.start()


def connected_subgraph(start_id):
    id_map = {a['id']: a for a in atoms}
    if start_id not in id_map:
        return set()
    start_elem = id_map[start_id]['element']
    visited = {start_id}
    stack = [start_id]
    while stack:
        cur = stack.pop()
        cur_elem = id_map[cur]['element']
        for bond in bonds:
            ida, idb = bond['a1'], bond['a2']
            if ida == cur:
                nb = idb
            elif idb == cur:
                nb = ida
            else:
                continue
            if nb in visited:
                continue
            nb_atom = id_map.get(nb)
            if nb_atom is None:
                continue
            nb_elem = nb_atom['element']
            if cur_elem == 'C' and nb_elem == 'C':
                continue
            visited.add(nb)
            if nb_elem == 'C' and start_elem != 'C':
                continue
            stack.append(nb)
    return visited

def compute_ui_rects():
    elems = VISIBLE_ELEMENTS
    btn_w = 60
    gap = 10
    x0 = CANVAS_W + 14

    start_y = MENU_HEIGHT + 50  # <-- shifted down
    label_y = start_y
    elems_y = label_y + 26

    el_rects = []
    x = x0
    y = elems_y

    for idx, el in enumerate(elems):

        # -------------------------------
        # LAZY WRAP LOGIC (fix):
        # wrap only if:
        #   1. this is NOT the last element
        #   2. the next element would overflow row-width
        # -------------------------------
        is_last = (idx == len(elems) - 1)

        # check if next element causes overflow
        next_would_overflow = False
        if not is_last:
            next_x = x + btn_w + gap  # where NEXT would go
            right_edge = CANVAS_W + PANEL_W - 14
            if next_x + btn_w > right_edge:
                next_would_overflow = True

        # draw current element at current x,y
        rect = pygame.Rect(x, y, btn_w, 34)
        el_rects.append((rect, el))

        # move x for next element
        x += btn_w + gap

        # do lazy wrap ONLY if needed
        if next_would_overflow:
            x = x0
            y += 44
    # after elements block
    y += 12
    pt_btn = pygame.Rect(x0, y + MENU_HEIGHT, PANEL_W - 28, 36)

    y += 50
    clr_rect = pygame.Rect(x0, y + MENU_HEIGHT, PANEL_W - 28, 36)

    return {
        'label_y': label_y,
        'elements': el_rects,
        'add_element': pt_btn,
        'clear': clr_rect
    }


FONT_BASE_SIZE = 20
FONT_CACHE = {}


def get_zoomed_font():
    size = max(8, int(FONT_BASE_SIZE * ZOOM))
    if size not in FONT_CACHE:
        FONT_CACHE[size] = pygame.font.SysFont("Arial", size)
    return FONT_CACHE[size]


NAME_BASE_SIZE = 20
NAME_FONT_CACHE = {}


def get_zoomed_name_font():
    # scale slower than atoms
    scaled = NAME_BASE_SIZE * (ZOOM ** 0.5)
    size = max(10, int(scaled))

    if size not in NAME_FONT_CACHE:
        NAME_FONT_CACHE[size] = pygame.font.SysFont("Arial", size, bold=True)

    return NAME_FONT_CACHE[size]


# ===== UNDO / REDO =====
UNDO_STACK = []
REDO_STACK = []
MAX_HISTORY = 40  # don't balloon RAM


def snapshot_state():
    return {
        "atoms": [a.copy() for a in atoms],
        "bonds": [b.copy() for b in bonds],
        "next_id": next_id,
        "tool_mode": TOOL_MODE,
        "selected_atoms": list(SELECTED_ATOMS),
        "selected_bonds": list(SELECTED_BONDS)
    }


def restore_state(state):
    global atoms, bonds, next_id, TOOL_MODE
    global CAMERA_X, CAMERA_Y, ZOOM
    global SELECTED_ATOMS, SELECTED_BONDS

    atoms = [a.copy() for a in state["atoms"]]
    bonds = [b.copy() for b in state["bonds"]]
    next_id = state["next_id"]
    TOOL_MODE = state["tool_mode"]

    SELECTED_ATOMS = set(state.get("selected_atoms", []))
    SELECTED_BONDS = set(state.get("selected_bonds", []))


def push_undo():
    # prevent spam duplicates
    current = snapshot_state()
    if UNDO_STACK and UNDO_STACK[-1] == current:
        return
    if len(UNDO_STACK) >= MAX_HISTORY:
        UNDO_STACK.pop(0)
    UNDO_STACK.append(current)
    REDO_STACK.clear()


def undo():
    if not UNDO_STACK:
        return
    state = UNDO_STACK.pop()
    REDO_STACK.append(snapshot_state())
    restore_state(state)


def redo():
    if not REDO_STACK:
        return
    state = REDO_STACK.pop()
    UNDO_STACK.append(snapshot_state())
    restore_state(state)


def load_scene():
    """Load atoms, bonds, and full app state from a JSON file."""
    global atoms, bonds, next_id, CAMERA_X, CAMERA_Y, ZOOM, TOOL_MODE, LAST_SAVE_PATH

    root = Tk()
    root.withdraw()
    filepath = filedialog.askopenfilename(
        filetypes=[("JSON Molecule", "*.json")]
    )
    restore_pygame_focus()

    if not filepath:
        return

    with open(filepath, "r") as f:
        data = json.load(f)

    atoms = data.get("atoms", [])
    bonds = data.get("bonds", [])
    next_id = data.get("next_id", 1)
    CAMERA_X = data.get("camera_x", 0)
    CAMERA_Y = data.get("camera_y", 0)
    ZOOM = data.get("zoom", 1.0)
    TOOL_MODE = data.get("tool_mode", "select")

    LAST_SAVE_PATH = filepath


def draw_menu_bar():
    global MENU_RECTS
    MENU_RECTS = {}
    pygame.draw.rect(screen, MENU_BG, (0, 0, W, MENU_HEIGHT))
    x = 8
    for name in MENU_ITEMS:
        surf = font_menu.render(name, True, MENU_TEXT)
        w = surf.get_width() + 24
        rect = pygame.Rect(x, 0, w, MENU_HEIGHT)

        mx, my = pygame.mouse.get_pos()
        if MENU_ACTIVE == name:
            bg = MENU_ACTIVE_BG
        elif rect.collidepoint(mx, my):
            bg = MENU_HOVER
        else:
            bg = MENU_BG

        pygame.draw.rect(screen, bg, rect)
        screen.blit(surf, (rect.x + (w - surf.get_width()) // 2, 7))

        MENU_RECTS[name] = rect
        x += w + 6

    # Draw dropdown if open
    if MENU_ACTIVE:
        draw_dropdown(MENU_ACTIVE)


def draw_dropdown(menu_name):
    global DROPDOWN_RECTS, MENU_HOVER_ITEM

    items = DROPDOWN_CONTENT[menu_name]
    DROPDOWN_RECTS = {}

    # compute width
    width = 200
    for label, shortcut in items:
        txt_w = font_menu.render(label, True, MENU_TEXT).get_width()
        if shortcut:
            txt_w += font_menu.render(shortcut, True, MENU_TEXT).get_width() + 40
        width = max(width, txt_w + 20)

    base_rect = MENU_RECTS[menu_name]
    x = base_rect.x
    y = base_rect.bottom + 2
    item_h = 26

    mx, my = pygame.mouse.get_pos()
    MENU_HOVER_ITEM = None

    for i, (label, shortcut) in enumerate(items):
        rect = pygame.Rect(x, y + i * item_h, width, item_h)

        # hover
        if rect.collidepoint(mx, my):
            pygame.draw.rect(screen, DROPDOWN_HOVER, rect)
            MENU_HOVER_ITEM = label
        else:
            pygame.draw.rect(screen, DROPDOWN_BG, rect)

        # label
        surf = font_menu.render(label, True, MENU_TEXT)
        screen.blit(surf, (rect.x + 8, rect.y + 5))

        # shortcut
        if shortcut:
            s = font_menu.render(shortcut, True, (200, 205, 220))
            screen.blit(s, (rect.right - s.get_width() - 10, rect.y + 5))

        DROPDOWN_RECTS[label] = rect


def draw_about_popup():
    global ABOUT_CLOSE_RECT
    if not ABOUT_OPEN:
        return

    w, h = 400, 220
    x = CANVAS_W // 2 - w // 2
    y = 120

    pygame.draw.rect(screen, (32, 36, 48), (x, y, w, h), border_radius=10)
    pygame.draw.rect(screen, (140, 150, 175), (x, y, w, h), 2, border_radius=10)

    title = font_menu.render("Carbon Simulator — About", True, (255, 255, 255))
    screen.blit(title, (x + 20, y + 18))

    body_font = pygame.font.SysFont("Segoe UI", 15)
    body = body_font.render("Created by Avyaya • 2025", True, (210, 210, 220))
    screen.blit(body, (x + 20, y + 70))

    # Close button
    close_surf = font_menu.render("Close", True, (255, 255, 255))
    close_rect = pygame.Rect(x + w // 2 - 40, y + h - 50, 80, 32)
    pygame.draw.rect(screen, (70, 80, 120), close_rect, border_radius=6)

    screen.blit(close_surf,
                (close_rect.x + (80 - close_surf.get_width()) // 2,
                 close_rect.y + 6))

    ABOUT_CLOSE_RECT = close_rect


def draw_ui():
    global UI_RECTS, name_input_buffer

    # Right panel background
    pygame.draw.rect(screen, (12, 18, 30), (CANVAS_W, 0, PANEL_W, H))

    # Title
    title_surf = BIG_FONT.render("Tools", True, (220, 230, 255))
    screen.blit(title_surf, (CANVAS_W + 14, MENU_HEIGHT + 12))

    # Compute UI rectangles (element buttons + clear button)
    rects = compute_ui_rects()
    # merge so left_toolbar (and other keys) are preserved
    UI_RECTS.update(rects)

    # Label: Select element
    small = FONT
    screen.blit(
        small.render("Select element:", True, (180, 200, 230)),
        (CANVAS_W + 14, rects['label_y'])
    )

    # Element buttons
    for rect, el in rects['elements']:
        col = (30, 40, 60) if el != selected_element else (26, 84, 150)
        pygame.draw.rect(screen, col, rect, border_radius=6)

        text = FONT.render(el, True, (230, 235, 240))
        screen.blit(text, (rect.x + rect.w // 2 - text.get_width() // 2, rect.y + 8))

        # valence number on right
        v = VALENCES.get(el, '?')
        vv = FONT.render(str(v), True, (180, 200, 230))
        screen.blit(vv, (rect.x + rect.w - 16, rect.y + 6))

    # --- Add Element Button ---
    pt_btn = rects['add_element']
    pygame.draw.rect(screen, (50, 70, 110), pt_btn, border_radius=8)
    txt = small.render("Add Element +", True, (240, 240, 255))
    screen.blit(txt, (pt_btn.x + (pt_btn.w - txt.get_width()) // 2,
                      pt_btn.y + (pt_btn.h - txt.get_height()) // 2))
    UI_RECTS['add_element'] = pt_btn

    # Clear button
    clr_rect = rects['clear']
    pygame.draw.rect(screen, (140, 44, 44), clr_rect, border_radius=8)
    txt = small.render("Clear canvas", True, (250, 240, 240))
    screen.blit(txt, (clr_rect.x + 10, clr_rect.y + (clr_rect.h - txt.get_height()) // 2))

    hint_text = "H - Help"
    surf = FONT.render(hint_text, True, (200, 210, 230))

    # bottom-left corner of right panel
    x = CANVAS_W + 14
    y = H - surf.get_height() - 14

    screen.blit(surf, (x, y))

    # underline ONLY the 'H'
    h_width = FONT.render("H", True, (200, 210, 230)).get_width()
    pygame.draw.line(
        screen,
        (200, 210, 230),
        (x, y + surf.get_height() - 4),
        (x + h_width, y + surf.get_height() - 4),
        2
    )


def restore_pygame_focus():
    """
    After opening a Tk file dialog, pygame can lose focus.
    This helper tries to force the pygame window to foreground (Windows),
    clears stale events, redraws, and pauses briefly so input returns.
    Call this immediately after any tkinter dialog (open/save/export).
    """
    try:
        # Try Windows API to set the window foreground ( the best effort).
        info = pygame.display.get_wm_info()
        hwnd = info.get('window') or info.get('wmwindow') or info.get('handle')
        if hwnd:
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
    except Exception:
        pass

    # Clear any stale events from tkinter and force a small redraw.
    try:
        pygame.event.clear()
        pygame.mouse.get_rel()
        pygame.display.flip()
        pygame.time.wait(80)
    except Exception:
        # Non-fatal: best-effort only.
        pass


# -----------------------------------------------
# CHUNK 3 — Menu Actions + Missing Utility Functions
# -----------------------------------------------

import pygame
import tkinter as tk
from tkinter import filedialog

# we use Tk only for file dialogs; do not create a full window
_root = tk.Tk()
_root.withdraw()

# Tracks whether About dialog is open
ABOUT_OPEN = False
ABOUT_RECT = None


# ==========================================================
#  FILE OPERATIONS
# ==========================================================

def menu_save():
    """Save the scene to the last-known file or ask Save As if unknown."""
    global LAST_SAVE_PATH
    if LAST_SAVE_PATH is None:
        menu_save_as()
        restore_pygame_focus()
        return
    save_scene_to(LAST_SAVE_PATH)


def menu_save_as():
    """Open a dialog and save scene to a chosen file."""
    global LAST_SAVE_PATH
    path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON Molecule", "*.json"), ("All Files", "*.*")]
    )
    restore_pygame_focus()
    if not path:
        return
    LAST_SAVE_PATH = path
    save_scene_to(path)


def save_scene_to(path):
    """Serialize atoms & bonds to a JSON file."""
    import json
    data = {
        "atoms": atoms,
        "bonds": bonds,
        "selected_element": selected_element,
        "zoom": ZOOM,
        "camera_x": CAMERA_X,
        "camera_y": CAMERA_Y
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[INFO] Saved file: {path}")


# ==========================================================
#  EDIT OPERATIONS
# ==========================================================

# For name popup cut/copy/paste:
CLIPBOARD_TEXT = ""


def menu_cut():
    """Cut text only if Name Input popup is active."""
    global name_input_buffer, CLIPBOARD_TEXT
    if not NAME_INPUT_OPEN:
        return
    CLIPBOARD_TEXT = name_input_buffer
    name_input_buffer = ""
    print("[INFO] Cut name input text.")


def menu_copy():
    """Copy text only inside the name input popup."""
    global CLIPBOARD_TEXT
    if not NAME_INPUT_OPEN:
        return
    CLIPBOARD_TEXT = name_input_buffer
    print("[INFO] Copied name input text.")


def menu_paste():
    """Paste text only inside the name input popup."""
    global name_input_buffer, CLIPBOARD_TEXT
    if not NAME_INPUT_OPEN:
        return
    name_input_buffer += CLIPBOARD_TEXT
    print("[INFO] Pasted name input text.")


def menu_select_all():
    """Select all atoms in the molecule."""
    SELECTED_ATOMS.clear()
    for a in atoms:
        SELECTED_ATOMS.add(a['id'])
    update_bond_selection_from_atoms()
    print("[INFO] Select All atoms.")


def menu_delete():
    """Delete selected atoms and connected bonds."""
    global atoms, bonds
    if not SELECTED_ATOMS:
        return
    # remove atoms
    atoms[:] = [a for a in atoms if a['id'] not in SELECTED_ATOMS]
    # remove bonds connected to any selected atom
    bonds[:] = [b for b in bonds
                if b['a1'] not in SELECTED_ATOMS and b['a2'] not in SELECTED_ATOMS]
    SELECTED_ATOMS.clear()
    SELECTED_BONDS.clear()
    print("[INFO] Deleted selected atoms.")


# ==========================================================
#  HELP → ABOUT POPUP
# ==========================================================

def open_about_popup():
    """Activate the About popup."""
    global ABOUT_OPEN, ABOUT_RECT
    ABOUT_OPEN = True

    w, h = 380, 220
    x = CANVAS_W // 2 - w // 2
    y = 120
    ABOUT_RECT = pygame.Rect(x, y, w, h)


def close_about_popup():
    """Close the popup."""
    global ABOUT_OPEN
    ABOUT_OPEN = False


# ==========================================================
#  MENU ACTION HANDLER
# ==========================================================

def handle_menu_action(menu, item):
    """
    Called when a dropdown item is clicked.
    menu = "File", "Edit", "View", "Help"
    item = label name ("Save", "Cut", "About", etc.)
    """
    global show_help, ZOOM, CAMERA_X, CAMERA_Y

    # -------- FILE --------
    if menu == "File":
        if item == "New":
            atoms.clear()
            bonds.clear()
            SELECTED_ATOMS.clear()
            SELECTED_BONDS.clear()
        elif item == "Open":
            load_scene()
        elif item == "Save":
            menu_save()
        elif item == "Save As":
            menu_save_as()

    # -------- EDIT --------
    elif menu == "Edit":
        if item == "Cut":
            menu_cut()
        elif item == "Copy":
            menu_copy()
        elif item == "Paste":
            menu_paste()
        elif item == "Select All":
            menu_select_all()
        elif item == "Delete":
            menu_delete()

    # -------- VIEW --------
    elif menu == "View":
        if item == "Reset Zoom":
            reload()
        elif item == "Center Molecule" and atoms:
            cx = sum(a['x'] for a in atoms) / len(atoms)
            cy = sum(a['y'] for a in atoms) / len(atoms)
            CAMERA_X = cx - CANVAS_W / (2 * ZOOM)
            CAMERA_Y = cy - H / (2 * ZOOM)

    # -------- HELP --------
    elif menu == "Help":
        if item == "About":
            open_about_popup()
        if item == "Help":
            show_help = not show_help


def draw_periodic_panel():
    if not PERIODIC_PANEL_OPEN:
        return

    panel_w = 400
    panel_h = 300

    # Center horizontally *over the canvas*, not including the right UI panel
    canvas_center_x = CANVAS_W // 2
    x = canvas_center_x - panel_w // 2

    # Slightly below menu bar
    y = MENU_HEIGHT + 40

    pygame.draw.rect(screen, (18, 24, 40), (x, y, panel_w, panel_h), border_radius=10)
    pygame.draw.rect(screen, (80, 90, 120), (x, y, panel_w, panel_h), 2, border_radius=10)

    cell_w = 40
    cell_h = 30
    margin = 10

    PERIODIC_PANEL_RECTS.clear()

    cx = x + margin
    cy = y + margin

    for i, el in enumerate(PERIODIC_ELEMENTS):
        rect = pygame.Rect(cx, cy, cell_w, cell_h)
        PERIODIC_PANEL_RECTS[el] = rect

        col = (40, 60, 90)
        pygame.draw.rect(screen, col, rect, border_radius=6)

        surf = FONT.render(el, True, (240, 240, 255))
        screen.blit(surf, (rect.x + (cell_w - surf.get_width()) // 2,
                           rect.y + (cell_h - surf.get_height()) // 2))

        cx += cell_w + 8
        if (i + 1) % 8 == 0:
            cx = x + margin
            cy += cell_h + 8


def toggle_selection(item_id, selected_set):
    """Toggle an item in a selection set (atom or bond)."""
    if item_id in selected_set:
        selected_set.remove(item_id)
    else:
        selected_set.add(item_id)


def update_bond_selection_from_atoms():
    """Auto-select bonds whose endpoints are both selected atoms."""
    SELECTED_BONDS.clear()
    for i, b in enumerate(bonds):
        if b["a1"] in SELECTED_ATOMS and b["a2"] in SELECTED_ATOMS:
            SELECTED_BONDS.add(i)


def name_worker():
    global display_name, compute_name_requested
    while True:
        if compute_name_requested:
            try:
                display_name = compute_name().lower()
            except Exception:
                display_name = ""
            compute_name_requested = False
        time.sleep(0.01)  # avoid busy loop


# Start thread once
threading.Thread(target=name_worker, daemon=True).start()


def draw_canvas():
    ATOM_SCALE = 0.75  # 75% size (tweak as needed)
    pygame.draw.rect(screen, (6, 12, 22), (0, 0, CANVAS_W, H))
    # -------------------------------
    # Draw Bonds (supports all types)
    # -------------------------------
    for bond in bonds:
        ida = bond['a1']
        idb = bond['a2']
        btype = bond.get('type', 'S')

        A = next((a for a in atoms if a['id'] == ida), None)
        B = next((a for a in atoms if a['id'] == idb), None)
        if not A or not B:
            continue

        # raw coords
        ax, ay = A['x'], A['y']
        bx, by = B['x'], B['y']

        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy)
        if d == 0:
            continue

        nx, ny = -dy / d, dx / d  # perpendicular normal

        # Apply camera + zoom
        def scr(x, y):
            return int((x - CAMERA_X) * ZOOM), int((y - CAMERA_Y) * ZOOM)

        # Colors & widths
        normal_color = (220, 235, 255)

        if btype in ("S", "D", "T"):
            order_num = BOND_ORDER_VALUE.get(btype, 1)
            spacing = 6

            line_width = 2

            for i in range(order_num):
                offset = (i - (order_num - 1) / 2) * spacing
                x1 = ax + nx * offset
                y1 = ay + ny * offset
                x2 = bx + nx * offset
                y2 = by + ny * offset
                X1, Y1 = scr(x1, y1)
                X2, Y2 = scr(x2, y2)
                pygame.draw.line(screen, normal_color, (X1, Y1), (X2, Y2), max(2, int(line_width * ZOOM)))
        # ----- ZOOM BUTTONS (Google Maps style) -----
    global UI_RECTS

    btn_w = 40
    btn_h = 40
    pad = 10

    zoom_x = CANVAS_W - btn_w - pad
    zoom_y_plus = pad + MENU_HEIGHT
    zoom_y_minus = pad + btn_h + 8 + MENU_HEIGHT

    # plus button
    rect_plus = pygame.Rect(zoom_x, zoom_y_plus, btn_w, btn_h)
    pygame.draw.rect(screen, (28, 40, 60), rect_plus, border_radius=8)
    ptxt = FONT.render("+", True, (240, 240, 255))
    screen.blit(ptxt, (rect_plus.centerx - ptxt.get_width() // 2,
                       rect_plus.centery - ptxt.get_height() // 2))

    # minus button
    rect_minus = pygame.Rect(zoom_x, zoom_y_minus, btn_w, btn_h)
    pygame.draw.rect(screen, (28, 40, 60), rect_minus, border_radius=8)
    mtxt = FONT.render("−", True, (240, 240, 255))
    screen.blit(mtxt, (rect_minus.centerx - mtxt.get_width() // 2,
                       rect_minus.centery - mtxt.get_height() // 2))

    # save to UI dict
    UI_RECTS["zoom_plus"] = rect_plus
    UI_RECTS["zoom_minus"] = rect_minus

    if MARQUEE_ACTIVE:
        x1, y1 = MARQUEE_START
        x2, y2 = MARQUEE_END
        rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

        # translucent box
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((100, 160, 255, 60))
        screen.blit(shade, rect.topleft)

        # border
        pygame.draw.rect(screen, (120, 180, 255), rect, 2)

    for idx in SELECTED_BONDS:
        if not (0 <= idx < len(bonds)):
            continue
        b = bonds[idx]

        A = next((a for a in atoms if a['id'] == b['a1']), None)
        B = next((a for a in atoms if a['id'] == b['a2']), None)
        if not A or not B:
            continue

        ax, ay = A['x'], A['y']
        bx, by = B['x'], B['y']
        dx = bx - ax
        dy = by - ay
        d = math.hypot(dx, dy)
        nx, ny = -dy / d, dx / d

        hl_color = (255, 240, 120)
        w = int(8 * ZOOM)

        # Straight types (S, D, T, bold)
        if b['type'] in ("S", "D", "T"):
            order = BOND_ORDER_VALUE.get(b['type'], 1)
            spacing = 6
            for i in range(order):
                off = (i - (order - 1) / 2) * spacing
                X1, Y1 = world_to_screen(ax + nx * off, ay + ny * off)
                X2, Y2 = world_to_screen(bx + nx * off, by + ny * off)
                pygame.draw.line(screen, hl_color, (X1, Y1), (X2, Y2), w)

    # --- Draw Atoms (single unified block) ---
    for a in atoms:
        el = a['element']
        base_r = RADIUS.get(el, 12)

        # scale down atoms (H stays normal if you want)
        if el == "H":
            sr = max(int(base_r * ZOOM), 2)
        else:
            sr = max(int(base_r * ZOOM * ATOM_SCALE), 2)

        # world → screen
        sx, sy = world_to_screen(a['x'], a['y'])

        # --- highlight ring (always bigger) ---
        if a['id'] in SELECTED_ATOMS:
            sel_r = sr + max(4, int(5 * ZOOM))
            pygame.draw.circle(screen, (255, 220, 130), (sx, sy), sel_r)

        # --- atom body ---
        col = COLORS.get(el, (200, 200, 200))
        pygame.draw.circle(screen, col, (sx, sy), sr)
        pygame.draw.circle(screen, (8, 14, 20), (sx, sy), max(sr - 2, 1))

        # --- draw element symbol (smaller font now) ---
        FONT_Z = pygame.font.SysFont("Arial", int(17 * ZOOM), bold=False)
        txt = FONT_Z.render(el, True, (230, 240, 255))
        screen.blit(txt, (sx - txt.get_width() // 2, sy - txt.get_height() // 2))

        # --- formal charge (scaled down) ---
        fc = a.get("formal_charge", 0)
        if fc != 0:
            sign = "+" if fc > 0 else ""
            charge_text = f"{sign}{fc}"

            charge_font = pygame.font.SysFont("Arial", max(10, int(12 * ZOOM * 0.7)), bold=True)
            c_surf = charge_font.render(charge_text, True, (230, 240, 255))

            draw_x = sx - c_surf.get_width() // 2
            draw_y = sy - sr - c_surf.get_height() - 2

            screen.blit(c_surf, (draw_x, draw_y))


def make_bond_icon(mode):
    """Return a 28x28 pygame.Surface icon for the given bond mode."""
    surf = pygame.Surface((28, 28), pygame.SRCALPHA)
    bond_color = (240, 240, 240)

    x1, y1 = 6, 22
    x2, y2 = 22, 6

    # Single / Double / Triple
    if mode == "S":
        pygame.draw.line(surf, bond_color, (x1, y1), (x2, y2), 3)

    elif mode == "D":
        pygame.draw.line(surf, bond_color, (x1, y1), (x2, y2), 3)
        pygame.draw.line(surf, bond_color, (x1 + 5, y1), (x2 + 5, y2), 3)

    elif mode == "T":
        pygame.draw.line(surf, bond_color, (x1, y1), (x2, y2), 3)
        pygame.draw.line(surf, bond_color, (x1 + 5, y1), (x2 + 5, y2), 3)
        pygame.draw.line(surf, bond_color, (x1 - 5, y1), (x2 - 5, y2), 3)

    else:
        # fallback: blank icon
        pass

    return surf


# Bond icons (use new factory)
ICON_SINGLE = make_bond_icon("S")
ICON_DOUBLE = make_bond_icon("D")
ICON_TRIPLE = make_bond_icon("T")

# default
CURRENT_BOND_ICON = ICON_SINGLE


def draw_bond_menu():
    global BOND_OPTION_RECTS
    if not BOND_MENU_OPEN:
        BOND_OPTION_RECTS = {}
        return

    x0 = UI_RECTS['bond_button'].right + 6
    y0 = UI_RECTS['bond_button'].top
    w = 40
    h = UI_RECTS['bond_button'].height

    # Row 1 (6 items): S, D, T, bold, wedge, dash
    row = [
        ("S", ICON_SINGLE),
        ("D", ICON_DOUBLE),
        ("T", ICON_TRIPLE)
    ]

    BOND_OPTION_RECTS = {}

    # Draw row1
    for i, (mode, icon) in enumerate(row):
        r = pygame.Rect(x0 + i * (w + 6), y0, w, h)
        pygame.draw.rect(screen, (28, 40, 60), r, border_radius=8)
        screen.blit(icon, (r.centerx - 14, r.centery - 14))
        BOND_OPTION_RECTS[mode] = r


# --- Draw bonds (NEW comprehensive renderer) ---
def _draw_bond_solid(ax, ay, bx, by, color, width):
    pygame.draw.line(screen, color, (ax, ay), (bx, by), int(max(1, width)))


def _draw_bond_multiple(ax, ay, bx, by, color, order_num, zoom):
    dx, dy = bx - ax, by - ay
    d = math.hypot(dx, dy) or 1
    nx, ny = -dy / d, dx / d
    spacing = 4 * zoom
    offsets = [0]
    if order_num == 2: offsets = [-spacing / 2, spacing / 2]
    if order_num == 3: offsets = [-spacing, 0, spacing]
    for off in offsets:
        x1 = ax + nx * off
        y1 = ay + ny * off
        x2 = bx + nx * off
        y2 = by + ny * off
        pygame.draw.line(screen, color, (x1, y1), (x2, y2), max(2, int(3 * ZOOM)))


def draw_bond_tooltip():
    if not BOND_MENU_OPEN:
        return

    mx, my = pygame.mouse.get_pos()

    if my < MENU_HEIGHT:
        return

    names = {
        "S": "Single bond",
        "D": "Double bond",
        "T": "Triple bond"
    }

    for mode, rect in BOND_OPTION_RECTS.items():
        if rect.collidepoint(mx, my):
            text = names.get(mode, mode)
            surf = FONT.render(text, True, (255, 255, 255))

            pad = 6
            box = surf.get_rect()
            box.x = mx + 12
            box.y = my + 12
            box.inflate_ip(pad * 2, pad * 2)

            pygame.draw.rect(screen, (20, 20, 30), box, border_radius=6)
            pygame.draw.rect(screen, (90, 100, 130), box, 2, border_radius=6)
            screen.blit(surf, (box.x + pad, box.y + pad))
            break


def draw_left_toolbar():
    """Left vertical toolbar with correct TOOL_MODE highlighting and icons."""
    global UI_RECTS, TOOL_MODE, ERASE_ICON, SELECT_ICON, BROOM_ICON

    btn_w, btn_h, pad = 44, 44, 8
    x = 10
    y = MENU_HEIGHT + 10  # shifted below menu bar

    # Toolbar button definitions
    items = [
        ("select", SELECT_ICON if SELECT_ICON else "S"),
        ("edit", "+"),
        ("delete", ERASE_ICON if ERASE_ICON else "D")
    ]

    left_rects = []

    # Draw the 3 main tool buttons
    for name, icon_or_char in items:

        rect = pygame.Rect(x, y, btn_w, btn_h)

        # -------------------------
        # CORRECT HIGHLIGHT LOGIC
        # -------------------------
        if TOOL_MODE == name:
            col = (28, 120, 180)  # active (blue)
        else:
            col = (40, 50, 70)  # inactive

        pygame.draw.rect(screen, col, rect, border_radius=8)

        # Draw icon
        if isinstance(icon_or_char, pygame.Surface):
            icon = icon_or_char
            screen.blit(icon, (
                rect.centerx - icon.get_width() // 2,
                rect.centery - icon.get_height() // 2
            ))
        else:
            icon_surf = FONT.render(icon_or_char, True, (240, 240, 240))
            screen.blit(icon_surf, (
                rect.centerx - icon_surf.get_width() // 2,
                rect.centery - icon_surf.get_height() // 2
            ))

        # Text label to the right
        label = FONT.render(name.capitalize(), True, (200, 220, 240))
        screen.blit(label, (rect.right + 8, rect.y + (btn_h - label.get_height()) // 2))

        left_rects.append((name, rect))
        y += btn_h + pad

    # -------------------------
    # Bond button (unchanged)
    # -------------------------
    bond_rect = pygame.Rect(x, y, btn_w, btn_h)
    pygame.draw.rect(screen, (40, 50, 70), bond_rect, border_radius=8)
    screen.blit(CURRENT_BOND_ICON, (bond_rect.centerx - 14, bond_rect.centery - 14))
    UI_RECTS['bond_button'] = bond_rect

    # -------------------------
    # Separator line
    # -------------------------
    LINE_COLOR = (90, 100, 130)
    LINE_THICKNESS = 2
    line_start_x = x + 8
    line_end_x = x + btn_w - 8
    line_y = y + btn_h + pad // 2
    pygame.draw.line(screen, LINE_COLOR, (line_start_x, line_y), (line_end_x, line_y), LINE_THICKNESS)

    y = line_y + pad

    # -------------------------
    # Clear-Up button (tiny icon)
    # -------------------------
    CLEAR_UP_RECT.x = x
    CLEAR_UP_RECT.y = y
    CLEAR_UP_RECT.w = btn_w
    CLEAR_UP_RECT.h = btn_h

    draw_rect = pygame.Rect(x, y, btn_w, btn_h)

    pygame.draw.rect(screen, (40, 50, 70), draw_rect, border_radius=8)

    if BROOM_ICON:
        icon = BROOM_ICON
        screen.blit(icon, (
            draw_rect.centerx - icon.get_width() // 2,
            draw_rect.centery - icon.get_height() // 2
        ))

    # Tooltip
    mouse_pos = pygame.mouse.get_pos()
    if draw_rect.collidepoint(mouse_pos):
        tip = "Clear-Up"
        surf = FONT.render(tip, True, (255, 255, 255))
        pad = 6
        box = surf.get_rect()
        box.x = mouse_pos[0] + 12
        box.y = mouse_pos[1] + 12
        box.inflate_ip(pad * 2, pad * 2)
        pygame.draw.rect(screen, (20, 20, 30), box, border_radius=6)
        pygame.draw.rect(screen, (90, 100, 130), box, 2, border_radius=6)
        screen.blit(surf, (box.x + pad, box.y + pad))

    UI_RECTS['left_toolbar'] = left_rects


def draw_fg_panel():
    if not fg_panel_active:
        return

    atom = next((a for a in atoms if a['id'] == fg_panel_carbon_id), None)
    if not atom:
        return

    # Convert atom position to screen space
    ax = (atom['x'] - CAMERA_X) * ZOOM
    ay = (atom['y'] - CAMERA_Y) * ZOOM

    # Panel world offset (30 right, 30 up) scaled to screen
    panel_w = int(130 * ZOOM)
    cx = ax + 30 * ZOOM
    cy = ay - 30 * ZOOM

    panel = pygame.Rect(cx, cy, panel_w, FG_PANEL_HEIGHT * ZOOM)

    # Draw panel
    pygame.draw.rect(screen, (18, 28, 40), panel, border_radius=8)
    pygame.draw.rect(screen, (80, 90, 110), panel, 2, border_radius=8)

    pad = int(8 * ZOOM)
    btn_w = panel_w - pad * 2

    global fg_panel_rects
    fg_panel_rects = []

    # Start y inside panel
    start_y = cy + pad - fg_scroll * ZOOM

    for i, name in enumerate(FG_OPTIONS):
        btn_rect = pygame.Rect(
            cx + pad,
            start_y + i * ((FG_BUTTON_HEIGHT + 4) * ZOOM),
            btn_w,
            FG_BUTTON_HEIGHT * ZOOM
        )

        # Only draw if visible
        if btn_rect.bottom >= cy and btn_rect.top <= cy + panel.height:
            pygame.draw.rect(screen, (40, 50, 70), btn_rect, border_radius=6)

            # Scaled font for FG panel (slightly smaller)
            base = FONT.get_height()
            scaled_size = max(10, int(base * ZOOM))
            fg_font = pygame.font.Font(None, scaled_size)

            t = fg_font.render(name, True, (220, 230, 240))
            screen.blit(t, (btn_rect.x + 6 * ZOOM, btn_rect.y + 5 * ZOOM))

        fg_panel_rects.append((name, btn_rect))


def allowed_valence(element, charge):
    base = VALENCES.get(element, 4)
    return base + charge


def total_bond_order(atom_id):
    return sum(
        BOND_ORDER_VALUE.get(bond['type'], 0)
        for bond in bonds
        if bond['a1'] == atom_id or bond['a2'] == atom_id
    )


def can_accept_more_bonds(atom_id, add_type="S"):
    add_type = BOND_NAME_TO_LETTER.get(add_type, add_type)
    atom = next((a for a in atoms if a["id"] == atom_id), None)
    if atom is None:
        return False

    charge = atom.get("formal_charge", 0)
    max_v = allowed_valence(atom["element"], charge)

    return total_bond_order(atom_id) + BOND_ORDER_VALUE.get(add_type, 0) <= max_v


def atom_free_valence(atom_id):
    a = next((x for x in atoms if x['id'] == atom_id), None)
    if not a:
        return 0

    used = sum(
        BOND_ORDER_VALUE.get(bond['type'], 0)
        for bond in bonds
        if bond['a1'] == atom_id or bond['a2'] == atom_id
    )

    charge = a.get("formal_charge", 0)
    max_v = allowed_valence(a['element'], charge)

    return max(0, max_v - used)


# update FG constructors -> bonds.append uses dicts now (example for several)
def attach_fg_ester(carbon):
    global next_id, atoms, bonds
    cid = carbon['id']
    if atom_free_valence(cid) < 3:
        return
    o1 = {'id': next_id, 'x': carbon['x'], 'y': carbon['y'] - 45, 'element': 'O', 'formal_charge': 0}
    next_id += 1

    bonds.append({"a1": cid, "a2": o1['id'], "type": "D"})
    o2 = {'id': next_id, 'x': carbon['x'] + 45, 'y': carbon['y'], 'element': 'O', 'formal_charge': 0}
    next_id += 1
    bonds.append({"a1": cid, "a2": o2['id'], "type": "S"})
    c2 = {'id': next_id, 'x': carbon['x'] + 90, 'y': carbon['y'], 'element': 'C', 'formal_charge': 0}
    next_id += 1
    bonds.append({"a1": o2['id'], "a2": c2['id'], "type": "S"})
    atoms.extend([o1, o2, c2])


def attach_fg_methyl(carbon):
    # CH3 : Carbon + 3 Hydrogens
    global atoms, bonds, next_id
    cx, cy = carbon['x'], carbon['y']
    neigh = [b['a2'] for b in bonds if b['a1'] == carbon['id']] + [b['a1'] for b in bonds if b['a2'] == carbon['id']]
    dx, dy = 0, -1
    if neigh:
        n_atom = next(a for a in atoms if a['id'] == neigh[0])
        dx, dy = carbon['x'] - n_atom['x'], carbon['y'] - n_atom['y']
        d = (dx * dx + dy * dy) ** 0.5 or 1
        dx /= d
        dy /= d
    mx = cx + dx * 60
    my = cy + dy * 60

    atoms.append({'id': next_id, 'x': mx, 'y': my, 'element': 'C', 'auto': False, 'formal_charge': 0})
    mid = next_id
    next_id += 1
    bonds.append({"a1": carbon['id'], "a2": mid, "type": "S"})
    for i in range(3):
        ang = i * (2 * math.pi / 3)
        hx = mx + math.cos(ang) * 28
        hy = my + math.sin(ang) * 28
        atoms.append({'id': next_id, 'x': hx, 'y': hy, 'element': 'H', 'auto': False, 'formal_charge': 0})
        bonds.append({"a1": mid, "a2": next_id, "type": "S"})
        next_id += 1


def attach_fg_ethyl(carbon):
    global atoms, bonds, next_id
    cx, cy = carbon['x'], carbon['y']
    neigh = [b['a2'] for b in bonds if b['a1'] == carbon['id']] + [b['a1'] for b in bonds if b['a2'] == carbon['id']]
    dx, dy = 0, -1
    if neigh:
        n_atom = next(a for a in atoms if a['id'] == neigh[0])
        dx, dy = carbon['x'] - n_atom['x'], carbon['y'] - n_atom['y']
        d = (dx * dx + dy * dy) ** 0.5 or 1
        dx /= d
        dy /= d

    # first carbon of ethyl
    c1x = cx + dx * 60
    c1y = cy + dy * 60

    atoms.append({'id': next_id, 'x': c1x, 'y': c1y, 'element': 'C', 'auto': False, 'formal_charge': 0})
    c1 = next_id
    next_id += 1
    bonds.append({"a1": carbon['id'], "a2": c1, "type": "S"})

    # second carbon
    c2x = c1x + dx * 60
    c2y = c1y + dy * 60
    atoms.append({'id': next_id, 'x': c2x, 'y': c2y, 'element': 'C', 'auto': False, 'formal_charge': 0})
    c2 = next_id
    next_id += 1
    bonds.append({"a1": c1, "a2": c2, "type": "S"})

    # hydrogens for c1 (2)
    for ang in [0, math.pi]:
        hx = c1x + math.cos(ang) * 28
        hy = c1y + math.sin(ang) * 28
        atoms.append({'id': next_id, 'x': hx, 'y': hy, 'element': 'H', 'auto': False, 'formal_charge': 0})
        bonds.append({"a1": c1, "a2": next_id, "type": "S"})
        next_id += 1

    # hydrogens for c2 (3)
    for i in range(3):
        ang = i * (2 * math.pi / 3)
        hx = c2x + math.cos(ang) * 28
        hy = c2y + math.sin(ang) * 28
        atoms.append({'id': next_id, 'x': hx, 'y': hy, 'element': 'H', 'auto': False, 'formal_charge': 0})
        bonds.append({"a1": c2, "a2": next_id, "type": "S"})
        next_id += 1


def attach_fg_hydroxy(carbon):
    global atoms, bonds, next_id
    cx, cy = carbon['x'], carbon['y']
    ox = cx
    oy = cy - 60

    atoms.append({'id': next_id, 'x': ox, 'y': oy, 'element': 'O', 'auto': False, 'formal_charge': 0})
    oid = next_id
    next_id += 1
    bonds.append({"a1": carbon['id'], "a2": oid, "type": "S"})

    hx = ox + 16
    hy = oy - 20
    atoms.append({'id': next_id, 'x': hx, 'y': hy, 'element': 'H', 'auto': False, 'formal_charge': 0})
    bonds.append({"a1": oid, "a2": next_id, "type": "S"})
    next_id += 1


def attach_fg_carboxyl(carbon):
    global atoms, bonds, next_id
    cx, cy = carbon['x'], carbon['y']

    # carbonyl carbon
    c2x = cx
    c2y = cy - 60

    atoms.append({'id': next_id, 'x': c2x, 'y': c2y, 'element': 'C', 'auto': False, 'formal_charge': 0})
    cid = next_id
    next_id += 1
    bonds.append({"a1": carbon['id'], "a2": cid, "type": "S"})

    # double-bonded O
    ox1 = c2x - 32
    oy1 = c2y - 28
    atoms.append({'id': next_id, 'x': ox1, 'y': oy1, 'element': 'O', 'auto': False, 'formal_charge': 0})
    oid1 = next_id
    next_id += 1
    bonds.append({"a1": cid, "a2": oid1, "type": "D"})

    # OH
    ox2 = c2x + 32
    oy2 = c2y - 28
    atoms.append({'id': next_id, 'x': ox2, 'y': oy2, 'element': 'O', 'auto': False, 'formal_charge': 0})
    oid2 = next_id
    next_id += 1
    bonds.append({"a1": cid, "a2": oid2, "type": "S"})

    hx = ox2 + 16
    hy = oy2 - 20
    atoms.append({'id': next_id, 'x': hx, 'y': hy, 'element': 'H', 'auto': False, 'formal_charge': 0})
    bonds.append({"a1": oid2, "a2": next_id, "type": "S"})
    next_id += 1


def attach_fg_aldehyde(carbon):
    global atoms, bonds, next_id
    cx, cy = carbon['x'], carbon['y']

    # carbonyl carbon
    c2x = cx
    c2y = cy - 60

    atoms.append({'id': next_id, 'x': c2x, 'y': c2y, 'element': 'C', 'auto': False, 'formal_charge': 0})
    cid = next_id
    next_id += 1
    bonds.append({"a1": carbon['id'], "a2": cid, "type": "S"})

    # double-bonded O
    ox1 = c2x
    oy1 = c2y - 32
    atoms.append({'id': next_id, 'x': ox1, 'y': oy1, 'element': 'O', 'auto': False, 'formal_charge': 0})
    oid1 = next_id
    next_id += 1
    bonds.append({"a1": cid, "a2": oid1, "type": "D"})

    # hydrogen on aldehyde carbon
    hx = c2x + 28
    hy = c2y
    atoms.append({'id': next_id, 'x': hx, 'y': hy, 'element': 'H', 'auto': False, 'formal_charge': 0})
    bonds.append({"a1": cid, "a2": next_id, "type": "S"})
    next_id += 1


def attach_fg_amino(carbon):
    if atom_free_valence(carbon['id']) < 1:
        return
    global next_id, atoms, bonds

    N = {'id': next_id, 'x': carbon['x'], 'y': carbon['y'] - 40, 'element': 'N', 'formal_charge': 0}
    next_id += 1
    H1 = {'id': next_id, 'x': carbon['x'] - 20, 'y': carbon['y'] - 60, 'element': 'H', 'formal_charge': 0}
    next_id += 1
    H2 = {'id': next_id, 'x': carbon['x'] + 20, 'y': carbon['y'] - 60, 'element': 'H', 'formal_charge': 0}
    next_id += 1

    atoms.extend([N, H1, H2])
    bonds.append({"a1": carbon['id'], "a2": N['id'], "type": "S"})
    bonds.append({"a1": N['id'], "a2": H1['id'], "type": "S"})
    bonds.append({"a1": N['id'], "a2": H2['id'], "type": "S"})


def attach_fg_nitro(carbon):
    if atom_free_valence(carbon['id']) < 1:
        return
    global next_id, atoms, bonds
    N = {'id': next_id, 'x': carbon['x'], 'y': carbon['y'] - 40, 'element': 'N', 'formal_charge': +1}
    next_id += 1
    O1 = {'id': next_id, 'x': carbon['x'] - 25, 'y': carbon['y'] - 70, 'element': 'O', 'formal_charge': 0}
    next_id += 1
    O2 = {'id': next_id, 'x': carbon['x'] + 25, 'y': carbon['y'] - 70, 'element': 'O', 'formal_charge': -1}
    next_id += 1

    atoms.extend([N, O1, O2])
    bonds.append({"a1": carbon['id'], "a2": N['id'], "type": "S"})
    bonds.append({"a1": N['id'], "a2": O1['id'], "type": "D"})  # N=O double
    bonds.append({"a1": N['id'], "a2": O2['id'], "type": "S"})  # N-O(-) single


def attach_fg_cyano(carbon):
    if atom_free_valence(carbon['id']) < 1:
        return
    global next_id, atoms, bonds
    C = {'id': next_id, 'x': carbon['x'], 'y': carbon['y'] - 40, 'element': 'C', 'formal_charge': 0}
    next_id += 1
    N = {'id': next_id, 'x': carbon['x'], 'y': carbon['y'] - 70, 'element': 'N', 'formal_charge': 0}
    next_id += 1

    atoms.extend([C, N])
    bonds.append({"a1": carbon['id'], "a2": C['id'], "type": "S"})
    bonds.append({"a1": C['id'], "a2": N['id'], "type": "D"})


def attach_fg_halogen(carbon, symbol):
    if atom_free_valence(carbon['id']) < 1:
        return
    global next_id, atoms, bonds
    X = {'id': next_id, 'x': carbon['x'], 'y': carbon['y'] - 40, 'element': symbol, 'formal_charge': 0}
    next_id += 1

    atoms.append(X)
    bonds.append({"a1": carbon['id'], "a2": X['id'], "type": "S"})


def is_valid_tetrahedral_center(atom_id):
    attached = []
    for b in bonds:
        if atom_id in (b['a1'], b['a2']):
            attached.append(b)

    # Must have exactly 4 single bonds
    if len(attached) != 4:
        return False

    # Must be carbon
    atom = get_atom(atom_id)
    if not atom or atom['element'] != 'C':
        return False

    # Must have 4 UNIQUE substituents
    neighbor_elements = []
    for b in attached:
        other = b['a2'] if b['a1'] == atom_id else b['a1']
        neighbor_elements.append(get_atom(other)['element'])

    return len(set(neighbor_elements)) == 4


def compute_sim_formula_and_mass():
    """Compute formula and approximate molar mass from simulator atoms only.
       Returns (formula_string, mass_float).
    """
    from rdkit import Chem
    # count atoms from your simulator (explicit atoms only)
    counts = {}
    for a in atoms:
        el = a.get("element", "")
        if not el:
            continue
        counts[el] = counts.get(el, 0) + 1

    # Build Hill-system-ish formula: C then H then sorted others
    pieces = []
    if counts.get("C", 0) > 0:
        n = counts["C"]
        pieces.append(f"C{n if n > 1 else ''}")
    if counts.get("H", 0) > 0:
        n = counts["H"]
        pieces.append(f"H{n if n > 1 else ''}")
    for el in sorted(counts.keys()):
        if el in ("C", "H"):
            continue
        n = counts[el]
        pieces.append(f"{el}{n if n > 1 else ''}")
    formula = "".join(pieces) if pieces else ""

    # mass from RDKit periodic table (good enough)
    mass = 0.0
    try:
        periodic = Chem.GetPeriodicTable()
        for el, n in counts.items():
            try:
                mass += periodic.GetAtomicWeight(el) * n
            except Exception:
                # unknown element fallback: ignore
                pass
    except Exception:
        mass = 0.0

    return formula, mass



def normalize_rdkit_coords(coords, scale=55.0):
    """Convert RDKit raw coords → world coords (scaled only)."""
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    centered = []
    for x, y in coords:
        cx = (x - (min_x + max_x) / 2) * scale
        cy = (y - (min_y + max_y) / 2) * scale
        centered.append((cx, cy))

    return centered


def center_molecule_world():
    global CAMERA_X, CAMERA_Y

    xs = [a["x"] for a in atoms]
    ys = [a["y"] for a in atoms]

    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2

    CAMERA_X = cx - CANVAS_W / 2
    CAMERA_Y = cy - H / 2


def build_from_name(name: str):
    global atoms, bonds, next_id, ZOOM
    atoms.clear()
    bonds.clear()
    next_id = 1

    try:
        # OPSIN lookup
        url = "https://opsin.ch.cam.ac.uk/opsin/" + urllib.parse.quote(name) + ".json"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            print("OPSIN failed:", r.text)
            return

        data = r.json()
        if "smiles" not in data:
            print("Unable to parse name:", name)
            return

        smiles = data["smiles"]

        # RDKit molecule
        mol = Chem.MolFromSmiles(smiles)
        mol = Chem.AddHs(mol)
        AllChem.Compute2DCoords(mol)

        conformer = mol.GetConformer()

        # -----------------------------
        # Extract RDKit coords
        # -----------------------------
        raw_coords = []
        for i in range(mol.GetNumAtoms()):
            pos = conformer.GetAtomPosition(i)
            raw_coords.append((pos.x, pos.y))

        # -----------------------------
        # Convert to WORLD coordinates
        # -----------------------------
        world_coords = normalize_rdkit_coords(raw_coords, scale=55.0)

        # -----------------------------
        # Simulator atoms (ONLY ONCE)
        # -----------------------------
        for idx, rdatom in enumerate(mol.GetAtoms()):
            x, y = world_coords[idx]

            atoms.append({
                "id": next_id,
                "x": x,
                "y": y,
                "element": rdatom.GetSymbol(),
                "auto": False,
                "formal_charge": rdatom.GetFormalCharge()
            })

            rdatom.SetIntProp("sim_id", next_id)
            next_id += 1

        # -----------------------------
        # Simulator bonds
        # -----------------------------
        for bond in mol.GetBonds():
            ida = bond.GetBeginAtom().GetIntProp("sim_id")
            idb = bond.GetEndAtom().GetIntProp("sim_id")

            # Bond type (S, D, T)
            bt = bond.GetBondType()
            order = "S"
            if bt == Chem.BondType.DOUBLE:
                order = "D"
            elif bt == Chem.BondType.TRIPLE:
                order = "T"

            bonds.append({
                "a1": ida,
                "a2": idb,
                "type": order
            })

        # -----------------------------
        # OPTIONAL: Aromatic correction
        # -----------------------------
        ri = mol.GetRingInfo()
        for ring in ri.AtomRings():
            if not all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in ring):
                continue

            n = len(ring)
            for i in range(n):
                a_idx = ring[i]
                b_idx = ring[(i + 1) % n]

                a_sim = mol.GetAtomWithIdx(a_idx).GetIntProp("sim_id")
                b_sim = mol.GetAtomWithIdx(b_idx).GetIntProp("sim_id")

                for bi, bd in enumerate(bonds):
                    if {bd["a1"], bd["a2"]} == {a_sim, b_sim}:
                        if bd["type"] == 1:
                            bd["type"] = 2
                        break

        # -----------------------------
        # Center + reset camera3,7-dihydro-1,3,7-trimethyl-1H-purine-2,6-dione
        # -----------------------------
        ZOOM = 1.0
        center_molecule_world()

    except Exception as e:
        print("OPSIN error:", e)


# Function to query CIR (similar to the one provided earlier)
import requests
from rdkit import Chem  # Assuming RDKit is imported globally


def nist_iupac_for(smiles):
    # ... (Your original nist_iupac_for function remains unchanged)
    if not smiles:
        return None
    try:
        encoded = urllib.parse.quote(smiles, safe="")
        url = f"https://webbook.nist.gov/cgi/cbook.cgi?SMILES={encoded}&Units=SI&Mask=1000"
        resp = requests.get(url, timeout=6)

        if resp.status_code == 200 and "IUPAC Name" in resp.text:
            start_tag = 'IUPAC Name:</label> '
            start_index = resp.text.find(start_tag)

            if start_index == -1: return None

            name_start = start_index + len(start_tag)
            name_end = resp.text.find('</p>', name_start)

            if name_end == -1:
                name_end = resp.text.find('<br>', name_start)

            if name_end != -1:
                iupac_name = resp.text[name_start:name_end].strip()
                iupac_name = iupac_name.replace('<b>', '').replace('</b>', '').replace('&nbsp;', ' ')
                return iupac_name if iupac_name else None

    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None
    return None


def compute_name():
    """
    Build RDKit molecule from simulator state and look up a human name.
    - Includes crucial RDKit property update for stable identifiers.
    """

    global GLOBAL_FORMULA, GLOBAL_MASS
    if not atoms:
        return "—"

    mol = Chem.RWMol()
    id_to_idx = {}
    for a in atoms:
        at = Chem.Atom(a['element'])
        idx = mol.AddAtom(at)
        id_to_idx[a['id']] = idx
        fc = int(a.get('formal_charge', 0) or 0)
        if fc != 0:
            mol.GetAtomWithIdx(idx).SetFormalCharge(fc)

    for bond in bonds:
        a_id = bond['a1']
        b_id = bond['a2']
        order = bond.get('type', 1)
        if a_id not in id_to_idx or b_id not in id_to_idx:
            continue
        bt = {'S': Chem.BondType.SINGLE, 'D': Chem.BondType.DOUBLE, 'T': Chem.BondType.TRIPLE}.get(order,
                                                                                                   Chem.BondType.SINGLE)
        try:
            mol.AddBond(id_to_idx[a_id], id_to_idx[b_id], bt)
        except Exception:
            continue

    # get RDKit Mol and produce a H-stripped copy for name lookups
    try:
        rdkit_mol = mol.GetMol()
        rdkit_mol.UpdatePropertyCache()

        # best-effort sanitize
        try:
            # OPTIONAL BUT RECOMMENDED: Use SANITIZE_ALL for best stability
            Chem.SanitizeMol(rdkit_mol, Chem.SanitizeFlags.SANITIZE_ALL)
        except Exception:
            pass
    except Exception:
        return "Invalid structure"

        # compute formula + mass using real molecule WITH hydrogens
    try:
        GLOBAL_FORMULA, GLOBAL_MASS = compute_sim_formula_and_mass()
    except Exception:
        GLOBAL_FORMULA = ""
        GLOBAL_MASS = 0.0

    # Make a version without explicit hydrogens for cleaner SMILES/InChI
    try:
        no_h = Chem.RemoveHs(rdkit_mol)
        try:
            # Recommended: Sanitize the stripped version too
            Chem.SanitizeMol(no_h, Chem.SanitizeFlags.SANITIZE_ALL)
        except Exception:
            pass
    except Exception:
        # if removing H fails, continue using the original
        no_h = rdkit_mol

    def mol_identifiers(m):
        try:
            smiles_iso = Chem.MolToSmiles(m, canonical=True, isomericSmiles=True)
        except Exception:
            smiles_iso = None
        try:
            smiles_plain = Chem.MolToSmiles(m, canonical=True, isomericSmiles=False)
        except Exception:
            smiles_plain = None
        try:
            inchi = Chem.MolToInchi(m)
        except Exception:
            inchi = None
        return smiles_iso, smiles_plain, inchi

    smiles_iso, smiles_plain, inchi = mol_identifiers(no_h)

    # common-name overrides (match canonical SMILES without explicit H)
    # NOTE: common_names definition must be accessible here.
    # noinspection SpellCheckingInspection
    common_names = {
        "c1ccoc1": "furan",
        "c1ccsc1": "thiophene",
        "c1cc[nH]c1": "pyrrole",
        "c1ccncc1": "pyridine",
        "c1ccc2ccccc2c1": "naphthalene",
        "c1ccc(cc1)c2ccccc2": "biphenyl",
    }

    if smiles_iso in common_names:
        return common_names[smiles_iso]
    if smiles_plain in common_names:
        return common_names[smiles_plain]

    def cactus_iupac_for(ident):
        if not ident:
            return None, None
        try:
            encoded = urllib.parse.quote(ident, safe="")
            url = f"https://cactus.nci.nih.gov/chemical/structure/{encoded}/iupac_name"
            resp = requests.get(url, timeout=6)
            return resp.status_code, resp.text.strip() if resp.status_code == 200 else None
        except requests.exceptions.RequestException:
            return None, None

    # try lookups: isomeric SMILES -> plain SMILES -> InChI via CACTUS
    for ident in (smiles_iso, smiles_plain, inchi):
        status, name = cactus_iupac_for(ident)
        if status == 200 and name:
            return name
        if status == 404:
            continue
        if status is None:
            return "Network error"

    # Fallback: try PubChem PUG REST which often has IUPAC names
    def pubchem_iupac_for(smiles):
        # ... (Your original pubchem_iupac_for remains unchanged)
        if not smiles:
            return None
        try:
            enc = urllib.parse.quote(smiles, safe="")
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{enc}/property/IUPACName/JSON"
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                obj = r.json()
                props = obj.get("PropertyTable", {}).get("Properties", [])
                if props:
                    return props[0].get("IUPACName")
        except requests.RequestException:
            return None
        except Exception:
            return None
        return None

    if not name:
        for ident in (smiles_iso, smiles_plain):
            name = pubchem_iupac_for(ident)
            if name:
                return name

        if not name:
            for ident in (smiles_iso, smiles_plain):
                name = nist_iupac_for(ident)
                if name:
                    return name

    # final fallback: InChIKey
    try:
        # Inchi must be the value generated earlier by mol_identifiers(no_h)
        inchikey = Chem.InchiToInchiKey(inchi)
        if inchikey and inchikey != "InChIKey=None":
            return f"Structure ID (InChIKey): {inchikey}"
    except:
        pass

    # absolute fallback: canonical SMILES
    return smiles_iso or smiles_plain or "Unknown"


# --- Main loop ---
def main():
    global next_id, selected_element, dragging_id, drag_offset, smart_join, dragging_group, drag_offsets
    global mouse_down_pos, mouse_down_time, last_click_time, auto_bond, threshold, bonds, UI_RECTS, atoms
    global name_input_buffer, fg_panel_active, fg_panel_carbon_id, fg_panel_rects
    global bond_creating, skip_next_mouseup_add, name_input_scroll, ABOUT_RECT
    global fg_scroll, compute_name_requested, last_name_compute_time, NAME_COMPUTE_INTERVAL
    global display_name, TOOL_MODE, delete_dragging, CURRENT_BOND_ICON, BOND_MENU_OPEN, BOND_MODE, BOND_OPTION_RECTS
    global CAMERA_X, CAMERA_Y, ZOOM, PAN_ACTIVE, GLOBAL_FORMULA, GLOBAL_MASS, MARQUEE_ACTIVE, MARQUEE_START, MARQUEE_END, SELECTED_ATOMS
    global NAME_INPUT_OPEN, name_input_buffer, name_input_cursor, JUST_OPENED_NAME_INPUT, CLEAR_UP_RECT, show_help
    global MENU_ACTIVE, MENU_RECTS, DROPDOWN_RECTS, PERIODIC_PANEL_OPEN, PERIODIC_PANEL_RECTS
    global LAST_SAVE_PATH

    try:
        skip_next_mouseup_add
    except NameError:
        skip_next_mouseup_add = False

    fg_panel_active = False
    fg_panel_carbon_id = None
    fg_panel_rects = []
    display_name = ""

    running = True
    while running:
        clock.tick(FPS)
        if app_state == "loading":
            continue

        screen.fill((0, 0, 0))
        draw_canvas()
        draw_left_toolbar()
        draw_bond_menu()
        draw_bond_tooltip()
        draw_ui()
        draw_periodic_panel()
        draw_fg_panel()
        draw_menu_bar()
        draw_about_popup()
        update_window_title()

        if TOOL_MODE == "select":
            fg_panel_active = False
            fg_panel_carbon_id = None
            fg_panel_rects = []
            BOND_MENU_OPEN = False
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        elif TOOL_MODE == "edit":
            SELECTED_ATOMS.clear()
            SELECTED_BONDS.clear()
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)
        elif TOOL_MODE == "delete":
            SELECTED_ATOMS.clear()
            SELECTED_BONDS.clear()
            fg_panel_active = False
            fg_panel_carbon_id = None
            fg_panel_rects = []
            BOND_MENU_OPEN = False
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_NO)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if NAME_INPUT_OPEN:
                if handle_name_input_event(event):
                    continue

            elif event.type == pygame.MOUSEWHEEL:
                # If name input is open, scroll the text box
                if NAME_INPUT_OPEN and name_input_scrollbar_visible:
                    name_input_scroll -= event.y * 1  # Scroll 1 line per wheel step
                    line_height = pygame.font.SysFont("Arial", 22).get_height() + 4
                    box_h = int(H * 0.55)
                    th = box_h - 150
                    visible_lines = th // line_height
                    max_scroll = max(0, len(name_input_lines) - visible_lines)
                    name_input_scroll = max(0, min(name_input_scroll, max_scroll))
                    continue

                # If FG panel is open, scroll that instead
                if fg_panel_active:
                    fg_scroll -= event.y * 20
                    max_scroll = max(0, len(FG_OPTIONS) * (FG_BUTTON_HEIGHT + 4) - FG_PANEL_HEIGHT)
                    fg_scroll = max(0, min(fg_scroll, max_scroll))
                    continue

                # ---- Canvas zooming ----
                old_zoom = ZOOM

                # you can tweak sensitivity here:
                zoom_factor = 1.12  # 12% per wheel step

                if event.y > 0:  # wheel up → zoom in
                    ZOOM *= zoom_factor
                elif event.y < 0:  # wheel down → zoom out
                    ZOOM /= zoom_factor

                # keep zoom sane
                ZOOM = max(0.15, min(ZOOM, 4.0))

                # ---- Keep zoom centered on the mouse ----
                mx, my = pygame.mouse.get_pos()

                # only zoom canvas area
                if mx < CANVAS_W:
                    # convert to world coords
                    wx_before = CAMERA_X + mx / old_zoom
                    wy_before = CAMERA_Y + my / old_zoom

                    wx_after = CAMERA_X + mx / ZOOM
                    wy_after = CAMERA_Y + my / ZOOM

                    CAMERA_X += wx_before - wx_after
                    CAMERA_Y += wy_before - wy_after


            # ---------- MOUSE DOWN ----------
            elif event.type == pygame.MOUSEBUTTONDOWN:
                push_undo()

                if event.button in (4, 5):
                    continue

                mx, my = event.pos
                button = getattr(event, 'button', 1)
                mx_world, my_world = screen_to_world(mx, my)
                clicked_atom = hit_atom_at((mx_world, my_world))
                # --- CTRL multi-select (runs before anything else) ---
                if TOOL_MODE == "select" and clicked_atom and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    aid = clicked_atom['id']
                    toggle_selection(aid, SELECTED_ATOMS)
                    update_bond_selection_from_atoms()
                    skip_next_mouseup_add = True
                    continue

                # --- Atom Selection with CTRL / normal click ---
                # --- Normal click atom selection + immediate drag setup ---
                if clicked_atom and TOOL_MODE == "select":
                    atom_id = clicked_atom['id']

                    # Normal click (NOT CTRL): replace selection
                    if atom_id not in SELECTED_ATOMS:
                        SELECTED_ATOMS.clear()
                        SELECTED_ATOMS.add(atom_id)
                        update_bond_selection_from_atoms()

                    # Begin drag on this selection
                    mouse_down_pos = (mx, my)
                    mouse_down_time = time.time()

                    mx_world, my_world = screen_to_world(mx, my)
                    dragging_group = SELECTED_ATOMS.copy()
                    drag_offsets = {}

                    for aid in dragging_group:
                        atom = next((z for z in atoms if z['id'] == aid), None)
                        if atom:
                            drag_offsets[aid] = (atom['x'] - mx_world, atom['y'] - my_world)

                    dragging_id = None
                    skip_next_mouseup_add = True
                    continue

                if my < MENU_HEIGHT:
                    for name, rect in MENU_RECTS.items():
                        if rect.collidepoint(mx, my):
                            # toggle
                            MENU_ACTIVE = name if MENU_ACTIVE != name else None
                            skip_next_mouseup_add = True
                    continue

                # --- DROPDOWN CLICK ---
                if MENU_ACTIVE and DROPDOWN_RECTS:
                    clicked_item = None
                    for label, rect in DROPDOWN_RECTS.items():
                        if rect.collidepoint(mx, my):
                            clicked_item = label
                            break

                    if clicked_item:
                        handle_menu_action(MENU_ACTIVE, clicked_item)
                        MENU_ACTIVE = None
                        skip_next_mouseup_add = True
                        continue

                    # clicked somewhere else -> close menu
                    MENU_ACTIVE = None

                # clicking outside closes menu
                MENU_ACTIVE = None

                # --- ABOUT POPUP CLICK ---
                if ABOUT_OPEN:
                    if ABOUT_CLOSE_RECT.collidepoint(event.pos):
                        close_about_popup()
                        continue
                    # clicking outside the popup closes it
                    if not ABOUT_RECT.collidepoint(event.pos):
                        close_about_popup()
                    continue

                # ---------- PERIODIC TABLE MUST BE CHECKED FIRST (GLOBAL OVERLAY!) ----------
                # If periodic panel is open, it intercepts ALL clicks anywhere on screen
                try:
                    # ------------------------------------------------------------
                    # PERIODIC TABLE CLICK (always handled before right-panel)
                    # ------------------------------------------------------------
                    if PERIODIC_PANEL_OPEN:
                        # IMPORTANT: NO push_undo() here – UI palette changes should NOT affect undo history
                        if button == 1:

                            clicked_el = None
                            for el, rect in PERIODIC_PANEL_RECTS.items():
                                if rect.collidepoint(mx, my):
                                    clicked_el = el
                                    break

                            if clicked_el:
                                # ------------------------------------
                                # Add new element ONLY to palette
                                # ------------------------------------
                                if clicked_el not in VISIBLE_ELEMENTS:
                                    VISIBLE_ELEMENTS.append(clicked_el)

                                # add defaults if missing
                                VALENCES.setdefault(clicked_el, 2)
                                COLORS.setdefault(clicked_el, (200, 200, 200))
                                RADIUS.setdefault(clicked_el, 22)

                                selected_element = clicked_el
                                TOOL_MODE = "edit"
                                PERIODIC_PANEL_OPEN = False

                                skip_next_mouseup_add = True
                                continue

                            else:
                                skip_next_mouseup_add = True
                                continue

                        else:
                            skip_next_mouseup_add = True
                            continue

                    # ------------------------------------------------------------
                    # RIGHT PANEL CLICKS
                    # ------------------------------------------------------------
                    if mx >= CANVAS_W:

                        rects = UI_RECTS or compute_ui_rects()
                        # ELEMENT PALETTE BUTTONS
                        handled = False
                        for rect, el in rects.get('elements', []):
                            if rect.collidepoint(mx, my):
                                selected_element = el
                                TOOL_MODE = "edit"
                                PERIODIC_PANEL_OPEN = False
                                skip_next_mouseup_add = True
                                handled = True
                                break

                        if handled:
                            continue

                        # ADD ELEMENT BUTTON
                        add_rect = rects.get('add_element')
                        if add_rect and add_rect.collidepoint(mx, my):
                            PERIODIC_PANEL_OPEN = not PERIODIC_PANEL_OPEN
                            skip_next_mouseup_add = True
                            continue

                        # CLEAR BUTTON
                        clr = rects.get('clear')
                        if clr and clr.collidepoint(mx, my):
                            atoms.clear()
                            bonds.clear()
                            next_id = 1
                            skip_next_mouseup_add = True
                            continue

                        # CLICKED IN PANEL BUT NOT ON ANY CONTROL
                        skip_next_mouseup_add = True
                        continue

                except Exception as e:
                    import traceback
                    print("[ERROR] click handling exception:", e)
                    traceback.print_exc()
                    skip_next_mouseup_add = True
                    continue

                # ---------- BLANK CANVAS CLICK BEHAVIOR ----------
                # Blank canvas click (not on atom, not on UI)
                # Handle clicking empty canvas
                if clicked_atom is None and mx < CANVAS_W:

                    # Only compute drag distance if we actually have a mouse_down_pos
                    small_drag = False
                    if mouse_down_pos is not None:
                        dx = mx - mouse_down_pos[0]
                        dy = my - mouse_down_pos[1]
                        small_drag = abs(dx) < DRAG_THRESHOLD and abs(dy) < DRAG_THRESHOLD

                    # Only clear selection on a real click (not drag) and no marquee
                    if small_drag and not MARQUEE_ACTIVE:
                        SELECTED_ATOMS.clear()
                        SELECTED_BONDS.clear()

                        # Close FG panel
                        fg_panel_active = False
                        fg_panel_carbon_id = None
                        fg_panel_rects = []

                        # Close bond submenu
                        BOND_MENU_OPEN = False

                    # Always stop marquee when releasing
                    MARQUEE_ACTIVE = False

                    skip_next_mouseup_add = True

                # start panning with middle button
                if button == PAN_BUTTON:
                    PAN_ACTIVE = True
                    # consume this click so it doesn't add atoms or open FG
                    skip_next_mouseup_add = True
                    continue

                elif TOOL_MODE == "select" and button == 3 and mx < CANVAS_W:
                    # start marquee
                    MARQUEE_ACTIVE = True
                    MARQUEE_START = (mx, my)
                    MARQUEE_END = (mx, my)

                    SELECTED_ATOMS.clear()
                    SELECTED_BONDS.clear()

                    dragging_id = None
                    dragging_group = set()
                    drag_offsets = {}
                    continue

                # zoom buttons
                if UI_RECTS.get("zoom_plus") and UI_RECTS["zoom_plus"].collidepoint(mx, my):
                    ZOOM *= 1.1
                    continue

                if UI_RECTS.get("zoom_minus") and UI_RECTS["zoom_minus"].collidepoint(mx, my):
                    ZOOM /= 1.1
                    continue
                # 1 left, 3 right

                # ---------------------------------------------------
                # 1) Left-toolbar mode buttons (select / edit / delete)
                # ---------------------------------------------------
                handled_mode_click = False
                for name, rect in UI_RECTS.get('left_toolbar', []):
                    if rect.collidepoint(mx, my):
                        TOOL_MODE = name

                        if TOOL_MODE == "delete":
                            # If user *already had* a selection, delete it instantly
                            if SELECTED_ATOMS:
                                # delete atoms
                                atoms[:] = [a for a in atoms if a['id'] not in SELECTED_ATOMS]

                                # delete bonds connected to those atoms
                                bonds[:] = [
                                    b for b in bonds
                                    if b['a1'] not in SELECTED_ATOMS and b['a2'] not in SELECTED_ATOMS
                                ]
                                SELECTED_ATOMS.clear()
                                SELECTED_BONDS.clear()
                        skip_next_mouseup_add = True
                        # cancel partial bond creation
                        bond_creating = None
                        SELECTED_ATOMS.clear()
                        SELECTED_BONDS.clear()
                        MARQUEE_ACTIVE = False
                        # cancel dragging
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}

                        # close bond menu when switching modes
                        BOND_MENU_OPEN = False

                        handled_mode_click = True

                        break

                if handled_mode_click:
                    continue

                # ---------------------------------------------------
                # 2) Bond button click (open/close horizontal submenu)
                # ---------------------------------------------------
                if UI_RECTS.get('bond_button') and UI_RECTS['bond_button'].collidepoint(mx, my):
                    if TOOL_MODE != "edit":
                        TOOL_MODE = "edit"
                    BOND_MENU_OPEN = not BOND_MENU_OPEN
                    skip_next_mouseup_add = True
                    continue

                # ---------------------------------------------------
                # 3) Bond submenu clicks (single/double/triple/auto)
                # ---------------------------------------------------
                if BOND_MENU_OPEN:
                    clicked_option = False
                    for mode, r in BOND_OPTION_RECTS.items():
                        if r.collidepoint(mx, my):
                            BOND_MODE = mode

                            # update icon mapping
                            if mode == "S":
                                CURRENT_BOND_ICON = ICON_SINGLE
                            elif mode == "D":
                                CURRENT_BOND_ICON = ICON_DOUBLE
                            elif mode == "T":
                                CURRENT_BOND_ICON = ICON_TRIPLE

                            BOND_MENU_OPEN = False
                            skip_next_mouseup_add = True
                            clicked_option = True
                            break

                    if clicked_option:
                        continue

                    # If user clicks outside menu + outside main button, close menu
                    if not UI_RECTS['bond_button'].collidepoint(mx, my):
                        outside = True
                        for r in BOND_OPTION_RECTS.values():
                            if r.collidepoint(mx, my):
                                outside = False
                                break
                        if outside:
                            BOND_MENU_OPEN = False
                    # continue normal behavior after closing

                # --------------------------
                # 1) Right-side UI clicks
                # --------------------------
                if mx >= CANVAS_W:
                    rects = UI_RECTS or compute_ui_rects()

                    # 1) Element buttons (switch to edit mode)
                    el_handled = False
                    for rect, el in rects.get('elements', []):
                        if rect.collidepoint(mx, my):
                            selected_element = el
                            TOOL_MODE = "edit"  # auto switch to edit
                            el_handled = True
                            PERIODIC_PANEL_OPEN = False  # close periodic panel if open
                            break
                    if el_handled:
                        skip_next_mouseup_add = True
                        continue  # consumed

                    # 2) Add Element (open periodic panel)
                    add_rect = rects.get('add_element')
                    if add_rect and add_rect.collidepoint(mx, my):
                        PERIODIC_PANEL_OPEN = not PERIODIC_PANEL_OPEN
                        skip_next_mouseup_add = True
                        continue

                    # 3) If the periodic panel is open, check its cells BEFORE other controls
                    if PERIODIC_PANEL_OPEN:
                        handled_periodic = False
                        for el, pr in PERIODIC_PANEL_RECTS.items():
                            if pr.collidepoint(mx, my):
                                # Insert into palette if missing
                                if el not in VALENCES:
                                    VALENCES[el] = 4
                                    COLORS[el] = COLORS.get(el, (200, 200, 200))
                                    RADIUS[el] = RADIUS.get(el, 12)
                                selected_element = el
                                TOOL_MODE = "edit"
                                PERIODIC_PANEL_OPEN = False
                                handled_periodic = True
                                break
                        # Click inside the right panel area when the periodic is open should be consumed
                        if handled_periodic or mx >= CANVAS_W and my >= MENU_HEIGHT:
                            skip_next_mouseup_add = True
                            continue

                    # 4) Clear button
                    if rects['clear'].collidepoint(mx, my):
                        atoms.clear()
                        bonds.clear()
                        next_id = 1
                        skip_next_mouseup_add = True
                        continue

                    # 5) Clicked panel but not on a control — consume it
                    skip_next_mouseup_add = True
                    continue

                # --------------------------
                # 2) FG PANEL CLICKS
                # --------------------------
                # only allow FG interactions in edit mode
                if fg_panel_active:
                    clicked_inside = False
                    for _, r in fg_panel_rects:
                        if r.collidepoint(mx, my):
                            clicked_inside = True
                            break
                    if not clicked_inside:
                        fg_panel_active = False
                        fg_panel_carbon_id = None

                if fg_panel_active and TOOL_MODE == "edit":
                    clicked_fg = False
                    for name, r in fg_panel_rects:
                        if r.collidepoint(mx, my):
                            clicked_fg = True
                            carbon = next((a for a in atoms if a['id'] == fg_panel_carbon_id), None)
                            if carbon:
                                if name == "methyl":
                                    attach_fg_methyl(carbon)
                                elif name == "ethyl":
                                    attach_fg_ethyl(carbon)
                                elif name == "hydroxy":
                                    attach_fg_hydroxy(carbon)
                                elif name == "carboxyl":
                                    attach_fg_carboxyl(carbon)
                                elif name == "aldehyde":
                                    attach_fg_aldehyde(carbon)
                                elif name == "amino":
                                    attach_fg_amino(carbon)
                                elif name == "nitro":
                                    attach_fg_nitro(carbon)
                                elif name == "cyano":
                                    attach_fg_cyano(carbon)
                                elif name == "fluoro":
                                    attach_fg_halogen(carbon, "F")
                                elif name == "chloro":
                                    attach_fg_halogen(carbon, "Cl")
                                elif name == "bromo":
                                    attach_fg_halogen(carbon, "Br")
                                elif name == "iodo":
                                    attach_fg_halogen(carbon, "I")
                                elif name == "ester":
                                    attach_fg_ester(carbon)

                            fg_panel_active = False
                            fg_panel_carbon_id = None
                            break
                    if clicked_fg:
                        skip_next_mouseup_add = True
                        continue
                    fg_panel_active = False

                # --------------------------
                # 3) Canvas click: left = drag/add (in edit), right = start bond-creation
                # --------------------------
                mouse_down_pos = (mx, my)
                mouse_down_time = time.time()

                a = hit_atom_at((mx, my))

                if button == 3:
                    # RIGHT BUTTON: allow bond creation only in edit mode
                    if TOOL_MODE != "edit":
                        bond_creating = None
                        continue
                    if TOOL_MODE == "select":
                        # start marquee
                        MARQUEE_ACTIVE = True
                        MARQUEE_START = (mx, my)
                        MARQUEE_END = (mx, my)
                        SELECTED_ATOMS.clear()
                        SELECTED_BONDS.clear()
                        dragging_group = set()
                        dragging_id = None
                        drag_offsets = {}
                        skip_next_mouseup_add = True
                        continue
                    if a:
                        bond_creating = a['id']
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}
                        skip_next_mouseup_add = True
                        continue
                    else:
                        bond_creating = None
                        continue

                # button == 1 (left click)
                if a:
                    if TOOL_MODE == "delete":
                        # delete atom immediately on press
                        if mx < CANVAS_W:
                            atoms[:] = [x for x in atoms if x['id'] != a['id']]
                            bonds[:] = [b for b in bonds
                                        if b['a1'] != a['id'] and b['a2'] != a['id']]

                        # prepare drag-delete
                        delete_dragging = True
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}
                        skip_next_mouseup_add = True

                    else:
                        # ==========================
                        # SELECT MODE (fixed ctrl toggle)
                        # ==========================
                        if TOOL_MODE == "select":
                            mx_world, my_world = screen_to_world(mx, my)
                            mods = pygame.key.get_mods()

                            if mods & pygame.KMOD_CTRL:
                                # CTRL → toggle
                                if a['id'] in SELECTED_ATOMS:
                                    SELECTED_ATOMS.remove(a['id'])
                                else:
                                    SELECTED_ATOMS.add(a['id'])
                            else:
                                # Normal click → single select
                                if (a['id'] not in SELECTED_ATOMS
                                        or len(SELECTED_ATOMS) > 1):
                                    SELECTED_ATOMS.clear()
                                    SELECTED_ATOMS.add(a['id'])

                            # update selected bonds AFTER selection change
                            update_bond_selection_from_atoms()

                            # --------------------------
                            # dragging selected atoms
                            # --------------------------
                            dragging_group = SELECTED_ATOMS.copy()
                            drag_offsets = {}

                            for aid in dragging_group:
                                atom = next((z for z in atoms if z['id'] == aid), None)
                                if atom:
                                    drag_offsets[aid] = (atom['x'] - mx_world,
                                                         atom['y'] - my_world)

                            dragging_id = None
                            skip_next_mouseup_add = True

                        else:
                            # OTHER MODES (normal behavior retained)
                            dragging_id = None
                            dragging_group = set()
                            drag_offsets = {}
                            skip_next_mouseup_add = False

                    # ==========================
                    # OPEN FG PANEL (unchanged)
                    # ==========================
                    if TOOL_MODE == "edit" and a['element'] == 'C' and atom_free_valence(a['id']) > 0:
                        fg_panel_active = True
                        fg_panel_carbon_id = a['id']
                    else:
                        fg_panel_active = False
                        fg_panel_carbon_id = None

                else:
                    # ==========================
                    # CLICKED ON EMPTY CANVAS
                    # ==========================
                    if TOOL_MODE == "delete" and mx < CANVAS_W:

                        # allow immediate bond deletion if clicked directly on a bond
                        bond_hit = hit_bond_at((mx, my), threshold=8)
                        if bond_hit:
                            bi, _ = bond_hit
                            bonds.pop(bi)
                            skip_next_mouseup_add = True

                        # start delete-drag mode (delete bonds while dragging)
                        delete_dragging = True
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}

                    else:
                        # seed empty behavior unchanged
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}
                        skip_next_mouseup_add = False


            # ---------- MOUSE MOTION ----------
            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                wx = mx / ZOOM + CAMERA_X
                wy = my / ZOOM + CAMERA_Y
                # delete-on-drag behavior
                for name, rect in MENU_RECTS.items():
                    if rect.collidepoint(mx, my):
                        break

                if delete_dragging and TOOL_MODE == "delete" and mx < CANVAS_W and (
                        event.buttons[0] == 1 or event.buttons[0] is None):
                    # prioritized atom deletion
                    hit_a = hit_atom_at((mx, my))
                    if hit_a:
                        aid = hit_a['id']
                        atoms[:] = [x for x in atoms if x['id'] != aid]
                        bonds[:] = [b for b in bonds if b['a1'] != aid and b['a2'] != aid]
                    else:
                        hb = hit_bond_at((mx, my), threshold=8)
                        if hb:
                            bi, _ = hb
                            # pop if still exists
                            if 0 <= bi < len(bonds):
                                bonds.pop(bi)
                    continue

                if MARQUEE_ACTIVE:
                    MARQUEE_END = (mx, my)

                    x1, y1 = MARQUEE_START
                    x2, y2 = MARQUEE_END
                    left = min(x1, x2)
                    top = min(y1, y2)
                    right = max(x1, x2)
                    bottom = max(y1, y2)

                    SELECTED_ATOMS.clear()
                    SELECTED_BONDS.clear()

                    # atoms: test screen-pos against marquee rect
                    for a in atoms:
                        sx, sy = world_to_screen(a['x'], a['y'])
                        if left <= sx <= right and top <= sy <= bottom:
                            SELECTED_ATOMS.add(a['id'])

                    # bonds: highlight only if both atom ids are selected
                    for i, b in enumerate(bonds):
                        if b['a1'] in SELECTED_ATOMS and b['a2'] in SELECTED_ATOMS:
                            SELECTED_BONDS.add(i)

                    continue

                # if panning, use event.rel to update camera offset (use ZOOM to get consistent speed)
                if PAN_ACTIVE:
                    dx, dy = event.rel  # pixels moved on screen
                    CAMERA_X -= dx / ZOOM
                    CAMERA_Y -= dy / ZOOM
                    continue

                if event.buttons[1] and TOOL_MODE == "select":  # middle mouse held
                    CAMERA_X -= event.rel[0] / ZOOM
                    CAMERA_Y -= event.rel[1] / ZOOM

                if dragging_group and TOOL_MODE == "select":
                    for aid in dragging_group:
                        atom = next((z for z in atoms if z['id'] == aid), None)
                        if atom:
                            offx, offy = drag_offsets.get(aid, (0, 0))
                            atom['x'] = wx + offx
                            atom['y'] = wy + offy

            # ---------- MOUSE UP ----------
            elif event.type == pygame.MOUSEBUTTONUP:
                push_undo()
                mx, my = event.pos
                button = getattr(event, 'button', 1)

                was_drag = False
                if mouse_down_pos:
                    dx = mx - mouse_down_pos[0]
                    dy = my - mouse_down_pos[1]
                    if abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD:
                        was_drag = True

                now = time.time()
                if button == PAN_BUTTON:
                    PAN_ACTIVE = False
                    continue

                if MARQUEE_ACTIVE:
                    MARQUEE_ACTIVE = False

                    continue

                    # --- CLEAR UP BUTTON CLICK ---
                if CLEAR_UP_RECT.collidepoint(mx, my) and event.button == 1:
                    clear_up_molecule()  # <--- CALL THE NEW FUNCTION
                    global compute_name_requested
                    compute_name_requested = True
                    continue  # Important to consume the click
                if button == 3:

                    start_id = bond_creating
                    bond_creating = None  # ALWAYS RESET IMMEDIATELY

                    if start_id is None or TOOL_MODE != "edit":
                        continue

                    target = hit_atom_at((mx, my))
                    if not target:
                        continue

                    end_id = target['id']
                    if end_id == start_id:
                        continue

                    # Check if the bond already exists
                    pair = {start_id, end_id}
                    existing_index = None
                    for i, b in enumerate(bonds):
                        if {b['a1'], b['a2']} == pair:
                            existing_index = i
                            break

                    # =================================================
                    #      NON-AUTO MODE: Create bond with chosen order
                    # =================================================
                    if existing_index is None:
                        order = BOND_MODE

                        if can_accept_more_bonds(start_id, order) and \
                                can_accept_more_bonds(end_id, order):
                            bonds.append({"a1": start_id, "a2": end_id, "type": order})

                    continue

                # Left-button normal click / drag end
                if button == 1:
                    # stop delete-drag on mouse up
                    if delete_dragging:
                        delete_dragging = False
                        skip_next_mouseup_add = False
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}
                        # prevent adding on the same up event
                        mouse_down_pos = None
                        continue

                    # if FG consumed the down/click, prevent adding
                    if skip_next_mouseup_add:
                        skip_next_mouseup_add = False
                        dragging_id = None
                        dragging_group = set()
                        drag_offsets = {}
                        mouse_down_pos = None
                        continue

                    if not was_drag:
                        a = hit_atom_at((mx, my))
                        # Delete mode: single click deletes
                        if TOOL_MODE == "delete":
                            if a:
                                atoms[:] = [x for x in atoms if x['id'] != a['id']]
                                bonds[:] = [b for b in bonds if b['a1'] != a['id'] and b['a2'] != a['id']]
                            # no adding in delete
                        elif a:
                            # Do nothing on double-click here — deletion happens only in delete mode.
                            # Selection / other behaviors are already handled on mouse down.
                            pass
                        else:
                            wx = mx / ZOOM + CAMERA_X
                            wy = my / ZOOM + CAMERA_Y
                            # add only in edit mode and if click inside canvas
                            if TOOL_MODE == "edit" and mx < CANVAS_W:
                                atoms.append({
                                    'id': next_id,
                                    'x': wx,
                                    'y': wy,
                                    'element': selected_element,
                                    'auto': False,
                                    'formal_charge': 0
                                })
                                next_id += 1
                        last_click_time = now

                    # clear drag state
                    dragging_id = None
                    dragging_group = set()
                    drag_offsets = {}
                    mouse_down_pos = None

            # ---------- KEYBOARD ----------
            elif event.type == pygame.KEYDOWN:
                if not (pygame.key.get_mods() & pygame.KMOD_CTRL and event.key in (pygame.K_z, pygame.K_y)):
                    push_undo()
                # normal shortcuts when not typing
                if event.key == pygame.K_c:
                    atoms.clear()
                    bonds.clear()
                if event.key == pygame.K_h:  # press H to toggle help
                    show_help = not show_help
                if event.key == pygame.K_1:
                    BOND_MODE = "S"
                    CURRENT_BOND_ICON = ICON_SINGLE
                elif event.key == pygame.K_2:
                    BOND_MODE = "D"
                    CURRENT_BOND_ICON = ICON_DOUBLE
                elif event.key == pygame.K_3:
                    BOND_MODE = "T"
                    CURRENT_BOND_ICON = ICON_TRIPLE
                elif event.key == pygame.K_a and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    menu_select_all()
                elif event.key == pygame.K_n and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    atoms.clear()
                    bonds.clear()
                    SELECTED_ATOMS.clear()
                    SELECTED_BONDS.clear()
                    LAST_SAVE_PATH = None
                elif event.key == pygame.K_r and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    reload()
                elif event.key == pygame.K_n:
                    NAME_INPUT_OPEN = True
                    name_input_buffer = ""
                    name_input_cursor = 0
                    pygame.key.start_text_input()
                    JUST_OPENED_NAME_INPUT = True
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_SHIFT and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    menu_save_as()
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    menu_save()
                elif event.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    load_scene()
                elif event.key == pygame.K_DELETE:
                    menu_delete()
                elif event.key == pygame.K_s:
                    TOOL_MODE = "select"
                elif event.key == pygame.K_e:
                    TOOL_MODE = "edit"
                elif event.key == pygame.K_d:
                    if TOOL_MODE == "select":
                        menu_delete()  # Delete selected atoms when in Select Mode
                    else:
                        TOOL_MODE = "delete"  # Switch to Delete Mode
                elif event.key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    if UNDO_STACK:
                        REDO_STACK.append(snapshot_state())
                        restore_state(UNDO_STACK.pop())

                elif event.key == pygame.K_y and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    if REDO_STACK:
                        UNDO_STACK.append(snapshot_state())
                        restore_state(REDO_STACK.pop())

        # compute name and render above bounding box
        now = time.time()
        if atoms and now - last_name_compute_time >= NAME_COMPUTE_INTERVAL:
            compute_name_requested = True
            last_name_compute_time = now

        # draw floating name+formula box above molecule (screen coords)
        if atoms and display_name:
            # compute world center and top Y of molecules
            center_x = sum(a['x'] for a in atoms) / len(atoms)
            min_y = min(a['y'] for a in atoms)

            # convert to screen coordinates
            sx = int((center_x - CAMERA_X) * ZOOM)
            sy = int((min_y - CAMERA_Y) * ZOOM)

            base_name_px = 20
            base_info_px = 14

            # name_scale: maps ZOOM=1 -> 1.0, higher -> slower growth
            name_scale = 1.0 + (ZOOM - 1.0) * 0.45
            info_scale = 1.0 + (ZOOM - 1.0) * 0.30

            name_font = pygame.font.SysFont("Arial", max(10, int(base_name_px * name_scale)), bold=True)
            info_font = pygame.font.SysFont("Arial", max(8, int(base_info_px * info_scale)))
            # render lines
            name_surf = name_font.render(display_name, True, (230, 240, 255))
            formula_text = GLOBAL_FORMULA or ""
            mass_text = f"{GLOBAL_MASS:.4f} g/mol" if GLOBAL_MASS else ""
            formula_surf = info_font.render(formula_text, True, (200, 220, 255))
            mass_surf = info_font.render(mass_text, True, (200, 220, 255))

            # box layout: name on first line, formula second, mass third (all inside)
            padding_x = 10
            padding_y = 8
            width = max(name_surf.get_width(), formula_surf.get_width(), mass_surf.get_width()) + padding_x * 2
            height = name_surf.get_height() + formula_surf.get_height() + mass_surf.get_height() + padding_y * 3

            # box center above molecule; offset upward so it doesn't overlap atoms
            molecule_height = max(a['y'] for a in atoms) - min_y
            offset = int(max(60, molecule_height * 0.6) * ZOOM)  # <= minimum 60px
            box_center = (sx, sy - offset)
            # adjust -40*ZOOM as needed
            box_rect = pygame.Rect(0, 0, width, height)
            box_rect.center = box_center

            # clamp box inside canvas boundaries a bit
            box_rect.x = max(6, min(box_rect.x, CANVAS_W - box_rect.w - 6))
            box_rect.y = max(6, min(box_rect.y, H - box_rect.h - 6))

            # draw box (slightly translucent background)
            bg_surf = pygame.Surface((box_rect.w, box_rect.h), pygame.SRCALPHA)
            bg_surf.fill((6, 10, 18, 220))  # dark translucent
            screen.blit(bg_surf, (box_rect.x, box_rect.y))

            # border
            pygame.draw.rect(screen, (40, 50, 74), box_rect, 2, border_radius=8)

            # blit text lines inside box
            cursor_y = box_rect.y + padding_y
            screen.blit(name_surf, (box_rect.x + (box_rect.w - name_surf.get_width()) // 2, cursor_y))
            cursor_y += name_surf.get_height() + padding_y // 2
            screen.blit(formula_surf, (box_rect.x + (box_rect.w - formula_surf.get_width()) // 2, cursor_y))
            cursor_y += formula_surf.get_height() + padding_y // 2
            screen.blit(mass_surf, (box_rect.x + (box_rect.w - mass_surf.get_width()) // 2, cursor_y))

        if NAME_INPUT_OPEN:
            draw_name_input_overlay()
        if show_help:
            draw_help_overlay(screen, FONT, fade_alpha=220)
        pygame.display.flip()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    # prepare UI in background then show loading and start main loop
    threading.Thread(target=prepare_ui, daemon=True).start()
    show_loading_until_ready()
    main()
