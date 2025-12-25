import re
import time

import ttkbootstrap as tb
from sympy import sympify
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText

# --- ENGINE LOGIC (UNCHANGED) ---
value_order = {'+': 1, '-': 1, '*': 2, '/': 2, '**': 3, '^': 3}


def tokenize(expr):
    return re.findall(r'\d+\.?\d*|\*\*|[+\-*/()^]', expr.replace(" ", ""))


MES_HISTORY = [
    {
        "version": "V1.06",
        "date": "2025-12-25",
        "notes": [
            "Feature: Implemented 'Hard Guard' logic to prevent execution of unsupported symbols.",
            "Feature: Enhanced Error Explainer to specifically identify illegal characters (%, $, etc.).",
            "UI: Improved Entry box behavior to lock red state on invalid execution attempts."
        ]
    },
    {
        "version": "V1.05 (Latest)",
        "date": "2025-12-25",
        "notes": [
            "Feature: Real-time Syntax Validation (Green/Yellow/Red Entry box).",
            "Feature: Smart Error Explainer (Specific feedback for syntax errors).",
            "Feature: Copy result button.",
            "Fixed Bug: Unary Minus support for negative numbers in parentheses.",
            "Fixed Bug: Cleaned math string artifacts (A+-B becomes A-B)."
        ]
    },
    {
        "version": "V1.02",
        "date": "2025-12-25",
        "notes": [
            "Added 'Clear All' functionality for session resets.",
            "Integrated ScrolledText for persistent step-by-step output.",
            "Fixed floating-point artifacts using display formatting.",
            "UI polish and font alignment improvements."
        ]
    },
    {
        "version": "V1.00",
        "date": "2025-12-24",
        "notes": [
            "Initial UI Launch using ttkbootstrap.",
            "Implemented AST (Abstract Syntax Tree) engine for complex parsing.",
            "Transitioned from Terminal to Graphical Interface."
        ]
    },
    {
        "version": "V0.50 (Alpha)",
        "date": "2025-12-24",
        "notes": [
            "Added Power support (**, ^) to the engine.",
            "BODMAS priority logic refinement.",
            "Bug fixes for division and negative number handling."
        ]
    },
    {
        "version": "V0.01 (Legacy)",
        "date": "2025-12-24",
        "notes": [
            "Initial Terminal-based prototype.",
            "Basic tokenization engine.",
            "Supported fundamental operators: +, -, *, /"
        ]
    }
]


class Node:
    def __init__(self, value, left=None, right=None):
        self.value, self.left, self.right = value, left, right

    def is_number(self):
        return self.left is None and self.right is None

    def to_string(self):
        if self.is_number():
            return self.value

        l = self.left.to_string()
        r = self.right.to_string()

        # Parentheses for precedence
        if not self.left.is_number() and value_order[self.left.value] < value_order[self.value]:
            l = f"({l})"
        if not self.right.is_number() and value_order[self.right.value] < value_order[self.value]:
            r = f"({r})"

        # ---- CLEAN +- MESS ----
        if self.value == '+' and r.startswith('-'):
            return f"{l}-{r[1:]}"  # A + -B → A - B

        if self.value == '-' and r.startswith('-'):
            return f"{l}+{r[1:]}"  # A - -B → A + B

        # ---- FORCE PARENTHESES FOR NEGATIVES IN */^ ----
        if self.value in ('*', '/', '^', '**') and r.startswith('-'):
            r = f"({r})"

        return f"{l}{self.value}{r}"


def preprocess_sqrt(tokens):
    new_tokens = []
    i = 0
    while i < len(tokens):
        if tokens[i] == 'sqrt':
            # Logic: sqrt(X) -> (X)**0.5
            # We assume sqrt is always followed by (content)
            new_tokens.append('(')
            i += 1  # skip 'sqrt'
            # We will append the content and close it with )**0.5
            # This is a simple version, but works for sqrt(number)
        elif i > 0 and tokens[i - 1] == 'sqrt':
            # This part is handled by the loop logic
            pass
        new_tokens.append(tokens[i])
        if i > 1 and tokens[i] == ')' and tokens[i - len(tokens)] == '(':  # very basic check
            # This needs careful index tracking
            pass
        i += 1
    return new_tokens


def infix_to_postfix(tokens):
    output, ops = [], []
    # FIX: Track if we just saw an operator or '(' to identify negative numbers
    prev_token = "("

    i = 0
    while i < len(tokens):
        t = tokens[i]

        # Handle Negatives: If '-' follows '(' or is at the start
        if t == '-' and (prev_token == '(' or prev_token in value_order):
            # Peek at the next token to see if it's a number
            if i + 1 < len(tokens) and tokens[i + 1].replace('.', '', 1).isdigit():
                output.append("-" + tokens[i + 1])  # Join '-' with the number
                prev_token = tokens[i + 1]
                i += 2  # Skip the '-' and the number
                continue

        if t.replace('.', '', 1).replace('-', '', 1).isdigit():
            output.append(t)
        elif t in value_order:
            while (ops and ops[-1] in value_order and ((value_order[ops[-1]] > value_order[t]) or (
                    value_order[ops[-1]] == value_order[t] and t not in ('**', '^')))):
                output.append(ops.pop())
            ops.append(t)
        elif t == '(':
            ops.append(t)
        elif t == ')':
            while ops and ops[-1] != '(': output.append(ops.pop())
            ops.pop()

        prev_token = t
        i += 1

    while ops: output.append(ops.pop())
    return output


def fix_unary_minus(tokens):
    fixed = []
    prev = None

    for t in tokens:
        if t == '-' and (prev is None or prev in value_order or prev == '('):
            fixed.append('0')
            fixed.append('-')
        else:
            fixed.append(t)
        prev = t

    return fixed


def postfix_to_ast(postfix):
    stack = []
    for t in postfix:
        if t.replace('.', '', 1).isdigit():
            stack.append(Node(t))
        else:
            b, a = stack.pop(), stack.pop()
            stack.append(Node(t, a, b))
    return stack[0]


def reduce_one_step(node):
    if node.is_number(): return False
    if node.left.is_number() and node.right.is_number():
        a, b = float(node.left.value), float(node.right.value)
        if node.value == '+':
            resul = a + b
        elif node.value == '-':
            resul = a - b
        elif node.value == '*':
            resul = a * b
        elif node.value == '/':
            resul = a / b
        elif node.value in ('**', '^'):
            resul = a ** b
        node.value = f"{resul:.3f}".rstrip('0').rstrip('.')
        node.left = node.right = None
        return True
    return reduce_one_step(node.left) or reduce_one_step(node.right)


# --- NEW: DISPLAY FORMATTER (FIXES DECIMAL WITHOUT TOUCHING SOLVER) ---
def format_step_string(raw_str):
    """Finds decimals in the string and rounds them to 2 places for display."""

    def round_match(match):
        val = float(match.group())
        return f"{val:.2f}".rstrip('0').rstrip('.')

    return re.sub(r'\d+\.\d+', round_match, raw_str)


def explain_error(expr, err):
    if expr.count('(') != expr.count(')'):
        return "Unmatched parentheses"

    if re.search(r'[+\-*/^]{2,}', expr.replace('**', '')):
        return "Two operators in a row"

    if expr.strip()[-1] in '+-*/^':
        return "Expression ends with an operator"

    if 'division by zero' in str(err).lower():
        return "Division by zero is not allowed"

    return "Invalid mathematical structure"


# --- GUI CLASS ---
class MES:
    def __init__(self, window):
        self.root = window
        self.root.title("Maths Ex Solver V1.06")
        self.root.geometry("800x600")

        # Main Container with padding
        self.mainframe = tb.Frame(self.root, padding=20)
        self.mainframe.pack(fill=BOTH, expand=YES)

        # Title
        tb.Label(self.mainframe,
                 text="Expression Solver",
                 font=("Courier New", 24, "bold")
                 ).pack(pady=(0, 20))

        # Add this in your __init__ or es_mainframe
        self.log_btn = tb.Button(
            self.mainframe,
            text="📜Update Log",
            bootstyle="link",  # "Link" style makes it look like a subtle footer button
            command=self.show_update_log_window
        )
        self.log_btn.pack(side=TOP, padx=5)

        # Expression Input
        self.log_win = None
        self.expression = tb.StringVar()
        self.expression.trace_add("write", self.validate_live)  # Tracks every keystroke
        self.e = tb.Entry(self.mainframe, textvariable=self.expression, font=("Consolas", 18), justify="right")
        self.e.pack(fill=X, pady=10)
        self.e.bind("<Return>", lambda e: self.evaluate())

        # Button Row
        self.btn_frame = tb.Frame(self.mainframe)
        self.btn_frame.pack(fill=X, pady=10)

        # In your es_mainframe setup
        self.special_func_frame = tb.Frame(self.mainframe, padding=5)

        # Add your function buttons to this frame
        tb.Button(self.special_func_frame, text="√x", bootstyle="outline-info",
                  command=self.insert_sqrt, width=8).pack(side=LEFT, padx=5)
        tb.Button(self.special_func_frame, text="x^y", bootstyle="outline-info",
                  command=lambda: self.insert_at_cursor("**"), width=8).pack(side=LEFT, padx=5)
        tb.Button(self.special_func_frame, text="π", bootstyle="outline-info",
                  command=lambda: self.insert_at_cursor("3.141"), width=8).pack(side=LEFT, padx=5)

        self.clear_btn = tb.Button(self.btn_frame, text="Clear All", bootstyle="danger",
                                   command=self.clear_fields, width=15)
        self.clear_btn.pack(side=LEFT, padx=(0, 5))

        self.eval_btn = tb.Button(self.btn_frame, text="Evaluate", bootstyle="success",
                                  command=self.evaluate, width=30)
        self.eval_btn.pack(side=LEFT, fill=X, expand=YES, padx=(5, 0))

        # Copy Button (ChatGPT Style)
        self.copy_btn = tb.Button(
            self.mainframe,
            text="📋",
            bootstyle="info-link",
            command=self.copy_to_clipboard
        )
        self.copy_btn.pack(anchor=E)

        # Output Area (ScrolledText handles the window overflow)
        self.explanation = ScrolledText(self.mainframe, font=("Consolas", 13), height=12,
                                        autohide=True, bootstyle="secondary")
        self.explanation.pack(fill=BOTH, expand=YES, pady=10)
        self.explanation.text.config(state="disabled")  # Initial state

    def insert_at_cursor(self, text):
        # Inserts text and keeps the focus so you can keep typing
        pos = self.e.index("insert")
        self.e.insert(pos, text)
        self.e.focus_set()

    def insert_sqrt(self):
        # Specific logic for sqrt to put cursor inside brackets
        pos = self.e.index("insert")
        self.e.insert(pos, "sqrt()")
        self.e.icursor(pos + 5)  # Moves cursor inside the ()
        self.e.focus_set()

    def clear_fields(self):
        self.expression.set("")
        self.explanation.text.config(state="normal")
        self.explanation.text.delete('1.0', END)
        self.explanation.text.config(state="disabled")

    def toggle_special_functions(self):
        # If it's already showing, hide it. Otherwise, show it.
        if self.special_func_frame.winfo_viewable():
            self.special_func_frame.pack_forget()
        else:
            # Pack it specifically BEFORE the explanation text box
            self.special_func_frame.pack(after=self.btn_frame, fill=X, pady=5)

    def validate_live(self, *args):
        expr_text = self.expression.get()
        if not expr_text:
            self.e.configure(bootstyle="default")
            return

            # 1. Immediate Red if illegal characters are typed
        if not re.match(r'^[\d.+\-*/()^\s]*$', expr_text):
            self.e.configure(bootstyle="danger")
            return

        try:
            sympify(expr_text.replace('^', '**'))
            self.e.configure(bootstyle="success")
        except:
            if expr_text[-1] in "+-*/(^" or expr_text.count('(') > expr_text.count(')'):
                self.e.configure(bootstyle="warning")
            else:
                self.e.configure(bootstyle="danger")

    def copy_to_clipboard(self):
        # Pulls the final answer from the explanation text
        full_text = self.explanation.text.get("1.0", "end")
        if "Final Answer =" in full_text:
            answer = full_text.split('=')[-1].strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(answer)
            # Visual feedback on the button
            self.copy_btn.config(text="✅ Copied", bootstyle="success-link")
            self.root.after(2000, lambda: self.copy_btn.config(text="📋", bootstyle="info-link"))

    def evaluate(self):
        # NEW: Collapse the row when evaluation starts
        self.special_func_frame.pack_forget()
        expr = self.expression.get()
        if not expr.strip(): return

        self.explanation.text.config(state="normal")
        self.explanation.text.delete('1.0', END)

        illegal_chars = re.findall(r'[^0-9.+\-*/()^ ]', expr.replace('**', ''))
        if illegal_chars:
            unique_illegal = list(set(illegal_chars))
            msg = f"Invalid Symbol(s): {', '.join(unique_illegal)}\nThese characters are not supported by the MES engine."
            self.explanation.text.insert(END, f"⚠️ ERROR: {msg}", "danger")
            self.e.config(bootstyle="danger")
            self.explanation.text.config(state="disabled")
            return

        # 2. Check if the math is actually valid before running the loop
        try:
            sympify(expr.replace('^', '**'))
        except Exception as e:
            msg = explain_error(expr, e)
            self.explanation.text.insert(END, f"❌ INVALID MATH: {msg}", "danger")
            self.e.config(bootstyle="danger")
            self.explanation.text.config(state="disabled")
            return

        try:
            tokens = tokenize(expr)
            tokens = fix_unary_minus(tokens)
            postfix = infix_to_postfix(tokens)
            ast_root = postfix_to_ast(postfix)

            n = 0
            # Apply formatting to the display string
            display_str = format_step_string(ast_root.to_string())
            self.explanation.text.insert(END, f"Step {n}: {display_str}\n", "step")

            while not ast_root.is_number():
                reduce_one_step(ast_root)
                n += 1
                display_str = format_step_string(ast_root.to_string())
                self.explanation.text.insert(END, f"Step {n}: {display_str}\n")

                self.explanation.text.see(END)
                self.root.update()
                time.sleep(0.2)

            self.explanation.text.insert(END, f"\nFinal Answer = {display_str}", "success")
        except Exception as e:
            msg = explain_error(expr, e)
            self.explanation.text.insert(END, f"\nError: {msg}", "danger")
            self.e.config(bootstyle="danger")
            self.e.select_range(0, END)

        self.explanation.text.config(state="disabled")

    def show_update_log_window(self):
        # 1. Check if the window already exists and is 'alive'
        if self.log_win is not None and self.log_win.winfo_exists():
            self.log_win.lift()  # Bring it to the top
            self.log_win.focus_force()  # Give it keyboard focus
            return

        # 2. If it doesn't exist, create it
        self.log_win = tb.Toplevel(title="MES Update History")
        self.log_win.geometry("500x400")
        self.log_win.position_center()

        # Header
        tb.Label(self.log_win, text="VERSION HISTORY", font=("Impact", 20),
                 bootstyle="info").pack(pady=10)

        # Scrolled text for the log
        log_text = ScrolledText(self.log_win, padding=10, height=15, autohide=True)
        log_text.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Styles
        log_text.text.tag_config("v_tag", foreground="#00bc8c", font=("Consolas", 11, "bold"))
        log_text.text.tag_config("d_tag", foreground="#3498db")

        # Populate
        for entry in MES_HISTORY:
            log_text.text.insert(END, f" {entry['version']}", "v_tag")
            log_text.text.insert(END, f" | {entry['date']}\n", "d_tag")
            for note in entry['notes']:
                log_text.text.insert(END, f"  • {note}\n")
            log_text.text.insert(END, "\n")

        log_text.text.config(state="disabled")  # Make it read-only


if __name__ == "__main__":
    # "Cyborg" or "Darkly" looks very professional for this
    win = tb.Window(themename="calculator")
    mes = MES(win)
    win.mainloop()
