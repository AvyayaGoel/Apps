import sys
import re
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QLineEdit, QPushButton, QLabel, QSplitter,
                             QGroupBox, QHeaderView, QMessageBox, QComboBox,
                             QFrame, QGridLayout, QMenu)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from mendeleev import element
# Import separated modules
from constants import (ARROWS, COMMON_REACTION_TYPES, DEFAULT_COLOR, REACTIONS_COLUMNS, SUBSCRIPT_MAP,
                      COMPOUNDS_COLUMNS, ELEMENTS_COLUMNS, SUBSCRIPT_DIGITS, STATE_NAMES, STATE_ABBREVIATIONS,
                      ARROW_MAP, SUBSCRIPT_DISPLAY_MAP, STATE_SYMBOL_PATTERN, ADD_REACTION_BTN_TEXT)
from chemlab_parser import ChemLabParser
from chemlab_database import ChemLabDatabase
from ChemicalKeyboard import ChemicalKeyboard
from compound_learner import CompoundLearner

logging.basicConfig(
    filename="chemlab_errors.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class SaveReactionWorker(QThread):
    """Worker thread for balancing and saving reactions to prevent UI lag"""
    finished = pyqtSignal(bool, str, int)  # success, error_message, reaction_id
    progress = pyqtSignal(str)  # status message
    balanced_reaction = pyqtSignal(str)  # balanced reaction string
    
    def __init__(self, db, reaction, reaction_type, current_reaction_id=None, compounds_data=None):
        super().__init__()
        self.db = db
        self.reaction = reaction
        self.reaction_type = reaction_type
        self.current_reaction_id = current_reaction_id
        self.compounds_data = compounds_data or {}  # Dict keyed by (clean_formula, type) with user data
    
    def run(self):
        try:
            self.progress.emit("Auto-balancing reaction...")
            
            # Auto-balance the reaction
            balanced = ChemLabParser.auto_balance_reaction(self.reaction)
            
            if balanced != self.reaction:
                self.balanced_reaction.emit(balanced)
                self.reaction = balanced
            
            self.progress.emit("Saving reaction...")
            
            # Save reaction to database
            if self.current_reaction_id:
                reaction_id = self.current_reaction_id
                self.db.update_reaction(reaction_id, self.reaction, self.reaction_type)
            else:
                reaction_id = self.db.add_reaction(self.reaction, self.reaction_type)
            
            self.progress.emit("Extracting elements...")
            
            # Save elements
            elements = ChemLabParser.extract_elements_from_reaction(self.reaction)
            for element_symbol in elements:
                try:
                    elem = element(element_symbol)
                    self.db.add_or_update_element(element_symbol, elem.name, elem.atomic_number)
                except Exception:
                    self.db.add_or_update_element(element_symbol, 'Unknown', 0)
            
            self.progress.emit("Saving compounds...")
            
            # If updating, delete existing compounds first
            if self.current_reaction_id:
                self.db.delete_compounds_for_reaction(self.current_reaction_id)
            
            # Save compounds
            reactants, products = ChemLabParser.split_reaction(self.reaction)
            if reactants and products:
                all_compounds = []
                for comp in reactants.split('+'):
                    all_compounds.append((comp.strip(), 'Reactant'))
                for comp in products.split('+'):
                    all_compounds.append((comp.strip(), 'Product'))
                
                for formula, comp_type in all_compounds:
                    state, clean_formula = ChemLabParser.extract_state_symbol(formula)
                    # Look up user-entered data from table
                    key = (clean_formula, comp_type)
                    user_data = self.compounds_data.get(key, {})
                    name = user_data.get('name', '')
                    color = user_data.get('color', '')
                    notes = user_data.get('notes', '')
                    self.db.add_compound(reaction_id, clean_formula, comp_type, name, color, state, notes)
            
            self.finished.emit(True, "", reaction_id)
            
        except Exception as e:
            self.finished.emit(False, str(e), 0)


class ChemLab(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChemLab - Chemistry Laboratory Manager")
        self.setGeometry(100, 100, 1400, 800)
        
        # Database
        self.db = ChemLabDatabase("chemlab_data.db")
        
        # Data storage
        self.reactions_data = []
        self.elements_data = {}
        self.viewing_reaction_id = None  # Track which reaction is being viewed
        self.view_overlay = None  # Overlay widget for viewing reactions
        self.current_reaction_id = None  # For edit mode tracking
        self.keyboard_window = None
        self.last_focused_widget = None
        self.reactions_table = QTableWidget()
        self.reaction_entry = QLineEdit()
        self.keyboard_btn = QPushButton("🧪 Chemical Keyboard")
        self.reaction_type_cb = QComboBox()
        self.view_reaction_btn = QPushButton("👁 View")
        self.edit_reaction_btn = QPushButton("✏️ Edit")
        self.delete_reaction_btn = QPushButton("🗑 Delete")
        self.elements_table = QTableWidget()
        self.compounds_table = QTableWidget()
        self.add_reaction_btn = QPushButton(ADD_REACTION_BTN_TEXT)
        self.cancel_btn = QPushButton("❌ Cancel") # Cancel button for edit mode
        self.filter_menu = QMenu(self)
        self.central_widget = None  # Will hold reference to central widget

        self._worker = None
        
        # Compound learner for name/color suggestions
        self.compound_learner = CompoundLearner(default_color=DEFAULT_COLOR)

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
        
        # Pagination state
        self.current_page = 1
        self.items_per_page = 7
        self.filtered_reactions = []
        self.all_reactions = []
        self.current_type_filter = "All"
        
        # Debounce timer for preview updates (prevents UI lag)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview_tables)
        
        # Ctrl+N shortcut for clearing form
        self.clear_form_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.clear_form_shortcut.activated.connect(self.reset_form_to_normal)
        
        # Initialize UI
        self.init_ui()
        self.load_data()

        self._train_compound_learner()
        
    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        
        # Title
        title_label = QLabel("ChemLab - Chemistry Laboratory Manager")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Reactions Table Section (at the top)
        self.create_reactions_table(main_layout)
        
        # Reaction Entry Section
        reaction_group = QGroupBox("Reaction Entry")
        reaction_layout = QVBoxLayout()
        
        # Reaction input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Enter Reaction:"))
        self.reaction_entry.setPlaceholderText("e.g., 2H₂ + O₂ → 2H₂O")
        self.reaction_entry.textChanged.connect(self.on_reaction_changed)
        self.reaction_entry.focusInEvent = self.on_entry_focus
        
        # Add key press event handler for subscript conversion
        self.reaction_entry.keyPressEvent = self.on_reaction_key_press
        input_layout.addWidget(self.reaction_entry)
        
        # Keyboard button
        self.keyboard_btn.clicked.connect(self.open_keyboard)
        input_layout.addWidget(self.keyboard_btn)
        
        reaction_layout.addLayout(input_layout)
        
        # Reaction type input
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Reaction Type:"))
        self.reaction_type_cb.setEditable(True)  # Allow custom typing
        self.reaction_type_cb.addItems(COMMON_REACTION_TYPES)
        self.reaction_type_cb.setCurrentText("")  # Start with empty selection
        type_layout.addWidget(self.reaction_type_cb, 1)  # Add stretch factor
        
        reaction_layout.addLayout(type_layout)
        reaction_group.setLayout(reaction_layout)
        main_layout.addWidget(reaction_group)
        
        # Tables section with splitter
        self.create_compound_tables(main_layout)
        
        # Bottom section with Add Reaction button
        self.create_bottom_section(main_layout)
        
    def create_reactions_table(self, parent_layout):
        reactions_group = QGroupBox("Saved Reactions")
        reactions_layout = QVBoxLayout()

        # Search controls
        search_layout = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search reactions...")
        self.search_entry.textChanged.connect(self.on_search_text_changed)
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
        self.reactions_table.setColumnCount(2)
        self.reactions_table.setHorizontalHeaderLabels(REACTIONS_COLUMNS)
        self.reactions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.reactions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.reactions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reactions_table.itemSelectionChanged.connect(self.on_reaction_selected)
        self.reactions_table.setAlternatingRowColors(True)
        
        reactions_layout.addWidget(self.reactions_table)
        
        # Pagination and action controls combined in one row
        nav_layout = QHBoxLayout()
        
        # Create font for navigation elements
        nav_font = QFont("Arial", 12)
        
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
        reactions_group.setLayout(reactions_layout)
        parent_layout.addWidget(reactions_group)
        
    def create_compound_tables(self, parent_layout):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Elements Table
        elements_group = QGroupBox("Elements Used in Reactions")
        elements_layout = QVBoxLayout()

        self.elements_table.setColumnCount(3)
        self.elements_table.setHorizontalHeaderLabels(ELEMENTS_COLUMNS)
        self.elements_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.elements_table.setAlternatingRowColors(True)
        elements_layout.addWidget(self.elements_table)
        
        elements_group.setLayout(elements_layout)
        splitter.addWidget(elements_group)
        
        # Compounds Table
        compounds_group = QGroupBox("Reactants & Products")
        compounds_layout = QVBoxLayout()

        self.compounds_table.setColumnCount(6)
        self.compounds_table.setHorizontalHeaderLabels(COMPOUNDS_COLUMNS)
        self.compounds_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.compounds_table.setAlternatingRowColors(True)
        self.compounds_table.itemChanged.connect(self.on_compound_item_changed)
        compounds_layout.addWidget(self.compounds_table)
        
        compounds_group.setLayout(compounds_layout)
        splitter.addWidget(compounds_group)
        
        # Set splitter sizes
        splitter.setSizes([400, 800])
        parent_layout.addWidget(splitter)
        
    def create_bottom_section(self, parent_layout):
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        # Cancel button (only visible in edit mode)
        self.cancel_btn.clicked.connect(self.reset_form_to_normal)
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setVisible(False)  # Hidden by default
        bottom_layout.addWidget(self.cancel_btn)
        
        # Add reaction button (moved to bottom)
        self.add_reaction_btn.clicked.connect(self.add_reaction)
        self.add_reaction_btn.setEnabled(False)
        self.add_reaction_btn.setMinimumHeight(40)
        bottom_layout.addWidget(self.add_reaction_btn)
        
        parent_layout.addLayout(bottom_layout)
    
    def on_reaction_key_press(self, event):
        """Handle key press events for subscript conversion"""
        # Check if a digit key (0-9) is pressed
        if Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9:
            cursor = self.reaction_entry.cursorPosition()
            text = self.reaction_entry.text()
            
            # Check if the character before cursor is a letter
            if cursor > 0 and text[cursor-1].isalpha():
                # Convert digit to subscript using parser
                digit = str(event.key() - Qt.Key.Key_0)
                subscript_digit = SUBSCRIPT_DIGITS.get(digit)
                new_text = text[:cursor] + subscript_digit + text[cursor:]
                self.reaction_entry.setText(new_text)
                self.reaction_entry.setCursorPosition(cursor + 1)
                return  # Don't process the event further
        
        # Call original key press event for other keys
        QLineEdit.keyPressEvent(self.reaction_entry, event)

    def on_entry_focus(self, event):
        self.last_focused_widget = self.reaction_entry
        QLineEdit.focusInEvent(self.reaction_entry, event)
    
    def open_keyboard(self):
        """Open the chemical keyboard window"""
        if self.keyboard_window is None:
            self.keyboard_window = ChemicalKeyboard()
            self.keyboard_window.symbol_clicked.connect(self.insert_symbol_into_focused)
            
        self.keyboard_window.show()
        self.keyboard_window.raise_()
        self.keyboard_window.activateWindow()
    
    def insert_symbol_into_focused(self, symbol):
        """Insert symbol into the last focused widget"""
        if self.last_focused_widget:
            cursor = self.last_focused_widget.cursorPosition()
            current_text = self.last_focused_widget.text()
            new_text = current_text[:cursor] + symbol + current_text[cursor:]
            self.last_focused_widget.setText(new_text)
            self.last_focused_widget.setCursorPosition(cursor + len(symbol))
            # Keep focus on the main widget
            self.last_focused_widget.setFocus()
    
    def on_reaction_changed(self):
        """Enable/disable add button based on arrow presence and update preview with debounce"""
        reaction = self.reaction_entry.text().strip()
        has_arrow = any(arrow in reaction for arrow in ARROWS)
        
        # Validate reaction if it has an arrow (for UI feedback only, don't block preview)
        if has_arrow and reaction:
            validation_result = ChemLabParser.validate_reaction(reaction)
            if not validation_result['valid']:
                # Show validation error but don't block preview update
                self.reaction_entry.setStyleSheet("border: 2px solid red;")
                self.add_reaction_btn.setEnabled(False)
            else:
                # Valid reaction
                self.reaction_entry.setStyleSheet("")
                self.add_reaction_btn.setEnabled(True)
        else:
            # No arrow - reset style, disable add button
            self.reaction_entry.setStyleSheet("")
            self.add_reaction_btn.setEnabled(has_arrow and len(reaction) > 0)
            
        # Always update preview (debounced) to show compound changes even without arrow
        self.preview_timer.stop()
        self.preview_timer.start(600)

    @staticmethod
    def _normalize_formula(formula):
        if not formula:
            return ''
        value = str(formula).strip()
        value = re.sub(r'^\d+', '', value)
        value = re.sub(STATE_SYMBOL_PATTERN, '', value)
        value = value.translate(SUBSCRIPT_MAP)
        return value.strip()

    @staticmethod
    def _display_formula(formula):
        """Convert formula for display with Unicode subscripts (H2O → H₂O)"""
        if not formula:
            return ''
        value = str(formula).strip()
        value = re.sub(r'^\d+', '', value)  # Remove coefficients
        # Don't strip state symbols here - let them remain for display
        return value.translate(SUBSCRIPT_DISPLAY_MAP)

    @staticmethod
    def _convert_arrows_to_unicode(text):
        """Convert keyboard arrows in text to Unicode arrows"""
        result = text
        for arrow, unicode_arrow in ARROW_MAP.items():
            result = result.replace(arrow, unicode_arrow)
        return result
    
    def update_preview_tables(self):
        """Update elements and compounds tables for live preview - preserves user-entered data"""
        reaction = self.reaction_entry.text().strip()

        # Don't clear tables if reaction is empty - this preserves user data while typing
        if not reaction:
            return
            
        # Validate reaction before showing preview
        validation_result = ChemLabParser.validate_reaction(reaction)
        if not validation_result['valid']:
            if not validation_result.get('allow_save', False):
                return  # Don't show preview for invalid elements
        
        # Extract elements for preview
        elements = ChemLabParser.extract_elements_from_reaction(reaction)
        preview_elements = {}
        for element_symbol in elements:
            try:
                elem = element(element_symbol)
                preview_elements[element_symbol] = {
                    'name': elem.name,
                    'atomic_number': elem.atomic_number
                }
            except Exception:
                preview_elements[element_symbol] = {
                    'name': 'Unknown',
                    'atomic_number': 0
                }
        
        # Update elements table
        self.update_elements_table_preview(preview_elements)
        # Extract compounds from reaction and update table incrementally
        compounds = ChemLabParser.extract_compounds_from_reaction(reaction)
        self._update_compounds_table_incremental(compounds)
    
    def _update_compounds_table_incremental(self, compounds):
        """Update compounds table incrementally, preserving user-entered data"""
        # Block signals to prevent unwanted updates
        self.compounds_table.blockSignals(True)
        
        try:
            # Get current table data keyed by (formula, type, occurrence)
            current_data = {}
            seen = {}
            for row in range(self.compounds_table.rowCount()):
                formula_item = self.compounds_table.item(row, 0)
                type_item = self.compounds_table.item(row, 1)
                if not formula_item or not type_item:
                    continue

                formula = formula_item.text()
                ctype = type_item.text()
                seen_key = (formula, ctype)
                seen[seen_key] = seen.get(seen_key, 0) + 1
                key = (formula, ctype, seen[seen_key])

                current_data[key] = {
                    'row': row,
                    'name': self._get_cell_text(row, 2),
                    'color': self._get_cell_text(row, 3),
                    'state': self._get_cell_text(row, 4),
                    'notes': self._get_cell_text(row, 5),
                }
            
            # Build new compound list preserving existing data
            new_compounds = []
            seen_new = {}
            for compound in compounds:
                clean_formula = re.sub(r'^\d+', '', compound['formula'])
                clean_formula = re.sub(STATE_SYMBOL_PATTERN, '', clean_formula)
                clean_formula = clean_formula.translate(SUBSCRIPT_MAP)
                
                # Extract state from formula if present
                state_match = re.search(STATE_SYMBOL_PATTERN, compound['formula'])
                detected_state_abbr = state_match.group(1) if state_match else ''
                detected_state = STATE_NAMES.get(detected_state_abbr, '')

                ctype = compound.get('type', '')
                base_key = (clean_formula, ctype)
                seen_new[base_key] = seen_new.get(base_key, 0) + 1
                key = (clean_formula, ctype, seen_new[base_key])
                
                if key in current_data:
                    # Preserve user data, only update auto-detected state if formula has it
                    existing = current_data[key]
                    new_compounds.append({
                        'formula': clean_formula,
                        'type': ctype,
                        'name': existing['name'],  # Preserve user-entered name
                        'color': existing['color'],  # Preserve user-entered color
                        'state': detected_state if detected_state else existing['state'],  # Update only if state in formula
                        'notes': existing['notes'],  # Preserve user-entered notes
                    })
                else:
                    # New compound - use learner suggestions
                    # Get suggested name (state-agnostic)
                    suggested_name = self._get_suggested_name(clean_formula) or ''
                    # Get suggested color (state-aware)
                    suggested_color = self._get_suggested_color(clean_formula, detected_state_abbr)
                    
                    new_compounds.append({
                        'formula': clean_formula,
                        'type': ctype,
                        'name': suggested_name,
                        'color': suggested_color,
                        'state': detected_state,
                        'notes': '',
                    })
                    
            self._update_table_incremental(new_compounds)
            
        finally:
            self.compounds_table.blockSignals(False)
    
    def _update_table_incremental(self, new_compounds):
        """Update table incrementally - add new rows only, preserve existing"""
        # Count how many rows we need
        current_rows = self.compounds_table.rowCount()
        needed_rows = len(new_compounds)
        
        # Add new rows if needed
        if needed_rows > current_rows:
            self.compounds_table.setRowCount(needed_rows)
        
        # Update or add formula/type for each row
        for row, compound in enumerate(new_compounds):
            formula_item = self.compounds_table.item(row, 0)
            
            # If this row doesn't have a formula item, create one
            if not formula_item:
                formula_item = QTableWidgetItem(self._display_formula(compound['formula']))
                formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.compounds_table.setItem(row, 0, formula_item)
                
                type_item = QTableWidgetItem(compound['type'])
                type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.compounds_table.setItem(row, 1, type_item)
                
                # Set defaults for editable columns
                state_value = compound.get('state', '')
                display_state = STATE_NAMES.get(state_value, state_value)
                self.compounds_table.setItem(row, 2, QTableWidgetItem(compound.get('name', '')))
                self.compounds_table.setItem(row, 3, QTableWidgetItem(compound.get('color', DEFAULT_COLOR)))
                self.compounds_table.setItem(row, 4, QTableWidgetItem(display_state))
                self.compounds_table.setItem(row, 5, QTableWidgetItem(compound.get('notes', '')))
            else:
                # Update display formula
                formula_item.setText(self._display_formula(compound['formula']))
                # Also update type and state in case they changed
                type_item = self.compounds_table.item(row, 1)
                if type_item:
                    type_item.setText(compound['type'])
                state_value = compound.get('state', '')
                display_state = STATE_NAMES.get(state_value, state_value)
                state_item = self.compounds_table.item(row, 4)
                if state_item:
                    state_item.setText(display_state)
    
    def _get_cell_text(self, row, col):
        """Get text from table cell, return empty string if None"""
        item = self.compounds_table.item(row, col)
        return item.text() if item else ''
    
    def update_elements_table_preview(self, elements_data):
        """Update elements table for preview"""
        self.elements_table.setRowCount(len(elements_data))
        
        for row, (symbol, data) in enumerate(elements_data.items()):
            self.elements_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.elements_table.setItem(row, 1, QTableWidgetItem(data['name']))
            self.elements_table.setItem(row, 2, QTableWidgetItem(str(data['atomic_number'])))
    
    def load_compounds_for_reaction(self, reaction_id, view_mode=False):
        """Load compounds for a specific reaction"""
        try:
            compounds = self.db.get_compounds_for_reaction(reaction_id)
            self._populate_compounds_table(compounds, view_mode)
            self._load_and_display_elements(compounds)
        except Exception as e:
            logging.error(f"Failed to load compounds for reaction: {e}")

    def _populate_compounds_table(self, compounds, view_mode):
        """Populate the compounds table with data"""
        self.compounds_table.blockSignals(True)
        try:
            self.compounds_table.setRowCount(len(compounds))
            for row, compound in enumerate(compounds):
                self._create_compound_row(row, compound, view_mode)
        finally:
            self.compounds_table.blockSignals(False)

    def _create_compound_row(self, row, compound, view_mode):
        """Create a single compound row in the table"""
        # Formula (not editable) - display with subscripts
        formula_display = self._display_formula(compound['formula'])
        formula_item = QTableWidgetItem(formula_display)
        formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        formula_item.setData(Qt.ItemDataRole.UserRole, compound['id'])
        self.compounds_table.setItem(row, 0, formula_item)
        
        # Type (not editable)
        type_item = QTableWidgetItem(compound['type'])
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.compounds_table.setItem(row, 1, type_item)
        
        # Editable fields
        name_value = compound.get('name') or ''
        self.compounds_table.setItem(row, 2, QTableWidgetItem(name_value))
        
        color_value = compound.get('color') or DEFAULT_COLOR
        self.compounds_table.setItem(row, 3, QTableWidgetItem(color_value))
        
        state_display = self._get_state_display(compound)
        self.compounds_table.setItem(row, 4, QTableWidgetItem(state_display))
        
        notes_value = compound.get('notes') or ''
        self.compounds_table.setItem(row, 5, QTableWidgetItem(notes_value))
        
        if view_mode:
            self._make_row_readonly(row)

    @staticmethod
    def _get_state_display(compound):
        """Get display state name from compound data"""
        state_value = compound.get('state') or ''
        return STATE_NAMES.get(state_value, state_value)

    def _train_compound_learner(self):
        """Load all compounds from database to train the learner"""
        try:
            all_compounds = self.db.get_all_compounds()
            self.compound_learner.learn(all_compounds)
            if self.compound_learner.has_data():
                logging.info(f"Trained compound learner with {len(all_compounds)} compounds")
        except Exception as e:
            logging.error(f"Failed to train compound learner: {e}")

    def _get_suggested_name(self, formula):
        """Get suggested name for a compound formula"""
        return self.compound_learner.get_name(formula)

    def _get_suggested_color(self, formula, state):
        """Get suggested color for a compound based on formula and state"""
        return self.compound_learner.get_color(formula, state)

    def _make_row_readonly(self, row):
        """Make all cells in a row readonly"""
        for col in range(6):
            item = self.compounds_table.item(row, col)
            if item:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _load_and_display_elements(self, compounds):
        """Extract elements from compounds and display them"""
        reaction_elements = self._extract_elements_from_compounds(compounds)
        elements_data = self._load_elements_data(reaction_elements)
        self.update_elements_table_preview(elements_data)

    @staticmethod
    def _extract_elements_from_compounds(compounds):
        """Extract unique element symbols from compound formulas"""
        reaction_elements = set()
        for compound in compounds:
            formula = (compound.get('formula') or '').translate(SUBSCRIPT_MAP)
            formula = re.sub(STATE_SYMBOL_PATTERN, '', formula)
            matches = re.findall(r'[A-Z][a-z]?', formula)
            for match in matches:
                reaction_elements.add(match)
        return reaction_elements

    def _load_elements_data(self, reaction_elements):
        """Load element data from mendeleev for given symbols"""
        elements_data = {}
        for elem_symbol in reaction_elements:
            elements_data[elem_symbol] = self._get_element_info(elem_symbol)
        return elements_data

    @staticmethod
    def _get_element_info(elem_symbol):
        """Get element info from mendeleev, return default if not found"""
        try:
            elem = element(elem_symbol)
            return {'name': elem.name, 'atomic_number': elem.atomic_number}
        except Exception:
            return {'name': 'Unknown', 'atomic_number': 0}
    
    def update_compounds_table_preview(self, compounds):
        """Update compounds table for preview"""
        self.compounds_table.setRowCount(len(compounds))
        
        for row, compound in enumerate(compounds):
            # Formula (not editable) - display with subscripts
            formula_item = QTableWidgetItem(self._display_formula(compound['formula']))
            formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compounds_table.setItem(row, 0, formula_item)
            
            # Type (not editable)
            type_item = QTableWidgetItem(compound['type'])
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compounds_table.setItem(row, 1, type_item)
            
            # Editable fields
            self.compounds_table.setItem(row, 2, QTableWidgetItem(compound['name']))
            self.compounds_table.setItem(row, 3, QTableWidgetItem(compound['color'] or DEFAULT_COLOR))
            self.compounds_table.setItem(row, 4, QTableWidgetItem(compound['state']))
            self.compounds_table.setItem(row, 5, QTableWidgetItem(compound['notes']))

    def add_reaction(self):
        """Add or update a reaction in database with auto-balancing (threaded)"""
        reaction = self.reaction_entry.text().strip()
        reaction_type = self.reaction_type_cb.currentText().strip() or 'Unknown'

        # Basic check for arrow
        validate = self._validate_reaction_input(reaction)
        if not reaction or not validate:
            return
        
        # Disable button to prevent double-click
        self.add_reaction_btn.setEnabled(False)
        self.add_reaction_btn.setText("⏳ Processing...")
        
        # Collect user-entered compound data from table
        compounds_data = {}
        for row in range(self.compounds_table.rowCount()):
            formula_item = self.compounds_table.item(row, 0)
            if not formula_item:
                continue
            clean_formula = ChemLabParser.extract_state_symbol(formula_item.text())[1]
            comp_type = self.compounds_table.item(row, 1)
            if comp_type:
                key = (clean_formula, comp_type.text())
                compounds_data[key] = {
                    'name': self._get_table_text(row, 2),
                    'color': self._get_table_text(row, 3),
                    'notes': self._get_table_text(row, 5)
                }
        
        # Create and start worker thread
        self._worker = SaveReactionWorker(
            self.db, reaction, reaction_type, self.current_reaction_id, compounds_data
        )
        self._worker.balanced_reaction.connect(self._on_balanced_reaction)
        self._worker.finished.connect(self._on_save_finished)
        self._worker.start()
    
    def _on_balanced_reaction(self, balanced):
        """Handle balanced reaction from worker thread"""
        # Update the entry with balanced version
        self.reaction_entry.blockSignals(True)
        self.reaction_entry.setText(balanced)
        self.reaction_entry.blockSignals(False)
        self.update_preview_tables()
    
    def _on_save_finished(self, success, error_message):
        """Handle save completion from worker thread"""
        self.add_reaction_btn.setEnabled(True)
        self.add_reaction_btn.setText(
            "💾 Update Reaction" if self.current_reaction_id else ADD_REACTION_BTN_TEXT
        )
        
        if success:
            self._finalize_add_reaction()
            # Update the learner with new data
            self._train_compound_learner()
        else:
            logging.error(f"Failed to add/update reaction: {error_message}")
            QMessageBox.critical(self, "Error", f"Failed: {error_message}")

    def _validate_reaction_input(self, reaction):
        """Validate reaction input before saving"""
        has_arrow = any(arrow in reaction for arrow in ARROWS)

        if not reaction or not has_arrow:
            QMessageBox.warning(self, "Invalid Reaction", "Please enter a reaction with an arrow")
            return False

        validation_result = ChemLabParser.validate_reaction(reaction)

        if not validation_result['valid']:
            return self._handle_validation_error(validation_result)

        return True

    def _handle_validation_error(self, validation_result):
        """Handle validation error - auto-balance or prompt user"""
        if not validation_result.get('allow_save', False):
            QMessageBox.warning(self, "Invalid Reaction", validation_result['error'])
            return False
        return True

    def _save_reaction(self, reaction, reaction_type):
        """Save reaction to database (update if in edit mode, add if new)"""
        if self.current_reaction_id:
            reaction_id = self.current_reaction_id
            self.db.update_reaction(reaction_id, reaction, reaction_type)
        else:
            reaction_id = self.db.add_reaction(reaction, reaction_type)

        self.update_reaction_type_combobox()
        return reaction_id

    def _get_table_text(self, row, col):
        """Get text from table cell, return empty string if cell doesn't exist"""
        item = self.compounds_table.item(row, col)
        return item.text() if item else ''


    def _finalize_add_reaction(self):
        """Reset form and reload data after successful save"""
        self.current_reaction_id = None
        self.reset_form_to_normal()
        self.load_data()
    
    def update_filter_menu(self):
        """Populate filter menu with reaction types from combobox"""
        try:
            self.filter_menu.clear()
            self.filter_menu.addAction("All Types", lambda: self._safe_apply_filter("All"))
            self.filter_menu.addSeparator()
            # Use items from reaction_type_cb combobox
            for i in range(self.reaction_type_cb.count()):
                rtype = self.reaction_type_cb.itemText(i)
                if rtype:
                    try:
                        action = self.filter_menu.addAction(rtype)
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
    
    def update_reaction_type_combobox(self):
        """Update reaction type combobox with existing types from database"""
        try:
            # Get all unique reaction types from database
            existing_types = {
                r['reaction_type']
                for r in self.db.get_all_reactions()
                if r.get('reaction_type') and r['reaction_type'] != 'Unknown'
            }
            
            # Get current combobox items
            current_items = {self.reaction_type_cb.itemText(i) for i in range(self.reaction_type_cb.count())}
            
            # Add new types to combobox
            new_types = existing_types - current_items
            if new_types:
                # Get all current items and add new ones
                all_types = list(current_items) + list(new_types)
                self.reaction_type_cb.clear()
                self.reaction_type_cb.addItems(sorted(all_types))
                self.reaction_type_cb.setCurrentText("")
                # Update filter menu after updating combobox
            self.update_filter_menu()
                
        except Exception as e:
            logging.error(f"Failed to update reaction type combobox: {e}")
    
    def view_selected_reaction(self):
        """View the selected reaction in an overlay widget"""
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            reaction_id = self.reactions_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
            reaction_text = self.reactions_table.item(selected_row, 0).text()
            reaction_type = self.reactions_table.item(selected_row, 1).text()
            
            # Store the viewing state
            self.viewing_reaction_id = reaction_id
            
            # Create and show the view overlay
            self.create_view_overlay(reaction_id, reaction_text, reaction_type)

    def edit_selected_reaction(self):
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            reaction_id = self.reactions_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
            reaction_text = self.reactions_table.item(selected_row, 0).text()
            reaction_type = self.reactions_table.item(selected_row, 1).text()

            # Close any view overlay if open
            self.close_view_overlay()

            # 🔥 SET EDIT MODE
            self.current_reaction_id = reaction_id

            # Block signals to prevent on_reaction_changed from clearing tables
            self.reaction_entry.blockSignals(True)
            self.reaction_entry.setText(reaction_text)
            self.reaction_entry.blockSignals(False)
            self.reaction_entry.setReadOnly(False)

            self.reaction_type_cb.setCurrentText(reaction_type)
            self.reaction_type_cb.setEnabled(True)

            # Load compounds for this reaction (this will populate tables)
            self.load_compounds_for_reaction(reaction_id, view_mode=False)

            self.add_reaction_btn.setText("💾 Update Reaction")
            self.add_reaction_btn.setEnabled(True)
            
            # Show cancel button in edit mode
            self.cancel_btn.setVisible(True)
    
    def delete_selected_reaction(self):
        """Delete the selected reaction"""
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            reaction_id = self.reactions_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
            reaction_text = self.reactions_table.item(selected_row, 0).text()
            
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
                    self.reset_form_to_normal()
                    self.load_data()
                except Exception as e:
                    logging.error(f"Failed to delete reaction: {e}")
                    QMessageBox.critical(self, "Error", f"Failed to delete reaction: {e}")
    
    def on_reaction_selected(self):
        """Handle reaction selection and enable/disable action buttons"""
        selected_items = self.reactions_table.selectedItems()
        has_selection = len(selected_items) > 0
        
        # Enable/disable action buttons based on selection
        self.view_reaction_btn.setEnabled(has_selection)
        self.edit_reaction_btn.setEnabled(has_selection)
        self.delete_reaction_btn.setEnabled(has_selection)
    
    def reset_form_to_normal(self):
        """Reset the form back to normal add mode"""
        # Close view overlay if open
        self.close_view_overlay()
        
        self.reaction_entry.clear()
        self.reaction_entry.setReadOnly(False)
        self.reaction_type_cb.setCurrentText("")
        self.reaction_type_cb.setEnabled(True)
        self.add_reaction_btn.setText(ADD_REACTION_BTN_TEXT)
        
        # Hide cancel button when not in edit mode
        self.cancel_btn.setVisible(False)
        
        # Clear both tables
        self.elements_table.setRowCount(0)
        self.compounds_table.setRowCount(0)
        self.current_reaction_id = None
        # Clear selection in reactions table and disable buttons
        self.reactions_table.clearSelection()
        self.view_reaction_btn.setEnabled(False)
        self.edit_reaction_btn.setEnabled(False)
        self.delete_reaction_btn.setEnabled(False)
    
    def on_search_text_changed(self, _text):
        """Handle search text changes"""
        self.current_page = 1
        self.apply_filter_and_pagination()
    
    def clear_search(self):
        """Clear search field"""
        self.search_entry.clear()
        self.current_page = 1
        self.apply_filter_and_pagination()
    
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
        except Exception as e:
            logging.error(f"Error in apply_type_filter: {e}")
    
    def apply_filter_and_pagination(self):
        """Apply search filter, type filter, and pagination to reactions"""
        search_text = self.search_entry.text().lower()
        
        # Start with all reactions
        filtered = self.all_reactions[:]
        
        # Apply type filter if not "All"
        if self.current_type_filter != "All":
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
            # Reaction text - convert keyboard arrows to Unicode
            reaction_item = QTableWidgetItem(self._convert_arrows_to_unicode(reaction['reaction_text']))
            reaction_item.setFlags(reaction_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            reaction_item.setData(Qt.ItemDataRole.UserRole, reaction['id'])  # Store ID
            self.reactions_table.setItem(row, 0, reaction_item)
            
            # Reaction type
            type_item = QTableWidgetItem(reaction.get('reaction_type', 'Unknown'))
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.reactions_table.setItem(row, 1, type_item)
        
        # Update pagination controls
        self.page_entry.setText(str(self.current_page))
        self.page_label.setText(f"of {total_pages}")
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)
        
        # Update page entry validator
        from PyQt6.QtGui import QIntValidator
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
    
    def on_compound_item_changed(self, item):
        """Handle compound table item changes"""
        if item.row() >= 0 and item.column() >= 2:  # Only update editable columns
            formula_item = self.compounds_table.item(item.row(), 0)
            if not formula_item:
                return

            compound_id = formula_item.data(Qt.ItemDataRole.UserRole)
            if compound_id:
                column_name = COMPOUNDS_COLUMNS[item.column()].lower()
                value = item.text()
                
                # Convert full state name to abbreviation for State column (column 4)
                if item.column() == 4 and value:
                    value = STATE_ABBREVIATIONS.get(value, value)
                
                # Update database
                update_data = {column_name: value}
                self.db.update_compound(compound_id, **update_data)
    
    def load_data(self):
        """Load all data from database with pagination"""
        try:
            # Load all reactions
            self.all_reactions = self.db.get_all_reactions()
            self.current_page = 1
            self.apply_filter_and_pagination()
            
            # Update reaction type combobox and filter menu
            self.update_reaction_type_combobox()
            
            # Clear elements and compounds tables (will load when reaction is selected)
            self.elements_table.setRowCount(0)
            self.compounds_table.setRowCount(0)
            
        except Exception as e:
            logging.error(f"Failed to load data: {e}")
    
    def update_elements_table(self):
        """Update the elements table"""
        self.elements_table.setRowCount(len(self.elements_data))
        
        for row, (symbol, data) in enumerate(self.elements_data.items()):
            self.elements_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.elements_table.setItem(row, 1, QTableWidgetItem(data['name']))
            self.elements_table.setItem(row, 2, QTableWidgetItem(str(data['atomic_number'])))
    
    def update_compounds_table(self, compounds):
        """Update the compounds table"""
        self.compounds_table.setRowCount(len(compounds))
        
        for row, compound in enumerate(compounds):
            # Formula (not editable)
            formula_item = QTableWidgetItem(compound['formula'])
            formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            formula_item.setData(Qt.ItemDataRole.UserRole, compound['id'])  # Store ID for updates
            self.compounds_table.setItem(row, 0, formula_item)
            
            # Type (not editable)
            type_item = QTableWidgetItem(compound['type'])
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compounds_table.setItem(row, 1, type_item)
            
            # Editable fields
            self.compounds_table.setItem(row, 2, QTableWidgetItem(compound['name'] or ''))
            self.compounds_table.setItem(row, 3, QTableWidgetItem(compound['color'] or ''))
            
            # State - convert abbreviation to full name
            state_value = compound.get('state') or ''
            if state_value and state_value in STATE_NAMES:
                state_value = STATE_NAMES[state_value]
            self.compounds_table.setItem(row, 4, QTableWidgetItem(state_value))
            
            self.compounds_table.setItem(row, 5, QTableWidgetItem(compound['notes'] or ''))
    

    def backup_database(self):
        """Create a backup of the database"""
        try:
            backup_name = f"chemlab_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            import shutil
            shutil.copy2("chemlab_data.db", backup_name)
            
            QMessageBox.information(self, "Backup Successful", f"Database backed up to {backup_name}")
            
        except Exception as e:
            logging.error(f"Failed to backup database: {e}")
            QMessageBox.critical(self, "Backup Failed", f"Failed to backup database: {e}")
    

    
    def closeEvent(self, event):
        """Handle application close"""
        try:
            self.db.close()
            if self.keyboard_window:
                self.keyboard_window.close()
            if self.view_overlay:
                self.view_overlay.close()
        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")
        
        event.accept()

    def create_view_overlay(self, reaction_id, reaction_text, reaction_type):
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
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #ffffff; padding: 10px;")
        overlay_layout.addWidget(title)
        
        # Reaction info section
        info_group = QGroupBox("Reaction Information")
        info_layout = QGridLayout()
        info_layout.setSpacing(10)
        
        reaction_label = QLabel(f"<b>Reaction:</b> {self._convert_arrows_to_unicode(reaction_text)}")
        reaction_label.setWordWrap(True)
        reaction_label.setFont(QFont("Arial", 12))
        reaction_label.setStyleSheet("color: #ffffff;")
        reaction_label.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(reaction_label, 0, 0, 1, 2)
        
        type_label = QLabel(f"<b>Type:</b> {reaction_type}")
        type_label.setFont(QFont("Arial", 11))
        type_label.setStyleSheet("color: #ffffff;")
        info_layout.addWidget(type_label, 1, 0)
        
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
        elements_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        compounds_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
                formula_item = QTableWidgetItem(self._display_formula(compound['formula']))
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
                except Exception:
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
        """Handle resize events to keep overlay filling the central widget"""
        if obj == self.central_widget and event.type() == event.Type.Resize:
            if self.view_overlay:
                self.view_overlay.setGeometry(self.central_widget.rect())
        return super().eventFilter(obj, event)
    
    def on_view_back_clicked(self):
        """Handle back button click in view mode"""
        self.close_view_overlay()
        self.reset_form_to_normal()
        self.reactions_table.clearSelection()
        self.view_reaction_btn.setEnabled(False)
        self.edit_reaction_btn.setEnabled(False)
        self.delete_reaction_btn.setEnabled(False)

def main():
    app = QApplication(sys.argv)
    window = ChemLab()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
