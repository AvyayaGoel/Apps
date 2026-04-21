"""Stats dialog for displaying reaction statistics."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)


class StatsDialog(QDialog):
    """Dialog displaying reaction statistics with clickable type filters."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.total_label = QLabel("Total Reactions: Loading...")
        self.heat_table = QTableWidget()
        self.types_table = QTableWidget()
        self.db = db
        self.parent_window = parent
        self.setWindowTitle("Reaction Statistics")
        self.setGeometry(200, 200, 600, 550)  # Wider and taller
        self.init_ui()
        self.load_stats()

    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Total count section
        total_group = QGroupBox("Overview")
        total_layout = QVBoxLayout()

        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        self.total_label.setFont(font)
        total_layout.addWidget(self.total_label)
        total_group.setLayout(total_layout)
        layout.addWidget(total_group)

        # Instruction label (moved outside boxes)
        instruction = QLabel("Click a type to filter the main window:")
        layout.addWidget(instruction)

        # Heat type section (Exothermic/Endothermic) - fixed size, no expand
        heat_group = QGroupBox("Reactions by Heat Type")
        heat_layout = QVBoxLayout()
        heat_layout.setContentsMargins(5, 5, 5, 5)
        heat_layout.setSpacing(2)

        # Table for heat types
        self.heat_table.setColumnCount(2)
        self.heat_table.setHorizontalHeaderLabels(["Heat Type", "Count"])
        heat_header = self.heat_table.horizontalHeader()
        if heat_header:
            heat_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            heat_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.heat_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.heat_table.setAlternatingRowColors(True)
        self.heat_table.cellClicked.connect(self.on_heat_type_clicked)
        # Auto-size height to fit content (no scrolling)
        self.heat_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.heat_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        heat_layout.addWidget(self.heat_table)

        heat_group.setLayout(heat_layout)
        layout.addWidget(heat_group)
        # Heat group doesn't expand - fixed size based on content

        # Reaction types section - expands to fill remaining space
        types_group = QGroupBox("Reactions by Type")
        types_layout = QVBoxLayout()
        types_layout.setContentsMargins(5, 5, 5, 5)

        # Table for reaction types
        self.types_table.setColumnCount(2)
        self.types_table.setHorizontalHeaderLabels(["Reaction Type", "Count"])
        header = self.types_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.types_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.types_table.setAlternatingRowColors(True)
        self.types_table.cellClicked.connect(self.on_type_clicked)
        types_layout.addWidget(self.types_table)

        types_group.setLayout(types_layout)
        layout.addWidget(types_group, 1)  # Stretch factor 1 = expand

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def load_stats(self):
        """Load statistics from the database."""
        # Get total count
        total_count = self.db.get_total_reaction_count()
        self.total_label.setText(f"Total Reactions: {total_count}")

        # Get counts by heat type
        heat_counts = self.db.get_reaction_counts_by_heat_type()

        # Populate heat table
        self.heat_table.setRowCount(2)
        heat_types = [
            ("Exothermic", heat_counts['exothermic']),
            ("Endothermic", heat_counts['endothermic'])
        ]
        for row, (heat_type, count) in enumerate(heat_types):
            # Heat type name (non-editable)
            type_item = QTableWidgetItem(heat_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            type_item.setData(Qt.ItemDataRole.UserRole, heat_type)
            self.heat_table.setItem(row, 0, type_item)

            # Count (non-editable, centered)
            count_item = QTableWidgetItem(str(count))
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.heat_table.setItem(row, 1, count_item)

        # Adjust height to fit content exactly
        self._adjust_heat_table_height()

        # Get counts by type
        type_counts = self.db.get_reaction_counts_by_type()

        # Populate types table
        self.types_table.setRowCount(len(type_counts))
        for row, (reaction_type, count) in enumerate(type_counts):
            # Type name (non-editable)
            type_item = QTableWidgetItem(reaction_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            type_item.setData(Qt.ItemDataRole.UserRole, reaction_type)
            self.types_table.setItem(row, 0, type_item)

            # Count (non-editable, centered)
            count_item = QTableWidgetItem(str(count))
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.types_table.setItem(row, 1, count_item)

    def _adjust_heat_table_height(self):
        """Calculate and set exact height needed for all rows + header"""
        # Calculate total height: header + rows + margins
        header_height = self.heat_table.horizontalHeader().height()
        row_height = self.heat_table.verticalHeader().defaultSectionSize()
        row_count = self.heat_table.rowCount()
        # Add small buffer for borders
        total_height = header_height + (row_height * row_count) + 4
        self.heat_table.setFixedHeight(total_height)

    def on_heat_type_clicked(self, row):
        """Handle click on a heat type row."""
        # Get the heat type from the clicked row
        heat_item = self.heat_table.item(row, 0)
        if heat_item:
            heat_type = heat_item.data(Qt.ItemDataRole.UserRole)

            # Set the filter in the parent window if available
            if self.parent_window and hasattr(self.parent_window, 'set_type_filter'):
                self.parent_window.set_type_filter(heat_type)

    def on_type_clicked(self, row):
        """Handle click on a reaction type row."""
        # Get the reaction type from the clicked row
        type_item = self.types_table.item(row, 0)
        if type_item:
            reaction_type = type_item.data(Qt.ItemDataRole.UserRole)

            # Set the filter in the parent window if available
            if self.parent_window and hasattr(self.parent_window, 'set_type_filter'):
                self.parent_window.set_type_filter(reaction_type)
            elif self.parent_window and hasattr(self.parent_window, 'current_type_filter'):
                # Direct attribute access fallback
                self.parent_window.current_type_filter = reaction_type
                if hasattr(self.parent_window, 'apply_type_filter'):
                    self.parent_window.apply_type_filter()
                elif hasattr(self.parent_window, 'load_data'):
                    self.parent_window.load_data()

            # Close this dialog
            self.close()

    def close(self):
        """Close the dialog."""
        super().close()
        if self.parent_window:
            self.parent_window.stats_dialog = None
