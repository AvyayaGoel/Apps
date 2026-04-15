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
        self.types_table = QTableWidget()
        self.db = db
        self.parent_window = parent
        self.setWindowTitle("Reaction Statistics")
        self.setGeometry(200, 200, 500, 400)
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

        # Reaction types section
        types_group = QGroupBox("Reactions by Type")
        types_layout = QVBoxLayout()

        # Instruction label
        instruction = QLabel("Click a type to filter the main window:")
        types_layout.addWidget(instruction)

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
        layout.addWidget(types_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def load_stats(self):
        """Load statistics from the database."""
        # Get total count
        total_count = self.db.get_total_reaction_count()
        self.total_label.setText(f"Total Reactions: {total_count}")

        # Get counts by type
        type_counts = self.db.get_reaction_counts_by_type()

        # Populate table
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