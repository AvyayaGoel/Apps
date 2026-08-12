"""
FormulaDialog Module (PyQt6)
Updated for FormulaEntry / FormulaCollection class structure.
No backward compatibility.
"""

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QPoint, QTimer
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QVBoxLayout, QWidget,
    QListWidget, QListWidgetItem, QScrollArea, QGridLayout,
    QMessageBox, QGraphicsDropShadowEffect, QSizePolicy, QTextEdit
)

from constants import NO_DIMENSION_UNITS, SAVE_FORMULA, FORMULA_DIALOG_STYLESHEET
from formula_entry import FormulaCollection, FormulaEntry
from formula_utils import FormulaUtils
from symbol_learner import SymbolLearner


# ── Custom Widgets ──

class FormulaLineEdit(QLineEdit):
    """Line edit with auto-bracket completion."""

    def keyPressEvent(self, event: QKeyEvent):
        char = event.text()
        if char and len(char) == 1 and char in '([{':
            pairs = {'(': ')', '[': ']', '{': '}'}
            closing = pairs[char]
            cursor = self.cursorPosition()
            super().keyPressEvent(event)
            self.insert(closing)
            self.setCursorPosition(cursor + 1)
            return
        super().keyPressEvent(event)


class GhostOverlay(QFrame):
    """Inline floating overlay — child of the dialog."""
    suggestion_accepted = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ghostOverlay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list_widget.itemClicked.connect(self._on_item_activated)
        self.list_widget.itemActivated.connect(self._on_item_activated)

        layout.addWidget(self.list_widget)

        self.setStyleSheet("""
            #ghostOverlay {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 4px;
            }
            QListWidget {
                background: transparent;
                color: #e0e0e0;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #2980b9;
            }
            QListWidget::item:hover:!selected {
                background-color: #3a3a3a;
            }
        """)

        self.hide()

    def set_suggestions(self, suggestions: List[Tuple[str, str, int]]):
        self.list_widget.clear()
        if not suggestions:
            self.hide()
            return

        for i, (name, unit, confidence) in enumerate(suggestions):
            colors = {1: "🔴 Low", 2: "🟡 Medium", 3: "🟢 High"}
            badge = colors.get(confidence, "")
            text = f"[{i + 1}/{len(suggestions)}]  {name}  ·  {unit}  ({badge})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (name, unit))
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.list_widget.item(0).setSelected(True)

        row_height = max(self.list_widget.sizeHintForRow(0), 32)
        content_width = max(self.list_widget.sizeHintForColumn(0), 220)
        total_height = len(suggestions) * row_height + 4
        total_width = content_width + 8

        self.list_widget.setFixedSize(total_width, total_height)
        self.setFixedSize(total_width, total_height)

        self.show()
        self.raise_()

    def _on_item_activated(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            name, unit = data
            self.suggestion_accepted.emit(name, unit)

    def has_focus(self) -> bool:
        fw = self.window().focusWidget()
        return fw is not None and (fw is self or self.isAncestorOf(fw))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class VariableChip(QFrame):
    """Removable variable chip."""

    remove_requested = pyqtSignal(object)
    edit_requested = pyqtSignal(str, str, str)

    def __init__(self, symbol: str, name: str, unit: str, parent=None):
        super().__init__(parent)

        self.symbol = symbol
        self.name = name
        self.unit = unit

        self.setObjectName("varChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)

        badge = QLabel(symbol)
        badge.setStyleSheet("""
            background-color: #2980b9;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 12px;
        """)
        layout.addWidget(badge)

        unit_display = "" if unit.lower() in NO_DIMENSION_UNITS else f"· {unit}"
        info = QLabel(f"{name}  <span style='color:#888'>{unit_display}</span>")
        info.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        layout.addWidget(info)

        layout.addStretch()

        edit_btn = QPushButton("✎")
        edit_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: none; font-size: 12px; padding: 2px; }
            QPushButton:hover { color: #3498db; }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(symbol, name, unit))
        layout.addWidget(edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: none; font-size: 12px; padding: 2px; }
            QPushButton:hover { color: #e74c3c; }
        """)
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(del_btn)

        self.setStyleSheet("""
            #varChip {
                background-color: #252525;
                border-radius: 6px;
                border: 1px solid #333;
            }
            #varChip:hover {
                border-color: #444;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)


class TagChip(QFrame):
    """Removable tag chip with fixed sizing to prevent overlap."""

    removed = pyqtSignal(str)

    def __init__(self, tag: str, parent=None):
        super().__init__(parent)
        self.tag = tag

        self.setStyleSheet('''
            QFrame {
                background-color: #252525;
                border-radius: 10px;
                border: 1px solid #333;
            }
            QLabel {
                color: #e0e0e0;
                padding-left: 8px;
                font-size: 12px;
                background: transparent;
            }
            QPushButton {
                color: #888;
                border: none;
                background: transparent;
                padding: 2px 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                color: white;
                background: rgba(255,255,255,0.08);
                border-radius: 6px;
            }
        ''')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 2, 2)
        layout.setSpacing(2)

        label = QLabel(tag)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        remove_btn = QPushButton('✕')
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setFixedSize(18, 18)
        remove_btn.clicked.connect(lambda: self.removed.emit(tag))

        layout.addWidget(label)
        layout.addWidget(remove_btn)


# ── Main Dialog ──

class FormulaDialog(QDialog):
    """Formula entry/edit dialog with auto-resizing layout."""

    def __init__(self, parent=None, edit_data: FormulaEntry | None = None,
                 master_data: FormulaCollection | None = None,
                 symbol_learner: SymbolLearner | None = None, max_suggestions: int = 3):
        super().__init__(parent)

        self.parent = parent
        self.edit_mode = edit_data is not None
        self.edit_id = edit_data.display_id if isinstance(edit_data, FormulaEntry) else None
        self.variables: List[Dict] = [v.to_dict() for v in edit_data.variables] if isinstance(edit_data,
                                                                                              FormulaEntry) else []
        self.master_data = master_data or FormulaCollection()

        self.symbol_learner = symbol_learner
        if self.symbol_learner is None and len(self.master_data) > 0:
            self.symbol_learner = SymbolLearner()
            self.symbol_learner.learn(self.master_data)

        self.max_suggestions = max_suggestions
        self._ghost_overlay: Optional[GhostOverlay] = None
        self._result: Optional[Dict] = None

        self.setWindowTitle("Edit Formula" if self.edit_mode else "New Formula")
        self.setMinimumSize(1100, 700)

        self.tags = []
        self.tags_input = None
        self.tags_container = None
        self.tags_scroll = None
        self.tags_chips_widget = None

        self._build_ui()
        self._apply_styles()
        self._update_combobox_data()

        if not self.edit_mode:
            self._clear_all_fields()

        if edit_data:
            self._load_edit_data(edit_data)

        self._install_enter_navigation()

        self.keypad_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.keypad_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.keypad_shortcut.activated.connect(self.parent.toggle_keypad)

        self.esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.esc_shortcut.activated.connect(self.reject)
        if self.symbol_learner:
            self.symbol_learner.start_session(
                self.subject_cb.currentText(),
                self.topic_cb.currentText(),
                self.subtopic_cb.currentText()
            )

    # ── UI Construction ──

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        # HEADER
        header_text = (
            f"✎  EDIT FORMULA #{self.edit_id}"
            if self.edit_mode else
            "➕  NEW FORMULA"
        )

        header = QLabel(header_text)
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #e0e0e0;
        """)
        outer.addWidget(header)

        # MAIN GRID
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(16)

        # LEFT SIDE - FORMULA
        formula_container = QFrame()
        formula_container.setObjectName("inputFrame")

        formula_layout = QVBoxLayout(formula_container)
        formula_layout.setContentsMargins(14, 12, 14, 12)
        formula_layout.setSpacing(8)

        formula_lbl = QLabel("FORMULA")
        formula_lbl.setStyleSheet(FORMULA_DIALOG_STYLESHEET)

        self.formula_field = FormulaLineEdit()
        self.formula_field.setPlaceholderText("e.g.  F = ma")

        math_font = QFont("Cambria Math", 16)
        math_font.setStyleHint(QFont.StyleHint.Serif)
        self.formula_field.setFont(math_font)

        formula_layout.addWidget(formula_lbl)
        formula_layout.addWidget(self.formula_field)

        grid.addWidget(formula_container, 0, 0, 1, 2)

        # CLASSIFICATION
        left_panel = QFrame()
        left_panel.setObjectName("inputFrame")

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(12)

        meta_lbl = QLabel("CLASSIFICATION")
        meta_lbl.setStyleSheet(FORMULA_DIALOG_STYLESHEET)
        left_layout.addWidget(meta_lbl)

        self.subject_cb = QComboBox()
        self.subject_cb.setEditable(True)
        self.subject_cb.currentTextChanged.connect(self._on_subject_change)
        left_layout.addLayout(self._field_block("Subject", self.subject_cb))

        self.topic_cb = QComboBox()
        self.topic_cb.setEditable(True)
        self.topic_cb.currentTextChanged.connect(self._on_topic_change)
        left_layout.addLayout(self._field_block("Topic", self.topic_cb))

        self.subtopic_cb = QComboBox()
        self.subtopic_cb.setEditable(True)
        left_layout.addLayout(self._field_block("Sub-topic", self.subtopic_cb))

        left_layout.addStretch()

        grid.addWidget(left_panel, 1, 0)

        # VARIABLES
        right_panel = QFrame()
        right_panel.setObjectName("inputFrame")

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        var_lbl = QLabel("VARIABLES")
        var_lbl.setStyleSheet(FORMULA_DIALOG_STYLESHEET)
        right_layout.addWidget(var_lbl)

        self.chips_scroll = QScrollArea()
        self.chips_scroll.setWidgetResizable(True)
        self.chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chips_scroll.setMinimumHeight(130)

        self.chips_widget = QWidget()
        self.chips_widget.setStyleSheet("""
            background-color: #252525;
        """)

        self.chips_layout = QVBoxLayout(self.chips_widget)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)
        self.chips_layout.addStretch()

        self.chips_scroll.setWidget(self.chips_widget)
        right_layout.addWidget(self.chips_scroll)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.sym_field = QLineEdit()
        self.sym_field.setPlaceholderText("v")
        self.sym_field.setMaximumWidth(90)
        self.sym_field.textChanged.connect(self._on_symbol_change)

        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Velocity")

        self.unit_field = QLineEdit()
        self.unit_field.setPlaceholderText("m/s")
        self.unit_field.setMaximumWidth(110)

        self._ghost_overlay = GhostOverlay(self)
        self._ghost_overlay.suggestion_accepted.connect(self._accept_ghost)
        self._ghost_overlay.hide()

        add_btn = QPushButton("+")
        add_btn.setObjectName("addBtn")
        add_btn.setFixedWidth(42)
        add_btn.clicked.connect(self._add_variable)

        row.addWidget(self.sym_field)
        row.addWidget(self.name_field, 1)
        row.addWidget(self.unit_field)
        row.addWidget(add_btn)

        right_layout.addLayout(row)

        grid.addWidget(right_panel, 1, 1)

        # TAGS
        tags_frame = QFrame()
        tags_frame.setObjectName("inputFrame")

        tags_layout = QVBoxLayout(tags_frame)
        tags_layout.setContentsMargins(14, 12, 14, 12)
        tags_layout.setSpacing(10)

        tags_lbl = QLabel("TAGS")
        tags_lbl.setStyleSheet(FORMULA_DIALOG_STYLESHEET)
        tags_layout.addWidget(tags_lbl)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(8)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Add tag and press Enter...")
        self.tags_input.returnPressed.connect(self.add_tag)

        tag_add_btn = QPushButton("+ Add Tag")
        tag_add_btn.setObjectName("addBtn")
        tag_add_btn.clicked.connect(self.add_tag)

        tag_row.addWidget(self.tags_input, 1)
        tag_row.addWidget(tag_add_btn)

        tags_layout.addLayout(tag_row)

        self.tags_scroll = QScrollArea()
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tags_scroll.setMinimumHeight(70)

        self.tags_chips_widget = QWidget()
        self.tags_chips_widget.setStyleSheet("""
            background-color: #252525;
        """)

        self.tags_container = QHBoxLayout(self.tags_chips_widget)
        self.tags_container.setContentsMargins(0, 0, 0, 0)
        self.tags_container.setSpacing(6)
        self.tags_container.addStretch()

        self.tags_scroll.setWidget(self.tags_chips_widget)
        tags_layout.addWidget(self.tags_scroll)

        grid.addWidget(tags_frame, 2, 0, 1, 2)

        # NOTES SIDEBAR
        notes_panel = QFrame()
        notes_panel.setObjectName("inputFrame")

        notes_layout = QVBoxLayout(notes_panel)
        notes_layout.setContentsMargins(14, 14, 14, 14)
        notes_layout.setSpacing(10)

        notes_lbl = QLabel("NOTES")
        notes_lbl.setStyleSheet(FORMULA_DIALOG_STYLESHEET)
        notes_layout.addWidget(notes_lbl)

        self.notes_field = QTextEdit()
        self.notes_field.setPlaceholderText("Assumptions, derivations, hints...")
        self.notes_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        notes_layout.addWidget(self.notes_field)

        grid.addWidget(notes_panel, 0, 2, 3, 1)

        # STRETCHING
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 2)

        grid.setRowStretch(0, 2)
        grid.setRowStretch(1, 2)
        grid.setRowStretch(2, 1)

        outer.addLayout(grid)

        # ACTIONS
        outer.addStretch()

        actions = QHBoxLayout()
        actions.addStretch()

        if self.edit_mode:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setObjectName("secondaryBtn")
            cancel_btn.clicked.connect(self.reject)
            cancel_btn.setMinimumHeight(38)
            actions.addWidget(cancel_btn)

        save_text = "Update Formula" if self.edit_mode else SAVE_FORMULA

        self.save_btn = QPushButton(save_text)
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self._save)
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setMinimumWidth(180)

        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self._save)

        actions.addWidget(self.save_btn)

        outer.addLayout(actions)

    def _field_block(self, title: str, widget):
        layout = QVBoxLayout()
        layout.setSpacing(4)

        lbl = self._small_label(title)
        layout.addWidget(lbl)
        layout.addWidget(widget)

        return layout

    def add_tag(self):
        text = self.tags_input.text().strip().lower()
        text = text.lstrip("#").strip()
        if not text:
            return
        if text in self.tags:
            self.tags_input.clear()
            return

        self.tags.append(text)
        self.tags_input.clear()
        self.refresh_tags_ui()
        self._resize_to_fit_content()

    def remove_tag(self, tag: str):
        if tag in self.tags:
            self.tags.remove(tag)
        self.refresh_tags_ui()
        self._resize_to_fit_content()

    def refresh_tags_ui(self):
        while self.tags_container.count():
            item = self.tags_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for tag in self.tags:
            chip = TagChip(tag)
            chip.removed.connect(self.remove_tag)
            self.tags_container.addWidget(chip)

        self.tags_container.addStretch()

    def _resize_to_fit_content(self):
        self.adjustSize()
        w = max(self.width(), 900)
        h = max(self.height(), 680)
        self.resize(w, h)

    @staticmethod
    def _small_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #777; font-size: 11px;")
        return lbl

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QWidget { font-family: "Segoe UI", "Arial", sans-serif; font-size: 13px; }
            QLineEdit {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit:focus { border-color: #2980b9; }
            QComboBox {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px;
                min-height: 32px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                selection-background-color: #2980b9;
            }
            QComboBox::editable { background-color: #2d2d2d; }
            #inputFrame {
                background-color: #252525;
                border-radius: 6px;
                border: 1px solid #2a2a2a;
            }
            #addBtn {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            #addBtn:hover { background-color: #2ecc71; }
            #secondaryBtn {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px 16px;
            }
            #secondaryBtn:hover { background-color: #4a4a4a; }
            #saveBtn {
                background-color: #2980b9;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            #saveBtn:hover { background-color: #3498db; }
            QScrollArea { border: none; background: transparent; }
            QTextEdit {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
            }
            QTextEdit:focus {
                border-color: #2980b9;
            }
        """)

    # ── Enter Navigation ──

    def _install_enter_navigation(self):
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)

        key = event.key()
        modifiers = event.modifiers()

        if self._ghost_overlay.isVisible():
            overlay_focused = self._ghost_overlay.has_focus()

            if overlay_focused:
                if key == Qt.Key.Key_Escape:
                    self._hide_ghost()
                    return True
                return False

            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self._ghost_overlay.list_widget.setFocus()
                return True

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._hide_ghost()
                self.name_field.setFocus()
                self.name_field.selectAll()
                return True

        if (self._handle_shift_enter(key, modifiers)
                or self._handle_enter(key, modifiers)
                or self._handle_escape(key)):
            return True

        return super().eventFilter(obj, event)

    def _handle_shift_enter(self, key: int, modifiers) -> bool:
        if key not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        if modifiers != Qt.KeyboardModifier.ShiftModifier:
            return False
        self._navigate_field(backward=True)
        return True

    def _handle_enter(self, key: int, modifiers) -> bool:
        if key not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        if modifiers != Qt.KeyboardModifier.NoModifier:
            return False

        if getattr(self, '_block_next_enter', False):
            return True

        if self._ghost_overlay_visible() and not self._ghost_overlay.has_focus():
            self._hide_ghost()
            return True

        if self._ghost_overlay_visible() and self._ghost_overlay.has_focus():
            return False

        self._navigate_field(backward=False)
        return True

    def _handle_escape(self, key: int) -> bool:
        if key != Qt.Key.Key_Escape:
            return False
        if not self._ghost_overlay:
            return False
        self._hide_ghost()
        return True

    def _ghost_overlay_visible(self) -> bool:
        return self._ghost_overlay is not None and self._ghost_overlay.isVisible()

    def _navigate_field(self, backward: bool = False):
        focus_order = self._get_focus_order()
        current = self._resolve_focus_widget()

        if current is None:
            return

        try:
            idx = focus_order.index(current)
        except ValueError:
            return

        new_idx = self._compute_new_index(idx, backward, len(focus_order), current)

        if new_idx is None:
            return

        target = focus_order[new_idx]
        self._focus_and_select(target)

    def _get_focus_order(self) -> list:
        return [
            self.formula_field,
            self.subject_cb,
            self.topic_cb,
            self.subtopic_cb,
            self.sym_field,
            self.name_field,
            self.unit_field,
        ]

    def _resolve_focus_widget(self):
        current = self.focusWidget()
        for field in self._get_focus_order():
            if current is field:
                return field
            if isinstance(field, QComboBox) and field.isEditable() and current is field.lineEdit():
                return field
        return None

    def _compute_new_index(self, idx: int, backward: bool, length: int, current) -> int | None:
        if backward:
            return (idx - 1) % length

        next_idx = idx + 1
        if next_idx < length:
            return next_idx

        if current == self.unit_field:
            self._add_variable()
            return None

        return 0

    def _focus_and_select(self, target):
        target.setFocus()
        edit_widget = self._get_editable_widget(target)
        if edit_widget is not None:
            edit_widget.selectAll()

    @staticmethod
    def _get_editable_widget(target):
        if isinstance(target, QLineEdit):
            return target
        if isinstance(target, QComboBox) and target.isEditable():
            return target.lineEdit()
        return None

    # ── Dynamic Data ──

    def _update_combobox_data(self):
        """Populate combobox dropdowns from master_data history."""
        subjects = self.master_data.subjects()
        topics_by_subject = self.master_data.topics_by_subject()
        subtopics_by_topic = self.master_data.subtopics_by_topic()

        self._topics_by_subject = topics_by_subject
        self._subtopics_by_topic = subtopics_by_topic

        self.subject_cb.clear()
        defaults = {"Physics", "Chemistry", "Maths"}
        self.subject_cb.addItems(sorted(subjects | defaults))

    def _clear_all_fields(self):
        self.formula_field.clear()
        self.subject_cb.setCurrentText("")
        self.topic_cb.clear()
        self.topic_cb.setCurrentText("")
        self.subtopic_cb.clear()
        self.subtopic_cb.setCurrentText("")
        self.sym_field.clear()
        self.name_field.clear()
        self.unit_field.clear()
        self.notes_field.clear()
        self.variables = []
        self.tags = []
        self.refresh_tags_ui()
        self._refresh_chips()

    def _on_subject_change(self, text: str):
        self.topic_cb.blockSignals(True)
        self.topic_cb.clear()
        topics = self._topics_by_subject.get(text, set())
        self.topic_cb.addItems(sorted(topics))
        self.topic_cb.setCurrentText("")
        self.topic_cb.blockSignals(False)

        self.subtopic_cb.clear()
        self.subtopic_cb.setCurrentText("")

        if self.sym_field.text().strip():
            self._on_symbol_change(self.sym_field.text())

    def _on_topic_change(self, text: str):
        subj = self.subject_cb.currentText()

        self.subtopic_cb.blockSignals(True)
        self.subtopic_cb.clear()
        subs = self._subtopics_by_topic.get((subj, text), set())
        self.subtopic_cb.addItems(sorted(subs))
        self.subtopic_cb.setCurrentText("")
        self.subtopic_cb.blockSignals(False)

        if self.sym_field.text().strip():
            self._on_symbol_change(self.sym_field.text())

    # ── Ghost Suggestions ──

    def _on_symbol_change(self, text: str):
        text = text.strip()
        if not text:
            self._hide_ghost()
            return

        if not self.symbol_learner or len(self.master_data) < 6:
            self._hide_ghost()
            return

        subj = self.subject_cb.currentText().strip() or "_GENERAL_"
        topic = self.topic_cb.currentText().strip() or "_GENERAL_"
        sub_topic = self.subtopic_cb.currentText().strip() or "_GENERAL_"

        try:
            matches = self.symbol_learner.all_matches(
                subj, topic, sub_topic, text,
                min_confidence=1,
                max_results=self.max_suggestions,
                live_variables=self.variables
            )
        except Exception:
            self._hide_ghost()
            return

        if not matches:
            self._hide_ghost()
            return

        suggestions = []
        conf_map = {1: [3], 2: [3, 2], 3: [3, 2, 1], 4: [3, 3, 2, 1]}
        levels = conf_map.get(len(matches), [3, 3, 2, 2, 1])

        for i, (name, unit) in enumerate(matches):
            conf = levels[min(i, len(levels) - 1)]
            suggestions.append((name, unit, conf))

        self._show_ghost(suggestions)

    def _show_ghost(self, suggestions):
        self._ghost_overlay.set_suggestions(suggestions)
        global_pos = self.sym_field.mapToGlobal(QPoint(0, self.sym_field.height()))
        local_pos = self.mapFromGlobal(global_pos)
        self._ghost_overlay.move(local_pos.x(), local_pos.y() + 2)
        self._ghost_overlay.raise_()

    def _hide_ghost(self):
        self._ghost_overlay.hide()
        self.sym_field.setFocus()

    def _accept_ghost(self, name: str, unit: str):
        self.name_field.setText(name)
        self.unit_field.setText(unit)
        self._hide_ghost()
        self.unit_field.setFocus()

        if self.symbol_learner:
            self.symbol_learner.record_acceptance(name, unit)

        self._block_next_enter = True
        QTimer.singleShot(50, lambda: setattr(self, '_block_next_enter', False))

    def hideEvent(self, event):
        self._hide_ghost()
        super().hideEvent(event)

    # ── Variables ──

    def _add_variable(self):
        sym = self.sym_field.text().strip()
        name = self.name_field.text().strip()
        unit = self.unit_field.text().strip()

        if not sym or not name:
            QMessageBox.warning(self, "Empty Variable", "Symbol and Name are required.")
            return

        for v in self.variables:
            if v["symbol"] == sym:
                reply = QMessageBox.question(
                    self, "Duplicate Symbol",
                    f"Symbol '{sym}' already exists. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    v["name"] = name
                    v["unit"] = unit
                    self._refresh_chips()
                    self._clear_var_fields()
                return

        self.variables.append({"symbol": sym, "name": name, "unit": unit})
        self._refresh_chips()
        self._clear_var_fields()

    def _remove_chip(self, chip: VariableChip):
        self.variables = [v for v in self.variables
                          if not (v["symbol"] == chip.symbol and v["name"] == chip.name)]
        self._refresh_chips()

    def _edit_chip(self, symbol: str, name: str, unit: str):
        self.sym_field.setText(symbol)
        self.name_field.setText(name)
        self.unit_field.setText(unit)
        self._remove_by_symbol(symbol)

    def _remove_by_symbol(self, symbol: str):
        self.variables = [v for v in self.variables if v["symbol"] != symbol]
        self._refresh_chips()

    def _refresh_chips(self):
        while self.chips_layout.count() > 1:
            item = self.chips_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for v in self.variables:
            chip = VariableChip(v["symbol"], v["name"], v["unit"])
            chip.remove_requested.connect(self._remove_chip)
            chip.edit_requested.connect(self._edit_chip)
            self.chips_layout.insertWidget(self.chips_layout.count() - 1, chip)

    def _clear_var_fields(self):
        self.sym_field.clear()
        self.name_field.clear()
        self.unit_field.clear()
        self.sym_field.setFocus()

    # ── Edit Mode ──

    def _load_edit_data(self, entry: FormulaEntry):
        """Load data from a FormulaEntry object."""
        self.formula_field.setText(entry.formula_text)
        self.subject_cb.setCurrentText(entry.subject)
        self._on_subject_change(entry.subject)

        self.topic_cb.blockSignals(True)
        self.topic_cb.setCurrentText(entry.topic)
        self.topic_cb.blockSignals(False)
        self._on_topic_change(entry.topic)

        self.subtopic_cb.blockSignals(True)
        self.subtopic_cb.setCurrentText(entry.sub_topic)
        self.subtopic_cb.blockSignals(False)

        self.notes_field.setPlainText(entry.notes)

        self.variables = [v.to_dict() for v in entry.variables]
        self._refresh_chips()

        self.tags = entry.tags.copy()
        self.refresh_tags_ui()

    # ── Save ──

    def _save(self):
        if self.sym_field.text().strip() and self.name_field.text().strip():
            self._add_variable()

        formula = self.formula_field.text().strip()
        field = self.subject_cb.currentText().strip()
        topic = self.topic_cb.currentText().strip()
        sub_topic = self.subtopic_cb.currentText().strip() or "_GENERAL_"
        notes = self.notes_field.toPlainText().strip()

        is_valid, error = FormulaUtils.validate_formula_data(formula, field, topic)

        if not is_valid and field != "_SYSTEM_" and topic != "UNDEFINED_BEHAVIOUR":
            QMessageBox.warning(self, "Validation Error", error)
            return

        if not self.edit_mode:
            existing = [e.formula_text for e in self.master_data.values()]
            if formula in existing:
                QMessageBox.warning(
                    self, "Duplicate Formula",
                    f"The formula '{formula}' already exists in your sheet."
                )
                return

        self._result = {
            "id": self.edit_id,
            "formula": formula,
            "field": field,
            "topic": topic,
            "sub_topic": sub_topic,
            "notes": notes,
            "variables": self.variables.copy(),
            "tags": self.tags.copy()
        }

        self.accept()

    def get_result(self) -> Optional[Dict]:
        return self._result
