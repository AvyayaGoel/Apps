import json
import logging
import os
import random
import shutil
import sys
import tkinter as tk
from typing import Dict, Tuple, Optional
from typing import Protocol

import ttkbootstrap as tb
from ttkbootstrap.constants import (BOTH, TOP, X, YES, INFO,
                                    SUCCESS, DANGER, END, N, EW, LEFT, RIGHT, Y, W, E,
                                    INSERT, WARNING, INVERSE, DARK, CENTER, SOLID,
                                    DISABLED, VERTICAL, HORIZONTAL, BOTTOM, SECONDARY)
from ttkbootstrap.dialogs import ColorChooserDialog
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from ttkbootstrap.widgets.tableview import Tableview
from ttkbootstrap.widgets.toast import ToastNotification
from ttkbootstrap.widgets.tooltip import ToolTip

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


def show_toast(message, bootstyle=SUCCESS):
    # Count existing top levels
    before = set(root.winfo_children())

    toast = ToastNotification(
        title="Calculus Console",
        message=message,
        duration=10000,
        bootstyle=bootstyle,
        position=(0, 60, 'se')
    )
    toast.show_toast()

    # Find the new Toplevel
    after = set(root.winfo_children())
    new_windows = after - before

    toast_window = None
    for w in new_windows:
        if isinstance(w, tb.Toplevel):
            toast_window = w
            break

    if toast_window:
        toast_manager.show(toast_window)


class ToastManager:
    def __init__(self):
        self.root = None
        self.active = []
        self.base_offset = 60
        self.spacing = 80

    def bind_root(self, toast_root):
        self.root = toast_root

    def show(self, win):
        if not win or not win.winfo_exists():
            return

        self.active.append(win)
        self._reposition()

        # Auto-remove after toast destroys itself
        self.root.after(10000, lambda: self._remove(win))

    def _remove(self, win):
        if win in self.active:
            self.active.remove(win)
            self._reposition()

    def _reposition(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        total = len(self.active)

        for i, win in enumerate(self.active):
            if not win.winfo_exists():
                continue

            win.update_idletasks()
            w = win.winfo_width()
            h = win.winfo_height()

            y = sh - self.base_offset - h - (total - i - 1) * self.spacing
            x = sw - w - 12

            win.geometry(f"+{x}+{y}")


# GLOBAL INSTANCE
toast_manager = ToastManager()


def normalize_main_info(data):
    """
    Ensures main_info always has:
    [id, formula, field, topic, sub_topic]
    """
    mi = data.get("main_info", [])

    # Old format: no sub_topic
    if len(mi) == 4:
        mi.append("_GENERAL_")

    # Defensive: truncate if corrupted
    data["main_info"] = mi[:5]
    return data


class AppWindow(Protocol):
    win: tk.Toplevel


class KeypadWindow:
    def __init__(self, k_root):
        self.win = tb.Toplevel(k_root)


class Sheet:
    def __init__(self, f_sheet):
        self.root = f_sheet
        self.root.title("Calculus Console")
        self.root.geometry("1000x900")
        self.root.minsize(900, 900)
        appdata_path = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        self.data_dir = os.path.join(appdata_path, "CalculusConsole")

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        def resource_path(relative_path):
            """ Get absolute path to resource, works for dev and for PyInstaller """
            base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))

            return os.path.join(base_path, relative_path)

        # --- Inside your Sheet class __init__ ---
        self.db_name = "formula_data.json"
        self.icon_file = resource_path(os.path.join("data", "formula_sheet_icon.png"))
        self.db_file = os.path.join(self.data_dir, self.db_name)
        self.config_file = os.path.join(self.data_dir, "config.json")
        self.tip_file = os.path.join(self.data_dir, "tip_state.json")
        self.new_db_name = "schema_v1.dat"
        self.backup_slots = [
            os.path.join(self.data_dir, "schema_idx_0.db"),
            os.path.join(self.data_dir, "schema_idx_1.db"),
            os.path.join(self.data_dir, "schema_idx_2.db")
        ]
        self.check_and_migrate_env()

        self.tip_state = self.load_tip_state()
        if os.path.exists(self.icon_file):
            # Load the PNG
            self.icon_obj = tk.PhotoImage(file=self.icon_file)
            self.root.iconphoto(False, self.icon_obj)
            self.root.tk.call('wm', 'iconphoto', str(self.root), "-default", self.icon_obj)
        else:
            print(f"File not found: {self.icon_file}")
        self.master_data = {}
        self.temp_variables = []
        self.editing_mode = False
        self.edit_id = None

        self.auto_save_timer = None

        self.last_focused_widget = None

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

        self.symbol_learner = SymbolLearner(normalize_main_info)
        self.symbol_stats = {}
        self.symbol_kb = {}  # Format: {Field: {Symbol: {"name": name, "unit": unit}}}
        self.ghost_active = False

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

        self.mainframe = tb.Frame(self.root, padding=10)
        self.mainframe.pack(fill=BOTH, expand=YES)

        # 1. MAIN TABLE
        self.table_frame = tb.Frame(self.mainframe, height=350)
        self.table_frame.pack_propagate(False)
        self.table_frame.pack(fill=X, side=TOP, pady=(0, 10))

        # 1. Create a dedicated container for the right-side buttons
        self.utility_bar = tb.Frame(self.table_frame)
        self.utility_bar.pack(side=RIGHT, fill=Y, padx=5)

        # 2. Pack the Help button at the TOP of that bar
        self.help_table = tb.Button(self.utility_bar,
                                    text="?", width=3,
                                    bootstyle="info-outline")
        self.help_table.pack(side=TOP, anchor=N, pady=(0, 5))  # Added small bottom padding
        ToolTip(self.help_table, text="Double-click a row to View Details or Edit the formula."
                                      "\nRight click on a row for more options.", bootstyle="info-inverse")

        # 3. Pack the Stats button directly UNDER it
        self.stats_btn = tb.Button(self.utility_bar,
                                   text="📊", width=3,  # Kept width consistent
                                   bootstyle=SECONDARY,
                                   command=lambda: self.open_stats())
        self.stats_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        ToolTip(self.stats_btn, text="View Formula Distribution by Subject/Topic", bootstyle="secondary-inverse")

        self.view_btn = tb.Button(self.utility_bar,
                                  text="🔍", width=3,
                                  bootstyle="success-outline",
                                  command=self.details)
        self.view_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        ToolTip(self.view_btn, text="View Selected Formula", bootstyle="success")

        self.edit_btn = tb.Button(self.utility_bar,
                                  text="🖉", width=3,
                                  bootstyle="warning-outline",
                                  command=self.edit)
        self.edit_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        ToolTip(self.edit_btn, text="Edit Selected Formula", bootstyle="warning")

        self.del_btn = tb.Button(self.utility_bar,
                                 text="🗑", width=3,
                                 bootstyle="danger-outline",
                                 command=self.delete)
        self.del_btn.pack(side=TOP, anchor=N, pady=(0, 5))
        ToolTip(self.del_btn, text="Delete Selected Formula", bootstyle="danger")

        self.formula_table = Tableview(master=self.table_frame,
                                       coldata=self.cols,
                                       searchable=True,
                                       paginated=True,
                                       bootstyle=INFO,
                                       )
        self.formula_table.pack(fill=BOTH, expand=YES)
        self.apply_row_colors()
        self.formula_table.view.bind("<<TreeviewSelect>>", lambda e: self.root.after(1, self.apply_row_colors))

        # 2. ENTRY SECTION
        self.data_entry_frame = tb.Labelframe(self.mainframe, text=" Formula Entry ", padding=20)
        self.data_entry_frame.pack(fill=BOTH, expand=YES)
        self.data_entry_frame.columnconfigure(1, weight=1)

        # Main Fields with Focus Binding
        fields = [("Formula:", self.formula_e), ("Field:", self.field_e), ("Topic:", self.topic_e),
                  ("Sub-Topic:", self.sub_topic_e)]
        for i, (label, var) in enumerate(fields):
            tb.Label(self.data_entry_frame,
                     text=label
                     ).grid(row=i, column=0, sticky=W, pady=5)
            if label == "Field:":
                self.subject_cb = tb.Combobox(self.data_entry_frame,
                                              values=["Physics", "Chemistry", "Maths"],
                                              textvariable=var)
                self.subject_cb.bind(COMBOBOX_SELECTED_EVENT, lambda e: self.on_subject_change())
                self.subject_cb.bind(KEY_RELEASE_EVENT, lambda e: self.on_subject_change())
                # ADD THIS: Update preview when subject changes
                self.subject_cb.bind(COMBOBOX_SELECTED_EVENT, lambda e: self.update_preview(), add="+")
                widget = self.subject_cb
            elif label == "Topic:":
                self.topic_cb = tb.Combobox(self.data_entry_frame,
                                            values=[],
                                            textvariable=var)
                # ADD THIS: Update preview when topic changes
                self.topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda e: self.on_topic_change())
                self.topic_cb.bind(KEY_RELEASE_EVENT, lambda e: self.on_topic_change())
                self.topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda e: self.update_preview(), add="+")
                widget = self.topic_cb
            elif label == "Sub-Topic:":
                self.sub_topic_cb = tb.Combobox(self.data_entry_frame,
                                                values=[],
                                                textvariable=var)
                self.sub_topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda e: self.update_preview())
                widget = self.sub_topic_cb
            else:
                self.formula = tb.Entry(self.data_entry_frame, textvariable=var)
                widget = self.formula

            # BIND FOCUS EVENT
            widget.bind(FOCUS_IN_EVENT, self.handle_focus)
            widget.grid(row=i, column=1, sticky=EW, padx=10)

        # 3. VARIABLE MANAGEMENT
        var_mgmt_frame = tb.Labelframe(self.data_entry_frame,
                                       text=" Variables ",
                                       padding=10)
        var_mgmt_frame.grid(row=4, column=0,
                            columnspan=2, sticky=EW,
                            pady=10)

        input_row = tb.Frame(var_mgmt_frame)
        input_row.pack(fill=X, pady=5)

        # Create and Bind Variable Inputs
        self.v_sym = self.setup_entry(tb.Entry(input_row, width=10), "Symbol")
        self.v_sym.pack(side=LEFT, padx=2)

        self.v_name = self.setup_entry(tb.Entry(input_row), "Variable Name")
        self.v_name.pack(side=LEFT, fill=X, expand=YES, padx=2)

        self.v_unit = self.setup_entry(tb.Entry(input_row, width=15), "Unit")
        self.v_unit.pack(side=LEFT, padx=2)

        self.v_add = tb.Button(input_row, text="+",
                               bootstyle=SUCCESS,
                               command=self.add_variable
                               )
        self.v_add.pack(side=LEFT, padx=2)

        self.staging_table = Tableview(
            master=var_mgmt_frame,
            coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                     {"text": "Name", "stretch": True},
                     {"text": "Unit", "stretch": True}],
            rowdata=[],
            bootstyle=SECONDARY,
            height=4
        )
        self.staging_table.pack(fill=X, pady=5)

        # Action Buttons
        btn_row = tb.Frame(var_mgmt_frame)
        btn_row.pack(fill=X)

        self.v_edit = tb.Button(btn_row, text="Edit Selected",
                                bootstyle="warning-outline",
                                command=self.load_variable_to_fix)
        self.v_edit.pack(side=LEFT, padx=5)
        self.v_del = tb.Button(btn_row, text="Delete Selected",
                               bootstyle="danger-outline",
                               command=self.remove_variable)
        self.v_del.pack(side=LEFT, padx=5)

        # --- NEW KEYPAD BUTTON ---
        self.keypad_btn = tb.Button(btn_row, text="⌨", bootstyle=SECONDARY, command=self.toggle_keypad)
        self.keypad_btn.pack(side=LEFT, padx=(20, 0))

        # Change your settings button to this:
        self.settings_btn = tb.Button(btn_row, text="⛭", bootstyle=SECONDARY,
                                      command=self.open_settings)
        self.settings_btn.pack(side=LEFT, padx=5)

        award_text = "🏅" if len(self.master_data) < 30 else "🔒"
        self.award_panel = tb.Button(btn_row, text=award_text, bootstyle=SECONDARY,
                                     command=self.open_awards)
        self.award_panel.pack(side=LEFT, padx=5)
        # -------------------------

        self.help_var = tb.Button(btn_row, text="?", width=3, bootstyle="info-outline")
        self.help_var.pack(side=RIGHT, padx=5)
        ToolTip(self.help_var,
                text="1. Add variables using '+'."
                     "\n2. Fix typos via 'Edit Selected'."
                     "\n3. Use ⌨ for special symbols.",
                bootstyle="info-inverse"
                )

        self.save_btn = tb.Button(self.data_entry_frame, text="Save Formula", width=20, bootstyle=INFO,
                                  command=self.save_to_table)
        self.save_btn.grid(row=5, column=1, sticky=E, pady=10)

        self.details_frame = tb.Frame(self.mainframe)
        self.root.bind("<Control-k>", lambda e: self.toggle_keypad())
        self.root.bind("<Control-n>", lambda e: self.clear_entries())
        self.root.bind("<Control-comma>", lambda e: self.open_settings())
        self.root.bind("<Control-BackSpace>", lambda e: self.remove_variable())
        self.root.bind("<Control-s>", lambda e: self.save_to_table())
        self.formula.bind(RETURN_EVENT, lambda e: self.subject_cb.focus())
        self.subject_cb.bind(RETURN_EVENT, lambda e: self.topic_cb.focus())
        self.topic_cb.bind(RETURN_EVENT, lambda e: self.sub_topic_cb.focus())
        self.sub_topic_cb.bind(RETURN_EVENT, lambda e: self.v_sym.focus())
        self.v_sym.bind(RETURN_EVENT, lambda e: self.v_name.focus())
        self.v_name.bind(RETURN_EVENT, lambda e: self.v_unit.focus())
        self.v_unit.bind(RETURN_EVENT, lambda e: self.add_variable())
        self.bind_autosave_widgets()
        self.v_sym.bind(KEY_RELEASE_EVENT, lambda e: self.update_preview())
        self.v_sym.bind("<Right>", lambda e: self.auto_fill_variable())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_from_file()
        self.create_backup()
        self.load_config()
        self.update_suggestions()

    def trigger_auto_save(self):
        """Resets the timer every time the user types."""
        if self.auto_save_timer is not None:
            self.root.after_cancel(self.auto_save_timer)
        self.auto_save_timer = self.root.after(self.auto_save_delay, self.perform_silent_save)

    def load_tip_state(self):
        if os.path.exists(self.tip_file):
            try:
                with open(self.tip_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
            except Exception as e:
                logging.error(f"Failed to load tip state from {self.tip_file}: {e}", exc_info=True)

        return {
            "shown": {},  # tip_id → true
            "counters": {},  # tip_id → int
            "last_seen": {}  # tip_id → timestamp (optional)
        }

    def save_tip_state(self):
        with open(self.tip_file, "w") as f:
            json.dump(self.tip_state, f, indent=4)

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
        widget.bind(FOCUS_OUT_EVENT, lambda e: self.on_entry_focus_out())
        return widget

    def perform_silent_save(self):
        """Writes data to file sorted by ID, ignoring the table's current view order."""
        # 1. Get all IDs from your master dictionary and sort them numerically
        sorted_ids = sorted(self.master_data.keys())
        final_save_list = [self.master_data[i] for i in sorted_ids]
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(final_save_list, f, indent=4, ensure_ascii=False)

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
        if not os.path.exists(self.config_file):
            # Create default if missing
            default = {
                "theme": "darkly",
                "delay": 5000,
                "backups": True,
                "suggestions": True,
                "suggestion_strictness": "Balanced",
                "macros": [],
                "always_on_top": False,
                "subject_colors": {
                    "Physics": "#5dade2",
                    "Chemistry": "#58d68d",
                    "Maths": "#af7ac5"
                }
            }
            with open(self.config_file, 'w') as f:
                json.dump(default, f, indent=4)
            return

        try:
            with open(self.config_file) as f:
                cfg = json.load(f)
                self.root.style.theme_use(cfg.get("theme", "darkly"))
                self.auto_save_delay = cfg.get("delay", 5000)
                self.enable_backups = cfg.get("backups", True)
                self.enable_suggestions = cfg.get("suggestions", True)
                self.suggestion_strictness = cfg.get("suggestion_strictness", "Balanced")
                self.user_macros = cfg.get("macros", [])
                self.always_on_top = cfg.get("always_on_top", False)
                self.subject_colors = cfg.get("subject_colors", {
                    "Physics": "#5dade2",
                    "Chemistry": "#58d68d",
                    "Maths": "#af7ac5"
                })
                self.root.attributes("-topmost", self.always_on_top)
        except (json.JSONDecodeError, KeyError):
            # If config is corrupted, create a new default one
            self.load_config()

    def save_config(self):
        config = {
            "theme": self.root.style.theme.name,
            "delay": self.auto_save_delay,
            "backups": self.enable_backups,
            "suggestions": self.enable_suggestions,
            "suggestion_strictness": self.suggestion_strictness,
            "macros": self.user_macros,
            "always_on_top": self.always_on_top,
            "subject_colors": self.subject_colors
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)

    def handle_focus(self, event):
        """Remembers the last Entry widget the user clicked."""
        if isinstance(event.widget, (tb.Entry, tb.Combobox)):
            self.last_focused_widget = event.widget

    def on_entry_focus_in(self, event):
        """Handles clearing placeholders and managing ghost text interaction."""
        widget = event.widget
        self.handle_focus(event)

        main_group = [self.v_sym, self.v_name, self.v_unit]

        # 1. GROUP PLACEHOLDER LOGIC
        # If any of the 3 is clicked, clear ALL placeholders in the group
        if widget in main_group:
            for w in main_group:
                placeholder = getattr(w, 'placeholder', None)
                if placeholder and w.get() == placeholder:
                    w.delete(0, END)
                    w.configure(foreground="")
            # Reset to normal text color

        # 2. GHOST TEXT LOGIC
        if self.ghost_active and widget in (self.v_name, self.v_unit):
            self.solidify_ghost_text()

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

    def apply_ghost_text(self, name, unit):
        """Inserts the suggestion as gray ghost text."""
        # Only apply if fields are empty or already ghosting
        current_name = self.v_name.get().strip()
        current_unit = self.v_unit.get().strip()

        if (not current_name and not current_unit) or self.ghost_active:
            self.ghost_active = True

            # 1. Clear current (needed if updating from one ghost to another)
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)

            # 2. Insert Ghost Text
            self.v_name.insert(0, name)
            self.v_unit.insert(0, unit)

            # 3. Set Color to Gray (Placeholder look)
            self.v_name.configure(foreground="gray")
            self.v_unit.configure(foreground="gray")

    def solidify_ghost_text(self):
        """Turns ghost text into real text (e.g. on Tab)."""
        if self.ghost_active:
            self.v_name.configure(foreground="")  # Reset to normal theme color
            self.v_unit.configure(foreground="")
            self.ghost_active = False

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

        win = win_obj.win  # actual Toplevel

        x = win.winfo_x() - self.drag_x + event.x
        y = win.winfo_y() - self.drag_y + event.y
        win.geometry(f"+{x}+{y}")

    def toggle_keypad(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_MSG, bootstyle=DANGER)
            return

        win_obj = self.windows["keypad"]
        if win_obj is not None:
            win_obj.win.destroy()
            self.windows["keypad"] = None
            return

        kp = KeypadWindow(self.root)
        win = kp.win

        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.wm_attributes("-toolwindow", True)

        x = self.keypad_btn.winfo_rootx()
        y = self.keypad_btn.winfo_rooty() - 530
        win.geometry(f"+{x}+{y}")

        self.windows["keypad"] = kp

        # --- DRAG HANDLE (The "Little Area") ---
        drag_handle = tb.Frame(self.windows["keypad"].win, bootstyle=SECONDARY, height=20)
        drag_handle.pack(fill=X)

        # Add a grip visual
        grip_lbl = tb.Label(drag_handle, text=":::: Grip to Move ::::", bootstyle="inverse-secondary",
                            font=("Arial", 8))
        grip_lbl.pack(pady=2)

        # Bind events for dragging
        drag_handle.bind(BUTTON_1_EVENT, self.start_move)
        drag_handle.bind(B1_MOTION_EVENT, self.do_move)
        grip_lbl.bind(BUTTON_1_EVENT, self.start_move)
        grip_lbl.bind(B1_MOTION_EVENT, self.do_move)
        # ---------------------------------------

        # Main Container
        p_frame = tb.Frame(self.windows["keypad"].win, padding=5, bootstyle="dark")
        p_frame.pack(fill=BOTH, expand=YES)

        symbol_sets = [
            ["π", "θ", "λ", "Δ", "ρ", "ω", "Ω", "μ", "α", "β", "γ", "δ"],
            ["·", "×", "÷", "±", "≈", "√", "°", "∞", "≠", "≤", "≥", "≡"],
            ["∫", "∂", "∑", "∏", "∈", "∉", "⊆", "⊂", "∠", "⊥", "∥", "∝"],
            ["⁺", "⁻", "⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"],
            ["₊", "₋", "₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉"]
        ]

        for r_idx, row_syms in enumerate(symbol_sets):
            row_f = tb.Frame(p_frame)
            row_f.pack(fill=X, pady=1)
            for sym in row_syms:
                # Use lambda to capture the specific symbol
                btn = tb.Button(row_f, text=sym, width=3, bootstyle=SECONDARY,
                                command=lambda s=sym: self.insert_text(s),
                                takefocus=False)  # Important: Don't steal focus!
                btn.pack(side=LEFT, padx=1)

        if self.user_macros:
            tb.Separator(p_frame, bootstyle=SECONDARY).pack(fill=X, pady=10)
            # Create a frame for user buttons
            u_row = tb.Frame(p_frame, bootstyle="dark")
            u_row.pack(fill=X, pady=2)

            for i, m in enumerate(self.user_macros):
                # Wrap to new row every 5 buttons
                if i > 0 and i % 5 == 0:
                    u_row = tb.Frame(p_frame, bootstyle="dark")
                    u_row.pack(fill=X, pady=2)

                warp_val = m.get('warp', 0)
                tb.Button(u_row, text=m['label'], bootstyle="info-outline",
                          command=lambda c=m['content'], w=warp_val: self.insert_text(c, w),
                          takefocus=False).pack(side=LEFT, padx=2, expand=YES, fill=X)

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

    def get_best_match(self, subj, topic, sub_topic, sym, min_confidence=2):
        return self.symbol_learner.best_match(
            subj, topic, sub_topic, sym, min_confidence
        )

    def update_preview(self):
        if not self.enable_suggestions:
            self._clear_ghosts()
            return

        # Require sufficient data
        if len(self.master_data) < 6:
            self._clear_ghosts()
            return

        if self.ghost_active and self.root.focus_get() == self.v_sym:
            self._clear_ghosts()

        # Must have symbol entry focused or recently edited
        focused = self.last_focused_widget
        if focused not in (self.v_sym, self.v_name, self.v_unit):
            return

        sym = self.v_sym.get().strip()
        placeholder = getattr(self.v_sym, "placeholder", None)

        if not sym or (placeholder and sym == placeholder):
            self._clear_ghosts()
            return

        subj = self.field_e.get().strip()
        topic = self.topic_e.get().strip()
        sub_topic = self.sub_topic_e.get().strip() or "_GENERAL_"

        confidence_map = {
            "Conservative": 3,
            "Balanced": 2,
            "Aggressive": 1
        }
        min_conf = confidence_map.get(self.suggestion_strictness, 2)
        match = self.get_best_match(subj, topic, sub_topic, sym, min_confidence=min_conf)

        if not match:
            self._clear_ghosts()
            return

        name, unit = match
        if focused not in (self.v_name, self.v_unit):
            self.apply_ghost_text(name, unit)

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

    def auto_fill_variable(self):
        """Accepts the suggestion (solidifies ghost text)."""
        if self.ghost_active:
            self.solidify_ghost_text()
            self.v_name.focus()
            return "break"

        subj = self.field_e.get().strip()
        topic = self.topic_e.get().strip()
        sub_topic = self.sub_topic_e.get().strip() or "_GENERAL_"
        sym = self.v_sym.get().strip()

        confidence_map = {
            "Conservative": 3,
            "Balanced": 2,
            "Aggressive": 1
        }
        min_conf = confidence_map.get(self.suggestion_strictness, 2)
        match = self.get_best_match(subj, topic, sub_topic, sym, min_confidence=min_conf)

        if match:
            name, unit = match
            self.v_name.delete(0, END)
            self.v_name.insert(0, name)
            self.v_unit.delete(0, END)
            self.v_unit.insert(0, unit)
            self.v_unit.focus()
            return "break"
        return None

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
        for row in self.formula_table.tablerows:
            if int(row.values[0]) == int(formula_id):
                row.values = new_main_info
                self.formula_table.load_table_data()
                self.apply_row_colors()
                return True
        return False

    def refresh_main_table(self):
        rows = [v["main_info"] for v in self.master_data.values()]
        rows.sort(key=lambda x: int(x[0]))

        self.formula_table.build_table_data(self.cols, rows)  # type: ignore
        self.formula_table.load_table_data()
        self.apply_row_colors()

    def validate_formula_entry(self):
        if not self.formula_e.get().strip():
            Messagebox.show_warning("Formula cannot be empty.", "Validation Error")
            return False

        if not self.field_e.get().strip():
            Messagebox.show_warning("Please select a Field.", "Validation Error")
            return False

        if self.v_unit.get() == "Unit":
            Messagebox.show_warning("Please enter a valid Variable.", "Variable Empty")
            return False

        if self.v_name.cget("foreground") == "gray" or self.v_unit.cget("foreground") == "gray":
            response = Messagebox.yesno(
                "You have unaccepted suggestions (Ghost Text). Save them as real data?",
                "Unaccepted Suggestions",
            )
            if response == "Yes":
                self.solidify_ghost_text()
            else:
                return False

        return True

    def renumber_database(self):
        new_master = {}
        for index, old_id in enumerate(sorted(self.master_data.keys()), start=1):
            data = self.master_data[old_id]
            data["main_info"][0] = index
            new_master[index] = data
        self.master_data = new_master

    def show_milestone_banner(self, text, bootstyle="success"):
        """
        Shows a temporary slide-down banner.
        Safe:
        - One banner at a time
        - Auto-destroys
        - Theme-aware
        """

        # Prevent stacking banners
        if hasattr(self, "_active_banner") and self._active_banner.winfo_exists():
            return

        banner = tb.Frame(
            self.root,
            bootstyle=bootstyle,
            padding=(15, 8)
        )

        self._active_banner = banner  # Track active banner

        label = tb.Label(
            banner,
            text=text,
            font=(self.font_name, 11, "bold"),
            bootstyle=f"inverse-{bootstyle}"
        )
        label.pack()

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
                self.root.after(2800, slide_up)

        def slide_up():
            if not banner.winfo_exists():
                return

            y = banner.winfo_y()
            if y > -80:
                banner.place(y=y - step)
                self.root.after(15, slide_up)
            else:
                banner.destroy()

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
        2: "🌱 First Steps: You've started your collection!",
        5: "⚡ Quick Learner: You're getting the hang of the Console.",
        10: "🏆 Milestone Unlocked: The Beginner's Dozen! (10 Formulas Saved)",
        20: "🎉 20 formulas! Created by Avyaya Goel (Class 10)",
        25: "🚀 Milestone Unlocked: Physics Pro! (25 Formulas Saved)",
        30: "📐 Structure Forming: Patterns are beginning to stabilize.",
        50: "🔥 Milestone Unlocked: Half-Century! You are becoming a speed god.",
        75: "🧠 Sustained Usage Detected: This system is now part of your workflow.",
        100: "👑 LEGENDARY: 100 Formulas! Your Calculus Console is complete.",
        120: "⚠️ Extended Consistency Observed: Advanced behavior emerging.",
        151: "🌑 Static Silence: Most would have disconnected by now. You... stayed.",
        175: "🛰️ Observed Persistence: Interaction data is deviating from standard exit-rates.",
        200: "💎 Double Century: 200 Fragments. The architecture is no longer just lines of data.",
        238: "☢️ Critical Mass: 238 Formulas. The information density is warping the system clock.",
        300: "🪐 PLANETARY SCALE: 300 Formulas. A complete world of variables and constants.",
        400: "🔱 ABSOLUTE STABILITY: 400. There is too much friction."
             " The heat should have frozen this screen."
             " Why is everything still moving?"
    }

    COUNT_TIPS = {
        3: [("entry_tip", "Speed Tip: Use Enter to jump between fields instead of clicking.")],
        4: [("keypad_tip", "Speed Tip: Use 'Ctrl + K' to open the math symbol keypad instantly.")],
        6: [("Feature_Unlock", "✨ Feature Unlocked: Smart Suggestions is now active!")],
        7: [("arrow_tip", "Speed Tip: Use the 'Right Arrow' key to instantly accept suggestions.")],
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
        stats = {"Maths": 0, "Physics": 0, "Chemistry": 0}
        other_subjects = set()
        var_overload = False

        for entry in self.master_data.values():
            if len(entry.get("variables", [])) >= 5:
                var_overload = True
            subj = entry["main_info"][2]
            if subj in stats:
                stats[subj] += 1
            elif subj:
                other_subjects.add(subj)

        return stats, other_subjects, var_overload

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
                return
            y = self.entity_banner.winfo_y()
            if y > -90:
                self.entity_banner.place(y=y - step)
                self.root.after(15, slide_up)
            else:
                self.entity_banner.destroy()

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
        self.topic_cb.bind(COMBOBOX_SELECTED_EVENT, lambda e: self._advance_entity())

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

        self._cleanup_orphaned_data()
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
        visible_ids = [int(row.values[0]) for row in self.formula_table.tablerows]
        for stored_id in self.master_data.keys():
            if stored_id not in visible_ids:
                if not (self.editing_mode and stored_id == self.edit_id):
                    del self.master_data[stored_id]

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
        new_main_info = [target_id, form_data['text'], form_data['field'],
                         form_data['topic'], form_data['sub_topic']]

        self.master_data[target_id] = {
            "main_info": new_main_info,
            "variables": self.temp_variables.copy()
        }

        updated = self.update_table_row_by_id(target_id, new_main_info)
        if not updated:
            self.refresh_main_table()

        show_toast(f"Formula {form_data['text']} Changed Successfully")
        self.editing_mode = False
        self.edit_id = None
        self.save_btn.configure(text="Save Formula", bootstyle=INFO)

    def _handle_add_mode(self, form_data):
        """Handle saving in add mode - create new entry."""
        new_id = max(self.master_data.keys(), default=0) + 1
        self.master_data[new_id] = {
            "main_info": [new_id, form_data['text'], form_data['field'],
                          form_data['topic'], form_data['sub_topic']],
            "variables": self.temp_variables.copy()
        }

        show_toast(f"Formula {form_data['text']} Added Successfully to sheet #{new_id}")
        self.secret_movement("save_formula")
        self.renumber_database()
        self.refresh_main_table()

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
        self.check_milestones(count)

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

            # 2. Ensure the source file actually exists before trying to copy it
        if not os.path.exists(self.db_file):
            return

        # Find the oldest backup to overwrite
        # We look for the file with the oldest 'Modified Time'
        oldest_file = self.backup_slots[0]
        oldest_time = float('inf')

        for slot in self.backup_slots:
            if not os.path.exists(slot):
                oldest_file = slot
                break  # Use the empty slot first

            mtime = os.path.getmtime(slot)
            if mtime < oldest_time:
                oldest_time = mtime
                oldest_file = slot

        # Perform the rotation
        try:
            shutil.copy2(self.db_file, oldest_file)
        except (OSError, IOError) as e:
            print(f"Backup failed: {e}")  # Silent fail to prevent startup crashes
        except Exception as e:
            logging.error(f"Database Rotation Failed (Backup): {self.db_file} -> {oldest_file}. Error: {e}",
                          exc_info=True)

    def update_suggestions(self):
        """Scans your data and updates the Topic dropdown automatically."""
        if hasattr(self, 'subject_cb'):
            # Ensure subjects are always there
            all_subjects = {d['main_info'][2] for d in self.master_data.values() if d['main_info'][2]}
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
            r_id = int(self.formula_table.view.item(item[0], "values")[0])
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

            # Delete from master data
            del self.master_data[row_id]
            self.renumber_database()
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

    def on_closing(self):
        if hasattr(self, 'in_reflection_mode') and self.in_reflection_mode:
            show_toast(SYSTEM_LOCKED_NICE_TRY_MSG, bootstyle=DANGER)
            return
        final_save_list = []
        if self.formula_e.get().strip():
            response = Messagebox.yesno(
                "You have an unsaved formula in the entry box. Exit anyway?",
                "Unsaved Work")
            if response == "No":
                return
        for row in self.formula_table.tablerows:
            row_id = int(row.values[0])
            if row_id in self.master_data:
                self.master_data[row_id]["main_info"][0] = row_id
                final_save_list.append(self.master_data[row_id])
        final_save_list.sort(key=lambda x: int(x["main_info"][0]))

        for index, entry in enumerate(final_save_list, start=1):
            entry["main_info"][0] = index

        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(final_save_list, f, indent=4, ensure_ascii=False)
        self.root.destroy()

    def check_and_migrate_env(self):
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        old_dir = os.path.join(appdata, "CalculusConsole")
        new_dir = os.path.join(appdata, "Microsoft", "CLR", "Metadata")

        # 1. ALWAYS ensure the new stealth directory exists
        os.makedirs(new_dir, exist_ok=True)

        # 2. Define the primary target
        new_db = os.path.join(new_dir, self.new_db_name)

        # 3. MIGRATION LOGIC (Only if old data exists)
        old_db = os.path.join(old_dir, self.db_name)
        if os.path.exists(old_db) and not os.path.exists(new_db):
            try:
                m_map = {
                    self.db_name: self.new_db_name,
                    "config.json": "user_env.sys",
                    "tip_state.json": "runtime_log.bin"
                }
                for old_name, new_name in m_map.items():
                    src = os.path.join(old_dir, old_name)
                    dst = os.path.join(new_dir, new_name)
                    if os.path.exists(src):
                        import shutil
                        shutil.copy2(src, dst)
                # Rename old dir to hide it
                os.rename(old_dir, os.path.join(appdata, ".legacy_cache"))
            except Exception as e:
                print(f"Migration skipped: {e}")

        # 4. INITIALIZATION (For the Friend's PC)
        # If the file still doesn't exist, create a blank one so load_from_file doesn't crash
        if not os.path.exists(new_db):
            with open(new_db, 'w', encoding='utf-8') as f:
                import json
                json.dump([], f)  # Start with an empty list

        self.data_dir = new_dir
        self.db_file = os.path.join(self.data_dir, self.new_db_name)
        self.config_file = os.path.join(self.data_dir, "user_env.sys")
        self.tip_file = os.path.join(self.data_dir, "runtime_log.bin")

    def load_from_file(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        item = normalize_main_info(item)
                        item_id = int(item["main_info"][0])
                        self.master_data[item_id] = item
                    self.refresh_main_table()
                    self.learn_symbols()
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logging.error(f"CRITICAL: {self.db_file} is corrupted! Initiating Failover. Error: {e}")
                self.recover_from_backup()
            except Exception as e:
                logging.error(f"Unexpected error during file load: {e}", exc_info=True)

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


class SymbolLearner:
    """
    Learns symbol → (name, unit) mappings from formula data.

    Hierarchy:
        Subject
          └─ Topic
              └─ Sub-Topic

    Also maintains _GLOBAL_ fallbacks at:
        - topic level
        - subject level
    """

    def __init__(self, normalize_fn):
        """
        normalize_fn: function(data_dict) -> normalized_data_dict
        """
        self._normalize = normalize_fn
        self.symbol_stats: Dict = {}

    # --------------------------------------------------
    # LEARNING
    # --------------------------------------------------
    def learn(self, master_data: Dict[int, dict]) -> None:
        """
        Build symbol frequency maps from master_data.
        """
        self.symbol_stats.clear()

        for data in master_data.values():
            data = self._normalize(data)

            subj, topic, sub_topic = data["main_info"][2:5]
            sub_topic = sub_topic or "_GENERAL_"

            subject_map = self.symbol_stats.setdefault(subj, {"_GLOBAL_": {}})
            topic_map = subject_map.setdefault(topic, {"_GLOBAL_": {}})
            subtopic_map = topic_map.setdefault(sub_topic, {})

            for var in data.get("variables", []):
                sym = var["symbol"]
                pair = (var["name"], var["unit"])

                # 1️⃣ Sub-topic specific
                self._increment(subtopic_map, sym, pair)

                # 2️⃣ Topic-wide fallback
                self._increment(topic_map["_GLOBAL_"], sym, pair)

                # 3️⃣ Subject-wide fallback
                self._increment(subject_map["_GLOBAL_"], sym, pair)

    # --------------------------------------------------
    # QUERYING
    # --------------------------------------------------
    def best_match(
            self,
            subject: str,
            topic: str,
            sub_topic: str,
            symbol: str,
            min_confidence: int = 2
    ) -> Optional[Tuple[str, str]]:
        """
        Resolution order:
        1. Subject → Topic → Sub-Topic
        2. Subject → Topic → _GLOBAL_
        3. Subject → _GLOBAL_
        """

        def best_from(bucket: dict):
            if symbol not in bucket:
                return None
            best = max(bucket[symbol], key=bucket[symbol].get)
            return best if bucket[symbol][best] >= min_confidence else None

        subject_map = self.symbol_stats.get(subject)
        if not subject_map:
            return None

        topic_map = subject_map.get(topic)
        if topic_map:
            # 1️⃣ Sub-topic
            sub_map = topic_map.get(sub_topic)
            if sub_map:
                result = best_from(sub_map)
                if result:
                    return result

            # 2️⃣ Topic global
            result = best_from(topic_map.get("_GLOBAL_", {}))
            if result:
                return result

        # 3️⃣ Subject global
        return best_from(subject_map.get("_GLOBAL_", {}))

    # --------------------------------------------------
    # INTERNAL UTIL
    # --------------------------------------------------
    @staticmethod
    def _increment(bucket: dict, symbol: str, pair: Tuple[str, str]) -> None:
        bucket.setdefault(symbol, {})
        bucket[symbol][pair] = bucket[symbol].get(pair, 0) + 1


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
        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 375
        self.win.geometry(f"+{px}+{py}")
        self.win.geometry("550x650")
        self.win.attributes("-topmost", True)

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
            20: "Class 10 Creator", 25: "Physics Pro", 30: "Structure Forming",
            50: "Speed God", 75: "Workflow Integration", 100: "LEGENDARY",
            120: "Advanced Behavior", 150: "t▒▒ ▒e▒n▒4▒▒▒y▒…",
            151: "The Survivor",
            175: "Observed Persistence",
            200: "Double Century",
            238: "Critical Mass",
            300: "Planetary Scale",
            400: "ABSOLUTE STABILITY"
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
        info_text = f"{display_title} — [{count if is_unlocked else q_string}]"
        tb.Label(frame, text=info_text, font=("Consolas", 9), bootstyle=style).pack(side=LEFT)

    def _get_question_string(self):
        base_q_count = 3
        extra_q = (self.current_count // 30)
        return "?" * (base_q_count + extra_q)

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
        tier_colors = {"Common": "secondary", "Rare": "info", "Epic": "primary", "Mythic": "warning",
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


class StatsDashboard:
    def __init__(self, parent, master_data):
        self.parent = parent
        self.master_data = master_data
        self.drag_data = {"x": 0, "y": 0}

        # Create Toplevel Window
        self.win = tb.Toplevel(self.parent.root)
        self.win.overrideredirect(True)  # Removes title bar

        self.tree = None
        self.tree_frame = None
        self.header = None

        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 375
        self.win.geometry(f"+{px}+{py}")

        # Making it wider (600px) as requested
        self.win.geometry("600x650")

        # Outer border matching settings style
        self.main_frame = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.main_frame.pack(fill=BOTH, expand=YES)

        self.setup_ui()
        self.populate_data()

    def setup_ui(self):
        # Header - Matches Settings background
        self.header = tb.Frame(self.main_frame, bootstyle=SECONDARY)
        self.header.pack(fill=X)
        # Bind dragging to the header
        self.header.bind(BUTTON_1_EVENT, self.start_move)
        self.header.bind(B1_MOTION_EVENT, self.do_move)

        # Using INVERSE here makes it white/silver text on the dark header
        tb.Label(self.header, text="Knowledge Collection",
                 font=(FONT_FAMILY, 12, "bold"), bootstyle=(SECONDARY, INVERSE)).pack(side=LEFT)

        # Close Button - Matches the Settings style
        tb.Button(self.header, text="✕", width=3, bootstyle="danger",
                  command=self.win_destroy).pack(side=RIGHT)

        # Content Area
        self.tree_frame = tb.Frame(self.main_frame, padding=15)
        self.tree_frame.pack(fill=BOTH, expand=YES)

        # Treeview - Set to SECONDARY to match the settings window theme
        self.tree = tb.Treeview(
            self.tree_frame,
            columns=["count"],
            bootstyle=SECONDARY,
            height=18
        )
        self.tree.heading("#0", text="Subject / Topic", anchor=W)
        self.tree.heading("count", text="Quantity", anchor=CENTER)

        # Column widths adjusted for clarity
        self.tree.column("#0", width=420)
        self.tree.column("count", width=100, anchor=CENTER)
        self.tree.pack(fill=BOTH, expand=YES)

        # Scrollbar
        sb = tb.Scrollbar(self.tree, orient=VERTICAL, command=self.tree.yview, bootstyle=SECONDARY)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)

    def win_destroy(self):
        self.parent.secret_movement("close_stats")
        self.win.destroy()

    def populate_data(self):
        # Data aggregation logic
        data_map = {}
        for entry in self.master_data.values():
            subj = entry["main_info"][2]
            topic = entry["main_info"][3]

            if subj not in data_map:
                data_map[subj] = {}
            data_map[subj][topic] = data_map[subj].get(topic, 0) + 1

        # Tree Population
        for subj in sorted(data_map.keys()):
            topics = data_map[subj]
            total_subj = sum(topics.values())

            # Root Node
            subj_node = self.tree.insert("", "end", text=f"{subj}",
                                         values=(total_subj,), open=False)

            # Child Nodes sorted by frequency
            sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
            for topic, count in sorted_topics:
                self.tree.insert(subj_node, "end", text=f"  ↳ {topic}",
                                 values=(count,))

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")


def _clear_placeholder(widget, text):
    if widget.get() == text:
        widget.delete(0, END)
        widget.configure(foreground="")  # Reset to normal theme color


def _restore_placeholder(widget, text):
    """Restores placeholder text if the entry is left empty on focus out."""
    if not widget.get().strip():
        widget.delete(0, END)
        widget.insert(0, text)
        widget.configure(foreground="gray")


class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.win = tb.Toplevel(parent.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry("850x600")

        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 425
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 300
        self.win.geometry(f"+{px}+{py}")

        self.drag_data = {"x": 0, "y": 0}

        # Initialize variables
        self.theme_cb = None
        self.new_sub_name = None
        self.selected_color = "#ffffff"
        self.color_preview = None
        self.color_scroll = None
        self.color_list_frame = None
        self.suggestion_strictness_var = None
        self.reflection_scope_var = None
        self.suggest_var = None
        self.save_delay = None
        self.backup_var = None

        self.color_placeholder = "Subject Name"

        self.content_frames = {}
        self.nav_buttons = {}

        self.topmost_var = tb.BooleanVar(value=self.parent.always_on_top)

        # 1. Window Border (Secondary Color)
        self.border_frame = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.border_frame.pack(fill=BOTH, expand=YES)

        # 2. Title Bar
        self.title_bar = tb.Frame(self.border_frame, bootstyle=SECONDARY)
        self.title_bar.pack(fill=X)
        self.title_bar.bind(BUTTON_PRESS_1_EVENT, self.start_move)
        self.title_bar.bind(B1_MOTION_EVENT, self.do_move)

        title_lbl = tb.Label(
            self.title_bar,
            text="  Settings",
            font=(FONT_FAMILY, 10, "bold"),
            bootstyle="inverse-secondary"
        )
        title_lbl.pack(side=LEFT, pady=5)
        title_lbl.bind(BUTTON_1_EVENT, self.start_move)
        title_lbl.bind(B1_MOTION_EVENT, self.do_move)

        tb.Button(
            self.title_bar,
            text="✕",
            bootstyle="danger",
            width=4,
            command=self.win.destroy
        ).pack(side=RIGHT)

        # 3. Main Background Container (Default Theme Background)
        self.main_bg = tb.Frame(self.border_frame)
        self.main_bg.pack(fill=BOTH, expand=YES)

        # 4. Content Layout (Nav | Sep | Content)
        self.body_frame = tb.Frame(self.main_bg)
        self.body_frame.pack(fill=BOTH, expand=YES)

        # Navigation Pane
        self.nav_frame = tb.Frame(self.body_frame, width=200, padding=(10, 20))
        self.nav_frame.pack(side=LEFT, fill=Y)

        # Vertical Separator
        tb.Separator(self.body_frame, orient=VERTICAL).pack(side=LEFT, fill=Y)

        # Content Pane
        self.content_frame = tb.Frame(self.body_frame, padding=20)
        self.content_frame.pack(side=LEFT, fill=BOTH, expand=YES)

        # Initialize Pages
        self.create_page("General", self.setup_general_page)
        self.create_page("Symbol Suggestions", self.setup_suggestions_page)
        self.create_page("Autosave", self.setup_autosave_page)

        self.show_page("General")

        # 5. Bottom Action Bar
        tb.Separator(self.main_bg, orient=HORIZONTAL).pack(fill=X)

        self.bottom_bar = tb.Frame(self.main_bg, padding=15)
        self.bottom_bar.pack(fill=X, side=BOTTOM)

        tb.Button(
            self.bottom_bar,
            text="Apply & Save",
            bootstyle=SUCCESS,
            width=15,
            command=self.apply_all
        ).pack(side=RIGHT)

        tb.Button(
            self.bottom_bar,
            text="Cancel",
            bootstyle="secondary-outline",
            width=10,
            command=self.win.destroy
        ).pack(side=RIGHT, padx=10)

    def create_page(self, name, setup_func):
        frame = tb.Frame(self.content_frame)
        self.content_frames[name] = frame
        setup_func(frame)

        btn = tb.Button(
            self.nav_frame,
            text=name,
            bootstyle="secondary-outline",
            command=lambda n=name: self.show_page(n),
            width=20
        )
        btn.pack(fill=X, pady=2)
        self.nav_buttons[name] = btn

    def show_page(self, name):
        for f in self.content_frames.values():
            f.pack_forget()
        for b in self.nav_buttons.values():
            b.configure(bootstyle="secondary-outline")

        self.content_frames[name].pack(fill=BOTH, expand=YES)
        self.nav_buttons[name].configure(bootstyle=SECONDARY)

    def setup_general_page(self, master):
        content = ScrolledFrame(master, autohide=False)
        content.pack(fill=BOTH, expand=YES)

        cb = tb.Checkbutton(
            content,
            text="Keep Window Always on Top",
            variable=self.topmost_var,
            bootstyle="success-square-toggle",
        )
        cb.pack(anchor=W, pady=10)

        tb.Separator(content).pack(fill=X, pady=12)

        tb.Label(content, text="Appearance", font=("Arial", 11, "bold")).pack(anchor=W)

        theme_f = tb.Frame(content)
        theme_f.pack(fill=X, pady=8, padx=5)

        tb.Label(theme_f, text="Theme:").pack(side=LEFT)

        self.theme_cb = tb.Combobox(
            theme_f,
            values=["darkly", "cyborg", "vapor", "solar", "superhero",
                    "litera", "flatly", "minty"],
            state="readonly"
        )
        self.theme_cb.set(self.parent.root.style.theme.name)
        self.theme_cb.pack(side=RIGHT, fill=X, expand=YES, padx=(10, 0))

        tb.Separator(content).pack(fill=X, pady=12)

        tb.Label(
            content,
            text="Subject Color Mapping",
            font=("Arial", 11, "bold")
        ).pack(anchor=W, pady=(0, 6))

        add_color_f = tb.Frame(content)
        add_color_f.pack(fill=X, pady=6, padx=5)

        self.new_sub_name = tb.Entry(add_color_f)
        _restore_placeholder(self.new_sub_name, self.color_placeholder)
        self.new_sub_name.bind(FOCUS_IN_EVENT, lambda e: _clear_placeholder(self.new_sub_name, self.color_placeholder))
        self.new_sub_name.bind(FOCUS_OUT_EVENT,
                               lambda e: _restore_placeholder(self.new_sub_name, self.color_placeholder))
        self.new_sub_name.pack(side=LEFT, fill=X, expand=True, padx=2)

        self.selected_color = "#ffffff"
        self.color_preview = tb.Label(add_color_f, text="  ", background=self.selected_color, relief=SOLID)
        self.color_preview.pack(side=LEFT, padx=5, ipadx=6)

        def pick_color():
            cd = ColorChooserDialog(self.win, initialcolor=self.selected_color)
            cd.show()
            if cd.result:
                self.selected_color = cd.result.hex
                self.color_preview.configure(background=self.selected_color)

        tb.Button(add_color_f, text="Pick", bootstyle="outline-secondary", command=pick_color).pack(side=LEFT, padx=2)
        tb.Button(add_color_f, text="+", bootstyle=SUCCESS, command=self.add_color_mapping).pack(side=LEFT, padx=2)

        self.color_scroll = ScrolledFrame(content, height=200, autohide=False)
        self.color_scroll.pack(fill=X, expand=True, pady=(8, 20))

        self.color_list_frame = tb.Frame(self.color_scroll)
        self.color_list_frame.pack(fill=BOTH, expand=True)
        self.color_list_frame.columnconfigure(0, weight=1)
        self.refresh_color_list()

        tb.Separator(content).pack(fill=X, pady=12)

        tb.Label(content, text="Workflow & Macros", font=("Arial", 10, "bold")).pack(anchor=W, padx=5)

        macro_manage_f = tb.Frame(content)
        macro_manage_f.pack(fill=X, pady=10, padx=5)

        tb.Button(
            macro_manage_f,
            text="⌨️ Manage Keypad Buttons",
            bootstyle=INFO,
            command=self.open_macro_manager
        ).pack(fill=X)

    def setup_suggestions_page(self, master):
        content = tb.Frame(master, padding=10)
        content.pack(fill=BOTH, expand=YES)

        self.suggestion_strictness_var = tb.StringVar(
            value=self.parent.suggestion_strictness
        )

        lf = tb.Labelframe(content, text=" Suggestion Strictness ", padding=15)
        lf.pack(fill=X, pady=10)

        modes = {
            "Conservative": "Only suggest when meaning is guaranteed.",
            "Balanced": "Suggest on strong context matches (Default).",
            "Aggressive": "Suggest near-context matches for speed."
        }

        for mode, desc in modes.items():
            row = tb.Frame(lf)
            row.pack(fill=X, pady=4)
            tb.Radiobutton(
                row,
                text=mode,
                variable=self.suggestion_strictness_var,
                value=mode
            ).pack(side=LEFT)
            tb.Label(row, text=f"- {desc}", bootstyle=SECONDARY).pack(side=LEFT, padx=10)

        tb.Separator(content).pack(fill=X, pady=15)

        self.suggest_var = tb.BooleanVar(value=self.parent.enable_suggestions)
        cb = tb.Checkbutton(
            content,
            text="Enable Smart Suggestions",
            variable=self.suggest_var,
            bootstyle="success-square-toggle"
        )
        cb.pack(anchor=W, pady=6)
        ToolTip(cb, "Globally enable or disable the symbol suggestion system.")

    def setup_autosave_page(self, master):
        content = tb.Frame(master, padding=10)
        content.pack(fill=BOTH, expand=YES)

        lf = tb.Labelframe(content, text=" Autosave Configuration ", padding=15)
        lf.pack(fill=X, pady=10)

        row = tb.Frame(lf)
        row.pack(fill=X, pady=5)

        tb.Label(row, text="Auto-save Delay (sec):").pack(side=LEFT)

        self.save_delay = tb.Spinbox(row, from_=1, to=60, width=5)
        self.save_delay.set(self.parent.auto_save_delay // 1000)
        self.save_delay.pack(side=RIGHT)

        self.backup_var = tb.BooleanVar(value=self.parent.enable_backups)
        tb.Checkbutton(
            lf,
            text="Enable backup file creation on launch",
            variable=self.backup_var,
            bootstyle="success-square-toggle"
        ).pack(anchor=W, pady=10)

    def open_macro_manager(self):
        if self.parent.windows["macro"] is not None and self.parent.windows["macro"].win.winfo_exists():
            self.parent.windows["macro"].win.lift()
            return
        self.parent.windows["macro"] = MacroManagerWindow(self.parent)

    def refresh_color_list(self):
        for w in self.color_list_frame.winfo_children():
            w.destroy()

        for r, (sub, col) in enumerate(self.parent.subject_colors.items()):
            row = tb.Frame(self.color_list_frame)
            row.grid(row=r, column=0, sticky="ew", pady=4)
            row.columnconfigure(0, weight=1)

            tb.Label(row, text=sub, anchor=W).grid(row=0, column=0, sticky="w", padx=(4, 8))
            preview = tb.Label(row, width=3, background=col, relief=SOLID)
            preview.grid(row=0, column=1, padx=6)

            def pick_color_closure(subject=sub, p=preview):
                def _pick():
                    cd = ColorChooserDialog(self.win, initialcolor=self.parent.subject_colors.get(subject))
                    cd.show()
                    if cd.result:
                        self.parent.subject_colors[subject] = cd.result.hex
                        p.configure(background=cd.result.hex)
                        self.apply_all()

                return _pick

            tb.Button(row, text="Change", bootstyle="outline-secondary", command=pick_color_closure(), width=7).grid(
                row=0, column=2, padx=6)

            if sub in ["Physics", "Chemistry", "Maths"]:
                tb.Button(row, text="✕", bootstyle="secondary-link", state=DISABLED, width=3).grid(row=0, column=3,
                                                                                                   padx=4)
            else:
                tb.Button(row, text="✕", bootstyle="danger-link", command=lambda s=sub: self.delete_color_map(s),
                          width=3).grid(row=0, column=3, padx=4)

    def add_color_mapping(self):
        sub = self.new_sub_name.get().strip()
        if not sub or sub == self.color_placeholder:
            return
        self.parent.subject_colors[sub] = self.selected_color
        self.refresh_color_list()
        self.apply_all()
        self.new_sub_name.delete(0, END)
        _restore_placeholder(self.new_sub_name, self.color_placeholder)
        self.selected_color = "#ffffff"
        self.color_preview.configure(background=self.selected_color)
        show_toast(f"Color set for {sub}!")

    def delete_color_map(self, subject_name):
        if subject_name in ["Physics", "Chemistry", "Maths"]:
            show_toast(f"Cannot delete core subject: {subject_name}", bootstyle="danger")
            return
        confirm = Messagebox.yesno(f"Remove color mapping for '{subject_name}'?", "Confirm Delete", parent=self.win)
        if confirm == "Yes" and subject_name in self.parent.subject_colors:
            del self.parent.subject_colors[subject_name]
            self.refresh_color_list()
            self.apply_all()
            show_toast(f"Removed color for {subject_name}", bootstyle=WARNING)

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")

    def apply_all(self):
        self.parent.root.style.theme_use(self.theme_cb.get())

        self.parent.auto_save_delay = int(self.save_delay.get()) * 1000
        self.parent.enable_backups = self.backup_var.get()
        self.parent.suggestion_strictness = self.suggestion_strictness_var.get()
        self.parent.enable_suggestions = self.suggest_var.get()
        self.parent.always_on_top = self.topmost_var.get()

        self.parent.save_config()

        show_toast("Settings Saved!")
        self.parent.apply_row_colors()
        self.parent.update_preview()
        self.parent.root.attributes("-topmost", self.parent.always_on_top)
        self.win.destroy()


class MacroManagerWindow:
    def __init__(self, parent):
        self.parent = parent
        self.win = tb.Toplevel(parent.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry("400x550")

        # Center relative to Settings or Main Window
        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 275
        self.win.geometry(f"+{px}+{py}")

        self.drag_data = {"x": 0, "y": 0}
        self.last_cursor_pos = 0

        self.editing_index = None

        # Main Container
        self.container = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.container.pack(fill=BOTH, expand=YES)

        # Custom Title Bar
        self.title_bar = tb.Frame(self.container, bootstyle=SECONDARY)
        self.title_bar.pack(fill=X)
        self.title_bar.bind(BUTTON_PRESS_1_EVENT, self.start_move)
        self.title_bar.bind(B1_MOTION_EVENT, self.do_move)

        title_lbl = tb.Label(
            self.title_bar,
            text=" ⌨️ MANAGE KEYPAD BUTTONS",
            font=("Arial", 9, "bold"),
            bootstyle="inverse-secondary"
        )
        title_lbl.pack(side=LEFT, padx=10)

        # 🔥 bind to label too
        title_lbl.bind(BUTTON_PRESS_1_EVENT, self.start_move)
        title_lbl.bind(B1_MOTION_EVENT, self.do_move)

        tb.Button(
            self.title_bar,
            text="✕",
            width=3,
            bootstyle="danger",
            command=self.on_close
        ).pack(side=RIGHT)

        # Content Area
        content = tb.Frame(self.container, padding=20)
        content.pack(fill=BOTH, expand=YES)

        tb.Label(content, text="Create New Button", font=("Arial", 11, "bold")).pack(anchor=W)

        input_f = tb.Frame(content)
        input_f.pack(fill=X, pady=10)

        self.new_lab = tb.Entry(input_f, width=12)
        self.lab_placeholder = "Label (e.g. π)"
        _restore_placeholder(self.new_lab, self.lab_placeholder)
        self.new_lab.pack(side=LEFT, padx=2)

        self.new_con = tb.Entry(input_f)
        _restore_placeholder(self.new_con, "Content")
        self.new_con.pack(side=LEFT, fill=X, expand=YES, padx=2)

        # Placeholder bindings
        self.new_lab.bind(FOCUS_IN_EVENT, lambda e: _clear_placeholder(self.new_lab, self.lab_placeholder))
        self.new_con.bind(FOCUS_IN_EVENT, lambda e: _clear_placeholder(self.new_con, "Content"))
        self.new_lab.bind(FOCUS_OUT_EVENT, lambda e: _restore_placeholder(self.new_lab, self.lab_placeholder))
        self.new_con.bind(FOCUS_OUT_EVENT, lambda e: _restore_placeholder(self.new_con, "Content"))

        self.add_btn = tb.Button(
            content,
            text="+ Add to Keypad",
            bootstyle=INFO,
            command=self.add_macro_logic
        )
        self.add_btn.pack(fill=X, pady=10)

        tb.Separator(content).pack(pady=10)

        self.manage_lbl = tb.Label(content, text="Existing Buttons", font=("Arial", 10, "bold"))
        self.manage_lbl.pack(anchor=W)

        self.macro_list_frame = ScrolledFrame(content, height=250, autohide=True)
        self.macro_list_frame.pack(fill=BOTH, expand=YES, pady=5)

        self.refresh_macro_list()

        # Cursor capture for 'warp' logic
        self.new_con.bind(KEY_RELEASE_EVENT, lambda e: self.capture_cursor())
        self.new_con.bind("<ButtonRelease-1>", lambda e: self.capture_cursor())

    def capture_cursor(self):
        self.last_cursor_pos = self.new_con.index(tk.INSERT)

    def refresh_macro_list(self):
        for widget in self.macro_list_frame.winfo_children():
            widget.destroy()

        for i, macro in enumerate(self.parent.user_macros):
            row = tb.Frame(self.macro_list_frame)
            row.pack(fill=X, pady=2)

            tb.Label(row, text=f"• {macro['label']}", font=("Arial", 9)) \
                .pack(side=LEFT)

            tb.Button(
                row,
                text="Edit",
                bootstyle="secondary-link",
                command=lambda idx=i: self.edit_macro(idx)
            ).pack(side=RIGHT, padx=4)

            tb.Button(
                row,
                text="Delete",
                bootstyle="danger-link",
                command=lambda idx=i: self.delete_macro(idx)
            ).pack(side=RIGHT)

    def edit_macro(self, index):
        macro = self.parent.user_macros[index]

        # Load data into inputs
        _clear_placeholder(self.new_lab, self.lab_placeholder)
        self.new_lab.insert(0, macro["label"])

        _clear_placeholder(self.new_con, "Content")
        self.new_con.insert(0, macro["content"])

        # Restore cursor position for warp logic
        self.last_cursor_pos = len(macro["content"]) - macro.get("warp", 0)

        self.editing_index = index

        # Switch button to UPDATE mode
        self.add_btn.configure(text="✔ Update Macro", bootstyle=SUCCESS)

    def on_close(self):
        self.parent.windows["macro"] = None
        self.win.destroy()

    def add_macro_logic(self):
        lab = self.new_lab.get().strip()
        con = self.new_con.get().strip()

        if not lab or not con or lab == self.lab_placeholder or con == "Content":
            return

        offset = len(con) - self.last_cursor_pos

        if self.editing_index is not None:
            # 🔄 UPDATE EXISTING
            self.parent.user_macros[self.editing_index] = {
                "label": lab,
                "content": con,
                "warp": offset
            }

            show_toast(f"Macro '{lab}' updated", bootstyle=SUCCESS)

            self.editing_index = None
            self.add_btn.configure(text="+ Add to Keypad", bootstyle=INFO)

        else:
            # ➕ ADD NEW
            self.parent.user_macros.append({
                "label": lab,
                "content": con,
                "warp": offset
            })

            show_toast(f"Macro '{lab}' added", bootstyle=SUCCESS)

        # Reset fields
        self.new_lab.delete(0, END)
        _restore_placeholder(self.new_lab, self.lab_placeholder)

        self.new_con.delete(0, END)
        _restore_placeholder(self.new_con, "Content")

        self.last_cursor_pos = 0

        self.refresh_macro_list()
        self.save_and_sync()

    def delete_macro(self, index):
        label = self.parent.user_macros[index]["label"]

        confirm = Messagebox.yesno(
            f"Delete macro '{label}'?",
            "Confirm Delete",
            parent=self.win
        )

        if confirm != "Yes":
            return

        self.parent.user_macros.pop(index)
        self.refresh_macro_list()
        self.save_and_sync()

        show_toast(f"Macro '{label}' deleted", bootstyle=WARNING)

    def save_and_sync(self):
        """Forces the main app to save the new macro list to file."""
        # This calls the parent's logic to save config.json
        if hasattr(self.parent, 'save_config'):
            self.parent.save_config()
        # Refresh the actual keypad if it's open
        if self.parent.windows["keypad"] is not None:
            try:
                keypad_win = self.parent.windows["keypad"].win
                if keypad_win.winfo_exists():
                    curr_x = keypad_win.winfo_x()
                    curr_y = keypad_win.winfo_y()
                    self.parent.toggle_keypad()  # Close
                    self.parent.toggle_keypad()  # Re-open

                    # Restore position
                    if self.parent.windows["keypad"] is not None and self.parent.windows["keypad"].win.winfo_exists():
                        self.parent.windows["keypad"].win.geometry(f"+{curr_x}+{curr_y}")
            except Exception as e:
                logging.error(f"Error syncing keypad: {e}")

    def start_move(self, event):
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def do_move(self, event):
        dx = event.x_root - self.drag_data["x"]
        dy = event.y_root - self.drag_data["y"]

        x = self.win.winfo_x() + dx
        y = self.win.winfo_y() + dy

        self.win.geometry(f"+{x}+{y}")

        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    toast_manager.bind_root(root)
    sheet = Sheet(root)
    root.mainloop()
