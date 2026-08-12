"""
Export Manager (PyQt6)
Handles exporting formulas to multiple formats with a hierarchical
subject/topic/sub-topic filter tree. Uses PyQt6's built-in QPrinter for PDF.
Updated for FormulaEntry / FormulaCollection class structure.
No backward compatibility.
"""

import csv
import html
import json
import time
from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import Qt, QMarginsF
from PyQt6.QtGui import QTextDocument, QPageLayout
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
    QCheckBox, QComboBox
)

from constants import NO_DIMENSION_UNITS
from formula_entry import FormulaCollection


# ── Data Structure for Hierarchy ──

class HierarchyNode:
    """Represents a node in the subject/topic/sub-topic tree."""

    def __init__(self, name: str, node_type: str):
        self.name = name
        self.node_type = node_type  # "all", "subject", "topic", "subtopic"
        self.children: Dict[str, "HierarchyNode"] = {}
        self.checkbox: Optional[QCheckBox] = None
        self.formula_ids: Set[int] = set()

    def add_formula(self, formula_id: int, subject: str, topic: str, sub_topic: str):
        """Register a formula under this node and its children."""
        self.formula_ids.add(formula_id)

        # Subject level
        if subject not in self.children:
            self.children[subject] = HierarchyNode(subject, "subject")
        subj_node = self.children[subject]
        subj_node.formula_ids.add(formula_id)

        # Topic level
        if topic not in subj_node.children:
            subj_node.children[topic] = HierarchyNode(topic, "topic")
        topic_node = subj_node.children[topic]
        topic_node.formula_ids.add(formula_id)

        # Sub-topic level
        sub_key = sub_topic if sub_topic else "_GENERAL_"
        if sub_key not in topic_node.children:
            topic_node.children[sub_key] = HierarchyNode(sub_key, "subtopic")
        topic_node.children[sub_key].formula_ids.add(formula_id)

    def get_selected_ids(self) -> Set[int]:
        """Get all formula IDs that are selected under this node."""
        if not self.checkbox or self.checkbox.checkState() == Qt.CheckState.Unchecked:
            return set()

        if not self.children:
            return set(self.formula_ids)

        ids = set()
        for child in self.children.values():
            ids.update(child.get_selected_ids())
        return ids


# ── Export Logic ──

class ExportManager:
    """Static utility class for exporting formula data."""

    @staticmethod
    def get_supported_formats() -> Dict[str, str]:
        return {
            "html": "HTML Document (.html)",
            "pdf": "PDF Document (.pdf)",
            "txt": "Text File (.txt)",
            "csv": "CSV File (.csv)",
            "json": "JSON File (.json)",
            "md": "Markdown File (.md)",
        }

    @staticmethod
    def get_file_extension(fmt: str) -> str:
        return {
            "html": ".html", "pdf": ".pdf", "txt": ".txt",
            "csv": ".csv", "json": ".json", "md": ".md",
        }.get(fmt, ".txt")

    @staticmethod
    def get_file_filter(fmt: str) -> str:
        return {
            "html": "HTML files (*.html)", "pdf": "PDF files (*.pdf)",
            "txt": "Text files (*.txt)", "csv": "CSV files (*.csv)",
            "json": "JSON files (*.json)", "md": "Markdown files (*.md)",
        }.get(fmt, "All files (*.*)")

    @classmethod
    def export(cls, master_data: FormulaCollection, file_path: str, fmt: str) -> None:
        handlers = {
            "html": cls._export_to_html, "pdf": cls._export_to_pdf,
            "txt": cls._export_to_txt, "csv": cls._export_to_csv,
            "json": cls._export_to_json, "md": cls._export_to_markdown,
        }
        handler = handlers.get(fmt)
        if not handler:
            raise ValueError(f"Unsupported format: {fmt}")
        handler(master_data, file_path)

    @staticmethod
    def _build_html_content(master_data: FormulaCollection) -> str:
        total = len(master_data)
        entries = sorted(master_data.values(), key=lambda e: e.display_id)

        body_parts = []
        for entry in entries:
            formula_text = html.escape(entry.formula_text).replace("\n", "<br>")
            subject = html.escape(entry.subject)
            topic = html.escape(entry.topic)
            sub_topic = html.escape(entry.display_sub_topic)

            vars_html = ""
            if entry.variables:
                var_lines = []
                for var in entry.variables:
                    sym, name, unit = html.escape(var.symbol), html.escape(var.name), html.escape(var.unit)
                    text = f"{sym} means {name}" if unit.lower() in NO_DIMENSION_UNITS else f"{sym} means {name} with unit {unit}"
                    var_lines.append(f'<div class="variable">• {text}</div>')
                vars_html = f'<div class="variables"><b>Variables:</b>\n{"".join(var_lines)}\n</div>\n'

            notes_html = ""
            if entry.has_notes:
                notes_escaped = html.escape(entry.notes).replace("\n", "<br>")
                notes_html = f'<div class="notes"><b>Notes:</b><br>{notes_escaped}</div>\n'

            body_parts.append(f"""
    <div class="formula">
        <div class="formula-id">#{entry.display_id}</div>
        <div class="formula-text">{formula_text}</div>
        {notes_html}
        <div class="metadata">Subject: {subject} | Topic: {topic} | Sub-Topic: {sub_topic}</div>
        {vars_html}
    </div>""")

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Formulas #{total}</title>
    <link href="https://fonts.googleapis.com/css2?family=Cambria+Math&family=STIX+Two+Math&family=DejaVu+Sans&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Cambria Math','STIX Two Math','DejaVu Sans','Times New Roman',Arial,sans-serif; margin:40px; line-height:1.6; font-size:14px; }}
        .title-page {{ page-break-after: always; text-align: center; margin-top: 300px; }}
        .title-inner {{ font-size: 28pt; font-weight: bold; }}
        .formula {{ margin-bottom:30px; page-break-inside: avoid; break-inside: avoid; }}
        .formula-id {{ font-size:16px; font-weight:bold; color:#333; }}
        .formula-text {{ font-size:15pt; margin:10px 0; background:#f5f5f5; padding:15px; border-radius:5px; font-family:'Cambria Math','STIX Two Math',serif; line-height:1.5; white-space: pre-wrap; }}
        .metadata {{ font-size:12px; color:#666; margin:5px 0; }}
        .variables {{ margin-top:10px; }}
        .variable {{ font-size:12px; margin-left:20px; color:#555; }}
        .notes {{ font-size:12px; color:#555; margin-top:10px; padding:10px; background:#fafafa; border-left:3px solid #999; }}
        @media print {{ .formula {{ page-break-inside:avoid; }} }}
    </style>
</head>
<body>
    <div class="title-page">
        <div class="title-inner">Formulas #{total}</div>
    </div>
    {"".join(body_parts)}
</body>
</html>"""

    @classmethod
    def _export_to_html(cls, master_data: FormulaCollection, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(cls._build_html_content(master_data))

    @classmethod
    def _export_to_pdf(cls, master_data: FormulaCollection, path: str) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)

        printer.setPageMargins(
            QMarginsF(20, 20, 20, 20),
            QPageLayout.Unit.Millimeter
        )

        doc = QTextDocument()
        doc.setDocumentMargin(20)
        doc.setUseDesignMetrics(True)
        doc.setHtml(cls._build_html_content(master_data))

        page_rect = printer.pageRect(QPrinter.Unit.Point)
        doc.setPageSize(page_rect.size())

        doc.print(printer)

    @staticmethod
    def _export_to_txt(master_data: FormulaCollection, path: str) -> None:
        total = len(master_data)
        lines = [f"Formulas #{total}\n", "=" * 50 + "\n\n"]
        for entry in sorted(master_data.values(), key=lambda e: e.display_id):
            lines.append(f"#{entry.display_id}\nFormula: {entry.formula_text}\n")
            if entry.has_notes:
                lines.append(f"Notes: {entry.notes}\n")
            lines.append(f"Subject: {entry.subject} | Topic: {entry.topic} | Sub-Topic: {entry.display_sub_topic}\n")
            if entry.variables:
                lines.append("Variables:\n")
                for var in entry.variables:
                    unit = var.unit
                    text = f"{var.symbol} means {var.name}" if unit.lower() in NO_DIMENSION_UNITS else f"{var.symbol} means {var.name} with unit {unit}"
                    lines.append(f"  • {text}\n")
                lines.append("\n" + "-" * 30 + "\n\n")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("".join(lines))

    @staticmethod
    def _export_to_csv(master_data: FormulaCollection, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f,
                                    fieldnames=["ID", "Formula", "Field", "Topic", "Sub-Topic", "Notes", "Variables"])
            writer.writeheader()
            for entry in sorted(master_data.values(), key=lambda e: e.display_id):
                vars_str = "; ".join(f"{v.symbol}: {v.name} ({v.unit})" for v in entry.variables)
                writer.writerow({
                    "ID": entry.display_id, "Formula": entry.formula_text, "Field": entry.subject,
                    "Topic": entry.topic, "Sub-Topic": entry.display_sub_topic, "Variables": vars_str,
                    "Notes": entry.notes,
                })

    @staticmethod
    def _export_to_json(master_data: FormulaCollection, path: str) -> None:
        export_data = {
            "total_formulas": len(master_data),
            "export_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "formulas": {
                str(entry.display_id): {
                    "formula": entry.formula_text, "field": entry.subject,
                    "topic": entry.topic, "sub_topic": entry.sub_topic,
                    "notes": entry.notes,
                    "variables": [v.to_dict() for v in entry.variables],
                }
                for entry in sorted(master_data.values(), key=lambda e: e.display_id)
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _export_to_markdown(master_data: FormulaCollection, path: str) -> None:
        total = len(master_data)
        lines = [
            f"# Formulas Collection ({total} formulas)\n\n",
            f"*Exported on {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n---\n\n",
        ]
        for entry in sorted(master_data.values(), key=lambda e: e.display_id):
            lines.append(f"## #{entry.display_id}\n\n**Formula:** `{entry.formula_text}`\n\n")
            if entry.has_notes:
                lines.append(f"**Notes:** {entry.notes}\n\n")
            lines.append(
                f"**Field:** {entry.subject} | **Topic:** {entry.topic} | **Sub-Topic:** {entry.display_sub_topic}\n\n")
            if entry.variables:
                lines.append("**Variables:**\n")
                for var in entry.variables:
                    sym, name, unit = var.symbol, var.name, var.unit
                    text = f"- **{sym}** means {name}" if unit.lower() in NO_DIMENSION_UNITS else f"- **{sym}** means {name} with unit {unit}"
                    lines.append(f"{text}\n")
                lines.append("\n")
            lines.append("---\n\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(lines))


# ── Hierarchical Filter Dialog ──

class ExportDialog(QDialog):
    """
    Export dialog with a hierarchical filter tree.
    """

    def __init__(self, parent=None, master_data: FormulaCollection | None = None):
        super().__init__(parent)
        self.master_data = master_data or FormulaCollection()
        self.selected_format = "html"

        self.setWindowTitle("Export Formulas")
        self.setMinimumSize(520, 600)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self.root_node = HierarchyNode("All", "all")
        self._build_hierarchy()

        self._all_checkboxes: List[QCheckBox] = []
        self._subject_nodes: List[Tuple[HierarchyNode, QCheckBox]] = []
        self._topic_nodes: List[Tuple[HierarchyNode, QCheckBox]] = []
        self._subtopic_nodes: List[Tuple[HierarchyNode, QCheckBox]] = []

        self._build_ui()
        self._apply_styles()

    def _build_hierarchy(self):
        """Build subject/topic/sub-topic tree from master_data."""
        for entry in self.master_data.values():
            self.root_node.add_formula(
                entry.display_id,
                entry.subject,
                entry.topic,
                entry.sub_topic
            )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QLabel("📄 Export Formulas")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(header)

        info = QLabel(f"{len(self.master_data)} formulas available")
        info.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(info)

        self._build_format_section(layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #333;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        filter_label = QLabel("Filter by Hierarchy")
        filter_label.setStyleSheet("font-weight: bold; color: #aaa; font-size: 13px;")
        layout.addWidget(filter_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(280)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.tree_container = QWidget()
        self.tree_layout = QVBoxLayout(self.tree_container)
        self.tree_layout.setContentsMargins(0, 0, 0, 0)
        self.tree_layout.setSpacing(4)
        self.tree_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._build_tree()

        self.tree_layout.addStretch()
        scroll.setWidget(self.tree_container)
        layout.addWidget(scroll, stretch=1)

        self.summary_label = QLabel("Selected: 0 formulas")
        self.summary_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.summary_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        export_btn = QPushButton("Export")
        export_btn.setObjectName("primaryBtn")
        export_btn.clicked.connect(self._do_export)
        btn_row.addWidget(export_btn)

        layout.addLayout(btn_row)

        self._update_summary()

    def _build_format_section(self, parent_layout: QVBoxLayout):
        fmt_frame = QFrame()
        fmt_frame.setObjectName("formArea")
        fmt_layout = QVBoxLayout(fmt_frame)
        fmt_layout.setContentsMargins(16, 16, 16, 16)
        fmt_layout.setSpacing(10)

        fmt_label = QLabel("Select Export Format:")
        fmt_label.setStyleSheet("font-weight: bold; color: #aaa;")
        fmt_layout.addWidget(fmt_label)

        self.format_combo = QComboBox()
        self.format_combo.setMinimumWidth(280)
        self.format_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #f0f0f0;
                border: 1px solid #404040;
                selection-background-color: #2980b9;
            }
        """)
        formats = ExportManager.get_supported_formats()
        for key, label in formats.items():
            self.format_combo.addItem(label, key)
        self.format_combo.setCurrentIndex(0)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(self.format_combo)

        parent_layout.addWidget(fmt_frame)

    def _build_tree(self):
        all_cb = QCheckBox(f"All  ({len(self.master_data)} formulas)")
        all_cb.setTristate(True)
        all_cb.setChecked(True)
        all_cb.stateChanged.connect(self._on_all_changed)
        self.root_node.checkbox = all_cb
        self.tree_layout.addWidget(all_cb)
        self._all_checkboxes.append(all_cb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #444;")
        sep.setFixedHeight(1)
        self.tree_layout.addWidget(sep)

        for subject_name in sorted(self.root_node.children.keys()):
            subj_node = self.root_node.children[subject_name]
            count = len(subj_node.formula_ids)

            subj_frame = QFrame()
            subj_frame.setObjectName("subjectFrame")
            subj_layout = QVBoxLayout(subj_frame)
            subj_layout.setContentsMargins(12, 8, 8, 8)
            subj_layout.setSpacing(4)

            header_layout = QHBoxLayout()
            header_layout.setSpacing(6)

            toggle_btn = QPushButton("▶")
            toggle_btn.setFixedSize(22, 22)
            toggle_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #888;
                    border: none;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0px;
                }
                QPushButton:hover { color: #ccc; }
            """)
            header_layout.addWidget(toggle_btn)

            subj_cb = QCheckBox(f"{subject_name}  ({count})")
            subj_cb.setTristate(True)
            subj_cb.setChecked(True)
            subj_cb.stateChanged.connect(
                lambda state,
                       node=subj_node: self._on_subject_changed(node, state)
            )
            subj_node.checkbox = subj_cb
            header_layout.addWidget(subj_cb, stretch=1)
            subj_layout.addLayout(header_layout)
            self._subject_nodes.append((subj_node, subj_cb))

            topics_container = QFrame()
            topics_container.setStyleSheet("border-left: 2px solid #333;")

            topics_layout = QVBoxLayout(topics_container)
            topics_layout.setContentsMargins(24, 4, 0, 4)
            topics_layout.setSpacing(2)

            for topic_name in sorted(subj_node.children.keys()):
                topic_node = subj_node.children[topic_name]
                tcount = len(topic_node.formula_ids)

                topic_wrapper = QFrame()
                topic_wrapper_layout = QVBoxLayout(topic_wrapper)
                topic_wrapper_layout.setContentsMargins(0, 0, 0, 0)
                topic_wrapper_layout.setSpacing(2)

                topic_header = QHBoxLayout()
                topic_header.setSpacing(6)

                topic_toggle = QPushButton("▶")
                topic_toggle.setFixedSize(24, 24)
                topic_toggle.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #888;
                        border: none;
                        font-size: 11px;
                        font-weight: bold;
                        padding: 0px;
                    }
                    QPushButton:hover { color: #ccc; }
                """)
                topic_header.addWidget(topic_toggle)

                topic_cb = QCheckBox(f"{topic_name}  ({tcount})")
                topic_cb.setTristate(True)
                topic_cb.setChecked(True)
                topic_cb.stateChanged.connect(
                    lambda state,
                           node=topic_node,
                           parent_node=subj_node: self._on_topic_changed(node, state)
                )
                topic_node.checkbox = topic_cb
                topic_header.addWidget(topic_cb, stretch=1)
                topic_wrapper_layout.addLayout(topic_header)
                self._topic_nodes.append((topic_node, topic_cb))

                sub_container = QFrame()
                sub_container.setStyleSheet("border-left: 2px solid #2a2a2a;")

                sub_layout = QVBoxLayout(sub_container)
                sub_layout.setContentsMargins(48, 2, 0, 2)
                sub_layout.setSpacing(1)

                for sub_name in sorted(topic_node.children.keys()):
                    sub_node = topic_node.children[sub_name]
                    scount = len(sub_node.formula_ids)
                    display_name = sub_name if sub_name != "_GENERAL_" else "(General)"

                    sub_cb = QCheckBox(f"{display_name}  ({scount})")
                    sub_cb.setChecked(True)
                    sub_cb.stateChanged.connect(
                        lambda state,
                               node=sub_node,
                               parent_node=topic_node: self._on_subtopic_changed()
                    )
                    sub_node.checkbox = sub_cb
                    sub_layout.addWidget(sub_cb)
                    self._subtopic_nodes.append((sub_node, sub_cb))

                topic_wrapper_layout.addWidget(sub_container)
                sub_container.hide()

                topic_toggle.clicked.connect(
                    lambda checked,
                           btn=topic_toggle,
                           container=sub_container: self._toggle_section(btn, container)
                )

                topics_layout.addWidget(topic_wrapper)

            subj_layout.addWidget(topics_container)
            topics_container.hide()
            self.tree_layout.addWidget(subj_frame)

            toggle_btn.clicked.connect(
                lambda checked,
                       btn=toggle_btn,
                       container=topics_container: self._toggle_section(btn, container)
            )

    @staticmethod
    def _toggle_section(btn: QPushButton, container: QWidget):
        """Toggle collapse/expand of a tree section."""
        if container.isVisible():
            container.hide()
            btn.setText("▶")
        else:
            container.show()
            btn.setText("▼")

    def _on_all_changed(self, state: int):
        """When 'All' is toggled, propagate to all subjects."""
        if state == Qt.CheckState.PartiallyChecked.value:
            return

        checked = state == Qt.CheckState.Checked.value
        for subj_node, _ in self._subject_nodes:
            self._set_checkbox_state(subj_node.checkbox, checked)
            self._propagate_subject(subj_node, checked)

        self._update_summary()

    def _on_subject_changed(self, node: HierarchyNode, state: int):
        """When a subject is toggled, propagate to its topics."""
        if state == Qt.CheckState.PartiallyChecked.value:
            return

        checked = state == Qt.CheckState.Checked.value
        self._propagate_subject(node, checked)
        self._sync_parent_states()
        self._update_summary()

    def _on_topic_changed(self, node: HierarchyNode, state: int):
        """When a topic is toggled, propagate to its sub-topics."""
        if state == Qt.CheckState.PartiallyChecked.value:
            return

        checked = state == Qt.CheckState.Checked.value
        self._propagate_topic(node, checked)
        self._sync_parent_states()
        self._update_summary()

    def _on_subtopic_changed(self):
        self._sync_parent_states()
        self._update_summary()

    def _propagate_subject(self, subj_node: HierarchyNode, checked: bool):
        """Set all topics and sub-topics under a subject."""
        for topic_node in subj_node.children.values():
            self._set_checkbox_state(topic_node.checkbox, checked)
            self._propagate_topic(topic_node, checked)

    def _propagate_topic(self, topic_node: HierarchyNode, checked: bool):
        """Set all sub-topics under a topic."""
        for sub_node in topic_node.children.values():
            self._set_checkbox_state(sub_node.checkbox, checked)

    @staticmethod
    def _set_checkbox_state(checkbox: QCheckBox | None, state):
        if checkbox:
            checkbox.blockSignals(True)
            if isinstance(state, bool):
                state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
            checkbox.setCheckState(state)
            checkbox.blockSignals(False)

    @staticmethod
    def _calculate_state_from_children(child_states):
        """Calculate parent state from child states."""
        if not child_states:
            return Qt.CheckState.Unchecked
        if all(s == 2 for s in child_states):
            return Qt.CheckState.Checked
        elif any(s > 0 for s in child_states):
            return Qt.CheckState.PartiallyChecked
        else:
            return Qt.CheckState.Unchecked

    def _sync_parent_states(self):
        """Recalculate all parent checkbox states from leaf nodes up."""
        for subj_node, subj_cb in self._subject_nodes:
            topic_states = []
            for topic_node in subj_node.children.values():
                sub_states = [
                    self._qt_state_to_numeric(sub_node.checkbox.checkState())
                    if sub_node.checkbox else 0
                    for sub_node in topic_node.children.values()
                ]
                state = self._calculate_state_from_children(sub_states)
                self._set_checkbox_state(topic_node.checkbox, state)
                topic_states.append(self._qt_state_to_numeric(state))

            subj_state = self._calculate_state_from_children(topic_states)
            self._set_checkbox_state(subj_cb, subj_state)

        subj_states = [self._qt_state_to_numeric(cb.checkState())
                       for _, cb in self._subject_nodes]
        all_state = self._calculate_state_from_children(subj_states)
        self._set_checkbox_state(self.root_node.checkbox, all_state)

    @staticmethod
    def _qt_state_to_numeric(state):
        """Convert Qt checkbox state to numeric representation."""
        if state == Qt.CheckState.Checked:
            return 2
        elif state == Qt.CheckState.PartiallyChecked:
            return 1
        else:
            return 0

    def _update_summary(self):
        """Update the selected count label."""
        selected_ids = self.root_node.get_selected_ids()
        self.summary_label.setText(f"Selected: {len(selected_ids)} formulas")

    def _on_format_changed(self, _index: int = 0):
        self.selected_format = self.format_combo.currentData()

    # ── Export Execution ──

    def _do_export(self):
        selected_ids = self.root_node.get_selected_ids()
        if not selected_ids:
            QMessageBox.warning(self, "No Selection", "No formulas selected for export.")
            return

        filtered_data = FormulaCollection()
        for display_id in selected_ids:
            entry = self.master_data.get(display_id)
            if entry:
                filtered_data.add(entry)

        ext = ExportManager.get_file_extension(self.selected_format)
        file_filter = ExportManager.get_file_filter(self.selected_format)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {self.selected_format.upper()} file",
            f"formulas_export{ext}",
            file_filter,
        )

        if not file_path:
            return

        if not file_path.lower().endswith(ext):
            file_path += ext

        try:
            ExportManager.export(filtered_data, file_path, self.selected_format)
            QMessageBox.information(
                self, "Export Complete",
                f"Successfully exported {len(filtered_data)} formulas to {self.selected_format.upper()}!\n\n{file_path}"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Export failed:\n\n{str(e)}")

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QWidget { font-family: "Segoe UI", "Arial", sans-serif; font-size: 13px; }
            #formArea { background-color: #252525; border-radius: 6px; }
            #subjectFrame {
                background-color: #1f1f1f;
                border-radius: 6px;
                border: 1px solid #2a2a2a;
            }
            #subjectFrame:hover { border-color: #333; }
            QScrollArea { border: none; background: transparent; }
            #primaryBtn {
                background-color: #2980b9; color: white; border: none;
                border-radius: 4px; padding: 8px 24px; font-weight: bold;
            }
            #primaryBtn:hover { background-color: #3498db; }
            #secondaryBtn {
                background-color: #3a3a3a; color: #e0e0e0;
                border: 1px solid #4a4a4a; border-radius: 4px; padding: 8px 20px;
            }
            #secondaryBtn:hover { background-color: #4a4a4a; }
        """)
