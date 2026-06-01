"""
Calculator Tab - The main calculator interface using PyQt6.
Simple QLineEdit with custom styling (no MathQuill).
"""

import logging
import math
import re

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QLabel, QScrollArea,
    QFrame, QSizePolicy, QTabWidget
)

from calculator_engine import CalculationError, get_engine
from constants_calculator import FONT, OPERATORS, LABEL_STYLESHEET

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

        # Create frame for content with border
        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #4a4a4a;
                border: 1px solid #5a5a5a;
            }
        """)
        frame_layout = QVBoxLayout(content_frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)
        frame_layout.setSpacing(2)

        self.expr_label = QLabel(f"{self.expression} =")
        self.expr_label.setStyleSheet("color: #888888; font-size: 12px; border: none; background: transparent;")

        self.result_label = QLabel(self.result)
        self.result_label.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: bold; border: none; background: transparent;")

        frame_layout.addWidget(self.expr_label)
        frame_layout.addWidget(self.result_label)

        layout.addWidget(content_frame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(self.expression, self.result)


class _HistoryOverlayFrame(QFrame):
    """Overlay frame that emits signal when clicked (outside panel)."""
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panel = None

    def set_panel(self, panel):
        """Store reference to the panel widget."""
        self._panel = panel

    def mousePressEvent(self, event):
        """Close when clicking outside the panel."""
        # Get the widget at click position
        child = self.childAt(event.pos())

        # If clicked on empty space (no child) or directly on overlay background
        if child is None or child == self:
            self.close_requested.emit()
            return

        super().mousePressEvent(event)


# noinspection PyUnresolvedReferences
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
        # Memory storage for scientific mode
        self._memory_value = 0.0
        self._setup_ui()
        self._apply_styles()
        # Ensure this widget can receive keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def _setup_ui(self):
        # Threshold for history panel collapse
        self._history_collapse_threshold = 900
        self._history_overlay = None
        self._history_button = None
        self._history_panel_visible = True

        # Main layout
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(10, 10, 10, 10)
        self._main_layout.setSpacing(10)

        # Left side: Calculator
        calc_widget = QWidget()
        calc_layout = QVBoxLayout(calc_widget)
        calc_layout.setContentsMargins(0, 0, 0, 0)
        calc_layout.setSpacing(10)

        # Display area (now includes history button)
        self._setup_display(calc_layout)

        # Button grid (different for standard vs scientific)
        if self.mode == "scientific":
            self._setup_scientific_buttons(calc_layout)
        else:
            self._setup_standard_buttons(calc_layout)

        self._main_layout.addWidget(calc_widget, stretch=2)

        # Right side: History panel
        self._setup_history(self._main_layout)

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

        # Memory indicator row (for scientific mode)
        memory_row = QWidget()
        memory_layout = QHBoxLayout(memory_row)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        memory_layout.setSpacing(10)

        self.memory_indicator = QLabel("M")
        self.memory_indicator.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        self.memory_indicator.setStyleSheet("color: #ff9500; background: transparent; padding: 2px 8px;")
        self.memory_indicator.setToolTip("Memory is not empty")
        self.memory_indicator.hide()  # Hidden by default when memory is 0
        memory_layout.addWidget(self.memory_indicator)

        memory_layout.addStretch()
        display_layout.addWidget(memory_row)

        # Main input display - black background, white text, no border, expanded
        self.display = QLineEdit()
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setFont(QFont(FONT, 36, QFont.Weight.Bold))
        self.display.setReadOnly(True)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Don't steal focus
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

        # Connect display text changes to preview update
        self.display.textChanged.connect(self._update_preview)

        # Live preview label (shows calculation result as you type)
        self.preview_label = QLabel("")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.preview_label.setFont(QFont(FONT, 18))
        self.preview_label.setStyleSheet(LABEL_STYLESHEET)
        display_layout.addWidget(self.preview_label)

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

        # History expression label row with history button (shown when panel collapsed)
        history_header_row = QHBoxLayout()

        self._history_button = QPushButton("🕒")
        self._history_button.setFont(QFont(FONT, 11))
        self._history_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ff9500;
                border: 1px solid #ff9500;
                border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #ff9500;
                color: #ffffff;
            }
        """)
        self._history_button.clicked.connect(self._show_history_overlay)
        self._history_button.hide()  # Hidden by default (shown when panel collapsed)
        history_header_row.addWidget(self._history_button)

        history_header_row.addStretch()
        display_layout.insertLayout(0, history_header_row)

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

    def _update_preview(self):
        """Update the live preview label with calculation result or warnings."""
        expression = self.display.text()
        if not expression:
            self.preview_label.clear()
            self.preview_label.setStyleSheet(LABEL_STYLESHEET)
            return

        # Don't preview if expression is just a single number or empty
        if not any(op in expression for op in OPERATORS) and not any(
                func in expression for func in ['√', 'ln', 'log', '!']):
            self.preview_label.clear()
            return

        # Check feasibility on ORIGINAL expression (before normalization)
        # Users type scientific notation like 1e+1000, not SCINUM markers
        try:
            is_feasible, reason = self.engine._check_computation_feasibility(expression)
            if not is_feasible:
                # Show warning in preview box
                self.preview_label.setStyleSheet("""
                    QLabel {
                        color: #ff9500;
                        background: transparent;
                        padding: 5px 15px;
                        min-height: 28px;
                    }
                """)
                self.preview_label.setText(f"⚠️ {reason}")
                return
        except Exception:
            # If feasibility check fails, continue to try calculation
            pass

        # Reset style and try to calculate
        self.preview_label.setStyleSheet(LABEL_STYLESHEET)

        try:
            result = self.engine.calculate(expression)
            formatted = self.engine.format_result(result)
            self.preview_label.setText(f"= {formatted}")
        except Exception:
            # Don't show preview for invalid expressions
            self.preview_label.clear()

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
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setFont(QFont(FONT, 16))
            btn.clicked.connect(callback)
            self.buttons[text] = btn
            buttons_layout.addWidget(btn, row, col)

        # Make rows and columns stretch equally
        for i in range(5):  # 5 rows
            buttons_layout.setRowStretch(i, 1)
        for i in range(4):  # 4 columns
            buttons_layout.setColumnStretch(i, 1)

        parent_layout.addWidget(buttons_frame, stretch=1)

        # Trigger initial font sizing after layout is complete
        QTimer.singleShot(100, self._update_button_fonts)

    def _setup_scientific_buttons(self, parent_layout):
        """Setup the scientific calculator button grid (advanced functions)."""
        buttons_frame = QFrame()
        buttons_layout = QGridLayout(buttons_frame)
        buttons_layout.setSpacing(8)

        # Memory buttons row (MC, MR, M+, M-, MS)
        memory_buttons = [
            ('MC', self._on_memory_clear),
            ('MR', self._on_memory_recall),
            ('M+', self._on_memory_add),
            ('M-', self._on_memory_subtract),
            ('MS', self._on_memory_store),
        ]

        # Store scientific-specific buttons for font updating
        self._scientific_buttons = []

        for idx, (text, callback) in enumerate(memory_buttons):
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setFont(QFont(FONT, 16, QFont.Weight.Bold))
            self._scientific_buttons.append(btn)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    color: #ff9500;
                    border: 1px solid #ff9500;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                }
                QPushButton:pressed {
                    background-color: #ff9500;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(callback)
            buttons_layout.addWidget(btn, 0, idx)

        # Deg/Rad toggle button
        self.deg_rad_btn = QPushButton("DEG")
        self.deg_rad_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.deg_rad_btn.setFont(QFont(FONT, 17, QFont.Weight.Bold))
        self._scientific_buttons.append(self.deg_rad_btn)
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
        buttons_layout.addWidget(self.deg_rad_btn, 1, 0)

        # Trig button that opens floating overlay
        self.trig_btn = QPushButton("Trig")
        self.trig_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.trig_btn.setFont(QFont(FONT, 17))
        self.trig_btn.clicked.connect(self._show_trig_overlay)
        buttons_layout.addWidget(self.trig_btn, 1, 1)
        self._scientific_buttons.append(self.trig_btn)

        # Create trig overlay (hidden by default, floats above)
        self.trig_overlay = TrigOverlay(self)
        self.trig_overlay.func_selected.connect(self._apply_trig_function)

        # Scientific button definitions: (text, row, col, style, callback)
        # 6-column grid (0-5): cols 0-1 = scientific, cols 2-4 = numbers/funcs, col 5 = operators
        # Row 0 is memory buttons, so main buttons start at row 1
        button_defs = [
            # Row 1: C(2), ⌫(3), %(4), ÷(5)
            ('C', 1, 2, 'clear', self._on_clear),
            ('⌫', 1, 3, 'clear', self._on_backspace),
            ('%', 1, 4, 'function', self._on_percent),
            ('÷', 1, 5, 'operator', lambda: self._on_operator('/')),

            # Row 2: √(0), x²(1), 7(2), 8(3), 9(4), ×(5)
            ('√', 2, 0, 'function', self._on_sqrt),
            ('x²', 2, 1, 'function', self._on_square),
            ('7', 2, 2, 'number', lambda: self._on_number('7')),
            ('8', 2, 3, 'number', lambda: self._on_number('8')),
            ('9', 2, 4, 'number', lambda: self._on_number('9')),
            ('×', 2, 5, 'operator', lambda: self._on_operator('*')),

            # Row 3: π(0), ^(1), 4(2), 5(3), 6(4), -(5)
            ('π', 3, 0, 'constant', self._on_pi),
            ('^', 3, 1, 'function', lambda: self._on_operator('^')),
            ('4', 3, 2, 'number', lambda: self._on_number('4')),
            ('5', 3, 3, 'number', lambda: self._on_number('5')),
            ('6', 3, 4, 'number', lambda: self._on_number('6')),
            ('-', 3, 5, 'operator', lambda: self._on_operator('-')),

            # Row 4: e(0), !(1), 1(2), 2(3), 3(4), +(5)
            ('e', 4, 0, 'constant', self._on_euler),
            ('!', 4, 1, 'function', self._on_factorial),
            ('1', 4, 2, 'number', lambda: self._on_number('1')),
            ('2', 4, 3, 'number', lambda: self._on_number('2')),
            ('3', 4, 4, 'number', lambda: self._on_number('3')),
            ('+', 4, 5, 'operator', lambda: self._on_operator('+')),

            # Row 5: ln(0), log(1), 00(2), 0(3), .(4), =(5)
            ('ln', 5, 0, 'function', self._on_ln),
            ('log', 5, 1, 'function', self._on_log10),
            ('00', 5, 2, 'number', lambda: self._on_number('00')),
            ('0', 5, 3, 'number', lambda: self._on_number('0')),
            ('.', 5, 4, 'number', lambda: self._on_number('.')),
            ('=', 5, 5, 'equals', self._on_equals),
        ]

        # Store buttons for styling
        self.buttons = {}

        for text, row, col, style, callback in button_defs:
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setFont(QFont(FONT, 18))
            btn.clicked.connect(callback)
            self.buttons[text] = btn
            buttons_layout.addWidget(btn, row, col)
            self._scientific_buttons.append(btn)

        # Make rows and columns stretch equally
        for i in range(6):  # 6 rows (0-5)
            buttons_layout.setRowStretch(i, 1)
        for i in range(6):  # 6 columns (0-5)
            buttons_layout.setColumnStretch(i, 1)

        parent_layout.addWidget(buttons_frame, stretch=1)

        # Trigger initial font sizing after layout is complete
        QTimer.singleShot(100, self._update_button_fonts)

    def _setup_history(self, parent_layout):
        """Setup the history panel."""
        self._history_frame = QFrame()
        self._history_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid #3d3d3d;
            }
        """)
        history_layout = QVBoxLayout(self._history_frame)
        history_layout.setContentsMargins(10, 10, 10, 10)

        # History header
        header_layout = QHBoxLayout()
        title_frame = QFrame()
        title_frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        history_title = QLabel("History")
        history_title.setObjectName("historyTitle")
        history_title.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        title_layout.addWidget(history_title)
        header_layout.addWidget(title_frame)

        clear_btn = QPushButton("\U0001F5D1")  # Wastebasket Unicode
        clear_btn.setFixedSize(36, 36)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888888;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
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
                border: 2px solid #3d3d3d;
                border-radius: 6px;
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

        parent_layout.addWidget(self._history_frame, stretch=1)

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

        # Set application-wide styles for history titles and entries
        self.setStyleSheet(self.styleSheet() + """
            QLabel#historyTitle {
                color: #ff9500;
                font-weight: bold;
                padding: 2px 6px;
                background-color: transparent;
                border: none;
            }
            QLabel#historyTitleOverlay {
                color: #ff9500;
                font-weight: bold;
                font-size: 18px;
                padding: 4px 8px;
                background-color: transparent;
                border: none;
            }
        """)

    # Button handlers
    def _on_number(self, num: str):
        current = self.display.text()

        # If we just calculated and start typing a new number, clear the display
        if self._just_calculated:
            self.display.setText(num)
            self._just_calculated = False
            self.setFocus()
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
                self.setFocus()
                return
        self.display.setText(current + num)
        self.setFocus()

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
            self.setFocus()
            return

        last_char = current[-1] if current else ''

        # Replace last operator if another is pressed
        if last_char in OPERATORS and op in OPERATORS:
            self.display.setText(current[:-1] + op)
        else:
            self.display.setText(current + op)
        self.setFocus()

    def _on_clear(self):
        self.display.clear()
        self.history_label.clear()
        self.preview_label.clear()
        self._clear_error()
        # Reset repeat calculation state
        self._just_calculated = False
        self._last_operator = None
        self._last_right_operand = None
        self.setFocus()
        self._last_result = None

    # Memory button handlers
    def _on_memory_clear(self):
        """Clear memory (MC)."""
        self._memory_value = 0.0
        self.memory_indicator.hide()

    def _on_memory_recall(self):
        """Recall memory to display (MR)."""
        self._clear_error()
        # Clear display if we just calculated
        if self._just_calculated:
            self.display.clear()
            self._just_calculated = False
        # Format memory value appropriately
        if self._memory_value == int(self._memory_value):
            display_val = str(int(self._memory_value))
        else:
            display_val = str(self._memory_value)
        self.display.setText(display_val)

    def _on_memory_store(self):
        """Store display value to memory (MS)."""
        try:
            current = self.display.text()
            if current:
                value = float(self.engine.calculate(current) if any(op in current for op in OPERATORS) else current)
                self._memory_value = value
                self.memory_indicator.show()
        except ValueError:
            pass  # Don't store invalid values

    def _on_memory_add(self):
        """Add display value to memory (M+)."""
        try:
            current = self.display.text()
            if current:
                value = float(self.engine.calculate(current) if any(op in current for op in OPERATORS) else current)
                self._memory_value += value
                self.memory_indicator.show()
        except ValueError:
            pass

    def _on_memory_subtract(self):
        """Subtract display value from memory (M-)."""
        try:
            current = self.display.text()
            if current:
                value = float(self.engine.calculate(current) if any(op in current for op in OPERATORS) else current)
                self._memory_value -= value
                self.memory_indicator.show()
        except ValueError:
            pass

    def _on_backspace(self):
        current = self.display.text()
        if current:
            self.display.setText(current[:-1])
        # Ensure focus stays with calculator for keyboard input
        self.setFocus()

    def _animate_result_slide(self, expression: str, result: str):
        """Animate the result sliding up to history with the expression."""
        # Create fade-out animation for preview
        self.preview_label.setStyleSheet("""
            QLabel {
                color: #ff9500;
                background: transparent;
                padding: 5px 15px;
                min-height: 28px;
                font-weight: bold;
            }
        """)
        self.history_label.setText(f"{expression} =")

        # Set the result in display
        self.display.setText(result)
        self.preview_label.clear()
        self.preview_label.setStyleSheet(LABEL_STYLESHEET)

        self._add_history_entry(expression, result)

    def _on_equals(self):
        expression = self.display.text()
        if not expression:
            return

        self._clear_error()

        # Check if we should repeat the last operation
        # Only repeat if user pressed = without typing anything new (expression equals last result)
        is_repeat_press = (self._just_calculated and
                           self._last_operator and
                           self._last_right_operand is not None and
                           expression == self._last_result)

        if is_repeat_press:
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

            # Animate the transition
            self._animate_result_slide(expression, result)

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
        # Support integers, decimals, and scientific notation (e.g., 1e10, 1.5e-5, 8.333e-12)
        # Scientific notation: optional digits/decimals, optional e/E with optional sign and digits
        number_pattern = r'[\d.]+(?:[eE][+-]?\d+)?'
        pattern = rf'^({number_pattern})\s*([+\-*/^])\s*({number_pattern})$'
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
        'csc': lambda x: 1 / math.sin(x) if abs(math.sin(x)) > 1e-15 else float('inf'),
        'sec': lambda x: 1 / math.cos(x) if abs(math.cos(x)) > 1e-15 else float('inf'),
        'cot': lambda x: 1 / math.tan(x) if abs(math.tan(x)) > 1e-15 else float('inf'),
        'sin⁻¹': lambda x: math.asin(x) if -1 <= x <= 1 else float('nan'),
        'cos⁻¹': lambda x: math.acos(x) if -1 <= x <= 1 else float('nan'),
        'tan⁻¹': lambda x: math.atan(x),
        'csc⁻¹': lambda x: math.asin(1 / x) if abs(x) >= 1 else float('nan'),
        'sec⁻¹': lambda x: math.acos(1 / x) if abs(x) >= 1 else float('nan'),
        'cot⁻¹': lambda x: math.atan(1 / x) if x != 0 else float('nan'),
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

    def _clear_history_and_refresh_overlay(self):
        """Clear history and refresh overlay view immediately."""
        self._clear_history()
        # Refresh overlay scroll area if open
        if self._history_overlay and hasattr(self._history_overlay, '_scroll'):
            scroll = self._history_overlay._scroll
            if scroll and scroll.widget():
                # Clear the clone layout
                clone_widget = scroll.widget()
                clone_layout = clone_widget.layout()
                if clone_layout:
                    while clone_layout.count():
                        item = clone_layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()

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

    def resizeEvent(self, event):
        """Handle resize to collapse/expand history panel and update overlay."""
        super().resizeEvent(event)
        self._update_history_visibility()

        # Update button font sizes based on button dimensions
        self._update_button_fonts()

        # Update overlay geometry if it exists
        if self._history_overlay and self._history_overlay.isVisible():
            self._history_overlay.setGeometry(0, 0, self.width(), self.height())
            # Update panel size and position (full width at bottom)
            panel = getattr(self._history_overlay, '_panel', None)
            if panel:
                panel.setFixedWidth(self.width() - 40)
                panel.setFixedHeight(min(400, self.height() - 100))
                new_x = 20
                new_y = self.height() - panel.height()
                panel.move(new_x, new_y)

    def _update_button_fonts(self):
        """Update calculator button font sizes based on their dimensions."""
        if not self.buttons:
            return

        # Get a reference button to calculate font size
        sample_btn = next(iter(self.buttons.values()))
        btn_height = sample_btn.height()
        btn_width = sample_btn.width()

        # Check if button has been laid out (not returning parent size)
        # If height > 200, layout hasn't settled yet - retry later
        if btn_height > 200:
            QTimer.singleShot(50, self._update_button_fonts)
            return

        # Calculate font size - use average of dimensions for better scaling
        avg_dim = (btn_height + btn_width) / 2
        # Scale factor: ~18% of average dimension, clamped between 8 and 24
        font_size = max(8, min(24, int(avg_dim * 0.18)))

        # Update font for all buttons
        font = QFont(FONT, font_size)
        for btn in self.buttons.values():
            btn.setFont(font)

        # Also update scientific mode buttons if they exist
        if hasattr(self, '_scientific_buttons'):
            for btn in self._scientific_buttons:
                btn.setFont(font)

    def _update_history_visibility(self):
        """Show/hide history panel based on window width."""
        if not hasattr(self, '_history_frame') or not self._history_frame:
            return

        width = self.width()
        should_show_panel = width >= self._history_collapse_threshold

        if should_show_panel != self._history_panel_visible:
            self._history_panel_visible = should_show_panel

            if should_show_panel:
                # Show panel, hide button, close overlay
                self._history_frame.show()
                if self._history_button:
                    self._history_button.hide()
                self._close_history_overlay()
            else:
                # Hide panel, show button
                self._history_frame.hide()
                if self._history_button:
                    self._history_button.show()

    def _show_history_overlay(self):
        """Show history panel as bottom-up overlay."""
        if self._history_overlay:
            return  # Already open

        # Create overlay container with click-to-close behavior
        self._history_overlay = _HistoryOverlayFrame(self)
        self._history_overlay.setGeometry(0, 0, self.width(), self.height())
        self._history_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.6);
            }
        """)
        self._history_overlay.close_requested.connect(self._close_history_overlay)

        # Create history panel clone (child of overlay) - cover full width at bottom
        overlay_panel = QFrame(self._history_overlay)
        overlay_panel.setFixedWidth(self.width() - 40)
        overlay_panel.setFixedHeight(min(400, self.height() - 100))
        overlay_panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 12px 12px 0 0;
                border: 1px solid #3d3d3d;
                border-bottom: none;
            }
        """)

        # Position at bottom, full width
        panel_x = 20  # 20px margin on each side
        panel_y = self.height() - overlay_panel.height()
        overlay_panel.move(panel_x, self.height())  # Start off-screen

        # Setup panel layout
        panel_layout = QVBoxLayout(overlay_panel)
        panel_layout.setContentsMargins(15, 15, 15, 15)

        # Header with close button
        header_layout = QHBoxLayout()
        title_frame = QFrame()
        title_frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        history_title = QLabel("History")
        history_title.setObjectName("historyTitleOverlay")
        history_title.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        title_layout.addWidget(history_title)
        header_layout.addWidget(title_frame)

        # Trash clear button (left of close)
        clear_btn = QPushButton("\U0001F5D1")  # Wastebasket Unicode
        clear_btn.setFixedSize(36, 36)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888888;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        clear_btn.clicked.connect(self._clear_history_and_refresh_overlay)
        header_layout.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        close_btn.setFont(QFont(FONT, 12))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
        """)
        close_btn.clicked.connect(self._close_history_overlay)
        header_layout.addWidget(close_btn)

        panel_layout.addLayout(header_layout)

        # Scroll area with current history
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 2px solid #3d3d3d;
                border-radius: 6px;
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

        # Copy current history entries
        history_clone = QWidget()
        history_clone_layout = QVBoxLayout(history_clone)
        history_clone_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        history_clone_layout.setSpacing(8)
        history_clone_layout.setContentsMargins(0, 0, 0, 0)

        for i in range(self.history_layout.count()):
            item = self.history_layout.itemAt(i)
            if item and item.widget():
                entry = item.widget()
                if isinstance(entry, HistoryEntry):
                    cloned = HistoryEntry(entry.expression, entry.result)
                    cloned.clicked.connect(self._on_history_clicked)
                    history_clone_layout.addWidget(cloned)

        scroll.setWidget(history_clone)
        panel_layout.addWidget(scroll)

        # Show overlay
        self._history_overlay.show()

        # Animate panel sliding up
        self._panel_animation = QPropertyAnimation(overlay_panel, b"pos")
        self._panel_animation.setDuration(250)
        self._panel_animation.setStartValue(QPoint(panel_x, self.height()))
        self._panel_animation.setEndValue(QPoint(panel_x, panel_y))
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()

        # Store reference to overlay panel for updates and click detection
        self._history_overlay.set_panel(overlay_panel)
        self._history_overlay._scroll = scroll

    def _close_history_overlay(self):
        """Close the history overlay."""
        if not self._history_overlay:
            return

        # Get panel reference from overlay
        panel = self._history_overlay._panel if self._history_overlay else None

        if panel:
            # Animate down (store as instance variable to prevent garbage collection)
            self._close_anim = QPropertyAnimation(panel, b"pos")
            self._close_anim.setDuration(200)
            self._close_anim.setStartValue(panel.pos())
            self._close_anim.setEndValue(QPoint(panel.x(), self.height()))
            self._close_anim.setEasingCurve(QEasingCurve.Type.InCubic)
            self._close_anim.finished.connect(self._destroy_history_overlay)
            self._close_anim.start()
        else:
            self._destroy_history_overlay()

    def _destroy_history_overlay(self):
        """Destroy the history overlay."""
        if self._history_overlay:
            self._history_overlay.deleteLater()
            self._history_overlay = None
        # Clean up animation reference
        if hasattr(self, '_close_anim'):
            self._close_anim = None
