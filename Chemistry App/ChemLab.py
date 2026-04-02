import sys
import re
import logging
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QLineEdit, QPushButton, QLabel, QSplitter,
                             QGroupBox, QHeaderView, QMessageBox, QComboBox,
                             QFrame, QGridLayout, QMenu)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QIntValidator, QIcon
from mendeleev import element
# Import separated modules
from constants import (
    ARROWS, COMMON_REACTION_TYPES, DEFAULT_COLOR, REACTIONS_COLUMNS,
    COMPOUNDS_COLUMNS, ELEMENTS_COLUMNS, SUBSCRIPT_DIGITS, STATE_NAMES,
    STATE_ABBREVIATIONS, ADD_REACTION_BTN_TEXT, COLOR_STYLE, FONT, ICON_PATH
                       )
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
    
    def _save_elements(self, reaction):
        """Extract and save elements from reaction to database."""
        elements = ChemLabParser.extract_elements_from_reaction(reaction)
        for element_symbol in elements:
            try:
                elem = element(element_symbol)
                self.db.add_or_update_element(element_symbol, elem.name, elem.atomic_number)
            except (ValueError, KeyError):
                self.db.add_or_update_element(element_symbol, 'Unknown', 0)
        return elements

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
            self._save_elements(self.reaction)
            
            self.progress.emit("Saving compounds...")
            
            # If updating, delete existing compounds first
            if self.current_reaction_id:
                self.db.delete_compounds_for_reaction(self.current_reaction_id)
            
            # Save compounds
            reactants, products = ChemLabParser.split_reaction(self.reaction)
            logging.info(f"DEBUG WORKER: Split reaction - reactants='{reactants}', products='{products}'")
            logging.info(f"DEBUG WORKER: compounds_data keys received: {list(self.compounds_data.keys())}")
            
            if reactants and products:
                all_compounds = []
                for comp in reactants.split('+'):
                    all_compounds.append((comp.strip(), 'Reactant'))
                for comp in products.split('+'):
                    all_compounds.append((comp.strip(), 'Product'))
                
                logging.info(f"DEBUG WORKER: all_compounds list: {all_compounds}")
                
                for formula, comp_type in all_compounds:
                    # Normalize first to strip coefficients and state symbols
                    clean_formula = ChemLabParser.normalize_formula(formula)
                    state, _ = ChemLabParser.extract_state_symbol(formula)
                    # Look up user-entered data from table
                    key = (clean_formula, comp_type)
                    user_data = self.compounds_data.get(key, {})
                    name = user_data.get('name', '')
                    color = user_data.get('color', '')
                    notes = user_data.get('notes', '')
                    logging.info(f"DEBUG WORKER: Saving compound - formula='{clean_formula}', type='{comp_type}', key={key}")
                    logging.info(f"DEBUG WORKER:   user_data found={bool(user_data)}, name='{name}', color='{color}', notes='{notes}'")
                    self.db.add_compound(reaction_id, clean_formula, comp_type, name, color, state, notes)
            
            self.finished.emit(True, "", reaction_id)
            
        except Exception as e:
            logging.error(f"DEBUG WORKER: Exception in run: {e}", exc_info=True)
            self.finished.emit(False, str(e), 0)


class PreviewWorker(QThread):
    """Worker thread for live preview updates to prevent UI lag"""
    finished = pyqtSignal(dict, list)  # elements_data, compounds_list
    error = pyqtSignal(str)  # error message
    
    def __init__(self, reaction, compound_learner):
        super().__init__()
        self.reaction = reaction
        self.compound_learner = compound_learner
    
    def run(self):
        try:
            # Validate reaction
            validation_result = ChemLabParser.validate_reaction(self.reaction)
            if not validation_result['valid'] and not validation_result.get('allow_save', False):
                self.error.emit("Invalid reaction")
                return
            
            # Extract elements and look up their info
            elements = ChemLabParser.extract_elements_from_reaction(self.reaction)
            preview_elements = {}
            for element_symbol in elements:
                try:
                    elem = element(element_symbol)
                    preview_elements[element_symbol] = {
                        'name': elem.name,
                        'atomic_number': elem.atomic_number
                    }
                except (ValueError, KeyError):
                    preview_elements[element_symbol] = {
                        'name': 'Unknown',
                        'atomic_number': 0
                    }
            
            # Extract compounds with suggestions
            compounds = ChemLabParser.extract_compounds_from_reaction(self.reaction)
            preview_compounds = []
            
            for compound in compounds:
                clean_formula, detected_state, detected_state_abbr = ChemLabParser.parse_compound(compound)
                
                # Get suggestions from learner
                suggested_name = self.compound_learner.get_name(clean_formula) or ''
                suggested_color = self.compound_learner.get_color(clean_formula, detected_state_abbr)
                
                preview_compounds.append({
                    'formula': clean_formula,
                    'type': compound.get('type', ''),
                    'name': suggested_name,
                    'color': suggested_color,
                    'state': detected_state,
                    'state_abbr': detected_state_abbr,
                    'notes': ''
                })
            
            self.finished.emit(preview_elements, preview_compounds)
            
        except Exception as e:
            logging.error(f"Preview worker error: {e}", exc_info=True)
            self.error.emit(str(e))


class ChemLab(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChemLab - Chemistry Laboratory Manager")
        self.setGeometry(100, 100, 1400, 800)
        self.setWindowIcon(QIcon(ICON_PATH))
        # Database
        self.db = ChemLabDatabase("chemlab_data.db")
        
        # Data storage
        self.reactions_data = []
        self.elements_data = {}
        self.viewing_reaction_id = None  # Track which reaction is being viewed
        self.view_overlay = None  # Overlay widget for viewing reactions
        self.compound_overlay = None  # Overlay widget for viewing compound stats
        self.compound_overlay_parent = None  # Track parent overlay to return to
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
        self._preview_worker = None  # Worker for live preview threading
        
        # Compound learner for name/color suggestions
        self.compound_learner = CompoundLearner()

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

        # Clear suggestion tracking dictionaries to avoid stale data
        self._last_suggested_colors = {}
        self._last_suggested_names = {}
        self._last_formulas = {}
        self._last_state_abbrs = {}

        # Pagination state
        self.current_page = 1
        self.items_per_page = 5
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
        table_font = QFont(FONT, 13)
        self.reactions_table.setColumnCount(2)
        self.reactions_table.setHorizontalHeaderLabels(REACTIONS_COLUMNS)
        header = self.reactions_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.reactions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reactions_table.itemSelectionChanged.connect(self.on_reaction_selected)
        self.reactions_table.setFont(table_font)
        self.reactions_table.setMaximumHeight(230)
        # noinspection PyUnresolvedReferences
        self.reactions_table.verticalHeader().setDefaultSectionSize(40)
        self.reactions_table.setAlternatingRowColors(True)
        
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
        header = self.elements_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.elements_table.setAlternatingRowColors(True)
        elements_layout.addWidget(self.elements_table)
        
        elements_group.setLayout(elements_layout)
        splitter.addWidget(elements_group)
        
        # Compounds Table
        compounds_group = QGroupBox("Reactants & Products")
        compounds_layout = QVBoxLayout()

        self.compounds_table.setColumnCount(6)
        self.compounds_table.setHorizontalHeaderLabels(COMPOUNDS_COLUMNS)
        header = self.compounds_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

    def update_preview_tables(self):
        """Update elements and compounds tables for live preview using threaded worker"""
        reaction = self.reaction_entry.text().strip()

        # Don't clear tables if reaction is empty - this preserves user data while typing
        if not reaction:
            return
            
        # Cancel any existing preview worker
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.wait(100)  # Wait briefly for cleanup
        
        # Create and start preview worker thread
        self._preview_worker = PreviewWorker(reaction, self.compound_learner)
        self._preview_worker.finished.connect(self._on_preview_finished)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()
    
    def _on_preview_finished(self, elements_data, compounds_list):
        """Handle preview worker completion - update tables in main thread"""
        # Update elements table
        self.update_elements_table_preview(elements_data)
        # Update compounds table with incremental merge
        self._update_compounds_table_from_worker(compounds_list)
    
    @staticmethod
    def _on_preview_error(error_message):
        """Handle preview worker error"""
        logging.warning(f"Preview worker error: {error_message}")
        # Don't show UI errors for preview - it's non-critical
    
    def _update_compounds_table_from_worker(self, worker_compounds):
        """Update compounds table from worker data, preserving user-entered data"""
        self.compounds_table.blockSignals(True)
        try:
            current_data = self._collect_current_table_data()
            self._init_tracking_dicts()
            
            # Merge worker compounds with existing user data
            new_compounds = []
            seen_new = {}
            
            for compound in worker_compounds:
                clean_formula = compound['formula']
                ctype = compound['type']
                detected_state = compound['state']
                detected_state_abbr = compound['state_abbr']
                
                base_key = (clean_formula, ctype)
                seen_new[base_key] = seen_new.get(base_key, 0) + 1
                key = (clean_formula, ctype, seen_new[base_key])
                
                if key in current_data:
                    # Existing compound - merge with user data
                    existing = current_data[key]
                    prev_formula = existing.get('prev_formula')
                    prev_state = existing.get('prev_state_abbr')
                    context_changed = (prev_formula != clean_formula) or (prev_state != detected_state_abbr)
                    
                    current_color = existing['color']
                    prev_suggested_color = existing.get('prev_suggested_color')
                    color_was_suggested = current_color == prev_suggested_color
                    
                    current_name = existing['name']
                    prev_suggested_name = existing.get('prev_suggested_name')
                    name_was_suggested = current_name == prev_suggested_name
                    
                    suggested_color = self._get_suggestion_or_preserve(
                        context_changed, color_was_suggested, clean_formula, detected_state_abbr,
                        current_color, is_color=True
                    )
                    suggested_name = self._get_suggestion_or_preserve(
                        context_changed, name_was_suggested, clean_formula, detected_state_abbr,
                        current_name, is_color=False
                    )
                    
                    merged_compound = {
                        'formula': clean_formula,
                        'type': ctype,
                        'name': suggested_name,
                        'color': suggested_color,
                        'state': detected_state if detected_state else existing['state'],
                        'notes': existing['notes'],
                    }
                else:
                    # New compound - use worker suggestions
                    merged_compound = compound
                
                new_compounds.append(merged_compound)
                self._track_suggestions(len(new_compounds) - 1, clean_formula, detected_state_abbr, merged_compound)
            
            self._update_table_incremental(new_compounds)
        finally:
            self.compounds_table.blockSignals(False)
    
    def _update_compounds_table_incremental(self, compounds):
        """Update compounds table incrementally, preserving user-entered data"""
        self.compounds_table.blockSignals(True)
        try:
            current_data = self._collect_current_table_data()
            self._init_tracking_dicts()
            new_compounds = self._build_compound_list(compounds, current_data)
            self._update_table_incremental(new_compounds)
        finally:
            self.compounds_table.blockSignals(False)

    def _collect_current_table_data(self):
        """Collect current table data keyed by (formula, type, occurrence)"""
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
                'prev_suggested_color': getattr(self, '_last_suggested_colors', {}).get(row),
                'prev_suggested_name': getattr(self, '_last_suggested_names', {}).get(row),
                'prev_formula': getattr(self, '_last_formulas', {}).get(row),
                'prev_state_abbr': getattr(self, '_last_state_abbrs', {}).get(row),
            }
        return current_data

    def _init_tracking_dicts(self):
        """Initialize tracking dicts if not present"""
        for attr in ['_last_suggested_colors', '_last_suggested_names', '_last_formulas', '_last_state_abbrs']:
            if not hasattr(self, attr):
                setattr(self, attr, {})

    def _build_compound_list(self, compounds, current_data):
        """Build new compound list preserving existing data"""
        new_compounds = []
        seen_new = {}
        for compound in compounds:
            clean_formula, detected_state, detected_state_abbr = ChemLabParser.parse_compound(compound)
            ctype = compound.get('type', '')
            base_key = (clean_formula, ctype)
            seen_new[base_key] = seen_new.get(base_key, 0) + 1
            key = (clean_formula, ctype, seen_new[base_key])

            compound_data = self._create_compound_data(
                key, current_data, clean_formula, ctype, detected_state, detected_state_abbr
            )
            new_compounds.append(compound_data)
            self._track_suggestions(len(new_compounds) - 1, clean_formula, detected_state_abbr, compound_data)
        return new_compounds

    def _create_compound_data(self, key, current_data, clean_formula, ctype, detected_state, detected_state_abbr):
        """Create compound data dict, either from existing or as new"""
        if key in current_data:
            return self._build_existing_compound(
                current_data[key], clean_formula, ctype, detected_state, detected_state_abbr
            )
        return self._build_new_compound(clean_formula, ctype, detected_state, detected_state_abbr)

    def _build_existing_compound(self, existing, clean_formula, ctype, detected_state, detected_state_abbr):
        """Build compound data from existing row data"""
        prev_formula = existing.get('prev_formula')
        prev_state = existing.get('prev_state_abbr')
        context_changed = (prev_formula != clean_formula) or (prev_state != detected_state_abbr)

        current_color = existing['color']
        prev_suggested_color = existing.get('prev_suggested_color')
        color_was_suggested = current_color == prev_suggested_color

        current_name = existing['name']
        prev_suggested_name = existing.get('prev_suggested_name')
        name_was_suggested = current_name == prev_suggested_name

        suggested_color = self._get_suggestion_or_preserve(
            context_changed, color_was_suggested, clean_formula, detected_state_abbr,
            current_color, is_color=True
        )
        suggested_name = self._get_suggestion_or_preserve(
            context_changed, name_was_suggested, clean_formula, detected_state_abbr,
            current_name, is_color=False
        )

        return {
            'formula': clean_formula,
            'type': ctype,
            'name': suggested_name,
            'color': suggested_color,
            'state': detected_state if detected_state else existing['state'],
            'notes': existing['notes'],
        }

    def _build_new_compound(self, clean_formula, ctype, detected_state, detected_state_abbr):
        """Build compound data for a new compound"""
        return {
            'formula': clean_formula,
            'type': ctype,
            'name': self._get_suggested_name(clean_formula) or '',
            'color': self._get_suggested_color(clean_formula, detected_state_abbr),
            'state': detected_state,
            'notes': '',
        }

    def _get_suggestion_or_preserve(self, context_changed, was_suggested, clean_formula,
                                     detected_state_abbr, current_value, is_color):
        """Get new suggestion if context changed and value was auto-suggested, else preserve"""
        if context_changed and was_suggested:
            log_msg = "[PREVIEW COLOR]" if is_color else "[PREVIEW NAME]"
            logging.info(f"{log_msg} Context changed for {clean_formula}, re-querying learner")
            if is_color:
                return self._get_suggested_color(clean_formula, detected_state_abbr)
            return self._get_suggested_name(clean_formula) or ''
        return current_value

    def _track_suggestions(self, row_idx, clean_formula, detected_state_abbr, compound_data):
        """Track what we're suggesting for this row"""
        self._last_suggested_colors[row_idx] = compound_data['color']
        self._last_suggested_names[row_idx] = compound_data['name']
        self._last_formulas[row_idx] = clean_formula
        self._last_state_abbrs[row_idx] = detected_state_abbr
    
    def _update_table_incremental(self, new_compounds):
        """Update table - create rows and fill empty cells with suggestions."""
        current_rows = self.compounds_table.rowCount()
        needed_rows = len(new_compounds)

        if needed_rows > current_rows:
            self.compounds_table.setRowCount(needed_rows)

        for row, compound in enumerate(new_compounds):
            self._update_formula_cell(row, compound['formula'])
            self._update_type_cell(row, compound['type'])
            self._update_state_cell(row, compound.get('state', ''))
            self._update_notes_cell(row, compound.get('notes', ''))
            self._update_name_cell(row, compound.get('name', ''))
            self._update_color_cell(row, compound.get('color', ''))

    def _get_or_create_item(self, row, col, text, editable=False):
        """Get existing item or create new one. Returns the item."""
        item = self.compounds_table.item(row, col)
        if not item:
            item = QTableWidgetItem(text)
            if not editable:
                item.setFlags(item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
            self.compounds_table.setItem(row, col, item)
        else:
            item.setText(text)
        return item

    def _update_formula_cell(self, row, formula):
        """Update formula cell (column 0) - not editable."""
        self._get_or_create_item(row, 0, ChemLabParser.display_formula(formula), editable=False)

    def _update_type_cell(self, row, comp_type):
        """Update type cell (column 1) - not editable."""
        self._get_or_create_item(row, 1, comp_type, editable=False)

    def _update_state_cell(self, row, state_value):
        """Update state cell (column 4)."""
        display_state = STATE_NAMES.get(state_value, state_value)
        self._get_or_create_item(row, 4, display_state)

    def _update_notes_cell(self, row, notes):
        """Update notes cell (column 5) - only if empty."""
        if not self.compounds_table.item(row, 5):
            self.compounds_table.setItem(row, 5, QTableWidgetItem(notes))

    def _update_name_cell(self, row, suggested_name):
        """Update name cell (column 2) - fill only if empty."""
        name_item = self.compounds_table.item(row, 2)
        if not name_item:
            self.compounds_table.setItem(row, 2, QTableWidgetItem(suggested_name))
        elif not name_item.text().strip() and suggested_name:
            name_item.setText(suggested_name)

    @staticmethod
    def _should_update_color(color_item, suggested_color):
        """Check if color cell should be updated."""
        if not suggested_color:
            return False
        if not color_item:
            return True
        current = color_item.text().strip().lower()
        return current == '' or current == DEFAULT_COLOR

    def _update_color_cell(self, row, suggested_color):
        """Update color cell (column 3) - fill only if empty or default."""
        color_item = self.compounds_table.item(row, 3)
        current_color = color_item.text() if color_item else "(empty)"
        logging.info(f"[PREVIEW COLOR] Row {row}: current={current_color!r}, suggested={suggested_color!r}")
        if not self._should_update_color(color_item, suggested_color):
            logging.info(f"[PREVIEW COLOR] Row {row}: Skipping update (should_update=False)")
            return
        logging.info(f"[PREVIEW COLOR] Row {row}: Updating color to {suggested_color!r}")
        if not color_item:
            self.compounds_table.setItem(row, 3, QTableWidgetItem(suggested_color))
        else:
            color_item.setText(suggested_color)
    
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
        formula_display = ChemLabParser.display_formula(compound['formula'])
        formula_item = QTableWidgetItem(formula_display)
        formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
        formula_item.setData(Qt.ItemDataRole.UserRole, compound['id'])
        self.compounds_table.setItem(row, 0, formula_item)
        
        # Type (not editable)
        type_item = QTableWidgetItem(compound['type'])
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
        self.compounds_table.setItem(row, 1, type_item)
        
        # Editable fields
        name_value = compound.get('name') or ''
        self.compounds_table.setItem(row, 2, QTableWidgetItem(name_value))
        
        color_value = compound.get('color') or DEFAULT_COLOR
        self.compounds_table.setItem(row, 3, QTableWidgetItem(color_value))
        
        state_display = ChemLabParser.get_state_display(compound)
        self.compounds_table.setItem(row, 4, QTableWidgetItem(state_display))
        
        notes_value = compound.get('notes') or ''
        self.compounds_table.setItem(row, 5, QTableWidgetItem(notes_value))
        
        if view_mode:
            self._make_row_readonly(row)

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
        logging.info(f"[PREVIEW COLOR] Getting suggested color for formula={formula!r}, state={state!r}")
        color = self.compound_learner.get_color(formula, state)
        logging.info(f"[PREVIEW COLOR] Learner returned color={color!r}")
        return color

    def _make_row_readonly(self, row):
        """Make all cells in a row readonly"""
        for col in range(6):
            item = self.compounds_table.item(row, col)
            if item:
                item.setFlags(item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))

    def _load_and_display_elements(self, compounds):
        """Extract elements from compounds and display them"""
        reaction_elements = ChemLabParser.extract_elements_from_compounds(compounds)
        elements_data = ChemLabParser.load_elements_data(reaction_elements)
        self.update_elements_table_preview(elements_data)

    def update_compounds_table_preview(self, compounds):
        """Update compounds table for preview"""
        self.compounds_table.setRowCount(len(compounds))
        
        for row, compound in enumerate(compounds):
            # Formula (not editable) - display with subscripts
            formula_item = QTableWidgetItem(ChemLabParser.display_formula(compound['formula']))
            formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
            self.compounds_table.setItem(row, 0, formula_item)
            
            # Type (not editable)
            type_item = QTableWidgetItem(compound['type'])
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
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
        logging.info(f"DEBUG: Collecting from {self.compounds_table.rowCount()} table rows")
        for row in range(self.compounds_table.rowCount()):
            formula_item = self.compounds_table.item(row, 0)
            if not formula_item:
                logging.info(f"DEBUG: Row {row} - no formula item, skipping")
                continue
            # Normalize formula to ASCII to match worker lookup keys
            clean_formula = ChemLabParser.normalize_formula(formula_item.text())
            comp_type = self.compounds_table.item(row, 1)
            if comp_type:
                key = (clean_formula, comp_type.text())
                name = self._get_table_text(row, 2)
                color = self._get_table_text(row, 3)
                notes = self._get_table_text(row, 5)
                compounds_data[key] = {
                    'name': name,
                    'color': color,
                    'notes': notes
                }
                logging.info(f"DEBUG: Row {row} - key={key}, name={name!r}, color={color!r}")
            else:
                logging.info(f"DEBUG: Row {row} - no type item, skipping")
        logging.info(f"DEBUG: Final compounds_data keys: {list(compounds_data.keys())}")
        
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
            item = self.reactions_table.item(selected_row, 0)
            type_item = self.reactions_table.item(selected_row, 1)
            if not item or not type_item:
                return
            reaction_id = item.data(Qt.ItemDataRole.UserRole)
            reaction_text = item.text()
            reaction_type = type_item.text()
            
            # Store the viewing state
            self.viewing_reaction_id = reaction_id
            
            # Create and show the view overlay
            self.create_view_overlay(reaction_id, reaction_text, reaction_type)

    def edit_selected_reaction(self):
        selected_row = self.reactions_table.currentRow()
        if selected_row >= 0:
            item = self.reactions_table.item(selected_row, 0)
            type_item = self.reactions_table.item(selected_row, 1)
            if not item or not type_item:
                return
            reaction_id = item.data(Qt.ItemDataRole.UserRole)
            reaction_text = item.text()
            reaction_type = type_item.text()

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
            item = self.reactions_table.item(selected_row, 0)
            if not item:
                return
            reaction_id = item.data(Qt.ItemDataRole.UserRole)
            reaction_text = item.text()
            
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

        # Clear suggestion tracking dictionaries to avoid stale data
        self._last_suggested_colors = {}
        self._last_suggested_names = {}
        self._last_formulas = {}
        self._last_state_abbrs = {}

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
            reaction_item = QTableWidgetItem(ChemLabParser.convert_arrows_to_unicode(reaction['reaction_text']))
            reaction_item.setFlags(reaction_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
            reaction_item.setData(Qt.ItemDataRole.UserRole, reaction['id'])  # Store ID
            self.reactions_table.setItem(row, 0, reaction_item)
            
            # Reaction type
            type_item = QTableWidgetItem(reaction.get('reaction_type', 'Unknown'))
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
            self.reactions_table.setItem(row, 1, type_item)
        
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
            formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
            formula_item.setData(Qt.ItemDataRole.UserRole, compound['id'])  # Store ID for updates
            self.compounds_table.setItem(row, 0, formula_item)
            
            # Type (not editable)
            type_item = QTableWidgetItem(compound['type'])
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag(Qt.ItemFlag.ItemIsEditable))
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
        """Handle resize events to keep overlay filling the central widget"""
        if obj == self.central_widget and event.type() == event.Type.Resize:
            if self.view_overlay:
                self.view_overlay.setGeometry(self.central_widget.rect())
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
    
    def create_compound_overlay(self, formula, compound_name, compound_type, compound_color, compound_state, compound_notes):
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

        info_group = self._create_basic_info_group(formula, compound_name, compound_type, compound_color, compound_state, compound_notes)
        overlay_layout.addWidget(info_group)

        self._add_molar_mass_section(overlay_layout, formula)
        self._add_back_button(overlay_layout)

        self.compound_overlay.raise_()
        self.compound_overlay.show()

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
    
    def on_compound_back_clicked(self):
        """Handle back button in compound overlay"""
        self.close_compound_overlay()
        # If we came from view overlay, it should still be visible underneath
        # Just make sure it gets focus again
        if self.view_overlay:
            self.view_overlay.raise_()
            self.view_overlay.setFocus()

def main():
    app = QApplication(sys.argv)
    window = ChemLab()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
