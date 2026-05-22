"""
FormulaDialog (PyQt6)
Entry/edit dialog for formulas. Uses SymbolLearner for ghost suggestions,
dynamic comboboxes from master_data, and chip-based variable management.
Designed to be instantiated from the main application window.
"""

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QEvent
from PyQt6.QtGui import QColor, QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QVBoxLayout, QWidget,
    QListWidget, QListWidgetItem, QScrollArea,
    QMessageBox, QGraphicsDropShadowEffect
)

from constants import NO_DIMENSION_UNITS, SAVE_FORMULA
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


class GhostPopup(QFrame):
    """Floating suggestion popup under the symbol field.

    Uses Tool + DoesNotAcceptFocus so it never steals focus from the
    parent line edit, making clicks on list items work correctly.
    """

    suggestion_accepted = pyqtSignal(str, str)
    """Emitted when user clicks a suggestion: (name, unit)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self.setStyleSheet("""
            QFrame {
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

        self.list_widget.adjustSize()

        row_height = self.list_widget.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 32

        content_width = self.list_widget.sizeHintForColumn(0)
        if content_width <= 0:
            content_width = 220

        total_height = len(suggestions) * row_height + 2
        total_width = content_width + 4
        total_width = max(total_width, 220)
        total_height = max(total_height, row_height)

        self.list_widget.setFixedSize(total_width, total_height)
        self.setFixedSize(total_width, total_height)

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            name, unit = data
            self.suggestion_accepted.emit(name, unit)

    def current_selection(self) -> Optional[Tuple[str, str]]:
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None


class VariableChip(QFrame):
    """Removable variable chip."""

    remove_requested = pyqtSignal(object)  # emits self
    edit_requested = pyqtSignal(str, str, str)  # symbol, name, unit

    def __init__(self, symbol: str, name: str, unit: str, parent=None):
        super().__init__(parent)

        self.symbol = symbol
        self.name = name
        self.unit = unit

        self.setObjectName("varChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)

        # Symbol badge
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

        # Name · Unit
        unit_display = "" if unit.lower() in NO_DIMENSION_UNITS else f"· {unit}"
        info = QLabel(f"{name}  <span style='color:#888'>{unit_display}</span>")
        info.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        layout.addWidget(info)

        layout.addStretch()

        # Edit
        edit_btn = QPushButton("✎")
        edit_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: none; font-size: 12px; padding: 2px; }
            QPushButton:hover { color: #3498db; }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(symbol, name, unit))
        layout.addWidget(edit_btn)

        # Remove
        del_btn = QPushButton("✕")
        del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: none; font-size: 12px; padding: 2px; }
            QPushButton:hover { color: #e74c3c; }
        """)
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(del_btn)

        self.setStyleSheet("""
            #varChip {
                background-color: #2a2a2a;
                border-radius: 6px;
                border: 1px solid #333;
            }
            #varChip:hover { border-color: #444; }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)


# ── Main Dialog ──

class FormulaDialog(QDialog):
    """Formula entry/edit dialog.

    Usage (from main app):
        dialog = FormulaDialog(
            parent=self,
            master_data=self.master_data,
            symbol_learner=self.symbol_learner,
            max_suggestions=self.max_suggestions,
            edit_data=existing_formula_dict  # omit for add mode
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            # result = {
            #     "id": int or None,
            #     "formula": str,
            #     "field": str,
            #     "topic": str,
            #     "sub_topic": str,
            #     "variables": [{"symbol": ..., "name": ..., "unit": ...}]
            # }
    """

    def __init__(self, parent=None, edit_data=None, master_data: Dict = None,
                 symbol_learner: SymbolLearner = None, max_suggestions: int = 3):
        super().__init__(parent)

        self.edit_mode = edit_data is not None
        self.edit_id = edit_data["main_info"][0] if edit_data else None
        self.variables: List[Dict] = edit_data["variables"].copy() if edit_data else []
        self.master_data = master_data or {}

        # Symbol learner
        self.symbol_learner = symbol_learner
        if self.symbol_learner is None and self.master_data:
            self.symbol_learner = SymbolLearner()
            self.symbol_learner.learn(self.master_data)

        self.max_suggestions = max_suggestions
        self._ghost_popup: Optional[GhostPopup] = None

        self._result: Optional[Dict] = None

        self.setWindowTitle("Edit Formula" if self.edit_mode else "New Formula")
        self.setMinimumSize(780, 560)

        self._build_ui()
        self._apply_styles()
        self._update_combobox_data()

        if not self.edit_mode:
            self._clear_all_fields()

        if edit_data:
            self._load_edit_data(edit_data)

        # Install Enter navigation on all input fields
        self._install_enter_navigation()

    # ── UI Construction ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header_text = f"✎  EDIT FORMULA #{self.edit_id}" if self.edit_mode else "➕  NEW FORMULA"
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(header)

        # Formula
        formula_lbl = QLabel("FORMULA")
        formula_lbl.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(formula_lbl)

        self.formula_field = FormulaLineEdit()
        self.formula_field.setPlaceholderText("e.g.  F = ma  or  E = mc²")
        self.formula_field.setMinimumHeight(38)

        math_font = QFont("Cambria Math", 14)
        math_font.setStyleHint(QFont.StyleHint.Serif)
        self.formula_field.setFont(math_font)

        layout.addWidget(self.formula_field)

        # Classification row
        class_lbl = QLabel("CLASSIFICATION")
        class_lbl.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(class_lbl)

        class_frame = QFrame()
        class_layout = QHBoxLayout(class_frame)
        class_layout.setContentsMargins(0, 0, 0, 0)
        class_layout.setSpacing(12)

        # Subject
        subj_box = QVBoxLayout()
        subj_box.setSpacing(4)
        subj_box.addWidget(self._small_label("Subject"))
        self.subject_cb = QComboBox()
        self.subject_cb.setEditable(True)
        self.subject_cb.setMinimumWidth(180)
        self.subject_cb.currentTextChanged.connect(self._on_subject_change)
        subj_box.addWidget(self.subject_cb)
        class_layout.addLayout(subj_box)

        # Topic
        topic_box = QVBoxLayout()
        topic_box.setSpacing(4)
        topic_box.addWidget(self._small_label("Topic"))
        self.topic_cb = QComboBox()
        self.topic_cb.setEditable(True)
        self.topic_cb.setMinimumWidth(220)
        self.topic_cb.currentTextChanged.connect(self._on_topic_change)
        topic_box.addWidget(self.topic_cb)
        class_layout.addLayout(topic_box)

        # Sub-topic
        subtopic_box = QVBoxLayout()
        subtopic_box.setSpacing(4)
        subtopic_box.addWidget(self._small_label("Sub-Topic"))
        self.subtopic_cb = QComboBox()
        self.subtopic_cb.setEditable(True)
        self.subtopic_cb.setMinimumWidth(220)
        subtopic_box.addWidget(self.subtopic_cb)
        class_layout.addLayout(subtopic_box)

        class_layout.addStretch()
        layout.addWidget(class_frame)

        # Variables header
        var_header = QLabel("VARIABLES")
        var_header.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(var_header)

        # Chips
        self.chips_scroll = QScrollArea()
        self.chips_scroll.setWidgetResizable(True)
        self.chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chips_scroll.setMaximumHeight(140)

        self.chips_widget = QWidget()
        self.chips_layout = QVBoxLayout(self.chips_widget)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)
        self.chips_layout.addStretch()

        self.chips_scroll.setWidget(self.chips_widget)
        layout.addWidget(self.chips_scroll)

        # Variable input
        input_frame = QFrame()
        input_frame.setObjectName("varInput")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 12, 14, 12)
        input_layout.setSpacing(10)

        # Symbol
        sym_box = QVBoxLayout()
        sym_box.setSpacing(4)
        sym_box.addWidget(self._small_label("Symbol"))
        self.sym_field = QLineEdit()
        self.sym_field.setPlaceholderText("v")
        self.sym_field.setMaximumWidth(90)
        self.sym_field.setMinimumHeight(30)
        self.sym_field.textChanged.connect(self._on_symbol_change)
        sym_box.addWidget(self.sym_field)
        input_layout.addLayout(sym_box)

        # Name
        name_box = QVBoxLayout()
        name_box.setSpacing(4)
        name_box.addWidget(self._small_label("Name"))
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Velocity")
        self.name_field.setMinimumHeight(30)
        name_box.addWidget(self.name_field)
        input_layout.addLayout(name_box, stretch=2)

        # Unit
        unit_box = QVBoxLayout()
        unit_box.setSpacing(4)
        unit_box.addWidget(self._small_label("Unit"))
        self.unit_field = QLineEdit()
        self.unit_field.setPlaceholderText("m/s")
        self.unit_field.setMaximumWidth(120)
        self.unit_field.setMinimumHeight(30)
        unit_box.addWidget(self.unit_field)
        input_layout.addLayout(unit_box)

        # Add button
        add_box = QVBoxLayout()
        add_box.setSpacing(4)
        add_box.addWidget(QLabel(""))  # spacer
        add_btn = QPushButton("+ Add")
        add_btn.setObjectName("addBtn")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setMinimumHeight(30)
        add_btn.clicked.connect(self._add_variable)
        add_box.addWidget(add_btn)
        input_layout.addLayout(add_box)

        layout.addWidget(input_frame)

        # Ghost hint
        self.ghost_hint = QLabel("Type a symbol to see smart suggestions from your existing formulas")
        self.ghost_hint.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        layout.addWidget(self.ghost_hint)

        layout.addStretch()

        # Actions
        actions = QHBoxLayout()
        actions.addStretch()

        if self.edit_mode:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setObjectName("secondaryBtn")
            cancel_btn.setMinimumWidth(90)
            cancel_btn.clicked.connect(self.reject)
            actions.addWidget(cancel_btn)

        save_text = "Update Formula" if self.edit_mode else SAVE_FORMULA
        self.save_btn = QPushButton(save_text)
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setMinimumWidth(140)
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(self.save_btn)

        layout.addLayout(actions)

    def _small_label(self, text: str) -> QLabel:
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
                min-height: 30px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                selection-background-color: #2980b9;
            }
            QComboBox::editable { background-color: #2d2d2d; }
            #varInput { background-color: #252525; border-radius: 6px; }
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
        """)

    # ── Enter Navigation ──

    def _install_enter_navigation(self):
        """Install event filter on all input fields for Enter/Shift+Enter navigation."""
        fields = [
            self.formula_field,
            self.subject_cb,
            self.topic_cb,
            self.subtopic_cb,
            self.sym_field,
            self.name_field,
            self.unit_field,
        ]
        for w in fields:
            w.installEventFilter(self)
            # Also install on internal line edit of editable combo boxes
            if isinstance(w, QComboBox) and w.isEditable():
                w.lineEdit().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            # Ctrl+S = Save formula
            if event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._save()
                return True

            # Shift+Enter = previous field
            if event.key() in (Qt.Key.Key_Return,
                               Qt.Key.Key_Enter) and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self._navigate_field(backward=True)
                return True

            # Enter = next field
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # If ghost popup visible, dismiss it first
                if self._ghost_popup and self._ghost_popup.isVisible():
                    self._hide_ghost()
                    return True
                self._navigate_field(backward=False)
                return True

            # Escape = hide ghost popup
            if event.key() == Qt.Key.Key_Escape and self._ghost_popup:
                self._hide_ghost()
                return True

        return super().eventFilter(obj, event)

    def _navigate_field(self, backward: bool = False):
        """Navigate between fields with Enter/Shift+Enter."""
        focus_order = [
            self.formula_field,
            self.subject_cb,
            self.topic_cb,
            self.subtopic_cb,
            self.sym_field,
            self.name_field,
            self.unit_field,
        ]

        current = self.focusWidget()

        # Map internal line edits back to their parent combo boxes
        actual_current = None
        for field in focus_order:
            if current is field:
                actual_current = field
                break
            if isinstance(field, QComboBox) and field.isEditable():
                if current is field.lineEdit():
                    actual_current = field
                    break

        if actual_current is None:
            return

        idx = focus_order.index(actual_current)

        if backward:
            idx -= 1
            if idx < 0:
                idx = len(focus_order) - 1
        else:
            idx += 1
            if idx >= len(focus_order):
                # At unit_field: save variable and loop back to sym_field
                if actual_current == self.unit_field:
                    self._add_variable()
                    return
                idx = 0

        target = focus_order[idx]
        target.setFocus()

        # Select all text in target
        if isinstance(target, QLineEdit):
            target.selectAll()
        elif isinstance(target, QComboBox) and target.isEditable():
            target.lineEdit().selectAll()

    # ── Dynamic Data ──

    def _update_combobox_data(self):
        """Populate combobox dropdowns from master_data history."""
        subjects = set()
        topics_by_subject: Dict[str, set] = {}
        subtopics_by_topic: Dict[Tuple[str, str], set] = {}

        for entry in self.master_data.values():
            info = entry.get("main_info", [])
            if len(info) < 5:
                continue

            subj, topic, subtopic = info[2], info[3], info[4]
            subjects.add(subj)
            topics_by_subject.setdefault(subj, set()).add(topic)
            subtopics_by_topic.setdefault((subj, topic), set()).add(subtopic)

        self._topics_by_subject = topics_by_subject
        self._subtopics_by_topic = subtopics_by_topic

        self.subject_cb.clear()
        defaults = {"Physics", "Chemistry", "Maths"}
        self.subject_cb.addItems(sorted(subjects | defaults))

    def _clear_all_fields(self):
        """Ensure all entry fields are empty on open."""
        self.formula_field.clear()
        self.subject_cb.setCurrentText("")
        self.topic_cb.clear()
        self.topic_cb.setCurrentText("")
        self.subtopic_cb.clear()
        self.subtopic_cb.setCurrentText("")
        self.sym_field.clear()
        self.name_field.clear()
        self.unit_field.clear()
        self.variables = []
        self._refresh_chips()

    def _on_subject_change(self, text: str):
        """Populate topic dropdown for this subject. Leave text empty."""
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
        """Populate subtopic dropdown for this subject+topic. Leave text empty."""
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
                max_results=self.max_suggestions
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

    def _show_ghost(self, suggestions: List[Tuple[str, str, int]]):
        if self._ghost_popup:
            old = self._ghost_popup
            self._ghost_popup = None
            old.hide()
            old.deleteLater()

        self._ghost_popup = GhostPopup(self)
        self._ghost_popup.suggestion_accepted.connect(self._accept_ghost)
        self._ghost_popup.set_suggestions(suggestions)

        pos = self.sym_field.mapToGlobal(QPoint(0, self.sym_field.height()))
        self._ghost_popup.move(pos.x(), pos.y() + 2)
        self._ghost_popup.show()

        self.ghost_hint.setText("Click to accept suggestion")

    def _hide_ghost(self):
        if self._ghost_popup:
            popup = self._ghost_popup
            self._ghost_popup = None
            popup.hide()
            popup.deleteLater()
        self.ghost_hint.setText("Type a symbol to see smart suggestions from your existing formulas")

    def _accept_ghost(self, name: str, unit: str):
        self.name_field.setText(name)
        self.unit_field.setText(unit)
        self._hide_ghost()
        self.unit_field.setFocus()

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
            if item.widget():
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

    def _load_edit_data(self, data: Dict):
        info = data.get("main_info", [])
        if len(info) >= 2:
            self.formula_field.setText(info[1])
        if len(info) >= 3:
            self.subject_cb.setCurrentText(info[2])
            self._on_subject_change(info[2])
        if len(info) >= 4:
            self.topic_cb.blockSignals(True)
            self.topic_cb.setCurrentText(info[3])
            self.topic_cb.blockSignals(False)
            self._on_topic_change(info[3])
        if len(info) >= 5:
            self.subtopic_cb.blockSignals(True)
            self.subtopic_cb.setCurrentText(info[4])
            self.subtopic_cb.blockSignals(False)

        self.variables = data.get("variables", []).copy()
        self._refresh_chips()

    # ── Save ──

    def _save(self):
        if self.sym_field.text().strip() and self.name_field.text().strip():
            self._add_variable()

        formula = self.formula_field.text().strip()
        field = self.subject_cb.currentText().strip()
        topic = self.topic_cb.currentText().strip()
        sub_topic = self.subtopic_cb.currentText().strip() or "_GENERAL_"

        is_valid, error = FormulaUtils.validate_formula_data(formula, field, topic)
        if not is_valid and field != "_SYSTEM_" and topic != "UNDEFINED_BEHAVIOUR":
            QMessageBox.warning(self, "Validation Error", error)
            return

        if not self.edit_mode:
            existing = [d["main_info"][1] for d in self.master_data.values()]
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
            "variables": self.variables.copy()
        }
        self.accept()

    def get_result(self) -> Optional[Dict]:
        return self._result

    # ── Events ──

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape and self._ghost_popup:
            self._hide_ghost()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.sym_field.hasFocus():
                self.name_field.setFocus()
                return
            elif self.name_field.hasFocus():
                self.unit_field.setFocus()
                return
            elif self.unit_field.hasFocus():
                self._add_variable()
                return

        super().keyPressEvent(event)
