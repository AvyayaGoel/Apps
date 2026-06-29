"""Floating action toolbar (Undo/Redo, bond type, chain, formal charge, cleanup, marquee mode)."""

import logging
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtWidgets import QFrame, QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from config import BOND_DISPLAY_TO_LETTER, BOND_LETTER_TO_DISPLAY, BOND_TYPES
from mode_toolbar import toolbar_icon

logger = logging.getLogger(__name__)


class BondMenu(QFrame):
    bond_type_selected = pyqtSignal(str)

    def __init__(self, parent=None):
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
        self._active_letter: Optional[str] = None
        for bt in BOND_TYPES:
            btn = QPushButton(f"  {bt['glyph']}   {bt['name']}")
            btn.setFixedSize(170, 38)
            btn.setToolTip(bt['tooltip'])
            btn.setStyleSheet(self._row_style(False))
            btn.clicked.connect(lambda checked, letter=bt['letter']: self._pick(letter))
            layout.addWidget(btn)
            self._buttons[bt['letter']] = btn

    @staticmethod
    def _row_style(active: bool, enabled: bool = True) -> str:
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
        if not enabled:
            return '''
                QPushButton {
                    background-color: transparent;
                    color: #4a5568;
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
        self.bond_type_selected.emit(letter)
        self.close()

    def set_active(self, letter: str):
        self._active_letter = letter
        for lt, btn in self._buttons.items():
            btn.setEnabled(True)
            btn.setStyleSheet(self._row_style(lt == letter))

    def set_enabled_types(self, allowed_letters: set):
        for lt, btn in self._buttons.items():
            is_allowed = lt in allowed_letters
            btn.setEnabled(is_allowed)
            btn.setStyleSheet(self._row_style(lt == self._active_letter, is_allowed))

    def open_beside(self, anchor_widget: QWidget):
        global_pos = anchor_widget.mapToGlobal(QPoint(anchor_widget.width() + 6, 0))
        self.adjustSize()
        y_offset = (anchor_widget.height() - self.height()) // 2
        self.move(global_pos.x(), global_pos.y() + y_offset)
        self.show()


class MarqueeMenu(QFrame):
    """Popup menu for selecting marquee selection mode."""
    mode_selected = pyqtSignal(str)  # 'rectangle', 'lasso'

    def __init__(self, parent=None):
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
        self._active_mode: Optional[str] = None

        modes = [
            ('rectangle', 'marquee_rect', '  Rectangle', 'Rectangle selection — drag a box around atoms'),
            ('lasso', 'marquee_lasso', '  Lasso', 'Lasso selection — freehand-drag around atoms'),
        ]
        for mode, icon_name, label, tip in modes:
            btn = QPushButton(label)
            btn.setIcon(toolbar_icon(icon_name, 18))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(170, 38)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._row_style(False))
            btn.clicked.connect(lambda checked, m=mode: self._pick(m))
            layout.addWidget(btn)
            self._buttons[mode] = btn

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
                    padding-left: 6px;
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
                padding-left: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #243045;
                color: #dce8ff;
            }
        '''

    def _pick(self, mode: str):
        self.mode_selected.emit(mode)
        self.close()

    def set_active(self, mode: str):
        self._active_mode = mode
        for m, btn in self._buttons.items():
            btn.setStyleSheet(self._row_style(m == mode))

    def open_beside(self, anchor_widget: QWidget):
        global_pos = anchor_widget.mapToGlobal(QPoint(anchor_widget.width() + 6, 0))
        self.adjustSize()
        y_offset = (anchor_widget.height() - self.height()) // 2
        self.move(global_pos.x(), global_pos.y() + y_offset)
        self.show()


class ActionToolbar(QFrame):
    bond_mode_changed = pyqtSignal(str)
    chain_toggled = pyqtSignal(bool)
    edit_mode_requested = pyqtSignal()
    clear_up_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    formal_charge_toggled = pyqtSignal(str)
    marquee_mode_changed = pyqtSignal(str)  # new signal

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
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._buttons = {}
        self._edit_mode_active = False
        self._formal_charge_sign: Optional[str] = None
        self._chain_active = False

        # Undo / Redo
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

        # Bond type
        self.bond_btn = QPushButton('━')
        self.bond_btn.setFixedSize(40, 40)
        self.bond_btn.setStyleSheet(self._btn_style(False))
        self.bond_btn.setToolTip('Bond Type (click for menu, or 1\u20135)')
        self.bond_btn.clicked.connect(self._open_bond_menu)
        layout.addWidget(self.bond_btn)
        self._bond_menu = BondMenu(self)
        self._bond_menu.bond_type_selected.connect(self._on_bond_type_picked)
        self._bond_menu.set_active('S')

        # Chain tool
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

        # Formal charge
        self.charge_plus_btn = QPushButton('⊕')
        self.charge_plus_btn.setFixedSize(40, 40)
        self.charge_plus_btn.setCheckable(True)
        self.charge_plus_btn.setEnabled(False)
        self.charge_plus_btn.setToolTip('Add positive formal charge — toggle on, then click an atom (Edit mode only)')
        self.charge_plus_btn.setStyleSheet(self._charge_btn_style(False, False))
        self.charge_plus_btn.clicked.connect(lambda: self._toggle_charge('+'))
        layout.addWidget(self.charge_plus_btn)

        self.charge_minus_btn = QPushButton('⊖')
        self.charge_minus_btn.setFixedSize(40, 40)
        self.charge_minus_btn.setCheckable(True)
        self.charge_minus_btn.setEnabled(False)
        self.charge_minus_btn.setToolTip('Add negative formal charge — toggle on, then click an atom (Edit mode only)')
        self.charge_minus_btn.setStyleSheet(self._charge_btn_style(False, False))
        self.charge_minus_btn.clicked.connect(lambda: self._toggle_charge('-'))
        layout.addWidget(self.charge_minus_btn)

        # Marquee mode
        self.marquee_btn = QPushButton()
        self.marquee_btn.setIcon(toolbar_icon('marquee_rect', 20))
        self.marquee_btn.setIconSize(QSize(20, 20))
        self.marquee_btn.setFixedSize(40, 40)
        self.marquee_btn.setStyleSheet(self._btn_style(False))
        self.marquee_btn.setToolTip('Marquee mode (click for menu)')
        self.marquee_btn.clicked.connect(self._open_marquee_menu)
        layout.addWidget(self.marquee_btn)
        self._marquee_menu = MarqueeMenu(self)
        self._marquee_menu.mode_selected.connect(self._on_marquee_mode_picked)
        self._marquee_menu.set_active('rectangle')
        self._current_marquee_mode = 'rectangle'

        layout.addWidget(self._separator())

        # Clean Up
        clear_btn = QPushButton('✨')
        clear_btn.setFixedSize(40, 40)
        clear_btn.setStyleSheet(self._btn_style(False))
        clear_btn.setToolTip('Clean Up Structure')
        clear_btn.clicked.connect(self.clear_up_requested.emit)
        layout.addWidget(clear_btn)

        self.adjustSize()

    # ---- separators and styles (unchanged) ----
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

    # ---- public API ----
    def set_edit_mode_active(self, active: bool):
        self._edit_mode_active = active
        self.charge_plus_btn.setEnabled(active)
        self.charge_minus_btn.setEnabled(active)
        if not active and self._formal_charge_sign is not None:
            self._formal_charge_sign = None
            self.charge_plus_btn.setChecked(False)
            self.charge_minus_btn.setChecked(False)
        self.charge_plus_btn.setStyleSheet(self._charge_btn_style(self._formal_charge_sign == '+', active))
        self.charge_minus_btn.setStyleSheet(self._charge_btn_style(self._formal_charge_sign == '-', active))
        if not active and self._chain_active:
            self._chain_active = False
            self.chain_btn.setChecked(False)
        self.chain_btn.setStyleSheet(self._btn_style(self._chain_active))

    def set_marquee_mode(self, mode: str):
        self._current_marquee_mode = mode
        icon_names = {'rectangle': 'marquee_rect', 'lasso': 'marquee_lasso'}
        self.marquee_btn.setIcon(toolbar_icon(icon_names.get(mode, 'marquee_rect'), 20))
        self._marquee_menu.set_active(mode)

    def _toggle_charge(self, sign: str):
        if self._formal_charge_sign == sign:
            self._formal_charge_sign = None
        else:
            self._formal_charge_sign = sign
        self.charge_plus_btn.setChecked(self._formal_charge_sign == '+')
        self.charge_minus_btn.setChecked(self._formal_charge_sign == '-')
        self.charge_plus_btn.setStyleSheet(self._charge_btn_style(self._formal_charge_sign == '+', True))
        self.charge_minus_btn.setStyleSheet(self._charge_btn_style(self._formal_charge_sign == '-', True))
        if self._formal_charge_sign is not None and self._chain_active:
            self.untoggle_chain()
            self.chain_toggled.emit(False)
        self.formal_charge_toggled.emit(self._formal_charge_sign or '')

    def untoggle_formal_charge(self):
        self._formal_charge_sign = None
        self.charge_plus_btn.setChecked(False)
        self.charge_minus_btn.setChecked(False)
        self.charge_plus_btn.setStyleSheet(self._charge_btn_style(False, self._edit_mode_active))
        self.charge_minus_btn.setStyleSheet(self._charge_btn_style(False, self._edit_mode_active))

    def _toggle_chain(self):
        self._chain_active = self.chain_btn.isChecked()
        self.chain_btn.setStyleSheet(self._btn_style(self._chain_active))
        if self._chain_active:
            self.edit_mode_requested.emit()
            if self._formal_charge_sign is not None:
                self.untoggle_formal_charge()
                self.formal_charge_toggled.emit('')
        self.chain_toggled.emit(self._chain_active)

    def untoggle_chain(self):
        self._chain_active = False
        self.chain_btn.setChecked(False)
        self.chain_btn.setStyleSheet(self._btn_style(False))

    def _open_bond_menu(self):
        self.edit_mode_requested.emit()
        self._bond_menu.open_beside(self.bond_btn)

    def _open_marquee_menu(self):
        self._marquee_menu.open_beside(self.marquee_btn)

    def _on_bond_type_picked(self, letter: str):
        self.set_bond_mode(letter)
        self.bond_mode_changed.emit(letter)

    def _on_marquee_mode_picked(self, mode: str):
        self.set_marquee_mode(mode)
        self.marquee_mode_changed.emit(mode)

    def set_bond_mode(self, mode: str):
        if mode in BOND_LETTER_TO_DISPLAY:
            letter = mode
        elif mode in BOND_DISPLAY_TO_LETTER:
            letter = BOND_DISPLAY_TO_LETTER[mode]
        else:
            return
        glyph = BOND_LETTER_TO_DISPLAY[letter]
        self.bond_btn.setText(glyph)
        self._bond_menu.set_active(letter)

    def set_undo_enabled(self, enabled: bool):
        if 'undo' in self._buttons:
            self._buttons['undo'].setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool):
        if 'redo' in self._buttons:
            self._buttons['redo'].setEnabled(enabled)
