from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QGroupBox)

from constants import FONT


class ChemicalKeyboard(QWidget):
    symbol_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chemical Keyboard")
        self.resize(400, 300)

        # CRITICAL FIXES:
        # Qt.Tool - utility window, bypasses modal blocking
        # WindowDoesNotAcceptFocus - doesn't take focus at all
        # WindowStaysOnTopHint - stays above dialog
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("Chemical Symbols Keyboard")
        title.setFont(QFont(FONT, 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subscripts_group = QGroupBox("Subscripts")
        subscripts_layout = QHBoxLayout()
        subscripts = ["₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉"]
        for sub in subscripts:
            btn = self.create_button(sub)
            btn.clicked.connect(lambda checked, s=sub: self.emit_symbol(s))
            subscripts_layout.addWidget(btn)
        subscripts_group.setLayout(subscripts_layout)
        layout.addWidget(subscripts_group)

        arrows_group = QGroupBox("Arrows")
        arrows_layout = QHBoxLayout()
        arrows = ["→", "←", "⇌", "⇋", "↔", "↑", "↓"]
        for arrow in arrows:
            btn = self.create_button(arrow)
            btn.clicked.connect(lambda checked, a=arrow: self.emit_symbol(a))
            arrows_layout.addWidget(btn)
        arrows_group.setLayout(arrows_layout)
        layout.addWidget(arrows_group)

        states_group = QGroupBox("States")
        states_layout = QHBoxLayout()
        states = ["(aq)", "(s)", "(l)", "(g)", "(ppt)", "(↑)", "(↓)"]
        for state in states:
            btn = self.create_button(state, (45, 30))
            btn.clicked.connect(lambda checked, s=state: self.emit_symbol(s))
            states_layout.addWidget(btn)
        states_group.setLayout(states_layout)
        layout.addWidget(states_group)

        self.setLayout(layout)

    def emit_symbol(self, symbol):
        self.symbol_clicked.emit(symbol)

    def create_button(self, text, size=(35, 30)):
        btn = QPushButton(text)
        btn.setFixedSize(*size)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn
