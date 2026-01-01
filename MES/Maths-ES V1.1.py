import time

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from sympy import simplify
from Maths_Engine import *

TRANSFORMATIONS = (standard_transformations + (implicit_multiplication_application,))

# ─────────────────────────────────────────────
# VERSION HISTORY
# ─────────────────────────────────────────────
MES_HISTORY = [
    {
        "version": "V1.06",
        "date": "2025-12-25",
        "notes": [
            "Hard Guard for unsupported symbols",
            "Improved error explainer",
            "Locked red state on invalid execution",
        ],
    },
    {
        "version": "V1.05",
        "date": "2025-12-25",
        "notes": [
            "Live syntax validation",
            "Copy result button",
            "Unary minus fixes",
        ],
    },
    {
        "version": "V1.02",
        "date": "2025-12-25",
        "notes": [
            "Clear All",
            "Scrolled output",
            "Float cleanup",
        ],
    },
    {
        "version": "V1.00",
        "date": "2025-12-24",
        "notes": [
            "Initial GUI launch",
            "AST-based solver",
        ],
    },
]

# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────
class MES:
    def __init__(self, window: tb.Window):
        self.root = window
        self.root.title("Maths Ex Solver V1.1.1")
        self.root.geometry("800x600")

        self.log_win = None

        self._build_ui()
        self.explanation.text.tag_config(
            "step",
            font=("Consolas", 13),
            foreground="#bbbbbb"
        )

        self.explanation.text.tag_config(
            "highlight",
            font=("Consolas", 13, "bold"),
            foreground="#00bc8c"
        )

        self.explanation.text.tag_config(
            "reason",
            font=("Consolas", 11, "italic"),
            foreground="#3498db"
        )

        self.explanation.text.tag_config(
            "success",
            font=("Consolas", 14, "bold"),
            foreground="#2ecc71"
        )

    # ───────────────────────── UI SETUP ─────────────────────────
    def _build_ui(self):
        self.mainframe = tb.Frame(self.root, padding=20)
        self.mainframe.pack(fill=BOTH, expand=YES)

        tb.Label(
            self.mainframe,
            text="Expression Solver",
            font=("Courier New", 24, "bold"),
        ).pack(pady=(0, 15))

        tb.Button(
            self.mainframe,
            text="📜 Update Log",
            bootstyle="link",
            command=self.show_update_log_window,
        ).pack()

        self.expression = tb.StringVar()
        self.expression.trace_add("write", self.validate_live)

        self.entry = tb.Entry(
            self.mainframe,
            textvariable=self.expression,
            font=("Consolas", 18),
            justify="right",
        )
        self.entry.pack(fill=X, pady=10)
        self.entry.bind("<Return>", lambda e: self.evaluate())

        self._build_buttons()
        self._build_output()

    def _build_buttons(self):
        frame = tb.Frame(self.mainframe)
        frame.pack(fill=X, pady=10)

        tb.Button(
            frame,
            text="Clear All",
            bootstyle="danger",
            width=15,
            command=self.clear_fields,
        ).pack(side=LEFT)

        tb.Button(
            frame,
            text="Evaluate",
            bootstyle="success",
            width=30,
            command=self.evaluate,
        ).pack(side=LEFT, fill=X, expand=YES, padx=(5, 0))

        self.copy_btn = tb.Button(
            self.mainframe,
            text="📋",
            bootstyle="info-link",
            command=self.copy_to_clipboard,
        )
        self.copy_btn.pack(anchor=E)

    def _build_output(self):
        self.explanation = ScrolledText(
            self.mainframe,
            font=("Consolas", 13),
            height=12,
            autohide=True,
            bootstyle="secondary",
        )
        self.explanation.pack(fill=BOTH, expand=YES, pady=10)
        self.explanation.text.config(state="disabled")

    # ───────────────────────── UI ACTIONS ─────────────────────────
    def clear_fields(self):
        self.expression.set("")
        self._clear_output()

    def _clear_output(self):
        self.explanation.text.config(state="normal")
        self.explanation.text.delete("1.0", END)
        self.explanation.text.config(state="disabled")

    def copy_to_clipboard(self):
        text = self.explanation.text.get("1.0", END)
        if "Final Answer =" not in text:
            return

        answer = text.split("=")[-1].strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(answer)

        self.copy_btn.config(text="✅ Copied", bootstyle="success-link")
        self.root.after(1500, self._reset_copy_button)

    def _reset_copy_button(self):
        self.copy_btn.config(text="📋", bootstyle="info-link")

    def validate_live(self, *_):
        expr = self.expression.get()
        if not expr:
            self.entry.configure(bootstyle="default")
            return

        # UPDATED REGEX: Added a-zA-Z to allow variables
        if not re.fullmatch(r"[\d+\-*/().^ a-zA-Z]*", expr):
            self.entry.configure(bootstyle="danger")
            return

        try:
            # Use parse_expr with transformations so '21x' is valid
            parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS)
            self.entry.configure(bootstyle="success")
        except Exception:
            # Check if it's just incomplete (ends in operator) or actually invalid
            if expr and expr[-1] in "+-*/(^":
                self.entry.configure(bootstyle="warning")
            else:
                self.entry.configure(bootstyle="danger")

    # ───────────────────────── SOLVER ─────────────────────────
    def evaluate(self):
        expr = self.expression.get().strip()
        if not expr:
            return

        self._clear_output()
        self.explanation.text.config(state="normal")

        try:
            # ───── Build AST ─────
            tokens = tokenize(expr)
            tokens = insert_implicit_multiplication(tokens)
            postfix = infix_to_postfix(tokens)
            ast = postfix_to_ast(postfix)
            normalize_ast(ast)

            if not ast:
                raise ValueError("Invalid structure")

            # ───── Step 0 ─────
            step = 0
            self._write_step(step, ast, "Original expression", "step")

            previous = ast.to_string()

            # ───── Stepwise Reduction Loop ─────
            while True:
                changed, reason, kind = reduce_one_step(ast)
                current = ast.to_string()

                # Stop if nothing actually changed
                if not changed or current == previous:
                    break

                step += 1
                self._write_step(step, ast, reason, kind)

                previous = current

                # Quadratic solving is terminal
                if kind == "quadratic":
                    break

                self.root.update()
                time.sleep(0.35)

            # ───── Final Result ─────
            self.explanation.text.insert(END, "\n")

            if has_variables(expr):
                # Symbolic result
                res = solve_symbolic(expr)

                final_expr = simplify(parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS))
                self.explanation.text.insert(
                    END,
                    f"Final Result: {final_expr}\n",
                    "success"
                )

                if "roots" in res:
                    self.explanation.text.insert(
                        END,
                        f"Roots: {res['roots']}\n",
                        "success"
                    )
            else:
                # Numeric result
                final_expr = simplify(parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS))
                self.explanation.text.insert(
                    END,
                    f"Final Result: {final_expr}\n",
                    "success"
                )


        except Exception as e:
            self._write_error(explain_error(expr, e))

        self.explanation.text.config(state="disabled")


    def _write_step(self, step, ast, reason="", step_type=""):
        """
        Writes a single solution step with explanation and highlighting.
        """

        if not self.explanation or not self.explanation.text.winfo_exists():
            return  # Prevent Tk crashes if widget is gone

        expr = format_step_string(ast.to_string())

        # ---- Step line ----
        self.explanation.text.insert(
            END,
            f"Step {step}: {expr}\n",
            ("step", step_type)
        )

        # ---- Explanation line ----
        if reason:
            self.explanation.text.insert(
                END,
                f"   ↳ {reason}\n",
                "explain"
            )

        self.explanation.text.insert(END, "\n")
        self.explanation.text.see(END)

    def _write_error(self, msg):
        self.explanation.text.insert(END, f"❌ Error: {msg}")
        self.entry.configure(bootstyle="danger")
        self.explanation.text.config(state="disabled")

    # ───────────────────────── LOG WINDOW ─────────────────────────
    def show_update_log_window(self):
        if self.log_win is not None and self.log_win.winfo_exists():
            self.log_win.lift()  # Bring it to the top
            self.log_win.focus_force()  # Give it keyboard focus
            return

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
        MES(win)
        win.mainloop()
    except KeyboardInterrupt:
        pass
