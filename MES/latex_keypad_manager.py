"""
LaTeX Keypad Manager - Handles mathematical symbol keypad for Maths Engine.
Similar to Formula Sheet keypad but adapted for LaTeX/MathQuill integration.
"""

import logging

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFrame,
                             QPushButton, QLabel, QGridLayout, QScrollArea, QWidget)

# Unified LaTeX symbol structure with mapping and categories
LATEX_SYMBOLS = {
    "Greek Letters": [
        ["\\alpha", "\\beta", "\\gamma", "\\delta", "\\epsilon", "\\zeta", "\\eta", "\\theta"],
        ["\\iota", "\\kappa", "\\lambda", "\\mu", "\\nu", "\\xi", "\\pi", "\\rho"],
        ["\\sigma", "\\tau", "\\upsilon", "\\phi", "\\chi", "\\psi", "\\omega", "\\Omega"],
        ["\\Gamma", "\\Delta", "\\Theta", "\\Lambda", "\\Xi", "\\Pi", "\\Sigma", "\\Phi"]
    ],
    "Calculus": [
        ["\\int", "\\sum", "\\prod", "\\partial", "\\nabla", "\\infty", "\\cdot"],
        ["\\frac", "\\frac{d}{dx}", "\\frac{\\partial}{\\partial x}", "\\lim_{x\\to }"],
        ["\\left| \\right|", "\\left( \\right)", "\\left[ \\right]", "\\left\\{ \\right\\}"]
    ],
    "Operators": [
        ["\\pm", "\\mp", "\\times", "\\div", "\\leq", "\\geq", "\\neq", "\\approx"],
        ["\\equiv", "\\sim", "\\propto", "\\cong", "\\subset", "\\supset", "\\subseteq", "\\supseteq"],
        ["\\in", "\\notin", "\\cup", "\\cap", "\\wedge", "\\vee", "\\neg", "\\implies"],
        ["\\iff", "\\forall", "\\exists", "\\nexists", "\\ast", "\\star", "\\circ"]
    ],
    "Symbols": [
        ["\\sqrt{ }", "\\sqrt[ ]{ }", "\\vec{ }", "\\overline{ }", "\\underline{ }", "\\hat{ }", "\\dot{ }",
         "\\ddot{ }"],
        ["\\sin", "\\cos", "\\tan", "\\cot", "\\sec", "\\csc", "\\arcsin", "\\arccos"],
        ["\\arctan", "\\sinh", "\\cosh", "\\tanh", "\\log", "\\ln", "\\exp", "\\det"]
    ],
    "Special": [
        ["\\pi", "\\theta", "\\lambda", "\\mu", "\\sigma", "\\phi", "\\omega", "\\Delta"],
        ["\\infty", "\\emptyset"],
        ["\\angle", "\\perp", "\\parallel", "\\degree", "\\prime", "\\nabla\\cdot", "\\nabla\\times"]
    ]
}

# Symbol display mapping (LaTeX to Unicode)
SYMBOL_DISPLAY = {
    '\\alpha': 'α', '\\beta': 'β', '\\gamma': 'γ', '\\delta': 'δ',
    '\\epsilon': 'ε', '\\zeta': 'ζ', '\\eta': 'η', '\\theta': 'θ',
    '\\iota': 'ι', '\\kappa': 'κ', '\\lambda': 'λ', '\\mu': 'μ',
    '\\nu': 'ν', '\\xi': 'ξ', '\\pi': 'π', '\\rho': 'ρ',
    '\\sigma': 'σ', '\\tau': 'τ', '\\upsilon': 'υ', '\\phi': 'φ',
    '\\chi': 'χ', '\\psi': 'ψ', '\\omega': 'ω', '\\Omega': 'Ω',
    '\\Gamma': 'Γ', '\\Delta': 'Δ', '\\Theta': 'Θ', '\\Lambda': 'Λ',
    '\\Xi': 'Ξ', '\\Pi': 'Π', '\\Sigma': 'Σ', '\\Phi': 'Φ',
    '\\int': '∫', '\\sum': '∑', '\\prod': '∏', '\\lim': 'lim',
    '\\partial': '∂', '\\nabla': '∇', '\\infty': '∞', '\\cdot': '·',
    '\\pm': '±', '\\mp': '∓', '\\times': '×', '\\div': '÷',
    '\\leq': '≤', '\\geq': '≥', '\\neq': '≠', '\\approx': '≈',
    '\\equiv': '≡', '\\sim': '∼', '\\propto': '∝', '\\cong': '≅',
    '\\subset': '⊂', '\\supset': '⊃', '\\subseteq': '⊆', '\\supseteq': '⊇',
    '\\in': '∈', '\\notin': '∉', '\\cup': '∪', '\\cap': '∩',
    '\\wedge': '∧', '\\vee': '∨', '\\neg': '¬', '\\implies': '⇒',
    '\\iff': '⇔', '\\forall': '∀', '\\exists': '∃', '\\nexists': '∄',
    '\\sqrt': '√', '\\angle': '∠', '\\perp': '⊥', '\\parallel': '∥',
    '\\degree': '°', '\\prime': '′', '\\emptyset': '∅',
    '\\frac': 'a/b', '\\frac{d}{dx}': 'd/dx', "\\sqrt{ }": "√a", "\\sqrt[ ]{ }": "ᵇ√a",
    '\\int_{ }^{ }': '∫', '\\sum_{ }^{ }': '∑', '\\prod_{ }^{ }': '∏',
    '\\lim_{x\\to }': 'lim', '\\frac{\\partial}{\\partial x}': '∂/∂x',
    '\\nabla\\cdot': '∇·', '\\nabla\\times': '∇×',
    '\\left| \\right|': '| |',
    '\\left( \\right)': '( )', '\\left[ \\right]': '[ ]',
    '\\left\\{ \\right\\}': '{ }',
    '\\vec{ }': '⃗', '\\overline{ }': '¯',
    '\\underline{ }': '＿', '\\hat{ }': '̂', '\\dot{ }': '̇',
    '\\ddot{ }': '̈',
    '\\sin': 'sin', '\\cos': 'cos', '\\tan': 'tan', '\\cot': 'cot',
    '\\sec': 'sec', '\\csc': 'csc', '\\arcsin': 'asin', '\\arccos': 'acos',
    '\\arctan': 'atan', '\\sinh': 'sinh', '\\cosh': 'cosh', '\\tanh': 'tanh',
    '\\log': 'log', '\\ln': 'ln', '\\exp': 'exp', '\\det': 'det'
}


class LaTeXButton(QPushButton):
    """Custom button widget that displays mathematical symbols"""

    def __init__(self, latex_code, button_size=(70, 35)):
        super().__init__()
        self.latex_code = latex_code
        self.button_size = button_size
        self.setFixedSize(*button_size)
        self.setup_ui()

    def setup_ui(self):
        """Setup the button UI"""
        # Get the display symbol or use LaTeX code as fallback
        display_text = SYMBOL_DISPLAY.get(self.latex_code, self.latex_code)

        # Set button text
        self.setText(display_text)

        # Apply styling
        self.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                border-radius: 3px;
                font-family: 'Times New Roman', serif;
                font-size: 14px;
                font-weight: bold;
                min-height: 35px;
                max-height: 35px;
            }
            QPushButton:hover {
                background-color: #4ec9b0;
                border-color: #5ed1bc;
            }
            QPushButton:pressed {
                background-color: #3ba99c;
            }
        """)

        # Set tooltip to show LaTeX code
        self.setToolTip(f"LaTeX: {self.latex_code}")

    def get_latex_code(self):
        """Get the LaTeX code for this button"""
        return self.latex_code


class LaTeXKeypadManager:
    """Manages LaTeX mathematical symbol keypad window and functionality."""

    def __init__(self, parent_window, math_input_widget):
        """
        Initialize LaTeX Keypad Manager.
        
        Args:
            parent_window: The main window of the parent application
            math_input_widget: The MathQuill input widget to insert LaTeX into
        """
        self.parent_window = parent_window
        self.math_input_widget = math_input_widget
        self.window = None
        self.is_open = False
        self.drag_position = QPoint()

    def toggle_keypad(self, button_widget=None):
        """
        Toggle keypad window open/closed.
        
        Args:
            button_widget: The button that triggered this toggle
            
        Returns:
            bool: True if keypad was opened, False if closed
        """
        if self.is_open:
            self.close_keypad()
            return False
        return self.open_keypad(button_widget)

    def open_keypad(self, button_widget=None):
        """
        Open keypad window.
        
        Args:
            button_widget: The button that triggered opening
            
        Returns:
            bool: True if successfully opened
        """
        try:
            self.window = QDialog(self.parent_window)
            self.window.setWindowTitle("LaTeX Mathematical Symbols")
            self.window.setWindowFlags(
                Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)
            self.window.resize(600, 400)

            # Position relative to button if provided
            if button_widget:
                button_rect = button_widget.geometry()
                global_pos = button_widget.mapToGlobal(button_rect.bottomLeft())
                self.window.move(global_pos.x(), global_pos.y())

            self.is_open = True
            self._create_keypad_content()
            self.window.show()
            return True

        except Exception as e:
            logging.error(f"Error opening keypad: {e}", exc_info=True)
            return False

    def close_keypad(self):
        """Close keypad window."""
        if self.window and self.is_open:
            try:
                self.window.close()
            except Exception as e:
                logging.error(f"Error closing keypad: {e}", exc_info=True)
            finally:
                self.window = None
                self.is_open = False

    def _create_keypad_content(self):
        """Create content inside keypad window."""
        layout = QVBoxLayout(self.window)

        # Title bar with drag handle
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # Tabbed content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Create tabs for each category
        for category, symbols in LATEX_SYMBOLS.items():
            category_frame = self._create_category_frame(category, symbols)
            scroll_layout.addWidget(category_frame)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def _create_title_bar(self):
        """Create draggable title bar."""
        title_bar = QFrame()
        title_bar.setFrameStyle(QFrame.Shape.StyledPanel)
        title_bar.setStyleSheet("background-color: #3c3c3c; color: white; padding: 5px;")

        layout = QHBoxLayout(title_bar)

        title = QLabel("🧮 LaTeX Mathematical Symbols")
        title.setStyleSheet("font-weight: bold; color: #4ec9b0;")
        layout.addWidget(title)

        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 3px;
                width: 25px;
                height: 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        close_btn.clicked.connect(self.close_keypad)
        layout.addWidget(close_btn)

        # Make title bar draggable
        title_bar.mousePressEvent = self._start_drag
        title_bar.mouseMoveEvent = self._perform_drag

        return title_bar

    def _create_category_frame(self, category, symbols):
        """Create frame for a symbol category."""
        category_frame = QFrame()
        category_frame.setFrameStyle(QFrame.Shape.Box)
        category_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 5px;
                margin: 5px;
            }
        """)

        layout = QVBoxLayout(category_frame)

        # Category title
        title = QLabel(category)
        title.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #4ec9b0;
                padding: 5px;
                background-color: #3c3c3c;
                border-radius: 3px;
            }
        """)
        layout.addWidget(title)

        # Symbol buttons grid
        grid_layout = QGridLayout()

        for row_idx, row_symbols in enumerate(symbols):
            for col_idx, symbol in enumerate(row_symbols):
                if symbol:  # Skip empty symbols
                    # Create LaTeX button with rendered symbol
                    btn = LaTeXButton(symbol, button_size=(70, 35))
                    btn.clicked.connect(lambda checked, b=btn: self._insert_latex(b.get_latex_code()))
                    grid_layout.addWidget(btn, row_idx, col_idx)

        layout.addLayout(grid_layout)
        return category_frame

    def _insert_latex(self, latex_text):
        """
        Insert LaTeX symbol into MathQuill input widget.
        
        Args:
            latex_text: The LaTeX command to insert
        """
        try:
            if self.math_input_widget:
                # Commands that need write() instead of cmd()
                write_commands = {
                    '\\frac{ }{ }', '\\frac{d}{dx}',
                    '\\frac{\\partial}{\\partial x}', '\\lim_{x\\to }',
                    '\\int_{ }^{ }', '\\sum_{ }^{ }', '\\prod_{ }^{ }',
                    '\\sqrt{ }', '\\sqrt[ ]{ }', '\\vec{ }', '\\overline{ }',
                    '\\underline{ }', '\\hat{ }', '\\dot{ }', '\\ddot{ }',
                    '\\left| \\right|',
                    '\\left( \\right)', '\\left[ \\right]', '\\left\\{ \\right\\}',
                    '\\nabla\\cdot', '\\nabla\\times'
                }

                # Properly escape backslashes for JavaScript
                escaped_latex = latex_text.replace('\\', '\\\\')

                # Use appropriate MathQuill method
                if latex_text in write_commands:
                    # For complex commands, use write() to insert the LaTeX text
                    js_code = f"mathField.write('{escaped_latex}'); mathField.focus();"
                else:
                    # For simple commands, use cmd() 
                    js_code = f"mathField.cmd('{escaped_latex}'); mathField.focus();"

                self.math_input_widget.page().runJavaScript(js_code)

                # Keep focus on the input widget
                QTimer.singleShot(50, self.math_input_widget.setFocus)

        except Exception as e:
            logging.error(f"Error inserting LaTeX '{latex_text}': {e}", exc_info=True)

    def _start_drag(self, event):
        """Start dragging the window."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()

    def _perform_drag(self, event):
        """Perform window dragging."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.window.move(new_pos)
            event.accept()

    def is_keypad_open(self):
        """Check if keypad window is currently open."""
        return self.is_open and self.window and self.window.isVisible()
