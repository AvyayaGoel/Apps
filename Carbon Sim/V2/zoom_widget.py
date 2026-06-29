"""Small floating zoom control."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton


class CanvasZoomWidget(QFrame):
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet('''
            QFrame {
                background-color: rgba(12, 18, 30, 200);
                border: 1px solid #2a3a50;
                border-radius: 8px;
            }
        ''')
        layout = QHBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(5, 5, 5, 5)
        btn_style = '''
            QPushButton {
                background-color: #1a2435;
                color: #8ca0c0;
                border-radius: 6px;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #2a3a50;
            }
            QPushButton:hover {
                background-color: #243045;
                color: #dce8ff;
                border: 1px solid #3a5068;
            }
            QPushButton:pressed {
                background-color: #152030;
            }
        '''
        self.zoom_out_btn = QPushButton('−')
        self.zoom_out_btn.setFixedSize(34, 34)
        self.zoom_out_btn.setStyleSheet(btn_style)
        self.zoom_out_btn.setToolTip('Zoom Out')
        self.zoom_out_btn.clicked.connect(self.zoom_out_requested.emit)
        layout.addWidget(self.zoom_out_btn)

        self.zoom_in_btn = QPushButton('+')
        self.zoom_in_btn.setFixedSize(34, 34)
        self.zoom_in_btn.setStyleSheet(btn_style)
        self.zoom_in_btn.setToolTip('Zoom In')
        self.zoom_in_btn.clicked.connect(self.zoom_in_requested.emit)
        layout.addWidget(self.zoom_in_btn)

        self.adjustSize()
