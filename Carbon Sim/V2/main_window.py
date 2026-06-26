"""Main application window with menus, toolbars, panels, dialogs."""
import logging
import math
from pathlib import Path
from typing import Optional, List, Set, Dict

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QParallelAnimationGroup, QEasingCurve, QPropertyAnimation, QPoint
)
from PyQt6.QtGui import QAction, QKeySequence, QColor, QShortcut
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QDialog,
    QGridLayout, QFrame, QFileDialog, QMessageBox, QProgressDialog, QStatusBar, QScrollArea, QStackedWidget,
    QSizePolicy, QTabWidget, QTextEdit
)
from rdkit import Chem

from canvas_view import CanvasView
from chemistry import (
    compute_name, build_from_name, compute_smiles, clear_up_molecule, save_scene, load_scene,
    find_fragments, extract_fragment_mol, compute_fragment_formula, format_formula_html, molecule_to_rdkit
)
from config import (
    WINDOW_W, WINDOW_H, PANEL_W, COLORS, VALENCES, RADIUS, VISIBLE_ELEMENTS,
    PERIODIC_ELEMENTS, SHOW_GRID_DEFAULT, SNAP_TO_GRID_DEFAULT, SMART_JOIN_DEFAULT, IONIC_DISTANCE,
    STRUCTURE_TILE_W, STRUCTURE_TILE_THUMB_H, STRUCTURE_TILE_SPACING
)
from floating_toolbars import ModeToolbar, ActionToolbar, CanvasZoomWidget
from models import Molecule
from structure_library import StructureLibrary, StructureEntry
from utils import UndoManager

logger = logging.getLogger(__name__)

STATUS_LABEL_STYLE = 'color: #8ca0c0; font-size: 12px; padding: 2px 8px;'


class PeriodicDialog(QDialog):
    element_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowTitle('Periodic Table')
            self.setFixedSize(560, 360)
            self.setStyleSheet('background-color: #181c28;')
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet('QScrollArea { border: none; background: #181c28; }')
            container = QWidget()
            grid = QGridLayout(container)
            grid.setSpacing(4)
            grid.setContentsMargins(12, 16, 12, 12)
            for el, row, col in PERIODIC_ELEMENTS:
                btn = QPushButton(el)
                btn.setFixedSize(40, 32)
                color = QColor(*COLORS.get(el, (160, 160, 160)))
                brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
                text_color = 'black' if brightness > 160 else 'white'
                btn.setStyleSheet(
                    f'\n                QPushButton {{\n                    background-color: {color.name()};\n                    color: {text_color};\n                    font-weight: bold;\n                    font-size: 11px;\n                    border-radius: 4px;\n                    border: 1px solid #3a4560;\n                }}\n                QPushButton:hover {{\n                    border: 2px solid #6a85c0;\n                }}\n            ')
                btn.clicked.connect(lambda checked, elem=el: self._select(elem))
                grid.addWidget(btn, row, col)
            for row, text in [(8, 'La-Lu'), (9, 'Ac-Lr')]:
                lbl = QLabel(text)
                lbl.setStyleSheet('color: #8ca0c0; font-size: 10px; background: transparent; border: none;')
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(lbl, row, 2)
            grid.setRowStretch(10, 1)
            grid.setColumnStretch(18, 1)
            scroll.setWidget(container)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(scroll)

        except Exception as e:
            logger.exception(f"PeriodicDialog init error: {e}")

    def _select(self, element: str):
        try:
            self.element_selected.emit(element)
            self.accept()

        except Exception as e:
            logger.exception(f"PeriodicDialog select error: {e}")


class GrowingNameInput(QTextEdit):
    """A QTextEdit styled and behaving like a single-line input, except it
    grows downward as the wrapped text needs more lines (instead of
    scrolling sideways like a QLineEdit), up to a max height — beyond that
    it shows a normal scrollbar. Enter submits (doesn't insert a newline);
    Shift+Enter/Ctrl+Enter are swallowed too, since a chemical name has no
    legitimate reason to contain a line break."""
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
        self._chrome = 0  # padding+border+frame, measured once the widget is styled
        self.textChanged.connect(self._update_height)

    def _measure_chrome(self) -> int:
        """Total vertical space the border/padding/frame eat up around the
        document viewport — measured directly by diffing the widget's outer
        height against its actual viewport height (so CSS padding/border are
        included, not just Qt's own frame/contentsMargins, which the
        stylesheet's `padding` rule doesn't show up in). Guessing this
        instead (e.g. a flat '+10px') is what caused the bug where the box
        was a few px too short for one real line: the document then reported
        itself as needing more space than the viewport had, so the QTextEdit
        auto-scrolled to keep the cursor visible even though nothing had
        visually wrapped to a 2nd line yet."""
        probe_height = 200  # tall enough that viewport sizing isn't clamped by min/max constraints
        self.setFixedHeight(probe_height)
        chrome = probe_height - self.viewport().height()
        return max(chrome, 0)

    def configure_bounds(self, extra_lines_cap: int = 6):
        """Call once after construction and after the widget has its final
        font/stylesheet applied. Measures one real line's height from the
        font metrics + actual chrome, sets that as the resting (single-line)
        height, and caps growth at `extra_lines_cap` additional lines before
        a scrollbar takes over."""
        fm = self.fontMetrics()
        # +1px slack: text rendering can be a hair taller than the raw font
        # metrics report (hinting/antialiasing), and being even 1px short
        # reproduces the scroll-while-one-line bug this method exists to fix.
        line_h = fm.lineSpacing() + 1
        self._chrome = self._measure_chrome()
        extra_breathing_room = 5  # purely visual — keeps text/placeholder off the edges
        self._min_height = line_h + self._chrome + extra_breathing_room
        self._max_height = self._min_height + extra_lines_cap * line_h
        self.setFixedHeight(self._min_height)

    def _update_height(self):
        try:
            if self._max_height <= 0:
                return  # configure_bounds not called yet
            doc_h = int(self.document().size().height())
            target_h = doc_h + self._chrome
            new_h = max(self._min_height, min(target_h, self._max_height))
            at_cap = target_h > self._max_height
            self.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded if at_cap else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            if new_h != self.height():
                self.setFixedHeight(new_h)
                self.grew.emit()
        except Exception as e:
            logger.exception(f"GrowingNameInput _update_height error: {e}")

    def keyPressEvent(self, event):
        try:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.submitted.emit()
                return
            super().keyPressEvent(event)
        except Exception as e:
            logger.exception(f"GrowingNameInput keyPressEvent error: {e}")

    def text(self) -> str:
        """Drop-in compatibility with the QLineEdit call sites elsewhere —
        collapse any pasted line breaks since a name is conceptually one line
        even though it may now visually wrap across several."""
        return ' '.join(self.toPlainText().split())

    def setPlaceholderText(self, text: str):
        super().setPlaceholderText(text)


class NameInputDialog(QDialog):
    build_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowTitle('Build from IUPAC Name')
            self._collapsed_height = 200
            self.setFixedSize(500, self._collapsed_height)
            self.setStyleSheet(
                '\n            QDialog { background-color: #141c28; }\n            QLabel { color: #e0e8ff; font-size: 14px; }\n            QTextEdit {\n                background-color: #0a101c;\n                color: #e0e8ff;\n                border: 2px solid #506070;\n                border-radius: 8px;\n                padding: 8px;\n                font-size: 14px;\n            }\n            QTextEdit:focus { border: 2px solid #6a9fd0; }\n            QPushButton {\n                background-color: #3c6e9e;\n                color: white;\n                border-radius: 8px;\n                padding: 10px 20px;\n                font-weight: bold;\n                font-size: 14px;\n            }\n            QPushButton:hover { background-color: #4c8ec0; }\n        ')
            layout = QVBoxLayout(self)
            layout.setSpacing(15)
            title = QLabel('Enter IUPAC Name')
            title.setStyleSheet('font-size: 18px; font-weight: bold; color: #f0f4ff;')
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)
            self.input = GrowingNameInput()
            self.input.setPlaceholderText('e.g. 2-methylpropane, caffeine, benzene...')
            self.input.setFixedHeight(38)  # conservative guess, corrected precisely in showEvent
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

        except Exception as e:
            logger.exception(f"NameInputDialog init error: {e}")

    def showEvent(self, event):
        try:
            super().showEvent(event)
            if not self._bounds_configured:
                # Stylesheet padding/border aren't resolved into real pixel
                # metrics until the widget has actually been shown once —
                # measuring chrome any earlier (e.g. in __init__) silently
                # returns 0, which made the box too short for even one line
                # and caused it to auto-scroll while still on a single line.
                self.input.configure_bounds(extra_lines_cap=6)
                self._bounds_configured = True
        except Exception as e:
            logger.exception(f"NameInputDialog showEvent error: {e}")

    def _on_input_grew(self):
        try:
            # Grow the dialog itself by exactly how much the input grew past
            # its single-line height, so the Build/Cancel row is always
            # pushed down rather than the input overlapping it.
            extra = self.input.height() - self.input._min_height
            self.setFixedSize(500, self._collapsed_height + extra)
        except Exception as e:
            logger.exception(f"NameInputDialog _on_input_grew error: {e}")

    def _build(self):
        try:
            name = self.input.text().strip()
            if name:
                self.build_requested.emit(name)
                self.accept()

        except Exception as e:
            logger.exception(f"NameInputDialog build error: {e}")


class HelpOverlay(QFrame):

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setStyleSheet(
                '\n            QFrame {\n                background-color: rgba(20, 24, 36, 220);\n                border-radius: 16px;\n                border: 2px solid #586070;\n            }\n            QLabel {\n                color: #e0e8ff;\n                font-size: 13px;\n                padding: 2px;\n            }\n        ')
            self.setFixedSize(520, 460)
            layout = QHBoxLayout(self)
            layout.setSpacing(30)
            col1 = self._make_column([('=== Help / Controls ===', '#6eaaff', True), ('', '#e0e8ff', False),
                                      ('Left Click  - Add(E) / Delete(D)', '#e0e8ff', False),
                                      ('Right Click - Bond(E) / Marquee(S)', '#e0e8ff', False),
                                      ('Drag        - Move atom(s)', '#e0e8ff', False),
                                      ('Scroll      - Zoom', '#e0e8ff', False), ('', '#e0e8ff', False),
                                      ('Bond Types:', '#ffd26e', True), ('1 - Single', '#e0e8ff', False),
                                      ('2 - Double', '#e0e8ff', False), ('3 - Triple', '#e0e8ff', False),
                                      ('', '#e0e8ff', False), ('Modes:', '#ffd26e', True),
                                      ('S - Select Mode', '#e0e8ff', False), ('E - Edit Mode', '#e0e8ff', False),
                                      ('D - Delete Mode', '#e0e8ff', False)])
            col2 = self._make_column([('Shortcuts:', '#6effb4', True), ('Ctrl+Z - Undo', '#e0e8ff', False),
                                      ('Ctrl+Y - Redo', '#e0e8ff', False), ('Ctrl+S - Save', '#e0e8ff', False),
                                      ('Ctrl+O - Open', '#e0e8ff', False), ('Ctrl+N - New', '#e0e8ff', False),
                                      ('Ctrl+R - Reset Zoom', '#e0e8ff', False),
                                      ('C      - Clear Scene', '#e0e8ff', False),
                                      ('N      - Make from Name', '#e0e8ff', False),
                                      ('H      - Toggle Help', '#e0e8ff', False),
                                      ('Del    - Delete Selected', '#e0e8ff', False), ('', '#e0e8ff', False),
                                      ('Tips:', '#6effb4', True), ('- Zoom in for precision', '#e0e8ff', False),
                                      ('- Select Mode moves groups', '#e0e8ff', False),
                                      ('- Use Undo often', '#e0e8ff', False)])
            layout.addLayout(col1)
            layout.addLayout(col2)
            self.hide()

        except Exception as e:
            logger.exception(f"HelpOverlay init error: {e}")

    @staticmethod
    def _make_column(items):
        layout = QVBoxLayout()
        layout.setSpacing(4)
        for text, color, bold in items:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; {('font-weight: bold;' if bold else '')}")
            layout.addWidget(lbl)
        layout.addStretch()
        return layout


class ElementPanel(QFrame):
    element_selected = pyqtSignal(str)
    periodic_requested = pyqtSignal()
    size_changed = pyqtSignal()
    PERMANENT = ['H', 'C', 'N', 'O', 'S', 'Cl', 'P', 'F', 'Br', 'I']

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.setStyleSheet(
                '\n            QFrame {\n                background-color: rgba(12, 18, 30, 235);\n                border: 1px solid #2a3a50;\n                border-radius: 8px;\n            }\n            QPushButton {\n                background-color: transparent;\n                color: #e6eaf0;\n                border: 1px solid #2a3a50;\n                border-radius: 4px;\n                font-weight: bold;\n                font-size: 12px;\n                padding: 0px;\n            }\n            QPushButton:hover {\n                border: 1px solid #4a9fd0;\n                background-color: rgba(40, 60, 90, 180);\n            }\n            QPushButton:checked {\n                border: 2px solid #4a9fd0;\n                background-color: rgba(30, 50, 80, 200);\n            }\n        ')
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
            pt_btn = QPushButton('PT')
            pt_btn.setFixedSize(36, 36)
            pt_btn.setStyleSheet(
                '\n            QPushButton {\n                background-color: #1e2a40;\n                color: #8ca0c0;\n                font-size: 10px;\n                border: 1px solid #3a5068;\n                border-radius: 4px;\n            }\n            QPushButton:hover {\n                background-color: #2a3a58;\n                color: #dce8ff;\n            }\n        ')
            pt_btn.setToolTip('Periodic Table')
            pt_btn.clicked.connect(self.periodic_requested.emit)
            self._layout.addWidget(pt_btn)
            self._update_size()

        except Exception as e:
            logger.exception(f"ElementPanel init error: {e}")

    def _add_btn(self, el: str, layout):
        try:
            btn = QPushButton(el)
            btn.setFixedSize(36, 36)
            color = QColor(*COLORS.get(el, (200, 200, 200)))
            brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            text_color = '#060c16' if brightness > 160 else '#e6ecff'
            btn.setStyleSheet(
                f'\n            QPushButton {{\n                background-color: {color.name()};\n                color: {text_color};\n                border: 1px solid rgba(0,0,0,0.3);\n                border-radius: 4px;\n                font-weight: bold;\n                font-size: 12px;\n                padding: 0px;\n            }}\n            QPushButton:hover {{\n                border: 1px solid rgba(255,255,255,0.8);\n            }}\n            QPushButton:checked {{\n                border: 2px solid #4a9fd0;\n            }}\n        ')
            btn.setCheckable(True)
            btn.setChecked(el == self._current)
            btn.clicked.connect(lambda checked, elem=el: self._select(elem))
            layout.addWidget(btn)
            self._buttons[el] = btn
            return btn

        except Exception as e:
            logger.exception(f"ElementPanel add_btn error: {e}")

    def _select(self, el: str):
        try:
            self._current = el
            for b in self._buttons.values():
                b.setChecked(False)
            if el in self._buttons:
                self._buttons[el].setChecked(True)
            self.element_selected.emit(el)

        except Exception as e:
            logger.exception(f"ElementPanel select error: {e}")

    def add_recent(self, el: str):
        try:
            if el in self.PERMANENT:
                return
            if el in self._recent:
                self._recent.remove(el)
                self._recent.append(el)
                self._update_size()
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

        except Exception as e:
            logger.exception(f"ElementPanel add_recent error: {e}")

    def select_element(self, el: str):
        self._select(el)

    def _update_size(self):
        try:
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

        except Exception as e:
            logger.exception(f"ElementPanel update_size error: {e}")


class FragmentCard(QFrame):
    """Reusable card widget for fragment list items (Cases 1 & 3). Clicking
    a card selects every atom belonging to that molecule on the canvas and
    opens its detail view, the same as clicking those atoms directly would."""
    clicked = pyqtSignal(set)  # emits the card's current atom_ids

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
        try:
            if event.button() == Qt.MouseButton.LeftButton and self._atom_ids:
                self.clicked.emit(set(self._atom_ids))
                event.accept()
                return
        except Exception as e:
            logger.exception(f"FragmentCard mousePressEvent error: {e}")
        super().mousePressEvent(event)


class InspectorPanel(QFrame):
    """The original Info Panel content (fragment list / molecule detail / atom detail).
    Lives inside a tab of the outer InfoPanel; has no collapse logic of its own."""
    molecule_card_clicked = pyqtSignal(set)  # atom_ids of the molecule whose card was clicked

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
        # Let the stack widget expand to fill all available height

        # ── Header ──
        header = QHBoxLayout()
        self._title = QLabel('Info Panel')
        self._title.setStyleSheet('font-size: 18px; font-weight: bold; color: #dce8ff;')
        header.addWidget(self._title)
        header.addStretch()
        self._layout.addLayout(header)

        # ── Stacked pages ──
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self._layout.addWidget(self._stack, stretch=1)

        # Page 0 — Empty
        self._page_empty = QWidget()
        self._page_empty.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        empty_layout = QVBoxLayout(self._page_empty)
        empty_layout.setContentsMargins(0, 20, 0, 0)
        empty_lbl = QLabel('No data available')
        empty_lbl.setStyleSheet('color: #5a6a80; font-style: italic;')
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_lbl)

        # Page 1 — Fragment list (Cases 1 & 3)
        self._page_list = QScrollArea()
        self._page_list.setWidgetResizable(True)
        self._page_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._page_list.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        list_container = QWidget()
        list_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._list_layout = QVBoxLayout(list_container)
        self._list_layout.setSpacing(8)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._page_list.setWidget(list_container)
        self._list_cards: List[FragmentCard] = []

        # Page 2 — Detail (Case 2)
        self._page_detail = QWidget()
        self._page_detail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        detail_layout = QVBoxLayout(self._page_detail)
        detail_layout.setSpacing(8)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Formula (big)
        self._detail_formula = QLabel()
        self._detail_formula.setTextFormat(Qt.TextFormat.RichText)
        self._detail_formula.setStyleSheet(
            'font-size: 22px; color: #f0f4ff; margin: 4px 0; font-family: "Segoe UI", Arial, sans-serif;'
        )
        detail_layout.addWidget(self._detail_formula)

        # Name (as a proper labeled row: "Name: Fetching...")
        name_row = QHBoxLayout()
        name_key = QLabel('Name:')
        name_key.setStyleSheet('color: #8ca0c0; font-weight: bold; font-size: 11px;')
        self._detail_name = QLabel('Fetching')
        self._detail_name.setStyleSheet('font-size: 12px; color: #8ca0c0; font-style: italic;')
        self._detail_name.setWordWrap(True)
        name_row.addWidget(name_key)
        name_row.addWidget(self._detail_name, 1)
        detail_layout.addLayout(name_row)

        # Properties rows (persistent — we only update text)
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

        # Composition
        self._detail_comp_title = QLabel('Composition')
        self._detail_comp_title.setStyleSheet(
            'color: #8ca0c0; font-weight: bold; font-size: 11px; margin-top: 4px;'
        )
        detail_layout.addWidget(self._detail_comp_title)
        self._detail_composition = QLabel()
        self._detail_composition.setStyleSheet('color: #a0b8d8; font-size: 11px;')
        self._detail_composition.setWordWrap(True)
        detail_layout.addWidget(self._detail_composition)

        # Atom detail section (wrapped so we can hide the whole block)
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
        detail_layout.addStretch()  # Fill remaining vertical space

        # Register pages
        self._stack.addWidget(self._page_empty)  # 0
        self._stack.addWidget(self._page_list)  # 1
        self._stack.addWidget(self._page_detail)  # 2

        # ── Fetching animation ──
        self._fetch_timer = QTimer(self)
        self._fetch_timer.timeout.connect(self._animate_fetching)
        self._fetch_dots = 0

    # ── Fetching animation ──
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

    # ── Public API ──
    def set_case_1(self, fragments: List[dict]):
        try:
            self._title.setText('Molecules on Canvas')
            self._sync_list(fragments)
            self._stack.setCurrentIndex(1)
        except Exception as e:
            logger.exception(f"InspectorPanel set_case_1 error: {e}")

    def set_case_2(self, info: dict, atom=None, mol=None):
        try:
            self._title.setText('Selected Molecule')
            self._stack.setCurrentIndex(2)
            self._detail_formula.setText(f"<b>{info.get('formula_html', '—')}</b>")
            self._update_name_display(info)
            self._update_property_labels(info)
            self._update_ionic_pairs_row(info)
            self._update_smiles_row(info)
            self._update_composition_row(info)
            self._update_atom_detail(atom, mol)
        except Exception as e:
            logger.exception(f"InspectorPanel set_case_2 error: {e}")

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
        try:
            self._title.setText('Selected Molecules')
            self._sync_list(fragments)
            self._stack.setCurrentIndex(1)
        except Exception as e:
            logger.exception(f"InspectorPanel set_case_3 error: {e}")

    def set_empty(self):
        try:
            self._title.setText('Info Panel')
            self._stop_fetching()
            self._stack.setCurrentIndex(0)
        except Exception as e:
            logger.exception(f"InspectorPanel set_empty error: {e}")

    def update_fragment_name(self, name: str):
        logger.info(
            f"InspectorPanel.update_fragment_name: '{name[:60]}...' "
            if len(name) > 60 else f"InspectorPanel.update_fragment_name: '{name}'"
        )
        if not name:
            return
        if self._stack.currentIndex() == 2:
            self._stop_fetching()
            self._detail_name.setText(name)
            self._detail_name.setStyleSheet('font-size: 12px; color: #dce8ff; font-style: italic;')

    # ── Internal helpers ──
    def _sync_list(self, fragments: List[dict]):
        """Add cards when needed, hide extras, update visible ones in-place."""
        # Remove old stretch if present (it's always at the end)
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
        # Add stretch at the end to push cards to top and fill empty space
        self._list_layout.addStretch()


class StructureTile(QFrame):
    """One tile in the Structure Browser: name, formula, element counts, and a
    lazily-rendered 2D depiction (only drawn the first time the tile actually
    becomes visible on screen, via showEvent)."""
    clicked = pyqtSignal(object)  # emits the StructureEntry

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

        # Thumbnail placeholder — real SVG is injected lazily in showEvent()
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

    def showEvent(self, event):
        try:
            super().showEvent(event)
        except Exception as e:
            logger.exception(f'StructureTile showEvent error for {self.entry.name}: {e}')

    def ensure_thumb_loaded(self):
        """Called by the owning panel only when this tile is actually scrolled
        into the visible viewport — NOT from showEvent, which fires for every
        widget in a shown tab regardless of scroll position."""
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
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self.entry)
            super().mousePressEvent(event)
        except Exception as e:
            logger.exception(f'StructureTile mousePressEvent error: {e}')


class StructureBrowserPanel(QFrame):
    """Search bar + categorized, lazily-rendered tiles of prebuilt structures.
    Clicking a tile asks the canvas to enter ghost-placement mode (see
    MainWindow._on_structure_selected)."""
    structure_selected = pyqtSignal(object)  # emits the StructureEntry

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

        # ── Viewport-based lazy thumbnail loading ──
        # showEvent fires for every widget in a shown tab regardless of scroll
        # position, so real "only render what's actually visible" lazy loading
        # has to check tile geometry against the scroll area's viewport rect.
        self._lazy_timer = QTimer(self)
        self._lazy_timer.setSingleShot(True)
        self._lazy_timer.timeout.connect(self._load_visible_thumbnails)
        self._scroll.verticalScrollBar().valueChanged.connect(self._schedule_lazy_load)
        QTimer.singleShot(0, self._load_visible_thumbnails)

    def _schedule_lazy_load(self):
        # Debounce: coalesce rapid scroll events into a single check ~60ms later.
        self._lazy_timer.start(60)

    def _compute_cols(self) -> int:
        """How many tile columns fit, using the real scrollbar width (via Qt's
        own style metric, not a guessed constant) so this stays correct even
        if the panel is resized or the platform's scrollbar width differs."""
        try:
            scrollbar_w = self._scroll.verticalScrollBar().sizeHint().width() if hasattr(self, '_scroll') else 18
        except Exception:
            scrollbar_w = 18
        outer_margins = 10 + 10  # matches this panel's own layout.setContentsMargins
        grid_margins = 2 + 2  # matches each category's grid.setContentsMargins
        # StructureTile has setFixedWidth(130) but a 1px QFrame border on each side
        # makes Qt's style engine report sizeHint()=132 anyway; QGridLayout sizes
        # itself off sizeHint, not the fixed width, so budget for that 2px/tile.
        tile_border_overhead = 2
        available = PANEL_W - outer_margins - grid_margins - scrollbar_w
        effective_tile_w = STRUCTURE_TILE_W + tile_border_overhead
        # n columns need n*tile_w + (n-1)*spacing of width (no trailing gap after
        # the last column) — NOT n*(tile_w+spacing), which overcounts by one gap.
        n = 1
        while (n + 1) * effective_tile_w + n * STRUCTURE_TILE_SPACING <= available:
            n += 1
        return n

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            self._schedule_lazy_load()
            self._reflow_if_needed()
        except Exception as e:
            logger.exception(f'StructureBrowserPanel resizeEvent error: {e}')

    def _reflow_if_needed(self):
        """Re-wrap tiles into a new column count if the panel was resized
        enough to change how many tiles fit per row."""
        try:
            new_cols = self._compute_cols()
            if new_cols == self._current_cols:
                return
            self._current_cols = new_cols
            for category, grid in self._category_grids.items():
                entries = self._category_entries[category]
                # Re-place existing tiles (don't recreate — keeps thumbnails cached)
                tiles_by_name = {t.entry.name: t for t in self._all_tiles if t.entry.category == category}
                for i, entry in enumerate(entries):
                    tile = tiles_by_name.get(entry.name)
                    if tile is not None:
                        grid.addWidget(tile, i // new_cols, i % new_cols)
        except Exception as e:
            logger.exception(f'StructureBrowserPanel _reflow_if_needed error: {e}')

    def _load_visible_thumbnails(self):
        """Render thumbnails for tiles currently within (or just outside, as a
        small lookahead buffer) the scroll area's visible viewport."""
        try:
            viewport_rect = self._scroll.viewport().rect()
            buffer_px = STRUCTURE_TILE_THUMB_H * 2  # pre-load one screen's worth ahead
            check_rect = viewport_rect.adjusted(0, -buffer_px, 0, buffer_px)
            for tile in self._all_tiles:
                if tile._thumb_loaded or not tile.isVisible():
                    continue
                top_left = tile.mapTo(self._scroll.viewport(), tile.rect().topLeft())
                tile_rect_in_viewport = tile.rect()
                tile_rect_in_viewport.moveTopLeft(top_left)
                if check_rect.intersects(tile_rect_in_viewport):
                    tile.ensure_thumb_loaded()
        except Exception as e:
            logger.exception(f'StructureBrowserPanel _load_visible_thumbnails error: {e}')

    def _build_categorized_view(self):
        """Build one collapsible section per category (collapsed by default),
        each with a clickable header and a flow of tiles inside a QGridLayout.
        Built once; search just shows/hides + auto-expands matching sections."""
        try:
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
        except Exception as e:
            logger.exception(f'StructureBrowserPanel _build_categorized_view error: {e}')

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
        grid_host.hide()  # collapsed by default
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
        try:
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
        except Exception as e:
            logger.exception(f'StructureBrowserPanel _toggle_category error: {e}')

    def _on_search_changed(self, text: str):
        try:
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
        except Exception as e:
            logger.exception(f'StructureBrowserPanel _on_search_changed error: {e}')

    def _on_tile_clicked(self, entry: StructureEntry):
        try:
            self.structure_selected.emit(entry)
        except Exception as e:
            logger.exception(f'StructureBrowserPanel _on_tile_clicked error: {e}')


class InfoPanel(QFrame):
    """Outer right-side panel: collapsible container with two tabs —
    'Inspector' (selection/fragment details, the original Info Panel) and
    'Structures' (the prebuilt structure browser)."""
    collapse_changed = pyqtSignal(bool)
    structure_selected = pyqtSignal(object)  # emits the StructureEntry, forwarded from the browser tab
    molecule_card_clicked = pyqtSignal(set)  # forwarded from the inspector tab's fragment list

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

        # ── Width animation (collapse/expand) ──
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
        """Called by the external collapse button."""
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

    # ── Forwarded Inspector API (kept identical to the old InfoPanel's public surface
    #    so the rest of MainWindow needs no other changes) ──
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


class NameWorker(QThread):
    name_ready = pyqtSignal(str)

    def __init__(self, mol_dict: dict):
        try:
            super().__init__()
            self.mol_dict = mol_dict

        except Exception as e:
            logger.exception(f"NameWorker init error: {e}")

    def run(self):
        try:
            mol = Molecule()
            mol.from_dict(self.mol_dict)
            name = compute_name(mol)
            logger.info(f"NameWorker.run finished: name='{name[:60]}...' " if len(
                name) > 60 else f"NameWorker.run finished: name='{name}'")
            self.name_ready.emit(name)
        except Exception as e:
            logger.exception(f'Name computation error: {e}')
            self.name_ready.emit('')


class BuildWorker(QThread):
    molecule_ready = pyqtSignal(object)

    def __init__(self, name: str):
        try:
            super().__init__()
            self.name = name

        except Exception as e:
            logger.exception(f"BuildWorker init error: {e}")

    def run(self):
        try:
            mol = build_from_name(self.name)
            if not mol:
                logger.warning('BuildWorker.run finished: None')
            self.molecule_ready.emit(mol)
        except Exception as e:
            logger.exception(f'Build error: {e}')
            self.molecule_ready.emit(None)


class MainWindow(QMainWindow):

    def __init__(self):
        try:
            super().__init__()
            logger.info('MainWindow initializing...')
            self.setWindowTitle('Carbon Simulator')
            self.setMinimumSize(WINDOW_W, WINDOW_H)
            self.resize(WINDOW_W, WINDOW_H)
            self.setStyleSheet('background-color: #060c16;')
            self.mol = Molecule()
            self.undo_manager = UndoManager()
            self.last_save_path: Optional[str] = None
            self.display_name = ''
            self._current_name_worker: Optional[NameWorker] = None
            self._fragment_name_worker: Optional[NameWorker] = None
            self._build_worker: Optional[BuildWorker] = None
            self._progress: Optional[QProgressDialog] = None
            self._last_x = 0.0
            self._last_y = 0.0
            self._name_cache: dict[str, str] = {}
            self._current_whole_smiles: Optional[str] = None
            self._current_fragment_smiles: Optional[str] = None
            central = QWidget()
            self.setCentralWidget(central)
            layout = QHBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.status_bar = QStatusBar()
            self.status_bar.setStyleSheet(
                '\n                QStatusBar {\n                    background-color: #0c121e;\n                    color: #8ca0c0;\n                    border-top: 1px solid #1a2438;\n                }\n            ')
            self.setStatusBar(self.status_bar)
            self._status_coords = QLabel('X: 0.0  Y: 0.0')
            self._status_zoom = QLabel('Zoom: 100%')
            self._status_mol = QLabel('Atoms: 0  Bonds: 0')
            self._status_coords.setStyleSheet(STATUS_LABEL_STYLE)
            self._status_zoom.setStyleSheet(STATUS_LABEL_STYLE)
            self._status_mol.setStyleSheet(STATUS_LABEL_STYLE)
            self.status_bar.addWidget(self._status_coords)
            self.status_bar.addWidget(self._status_zoom)
            self.status_bar.addPermanentWidget(self._status_mol)
            self.mode_toolbar = ModeToolbar(central)
            self.mode_toolbar.mode_changed.connect(self._on_mode_changed)
            self.mode_toolbar.rotate_requested.connect(self._on_rotate_requested)
            self.mode_toolbar.flip_requested.connect(self._on_flip_requested)
            self.action_toolbar = ActionToolbar(central)
            self.action_toolbar.bond_mode_changed.connect(self._on_bond_mode_changed)
            self.action_toolbar.clear_up_requested.connect(self._clear_up)
            self.action_toolbar.undo_requested.connect(self._undo)
            self.action_toolbar.redo_requested.connect(self._redo)
            self.action_toolbar.formal_charge_toggled.connect(self._on_formal_charge_toggled)
            self.action_toolbar.chain_toggled.connect(self._on_chain_toggled)
            self.action_toolbar.edit_mode_requested.connect(lambda: self.mode_toolbar.set_mode('edit'))
            # Both float above the canvas (frameless, positioned in
            # _position_panels) rather than taking a column in the main layout.
            self.canvas = CanvasView(self.mol)
            self.canvas.mutation_about_to_apply.connect(self._push_undo)
            self.canvas.atom_added.connect(self._on_topology_changed)
            self.canvas.bond_added.connect(self._on_topology_changed)
            self.canvas.selection_changed.connect(self._on_selection_changed)
            self.canvas.atoms_deleted.connect(self._push_undo)
            self.canvas.atoms_deleted.connect(self._on_topology_changed)
            self.canvas.atom_erased.connect(self._on_topology_changed)
            self.canvas.drag_started.connect(self._push_undo)
            self.canvas.structure_about_to_place.connect(self._push_undo)
            self.canvas.structure_placed.connect(self._on_topology_changed)
            self.canvas.formal_charge_changed.connect(self._on_topology_changed)
            self.canvas.formal_charge_rejected.connect(self._on_formal_charge_rejected)
            self.canvas.formal_charge_mode_exited.connect(self.action_toolbar.untoggle_formal_charge)
            self.canvas.chain_built.connect(self._on_topology_changed)
            self.canvas.chain_about_to_build.connect(self._push_undo)
            self.canvas.chain_mode_exited.connect(self.action_toolbar.untoggle_chain)
            self.canvas.transform_about_to_apply.connect(self._push_undo)
            self.canvas.transform_applied.connect(self._on_topology_changed)
            self.canvas.selection_empty_for_transform.connect(self._on_transform_no_target)
            layout.addWidget(self.canvas)
            self.zoom_widget = CanvasZoomWidget(self.canvas)
            self.zoom_widget.zoom_in_requested.connect(self._zoom_in)
            self.zoom_widget.zoom_out_requested.connect(self._zoom_out)
            self.info_panel = InfoPanel()
            # External collapse button (positioned on the panel border)
            self._collapse_btn = QPushButton('◀', central)
            self._collapse_btn.setFixedSize(24, 40)
            self._collapse_btn.hide()
            self._collapse_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a2435;
                    color: #8ca0c0;
                    border: 1px solid #2a3a50;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #2a3a58;
                    color: #dce8ff;
                }
            """)
            self._collapse_btn.clicked.connect(self._toggle_info_panel)
            self._collapse_btn.setToolTip('Collapse Info Panel')

            # Connect panel animation to button repositioning
            self.info_panel.collapse_changed.connect(self._on_panel_anim_step)
            layout.addWidget(self.info_panel)
            self.element_panel = ElementPanel(central)
            self.element_panel.element_selected.connect(self._on_element_selected)
            self.element_panel.periodic_requested.connect(self._show_periodic)
            self.element_panel.size_changed.connect(self._position_panels)
            self.clear_btn = QPushButton('✕', central)
            self.clear_btn.setFixedSize(52, 36)
            self.clear_btn.setStyleSheet(
                '\n                QPushButton {\n                    background-color: #5c1c1c;\n                    color: #f0c0c0;\n                    font-size: 13px;\n                    border: 1px solid #8c2c2c;\n                    border-radius: 4px;\n                    font-weight: bold;\n                }\n                QPushButton:hover {\n                    background-color: #7c2c2c;\n                }\n            ')
            self.clear_btn.setToolTip('Clear Canvas (C)')
            self.clear_btn.clicked.connect(self._clear_scene)
            self.help_overlay = HelpOverlay(central)
            self.info_panel.structure_selected.connect(self._on_structure_selected)
            self.info_panel.molecule_card_clicked.connect(self._on_molecule_card_clicked)
            self._setup_menu()
            self._setup_shortcuts()
            self.canvas.reset_view()
            self._update_layout()
            self._status_timer = QTimer(self)
            self._status_timer.timeout.connect(self._update_status_bar)
            self._status_timer.start(100)
            self._clear_scene()
            self.undo_manager.undo_stack.clear()
            self.undo_manager.redo_stack.clear()
            self._update_undo_buttons()
            QTimer.singleShot(0, self._show_and_position_collapse_button)
            logger.info('MainWindow initialized successfully')
        except Exception as e:
            logger.exception(f'CRITICAL ERROR in MainWindow.__init__: {e}')
            raise

    def _show_and_position_collapse_button(self):
        """Show and position the collapse button after layout is valid."""
        self._update_layout()
        self._position_collapse_button()
        self._collapse_btn.show()

    def _available_height(self):
        h = self.height() - self.menuBar().height()
        sb = self.statusBar()
        if sb is not None and sb.isVisible():
            h -= sb.height()
        return h

    def _update_layout(self):
        """Recalculate canvas width and position floating panels."""
        if hasattr(self, 'canvas') and self.canvas is not None and hasattr(self, 'info_panel'):
            # ModeToolbar/ActionToolbar float above the canvas now (no layout
            # column reserved for them), so only the info panel competes with
            # the canvas for width.
            available_w = self.width() - self.info_panel.width()
            new_size = max(400, available_w)
            self.canvas.setFixedSize(new_size, self._available_height())
            logger.info(f'_update_layout: canvas size={new_size}x{self._available_height()}')
        self._position_panels()

    def _position_panels(self):
        """Position floating widgets."""
        if not hasattr(self, 'element_panel') or not hasattr(self, 'info_panel'):
            logger.warning('_position_panels: panels not ready')
            return
        margin = 12
        panel_gap = 10  # fixed gap between element_panel and info_panel — they
        # move together as info_panel collapses/expands/resizes
        # since element_panel is anchored to info_panel's own
        # actual left edge (via mapTo, the same way
        # _position_collapse_button anchors to it) rather than
        # being derived from canvas's width. Deriving it from
        # canvas was fragile: canvas's width itself depends on
        # info_panel.width() inside _update_layout, so reusing
        # canvas's geometry to place element_panel created a
        # circular, timing-sensitive dependency that could go
        # stale on window resize. Adding more floating side
        # panels later just means anchoring to the previous
        # panel's mapTo position the same way.
        central = self.centralWidget()
        if central and central.layout():
            central.layout().activate()
        info_top_left = self.info_panel.mapTo(central, QPoint(0, 0))
        ep_w = self.element_panel.width()
        x = info_top_left.x() - panel_gap - ep_w
        y = self.menuBar().height() + margin
        self.element_panel.move(x, y)
        self.element_panel.show()
        ep_h = self.element_panel.height()
        self.clear_btn.move(x, y + ep_h + margin - 2)
        self.clear_btn.show()
        canvas_geo = self.canvas.geometry()
        hx = canvas_geo.x() + (canvas_geo.width() - self.help_overlay.width()) // 2
        self.help_overlay.move(hx, 120)
        if hasattr(self, 'mode_toolbar'):
            mt_x = canvas_geo.x() + margin
            mt_y = canvas_geo.y() + (canvas_geo.height() - self.mode_toolbar.height()) // 2
            self.mode_toolbar.move(mt_x, mt_y)
            self.mode_toolbar.show()
            self.mode_toolbar.raise_()
        if hasattr(self, 'action_toolbar'):
            at_x = canvas_geo.x() + (canvas_geo.width() - self.action_toolbar.width()) // 2
            at_y = canvas_geo.y() + margin
            self.action_toolbar.move(at_x, at_y)
            self.action_toolbar.show()
            self.action_toolbar.raise_()
        if hasattr(self, 'zoom_widget'):
            # Child of the canvas itself, so coordinates are canvas-local.
            zw_x = self.canvas.width() - self.zoom_widget.width() - margin
            zw_y = self.canvas.height() - self.zoom_widget.height() - margin
            self.zoom_widget.move(zw_x, zw_y)
            self.zoom_widget.show()
            self.zoom_widget.raise_()
        self._position_collapse_button()

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            self._update_layout()
            self._position_collapse_button()
        except Exception as e:
            logger.exception(f'Error in resizeEvent: {e}')

    def _on_panel_anim_step(self, _collapsed: bool):
        """Called during animation to reposition the external button."""
        self._position_collapse_button()
        self._update_layout()

    def _position_collapse_button(self):
        """Position the collapse button flush against the InfoPanel's left border."""
        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()

        panel_top_left = self.info_panel.mapTo(self.centralWidget(), QPoint(0, 0))
        btn_w = self._collapse_btn.width()

        # Right edge of button touches panel's left border — sits cleanly on the line
        x = panel_top_left.x() - btn_w + 1

        y = panel_top_left.y() + 20

        self._collapse_btn.move(x, y)
        self._collapse_btn.raise_()

    def _toggle_info_panel(self):
        """Toggle panel collapse/expand with animation."""
        collapsed = self.info_panel.toggle_collapse()
        self._collapse_btn.setText('▶' if collapsed else '◀')
        self._collapse_btn.setToolTip('Expand Info Panel' if collapsed else 'Collapse Info Panel')
        # Reposition immediately so it doesn't lag behind animation
        self._position_collapse_button()

    def _setup_menu(self):
        try:
            logger.info('_setup_menu called')
            menubar = self.menuBar()
            menubar.setStyleSheet(
                '\n                QMenuBar {\n                    background-color: #181a22;\n                    color: #ebedff;\n                    padding: 4px;\n                }\n                QMenuBar::item:selected {\n                    background-color: #2d3748;\n                    border-radius: 4px;\n                }\n                QMenu {\n                    background-color: #1e2430;\n                    color: #ebedff;\n                    border: 1px solid #3a4050;\n                }\n                QMenu::item:selected {\n                    background-color: #2d3a50;\n                }\n            ')
            file_menu = menubar.addMenu('File')
            new_action = QAction('New', self)
            new_action.setShortcut(QKeySequence('Ctrl+N'))
            new_action.triggered.connect(self._new_scene)
            file_menu.addAction(new_action)
            open_action = QAction('Open...', self)
            open_action.setShortcut(QKeySequence('Ctrl+O'))
            open_action.triggered.connect(self._open_file)
            file_menu.addAction(open_action)
            save_action = QAction('Save', self)
            save_action.setShortcut(QKeySequence('Ctrl+S'))
            save_action.triggered.connect(self._save_file)
            file_menu.addAction(save_action)
            save_as_action = QAction('Save As...', self)
            save_as_action.setShortcut(QKeySequence('Ctrl+Shift+S'))
            save_as_action.triggered.connect(self._save_as)
            file_menu.addAction(save_as_action)
            file_menu.addSeparator()
            exit_action = QAction('Exit', self)
            exit_action.triggered.connect(self.close)
            file_menu.addAction(exit_action)
            edit_menu = menubar.addMenu('Edit')
            undo_action = QAction('Undo', self)
            undo_action.setShortcut(QKeySequence('Ctrl+Z'))
            undo_action.triggered.connect(self._undo)
            edit_menu.addAction(undo_action)
            redo_action = QAction('Redo', self)
            redo_action.setShortcut(QKeySequence('Ctrl+Y'))
            redo_action.triggered.connect(self._redo)
            edit_menu.addAction(redo_action)
            edit_menu.addSeparator()
            select_all_action = QAction('Select All', self)
            select_all_action.setShortcut(QKeySequence('Ctrl+A'))
            select_all_action.triggered.connect(self.canvas.select_all)
            edit_menu.addAction(select_all_action)
            delete_action = QAction('Delete', self)
            delete_action.setShortcut(QKeySequence('Delete'))
            delete_action.triggered.connect(self.canvas.delete_selected)
            edit_menu.addAction(delete_action)
            view_menu = menubar.addMenu('View')
            center_action = QAction('Center Molecule', self)
            center_action.triggered.connect(self.canvas.center_molecule)
            view_menu.addAction(center_action)
            reset_zoom_action = QAction('Reset Zoom', self)
            reset_zoom_action.setShortcut(QKeySequence('Ctrl+R'))
            reset_zoom_action.triggered.connect(self.canvas.reset_view)
            view_menu.addAction(reset_zoom_action)
            grid_action = QAction('Show Grid', self)
            grid_action.setCheckable(True)
            grid_action.setChecked(SHOW_GRID_DEFAULT)
            grid_action.triggered.connect(self._toggle_grid)
            view_menu.addAction(grid_action)
            snap_action = QAction('Snap to Grid', self)
            snap_action.setCheckable(True)
            snap_action.setChecked(SNAP_TO_GRID_DEFAULT)
            snap_action.triggered.connect(self._toggle_snap)
            view_menu.addAction(snap_action)
            smart_action = QAction('Smart Join', self)
            smart_action.setCheckable(True)
            smart_action.setChecked(SMART_JOIN_DEFAULT)
            smart_action.triggered.connect(self._toggle_smart_join)
            view_menu.addAction(smart_action)
            help_menu = menubar.addMenu('Help')
            help_action = QAction('Help', self)
            help_action.setShortcut(QKeySequence('H'))
            help_action.triggered.connect(self._toggle_help)
            help_menu.addAction(help_action)
            about_action = QAction('About', self)
            about_action.triggered.connect(self._show_about)
            help_menu.addAction(about_action)
        except Exception as e:
            logger.exception(f'Error in _setup_menu: {e}')

    def _setup_shortcuts(self):
        try:
            logger.info('_setup_shortcuts called')
            shortcuts = [(QKeySequence('S'), lambda: self.mode_toolbar.set_mode('select')),
                         (QKeySequence('E'), lambda: self.mode_toolbar.set_mode('edit')),
                         (QKeySequence('D'), lambda: self.mode_toolbar.set_mode('delete')),
                         (QKeySequence('1'), lambda: self._set_bond_mode('S')),
                         (QKeySequence('2'), lambda: self._set_bond_mode('D')),
                         (QKeySequence('3'), lambda: self._set_bond_mode('T')),
                         (QKeySequence('4'), lambda: self._set_bond_mode('A')),
                         (QKeySequence('5'), lambda: self._set_bond_mode('DA')),
                         (QKeySequence('C'), self._clear_scene),
                         (QKeySequence('N'), self._show_name_dialog), (QKeySequence('H'), self._toggle_help)]
            for seq, slot in shortcuts:
                sc = QShortcut(seq, self)
                sc.activated.connect(slot)
        except Exception as e:
            logger.exception(f'Error in _setup_shortcuts: {e}')

    def _on_mode_changed(self, mode: str):
        try:
            self.canvas.set_tool_mode(mode)
            self.canvas.cancel_structure_placement()
            self.action_toolbar.set_edit_mode_active(mode == 'edit')
        except Exception as e:
            logger.exception(f'Error in _on_mode_changed: {e}')

    def _on_bond_mode_changed(self, mode: str):
        try:
            self.canvas.set_bond_mode(mode)
        except Exception as e:
            logger.exception(f'Error in _on_bond_mode_changed: {e}')

    def _on_formal_charge_toggled(self, sign: str):
        """Toolbar +/- button was clicked; sign is the toolbar's new
        authoritative state: '+' / '-' / '' (untoggled). Mirror it onto the
        canvas so atom clicks know what to apply."""
        try:
            self.canvas.set_formal_charge_sign(sign or None)
        except Exception as e:
            logger.exception(f'Error in _on_formal_charge_toggled: {e}')

    def _on_chain_toggled(self, active: bool):
        """Toolbar chain button was clicked; mirror its state onto the
        canvas so mouse drags know whether to build a chain. Turning the
        tool on also force-switches to Edit mode (same expectation as the
        bond-type button — picking a drawing tool should put you in the
        mode that lets you draw)."""
        try:
            if active and self.mode_toolbar.current_mode != 'edit':
                self.mode_toolbar.set_mode('edit')
            self.canvas.set_chain_active(active)
        except Exception as e:
            logger.exception(f'Error in _on_chain_toggled: {e}')

    def _on_formal_charge_rejected(self, reason: str):
        try:
            self.statusBar().showMessage(f'Formal charge not applied — {reason}', 4000)
        except Exception as e:
            logger.exception(f'Error in _on_formal_charge_rejected: {e}')

    def _on_rotate_requested(self, degrees: float):
        try:
            self.canvas.rotate_selection(degrees)
        except Exception as e:
            logger.exception(f'Error in _on_rotate_requested: {e}')

    def _on_flip_requested(self, axis: str):
        try:
            self.canvas.flip_selection(axis)
        except Exception as e:
            logger.exception(f'Error in _on_flip_requested: {e}')

    def _on_transform_no_target(self):
        try:
            self.statusBar().showMessage('Nothing to transform — canvas is empty', 3000)
        except Exception as e:
            logger.exception(f'Error in _on_transform_no_target: {e}')

    def _set_bond_mode(self, mode: str):
        try:
            self.canvas.set_bond_mode(mode)
            self.action_toolbar.set_bond_mode(mode)
        except Exception as e:
            logger.exception(f'Error in _set_bond_mode: {e}')

    def _on_element_selected(self, element: str):
        try:
            self.canvas.set_selected_element(element)
            self.mode_toolbar.set_mode('edit')
        except Exception as e:
            logger.exception(f'Error in _on_element_selected: {e}')

    def _show_periodic(self):
        try:
            dialog = PeriodicDialog(self)
            dialog.element_selected.connect(self._on_periodic_selected)
            dialog.exec()
        except Exception as e:
            logger.exception(f'Error in _show_periodic: {e}')

    def _on_periodic_selected(self, element: str):
        try:
            if element not in VISIBLE_ELEMENTS:
                VISIBLE_ELEMENTS.append(element)
                COLORS.setdefault(element, (200, 200, 200))
                VALENCES.setdefault(element, 4)
                RADIUS.setdefault(element, 22)
            self.element_panel.add_recent(element)
            self.element_panel.select_element(element)
            self._on_element_selected(element)
        except Exception as e:
            logger.exception(f'Error in _on_periodic_selected: {e}')

    def _on_structure_selected(self, entry: StructureEntry):
        """Called when the user picks a tile in the Structure Browser. Enters
        ghost-placement mode on the canvas; the structure is committed where
        they next click (handled inside CanvasView)."""
        try:
            atoms, bonds = entry.ghost_geometry()
            if not atoms:
                logger.warning(f"_on_structure_selected: '{entry.name}' has no usable geometry")
                QMessageBox.warning(self, 'Structure Unavailable',
                                    f"Could not load the structure for '{entry.name}'.")
                return
            self.mode_toolbar.set_mode('edit')
            self.canvas.begin_structure_placement(atoms, bonds, entry.name)
            self.statusBar().showMessage(
                f"Placing {entry.name} — click on the canvas to drop it, Esc to cancel", 4000
            )
        except Exception as e:
            logger.exception(f'Error in _on_structure_selected: {e}')

    def _on_molecule_card_clicked(self, atom_ids: set):
        """A 'Molecules on Canvas' / 'Selected Molecules' card was clicked —
        select every atom of that molecule (all copies, if it's a
        deduplicated x-N card) exactly as if the user had drawn a marquee
        around it, then let the normal selection-changed pipeline refresh
        the info panel into whichever case the resulting selection calls for."""
        try:
            if not atom_ids:
                return
            self.canvas.scene.set_selected_atoms(set(atom_ids))
            self.canvas.selection_changed.emit()
        except Exception as e:
            logger.exception(f'Error in _on_molecule_card_clicked: {e}')

    def _on_selection_changed(self):
        try:
            self._update_info_panel()
            self._update_status_bar()
        except Exception as e:
            logger.exception(f'Error in _on_selection_changed: {e}')

    def _push_undo(self):
        try:
            self.undo_manager.snapshot(self.mol)
            self._update_undo_buttons()
        except Exception as e:
            logger.exception(f'Error in _push_undo: {e}')

    def _on_topology_changed(self):
        """Call this when atoms/bonds are added/removed (not just moved).
        Undo push happens earlier, at the mutation site itself (via
        mutation_about_to_apply / atoms_deleted / chain_about_to_build,
        all emitted BEFORE the mutation) — not here, since by this point
        self.mol already reflects the post-mutation state and pushing here
        would snapshot the wrong moment, corrupting undo granularity."""
        try:
            self._update_info_panel()
            self._update_undo_buttons()
            self._update_status_bar()
            self._check_name_update()
        except Exception as e:
            logger.exception(f'Error in _on_topology_changed: {e}')

    def _undo(self):
        try:
            if self.undo_manager.undo(self.mol):
                self.canvas.scene.rebuild()
                self._update_info_panel()
                self._update_undo_buttons()
                self._update_status_bar()
                self._check_name_update()
        except Exception as e:
            logger.exception(f'Error in _undo: {e}')

    def _redo(self):
        try:
            if self.undo_manager.redo(self.mol):
                self.canvas.scene.rebuild()
                self._update_info_panel()
                self._update_undo_buttons()
                self._update_status_bar()
                self._check_name_update()
        except Exception as e:
            logger.exception(f'Error in _redo: {e}')

    def _update_undo_buttons(self):
        try:
            can_u = self.undo_manager.can_undo
            can_r = self.undo_manager.can_redo
            self.action_toolbar.set_undo_enabled(can_u)
            self.action_toolbar.set_redo_enabled(can_r)
        except Exception as e:
            logger.exception(f'Error in _update_undo_buttons: {e}')

    def _clear_scene(self):
        try:
            self.undo_manager.snapshot(self.mol)
            self.mol.clear()
            self.canvas.scene.rebuild()
            self.canvas.reset_view()
            self._update_info_panel()
            self._update_undo_buttons()
            self._update_status_bar()
            self.display_name = ''
            self._current_whole_smiles = None
            self._current_fragment_smiles = None
        except Exception as e:
            logger.exception(f'Error in _clear_scene: {e}')

    def _new_scene(self):
        try:
            self._clear_scene()
            self.last_save_path = None
            self.setWindowTitle('Carbon Simulator - Untitled')
        except Exception as e:
            logger.exception(f'Error in _new_scene: {e}')

    def _clear_up(self):
        try:
            self.undo_manager.snapshot(self.mol)
            new_mol = clear_up_molecule(self.mol)
            self.mol.atoms = new_mol.atoms
            self.mol.bonds = new_mol.bonds
            self.mol.next_id = new_mol.next_id
            self.canvas.scene.rebuild()
            self.canvas.center_molecule()
            self._on_topology_changed()
        except Exception as e:
            logger.exception(f'Error in _clear_up: {e}')

    def _show_name_dialog(self):
        try:
            dialog = NameInputDialog(self)
            dialog.build_requested.connect(self._build_from_name)
            dialog.exec()
        except Exception as e:
            logger.exception(f'Error in _show_name_dialog: {e}')

    def _build_from_name(self, name: str):
        try:
            self._progress = QProgressDialog('Building molecule...', '', 0, 0, self)
            self._progress.setWindowModality(Qt.WindowModality.WindowModal)
            self._progress.setWindowTitle('Please Wait')
            self._progress.setCancelButton(None)
            self._progress.show()
            self._build_worker = BuildWorker(name)
            self._build_worker.molecule_ready.connect(self._on_build_ready)
            self._build_worker.finished.connect(self._progress.close)
            self._build_worker.finished.connect(self._build_worker.deleteLater)
            self._build_worker.start()
        except Exception as e:
            logger.exception(f'Error in _build_from_name: {e}')

    def _on_build_ready(self, new_mol):
        try:
            if new_mol:
                self.undo_manager.snapshot(self.mol)
                self.mol.atoms = new_mol.atoms
                self.mol.bonds = new_mol.bonds
                self.mol.next_id = new_mol.next_id
                self.canvas.scene.rebuild()
                self.canvas.reset_view()
                self._on_topology_changed()
            else:
                logger.warning('Build failed: new_mol is None')
                QMessageBox.warning(self, 'Build Failed', 'Could not build molecule from that name.')
        except Exception as e:
            logger.exception(f'Error in _on_build_ready: {e}')

    def _check_name_update(self):
        """Recompute whole-molecule name only if the graph changed."""
        try:
            if not self.mol.atoms:
                self.display_name = ''
                self._current_whole_smiles = None
                self._update_info_panel()
                return
            smiles = compute_smiles(self.mol)
            if not smiles or smiles == self._current_whole_smiles:
                return
            self._current_whole_smiles = smiles
            logger.info(f"_check_name_update: new SMILES='{smiles[:80]}'")
            if smiles in self._name_cache:
                self.display_name = self._name_cache[smiles]
                logger.info(f"_check_name_update: memory cache hit → '{self.display_name[:60]}'")
                self._update_info_panel()
                return
            if self._current_name_worker and self._current_name_worker.isRunning():
                return
            self._current_name_worker = NameWorker(self.mol.to_dict())
            self._current_name_worker.name_ready.connect(lambda name, s=smiles: self._on_name_ready(name, s))
            self._current_name_worker.finished.connect(self._cleanup_name_worker)
            self._current_name_worker.start()
            logger.info('_check_name_update: started NameWorker')
        except Exception as e:
            logger.exception(f'Error in _check_name_update: {e}')

    def _on_name_ready(self, name: str, smiles: str):
        try:
            self._name_cache[smiles] = name
            self.display_name = name
            self._update_info_panel()
        except Exception as e:
            logger.exception(f'Error in _on_name_ready: {e}')

    def _cleanup_name_worker(self):
        try:
            sender = self.sender()
            if sender == self._current_name_worker:
                self._current_name_worker.deleteLater()
                self._current_name_worker = None
        except Exception as e:
            logger.exception(f'Error in _cleanup_name_worker: {e}')

    def _lookup_fragment_name(self, frag_mol: Molecule, smiles: str):
        """Background name lookup for a single fragment."""
        try:
            if smiles in self._name_cache:
                cached = self._name_cache[smiles]
                logger.info(f"_lookup_fragment_name: cache hit → '{cached[:60]}'")
                self.info_panel.update_fragment_name(cached)
                return
            if self._fragment_name_worker and self._fragment_name_worker.isRunning():
                return
            self._fragment_name_worker = NameWorker(frag_mol.to_dict())
            self._fragment_name_worker.name_ready.connect(lambda name, s=smiles: self._on_fragment_name_ready(name, s))
            self._fragment_name_worker.finished.connect(self._cleanup_fragment_name_worker)
            self._fragment_name_worker.start()
            logger.info('_lookup_fragment_name: started NameWorker')
        except Exception as e:
            logger.exception(f'Error in _lookup_fragment_name: {e}')

    def _on_fragment_name_ready(self, name: str, smiles: str):
        self._name_cache[smiles] = name
        self.info_panel.update_fragment_name(name)

    def _cleanup_fragment_name_worker(self):
        try:
            sender = self.sender()
            if sender == self._fragment_name_worker:
                self._fragment_name_worker.deleteLater()
                self._fragment_name_worker = None
        except Exception as e:
            logger.exception(f'Error in _cleanup_fragment_name_worker: {e}')

    def _update_info_panel(self):
        """Recompute fragments and refresh InfoPanel based on selection state."""
        try:
            selected = self.canvas.get_selected_atoms()
            fragments = find_fragments(self.mol)
            logger.info(f'_update_info_panel: {len(selected)} selected, {len(fragments)} fragments total')
            fragment_smiles = self._compute_fragment_smiles_map(fragments)
            if len(selected) == 0:
                self._show_no_selection_case(fragments, fragment_smiles)
            elif len(selected) == 1:
                self._show_single_atom_case(selected, fragments, fragment_smiles)
            else:
                self._show_multi_atom_case(selected, fragments, fragment_smiles)
        except Exception as e:
            logger.exception(f'Error in _update_info_panel: {e}')

    def _compute_fragment_smiles_map(self, fragments) -> dict:
        fragment_smiles: dict[frozenset, str] = {}
        for frag in fragments:
            frag_mol = extract_fragment_mol(self.mol, frag)
            smiles = compute_smiles(frag_mol)
            fragment_smiles[frozenset(frag)] = smiles
        return fragment_smiles

    @staticmethod
    def _fragment_dedup_key(info: dict, smiles: str) -> str:
        return smiles if smiles else f"{info['formula_plain']}_{info['atom_count']}_{info['charge']}"

    def _show_no_selection_case(self, fragments, fragment_smiles: dict):
        """Case 1: nothing selected — list every distinct fragment on the canvas."""
        self._current_fragment_smiles = None
        frag_data = []
        seen: dict[str, dict] = {}
        for frag in fragments:
            smiles = fragment_smiles.get(frozenset(frag), '')
            info = self._compute_fragment_info(frag, detailed=False)
            info['smiles'] = smiles
            info['count'] = 1
            key = self._fragment_dedup_key(info, smiles)
            if key in seen:
                seen[key]['count'] += 1
                seen[key]['atom_ids'] |= info['atom_ids']  # select ALL copies on click, not just the first
            else:
                seen[key] = info
                frag_data.append(info)
        self.info_panel.set_case_1(frag_data)

    def _show_single_atom_case(self, selected: set, fragments, fragment_smiles: dict):
        """Case 2: exactly one atom selected — show full detail for its fragment,
        including the per-atom valence/charge breakdown for that one atom."""
        atom_id = next(iter(selected))
        target_frag = set(next((frag for frag in fragments if atom_id in frag), ()))
        if not target_frag:
            logger.warning('Case 2: selected atom not found in any fragment')
            self.info_panel.set_empty()
            return
        info = self._show_fragment_detail(target_frag, fragment_smiles)
        atom = self.mol.get_atom(atom_id)
        self.info_panel.set_case_2(info, atom, self.mol)

    def _refresh_fragment_name_if_changed(self, target_frag, frag_smiles: str):
        if frag_smiles == self._current_fragment_smiles:
            return
        self._current_fragment_smiles = frag_smiles
        if frag_smiles in self._name_cache:
            self.info_panel.update_fragment_name(self._name_cache[frag_smiles])
        elif len(target_frag) >= 2:
            frag_mol = extract_fragment_mol(self.mol, target_frag)
            self._lookup_fragment_name(frag_mol, frag_smiles)
        else:
            self.info_panel.update_fragment_name('')

    def _show_multi_atom_case(self, selected: set, fragments, fragment_smiles: dict):
        """Case 3: multiple atoms selected.

        If the selection touches exactly one distinct molecule, there's
        nothing to list — just show that molecule's full detail view
        (same as Case 2, minus the single-atom breakdown, since several
        atoms are selected rather than one specific atom). A fragment list
        is only useful once the selection actually spans 2+ distinct
        molecules; otherwise it was a redundant single-item list repeating
        what the detail view already says more completely.
        """
        touched = [frag for frag in fragments if frag & selected]
        if len(touched) == 1:
            info = self._show_fragment_detail(touched[0], fragment_smiles)
            self.info_panel.set_case_2(info, None, self.mol)
            return
        self._current_fragment_smiles = None
        frag_data = []
        seen_keys = set()
        for frag in touched:
            smiles = fragment_smiles.get(frozenset(frag), '')
            info = self._compute_fragment_info(frag, detailed=False)
            info['smiles'] = smiles
            key = self._fragment_dedup_key(info, smiles)
            if key not in seen_keys:
                seen_keys.add(key)
                frag_data.append(info)
        self.info_panel.set_case_3(frag_data)

    def _show_fragment_detail(self, target_frag: set, fragment_smiles: dict):
        """Shared by Case 2 (single atom) and the single-molecule collapse
        of Case 3 (multiple atoms, but all within one molecule): renders
        the full molecule detail view. `atom` is omitted (None) whenever
        there isn't exactly one specific atom of interest, which correctly
        hides the per-atom valence/charge breakdown in that case."""
        frag_smiles = fragment_smiles.get(frozenset(target_frag), '')
        info = self._compute_fragment_info(target_frag, detailed=True)
        info['smiles'] = frag_smiles
        self._refresh_fragment_name_if_changed(target_frag, frag_smiles)
        if len(target_frag) == len(self.mol.atoms) and self.display_name:
            info['name'] = self.display_name
        return info

    def _compute_fragment_info(self, atom_ids: Set[int], detailed: bool = False) -> dict:
        """Gather info dictionary for a fragment."""
        frag_mol = extract_fragment_mol(self.mol, atom_ids)
        formula, mass, charge = compute_fragment_formula(frag_mol)
        formula_html = format_formula_html(formula, charge)
        bond_count = sum(1 for b in self.mol.bonds if b.a1 in atom_ids and b.a2 in atom_ids)
        composition: dict[str, int] = {}
        for a in self.mol.atoms:
            if a.id in atom_ids:
                composition[a.element] = composition.get(a.element, 0) + 1
        info = {'formula_html': formula_html, 'formula_plain': formula, 'mass': mass, 'charge': charge,
                'atom_count': len(atom_ids), 'bond_count': bond_count, 'composition': composition,
                'atom_ids': set(atom_ids)}
        if detailed:
            info['ionic_pairs'] = self._count_ionic_pairs(atom_ids)
            info['smiles'] = self._compute_fragment_smiles_safe(frag_mol)
            if len(atom_ids) == len(self.mol.atoms) and self.display_name:
                info['name'] = self.display_name
        return info

    def _count_ionic_pairs(self, atom_ids: Set[int]) -> int:
        charged = [a for a in self.mol.atoms if a.id in atom_ids and a.formal_charge != 0]
        ionic_pairs = 0
        for i, a1 in enumerate(charged):
            for a2 in charged[i + 1:]:
                if a1.formal_charge * a2.formal_charge >= 0:
                    continue
                d = math.hypot(a1.x - a2.x, a1.y - a2.y)
                if d <= IONIC_DISTANCE:
                    ionic_pairs += 1
        return ionic_pairs

    @staticmethod
    def _compute_fragment_smiles_safe(frag_mol) -> str:
        try:
            rdmol = molecule_to_rdkit(frag_mol)
            if rdmol:
                return Chem.MolToSmiles(rdmol, canonical=True)
            return ''
        except Exception as e:
            logger.warning(f'_compute_fragment_smiles_safe failed: {e}')
            return ''

    def _update_status_bar(self):
        """Poll live state and refresh status bar labels."""
        try:
            zoom = self.canvas.get_zoom()
            mouse_world = self.canvas.get_mouse_world_pos()
            self._status_coords.setText(f'X: {mouse_world.x():.1f}  Y: {mouse_world.y():.1f}')
            self._status_zoom.setText(f'Zoom: {zoom * 100:.0f}%')
            self._status_mol.setText(f'Atoms: {len(self.mol.atoms)}  Bonds: {len(self.mol.bonds)}')
        except Exception as e:
            logger.exception(f'Error in _update_status_bar: {e}')

    def _toggle_help(self):
        try:
            visible = self.help_overlay.isVisible()
            self.help_overlay.setVisible(not visible)
            if self.help_overlay.isVisible():
                self.help_overlay.raise_()
        except Exception as e:
            logger.exception(f'Error in _toggle_help: {e}')

    def _show_about(self):
        try:
            QMessageBox.about(self, 'About Carbon Simulator',
                              '<h2>Carbon Simulator</h2><p>Created by Avyaya &bull; 2025</p><p>A molecular structure editor built with PyQt6 and RDKit.</p>')
        except Exception as e:
            logger.exception(f'Error in _show_about: {e}')

    def _toggle_grid(self, checked):
        try:
            self.canvas.set_grid_visible(checked)
        except Exception as e:
            logger.exception(f'Error in _toggle_grid: {e}')

    def _toggle_snap(self, checked):
        try:
            self.canvas.set_snap_enabled(checked)
        except Exception as e:
            logger.exception(f'Error in _toggle_snap: {e}')

    def _toggle_smart_join(self, checked):
        try:
            self.canvas.set_smart_join(checked)
        except Exception as e:
            logger.exception(f'Error in _toggle_smart_join: {e}')

    def _save_file(self):
        try:
            if self.last_save_path:
                cam = self.canvas.get_camera()
                save_scene(self.mol, self.last_save_path, cam[0], cam[1], self.canvas.get_zoom())
            else:
                self._save_as()
        except Exception as e:
            logger.exception(f'Error in _save_file: {e}')

    def _save_as(self):
        try:
            result = QFileDialog.getSaveFileName(self, 'Save Molecule', '', 'JSON Molecule (*.json)')
            path: str = result[0]
            if path:
                cam = self.canvas.get_camera()
                save_scene(self.mol, path, cam[0], cam[1], self.canvas.get_zoom())
                self.last_save_path = path
                filename = Path(path).name
                self.setWindowTitle(f'Carbon Simulator - {filename}')
                logger.info(f'Saved as: {path}')
        except Exception as e:
            logger.exception(f'Error in _save_as: {e}')

    def _open_file(self):
        try:
            result = QFileDialog.getOpenFileName(self, 'Open Molecule', '', 'JSON Molecule (*.json)')
            path: str = result[0]
            if path:
                logger.info(f'Opening: {path}')
                try:
                    mol, cam_x, cam_y, zoom = load_scene(path)
                    self.undo_manager.snapshot(self.mol)
                    self.mol.atoms = mol.atoms
                    self.mol.bonds = mol.bonds
                    self.mol.next_id = mol.next_id
                    self.canvas.scene.rebuild()
                    self.canvas.set_camera(cam_x, cam_y)
                    self.canvas.set_zoom(zoom)
                    self.last_save_path = path
                    filename = Path(path).name
                    self.setWindowTitle(f'Carbon Simulator - {filename}')
                    self._on_topology_changed()
                except Exception as e:
                    logger.exception(f'Failed to load file: {e}')
                    QMessageBox.critical(self, 'Error', f'Failed to load file:\n{e}')
        except Exception as e:
            logger.exception(f'Error in _open_file: {e}')

    def _zoom_in(self):
        try:
            old = self.canvas.get_zoom()
            new = old * 1.2
            self.canvas.set_zoom(new)
        except Exception as e:
            logger.exception(f'Error in _zoom_in: {e}')

    def _zoom_out(self):
        try:
            old = self.canvas.get_zoom()
            new = old / 1.2
            self.canvas.set_zoom(new)
        except Exception as e:
            logger.exception(f'Error in _zoom_out: {e}')

    def keyPressEvent(self, event):
        try:
            if event.key() == Qt.Key.Key_Escape:
                self.canvas.cancel_structure_placement()
                self.help_overlay.hide()
            super().keyPressEvent(event)
        except Exception as e:
            logger.exception(f'Error in keyPressEvent: {e}')
