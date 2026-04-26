import time
import tkinter as tk

import ttkbootstrap as tb
from sympy import simplify
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText

from Maths_Engine import *
from wysiwyg_math_input import WYSIWYGMathInput

TRANSFORMATIONS = (standard_transformations + (implicit_multiplication_application,))

# ─────────────────────────────────────────────
# VERSION HISTORY
# ─────────────────────────────────────────────
MES_HISTORY = [
    {
        "version": "V1.2.0",
        "date": "2026-02-25",
        "notes": [
            "Added WYSIWYG math input with real-time rendering",
            "Superscript (^) and subscript (_) cursor positioning",
            "GeoGebra/Wolfram Alpha style mathematical input",
            "Real-time LaTeX rendering preview",
            "Toggle between WYSIWYG and regular input modes",
        ],
    },
    {
        "version": "V1.1.2",
        "date": "2026-02-25",
        "notes": [
            "Added LaTeX format support",
            "Users can now toggle between regular and LaTeX display",
            "Automatic LaTeX conversion for mathematical expressions",
            "LaTeX output for step-by-step solutions",
        ],
    },
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
        self.root.title("Maths Ex Solver V1.2.0")
        self.root.geometry("800x700")

        self.log_win = None
        self.latex_mode = tk.BooleanVar(value=True)  # Default to LaTeX mode
        self.wysiwyg_mode = tk.BooleanVar(value=True)  # Default to WYSIWYG

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

        # LaTeX display styles
        self.explanation.text.tag_config(
            "latex",
            font=("Times New Roman", 16),  # Larger font for LaTeX
            foreground="#e74c3c"
        )

        # Error display styles
        self.explanation.text.tag_config(
            "error",
            font=("Consolas", 12),
            foreground="#e74c3c"
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

        # Input mode toggle
        mode_frame = tb.Frame(self.mainframe)
        mode_frame.pack(fill=X, pady=5)

        tb.Checkbutton(
            mode_frame,
            text="WYSIWYG Math Input",
            variable=self.wysiwyg_mode,
            bootstyle="success",
            command=self.toggle_input_mode,
        ).pack(side=LEFT)

        tb.Checkbutton(
            mode_frame,
            text="LaTeX Display",
            variable=self.latex_mode,
            bootstyle="info",
            command=self.toggle_latex_display,
        ).pack(side=LEFT, padx=(20, 0))

        # Expression input (will be set up based on mode)
        self.input_container = tb.Frame(self.mainframe)
        self.input_container.pack(fill=X, pady=10)

        self._setup_input()

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
            wrap=tk.WORD,  # Better word wrapping
            undo=True,  # Enable undo functionality
            maxundo=-1,  # Unlimited undo
        )
        self.explanation.pack(fill=BOTH, expand=YES, pady=10)
        self.explanation.text.config(state="disabled")

    def _setup_input(self):
        """Setup the appropriate input widget based on mode"""
        # Clear existing input
        for widget in self.input_container.winfo_children():
            widget.destroy()

        if self.wysiwyg_mode.get():
            # WYSIWYG Math Input
            self.math_input = WYSIWYGMathInput(
                self.input_container,
                on_expression_change=self.on_expression_change
            )
            self.math_input.pack(fill=X)
            self.entry = None  # No regular entry in WYSIWYG mode
        else:
            # Regular text input
            self.expression = tb.StringVar()
            self.expression.trace_add("write", self.validate_live)

            self.entry = tb.Entry(
                self.input_container,
                textvariable=self.expression,
                font=("Consolas", 18),
                justify="right",
            )
            self.entry.pack(fill=X)
            self.entry.bind("<Return>", lambda e: self.evaluate())
            self.math_input = None  # No WYSIWYG in regular mode

    def toggle_input_mode(self):
        """Toggle between WYSIWYG and regular input"""
        current_expr = self.get_expression()
        self._setup_input()
        self.set_expression(current_expr)

    def on_expression_change(self, expr):
        """Handle expression change from WYSIWYG input"""
        # Trigger evaluation if needed
        pass

    def get_expression(self):
        """Get current expression from active input"""
        if self.wysiwyg_mode.get() and self.math_input:
            return self.math_input.get_expression()
        elif self.entry:
            return self.expression.get()
        return ""

    def set_expression(self, expr):
        """Set expression in active input"""
        if self.wysiwyg_mode.get() and self.math_input:
            self.math_input.set_expression(expr)
        elif self.entry:
            self.expression.set(expr)

    # ───────────────────────── UI ACTIONS ─────────────────────────
    def clear_fields(self):
        if self.wysiwyg_mode.get() and self.math_input:
            self.math_input.clear()
        elif self.entry:
            self.expression.set("")
        self._clear_output()

    def _clear_output(self):
        self.explanation.text.config(state="normal")
        self.explanation.text.delete("1.0", END)
        self.explanation.text.config(state="disabled")

    def copy_to_clipboard(self):
        text = self.explanation.text.get("1.0", END)
        if "Final Result =" not in text:
            return

        answer = text.split("=")[-1].strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(answer)

        self.copy_btn.config(text="✅ Copied", bootstyle="success-link")
        self.root.after(1500, self._reset_copy_button)

    def _reset_copy_button(self):
        self.copy_btn.config(text="📋", bootstyle="info-link")

    def toggle_latex_display(self):
        """Toggle between regular and LaTeX display modes"""
        if self.get_expression():
            self.evaluate()  # Re-evaluate with new display mode

    def validate_live(self, *_):
        expr = self.get_expression()
        if not expr:
            if self.entry:
                self.entry.configure(bootstyle="default")
            return

        # UPDATED REGEX: Added a-zA-Z to allow variables
        if not re.fullmatch(r"[\d+\-*/().^ a-zA-Z]*", expr):
            if self.entry:
                self.entry.configure(bootstyle="danger")
            return

        try:
            # Use parse_expr with transformations so '21x' is valid
            parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS)
            if self.entry:
                self.entry.configure(bootstyle="success")
        except Exception:
            # Check if it's just incomplete (ends in operator) or actually invalid
            if expr and expr[-1] in "+-*/(^":
                if self.entry:
                    self.entry.configure(bootstyle="warning")
            else:
                if self.entry:
                    self.entry.configure(bootstyle="danger")

    # ───────────────────────── SOLVER ─────────────────────────
    def evaluate(self):
        expr = self.get_expression().strip()
        if not expr:
            return

        self._clear_output()
        self.explanation.text.config(state="normal")

        try:
            # Check if it's an equation first
            if '=' in expr:
                # Handle equations directly without AST building
                res = solve_symbolic(expr)

                if "error" in res:
                    self.explanation.text.insert(
                        END,
                        f"❌ Error solving equation: {res['error']}\n",
                        "error"
                    )
                elif "roots" in res and res["roots"]:
                    if self.latex_mode.get():
                        roots_str = ", ".join([to_latex(root) for root in res['roots']])
                        var_name = res.get('variable', 'x')
                        self.explanation.text.insert(
                            END,
                            f"Solutions: ${var_name} = {roots_str}$\n",
                            "latex"
                        )
                    else:
                        var_name = res.get('variable', 'x')
                        self.explanation.text.insert(
                            END,
                            f"Solutions: {var_name} = {res['roots']}\n",
                            "success"
                        )
                elif "solutions" in res:
                    # Multiple variables case
                    if self.latex_mode.get():
                        sol_text = []
                        for var, roots in res['solutions'].items():
                            roots_str = ", ".join([to_latex(root) for root in roots])
                            sol_text.append(f"${var} = {roots_str}$")
                        self.explanation.text.insert(
                            END,
                            f"Solutions: {', '.join(sol_text)}\n",
                            "latex"
                        )
                    else:
                        sol_text = []
                        for var, roots in res['solutions'].items():
                            sol_text.append(f"{var} = {roots}")
                        self.explanation.text.insert(
                            END,
                            f"Solutions: {', '.join(sol_text)}\n",
                            "success"
                        )
                else:
                    self.explanation.text.insert(
                        END,
                        "No solutions found\n",
                        "success"
                    )
            else:
                # Regular expression - use AST building
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
                    # Symbolic result (non-equation)
                    res = solve_symbolic(expr)

                    final_expr = simplify(parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS))

                    if self.latex_mode.get():
                        latex_result = to_latex(str(final_expr))
                        self.explanation.text.insert(
                            END,
                            f"Final Result: ${latex_result}$\n",
                            "latex"
                        )
                    else:
                        self.explanation.text.insert(
                            END,
                            f"Final Result: {final_expr}\n",
                            "success"
                        )

                    if "roots" in res:
                        if self.latex_mode.get():
                            roots_str = ", ".join([to_latex(root) for root in res['roots']])
                            self.explanation.text.insert(
                                END,
                                f"Roots: $x = {roots_str}$\n",
                                "latex"
                            )
                        else:
                            self.explanation.text.insert(
                                END,
                                f"Roots: {res['roots']}\n",
                                "success"
                            )
                else:
                    # Numeric result
                    final_expr = simplify(parse_expr(expr.replace("^", "**"), transformations=TRANSFORMATIONS))

                    if self.latex_mode.get():
                        latex_result = to_latex(str(final_expr))
                        self.explanation.text.insert(
                            END,
                            f"Final Result: ${latex_result}$\n",
                            "latex"
                        )
                    else:
                        self.explanation.text.insert(
                            END,
                            f"Final Result: {final_expr}\n",
                            "success"
                        )

        except Exception as e:
            # Enhanced error handling - don't break on unknown expressions
            try:
                error_msg = explain_error(expr, e)
                self._write_error(error_msg)
            except Exception as fallback_error:
                # Ultimate fallback if even error handling fails
                self._write_error(f"Unable to process expression: {expr}")

            # Try to at least show the LaTeX rendering if possible
            try:
                if self.latex_mode.get():
                    latex_result = to_latex(expr)
                    self.explanation.text.insert(
                        END,
                        f"\nLaTeX representation: ${latex_result}$\n",
                        "latex"
                    )
                    self.explanation.text.config(state="disabled")
            except:
                pass  # If LaTeX fails too, just show the error

        self.explanation.text.config(state="disabled")


    def _write_step(self, step, ast, reason="", step_type=""):
        """
        Writes a single solution step with explanation and highlighting.
        Supports both regular text and LaTeX display modes.
        """

        if not self.explanation or not self.explanation.text.winfo_exists():
            return  # Prevent Tk crashes if widget is gone

        if self.latex_mode.get():
            # LaTeX mode - convert to proper LaTeX
            try:
                latex_expr = ast_to_latex(ast)
                display_expr = f"${latex_expr}$"
            except:
                # Fallback to regular expression
                expr = format_step_string(ast.to_string())
                display_expr = expr
        else:
            # Regular mode
            expr = format_step_string(ast.to_string())
            display_expr = expr

        # ---- Step line ----
        self.explanation.text.insert(
            END,
            f"Step {step}: {display_expr}\n",
            ("latex" if self.latex_mode.get() else "step", step_type)
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
        # Only configure entry if it exists (not in WYSIWYG mode)
        if self.entry:
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
        win = tb.Window(themename="darkly")
        MES(win)
        win.mainloop()
    except KeyboardInterrupt:
        pass
