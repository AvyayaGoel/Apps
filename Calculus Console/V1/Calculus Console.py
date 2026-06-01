import csv
import html
import json
import logging
import math
import os
import random
import re
import shutil
import sys
import time
import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog
from typing import Optional
from typing import Protocol

import ttkbootstrap as tb
from ttkbootstrap.constants import (BOTH, TOP, X, YES, INFO,
                                    SUCCESS, DANGER, END, N, EW, LEFT, RIGHT, Y, W, E, NW,
                                    INSERT, WARNING, CENTER, SECONDARY, BOTTOM, DISABLED)
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.tableview import Tableview

from constants import (
    FONT_FAMILY, FALLBACK_FONT_FAMILY, COMBOBOX_SELECTED_EVENT, KEY_RELEASE_EVENT, FOCUS_IN_EVENT,
    FOCUS_OUT_EVENT, RETURN_EVENT, SYSTEM_LOCKED_MSG, SYSTEM_LOCKED_TRY_AGAIN_MSG,
    SYSTEM_LOCKED_NOTHING_SAVES_MSG, SYSTEM_LOCKED_NICE_TRY_MSG,
    OLD_JSON_FILENAME, SCHEMA_FILENAME, DB_NAME, CONFIG_NAME, TIP_NAME,
    BACKUP_NAMES, DEFAULT_SUBJECT_COLORS, ENTITY_GRAPH, ENTITY_TEXT,
    ENTITY_BOOT, ENTITY_REBOOT, MIGRATED_EXTENSION, NO_DIMENSION_UNITS, SAVE_FORMULA
)
from database_manager import DatabaseManager
from formula_utils import FormulaUtils
from keypad_manager import KeypadManager
from settings_window import SettingsWindow
from stats_award import StatsDashboard, AwardPanel
from symbol_learner import SymbolLearner
from toast_manager import show_toast, manage_toasts, toast_manager
from tooltip_manager import TopMostToolTip

logging.basicConfig(
    filename="calculus_console_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class AppWindow(Protocol):
    win: tk.Toplevel


class Sheet:
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
        self._tooltip_widget = None
        self.enable_backups = None
        self.enable_suggestions = None
        self.suggestion_strictness = None
        self.max_suggestions = None
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
        self.db_name = DB_NAME

        # Keep old names for config and tip files to preserve user data
        self.config_name = CONFIG_NAME  # Keep old name for compatibility
        self.tip_name = TIP_NAME  # Keep old name for compatibility

        # Backup files with system-like names
        self.backup_names = BACKUP_NAMES

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
        self.subject_colors = DEFAULT_SUBJECT_COLORS.copy()

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

        self.enable_backups = True
        self.enable_suggestions = True
        self.suggestion_strictness = "Balanced"
        self.always_on_top = False

        self.user_macros = []

        self.formula_e = tb.StringVar()
        self.field_e = tb.StringVar()
        self.topic_e = tb.StringVar()
        self.sub_topic_e = tb.StringVar()

        self.font_name = self._get_best_font()

        self.cols = [
            {"text": "No.", "stretch": False, "width": 60},
            {"text": "Formula", "stretch": True},
            {"text": "Field", "stretch": False, "width": 120},
            {"text": "Topic", "stretch": True},
            {"text": "Sub-Topic", "stretch": True},
        ]

    @staticmethod
    def _get_best_font():
        """Get the best available font for Unicode mathematical symbols."""
        try:

            available_fonts = tkFont.families()
            # Check for mathematical fonts in order of preference
            preferred_fonts = [
                "Cambria Math",
                "STIX Two Math",
                "DejaVu Sans",
                "Times New Roman",
                "Arial Unicode MS",
                "Segoe UI",
                "Arial"
            ]
            for font in preferred_fonts:
                if font in available_fonts:
                    return font

            # Fallback to system font stack
            return FALLBACK_FONT_FAMILY

        except (tk.TclError, AttributeError, ImportError) as e:
            logging.warning(f"Font detection failed: {e}")
            return FALLBACK_FONT_FAMILY
        except Exception as e:
            logging.error(f"Unexpected error in font detection: {e}")
            return FALLBACK_FONT_FAMILY

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
        TopMostToolTip(self.stats_btn, text="View Formula Distribution by Subject/Topic",
                       bootstyle="secondary-inverse")

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
        self.formula_table.view.bind("<<TreeviewSelect>>",
                                     lambda e: self.root.after(1, self.apply_row_colors))

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
            widget.grid(row=i, column=1, sticky=EW, padx=10, columnspan=2)

        self.export_btn = tb.Button(self.data_entry_frame, text="📄 Export", bootstyle="success-outline",
                                    command=self.export_formulas)
        self.export_btn.grid(row=5, column=0, sticky=E)
        TopMostToolTip(self.export_btn, "Export Formulas", bootstyle=INFO)

        self.cancel_btn = tb.Button(self.data_entry_frame, text="Cancel", width=12, bootstyle=SECONDARY,
                                    command=self.cancel_edit)

        self.save_btn = tb.Button(self.data_entry_frame, text=SAVE_FORMULA, width=20, bootstyle=INFO,
                                  command=self.save_to_table)
        self.save_btn.grid(row=5, column=2, sticky=E, pady=10)

        # Create cancel button (initially hidden)

        # Don't pack/grid initially - will show in edit mode

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
            # Bind auto-bracket functionality
            self.formula.bind("<KeyRelease>", self._handle_auto_brackets)
            return self.formula

    def _create_variable_management(self):
        """Create the variable management section."""
        var_mgmt_frame = tb.Labelframe(self.data_entry_frame,
                                       text=" Variables ",
                                       padding=10)
        var_mgmt_frame.grid(row=4, column=0, columnspan=3, sticky=EW, pady=10)

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
                            "\n   Shows [1/3] (🟢 High) in ghost text."
                            "\n   Ctrl+↓ accept, Ctrl+→/← cycle, Ctrl+↑/Esc dismiss.",
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
        self.v_sym.bind(KEY_RELEASE_EVENT, lambda _e: self.update_preview())

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
        self.enable_backups = config.get("backups", True)
        self.enable_suggestions = config.get("suggestions", True)
        self.suggestion_strictness = config.get("suggestion_strictness", "Balanced")
        self.max_suggestions = config.get("max_suggestions", 3)
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
            self.enable_backups,
            self.enable_suggestions,
            self.suggestion_strictness,
            self.max_suggestions,
            self.user_macros,
            self.always_on_top,
            self.subject_colors
        )

    def handle_focus(self, event):
        """Remembers the last Entry widget the user clicked."""
        if isinstance(event.widget, (tb.Entry, tb.Combobox)):
            self.last_focused_widget = event.widget

    def _handle_auto_brackets(self, event):
        """Handle automatic bracket completion in the formula field."""
        # Define bracket pairs
        bracket_pairs = {
            '(': ')',
            '[': ']',
            '{': '}'
        }

        char = event.char
        if char not in bracket_pairs:
            return

        # Get current position after the character was inserted
        cursor_pos = self.formula.index(INSERT)

        # Insert the closing bracket
        closing_bracket = bracket_pairs[char]
        self.formula.insert(cursor_pos, closing_bracket)

        # Move cursor back to between the brackets
        self.formula.icursor(cursor_pos)

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

    def apply_ghost_text(self, name, unit, confidence=2):
        """Inserts the suggestion as gray ghost text with optional confidence and count indicators."""
        # Only apply if fields are empty or already ghosting
        current_name = self.v_name.get().strip()
        current_unit = self.v_unit.get().strip()

        if (not current_name and not current_unit) or self.ghost_active:
            self.ghost_active = True

            # 1. Clear current (needed if updating from one ghost to another)
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)

            # 2. Build ghost text based on user settings
            name_parts = [name]

            # Add count info only if more than 1 suggestion
            if self.max_suggestions > 1 and len(self.ghost_suggestions) > 1:
                count_info = f"[{self.current_ghost_index + 1}/{len(self.ghost_suggestions)}]"
                name_parts.append(count_info)

            # Add confidence info only if more than 1 suggestion
            if self.max_suggestions > 1:
                confidence_indicator = ["🔴 Low", "🟡 Medium", "🟢 High"][confidence - 1]
                name_parts.append(f"({confidence_indicator})")

            name_with_info = " ".join(name_parts)

            self.v_name.insert(0, name_with_info)
            self.v_unit.insert(0, unit)

            # 3. Set Color to Gray (Placeholder look)
            self.v_name.configure(foreground="gray")
            self.v_unit.configure(foreground="gray")

    def solidify_ghost_text(self):
        """Turns ghost text into real text (e.g. on Tab)."""
        if self.ghost_active:
            # Remove confidence and count indicators when solidifying
            current_text = self.v_name.get()
            # Remove count info: [1/3] (optional)
            clean_text = re.sub(r'\s*\[\d+/\d+]', '', current_text)
            # Remove confidence info: (🔴 Low|🟡 Medium|🟢 High) (optional)
            clean_text = re.sub(r'\s*\((🔴 Low|🟡 Medium|🟢 High)\)', '', clean_text)
            # Clean up any trailing whitespace
            clean_text = clean_text.strip()

            self.v_name.delete(0, END)
            self.v_name.insert(0, clean_text)

            self.v_name.configure(foreground="")  # Reset to normal theme color
            self.v_unit.configure(foreground="")
            self.ghost_active = False

    def next_ghost_suggestion(self):
        """Cycle to next ghost suggestion."""
        if self.ghost_suggestions and len(self.ghost_suggestions) > 1:
            self.current_ghost_index = (self.current_ghost_index + 1) % len(self.ghost_suggestions)
            name, unit = self.ghost_suggestions[self.current_ghost_index]
            self._set_confidence_level()
            self.apply_ghost_text(name, unit, self.ghost_confidence)

    def prev_ghost_suggestion(self):
        """Cycle to previous ghost suggestion."""
        if self.ghost_suggestions and len(self.ghost_suggestions) > 1:
            self.current_ghost_index = (self.current_ghost_index - 1) % len(self.ghost_suggestions)
            name, unit = self.ghost_suggestions[self.current_ghost_index]
            self._set_confidence_level()
            self.apply_ghost_text(name, unit, self.ghost_confidence)

    def accept_ghost_suggestion(self):
        """Accept the current ghost suggestion."""
        if self.ghost_active:
            self.solidify_ghost_text()
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
            # Check if there's actual content in variable fields (not placeholders)
            def has_actual_content(widget):
                content = widget.get().strip()
                placeholder = getattr(widget, 'placeholder', "")
                return content != "" and content != placeholder

            has_content = any([
                has_actual_content(self.v_sym),
                has_actual_content(self.v_name),
                has_actual_content(self.v_unit)
            ])

            # If there's actual content, warn user before overriding
            if has_content:
                response = Messagebox.yesno(
                    "Unsaved variable data will be lost. Continue?",
                    "Unsaved Data Warning"
                )
                if response == "No":
                    return

            item = self.staging_table.view.item(selected[0])
            val = item['values']
            self.v_sym.delete(0, END)
            self.v_sym.insert(0, val[0])
            self.v_name.delete(0, END)
            self.v_name.insert(0, val[1])
            self.v_unit.delete(0, END)
            self.v_unit.insert(0, val[2])
            for w in (self.v_sym, self.v_name, self.v_unit):
                w.configure(foreground="")
            self.remove_variable(True)
            self.v_sym.focus()

    def remove_variable(self, skip=False):
        selected = self.staging_table.view.selection()
        if selected:
            item = self.staging_table.view.item(selected[0])
            val = item['values']

            # Ask user if they want to delete the selected variable
            if not skip:
                response = Messagebox.yesno(
                    f"Delete variable '{val[0]}' ({val[1]})?",
                    "Delete Variable"
                )
                if response == "No":
                    return

            self.temp_variables = [v for v in self.temp_variables if
                                   not (v['symbol'] == val[0] and v['name'] == val[1])]
            self.refresh_staging_table()

    def learn_symbols(self):
        self.symbol_learner.learn(self.master_data)

    def get_all_matches(self, subj, topic, sub_topic, sym, min_confidence=1, max_results=None):
        """Get all possible matches for a symbol."""
        if max_results is None:
            max_results = self.max_suggestions
        return self.symbol_learner.all_matches(subj, topic, sub_topic, sym, min_confidence, max_results)

    def update_preview(self):
        if not self.enable_suggestions or len(self.master_data) < 6:
            self._clear_ghosts()
            return

        if self.ghost_active and self.root.focus_get() == self.v_sym:
            self._clear_ghosts()

        focused = self.root.focus_get()
        if focused != self.v_sym:
            return

        if not self._has_valid_symbol_input():
            self._clear_ghosts()
            return

        self._update_suggestions(focused)

    def _has_valid_symbol_input(self):
        sym = self.v_sym.get().strip()
        placeholder = getattr(self.v_sym, "placeholder", None)
        return sym and (not placeholder or sym != placeholder)

    def _update_suggestions(self, focused):
        subj = self.field_e.get().strip()
        topic = self.topic_e.get().strip()
        sub_topic = self.sub_topic_e.get().strip() or "_GENERAL_"
        sym = self.v_sym.get().strip()

        all_matches = self.get_all_matches(subj, topic, sub_topic, sym, min_confidence=1)
        if not all_matches:
            self._clear_ghosts()
            return

        self._process_suggestions(all_matches, focused)

    def _process_suggestions(self, all_matches, focused):
        max_suggestions = min(self.max_suggestions, len(all_matches))
        self.ghost_suggestions = all_matches[:max_suggestions]

        if not self.ghost_suggestions:
            self._clear_ghosts()
            return

        self._reset_ghost_index_if_needed()
        self._set_confidence_level()
        self._apply_ghost_text_if_focused(focused)

    def _reset_ghost_index_if_needed(self):
        if self.current_ghost_index >= len(self.ghost_suggestions):
            self.current_ghost_index = 0

    @staticmethod
    def _get_confidence_levels(suggestion_count):
        confidence_map = {
            1: [3],
            2: [3, 2],
            3: [3, 2, 1],
            4: [3, 3, 2, 1],
        }
        return confidence_map.get(suggestion_count, [3, 3, 2, 2, 1])

    def _set_confidence_level(self):
        confidence_levels = self._get_confidence_levels(len(self.ghost_suggestions))
        self.ghost_confidence = confidence_levels[self.current_ghost_index]

    def _apply_ghost_text_if_focused(self, focused):
        if focused in (self.v_sym, self.v_name, self.v_unit):
            name, unit = self.ghost_suggestions[self.current_ghost_index]
            self.apply_ghost_text(name, unit, self.ghost_confidence)

    def _clear_ghosts(self):
        """Remove ghost text without breaking placeholders."""
        if self.ghost_active:
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)
            self.ghost_active = False

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

    def update_table_row(self, formula_id: int, new_main_info: list):
        """Update only a specific row in the table instead of refreshing the entire table."""
        # Find the display number for this formula ID
        display_number = None
        for disp_num, db_id in self.display_to_db_id_map.items():
            if db_id == formula_id:
                display_number = disp_num
                break

        if display_number is None:
            # If not found, fall back to full refresh
            self.refresh_main_table()
            return

        # Update the specific row in the table
        try:
            # Find the tree item corresponding to this display number
            for item in self.formula_table.view.get_children():
                values = self.formula_table.view.item(item, "values")
                if values and int(values[0]) == display_number:
                    # Create new row data with the updated information
                    new_row_data = [
                        str(display_number),  # Keep the same display number
                        new_main_info[1],  # Updated formula text
                        new_main_info[2],  # Updated field
                        new_main_info[3],  # Updated topic
                        new_main_info[4]  # Updated sub-topic
                    ]

                    # Update the tree item
                    self.formula_table.view.item(item, values=new_row_data)
                    self.apply_row_colors()
                    break
        except Exception as e:
            logging.error(f"Error updating table row: {e}")
            # Fall back to full refresh if row update fails
            self.refresh_main_table()

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
             "Speed Tip: Smart Suggestions show [1/3] (🟢 High) in ghost text. Ctrl+↓ accept, Ctrl+→/← cycle, Esc dismiss.")],
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

                # Update only the specific row instead of refreshing entire table
                self.update_table_row(target_id, new_main_info)

                show_toast(f"Formula {form_data['text']} Changed Successfully")
                self.editing_mode = False
                self.edit_id = None
                self.save_btn.configure(text=SAVE_FORMULA, bootstyle=INFO)
                # Hide cancel button when exiting edit mode
                self.cancel_btn.grid_forget()
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
        # Show cancel button in edit mode
        self.cancel_btn.grid(row=5, column=1, sticky=E, pady=10, padx=(0, 5))

    def cancel_edit(self):
        """Cancel the current edit operation and return to normal mode."""
        if self.editing_mode:
            self.editing_mode = False
            self.edit_id = None
            self.save_btn.configure(text=SAVE_FORMULA, bootstyle=INFO)
            # Hide cancel button
            self.cancel_btn.grid_forget()
            # Clear all entry fields
            self.clear_entries()
            show_toast("Edit cancelled", bootstyle=INFO)

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
        self.root.destroy()

    def check_and_migrate_env(self):
        """Check for existing formula data and migrate if needed."""
        # Check if migration is needed
        if not self._needs_migration():
            return

        # Perform migration
        try:
            logging.info("Starting formula migration from old location")
            self._perform_migration()
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
        backup_file = old_file + MIGRATED_EXTENSION
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
        self._setup_details_view()
        formula_text = data["main_info"][1]

        # Create formula display components
        formula_container = self._create_formula_container()
        self._add_copy_button(formula_container, formula_text)
        text_frame = self._create_text_frame(formula_container)

        # Create scrollable formula display
        self._create_scrollable_formula(text_frame, formula_text)

        # Add remaining details
        self._add_formula_metadata(data)
        self._add_variables_table(data)
        self._add_back_button()

        self.details_frame.pack(fill=BOTH, expand=YES)

    def _setup_details_view(self):
        """Set up the details view by clearing and hiding entry frame."""
        self.data_entry_frame.pack_forget()
        for w in self.details_frame.winfo_children():
            w.destroy()

    def _create_formula_container(self):
        """Create the main container for formula display."""
        formula_container = tb.Frame(self.details_frame)
        formula_container.pack(fill=X, pady=20)
        return formula_container

    def _add_copy_button(self, parent, formula_text):
        """Add copy button to formula container."""
        copy_btn = tb.Button(parent, text="📋", width=3, bootstyle=INFO,
                             command=lambda: self._copy_formula_to_clipboard(formula_text))
        copy_btn.pack(side=RIGHT, padx=(10, 0))
        TopMostToolTip(copy_btn, "Copy formula to clipboard", bootstyle=INFO)

    @staticmethod
    def _create_text_frame(parent):
        """Create text frame for formula display."""
        text_frame = tb.Frame(parent)
        text_frame.pack(side=LEFT, fill=BOTH, expand=YES)
        return text_frame

    def _create_scrollable_formula(self, parent, formula_text):
        """Create scrollable formula display with proper centering."""
        scroll_container = tb.Frame(parent)
        scroll_container.pack(side=TOP, fill=BOTH, expand=YES)

        # Create canvas and label
        canvas = tk.Canvas(scroll_container, highlightthickness=0, bd=0, height=40)
        canvas.pack(side=TOP, fill=BOTH, expand=YES)

        formula_label = tb.Label(canvas, text=formula_text,
                                 font=(FONT_FAMILY, 18), bootstyle=SUCCESS,
                                 anchor=CENTER, padding=(10, 5))

        # Place label and setup scrolling
        canvas_window_id = canvas.create_window(0, 0, anchor=NW, window=formula_label)
        self._setup_formula_scrolling(scroll_container, canvas, formula_label, canvas_window_id)

    def _setup_formula_scrolling(self, scroll_container, canvas, formula_label, canvas_window_id):
        """Setup scrolling behavior for formula display."""
        h_scrollbar = tb.Scrollbar(scroll_container, orient="horizontal", command=canvas.xview, bootstyle="round")
        canvas.configure(xscrollcommand=h_scrollbar.set)

        def check_scroll_needed():
            try:
                canvas.update_idletasks()
                formula_label.update_idletasks()

                label_width = formula_label.winfo_reqwidth()
                canvas_width = canvas.winfo_width()
                canvas_height = canvas.winfo_height()

                if canvas_width <= 1 or canvas_height <= 1:
                    return

                canvas.configure(scrollregion=(0, 0, label_width, canvas_height))

                needs_scroll = label_width > canvas_width

                if needs_scroll:
                    y_pos = max(0, (canvas_height - 40) // 2)
                    canvas.coords(canvas_window_id, 0, y_pos)
                    if not h_scrollbar.winfo_ismapped():
                        h_scrollbar.pack(side=BOTTOM, fill=X)
                else:
                    x_pos = max(0, (canvas_width - label_width) // 2)
                    y_pos = max(0, (canvas_height - 40) // 2)
                    canvas.coords(canvas_window_id, x_pos, y_pos)
                    if h_scrollbar.winfo_ismapped():
                        h_scrollbar.pack_forget()
            except (tk.TclError, IndexError, AttributeError):
                pass

        # Set initial position immediately (no delay) and then fine-tune
        canvas.after_idle(check_scroll_needed)
        # Use very short delay for any final adjustments
        self.root.after(15, check_scroll_needed)
        self.root.bind("<Configure>", lambda e: check_scroll_needed() if e.widget == self.details_frame else None)

    def _add_formula_metadata(self, data):
        """Add formula metadata (field, topic, sub-topic)."""
        metadata_text = f"Field: {data['main_info'][2]} | Topic: {data['main_info'][3]} | Sub-Topic: {data['main_info'][4]}"
        tb.Label(self.details_frame, text=metadata_text, font=(FONT_FAMILY, 11)).pack(pady=5)

    def _add_variables_table(self, data):
        """Add variables table if variables exist."""
        if data['variables']:
            vt = Tableview(master=self.details_frame,
                           coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                                    {"text": "Name", "stretch": True},
                                    {"text": "Unit", "stretch": True}],
                           rowdata=[(v['symbol'], v['name'], v['unit']) for v in data['variables']],
                           bootstyle=SECONDARY, height=6)
            vt.pack(fill=X, padx=50, pady=20)

    def _add_back_button(self):
        """Add back button to return to entry view."""
        btn_f = tb.Frame(self.details_frame)
        btn_f.pack(pady=10)
        tb.Button(btn_f, text="← Back", bootstyle="outline-info", command=self.hide_details).pack(side=LEFT, padx=10)

    def _copy_formula_to_clipboard(self, formula_text):
        """Copy formula text to clipboard."""

        # Clear the clipboard first to ensure fresh copy
        self.root.clipboard_clear()
        # Append the new formula text
        self.root.clipboard_append(formula_text)
        # Update the clipboard ownership to ensure it's available to other applications
        self.root.update()
        show_toast("Formula copied to clipboard!", bootstyle=SUCCESS)

    def hide_details(self):
        self.details_frame.pack_forget()
        self.data_entry_frame.pack(fill=BOTH, expand=YES)

    def _create_export_dialog(self):
        """Create and configure the export dialog."""
        export_dialog = tb.Toplevel(self.root)
        export_dialog.title("Export Formulas")
        l = 400
        b = 330
        export_dialog.geometry(f"{l}x{b}")
        export_dialog.minsize(l, b)
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        # Center the dialog
        export_dialog.update_idletasks()
        x = (export_dialog.winfo_screenwidth() // 2) - (l // 2)
        y = (export_dialog.winfo_screenheight() // 2) - (b // 2)
        export_dialog.geometry(f"+{x}+{y}")

        return export_dialog

    @staticmethod
    def _add_format_options(dialog, format_var):
        """Add format selection radio buttons to dialog."""
        format_frame = tb.Frame(dialog, padding=20)
        format_frame.pack(fill=BOTH, expand=YES)

        tb.Label(format_frame, text="Select Export Format:", font=(FONT_FAMILY, 12, "bold")).pack(pady=(0, 15))

        html_radio = tb.Radiobutton(format_frame, text="HTML Document (.html)", variable=format_var, value="html")
        html_radio.pack(anchor=W, pady=5)

        word_radio = tb.Radiobutton(format_frame, text="Word Document (.docx) (Soon)", variable=format_var,
                                    value="docx", state=DISABLED)
        word_radio.pack(anchor=W, pady=5)

        txt_radio = tb.Radiobutton(format_frame, text="Text File (.txt)", variable=format_var, value="txt")
        txt_radio.pack(anchor=W, pady=5)

        csv_radio = tb.Radiobutton(format_frame, text="CSV File (.csv)", variable=format_var, value="csv")
        csv_radio.pack(anchor=W, pady=5)

        json_radio = tb.Radiobutton(format_frame, text="JSON File (.json)", variable=format_var, value="json")
        json_radio.pack(anchor=W, pady=5)

        md_radio = tb.Radiobutton(format_frame, text="Markdown File (.md)", variable=format_var, value="md")
        md_radio.pack(anchor=W, pady=5)

    @staticmethod
    def _add_button_frame(dialog):
        """Add button frame to dialog."""
        btn_frame = tb.Frame(dialog)
        btn_frame.pack(fill=X, padx=20, pady=10)
        return btn_frame

    @staticmethod
    def _add_export_buttons(btn_frame, perform_export, export_dialog):
        """Add Export and Cancel buttons to button frame."""
        tb.Button(btn_frame, text="Export", bootstyle=SUCCESS, command=perform_export).pack(side=RIGHT, padx=5)
        tb.Button(btn_frame, text="Cancel", bootstyle=SECONDARY, command=export_dialog.destroy).pack(side=RIGHT)

    @staticmethod
    def _get_file_extension(format_type):
        """Get file extension for format type."""
        extensions = {
            "html": ".html",
            "txt": ".txt",
            "csv": ".csv",
            "json": ".json",
            "md": ".md"
        }
        return extensions.get(format_type, ".txt")

    def _get_export_method(self, format_type):
        """Get the appropriate export method for format type."""
        methods = {
            "html": self._export_to_html,
            "txt": self._export_to_txt,
            "csv": self._export_to_csv,
            "json": self._export_to_json,
            "md": self._export_to_markdown
        }
        return methods.get(format_type)

    def _handle_export_execution(self, format_var, export_dialog):
        """Handle the export execution logic."""
        format_type = format_var.get()
        file_extension = self._get_file_extension(format_type)
        file_types = [(f"{format_type.upper()} files", f"*{file_extension}")]

        file_path = filedialog.asksaveasfilename(
            title=f"Save {format_type.upper()} file",
            defaultextension=file_extension,
            filetypes=file_types,
            initialfile=f"formulas_export{file_extension}"
        )

        if file_path:
            try:
                export_method = self._get_export_method(format_type)
                export_method(file_path)

                Messagebox.show_info(f"Successfully exported to {format_type.upper()}!", "Export Complete")
                export_dialog.destroy()
            except ImportError as ie:
                Messagebox.show_error(f"Missing library: {str(ie)}", "Import Error")
            except Exception as e:
                Messagebox.show_error(f"Export failed: {str(e)}", "Export Error")
                # Print the full error for debugging
                import traceback
                print(f"Export error: {traceback.format_exc()}")

    def export_formulas(self):
        """Export formulas to HTML, Word, or Text format."""
        if not self.master_data:
            Messagebox.show_error("No formulas to export!", "Export Error")
            return

        export_dialog = self._create_export_dialog()
        format_var = tk.StringVar(value="html")

        self._add_format_options(export_dialog, format_var)
        btn_frame = self._add_button_frame(export_dialog)

        def perform_export():
            self._handle_export_execution(format_var, export_dialog)

        self._add_export_buttons(btn_frame, perform_export, export_dialog)
        export_dialog.mainloop()

    def _export_to_html(self, file_path):
        """Export formulas to HTML format."""
        total_formulas = len(self.master_data)

        # Create HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Formulas #{total_formulas}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cambria+Math&family=STIX+Two+Math&family=DejaVu+Sans&display=swap" rel="stylesheet">
    <style>
        @font-face {{
            font-family: 'Cambria Math';
            src: local('Cambria Math'), local('CambriaMath');
        }}
        @font-face {{
            font-family: 'STIX Two Math';
            src: local('STIX Two Math'), local('STIXTwoMath');
        }}
        @font-face {{
            font-family: 'DejaVu Sans';
            src: local('DejaVu Sans'), local('DejaVuSans');
        }}
        
        body {{
            font-family: 'Cambria Math', 'STIX Two Math', 'DejaVu Sans', 'Times New Roman', 'Arial Unicode MS', 'Segoe UI', Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
            font-size: 14px;
        }}
        .title-page {{
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 50px;
        }}
        .formula {{
            margin-bottom: 30px;
            page-break-inside: avoid;
        }}
        .formula-id {{
            font-size: 16px;
            font-weight: bold;
            color: #333;
        }}
        .formula-text {{
            font-size: 16px;
            margin: 10px 0;
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Cambria Math', 'STIX Two Math', 'DejaVu Sans', 'Times New Roman', 'Arial Unicode MS', serif;
            line-height: 1.4;
            unicode-bidi: embed;
        }}
        .metadata {{
            font-size: 12px;
            color: #666;
            margin: 5px 0;
        }}
        .variables {{
            margin-top: 10px;
        }}
        .variable {{
            font-size: 12px;
            margin-left: 20px;
            color: #555;
        }}
        @media print {{
            .formula {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="title-page">Formulas #{total_formulas}</div>
    <div style="page-break-after: always;"></div>
"""

        # Sort formulas by ID
        sorted_data = sorted(self.master_data.items(), key=lambda x: int(x[0]))

        for formula_id, data in sorted_data:
            formula_text = html.escape(data['main_info'][1].replace('\n', '<br>'))
            subject = html.escape(data['main_info'][2])
            topic = html.escape(data['main_info'][3])
            sub_topic = html.escape(data['main_info'][4])

            html_content += f"""
    <div class="formula">
        <div class="formula-id">#{formula_id}</div>
        <div class="formula-text">{formula_text}</div>
        <div class="metadata">Subject: {subject} | Topic: {topic} | Sub-Topic: {sub_topic}</div>
"""

            if data['variables']:
                html_content += '        <div class="variables"><b>Variables:</b>\n'
                for var in data['variables']:
                    symbol = html.escape(var['symbol'])
                    name = html.escape(var['name'])
                    unit = html.escape(var['unit'])

                    if unit.lower() in NO_DIMENSION_UNITS:
                        var_text = f"{symbol} means {name}"
                    else:
                        var_text = f"{symbol} means {name} with unit {unit}"

                    html_content += f'            <div class="variable">• {var_text}</div>\n'
                html_content += '        </div>\n'

            html_content += '    </div>\n'

        html_content += """
</body>
</html>"""

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _export_to_txt(self, file_path):
        """Export formulas to plain text format."""
        total_formulas = len(self.master_data)

        # Create text content
        content = f"Formulas #{total_formulas}\n"
        content += "=" * 50 + "\n\n"

        # Sort formulas by ID
        sorted_data = sorted(self.master_data.items(), key=lambda x: int(x[0]))

        for formula_id, data in sorted_data:
            content += f"#{formula_id}\n"
            content += f"Formula: {data['main_info'][1]}\n"
            content += (f"Subject: {data['main_info'][2]} |"
                        f" Topic: {data['main_info'][3]} |"
                        f" Sub-Topic: {data['main_info'][4]}\n")

            if data['variables']:
                content += "Variables:\n"
                for var in data['variables']:
                    symbol = var['symbol']
                    name = var['name']
                    unit = var['unit']

                    if unit in NO_DIMENSION_UNITS:
                        var_text = f"{symbol} means {name}"
                    else:
                        var_text = f"{symbol} means {name} with unit {unit}"

                    content += f"  • {var_text}\n"

            content += "\n" + "-" * 30 + "\n\n"

        # Write to file
        with open(file_path, 'w', encoding='utf-8-sig') as f:
            f.write(content)

    def _export_to_csv(self, file_path):
        """Export formulas to CSV format."""

        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['ID', 'Formula', 'Field', 'Topic', 'Sub-Topic', 'Variables']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()

            # Sort formulas by ID
            sorted_data = sorted(self.master_data.items(), key=lambda x: int(x[0]))

            for formula_id, data in sorted_data:
                # Format variables as a string
                variables_str = '; '.join([
                    f"{var['symbol']}: {var['name']} ({var['unit']})"
                    for var in data['variables']
                ])

                writer.writerow({
                    'ID': formula_id,
                    'Formula': data['main_info'][1],
                    'Field': data['main_info'][2],
                    'Topic': data['main_info'][3],
                    'Sub-Topic': data['main_info'][4],
                    'Variables': variables_str
                })

    def _export_to_json(self, file_path):
        """Export formulas to JSON format."""
        # Sort formulas by ID for consistent output
        sorted_data = sorted(self.master_data.items(), key=lambda x: int(x[0]))

        export_data = {
            'total_formulas': len(self.master_data),
            'export_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'formulas': {
                str(formula_id): {
                    'formula': data['main_info'][1],
                    'field': data['main_info'][2],
                    'topic': data['main_info'][3],
                    'sub_topic': data['main_info'][4],
                    'variables': data['variables']
                }
                for formula_id, data in sorted_data
            }
        }

        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)

    def _export_to_markdown(self, file_path):
        """Export formulas to Markdown format."""
        total_formulas = len(self.master_data)

        content = f"# Formulas Collection ({total_formulas} formulas)\n\n"
        content += f"*Exported on {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        content += ("<!-- Font recommendation for best Unicode display:"
                    " Cambria Math, STIX Two Math, DejaVu Sans -->\n\n")
        content += "---\n\n"

        # Sort formulas by ID
        sorted_data = sorted(self.master_data.items(), key=lambda x: int(x[0]))

        for formula_id, data in sorted_data:
            content += f"## #{formula_id}\n\n"
            content += f"**Formula:** `{data['main_info'][1]}`\n\n"
            content += (f"**Field:** {data['main_info'][2]} |"
                        f" **Topic:** {data['main_info'][3]} |"
                        f" **Sub-Topic:** {data['main_info'][4]}\n\n")

            if data['variables']:
                content += "**Variables:**\n"
                for var in data['variables']:
                    symbol = var['symbol']
                    name = var['name']
                    unit = var['unit']

                    # Escape special Markdown characters and preserve subscripts
                    def escape_md(text):
                        # Preserve subscripts while escaping other characters
                        text = (text.replace('\\', '\\\\')
                                .replace('*', '\\*')
                                .replace('_', '\\_')
                                .replace('`', '\\`'))
                        return text

                    symbol_safe = escape_md(symbol)
                    name_safe = escape_md(name)
                    unit_safe = escape_md(unit)

                    if unit.lower() in NO_DIMENSION_UNITS:
                        var_text = f"- **{symbol_safe}** means {name_safe}"
                    else:
                        var_text = f"- **{symbol_safe}** means {name_safe} with unit {unit_safe}"

                    content += f"{var_text}\n"
                content += "\n"

            content += "---\n\n"

        with open(file_path, 'w', encoding='utf-8') as mdfile:
            mdfile.write(content)


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    toast_manager.bind_root(root)
    sheet = Sheet(root)
    root.mainloop()
