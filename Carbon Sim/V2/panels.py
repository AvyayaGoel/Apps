"""All GUI panels and dialogs that were previously inside main_window.py."""

import logging
from typing import Optional, List, Set, Dict

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QParallelAnimationGroup,
    QEasingCurve, QPropertyAnimation
)
from PyQt6.QtGui import QColor
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QDialog, QGridLayout, QScrollArea, QStackedWidget, QTextEdit, QSizePolicy
)
from rdkit import Chem

from config import (
    COLORS, VALENCES, PERIODIC_ELEMENTS,
    STRUCTURE_TILE_W, STRUCTURE_TILE_THUMB_H, STRUCTURE_TILE_SPACING,
    PANEL_W
)
from structure_library import StructureLibrary, StructureEntry

logger = logging.getLogger(__name__)


# ---- Info Panel components ----

class FragmentCard(QFrame):
    clicked = pyqtSignal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('FragmentCard')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._atom_ids: Set[int] = set()
        self.setStyleSheet("""
            QFrame#FragmentCard {
                background-color: #0e1420;
                border: 1px solid #1e2a40;
                border-radius: 6px;
            }
            QFrame#FragmentCard:hover {
                border: 1px solid #3a5a82;
                background-color: #121a2a;
            }
            QFrame#FragmentCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        self._formula = QLabel()
        self._formula.setTextFormat(Qt.TextFormat.RichText)
        self._formula.setStyleSheet(
            'font-size: 14px; color: #f0f4ff; font-family: "Segoe UI", Arial, sans-serif;'
        )
        layout.addWidget(self._formula)

        self._name = QLabel()
        self._name.setStyleSheet('color: #8ca0c0; font-size: 10px; font-style: italic;')
        self._name.setWordWrap(True)
        layout.addWidget(self._name)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        self._mass = QLabel()
        self._mass.setStyleSheet('color: #a0b8d8; font-size: 11px;')
        meta.addWidget(self._mass)
        self._charge = QLabel()
        self._charge.setStyleSheet('color: #ff8c8c; font-size: 11px;')
        meta.addWidget(self._charge)
        self._badge = QLabel()
        self._badge.setStyleSheet("""
            color: #6eaaff;
            font-size: 11px;
            font-weight: bold;
            background-color: #1a2a40;
            border-radius: 4px;
            padding: 1px 6px;
        """)
        meta.addWidget(self._badge)
        meta.addStretch()
        layout.addLayout(meta)

        self._count = QLabel()
        self._count.setStyleSheet('color: #6a7a90; font-size: 10px;')
        layout.addWidget(self._count)

    def set_data(self, info: dict, index: int):
        self._atom_ids = info.get('atom_ids', set())
        self._formula.setText(f"<b>{index}. {info.get('formula_html', '—')}</b>")
        if info.get('name'):
            self._name.setText(info['name'])
            self._name.show()
        else:
            self._name.hide()
        self._mass.setText(f"{info.get('mass', 0.0):.2f} g/mol")
        if info.get('charge', 0) != 0:
            self._charge.setText(f"q={info['charge']:+d}")
            self._charge.show()
        else:
            self._charge.hide()
        count = info.get('count', 1)
        if count > 1:
            self._badge.setText(f'×{count}')
            self._badge.show()
        else:
            self._badge.hide()
        self._count.setText(
            f"{info.get('atom_count', 0)} atoms · {info.get('bond_count', 0)} bonds"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._atom_ids:
            self.clicked.emit(set(self._atom_ids))
            event.accept()
            return
        super().mousePressEvent(event)


class InspectorPanel(QFrame):
    molecule_card_clicked = pyqtSignal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('InspectorPanel')
        self.setStyleSheet("""
            #InspectorPanel {
                background-color: #0c121e;
            }
            #InspectorPanel QLabel {
                color: #b4c4e4;
                font-size: 12px;
                background: transparent;
                border: none;
            }
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(10, 12, 10, 12)

        header = QHBoxLayout()
        self._title = QLabel('Info Panel')
        self._title.setStyleSheet('font-size: 18px; font-weight: bold; color: #dce8ff;')
        header.addWidget(self._title)
        header.addStretch()
        self._layout.addLayout(header)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self._layout.addWidget(self._stack, stretch=1)

        # Page 0 – Empty
        self._page_empty = QWidget()
        empty_layout = QVBoxLayout(self._page_empty)
        empty_layout.setContentsMargins(0, 20, 0, 0)
        empty_lbl = QLabel('No data available')
        empty_lbl.setStyleSheet('color: #5a6a80; font-style: italic;')
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_lbl)
        self._stack.addWidget(self._page_empty)

        # Page 1 – Fragment list
        self._page_list = QScrollArea()
        self._page_list.setWidgetResizable(True)
        self._page_list.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        list_container = QWidget()
        self._list_layout = QVBoxLayout(list_container)
        self._list_layout.setSpacing(8)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._page_list.setWidget(list_container)
        self._list_cards: List[FragmentCard] = []
        self._stack.addWidget(self._page_list)

        # Page 2 – Detail view
        self._page_detail = QWidget()
        detail_layout = QVBoxLayout(self._page_detail)
        detail_layout.setSpacing(8)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._detail_formula = QLabel()
        self._detail_formula.setTextFormat(Qt.TextFormat.RichText)
        self._detail_formula.setStyleSheet(
            'font-size: 22px; color: #f0f4ff; margin: 4px 0; font-family: "Segoe UI", Arial, sans-serif;'
        )
        detail_layout.addWidget(self._detail_formula)

        name_row = QHBoxLayout()
        name_key = QLabel('Name:')
        name_key.setStyleSheet('color: #8ca0c0; font-weight: bold; font-size: 11px;')
        self._detail_name = QLabel('Fetching')
        self._detail_name.setStyleSheet('font-size: 12px; color: #8ca0c0; font-style: italic;')
        self._detail_name.setWordWrap(True)
        name_row.addWidget(name_key)
        name_row.addWidget(self._detail_name, 1)
        detail_layout.addLayout(name_row)

        self._prop_labels: Dict[str, QLabel] = {}
        self._prop_keys: Dict[str, QLabel] = {}
        prop_defs = [
            ('molar_mass', 'Molar Mass'),
            ('net_charge', 'Net Charge'),
            ('total_atoms', 'Total Atoms'),
            ('covalent_bonds', 'Covalent Bonds'),
            ('ionic_pairs', 'Ionic Pairs'),
            ('smiles', 'SMILES'),
        ]
        for key, label in prop_defs:
            row = QHBoxLayout()
            k = QLabel(f'{label}:')
            k.setStyleSheet('color: #8ca0c0; font-weight: bold; font-size: 11px;')
            v = QLabel('—')
            v.setStyleSheet('color: #dce8ff; font-size: 11px;')
            v.setWordWrap(True)
            row.addWidget(k)
            row.addWidget(v, 1)
            detail_layout.addLayout(row)
            self._prop_labels[key] = v
            self._prop_keys[key] = k

        self._detail_comp_title = QLabel('Composition')
        self._detail_comp_title.setStyleSheet(
            'color: #8ca0c0; font-weight: bold; font-size: 11px; margin-top: 4px;'
        )
        detail_layout.addWidget(self._detail_comp_title)
        self._detail_composition = QLabel()
        self._detail_composition.setStyleSheet('color: #a0b8d8; font-size: 11px;')
        self._detail_composition.setWordWrap(True)
        detail_layout.addWidget(self._detail_composition)

        self._atom_section = QWidget()
        atom_layout = QVBoxLayout(self._atom_section)
        atom_layout.setSpacing(4)
        atom_layout.setContentsMargins(0, 0, 0, 0)
        atom_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color: #2a3a50; margin: 4px 0;')
        atom_layout.addWidget(sep)

        atom_title = QLabel('Selected Atom')
        atom_title.setStyleSheet(
            'font-size: 12px; font-weight: bold; color: #6eaaff; margin-top: 2px;'
        )
        atom_layout.addWidget(atom_title)

        self._atom_labels: Dict[str, QLabel] = {}
        for key, label in [('element', 'Element'), ('valence', 'Valence'), ('formal_charge', 'Formal Charge')]:
            row = QHBoxLayout()
            k = QLabel(f'{label}:')
            k.setStyleSheet('color: #8ca0c0; font-size: 11px;')
            v = QLabel('—')
            v.setStyleSheet('color: #dce8ff; font-size: 11px;')
            row.addWidget(k)
            row.addWidget(v, 1)
            atom_layout.addLayout(row)
            self._atom_labels[key] = v
        detail_layout.addWidget(self._atom_section)
        detail_layout.addStretch()

        self._stack.addWidget(self._page_detail)

        self._fetch_timer = QTimer(self)
        self._fetch_timer.timeout.connect(self._animate_fetching)
        self._fetch_dots = 0

    def _animate_fetching(self):
        if self._stack.currentIndex() != 2:
            return
        self._fetch_dots = (self._fetch_dots + 1) % 4
        dots = '.' * self._fetch_dots
        self._detail_name.setText(f"Fetching{dots}")

    def _start_fetching(self):
        self._fetch_dots = 0
        self._detail_name.setText('Fetching')
        self._fetch_timer.start(400)

    def _stop_fetching(self):
        self._fetch_timer.stop()

    def set_case_1(self, fragments: List[dict]):
        self._title.setText('Molecules on Canvas')
        self._sync_list(fragments)
        self._stack.setCurrentIndex(1)

    def set_case_2(self, info: dict, atom=None, mol=None):
        self._title.setText('Selected Molecule')
        self._stack.setCurrentIndex(2)
        self._detail_formula.setText(f"<b>{info.get('formula_html', '—')}</b>")
        self._update_name_display(info)
        self._update_property_labels(info)
        self._update_ionic_pairs_row(info)
        self._update_smiles_row(info)
        self._update_composition_row(info)
        self._update_atom_detail(atom, mol)

    def _update_name_display(self, info: dict):
        if info.get('name'):
            self._stop_fetching()
            self._detail_name.setText(info['name'])
            self._detail_name.setStyleSheet('font-size: 12px; color: #dce8ff; font-style: italic;')
        elif info.get('atom_count', 0) <= 1:
            self._stop_fetching()
            self._detail_name.setText('—')
            self._detail_name.setStyleSheet('font-size: 12px; color: #5a6a80; font-style: italic;')
        else:
            self._start_fetching()
            self._detail_name.setStyleSheet('font-size: 12px; color: #8ca0c0; font-style: italic;')

    def _update_property_labels(self, info: dict):
        self._prop_labels['molar_mass'].setText(f"{info.get('mass', 0.0):.4f} g/mol")
        charge = info.get('charge', 0)
        self._prop_labels['net_charge'].setText(f"{charge:+d}" if charge != 0 else '0')
        self._prop_labels['total_atoms'].setText(str(info.get('atom_count', 0)))
        self._prop_labels['covalent_bonds'].setText(str(info.get('bond_count', 0)))

    def _update_ionic_pairs_row(self, info: dict):
        ionic = info.get('ionic_pairs', 0)
        if ionic is not None and ionic > 0:
            self._prop_labels['ionic_pairs'].setText(str(ionic))
            self._prop_labels['ionic_pairs'].show()
            self._prop_keys['ionic_pairs'].show()
        else:
            self._prop_labels['ionic_pairs'].hide()
            self._prop_keys['ionic_pairs'].hide()

    def _update_smiles_row(self, info: dict):
        smiles = info.get('smiles', '')
        if smiles:
            self._prop_labels['smiles'].setText(smiles)
            self._prop_labels['smiles'].show()
            self._prop_keys['smiles'].show()
        else:
            self._prop_labels['smiles'].hide()
            self._prop_keys['smiles'].hide()

    def _update_composition_row(self, info: dict):
        comp = info.get('composition')
        if comp:
            self._detail_comp_title.show()
            self._detail_composition.show()
            parts = [f'{el}: {n}' for el, n in sorted(comp.items())]
            self._detail_composition.setText('  ·  '.join(parts))
        else:
            self._detail_comp_title.hide()
            self._detail_composition.hide()

    def _update_atom_detail(self, atom, mol):
        if atom and mol:
            self._atom_section.show()
            self._atom_labels['element'].setText(atom.element)
            used = mol.total_bond_order(atom.id)
            max_v = VALENCES.get(atom.element, 4) + atom.formal_charge
            self._atom_labels['valence'].setText(f'{used} / {max_v}')
            self._atom_labels['formal_charge'].setText(
                f'{atom.formal_charge:+d}' if atom.formal_charge != 0 else '0'
            )
        else:
            self._atom_section.hide()

    def set_case_3(self, fragments: List[dict]):
        self._title.setText('Selected Molecules')
        self._sync_list(fragments)
        self._stack.setCurrentIndex(1)

    def set_empty(self):
        self._title.setText('Info Panel')
        self._stop_fetching()
        self._stack.setCurrentIndex(0)

    def update_fragment_name(self, name: str):
        if not name:
            return
        if self._stack.currentIndex() == 2:
            self._stop_fetching()
            self._detail_name.setText(name)
            self._detail_name.setStyleSheet('font-size: 12px; color: #dce8ff; font-style: italic;')

    def _sync_list(self, fragments: List[dict]):
        if self._list_layout.count() > 0:
            item = self._list_layout.itemAt(self._list_layout.count() - 1)
            if item.spacerItem():
                self._list_layout.removeItem(item)
        while len(self._list_cards) < len(fragments):
            card = FragmentCard()
            card.clicked.connect(self.molecule_card_clicked.emit)
            self._list_layout.addWidget(card)
            self._list_cards.append(card)
        for i, frag in enumerate(fragments):
            self._list_cards[i].set_data(frag, i + 1)
            self._list_cards[i].show()
        for i in range(len(fragments), len(self._list_cards)):
            self._list_cards[i].hide()
        self._list_layout.addStretch()


# ---- InfoPanel (outer container with tabs) ----

class InfoPanel(QFrame):
    collapse_changed = pyqtSignal(bool)
    structure_selected = pyqtSignal(object)
    molecule_card_clicked = pyqtSignal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._expanded_width = PANEL_W
        self._animating = False
        self.setFixedWidth(self._expanded_width)
        self.setObjectName('InfoPanel')
        self.setStyleSheet("""
            #InfoPanel {
                background-color: #0c121e;
                border-left: 1px solid #1e2a40;
            }
        """)

        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QStackedWidget()  # actually we want a QTabWidget, but we'll use QTabWidget for tabs
        # Let's use QTabWidget
        from PyQt6.QtWidgets import QTabWidget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background-color: #0c121e; }
            QTabBar::tab {
                background-color: #0c121e;
                color: #8ca0c0;
                padding: 7px 14px;
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #dce8ff;
                border-bottom: 2px solid #4a9fd0;
            }
            QTabBar::tab:hover {
                color: #c0d0ee;
            }
        """)
        self.inspector = InspectorPanel()
        self.inspector.molecule_card_clicked.connect(self.molecule_card_clicked.emit)
        self.structure_browser = StructureBrowserPanel()
        self.structure_browser.structure_selected.connect(self.structure_selected.emit)
        self._tabs.addTab(self.inspector, 'Inspector')
        self._tabs.addTab(self.structure_browser, 'Structures')
        self._tabs.currentChanged.connect(self._on_tab_changed)
        outer_layout.addWidget(self._tabs)

        self._width_anim = QPropertyAnimation(self, b"maximumWidth")
        self._width_anim.setDuration(250)
        self._width_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._width_anim.valueChanged.connect(self._on_width_anim_value)

        self._min_width_anim = QPropertyAnimation(self, b"minimumWidth")
        self._min_width_anim.setDuration(250)
        self._min_width_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._anim_group = QParallelAnimationGroup()
        self._anim_group.addAnimation(self._width_anim)
        self._anim_group.addAnimation(self._min_width_anim)
        self._anim_group.finished.connect(self._on_anim_finished)

    def _on_width_anim_value(self, value):
        if value < 50:
            self._tabs.hide()
        else:
            self._tabs.show()
        self.collapse_changed.emit(self._collapsed)

    def _on_tab_changed(self, index: int):
        if index == 1:
            self.structure_browser._schedule_lazy_load()

    def _on_anim_finished(self):
        self._animating = False
        if self._collapsed:
            self._tabs.hide()
            self.setMaximumWidth(0)
            self.setMinimumWidth(0)
            self.setFixedWidth(0)
        else:
            self._tabs.show()
            self.setMaximumWidth(16777215)
            self.setMinimumWidth(0)
            self.setFixedWidth(self._expanded_width)
        self.collapse_changed.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapse(self):
        if self._animating:
            return None
        self._animating = True
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._width_anim.setStartValue(self.width())
            self._width_anim.setEndValue(0)
            self._min_width_anim.setStartValue(self.width())
            self._min_width_anim.setEndValue(0)
        else:
            self.setMaximumWidth(0)
            self.setMinimumWidth(0)
            self._width_anim.setStartValue(0)
            self._width_anim.setEndValue(self._expanded_width)
            self._min_width_anim.setStartValue(0)
            self._min_width_anim.setEndValue(self._expanded_width)
            self._tabs.show()
        self._anim_group.start()
        return self._collapsed

    # Forwarded Inspector API
    def set_case_1(self, fragments: List[dict]):
        self.inspector.set_case_1(fragments)

    def set_case_2(self, info: dict, atom=None, mol=None):
        self.inspector.set_case_2(info, atom, mol)

    def set_case_3(self, fragments: List[dict]):
        self.inspector.set_case_3(fragments)

    def set_empty(self):
        self.inspector.set_empty()

    def update_fragment_name(self, name: str):
        self.inspector.update_fragment_name(name)


# ---- Element Panel ----

class ElementPanel(QFrame):
    element_selected = pyqtSignal(str)
    periodic_requested = pyqtSignal()
    size_changed = pyqtSignal()
    PERMANENT = ['H', 'C', 'N', 'O', 'S', 'Cl', 'P', 'F', 'Br', 'I']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(12, 18, 30, 235);
                border: 1px solid #2a3a50;
                border-radius: 8px;
            }
            QPushButton {
                background-color: transparent;
                color: #e6eaf0;
                border: 1px solid #2a3a50;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover {
                border: 1px solid #4a9fd0;
                background-color: rgba(40, 60, 90, 180);
            }
            QPushButton:checked {
                border: 2px solid #4a9fd0;
                background-color: rgba(30, 50, 80, 200);
            }
        """)
        self.setFixedWidth(52)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(3)
        self._layout.setContentsMargins(5, 8, 5, 8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._buttons: dict[str, QPushButton] = {}
        self._current = 'C'
        self._recent: list[str] = []
        self._max_recent = 2
        for el in self.PERMANENT:
            self._add_btn(el, self._layout)
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        self._sep.setStyleSheet('color: #2a3a50;')
        self._sep.setFixedHeight(2)
        self._layout.addWidget(self._sep)
        self._recent_widget = QWidget()
        self._recent_layout = QVBoxLayout(self._recent_widget)
        self._recent_layout.setSpacing(3)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._layout.addWidget(self._recent_widget)
        for el in self._load_recent_elements():
            if el in self.PERMANENT or el in self._buttons:
                continue
            if len(self._recent) >= self._max_recent:
                break
            self._recent.append(el)
            self._add_btn(el, self._recent_layout)
        pt_btn = QPushButton('PT')
        pt_btn.setFixedSize(36, 36)
        pt_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2a40;
                color: #8ca0c0;
                font-size: 10px;
                border: 1px solid #3a5068;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2a3a58;
                color: #dce8ff;
            }
        """)
        pt_btn.setToolTip('Periodic Table')
        pt_btn.clicked.connect(self.periodic_requested.emit)
        self._layout.addWidget(pt_btn)
        self._update_size()

    def _add_btn(self, el: str, layout):
        btn = QPushButton(el)
        btn.setFixedSize(36, 36)
        color = QColor(*COLORS.get(el, (200, 200, 200)))
        brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
        text_color = '#060c16' if brightness > 160 else '#e6ecff'
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color.name()};
                color: {text_color};
                border: 1px solid rgba(0,0,0,0.3);
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                border: 1px solid rgba(255,255,255,0.8);
            }}
            QPushButton:checked {{
                border: 2px solid #4a9fd0;
            }}
        """
        )
        btn.setCheckable(True)
        btn.setChecked(el == self._current)
        btn.clicked.connect(lambda checked, elem=el: self._select(elem))
        layout.addWidget(btn)
        self._buttons[el] = btn
        return btn

    def _select(self, el: str):
        self._current = el
        for b in self._buttons.values():
            b.setChecked(False)
        if el in self._buttons:
            self._buttons[el].setChecked(True)
        self.element_selected.emit(el)

    def add_recent(self, el: str):
        if el in self.PERMANENT:
            return
        if el in self._recent:
            self._recent.remove(el)
            self._recent.append(el)
            self._update_size()
            self._save_recent_elements()
            return
        if len(self._recent) >= self._max_recent:
            old = self._recent.pop(0)
            if old in self._buttons:
                btn = self._buttons.pop(old)
                self._recent_layout.removeWidget(btn)
                btn.deleteLater()
        self._recent.append(el)
        self._add_btn(el, self._recent_layout)
        self._update_size()
        self._save_recent_elements()

    @staticmethod
    def _load_recent_elements() -> list[str]:
        from PyQt6.QtCore import QSettings
        settings = QSettings('CarbonSim', 'CarbonSimulator')
        recents = settings.value('recentElements', [])
        if isinstance(recents, str):
            return [recents] if recents else []
        if recents is None:
            return []
        return [str(r) for r in recents if r]

    def _save_recent_elements(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings('CarbonSim', 'CarbonSimulator')
        settings.setValue('recentElements', self._recent)

    def select_element(self, el: str):
        self._select(el)

    def _update_size(self):
        has_recent = len(self._recent) > 0
        self._sep.setVisible(has_recent)
        self._recent_widget.setVisible(has_recent)
        self._layout.invalidate()
        self._layout.activate()
        self._recent_widget.adjustSize()
        m = self._layout.contentsMargins()
        base_h = m.top() + m.bottom()
        base_h += len(self.PERMANENT) * (36 + 3)
        base_h -= 3
        if has_recent:
            base_h += 2 + 3
        base_h += len(self._recent) * (36 + 3)
        if len(self._recent) > 0:
            base_h -= 3
        base_h += 36 + 3
        self.setFixedHeight(base_h)
        self.setFixedWidth(52)
        self.size_changed.emit()


# ---- Periodic Dialog ----

class PeriodicDialog(QDialog):
    element_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Periodic Table')
        self.setMinimumSize(560, 400)
        self.resize(620, 440)
        self.setStyleSheet('background-color: #181c28;')

        pt = Chem.GetPeriodicTable()
        self._buttons: dict[str, QPushButton] = {}
        self._names: dict[str, str] = {}
        for el, _row, _col in PERIODIC_ELEMENTS:
            try:
                self._names[el] = pt.GetElementName(pt.GetAtomicNumber(el)).lower()
            except Exception:
                self._names[el] = ''

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        search_bar = QWidget()
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(12, 10, 12, 6)
        self._search = QLineEdit()
        self._search.setPlaceholderText('Search by symbol or name…  (e.g. "Na" or "sodium")')
        self._search.setStyleSheet(
            'QLineEdit { background-color: #0e1422; color: #dce8ff; border: 1px solid #2a3a50; '
            'border-radius: 4px; padding: 6px 10px; font-size: 13px; }'
            'QLineEdit:focus { border: 1px solid #5a7ab0; }'
        )
        self._search.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self._search)
        layout.addWidget(search_bar)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea { border: none; background: #181c28; }')
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(4)
        grid.setContentsMargins(12, 6, 12, 12)
        for el, row, col in PERIODIC_ELEMENTS:
            btn = QPushButton(el)
            btn.setFixedSize(40, 32)
            btn.setToolTip(self._names.get(el, '').capitalize() or el)
            color = QColor(*COLORS.get(el, (160, 160, 160)))
            brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            text_color = 'black' if brightness > 160 else 'white'
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color.name()};
                    color: {text_color};
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 4px;
                    border: 1px solid #3a4560;
                }}
                QPushButton:hover {{
                    border: 2px solid #6a85c0;
                }}
            """
            )
            btn.clicked.connect(lambda checked, elem=el: self._select(elem))
            grid.addWidget(btn, row, col)
            self._buttons[el] = btn
        for row, text in [(8, 'La-Lu'), (9, 'Ac-Lr')]:
            lbl = QLabel(text)
            lbl.setStyleSheet('color: #8ca0c0; font-size: 10px; background: transparent; border: none;')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, row, 2)
        grid.setRowStretch(10, 1)
        grid.setColumnStretch(18, 1)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self._search.setFocus()

    def _apply_filter(self, text: str):
        q = text.strip().lower()
        for el, btn in self._buttons.items():
            if not q:
                btn.setVisible(True)
                continue
            match = q in el.lower() or q in self._names.get(el, '')
            btn.setVisible(match)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            visible = [el for el, btn in self._buttons.items() if btn.isVisible()]
            if len(visible) == 1:
                self._select(visible[0])
                return
        super().keyPressEvent(event)

    def _select(self, element: str):
        self.element_selected.emit(element)
        self.accept()


# ---- Structure Browser ----

class StructureTile(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, entry: StructureEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._thumb_loaded = False
        self.setObjectName('StructureTile')
        self.setFixedWidth(STRUCTURE_TILE_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            #StructureTile {
                background-color: #0e1420;
                border: 1px solid #1e2a40;
                border-radius: 6px;
            }
            #StructureTile:hover {
                border: 1px solid #4a9fd0;
                background-color: #121c2c;
            }
            #StructureTile QLabel {
                background: transparent;
                border: none;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        self._thumb = QSvgWidget()
        self._thumb.setFixedSize(STRUCTURE_TILE_W - 12, STRUCTURE_TILE_THUMB_H)
        layout.addWidget(self._thumb)

        self._name = QLabel(entry.name)
        self._name.setWordWrap(True)
        self._name.setStyleSheet('font-size: 11px; font-weight: bold; color: #dce8ff;')
        layout.addWidget(self._name)

        self._formula = QLabel(entry.formula_html)
        self._formula.setTextFormat(Qt.TextFormat.RichText)
        self._formula.setStyleSheet('font-size: 12px; color: #6eaaff;')
        layout.addWidget(self._formula)

        elements_text = ' · '.join(f'{el}:{n}' for el, n in sorted(entry.elements.items()))
        self._elements = QLabel(elements_text)
        self._elements.setWordWrap(True)
        self._elements.setStyleSheet('font-size: 9px; color: #8ca0c0;')
        layout.addWidget(self._elements)

    def ensure_thumb_loaded(self):
        if self._thumb_loaded:
            return
        self._thumb_loaded = True
        try:
            svg = self.entry.svg(width=STRUCTURE_TILE_W - 12, height=STRUCTURE_TILE_THUMB_H)
            if svg:
                self._thumb.load(svg.encode('utf-8'))
        except Exception as e:
            logger.exception(f'StructureTile thumb load error for {self.entry.name}: {e}')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.entry)
        super().mousePressEvent(event)


class StructureBrowserPanel(QFrame):
    structure_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('StructureBrowserPanel')
        self.setStyleSheet("""
            #StructureBrowserPanel { background-color: #0c121e; }
            #StructureBrowserPanel QLabel { background: transparent; border: none; }
            QLineEdit {
                background-color: #0a101c;
                color: #dce8ff;
                border: 1px solid #2a3a50;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #4a9fd0; }
        """)
        try:
            self.library = StructureLibrary()
        except Exception as e:
            logger.exception(f'StructureBrowserPanel: failed to load StructureLibrary: {e}')
            self.library = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText('Search structures…')
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._count_label = QLabel('')
        self._count_label.setStyleSheet('font-size: 10px; color: #5a6a80;')
        layout.addWidget(self._count_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(14)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, stretch=1)

        self._category_widgets: Dict[str, QWidget] = {}
        self._category_bodies: Dict[str, QWidget] = {}
        self._category_headers: Dict[str, QPushButton] = {}
        self._category_expanded: Dict[str, bool] = {}
        self._category_grids: Dict[str, QGridLayout] = {}
        self._category_entries: Dict[str, list] = {}
        self._all_tiles: List[StructureTile] = []
        self._current_cols = self._compute_cols()
        self._build_categorized_view()

        self._lazy_timer = QTimer(self)
        self._lazy_timer.setSingleShot(True)
        self._lazy_timer.timeout.connect(self._load_visible_thumbnails)
        self._scroll.verticalScrollBar().valueChanged.connect(self._schedule_lazy_load)
        QTimer.singleShot(0, self._load_visible_thumbnails)

    def _schedule_lazy_load(self):
        self._lazy_timer.start(60)

    def _compute_cols(self) -> int:
        try:
            scrollbar_w = self._scroll.verticalScrollBar().sizeHint().width() if hasattr(self, '_scroll') else 18
        except Exception:
            scrollbar_w = 18
        outer_margins = 10 + 10
        grid_margins = 2 + 2
        tile_border_overhead = 2
        available = PANEL_W - outer_margins - grid_margins - scrollbar_w
        effective_tile_w = STRUCTURE_TILE_W + tile_border_overhead
        n = 1
        while (n + 1) * effective_tile_w + n * STRUCTURE_TILE_SPACING <= available:
            n += 1
        return n

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_lazy_load()
        self._reflow_if_needed()

    def _reflow_if_needed(self):
        new_cols = self._compute_cols()
        if new_cols == self._current_cols:
            return
        self._current_cols = new_cols
        for category, grid in self._category_grids.items():
            entries = self._category_entries[category]
            tiles_by_name = {t.entry.name: t for t in self._all_tiles if t.entry.category == category}
            for i, entry in enumerate(entries):
                tile = tiles_by_name.get(entry.name)
                if tile is not None:
                    grid.addWidget(tile, i // new_cols, i % new_cols)

    def _load_visible_thumbnails(self):
        viewport_rect = self._scroll.viewport().rect()
        buffer_px = STRUCTURE_TILE_THUMB_H * 2
        check_rect = viewport_rect.adjusted(0, -buffer_px, 0, buffer_px)
        for tile in self._all_tiles:
            if tile._thumb_loaded or not tile.isVisible():
                continue
            top_left = tile.mapTo(self._scroll.viewport(), tile.rect().topLeft())
            tile_rect_in_viewport = tile.rect()
            tile_rect_in_viewport.moveTopLeft(top_left)
            if check_rect.intersects(tile_rect_in_viewport):
                tile.ensure_thumb_loaded()

    def _build_categorized_view(self):
        if self.library is None:
            empty_lbl = QLabel('Structure library unavailable.')
            empty_lbl.setStyleSheet('color: #5a6a80; font-style: italic;')
            self._content_layout.addWidget(empty_lbl)
            return
        cols = self._current_cols
        for category in self.library.categories():
            entries = self.library.entries_for_category(category)
            if not entries:
                continue
            self._build_category_section(category, entries, cols)
        self._content_layout.addStretch()
        total = len(self._all_tiles)
        self._count_label.setText(f'{total} structures in {len(self._category_widgets)} categories')

    def _build_category_section(self, category: str, entries: list, cols: int):
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        header = QPushButton(f'▸  {category}   ·   {len(entries)}')
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet("""
            QPushButton {
                text-align: left;
                font-size: 12px;
                font-weight: bold;
                color: #6eaaff;
                background-color: #101826;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background-color: #15203a;
                color: #8cc4ff;
            }
        """)
        section_layout.addWidget(header)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setSpacing(STRUCTURE_TILE_SPACING)
        grid.setContentsMargins(2, 2, 2, 2)
        for i, entry in enumerate(entries):
            tile = StructureTile(entry)
            tile.clicked.connect(self._on_tile_clicked)
            grid.addWidget(tile, i // cols, i % cols)
            self._all_tiles.append(tile)
        grid_host.hide()
        section_layout.addWidget(grid_host)

        header.clicked.connect(lambda: self._toggle_category(category))
        self._content_layout.addWidget(section)
        self._category_widgets[category] = section
        self._category_bodies[category] = grid_host
        self._category_headers[category] = header
        self._category_expanded[category] = False
        self._category_grids[category] = grid
        self._category_entries[category] = entries

    def _toggle_category(self, category: str, expand: Optional[bool] = None):
        body = self._category_bodies.get(category)
        header = self._category_headers.get(category)
        if body is None or header is None:
            return
        new_state = (not self._category_expanded[category]) if expand is None else expand
        self._category_expanded[category] = new_state
        body.setVisible(new_state)
        arrow = '▾' if new_state else '▸'
        label = header.text().split('  ', 1)[1] if '  ' in header.text() else header.text()
        header.setText(f'{arrow}  {label}')
        if new_state:
            self._schedule_lazy_load()

    def _on_search_changed(self, text: str):
        if self.library is None:
            return
        query = text.strip().lower()
        if not query:
            for category, section in self._category_widgets.items():
                section.show()
                self._toggle_category(category, expand=False)
            for tile in self._all_tiles:
                tile.show()
            self._count_label.setText(
                f'{len(self._all_tiles)} structures in {len(self._category_widgets)} categories')
            return
        matches = {e.name for e in self.library.search(query)}
        visible_count = 0
        section_has_match: Dict[str, bool] = dict.fromkeys(self._category_widgets, False)
        for tile in self._all_tiles:
            is_match = tile.entry.name in matches
            tile.setVisible(is_match)
            if is_match:
                section_has_match[tile.entry.category] = True
                visible_count += 1
        for category, section in self._category_widgets.items():
            has_match = section_has_match.get(category, False)
            section.setVisible(has_match)
            self._toggle_category(category, expand=has_match)
        self._count_label.setText(f'{visible_count} matching structures')

    def _on_tile_clicked(self, entry: StructureEntry):
        self.structure_selected.emit(entry)


# ---- Help Overlay ----

class HelpOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('HelpOverlayFrame')
        self.setStyleSheet("""
            QFrame#HelpOverlayFrame {
                background-color: rgba(20, 24, 36, 235);
                border-radius: 16px;
                border: 2px solid #586070;
            }
        """)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(36)

        self._mode_sections: dict[str, list[QLabel]] = {'select': [], 'edit': [], 'delete': []}

        col1 = self._make_section([
            ('section', '=== Help / Controls ===', '#6eaaff'),
            ('gap', '', ''),
            ('section', 'Modes', '#ffd26e'),
            ('row', 'S', 'Select Mode'),
            ('row', 'E', 'Edit Mode'),
            ('row', 'D', 'Delete Mode'),
            ('gap', '', ''),
            ('section', 'Select Mode', '#ffd26e', 'select'),
            ('row', 'Click', 'Select an atom'),
            ('row', 'Ctrl+Click', 'Add/remove from selection'),
            ('row', 'Right-drag', 'Marquee select'),
            ('row', 'Drag', 'Move selected atom(s)'),
            ('row', 'Arrow keys', 'Nudge selection (Shift = bigger step)'),
            ('row', 'Space+Drag', 'Move the whole selection, even\nstarting from one of its atoms'),
            ('gap', '', ''),
            ('section', 'Edit Mode', '#ffd26e', 'edit'),
            ('row', 'Left Click', 'Place an atom, or pick up an\natom to drag a bond from'),
            ('row', 'Right-drag', 'Draw a bond between two atoms'),
            ('row', 'Right-click bond', 'Change that bond\'s type\n(works in Edit or Select mode)'),
        ])
        col2 = self._make_section([
            ('section', 'Delete Mode', '#ffd26e', 'delete'),
            ('row', 'Click', 'Erase an atom or bond'),
            ('row', 'Drag', 'Erase everything the cursor crosses'),
            ('gap', '', ''),
            ('section', 'Tools (Action Toolbar)', '#6effb4'),
            ('row', 'Bond type', 'Click for the menu, or press 1\u20135'),
            ('row', 'Chain tool', 'Click + drag to grow a carbon chain'),
            ('row', '\u2295 / \u2296', 'Add/remove formal charge\n(toggle, then click an atom)'),
            ('row', 'Clean Up', 'Tidy structure, fill valence with H'),
            ('gap', '', ''),
            ('section', 'Bond Types', '#ffd26e'),
            ('row', '1 / 2 / 3', 'Single / Double / Triple'),
            ('row', '4 / 5', 'Aromatic / Dative (coordinate)'),
            ('gap', '', ''),
            ('section', 'Shortcuts', '#6effb4'),
            ('row', 'Ctrl+Z / Ctrl+Y', 'Undo / Redo'),
            ('row', 'Ctrl+S / Ctrl+Shift+S', 'Save / Save As'),
            ('row', 'Ctrl+O / Ctrl+N', 'Open / New'),
            ('row', 'Ctrl+A', 'Select All'),
            ('row', 'Ctrl+R', 'Reset Zoom'),
            ('row', 'Del', 'Delete Selected'),
            ('row', 'C', 'Clear Scene'),
            ('row', 'N', 'Build from Name'),
            ('row', 'H', 'Toggle this Help panel'),
        ])
        outer.addLayout(col1)
        outer.addLayout(col2)
        self.adjustSize()
        self.hide()

    def highlight_mode(self, mode: str):
        for sections in self._mode_sections.values():
            for lbl in sections:
                base = lbl.property('_base_style') or ''
                lbl.setStyleSheet(base)
        for lbl in self._mode_sections.get(mode, []):
            base = lbl.property('_base_style') or ''
            lbl.setStyleSheet(base + ' background-color: rgba(255, 210, 110, 30); '
                                     'border-radius: 4px; padding: 2px 4px;')

    @staticmethod
    def _label(text: str, color: str = '#e0e8ff', bold: bool = False, size: int = 13) -> QLabel:
        lbl = QLabel(text)
        weight = 'font-weight: bold;' if bold else ''
        lbl.setStyleSheet(f'background: transparent; color: {color}; font-size: {size}px; {weight}')
        lbl.setWordWrap(True)
        return lbl

    def _make_section(self, items):
        KEY_COL_W = 150
        DESC_COL_W = 225
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        grid.setColumnMinimumWidth(0, KEY_COL_W)
        grid.setColumnMinimumWidth(1, DESC_COL_W)
        r = 0
        for item in items:
            kind, a, b = item[0], item[1], item[2]
            mode_tag = item[3] if len(item) > 3 else None
            if kind == 'gap':
                spacer = QLabel('')
                spacer.setStyleSheet('background: transparent;')
                spacer.setFixedHeight(8)
                grid.addWidget(spacer, r, 0, 1, 2)
            elif kind == 'section':
                section_lbl = self._label(a, color=b, bold=True, size=14)
                grid.addWidget(section_lbl, r, 0, 1, 2)
                if mode_tag and mode_tag in self._mode_sections:
                    section_lbl.setProperty('_base_style', section_lbl.styleSheet())
                    self._mode_sections[mode_tag].append(section_lbl)
            else:  # 'row'
                key_lbl = self._label(a, color='#9fd6ff', bold=True)
                key_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                key_lbl.setFixedWidth(KEY_COL_W)
                desc_lbl = self._label(b)
                desc_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                desc_lbl.setFixedWidth(DESC_COL_W)
                grid.addWidget(key_lbl, r, 0)
                grid.addWidget(desc_lbl, r, 1)
            r += 1
        outer_col = QVBoxLayout()
        outer_col.addLayout(grid)
        outer_col.addStretch()
        return outer_col


# ---- Name Input Dialog ----

class GrowingNameInput(QTextEdit):
    submitted = pyqtSignal()
    grew = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._min_height = 0
        self._max_height = 0
        self._chrome = 0
        self.textChanged.connect(self._update_height)

    def _measure_chrome(self) -> int:
        probe_height = 200
        self.setFixedHeight(probe_height)
        chrome = probe_height - self.viewport().height()
        return max(chrome, 0)

    def configure_bounds(self, extra_lines_cap: int = 6):
        fm = self.fontMetrics()
        line_h = fm.lineSpacing() + 1
        self._chrome = self._measure_chrome()
        extra_breathing_room = 5
        self._min_height = line_h + self._chrome + extra_breathing_room
        self._max_height = self._min_height + extra_lines_cap * line_h
        self.setFixedHeight(self._min_height)

    def _update_height(self):
        if self._max_height <= 0:
            return
        doc_h = int(self.document().size().height())
        target_h = doc_h + self._chrome
        new_h = max(self._min_height, min(target_h, self._max_height))
        at_cap = target_h > self._max_height
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if at_cap else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if new_h != self.height():
            self.setFixedHeight(new_h)
            self.grew.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submitted.emit()
            return
        super().keyPressEvent(event)

    def text(self) -> str:
        return ' '.join(self.toPlainText().split())

    def setPlaceholderText(self, text: str):
        super().setPlaceholderText(text)


class NameInputDialog(QDialog):
    build_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Build from IUPAC Name')
        self._collapsed_height = 200
        self.setFixedSize(500, self._collapsed_height)
        self.setStyleSheet("""
            QDialog { background-color: #141c28; }
            QLabel { color: #e0e8ff; font-size: 14px; }
            QTextEdit {
                background-color: #0a101c;
                color: #e0e8ff;
                border: 2px solid #506070;
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
            QTextEdit:focus { border: 2px solid #6a9fd0; }
            QPushButton {
                background-color: #3c6e9e;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #4c8ec0; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        title = QLabel('Enter IUPAC Name')
        title.setStyleSheet('font-size: 18px; font-weight: bold; color: #f0f4ff;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.input = GrowingNameInput()
        self.input.setPlaceholderText('e.g. 2-methylpropane, caffeine, benzene...')
        layout.addWidget(self.input)
        self.input.grew.connect(self._on_input_grew)
        self._bounds_configured = False

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        build_btn = QPushButton('Build')
        build_btn.setDefault(True)
        build_btn.clicked.connect(self._build)
        btn_layout.addWidget(build_btn)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.input.submitted.connect(self._build)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._bounds_configured:
            self.input.configure_bounds(extra_lines_cap=6)
            self._bounds_configured = True

    def _on_input_grew(self):
        extra = self.input.height() - self.input._min_height
        self.setFixedSize(500, self._collapsed_height + extra)

    def _build(self):
        name = self.input.text().strip()
        if name:
            self.build_requested.emit(name)
            self.accept()
