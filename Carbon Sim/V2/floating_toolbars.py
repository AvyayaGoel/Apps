"""Floating toolbar widgets that overlay the canvas: tool-mode icons,
the bond-type picker popup, the horizontal action bar (undo/redo, bond
type, chain tool, formal charge, cleanup), and the small zoom control.

These are all frameless QFrame popups/panels positioned by MainWindow
(see MainWindow._position_panels) rather than embedded in a layout column.
Split out of main_window.py because this group of widgets is self-contained
(depends only on config.py + generic Qt, nothing from MainWindow itself)
and was a large, steadily-growing chunk of an already-large file.

Imports: config.py (constants/colors/bond data)
"""
import logging
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QPoint, QByteArray, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFrame, QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from config import BOND_DISPLAY_TO_LETTER, BOND_LETTER_TO_DISPLAY, BOND_TYPES

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
        <path d="M3 17 L8 8 L13 17 L18 8 L21 13"
              fill="none" stroke="#aebdd6" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="3" cy="17" r="1.8" fill="#4a9fd0"/>
        <circle cx="8" cy="8" r="1.8" fill="#4a9fd0"/>
        <circle cx="13" cy="17" r="1.8" fill="#4a9fd0"/>
        <circle cx="18" cy="8" r="1.8" fill="#4a9fd0"/>
        </svg>''',
}
_icon_cache: Dict[str, QIcon] = {}


def toolbar_icon(name: str, size: int = 22) -> QIcon:
    """Render one of _TOOLBAR_ICONS to a QIcon, cached by (name, size)."""
    key = f'{name}@{size}'
    if key in _icon_cache:
        return _icon_cache[key]
    svg = _TOOLBAR_ICONS.get(name)
    if not svg:
        logger.warning(f'toolbar_icon: unknown icon name "{name}"')
        return QIcon()
    try:
        renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
        pix = QPixmap(size * 4, size * 4)  # render at 4x then let QIcon downscale, for crisp small icons
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


class BondMenu(QFrame):
    """Frameless popup listing every bond type, opened beside the bond
    button. Click a row to pick that bond type; clicking elsewhere or
    pressing Escape closes it without changing the selection."""
    bond_type_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
            self.setStyleSheet('''
                QFrame {
                    background-color: rgba(12, 18, 30, 245);
                    border: 1px solid #2a3a50;
                    border-radius: 8px;
                }
            ''')
            layout = QVBoxLayout(self)
            layout.setSpacing(2)
            layout.setContentsMargins(6, 6, 6, 6)
            self._buttons: Dict[str, QPushButton] = {}
            for bt in BOND_TYPES:
                btn = QPushButton(f"  {bt['glyph']}   {bt['name']}")
                btn.setFixedSize(170, 38)
                btn.setToolTip(bt['tooltip'])
                btn.setStyleSheet(self._row_style(False))
                btn.clicked.connect(lambda checked, letter=bt['letter']: self._pick(letter))
                layout.addWidget(btn)
                self._buttons[bt['letter']] = btn
        except Exception as e:
            logger.exception(f"BondMenu init error: {e}")

    @staticmethod
    def _row_style(active: bool) -> str:
        if active:
            return '''
                QPushButton {
                    background-color: #1c78b4;
                    color: white;
                    border-radius: 6px;
                    font-size: 14px;
                    text-align: left;
                    border: none;
                }
            '''
        return '''
            QPushButton {
                background-color: transparent;
                color: #c0d0e0;
                border-radius: 6px;
                font-size: 14px;
                text-align: left;
                border: none;
            }
            QPushButton:hover {
                background-color: #243045;
                color: #dce8ff;
            }
        '''

    def _pick(self, letter: str):
        try:
            self.bond_type_selected.emit(letter)
            self.close()
        except Exception as e:
            logger.exception(f"BondMenu pick error: {e}")

    def set_active(self, letter: str):
        try:
            for lt, btn in self._buttons.items():
                btn.setStyleSheet(self._row_style(lt == letter))
        except Exception as e:
            logger.exception(f"BondMenu set_active error: {e}")

    def open_beside(self, anchor_widget: QWidget):
        """Position to the right of anchor_widget (its parent's global
        coordinates), vertically centered on it."""
        try:
            global_pos = anchor_widget.mapToGlobal(QPoint(anchor_widget.width() + 6, 0))
            self.adjustSize()
            y_offset = (anchor_widget.height() - self.height()) // 2
            self.move(global_pos.x(), global_pos.y() + y_offset)
            self.show()
        except Exception as e:
            logger.exception(f"BondMenu open_beside error: {e}")


class ModeToolbar(QFrame):
    """Vertical floating panel on the left side of the canvas — mirrors
    ElementPanel's look exactly (same frame style, same fixed narrow width,
    vertically-stacked square buttons). Holds the Select/Edit/Delete modes
    plus one-shot selection transforms (Rotate / Flip), which are the
    chemistry-drawing equivalent of a transform tool palette: reorienting a
    drawn fragment before joining it to the rest of the molecule is a real,
    everyday action (e.g. flipping a substituent to avoid overlapping bond
    lines, or rotating a ring to align it before forming a bond) — distinct
    from Show Grid / Snap / Smart Join, which are already in the View menu."""
    mode_changed = pyqtSignal(str)
    rotate_requested = pyqtSignal(float)
    flip_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        try:
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

            mode_icons = [('select', 'Select Mode (S)'), ('edit', 'Edit Mode (E)'),
                          ('delete', 'Delete Mode (D)')]
            for mode, tip in mode_icons:
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

            transform_icons = [
                ('rotate', 'rotate', 'Rotate Selection 90° (or whole canvas if nothing selected)',
                 lambda: self.rotate_requested.emit(90.0)),
                ('flip_h', 'flip_h', 'Flip Selection Horizontally', lambda: self.flip_requested.emit('horizontal')),
                ('flip_v', 'flip_v', 'Flip Selection Vertically', lambda: self.flip_requested.emit('vertical')),
            ]
            for key, icon_name, tip, slot in transform_icons:
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
        except Exception as e:
            logger.exception(f"ModeToolbar init error: {e}")

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
            return '''
                QPushButton {
                    background-color: #1c78b4;
                    border-radius: 8px;
                    border: none;
                }
            '''
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
        try:
            self._current_mode = mode
            for m in ('select', 'edit', 'delete'):
                btn = self._buttons[m]
                btn.setChecked(m == mode)
                btn.setStyleSheet(self._btn_style(m == mode))
            self.mode_changed.emit(mode)
        except Exception as e:
            logger.exception(f"ModeToolbar set_mode error: {e}")

    def set_mode(self, mode: str):
        self._set_mode(mode)

    @property
    def current_mode(self) -> str:
        return self._current_mode


class ActionToolbar(QFrame):
    """Horizontal floating panel, top-centered above the canvas, holding
    Undo/Redo, the bond-type picker, the formal charge +/- toggles, and
    Clean Up. Zoom lives on the canvas itself; mode buttons live in
    ModeToolbar on the left."""
    bond_mode_changed = pyqtSignal(str)
    chain_toggled = pyqtSignal(bool)
    edit_mode_requested = pyqtSignal()
    clear_up_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    formal_charge_toggled = pyqtSignal(str)  # '+' or '-' or '' (untoggled)

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setStyleSheet('''
                QFrame {
                    background-color: rgba(12, 18, 30, 235);
                    border: 1px solid #2a3a50;
                    border-radius: 8px;
                }
            ''')
            layout = QHBoxLayout(self)
            layout.setSpacing(8)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self._buttons = {}
            self._edit_mode_active = False
            self._formal_charge_sign: Optional[str] = None
            self._chain_active = False

            for action, icon, tip in [('undo', '↶', 'Undo (Ctrl+Z)'), ('redo', '↪', 'Redo (Ctrl+Y)')]:
                btn = QPushButton(icon)
                btn.setFixedSize(40, 40)
                btn.setToolTip(tip)
                btn.setEnabled(False)
                btn.setStyleSheet(self._btn_style(False))
                if action == 'undo':
                    btn.clicked.connect(self.undo_requested.emit)
                else:
                    btn.clicked.connect(self.redo_requested.emit)
                layout.addWidget(btn)
                self._buttons[action] = btn

            layout.addWidget(self._separator())

            self.bond_btn = QPushButton('━')
            self.bond_btn.setFixedSize(40, 40)
            self.bond_btn.setStyleSheet(self._btn_style(False))
            self.bond_btn.setToolTip('Bond Type (click for menu, or 1\u20135)')
            self.bond_btn.clicked.connect(self._open_bond_menu)
            layout.addWidget(self.bond_btn)
            self._bond_menu = BondMenu(self)
            self._bond_menu.bond_type_selected.connect(self._on_bond_type_picked)
            self._bond_menu.set_active('S')

            self.chain_btn = QPushButton()
            self.chain_btn.setIcon(toolbar_icon('chain', 20))
            self.chain_btn.setIconSize(QSize(20, 20))
            self.chain_btn.setFixedSize(40, 40)
            self.chain_btn.setCheckable(True)
            self.chain_btn.setToolTip('Chain Tool — click and drag to grow a carbon chain')
            self.chain_btn.setStyleSheet(self._btn_style(False))
            self.chain_btn.clicked.connect(self._toggle_chain)
            layout.addWidget(self.chain_btn)

            layout.addWidget(self._separator())

            self.charge_plus_btn = QPushButton('⊕')
            self.charge_plus_btn.setFixedSize(40, 40)
            self.charge_plus_btn.setCheckable(True)
            self.charge_plus_btn.setEnabled(False)
            self.charge_plus_btn.setToolTip(
                'Add positive formal charge — toggle on, then click an atom (Edit mode only)')
            self.charge_plus_btn.setStyleSheet(self._charge_btn_style(False, False))
            self.charge_plus_btn.clicked.connect(lambda: self._toggle_charge('+'))
            layout.addWidget(self.charge_plus_btn)

            self.charge_minus_btn = QPushButton('⊖')
            self.charge_minus_btn.setFixedSize(40, 40)
            self.charge_minus_btn.setCheckable(True)
            self.charge_minus_btn.setEnabled(False)
            self.charge_minus_btn.setToolTip(
                'Add negative formal charge — toggle on, then click an atom (Edit mode only)')
            self.charge_minus_btn.setStyleSheet(self._charge_btn_style(False, False))
            self.charge_minus_btn.clicked.connect(lambda: self._toggle_charge('-'))
            layout.addWidget(self.charge_minus_btn)

            layout.addWidget(self._separator())

            clear_btn = QPushButton('✨')
            clear_btn.setFixedSize(40, 40)
            clear_btn.setStyleSheet(self._btn_style(False))
            clear_btn.setToolTip('Clean Up Structure')
            clear_btn.clicked.connect(self.clear_up_requested.emit)
            layout.addWidget(clear_btn)

            self.adjustSize()

        except Exception as e:
            logger.exception(f"ActionToolbar init error: {e}")

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet('color: #2a3a50;')
        sep.setFixedWidth(2)
        return sep

    @staticmethod
    def _btn_style(active: bool) -> str:
        if active:
            return '''
                QPushButton {
                    background-color: #1c78b4;
                    color: white;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 16px;
                    border: none;
                }
            '''
        return '''
            QPushButton {
                background-color: #1a2435;
                color: #8ca0c0;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
                border: 1px solid #2a3a50;
            }
            QPushButton:hover {
                background-color: #243045;
                color: #c0d0e0;
                border: 1px solid #3a5068;
            }
            QPushButton:pressed {
                background-color: #152030;
            }
            QPushButton:disabled {
                color: #4a5568;
                border: 1px solid #2a3a50;
            }
        '''

    @staticmethod
    def _charge_btn_style(active: bool, enabled: bool) -> str:
        if active:
            return '''
                QPushButton {
                    background-color: #b4781c;
                    color: white;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 18px;
                    border: none;
                }
            '''
        if not enabled:
            return '''
                QPushButton {
                    background-color: #141c2a;
                    color: #3a4558;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 18px;
                    border: 1px solid #202c3e;
                }
            '''
        return '''
            QPushButton {
                background-color: #1a2435;
                color: #8ca0c0;
                border-radius: 8px;
                font-weight: bold;
                font-size: 18px;
                border: 1px solid #2a3a50;
            }
            QPushButton:hover {
                background-color: #243045;
                color: #dcb86a;
                border: 1px solid #6a4a1c;
            }
        '''

    def set_edit_mode_active(self, active: bool):
        """Called by MainWindow whenever the ModeToolbar's mode changes.
        Formal charge buttons only make sense once already in Edit mode, so
        they stay gated. The chain button (like the bond-type button) stays
        clickable from any mode — clicking it is itself a request to switch
        into Edit mode (see ActionToolbar.edit_mode_requested), rather than
        something that only becomes available after the fact."""
        try:
            self._edit_mode_active = active
            self.charge_plus_btn.setEnabled(active)
            self.charge_minus_btn.setEnabled(active)
            if not active and self._formal_charge_sign is not None:
                self._formal_charge_sign = None
                self.charge_plus_btn.setChecked(False)
                self.charge_minus_btn.setChecked(False)
            self.charge_plus_btn.setStyleSheet(
                self._charge_btn_style(self._formal_charge_sign == '+', active))
            self.charge_minus_btn.setStyleSheet(
                self._charge_btn_style(self._formal_charge_sign == '-', active))
            if not active and self._chain_active:
                self._chain_active = False
                self.chain_btn.setChecked(False)
            self.chain_btn.setStyleSheet(self._btn_style(self._chain_active))
        except Exception as e:
            logger.exception(f"ActionToolbar set_edit_mode_active error: {e}")

    def _toggle_charge(self, sign: str):
        try:
            if self._formal_charge_sign == sign:
                self._formal_charge_sign = None
            else:
                self._formal_charge_sign = sign
            self.charge_plus_btn.setChecked(self._formal_charge_sign == '+')
            self.charge_minus_btn.setChecked(self._formal_charge_sign == '-')
            self.charge_plus_btn.setStyleSheet(
                self._charge_btn_style(self._formal_charge_sign == '+', True))
            self.charge_minus_btn.setStyleSheet(
                self._charge_btn_style(self._formal_charge_sign == '-', True))
            if self._formal_charge_sign is not None and self._chain_active:
                self.untoggle_chain()
                self.chain_toggled.emit(False)
            self.formal_charge_toggled.emit(self._formal_charge_sign or '')
        except Exception as e:
            logger.exception(f"ActionToolbar _toggle_charge error: {e}")

    def untoggle_formal_charge(self):
        """Externally force both charge buttons off (e.g. canvas exited
        formal-charge mode because the user picked an element or left Edit
        mode) without re-emitting the toggle signal."""
        try:
            self._formal_charge_sign = None
            self.charge_plus_btn.setChecked(False)
            self.charge_minus_btn.setChecked(False)
            self.charge_plus_btn.setStyleSheet(
                self._charge_btn_style(False, self._edit_mode_active))
            self.charge_minus_btn.setStyleSheet(
                self._charge_btn_style(False, self._edit_mode_active))
        except Exception as e:
            logger.exception(f"ActionToolbar untoggle_formal_charge error: {e}")

    def _toggle_chain(self):
        try:
            self._chain_active = self.chain_btn.isChecked()
            self.chain_btn.setStyleSheet(self._btn_style(self._chain_active))
            if self._chain_active:
                self.edit_mode_requested.emit()
                if self._formal_charge_sign is not None:
                    self.untoggle_formal_charge()
                    self.formal_charge_toggled.emit('')
            self.chain_toggled.emit(self._chain_active)
        except Exception as e:
            logger.exception(f"ActionToolbar _toggle_chain error: {e}")

    def untoggle_chain(self):
        """Externally force the chain button off (e.g. canvas exited chain
        mode because tool mode left Edit) without re-emitting the toggle
        signal."""
        try:
            self._chain_active = False
            self.chain_btn.setChecked(False)
            self.chain_btn.setStyleSheet(self._btn_style(False))
        except Exception as e:
            logger.exception(f"ActionToolbar untoggle_chain error: {e}")

    def _open_bond_menu(self):
        try:
            self.edit_mode_requested.emit()
            self._bond_menu.open_beside(self.bond_btn)
        except Exception as e:
            logger.exception(f"ActionToolbar _open_bond_menu error: {e}")

    def _on_bond_type_picked(self, letter: str):
        try:
            self.set_bond_mode(letter)
            self.bond_mode_changed.emit(letter)
        except Exception as e:
            logger.exception(f"ActionToolbar _on_bond_type_picked error: {e}")

    def set_bond_mode(self, mode: str):
        try:
            if mode in BOND_LETTER_TO_DISPLAY:
                letter = mode
            elif mode in BOND_DISPLAY_TO_LETTER:
                letter = BOND_DISPLAY_TO_LETTER[mode]
            else:
                logger.warning(f"ActionToolbar.set_bond_mode: unknown mode '{mode}'")
                return
            glyph = BOND_LETTER_TO_DISPLAY[letter]
            self.bond_btn.setText(glyph)
            self._bond_menu.set_active(letter)
        except Exception as e:
            logger.exception(f"ActionToolbar set_bond_mode error: {e}")

    def set_undo_enabled(self, enabled: bool):
        if 'undo' in self._buttons:
            self._buttons['undo'].setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool):
        if 'redo' in self._buttons:
            self._buttons['redo'].setEnabled(enabled)


class CanvasZoomWidget(QFrame):
    """Small floating +/- zoom control docked inside a corner of the canvas
    itself (rather than the side toolbar)."""
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()

    def __init__(self, parent=None):
        try:
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
        except Exception as e:
            logger.exception(f"CanvasZoomWidget init error: {e}")
