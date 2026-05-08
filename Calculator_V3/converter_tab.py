"""
Converter Tab - Comprehensive unit conversion interface.
"""

from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import QTimer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QComboBox,
    QFrame, QSizePolicy, QLabel, QProgressBar
)

from constants_calculator import FONT, REFRESH_BTN_TEXT
from conversions import ConversionCategory, get_manager, ConversionManager


class SingleConverter(QWidget):
    """A single conversion panel for one category."""

    def __init__(self, category: ConversionCategory, parent=None):
        super().__init__(parent)
        self.category = category
        self.manager = get_manager()
        self.buttons = {}  # Store buttons for font resizing
        self._setup_ui()

    def _setup_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(15, 15, 15, 15)
        self._main_layout.setSpacing(15)

        # Check if this is currency converter
        self._is_currency = (self.category == ConversionCategory.CURRENCY)

        # Create a container for display + numpad that can be reoriented
        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(15)

        # Display area - always stacked vertically (input on top, output below)
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

        # Add stretch to center content vertically
        display_layout.addStretch(1)

        # Loading progress bar (shown during refresh)
        self.loading_bar = QProgressBar()
        self.loading_bar.setFixedHeight(2)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet("""
            QProgressBar {
                background-color: transparent;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #4a90d9;
            }
        """)
        self.loading_bar.setRange(0, 0)  # Indeterminate mode
        self.loading_bar.hide()
        # Add at top of display_layout
        display_layout.insertWidget(0, self.loading_bar)

        # Main conversion entry layout (vertical stack: input | swap | output)
        conversion_entry = QVBoxLayout()
        conversion_entry.setSpacing(15)
        conversion_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # === FROM SECTION (field on top, combobox below) ===
        from_section = QVBoxLayout()
        from_section.setSpacing(8)
        from_section.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Input field with optional currency symbol prefix
        input_container = QHBoxLayout()
        input_container.setSpacing(0)
        input_container.setContentsMargins(0, 0, 0, 0)

        # Currency symbol label (prefix) - only shown for currency
        self.input_symbol_label = QLabel("")
        self.input_symbol_label.setFont(QFont(FONT, 20, QFont.Weight.Bold))
        self.input_symbol_label.setStyleSheet("color: #808080; background-color: transparent; border: none;")
        self.input_symbol_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.input_symbol_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.input_symbol_label.hide()
        input_container.addWidget(self.input_symbol_label)

        self.input_field = QLineEdit()
        self.input_field.setFont(QFont(FONT, 24, QFont.Weight.Bold))
        self.input_field.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.input_field.setPlaceholderText("0")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                padding: 10px;
            }
        """)
        self.input_field.textChanged.connect(self._on_input_changed)
        input_container.addWidget(self.input_field, stretch=2)
        from_section.addLayout(input_container)

        self.from_unit = QComboBox()
        self.from_unit.setFont(QFont(FONT, 12))
        self.from_unit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.from_unit.setStyleSheet("""
            QComboBox {
                background-color: transparent;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: #ffffff;
                selection-background-color: #ff9500;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
            }
        """)
        from_section.addWidget(self.from_unit, alignment=Qt.AlignmentFlag.AlignLeft)
        conversion_entry.addLayout(from_section)

        # === SWAP BUTTON (centered) ===
        self.swap_btn = QPushButton("⇅")
        self.swap_btn.setFont(QFont(FONT, 16))
        self.swap_btn.setFixedSize(50, 40)
        self.swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swap_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
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
        conversion_entry.addWidget(self.swap_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # === TO SECTION (field on top, combobox below) ===
        to_section = QVBoxLayout()
        to_section.setSpacing(8)
        to_section.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Output field with optional currency symbol prefix
        output_container = QHBoxLayout()
        output_container.setSpacing(0)
        output_container.setContentsMargins(0, 0, 0, 0)

        # Currency symbol label (prefix) - only shown for currency
        self.output_symbol_label = QLabel("")
        self.output_symbol_label.setFont(QFont(FONT, 20, QFont.Weight.Bold))
        self.output_symbol_label.setStyleSheet("color: #808080; background-color: transparent; border: none;")
        self.output_symbol_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.output_symbol_label.hide()
        output_container.addWidget(self.output_symbol_label)

        self.output_field = QLineEdit()
        self.output_field.setFont(QFont(FONT, 24, QFont.Weight.Bold))
        self.output_field.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.output_field.setReadOnly(True)
        self.output_field.setPlaceholderText("0")
        self.output_field.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: #66b3ff;
                padding: 10px;
            }
        """)
        output_container.addWidget(self.output_field, stretch=2)
        to_section.addLayout(output_container)

        self.to_unit = QComboBox()
        self.to_unit.setFont(QFont(FONT, 12))
        self.to_unit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.to_unit.setStyleSheet(self.from_unit.styleSheet())
        to_section.addWidget(self.to_unit, alignment=Qt.AlignmentFlag.AlignLeft)
        conversion_entry.addLayout(to_section)

        display_layout.addLayout(conversion_entry)
        # Add stretch above to center the conversion entries
        display_layout.addStretch(1)

        # Currency info section (refresh btn + last updated + exchange rate) inside display area
        self._info_widget = QWidget()
        self._info_widget.setFixedHeight(32)
        self._info_widget.setStyleSheet("background-color: transparent; border: none;")

        self._info_layout = QHBoxLayout(self._info_widget)
        self._info_layout.setContentsMargins(0, 0, 0, 0)
        self._info_layout.setSpacing(8)

        display_layout.addWidget(self._info_widget)

        self._content_layout.addWidget(display_frame)

        # Setup numpad (store reference for responsive layout)
        self._numpad_frame = self._create_numpad()
        self._content_layout.addWidget(self._numpad_frame)

        self._main_layout.addWidget(self._content_container)

        # Populate unit dropdowns
        self._populate_units()

        # Add unit info bar for all converters
        self._add_unit_info_bar()

        # Initialize currency symbols if this is currency converter
        if self._is_currency:
            self._update_currency_symbols()

        # Connect unit changes
        self.from_unit.currentIndexChanged.connect(self._on_input_changed)
        self.from_unit.currentIndexChanged.connect(self._on_unit_changed)
        self.to_unit.currentIndexChanged.connect(self._on_input_changed)
        self.to_unit.currentIndexChanged.connect(self._on_unit_changed)

    def _create_numpad(self):
        """Create the numeric keypad frame."""
        numpad_frame = QFrame()
        numpad_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 12px;
                border: 1px solid #3d3d3d;
            }
        """)
        numpad_layout = QGridLayout(numpad_frame)
        numpad_layout.setSpacing(8)
        numpad_layout.setContentsMargins(15, 15, 15, 15)

        buttons = [
            ('C', 0, 0), ('⌫', 0, 1), ('±', 0, 2),
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2),
            ('0', 4, 0), ('.', 4, 1), ('00', 4, 2),
        ]

        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setFont(QFont(FONT, 14))
            self.buttons[text] = btn

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
                # Skip +/- button for currency
                if self._is_currency:
                    continue
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

        # Make rows and columns stretch equally
        for i in range(5):  # 5 rows
            numpad_layout.setRowStretch(i, 1)
        for i in range(3):  # 3 columns
            numpad_layout.setColumnStretch(i, 1)

        return numpad_frame

    def resizeEvent(self, event):
        """Handle resize to switch between stacked and side-by-side layout."""
        super().resizeEvent(event)

        # Update button font sizes based on button dimensions
        self._update_button_fonts()

        # Update converter element font sizes based on window size
        self._update_converter_fonts()

        self._update_content_layout()

    def _update_button_fonts(self):
        """Update numpad button font sizes based on their dimensions."""
        if not self.buttons:
            return

        # Get a reference button to calculate font size
        sample_btn = next(iter(self.buttons.values()))
        btn_height = sample_btn.height()
        btn_width = sample_btn.width()

        # Calculate font size - use average of dimensions for better scaling
        avg_dim = (btn_height + btn_width) / 2
        # Scale factor: ~18% of average dimension, clamped between 8 and 24
        font_size = max(8, min(24, int(avg_dim * 0.18)))

        # Update font for all buttons
        font = QFont(FONT, font_size)
        for btn in self.buttons.values():
            btn.setFont(font)

    def _update_converter_fonts(self):
        """Update converter element font sizes based on window width."""
        # Calculate scale factor based on window width
        window_width = self.width()

        # Base font sizes at reference width (700px)
        # Scale proportionally: larger window = larger fonts
        scale_factor = window_width / 700.0

        # Input/output fields - scale between 16 and 32
        field_font_size = max(16, min(32, int(24 * scale_factor)))
        field_font = QFont(FONT, field_font_size, QFont.Weight.Bold)
        self.input_field.setFont(field_font)
        self.output_field.setFont(field_font)

        # Symbol labels - slightly smaller than fields
        symbol_font_size = max(14, min(28, int(20 * scale_factor)))
        symbol_font = QFont(FONT, symbol_font_size, QFont.Weight.Bold)
        self.input_symbol_label.setFont(symbol_font)
        self.output_symbol_label.setFont(symbol_font)

        # Unit comboboxes - smaller
        combo_font_size = max(10, min(18, int(12 * scale_factor)))
        combo_font = QFont(FONT, combo_font_size)
        self.from_unit.setFont(combo_font)
        self.to_unit.setFont(combo_font)

        # Swap button
        swap_font_size = max(12, min(24, int(16 * scale_factor)))
        self.swap_btn.setFont(QFont(FONT, swap_font_size))

        # Conversion label in info bar
        if hasattr(self, 'conversion_label'):
            info_font_size = max(9, min(16, int(11 * scale_factor)))
            self.conversion_label.setFont(QFont(FONT, info_font_size))

        # Refresh button and last updated for currency
        if self._is_currency:
            refresh_font_size = max(10, min(16, int(12 * scale_factor)))
            if hasattr(self, 'refresh_btn'):
                self.refresh_btn.setFont(QFont(FONT, refresh_font_size))
            if hasattr(self, 'last_updated_label'):
                time_font_size = max(8, min(14, int(9 * scale_factor)))
                self.last_updated_label.setFont(QFont(FONT, time_font_size))

    def _update_content_layout(self):
        """Update layout based on available width - keypad on side when wide."""
        # Threshold: 700 pixels for side-by-side
        use_side_by_side = self.width() >= 700

        # Check if we need to change layout
        current_is_horizontal = isinstance(self._content_layout, QHBoxLayout)

        if use_side_by_side and not current_is_horizontal:
            # Switch to horizontal (display left, numpad right)
            old_widget = self._content_container
            self._content_layout.deleteLater()

            self._content_container = QWidget()
            self._content_layout = QHBoxLayout(self._content_container)
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            self._content_layout.setSpacing(15)

            # Get display frame (first widget)
            display_frame = old_widget.layout().itemAt(0).widget()
            numpad_frame = old_widget.layout().itemAt(1).widget()

            self._content_layout.addWidget(display_frame, stretch=2)
            self._content_layout.addWidget(numpad_frame, stretch=1)

            # Replace in main layout
            self._main_layout.removeItem(self._main_layout.itemAt(0))
            self._main_layout.addWidget(self._content_container)

        elif not use_side_by_side and current_is_horizontal:
            # Switch to vertical (display top, numpad bottom)
            old_widget = self._content_container
            self._content_layout.deleteLater()

            self._content_container = QWidget()
            self._content_layout = QVBoxLayout(self._content_container)
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            self._content_layout.setSpacing(15)

            # Get widgets
            display_frame = old_widget.layout().itemAt(0).widget()
            numpad_frame = old_widget.layout().itemAt(1).widget()

            self._content_layout.addWidget(display_frame)
            self._content_layout.addWidget(numpad_frame)

            # Replace in main layout
            self._main_layout.removeItem(self._main_layout.itemAt(0))
            self._main_layout.addWidget(self._content_container)

    def _populate_units(self):
        """Populate unit dropdowns."""
        units = self.manager.get_units(self.category)

        if self._is_currency:
            # For currency, make comboboxes editable/searchable and show full names
            self.from_unit.setEditable(True)
            self.from_unit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self.to_unit.setEditable(True)
            self.to_unit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

            for key, name, symbol in units:
                display = f"{key} - {name}"  # Show code and full name
                self.from_unit.addItem(display, key)
                self.to_unit.addItem(display, key)
        else:
            # Normal converter - show name and symbol
            for key, name, symbol in units:
                display = f"{name} ({symbol})"
                self.from_unit.addItem(display, key)
                self.to_unit.addItem(display, key)

        # Set different defaults
        if self.from_unit.count() > 1:
            self.to_unit.setCurrentIndex(1)

    def _add_unit_info_bar(self):
        """Add unit info bar showing conversion rate for all converters."""
        # ALL converters get the conversion label (aligned right)
        self.conversion_label = QLabel("1 - = -- -")
        self.conversion_label.setFont(QFont(FONT, 10))
        self.conversion_label.setStyleSheet("color: #a0a0a0; background-color: transparent;")
        self.conversion_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if self._is_currency:
            # For currency: add refresh button + time + conversion label
            self.refresh_btn = QPushButton("🔄 Refresh")
            self.refresh_btn.setFont(QFont(FONT, 10))
            self.refresh_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a;
                    color: #ffffff;
                    border: none;
                    border-radius: 5px;
                    padding: 2px 8px;
                }
                QPushButton:hover {
                    background-color: #ff9500;
                }
            """)
            self.refresh_btn.clicked.connect(self._on_refresh_currency)
            self._info_layout.addWidget(self.refresh_btn)

            # Offline indicator - shows when using cached/offline rates
            self.offline_label = QLabel("Offline")
            self.offline_label.setFont(QFont(FONT, 9))
            self.offline_label.setStyleSheet(
                "color: #ff9500; background-color: transparent; padding: 2px 6px; border-radius: 4px;")
            self.offline_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            self.offline_label.hide()
            self._info_layout.addWidget(self.offline_label)

            # Last updated label - compact time only
            self.last_updated_label = QLabel("--:--")
            self.last_updated_label.setFont(QFont(FONT, 9))
            self.last_updated_label.setStyleSheet("color: #808080; background-color: transparent;")
            self.last_updated_label.setFixedSize(40, 24)
            self.last_updated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._info_layout.addWidget(self.last_updated_label)

            self._info_layout.addStretch()
            self._info_layout.addWidget(self.conversion_label)

            # Check offline status and update UI
            self._update_offline_status()

            # Update last updated time
            self._update_last_updated_time()
            self._update_exchange_rate_label()
        else:
            # For other converters: just conversion label (stretches to right)
            self._info_layout.addStretch()
            self._info_layout.addWidget(self.conversion_label)
            self._update_exchange_rate_label()

    def _update_last_updated_time(self):
        """Update the last updated time display."""
        last_updated = self.manager.get_last_updated()
        if last_updated:
            time_str = last_updated.strftime("%H:%M")
        else:
            time_str = "--:--"
        self.last_updated_label.setText(time_str)

    def _update_offline_status(self):
        """Update offline indicator based on manager status."""
        if self.manager.is_offline():
            self.offline_label.show()
        else:
            self.offline_label.hide()

    def _on_refresh_currency(self):
        """Refresh currency rates."""
        # Show loading bar
        self.loading_bar.show()
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("⏳ Refreshing...")

        manager = get_manager()
        success = manager.refresh_currency_rates()

        # Hide loading bar and re-enable button
        self.loading_bar.hide()
        self.refresh_btn.setEnabled(True)

        if success:
            self._update_last_updated_time()
            self._update_offline_status()  # Hide offline indicator
            # Recalculate current conversion
            self._on_input_changed()
            self.refresh_btn.setText("🔄 Refreshed!")
            QTimer.singleShot(2000, lambda: self.refresh_btn.setText(REFRESH_BTN_TEXT))
        else:
            self._update_offline_status()  # Show offline indicator if still offline
            self.refresh_btn.setText("❌ Failed")
            QTimer.singleShot(2000, lambda: self.refresh_btn.setText(REFRESH_BTN_TEXT))

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

    def _on_unit_changed(self):
        """Handle unit selection change - update exchange rate and currency symbols."""
        # Update exchange rate label for ALL converters
        self._update_exchange_rate_label()

        if self._is_currency:
            self._update_currency_symbols()

    @staticmethod
    def _get_currency_symbol(currency_code: str) -> str:
        """Get the currency symbol for a given currency code. Fallback to code if no symbol."""
        return ConversionManager._CURRENCY_SYMBOLS.get(currency_code, currency_code)

    def _update_currency_symbols(self):
        """Update currency symbol labels based on current selection."""
        from_key = self.from_unit.currentData()
        to_key = self.to_unit.currentData()

        if from_key:
            from_symbol = self._get_currency_symbol(from_key)
            self.input_symbol_label.setText(from_symbol)
            self.input_symbol_label.setVisible(bool(from_symbol))

        if to_key:
            to_symbol = self._get_currency_symbol(to_key)
            self.output_symbol_label.setText(to_symbol)
            self.output_symbol_label.setVisible(bool(to_symbol))

    def _on_input_changed(self):
        """Handle input change and perform conversion."""
        text = self.input_field.text()

        if not text:
            self.output_field.clear()
            self._update_exchange_rate_label()
            return

        try:
            # Try Decimal first for large number support
            try:
                value = Decimal(text)
            except InvalidOperation:
                value = float(text)

            from_key = self.from_unit.currentData()
            to_key = self.to_unit.currentData()

            if from_key and to_key:
                result = self.manager.convert(self.category, from_key, to_key, value)

                # Format result - all converters get 4-5 decimal places
                formatted = self._format_result(result)
                self._update_exchange_rate_label()
                self.output_field.setText(formatted)
        except ValueError:
            self.output_field.setText("Invalid input")
        except OverflowError:
            self.output_field.setText("∞ (overflow)")
        except Exception:
            self.output_field.setText("Error")

    @staticmethod
    def _format_result(result) -> str:
        """Format conversion result to 4-5 decimal places."""
        try:
            float_result = float(result)
            # Use scientific notation for very large or very small numbers
            if abs(float_result) >= 1e6 or (abs(float_result) < 1e-4 and float_result != 0):
                return f"{float_result:.5e}"
            # Otherwise use 4 decimal places
            return f"{float_result:.4f}"
        except (ValueError, OverflowError):
            return str(result)

    def _update_exchange_rate_label(self):
        """Update the exchange rate label showing 1 from = ? to."""
        from_key = self.from_unit.currentData()
        to_key = self.to_unit.currentData()

        if from_key and to_key:
            # Get unit info for display names
            units = self.manager.get_units(self.category)
            from_unit = next((u for u in units if u[0] == from_key), (from_key, from_key, from_key))
            to_unit = next((u for u in units if u[0] == to_key), (to_key, to_key, to_key))

            # Calculate rate for 1 unit
            rate = self.manager.convert(self.category, from_key, to_key, Decimal('1'))

            if self._is_currency:
                # For currency: show code with 4 decimals
                self.conversion_label.setText(f"1 {from_key} = {float(rate):.4f} {to_key}")
            else:
                # For other units: show short symbol
                from_symbol = from_unit[2]  # symbol
                to_symbol = to_unit[2]  # symbol
                # Format rate appropriately
                if rate >= 1000 or (0.01 > rate > 0):
                    formatted_rate = f"{float(rate):.4e}"
                else:
                    formatted_rate = f"{float(rate):.4f}"
                self.conversion_label.setText(f"1 {from_symbol} = {formatted_rate} {to_symbol}")

    def showEvent(self, event):
        """Override showEvent to auto-refresh currency rates when tab becomes visible."""
        super().showEvent(event)
        if self._is_currency:
            # Refresh every time currency tab is shown
            QTimer.singleShot(300, self._on_refresh_currency)
