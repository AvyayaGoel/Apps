import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
import time
from sympy import sympify
from Maths_Engine import *


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
        "version": "V1.05",
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


class MES:
    def __init__(self, window):
        self.root = window
        self.root.title("Maths Ex Solver V1.1")
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

        illegal_chars = re.findall(r'[^0-9.+\-*/()^]', expr.replace('**', ''))
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
            self.explanation.text.insert(END, f"❌ INVALID MATH: {msg},\n{e}", "danger")
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

        log_text.text.config(state="disabled")



if __name__ == "__main__":
    try:
        win = tb.Window(themename="calculator")
        mes = MES(win)
        win.mainloop()
    except KeyboardInterrupt:
        pass