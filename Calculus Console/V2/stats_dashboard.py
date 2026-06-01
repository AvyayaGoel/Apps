"""
Statistics Dashboard v2 (PyQt6)
Knowledge collection overview with subject/topic hierarchy,
Quick Metrics KPI header, inline progress bars, and expand/collapse controls.
"""
from typing import Dict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QHBoxLayout, QPushButton, QFrame,
    QLabel, QProgressBar, QGraphicsDropShadowEffect,
    QSizePolicy, QLineEdit, QWidget
)


class MicroProgressBar(QProgressBar):
    """Compact, styled progress bar for tree widget embedding."""

    def __init__(self, value: float, color: str = "#3B82F6", parent=None):
        super().__init__(parent)

        self.setRange(0, 100)
        self.setValue(int(value))
        self.setTextVisible(False)

        self.setFixedHeight(10)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: #202020;
                border: none;
            }}

            QProgressBar::chunk {{
                background-color: {color};
                min-width: 2px;
            }}
        """)


class MetricChip(QFrame):
    """KPI summary chip with label and big value."""

    def __init__(self, label: str, value: str, accent_color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self.setObjectName("metricChip")
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        # Small uppercase label
        self._label = QLabel(label.upper())
        self._label.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self._label)

        # Big value
        self._value = QLabel(value)
        self._value.setStyleSheet(f"color: {accent_color}; font-size: 28px; font-weight: bold;")
        layout.addWidget(self._value)

        # Subtle left accent border
        self.setStyleSheet(f"""
            #metricChip {{
                background-color: #1C1C1C;
                border-radius: 10px;
                border: 1px solid #2A2A2A;
                border-left: 3px solid {accent_color};
            }}
        """)

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def set_value(self, text: str):
        """Update the displayed value text."""
        self._value.setText(text)


class StatsDashboard(QDialog):
    """Hierarchical statistics window with KPI header, progress bars, and tree controls."""

    # Accent colors for metrics chips
    METRIC_COLORS = {
        "total": "#3B82F6",  # Blue
        "subjects": "#10B981",  # Emerald
        "topics": "#F59E0B",  # Amber
    }

    def __init__(self, parent, master_data):
        super().__init__(parent.root if hasattr(parent, 'root') else parent)
        self.parent = parent
        self.master_data = master_data

        self.setWindowTitle("Knowledge Collection")
        self.setMinimumSize(820, 700)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._build_ui()
        self._apply_styles()
        self._populate_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # =============================
        # KPI CARDS
        # =============================

        metrics_layout = QHBoxLayout()

        self.metric_total = MetricChip(
            "📚 Formulas",
            "0",
            self.METRIC_COLORS["total"]
        )

        self.metric_subjects = MetricChip(
            "🧪 Subjects",
            "0",
            self.METRIC_COLORS["subjects"]
        )

        self.metric_topics = MetricChip(
            "🗂 Topics",
            "0",
            self.METRIC_COLORS["topics"]
        )

        metrics_layout.addWidget(self.metric_total)
        metrics_layout.addWidget(self.metric_subjects)
        metrics_layout.addWidget(self.metric_topics)

        layout.addLayout(metrics_layout)

        # =============================
        # TOOLBAR
        # =============================

        toolbar = QHBoxLayout()

        self.expand_btn = QPushButton("📂 Expand All")
        self.expand_btn.setObjectName("toolbarBtn")
        self.expand_btn.clicked.connect(self.tree_expand_all)

        self.collapse_btn = QPushButton("📁 Collapse All")
        self.collapse_btn.setObjectName("toolbarBtn")
        self.collapse_btn.clicked.connect(self.tree_collapse_all)

        toolbar.addWidget(self.expand_btn)
        toolbar.addWidget(self.collapse_btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)

        # =============================
        # SEARCH
        # =============================

        self.search_box = QLineEdit()
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setPlaceholderText(
            "Search subjects or topics..."
        )

        self.search_box.textChanged.connect(
            self.filter_tree
        )

        layout.addWidget(self.search_box)

        # =============================
        # TREE
        # =============================

        self.tree = QTreeWidget()

        self.tree.setColumnCount(6)

        self.tree.setHeaderLabels([
            "Rank",
            "Subject / Topic",
            "Count",
            "Subject %",
            "Total %",
            "Distribution"
        ])

        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(22)

        header = self.tree.header()

        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(
                1,
                QHeaderView.ResizeMode.Stretch
            )

        # Rank (small fixed)
        self.tree.setColumnWidth(0, 50)

        # Count
        self.tree.setColumnWidth(2, 80)

        # Subject %
        self.tree.setColumnWidth(3, 90)

        # Total %
        self.tree.setColumnWidth(4, 90)

        # Distribution (progress bar)
        self.tree.setColumnWidth(5, 200)

        layout.addWidget(self.tree, stretch=1)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
            }
            QWidget {
                font-family: "Segoe UI", "Consolas", sans-serif;
                font-size: 13px;
            }
            #toolbarBtn {
                background-color: #1F1F1F;
                color: #888;
                border: 1px solid #2F2F2F;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            #toolbarBtn:hover {
                background-color: #2A2A2A;
                border-color: #3B82F6;
                color: #e0e0e0;
            }
            #toolbarBtn:pressed {
                background-color: #2563EB;
                color: white;
            }
            QTreeWidget {
                background-color: #161616;
                color: #e0e0e0;
                border: 1px solid #2A2A2A;
                border-radius: 10px;
                outline: none;
                padding: 4px;
            }
            QTreeWidget::item {
                padding: 8px 6px;
                border-bottom: 1px solid #202020;
                min-height: 32px;
            }
            QTreeWidget::item:selected {
                background-color: #2563EB;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #1E1E1E;
            }
            QHeaderView::section {
                background-color: #1E1E1E;
                color: #B0B0B0;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #2A2A2A;
                font-weight: bold;
            }
        """)

    def _populate_data(self):

        self.tree.clear()

        data_map: Dict[str, Dict[str, int]] = {}

        for entry in self.master_data.values():
            subj = entry["main_info"][2]
            topic = entry["main_info"][3]

            data_map.setdefault(subj, {})
            data_map[subj][topic] = (
                    data_map[subj].get(topic, 0) + 1
            )

        total_formulas = len(self.master_data)

        unique_subjects = len(data_map)

        unique_topics = sum(
            len(x)
            for x in data_map.values()
        )

        self.metric_total.set_value(
            str(total_formulas)
        )

        self.metric_subjects.set_value(
            str(unique_subjects)
        )

        self.metric_topics.set_value(
            str(unique_topics)
        )

        sorted_subjects = sorted(
            data_map.items(),
            key=lambda item: int(sum(item[1].values())),
            reverse=True
        )

        medals = ["🥇", "🥈", "🥉"]

        for rank, (subj, topics) in enumerate(
                sorted_subjects
        ):

            total_subj = sum(
                topics.values()
            )

            subject_pct = (
                    total_subj
                    / total_formulas
                    * 100
            )

            color = "#3B82F6"

            if hasattr(
                    self.parent,
                    "subject_colors"
            ):
                color = (
                    self.parent.subject_colors.get(
                        subj,
                        color
                    )
                )

            if rank < 3:
                rank_text = medals[rank]
            else:
                rank_text = f"#{rank + 1}"

            parent_item = QTreeWidgetItem(
                self.tree
            )
            parent_item.setTextAlignment(
                0,
                Qt.AlignmentFlag.AlignCenter
            )
            parent_item.setText(0, rank_text)
            parent_item.setText(1, subj)
            parent_item.setText(2, str(total_subj))
            parent_item.setText(3, "100%")
            parent_item.setText(4, f"{subject_pct:.1f}%")

            parent_item.setForeground(
                1,
                QColor(color)
            )

            font = parent_item.font(0)
            font.setBold(True)

            parent_item.setFont(0, font)

            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            bar = MicroProgressBar(subject_pct, color)

            container_layout.addWidget(bar)

            self.tree.setItemWidget(parent_item, 5, container)

            for topic, count in sorted(
                    topics.items(),
                    key=lambda x: x[1],
                    reverse=True
            ):
                subject_share = (
                        count
                        / total_subj
                        * 100
                )

                total_share = (
                        count
                        / total_formulas
                        * 100
                )

                child = QTreeWidgetItem(
                    parent_item
                )

                child.setTextAlignment(
                    0,
                    Qt.AlignmentFlag.AlignCenter
                )
                child.setText(0, "")
                child.setText(1, topic)
                child.setText(2, str(count))
                child.setText(3, f"{subject_share:.1f}%")
                child.setText(4, f"{total_share:.1f}%")

                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

                bar = MicroProgressBar(subject_share, color)

                layout.addWidget(bar)

                self.tree.setItemWidget(child, 5, container)

        self.tree.expandAll()

    def filter_tree(self):

        text = self.search_box.text().lower()

        for i in range(self.tree.topLevelItemCount()):

            parent = self.tree.topLevelItem(i)

            parent_visible = (
                    text in parent.text(1).lower()
            )

            child_visible = False

            for j in range(parent.childCount()):
                child = parent.child(j)

                visible = (
                        text in child.text(1).lower()
                )

                child.setHidden(
                    not visible
                )

                child_visible |= visible

            parent.setHidden(
                not (
                        parent_visible
                        or child_visible
                )
            )

    def tree_expand_all(self):
        """Expand all tree nodes."""
        self.tree.expandAll()

    def tree_collapse_all(self):
        """Collapse all tree nodes."""
        self.tree.collapseAll()

    def closeEvent(self, event):
        if hasattr(self.parent, 'secret_movement'):
            self.parent.secret_movement("close_stats")
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["stats"] = None
        event.accept()
