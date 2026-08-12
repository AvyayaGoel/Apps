"""
Trash / Recently Deleted Dialog (PyQt6)
Restore or permanently delete soft-deleted formulas.
"""

from typing import Callable, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout
)


class TrashDialog(QDialog):
    """Dialog for managing soft-deleted formulas."""

    def __init__(
            self,
            parent,
            deleted_formulas: List[dict],
            on_restore: Callable[[List[int]], bool],
            on_perma_delete: Callable[[List[int]], bool],
    ):
        super().__init__(parent)

        self.deleted_formulas = deleted_formulas
        self.on_restore = on_restore
        self.on_perma_delete = on_perma_delete

        self.setWindowTitle("Recently Deleted")
        self.setMinimumSize(520, 450)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self._build_ui()
        self._apply_styles()
        self._populate_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header = QLabel("Recently Deleted")
        header.setObjectName("trashHeader")
        layout.addWidget(header)

        hint = QLabel("Shift/Ctrl click to select multiple. Restore or permanently delete.")
        hint.setObjectName("trashHint")
        layout.addWidget(hint)

        # Selection controls
        select_row = QHBoxLayout()
        select_row.addStretch()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setObjectName("selectBtn")
        self.select_all_btn.clicked.connect(self._select_all)
        select_row.addWidget(self.select_all_btn)

        layout.addLayout(select_row)

        # List — multi-select enabled
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("trashList")
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget, stretch=1)

        # Selection count label
        self.count_lbl = QLabel("0 selected")
        self.count_lbl.setObjectName("countLabel")
        layout.addWidget(self.count_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("secondaryBtn")
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)

        self.perma_btn = QPushButton("🗑 Permanently Delete")
        self.perma_btn.setObjectName("permaBtn")
        self.perma_btn.setEnabled(False)
        self.perma_btn.clicked.connect(self._do_perma_delete)
        btn_row.addWidget(self.perma_btn)

        self.restore_btn = QPushButton("↩ Restore")
        self.restore_btn.setObjectName("restoreBtn")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self._do_restore)
        btn_row.addWidget(self.restore_btn)

        layout.addLayout(btn_row)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: "Segoe UI", "Arial", sans-serif;
                font-size: 13px;
            }
            #trashHeader {
                font-size: 20px;
                font-weight: bold;
                color: #e0e0e0;
            }
            #trashHint {
                color: #888;
                font-size: 12px;
            }
            #countLabel {
                color: #666;
                font-size: 11px;
            }
            #trashList {
                background-color: #252525;
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 8px;
                outline: none;
            }
            #trashList::item {
                padding: 10px 12px;
                border-bottom: 1px solid #2a2a2a;
            }
            #trashList::item:selected {
                background-color: #2980b9;
            }
            #trashList::item:hover:!selected {
                background-color: #2a2a2a;
            }
            #selectBtn {
                background-color: #2a2a2a;
                color: #aaa;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            #selectBtn:hover {
                background-color: #333;
                color: #e0e0e0;
            }
            #secondaryBtn {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 8px 18px;
            }
            #secondaryBtn:hover {
                background-color: #4a4a4a;
            }
            #permaBtn {
                background-color: #5c1a1a;
                color: #ff6b6b;
                border: 1px solid #8b0000;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            #permaBtn:hover {
                background-color: #7a1f1f;
            }
            #permaBtn:disabled {
                background-color: #3a1a1a;
                color: #666;
                border-color: #4a1a1a;
            }
            #restoreBtn {
                background-color: #2980b9;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            #restoreBtn:hover {
                background-color: #3498db;
            }
            #restoreBtn:disabled {
                background-color: #1a3a5c;
                color: #888;
            }
        """)

    def _populate_list(self):
        self.list_widget.clear()

        if not self.deleted_formulas:
            item = QListWidgetItem("No recently deleted formulas")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return

        for f in self.deleted_formulas:
            display = f.get('id') if f.get('id') is not None else f"DB-{f['db_id']}"
            text = f"#{display}  —  {f['formula_text'][:55]}{'...' if len(f['formula_text']) > 55 else ''}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, f['db_id'])
            self.list_widget.addItem(item)

    def _selected_db_ids(self) -> List[int]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.list_widget.selectedItems()
        ]

    def _on_selection_changed(self):
        count = len(self.list_widget.selectedItems())
        self.count_lbl.setText(f"{count} selected")
        self.restore_btn.setEnabled(count > 0)
        self.perma_btn.setEnabled(count > 0)

    def _select_all(self):
        self.list_widget.selectAll()

    def _deselect_all(self):
        self.list_widget.clearSelection()

    def _do_restore(self):
        db_ids = self._selected_db_ids()
        if not db_ids:
            return

        if len(db_ids) == 1:
            msg = "Restore this formula?"
        else:
            msg = f"Restore {len(db_ids)} formulas?"

        reply = QMessageBox.question(self, "Confirm Restore", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.on_restore(db_ids):
            self._remove_selected_items()
        else:
            QMessageBox.warning(self, "Restore Failed", "Some formulas could not be restored.")

    def _do_perma_delete(self):
        db_ids = self._selected_db_ids()
        if not db_ids:
            return

        if len(db_ids) == 1:
            msg = "This formula will be permanently deleted.\nNo undo possible.\n\nAre you sure?"
        else:
            msg = f"{len(db_ids)} formulas will be permanently deleted.\nNo undo possible.\n\nAre you sure?"

        reply = QMessageBox.question(self, "Confirm Permanent Delete", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.on_perma_delete(db_ids):
            self._remove_selected_items()
        else:
            QMessageBox.warning(self, "Delete Failed", "Some formulas could not be deleted.")

    def _remove_selected_items(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

        if self.list_widget.count() == 0:
            self.accept()
