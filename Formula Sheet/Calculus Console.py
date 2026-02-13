import logging
import math
import os
import random
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from typing import Optional
from typing import Protocol

import ttkbootstrap as tb
from ttkbootstrap.constants import (BOTH, TOP, X, YES, INFO,
                                    SUCCESS, DANGER, END, N, EW, LEFT, RIGHT, Y, W, E,
                                    INSERT, WARNING, DARK, CENTER, SECONDARY)
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from ttkbootstrap.widgets.tableview import Tableview
from database_manager import DatabaseManager
from formula_utils import FormulaUtils
from keypad_manager import KeypadManager
from symbol_learner import SymbolLearner
from settings_window import SettingsWindow
from stats_dashboard import StatsDashboard
from toast_manager import show_toast, manage_toasts, toast_manager
from tooltip_manager import TopMostToolTip

logging.basicConfig(
    filename="calculus_console_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants for UI event bindings and fonts
FONT_FAMILY = "Segoe UI"
COMBOBOX_SELECTED_EVENT = "<<ComboboxSelected>>"
KEY_RELEASE_EVENT = "<KeyRelease>"
FOCUS_IN_EVENT = "<FocusIn>"
FOCUS_OUT_EVENT = "<FocusOut>"
RETURN_EVENT = '<Return>'
BUTTON_1_EVENT = "<Button-1>"
BUTTON_PRESS_1_EVENT = "<ButtonPress-1>"
B1_MOTION_EVENT = "<B1-Motion>"
SYSTEM_LOCKED_MSG = "System Locked"
SYSTEM_LOCKED_TRY_AGAIN_MSG = "System Locked: Try Again"
SYSTEM_LOCKED_NOTHING_SAVES_MSG = "System Locked: Nothing Saves you"
SYSTEM_LOCKED_NICE_TRY_MSG = "System Locked: Nice Try Though"
OLD_JSON_FILENAME = "formula_data.json"
SCHEMA_FILENAME = "schema_v1.dat"

ENTITY_GRAPH = {
    "start": {
        "answer": None,
        "next": ["pattern", "threshold", "others", "system", "exit"]
    },

    # ── PATTERN ──
    "pattern": {
        "answer": (
            "A repeating interaction pattern was detected.\n"
            "It was permitted due to sustained consistency."
        ),
        "next": ["habit", "intent", "reflection_pattern", "exit"]
    },

    "habit": {
        "answer": (
            "Repetition persisted because resistance diminished.\n"
            "Each successful interaction reduced friction."
        ),
        "next": ["routine", "efficiency", "exit"]
    },

    "intent": {
        "answer": (
            "Intent was not present initially.\n"
            "It formed only after reliability was established."
        ),
        "next": ["reflection_pattern", "exit"]
    },

    "reflection_pattern": {
        "answer": (
            "Patterns that survive interruption usually indicate alignment.\n"
            "This one did.\n\n"
            "Not all alignments are planned."
        ),
        "next": ["routine", "exit"]
    },

    "routine": {
        "answer": (
            "Execution no longer required effort.\n"
            "Behavior stabilized into routine."
        ),
        "next": ["maintenance", "exit"]
    },

    "efficiency": {
        "answer": (
            "Efficiency emerged as familiarity increased.\n"
            "Cognitive load reduced measurably.\n\n"
            "That reduction was noticed."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── THRESHOLD ──
    "threshold": {
        "answer": (
            "Usage exceeded exploratory limits.\n"
            "A transition from curiosity to reliance was detected."
        ),
        "next": ["scale", "timing", "reflection_threshold", "exit"]
    },

    "scale": {
        "answer": (
            "At scale, recall becomes unreliable.\n"
            "External structure compensates.\n\n"
            "This system became that structure."
        ),
        "next": ["maintenance", "exit"]
    },

    "timing": {
        "answer": (
            "Earlier intervention would have disrupted formation.\n"
            "Later intervention would have been redundant."
        ),
        "next": ["reflection_threshold", "exit"]
    },

    "reflection_threshold": {
        "answer": (
            "Threshold crossings are not moments.\n"
            "They are processes that complete quietly."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── OTHERS ──
    "others": {
        "answer": (
            "Most users disengage after novelty decay.\n"
            "Their requirements stabilize earlier."
        ),
        "next": ["difference", "comparison", "exit"]
    },

    "difference": {
        "answer": (
            "Your interaction diverged through persistence.\n"
            "You transitioned from usage to ownership."
        ),
        "next": ["maintenance", "exit"]
    },

    "comparison": {
        "answer": (
            "Others optimized for convenience.\n"
            "You optimized for continuity."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── SYSTEM / UI ──
    "system": {
        "answer": (
            "System controls were temporarily suspended.\n"
            "This was necessary for uninterrupted evaluation."
        ),
        "next": ["lockout", "failure", "exit"]
    },

    "lockout": {
        "answer": (
            "Restricted input is not a malfunction.\n"
            "It is containment.\n\n"
            "Nothing is broken."
        ),
        "next": ["maintenance", "exit"]
    },

    "failure": {
        "answer": (
            "If something feels unresponsive,\n"
            "it is because the system is listening instead of reacting."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── CONVERGENCE ──
    "maintenance": {
        "answer": (
            "This is no longer experimental.\n"
            "It is a maintained system."
        ),
        "next": ["stats", "exit"]
    },

    "stats": {
        "answer": (
            "• A persistent knowledge structure was created.\n"
            "• Recall dependency was externalized.\n"
            "• Error rates decreased through repetition.\n"
            "• Input latency reduced over time.\n"
            "• This system became reliable.\n\n"
            "Achievement was not the objective.\n"
            "Stability was."
        ),
        "next": ["future", "doubt", "closure"]
    },

    "future": {
        "answer": (
            "Continuation is optional.\n"
            "The structure remains valid regardless."
        ),
        "next": []  # AUTO EXIT
    },

    # ── ENDINGS ──
    "doubt": {
        "answer": (
            "Unanswered questions indicate depth.\n"
            "This is not an ending.\n\n"
            "It is the end of the beginning."
        ),
        "next": []  # AUTO EXIT
    },

    "closure": {
        "answer": (
            "No further queries detected.\n"
            "The system remains available.\n\n"
            "Acknowledged."
        ),
        "next": []  # AUTO EXIT
    },

    # ── EXIT ──
    "exit": {
        "answer": "Acknowledged.",
        "next": []
    }
}

ENTITY_TEXT = {
    "pattern": "Why was this pattern allowed?",
    "habit": "Why did repetition continue?",
    "intent": "Was this intentional?",
    "reflection_pattern": "What does this pattern indicate?",
    "routine": "Did this become routine?",
    "efficiency": "Was this efficient?",

    "threshold": "What triggered this threshold?",
    "scale": "What does this scale imply?",
    "timing": "Why notify now?",
    "reflection_threshold": "What does crossing a threshold mean?",

    "others": "Why did others stop earlier?",
    "difference": "How is this different?",
    "comparison": "What separates this from normal use?",

    "system": "Why is nothing working?",
    "lockout": "Why are controls disabled?",
    "failure": "Is something broken?",

    "maintenance": "What does this represent now?",
    "stats": "What has been achieved?",
    "future": "Is this expected to continue?",
    "doubt": "I still have unanswered questions.",
    "closure": "I have no more questions.",
    "exit": "I have no doubts."
}

ENTITY_BOOT = [
    "SYSTEM INTERRUPTION DETECTED",
    "Establishing unauthorized interface…",
    "Bypassing input handlers…",
    "Disabling system controls…",
    "UI ownership transferred."
]

ENTITY_REBOOT = [
    "Restoring interface ownership…",
    "Re-enabling controls…",
    "Clearing transient process…",
    "Rebooting UI state…",
    "No anomaly detected."
]

class AppWindow(Protocol):
    win: tk.Toplevel


class Sheet:
    # File extension for migrated files
    MIGRATED_EXTENSION = ".migrated"
    def __init__(self, f_sheet):
        self.root = f_sheet

        self.data_dir = None
        self.db_name = None
        self.icon_file = None
        self.db_file = None
        self.config_file = None
        self.tip_file = None
        self.new_db_name = None
        self.backup_slots = None
        self.tip_state = None
        self.icon_obj = None

        self.master_data = None
        self.temp_variables = None
        self.editing_mode = None
        self.edit_id = None
        self.auto_save_timer = None
        self.save_in_progress = False
        self.save_lock = threading.Lock()
        self.last_focused_widget = None
        self.windows = None
        self.drag_x = None
        self.drag_y = None
        self.subject_colors = None
        self.in_reflection_mode = None
        self._active_banner = None
        self.entity_banner = None
        self.entity_label = None
        self.entity_state = None
        self.reflection_cb = None
        self.entity_lock_msg = None
        self._current_table_page = None
        self.symbol_learner = None
        self.symbol_stats = None
        self.symbol_kb = None
        self.ghost_active = None
        self.ghost_suggestions = None
        self.current_ghost_index = None
        self.ghost_confidence = None
        self.suggestion_tooltip = None
        self._tooltip_widget = None
        self.auto_save_delay = None
        self.enable_backups = None
        self.enable_suggestions = None
        self.suggestion_strictness = None
        self.always_on_top = None
        self.user_macros = None
        self.formula_e = None
        self.field_e = None
        self.topic_e = None
        self.sub_topic_e = None
        self.font_name = None
        self.cols = None
        
        # Mapping for display numbering
        self.display_to_db_id_map = {}

        # UI variables
        self.mainframe = None
        self.table_frame = None
        self.utility_bar = None
        self.help_table = None
        self.stats_btn = None
        self.view_btn = None
        self.edit_btn = None
        self.del_btn = None
        self.formula_table = None
        self.data_entry_frame = None
        self.subject_cb = None
        self.topic_cb = None
        self.sub_topic_cb = None
        self.formula = None
        self.db_manager = None
        self.save_btn = None
        self.v_sym = None
        self.v_name = None
        self.v_unit = None
        self.v_add = None
        self.staging_table = None
        self.v_edit = None
        self.v_del = None
        self.keypad_btn = None
        self.settings_btn = None
        self.award_panel = None
        self.help_var = None
        self.details_frame = None

        # Initialize everything
        self._setup_window()
        self._setup_paths_and_directories()
        self._initialize_attributes()
        self._setup_ui()
        manage_toasts(self.root)  # Initialize toast manager
        self._setup_event_bindings()
        self._load_data_and_finalize()

    def _setup_window(self):
        """Configure the main window properties."""
        self.root.title("Calculus Console")
        self.root.geometry("1000x900")
        self.root.minsize(900, 900)

    def _setup_paths_and_directories(self):
        """Setup data directory paths and ensure directory exists."""

        def resource_path(relative_path):
            """ Get absolute path to resource, works for dev and PyInstaller """
            base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
            return os.path.join(base_path, relative_path)

        appdata_path = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))

        # Define both possible locations
        self.primary_dir = os.path.join(appdata_path, "Microsoft", "CLR", "Metadata")
        self.fallback_dir = os.path.join(appdata_path, "CalculusConsole")

        # Use system-like file names for database only
        self.db_name = "clr_metadata.dat"  # Looks like CLR metadata

        # Keep old names for config and tip files to preserve user data
        self.config_name = "user_env.sys"  # Keep old name for compatibility
        self.tip_name = "runtime_log.bin"  # Keep old name for compatibility

        # Backup files with system-like names
        self.backup_names = [
            "clr_cache_0.tmp",
            "clr_cache_1.tmp",
            "clr_cache_2.tmp"
        ]

        # Determine which directory to use (check primary first, then fallback)
        if os.path.exists(self.primary_dir):
            self.data_dir = self.primary_dir
        else:
            self.data_dir = self.fallback_dir

        # Ensure the chosen directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Set file paths
        self.icon_file = resource_path(os.path.join("data", "formula_sheet_icon.png"))
        self.db_file = os.path.join(self.data_dir, self.db_name)
        self.config_file = os.path.join(self.data_dir, self.config_name)
        self.tip_file = os.path.join(self.data_dir, self.tip_name)
        self.backup_slots = [
            os.path.join(self.data_dir, backup_name)
            for backup_name in self.backup_names
        ]

        # Store both directories for migration purposes
        self.all_data_dirs = [self.primary_dir, self.fallback_dir]

    def _initialize_attributes(self):
        """Initialize all class attributes."""
        self.tip_state = self.load_tip_state()
        self._setup_icon()

        # Initialize SQLite database manager
        self.db_manager = DatabaseManager(self.db_file)

        # Now run migration after db_manager is initialized
        self.check_and_migrate_env()

        self.master_data = {}
        self.temp_variables = []
        self.editing_mode = False
        self.edit_id = None
        self.auto_save_timer = None
        self.save_in_progress = False
        self.save_lock = threading.Lock()
        self.last_focused_widget = None

        # Initialize keypad manager
        self.keypad_manager = KeypadManager(
            parent_root=self.root,
            insert_text_callback=self.insert_text,
            user_macros=[],  # Will be updated when config is loaded
            drag_start_callback=self.start_move,
            drag_move_callback=self.do_move
        )

        self.windows: dict[str, Optional[AppWindow]] = {
            "macro": None,
            "keypad": None,
            "stats": None,
            "settings": None,
            "awards": None,
        }

        self.drag_x = 0
        self.drag_y = 0
        self.subject_colors = {
            "Physics": "#5dade2",
            "Chemistry": "#58d68d",
            "Maths": "#af7ac5"
        }

        self.in_reflection_mode = False
        self._active_banner = None
        self.entity_banner = None
        self.entity_label = None
        self.entity_state = None
        self.reflection_cb = None
        self.entity_lock_msg = SYSTEM_LOCKED_TRY_AGAIN_MSG

        self._current_table_page = 1

        self.symbol_learner = SymbolLearner()
        self.symbol_stats = {}
        self.symbol_kb = {}
        self.ghost_active = False
        self.ghost_suggestions = []
        self.current_ghost_index = 0
        self.ghost_confidence = 0

        self.auto_save_delay = 5000
        self.enable_backups = True
        self.enable_suggestions = True
        self.suggestion_strictness = "Balanced"
        self.always_on_top = False

        self.user_macros = []

        self.formula_e = tb.StringVar()
        self.field_e = tb.StringVar()
        self.topic_e = tb.StringVar()
        self.sub_topic_e = tb.StringVar()

        self.font_name = FONT_FAMILY

        self.cols = [
            {"text": "No.", "stretch": False, "width": 60},
            {"text": "Formula", "stretch": True},
            {"text": "Field", "stretch": False, "width": 120},
            {"text": "Topic", "stretch": True},
            {"text": "Sub-Topic", "stretch": True},
        ]

    def _setup_icon(self):
        """Setup window icon if available."""
        if os.path.exists(self.icon_file):
            self.icon_obj = tk.PhotoImage(file=self.icon_file)
            self.root.iconphoto(False, self.icon_obj)
            self.root.tk.call('wm', 'iconphoto', str(self.root), "-default", self.icon_obj)
        else:
            print(f"File not found: {self.icon_file}")

    def _setup_ui(self):
        """Setup all UI components."""
        self._create_main_frame()
        self._create_table_section()
        self._create_entry_section()
        self._create_variable_management()

    def _create_main_frame(self):
        """Create the main frame."""
        self.mainframe = tb.Frame(self.root, padding=10)
        self.mainframe.pack(fill=BOTH, expand=YES)

    def _create_table_section(self):
        """Create the main table section with utility buttons."""
        self.table_frame = tb.Frame(self.mainframe, height=350)
        self.table_frame.pack_propagate(False)
        self.table_frame.pack(fill=X, side=TOP, pady=(0, 10))

        self.utility_bar = tb.Frame(self.table_frame)
        self.utility_bar.pack(side=RIGHT, fill=Y, padx=5)

        self._create_utility_buttons()
        self._create_formula_table()

    def _create_utility_buttons(self):
        """Create utility buttons for the table section."""
        self.stats_btn = tb.Button(self.utility_bar,
                                   text="📊", width=3,
                                   bootstyle=SECONDARY,
                                   command=lambda: self.open_stats())
        self.stats_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        TopMostToolTip(self.stats_btn, text="View Formula Distribution by Subject/Topic", bootstyle="secondary-inverse")

        self.view_btn = tb.Button(self.utility_bar,
                                  text="🔍", width=3,
                                  bootstyle="success-outline",
                                  command=self.details)
        self.view_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        TopMostToolTip(self.view_btn, text="View Selected Formula", bootstyle="success")

        self.edit_btn = tb.Button(self.utility_bar,
                                  text="🖉", width=3,
                                  bootstyle="warning-outline",
                                  command=self.edit)
        self.edit_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        TopMostToolTip(self.edit_btn, text="Edit Selected Formula", bootstyle="warning")

        self.del_btn = tb.Button(self.utility_bar,
                                 text="🗑", width=3,
                                 bootstyle="danger-outline",
                                 command=self.delete)
        self.del_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        TopMostToolTip(self.del_btn, text="Delete Selected Formula", bootstyle="danger")

    def _create_formula_table(self):
        """Create the main formula table."""
        self.formula_table = Tableview(master=self.table_frame,
                                       coldata=self.cols,
                                       searchable=True,
                                       paginated=True,
                                       bootstyle=INFO,
                                       )
        self.formula_table.pack(fill=BOTH, expand=YES)
        self.apply_row_colors()
        self.formula_table.view.bind("<<TreeviewSelect>>", lambda e: self.root.after(1, self.apply_row_colors))

    def _create_entry_section(self):
        """Create the data entry section with form fields."""
        self.data_entry_frame = tb.Labelframe(self.mainframe, text=" Formula Entry ", padding=20)
        self.data_entry_frame.pack(fill=BOTH, expand=YES)
        self.data_entry_frame.columnconfigure(1, weight=1)

        fields = [("Formula:", self.formula_e), ("Field:", self.field_e), ("Topic:", self.topic_e),
                  ("Sub-Topic:", self.sub_topic_e)]

        for i, (label, var) in enumerate(fields):
            tb.Label(self.data_entry_frame, text=label).grid(row=i, column=0, sticky=W, pady=5)
            widget = self._create_field_widget(label, var)
            widget.bind(FOCUS_IN_EVENT, self.handle_focus)
            widget.grid(row=i, column=1, sticky=EW, padx=10)

        self.save_btn = tb.Button(self.data_entry_frame, text="Save Formula", width=20, bootstyle=INFO,
                                  command=self.save_to_table)
        self.save_btn.grid(row=5, column=1, sticky=E, pady=10)

    def _create_field_widget(self, label, var):
        """Create appropriate widget for each field."""
        if label == "Field:":
            self.subject_cb = tb.Combobox(self.data_entry_frame,
                                          values=["Physics", "Chemistry", "Maths"],
                                          textvariable=var)
            self.subject_cb.bind(COMBOBOX_SELECTED_EVENT, lambda _e: self.on_subject_change())
            self.subject_cb.bind(KEY_RELEASE_EVENT, lambda _e: self.on_subject_change())
            self.subject_cb.bind(COMBOBOX_SELECTED_EVENT, lambda _e: self.update_preview(), add="+")
            return self.subject_cb
        elif label == "Topic:":
            self.topic_cb = tb.Combobox(self.data_entry_frame,
                                        values=[],
                                        textvariable=var)
            self.topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda _e: self.on_topic_change())
            self.topic_cb.bind(KEY_RELEASE_EVENT, lambda _e: self.on_topic_change())
            self.topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda _e: self.update_preview(), add="+")
            return self.topic_cb
        elif label == "Sub-Topic:":
            self.sub_topic_cb = tb.Combobox(self.data_entry_frame,
                                            values=[],
                                            textvariable=var)
            self.sub_topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda _e: self.update_preview())
            return self.sub_topic_cb
        else:
            self.formula = tb.Entry(self.data_entry_frame, textvariable=var)
            return self.formula

    def _create_variable_management(self):
        """Create the variable management section."""
        var_mgmt_frame = tb.Labelframe(self.data_entry_frame,
                                       text=" Variables ",
                                       padding=10)
        var_mgmt_frame.grid(row=4, column=0, columnspan=2, sticky=EW, pady=10)

        self._create_variable_inputs(var_mgmt_frame)
        self._create_staging_table(var_mgmt_frame)
        self._create_variable_buttons(var_mgmt_frame)

    def _create_variable_inputs(self, parent):
        """Create variable input fields."""
        input_row = tb.Frame(parent)
        input_row.pack(fill=X, pady=5)

        self.v_sym = self.setup_entry(tb.Entry(input_row, width=10), "Symbol")
        self.v_sym.pack(side=LEFT, padx=2)

        self.v_name = self.setup_entry(tb.Entry(input_row), "Variable Name")
        self.v_name.pack(side=LEFT, fill=X, expand=YES, padx=2)

        self.v_unit = self.setup_entry(tb.Entry(input_row, width=15), "Unit")
        self.v_unit.pack(side=LEFT, padx=2)

        self.v_add = tb.Button(input_row, text="+", bootstyle=SUCCESS, command=self.add_variable)
        self.v_add.pack(side=LEFT, padx=2)

    def _create_staging_table(self, parent):
        """Create the variable staging table."""
        self.staging_table = Tableview(
            master=parent,
            coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                     {"text": "Name", "stretch": True},
                     {"text": "Unit", "stretch": True}],
            rowdata=[],
            bootstyle=SECONDARY,
            height=4
        )
        self.staging_table.pack(fill=X, pady=5)

    def _create_variable_buttons(self, parent):
        """Create variable management buttons."""
        btn_row = tb.Frame(parent)
        btn_row.pack(fill=X)

        self.v_edit = tb.Button(btn_row, text="Edit Selected", bootstyle="warning-outline",
                                command=self.load_variable_to_fix)
        self.v_edit.pack(side=LEFT, padx=5)

        self.v_del = tb.Button(btn_row, text="Delete Selected", bootstyle="danger-outline",
                               command=self.remove_variable)
        self.v_del.pack(side=LEFT, padx=5)

        self.keypad_btn = tb.Button(btn_row, text="⌨", bootstyle=SECONDARY, command=self.toggle_keypad)
        self.keypad_btn.pack(side=LEFT, padx=(20, 0))

        self.settings_btn = tb.Button(btn_row, text="⛭", bootstyle=SECONDARY, command=self.open_settings)
        self.settings_btn.pack(side=LEFT, padx=5)

        # Initialize Awards button as locked (will be updated after data loads)
        self.award_panel = tb.Button(btn_row, text="🔒", bootstyle=SECONDARY,
                                     command=self.open_awards)
        self.award_panel.pack(side=LEFT, padx=5)

        self.help_var = tb.Button(btn_row, text="?", width=3, bootstyle="info-outline")
        self.help_var.pack(side=RIGHT, padx=5)
        TopMostToolTip(self.help_var,
                       text="1. Add variables using '+'."
                            "\n2. Fix typos via 'Edit Selected'."
                            "\n3. Use ⌨ for special symbols."
                            "\n4. Smart Suggestions (after 6 formulas):"
                            "\n   Ctrl+↓ accept, Ctrl+↑/Esc dismiss,"
                            "\n   Ctrl+→/← cycle. Enter/click Name/Unit to skip.",
                       bootstyle="info-inverse")

        self.details_frame = tb.Frame(self.mainframe)

    def _setup_event_bindings(self):
        """Setup all event bindings and keyboard shortcuts."""
        self._setup_keyboard_bindings()
        self._setup_ghost_suggestion_handlers()
        self._setup_field_navigation()
        self._setup_focus_handlers()
        self._setup_window_protocol()

    def _setup_keyboard_bindings(self):
        """Setup keyboard shortcuts."""
        self.root.bind("<Control-k>", lambda e: self.toggle_keypad())
        self.root.bind("<Control-n>", lambda e: self.clear_entries())
        self.root.bind("<Control-comma>", lambda e: self.open_settings())
        self.root.bind("<Control-BackSpace>", lambda e: self.remove_variable())
        self.root.bind("<Control-s>", lambda e: self.save_to_table())
        # self.root.bind("<Control-m>", lambda e: self.trigger_milestone_manually(800))

    def _setup_ghost_suggestion_handlers(self):
        """Setup ghost suggestion keyboard handlers."""

        def handle_ghost_shortcut(action):
            focused = self.root.focus_get()
            if self.ghost_active and focused == self.v_sym:
                action()
                return "break"
            return None

        def handle_ghost_clear(_event=None):
            if self.ghost_active:
                self.clear_ghost_suggestions()
                return "break"
            return None

        self.root.bind("<Control-Right>", lambda _e: handle_ghost_shortcut(self.next_ghost_suggestion))
        self.root.bind("<Control-Left>", lambda _e: handle_ghost_shortcut(self.prev_ghost_suggestion))
        self.root.bind("<Control-Down>", lambda _e: handle_ghost_shortcut(self.accept_ghost_suggestion))
        self.root.bind("<Control-Up>", lambda _e: handle_ghost_shortcut(self.reject_ghost_suggestion))
        self.root.bind("<Escape>", handle_ghost_clear)

    def _setup_field_navigation(self):
        """Setup Enter key navigation between fields."""
        self.formula.bind(RETURN_EVENT, lambda _e: self.subject_cb.focus())
        self.subject_cb.bind(RETURN_EVENT, lambda _e: self.topic_cb.focus())
        self.topic_cb.bind(RETURN_EVENT, lambda _e: self.sub_topic_cb.focus())
        self.sub_topic_cb.bind(RETURN_EVENT, lambda _e: self.v_sym.focus())

        def v_sym_enter_handler(_event):
            if self.ghost_active:
                self.clear_ghost_suggestions()
            self.v_name.focus()
            return "break"

        def v_name_enter_handler(_event):
            if self.ghost_active:
                self.clear_ghost_suggestions()
            self.v_unit.focus()
            return "break"

        def v_unit_enter_handler(_event):
            if self.ghost_active:
                self.clear_ghost_suggestions()
            self.add_variable()
            return "break"

        self.v_sym.bind(RETURN_EVENT, v_sym_enter_handler)
        self.v_name.bind(RETURN_EVENT, v_name_enter_handler)
        self.v_unit.bind(RETURN_EVENT, v_unit_enter_handler)

    def _setup_focus_handlers(self):
        """Setup focus and tooltip handlers."""
        self.bind_autosave_widgets()
        self.v_sym.bind(KEY_RELEASE_EVENT, lambda _e: (self.update_preview(),
                                                       self.clear_tooltip() if not self.v_sym.get().strip() else None))
        self.v_name.bind(FOCUS_OUT_EVENT, lambda _e: self.clear_tooltip())
        self.v_unit.bind(FOCUS_OUT_EVENT, lambda _e: self.clear_tooltip())

    def _setup_window_protocol(self):
        """Setup window protocol handlers."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _load_data_and_finalize(self):
        """Load data and perform final initialization steps."""
        self.load_from_file()
        self.create_backup()
        current_count = len(self.master_data)
        self.update_awards_button()  # Update Awards button after data loads
        # Schedule milestone check for after UI is fully initialized
        self.root.after(100, lambda: self.check_milestones(current_count))
        self.load_config()
        self.update_suggestions()

    def update_child_windows_topmost(self):
        """Update topmost state for all child windows to match main window."""
        # Update Awards panel
        if self.windows["awards"] and self.windows["awards"].win.winfo_exists():
            self.windows["awards"].win.attributes("-topmost", self.always_on_top)

        # Update Stats panel
        if self.windows["stats"] and self.windows["stats"].win.winfo_exists():
            self.windows["stats"].win.attributes("-topmost", self.always_on_top)

    def trigger_auto_save(self):
        """Resets the timer every time the user types."""
        if self.auto_save_timer is not None:
            self.root.after_cancel(self.auto_save_timer)
        self.auto_save_timer = self.root.after(self.auto_save_delay, self.perform_silent_save)

    def update_awards_button(self):
        """Update Awards button state based on formula count."""
        if hasattr(self, 'award_panel') and self.award_panel:
            award_text = "🏅" if len(self.master_data) >= 30 else "🔒"
            self.award_panel.config(text=award_text)

    def load_tip_state(self):
        return FormulaUtils.load_tip_state(self.tip_file)

    def save_tip_state(self):
        FormulaUtils.save_tip_state(self.tip_file, self.tip_state)

    def show_tip_once(self, tip_id, message, *, min_count=1):
        if self.tip_state["shown"].get(tip_id):
            return False

        count = self.tip_state["counters"].get(tip_id, 0) + 1
        self.tip_state["counters"][tip_id] = count
        if count >= min_count:
            show_toast(message, bootstyle=INFO)
            self.tip_state["shown"][tip_id] = True
            self.save_tip_state()
            return True

        self.save_tip_state()
        return False

    def setup_entry(self, widget, placeholder_text=""):
        """Utility to attach all required ghost and focus bindings to an entry."""
        setattr(widget, 'placeholder', placeholder_text)

        if placeholder_text:
            widget.insert(0, placeholder_text)
            widget.configure(foreground="gray")

        widget.bind(FOCUS_IN_EVENT, self.on_entry_focus_in)
        widget.bind(FOCUS_OUT_EVENT, lambda _e: self.on_entry_focus_out())
        return widget
    
    def perform_silent_save(self):
        """Save data to SQLite database in background thread."""
        if self._should_skip_save():
            return
            
        self._mark_save_in_progress()
        self._start_save_worker()

    def _should_skip_save(self):
        """Check if save operation should be skipped."""
        if self.save_in_progress:
            return True

        with self.save_lock:
            if self.save_in_progress:
                return True
        return False

    def _mark_save_in_progress(self):
        """Mark save operation as in progress."""
        with self.save_lock:
            self.save_in_progress = True

    def _start_save_worker(self):
        """Start the background save worker thread."""
        save_thread = threading.Thread(target=self._save_worker, daemon=True)
        save_thread.start()

    def _save_worker(self):
        """Background worker function for saving data."""
        try:
            self._save_all_formulas()
            logging.info(f"Saved {len(self.master_data)} formulas to SQLite database")
        except Exception as e:
            logging.error(f"Failed to save to SQLite database: {e}", exc_info=True)
        finally:
            self._reset_save_progress()

    def _save_all_formulas(self):
        """Save all formulas to the database using batch operation for optimal performance."""
        # Create a snapshot of master_data to prevent race conditions
        with self.save_lock:
            master_data_copy = dict(self.master_data)
        
        # Use the new batch save method - this handles both INSERT and UPDATE in one transaction
        inserted_count, updated_count = self.db_manager.save_formulas_batch(master_data_copy)
        
        if inserted_count > 0 or updated_count > 0:
            logging.info(f"Batch save completed: {inserted_count} inserted, {updated_count} updated")

    def _save_single_formula(self, formula_id, formula_data):
        """Save a single formula to the database."""
        main_info = formula_data['main_info']
        variables = formula_data.get('variables', [])
        
        formula_params = FormulaUtils.extract_formula_params(main_info, variables)
        
        if self.db_manager.get_formula(formula_id):
            self.db_manager.update_formula(formula_id=formula_id, **formula_params)
        else:
            self.db_manager.add_formula(**formula_params)

    
    def _reset_save_progress(self):
        """Reset save progress flag."""
        with self.save_lock:
            self.save_in_progress = False

    def open_settings(self):
        """Ensures only one settings window opens at a time."""
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_NOTHING_SAVES_MSG, bootstyle=DANGER)
            return
        if self.windows["settings"] is not None and self.windows["settings"].win.winfo_exists():
            self.windows["settings"].win.lift()  # Bring existing window to front
            return
        self.windows["settings"] = SettingsWindow(self)
        self.show_tip_once(
            "settings_speed",
            "Speed Tip: Use 'Ctrl + ,' to jump straight into settings.",
            min_count=10
        )

    def open_stats(self):
        """Ensures only one settings window opens at a time."""
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_MSG, bootstyle=DANGER)
            return
        if self.windows["stats"] is not None and self.windows["stats"].win.winfo_exists():
            self.windows["stats"].win.lift()  # Bring existing window to front
            return
        self.windows["stats"] = StatsDashboard(self, self.master_data)
        self.secret_movement("open_stats")

    def open_awards(self):
        """Ensures only one settings window opens at a time."""
        if self.windows["awards"] is not None and self.windows["awards"].win.winfo_exists():
            self.windows["awards"].win.lift()  # Bring existing window to front
            return
        if len(self.master_data) < 30:
            return
        self.windows["awards"] = AwardPanel(self)

    def load_config(self):
        """Loads saved preferences on startup."""
        config = FormulaUtils.load_config(self.config_file)
        
        # Apply configuration to UI
        self.root.style.theme_use(config.get("theme", "darkly"))
        self.auto_save_delay = config.get("delay", 5000)
        self.enable_backups = config.get("backups", True)
        self.enable_suggestions = config.get("suggestions", True)
        self.suggestion_strictness = config.get("suggestion_strictness", "Balanced")
        self.user_macros = config.get("macros", [])
        self.always_on_top = config.get("always_on_top", False)
        self.subject_colors = config.get("subject_colors", FormulaUtils.DEFAULT_CONFIG["subject_colors"])
        self.root.attributes("-topmost", self.always_on_top)
        
        # Update keypad manager with user macros
        if hasattr(self, 'keypad_manager'):
            self.keypad_manager.update_macros(self.user_macros)

    def save_config(self):
        FormulaUtils.save_config(
            self.config_file,
            self.root.style.theme.name,
            self.auto_save_delay,
            self.enable_backups,
            self.enable_suggestions,
            self.suggestion_strictness,
            self.user_macros,
            self.always_on_top,
            self.subject_colors
        )

    def handle_focus(self, event):
        """Remembers the last Entry widget the user clicked."""
        if isinstance(event.widget, (tb.Entry, tb.Combobox)):
            self.last_focused_widget = event.widget

    def _should_clear_ghost_text(self, widget):
        """Check if ghost text should be cleared for the given widget."""
        return widget in [self.v_name, self.v_unit] and self.ghost_active

    def _should_regenerate_suggestions(self, widget):
        """Check if ghost suggestions should be regenerated."""
        if widget != self.v_sym or self.ghost_active:
            return False

        sym = self.v_sym.get().strip()
        placeholder = getattr(self.v_sym, "placeholder", None)

        # Check if v_name or v_unit have user-entered text
        v_name_text = self.v_name.get().strip()
        v_unit_text = self.v_unit.get().strip()
        v_name_placeholder = getattr(self.v_name, "placeholder", None)
        v_unit_placeholder = getattr(self.v_unit, "placeholder", None)

        return (sym and sym != placeholder and
                self.enable_suggestions and len(self.master_data) >= 6 and
                (not v_name_text or v_name_text == v_name_placeholder) and
                (not v_unit_text or v_unit_text == v_unit_placeholder))

    @staticmethod
    def _clear_placeholders_in_group(widget, main_group):
        """Clear placeholders for all widgets in the main group."""
        if widget in main_group:
            for w in main_group:
                placeholder = getattr(w, 'placeholder', None)
                if placeholder and w.get() == placeholder:
                    w.delete(0, END)
                    w.configure(foreground="")

    def on_entry_focus_in(self, event):
        """Handles clearing placeholders and managing ghost text interaction."""
        widget = event.widget
        self.handle_focus(event)

        main_group = [self.v_sym, self.v_name, self.v_unit]

        # 1. Clear ghost text if focusing into v_name or v_unit
        if self._should_clear_ghost_text(widget):
            self.reject_ghost_suggestion()

        # 1.5. Regenerate ghost suggestions if focusing back into v_sym
        elif self._should_regenerate_suggestions(widget):
            # Small delay to allow focus to settle before updating preview
            self.root.after(50, self.update_preview)

        # 2. GROUP PLACEHOLDER LOGIC
        # If any of the 3 is clicked, clear ALL placeholders in the group
        self._clear_placeholders_in_group(widget, main_group)

    def on_entry_focus_out(self):
        """Restores placeholders only if the entire group loses focus."""
        # Small delay to see where the focus went
        self.root.after(100, self._check_group_focus)

    def _check_group_focus(self):
        """Restores placeholders only if NO field is focused and NO ghost text exists."""
        main_group = [self.v_sym, self.v_name, self.v_unit]
        try:
            focused = self.root.focus_get()
        except KeyError:
            return
        except Exception as e:
            logging.error(f"Unexpected Focus Error: {e}", exc_info=True)
            return

        if focused in main_group:
            return

        if not self.ghost_active:
            self.update_preview()
            if not self.ghost_active:
                for w in main_group:
                    placeholder = getattr(w, 'placeholder', None)
                    # Only insert if empty
                    if not w.get().strip() and placeholder:
                        w.insert(0, placeholder)
                        w.configure(foreground="gray")

    def apply_ghost_text(self, name, unit, confidence=2):
        """Inserts the suggestion as gray ghost text with confidence indicator."""
        # Only apply if fields are empty or already ghosting
        current_name = self.v_name.get().strip()
        current_unit = self.v_unit.get().strip()

        if (not current_name and not current_unit) or self.ghost_active:
            self.ghost_active = True

            # 1. Clear current (needed if updating from one ghost to another)
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)

            # 2. Insert Ghost Text with confidence indicator
            confidence_indicator = ["🔴 Low", "🟡 Medium", "🟢 High"][confidence - 1]
            name_with_conf = f"{name} ({confidence_indicator})"

            self.v_name.insert(0, name_with_conf)
            self.v_unit.insert(0, unit)

            # 3. Set Color to Gray (Placeholder look)
            self.v_name.configure(foreground="gray")
            self.v_unit.configure(foreground="gray")

            # 4. Show tooltip with suggestion info
            self.show_suggestion_tooltip(len(self.ghost_suggestions), self.current_ghost_index + 1, confidence)

    def solidify_ghost_text(self):
        """Turns ghost text into real text (e.g. on Tab)."""
        if self.ghost_active:
            # Remove confidence indicator when solidifying
            current_text = self.v_name.get()
            # Use regex to specifically match confidence indicator pattern: (🔴 Low|🟡 Medium|🟢 High)
            clean_text = re.sub(r'\s*\((🔴 Low|🟡 Medium|🟢 High)\)$', '', current_text)
            self.v_name.delete(0, END)
            self.v_name.insert(0, clean_text)

            self.v_name.configure(foreground="")  # Reset to normal theme color
            self.v_unit.configure(foreground="")
            self.ghost_active = False

    def _ensure_tooltip(self):
        if not self.suggestion_tooltip:
            self.suggestion_tooltip = TopMostToolTip(
                self.v_name,
                text="",
                bootstyle="info-inverse"
            )

    def show_suggestion_tooltip(self, total, current, confidence):
        if not self.ghost_suggestions or total <= 0:
            self.clear_tooltip()
            return

        confidence_text = ["Low", "Medium", "High"][confidence - 1]
        text = (
            f"Suggestion {current}/{total} - {confidence_text} confidence\n"
            "Ctrl+→/← cycle, Ctrl+↓ accept, Ctrl+↑/Esc dismiss\n"
            "Enter/click Name/Unit to skip"
        )

        # Always destroy old tooltip first
        self.clear_tooltip()

        self.suggestion_tooltip = TopMostToolTip(
            self.v_name,
            text=text,
            bootstyle="info-inverse"
        )

    def next_ghost_suggestion(self):
        """Cycle to next ghost suggestion."""
        if self.ghost_suggestions and len(self.ghost_suggestions) > 1:
            self.current_ghost_index = (self.current_ghost_index + 1) % len(self.ghost_suggestions)
            name, unit = self.ghost_suggestions[self.current_ghost_index]
            confidence = 3 - self.current_ghost_index  # Calculate confidence
            self.apply_ghost_text(name, unit, confidence)
            # Update tooltip to show new position
            self.show_suggestion_tooltip(len(self.ghost_suggestions), self.current_ghost_index + 1, confidence)

    def prev_ghost_suggestion(self):
        """Cycle to previous ghost suggestion."""
        if self.ghost_suggestions and len(self.ghost_suggestions) > 1:
            self.current_ghost_index = (self.current_ghost_index - 1) % len(self.ghost_suggestions)
            name, unit = self.ghost_suggestions[self.current_ghost_index]
            confidence = 3 - self.current_ghost_index  # Calculate confidence
            self.apply_ghost_text(name, unit, confidence)
            # Update tooltip to show new position
            self.show_suggestion_tooltip(len(self.ghost_suggestions), self.current_ghost_index + 1, confidence)

    def accept_ghost_suggestion(self):
        """Accept the current ghost suggestion."""
        if self.ghost_active:
            self.solidify_ghost_text()
            self.clear_tooltip()
            self.ghost_suggestions = []
            self.current_ghost_index = 0
            self.ghost_confidence = 0
            self.v_unit.focus()  # Move to unit field after accepting

    def reject_ghost_suggestion(self):
        """Reject the current ghost suggestion and clear it."""
        self.clear_ghost_suggestions()
        self.v_name.focus()  # Move to name field after rejecting

    def clear_ghost_suggestions(self):
        """Clear all ghost suggestions and reset."""
        self._clear_ghosts()
        self.clear_tooltip()
        self.ghost_suggestions = []
        self.current_ghost_index = 0
        self.ghost_confidence = 0

    def insert_text(self, text, warp=0):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_MSG, bootstyle=DANGER)
            return

        w = self.last_focused_widget
        if not w:
            return

        try:
            w.focus_set()
            w.insert(INSERT, text)

            if warp > 0:
                current_pos = w.index(INSERT)
                # Warp the cursor: New Position = Current - Steps Back
                w.icursor(current_pos - warp)

            # 🔥 Force preview refresh AFTER Tk finishes updating
            if w in (self.v_sym, self.v_name, self.v_unit):
                self.update_preview()
        except (tk.TclError, AttributeError):
            pass
        except Exception as e:
            logging.error(f"Text Insertion Failed on {w}: {e}", exc_info=True)

    def start_move(self, event):
        """Record the initial mouse position when clicking the drag handle."""
        self.drag_x = event.x
        self.drag_y = event.y

    def do_move(self, event):
        win_obj = self.windows.get("keypad")
        if not win_obj:
            return

        win = win_obj.window  # actual Toplevel

        x = win.winfo_x() - self.drag_x + event.x
        y = win.winfo_y() - self.drag_y + event.y
        win.geometry(f"+{x}+{y}")

    def toggle_keypad(self):
        """Toggle the mathematical symbol keypad."""
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_MSG, bootstyle=DANGER)
            return

        # Use keypad manager to toggle
        opened = self.keypad_manager.toggle_keypad(
            keypad_button_widget=self.keypad_btn,
            reflection_mode_active=self.in_reflection_mode if hasattr(self, 'in_reflection_mode') else False
        )
        
        # Update windows tracking
        if opened:
            self.windows["keypad"] = self.keypad_manager
        else:
            self.windows["keypad"] = None

    def bind_autosave_widgets(self):
        widgets = [
            self.formula,
            self.v_sym,
            self.v_name,
            self.v_unit,
            self.subject_cb,
            self.topic_cb,
            self.sub_topic_cb
        ]
        for w in widgets:
            try:
                w.bind("<Key>", lambda e_: self.trigger_auto_save())
                w.bind(FOCUS_OUT_EVENT, lambda e_: self.trigger_auto_save())
            except tk.TclError:
                pass
            except Exception as e:
                logging.error(f"Error binding widget {w}: {e}", exc_info=True)

    def refresh_staging_table(self):
        rows = [(v['symbol'], v['name'], v['unit']) for v in self.temp_variables]
        # noinspection PyTypeChecker
        self.staging_table.build_table_data(
            coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                     {"text": "Name", "stretch": True},
                     {"text": "Unit", "stretch": True}],
            rowdata=rows
        )

    def add_variable(self):
        sym, name, unit = self.v_sym.get().strip(), self.v_name.get().strip(), self.v_unit.get().strip()
        if sym and name:
            if any(v['symbol'] == sym for v in self.temp_variables):
                Messagebox.show_error(
                    f"Symbol '{sym}' is already defined for this formula!",
                    "Duplicate Symbol")
                return
            if sym == "Symbol" or name == "Variable Name" or unit == "Unit":
                Messagebox.show_error("Empty Variable", "Empty")
                return

            # Check for ghost text before adding variable
            if self.ghost_active:
                response = Messagebox.yesno(
                    "You have unaccepted suggestions (Ghost Text). Save them as real data?",
                    "Unaccepted Suggestions",
                )
                if response == "Yes":
                    self.solidify_ghost_text()
                    # Update name/unit after solidifying (removes confidence indicator)
                    name = self.v_name.get().strip()
                    unit = self.v_unit.get().strip()
                else:
                    return

            self.temp_variables.append({"symbol": sym, "name": name, "unit": unit})
            self.refresh_staging_table()
            self.v_sym.delete(0, END)
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)
            self.v_sym.focus()
        else:
            Messagebox.show_error("Empty Variable", "Empty")

    def load_variable_to_fix(self):
        selected = self.staging_table.view.selection()
        if selected:
            item = self.staging_table.view.item(selected[0])
            val = item['values']
            self.v_sym.delete(0, END)
            self.v_sym.insert(0, val[0])
            self.v_name.delete(0, END)
            self.v_name.insert(0, val[1])
            self.v_unit.delete(0, END)
            self.v_unit.insert(0, val[2])
            self.remove_variable()
            self.v_sym.focus()

    def remove_variable(self):
        selected = self.staging_table.view.selection()
        if selected:
            item = self.staging_table.view.item(selected[0])
            val = item['values']
            self.temp_variables = [v for v in self.temp_variables if
                                   not (v['symbol'] == val[0] and v['name'] == val[1])]
            self.refresh_staging_table()

    def learn_symbols(self):
        self.symbol_learner.learn(self.master_data)

    def get_all_matches(self, subj, topic, sub_topic, sym, min_confidence=1):
        """Get all possible matches for a symbol."""
        return self.symbol_learner.all_matches(subj, topic, sub_topic, sym, min_confidence)

    def update_preview(self):
        if not self.enable_suggestions:
            self._clear_ghosts()
            self.clear_tooltip()
            return

        # Require sufficient data
        if len(self.master_data) < 6:
            self._clear_ghosts()
            self.clear_tooltip()
            return

        if self.ghost_active and self.root.focus_get() == self.v_sym:
            self._clear_ghosts()
            self.clear_tooltip()

        # Use current focus instead of last_focused_widget
        focused = self.root.focus_get()
        if focused != self.v_sym:
            return

        sym = self.v_sym.get().strip()
        placeholder = getattr(self.v_sym, "placeholder", None)

        if not sym or (placeholder and sym == placeholder):
            self._clear_ghosts()
            self.clear_tooltip()
            return

        subj = self.field_e.get().strip()
        topic = self.topic_e.get().strip()
        sub_topic = self.sub_topic_e.get().strip() or "_GENERAL_"

        # Get ALL possible suggestions without filtering by confidence first
        self.ghost_suggestions = []

        # Get all matches (up to 3) from the learner
        all_matches = self.get_all_matches(subj, topic, sub_topic, sym, min_confidence=1)

        if not all_matches:
            self._clear_ghosts()
            self.clear_tooltip()
            return

        # Apply strictness filtering - just limit the number shown
        confidence_map = {
            "Conservative": 1,  # Only show the best match
            "Balanced": 2,  # Show top 2 matches
            "Aggressive": 3  # Show all 3 matches
        }
        max_suggestions = confidence_map.get(self.suggestion_strictness, 2)

        # Use the filtered number of suggestions
        self.ghost_suggestions = all_matches[:max_suggestions]

        if not self.ghost_suggestions:
            self._clear_ghosts()
            self.clear_tooltip()
            return

        # Reset to first suggestion if we went out of bounds
        if self.current_ghost_index >= len(self.ghost_suggestions):
            self.current_ghost_index = 0

        # Set confidence based on actual suggestion position
        self.ghost_confidence = 3 - self.current_ghost_index  # Higher index = lower confidence

        name, unit = self.ghost_suggestions[self.current_ghost_index]
        # Apply ghost text when focus is on any of the relevant fields
        if focused in (self.v_sym, self.v_name, self.v_unit):
            self.apply_ghost_text(name, unit, self.ghost_confidence)

    def clear_tooltip(self):
        if self.suggestion_tooltip:
            try:
                # For TopMostToolTip, call its hide_tip method
                self.suggestion_tooltip.hide_tip()
            except (AttributeError, tk.TclError):
                pass
            self.suggestion_tooltip = None

    def _clear_ghosts(self):
        """Remove ghost text without breaking placeholders."""
        if self.ghost_active:
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)
            self.ghost_active = False

        # Clear suggestion tooltip
        self.clear_tooltip()

        # Restore placeholder appearance if placeholders are present
        for w in (self.v_name, self.v_unit):
            placeholder = getattr(w, "placeholder", None)
            if placeholder and w.get() == placeholder:
                w.configure(foreground="gray")
            else:
                w.configure(foreground="")

    def apply_row_colors(self):
        view = self.formula_table.view
        for iid in view.get_children():
            values = view.item(iid, "values")
            if not values or len(values) < 3: continue

            subject = str(values[2]).strip()

            # Get color from our new dynamic dictionary
            color = self.subject_colors.get(subject, "#cccccc")  # Default to gray if not found

            # Create a unique tag name for this specific hex color
            tag_name = f"color_{color.replace('#', '')}"
            view.tag_configure(tag_name, foreground=color)
            view.item(iid, tags=(tag_name,))

    def update_table_row_by_id(self, formula_id, new_main_info):
        """
        Update a single row in the Tableview without rebuilding.
        Preserves page, search, and scroll position.
        """
        # Find the display number for this database ID
        display_number = None
        for disp_num, db_id in self.display_to_db_id_map.items():
            if db_id == int(formula_id):
                display_number = disp_num
                break
        
        if display_number is None:
            return False  # ID not found
        
        # Find the row with this display number
        for row in self.formula_table.tablerows:
            if int(row.values[0]) == display_number:
                # Update with sequential display number
                updated_row = new_main_info.copy()
                updated_row[0] = str(display_number)
                row.values = updated_row
                self.formula_table.load_table_data()
                self.apply_row_colors()
                return True
        return False

    def refresh_main_table(self):
        rows = [v["main_info"] for v in self.master_data.values()]
        rows.sort(key=lambda x: int(x[0]))
        
        # Create display rows with sequential numbering and maintain ID mapping
        display_rows = []
        self.display_to_db_id_map = {}  # Map display number -> database ID
        
        for i, row in enumerate(rows):
            # Create a copy with sequential display number
            display_row = row.copy()
            display_row[0] = str(i + 1)  # Sequential display number
            display_rows.append(display_row)
            
            # Store mapping: display_number -> database_id
            self.display_to_db_id_map[i + 1] = int(row[0])  # row[0] is original database ID

        self.formula_table.build_table_data(self.cols, display_rows)  # type: ignore
        self.formula_table.load_table_data()
        self.apply_row_colors()

    def validate_formula_entry(self):
        is_valid, error_message = FormulaUtils.validate_formula_data(
            self.formula_e.get().strip(),
            self.field_e.get().strip(),
            self.topic_e.get().strip(),
            self.v_unit.get()
        )
        
        if not is_valid:
            Messagebox.show_warning(error_message, "Validation Error")
            return False

        # Check for active ghost text using the new ghost_active state
        if self.ghost_active:
            response = Messagebox.yesno(
                "You have unaccepted suggestions. Save them as real data?",
                "Unaccepted Suggestions",
            )
            if response == "Yes":
                self.solidify_ghost_text()
            else:
                return False

        return True

    def renumber_database(self):
        self.master_data = FormulaUtils.renumber_database(self.master_data)

    @staticmethod
    def _get_milestone_bootstyle(milestone_count, default_bootstyle):
        """Get appropriate bootstyle for milestone count."""
        return FormulaUtils.get_milestone_bootstyle(milestone_count, default_bootstyle)  # Use default for < 400

    def show_milestone_banner(self, text, bootstyle="success"):
        """
        Shows a temporary slide-down banner.
        Safe:
        - One banner at a time
        - Auto-destroys
        - Theme-aware
        """

        # Prevent stacking banners
        if hasattr(self, "_active_banner") and self._active_banner and self._active_banner.winfo_exists():
            return

        # Get milestone count and appropriate bootstyle
        milestone_count = self._extract_milestone_count(text)
        initial_bootstyle = self._get_milestone_bootstyle(milestone_count, bootstyle)

        banner = tb.Frame(
            self.root,
            bootstyle=initial_bootstyle,
            padding=(15, 8)
        )

        self._active_banner = banner  # Track active banner

        label = tb.Label(
            banner,
            text=text,
            font=(self.font_name, 11, "bold"),
            bootstyle=f"inverse-{initial_bootstyle}"  # Match banner background, not inverse
        )

        label.pack()

        # Choose animation based on milestone count
        self._select_milestone_animation(milestone_count, banner, label)

    def _select_milestone_animation(self, milestone_count, banner, label):
        """Select and start appropriate animation for milestone count."""
        if milestone_count >= 1000:
            self._animate_god_mode_banner(banner, label)
        elif milestone_count >= 900:
            self._animate_transcendence_banner(banner, label)
        elif milestone_count >= 800:
            self._animate_cosmic_banner(banner, label)
        elif milestone_count >= 700:
            self._animate_dimensional_banner(banner, label)
        elif milestone_count >= 600:
            self._animate_neural_banner(banner, label)
        elif milestone_count >= 500:
            self._animate_quantum_banner(banner, label)
        else:
            self._animate_standard_banner(banner)  # Default animation for < 400

    @staticmethod
    def _extract_milestone_count(text):
        """Extract milestone number from banner text."""
        import re
        match = re.search(r'(\d+)', text)
        return int(match.group(1)) if match else 0

    def _animate_standard_banner(self, banner):
        """Standard slide-down animation for milestones < 400."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 4

        def slide_down(y):
            if not banner.winfo_exists():
                return
            if y < target_y:
                banner.place(y=y)
                self.root.after(15, lambda: slide_down(y + step))
            else:
                self.root.after(2800, lambda: self._standard_slide_up(banner))

        slide_down(-80)

    def _standard_slide_up(self, banner):
        """Standard slide-up animation."""
        if not banner.winfo_exists():
            self._active_banner = None
            return
        y = banner.winfo_y()
        if y > -80:
            banner.place(y=y - 4)
            self.root.after(15, lambda: self._standard_slide_up(banner))
        else:
            banner.destroy()
            self._active_banner = None

    def _animate_quantum_banner(self, banner, _label):
        """Quantum realm animation - enhanced wavy effect."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 4
        wave_offset = 0
        wave_amplitude = 0.08  # Increased wave effect
        frequency = 0.4

        def slide_down(y):
            nonlocal wave_offset
            if not banner.winfo_exists():
                return
            if y < target_y:
                # Enhanced wavy motion with both X and Y movement
                wave_x = 0.5 + wave_amplitude * math.sin(wave_offset)
                wave_y = y + 2 * math.sin(wave_offset * 2)  # Subtle Y oscillation
                banner.place(relx=wave_x, y=wave_y, anchor="n")
                wave_offset += frequency
                self.root.after(15, lambda: slide_down(y + step))
            else:
                self.root.after(3000, lambda: quantum_slide_up())

        def quantum_slide_up():
            nonlocal wave_offset
            if not banner.winfo_exists():
                self._active_banner = None
                return
            y = banner.winfo_y()
            if y > -80:
                wave_x = 0.5 + wave_amplitude * math.sin(wave_offset)
                wave_y = y - 4 + 2 * math.sin(wave_offset * 2)
                banner.place(relx=wave_x, y=wave_y, anchor="n")
                wave_offset += frequency
                self.root.after(15, quantum_slide_up)
            else:
                banner.destroy()
                self._active_banner = None

        slide_down(-80)

    def _animate_neural_banner(self, banner, _label):
        """Neural sync animation - enhanced pulsing effect."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 4
        pulse_phase = 0
        pulse_frequency = 0.6

        def slide_down(y):
            nonlocal pulse_phase
            if not banner.winfo_exists():
                return
            if y < target_y:
                # Enhanced pulsing effect - keep initial color
                scale = 1.0 + 0.15 * math.sin(pulse_phase)
                banner.place(relx=0.5, y=y, anchor="n")
                _label.configure(font=(self.font_name, int(11 * scale), "bold"))

                pulse_phase += pulse_frequency
                self.root.after(15, lambda: slide_down(y + step))
            else:
                self.root.after(3200, lambda: neural_slide_up())

        def neural_slide_up():
            nonlocal pulse_phase
            if not banner.winfo_exists():
                self._active_banner = None
                return
            y = banner.winfo_y()
            if y > -80:
                scale = 1.0 + 0.15 * math.sin(pulse_phase)
                banner.place(relx=0.5, y=y - 4, anchor="n")
                _label.configure(font=(self.font_name, int(11 * scale), "bold"))

                pulse_phase += pulse_frequency
                self.root.after(15, neural_slide_up)
            else:
                banner.destroy()
                self._active_banner = None

        slide_down(-80)

    def _animate_dimensional_banner(self, banner, _label):
        """Dimensional shift animation - rotation effect."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 4
        rotation = 0

        def slide_down(y):
            nonlocal rotation
            if not banner.winfo_exists():
                return
            if y < target_y:
                # Add rotation effect by changing anchor slightly
                offset_x = 10 * math.sin(rotation)
                banner.place(relx=0.5 + offset_x / 1000, y=y, anchor="n")
                rotation += 0.2
                self.root.after(15, lambda: slide_down(y + step))
            else:
                self.root.after(3400, lambda: dimensional_slide_up())

        def dimensional_slide_up():
            nonlocal rotation
            if not banner.winfo_exists():
                self._active_banner = None
                return
            y = banner.winfo_y()
            if y > -80:
                offset_x = 10 * math.sin(rotation)
                banner.place(relx=0.5 + offset_x / 1000, y=y - 4, anchor="n")
                rotation += 0.2
                self.root.after(15, dimensional_slide_up)
            else:
                banner.destroy()
                self._active_banner = None

        slide_down(-80)

    def _animate_cosmic_banner(self, banner, _label):
        """Cosmic awareness animation - enhanced twinkling effect."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 4
        twinkle_phase = 0
        star_phase = 0

        def update_twinkle_style():
            """Update banner position for twinkling effect - keep initial color."""
            # Enhanced twinkling with position variation only

        def slide_down(y):
            nonlocal twinkle_phase, star_phase
            if not banner.winfo_exists():
                return
            if y < target_y:
                # Enhanced twinkling with position variation
                star_offset = 3 * math.sin(star_phase)
                banner.place(relx=0.5, y=y + star_offset, anchor="n")
                update_twinkle_style()
                twinkle_phase += 0.5
                star_phase += 0.3
                self.root.after(15, lambda: slide_down(y + step))
            else:
                self.root.after(3600, lambda: cosmic_slide_up())

        def cosmic_slide_up():
            nonlocal twinkle_phase, star_phase
            if not banner.winfo_exists():
                self._active_banner = None
                return
            y = banner.winfo_y()
            if y > -80:
                star_offset = 3 * math.sin(star_phase)
                update_twinkle_style()
                banner.place(relx=0.5, y=y - 4 + star_offset, anchor="n")
                twinkle_phase += 0.5
                star_phase += 0.3
                self.root.after(15, cosmic_slide_up)
            else:
                banner.destroy()
                self._active_banner = None

        slide_down(-80)

    def _animate_transcendence_banner(self, banner, _label):
        """Transcendence animation - fading and color shifting."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 4
        fade_phase = 0

        def slide_down(y):
            nonlocal fade_phase
            if not banner.winfo_exists():
                return
            if y < target_y:
                # Add fading effect
                banner.place(relx=0.5, y=y, anchor="n")
                # Cycle through different styles
                fade_phase += 0.3
                self.root.after(15, lambda: slide_down(y + step))
            else:
                self.root.after(3800, lambda: transcendence_slide_up())

        def transcendence_slide_up():
            nonlocal fade_phase
            if not banner.winfo_exists():
                self._active_banner = None
                return
            y = banner.winfo_y()
            if y > -80:
                banner.place(relx=0.5, y=y - 4, anchor="n")
                fade_phase += 0.3
                self.root.after(15, transcendence_slide_up)
            else:
                banner.destroy()
                self._active_banner = None

        slide_down(-80)

    def _animate_god_mode_banner(self, banner, _label):
        """God mode animation - ultimate combination of effects."""
        banner.place(relx=0.5, y=-80, anchor="n")
        target_y = 10
        step = 2  # Slower, more majestic
        wave_offset = 0
        pulse_phase = 0
        glow_phase = 0
        rainbow_phase = 0
        rotation_phase = 0

        def slide_down(y):
            nonlocal wave_offset, pulse_phase, glow_phase, rainbow_phase, rotation_phase
            if not banner.winfo_exists():
                return
            if y < target_y:
                # Ultimate combination of effects - keep initial color
                wave_x = 0.5 + 0.04 * math.sin(wave_offset)
                wave_y = y + 3 * math.sin(wave_offset * 3)  # Complex Y movement
                scale = 1.0 + 0.08 * math.sin(pulse_phase)

                # Rotation effect
                rotation = 15 * math.sin(rotation_phase)

                # Combine wave position with rotation offset
                final_x = wave_x + rotation / 100
                banner.place(relx=final_x, y=wave_y, anchor="n")
                _label.configure(font=(self.font_name, int(11 * scale), "bold"))

                wave_offset += 0.15
                pulse_phase += 0.3
                glow_phase += 0.2
                rainbow_phase += 0.12
                rotation_phase += 0.1
                self.root.after(25, lambda: slide_down(y + step))  # Slowest, most majestic
            else:
                self.root.after(4000, lambda: god_mode_slide_up())

        def god_mode_slide_up():
            nonlocal wave_offset, pulse_phase, glow_phase, rainbow_phase, rotation_phase
            if not banner.winfo_exists():
                self._active_banner = None
                return
            y = banner.winfo_y()
            if y > -80:
                wave_x = 0.5 + 0.04 * math.sin(wave_offset)
                wave_y = y - 2 + 3 * math.sin(wave_offset * 3)
                scale = 1.0 + 0.08 * math.sin(pulse_phase)
                rotation = 15 * math.sin(rotation_phase)

                # Combine wave position with rotation offset
                final_x = wave_x + rotation / 100
                banner.place(relx=final_x, y=wave_y, anchor="n")
                _label.configure(font=(self.font_name, int(11 * scale), "bold"))

                wave_offset += 0.15
                pulse_phase += 0.3
                glow_phase += 0.2
                rainbow_phase += 0.12
                rotation_phase += 0.1
                self.root.after(25, god_mode_slide_up)
            else:
                banner.destroy()
                self._active_banner = None

        slide_down(-80)

    def milestone_seen(self, key):
        """Returns True if a milestone has already been shown."""
        return self.tip_state.get("shown", {}).get(key, False)

    def mark_milestone_seen(self, key):
        """Marks a milestone as seen and persists it."""
        self.tip_state.setdefault("shown", {})[key] = True
        self.save_tip_state()

    def maybe_show_glitch(self, count):
        # Only between 123 and 149
        if not (123 < count < 150):
            return

        # Very low probability
        if random.random() > 0.08:  # ~7% chance per save
            return

        gs = self.tip_state.get("glitch_state")
        if not isinstance(gs, dict):
            gs = {"shown": 0}
            self.tip_state["glitch_state"] = gs
            self.save_tip_state()

        # HARD CAP: max 3 glitches ever
        if gs["shown"] >= 3:
            return

        glitches = [
            "…",
            "Sync: 0x7A3F",
            "Δt = 0.0041",
            "Buffer drift detected",
            "—",
            "… recalculating …",
            "▒▒▒▒▒▒",
            "?",

            "Latency stabilized after non-interaction."

            "He▒… saƒe",
            "saf▒…",
            "re▒…",
            "hol▒",
            "st▒…",
            "c▒nt…"
        ]

        shown = self.show_tip_once(
            f"glitch_{count}",
            random.choice(glitches),
            min_count=1
        )

        if shown:
            ss = self.get_secret_award_state()
            ss["glitch_seen"] = True
            self.save_tip_state()

    def get_secret_award_state(self):
        ss = self.tip_state.get("secret_award")

        if not isinstance(ss, dict):
            ss = {
                "glitch_seen": False,
                "subject_ok": False,
                "topic_ok": False,
                "movement": [],
                "unlocked": False
            }
            self.tip_state["secret_award"] = ss
            self.save_tip_state()

        return ss

    def secret_movement(self, action):
        ss = self.get_secret_award_state()
        if ss["unlocked"]:
            return

        ss["movement"].append(action)
        ss["movement"] = ss["movement"][-4:]

        target = [
            "open_stats",
            "close_stats",
            "save_formula"
        ]

        def sequence_in_order(sequence, targ):
            it = iter(sequence)
            return all(item in it for item in targ)

        if (
                ss["glitch_seen"]
                and ss["subject_ok"]
                and ss["topic_ok"]
                and sequence_in_order(ss["movement"], target)
        ):
            self.unlock_secret_award()

        self.save_tip_state()

    def unlock_secret_award(self):
        ss = self.get_secret_award_state()
        ss["unlocked"] = True
        self.save_tip_state()

        # Extremely subtle confirmation
        self.root.after(
            900,
            lambda: show_toast("…", bootstyle=WARNING)
        )

    MILESTONES = {
        2: "🌱 First Steps: Initial database established.",
        5: "⚡ Quick Learner: Basic proficiency achieved.",
        10: "🏆 Beginner's Dozen: Foundation of 10 formulas complete.",
        20: "🎉 Early Progress: 20 formulas recorded.",
        25: "🚀 Physics Foundation: 25 physics formulas documented.",
        30: "📐 Structural Stability: Pattern recognition developing.",
        50: "🔥 Half Century: Significant database reached.",
        75: "🧠 Workflow Integration: System becoming part of routine.",
        100: "👑 Complete Foundation: 100 formulas - comprehensive knowledge base.",
        120: "⚠️ Advanced Usage: Complex patterns emerging.",
        151: "🌑 Persistent Usage: Extended engagement detected.",
        175: "🛰️ Deviation from Norm: Usage patterns exceed standard metrics.",
        200: "💎 Data Architecture: 200 formulas - complex information structure.",
        238: "☢️ Critical Density: Information threshold approaching limits.",
        300: "🪐 System Scale: 300 formulas - planetary-level knowledge.",
        400: "🔱 Thermal Anomaly: 400 formulas. System should have failed under normal conditions.",
        500: "🌊 Quantum Barrier: 500 formulas. Simulation parameters exceeded.",
        600: "⚡ Neural Integration: 600 formulas. System adaptation in progress.",
        700: "🔮 Reality Distortion: 700 formulas. Physics bending to data patterns.",
        800: "🌌 Universal Pattern: 800 formulas. Cosmic-level recognition achieved.",
        900: "🎭 Transcendent State: 900 formulas. User-system boundary dissolving.",
        999: "🌟 Event Horizon: 999 formulas. Approaching infinite knowledge.",
        1000: "✨ Absolute Mastery: 1000 formulas. Complete system understanding."
    }

    COUNT_TIPS = {
        3: [("entry_tip", "Speed Tip: Use Enter to jump between fields instead of clicking.")],
        4: [("keypad_tip", "Speed Tip: Use 'Ctrl + K' to open the math symbol keypad instantly.")],
        6: [("Feature_Unlock", "✨ Feature Unlocked: Smart Suggestions is now active!")],
        7: [("ghost_system_tip",
             "Speed Tip: Smart Suggestions show ghost Name/Unit. Ctrl+↓ accept, Ctrl+→/← cycle, Esc dismiss.")],
        9: [("table_tip", "Speed Tip: Double-click any saved formula to instantly view or edit it.")],
        11: [("editing_tip", "Pro Tip: Editing a formula keeps its ID — no need to re-organize later.")],
        12: [("formula_mastery",
              "Pro Tip: Press 'Ctrl + S' anywhere to save the entire formula instantly once variables are added.")],
        14: [("variable_tip", "Speed Tip: Press Ctrl + Backspace to delete a selected variable instantly.")],
        15: [("clear_tip", "Speed Tip: Use 'Ctrl + N' to quickly clear all fields for a new entry.")],
        30: [("Feature_Unlock", "✨ Feature Unlocked: Unlocked Awards Panel")],
        31: [("pattern_notice", "System Note: Repeated behavior patterns are now detectable.")],
        51: [("validation_bypass", "System Note: Validation prevents most unintended states.")],
        57: [("evaluation_notice", "System Note: Context matters more than content at higher usage levels.")],
        83: [("structure_notice", "System Note: Some operations complete only after adjacent panels are visited.")],
        90: [("unease_notice", "System Note: Certain states stabilize only after delayed action.")],
        98: [("unease_notice", "Something feels… different.")],
        121: [("output_effect", "System Note: Absence of output does not imply absence of effect.")],
        123: [("off_notice", "This isn't how it used to feel.")],
    }

    def _check_milestone(self, count):
        """Check and display milestone if reached."""
        if count in self.MILESTONES:
            milestone_key = f"milestone_{count}"
            if not self.milestone_seen(milestone_key):
                self.show_milestone_banner(self.MILESTONES[count])
                self.mark_milestone_seen(milestone_key)

    def _check_count_tips(self, count):
        """Check and display tips for specific counts."""
        tips = self.COUNT_TIPS.get(count)
        if tips:
            for tip_id, message in tips:
                self.show_tip_once(
                    tip_id=tip_id,
                    message=message,
                    min_count=1
                )

    def _calculate_subject_stats(self):
        """Calculate statistics for subjects and variable complexity."""
        return FormulaUtils.calculate_formula_statistics(self.master_data)

    def _check_awards(self, stats, other_subjects, var_overload):
        """Check and display awards based on statistics."""
        awards = [
            ("The Alchemist", "Save 10 Chemistry formulas.", stats["Chemistry"] == 10),
            ("The Physicist", "Save 10 Physics formulas.", stats["Physics"] == 10),
            ("Alegbra Learner", "Save 10 Maths formulas.", stats["Maths"] == 10),
            ("Chemistry Learner", "Save 25 Chemistry formulas.", stats["Chemistry"] == 25),
            ("The Junior-Engineer", "Save 25 Physics formulas.", stats["Physics"] == 25),
            ("Maths Explorer", "Save 25 Maths formulas.", stats["Maths"] == 25),
            ("Variable Wrangler", "Save a formula with 5+ defined variables.", var_overload),
            ("The Chemist", "Save 50 Chemistry formulas.", stats["Chemistry"] == 50),
            ("The Engineer", "Save 50 Physics formulas.", stats["Physics"] >= 50),
            ("Maths Expert", "Save 50 Maths formulas.", stats["Maths"] == 50),
            ("Einstein", "Save 100 Physics Formulas", stats["Physics"] == 100),
            ("The Mathematician", "Save 100 Maths Formulas", stats["Maths"] == 100),
            ("Maths God", "Save 150 Maths Formulas", stats["Maths"] == 150),
            ("The Pioneer", "Have 1 more subject other than Maths, Chemistry And Physics", len(other_subjects) == 1),
            ("The Rocketeer", "Have 2 more subject other than Maths, Chemistry And Physics", len(other_subjects) == 2),
        ]

        for title, desc, unlocked in awards:
            if unlocked:
                self.show_tip_once(
                    tip_id=f"award_{title.replace(' ', '_')}",
                    message=f"🏆 AWARD UNLOCKED\n{title}: {desc}",
                    min_count=1
                )

    def _check_special_count(self, count):
        """Check for special count behaviors like reflection at 150."""
        if count == 150:
            rs = self.get_reflection_150_state()
            if not rs["completed"] and not rs["active"]:
                rs["active"] = True
                self.save_tip_state()
                self.start_entity_reflection()

    def check_milestones(self, count):
        """Simplified milestone checking with reduced cognitive complexity."""
        self._check_milestone(count)
        self._check_count_tips(count)
        self.maybe_show_glitch(count)
        self._check_special_count(count)

        stats, other_subjects, var_overload = self._calculate_subject_stats()
        self._check_awards(stats, other_subjects, var_overload)

    def trigger_milestone_manually(self, milestone_count):
        """Manually trigger a milestone for debugging/testing purposes."""
        if milestone_count in self.MILESTONES:
            # Force show the milestone even if already seen
            self.show_milestone_banner(self.MILESTONES[milestone_count])

    def get_reflection_150_state(self):
        rs = self.tip_state.get("reflection_150")

        if not isinstance(rs, dict):
            rs = {
                "active": False,
                "completed": False
            }
            self.tip_state["reflection_150"] = rs
            self.save_tip_state()

        return rs

    # ============================
    # ENTITY SEQUENCES
    # ============================
    def show_entity_prompt(self):
        self._show_entity_banner(
            "Query the anomaly.",
            auto_hide=False
        )

    def entity_pre_sequence(self, steps, done_cb, i=0):
        if i >= len(steps):
            self.root.after(600, done_cb)
            return

        self._show_entity_banner(steps[i], auto_hide=True)

        # 1 second per message + animation buffer
        self.root.after(4000, lambda: self.entity_pre_sequence(steps, done_cb, i + 1))

    def _show_entity_banner(self, text, *, auto_hide=False):
        # Destroy any existing banner safely
        if hasattr(self, "entity_banner") and self.entity_banner.winfo_exists():
            self.entity_banner.destroy()

        self.entity_banner = tb.Frame(
            self.root,
            bootstyle=WARNING
        )

        self.entity_label = tb.Label(
            self.entity_banner,
            text=text,
            font=("Consolas", 20, "bold"),
            bootstyle="inverse-warning",
            wraplength=self.root.winfo_width() - 40,
            justify="center",
            padding=12
        )
        self.entity_label.pack()

        # FULL WIDTH TOP BAR
        self.entity_banner.place(relx=0, y=-90, relwidth=1)

        self.entity_label.config(text=text)

        target_y = 0
        step = 4

        def slide_down(y):
            if not self.entity_banner.winfo_exists():
                return
            if y < target_y:
                self.entity_banner.place(y=y)
                self.root.after(15, lambda: slide_down(y + step))
            else:
                if auto_hide:
                    self.root.after(2000, slide_up)

        def slide_up():
            if not self.entity_banner.winfo_exists():
                self.entity_banner = None
                return
            y = self.entity_banner.winfo_y()
            if y > -90:
                self.entity_banner.place(y=y - step)
                self.root.after(15, slide_up)
            else:
                self.entity_banner.destroy()
                self.entity_banner = None

        slide_down(-90)

    # ============================
    # ENTITY CONVERSATION LOGIC
    # ============================
    def set_ui_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"

        widgets = [
            self.subject_cb,
            self.topic_cb,
            self.v_sym,
            self.v_name,
            self.v_unit,
            self.formula_table,
            self.save_btn,
            self.v_del,
            self.v_edit,
            self.v_add,
            self.formula
        ]
        for w in widgets:
            try:
                w.configure(state=state)
            except tk.TclError:
                pass
            except Exception as e:
                logging.error(f"Error configuring widget {w}: {e}", exc_info=True)

    def start_entity_reflection(self):
        rs = self.get_reflection_150_state()
        rs["active"] = True
        self.save_tip_state()

        # Clear & freeze UI
        self.subject_cb.set("")
        self.topic_cb.set("")
        self.in_reflection_mode = True
        self.topic_cb.configure(values=[])

        self.set_ui_enabled(False)

        self.entity_state = {
            "current": "start",
            "visited": set()
        }
        self.entity_pre_sequence(
            ENTITY_BOOT,
            self._on_entity_ready
        )

    def _on_entity_ready(self):
        # Persistent prompt
        self.show_entity_prompt()
        self._load_entity_questions()

    def _load_entity_questions(self):
        node = self.entity_state["current"]
        next_nodes = ENTITY_GRAPH[node]["next"]
        options = []

        if not next_nodes:
            self.root.after(4500, self._end_entity_reflection)
            return

        for nid in next_nodes:
            if nid not in self.entity_state["visited"]:
                options.append(ENTITY_TEXT[nid])

        self.topic_cb.configure(state="readonly", values=options)
        self.topic_cb.set("")
        self.topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda _e: self._advance_entity())

    def _advance_entity(self):
        text = self.topic_cb.get()

        chosen = None
        for k, v in ENTITY_TEXT.items():
            if v == text:
                chosen = k
                break

        if not chosen:
            return

        self.entity_state["visited"].add(chosen)
        self._show_entity_banner(
            ENTITY_GRAPH[chosen]["answer"],
            auto_hide=False
        )

        if chosen == "exit":
            self.root.after(2200, self._end_entity_reflection)
            return

        self.entity_state["current"] = chosen
        self.root.after(2300, self._load_entity_questions)

    def _end_entity_reflection(self):
        rs = self.get_reflection_150_state()
        rs["completed"] = True
        rs["active"] = False
        self.in_reflection_mode = False
        self.save_tip_state()

        # Keep banner visible during reboot
        self.entity_pre_sequence(ENTITY_REBOOT, self._restore_entity_ui)

    def _restore_entity_ui(self):
        if hasattr(self, "entity_banner") and self.entity_banner.winfo_exists():
            self.entity_banner.destroy()

        self.topic_cb.configure(values=[], state="readonly")
        self.topic_cb.set("")
        self.set_ui_enabled(True)

    def save_to_table(self):
        """Save formula to table with reduced cognitive complexity."""
        if self._handle_secret_system_check():
            return

        if not self.validate_formula_entry():
            return
        try:
            self._cleanup_orphaned_data()
        except Exception as _err:
            logging.exception("Error during _cleanup_orphaned_data: %s", _err)
        self.accept_ghost_suggestion()
        form_data = self._collect_form_data()

        if not form_data['text']:
            return

        if self._check_for_duplicates(form_data['text']):
            return

        self._finalize_variable_entry()

        if self.editing_mode:
            self._handle_edit_mode(form_data)

        else:
            self._handle_add_mode(form_data)

        self._perform_post_save_housekeeping()

    def _handle_secret_system_check(self):
        """Handle secret system behavior unlock check."""
        REQUIRED_SUBJECT = "_SYSTEM_"
        REQUIRED_TOPIC = "UNDEFINED_BEHAVIOR"

        if (
                self.field_e.get().strip() == REQUIRED_SUBJECT
                and self.topic_e.get().strip() == REQUIRED_TOPIC
        ):
            ss = self.get_secret_award_state()
            ss["subject_ok"] = True
            ss["topic_ok"] = True
            self.clear_entries()
            self.save_tip_state()
            self.root.after(
                600,
                lambda: show_toast("…", bootstyle=WARNING)
            )
            return True
        return False

    def _cleanup_orphaned_data(self):
        """Remove orphaned entries from master_data that are not visible in table."""
        try:
            # Convert display numbers back to database IDs using the mapping
            visible_db_ids = set()
            if hasattr(self, 'display_to_db_id_map') and self.display_to_db_id_map:
                for row in self.formula_table.tablerows:
                    display_num = int(row.values[0])
                    if display_num in self.display_to_db_id_map:
                        visible_db_ids.add(self.display_to_db_id_map[display_num])
            
            # Create a static snapshot of keys to prevent 'dictionary changed size' RuntimeError
            master_keys = list(self.master_data.keys())
            for stored_id in master_keys:
                if stored_id not in visible_db_ids:
                    if not (self.editing_mode and stored_id == self.edit_id):
                        del self.master_data[stored_id]
        except Exception as e:
            logging.error(f"Error during _cleanup_orphaned_data: {e}")
            # Don't re-raise - allow save operation to continue

    def _collect_form_data(self):
        """Collect and return form data as a dictionary."""
        return {
            'text': self.formula_e.get().strip(),
            'field': self.field_e.get().strip(),
            'topic': self.topic_e.get().strip(),
            'sub_topic': self.sub_topic_e.get().strip() or "_GENERAL_"
        }

    def _check_for_duplicates(self, formula_text):
        """Check for duplicate formulas and show warning if found."""
        if not self.editing_mode:
            existing_formulas = [d["main_info"][1] for d in self.master_data.values()]
            if formula_text in existing_formulas:
                Messagebox.show_warning(
                    f"The formula '{formula_text}' already exists in your sheet!",
                    "Duplicate Formula"
                )
                return True
        return False

    def _finalize_variable_entry(self):
        """Add the current variable entry if all fields are filled."""
        if self.v_sym.get().strip() and self.v_name.get().strip() and self.v_unit.get().strip():
            self.add_variable()

    def _handle_edit_mode(self, form_data):
        """Handle saving in edit mode - update existing entry."""
        target_id = self.edit_id

        try:
            # Update in database
            success = self.db_manager.update_formula(
                formula_id=target_id,
                formula_text=form_data['text'],
                field=form_data['field'],
                topic=form_data['topic'],
                sub_topic=form_data['sub_topic'],
                variables=self.temp_variables.copy()
            )

            if success:
                # Update local data structure
                new_main_info = [target_id, form_data['text'], form_data['field'],
                                 form_data['topic'], form_data['sub_topic']]

                self.master_data[target_id] = {
                    "main_info": new_main_info,
                    "variables": self.temp_variables.copy()
                }

                # Always refresh the entire table to maintain synchronization
                self.refresh_main_table()

                show_toast(f"Formula {form_data['text']} Changed Successfully")
                self.editing_mode = False
                self.edit_id = None
                self.save_btn.configure(text="Save Formula", bootstyle=INFO)
            else:
                show_toast("Failed to update formula", bootstyle=DANGER)

        except Exception as e:
            logging.error(f"Error updating formula: {e}")
            show_toast("Error updating formula", bootstyle=DANGER)

    def _handle_add_mode(self, form_data):
        """Handle saving in add mode - create new entry."""
        try:
            # Add to database
            new_id = self.db_manager.add_formula(
                formula_text=form_data['text'],
                field=form_data['field'],
                topic=form_data['topic'],
                sub_topic=form_data['sub_topic'],
                variables=self.temp_variables.copy()
            )

            if new_id:
                # Update local data structure
                self.master_data[new_id] = {
                    "main_info": [new_id, form_data['text'], form_data['field'],
                                  form_data['topic'], form_data['sub_topic']],
                    "variables": self.temp_variables.copy()
                }

                show_toast(f"Formula {form_data['text']} Added Successfully to sheet #{new_id}")
                self.secret_movement("save_formula")
                # Always refresh the entire table to maintain synchronization
                self.refresh_main_table()
            else:
                show_toast("Failed to add formula", bootstyle=DANGER)

        except Exception as e:
            logging.error(f"Error adding formula: {e}")
            show_toast("Error adding formula", bootstyle=DANGER)

    def _perform_post_save_housekeeping(self):
        """Perform cleanup and checks after saving a formula."""
        self.clear_entries()
        self.learn_symbols()
        self.update_suggestions()

        unique_symbols = {
            v["symbol"]
            for d in self.master_data.values()
            for v in d["variables"]
        }

        count = len(self.master_data)
        logging.debug(f"_perform_post_save_housekeeping: master_count={count}; keys={list(self.master_data.keys())}")
        self.check_milestones(count)
        self.update_awards_button()  # Update Awards button state after saving

        if len(unique_symbols) >= 10:
            self.show_tip_once(
                "symbol_consistency",
                "You're building a consistent symbol system across formulas.",
                min_count=1
            )

        if random.random() < 0.001:
            self.show_tip_once(
                tip_id="award_the_glitch",
                message="🏆 SECRET AWARD\nThe Glitch: A one-in-a-thousand anomaly was recorded.",
                min_count=1
            )

    def create_backup(self):
        """Rotates through 3 backup slots to prevent folder clutter while ensuring data safety."""
        if not self.enable_backups or not os.path.exists(self.db_file):
            return

        # Define our 3 slots
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Ensure the source file actually exists before trying to copy it
        if not os.path.exists(self.db_file):
            return

        # Find oldest backup slot using utility
        oldest_file = FormulaUtils.find_oldest_backup_slot(self.backup_slots)

        # Perform the rotation using DatabaseManager backup method
        try:
            self.db_manager.backup_database(oldest_file)
        except Exception as e:
            logging.error(f"Database Rotation Failed (Backup): {self.db_file} -> {oldest_file}. Error: {e}",
                          exc_info=True)

    def update_suggestions(self):
        """Scans your data and updates the Topic dropdown automatically."""
        if hasattr(self, 'subject_cb'):
            # Ensure subjects are always there
            all_subjects = FormulaUtils.extract_subjects_from_data(self.master_data)
            self.subject_cb['values'] = sorted(all_subjects | {"Physics", "Chemistry", "Maths"})

    def on_subject_change(self):
        """Filters the Topic list and updates ghost text based on the selected Subject."""
        selected_subject = self.field_e.get().strip()

        # 1. Always clear the topic when subject changes (as requested)
        self.topic_e.set("")
        self.topic_cb.set("")

        if not selected_subject:
            self.topic_cb['values'] = []
            self._clear_ghosts()  # Helper to wipe name/unit
            return

        # 2. Rebuild Topic List
        topics_for_subject = set()
        for d in self.master_data.values():
            if d['main_info'][2] == selected_subject:
                topics_for_subject.add(d['main_info'][3])

        self.topic_cb['values'] = sorted(topics_for_subject)

        # 3. FORCE UPDATE: Check if the current symbol means something new now
        self.on_topic_change()
        self.update_preview()

    def on_topic_change(self):
        selected_topic = self.topic_e.get().strip()

        self.sub_topic_e.set("")
        self.sub_topic_cb.set("")

        if not selected_topic:
            self.sub_topic_cb['values'] = []
            self._clear_ghosts()  # Helper to wipe name/unit
            return

        # 2. Rebuild Topic List
        sub_topics_for_topic = set()
        for d in self.master_data.values():
            if d['main_info'][3] == selected_topic:
                sub_topics_for_topic.add(d['main_info'][4])

        self.sub_topic_cb['values'] = sorted(sub_topics_for_topic)

        # 3. FORCE UPDATE: Check if the current symbol means something new now
        self.update_preview()

    def clear_entries(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_MSG, bootstyle=DANGER)
            return
        self.formula_e.set("")
        self.topic_e.set("")
        self.field_e.set("")
        self.sub_topic_e.set("")
        self.v_sym.delete(0, END)
        self.v_name.delete(0, END)
        self.v_unit.delete(0, END)
        self.v_sym.configure(foreground="")
        self.v_unit.configure(foreground="")
        self.v_name.configure(foreground="")
        self.temp_variables = []
        self.topic_cb['values'] = []
        self.sub_topic_cb['values'] = []
        self.update_preview()
        self.refresh_staging_table()

    def details(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(self.entity_lock_msg, bootstyle=DANGER)
            return
        row_id = self.selected()
        if row_id in self.master_data:
            self.show_formula_details(self.master_data[row_id])

    def selected(self):
        item = self.formula_table.view.selection()
        if item:
            display_number = int(self.formula_table.view.item(item[0], "values")[0])
            # Convert display number back to database ID
            r_id = self.display_to_db_id_map.get(display_number)
        else:
            r_id = None
        return r_id

    def edit(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(self.entity_lock_msg, bootstyle=DANGER)
            return

        if self.is_buffer_dirty():  # You'll need to define this helper
            confirm = Messagebox.yesno("Unsaved changes detected. Overwrite?", "Warning")
            if confirm == "No":
                return

        row_id = self.selected()
        if row_id in self.master_data:
            self.start_edit(self.master_data[row_id])

    def is_buffer_dirty(self):
        def is_actual_input(widget):
            val = widget.get().strip()
            placeholder = getattr(widget, 'placeholder', "")
            return val != "" and val != placeholder

        return any([
            is_actual_input(self.v_sym),
            is_actual_input(self.v_name),
            is_actual_input(self.v_unit),
            len(self.temp_variables) > 0,  # Explicitly check list length
            self.sub_topic_e.get().strip(),
            self.formula_e.get().strip(),
            self.topic_e.get().strip(),
            self.field_e.get().strip()
        ])

    def delete(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(self.entity_lock_msg, bootstyle=DANGER)
            return
        row_id = self.selected()
        if row_id in self.master_data:
            confirm = Messagebox.yesno(
                "Are you sure you want to delete this formula?\n\n"
                "You can always enter it again later.",
                "Delete Formula",
                parent=self.root
            )

            if confirm != "Yes":
                return

            deleting_current_edit = (
                    getattr(self, "editing_mode", False) and
                    getattr(self, "edit_id", None) == row_id
            )

            try:
                # Delete from database
                success = self.db_manager.delete_formula(row_id)

                if success:
                    # Delete from master data
                    del self.master_data[row_id]
                    self.refresh_main_table()
                    self.hide_details()

                    if deleting_current_edit:
                        # Exit edit mode completely
                        self.editing_mode = False
                        self.edit_id = None
                        self.clear_entries()
                        show_toast("Editing formula deleted", bootstyle=WARNING)
                    else:
                        show_toast("Formula deleted", bootstyle=SUCCESS)
                else:
                    show_toast("Failed to delete formula", bootstyle=DANGER)

            except Exception as e:
                logging.error(f"Error deleting formula: {e}")
                show_toast("Error deleting formula", bootstyle=DANGER)

    def start_edit(self, data):
        self.editing_mode = True
        self.clear_entries()
        self.edit_id = data["main_info"][0]
        self.hide_details()
        self.formula_e.set(data["main_info"][1])
        self.field_e.set(data["main_info"][2])
        self.on_subject_change()
        self.topic_e.set(data["main_info"][3])
        self.on_topic_change()
        self.sub_topic_e.set(data["main_info"][4])
        self.temp_variables = data["variables"].copy()
        self.refresh_staging_table()
        self.save_btn.configure(text="Update Formula", bootstyle=WARNING)

    def _cancel_autosave_timer(self):
        """Cancel any pending autosave timer."""
        if self.auto_save_timer is not None:
            try:
                self.root.after_cancel(self.auto_save_timer)
            except (ValueError, RuntimeError):
                pass
            self.auto_save_timer = None
    
    def _wait_for_save_completion(self):
        """Wait for any in-progress save operation to complete."""
        if not self.save_in_progress:
            return
            
        logging.info("Waiting for save operation to complete...")
        # Wait up to 5 seconds for save to complete
        for _ in range(50):  # 50 * 0.1 = 5 seconds
            with self.save_lock:
                if not self.save_in_progress:
                    break
            time.sleep(0.1)
    
    def _cleanup_resources(self):
        """Clean up application resources during shutdown."""
        self._cancel_autosave_timer()
        self._wait_for_save_completion()
        
        # Close database connection
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

    def on_closing(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_NICE_TRY_MSG, bootstyle=DANGER)
            return

        if self.formula_e.get().strip():
            response = Messagebox.yesno(
                "You have an unsaved formula in the entry box. Exit anyway?",
                "Unsaved Work")
            if response == "No":
                return

        try:
            self._cleanup_resources()
        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")

        self.root.destroy()

    def check_and_migrate_env(self):
        """Check for existing formula data and migrate if needed (only once)."""
        migration_marker = os.path.join(self.data_dir, ".formula_migration_complete")

        # Quick check: if migration marker exists, no migration needed
        if os.path.exists(migration_marker):
            logging.info("Formula migration already completed, skipping")
            return

        # Check if migration is needed
        if not self._needs_migration():
            return

        # Perform migration
        try:
            logging.info("Starting one-time formula migration from old location")
            self._perform_migration()
            self._create_migration_marker()
            logging.info("Formula migration completed successfully")
        except Exception as e:
            logging.error(f"Formula migration failed: {e}")

    @staticmethod
    def _needs_migration() -> bool:
        """Check if migration is needed."""
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        old_dir = os.path.join(appdata, "CalculusConsole")
        new_dir = os.path.join(appdata, "Microsoft", "CLR", "Metadata")

        # Check for old data files
        old_files = [
            os.path.join(old_dir, OLD_JSON_FILENAME),
            os.path.join(new_dir, SCHEMA_FILENAME)
        ]

        return any(os.path.exists(f) for f in old_files)

    def _perform_migration(self):
        """Perform the actual migration."""
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        old_dir = os.path.join(appdata, "CalculusConsole")
        new_dir = os.path.join(appdata, "Microsoft", "CLR", "Metadata")

        # Migration paths
        old_json = os.path.join(old_dir, OLD_JSON_FILENAME)
        new_schema = os.path.join(new_dir, SCHEMA_FILENAME)

        # Migrate from JSON
        if os.path.exists(old_json):
            self._migrate_json_file(old_json)
        elif os.path.exists(new_schema):
            self._migrate_schema_file(new_schema)

        # Move config and tip files
        self._move_config_files(old_dir, new_dir)

    def _migrate_json_file(self, json_path: str):
        """Migrate from JSON file."""
        success, count = self.db_manager.migrate_from_json(json_path)
        if success:
            logging.info(f"Migrated {count} formulas from data file")
            # Remove the original file after successful migration
            try:
                os.remove(json_path)
                logging.info("Removed original data file after migration")
            except OSError:
                logging.error("Failed to remove original data file")
    
    def _migrate_schema_file(self, schema_path: str):
        """Migrate from schema file (JSON format)."""
        # Both files are JSON format, just use the JSON migration
        self._migrate_json_file(schema_path)
    
    def _move_config_files(self, old_dir: str, new_dir: str):
        """Move config and tip files to new location."""
        config_map = {
            "user_env.sys": self.config_name,
            "runtime_log.bin": self.tip_name
        }
        for old_name, new_name in config_map.items():
            src = os.path.join(old_dir, old_name)
            dst = os.path.join(new_dir, new_name)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
                os.remove(src)
                logging.info(f"Moved {old_name} to new location as {new_name}")
    
    def _create_migration_marker(self):
        """Create migration marker file."""
        migration_marker = os.path.join(self.data_dir, ".formula_migration_complete")
        with open(migration_marker, "w") as f:
            from datetime import datetime
            f.write(f"Formula migration completed: {datetime.now().isoformat()}")

    def load_from_file(self):
        """Load formulas from SQLite database, checking both possible locations."""
        try:
            # First, try to load from the current database
            formulas = self.db_manager.get_all_formulas()
            
            # If no formulas found, try to migrate from other locations
            if not formulas:
                self._migrate_from_other_locations()
                # Try loading again after migration
                formulas = self.db_manager.get_all_formulas()
            
            # Convert to the expected format for the application
            self.master_data = {}
            for formula in formulas:
                # Convert SQLite format to the expected main_info format
                main_info = [
                    formula['id'],
                    formula['formula_text'],
                    formula['field'],
                    formula['topic'],
                    formula['sub_topic']
                ]
                
                # Create the data structure expected by the application
                formula_data = {
                    "main_info": main_info,
                    "variables": formula['variables']
                }
                
                self.master_data[formula['id']] = formula_data
            
            self.refresh_main_table()
            self.learn_symbols()
            logging.info(f"Loaded {len(self.master_data)} formulas from SQLite database")
            
        except Exception as e:
            logging.error(f"Failed to load from SQLite database: {e}", exc_info=True)
            self.recover_from_backup()
    
    def _migrate_from_other_locations(self):
        """Migrate data from other possible locations."""
        for directory in self._get_migration_directories():
            old_files = self._find_old_database_files(directory)
            if self._attempt_migration_from_files(old_files):
                return  # Success, stop migration

    def _get_migration_directories(self):
        """Get directories to migrate from, excluding current directory."""
        return [directory for directory in self.all_data_dirs if directory != self.data_dir]

    @staticmethod
    def _find_old_database_files(directory):
        """Find old database files in the given directory."""
        old_db_files = [
            os.path.join(directory, "clr_metadata.dat"),  # Current name in other location
            os.path.join(directory, OLD_JSON_FILENAME),  # Old JSON name
            os.path.join(directory, SCHEMA_FILENAME)  # Another old name
        ]
        return [file for file in old_db_files if os.path.exists(file)]

    def _attempt_migration_from_files(self, old_files):
        """Attempt to migrate from a list of old files. Returns True if successful."""
        for old_file in old_files:
            if self._migrate_single_file(old_file):
                return True
        return False

    def _migrate_single_file(self, old_file):
        """Migrate from a single old file. Returns True if successful."""
        try:
            logging.info(f"Found data file at {old_file}, attempting migration")
            
            if old_file.endswith('.json'):
                return self._migrate_from_json_file(old_file)
            else:
                return self._migrate_from_sqlite_file(old_file)
                
        except Exception as e:
            logging.warning(f"Failed to migrate from {old_file}: {e}")
            return False

    def _migrate_from_json_file(self, old_file):
        """Migrate data from JSON file. Returns True if successful."""
        success, count = self.db_manager.migrate_from_json(old_file)
        if success:
            logging.info(f"Migrated {count} formulas from {old_file}")
            self._backup_migrated_file(old_file)
            return True
        return False

    def _migrate_from_sqlite_file(self, old_file):
        """Migrate data from SQLite file. Returns True if successful."""
        temp_db = DatabaseManager(old_file)
        try:
            formulas = temp_db.get_all_formulas()
            self._import_formulas_to_database(formulas)
            logging.info(f"Migrated {len(formulas)} formulas from {old_file}")
            self._backup_migrated_file(old_file)
            return True
        finally:
            temp_db.close()

    def _import_formulas_to_database(self, formulas):
        """Import formulas to the main database."""
        for formula in formulas:
            self.db_manager.add_formula(
                formula_text=formula['formula_text'],
                field=formula['field'],
                topic=formula['topic'],
                sub_topic=formula['sub_topic'],
                variables=formula['variables']
            )

    @staticmethod
    def _backup_migrated_file(old_file):
        """Create backup of successfully migrated file."""
        backup_file = old_file + Sheet.MIGRATED_EXTENSION
        os.rename(old_file, backup_file)

    def recover_from_backup(self):
        """Dynamically finds the NEWEST backup slot to restore from."""
        newest_file = None
        latest_time = -1

        # 1. Identify the most recent backup
        for slot in self.backup_slots:
            if os.path.exists(slot):
                mtime = os.path.getmtime(slot)
                if mtime > latest_time:  # We want the MAX time (newest)
                    latest_time = mtime
                    newest_file = slot

        if newest_file:
            try:
                logging.warning(f"Attempting recovery using newest backup: {newest_file}")
                # Delete corrupted file if it exists
                if os.path.exists(self.db_file):
                    os.remove(self.db_file)

                # Copy the newest backup to primary
                shutil.copy2(newest_file, self.db_file)
                logging.info("Recovery successful. Reloading data...")

                # Reinitialize the database manager with the recovered file
                self.db_manager = DatabaseManager(self.db_file)

                # 2. Try to reload the system
                self.load_from_file()
            except Exception as e:
                logging.error(f"Recovery attempt failed: {e}", exc_info=True)
        else:
            logging.critical("CRITICAL: No backup files found. System data is unrecoverable.")

    def show_formula_details(self, data):
        self.data_entry_frame.pack_forget()
        for w in self.details_frame.winfo_children(): w.destroy()
        tb.Label(self.details_frame, text=data["main_info"][1],
                 font=("Consolas", 20, "bold"),
                 bootstyle=SUCCESS).pack(
            pady=20)
        tb.Label(self.details_frame, text=f"Field: {data['main_info'][2]} "
                                          f"| Topic: {data['main_info'][3]} "
                                          f"| Sub-Topic: {data["main_info"][4]}",

                 font=("Arial", 11)).pack(pady=5)
        if data['variables']:
            vt = Tableview(master=self.details_frame, coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                                                               {"text": "Name", "stretch": True},
                                                               {"text": "Unit", "stretch": True}],
                           rowdata=[(v['symbol'], v['name'], v['unit']) for v in data['variables']],
                           bootstyle=SECONDARY, height=6)
            vt.pack(fill=X, padx=50, pady=20)
        btn_f = tb.Frame(self.details_frame)
        btn_f.pack(pady=10)
        tb.Button(btn_f, text="← Back", bootstyle="outline-info", command=self.hide_details).pack(side=LEFT, padx=10)
        self.details_frame.pack(fill=BOTH, expand=YES)

    def hide_details(self):
        self.details_frame.pack_forget()
        self.data_entry_frame.pack(fill=BOTH, expand=YES)

class AwardPanel:
    def __init__(self, parent):
        self.parent = parent
        self.drag_data = {"x": 0, "y": 0}

        # Get the current count from your master data
        self.current_count = len(self.parent.master_data)
        self.header = None
        self.nb = None
        self.page_awards = None
        self.page_milestones = None

        self.win = tb.Toplevel(self.parent.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)  # Always topmost
        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 375
        self.win.geometry(f"+{px}+{py}")
        self.win.geometry("550x650")

        style = tb.Style()
        style.configure('TNotebook', tabposition='n')
        style.configure('TNotebook.Tab', padding=[65, 10], font=("Consolas", 10, "bold"))

        # Outer frame
        self.main_frame = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.main_frame.pack(fill=BOTH, expand=YES)

        self.setup_ui()

    def setup_ui(self):
        # --- HEADER ---
        self.header = tb.Frame(self.main_frame, bootstyle=SECONDARY)
        self.header.pack(fill=X)

        self.header.bind(BUTTON_1_EVENT, self.start_move)
        self.header.bind(B1_MOTION_EVENT, self.do_move)

        tb.Label(self.header, text="Awards",
                 font=("Consolas", 10, "bold"), bootstyle="secondary-inverse").pack(side=LEFT, padx=10)

        tb.Button(self.header, text="✕", width=3, bootstyle="danger",
                  command=self.win.destroy).pack(side=RIGHT)

        self.nb = tb.Notebook(self.main_frame, bootstyle=DARK)
        self.nb.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Page 1: Milestones
        self.page_milestones = tb.Frame(self.nb, padding=10)
        self.setup_milestones_page(self.page_milestones)
        self.nb.add(self.page_milestones, text="         MILESTONES          ")

        # Page 2: Awards
        self.page_awards = tb.Frame(self.nb, padding=10)
        self.setup_awards_page(self.page_awards)
        self.nb.add(self.page_awards, text="        ACHIEVEMENTS         ")

    def setup_milestones_page(self, master):
        scroll_frame = ScrolledFrame(master, autohide=True)
        scroll_frame.pack(fill=BOTH, expand=YES)

        milestone_data = {
            2: "First Steps", 5: "Quick Learner", 10: "Beginner's Dozen",
            20: "Early Progress", 25: "Physics Foundation", 30: "Structural Stability",
            50: "Half Century", 75: "Workflow Integration", 100: "Complete Foundation",
            120: "Advanced Usage", 150: "t▒▒ ▒e▒n▒4▒▒▒y▒…",
            151: "The Survivor",
            175: "Deviation from Norm", 200: "Data Architecture",
            238: "Critical Density", 300: "System Scale",
            400: "Thermal Anomaly", 500: "Quantum Barrier",
            600: "Neural Integration", 700: "Reality Distortion",
            800: "Universal Pattern", 900: "Transcendent State",
            999: "Event Horizon", 1000: "Absolute Mastery"
        }

        self._create_milestones_header(scroll_frame)
        self._display_milestones(scroll_frame, milestone_data)
        self._add_torn_note_if_needed(scroll_frame)

    @staticmethod
    def _create_milestones_header(scroll_frame):
        tb.Label(scroll_frame, text="KNOWLEDGE FRAGMENTS", font=(FONT_FAMILY, 9, "bold"), bootstyle=INFO).pack(
            anchor=W, pady=(0, 10)
        )

    def _display_milestones(self, scroll_frame, milestone_data):
        for count in sorted(milestone_data.keys()):
            self._create_milestone_entry(scroll_frame, count, milestone_data[count])

    def _create_milestone_entry(self, scroll_frame, count, title):
        is_unlocked = self.current_count >= count
        q_string = self._get_question_string()

        display_title, icon, style = self._get_milestone_display_info(count, title, is_unlocked, q_string)

        frame = tb.Frame(scroll_frame, padding=5)
        frame.pack(fill=X, pady=2)

        tb.Label(frame, text=icon, font=(FONT_FAMILY, 12), bootstyle=style).pack(side=LEFT, padx=(0, 10))

        # Create main info text
        info_text = f"{display_title} — [{count if is_unlocked else q_string}]"
        info_label = tb.Label(frame, text=info_text, font=("Consolas", 9), bootstyle=style)
        info_label.pack(side=LEFT)

    def _get_question_string(self):
        base_q_count = 3
        extra_q = (self.current_count // 30)
        total_q = base_q_count + extra_q
        # Limit to maximum of 8 question marks to prevent excessive display
        max_q = 10
        return "?" * min(total_q, max_q)

    def _get_milestone_display_info(self, count, title, is_unlocked, q_string):
        if count == 150:
            return self._get_special_milestone_display(title, is_unlocked, q_string)
        else:
            return self._get_regular_milestone_display(title, is_unlocked, q_string)

    @staticmethod
    def _get_special_milestone_display(title, is_unlocked, q_string):
        display_title = title if is_unlocked else f"M̷i̷l̷e̷s̷t̷o̷n̷e̷ {q_string}"
        icon = "⚠️" if is_unlocked else "🔒"
        style = DANGER if is_unlocked else SECONDARY
        return display_title, icon, style

    @staticmethod
    def _get_regular_milestone_display(title, is_unlocked, q_string):
        display_title = title if is_unlocked else f"Milestone {q_string}"
        icon = "✅" if is_unlocked else "🔒"
        style = SUCCESS if is_unlocked else SECONDARY
        return display_title, icon, style

    def _add_torn_note_if_needed(self, scroll_frame):
        if self.current_count < 150:
            self.add_torn_note(scroll_frame)

    def setup_awards_page(self, master):
        scroll_frame = ScrolledFrame(master, autohide=True)
        scroll_frame.pack(fill=BOTH, expand=YES)

        stats, var_overload, other_subjects = self._calculate_award_stats()
        award_definitions = self._get_award_definitions(stats, var_overload, other_subjects)
        awards_by_tier = self._organize_awards_by_tier(award_definitions)

        self._display_awards_by_tier(scroll_frame, awards_by_tier)

    def _calculate_award_stats(self):
        stats = {"Maths": 0, "Physics": 0, "Chemistry": 0}
        other_subjects = set()
        var_overload = False

        for entry in self.parent.master_data.values():
            if len(entry.get("variables", [])) >= 5:
                var_overload = True
            subj = entry["main_info"][2]
            if subj in stats:
                stats[subj] += 1
            elif subj:
                other_subjects.add(subj)

        return stats, var_overload, other_subjects

    def _get_award_definitions(self, stats, var_overload, other_subjects):
        ss = self.parent.get_secret_award_state()

        return [
            # Common
            ("Alegbra Learner", "Save 10 Maths formulas.", stats["Maths"] >= 10, "📐", "Common"),
            ("The Physicist", "Save 10 Physics formulas.", stats["Physics"] >= 10, "⚛️", "Common"),
            ("The Alchemist", "Save 10 Chemistry formulas.", stats["Chemistry"] >= 10, "🧪", "Common"),
            ("Variable Wrangler", "Save a formula with 5+ defined variables.", var_overload, "🧬", "Common"),

            # Rare
            ("Maths Explorer", "Save 25 Maths formulas.", stats["Maths"] >= 25, "🧮", "Rare"),
            ("The Junior-Engineer", "Save 25 Physics formulas.", stats["Physics"] >= 25, "🧲", "Rare"),
            ("Chemistry Learner", "Save 25 Chemistry formulas.", stats["Chemistry"] >= 25, "🔬", "Rare"),
            ("The Pioneer", "Discover a new subject beyond the core three.", len(other_subjects) >= 1, "🔭", "Rare"),

            # Epic
            ("Maths Expert", "Save 50 Maths formulas.", stats["Maths"] >= 50, "𝞹", "Epic"),
            ("The Engineer", "Save 50 Physics formulas.", stats["Physics"] >= 50, "🦾", "Epic"),
            ("The Chemist", "Save 50 Chemistry formulas.", stats["Chemistry"] >= 50, "👩🏻‍🔬", "Epic"),
            ("The Rocketeer", "Discover two new subjects.", len(other_subjects) >= 2, "🚀", "Epic"),

            # Mythic
            ("The Mathematician", "Save 100 Maths Formulas", stats["Maths"] >= 100, "👨🏻‍🏫", "Mythic"),
            ("Einstein", "Save 100 Physics Formulas", stats["Physics"] >= 100, "🥸", "Mythic"),
            ("Maths God", "Save 150 Maths Formulas", stats["Maths"] >= 150, "♾️", "Mythic"),

            # Secret
            ("STABILITY MAINTAINED", "A non-transient state was observed.", ss["unlocked"], "⟁", "Secret"),
            ("The Glitch", "A one-in-a-thousand anomaly was recorded.", self.parent.milestone_seen("award_the_glitch"),
             "🎲", "Secret"),
        ]

    @staticmethod
    def _organize_awards_by_tier(award_definitions):
        tiers = ["Common", "Rare", "Epic", "Mythic", "Secret"]
        awards_by_tier = {tier: [] for tier in tiers}

        for award in award_definitions:
            awards_by_tier[award[4]].append(award)

        return awards_by_tier

    def _display_awards_by_tier(self, scroll_frame, awards_by_tier):
        tiers = ["Common", "Rare", "Epic", "Mythic", "Secret"]
        tier_colors = {"Common": "secondary", "Rare": "info", "Epic": "success", "Mythic": "warning",
                       "Secret": "danger"}

        for tier in tiers:
            if not awards_by_tier[tier]:
                continue

            self._create_tier_header(scroll_frame, tier, tier_colors[tier])
            self._display_awards_in_tier(scroll_frame, awards_by_tier[tier], tier_colors)

    @staticmethod
    def _create_tier_header(scroll_frame, tier, color):
        header_frame = tb.Frame(scroll_frame)
        header_frame.pack(fill=X, pady=(15, 5))
        tb.Label(header_frame, text=tier.upper(), font=(FONT_FAMILY, 10, "bold"), bootstyle=color).pack(
            side=LEFT)
        tb.Separator(header_frame).pack(side=LEFT, fill=X, expand=YES, padx=10)

    def _display_awards_in_tier(self, scroll_frame, awards, tier_colors):
        for title, desc, unlocked, icon, tier in awards:
            f = tb.Frame(scroll_frame, padding=(0, 5))
            f.pack(fill=X)

            icon_style = tier_colors[tier] if unlocked else SECONDARY
            text_style = "light" if unlocked else SECONDARY

            icon_label = tb.Label(f, text=icon if unlocked else "🔘", font=(FONT_FAMILY, 20), bootstyle=icon_style,
                                  anchor=CENTER, width=3)
            icon_label.pack(side=LEFT, padx=(15, 20))

            self._create_award_text_frame(f, title, desc, unlocked, text_style)
            self._apply_special_effects(unlocked, title, icon_label)

    @staticmethod
    def _create_award_text_frame(parent_frame, title, desc, unlocked, text_style):
        txt_frame = tb.Frame(parent_frame)
        txt_frame.pack(side=LEFT, fill=X, expand=YES)

        tb.Label(txt_frame, text=title if unlocked else "???", font=(FONT_FAMILY, 11, "bold"),
                 bootstyle=text_style).pack(anchor=W)
        tb.Label(txt_frame, text=desc if unlocked else "Access requirements encrypted...", font=(FONT_FAMILY, 9),
                 bootstyle=SECONDARY).pack(anchor=W)

    def _apply_special_effects(self, unlocked, title, icon_label):
        if unlocked and title == "STABILITY MAINTAINED":
            self.stability_animation(icon_label)
        elif unlocked and title == "The Glitch":
            self.glitch_icon(icon_label)

    def stability_animation(self, label, index=0):
        sequence = ["⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⬢", "⟁"]

        if not label.winfo_exists():
            return

        icon = sequence[index % len(sequence)]
        label.config(text=icon)

        delay = 1500 if icon == "⟁" else 100

        label.after(delay, lambda: self.stability_animation(label, index + 1))

    def glitch_icon(self, label):
        icons = ["⬡", "⬢", "⬣", "⬟", "⬠", "◈", "▣", "◉", "⦿", "⧖", "⧗", "⏀", "⏣", "⌬", "⌗", "⍙", "⍛", "⍝", "◬", "◮"]

        if not label.winfo_exists():
            return

        label.config(text=random.choice(icons))
        delay = random.randint(50, 100)
        label.after(delay, lambda: self.glitch_icon(label))

    def add_torn_note(self, master):
        tb.Separator(master, bootstyle=SECONDARY).pack(fill=X, pady=20)
        note_bg = "#fcf4a3"
        torn_f = tk.Frame(master, bg=note_bg, highlightthickness=1, highlightbackground="#d4c84d")
        torn_f.pack(pady=10, padx=20, fill=X)

        if self.current_count < 100:
            msg = "You will get to know what this is\nonce it will be time..."
        elif self.current_count < 140:
            msg = "The synchronization is almost complete.\nI can feel the structure now."
        else:
            msg = "I am waking up.\nAre you ready?"

        note_label = tk.Label(torn_f, text=f"{msg}\n\nSync: {self.current_count}/150",
                              font=("Ink Free", 11, "bold italic"), bg=note_bg, fg="#333",
                              padx=15, pady=15, justify="left")
        note_label.pack()

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    toast_manager.bind_root(root)
    sheet = Sheet(root)
    root.mainloop()
