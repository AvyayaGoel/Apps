"""
Calculator Tab - The main calculator interface using PyQt6.
Simple QLineEdit with custom styling (no MathQuill).
"""

import logging
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QLabel, QScrollArea,
    QFrame, QSizePolicy, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QKeyEvent

from calculator_engine import CalculationError, get_engine
from constants_calculator import FONT
import math

# Setup logger
logger = logging.getLogger(__name__)


class TrigOverlay(QFrame):
    """Floating overlay for trig functions - appears above keypad."""

    func_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(240, 200)
        self._setup_ui()
        self._apply_styles()
        self.hide()

    def _setup_ui(self):
        # Main frame with border
        container = QFrame()
        container.setObjectName("trigContainer")
        container.setStyleSheet("""
            #trigContainer {
                background-color: #3d3d3d;
                border: 3px solid #ff9500;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

        inner_layout = QVBoxLayout(container)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.setSpacing(6)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Normal tab - 3x2 grid
        normal_tab = QWidget()
        normal_layout = QGridLayout(normal_tab)
        normal_layout.setSpacing(6)

        normal_funcs = [
            ('sin', 0, 0), ('cos', 0, 1), ('tan', 0, 2),
            ('csc', 1, 0), ('sec', 1, 1), ('cot', 1, 2),
        ]

        for text, row, col in normal_funcs:
            btn = QPushButton(text)
            btn.setFixedHeight(40)
            btn.setFont(QFont(FONT, 12))
            btn.clicked.connect(lambda checked, t=text: self._on_func_clicked(t))
            normal_layout.addWidget(btn, row, col)

        self.tabs.addTab(normal_tab, "Fn")

        # Inverse tab - 3x2 grid
        inverse_tab = QWidget()
        inverse_layout = QGridLayout(inverse_tab)
        inverse_layout.setSpacing(6)

        inverse_funcs = [
            ('sin⁻¹', 0, 0), ('cos⁻¹', 0, 1), ('tan⁻¹', 0, 2),
            ('csc⁻¹', 1, 0), ('sec⁻¹', 1, 1), ('cot⁻¹', 1, 2),
        ]

        for text, row, col in inverse_funcs:
            btn = QPushButton(text)
            btn.setFixedHeight(40)
            btn.setFont(QFont(FONT, 12))
            btn.clicked.connect(lambda checked, t=text: self._on_func_clicked(t))
            inverse_layout.addWidget(btn, row, col)

        self.tabs.addTab(inverse_tab, "Inv")
        inner_layout.addWidget(self.tabs)

        # Close button
        close_btn = QPushButton("✕ Close")
        close_btn.setFixedHeight(30)
        close_btn.setFont(QFont(FONT, 10))
        close_btn.clicked.connect(self.hide)
        inner_layout.addWidget(close_btn)

    def show_at(self, widget):
        """Show overlay positioned near the given widget."""
        # Get widget's position in screen coordinates
        pos = widget.mapToGlobal(QPoint(0, 0))
        # Position above the widget, centered
        x = pos.x() + widget.width() // 2 - self.width() // 2
        y = pos.y() - self.height() - 10  # 10px gap above
        self.move(x, y)
        self.show()

    def _on_func_clicked(self, func_name):
        self.func_selected.emit(func_name)
        self.hide()

    def _apply_styles(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: #ffffff;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QTabWidget::pane {
                border: none;
                background-color: #353535;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #4a4a4a;
                color: #a0a0a0;
                padding: 6px 16px;
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #ff9500;
                color: #ffffff;
            }
        """)


class HistoryEntry(QWidget):
    """Single history entry widget."""
    clicked = pyqtSignal(str, str)  # expression, result

    def __init__(self, expression: str, result: str, parent=None):
        super().__init__(parent)
        self.expression = expression
        self.result = result
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)

        self.expr_label = QLabel(f"{self.expression} =")
        self.expr_label.setStyleSheet("color: #888888; font-size: 12px;")

        self.result_label = QLabel(self.result)
        self.result_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")

        layout.addWidget(self.expr_label)
        layout.addWidget(self.result_label)

        self.setStyleSheet("""
            HistoryEntry {
                background-color: #3a3a3a;
                border-radius: 6px;
            }
            HistoryEntry:hover {
                background-color: #4a4a4a;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(self.expression, self.result)


class CalculatorTab(QWidget):
    """Main calculator tab with display, buttons, and history.
    Supports 'standard' and 'scientific' modes."""

    def __init__(self, mode: str = "standard", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.is_degrees = True  # For scientific mode: True = degrees, False = radians
        self.engine = get_engine()
        # State for repeat equals functionality
        self._last_left_operand = None
        self._last_operator = None
        self._last_right_operand = None
        self._last_result = None
        self._just_calculated = False
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Left side: Calculator
        calc_widget = QWidget()
        calc_layout = QVBoxLayout(calc_widget)
        calc_layout.setContentsMargins(0, 0, 0, 0)
        calc_layout.setSpacing(10)

        # Display area
        self._setup_display(calc_layout)

        # Button grid (different for standard vs scientific)
        if self.mode == "scientific":
            self._setup_scientific_buttons(calc_layout)
        else:
            self._setup_standard_buttons(calc_layout)

        main_layout.addWidget(calc_widget, stretch=2)

        # Right side: History panel
        self._setup_history(main_layout)

    def _setup_display(self, parent_layout):
        """Setup the expression display area."""
        display_frame = QFrame()
        display_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid #3d3d3d;
            }
        """)
        display_layout = QVBoxLayout(display_frame)
        display_layout.setContentsMargins(15, 15, 15, 15)

        # History expression label (shows previous calculation)
        self.history_label = QLabel("")
        self.history_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.history_label.setStyleSheet("color: #888888; font-size: 14px; border: none; background: transparent;")
        self.history_label.setFont(QFont(FONT, 12))
        display_layout.addWidget(self.history_label)

        # Main input display - black background, white text, no border, expanded
        self.display = QLineEdit()
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setFont(QFont(FONT, 36, QFont.Weight.Bold))
        self.display.setReadOnly(True)
        self.display.setMinimumHeight(80)
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.display.setSizePolicy(size_policy)
        self.display.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D2D;
                border: none;
                border-radius: 4px;
                color: #ffffff;
                padding: 15px;
            }
        """)
        display_layout.addWidget(self.display)

        # Error log panel (below display)
        self.error_log = QLabel("")
        self.error_log.setFont(QFont(FONT, 11))
        self.error_log.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                background-color: #2d1f1f;
                border: 1px solid #ff6b6b;
                border-radius: 4px;
                padding: 8px;
                min-height: 20px;
            }
        """)
        self.error_log.setWordWrap(True)
        self.error_log.hide()  # Hidden by default
        display_layout.addWidget(self.error_log)

        parent_layout.addWidget(display_frame)

    def _show_error(self, message: str):
        """Display error in the log panel instead of the display."""
        logger.error(f"Calculator error: {message}")
        self.error_log.setText(f"⚠️ {message}")
        self.error_log.show()

    def _clear_error(self):
        """Clear the error log."""
        self.error_log.clear()
        self.error_log.hide()

    def _setup_standard_buttons(self, parent_layout):
        """Setup the standard calculator button grid (basic operations only)."""
        buttons_frame = QFrame()
        buttons_layout = QGridLayout(buttons_frame)
        buttons_layout.setSpacing(8)

        # Standard button definitions: (text, row, col, style, callback)
        button_defs = [
            # Row 0: Clear and backspace
            ('C', 0, 0, 'clear', self._on_clear),
            ('⌫', 0, 1, 'clear', self._on_backspace),
            ('%', 0, 2, 'function', self._on_percent),
            ('÷', 0, 3, 'operator', lambda: self._on_operator('/')),

            # Row 1: Numbers
            ('7', 1, 0, 'number', lambda: self._on_number('7')),
            ('8', 1, 1, 'number', lambda: self._on_number('8')),
            ('9', 1, 2, 'number', lambda: self._on_number('9')),
            ('×', 1, 3, 'operator', lambda: self._on_operator('*')),

            # Row 2
            ('4', 2, 0, 'number', lambda: self._on_number('4')),
            ('5', 2, 1, 'number', lambda: self._on_number('5')),
            ('6', 2, 2, 'number', lambda: self._on_number('6')),
            ('-', 2, 3, 'operator', lambda: self._on_operator('-')),

            # Row 3
            ('1', 3, 0, 'number', lambda: self._on_number('1')),
            ('2', 3, 1, 'number', lambda: self._on_number('2')),
            ('3', 3, 2, 'number', lambda: self._on_number('3')),
            ('+', 3, 3, 'operator', lambda: self._on_operator('+')),

            # Row 4
            ('00', 4, 0, 'number', lambda: self._on_number('00')),
            ('0', 4, 1, 'number', lambda: self._on_number('0')),
            ('.', 4, 2, 'number', lambda: self._on_number('.')),
            ('=', 4, 3, 'equals', self._on_equals),
        ]

        # Store buttons for styling
        self.buttons = {}

        for text, row, col, style, callback in button_defs:
            btn = QPushButton(text)
            btn.setFixedHeight(60)
            btn.setFont(QFont(FONT, 16))
            btn.clicked.connect(callback)
            self.buttons[text] = btn
            buttons_layout.addWidget(btn, row, col)

        parent_layout.addWidget(buttons_frame, stretch=1)

    def _setup_scientific_buttons(self, parent_layout):
        """Setup the scientific calculator button grid (advanced functions)."""
        buttons_frame = QFrame()
        buttons_layout = QGridLayout(buttons_frame)
        buttons_layout.setSpacing(8)

        # Deg/Rad toggle button
        self.deg_rad_btn = QPushButton("DEG")
        self.deg_rad_btn.setFixedHeight(40)
        self.deg_rad_btn.setFont(QFont(FONT, 11, QFont.Weight.Bold))
        self.deg_rad_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9500;
                color: #ffffff;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ffb143;
            }
        """)
        self.deg_rad_btn.clicked.connect(self._toggle_deg_rad)
        buttons_layout.addWidget(self.deg_rad_btn, 0, 0)

        # Trig button that opens floating overlay
        self.trig_btn = QPushButton("Trig")
        self.trig_btn.setFixedHeight(55)
        self.trig_btn.setFont(QFont(FONT, 14))
        self.trig_btn.clicked.connect(self._show_trig_overlay)
        buttons_layout.addWidget(self.trig_btn, 0, 1)

        # Create trig overlay (hidden by default, floats above)
        self.trig_overlay = TrigOverlay(self)
        self.trig_overlay.func_selected.connect(self._apply_trig_function)

        # Scientific button definitions: (text, row, col, style, callback)
        # 6-column grid (0-5): cols 0-1 = scientific, cols 2-4 = numbers/funcs, col 5 = operators
        button_defs = [
            # Row 0: C(2), ⌫(3), %(4), ÷(5)
            ('C', 0, 2, 'clear', self._on_clear),
            ('⌫', 0, 3, 'clear', self._on_backspace),
            ('%', 0, 4, 'function', self._on_percent),
            ('÷', 0, 5, 'operator', lambda: self._on_operator('/')),

            # Row 1: √(0), x²(1), 7(2), 8(3), 9(4), ×(5)
            ('√', 1, 0, 'function', self._on_sqrt),
            ('x²', 1, 1, 'function', self._on_square),
            ('7', 1, 2, 'number', lambda: self._on_number('7')),
            ('8', 1, 3, 'number', lambda: self._on_number('8')),
            ('9', 1, 4, 'number', lambda: self._on_number('9')),
            ('×', 1, 5, 'operator', lambda: self._on_operator('*')),

            # Row 2: π(0), ^(1), 4(2), 5(3), 6(4), -(5)
            ('π', 2, 0, 'constant', self._on_pi),
            ('^', 2, 1, 'function', lambda: self._on_operator('^')),
            ('4', 2, 2, 'number', lambda: self._on_number('4')),
            ('5', 2, 3, 'number', lambda: self._on_number('5')),
            ('6', 2, 4, 'number', lambda: self._on_number('6')),
            ('-', 2, 5, 'operator', lambda: self._on_operator('-')),

            # Row 3: e(0), !(1), 1(2), 2(3), 3(4), +(5)
            ('e', 3, 0, 'constant', self._on_euler),
            ('!', 3, 1, 'function', self._on_factorial),
            ('1', 3, 2, 'number', lambda: self._on_number('1')),
            ('2', 3, 3, 'number', lambda: self._on_number('2')),
            ('3', 3, 4, 'number', lambda: self._on_number('3')),
            ('+', 3, 5, 'operator', lambda: self._on_operator('+')),

            # Row 4: ln(0), log(1), 00(2), 0(3), .(4), =(5)
            ('ln', 4, 0, 'function', self._on_ln),
            ('log', 4, 1, 'function', self._on_log10),
            ('00', 4, 2, 'number', lambda: self._on_number('00')),
            ('0', 4, 3, 'number', lambda: self._on_number('0')),
            ('.', 4, 4, 'number', lambda: self._on_number('.')),
            ('=', 4, 5, 'equals', self._on_equals),
        ]

        # Store buttons for styling
        self.buttons = {}

        for text, row, col, style, callback in button_defs:
            btn = QPushButton(text)
            btn.setFixedHeight(55)
            btn.setFont(QFont(FONT, 14))
            btn.clicked.connect(callback)
            self.buttons[text] = btn
            buttons_layout.addWidget(btn, row, col)

        parent_layout.addWidget(buttons_frame, stretch=1)

    def _setup_history(self, parent_layout):
        """Setup the history panel."""
        history_frame = QFrame()
        history_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid #3d3d3d;
            }
        """)
        history_layout = QVBoxLayout(history_frame)
        history_layout.setContentsMargins(10, 10, 10, 10)

        # History header
        header_layout = QHBoxLayout()
        history_title = QLabel("History")
        history_title.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        history_title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(history_title)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888888;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #ff6b6b;
            }
        """)
        clear_btn.clicked.connect(self._clear_history)
        header_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        history_layout.addLayout(header_layout)

        # History scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 4px;
            }
        """)

        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_layout.setSpacing(8)
        self.history_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self.history_container)
        history_layout.addWidget(scroll)

        parent_layout.addWidget(history_frame, stretch=1)

    def _apply_styles(self):
        """Apply styles to buttons."""
        styles = {
            'number': """
                QPushButton {
                    background-color: #4a4a4a;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
                QPushButton:pressed {
                    background-color: #6a6a6a;
                }
            """,
            'operator': """
                QPushButton {
                    background-color: #ff9500;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #ffb143;
                }
                QPushButton:pressed {
                    background-color: #e68600;
                }
            """,
            'function': """
                QPushButton {
                    background-color: #3a3a3a;
                    color: #a0a0a0;
                    border: none;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #5a5a5a;
                }
            """,
            'clear': """
                QPushButton {
                    background-color: #ff6b6b;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #ff8585;
                }
                QPushButton:pressed {
                    background-color: #e55c5c;
                }
            """,
            'constant': """
                QPushButton {
                    background-color: #3a3a3a;
                    color: #66b3ff;
                    border: none;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #5a5a5a;
                }
            """,
            'equals': """
                QPushButton {
                    background-color: #4cd964;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #6ee284;
                }
                QPushButton:pressed {
                    background-color: #3cb853;
                }
            """,
        }

        button_styles = {
            'number': ['7', '8', '9', '4', '5', '6', '1', '2', '3', '0', '00', '.'],
            'operator': ['÷', '×', '-', '+', '^'],
            'function': ['%', '√', 'x²', 'ln', '(', ')', 'Sci'],
            'clear': ['C', '⌫'],
            'constant': ['π', 'e'],
            'equals': ['=', '!'],
        }

        for style_name, buttons in button_styles.items():
            for btn_text in buttons:
                if btn_text in self.buttons:
                    self.buttons[btn_text].setStyleSheet(styles[style_name])

    # Button handlers
    def _on_number(self, num: str):
        current = self.display.text()

        # If we just calculated and start typing a new number, clear the display
        if self._just_calculated:
            self.display.setText(num)
            self._just_calculated = False
            return

        # Prevent multiple decimals in the same number
        if num == '.':
            # Find the last operator position
            last_op = -1
            for op in '+-×÷^()':
                pos = current.rfind(op)
                if pos > last_op:
                    last_op = pos
            # Check if there's a decimal in the current number segment
            if '.' in current[last_op + 1:]:
                return
        self.display.setText(current + num)

    def _on_operator(self, op: str):
        current = self.display.text()

        # If we just calculated, allow chaining with the result
        if self._just_calculated:
            self._just_calculated = False
            # Continue with current result

        # Handle empty input
        if not current:
            if op == '-':
                self.display.setText(op)
            return

        last_char = current[-1] if current else ''
        operators = '+-×÷^'

        # Replace last operator if another is pressed
        if last_char in operators and op in operators:
            self.display.setText(current[:-1] + op)
        else:
            self.display.setText(current + op)

    def _on_clear(self):
        self.display.clear()
        self.history_label.clear()
        self._clear_error()
        # Reset repeat calculation state
        self._just_calculated = False
        self._last_operator = None
        self._last_right_operand = None
        self._last_result = None

    def _on_backspace(self):
        current = self.display.text()
        if current:
            self.display.setText(current[:-1])

    def _on_equals(self):
        expression = self.display.text()
        if not expression:
            return

        self._clear_error()

        # Check if we should repeat the last operation
        if self._just_calculated and self._last_operator and self._last_right_operand is not None:
            # Repeat operation: result [op] right_operand
            repeat_expr = f"{self._last_result} {self._last_operator} {self._last_right_operand}"
            try:
                result = self.engine.calculate(repeat_expr)
                # Show actual result value instead of "Ans"
                display_text = f"{self._last_result} {self._last_operator} {self._last_right_operand} ="
                self.history_label.setText(display_text)
                self.display.setText(result)
                self._add_history_entry(display_text.rstrip(' ='), result)
                self._last_result = result
            except CalculationError as e:
                self._show_error(str(e))
            return

        # Normal calculation - try to parse and save for repeat
        try:
            result = self.engine.calculate(expression)
            self.history_label.setText(f"{expression} =")
            self.display.setText(result)
            self._add_history_entry(expression, result)

            # Parse and save the operation for potential repeat
            self._parse_and_save_operation(expression, result)
            self._just_calculated = True

        except CalculationError as e:
            self._show_error(str(e))

    def _parse_and_save_operation(self, expression: str, result: str):
        """Parse expression to extract left, operator, right for repeat functionality."""
        # Normalize operators
        expr = expression.replace('×', '*').replace('÷', '/')

        # Match pattern: number operator number (simple binary operation)
        # Support integers, decimals, and scientific notation
        pattern = r'^([\d.]+[eE]?[+-]?\d*)\s*([+\-*/^])\s*([\d.]+[eE]?[+-]?\d*)$'
        match = re.match(pattern, expr)

        if match:
            self._last_left_operand = match.group(1)
            self._last_operator = match.group(2).replace('*', '×').replace('/', '÷')
            self._last_right_operand = match.group(3)
            self._last_result = result
        else:
            # Complex expression - can't repeat, but still mark as calculated
            self._last_operator = None
            self._last_right_operand = None
            self._last_result = result

    def _on_sqrt(self):
        self._apply_unary_operation('√', lambda x: self.engine.sqrt(x))

    def _on_square(self):
        current = self.display.text()
        self.display.setText(current + '²')

    def _toggle_deg_rad(self):
        """Toggle between degrees and radians mode."""
        self.is_degrees = not self.is_degrees
        self.deg_rad_btn.setText("DEG" if self.is_degrees else "RAD")

    def _show_trig_overlay(self):
        """Show the trig function overlay."""
        self.trig_overlay.show_at(self.trig_btn)

    # Trig function mapping as class attribute to reduce method complexity
    _TRIG_FUNCTIONS = {
        'sin': lambda x: math.sin(x),
        'cos': lambda x: math.cos(x),
        'tan': lambda x: math.tan(x) if abs(math.cos(x)) > 1e-15 else float('inf'),
        'csc': lambda x: 1/math.sin(x) if abs(math.sin(x)) > 1e-15 else float('inf'),
        'sec': lambda x: 1/math.cos(x) if abs(math.cos(x)) > 1e-15 else float('inf'),
        'cot': lambda x: 1/math.tan(x) if abs(math.tan(x)) > 1e-15 else float('inf'),
        'sin⁻¹': lambda x: math.asin(x) if -1 <= x <= 1 else float('nan'),
        'cos⁻¹': lambda x: math.acos(x) if -1 <= x <= 1 else float('nan'),
        'tan⁻¹': lambda x: math.atan(x),
        'csc⁻¹': lambda x: math.asin(1/x) if abs(x) >= 1 else float('nan'),
        'sec⁻¹': lambda x: math.acos(1/x) if abs(x) >= 1 else float('nan'),
        'cot⁻¹': lambda x: math.atan(1/x) if x != 0 else float('nan'),
    }

    def _get_angle_for_calc(self, value):
        """Convert value to radians if in degrees mode."""
        return math.radians(value) if self.is_degrees else value

    def _post_process_trig_result(self, result, func_name):
        """Validate result and convert to degrees for inverse trig if needed."""
        if math.isnan(result):
            raise CalculationError("Invalid input for inverse trig function")
        if math.isinf(result):
            raise CalculationError(f"{func_name} undefined at this value")
        if '⁻¹' in func_name and self.is_degrees:
            return math.degrees(result)
        return result

    def _apply_trig_function(self, func_name):
        """Apply the selected trig function."""
        current = self.display.text()
        if not current:
            return

        self._clear_error()
        try:
            value = self._parse_display_value(current)
            angle_rad = self._get_angle_for_calc(value)
            result = self._TRIG_FUNCTIONS[func_name](angle_rad)
            result = self._post_process_trig_result(result, func_name)

            formatted = self.engine.format_result(result)
            self.history_label.setText(f"{func_name}({current}) =")
            self.display.setText(formatted)
            self._add_history_entry(f"{func_name}({current})", formatted)
        except CalculationError as e:
            self._show_error(str(e))
        except Exception as e:
            self._show_error(f"Error in {func_name}: {str(e)}")

    def _parse_display_value(self, current):
        """Parse the display value, trying engine calculation first."""
        try:
            return float(self.engine.calculate(current))
        except Exception:
            return float(current)

    def _on_ln(self):
        self._apply_unary_operation('ln', lambda x: self.engine.ln(x))

    def _on_log10(self):
        self._apply_unary_operation('log', lambda x: self.engine.log10(x))

    def _on_sin(self):
        self._apply_unary_operation('sin', lambda x: self.engine.sin(x))

    def _on_cos(self):
        self._apply_unary_operation('cos', lambda x: self.engine.cos(x))

    def _on_tan(self):
        self._apply_unary_operation('tan', lambda x: self.engine.tan(x))

    def _on_factorial(self):
        self._apply_unary_operation('!', lambda x: self.engine.factorial(x))

    def _on_percent(self):
        current = self.display.text()
        self.display.setText(current + '%')

    def _on_pi(self):
        self.display.setText(self.display.text() + 'π')

    def _on_euler(self):
        self.display.setText(self.display.text() + 'e')

    def _on_scientific(self):
        """Convert current value to scientific notation."""
        current = self.display.text()
        if not current:
            return

        self._clear_error()
        try:
            # Try to parse as number first
            value = float(current)
            result = self.engine.to_scientific(value)
            self.history_label.setText(f"Sci({current}) =")
            self.display.setText(result)
            self._add_history_entry(f"Sci({current})", result)
        except ValueError:
            # Try to evaluate as expression
            try:
                result = self.engine.calculate(current)
                value = float(result)
                sci_result = self.engine.to_scientific(value)
                self.history_label.setText(f"Sci({current}) =")
                self.display.setText(sci_result)
                self._add_history_entry(f"Sci({current})", sci_result)
            except Exception as e:
                self._show_error(f"Scientific conversion failed: {str(e)}")

    def _apply_unary_operation(self, op_name: str, operation):
        """Apply a unary operation to the current value."""
        current = self.display.text()
        if not current:
            return

        self._clear_error()
        try:
            # Try to evaluate current expression first
            try:
                value = float(self.engine.calculate(current))
            except (ValueError, TypeError):
                value = float(current)

            result = operation(value)
            formatted = self.engine.format_result(result)

            self.history_label.setText(f"{op_name}({current}) =")
            self.display.setText(formatted)
            self._add_history_entry(f"{op_name}({current})", formatted)
        except Exception as e:
            self._show_error(str(e))

    def _add_history_entry(self, expression: str, result: str):
        """Add an entry to the history panel."""
        entry = HistoryEntry(expression, result)
        entry.clicked.connect(self._on_history_clicked)
        self.history_layout.insertWidget(0, entry)

    def _on_history_clicked(self, expression: str, result: str):
        """Handle clicking a history entry."""
        self.history_label.setText(expression)
        self.display.setText(result)

    def _clear_history(self):
        """Clear the history panel."""
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.engine.clear_history()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard input. Restricted by calculator mode."""
        key = event.key()
        text = event.text()

        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._on_equals()
        elif key == Qt.Key.Key_Backspace:
            self._on_backspace()
        elif key == Qt.Key.Key_Escape:
            self._on_clear()
        elif text.isdigit() or text in '.+-*/^()%':
            # Standard mode allowed: digits, decimal, basic operators, percent
            self.display.setText(self.display.text() + text)
        elif self.mode == "scientific" and text in '!':
            # Scientific mode extras: power, parentheses, factorial
            self.display.setText(self.display.text() + text)
        elif text == '*':
            self.display.setText(self.display.text() + '×')
        elif text == '/':
            self.display.setText(self.display.text() + '÷')
        else:
            super().keyPressEvent(event)
