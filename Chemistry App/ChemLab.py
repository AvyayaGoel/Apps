import logging
import re
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (QFont, QKeySequence, QShortcut,
                         QIntValidator, QIcon, QAction, QColor)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QLineEdit, QPushButton, QLabel,
                             QGroupBox, QHeaderView, QMessageBox,
                             QFrame, QGridLayout, QMenu)
from mendeleev import element

from chemlab_database import ChemLabDatabase
from chemlab_parser import ChemLabParser
from constants import (
    DEFAULT_COLOR, REACTIONS_COLUMNS,
    COMPOUNDS_COLUMNS, ELEMENTS_COLUMNS, SUBSCRIPT_DIGITS, STATE_NAMES,
    COLOR_STYLE, FONT, ICON_PATH, ARROW_MAP
)
from stats_dialog import StatsDialog
from toast_widget import ToastManager
from export_dialog import ExportDialog
from calculate_dialog import CalculateDialog
from reaction_dialog import ReactionDialog

logging.basicConfig(
    filename="chemlab_errors.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class ChemLab(QMainWindow):
    def __init__(self):
        super().__init__()
        self.stats_dialog = None
        self.setWindowTitle("ChemLab - Chemistry Laboratory Manager")
        self.setGeometry(100, 100, 1400, 800)
        self.setWindowIcon(QIcon(ICON_PATH))

        self.db = ChemLabDatabase()

        self.viewing_reaction_id = None  # Track which reaction is being viewed
        self.view_overlay = None  # Overlay widget for viewing reactions
        self.compound_overlay = None  # Overlay widget for viewing compound stats
        self.compound_overlay_parent = None  # Track parent overlay to return to
        self.keyboard_window = None
        self.reactions_table = QTableWidget()
        self.view_reaction_btn = QPushButton("👁 View")
        self.edit_reaction_btn = QPushButton("✏️ Edit")
        self.delete_reaction_btn = QPushButton("🗑 Delete")
        self.cancel_calc_btn = QPushButton("❌ Cancel Calculation")  # Cancel button for calculation selection mode
        self.filter_menu = QMenu(self)
        self.central_widget = None  # Will hold reference to central widget

        # Calculate dialog and selection mode tracking
        self.calculate_dialog = None
        self.in_calculation_selection_mode = False

        # Search and pagination controls (initialized in create_reactions_table)
        self.search_entry = None
        self.clear_search_btn = None
        self.filter_btn = None
        self.first_page_btn = None
        self.prev_page_btn = None
        self.page_entry = None
        self.page_label = None
        self.next_page_btn = None
        self.last_page_btn = None
        self.reactions_group = None  # Created in create_reactions_table

        # Pagination state
        self.current_page = 1
        self.items_per_page = 10
        self.filtered_reactions = []
        self.all_reactions = []
        self.current_type_filter = "All"
        self._target_reaction_id = None  # Track reaction to jump to after load

        # Ctrl+D shortcut for delete selected
        self.delete_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.delete_shortcut.activated.connect(self.delete_selected_reaction)

        # Ctrl+V shortcut for view selected
        self.view_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.view_shortcut.activated.connect(self.view_selected_reaction)

        # Ctrl+E shortcut for edit selected
        self.edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        self.edit_shortcut.activated.connect(self.edit_selected_reaction)

        # Initialize UI
        self.init_ui()
        self.load_data()

        # Toast notification manager
        self.toast = ToastManager(self)

    def init_ui(self):
        # Create menubar first
        self.create_menubar()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Main layout
        main_layout = QVBoxLayout(self.central_widget)

        # Reactions Table Section (at the top)
        self.create_reactions_table(main_layout)

    def create_reactions_table(self, parent_layout):
        self.reactions_group = QGroupBox("Saved Reactions")
        reactions_layout = QVBoxLayout()

        # Search controls
        search_layout = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search reactions...")
        self.search_entry.textChanged.connect(self.on_search_text_changed)
        self.search_entry.keyPressEvent = self.on_reaction_key_press
        search_layout.addWidget(self.search_entry)

        # Filter button with dropdown menu - populated after data loads
        self.filter_btn = QPushButton("Filter")
        self.filter_btn.setToolTip("Filter by reaction type")
        self.filter_btn.setMenu(self.filter_menu)
        search_layout.addWidget(self.filter_btn)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(self.clear_search_btn)
        reactions_layout.addLayout(search_layout)

        # Reactions table
        table_font = QFont(FONT, 16)
        self.reactions_table.setColumnCount(3)
        self.reactions_table.setHorizontalHeaderLabels(REACTIONS_COLUMNS)
        header = self.reactions_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Star column - fixed width
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Reaction - stretch
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type - auto
        self.reactions_table.setColumnWidth(0, 40)  # Star column width
        self.reactions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reactions_table.itemSelectionChanged.connect(self.on_reaction_selected)
        self.reactions_table.cellClicked.connect(self.on_reaction_cell_clicked)
        self.reactions_table.setFont(table_font)
        self.reactions_table.setMinimumHeight(635)
        # noinspection PyUnresolvedReferences
        self.reactions_table.verticalHeader().setDefaultSectionSize(60)
        self.reactions_table.setAlternatingRowColors(True)

        # Enable hover tooltips for reaction details
        self.reactions_table.setMouseTracking(True)
        self.reactions_table.cellEntered.connect(self._on_reaction_hover)

        reactions_layout.addWidget(self.reactions_table)

        # Pagination and action controls combined in one row
        nav_layout = QHBoxLayout()

        # Create font for navigation elements
        nav_font = QFont(FONT, 12)

        # First page button
        self.first_page_btn = QPushButton("«")
        self.first_page_btn.setFixedWidth(45)
        self.first_page_btn.setToolTip("First page")
        self.first_page_btn.setFont(nav_font)
        self.first_page_btn.clicked.connect(self.go_to_first_page)
        self.first_page_btn.setEnabled(False)
        nav_layout.addWidget(self.first_page_btn)

        # Previous page button
        self.prev_page_btn = QPushButton("‹")
        self.prev_page_btn.setFixedWidth(40)
        self.prev_page_btn.setToolTip("Previous page")
        self.prev_page_btn.setFont(nav_font)
        self.prev_page_btn.clicked.connect(self.go_to_prev_page)
        self.prev_page_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_page_btn)

        # Page number entry
        self.page_entry = QLineEdit()
        self.page_entry.setFixedWidth(55)
        self.page_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_entry.setFont(nav_font)
        self.page_entry.setValidator(None)
        self.page_entry.setText("1")
        self.page_entry.returnPressed.connect(self.on_page_entry_changed)
        nav_layout.addWidget(self.page_entry)

        # Total pages label
        self.page_label = QLabel("of 1")
        self.page_label.setFont(nav_font)
        nav_layout.addWidget(self.page_label)

        # Next page button
        self.next_page_btn = QPushButton("›")
        self.next_page_btn.setFixedWidth(40)
        self.next_page_btn.setToolTip("Next page")
        self.next_page_btn.setFont(nav_font)
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        self.next_page_btn.setEnabled(False)
        nav_layout.addWidget(self.next_page_btn)

        # Last page button
        self.last_page_btn = QPushButton("»")
        self.last_page_btn.setFixedWidth(45)
        self.last_page_btn.setToolTip("Last page")
        self.last_page_btn.setFont(nav_font)
        self.last_page_btn.clicked.connect(self.go_to_last_page)
        self.last_page_btn.setEnabled(False)
        nav_layout.addWidget(self.last_page_btn)

        # Cancel Calculation button (only visible during calculation selection mode)
        self.cancel_calc_btn.setFont(nav_font)
        self.cancel_calc_btn.clicked.connect(self.cancel_calculation_selection)
        self.cancel_calc_btn.setVisible(False)  # Hidden by default
        nav_layout.addWidget(self.cancel_calc_btn)

        # Spacer to push action buttons to the right
        nav_layout.addStretch()

        # Action buttons with same font
        self.view_reaction_btn.setFont(nav_font)
        self.view_reaction_btn.clicked.connect(self.view_selected_reaction)
        self.view_reaction_btn.setEnabled(False)
        nav_layout.addWidget(self.view_reaction_btn)

        self.edit_reaction_btn.setFont(nav_font)
        self.edit_reaction_btn.clicked.connect(self.edit_selected_reaction)
        self.edit_reaction_btn.setEnabled(False)
        nav_layout.addWidget(self.edit_reaction_btn)

        self.delete_reaction_btn.setFont(nav_font)
        self.delete_reaction_btn.clicked.connect(self.delete_selected_reaction)
        self.delete_reaction_btn.setEnabled(False)
        nav_layout.addWidget(self.delete_reaction_btn)

        reactions_layout.addLayout(nav_layout)
        self.reactions_group.setLayout(reactions_layout)
        parent_layout.addWidget(self.reactions_group)

    def create_menubar(self):
        """Create menubar with File and Stats menus"""
        menubar = self.menuBar()
        if not menubar:
            return

        # File menu
        file_menu = menubar.addMenu("Reactions")
        if file_menu:
            add_action = QAction("Add Reaction...", self)
            add_action.setShortcut("Ctrl+N")
            add_action.triggered.connect(self.open_reaction_dialog)
            file_menu.addAction(add_action)

            export_action = QAction("Export Reactions...", self)
            export_action.triggered.connect(self.open_export_dialog)
            file_menu.addAction(export_action)

        tools_menu = menubar.addMenu("Tools")
        if not tools_menu:
            return
        stats_action = QAction("Show Statistics", self)
        stats_action.triggered.connect(self.show_stats_dialog)
        tools_menu.addAction(stats_action)

        # Calculate action
        calc_action = QAction("🧮 Calculate", self)
        calc_action.triggered.connect(self.show_calculate_dialog)
        tools_menu.addAction(calc_action)

    def show_stats_dialog(self):
        """Show statistics dialog"""
        if not self.stats_dialog:
            self.stats_dialog = StatsDialog(self.db, self)
            self.stats_dialog.exec()
            # After exec() returns, dialog is closed and stats_dialog is None
            return
        self.stats_dialog.raise_()
        self.stats_dialog.activateWindow()

    def show_calculate_dialog(self):
        """Show calculation dialog"""
        if not self.calculate_dialog:
            self.calculate_dialog = CalculateDialog(self.db, self)
        self.calculate_dialog.show()
        self.calculate_dialog.raise_()
        self.calculate_dialog.activateWindow()

    def open_reaction_dialog(self, reaction_id=None):
        """Open the reaction dialog for adding or editing a reaction"""
        try:
            dialog = ReactionDialog(self.db, reaction_id, self)
            dialog.reaction_saved.connect(self.on_dialog_reaction_saved)
            dialog.exec()
        except Exception as e:
            logging.error(f"Failed to open reaction dialog: {e}")
            self.toast.error(f"Failed to open reaction dialog: {e}")

    def on_dialog_reaction_saved(self, success, message, reaction_id):
        """Handle reaction saved signal from dialog"""
        logging.info(f"[MainWindow] on_dialog_reaction_saved called: success={success}, reaction_id={reaction_id}")
        try:
            if success:
                self.toast.info("Reaction saved successfully!")
                # Set target to jump to the saved reaction's page
                if reaction_id:
                    self._target_reaction_id = reaction_id
                self.load_data()  # Refresh main table
                self.update_filter_menu()  # Refresh filter menu with new reaction types
                if getattr(self, 'stats_dialog', None) and self.stats_dialog.isVisible():
                    self.stats_dialog.refresh()
                logging.info("[MainWindow] Save handling completed successfully")
            else:
                self.toast.error(f"Failed to save: {message}")
        except Exception as e:
            logging.error(f"[MainWindow] Error handling saved reaction: {e}", exc_info=True)
            self.toast.error(f"Error after save: {e}")

    def open_export_dialog(self):
        """Open the export dialog for exporting reactions"""
        # Get unique reaction types from database
        all_reactions = self.db.get_all_reactions()
        unique_types = sorted(set(
            r.get('reaction_type', 'Unknown')
            for r in all_reactions
            if r.get('reaction_type')
        ))

        if not unique_types:
            QMessageBox.warning(self, "No Reaction Types", "No reaction types found to export.")
            return

        # Create and show export dialog
        dialog = ExportDialog(self, self.db, unique_types)
        dialog.exec()

    def on_reaction_key_press(self, event):
        """Handle key press events for subscript conversion and bracket auto-complete"""
        key = event.key()
        cursor = self.search_entry.cursorPosition()
        text = self.search_entry.text()
        selected = self.search_entry.selectedText()

        # Handle bracket auto-complete for opening brackets
        if key == Qt.Key.Key_ParenLeft:  # (
            if selected:
                start = cursor - len(selected)
                self.search_entry.deselect()
                new_text = text[:start] + "(" + selected + ")" + text[cursor:]
                self.search_entry.setText(new_text)
                self.search_entry.setSelection(start + 1, len(selected))
            else:
                # Auto-complete with ) and place cursor inside
                new_text = text[:cursor] + "()" + text[cursor:]
                self.search_entry.setText(new_text)
                self.search_entry.setCursorPosition(cursor + 1)
            return

        if key == Qt.Key.Key_BracketLeft:  # [
            if selected:
                # Wrap selected text with brackets - deselect first to avoid duplication
                start = cursor - len(selected)
                self.search_entry.deselect()
                new_text = text[:start] + "[" + selected + "]" + text[cursor:]
                self.search_entry.setText(new_text)
                self.search_entry.setSelection(start + 1, len(selected))
            else:
                # Auto-complete with ] and place cursor inside
                new_text = text[:cursor] + "[]" + text[cursor:]
                self.search_entry.setText(new_text)
                self.search_entry.setCursorPosition(cursor + 1)
            return

        # Check if a digit key (0-9) is pressed
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            # Check if the character before cursor is a letter, subscript digit, or closing bracket
            if cursor > 0:
                prev_char = text[cursor - 1]
                subscript_values = set(SUBSCRIPT_DIGITS.values())
                # Convert to subscript if after: letter, subscript digit, or closing bracket ) or ]
                if prev_char.isalpha() or prev_char in subscript_values or prev_char in ')]':
                    digit = str(key - Qt.Key.Key_0)
                    subscript_digit = SUBSCRIPT_DIGITS.get(digit)
                    new_text = text[:cursor] + subscript_digit + text[cursor:]
                    self.search_entry.setText(new_text)
                    self.search_entry.setCursorPosition(cursor + 1)
                    return  # Don't process the event further

        # Call original key press event for other keys
        QLineEdit.keyPressEvent(self.search_entry, event)

    def update_filter_menu(self):
        """Populate filter menu with reaction types from database"""
        try:
            self.filter_menu.clear()
            self.filter_menu.addAction("All Types", lambda: self._safe_apply_filter("All"))
            self.filter_menu.addAction("★ Favorites", lambda: self._safe_apply_filter("Favorites"))
            self.filter_menu.addSeparator()

            # Get reaction types directly from database
            all_types = self.db.get_all_reaction_types()
            for rtype in sorted(all_types):
                if rtype:
                    try:
                        action = self.filter_menu.addAction(rtype)
                        if action:
                            action.triggered.connect(lambda checked=False, t=rtype: self._safe_apply_filter(t))
                    except Exception as e:
                        logging.error(f"Failed to add filter action for {rtype}: {e}")
        except Exception as e:
            logging.error(f"Failed to update filter menu: {e}")

    def _safe_apply_filter(self, reaction_type):
        """Safely apply type filter with error handling"""
        try:
            self.apply_type_filter(reaction_type)
        except Exception as e:
            logging.error(f"Failed to apply type filter '{reaction_type}': {e}")

    def view_selected_reaction(self):
        """View the selected reaction in an overlay widget"""
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            # Column 0 is star, column 1 is reaction text, column 2 is type
            reaction_item = self.reactions_table.item(selected_row, 1)
            type_item = self.reactions_table.item(selected_row, 2)
            if not reaction_item or not type_item:
                return
            reaction_id = reaction_item.data(Qt.ItemDataRole.UserRole)
            reaction_text = reaction_item.text()
            reaction_type = type_item.text()

            # Fetch heat data from database
            heat_data = self.db.get_reaction_heat_data(reaction_id)
            heat_value = heat_data.get('heat_value')
            heat_type = heat_data.get('heat_type')
            logging.info(f"[ViewMode] Fetched heat_data: {heat_data}, heat_value={heat_value}, heat_type={heat_type}")

            # Store the viewing state
            self.viewing_reaction_id = reaction_id

            # Create and show the view overlay
            self.create_view_overlay(reaction_id, reaction_text, reaction_type, heat_value, heat_type)

    def edit_selected_reaction(self):
        """Open dialog to edit selected reaction"""
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            reaction_item = self.reactions_table.item(selected_row, 1)
            if not reaction_item:
                return
            reaction_id = reaction_item.data(Qt.ItemDataRole.UserRole)

            self.close_view_overlay()
            # Show toast notification
            self.toast.info("Edit mode - make changes and click Update")
            self.open_reaction_dialog(reaction_id)

    def on_reaction_cell_clicked(self, row, column):
        """Handle cell click in reactions table - toggle favorite on star column"""
        if column == 0:  # Star column
            star_item = self.reactions_table.item(row, 0)
            if not star_item:
                return
            
            reaction_id = star_item.data(Qt.ItemDataRole.UserRole)
            if not reaction_id:
                return
            
            # Toggle favorite status
            new_status = self.db.toggle_reaction_favorite(reaction_id)
            
            # Update the star display
            star_text = "★" if new_status else "☆"
            star_item.setText(star_text)
            
            # Update color
            if new_status:
                star_item.setForeground(QColor("#FFD700"))  # Gold
                self.toast.success("Reaction starred!")
            else:
                star_item.setForeground(QColor("#888888"))  # Gray
                self.toast.info("Reaction unstarred")
            
            # Set target reaction so we jump to its new page after reload
            self._target_reaction_id = reaction_id
            # Reload data to resort (favorites go to top)
            QTimer.singleShot(300, self.load_data)

    def _on_reaction_hover(self, row, column):
        """Show rich tooltip with reaction details on hover"""
        try:
            star_item = self.reactions_table.item(row, 0)
            if not star_item:
                return

            reaction_id = star_item.data(Qt.ItemDataRole.UserRole)
            if not reaction_id:
                return

            # Fetch reaction details from database
            reaction = self.db.get_reaction_by_id(reaction_id)
            if not reaction:
                return

            # Build rich HTML tooltip
            reaction_text = reaction.get('reaction_text', '')
            reaction_type = reaction.get('reaction_type', 'Unknown')
            heat_value = reaction.get('heat_value', '')
            heat_type = reaction.get('heat_type', '')

            # Convert arrows to standard Unicode arrows
            display_text = reaction_text
            for ascii_arrow, unicode_arrow in ARROW_MAP.items():
                display_text = display_text.replace(ascii_arrow, unicode_arrow)

            # Calculate dynamic width based on character count (avg 9px per char at 16px font)
            text_length = len(display_text)
            char_width = 9  # Average pixels per character
            padding = 40  # Left/right padding total
            calculated_width = (text_length * char_width) + padding

            # Clamp between reasonable bounds
            tooltip_width = max(200, min(900, calculated_width))
            font_size = "16px"

            # Format heat info (using br for spacing to work in table)
            heat_info = ""
            if heat_value and heat_type:
                heat_emoji = "🔥" if heat_type.lower() == 'exothermic' else "❄️"
                heat_info = f"<br><b>ΔH:</b> {heat_value} kJ/mol ({heat_emoji} {heat_type.capitalize()})"
            elif heat_type:
                heat_emoji = "🔥" if heat_type.lower() == 'exothermic' else "❄️"
                heat_info = f"<br><b>Type:</b> {heat_emoji} {heat_type.capitalize()}"

            # Build tooltip HTML with gray background
            tooltip_html = f"""
            <table cellpadding="10" cellspacing="0" width="{tooltip_width}" style="background-color: #3C3C3C;">
                <tr>
                    <td width="{tooltip_width}" style="background-color: #3C3C3C; color: #4CAF50; font-size: {font_size}; font-weight: bold; line-height: 1.5; padding-bottom: 8px;">
                        {display_text}
                    </td>
                </tr>
                <tr>
                    <td width="{tooltip_width}" style="background-color: #3C3C3C; color: #dddddd; font-size: 12px; padding-top: 6px;">
                        <b style="color: #ffffff;">Type:</b> {reaction_type}{heat_info}
                    </td>
                </tr>
            </table>
            """

            # Set tooltip on the item being hovered
            item = self.reactions_table.item(row, column)
            if item:
                item.setToolTip(tooltip_html)

        except Exception as e:
            logging.error(f"Error showing reaction hover tooltip: {e}")

    def delete_selected_reaction(self):
        """Delete the selected reaction"""
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            # Column 0 is star (has ID), column 1 is reaction text
            star_item = self.reactions_table.item(selected_row, 0)
            reaction_item = self.reactions_table.item(selected_row, 1)
            if not star_item or not reaction_item:
                return
            reaction_id = star_item.data(Qt.ItemDataRole.UserRole)
            reaction_text = reaction_item.text()

            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete this reaction?\n\n{reaction_text}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.db.delete_reaction(reaction_id)
                    # Clear all tables and reload
                    self.close_view_overlay()
                    self.load_data()
                    self.toast.success("Reaction deleted successfully!")
                except Exception as e:
                    logging.error(f"Failed to delete reaction: {e}")
                    self.toast.error(f"Failed to delete reaction: {e}")

    def on_reaction_selected(self):
        """Handle reaction selection and enable/disable action buttons"""
        selected_items = self.reactions_table.selectedItems()
        has_selection = len(selected_items) > 0

        # If in calculation selection mode, handle selection differently
        if self.in_calculation_selection_mode and has_selection:
            # Get the selected reaction data
            selected_row = selected_items[0].row()
            # Column 0 is star (has ID), column 1 is reaction text
            star_item = self.reactions_table.item(selected_row, 0)

            if star_item:
                reaction_id = star_item.data(Qt.ItemDataRole.UserRole)

                # Find the full reaction data from all_reactions
                reaction_data = None
                for reaction in self.all_reactions:
                    if reaction['id'] == reaction_id:
                        reaction_data = reaction
                        break

                if reaction_data and self.calculate_dialog:
                    # Disable selection mode
                    self.disable_reaction_selection_mode()
                    # Notify the dialog
                    self.calculate_dialog.on_reaction_selected(reaction_data)
            return

        # Normal mode: Enable/disable action buttons based on selection
        self.view_reaction_btn.setEnabled(has_selection)
        self.edit_reaction_btn.setEnabled(has_selection)
        self.delete_reaction_btn.setEnabled(has_selection)

    def on_search_text_changed(self, _text):
        """Handle search text changes"""
        self.current_page = 1
        self.apply_filter_and_pagination()

    def clear_search(self):
        """Clear search field"""
        self.search_entry.clear()
        self._safe_apply_filter("All")
        self.current_page = 1
        self.apply_filter_and_pagination()
        self.toast.info("Search cleared")

    def go_to_prev_page(self):
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.apply_filter_and_pagination()

    def go_to_next_page(self):
        """Go to next page"""
        total_pages = self.get_total_pages()
        if self.current_page < total_pages:
            self.current_page += 1
            self.apply_filter_and_pagination()

    def get_total_pages(self):
        """Calculate total number of pages"""
        items_to_show = self.filtered_reactions if self.filtered_reactions else self.all_reactions
        return max(1, (len(items_to_show) + self.items_per_page - 1) // self.items_per_page)

    def apply_type_filter(self, reaction_type):
        """Apply filter by reaction type"""
        try:
            self.current_type_filter = reaction_type
            self.current_page = 1
            self.apply_filter_and_pagination()
            # Show toast for filter applied
            if reaction_type == "All":
                self.toast.info("Filter cleared - showing all reactions")
            elif reaction_type == "Favorites":
                self.toast.info("Filter applied: Favorites only")
            else:
                self.toast.info(f"Filter applied: {reaction_type}")
        except Exception as e:
            logging.error(f"Error in apply_type_filter: {e}")
            self.toast.error(f"Failed to apply filter: {e}")

    def set_type_filter(self, reaction_type):
        """Public method to set type filter from external dialogs (e.g., StatsDialog)"""
        self.apply_type_filter(reaction_type)

    def apply_filter_and_pagination(self):
        """Apply search filter, type filter, and pagination to reactions"""
        search_text = self.search_entry.text().lower()

        # Start with all reactions
        filtered = self.all_reactions[:]

        # Apply type filter if not "All"
        if self.current_type_filter == "Favorites":
            filtered = [
                r for r in filtered
                if r.get('is_favorite', 0)
            ]
        elif self.current_type_filter != "All":
            filtered = [
                r for r in filtered
                if r.get('reaction_type', '').lower() == self.current_type_filter.lower()
            ]

        # Apply search filter
        if search_text:
            filtered = [
                r for r in filtered
                if search_text in r['reaction_text'].lower() or
                   search_text in r.get('reaction_type', '').lower()
            ]

        self.filtered_reactions = filtered

        total_pages = self.get_total_pages()

        # Ensure current page is valid
        if self.current_page > total_pages:
            self.current_page = total_pages
        if self.current_page < 1:
            self.current_page = 1

        # Get items for current page
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.filtered_reactions[start_idx:end_idx]

        # Update table
        self.reactions_table.setRowCount(len(page_items))
        for row, reaction in enumerate(page_items):
            # Star/favorite column (column 0)
            is_fav = reaction.get('is_favorite', 0)
            star_text = "★" if is_fav else "☆"
            star_item = QTableWidgetItem(star_text)
            star_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)  # Clickable but not editable
            star_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            star_item.setData(Qt.ItemDataRole.UserRole, reaction['id'])  # Store ID for click handling
            # Set color for favorite (gold for starred, gray for not)
            if is_fav:
                star_item.setForeground(QColor("#FFD700"))  # Gold color
            else:
                star_item.setForeground(QColor("#888888"))  # Gray color
            self.reactions_table.setItem(row, 0, star_item)

            # Reaction text - convert keyboard arrows to Unicode (column 1)
            reaction_item = QTableWidgetItem(ChemLabParser.convert_arrows_to_unicode(reaction['reaction_text']))
            reaction_item.setFlags(reaction_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            reaction_item.setData(Qt.ItemDataRole.UserRole, reaction['id'])  # Store ID
            self.reactions_table.setItem(row, 1, reaction_item)

            # Reaction type (column 2)
            type_item = QTableWidgetItem(reaction.get('reaction_type', 'Unknown'))
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.reactions_table.setItem(row, 2, type_item)

        # Update pagination controls
        self.page_entry.setText(str(self.current_page))
        self.page_label.setText(f"of {total_pages}")
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)

        # Update page entry validator
        self.page_entry.setValidator(QIntValidator(1, max(1, total_pages), self))

    def go_to_first_page(self):
        """Go to first page"""
        self.current_page = 1
        self.apply_filter_and_pagination()

    def go_to_last_page(self):
        """Go to last page"""
        self.current_page = self.get_total_pages()
        self.apply_filter_and_pagination()

    def on_page_entry_changed(self):
        """Handle page number entry"""
        try:
            page_text = self.page_entry.text().strip()
            if not page_text:
                return

            # Convert to integer (rounds decimals to nearest integer)
            page = int(float(page_text))
            total_pages = self.get_total_pages()

            # Validate range
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            self.current_page = page
            self.apply_filter_and_pagination()
        except ValueError:
            # Reset to current page if invalid input
            self.page_entry.setText(str(self.current_page))

    def load_data(self):
        """Load all data from database with pagination"""
        try:
            # Load all reactions
            self.all_reactions = self.db.get_all_reactions()
            
            # If we have a target reaction, find which page it's on
            if self._target_reaction_id is not None:
                self._jump_to_reaction_page(self._target_reaction_id)
                self._target_reaction_id = None  # Clear after using
            else:
                self.current_page = 1
            
            self.apply_filter_and_pagination()
            self.update_filter_menu()
        except Exception as e:
            logging.error(f"Failed to load data: {e}")

    def _jump_to_reaction_page(self, reaction_id):
        """Calculate and set the page containing the given reaction ID"""
        # Find the index of the reaction in all_reactions
        for idx, reaction in enumerate(self.all_reactions):
            if reaction['id'] == reaction_id:
                # Calculate page number (1-indexed)
                page = (idx // self.items_per_page) + 1
                self.current_page = page
                return
        # If not found, stay on current page or go to page 1
        if self.current_page < 1:
            self.current_page = 1

    def closeEvent(self, event):
        """Handle application close"""
        try:
            self.db.close()
            if self.view_overlay:
                self.view_overlay.close()
        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")

        event.accept()

    def create_view_overlay(self, reaction_id, reaction_text, reaction_type, heat_value=None, heat_type=None):
        """Create and show the view overlay widget that covers the entire central widget"""
        # Close existing overlay if any
        self.close_view_overlay()

        # Create overlay widget as child of central widget
        self.view_overlay = QFrame(self.central_widget)
        self.view_overlay.setObjectName("viewOverlay")

        # Set style to black background with white text for contrast
        self.view_overlay.setStyleSheet("""
            QFrame#viewOverlay {
                background-color: #1a1a1a;
                border: none;
            }
            QFrame#viewOverlay QLabel {
                color: #ffffff;
            }
            QFrame#viewOverlay QGroupBox {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
                font-weight: bold;
            }
            QFrame#viewOverlay QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #ffffff;
            }
            QFrame#viewOverlay QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                gridline-color: #444444;
                border: 1px solid #444444;
            }
            QFrame#viewOverlay QTableWidget::item {
                padding: 5px;
                color: #ffffff;
            }
            QFrame#viewOverlay QTableWidget::item:alternate {
                background-color: #353535;
            }
            QFrame#viewOverlay QTableWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QFrame#viewOverlay QHeaderView::section {
                background-color: #3d3d3d;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #444444;
                font-weight: bold;
            }
        """)

        # Make overlay fill the entire central widget
        self.view_overlay.setGeometry(self.central_widget.rect())

        # Main layout for overlay
        overlay_layout = QVBoxLayout(self.view_overlay)
        overlay_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Viewing Reaction")
        title.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #ffffff; padding: 10px;")
        overlay_layout.addWidget(title)

        # Reaction info section
        info_group = QGroupBox("Reaction Information")
        info_layout = QGridLayout()
        info_layout.setSpacing(10)

        reaction_label = QLabel(f"<b>Reaction:</b> {ChemLabParser.convert_arrows_to_unicode(reaction_text)}")
        reaction_label.setWordWrap(True)
        reaction_label.setFont(QFont(FONT, 12))
        reaction_label.setStyleSheet(COLOR_STYLE)
        reaction_label.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(reaction_label, 0, 0, 1, 2)

        type_label = QLabel(f"<b>Type:</b> {reaction_type}")
        type_label.setFont(QFont(FONT, 11))
        type_label.setStyleSheet(COLOR_STYLE)
        info_layout.addWidget(type_label, 1, 0)

        # Display heat information if available (from database fields)
        logging.info(f"[ViewMode] heat_value={heat_value}, heat_type={heat_type}")
        if heat_value is not None or heat_type:
            if heat_type == 'exothermic':
                heat_display = f"ΔH = -{abs(heat_value) if heat_value else '?'} kJ/mol"
                heat_color = "#ff6b6b"  # Red for exothermic
            elif heat_type == 'endothermic':
                heat_display = f"ΔH = +{heat_value if heat_value else '?'} kJ/mol"
                heat_color = "#4dabf7"  # Blue for endothermic
            else:
                # Just value, no type specified
                sign = "+" if heat_value and heat_value > 0 else ""
                heat_display = f"ΔH = {sign}{heat_value if heat_value else '?'} kJ/mol"
                heat_color = "#ffd43b"  # Yellow

            logging.info(f"[ViewMode] Displaying: {heat_display}")
            heat_label = QLabel(heat_display)
            heat_label.setFont(QFont(FONT, 11))
            heat_label.setStyleSheet(f"color: {heat_color}; font-weight: bold;")
            info_layout.addWidget(heat_label, 1, 1)

        info_group.setLayout(info_layout)
        overlay_layout.addWidget(info_group)

        # Tables section - takes most of the space
        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(15)

        # Elements table
        elements_group = QGroupBox("Elements")
        elements_layout = QVBoxLayout()
        elements_layout.setContentsMargins(5, 5, 5, 5)
        elements_table = QTableWidget()
        elements_table.setColumnCount(3)
        elements_table.setHorizontalHeaderLabels(ELEMENTS_COLUMNS)
        header = elements_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        elements_table.setAlternatingRowColors(True)
        elements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        elements_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        elements_layout.addWidget(elements_table)
        elements_group.setLayout(elements_layout)
        tables_layout.addWidget(elements_group, 1)

        # Compounds table
        compounds_group = QGroupBox("Compounds")
        compounds_layout = QVBoxLayout()
        compounds_layout.setContentsMargins(5, 5, 5, 5)
        compounds_table = QTableWidget()
        compounds_table.setColumnCount(6)
        compounds_table.setHorizontalHeaderLabels(COMPOUNDS_COLUMNS)
        header = compounds_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        compounds_table.setAlternatingRowColors(True)
        compounds_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        compounds_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        compounds_layout.addWidget(compounds_table)
        compounds_group.setLayout(compounds_layout)
        tables_layout.addWidget(compounds_group, 2)

        overlay_layout.addLayout(tables_layout, 1)  # Stretch factor 1 to take available space

        # Back button
        back_layout = QHBoxLayout()
        back_layout.addStretch()
        back_btn = QPushButton("← Back")
        back_btn.setMinimumHeight(45)
        back_btn.setMinimumWidth(150)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        back_btn.clicked.connect(self.on_view_back_clicked)
        back_layout.addWidget(back_btn)
        overlay_layout.addLayout(back_layout)

        # Load data into overlay tables
        self.load_overlay_data(reaction_id, elements_table, compounds_table)

        # Connect compound click handler
        compounds_table.cellClicked.connect(lambda row, col: self.on_compound_clicked(row, compounds_table))

        # Show overlay
        self.view_overlay.raise_()
        self.view_overlay.show()

        # Install event filter on central widget to handle resizing
        self.central_widget.installEventFilter(self)

    def load_overlay_data(self, reaction_id, elements_table, compounds_table):
        """Load data into overlay tables"""
        try:
            # Get compounds for this reaction
            compounds = self.db.get_compounds_for_reaction(reaction_id)

            # Populate compounds table
            compounds_table.setRowCount(len(compounds))
            reaction_elements = set()

            for row, compound in enumerate(compounds):
                # Formula - display with subscripts
                formula_item = QTableWidgetItem(ChemLabParser.display_formula(compound['formula']))
                compounds_table.setItem(row, 0, formula_item)

                # Type
                type_item = QTableWidgetItem(compound['type'])
                compounds_table.setItem(row, 1, type_item)

                # Name
                name_item = QTableWidgetItem(compound.get('name') or '')
                compounds_table.setItem(row, 2, name_item)

                # Color
                color_item = QTableWidgetItem(compound.get('color') or DEFAULT_COLOR)
                compounds_table.setItem(row, 3, color_item)

                # State - convert to full name
                state_value = compound.get('state') or ''
                if state_value and state_value in STATE_NAMES:
                    state_value = STATE_NAMES[state_value]
                state_item = QTableWidgetItem(state_value)
                compounds_table.setItem(row, 4, state_item)

                # Notes
                notes_item = QTableWidgetItem(compound.get('notes') or '')
                compounds_table.setItem(row, 5, notes_item)

                # Extract elements from formula
                matches = re.findall(r'[A-Z][a-z]?', compound['formula'])
                for match in matches:
                    reaction_elements.add(match)

            # Populate elements table
            elements_table.setRowCount(len(reaction_elements))
            for row, elem_symbol in enumerate(sorted(reaction_elements)):
                try:
                    elem = element(elem_symbol)
                    elements_table.setItem(row, 0, QTableWidgetItem(elem_symbol))
                    elements_table.setItem(row, 1, QTableWidgetItem(elem.name))
                    elements_table.setItem(row, 2, QTableWidgetItem(str(elem.atomic_number)))
                except (ValueError, KeyError):
                    elements_table.setItem(row, 0, QTableWidgetItem(elem_symbol))
                    elements_table.setItem(row, 1, QTableWidgetItem('Unknown'))
                    elements_table.setItem(row, 2, QTableWidgetItem('0'))

        except Exception as e:
            logging.error(f"Failed to load overlay data: {e}")

    def close_view_overlay(self):
        """Close the view overlay and reset viewing state"""
        if self.view_overlay:
            self.view_overlay.close()
            self.view_overlay.deleteLater()
            self.view_overlay = None
        self.viewing_reaction_id = None
        # Remove event filter when overlay is closed
        if self.central_widget:
            self.central_widget.removeEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle resize events to keep overlays filling the central widget"""
        if obj == self.central_widget and event.type() == event.Type.Resize:
            if self.view_overlay:
                self.view_overlay.setGeometry(self.central_widget.rect())
            if self.compound_overlay:
                self.compound_overlay.setGeometry(self.central_widget.rect())
        return super().eventFilter(obj, event)

    def on_compound_clicked(self, row, compounds_table):
        """Handle compound click in view overlay - show compound stats"""
        try:
            # Get compound data from the clicked row
            formula_item = compounds_table.item(row, 0)
            if not formula_item:
                return
            formula_text = formula_item.text()
            # Convert displayed formula back to plain text for parsing
            formula = ChemLabParser.normalize_formula(formula_text)

            type_item = compounds_table.item(row, 1)
            name_item = compounds_table.item(row, 2)
            color_item = compounds_table.item(row, 3)
            state_item = compounds_table.item(row, 4)
            notes_item = compounds_table.item(row, 5)

            compound_type = type_item.text() if type_item else ''
            compound_name = name_item.text() if name_item else ''
            compound_color = color_item.text() if color_item else DEFAULT_COLOR
            compound_state = state_item.text() if state_item else ''
            compound_notes = notes_item.text() if notes_item else ''

            # Convert state display name back to abbreviation if needed
            for abbrev, full_name in STATE_NAMES.items():
                if full_name == compound_state:
                    compound_state = abbrev
                    break

            # Show compound stats overlay
            self.create_compound_overlay(formula, compound_name, compound_type,
                                         compound_color, compound_state, compound_notes)

        except Exception as e:
            logging.error(f"Error handling compound click: {e}")

    def on_view_back_clicked(self):
        """Handle back button click in view mode"""
        self.close_view_overlay()
        self.reactions_table.clearSelection()
        self.view_reaction_btn.setEnabled(False)
        self.edit_reaction_btn.setEnabled(False)
        self.delete_reaction_btn.setEnabled(False)

    def create_compound_overlay(self, formula, compound_name, compound_type, compound_color, compound_state,
                                compound_notes):
        """Create and show compound stats overlay"""
        self.close_compound_overlay()
        self.compound_overlay_parent = 'view'

        self.compound_overlay = QFrame(self.central_widget)
        self.compound_overlay.setObjectName("compoundOverlay")
        self._apply_compound_overlay_styles()
        self.compound_overlay.setGeometry(self.central_widget.rect())

        overlay_layout = QVBoxLayout(self.compound_overlay)
        overlay_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel(f"Compound Statistics: {ChemLabParser.display_formula(formula)}")
        title.setFont(QFont(FONT, 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #ffffff; padding: 15px;")
        overlay_layout.addWidget(title)

        info_group = self._create_basic_info_group(formula, compound_name, compound_type, compound_color,
                                                   compound_state, compound_notes)
        overlay_layout.addWidget(info_group)

        self._add_molar_mass_section(overlay_layout, formula)
        self._add_back_button(overlay_layout)

        self.compound_overlay.raise_()
        self.compound_overlay.show()

        # Install event filter on central widget to handle resizing
        self.central_widget.installEventFilter(self)

    def _apply_compound_overlay_styles(self):
        """Apply stylesheet to compound overlay"""
        self.compound_overlay.setStyleSheet("""
            QFrame#compoundOverlay {
                background-color: #1a1a1a;
                border: none;
            }
            QFrame#compoundOverlay QLabel {
                color: #ffffff;
            }
            QFrame#compoundOverlay QGroupBox {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
                font-weight: bold;
            }
            QFrame#compoundOverlay QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #ffffff;
            }
            QFrame#compoundOverlay QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                gridline-color: #444444;
                border: 1px solid #444444;
            }
            QFrame#compoundOverlay QTableWidget::item {
                padding: 5px;
                color: #ffffff;
            }
            QFrame#compoundOverlay QTableWidget::item:alternate {
                background-color: #353535;
            }
            QFrame#compoundOverlay QHeaderView::section {
                background-color: #3d3d3d;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #444444;
                font-weight: bold;
            }
            QFrame#compoundOverlay QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QFrame#compoundOverlay QPushButton:hover {
                background-color: #106ebe;
            }
        """)

    @staticmethod
    def _create_basic_info_group(formula, compound_name, compound_type, compound_color, compound_state, compound_notes):
        """Create basic information group box"""
        info_group = QGroupBox("Basic Information")
        info_layout = QGridLayout()
        info_layout.setSpacing(10)

        formula_label = QLabel(f"<b>Formula:</b> {ChemLabParser.display_formula(formula)}")
        formula_label.setFont(QFont(FONT, 12))
        formula_label.setStyleSheet(COLOR_STYLE)
        info_layout.addWidget(formula_label, 0, 0)

        type_label = QLabel(f"<b>Type:</b> {compound_type}")
        type_label.setFont(QFont(FONT, 12))
        type_label.setStyleSheet(COLOR_STYLE)
        info_layout.addWidget(type_label, 0, 1)

        name_label = QLabel(f"<b>Name:</b> {compound_name or 'Not specified'}")
        name_label.setFont(QFont(FONT, 12))
        name_label.setStyleSheet(COLOR_STYLE)
        info_layout.addWidget(name_label, 1, 0)

        color_label = QLabel(f"<b>Color:</b> {compound_color or DEFAULT_COLOR}")
        color_label.setFont(QFont(FONT, 12))
        color_label.setStyleSheet(COLOR_STYLE)
        info_layout.addWidget(color_label, 1, 1)

        state_display = STATE_NAMES.get(compound_state, compound_state) or 'Not specified'
        state_label = QLabel(f"<b>State:</b> {state_display}")
        state_label.setFont(QFont(FONT, 12))
        state_label.setStyleSheet(COLOR_STYLE)
        info_layout.addWidget(state_label, 2, 0)

        if compound_notes:
            notes_label = QLabel(f"<b>Notes:</b> {compound_notes}")
            notes_label.setFont(QFont(FONT, 11))
            notes_label.setStyleSheet(COLOR_STYLE)
            notes_label.setWordWrap(True)
            info_layout.addWidget(notes_label, 3, 0, 1, 2)

        info_group.setLayout(info_layout)
        return info_group

    def _add_molar_mass_section(self, overlay_layout, formula):
        """Add molar mass and composition section to overlay"""
        molar_mass = ChemLabParser.calculate_molar_mass(formula)
        composition, _ = ChemLabParser.calculate_elemental_composition(formula)

        if not molar_mass:
            error_label = QLabel("Could not calculate molar mass. Invalid formula or unknown elements.")
            error_label.setStyleSheet("color: #ff6b6b; padding: 20px;")
            overlay_layout.addWidget(error_label)
            return

        mass_group = QGroupBox("Molar Mass")
        mass_layout = QVBoxLayout()

        mass_label = QLabel(f"<b>{molar_mass} g/mol</b>")
        mass_label.setFont(QFont(FONT, 14))
        mass_label.setStyleSheet("color: #00d4aa;")
        mass_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mass_layout.addWidget(mass_label)

        mass_group.setLayout(mass_layout)
        overlay_layout.addWidget(mass_group)

        if composition:
            self._add_composition_table(overlay_layout, composition)

    @staticmethod
    def _add_composition_table(overlay_layout, composition):
        """Add elemental composition table to overlay"""
        comp_group = QGroupBox("Elemental Composition")
        comp_layout = QVBoxLayout()

        comp_table = QTableWidget()
        comp_table.setColumnCount(4)
        comp_table.setHorizontalHeaderLabels(["Element", "Count", "Mass (g/mol)", "% by Mass"])
        header = comp_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        comp_table.setAlternatingRowColors(True)
        comp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        comp_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        comp_table.setRowCount(len(composition))
        for row, (elem, data) in enumerate(sorted(composition.items())):
            comp_table.setItem(row, 0, QTableWidgetItem(elem))
            comp_table.setItem(row, 1, QTableWidgetItem(str(data['count'])))
            comp_table.setItem(row, 2, QTableWidgetItem(str(data['mass'])))
            comp_table.setItem(row, 3, QTableWidgetItem(f"{data['percentage']}%"))

        comp_layout.addWidget(comp_table)
        comp_group.setLayout(comp_layout)
        overlay_layout.addWidget(comp_group, 1)

    def _add_back_button(self, overlay_layout):
        """Add back button to overlay layout"""
        back_layout = QHBoxLayout()
        back_layout.addStretch()
        back_btn = QPushButton("← Back")
        back_btn.setMinimumHeight(45)
        back_btn.setMinimumWidth(150)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        back_btn.clicked.connect(self.on_compound_back_clicked)
        back_layout.addWidget(back_btn)
        overlay_layout.addLayout(back_layout)

    def close_compound_overlay(self):
        """Close compound overlay"""
        if self.compound_overlay:
            self.compound_overlay.close()
            self.compound_overlay.deleteLater()
            self.compound_overlay = None
        self.compound_overlay_parent = None
        # Only remove event filter if view overlay is also closed
        if not self.view_overlay and self.central_widget:
            self.central_widget.removeEventFilter(self)

    def on_compound_back_clicked(self):
        """Handle back button in compound overlay"""
        self.close_compound_overlay()
        # If we came from view overlay, it should still be visible underneath
        # Just make sure it gets focus again
        if self.view_overlay:
            self.view_overlay.raise_()
            self.view_overlay.setFocus()

    def enable_reaction_selection_mode(self, calculate_dialog):
        """Enable reaction selection mode for calculation dialog"""
        self.in_calculation_selection_mode = True
        self.calculate_dialog = calculate_dialog

        # Show the cancel calculation button
        self.cancel_calc_btn.setVisible(True)

        # Disable View, Edit, Delete buttons
        self.view_reaction_btn.setEnabled(False)
        self.edit_reaction_btn.setEnabled(False)
        self.delete_reaction_btn.setEnabled(False)

        # Keep pagination and search enabled
        # (first_page_btn, prev_page_btn, page_entry, next_page_btn, last_page_btn, search_entry, clear_search_btn, filter_btn)

        # Highlight the Reaction Entry group to indicate selection mode
        self.reactions_group.setStyleSheet("""
            QGroupBox {
                border: 3px solid #0078d4;
                border-radius: 5px;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #0078d4;
            }
        """)

        # Clear any existing selection
        self.reactions_table.clearSelection()

    def disable_reaction_selection_mode(self):
        """Disable reaction selection mode and restore normal UI"""
        self.in_calculation_selection_mode = False

        # Hide the cancel calculation button
        self.cancel_calc_btn.setVisible(False)

        # Restore table selection behavior - selection will enable View/Edit/Delete if appropriate
        self.on_reaction_selected()

        # Restore normal styling on reaction group
        self.reactions_group.setStyleSheet("")

    def cancel_calculation_selection(self):
        """Handle cancel button click during calculation selection mode"""
        self.disable_reaction_selection_mode()

        # Notify the calculate dialog that selection was canceled
        if self.calculate_dialog:
            self.calculate_dialog.on_selection_cancelled()


def main():
    app = QApplication(sys.argv)
    window = ChemLab()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
