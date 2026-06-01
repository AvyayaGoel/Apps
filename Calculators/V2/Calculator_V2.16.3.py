import math
import os
import re
import sys
import tkinter.font as tkfont

import numexpr
import sympy as sp
import ttkbootstrap as tb
from ttkbootstrap.constants import LEFT, DARK, SECONDARY, SUCCESS
from ttkbootstrap.dialogs import Messagebox as Mb
from ttkbootstrap_icons_bs import BootstrapIcon

# Increase the limit for integer-to-string conversion safety
sys.set_int_max_str_digits(2147483646)


def do_convert(v_in, v_out, d1, d2, factors):
    try:
        val_str = v_in.get().strip()
        if not val_str:  # The "Logic Gate"
            v_out.set("")
            return

        val = float(val_str)
        res = val * factors[d1.get()] / factors[d2.get()]
        v_out.set(f"{res:.4f}")
    except Exception as e:
        Mb.show_error("Error", str(e))
        v_out.set("")


def handle_num_input(var, value):
    """Adds a character to the specified StringVar."""
    var.set(var.get() + str(value))


def clear_input(input_var, output_var=None):
    """Clears the input (and optional output) StringVars."""
    input_var.set("")
    if output_var:
        output_var.set("")


def backspace_input(var):
    """Removes the last character from the specified StringVar."""
    var.set(var.get()[:-1])


# -------------------------------------------------
# SYMPY-BASED NORMALIZATION & SIMPLIFICATION
# -------------------------------------------------

def normalize_expr(expr: str) -> str:
    """Converts UI symbols to SymPy-readable Python math."""
    # Handle Factorials: Convert '5!' to 'factorial(5)'
    # This regex looks for numbers or groups in parentheses followed by !
    expr = re.sub(r'(\d+|\([^()]+\))!', r'factorial(\1)', expr)

    return (
        expr.replace("×", "*")
        .replace("x", "*")
        .replace("²", "**2")
        .replace("÷", "/")
        .replace("^", "**")
        .replace("π", "pi")
        .replace("e", "E")  # SymPy uses E for Euler's constant
        .replace(" ", "")
    )


def rewrite_percent_logic(expr: str) -> str:
    """
    Handles Consumer Percentages (Windows Style).
    Works with factorials, parentheses, chaining, and multipliers.
    Identity:
      A ± B%        → A ± (A * B / 100)
      A ± B% * C    → A ± (A * (B * C) / 100)
    """

    # ---------- 1. Standalone percent in BODMAS contexts ----------
    # e.g. 50% * 2 → (50/100) * 2
    expr = re.sub(r'(\d+(?:\.\d+)?)%(?=[*/])', r'(\1/100)', expr)

    # ---------- 2. Consumer percent resolution (LEFT → RIGHT) ----------
    while "%" in expr:
        pct_pos = expr.find("%")

        # ---- find owning + or - (depth-aware) ----
        depth = 0
        op_pos = None
        for i in range(pct_pos - 1, -1, -1):
            if expr[i] == ")":
                depth += 1
            elif expr[i] == "(":
                depth -= 1
            elif depth == 0 and expr[i] in "+-":
                op_pos = i
                break

        # ---- standalone percent fallback ----
        if op_pos is None:
            expr = expr[:pct_pos] + "/100" + expr[pct_pos + 1:]
            continue

        base = expr[:op_pos]
        op = expr[op_pos]

        # ---- extract percent-number ----
        i = pct_pos - 1
        while i >= 0 and (expr[i].isdigit() or expr[i] == "."):
            i -= 1

        # ---- absorb multiplier/divider after % ----
        j = pct_pos + 1
        while j < len(expr) and expr[j] in "*/0123456789().":
            j += 1

        pct_expr = expr[i + 1:j].replace("%", "")
        remainder = expr[j:]

        # ---- rewrite safely (factorial-safe) ----
        replacement = f"({base}{op}({base}*({pct_expr})/100))"
        expr = replacement + remainder

    return expr


def fully_simplify(expr: str) -> str:
    """Uses SymPy to simplify factorials and algebraic expressions."""
    expr = normalize_expr(expr)
    expr = rewrite_percent_logic(expr)

    try:
        # SymPy parses the string and simplifies it (e.g., factorial(100)/factorial(99) -> 100)
        sym_expr = sp.sympify(expr)
        simplified = sp.simplify(sym_expr)
        return str(simplified)
    except:
        return expr


class Calculator:
    HISTORY_BREAKPOINT = 800
    HISTORY_WIDTH = 300

    def __init__(self, window):
        self.root = window
        self.root.title("Calculator_V2.16")

        # NOTE: Update the icon path if necessary
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "Calculator-Icon.ico")
        self.root.iconbitmap(icon_path)

        # --- 1. Window Configuration ---
        self.root.geometry("500x600")
        self.root.minsize(500, 600)
        self.base_width = 500
        self.base_height = 600

        self.sidebar_open = False
        self.max_sidebar_width = 350
        self.animation_speed = 10
        self.animation_step = 25
        self.header_height = 0
        self.sidebar_buttons = {}
        self.icon_context = BootstrapIcon
        self._resize_job = None
        self._last_font_scale = None
        self.history_expanded = False
        self.prev_width = None
        self.history_forced = False
        self.history_manual = False
        self.history_auto = False
        self.show_history = False
        self.pre_history_width = 500
        self.was_expanded_by_logic = False

        # --- 2. Style Setup ---
        self.style = tb.Style()

        self.font_button = tkfont.Font(family="Arial", size=25)
        self.font_entry = tkfont.Font(family="Arial", size=24)
        self.font_converter = tkfont.Font(family="Arial", size=12)

        self.style.configure("TButton", padding=2, font=self.font_button)
        self.style.configure("Converter.TButton", font=self.font_converter)
        self.style.configure("TEntry", padding=5)

        # Flat Entry Layout
        self.style.layout("Flat.TEntry", [
            ("Entry.field", {"sticky": "nsew", "children": [
                ("Entry.padding", {"sticky": "nsew", "children": [
                    ("Entry.textarea", {"sticky": "nsew"})
                ]})
            ]})
        ])

        # Flat Combobox Layout
        self.style.layout("Flat.TCombobox", [
            ("Combobox.field", {"sticky": "nsew", "children": [
                ("Combobox.padding", {"sticky": "nsew", "children": [
                    ("Combobox.textarea", {"sticky": "nsew"})
                ]})
            ]})
        ])

        bg = self.style.colors.bg
        hover = self.style.colors.secondary
        fg = self.style.colors.fg

        self.style.configure("Flat.TEntry", padding=8, background=bg, fieldbackground=bg, foreground=fg, insertcolor=fg)
        self.style.map("Flat.TEntry", background=[("focus", hover), ("active", hover)],
                       fieldbackground=[("focus", hover), ("active", hover)])

        self.style.configure("Flat.TCombobox", relief="flat", borderwidth=0, padding=6, fieldbackground=bg,
                             background=bg, foreground=fg)
        self.style.map("Flat.TCombobox", background=[("active", hover), ("focus", hover)],
                       fieldbackground=[("readonly", bg), ("active", hover), ("focus", hover)])

        # Sidebar Button Styles
        self.style.configure("Header.TButton", font=("Segoe UI", 16, "bold"), padding=(5, 5), bootstyle="dark-link",
                             borderwidth=0)
        self.style.configure("Sidebar.TButton", font=("Segoe UI", 14), anchor="w", padding=(5, 8), bootstyle="dark",
                             borderwidth=0)
        self.style.map("Sidebar.TButton", background=[('active', hover)],
                       foreground=[('active', self.style.colors.light)])

        self.style.configure("History.TButton", font=("Segoe UI", 12))
        self.style.configure("Win11.TEntry", fieldbackground=bg, foreground=fg)

        # --- 3. Main Layout Structure ---
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)

        # Header
        self.header_frame = tb.Frame(self.root, bootstyle="dark")
        self.header_frame.grid(row=0, column=0, sticky="new")

        self.menu_button = tb.Button(self.header_frame, text="☰", command=self.toggle_sidebar, style="Header.TButton")
        self.menu_button.pack(side="left", padx=10, pady=5)

        self.header_label = tb.Label(self.header_frame, text="Standard", font=("Segoe UI", 12, "bold"),
                                     bootstyle="inverse-dark")
        self.header_label.pack(side="left", padx=5)

        self.root.update_idletasks()
        self.header_height = self.header_frame.winfo_height()

        # Content Container
        self.content_container = tb.Frame(self.root)
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.columnconfigure(0, weight=1)
        self.content_container.rowconfigure(0, weight=1)

        self.calculator_frame = tb.Frame(self.content_container, padding=5)
        self.length_frame = tb.Frame(self.content_container, padding=5)
        self.area_frame = tb.Frame(self.content_container, padding=5)
        self.temp_frame = tb.Frame(self.content_container, padding=5)

        for f in (self.calculator_frame, self.length_frame, self.area_frame, self.temp_frame):
            f.grid(row=0, column=0, sticky="nsew")

        # StringVars
        self.calculator_text = tb.StringVar(value="")
        self.length_input_text = tb.StringVar(value="")
        self.length_output_text = tb.StringVar(value="")
        self.area_input_text = tb.StringVar(value="")
        self.area_output_text = tb.StringVar(value="")
        self.temp_input_text = tb.StringVar(value="")
        self.temp_output_text = tb.StringVar(value="")
        self.history_text = tb.StringVar()
        self.history_list = []

        # Initialize tabs
        self.setup_calculator_tab()
        self.setup_length_converter_tab()
        self.setup_area_converter_tab()
        self.setup_temp_converter_tab()

        self.show_frame(self.calculator_frame, "Standard", initial=True)

        # Sidebar Overlay
        self.flyout_sidebar_frame = tb.Frame(self.root, bootstyle="dark", width=self.max_sidebar_width)
        self.flyout_sidebar_frame.place(x=-self.max_sidebar_width, y=self.header_height)

        self.setup_sidebar_contents()

        self.separator = tb.Frame(self.root, bootstyle="secondary", height=1)
        self.separator.place(x=-self.max_sidebar_width - 1, y=self.header_height)

        self.root.bind("<Configure>", self.on_resize)
        self.root.bind('<Return>', self.eq)
        self.root.bind("<Button-1>", self.check_outside_click)

    # --- UI Logic Methods ---

    def setup_sidebar_contents(self):
        for widget in self.flyout_sidebar_frame.winfo_children():
            widget.destroy()

        tb.Label(self.flyout_sidebar_frame, text="Calculators", font=("Segoe UI", 15, "bold"),
                 bootstyle="inverse-dark").pack(fill='x', pady=(15, 5), padx=6)

        def add_menu_item(key, icon_name, text, command):
            icon_image = self.icon_context(icon_name, size=22, color="white")
            btn = tb.Button(self.flyout_sidebar_frame, text=text, image=icon_image, compound=LEFT, command=command,
                            style="Sidebar.TButton")
            btn.image = icon_image
            btn.pack(fill='x', pady=5, padx=6)
            self.sidebar_buttons[key] = btn

        add_menu_item("calc", "calculator", "Calculator", lambda: self.show_frame(self.calculator_frame, "Standard"))
        tb.Label(self.flyout_sidebar_frame, text="CONVERTERS", font=("Segoe UI", 15, "bold"),
                 bootstyle="inverse-dark").pack(fill='x', pady=(15, 5), padx=6)
        add_menu_item("len", "rulers", "Length", lambda: self.show_frame(self.length_frame, "Length"))
        add_menu_item("area", "grid-3x3", "Area", lambda: self.show_frame(self.area_frame, "Area"))
        add_menu_item("temp", "thermometer", "Temperature", lambda: self.show_frame(self.temp_frame, "Temperature"))

    def toggle_sidebar(self):
        target_width = self.max_sidebar_width
        if self.sidebar_open:
            self.animate_sidebar(0, -target_width)
            self.sidebar_open = False
            self.menu_button.config(text="☰")
        else:
            self.animate_sidebar(-target_width, 0)
            self.sidebar_open = True
            self.menu_button.config(text="✕")

    def animate_sidebar(self, start_x, end_x):
        step = self.animation_step if end_x > start_x else -self.animation_step

        def step_anim(current_x):
            current_h = self.root.winfo_height() - self.header_height
            if (step > 0 and current_x >= end_x) or (step < 0 and current_x <= end_x):
                self.flyout_sidebar_frame.place(x=end_x, height=current_h, width=self.max_sidebar_width)
                self.separator.place(x=end_x + self.max_sidebar_width, y=self.header_height, width=1, height=current_h)
                if end_x < 0: self.separator.place(x=-self.max_sidebar_width - 1)
                return
            new_x = current_x + step
            self.flyout_sidebar_frame.place(x=new_x, y=self.header_height, height=current_h,
                                            width=self.max_sidebar_width)
            self.separator.place(x=new_x + self.max_sidebar_width, y=self.header_height, width=1, height=current_h)
            self.root.after(self.animation_speed, lambda: step_anim(new_x))

        step_anim(start_x)

    # --- Calculator Setup & Math ---

    def setup_calculator_tab(self):
        # 1. Main Grid Configuration for the Calculator Tab
        # Column 0 is for the Calculator, Column 1 is for History
        self.calculator_frame.columnconfigure(0, weight=1)
        self.calculator_frame.columnconfigure(1, weight=0)
        self.calculator_frame.rowconfigure(0, weight=1)

        # 2. LEFT SIDE: CALCULATOR CONTAINER
        # We put all calculator elements inside this frame to keep their grid independent
        self.calc_container = tb.Frame(self.calculator_frame)
        self.calc_container.grid(row=0, column=0, sticky="nsew")

        # Configure the Internal Grid (6 columns for buttons)
        for i in range(6): self.calc_container.columnconfigure(i, weight=1)
        self.calc_container.rowconfigure(0, weight=0)  # Top Bar
        self.calc_container.rowconfigure(1, weight=1)  # Display Area
        for i in range(2, 7): self.calc_container.rowconfigure(i, weight=1)  # Button Rows

        # --- A. TOP UTILITY BAR ---
        util_frame = tb.Frame(self.calc_container)
        util_frame.grid(row=0, column=0, columnspan=6, sticky="ew", padx=10, pady=(5, 0))

        # We save this as self.hist_btn for the 'click outside' check
        self.hist_btn = tb.Button(
            util_frame,
            text="🕒",
            style="History.TButton",
            bootstyle="link-light",
            command=self.toggle_history
        )
        self.hist_btn.pack(side="right")

        # --- B. DISPLAY AREA ---
        display_container = tb.Frame(self.calc_container)
        display_container.grid(row=1, column=0, columnspan=6, sticky="nsew", padx=5, pady=5)

        tb.Label(
            display_container,
            textvariable=self.history_text,
            font=("Segoe UI", 11),
            foreground="#a0a0a0",
            anchor="e"
        ).pack(fill="x", padx=10, pady=(10, 0))

        self.e1 = tb.Entry(
            display_container,
            textvariable=self.calculator_text,
            font=("Segoe UI", 40, "bold"),
            style="Win11.TEntry",
            justify="right"
        )
        self.e1.pack(fill="x", padx=5, pady=(0, 10))

        # --- C. BUTTONS ---
        buttons = [
            ('%', 0, 2), ('C', 1, 2), ('←', 2, 2), ('^', 3, 2), ('(', 4, 2), (')', 5, 2),
            ('√', 0, 3), ('7', 1, 3), ('8', 2, 3), ('9', 3, 3), ('/', 4, 3), ('x²', 5, 3),
            ('π', 0, 4), ('4', 1, 4), ('5', 2, 4), ('6', 3, 4), ('*', 4, 4), ('e', 5, 4),
            ('ln', 0, 5), ('1', 1, 5), ('2', 2, 5), ('3', 3, 5), ('-', 4, 5), ('!', 5, 5),
            ('Sc', 0, 6), ('00', 1, 6), ('0', 2, 6), ('.', 3, 6), ('+', 4, 6), ('=', 5, 6)
        ]

        for (text, col, row) in buttons:
            if text == '=':
                btn_style, cmd = SUCCESS, self.eq
            elif text in ['C', '←'] or text.isdigit() or text in ['.', '00', '+', '-', '*', '/']:
                btn_style = SECONDARY
                if text == 'C':
                    cmd = self.clear_calculator
                elif text == '←':
                    cmd = self.backspace_calculator
                else:
                    cmd = lambda t=text: self.handle_calculator_button(t)
            else:
                btn_style = DARK
                cmd = self.get_special_command(text)

            tb.Button(self.calc_container, text=text, command=cmd, bootstyle=btn_style).grid(
                column=col, row=row, sticky="nsew", padx=1, pady=1
            )

        # --- 3. RIGHT SIDE: HISTORY PANEL ---
        # Note: This is gridded inside self.calculator_frame but stays hidden
        self.history_panel = tb.Frame(self.calculator_frame, width=300, bootstyle="secondary")

        tb.Label(self.history_panel, text="History", font=("Segoe UI", 14, "bold"),
                 padding=15, bootstyle="inverse-secondary").pack(fill="x")

        self.hist_display = tb.Text(
            self.history_panel, width=30, font=("Segoe UI", 11),
            state="disabled", relief="flat", bg="#2b2b2b", fg="white", padx=10, pady=10
        )
        self.hist_display.pack(fill="both", expand=True)

    def check_outside_click(self, event):
        """Closes history if the user clicks anywhere outside the history panel."""
        w = self.root.winfo_width()
        if not self.show_history:
            return
        if w >= self.HISTORY_BREAKPOINT:
            return
        # Get the widget that was clicked
        clicked_widget = event.widget
        # Check if we clicked inside the history panel
        # We check if the clicked widget's name starts with the history panel's name
        if str(clicked_widget).startswith(str(self.history_panel)):
            return
            # Check if we clicked the toggle button (otherwise it closes and immediately re-opens)
        if hasattr(self, 'hist_btn') and str(clicked_widget) == str(self.hist_btn):
            return
        # If we reached here, we clicked outside -> Close History
        self.toggle_history()

    def toggle_history(self):
        w = self.root.winfo_width()
        h = self.root.winfo_height()

        if not self.show_history:
            self.history_manual = True
            self.show_history = True

            if w < self.HISTORY_BREAKPOINT:
                self.prev_width = w
                self.root.geometry(f"{w + self.HISTORY_WIDTH}x{h}")

            self.history_panel.grid(row=0, column=1, rowspan=2, sticky="nsew")

        else:
            self.history_manual = False
            self.show_history = False

            if self.prev_width:
                self.root.geometry(f"{self.prev_width}x{h}")
                self.prev_width = None

            self.history_panel.grid_forget()

    def show_history_panel(self):
        if self.show_history:
            return

        self.history_panel.grid(row=0, column=1, rowspan=2, sticky="nsew")
        self.calculator_frame.columnconfigure(1, weight=0)
        self.show_history = True

    def hide_history_panel(self):
        if not self.show_history:
            return

        self.history_panel.grid_forget()
        self.show_history = False

    def update_history_log(self, expr, res):
        self.hist_display.config(state="normal")

        # We create a unique tag for each entry so they don't overlap
        # but we also give them a general "clickable" tag for the mouse cursor
        entry_id = f"entry_{len(self.history_list)}"
        self.history_list.append((expr, res))

        self.hist_display.insert("1.0", "\n" + "-" * 30 + "\n")

        # Insert Result (Bold)
        self.hist_display.insert("1.0", f"{res}\n", (entry_id, "result_tag", "clickable"))

        # Insert Expression (Gray)
        self.hist_display.insert("1.0", f"{expr} =\n", (entry_id, "expr_tag", "clickable"))

        # Formatting Tags
        self.hist_display.tag_config("result_tag", font=("Segoe UI", 16, "bold"), foreground="white")
        self.hist_display.tag_config("expr_tag", foreground="#a0a0a0")

        # --- NEW: Bind the click to this specific entry ---
        # When clicked, it calls self.recall_history and passes the text
        self.hist_display.tag_bind(entry_id, "<Button-1>",
                                   lambda e, text=expr, value=res: self.recall_history(text, value))

        # --- NEW: Make cursor change to a 'hand' when hovering ---
        self.hist_display.tag_bind("clickable", "<Enter>", lambda e: self.hist_display.config(cursor="hand2"))
        self.hist_display.tag_bind("clickable", "<Leave>", lambda e: self.hist_display.config(cursor=""))

        self.hist_display.config(state="disabled")

    def log_special_operation(self, op_name, input_val, result):
        """Formats and logs special math operations to the history panel."""
        # Create a nice string like 'sqrt(25)' or '25²'
        if op_name == "sqrt":
            expr = f"√({input_val})"
        elif op_name == "sq":
            expr = f"({input_val})²"
        elif op_name == "ln":
            expr = f"ln({input_val})"
        elif op_name == "fact":
            expr = f"({input_val})!"
        elif op_name == "%":
            expr = f"({input_val})%"
        else:
            expr = f"{op_name}({input_val})"

        self.history_text.set(expr + " =")
        # Add it to the side history panel
        self.update_history_log(expr, result)
        # Set the main display to the result
        self.calculator_text.set(str(result))

    def recall_history(self, text, value):
        """Puts the historical expression back into the main calculator input."""
        self.history_text.set(text)
        self.calculator_text.set(value)
        self.e1.focus_set()

    def get_special_command(self, text):
        if text == '√': return self.square_root
        if text == 'x²': return self.square
        if text == 'ln': return self.ln
        if text == 'Sc': return self.scientific
        if text == 'π': return self.pi_val
        if text == 'e': return self.e_val
        return lambda t=text: self.handle_calculator_button(t)

    def handle_calculator_button(self, value):
        current = self.calculator_text.get()
        operators = "+-*/"

        # -----------------------------------------
        # Helper: find parentheses depth at end
        # -----------------------------------------
        def paren_depth(s):
            depth = 0
            for ch in s:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
            return depth

        depth = paren_depth(current)

        # -----------------------------------------
        # Operator handling
        # -----------------------------------------
        if value in operators:
            if not current:
                # Allow unary minus at start
                if value == "-":
                    self.calculator_text.set(value)
                return

            last = current[-1]

            # Allow unary minus after '('
            if value == "-" and last == "(":
                self.calculator_text.set(current + value)
                return

            # Replace operator ONLY at top level
            if depth == 0 and last in operators:
                self.calculator_text.set(current[:-1] + value)
                return

        # -----------------------------------------
        # Decimal handling (per-number)
        # -----------------------------------------
        if value == ".":
            last_op = max(current.rfind(op) for op in operators)
            last_paren = current.rfind("(")
            start = max(last_op, last_paren)
            if "." in current[start + 1:]:
                return

        self.calculator_text.set(current + str(value))

    def clear_calculator(self):
        self.calculator_text.set("")
        self.history_text.set("")

    def backspace_calculator(self):
        self.calculator_text.set(self.calculator_text.get()[:-1])

    def replacer(self):
        expr = self.calculator_text.get()
        if not expr:
            return ""

        expr = normalize_expr(expr)
        expr = fully_simplify(expr)
        return expr

    def eq(self, event=None):
        try:
            expression = self.calculator_text.get()
            if not expression:
                return

            clean_expr = self.replacer()

            # --- RULE 1: SCINUM is ALWAYS terminal ---
            if "SCINUM" in clean_expr:
                result = clean_expr.replace("SCINUM(", "").replace(")", "").replace(",", "e")

            # --- RULE 2: Huge scientific notation is terminal ---
            elif (
                    'e' in clean_expr
                    and not any(op in clean_expr for op in ['+', '-', '*', '/', '**'])
            ):
                result = clean_expr

            # --- RULE 3: Mixed arithmetic ONLY if exponent is small ---
            elif 'e' in clean_expr:
                exps = re.findall(r'e([+-]?\d+)', clean_expr)
                if any(len(exp) > 6 for exp in exps):
                    # Too large to safely evaluate
                    result = clean_expr
                else:
                    res = numexpr.evaluate(clean_expr)
                    result = res.item() if hasattr(res, "item") else res


            # --- RULE 4: Normal math ---
            else:
                res = numexpr.evaluate(clean_expr)
                result = res.item() if hasattr(res, "item") else res

            self.history_text.set(expression + " =")
            self.update_history_log(expression, result)
            self.calculator_text.set(str(result))

        except Exception as e:
            Mb.show_error("Error", str(e))
            self.clear_calculator()

    def square_root(self):
        try:
            raw_input = self.replacer()
            val = numexpr.evaluate(raw_input)
            val = val.item() if hasattr(val, "item") else val
            res = math.sqrt(val)
            self.log_special_operation("sqrt", raw_input, res)
        except Exception as e:
            Mb.show_error("Error", str(e))
            self.clear_calculator()

    def ln(self):
        try:
            raw_input = self.replacer()
            val = numexpr.evaluate(raw_input)
            val = val.item() if hasattr(val, "item") else val
            res = math.log(val)
            self.log_special_operation("ln", raw_input, res)
        except Exception as e:
            Mb.show_error("Error", str(e))
            self.clear_calculator()

    def square(self):
        self.calculator_text.set(self.calculator_text.get() + "²")

    def pi_val(self):
        self.calculator_text.set(self.calculator_text.get() + str(math.pi))

    def e_val(self):
        self.calculator_text.set(self.calculator_text.get() + str(math.e))

    def scientific(self):
        try:

            text = self.calculator_text.get()
            if 'e' in text and not any(op in text for op in ['+', '-', '*', '/']):
                parts = text.split('e')
                if len(parts) == 2:
                    mantissa = float(parts[0])
                    exponent = parts[1]
                    # Round the mantissa to exactly 2 decimal places
                    res_formatted = f"{mantissa:.2f}e{exponent}"

                    self.history_text.set(f"Sci({text}) =")
                    self.calculator_text.set(res_formatted)
                    return

            raw_input = self.replacer()
            val = numexpr.evaluate(raw_input).item()
            res_formatted = "{:.2e}".format(val)
            self.log_special_operation("Sci", raw_input, res_formatted)
        except Exception as e:
            Mb.show_error("Error", str(e))
            self.clear_calculator()

    # --- Converter Framework ---

    def setup_converter(self, frame, v_in, v_out, units, cmd, clr_cmd, back_cmd, num_cmd):
        # ── ROOT GRID: Adjusted weights to prioritize the content row ──────────────
        frame.grid_columnconfigure(0, weight=2)
        frame.grid_columnconfigure(1, weight=3)

        # Give row 1 (the content) the most weight so it expands to fill space
        frame.grid_rowconfigure(0, weight=0)  # top spacing (minimal)
        frame.grid_rowconfigure(1, weight=1)  # content (primary expansion)
        frame.grid_rowconfigure(2, weight=0)  # bottom spacing (minimal)

        # ── Containers ────────────────────────
        frame.left_container = tb.Frame(frame)
        frame.right_container = tb.Frame(frame)

        frame.left_container.grid(row=1, column=0, sticky="nsew", padx=20)
        frame.right_container.grid(row=1, column=1, sticky="nsew", padx=10, pady=(0, 10))  # Added bottom pady

        frame.left_container.grid_propagate(True)
        frame.right_container.grid_propagate(True)

        # ── LEFT SIDE (Display) ─────
        frame.left_container.grid_columnconfigure(0, weight=1)
        # Center the display vertically within its column
        frame.left_container.grid_rowconfigure(0, weight=1)
        frame.left_container.grid_rowconfigure(1, weight=0)
        frame.left_container.grid_rowconfigure(2, weight=1)

        display_area = tb.Frame(frame.left_container)
        display_area.grid(row=1, column=0, sticky="ew")
        display_area.columnconfigure(0, weight=1)

        tb.Entry(
            display_area,
            textvariable=v_in,
            font=self.font_entry,
            bootstyle="inverse-dark",
            style="Flat.TEntry",
            takefocus=0
        ).pack(fill="x", padx=20, pady=(4, 0))

        d1 = tb.Combobox(display_area, values=units, state="readonly", font=("Segoe UI", 12), bootstyle="dark",
                         style="Flat.TCombobox", takefocus=0)
        d1.pack(fill="x", padx=20)

        swap = tb.Canvas(display_area, width=60, height=40, bg=self.style.colors.bg, highlightthickness=0)
        swap.pack(pady=8)
        arrow = swap.create_text(30, 20, text="⇅", fill=self.style.colors.fg, font=self.font_entry)

        def _hover_on(_):
            swap.itemconfigure(arrow, fill=self.style.colors.secondary)

        def _hover_off(_):
            swap.itemconfigure(arrow, fill=self.style.colors.fg)

        swap.bind("<Enter>", _hover_on)
        swap.bind("<Leave>", _hover_off)

        def _swap(_=None):
            a, b = d1.current(), d2.current()
            d1.current(b)
            d2.current(a)
            cmd()

        swap.bind("<Button-1>", _swap)

        tb.Entry(display_area, textvariable=v_out, state="readonly", font=self.font_entry, bootstyle="inverse-dark",
                 style="Flat.TEntry", takefocus=0).pack(fill="x", padx=20)

        d2 = tb.Combobox(display_area, values=units, state="readonly", font=("Segoe UI", 12), bootstyle="dark",
                         style="Flat.TCombobox", takefocus=0)
        d2.pack(fill="x", padx=20, pady=(0, 4))

        d1.current(0)
        d2.current(1 if len(units) > 1 else 0)
        d1.bind("<<ComboboxSelected>>", cmd)
        d2.bind("<<ComboboxSelected>>", cmd)

        if frame == self.length_frame:
            self.ld1, self.ld2 = d1, d2
        elif frame == self.area_frame:
            self.ad1, self.ad2 = d1, d2
        elif frame == self.temp_frame:
            self.temp_from, self.temp_to = d1, d2

        # ── NUMPAD: Ensure it uses 100% of the container height ──────────────────────
        for c in range(3):
            frame.right_container.columnconfigure(c, weight=1, uniform="numpad")

        for r in range(5):
            # Uniform weight ensures buttons stretch to fill the bottom of the window
            frame.right_container.rowconfigure(r, weight=1, uniform="numpad")

        buttons = [
            ('C', 2, 0), ('←', 1, 0),
            ('7', 0, 1), ('8', 1, 1), ('9', 2, 1),
            ('4', 0, 2), ('5', 1, 2), ('6', 2, 2),
            ('1', 0, 3), ('2', 1, 3), ('3', 2, 3),
            ('0', 1, 4), ('.', 2, 4)
        ]

        frame.converter_buttons = []

        for text, col, row in buttons:
            btn = tb.Button(
                frame.right_container,
                text=text,
                bootstyle=SECONDARY,
                style="Converter.TButton",
                # Removed fixed padding to allow the grid weight to control size
                command=lambda x=text: self._handle_converter_button_click(x, clr_cmd, back_cmd, num_cmd)
            )
            btn.grid(column=col, row=row, sticky="nsew", padx=2, pady=2)
            frame.converter_buttons.append(btn)

    @staticmethod
    def _handle_converter_button_click(x, clr_cmd, back_cmd, num_cmd):
        """Handle converter button clicks with clear conditional logic."""
        if x not in ('C', '←'):
            num_cmd(x)
        elif x == 'C':
            clr_cmd()
        else:  # x == '←'
            back_cmd()

    # --- Converter Implementations ---

    def setup_length_converter_tab(self):
        self.setup_converter(
            self.length_frame,
            self.length_input_text,
            self.length_output_text,
            ["mm", "cm", "m", "km", "inches", "feet", "yards"],
            self.convert_length,
            lambda: clear_input(self.length_input_text, self.length_output_text),
            lambda: backspace_input(self.length_input_text),
            lambda v: handle_num_input(self.length_input_text, v)
        )
        self.length_input_text.trace_add("write", lambda n, i, m: self.convert_length())

    def setup_area_converter_tab(self):
        self.setup_converter(
            self.area_frame,
            self.area_input_text,
            self.area_output_text,
            ["mm²", "cm²", "m²", "km²", "inch²", "feet²", "yards²"],
            self.convert_area,
            lambda: clear_input(self.area_input_text, self.area_output_text),
            lambda: backspace_input(self.area_input_text),
            lambda v: handle_num_input(self.area_input_text, v)
        )
        self.area_input_text.trace_add("write", lambda n, i, m: self.convert_area())

    def setup_temp_converter_tab(self):
        self.setup_converter(
            self.temp_frame,
            self.temp_input_text,
            self.temp_output_text,
            ["°C", "°F", "K"],
            self.convert_temp,
            lambda: clear_input(self.temp_input_text, self.temp_output_text),
            lambda: backspace_input(self.temp_input_text),
            lambda v: handle_num_input(self.temp_input_text, v)
        )
        self.temp_input_text.trace_add("write", lambda n, i, m: self.convert_temp())

    def convert_length(self, event=None):
        f = {"cm": 0.01, "m": 1, "km": 1000, "mm": 0.001, "inches": 0.0254, "feet": 0.3048, "yards": 0.9144}
        do_convert(self.length_input_text, self.length_output_text, self.ld1, self.ld2, f)

    def convert_area(self, event=None):
        f = {"cm²": 0.0001, "m²": 1, "km²": 1000000, "mm²": 0.000001, "inch²": 0.00064516, "feet²": 0.092903,
             "yards²": 0.836127}
        do_convert(self.area_input_text, self.area_output_text, self.ad1, self.ad2, f)

    def convert_temp(self, event=None):
        try:
            v = float(self.temp_input_text.get())
            frm, to = self.temp_from.get(), self.temp_to.get()
            if frm == to: self.temp_output_text.set(f"{v:.2f}"); return
            # To Celsius
            if frm == "°C":
                c = v
            else:
                c = (v - 32) * 5 / 9 if frm == "°F" else v - 273.15
            # From Celsius
            if to == "°C":
                res = c
            else:
                res = c * 9 / 5 + 32 if to == "°F" else c + 273.15
            self.temp_output_text.set(f"{res:.2f}")
        except Exception as e:
            Mb.show_error("Error", str(e))
            self.temp_output_text.set("")

    # --- Responsive Logic ---

    def on_resize(self, event):
        if event.widget != self.root:
            return

        if self._resize_job:
            self.root.after_cancel(self._resize_job)

        self._resize_job = self.root.after(80, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        w = self.root.winfo_width()
        h = self.root.winfo_height()

        if w >= self.HISTORY_BREAKPOINT:
            self.history_manual = False

            if not self.show_history:
                self.show_history = True
                self.history_auto = True
                self.history_panel.grid(row=0, column=1, rowspan=2, sticky="nsew")

            self.hist_btn.pack_forget()

        else:
            if self.history_auto and not self.history_manual:
                self.history_panel.grid_forget()
                self.show_history = False
                self.history_auto = False

            if not self.hist_btn.winfo_ismapped():
                self.hist_btn.pack(side="right")

        # --- Converter layout logic (unchanged) ---
        is_wide = w >= 1000
        for f in (self.length_frame, self.area_frame, self.temp_frame):
            if not hasattr(f, "left_container"):
                continue
            f.left_container.grid_forget()
            f.right_container.grid_forget()
            if is_wide:
                f.left_container.grid(row=1, column=0, sticky="nsew")
                f.right_container.grid(row=0, column=1, rowspan=3, sticky="nsew")
            else:
                f.left_container.grid(row=0, column=0, columnspan=2, sticky="nsew")
                f.right_container.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # --- Font scaling (see Fix #2) ---
        self._resize_fonts(w, h)

    def _resize_fonts(self, w, h):
        scale = round(min(w / self.base_width, h / self.base_height), 2)

        if scale == self._last_font_scale:
            return  # No change → no work

        self._last_font_scale = scale

        self.font_button.configure(size=max(14, int(25 * scale)))
        self.font_entry.configure(size=max(14, int(24 * scale)))
        self.font_converter.configure(size=max(10, int(12 * scale)))

    def show_frame(self, frame, title, initial=False):
        frame.tkraise()
        self.header_label.config(text=title)
        if self.sidebar_open and not initial: self.toggle_sidebar()


if __name__ == "__main__":
    root = tb.Window(themename="calculator")
    calc = Calculator(root)
    root.mainloop()
