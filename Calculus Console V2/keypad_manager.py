"""
Keypad Manager (PyQt6 version)
Mathematical symbol keypad with clean layout.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget, QSizePolicy
)

from constants import SYMBOL_SETS


class KeypadWindow(QWidget):
    """Floating keypad window that never steals focus."""

    def __init__(self, insert_callback, user_macros=None):
        super().__init__(None)

        self._insert_callback = insert_callback
        self._user_macros = user_macros or []
        self._current_layout = "main"

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setWindowTitle("Symbol Keypad")

        self._apply_styles()
        self._build_ui()

    def _build_ui(self):
        self.setMinimumSize(500, 400)

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # Layout switcher
        switcher = QHBoxLayout()
        switcher.setSpacing(6)

        self._btn_main = QPushButton("Main")
        self._btn_super = QPushButton("Super")
        self._btn_sub = QPushButton("Sub")

        self._layout_buttons = {
            "main": self._btn_main,
            "super": self._btn_super,
            "sub": self._btn_sub
        }

        for name, btn in self._layout_buttons.items():
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setMinimumHeight(34)
            btn.clicked.connect(lambda checked, n=name: self._switch_layout(n))
            switcher.addWidget(btn)

        self._btn_main.setChecked(True)

        main.addLayout(switcher)

        # Symbol container
        self._grid_container = QFrame()

        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(6)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)

        main.addWidget(self._grid_container)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2d2d2d;")
        main.addWidget(sep)

        # Macros header
        macro_header = QLabel("USER MACROS")
        macro_header.setObjectName("macroHeader")
        main.addWidget(macro_header)

        # Macro area
        self._macro_scroll = QScrollArea()
        self._macro_scroll.setWidgetResizable(True)
        self._macro_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._macro_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._macro_widget = QWidget()

        self._macro_grid = QGridLayout(self._macro_widget)
        self._macro_grid.setSpacing(6)
        self._macro_grid.setContentsMargins(0, 0, 0, 0)

        self._macro_scroll.setWidget(self._macro_widget)

        main.addWidget(self._macro_scroll)

        self._refresh_symbols()
        self._refresh_macros()

        self.adjustSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        buttons: list[QPushButton] = self._grid_container.findChildren(QPushButton)

        if not buttons:
            return

        # Find column count
        symbols = SYMBOL_SETS.get(self._current_layout, [])

        if not symbols:
            return

        col_count = max(len(row) for row in symbols)

        spacing = self._grid_layout.spacing()

        margins = self._grid_layout.contentsMargins()

        available_width = (
                self._grid_container.width()
                - margins.left()
                - margins.right()
                - ((col_count - 1) * spacing)
        )

        btn_size = max(28, available_width // col_count)

        # Determine largest text size dynamically
        longest = ""

        for row in symbols:
            for sym in row:
                if len(sym) > len(longest):
                    longest = sym

        # Binary-ish font fitting
        test_font = self.font()

        font_size = btn_size

        while font_size > 6:
            test_font.setPixelSize(font_size)

            metrics = QFontMetrics(test_font)

            rect = metrics.boundingRect(longest)

            if (
                    rect.width() <= btn_size * 0.78 and
                    rect.height() <= btn_size * 0.78
            ):
                break

            font_size -= 1

        # Apply sizing
        for btn in buttons:
            if not isinstance(btn, QPushButton):
                continue

            btn_font = btn.font()

            btn_font.setPixelSize(font_size)

            btn.setFont(btn_font)

            btn.resize(btn_size, btn_size)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
                background-color: #181818;
                color: #f0f0f0;
            }

            QFrame {
                background: transparent;
            }

            QPushButton {
                background-color: #2b2b2b;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px 12px;
            }

            QPushButton:hover {
                background-color: #353535;
                border-color: #4a4a4a;
            }

            QPushButton:pressed {
                background-color: #202020;
            }

            QPushButton:checked {
                background-color: #2d6cdf;
                border-color: #4d8dff;
                color: white;
            }

            #macroHeader {
                color: #7f7f7f;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
                padding-left: 2px;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }

            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 4px;
            }
        """)

        self._symbol_style = """
            QPushButton {
                background-color: #242424;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 500;
                min-width: 42px;
                min-height: 42px;
                padding: 6px;
            }

            QPushButton:hover {
                background-color: #303030;
                border-color: #4f4f4f;
            }

            QPushButton:pressed {
                background-color: #171717;
            }
        """

    def _refresh_symbols(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        symbols = SYMBOL_SETS.get(self._current_layout, [])

        for row_idx, row_symbols in enumerate(symbols):
            for col_idx, symbol in enumerate(row_symbols):
                btn = QPushButton(symbol)

                btn.setCursor(
                    QCursor(Qt.CursorShape.PointingHandCursor)
                )

                btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Expanding
                )

                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #242424;
                        color: white;
                        border: 1px solid #3a3a3a;
                        border-radius: 8px;
                        padding: 2px;
                    }

                    QPushButton:hover {
                        background-color: #303030;
                        border-color: #4a4a4a;
                    }

                    QPushButton:pressed {
                        background-color: #171717;
                    }
                """)

                btn.clicked.connect(
                    lambda checked, s=symbol:
                    self._insert_symbol(s)
                )

                self._grid_layout.addWidget(
                    btn,
                    row_idx,
                    col_idx
                )

        # Stretch everything evenly
        max_cols = max((len(r) for r in symbols), default=1)

        for c in range(max_cols):
            self._grid_layout.setColumnStretch(c, 1)

        for r in range(len(symbols)):
            self._grid_layout.setRowStretch(r, 1)

        self.adjustSize()

        # Trigger responsive sizing immediately
        self.resizeEvent(None)

    def _refresh_macros(self):
        while self._macro_grid.count():
            item = self._macro_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._user_macros:
            empty = QLabel("No macros defined")

            empty.setStyleSheet("""
                color: #666;
                font-style: italic;
                padding: 4px;
            """)

            self._macro_grid.addWidget(empty, 0, 0)

            self._macro_scroll.setMaximumHeight(40)

            self.adjustSize()
            return

        cols = 4

        max_macro_width = 0

        metrics = QFontMetrics(self.font())

        for macro in self._user_macros:
            label = macro.get("label", "?")
            rect = metrics.boundingRect(label)

            max_macro_width = max(max_macro_width, rect.width())

        macro_btn_width = max(max_macro_width + 28, 70)

        for i, macro in enumerate(self._user_macros):
            btn = QPushButton(macro.get("label", "?"))

            btn.setMinimumWidth(macro_btn_width)
            btn.setMinimumHeight(34)

            btn.setStyleSheet("""
                QPushButton {
                    background-color: #25364a;
                    color: #f0f4ff;
                    border: 1px solid #35506e;
                    border-radius: 8px;
                    padding: 6px 10px;
                    font-size: 12px;
                    font-weight: 500;
                }

                QPushButton:hover {
                    background-color: #30465f;
                }

                QPushButton:pressed {
                    background-color: #1c2a3b;
                }
            """)

            btn.setCursor(
                QCursor(Qt.CursorShape.PointingHandCursor)
            )

            warp = macro.get("warp", 0)
            content = macro.get("content", "")

            btn.clicked.connect(
                lambda checked, c=content, w=warp:
                self._insert_symbol(c, w)
            )

            row = i // cols
            col = i % cols

            self._macro_grid.addWidget(btn, row, col)

        rows = (len(self._user_macros) + cols - 1) // cols

        self._macro_scroll.setMaximumHeight(
            min((rows * 44) + 8, 220)
        )

        self.adjustSize()

        hint = self.sizeHint()

        self.resize(
            hint.width(),
            hint.height()
        )

    def _switch_layout(self, layout_name):
        if layout_name == self._current_layout:
            return

        self._current_layout = layout_name

        for name, btn in self._layout_buttons.items():
            btn.setChecked(name == layout_name)

        self._refresh_symbols()

        # Recalculate entire window size
        self.adjustSize()

        hint = self.sizeHint()

        self.resize(
            hint.width(),
            hint.height()
        )

    def _insert_symbol(self, text, warp=0):
        if self._insert_callback:
            self._insert_callback(text, warp)

    def update_macros(self, new_macros):
        self._user_macros = new_macros or []
        self._refresh_macros()


class KeypadManager:
    """Manages keypad window lifecycle."""

    def __init__(self, insert_text_callback, user_macros=None):
        self._insert_callback = insert_text_callback
        self._user_macros = user_macros or []
        self._window = None

    def toggle(self, parent_widget=None):
        if self.is_open():
            self.close()
            return False
        return self.open(parent_widget)

    def open(self, parent_widget=None):
        self.close()
        self._window = KeypadWindow(self._insert_callback, self._user_macros)

        if parent_widget:
            geo = parent_widget.geometry()
            x = geo.x() + geo.width() // 2 - 220
            y = geo.y() + 100
            self._window.move(x, y)

        self._window.show()
        return True

    def close(self):
        if self._window:
            try:
                self._window.close()
                self._window.deleteLater()
            except RuntimeError:
                pass  # Already deleted
            finally:
                self._window = None

    def is_open(self):
        try:
            return self._window is not None and self._window.isVisible()
        except RuntimeError:
            # C++ object was deleted behind our back
            self._window = None
            return False

    def update_macros(self, new_macros):
        self._user_macros = new_macros or []
        if self.is_open():
            try:
                self._window.update_macros(self._user_macros)
            except RuntimeError:
                self._window = None
