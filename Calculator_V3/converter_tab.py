"""
Converter Tab - Comprehensive unit conversion interface.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QComboBox,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from conversions import ConversionCategory, get_manager
from constants_calculator import FONT


class SingleConverter(QWidget):
    """A single conversion panel for one category."""

    def __init__(self, category: ConversionCategory, parent=None):
        super().__init__(parent)
        self.category = category
        self.manager = get_manager()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Display area with inputs and unit selectors
        display_frame = QFrame()
        display_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 12px;
                border: 1px solid #3d3d3d;
            }
        """)
        display_layout = QVBoxLayout(display_frame)
        display_layout.setContentsMargins(20, 20, 20, 20)
        display_layout.setSpacing(10)

        # Input section
        input_layout = QHBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setFont(QFont(FONT, 24, QFont.Weight.Bold))
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.input_field.setPlaceholderText("0")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                border: 2px solid #4a4a4a;
                border-radius: 8px;
                color: #ffffff;
                padding: 10px;
            }
            QLineEdit:focus {
                border-color: #ff9500;
            }
        """)
        self.input_field.textChanged.connect(self._on_input_changed)
        input_layout.addWidget(self.input_field, stretch=2)

        self.from_unit = QComboBox()
        self.from_unit.setFont(QFont(FONT, 12))
        self.from_unit.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                border: 2px solid #4a4a4a;
                border-radius: 8px;
                color: #ffffff;
                padding: 8px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: #ffffff;
                selection-background-color: #ff9500;
            }
        """)
        input_layout.addWidget(self.from_unit, stretch=1)

        display_layout.addLayout(input_layout)

        # Swap button in the middle
        swap_layout = QHBoxLayout()
        swap_layout.addStretch()

        self.swap_btn = QPushButton("⇅")
        self.swap_btn.setFont(QFont(FONT, 16))
        self.swap_btn.setFixedSize(50, 40)
        self.swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swap_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: #a0a0a0;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #ff9500;
                color: #ffffff;
            }
        """)
        self.swap_btn.clicked.connect(self._on_swap)
        swap_layout.addWidget(self.swap_btn)

        swap_layout.addStretch()
        display_layout.addLayout(swap_layout)

        # Output section
        output_layout = QHBoxLayout()

        self.output_field = QLineEdit()
        self.output_field.setFont(QFont(FONT, 24, QFont.Weight.Bold))
        self.output_field.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.output_field.setReadOnly(True)
        self.output_field.setPlaceholderText("0")
        self.output_field.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                border: 2px solid #4a4a4a;
                border-radius: 8px;
                color: #66b3ff;
                padding: 10px;
            }
        """)
        output_layout.addWidget(self.output_field, stretch=2)

        self.to_unit = QComboBox()
        self.to_unit.setFont(QFont(FONT, 12))
        self.to_unit.setStyleSheet(self.from_unit.styleSheet())
        output_layout.addWidget(self.to_unit, stretch=1)

        display_layout.addLayout(output_layout)

        layout.addWidget(display_frame)

        # Numpad
        self._setup_numpad(layout)

        # Populate unit dropdowns
        self._populate_units()

        # Connect unit changes
        self.from_unit.currentIndexChanged.connect(self._on_input_changed)
        self.to_unit.currentIndexChanged.connect(self._on_input_changed)

    def _setup_numpad(self, parent_layout):
        """Setup the numeric keypad."""
        numpad_frame = QFrame()
        numpad_layout = QGridLayout(numpad_frame)
        numpad_layout.setSpacing(8)

        buttons = [
            ('C', 0, 0), ('⌫', 0, 1), ('±', 0, 2),
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2),
            ('0', 4, 0), ('.', 4, 1), ('00', 4, 2),
        ]

        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setFixedHeight(55)
            btn.setFont(QFont(FONT, 14))

            if text == 'C':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ff6b6b;
                        color: #ffffff;
                        border: none;
                        border-radius: 8px;
                    }
                    QPushButton:hover {
                        background-color: #ff8585;
                    }
                """)
                btn.clicked.connect(self._on_clear)
            elif text == '⌫':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ff6b6b;
                        color: #ffffff;
                        border: none;
                        border-radius: 8px;
                    }
                    QPushButton:hover {
                        background-color: #ff8585;
                    }
                """)
                btn.clicked.connect(self._on_backspace)
            elif text == '±':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3a3a3a;
                        color: #a0a0a0;
                        border: none;
                        border-radius: 8px;
                    }
                    QPushButton:hover {
                        background-color: #4a4a4a;
                    }
                """)
                btn.clicked.connect(self._on_negate)
            else:
                btn.setStyleSheet("""
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
                """)
                btn.clicked.connect(lambda checked, t=text: self._on_number(t))

            numpad_layout.addWidget(btn, row, col)

        parent_layout.addWidget(numpad_frame)

    def _populate_units(self):
        """Populate unit dropdowns."""
        units = self.manager.get_units(self.category)
        for key, name, symbol in units:
            display = f"{name} ({symbol})"
            self.from_unit.addItem(display, key)
            self.to_unit.addItem(display, key)

        # Set different defaults
        if self.from_unit.count() > 1:
            self.to_unit.setCurrentIndex(1)

    def _on_number(self, num: str):
        current = self.input_field.text()

        # Handle decimal
        if num == '.':
            if '.' in current:
                return
            if not current:
                self.input_field.setText('0.')
                return

        self.input_field.setText(current + num)

    def _on_clear(self):
        self.input_field.clear()
        self.output_field.clear()

    def _on_backspace(self):
        current = self.input_field.text()
        if current:
            self.input_field.setText(current[:-1])
            # Recalculate
            self._on_input_changed()

    def _on_negate(self):
        current = self.input_field.text()
        if not current or current == '0':
            return

        if current.startswith('-'):
            self.input_field.setText(current[1:])
        else:
            self.input_field.setText('-' + current)

    def _on_swap(self):
        """Swap from and to units."""
        from_idx = self.from_unit.currentIndex()
        to_idx = self.to_unit.currentIndex()
        self.from_unit.setCurrentIndex(to_idx)
        self.to_unit.setCurrentIndex(from_idx)

    def _on_input_changed(self):
        """Handle input change and perform conversion."""
        text = self.input_field.text()

        if not text:
            self.output_field.clear()
            return

        try:
            value = float(text)
            from_key = self.from_unit.currentData()
            to_key = self.to_unit.currentData()

            if from_key and to_key:
                result = self.manager.convert(self.category, from_key, to_key, value)
                formatted = self.manager.format_result(result)
                self.output_field.setText(formatted)
        except ValueError:
            self.output_field.setText("Invalid input")
        except Exception:
            self.output_field.setText("Error")
