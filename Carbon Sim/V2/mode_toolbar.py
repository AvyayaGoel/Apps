"""Floating mode toolbar (Select/Edit/Delete + transform tools)."""

import logging
from typing import Dict

from PyQt6.QtCore import Qt, QByteArray, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton

logger = logging.getLogger(__name__)

_TOOLBAR_ICONS = {
    'select': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 3 L5 19 L9.5 14.5 L12.5 21 L15 20 L12 13.3 L18 13.3 Z"
              fill="#aebdd6" stroke="#0c121e" stroke-width="1" stroke-linejoin="round"/>
        </svg>''',
    'edit': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <line x1="7" y1="15" x2="16" y2="8" stroke="#aebdd6" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="7" cy="15" r="4" fill="#3a5a82" stroke="#0c121e" stroke-width="1"/>
        <circle cx="16" cy="8" r="4" fill="#4a9fd0" stroke="#0c121e" stroke-width="1"/>
        <path d="M16 5.3 L16 10.7 M13.3 8 L18.7 8" stroke="#0c121e" stroke-width="1.3" stroke-linecap="round"/>
        </svg>''',
    'delete': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <g transform="rotate(-40 12 12)">
            <rect x="6" y="8.5" width="12" height="7" rx="1.8"
                  fill="#dce4f0" stroke="#0c121e" stroke-width="1.1"/>
            <rect x="6" y="8.5" width="4.2" height="7" rx="1.8"
                  fill="#e08090" stroke="#0c121e" stroke-width="1.1"/>
            <line x1="10.2" y1="8.7" x2="10.2" y2="15.3" stroke="#0c121e" stroke-width="0.8"/>
        </g>
        </svg>''',
    'rotate': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 12a7 7 0 1 1 -2.5 -5.4" fill="none" stroke="#aebdd6" stroke-width="2.3" stroke-linecap="round"/>
        <path d="M17.5 3.5 L16.6 7.4 L20.5 7.0 Z" fill="#aebdd6"/>
        </svg>''',
    'flip_h': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M11 5 L4 12 L11 19 Z" fill="#aebdd6"/>
        <path d="M13 5 L20 12 L13 19 Z" fill="#5a7088"/>
        <line x1="12" y1="3" x2="12" y2="21" stroke="#4a9fd0" stroke-width="1.4" stroke-dasharray="2.5,2.5"/>
        </svg>''',
    'flip_v': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 11 L12 4 L19 11 Z" fill="#aebdd6"/>
        <path d="M5 13 L12 20 L19 13 Z" fill="#5a7088"/>
        <line x1="3" y1="12" x2="21" y2="12" stroke="#4a9fd0" stroke-width="1.4" stroke-dasharray="2.5,2.5"/>
        </svg>''',
    'chain': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <line x1="4.5" y1="18" x2="11.5" y2="6.5" stroke="#aebdd6" stroke-width="2.2" stroke-linecap="round"/>
        <line x1="11.5" y1="6.5" x2="19.5" y2="11" stroke="#aebdd6" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="4.5" cy="18" r="3" fill="#3a5a82" stroke="#0c121e" stroke-width="1"/>
        <circle cx="11.5" cy="6.5" r="3" fill="#4a9fd0" stroke="#0c121e" stroke-width="1"/>
        <circle cx="19.5" cy="11" r="3" fill="#3a5a82" stroke="#0c121e" stroke-width="1"/>
        </svg>''',
    'marquee_rect': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="6" width="16" height="12" rx="1"
              fill="none" stroke="#aebdd6" stroke-width="1.8" stroke-dasharray="2.6,2.2"/>
        <circle cx="4" cy="6" r="1.4" fill="#dce8ff"/>
        <circle cx="20" cy="6" r="1.4" fill="#dce8ff"/>
        <circle cx="4" cy="18" r="1.4" fill="#dce8ff"/>
        <circle cx="20" cy="18" r="1.4" fill="#dce8ff"/>
        </svg>''',
    'marquee_lasso': '''<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M13.2 4.3 C8.8 3.6 5 6 4.3 9.6 C3.7 12.7 6 15.6 9.8 16.5
                 C13.1 17.3 16.6 16.2 18.4 13.8 C19.8 12 19.6 9.6 17.7 8.2
                 C15.8 6.8 12.6 6.9 10.7 8.5 C9.2 9.7 9.1 11.4 10.4 12.4
                 C11.5 13.2 13.2 13.1 14 12.1"
              fill="none" stroke="#aebdd6" stroke-width="1.8" stroke-linecap="round"
              stroke-dasharray="2.3,2.1"/>
        <path d="M9.8 16.5 C9.3 17.6 9.0 18.7 9.4 19.6 C9.8 20.4 10.8 20.6 11.6 20.0"
              fill="none" stroke="#aebdd6" stroke-width="1.8" stroke-linecap="round"
              stroke-dasharray="2.3,2.1"/>
        <circle cx="11.6" cy="20.0" r="1.5" fill="#4a9fd0" stroke="#0c121e" stroke-width="0.8"/>
        </svg>''',
}

_icon_cache: Dict[str, QIcon] = {}


def toolbar_icon(name: str, size: int = 22) -> QIcon:
    key = f'{name}@{size}'
    if key in _icon_cache:
        return _icon_cache[key]
    svg = _TOOLBAR_ICONS.get(name)
    if not svg:
        logger.warning(f'toolbar_icon: unknown icon name "{name}"')
        return QIcon()
    try:
        renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
        pix = QPixmap(size * 4, size * 4)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size * 4, size * 4))
        painter.end()
        icon = QIcon(pix)
        _icon_cache[key] = icon
        return icon
    except Exception as e:
        logger.exception(f'toolbar_icon render error for "{name}": {e}')
        return QIcon()


class ModeToolbar(QFrame):
    mode_changed = pyqtSignal(str)
    rotate_requested = pyqtSignal(float)
    flip_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet('''
            QFrame {
                background-color: rgba(12, 18, 30, 235);
                border: 1px solid #2a3a50;
                border-radius: 8px;
            }
        ''')
        self.setFixedWidth(52)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._buttons = {}
        self._current_mode = 'select'

        for mode, tip in [('select', 'Select Mode (S)'), ('edit', 'Edit Mode (E)'), ('delete', 'Delete Mode (D)')]:
            btn = QPushButton()
            btn.setIcon(toolbar_icon(mode, 22))
            btn.setIconSize(QSize(22, 22))
            btn.setFixedSize(36, 36)
            btn.setCheckable(True)
            btn.setChecked(mode == 'select')
            btn.setToolTip(tip)
            btn.setStyleSheet(self._btn_style(mode == 'select'))
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            layout.addWidget(btn)
            self._buttons[mode] = btn

        layout.addWidget(self._separator())

        for key, icon_name, tip, slot in [
            ('rotate', 'rotate', 'Rotate Selection 90° (or whole canvas if nothing selected)',
             lambda: self.rotate_requested.emit(90.0)),
            ('flip_h', 'flip_h', 'Flip Selection Horizontally', lambda: self.flip_requested.emit('horizontal')),
            ('flip_v', 'flip_v', 'Flip Selection Vertically', lambda: self.flip_requested.emit('vertical')),
        ]:
            btn = QPushButton()
            btn.setIcon(toolbar_icon(icon_name, 22))
            btn.setIconSize(QSize(22, 22))
            btn.setFixedSize(36, 36)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(slot)
            layout.addWidget(btn)
            self._buttons[key] = btn

        self.adjustSize()

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color: #2a3a50;')
        sep.setFixedHeight(1)
        return sep

    @staticmethod
    def _btn_style(active: bool) -> str:
        if active:
            return 'QPushButton { background-color: #1c78b4; border-radius: 8px; border: none; }'
        return '''
            QPushButton {
                background-color: #1a2435;
                border-radius: 8px;
                border: 1px solid #2a3a50;
            }
            QPushButton:hover {
                background-color: #243045;
                border: 1px solid #3a5068;
            }
            QPushButton:pressed {
                background-color: #152030;
            }
        '''

    def _set_mode(self, mode: str):
        self._current_mode = mode
        for m in ('select', 'edit', 'delete'):
            btn = self._buttons[m]
            btn.setChecked(m == mode)
            btn.setStyleSheet(self._btn_style(m == mode))
        self.mode_changed.emit(mode)

    def set_mode(self, mode: str):
        self._set_mode(mode)

    @property
    def current_mode(self) -> str:
        return self._current_mode
