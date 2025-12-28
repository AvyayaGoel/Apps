import json
import os

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.tableview import Tableview
from ttkbootstrap.widgets.tooltip import ToolTip


class Sheet:
    def __init__(self, f_sheet):
        self.root = f_sheet
        self.root.title("Formula Sheet Pro")
        self.root.geometry("1000x900")
        self.root.minsize(900, 870)
        self.db_file = "formula_data.json"

        self.master_data = {}
        self.temp_variables = []
        self.editing_mode = False
        self.edit_id = None  # Tracks the ID being edited

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

        self.details_frame = tb.Frame(self.mainframe)

        # Main Fields
        fields = [("Formula:", self.formula_e), ("Field:", self.field_e), ("Topic:", self.topic_e)]
        for i, (label, var) in enumerate(fields):
            tb.Label(self.data_entry_frame,
                     text=label
                     ).grid(row=i, column=0, sticky=W, pady=5)
            if label == "Field:":
                tb.Combobox(self.data_entry_frame,
                            values=["Physics", "Chemistry", "Maths"],
                            textvariable=var).grid(
                    row=i, column=1, sticky=EW, padx=10)
            else:
                tb.Entry(self.data_entry_frame,
                         textvariable=var
                         ).grid(row=i, column=1, sticky=EW, padx=10)

        # 3. VARIABLE MANAGEMENT
        var_mgmt_frame = tb.Labelframe(self.data_entry_frame,
                                       text=" Variables Staging (Edit variables here) ",
                                       padding=10)
        var_mgmt_frame.grid(row=3, column=0,
                            columnspan=2, sticky=EW,
                            pady=10)

        # Entry Row
        input_row = tb.Frame(var_mgmt_frame)
        input_row.pack(fill=X, pady=5)
        self.v_sym = tb.Entry(input_row, width=10)
        self.v_sym.pack(side=LEFT, padx=2)
        self.v_name = tb.Entry(input_row)
        self.v_name.pack(side=LEFT, fill=X, expand=YES, padx=2)
        self.v_unit = tb.Entry(input_row, width=15)
        self.v_unit.pack(side=LEFT, padx=2)
        tb.Button(input_row, text="+",
                  bootstyle=SUCCESS,
                  command=self.add_variable
                  ).pack(side=LEFT, padx=2)

        # Staging Table
        self.staging_table = Tableview(
            master=var_mgmt_frame,
            coldata=[
                {"text": "Symbol", "stretch": False, "width": 80},
                {"text": "Name", "stretch": True},  # This will now fill the middle
                {"text": "Unit", "stretch": True}
            ],
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

        self.help_var = tb.Button(btn_row, text="?", width=3, bootstyle="info-outline")
        self.help_var.pack(side=RIGHT, padx=5)
        ToolTip(self.help_var,
                text="1. Add variables using the '+' button.\n2. To fix a typo, select the row and click 'Edit Selected'.\n3. The 'Save' button will grab any text left in the boxes.")

        # Main Save
        self.save_btn = tb.Button(self.data_entry_frame, text="Save Formula", width=20, bootstyle=INFO,
                                  command=self.save_to_table)
        self.save_btn.grid(row=4, column=1, sticky=E, pady=10)

        self.details_frame = tb.Frame(self.mainframe)
        self.formula_table.view.bind("<Double-1>", self.on_double_click)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_from_file()

    # ==========================================================
    # VARIABLE REPAIR LOGIC
    # ==========================================================

    def refresh_staging_table(self):
        rows = [(v['symbol'], v['name'], v['unit']) for v in self.temp_variables]
        staging_cols = [
            {"text": "Symbol", "stretch": False, "width": 80},
            {"text": "Name", "stretch": True},
            {"text": "Unit", "stretch": False}
        ]
        # noinspection PyTypeChecker
        self.staging_table.build_table_data(coldata=staging_cols, rowdata=rows)

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
        """Pulls a variable out of the list and back into the entry boxes to fix it."""
        selected = self.staging_table.view.selection()
        if selected:
            item = self.staging_table.view.item(selected[0])
            val = item['values']

            # 1. Fill the entry boxes with the selected data
            self.v_sym.delete(0, END)
            self.v_sym.insert(0, val[0])
            self.v_name.delete(0, END)
            self.v_name.insert(0, val[1])
            self.v_unit.delete(0, END)
            self.v_unit.insert(0, val[2])

            # 2. Remove it from the temp list (user will '+' it back after fixing)
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

    # ==========================================================
    # SAVE & DATA LOGIC
    # ==========================================================

    def refresh_main_table(self):
        rows = [v["main_info"] for v in self.master_data.values()]
        rows.sort(key=lambda x: int(x[0]))
        # noinspection PyTypeChecker
        self.formula_table.build_table_data(coldata=self.cols, rowdata=rows)

    def renumber_database(self):
        """Re-assigns IDs 1 to N based on the current UI order."""
        new_master = {}
        # Get the current rows in the order they appear on screen
        current_rows = self.formula_table.tablerows

        for index, row in enumerate(current_rows, start=1):
            old_id = int(row.values[0])
            if old_id in self.master_data:
                data = self.master_data[old_id]
                # Update the ID inside the data
                data["main_info"][0] = index
                # Put it into the new dictionary with the new index as key
                new_master[index] = data

        self.master_data = new_master
        self.refresh_main_table()

    def save_to_table(self):
        # --- SYNC BLOCK: Removes "Ghost" data that was deleted via Right-Click ---
        # 1. Get a list of all IDs currently visible in the UI table
        visible_ids = [int(row.values[0]) for row in self.formula_table.tablerows]

        # 2. Delete any ID from master_data that is NOT in the visible table
        # We use list(self.master_data.keys()) to avoid errors while iterating
        for stored_id in list(self.master_data.keys()):
            if stored_id not in visible_ids:
                # Important: Only purge if we aren't currently editing THIS specific ID
                if not (self.editing_mode and stored_id == self.edit_id):
                    del self.master_data[stored_id]
        # -------------------------------------------------------------------------

        f_text = self.formula_e.get().strip()
        f_field = self.field_e.get().strip()
        f_topic = self.topic_e.get().strip()

        if not f_text: return
        if self.v_sym.get().strip(): self.add_variable()

        if self.editing_mode:
            target_id = self.edit_id
            self.master_data[target_id] = {
                "main_info": [target_id, f_text, f_field, f_topic],
                "variables": self.temp_variables.copy()
            }
            self.editing_mode = False
            self.save_btn.configure(text="Save Formula", bootstyle=INFO)
        else:
            # Create new entry by finding max ID + 1
            new_id = max(self.master_data.keys(), default=0) + 1
            self.master_data[new_id] = {
                "main_info": [new_id, f_text, f_field, f_topic],
                "variables": self.temp_variables.copy()
            }

        self.refresh_main_table()
        self.clear_entries()
        self.renumber_database()

    def clear_entries(self):
        self.formula_e.set("")
        self.topic_e.set("")
        self.field_e.set("")
        self.temp_variables = []
        self.refresh_staging_table()

    def on_double_click(self, event):
        item = self.formula_table.view.selection()
        if item:
            # Get the ID from the first column (No.)
            row_id = int(self.formula_table.view.item(item[0], "values")[0])
            if row_id in self.master_data:
                self.show_formula_details(self.master_data[row_id])

    def start_edit(self, data):
        self.editing_mode = True
        self.edit_id = data["main_info"][0]  # Track ID
        self.hide_details()
        self.formula_e.set(data["main_info"][1])
        self.field_e.set(data["main_info"][2])
        self.topic_e.set(data["main_info"][3])
        self.temp_variables = data["variables"].copy()
        self.refresh_staging_table()
        self.save_btn.configure(text="Update Formula", bootstyle=WARNING)

    def on_closing(self):
        # 1. Look at what is actually still in the table (UI)
        final_save_list = []

        for row in self.formula_table.tablerows:
            row_id = int(row.values[0])
            if row_id in self.master_data:
                # Update the ID in case you used "Move" to swap order
                self.master_data[row_id]["main_info"][0] = row_id
                final_save_list.append(self.master_data[row_id])

        # 2. Sort the list by ID so the JSON stays clean
        final_save_list.sort(key=lambda x: int(x["main_info"][0]))

        # 3. Write to file
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(final_save_list, f, indent=4, ensure_ascii=False)

        self.renumber_database()
        self.root.destroy()

    def load_from_file(self):
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    item_id = int(item["main_info"][0])
                    self.master_data[item_id] = item
                self.refresh_main_table()

    # --- SHOW/HIDE DETAILS (Keep your existing ones) ---
    def show_formula_details(self, data):
        self.data_entry_frame.pack_forget()
        for w in self.details_frame.winfo_children(): w.destroy()
        tb.Label(self.details_frame,
                 text=data["main_info"][1],
                 font=("Consolas", 24, "bold"),
                 bootstyle=SUCCESS
                 ).pack(pady=20)
        tb.Label(self.details_frame,
                 text=f"Field: {data['main_info'][2]} | Topic: {data['main_info'][3]}",
                 font=("Arial", 12)
                 ).pack(pady=5)
        if data['variables']:
            vt = Tableview(master=self.details_frame,
                           coldata=[
                               {"text": "Symbol", "stretch": False, "width": 80},
                               {"text": "Name", "stretch": True},
                               {"text": "Unit", "stretch": True}],
                           rowdata=[(v['symbol'], v['name'], v['unit']) for v in data['variables']],
                           bootstyle=SECONDARY, height=6)
            vt.pack(fill=X, padx=50, pady=20)
        btn_f = tb.Frame(self.details_frame)
        btn_f.pack(pady=10)
        tb.Button(btn_f, text="Edit Formula",
                  bootstyle=WARNING,
                  command=lambda: self.start_edit(data)
                  ).pack(side=LEFT, padx=10)
        tb.Button(btn_f, text="← Back", bootstyle="outline-info", command=self.hide_details).pack(side=LEFT, padx=10)
        self.details_frame.pack(fill=BOTH, expand=YES)

    def hide_details(self):
        self.details_frame.pack_forget()
        self.data_entry_frame.pack(fill=BOTH, expand=YES)


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    sheet = Sheet(root)
    root.mainloop()