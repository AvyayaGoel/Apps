"""
Macro Manager Window (PyQt6 version)
Create, edit, and delete custom keypad macro buttons.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget, QMessageBox
)


class MacroManagerWindow(QDialog):
    """Window for managing custom keypad macro buttons."""

    def __init__(self, parent):
        super().__init__(parent.root if hasattr(parent, 'root') else parent)
        self.parent = parent

        self.setWindowTitle("Manage Keypad Buttons")
        self.setMinimumSize(420, 500)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.editing_index = None
        self.last_cursor_pos = 0

        self._build_ui()
        self._apply_styles()
        self._refresh_macro_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # ── Header ──
        header = QLabel("⌨️ Manage Keypad Buttons")
        header.setObjectName("dialogHeader")
        layout.addWidget(header)

        # ── Input Form ──
        form = QFrame()
        form.setObjectName("formArea")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)

        # Label + Content row
        row = QHBoxLayout()
        row.setSpacing(8)

        self.new_lab = QLineEdit()
        self.new_lab.setPlaceholderText("Label (e.g. π)")
        self.new_lab.setFixedWidth(110)
        row.addWidget(self.new_lab)

        self.new_con = QLineEdit()
        self.new_con.setPlaceholderText("Content (e.g. \\frac{}{})")
        self.new_con.cursorPositionChanged.connect(self._capture_cursor)
        row.addWidget(self.new_con)

        form_layout.addLayout(row)

        # Hint
        hint = QLabel(
            "Tip: Click inside the Content field to set where the cursor lands after insertion."
        )
        hint.setObjectName("hintLabel")
        form_layout.addWidget(hint)

        # Action button
        self.add_btn = QPushButton("+ Add to Keypad")
        self.add_btn.setObjectName("actionBtn")
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.clicked.connect(self._add_or_update)
        form_layout.addWidget(self.add_btn)

        layout.addWidget(form)

        # ── Separator ──
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(sep)

        # ── Existing Macros List ──
        list_header = QLabel("Existing Buttons")
        list_header.setObjectName("listHeader")
        layout.addWidget(list_header)

        self.macro_scroll = QScrollArea()
        self.macro_scroll.setWidgetResizable(True)
        self.macro_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.macro_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.macro_list_widget = QWidget()
        self.macro_list_layout = QVBoxLayout(self.macro_list_widget)
        self.macro_list_layout.setContentsMargins(0, 0, 0, 0)
        self.macro_list_layout.setSpacing(4)
        self.macro_list_layout.addStretch()

        self.macro_scroll.setWidget(self.macro_list_widget)
        layout.addWidget(self.macro_scroll, stretch=1)

        # ── Bottom Actions ──
        bottom = QHBoxLayout()
        bottom.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)

        layout.addLayout(bottom)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: "Segoe UI", "Arial", sans-serif;
                font-size: 13px;
            }
            #dialogHeader {
                font-size: 15px;
                font-weight: bold;
                color: #e0e0e0;
            }
            #formArea {
                background-color: #252525;
                border-radius: 6px;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QLineEdit:focus {
                border-color: #2980b9;
            }
            #hintLabel {
                color: #888;
                font-size: 11px;
            }
            #actionBtn {
                background-color: #2980b9;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            #actionBtn:hover {
                background-color: #3498db;
            }
            #listHeader {
                font-size: 12px;
                font-weight: bold;
                color: #aaa;
            }
            #secondaryBtn {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 16px;
            }
            #secondaryBtn:hover {
                background-color: #4a4a4a;
            }
            QPushButton {
                font-size: 12px;
            }
            QScrollArea {
                background: transparent;
            }
        """)

    def _capture_cursor(self, old_pos, new_pos):
        self.last_cursor_pos = new_pos

    def _refresh_macro_list(self):
        # Clear existing rows (keep the stretch at the end)
        while self.macro_list_layout.count() > 1:
            item = self.macro_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        macros = getattr(self.parent, 'user_macros', [])

        if not macros:
            empty = QLabel("No custom buttons yet.")
            empty.setStyleSheet("color: #666; padding: 12px;")
            self.macro_list_layout.insertWidget(0, empty)
            return

        for i, macro in enumerate(macros):
            row = QFrame()
            row.setObjectName("macroRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)

            label = QLabel(f"• {macro.get('label', '?')}")
            label.setStyleSheet("color: #e0e0e0;")
            row_layout.addWidget(label, stretch=1)

            edit_btn = QPushButton("Edit")
            edit_btn.setObjectName("editBtn")
            edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            edit_btn.clicked.connect(lambda checked, idx=i: self._edit_macro(idx))
            row_layout.addWidget(edit_btn)

            del_btn = QPushButton("Delete")
            del_btn.setObjectName("delBtn")
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.clicked.connect(lambda checked, idx=i: self._delete_macro(idx))
            row_layout.addWidget(del_btn)

            row.setStyleSheet("""
                #macroRow {
                    background-color: #2a2a2a;
                    border-radius: 4px;
                }
                #macroRow:hover {
                    background-color: #333;
                }
                #editBtn {
                    background: transparent;
                    color: #888;
                    border: none;
                    padding: 2px 8px;
                }
                #editBtn:hover {
                    color: #3498db;
                }
                #delBtn {
                    background: transparent;
                    color: #888;
                    border: none;
                    padding: 2px 8px;
                }
                #delBtn:hover {
                    color: #e74c3c;
                }
            """)

            self.macro_list_layout.insertWidget(self.macro_list_layout.count() - 1, row)

    def _add_or_update(self):
        lab = self.new_lab.text().strip()
        con = self.new_con.text().strip()

        if not lab or not con:
            return

        offset = len(con) - self.last_cursor_pos

        if self.editing_index is not None:
            # Update existing
            self.parent.user_macros[self.editing_index] = {
                "label": lab,
                "content": con,
                "warp": offset
            }
            self.add_btn.setText("+ Add to Keypad")
            self.editing_index = None
        else:
            # Add new
            self.parent.user_macros.append({
                "label": lab,
                "content": con,
                "warp": offset
            })

        # Reset fields
        self.new_lab.clear()
        self.new_con.clear()
        self.last_cursor_pos = 0

        self._refresh_macro_list()
        self._save_and_sync()

    def _edit_macro(self, index):
        macro = self.parent.user_macros[index]

        self.new_lab.setText(macro["label"])
        self.new_con.setText(macro["content"])

        # Restore cursor position for warp logic
        warp = macro.get("warp", 0)
        pos = len(macro["content"]) - warp
        self.new_con.setCursorPosition(pos)
        self.last_cursor_pos = pos

        self.editing_index = index
        self.add_btn.setText("✔ Update Macro")

    def _delete_macro(self, index):
        label = self.parent.user_macros[index].get("label", "?")

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete macro '{label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.parent.user_macros.pop(index)
            self._refresh_macro_list()
            self._save_and_sync()

    def _save_and_sync(self):
        """Save config and refresh keypad if open."""
        if hasattr(self.parent, 'save_config'):
            self.parent.save_config()

        if hasattr(self.parent, 'keypad_manager') and self.parent.keypad_manager.is_open():
            try:
                self.parent.keypad_manager.update_macros(self.parent.user_macros)
            except Exception as e:
                import logging
                logging.error(f"Error syncing keypad: {e}")

    def closeEvent(self, event):
        """Clean up parent reference on close."""
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["macro"] = None
        event.accept()
