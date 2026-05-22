"""
Statistics Dashboard (PyQt6 version)
Knowledge collection overview with subject/topic hierarchy.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout
)


class StatsDashboard(QDialog):
    """Hierarchical statistics window showing formula distribution."""

    def __init__(self, parent, master_data):
        super().__init__(parent.root if hasattr(parent, 'root') else parent)
        self.parent = parent
        self.master_data = master_data

        self.setWindowTitle("Knowledge Collection")
        self.setMinimumSize(560, 600)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._build_ui()
        self._apply_styles()
        self._populate_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Subject / Topic", "Quantity"])
        self.tree.setColumnCount(2)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tree.header().setDefaultSectionSize(120)
        self.tree.setColumnWidth(1, 120)

        layout.addWidget(self.tree)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: "Segoe UI", "Consolas", sans-serif;
                font-size: 13px;
            }
            QTreeWidget {
                background-color: #252525;
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 6px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                border-bottom: 1px solid #2a2a2a;
            }
            QTreeWidget::item:selected {
                background-color: #2980b9;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #2d2d2d;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #aaa;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #333;
                font-weight: bold;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                image: none;
                border-image: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                image: none;
                border-image: none;
            }
        """)

    def _populate_data(self):
        # Aggregate data
        data_map = {}
        for entry in self.master_data.values():
            subj = entry["main_info"][2]
            topic = entry["main_info"][3]

            if subj not in data_map:
                data_map[subj] = {}
            data_map[subj][topic] = data_map[subj].get(topic, 0) + 1

        total_formulas = len(self.master_data)

        # Populate tree
        for subj in sorted(data_map.keys()):
            topics = data_map[subj]
            total_subj = sum(topics.values())
            subj_pct = (total_subj / total_formulas * 100) if total_formulas > 0 else 0

            subj_item = QTreeWidgetItem(self.tree)
            subj_item.setText(0, f"{subj}  ({subj_pct:.1f}%)")
            subj_item.setText(1, str(total_subj))
            subj_item.setExpanded(True)

            # Style parent node
            subj_item.setForeground(0, Qt.GlobalColor.white)
            font = subj_item.font(0)
            font.setBold(True)
            subj_item.setFont(0, font)
            subj_item.setFont(1, font)

            sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
            for topic, count in sorted_topics:
                topic_pct = (count / total_subj * 100) if total_subj > 0 else 0

                child = QTreeWidgetItem(subj_item)
                child.setText(0, f"  ↳ {topic}  ({topic_pct:.1f}%)")
                child.setText(1, str(count))
                child.setForeground(0, Qt.GlobalColor.gray)

    def closeEvent(self, event):
        if hasattr(self.parent, 'secret_movement'):
            self.parent.secret_movement("close_stats")
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["stats"] = None
        event.accept()
