import json
import os
import shutil

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from ttkbootstrap.widgets.tableview import Tableview
from ttkbootstrap.widgets.tooltip import ToolTip
from ttkbootstrap.widgets.toast import ToastNotification
import logging

logging.basicConfig(level=logging.INFO)


def show_toast(message, bootstyle=SUCCESS):
    """Displays a temporary notification at the bottom of the screen."""
    toast = ToastNotification(
        title="Calculus Console",
        message=message,
        duration=10000,  # Your 6-second preference
        bootstyle=bootstyle,
        position=(10, 60, 'se')  # 'se' stands for South-East (Bottom Right)
    )
    toast.show_toast()


class Sheet:
    def __init__(self, f_sheet):
        self.root = f_sheet
        self.root.title("Calculus Console")
        self.root.geometry("1000x900")
        self.root.minsize(900, 870)
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Update your file paths to live inside that folder
        self.db_file = os.path.join(self.data_dir, "formula_data.json")
        self.config_file = os.path.join(self.data_dir, "config.json")
        self.tip_file = os.path.join(self.data_dir, "tip_state.json")

        self.tip_state = self.load_tip_state()

        self.master_data = {}
        self.temp_variables = []
        self.editing_mode = False
        self.edit_id = None

        self.auto_save_timer = None

        self.last_focused_widget = None
        self.keypad_window = None
        self.drag_x = 0
        self.drag_y = 0

        self.symbol_stats = {}
        self.symbol_kb = {}  # Format: {Field: {Symbol: {"name": name, "unit": unit}}}
        self.ghost_active = False

        self.auto_save_delay = 5000
        self.enable_backups = True
        self.enable_suggestions = True
        self.settings_window = None
        self.user_macros = []

        self.formula_e = tb.StringVar()
        self.field_e = tb.StringVar()
        self.topic_e = tb.StringVar()

        self.cols = [
            {"text": "No.", "stretch": False, "width": 60},
            {"text": "Formula", "stretch": True},
            {"text": "Field", "stretch": False, "width": 120},
            {"text": "Topic", "stretch": True},
        ]

        self.mainframe = tb.Frame(self.root, padding=10)
        self.mainframe.pack(fill=BOTH, expand=YES)

        # 1. MAIN TABLE
        self.table_frame = tb.Frame(self.mainframe, height=350)
        self.table_frame.pack_propagate(False)
        self.table_frame.pack(fill=X, side=TOP, pady=(0, 10))

        self.help_table = tb.Button(self.table_frame,
                                    text="?", width=3,
                                    bootstyle="info-outline")
        self.help_table.pack(side=RIGHT, anchor=N, padx=5)
        ToolTip(self.help_table, text="Double-click a row to View Details or Edit the formula."
                                      "\nRight click on a row for more options.")

        self.formula_table = Tableview(master=self.table_frame,
                                       coldata=self.cols,
                                       searchable=True,
                                       paginated=True,
                                       bootstyle=INFO,
                                       )
        self.formula_table.pack(fill=BOTH, expand=YES)
        self.formula_table.view.tag_configure("physics_row", foreground="#5dade2")  # Light Blue
        self.formula_table.view.tag_configure("chemistry_row", foreground="#58d68d")  # Light Green
        self.formula_table.view.tag_configure("maths_row", foreground="#af7ac5")  # Lavender
        self.formula_table.view.tag_configure("other_row", foreground="#cccccc")
        self.formula_table.view.bind("<<TreeviewSelect>>", lambda e: self.root.after(1, self.apply_row_colors))

        # 2. ENTRY SECTION
        self.data_entry_frame = tb.Labelframe(self.mainframe, text=" Formula Entry ", padding=20)
        self.data_entry_frame.pack(fill=BOTH, expand=YES)
        self.data_entry_frame.columnconfigure(1, weight=1)

        # Main Fields with Focus Binding
        fields = [("Formula:", self.formula_e), ("Field:", self.field_e), ("Topic:", self.topic_e)]
        for i, (label, var) in enumerate(fields):
            tb.Label(self.data_entry_frame,
                     text=label
                     ).grid(row=i, column=0, sticky=W, pady=5)
            if label == "Field:":
                self.subject_cb = tb.Combobox(self.data_entry_frame,
                                              values=["Physics", "Chemistry", "Maths"],
                                              textvariable=var)
                self.subject_cb.bind("<<ComboboxSelected>>", self.on_subject_change)
                self.subject_cb.bind("<KeyRelease>", self.on_subject_change)
                # ADD THIS: Update preview when subject changes
                self.subject_cb.bind("<<ComboboxSelected>>", lambda e: self.update_preview(), add="+")
                widget = self.subject_cb
            elif label == "Topic:":
                self.topic_cb = tb.Combobox(self.data_entry_frame,
                                            values=[],
                                            textvariable=var)
                # ADD THIS: Update preview when topic changes
                self.topic_cb.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
                widget = self.topic_cb
            else:
                widget = tb.Entry(self.data_entry_frame, textvariable=var)

            # BIND FOCUS EVENT
            widget.bind("<FocusIn>", self.handle_focus)
            widget.grid(row=i, column=1, sticky=EW, padx=10)

        # 3. VARIABLE MANAGEMENT
        var_mgmt_frame = tb.Labelframe(self.data_entry_frame,
                                       text=" Variables ",
                                       padding=10)
        var_mgmt_frame.grid(row=3, column=0,
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

        tb.Button(input_row, text="+",
                  bootstyle=SUCCESS,
                  command=self.add_variable
                  ).pack(side=LEFT, padx=2)

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

        tb.Button(btn_row, text="Edit Selected",
                  bootstyle="warning-outline",
                  command=self.load_variable_to_fix).pack(
            side=LEFT, padx=5)
        tb.Button(btn_row, text="Delete Selected",
                  bootstyle="danger-outline",
                  command=self.remove_variable).pack(
            side=LEFT, padx=5)

        # --- NEW KEYPAD BUTTON ---
        self.keypad_btn = tb.Button(btn_row, text="⌨", bootstyle="secondary", command=self.toggle_keypad)
        self.keypad_btn.pack(side=LEFT, padx=(20, 0))

        # Change your settings button to this:
        self.settings_btn = tb.Button(btn_row, text="⛭", bootstyle="secondary",
                                      command=self.open_settings)
        self.settings_btn.pack(side=LEFT, padx=5)
        # -------------------------

        self.help_var = tb.Button(btn_row, text="?", width=3, bootstyle="info-outline")
        self.help_var.pack(side=RIGHT, padx=5)
        ToolTip(self.help_var,
                text="1. Add variables using '+'."
                     "\n2. Fix typos via 'Edit Selected'."
                     "\n3. Use ⌨ for special symbols."
                     "\nKEYBOARD SHORTCUTS:"
                     "\n• Ctrl+s: Save Formula"
                     "\n• Ctrl+n: New/Clear"
                     "\n• Ctrl+, : Settings"
                     "\n• Ctrl+Backspace: Delete Variable"
                )

        self.save_btn = tb.Button(self.data_entry_frame, text="Save Formula", width=20, bootstyle=INFO,
                                  command=self.save_to_table)
        self.save_btn.grid(row=4, column=1, sticky=E, pady=10)

        self.details_frame = tb.Frame(self.mainframe)
        self.formula_table.view.bind("<Double-1>", self.on_double_click)
        self.root.bind("<Control-k>", lambda e: self.toggle_keypad())
        self.root.bind("<Control-n>", lambda e: self.clear_entries())
        self.root.bind("<Control-comma>", lambda e: self.open_settings())
        self.root.bind("<Control-BackSpace>", lambda e: self.remove_variable())
        self.root.bind("<Control-s>", self.save_to_table)
        self.formula_e_widget = self.data_entry_frame.grid_slaves(row=0, column=1)[0]
        self.formula_e_widget.bind('<Return>', lambda e: self.subject_cb.focus())
        self.subject_cb.bind('<Return>', lambda e: self.topic_cb.focus())
        self.topic_cb.bind('<Return>', lambda e: self.v_sym.focus())
        self.v_sym.bind('<Return>', lambda e: self.v_name.focus())
        self.v_name.bind('<Return>', lambda e: self.v_unit.focus())
        self.v_unit.bind('<Return>', lambda e: self.add_variable())
        self.bind_autosave_widgets()
        self.v_sym.bind("<KeyRelease>", self.update_preview)
        self.v_sym.bind("<Tab>", self.auto_fill_variable)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_from_file()
        self.create_backup()
        self.load_config()
        self.update_suggestions()

    # ==========================================================
    # FOCUS & KEYPAD LOGIC (UPDATED WITH DRAG)
    # ==========================================================

    def trigger_auto_save(self, *args):
        """Resets the timer every time the user types."""
        if self.auto_save_timer is not None:
            self.root.after_cancel(self.auto_save_timer)
        # Wait for 3000ms (3 seconds) of silence before saving
        self.auto_save_timer = self.root.after(self.auto_save_delay, self.perform_silent_save)

    def load_tip_state(self):
        if os.path.exists(self.tip_file):
            try:
                with open(self.tip_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
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
            return

        count = self.tip_state["counters"].get(tip_id, 0) + 1
        self.tip_state["counters"][tip_id] = count

        if count >= min_count:
            show_toast(message, bootstyle=INFO)
            self.tip_state["shown"][tip_id] = True
            self.save_tip_state()

    def setup_entry(self, widget, placeholder_text=""):
        """Utility to attach all required ghost and focus bindings to an entry."""
        widget.placeholder = placeholder_text

        if placeholder_text:
            widget.insert(0, placeholder_text)
            widget.configure(foreground="gray")

        widget.bind("<FocusIn>", self.on_entry_focus_in)
        widget.bind("<FocusOut>", self.on_entry_focus_out)
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
        if self.settings_window is not None and self.settings_window.win.winfo_exists():
            self.settings_window.win.lift()  # Bring existing window to front
            return
        self.settings_window = SettingsWindow(self, self.root.style.theme.name)

    def load_config(self):
        """Loads saved preferences on startup."""
        if os.path.exists("data/config.json"):
            with open("data/config.json", "r") as f:
                cfg = json.load(f)
                self.root.style.theme_use(cfg.get("theme", "darkly"))
                self.auto_save_delay = cfg.get("delay", 5000)
                self.enable_backups = cfg.get("backups", True)
                self.enable_suggestions = cfg.get("suggestions", True)
                self.user_macros = cfg.get("macros", [])

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
                    w.configure(foreground="")  # Reset to normal text color

        # 2. GHOST TEXT LOGIC
        if self.ghost_active:
            if widget == self.v_name or widget == self.v_unit:
                self.v_name.delete(0, END)
                self.v_unit.delete(0, END)
                self.v_name.configure(foreground="")
                self.v_unit.configure(foreground="")
                self.ghost_active = False  # No longer a ghost, it's manual now.

                self.show_tip_once(
                    "manual_override",
                    "Nice — you’re defining variables confidently now.",
                    min_count=4
                )
            elif widget == self.v_sym:
                pass

    def on_entry_focus_out(self, event):
        """Restores placeholders only if the entire group loses focus."""
        # Small delay to see where the focus went
        self.root.after(100, self._check_group_focus)

    def _check_group_focus(self):
        """Restores placeholders only if NO field is focused and NO ghost text exists."""
        main_group = [self.v_sym, self.v_name, self.v_unit]

        try:
            focused = self.root.focus_get()
        except KeyError:
            return  # Handle 'popdown' error

        # 1. If still editing any variable field, do nothing
        if focused in main_group:
            return

        # 2. If we left the group, check if we should restore placeholders
        if not self.ghost_active:
            # Try to find a suggestion first (e.g. if we left the box but symbol is valid)
            self.update_preview()

            # If still no ghost text, put placeholders back
            if not self.ghost_active:
                for w in main_group:
                    placeholder = getattr(w, 'placeholder', None)
                    # Only insert if empty
                    if not w.get().strip() and placeholder:
                        w.insert(0, placeholder)
                        w.configure(foreground="gray")

    def run_macro(self, content):
        """Types out a custom string into the last focused widget."""
        if self.last_focused_widget:
            self.last_focused_widget.focus_set()
            self.last_focused_widget.insert(INSERT, content)
            self.ghost_active = False

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
        self.show_tip_once(
            "symbol_mastery",
            "You’re starting to recognize symbols without suggestions 👍",
            min_count=5
        )

    def insert_symbol(self, symbol):
        """Inserts symbol into the last focused widget."""
        if self.last_focused_widget:
            try:
                self.last_focused_widget.insert(INSERT, symbol)
                self.last_focused_widget.focus_set()  # Return focus so they can keep typing
            except AttributeError:
                pass
            except Exception:
                pass

    def start_move(self, event):
        """Record the initial mouse position when clicking the drag handle."""
        self.drag_x = event.x
        self.drag_y = event.y

    def do_move(self, event):
        """Calculate new position and move the window."""
        x = self.keypad_window.winfo_x() - self.drag_x + event.x
        y = self.keypad_window.winfo_y() - self.drag_y + event.y
        self.keypad_window.geometry(f"+{x}+{y}")

    def toggle_keypad(self):
        """Opens or closes the floating symbol keypad."""
        if self.keypad_window is not None:
            self.keypad_window.destroy()
            self.keypad_window = None
            return

        # Create Popup
        self.keypad_window = tb.Toplevel(self.root)
        self.keypad_window.overrideredirect(True)  # No title bar
        self.keypad_window.attributes('-topmost', True)  # Always on top

        # Position near the button (approximate)
        x = self.keypad_btn.winfo_rootx()
        y = self.keypad_btn.winfo_rooty() - 530
        self.keypad_window.geometry(f"+{x}+{y}")

        # --- DRAG HANDLE (The "Little Area") ---
        drag_handle = tb.Frame(self.keypad_window, bootstyle="secondary", height=20)
        drag_handle.pack(fill=X)

        # Add a grip visual
        grip_lbl = tb.Label(drag_handle, text=":::: Grip to Move ::::", bootstyle="inverse-secondary",
                            font=("Arial", 8))
        grip_lbl.pack(pady=2)

        # Bind events for dragging
        drag_handle.bind("<Button-1>", self.start_move)
        drag_handle.bind("<B1-Motion>", self.do_move)
        grip_lbl.bind("<Button-1>", self.start_move)
        grip_lbl.bind("<B1-Motion>", self.do_move)
        # ---------------------------------------

        # Main Container
        p_frame = tb.Frame(self.keypad_window, padding=5, bootstyle="dark")
        p_frame.pack(fill=BOTH, expand=YES)

        symbol_sets = [
            ["π", "θ", "λ", "Δ", "ρ", "ω", "Ω", "μ", "α", "β"],
            ["·", "×", "÷", "±", "≈", "√", "°", "∞", "≠", "≤"],
            ["⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"],
            ["₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉"]
        ]

        for r_idx, row_syms in enumerate(symbol_sets):
            row_f = tb.Frame(p_frame)
            row_f.pack(fill=X, pady=1)
            for sym in row_syms:
                # Use lambda to capture the specific symbol
                btn = tb.Button(row_f, text=sym, width=3, bootstyle="secondary",
                                command=lambda s=sym: self.insert_symbol(s),
                                takefocus=False)  # Important: Don't steal focus!
                btn.pack(side=LEFT, padx=1)

        if self.user_macros:
            tb.Separator(p_frame, bootstyle="secondary").pack(fill=X, pady=10)
            # Create a frame for user buttons
            u_row = tb.Frame(p_frame, bootstyle="dark")
            u_row.pack(fill=X, pady=2)

            for i, m in enumerate(self.user_macros):
                # Wrap to new row every 5 buttons
                if i > 0 and i % 5 == 0:
                    u_row = tb.Frame(p_frame, bootstyle="dark")
                    u_row.pack(fill=X, pady=2)

                tb.Button(u_row, text=m['label'], bootstyle="info-outline",
                          command=lambda c=m['content']: self.run_macro(c),
                          takefocus=False).pack(side=LEFT, padx=2, expand=YES, fill=X)

        self.show_tip_once(
            "keypad_shortcut",
            "Tip: Press Ctrl+K to toggle the keypad instantly.",
            min_count=5
        )

    def bind_autosave_widgets(self):
        widgets = [
            self.formula_e,
            self.v_sym,
            self.v_name,
            self.v_unit,
            self.subject_cb,
            self.topic_cb
        ]
        for w in widgets:
            try:
                w.bind("<Key>", self.trigger_auto_save)
                w.bind("<FocusOut>", self.trigger_auto_save)
            except Exception:
                pass

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
                Messagebox.show_error(f"Symbol '{sym}' is already defined for this formula!", "Duplicate Symbol")
                return
            self.temp_variables.append({"symbol": sym, "name": name, "unit": unit})
            self.refresh_staging_table()
            self.v_sym.delete(0, END)
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)
            self.v_sym.focus()

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
            show_toast(f"Variable '{val[0]}' Removed", bootstyle=SECONDARY)

    def learn_symbols(self):
        """
        Builds a frequency map of symbols.
        Learns based on Subject, Topic, and Case-sensitivity.
        """
        for data in self.master_data.values():
            subj = data["main_info"][2]
            topic = data["main_info"][3]

            if subj not in self.symbol_stats:
                self.symbol_stats[subj] = {"_GLOBAL_": {}}  # _GLOBAL_ is subject-wide fallback
            if topic not in self.symbol_stats[subj]:
                self.symbol_stats[subj][topic] = {}

            for var in data["variables"]:
                sym = var["symbol"]  # Case-sensitive as you specified
                name_unit = (var["name"], var["unit"])

                # 1. Update Topic-specific counts
                topic_map = self.symbol_stats[subj][topic]
                if sym not in topic_map: topic_map[sym] = {}
                topic_map[sym][name_unit] = topic_map[sym].get(name_unit, 0) + 1

                # 2. Update Subject-wide counts
                global_map = self.symbol_stats[subj]["_GLOBAL_"]
                if sym not in global_map: global_map[sym] = {}
                global_map[sym][name_unit] = global_map[sym].get(name_unit, 0) + 1

    def get_best_match(self, subj, topic, sym, min_confidence=2):
        """
        Returns (name, unit) only if the symbol usage is confident enough.
        Prevents one-off mistakes from polluting suggestions.
        """
        if subj in self.symbol_stats and topic in self.symbol_stats[subj]:
            topic_map = self.symbol_stats[subj][topic]
            if sym in topic_map:
                matches = topic_map[sym]
                best = max(matches, key=matches.get)
                if matches[best] >= min_confidence:
                    return best

        if subj in self.symbol_stats and sym in self.symbol_stats[subj]["_GLOBAL_"]:
            matches = self.symbol_stats[subj]["_GLOBAL_"][sym]
            best = max(matches, key=matches.get)
            if matches[best] >= min_confidence:
                return best

        return None

    def update_preview(self, event=None):
        """Updates preview and injects/clears ghost text based on current context."""
        if not self.enable_suggestions:
            return

        subj = self.field_e.get().strip()
        topic = self.topic_e.get().strip()
        sym = self.v_sym.get().strip()

        # Ignore if symbol box is empty or just holding the placeholder
        placeholder = getattr(self.v_sym, 'placeholder', None)
        if not sym or (placeholder and sym == placeholder):
            self._clear_ghosts()
            return

        # Get match based on NEW Subject/Topic
        match = self.get_best_match(subj, topic, sym)

        if match:
            name, unit = match
            # If we have a match, enforce it (unless user is manually typing in Name/Unit)
            focused = self.root.focus_get()
            if focused != self.v_name and focused != self.v_unit:
                self.apply_ghost_text(name, unit)
        else:
            # CRITICAL: If no match found in this new Topic, WIPE the old ghost text
            self._clear_ghosts()

    def _clear_ghosts(self):
        """Helper to safely remove ghost text without touching real user input."""
        if self.ghost_active:
            self.v_name.delete(0, END)
            self.v_unit.delete(0, END)
            self.ghost_active = False

    def auto_fill_variable(self, event):
        """Accepts the suggestion (solidifies ghost text)."""
        if self.ghost_active:
            self.solidify_ghost_text()
            self.v_name.focus()
            return "break"

        subj = self.field_e.get().strip()
        topic = self.topic_e.get().strip()
        sym = self.v_sym.get().strip()

        match = self.get_best_match(subj, topic, sym)
        if match:
            name, unit = match
            self.v_name.delete(0, END)
            self.v_name.insert(0, name)
            self.v_unit.delete(0, END)
            self.v_unit.insert(0, unit)
            self.v_name.focus()
            return "break"
        return None

    def apply_row_colors(self):
        view = self.formula_table.view
        for iid in view.get_children():
            values = view.item(iid, "values")
            if not values or len(values) < 3:
                continue

            field = str(values[2]).strip()

            tag = {
                "Physics": "physics_row",
                "Chemistry": "chemistry_row",
                "Maths": "maths_row"
            }.get(field, "other_row")

            view.item(iid, tags=(tag,))

    def refresh_main_table(self):
        rows = [v["main_info"] for v in self.master_data.values()]
        rows.sort(key=lambda x: int(x[0]))
        # noinspection PyTypeChecker
        self.formula_table.build_table_data(coldata=self.cols, rowdata=rows)
        self.formula_table.load_table_data()

        self.apply_row_colors()

    def validate_formula_entry(self):
        if not self.formula_e.get().strip():
            Messagebox.show_warning("Formula cannot be empty.", "Validation Error")
            return False

        if not self.field_e.get().strip():
            Messagebox.show_warning("Please select a Field.", "Validation Error")
            return False

        return True

    def renumber_database(self):
        new_master = {}
        current_rows = self.formula_table.tablerows
        for index, row in enumerate(current_rows, start=1):
            old_id = int(row.values[0])
            if old_id in self.master_data:
                data = self.master_data[old_id]
                data["main_info"][0] = index
                new_master[index] = data
        self.master_data = new_master
        self.refresh_main_table()

    def save_to_table(self):
        if not self.validate_formula_entry():
            return
        visible_ids = [int(row.values[0]) for row in self.formula_table.tablerows]
        for stored_id in list(self.master_data.keys()):
            if stored_id not in visible_ids:
                if not (self.editing_mode and stored_id == self.edit_id):
                    del self.master_data[stored_id]

        f_text = self.formula_e.get().strip()
        f_field = self.field_e.get().strip()
        f_topic = self.topic_e.get().strip()

        if not f_text: return

        if not self.editing_mode:
            existing_formulas = [d['main_info'][1] for d in self.master_data.values()]
            if f_text in existing_formulas:
                Messagebox.show_warning(f"The formula '{f_text}' already exists in your sheet!",
                                        "Duplicate Formula")
                return

        if self.v_sym.get().strip(): self.add_variable()

        if self.editing_mode:
            target_id = self.edit_id
            self.master_data[target_id] = {"main_info": [target_id, f_text, f_field, f_topic],
                                           "variables": self.temp_variables.copy()}
            show_toast(f"Formula {f_text} Changed Successfully")
            self.editing_mode = False
            self.save_btn.configure(text="Save Formula", bootstyle=INFO)
        else:
            new_id = max(self.master_data.keys(), default=0) + 1
            self.master_data[new_id] = {"main_info": [new_id, f_text, f_field, f_topic],
                                        "variables": self.temp_variables.copy()}
            show_toast(f"Formula {f_text} Added Successfully to sheet #{new_id}")

        self.refresh_main_table()
        self.clear_entries()
        self.renumber_database()
        self.learn_symbols()
        self.update_suggestions()
        unique_symbols = {
            v["symbol"]
            for d in self.master_data.values()
            for v in d["variables"]
        }

        if len(unique_symbols) >= 10:
            self.show_tip_once(
                "symbol_consistency",
                "You’re building a consistent symbol system across formulas.",
                min_count=3
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

            # 3. Define the 3 backup slots
        backup_slots = [
            os.path.join(self.data_dir, "formula_data_1.bak"),
            os.path.join(self.data_dir, "formula_data_2.bak"),
            os.path.join(self.data_dir, "formula_data_3.bak")
        ]

        # Find the oldest backup to overwrite
        # We look for the file with the oldest 'Modified Time'
        oldest_file = backup_slots[0]
        oldest_time = float('inf')

        for slot in backup_slots:
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
        except Exception:
            pass  # Silent fail to prevent startup crashes

    def update_suggestions(self):
        """Scans your data and updates the Topic dropdown automatically."""
        if hasattr(self, 'subject_cb'):
            # Ensure subjects are always there
            all_subjects = set(d['main_info'][2] for d in self.master_data.values() if d['main_info'][2])
            self.subject_cb['values'] = sorted(list(all_subjects | {"Physics", "Chemistry", "Maths"}))

    def on_subject_change(self, event=None):
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

        self.topic_cb['values'] = sorted(list(topics_for_subject))

        # 3. FORCE UPDATE: Check if the current symbol means something new now
        self.update_preview()

    def clear_entries(self):
        self.formula_e.set("")
        self.topic_e.set("")
        self.field_e.set("")
        self.v_sym.delete(0, END)
        self.v_name.delete(0, END)
        self.v_unit.delete(0, END)
        self.temp_variables = []
        self.topic_cb['values'] = []
        self.refresh_staging_table()

    def on_double_click(self, event):
        item = self.formula_table.view.selection()
        if item:
            row_id = int(self.formula_table.view.item(item[0], "values")[0])
            if row_id in self.master_data:
                self.show_formula_details(self.master_data[row_id])

    def start_edit(self, data):
        self.editing_mode = True
        self.edit_id = data["main_info"][0]
        self.hide_details()
        self.formula_e.set(data["main_info"][1])
        self.field_e.set(data["main_info"][2])
        self.topic_e.set(data["main_info"][3])
        self.temp_variables = data["variables"].copy()
        self.on_subject_change()
        self.refresh_staging_table()
        self.save_btn.configure(text="Update Formula", bootstyle=WARNING)

    def on_closing(self):
        final_save_list = []
        if self.formula_e.get().strip():
            response = Messagebox.yesno("You have an unsaved formula in the entry box. Exit anyway?", "Unsaved Work")
            if response == "No":
                return
        for row in self.formula_table.tablerows:
            row_id = int(row.values[0])
            if row_id in self.master_data:
                self.master_data[row_id]["main_info"][0] = row_id
                final_save_list.append(self.master_data[row_id])

        final_save_list.sort(key=lambda x: int(x["main_info"][0]))
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(final_save_list, f, indent=4, ensure_ascii=False)
        self.root.destroy()

    def load_from_file(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        item_id = int(item["main_info"][0])
                        self.master_data[item_id] = item
                    self.refresh_main_table()
                    self.learn_symbols()
            except json.JSONDecodeError:
                print("Error: Could not read JSON. File might be corrupted.")

    def show_formula_details(self, data):
        self.data_entry_frame.pack_forget()
        for w in self.details_frame.winfo_children(): w.destroy()
        tb.Label(self.details_frame, text=data["main_info"][1], font=("Consolas", 24, "bold"), bootstyle=SUCCESS).pack(
            pady=20)
        tb.Label(self.details_frame, text=f"Field: {data['main_info'][2]} | Topic: {data['main_info'][3]}",
                 font=("Arial", 12)).pack(pady=5)
        if data['variables']:
            vt = Tableview(master=self.details_frame, coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                                                               {"text": "Name", "stretch": True},
                                                               {"text": "Unit", "stretch": True}],
                           rowdata=[(v['symbol'], v['name'], v['unit']) for v in data['variables']],
                           bootstyle=SECONDARY, height=6)
            vt.pack(fill=X, padx=50, pady=20)
        btn_f = tb.Frame(self.details_frame)
        btn_f.pack(pady=10)
        tb.Button(btn_f, text="Edit Formula", bootstyle=WARNING, command=lambda: self.start_edit(data)).pack(side=LEFT,
                                                                                                             padx=10)
        tb.Button(btn_f, text="← Back", bootstyle="outline-info", command=self.hide_details).pack(side=LEFT, padx=10)
        self.details_frame.pack(fill=BOTH, expand=YES)

    def hide_details(self):
        self.details_frame.pack_forget()
        self.data_entry_frame.pack(fill=BOTH, expand=YES)


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
    def __init__(self, parent, current_theme):
        self.parent = parent
        self.win = tb.Toplevel(parent.root)
        self.win.overrideredirect(True)  # Remove title bar
        self.win.attributes("-topmost", True)
        self.win.geometry("460x670")

        # Center the window relative to parent
        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 375
        self.win.geometry(f"+{px}+{py}")

        self.drag_data = {"x": 0, "y": 0}

        # Main Container with border
        self.container = tb.Frame(self.win, bootstyle="secondary", padding=2)
        self.container.pack(fill=BOTH, expand=YES)

        # --- Custom Title Bar (Draggable) ---
        self.title_bar = tb.Frame(self.container, bootstyle="secondary")
        self.title_bar.pack(fill=X)
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)

        tb.Label(self.title_bar, text=" CONSOLE SETTINGS", font=("Arial", 9, "bold"),
                 bootstyle="inverse-secondary").pack(side=LEFT, padx=10)

        tb.Button(self.title_bar, text="✕", width=3, bootstyle="danger",
                  command=self.win.destroy).pack(side=RIGHT)

        # --- Content Area ---
        content = tb.Frame(self.container, padding=20)
        content.pack(fill=BOTH, expand=YES)

        tb.Label(content, text="Appearance", font=("Arial", 11, "bold")).pack(anchor=W)

        theme_f = tb.Frame(content)
        theme_f.pack(fill=X, pady=10)
        tb.Label(theme_f, text="Theme:").pack(side=LEFT)

        self.theme_cb = tb.Combobox(theme_f, values=["darkly", "cyborg", "vapor", "solar", "superhero"],
                                    state="readonly")
        self.theme_cb.set(current_theme)
        self.theme_cb.pack(side=RIGHT, fill=X, expand=YES, padx=(10, 0))

        tb.Separator(content).pack(pady=15)

        # 2. Auto-Save Interval (Now manual!)
        tb.Label(content, text="Automation", font=("Arial", 10, "bold")).pack(anchor=W)
        a_frame = tb.Frame(content)
        a_frame.pack(fill=X, pady=5)
        tb.Label(a_frame, text="Auto-save Delay (sec):").pack(side=LEFT)
        self.save_delay = tb.Spinbox(a_frame, from_=1, to=60, width=5)
        self.save_delay.set(parent.auto_save_delay // 1000)
        self.save_delay.pack(side=RIGHT)

        # 3. Backup Toggle
        self.backup_var = tb.BooleanVar(value=parent.enable_backups)
        tb.Checkbutton(content, text="Enable backup file creation on launch",
                       variable=self.backup_var,
                       bootstyle="success-square-toggle").pack(anchor=W, pady=10)

        self.suggest_var = tb.BooleanVar(value=parent.enable_suggestions)
        tb.Checkbutton(content, text="Enable smart suggestions",
                       variable=self.suggest_var,
                       bootstyle="success-square-toggle").pack(anchor=W, pady=10)
        # --- Footer ---

        tb.Separator(content).pack(pady=15)
        tb.Label(content, text="Custom Keypad Buttons", font=("Arial", 10, "bold")).pack(anchor=W)

        macro_f = tb.Frame(content)
        macro_f.pack(fill=X, pady=5)

        # Standard Entry (no placeholder_text attribute exists)
        self.new_lab = tb.Entry(macro_f, width=10)
        self.new_lab.insert(0, "Label (e.g. π)")
        self.new_lab.configure(foreground="gray")
        self.new_lab.pack(side=LEFT, padx=2)

        self.new_con = tb.Entry(macro_f)
        self.new_con.insert(0, "Content to insert")
        self.new_con.configure(foreground="gray")
        self.new_con.pack(side=LEFT, fill=X, expand=YES, padx=2)

        self.new_lab.bind("<FocusIn>",
                          lambda e: _clear_placeholder(self.new_lab, "Label (e.g. π)"))
        self.new_con.bind("<FocusIn>",
                          lambda e: _clear_placeholder(self.new_con, "Content to insert"))
        self.new_lab.bind("<FocusOut>",
                          lambda e: _restore_placeholder(self.new_lab, "Label (e.g. π)"))
        self.new_con.bind("<FocusOut>",
                          lambda e: _restore_placeholder(self.new_con, "Content to insert"))

        # Add Button
        tb.Button(content, text="+ Add to Keypad", bootstyle=INFO,
                  command=self.add_macro_logic).pack(fill=X, pady=5)

        tb.Label(content, text="Manage Current Buttons", font=("Arial", 10, "bold")).pack(anchor=W, pady=(10, 0))

        # THIS IS THE KEY: A dedicated frame for the list
        self.macro_list_frame = ScrolledFrame(content, height=80, autohide=True)
        self.macro_list_frame.pack(fill=BOTH, expand=YES, pady=5)

        # Initial build of the list
        self.refresh_macro_list()

        # Save Button (Move to the very bottom)
        tb.Button(content, text="Save & Apply Config", bootstyle=SUCCESS,
                  command=self.apply_all).pack(side=BOTTOM, fill=X, pady=(20, 0))

    def refresh_macro_list(self):
        """Clears and rebuilds only the macro list section."""
        # Wipe only the children of the list frame

        if not self.parent.user_macros:
            self.macro_list_frame.pack_forget()  # Hide the list
            # If you put the "Manage" label in a variable like self.manage_lbl:
            # self.manage_lbl.pack_forget()
            return
        self.macro_list_frame.pack(fill=BOTH, expand=YES, pady=5)

        for widget in self.macro_list_frame.winfo_children():
            widget.destroy()

        # Rebuild the rows
        for i, macro in enumerate(self.parent.user_macros):
            row = tb.Frame(self.macro_list_frame)
            row.pack(fill=X, pady=2)

            tb.Label(row, text=f"• {macro['label']}", font=("Arial", 9)).pack(side=LEFT)

            # Delete button - uses the helper to avoid window destruction
            tb.Button(row, text="Delete", bootstyle="danger-link",
                      command=lambda idx=i: self.delete_macro(idx)).pack(side=RIGHT)

    def refresh(self):
        self.refresh_macro_list()
        self.apply_all()
        if self.parent.keypad_window is not None:
            curr_x = self.parent.keypad_window.winfo_x()
            curr_y = self.parent.keypad_window.winfo_y()
            self.parent.toggle_keypad()
            self.parent.toggle_keypad()
            self.parent.keypad_window.geometry(f"+{curr_x}+{curr_y}")

    def add_macro_logic(self):
        """Adds macro and updates only the list."""
        lab = self.new_lab.get().strip()
        con = self.new_con.get().strip()
        if lab and con:
            self.parent.user_macros.append({"label": lab, "content": con})
            self.new_lab.delete(0, END)
            self.new_con.delete(0, END)
            self.refresh()
            self.parent.show_toast(f"Macro '{lab}' Added!")

    def delete_macro(self, index):
        """Removes a macro and refreshes only the list part of the UI."""
        label = self.parent.user_macros[index]['label']

        confirm = Messagebox.yesno(f"Delete the '{label}' button?", "Confirm Delete",
                                   parent=self.win)
        if confirm == "Yes":
            self.parent.user_macros.pop(index)
            self.refresh()
            self.parent.show_toast(f"Macro '{label}' Deleted", bootstyle=WARNING)

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")

    def apply_all(self):
        # Apply Theme
        new_theme = self.theme_cb.get()
        self.parent.root.style.theme_use(new_theme)

        # Apply Logic Settings
        self.parent.auto_save_delay = int(self.save_delay.get()) * 1000
        self.parent.enable_backups = self.backup_var.get()
        self.parent.enable_suggestions = self.suggest_var.get()

        # Save to a hidden config file so it persists!
        config = {
            "theme": new_theme,
            "delay": self.parent.auto_save_delay,
            "backups": self.parent.enable_backups,
            "suggestions": self.parent.enable_suggestions,
            "macros": self.parent.user_macros
        }
        with open("data/config.json", "w") as f:
            json.dump(config, f)

        show_toast("Settings Saved!")

        if self.parent.enable_suggestions:
            self.parent.update_preview()


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    sheet = Sheet(root)
    root.mainloop()
