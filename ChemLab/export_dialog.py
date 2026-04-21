# -*- coding: utf-8 -*-
"""
Export Dialog for ChemLab - Export reactions to various formats with reaction type filtering
"""
import csv
import html
import json
import time
from typing import Dict, List, Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QScrollArea, QWidget, QFrame, QFileDialog,
    QMessageBox, QCheckBox
)

from constants import ARROW_MAP, STATE_NAMES


class ExportDialog(QDialog):
    """Dialog for exporting reactions with reaction type filtering"""

    def __init__(self, parent, database, reaction_types):
        super().__init__(parent)
        self.db = database
        self.all_reaction_types = reaction_types
        self.type_checkboxes = []  # Store (rtype, checkbox) tuples
        self.all_checkbox = None  # Parent "All" checkbox
        self.favorites_checkbox = None  # Favorites checkbox (independent)
        self.format_combo = None
        self._has_favorites = False  # Track if favorites exist

        self.setWindowTitle("Export Reactions")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Export Reactions")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel("Select export format and reaction types to include.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)

        # Format selection
        format_frame = QFrame()
        format_layout = QHBoxLayout(format_frame)
        format_layout.setContentsMargins(0, 0, 0, 0)

        format_label = QLabel("Format:")
        format_layout.addWidget(format_label)

        self.format_combo = QComboBox()
        self.format_combo.setMinimumWidth(150)
        self.format_combo.addItems(["HTML", "CSV", "JSON", "Markdown", "Text"])
        self.format_combo.setCurrentText("HTML")
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()

        layout.addWidget(format_frame)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ccc;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Scroll area for reaction type checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(200)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)

        self.selectors_container = QWidget()
        self.selectors_layout = QVBoxLayout(self.selectors_container)
        self.selectors_layout.setSpacing(8)
        self.selectors_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.selectors_layout.setContentsMargins(5, 5, 5, 5)

        # Create tree-style checkboxes
        self._create_type_checkboxes()

        scroll.setWidget(self.selectors_container)
        layout.addWidget(scroll)

        # Separator line
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #ccc;")
        line2.setFixedHeight(1)
        layout.addWidget(line2)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        export_btn = QPushButton("Export")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        export_btn.clicked.connect(self._perform_export)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

    def _create_type_checkboxes(self):
        """Create tree-style checkboxes with parent 'All' checkbox"""
        # White checkbox style - let Qt draw native checkmarks
        checkbox_style = """
            QCheckBox {
                color: white;
                padding: 6px;
                font-size: 13px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
        """

        # Parent "All" checkbox
        self.all_checkbox = QCheckBox("All")
        self.all_checkbox.setTristate(True)  # Enable 3-state mode
        self.all_checkbox.setChecked(True)
        self.all_checkbox.setStyleSheet(checkbox_style + """
            QCheckBox {
                font-weight: bold;
                font-size: 14px;
            }
        """)
        self.all_checkbox.stateChanged.connect(self._on_all_checkbox_changed)
        self.selectors_layout.addWidget(self.all_checkbox)

        # Add separator line under "All"
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #666;")
        separator.setFixedHeight(1)
        self.selectors_layout.addWidget(separator)

        # Add separator before Favorites
        fav_separator = QFrame()
        fav_separator.setFrameShape(QFrame.Shape.HLine)
        fav_separator.setStyleSheet("background-color: #666;")
        fav_separator.setFixedHeight(1)
        self.selectors_layout.addWidget(fav_separator)

        # Check if favorites exist
        all_reactions = self.db.get_all_reactions()
        self._has_favorites = any(r.get('is_favorite', 0) == 1 for r in all_reactions)

        # Favorites checkbox (independent, not under "All")
        self.favorites_checkbox = QCheckBox("★ Favorites")
        self.favorites_checkbox.setChecked(False)
        self.favorites_checkbox.setEnabled(self._has_favorites)
        self.favorites_checkbox.setStyleSheet(checkbox_style + """
            QCheckBox {
                font-weight: bold;
                color: #FFD700;
            }
        """)
        self.selectors_layout.addWidget(self.favorites_checkbox)

        # Add separator after Favorites
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet("background-color: #666;")
        separator2.setFixedHeight(1)
        self.selectors_layout.addWidget(separator2)

        # Individual reaction type checkboxes
        for rtype in self.all_reaction_types:
            checkbox = QCheckBox(rtype)
            checkbox.setChecked(True)
            checkbox.setStyleSheet(checkbox_style)
            checkbox.stateChanged.connect(self._on_type_checkbox_changed)
            self.type_checkboxes.append((rtype, checkbox))
            self.selectors_layout.addWidget(checkbox)

        self.selectors_layout.addStretch()

        # Initialize favorites checkbox state
        self._update_favorites_state()

    def _on_all_checkbox_changed(self, state):
        """Handle parent 'All' checkbox change"""
        # Only handle Checked or Unchecked states (ignore PartiallyChecked from user click)
        if state == Qt.CheckState.PartiallyChecked.value:
            return

        checked = state == Qt.CheckState.Checked.value
        for rtype, checkbox in self.type_checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

        # Update favorites checkbox enabled state based on whether all types are checked
        self._update_favorites_state()

    def _on_type_checkbox_changed(self):
        """Handle individual type checkbox change - update parent 'All' state"""
        checked_count = sum(1 for rtype, cb in self.type_checkboxes if cb.isChecked())
        total_count = len(self.type_checkboxes)

        self.all_checkbox.blockSignals(True)
        if checked_count == 0:
            self.all_checkbox.setCheckState(Qt.CheckState.Unchecked)
        elif checked_count == total_count:
            self.all_checkbox.setCheckState(Qt.CheckState.Checked)
        else:
            # Partial selection - show indeterminate state
            self.all_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        self.all_checkbox.blockSignals(False)

        # Update favorites checkbox enabled state
        self._update_favorites_state()

    def _update_favorites_state(self):
        """Enable/disable favorites checkbox based on selection state"""
        if not self._has_favorites:
            self.favorites_checkbox.setEnabled(False)
            return

        # Disable favorites if all reaction types are selected
        checked_count = sum(1 for rtype, cb in self.type_checkboxes if cb.isChecked())
        total_count = len(self.type_checkboxes)
        all_types_selected = (checked_count == total_count)

        self.favorites_checkbox.setEnabled(not all_types_selected)

    def _get_selected_types(self):
        """Get list of checked reaction types"""
        return [rtype for rtype, checkbox in self.type_checkboxes if checkbox.isChecked()]

    def _get_filtered_reactions(self):
        """Get reactions based on current filter settings"""
        all_reactions = self.db.get_all_reactions()
        selected_types = self._get_selected_types()
        export_favorites = self.favorites_checkbox.isChecked()

        # If no types selected and favorites not checked, return empty
        if not selected_types and not export_favorites:
            return []

        filtered_ids = set()

        # Add reactions from selected types
        if selected_types:
            for r in all_reactions:
                if r.get('reaction_type', 'Unknown') in selected_types:
                    filtered_ids.add(r['id'])

        # Add favorite reactions (additive - combines with selected types)
        if export_favorites:
            for r in all_reactions:
                if r.get('is_favorite', 0) == 1:
                    filtered_ids.add(r['id'])

        # Return all reactions whose IDs are in the filtered set
        filtered = [r for r in all_reactions if r['id'] in filtered_ids]
        return filtered

    def _perform_export(self):
        """Perform the export based on selected format"""
        export_format = self.format_combo.currentText().lower()

        # Check if we have reactions to export
        filtered = self._get_filtered_reactions()

        if not filtered:
            QMessageBox.warning(self, "No Reactions", "No reactions found for the selected reaction types.")
            return

        # Get file extension and filter based on format
        format_settings = {
            "html": (".html", "HTML files (*.html)"),
            "csv": (".csv", "CSV files (*.csv)"),
            "json": (".json", "JSON files (*.json)"),
            "markdown": (".md", "Markdown files (*.md)"),
            "text": (".txt", "Text files (*.txt)")
        }

        ext, file_filter = format_settings.get(export_format, (".txt", "Text files (*.txt)"))

        # Get file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {export_format.upper()} File",
            f"reactions_export{ext}",
            file_filter
        )

        if not file_path:
            return

        try:
            # Call appropriate export method based on format
            if export_format == "html":
                self._export_to_html(file_path, filtered)
            elif export_format == "csv":
                self._export_to_csv(file_path, filtered)
            elif export_format == "json":
                self._export_to_json(file_path, filtered)
            elif export_format == "markdown":
                self._export_to_markdown(file_path, filtered)
            else:  # text or unknown
                self._export_to_txt(file_path, filtered)

            QMessageBox.information(self, "Export Complete",
                                    f"Successfully exported reactions to {export_format.upper()}!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")

    def _export_to_html(self, file_path: str, reactions: List[Dict[str, Any]]) -> None:
        """Export reactions to HTML format with index of links"""
        # Sort reactions by reaction type
        reactions.sort(key=lambda rtn: (rtn.get('reaction_type', 'Unknown'), rtn['reaction_text']))

        # Group by reaction type
        grouped = {}
        for r in reactions:
            rtype = r.get('reaction_type', 'Unknown')
            if rtype not in grouped:
                grouped[rtype] = []
            grouped[rtype].append(r)

        total_reactions = len(reactions)

        # Build HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ChemLab Reactions ({total_reactions})</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
            color: #333;
        }}
        .title {{
            text-align: center;
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .subtitle {{
            text-align: center;
            font-size: 16px;
            color: #666;
            margin-bottom: 30px;
        }}
        .index {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 40px;
        }}
        .index h2 {{
            margin-top: 0;
            font-size: 18px;
            color: #2c3e50;
        }}
        .index-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .index-link {{
            display: inline-block;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 14px;
            transition: background-color 0.2s;
        }}
        .index-link:hover {{
            background-color: #0056b3;
        }}
        .reaction-type {{
            margin-top: 40px;
            page-break-before: always;
        }}
        .reaction-type:first-of-type {{
            page-break-before: auto;
        }}
        .type-header {{
            font-size: 22px;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .reaction {{
            margin-bottom: 25px;
            padding: 15px;
            background-color: #f8f9fa;
            border-left: 4px solid #28a745;
            border-radius: 4px;
            page-break-inside: avoid;
        }}
        .reaction-text {{
            font-size: 16px;
            font-family: 'Cambria Math', 'Times New Roman', serif;
            margin-bottom: 8px;
        }}
        .reaction-meta {{
            font-size: 12px;
            color: #666;
        }}
        .reaction-heat {{
            margin-top: 8px;
            font-size: 14px;
            font-weight: bold;
            font-family: 'Cambria Math', 'Times New Roman', serif;
        }}
        .compound-section {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #dee2e6;
        }}
        .compound-section-title {{
            font-size: 11px;
            font-weight: bold;
            color: #555;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .compound-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .compound-table th {{
            text-align: left;
            padding: 6px 8px;
            background-color: #e9ecef;
            color: #495057;
            font-weight: 600;
            border-bottom: 1px solid #dee2e6;
        }}
        .compound-table td {{
            padding: 6px 8px;
            border-bottom: 1px solid #e9ecef;
        }}
        .compound-table tr:last-child td {{
            border-bottom: none;
        }}
        .compound-formula {{
            font-family: 'Cambria Math', 'Times New Roman', serif;
            font-weight: 500;
        }}
        .compound-type {{
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
            text-transform: uppercase;
            font-weight: bold;
        }}
        .type-reactant {{
            background-color: #fff3cd;
            color: #856404;
        }}
        .type-product {{
            background-color: #d4edda;
            color: #155724;
        }}
        /* Scroll to top button */
        #scrollToTopBtn {{
            display: none;
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 99;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
        }}
        #scrollToTopBtn:hover {{
            background-color: #0056b3;
            transform: translateY(-3px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.4);
        }}
        @media print {{
            .reaction {{
                page-break-inside: avoid;
            }}
            .compound-section {{
                page-break-inside: avoid;
            }}
            .reaction-type {{
                page-break-before: always;
            }}
            .reaction-type:first-of-type {{
                page-break-before: auto;
            }}
            #scrollToTopBtn {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="title" id="top">ChemLab Reactions</div>
    <div class="subtitle">Total Reactions: {total_reactions}</div>

    <!-- Scroll to top button -->
    <button id="scrollToTopBtn" title="Go to top">&#8593;</button>

    <script>
        // Get the button
        const scrollToTopBtn = document.getElementById("scrollToTopBtn");

        // When user scrolls down 300px from top, show button
        window.onscroll = function() {{
            if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {{
                scrollToTopBtn.style.display = "block";
            }} else {{
                scrollToTopBtn.style.display = "none";
            }}
        }};

        // When user clicks button, scroll to top
        scrollToTopBtn.addEventListener("click", function() {{
            window.scrollTo({{
                top: 0,
                behavior: "smooth"
            }});
        }});
    </script>
"""

        # Build index
        html_content += '    <div class="index">\n'
        html_content += '        <h2>Jump to Reaction Type</h2>\n'
        html_content += '        <div class="index-list">\n'

        for rtype in sorted(grouped.keys()):
            anchor = self._sanitize_anchor(rtype)
            count = len(grouped[rtype])
            html_content += f'            <a href="#{anchor}" class="index-link">{html.escape(rtype)} ({count})</a>\n'

        html_content += '        </div>\n'
        html_content += '    </div>\n'

        # Build reaction sections
        for rtype in sorted(grouped.keys()):
            anchor = self._sanitize_anchor(rtype)
            html_content += f'    <div class="reaction-type" id="{anchor}">\n'
            html_content += f'        <div class="type-header">{html.escape(rtype)}</div>\n'

            for reaction in grouped[rtype]:
                reaction_text = self._convert_arrows_to_unicode(reaction['reaction_text'])
                reaction_text = html.escape(reaction_text)

                html_content += '        <div class="reaction">\n'
                html_content += f'            <div class="reaction-text">{reaction_text}</div>\n'

                # Add heat output if available (separate from conditions)
                heat_value = reaction.get('heat_value', '')
                heat_type = reaction.get('heat_type', '')
                if heat_value or heat_type:
                    heat_display, _ = self._format_heat_display(heat_value, heat_type, use_html=True)
                    html_content += f'            <div class="reaction-heat" style="margin-top: 8px; font-size: 1em;">{heat_display}</div>\n'

                # Add reaction conditions if available
                temp = reaction.get('temperature', '')
                temp_unit = reaction.get('temperature_unit', '')
                pressure = reaction.get('pressure', '')
                pressure_unit = reaction.get('pressure_unit', '')
                catalyst = reaction.get('catalyst', '')
                if temp or pressure or catalyst:
                    conditions_parts = []
                    if temp:
                        temp_str = f"{html.escape(temp)}{html.escape(temp_unit)}" if temp_unit else html.escape(temp)
                        conditions_parts.append(f"Temp: {temp_str}")
                    if pressure:
                        pressure_str = f"{html.escape(pressure)}{html.escape(pressure_unit)}" if pressure_unit else html.escape(
                            pressure)
                        conditions_parts.append(f"Pressure: {pressure_str}")
                    if catalyst:
                        conditions_parts.append(f"Catalyst: {html.escape(catalyst)}")
                    conditions_text = " | ".join(conditions_parts)
                    html_content += f'            <div class="reaction-conditions" style="color: #666; font-size: 0.9em; margin-top: 5px;">Conditions: {conditions_text}</div>\n'

                # Add compound details if available
                compounds = self.db.get_compounds_for_reaction(reaction['id'])
                if compounds:
                    html_content += '            <div class="compound-section">\n'
                    html_content += '                <div class="compound-section-title">Compounds</div>\n'
                    html_content += '                <table class="compound-table">\n'
                    html_content += '                    <tr><th>Formula</th><th>Type</th><th>Name</th><th>Color</th><th>State</th></tr>\n'

                    for compound in compounds:
                        formula = self._convert_to_subscript_html(compound.get('formula', ''))
                        name = html.escape(compound.get('name', 'Unknown'))
                        color = html.escape(compound.get('color', 'Unknown'))
                        state_abbr = compound.get('state', '')
                        state_full = STATE_NAMES.get(state_abbr, state_abbr)
                        comp_type = compound.get('type', 'Unknown')

                        type_class = 'type-reactant' if comp_type == 'Reactant' else 'type-product'

                        html_content += f'                    <tr>\n'
                        html_content += f'                        <td class="compound-formula">{formula}</td>\n'
                        html_content += f'                        <td><span class="compound-type {type_class}">{comp_type}</span></td>\n'
                        html_content += f'                        <td>{name}</td>\n'
                        html_content += f'                        <td>{color}</td>\n'
                        html_content += f'                        <td>{state_full}</td>\n'
                        html_content += f'                    </tr>\n'

                    html_content += '                </table>\n'
                    html_content += '            </div>\n'

                html_content += '        </div>\n'

            html_content += '    </div>\n'

        html_content += """</body>
</html>"""

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _export_to_csv(self, file_path: str, reactions: List[Dict[str, Any]]) -> None:
        """Export reactions to CSV format"""
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['ID', 'Reaction', 'Type', 'Compound Count', 'Temperature', 'Pressure', 'Catalyst',
                          'ΔH Output', 'Heat Value', 'Heat Type']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()

            for r in reactions:
                compounds = self.db.get_compounds_for_reaction(r['id'])
                compound_count = len(compounds) if compounds else 0

                # Format temperature and pressure with units if available
                temp = r.get('temperature', '')
                temp_unit = r.get('temperature_unit', '')
                pressure = r.get('pressure', '')
                pressure_unit = r.get('pressure_unit', '')
                catalyst = r.get('catalyst', '')

                temp_display = f"{temp}{temp_unit}" if temp and temp_unit else (temp if temp else '')
                pressure_display = f"{pressure}{pressure_unit}" if pressure and pressure_unit else (
                    pressure if pressure else '')

                # Get heat info with formatted output
                heat_value = r.get('heat_value', '')
                heat_type = r.get('heat_type', '')
                heat_output, _ = self._format_heat_display(heat_value, heat_type, use_html=False)

                writer.writerow({
                    'ID': r['id'],
                    'Reaction': r['reaction_text'],
                    'Type': r.get('reaction_type', 'Unknown'),
                    'Compound Count': compound_count,
                    'Temperature': temp_display,
                    'Pressure': pressure_display,
                    'Catalyst': catalyst,
                    'ΔH Output': heat_output,
                    'Heat Value': heat_value,
                    'Heat Type': heat_type
                })

    def _export_to_json(self, file_path: str, reactions: List[Dict[str, Any]]) -> None:
        """Export reactions to JSON format"""
        export_data = {
            'total_reactions': len(reactions),
            'export_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'reactions': []
        }

        for r in reactions:
            compounds = self.db.get_compounds_for_reaction(r['id'])
            # Get formatted heat output
            heat_value = r.get('heat_value', '')
            heat_type = r.get('heat_type', '')
            heat_output, _ = self._format_heat_display(heat_value, heat_type, use_html=False)
            reaction_data = {
                'id': r['id'],
                'reaction_text': r['reaction_text'],
                'reaction_type': r.get('reaction_type', 'Unknown'),
                'temperature': r.get('temperature', ''),
                'temperature_unit': r.get('temperature_unit', ''),
                'pressure': r.get('pressure', ''),
                'pressure_unit': r.get('pressure_unit', ''),
                'catalyst': r.get('catalyst', ''),
                'heat_value': heat_value,
                'heat_type': heat_type,
                'heat_output': heat_output,
                'compounds': compounds if compounds else []
            }
            export_data['reactions'].append(reaction_data)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    def _export_to_markdown(self, file_path: str, reactions: List[Dict[str, Any]]) -> None:
        """Export reactions to Markdown format"""
        total = len(reactions)

        content = f"# ChemLab Reactions ({total} reactions)\n\n"
        content += f"*Exported on {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        content += "---\n\n"

        # Group by reaction type
        grouped = {}
        for r in reactions:
            rtype = r.get('reaction_type', 'Unknown')
            if rtype not in grouped:
                grouped[rtype] = []
            grouped[rtype].append(r)

        # Table of contents
        content += "## Reaction Types\n\n"
        for rtype in sorted(grouped.keys()):
            count = len(grouped[rtype])
            content += f"- [{rtype} ({count})]\n"
        content += "\n---\n\n"

        # Reactions by type
        for rtype in sorted(grouped.keys()):
            content += f"## {rtype}\n\n"

            for r in grouped[rtype]:
                content += f"**{r['reaction_text']}**\n\n"

                # Add heat output if available (separate from conditions)
                heat_value = r.get('heat_value', '')
                heat_type = r.get('heat_type', '')
                if heat_value or heat_type:
                    heat_display, _ = self._format_heat_display(heat_value, heat_type, use_html=False)
                    content += f"*{heat_display}*\n\n"

                # Add conditions if available
                temp = r.get('temperature', '')
                temp_unit = r.get('temperature_unit', '')
                pressure = r.get('pressure', '')
                pressure_unit = r.get('pressure_unit', '')
                catalyst = r.get('catalyst', '')
                if temp or pressure or catalyst:
                    conditions_parts = []
                    if temp:
                        temp_str = f"{temp}{temp_unit}" if temp_unit else temp
                        conditions_parts.append(f"Temp: {temp_str}")
                    if pressure:
                        pressure_str = f"{pressure}{pressure_unit}" if pressure_unit else pressure
                        conditions_parts.append(f"Pressure: {pressure_str}")
                    if catalyst:
                        conditions_parts.append(f"Catalyst: {catalyst}")
                    content += f"*Conditions: {' | '.join(conditions_parts)}*\n\n"

                compounds = self.db.get_compounds_for_reaction(r['id'])
                if compounds:
                    reactants = sum(1 for c in compounds if c['type'] == 'Reactant')
                    products = sum(1 for c in compounds if c['type'] == 'Product')
                    content += f"*Compounds: {reactants} reactant(s), {products} product(s)*\n\n"
                content += "\n"

            content += "---\n\n"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _export_to_txt(self, file_path: str, reactions: List[Dict[str, Any]]) -> None:
        """Export reactions to plain text format"""
        total = len(reactions)

        content = f"ChemLab Reactions ({total} reactions)\n"
        content += "=" * 50 + "\n\n"

        # Group by reaction type
        grouped = {}
        for r in reactions:
            rtype = r.get('reaction_type', 'Unknown')
            if rtype not in grouped:
                grouped[rtype] = []
            grouped[rtype].append(r)

        for rtype in sorted(grouped.keys()):
            content += f"\n{rtype}\n"
            content += "-" * len(rtype) + "\n\n"

            for r in grouped[rtype]:
                content += f"  {r['reaction_text']}\n"

                # Add heat output if available (separate from conditions)
                heat_value = r.get('heat_value', '')
                heat_type = r.get('heat_type', '')
                if heat_value or heat_type:
                    heat_display, _ = self._format_heat_display(heat_value, heat_type, use_html=False)
                    content += f"    [{heat_display}]\n"

                # Add reaction conditions if available
                temp = r.get('temperature', '')
                temp_unit = r.get('temperature_unit', '')
                pressure = r.get('pressure', '')
                pressure_unit = r.get('pressure_unit', '')
                catalyst = r.get('catalyst', '')
                if temp or pressure or catalyst:
                    conditions_parts = []
                    if temp:
                        temp_str = f"{temp}{temp_unit}" if temp_unit else temp
                        conditions_parts.append(f"Temp: {temp_str}")
                    if pressure:
                        pressure_str = f"{pressure}{pressure_unit}" if pressure_unit else pressure
                        conditions_parts.append(f"Pressure: {pressure_str}")
                    if catalyst:
                        conditions_parts.append(f"Catalyst: {catalyst}")
                    content += f"    [Conditions: {' | '.join(conditions_parts)}]\n"

                compounds = self.db.get_compounds_for_reaction(r['id'])
                if compounds:
                    reactants = sum(1 for c in compounds if c['type'] == 'Reactant')
                    products = sum(1 for c in compounds if c['type'] == 'Product')
                    content += f"    [{reactants} reactant(s), {products} product(s)]\n"
                content += "\n"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    @staticmethod
    def _sanitize_anchor(text):
        """Convert text to valid HTML/Markdown anchor ID"""
        return text.lower().replace(' ', '-').replace('/', '-')

    @staticmethod
    def _format_heat_display(heat_value: Any, heat_type: Any, use_html: bool = False) -> tuple:
        """Format heat value with sign based on type.

        Returns tuple: (display_text, color_code)
        Colors: Exothermic = red (#ff6b6b), Endothermic = blue (#4dabf7), Unknown = yellow (#ffd43b)
        """
        # Color codes
        EXOTHERMIC_COLOR = "#ff6b6b"  # Red
        ENDOTHERMIC_COLOR = "#4dabf7"  # Blue
        UNKNOWN_COLOR = "#ffd43b"  # Yellow

        # Handle None values
        heat_value = heat_value if heat_value is not None else ''
        heat_type = heat_type if heat_type is not None else ''

        if not heat_value and not heat_type:
            return None, None

        # Format based on type
        heat_type_lower = heat_type.lower()

        if heat_type_lower == 'exothermic':
            # Exothermic: negative sign
            try:
                val = abs(float(heat_value)) if heat_value else '?'
            except (ValueError, TypeError):
                val = '?'
            display = f"ΔH = -{val} kJ/mol (Exothermic)"
            color = EXOTHERMIC_COLOR
        elif heat_type_lower == 'endothermic':
            # Endothermic: positive sign
            try:
                val = float(heat_value) if heat_value else '?'
            except (ValueError, TypeError):
                val = '?'
            display = f"ΔH = +{val} kJ/mol (Endothermic)"
            color = ENDOTHERMIC_COLOR
        else:
            # Unknown type: just show value
            if heat_value:
                try:
                    sign = "+" if float(heat_value) > 0 else ""
                    display = f"ΔH = {sign}{heat_value} kJ/mol"
                except (ValueError, TypeError):
                    display = f"ΔH = {heat_value} kJ/mol"
            else:
                display = f"Type: {heat_type}"
            color = UNKNOWN_COLOR

        if use_html:
            display = f'<span style="color: {color}; font-weight: bold;">{display}</span>'

        return display, color

    @staticmethod
    def _convert_arrows_to_unicode(text):
        """Convert ASCII arrow representations to Unicode arrows"""
        if not text:
            return text

        # Convert arrows - sort by length descending to avoid partial matches
        arrows = sorted(ARROW_MAP.items(), key=lambda x: len(x[0]), reverse=True)
        for ascii_arrow, unicode_arrow in arrows:
            text = text.replace(ascii_arrow, unicode_arrow)

        return text

    @staticmethod
    def _convert_to_subscript_html(text):
        """Convert numbers in text to HTML subscript tags"""
        if not text:
            return text

        result = []
        i = 0
        while i < len(text):
            char = text[i]
            # Check if character is a digit
            if char.isdigit():
                result.append(f'<sub>{char}</sub>')
            else:
                result.append(html.escape(char))
            i += 1

        return ''.join(result)
