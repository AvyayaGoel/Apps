import json
import os

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.tableview import Tableview
from ttkbootstrap.widgets.tooltip import ToolTip


class Sheet:
    def __init__(self, f_sheet):

        self.root = f_sheet
        self.root.title("Calculus Console")
        self.root.geometry("1000x900")
        self.root.minsize(900, 870)
        self.db_file = "formula_data.json"

        self.master_data = {}
        self.temp_variables = []
        self.editing_mode = False
        self.edit_id = None

        self.auto_save_timer = None

        self.last_focused_widget = None
        self.keypad_window = None
        self.drag_x = 0
        self.drag_y = 0


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
        ToolTip(self.help_table, text="Double-click a row to View Details or Edit the formula.")

        self.formula_table = Tableview(master=self.table_frame,
                                       coldata=self.cols,
                                       searchable=True,
                                       paginated=True,
                                       bootstyle=INFO)
        self.formula_table.pack(fill=BOTH, expand=YES)

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
                widget = self.subject_cb
                self.subject_cb.bind("<<ComboboxSelected>>", self.on_subject_change)
                self.subject_cb.bind("<KeyRelease>", self.on_subject_change)
            elif label == "Topic:":
                self.topic_cb = tb.Combobox(self.data_entry_frame,
                                            values=[],
                                            textvariable=var)
                widget = self.topic_cb
            else:
                widget = tb.Entry(self.data_entry_frame, textvariable=var)

            # BIND FOCUS EVENT
            widget.bind("<FocusIn>", self.handle_focus)
            widget.grid(row=i, column=1, sticky=EW, padx=10)

        # 3. VARIABLE MANAGEMENT
        var_mgmt_frame = tb.Labelframe(self.data_entry_frame,
                                       text=" Variables Staging (Edit variables here) ",
                                       padding=10)
        var_mgmt_frame.grid(row=3, column=0,
                            columnspan=2, sticky=EW,
                            pady=10)

        input_row = tb.Frame(var_mgmt_frame)
        input_row.pack(fill=X, pady=5)

        # Create and Bind Variable Inputs
        self.v_sym = tb.Entry(input_row, width=10)
        self.v_sym.pack(side=LEFT, padx=2)
        self.v_sym.bind("<FocusIn>", self.handle_focus)  # Bind

        self.v_name = tb.Entry(input_row)
        self.v_name.pack(side=LEFT, fill=X, expand=YES, padx=2)
        self.v_name.bind("<FocusIn>", self.handle_focus)  # Bind

        self.v_unit = tb.Entry(input_row, width=15)
        self.v_unit.pack(side=LEFT, padx=2)
        self.v_unit.bind("<FocusIn>", self.handle_focus)  # Bind

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
        self.keypad_btn.pack(side=LEFT, padx=20)
        # -------------------------

        self.help_var = tb.Button(btn_row, text="?", width=3, bootstyle="info-outline")
        self.help_var.pack(side=RIGHT, padx=5)
        ToolTip(self.help_var,
                text="1. Add variables using '+'.\n2. Fix typos via 'Edit Selected'.\n3. Use ⌨ for special symbols.")

        self.save_btn = tb.Button(self.data_entry_frame, text="Save Formula", width=20, bootstyle=INFO,
                                  command=self.save_to_table)
        self.save_btn.grid(row=4, column=1, sticky=E, pady=10)

        self.details_frame = tb.Frame(self.mainframe)
        self.formula_table.view.bind("<Double-1>", self.on_double_click)
        self.root.bind("<FocusOut>", self.trigger_auto_save)
        self.root.bind("<Key>", self.trigger_auto_save)
        self.root.bind("<Button-1>", self.trigger_auto_save)
        self.root.bind("<Button-3>", self.trigger_auto_save)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_from_file()
        self.create_backup()
        self.update_suggestions()

    # ==========================================================
    # FOCUS & KEYPAD LOGIC (UPDATED WITH DRAG)
    # ==========================================================

    def trigger_auto_save(self, *args):
        """Resets the timer every time the user types."""
        if self.auto_save_timer is not None:
            self.root.after_cancel(self.auto_save_timer)
        # Wait for 3000ms (3 seconds) of silence before saving
        self.auto_save_timer = self.root.after(5000, self.perform_silent_save)

    def perform_silent_save(self):
        """Writes data to file sorted by ID, ignoring the table's current view order."""
        # 1. Get all IDs from your master dictionary and sort them numerically
        sorted_ids = sorted(self.master_data.keys())
        final_save_list = [self.master_data[i] for i in sorted_ids]
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(final_save_list, f, indent=4, ensure_ascii=False)


    def handle_focus(self, event):
        """Remembers the last Entry widget the user clicked."""
        self.last_focused_widget = event.widget

    def insert_symbol(self, symbol):
        """Inserts symbol into the last focused widget."""
        if self.last_focused_widget:
            try:
                self.last_focused_widget.insert(INSERT, symbol)
                self.last_focused_widget.focus_set()  # Return focus so they can keep typing
            except Exception:
                pass  # Ignore if widget is destroyed or invalid

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

    # ==========================================================
    # EXISTING LOGIC (Unchanged)
    # ==========================================================

    def refresh_staging_table(self):
        rows = [(v['symbol'], v['name'], v['unit']) for v in self.temp_variables]
        self.staging_table.build_table_data(
            coldata=[{"text": "Symbol", "stretch": False, "width": 80},
                     {"text": "Name", "stretch": True},
                     {"text": "Unit", "stretch": True}],
            rowdata=rows
        )

    def add_variable(self):
        sym, name, unit = self.v_sym.get().strip(), self.v_name.get().strip(), self.v_unit.get().strip()
        if sym and name:
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

    def refresh_main_table(self):
        rows = [v["main_info"] for v in self.master_data.values()]
        rows.sort(key=lambda x: int(x[0]))
        self.formula_table.build_table_data(coldata=self.cols, rowdata=rows)

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
                Messagebox.show_warning(f"The formula '{f_text}' already exists in your sheet!", "Duplicate Formula")
                return

        if self.v_sym.get().strip(): self.add_variable()

        if self.editing_mode:
            target_id = self.edit_id
            self.master_data[target_id] = {"main_info": [target_id, f_text, f_field, f_topic],
                                           "variables": self.temp_variables.copy()}
            self.editing_mode = False
            self.save_btn.configure(text="Save Formula", bootstyle=INFO)
        else:
            new_id = max(self.master_data.keys(), default=0) + 1
            self.master_data[new_id] = {"main_info": [new_id, f_text, f_field, f_topic],
                                        "variables": self.temp_variables.copy()}

        self.refresh_main_table()
        self.clear_entries()
        self.renumber_database()
        self.update_suggestions()

    def create_backup(self):
        """Creates a safety copy of the data file."""
        import shutil
        if os.path.exists(self.db_file):
            shutil.copy2(self.db_file, self.db_file + ".bak")

    def update_suggestions(self):
        """Scans your data and updates the Topic dropdown automatically."""
        if hasattr(self, 'subject_cb'):
            # Ensure subjects are always there
            all_subjects = set(d['main_info'][2] for d in self.master_data.values() if d['main_info'][2])
            self.subject_cb['values'] = sorted(list(all_subjects | {"Physics", "Chemistry", "Maths"}))

    def on_subject_change(self, event=None):
        """Filters the Topic list based on the selected Subject."""
        selected_subject = self.field_e.get().strip()

        if not selected_subject:
            self.topic_cb['values'] = []
            self.topic_e.set("")  # Clear topic if subject is deleted
            return

        # Find all formulas that match this specific subject
        topics_for_subject = set()
        for d in self.master_data.values():
            # index 2 is Field/Subject, index 3 is Topic
            if d['main_info'][2] == selected_subject:
                topics_for_subject.add(d['main_info'][3])

        # Sort and update the Topic Combobox
        self.topic_cb['values'] = sorted(list(topics_for_subject))

    def clear_entries(self):
        self.formula_e.set("")
        self.topic_e.set("")
        self.field_e.set("")
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


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    sheet = Sheet(root)
    root.mainloop()
