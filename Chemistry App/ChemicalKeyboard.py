from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

class ChemicalKeyboard(QWidget):
    # Signal to emit when a symbol is clicked
    symbol_clicked = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Keyboard")
        self.resize(400, 350)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Chemical Symbols Keyboard")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subscripts section
        subscripts_group = QGroupBox("Subscripts")
        subscripts_layout = QHBoxLayout()
        subscripts = ["₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉"]
        for sub in subscripts:
            btn = QPushButton(sub)
            btn.setFixedSize(35, 30)
            btn.clicked.connect(lambda checked, s=sub: self.emit_symbol(s))
            subscripts_layout.addWidget(btn)
        subscripts_group.setLayout(subscripts_layout)
        layout.addWidget(subscripts_group)
        
        # Arrows section
        arrows_group = QGroupBox("Arrows")
        arrows_layout = QHBoxLayout()
        arrows = ["→", "←", "⇌", "⇋", "↔", "↑", "↓"]
        for arrow in arrows:
            btn = QPushButton(arrow)
            btn.setFixedSize(35, 30)
            btn.clicked.connect(lambda checked, a=arrow: self.emit_symbol(a))
            arrows_layout.addWidget(btn)
        arrows_group.setLayout(arrows_layout)
        layout.addWidget(arrows_group)
        
        # States section
        states_group = QGroupBox("States")
        states_layout = QHBoxLayout()
        states = ["(aq)", "(s)", "(l)", "(g)"]
        for state in states:
            btn = QPushButton(state)
            btn.setFixedSize(45, 30)
            btn.clicked.connect(lambda checked, s=state: self.emit_symbol(s))
            states_layout.addWidget(btn)
        states_group.setLayout(states_layout)
        layout.addWidget(states_group)

        # Common compounds section
        compounds_group = QGroupBox("Common Compounds")
        compounds_layout = QHBoxLayout()
        compounds = ["H₂O", "CO₂", "NH₃", "CH₄", "O₂", "H₂", "N₂", "Cl₂"]
        for compound in compounds:
            btn = QPushButton(compound)
            btn.setFixedSize(45, 30)
            btn.clicked.connect(lambda checked, c=compound: self.emit_symbol(c))
            compounds_layout.addWidget(btn)
        compounds_group.setLayout(compounds_layout)
        layout.addWidget(compounds_group)
        
        self.setLayout(layout)
    
    def emit_symbol(self, symbol):
        """Emit the symbol clicked signal"""
        self.symbol_clicked.emit(symbol)
        
    def mousePressEvent(self, event):
        """Prevent window from taking focus on click"""
        event.ignore()
        
    def focusInEvent(self, event):
        """Prevent window from taking focus"""
        event.ignore()
