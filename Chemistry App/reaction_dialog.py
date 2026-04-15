import logging

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRegularExpression
from PyQt6.QtGui import (QKeySequence, QShortcut, QIcon,
                         QRegularExpressionValidator)
from PyQt6.QtWidgets import (QDialog, QVBoxLayout,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QLineEdit, QPushButton, QLabel, QSplitter,
                             QGroupBox, QHeaderView, QMessageBox, QComboBox)
from mendeleev import element

from ChemicalKeyboard import ChemicalKeyboard
from chemlab_parser import ChemLabParser
from compound_learner import CompoundLearner
from constants import (
    ARROWS, COMMON_REACTION_TYPES, DEFAULT_COLOR,
    COMPOUNDS_COLUMNS, ELEMENTS_COLUMNS, SUBSCRIPT_DIGITS, STATE_NAMES,
    ADD_REACTION_BTN_TEXT, ICON_PATH
)

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

    def __init__(self, db, reaction, reaction_type, heat_value=None, heat_type=None, current_reaction_id=None, compounds_data=None):
        super().__init__()
        self.db = db
        self.reaction = reaction
        self.reaction_type = reaction_type
        self.heat_value = heat_value
        self.heat_type = heat_type
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
                self.db.update_reaction(reaction_id, self.reaction, self.reaction_type, self.heat_value, self.heat_type)
            else:
                reaction_id = self.db.add_reaction(self.reaction, self.reaction_type, self.heat_value, self.heat_type)

            self.progress.emit("Extracting elements...")
            self._save_elements(self.reaction)

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
                    # Normalize first to strip coefficients and state symbols
                    clean_formula = ChemLabParser.normalize_formula(formula)
                    state, _ = ChemLabParser.extract_state_symbol(formula)
                    # Look up user-entered data from table
                    key = (clean_formula, comp_type)
                    user_data = self.compounds_data.get(key, {})
                    name = user_data.get('name', '')
                    color = user_data.get('color', '')
                    notes = user_data.get('notes', '')
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


class ReactionDialog(QDialog):
    """Dialog for adding or editing chemical reactions."""
    reaction_saved = pyqtSignal(bool, str, int)  # success, message, reaction_id
    
    def __init__(self, db, reaction_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_reaction_id = reaction_id
        self.setWindowTitle("Edit Reaction" if reaction_id else "Add New Reaction")
        self.setGeometry(100, 100, 1100, 500)
        self.setWindowIcon(QIcon(ICON_PATH))

        self.setModal(True)

        # Initialize CompoundLearner (trained on all compounds from DB)
        self.compound_learner = CompoundLearner(db=self.db)
        self._train_compound_learner()

        # Data storage
        self.elements_data = {}
        self.keyboard_window = None
        self.last_focused_widget = None

        # UI Elements (reaction entry section)
        self.reaction_entry = QLineEdit()
        btn_text = "💾 Update Reaction" if self.current_reaction_id else ADD_REACTION_BTN_TEXT
        self.add_reaction_btn = QPushButton(btn_text)
        self.clear_btn = QPushButton("🗑 Clear")
        self.cancel_btn = QPushButton("❌ Cancel")
        self.keyboard_btn = QPushButton("🧪 Chemical Keyboard")
        self.reaction_type_cb = QComboBox()
        self.heat_value_entry = QLineEdit()
        self.heat_type_cb = QComboBox()
        self.elements_table = QTableWidget()
        self.compounds_table = QTableWidget()

        self._worker = None
        self._preview_worker = None  # Worker for live preview threading

        # Clear suggestion tracking dictionaries to avoid stale data
        self._last_suggested_colors = {}
        self._last_suggested_names = {}
        self._last_formulas = {}
        self._last_state_abbrs = {}
        self._target_reaction_id = None  # Track reaction to jump to after load

        # Debounce timer for preview updates (prevents UI lag)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview_tables)

        # Debounce timer for validation (prevents typing lag)
        self.validation_timer = QTimer(self)
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._do_validation)
        self._pending_validation = False

        # Ctrl+S shortcut for saving reaction
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.add_reaction)

        # Ctrl+K shortcut for chemical keyboard
        self.keyboard_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.keyboard_shortcut.activated.connect(self.open_keyboard)

        # Ctrl+N shortcut for new/clear reaction in dialog
        self.new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut.activated.connect(self._on_ctrl_n_dialog)

        # Initialize UI
        self.init_ui()
        self.update_reaction_type_combobox()
        # Load reaction data if editing
        if self.current_reaction_id:
            self.load_reaction_data(self.current_reaction_id)

    def load_reaction_data(self, reaction_id):
        """Load reaction data from database by ID for editing"""
        try:
            reaction = self.db.get_reaction_by_id(reaction_id)
            if not reaction:
                QMessageBox.warning(self, "Load Error", f"Reaction {reaction_id} not found")
                return

            # Set reaction text
            self.reaction_entry.setText(reaction.get('reaction_text', ''))

            # Set reaction type
            reaction_type = reaction.get('reaction_type', '')
            if reaction_type:
                self.reaction_type_cb.setCurrentText(reaction_type)

            # Set heat value and type
            heat_value = reaction.get('heat_value', '')
            heat_type = reaction.get('heat_type', '')
            logging.info(f"[LoadReaction] heat_value={heat_value}, heat_type={heat_type}")
            logging.info(f"[LoadReaction] heat_type_cb items: {[self.heat_type_cb.itemText(i) for i in range(self.heat_type_cb.count())]}")
            if heat_value:
                self.heat_value_entry.setText(str(heat_value))
            if heat_type:
                # Capitalize for case-insensitive matching (database stores lowercase)
                heat_type_display = heat_type.capitalize()
                self.heat_type_cb.setCurrentText(heat_type_display)
                logging.info(f"[LoadReaction] Set heat_type_cb to: {self.heat_type_cb.currentText()} (from '{heat_type}')")

            # Parse and populate tables
            reaction_text = reaction.get('reaction_text', '')
            compounds = ChemLabParser.extract_compounds_from_reaction(reaction_text)
            elements_list = ChemLabParser.extract_elements_from_reaction(reaction_text)

            # Convert elements list to dictionary format for the table
            self.elements_data = {}
            for element_symbol in elements_list:
                try:
                    elem = element(element_symbol)
                    self.elements_data[element_symbol] = {
                        'name': elem.name,
                        'atomic_number': elem.atomic_number
                    }
                except (ValueError, KeyError):
                    self.elements_data[element_symbol] = {
                        'name': 'Unknown',
                        'atomic_number': 0
                    }

            # Update elements table
            self._update_elements_table()

            # Get compound data from database for name/color/state/notes
            db_compounds = self.db.get_compounds_for_reaction(reaction_id)
            db_compound_map = {c['formula']: c for c in db_compounds}

            # Build formatted compounds list
            formatted_compounds = []
            for comp in compounds:
                formula = comp['formula']
                db_comp = db_compound_map.get(formula, {})
                formatted_compounds.append({
                    'formula': formula,
                    'type': comp['type'],
                    'name': db_comp.get('name', comp.get('name', '')),
                    'state': db_comp.get('state', comp.get('state', '')),
                    'color': db_comp.get('color', comp.get('color', '')),
                    'notes': db_comp.get('notes', comp.get('notes', ''))
                })

            # Update compounds table
            self._update_table_incremental(formatted_compounds)

            logging.info(f"Loaded reaction {reaction_id}: {reaction_text}")

        except Exception as e:
            logging.error(f"Failed to load reaction {reaction_id}: {e}")
            QMessageBox.warning(self, "Load Error", f"Failed to load reaction: {e}")

    def init_ui(self):
        # Main layout for dialog
        main_layout = QVBoxLayout(self)

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

        # Heat value input (optional) - for exothermic/endothermic
        heat_layout = QHBoxLayout()
        heat_layout.addWidget(QLabel("ΔH (kJ/mol):"))
        self.heat_value_entry.setPlaceholderText("e.g., 286 (sign determined by type)")
        # Only allow positive numbers (0-9 and decimal point)
        self.heat_value_entry.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9]*\.?[0-9]*")))
        heat_layout.addWidget(self.heat_value_entry, 1)

        # Heat type combobox (optional)
        self.heat_type_cb.addItems(["", "Exothermic", "Endothermic"])
        self.heat_type_cb.setCurrentText("")
        self.heat_type_cb.setEditable(False)  # Prevent typing - only select from list
        heat_layout.addWidget(self.heat_type_cb)

        reaction_layout.addLayout(heat_layout)
        reaction_group.setLayout(reaction_layout)
        main_layout.addWidget(reaction_group)

        # Tables section with splitter
        self.create_compound_tables(main_layout)

        # Dialog buttons
        self.create_bottom_section(main_layout)

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

        # Clear button (left side)
        self.clear_btn.clicked.connect(self.clear_form)
        self.clear_btn.setMinimumHeight(40)
        bottom_layout.addWidget(self.clear_btn)

        bottom_layout.addStretch()

        # Cancel button (middle)
        self.cancel_btn.clicked.connect(self.cancel_dialog)
        self.cancel_btn.setMinimumHeight(40)
        bottom_layout.addWidget(self.cancel_btn)

        # Add/Update reaction button (right side)
        self.add_reaction_btn.clicked.connect(self.add_reaction)
        self.add_reaction_btn.setEnabled(False)
        self.add_reaction_btn.setMinimumHeight(40)
        bottom_layout.addWidget(self.add_reaction_btn)

        parent_layout.addLayout(bottom_layout)

    def clear_form(self):
        """Clear the form after confirmation if compounds exist"""
        # Check if there's at least 1 compound
        if self.compounds_table.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                "Clear Form",
                "Are you sure you want to clear the form? All entered data will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Clear all fields
        self.reaction_entry.clear()
        self.reaction_type_cb.setCurrentText("")
        self.heat_value_entry.clear()
        self.heat_type_cb.setCurrentText("")
        self.elements_table.setRowCount(0)
        self.compounds_table.setRowCount(0)

        # Clear tracking dicts
        self._last_suggested_colors = {}
        self._last_suggested_names = {}
        self._last_formulas = {}
        self._last_state_abbrs = {}

        # Reset reaction ID to add mode
        self.current_reaction_id = None
        self.add_reaction_btn.setText(ADD_REACTION_BTN_TEXT)
        self.setWindowTitle("Add New Reaction")

    def cancel_dialog(self):
        """Cancel and close dialog, clearing edit state"""
        self.current_reaction_id = None
        self.reject()

    def handle_reaction_saved(self, reaction, reaction_type, heat_value, heat_type, compounds_data, reaction_id):
        """Handle reaction saved from dialog"""
        # Create worker to save reaction
        worker = SaveReactionWorker(
            self.db, reaction, reaction_type, heat_value, heat_type,
            reaction_id if reaction_id else None, compounds_data
        )
        worker.finished.connect(self.on_reaction_worker_finished)
        worker.start()

    def on_reaction_worker_finished(self, success, message, reaction_id=None):
        """Handle reaction worker completion"""
        if success:
            try:
                self.reaction_saved.emit(True, message, reaction_id or 0)
                self.accept()
            except Exception as e:
                logging.error(f"[WorkerFinished] Error after save: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Saved but error occurred: {e}")
                self.accept()
        else:
            QMessageBox.critical(self, "Save Error", message)

    def on_reaction_key_press(self, event):
        """Handle key press events for subscript conversion and bracket auto-complete"""
        key = event.key()
        cursor = self.reaction_entry.cursorPosition()
        text = self.reaction_entry.text()
        selected = self.reaction_entry.selectedText()

        # Handle bracket auto-complete for opening brackets
        if key == Qt.Key.Key_ParenLeft:  # (
            if selected:
                start = cursor - len(selected)
                self.reaction_entry.deselect()
                new_text = text[:start] + "(" + selected + ")" + text[cursor:]
                self.reaction_entry.setText(new_text)
                self.reaction_entry.setSelection(start + 1, len(selected))
            else:
                # Auto-complete with ) and place cursor inside
                new_text = text[:cursor] + "()" + text[cursor:]
                self.reaction_entry.setText(new_text)
                self.reaction_entry.setCursorPosition(cursor + 1)
            return

        if key == Qt.Key.Key_BracketLeft:  # [
            if selected:
                # Wrap selected text with brackets - deselect first to avoid duplication
                start = cursor - len(selected)
                self.reaction_entry.deselect()
                new_text = text[:start] + "[" + selected + "]" + text[cursor:]
                self.reaction_entry.setText(new_text)
                self.reaction_entry.setSelection(start + 1, len(selected))
            else:
                # Auto-complete with ] and place cursor inside
                new_text = text[:cursor] + "[]" + text[cursor:]
                self.reaction_entry.setText(new_text)
                self.reaction_entry.setCursorPosition(cursor + 1)
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
        """Enable/disable add button based on arrow presence and trigger debounced validation"""
        reaction = self.reaction_entry.text().strip()
        has_arrow = any(arrow in reaction for arrow in ARROWS)

        # Simple check for arrow - don't validate synchronously to avoid lag
        if has_arrow and reaction:
            # Only enable button immediately if it has arrow, validate asynchronously
            self.add_reaction_btn.setEnabled(True)
            # Trigger debounced validation
            self.validation_timer.stop()
            self.validation_timer.start(3000)  # 3s delay for validation
        else:
            # No arrow - reset style, disable add button
            self.reaction_entry.setStyleSheet("")
            self.add_reaction_btn.setEnabled(has_arrow and len(reaction) > 0)

        # Always update preview (debounced) to show compound changes even without arrow
        self.preview_timer.stop()
        self.preview_timer.start(1000)

    def _do_validation(self):
        """Perform validation asynchronously to avoid typing lag"""
        reaction = self.reaction_entry.text().strip()
        has_arrow = any(arrow in reaction for arrow in ARROWS)

        if has_arrow and reaction:
            validation_result = ChemLabParser.validate_reaction(reaction)
            if not validation_result['valid']:
                # Show validation error
                self.reaction_entry.setStyleSheet("border: 2px solid red;")
                self.add_reaction_btn.setEnabled(False)
            else:
                # Valid reaction
                self.reaction_entry.setStyleSheet("")
                self.add_reaction_btn.setEnabled(True)

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
                    logging.info(f"[Merge] Found existing at key={key}: {existing}")
                    merged_compound = self._build_existing_compound(existing, clean_formula, ctype, detected_state,
                                                                    detected_state_abbr)
                    logging.info(f"[Merge] Merged compound: {merged_compound}")
                else:
                    # New compound - use worker suggestions
                    merged_compound = compound
                    logging.info(f"[Merge] New compound (no existing): {merged_compound}")

                new_compounds.append(merged_compound)
                self._track_suggestions(len(new_compounds) - 1, clean_formula, detected_state_abbr, merged_compound)

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

    def _build_existing_compound(self, existing, clean_formula, ctype, detected_state, detected_state_abbr):
        """Build compound data from existing row data"""
        prev_formula = existing.get('prev_formula')
        prev_state = existing.get('prev_state_abbr')
        context_changed = (prev_formula != clean_formula) or (prev_state != detected_state_abbr)
        logging.info(f"[BuildCompound] Row {existing.get('row', '?')}: prev='{prev_formula}' -> curr='{clean_formula}', changed={context_changed}")

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

    def _get_suggestion_or_preserve(self, context_changed, was_suggested, clean_formula,
                                    detected_state_abbr, current_value, is_color):
        """Get new suggestion if context changed and value was auto-suggested/PubChem, or if empty, else preserve"""
        field_type = 'color' if is_color else 'name'
        is_empty = not current_value or not current_value.strip()
        logging.info(f"[Suggestion] {field_type}: changed={context_changed}, was_suggested={was_suggested}, is_empty={is_empty}, current='{current_value}'")
        
        # Get new suggestion if: (context changed and was auto-suggested/PubChem) OR current is empty
        # was_suggested includes both learner-suggested AND PubChem-fetched names
        if (context_changed and was_suggested) or is_empty:
            if is_color:
                result = self._get_suggested_color(clean_formula, detected_state_abbr)
                logging.info(f"[Suggestion] {field_type} new suggestion: '{result}'")
                return result
            result = self._get_suggested_name(clean_formula) or ''
            logging.info(f"[Suggestion] {field_type} new suggestion: '{result}'")
            return result
        logging.info(f"[Suggestion] {field_type} preserving: '{current_value}'")
        return current_value

    def _track_suggestions(self, row_idx, clean_formula, detected_state_abbr, compound_data):
        """Track what we're suggesting for this row - only track if actually applied to cell"""
        # Only track color if it matches what we suggested (cell wasn't manually edited)
        current_color = compound_data.get('color', '')
        self._last_suggested_colors[row_idx] = current_color
        
        # For name, check if the cell actually has this value - if not, user edited it, don't track
        name_in_data = compound_data.get('name', '')
        name_item = self.compounds_table.item(row_idx, 2)  # Name column
        actual_name_in_cell = name_item.text() if name_item else ''
        
        # Only track as 'suggested' if the cell actually contains this name
        # If cell has a different value, user manually edited it - preserve that
        if actual_name_in_cell == name_in_data:
            self._last_suggested_names[row_idx] = name_in_data
        # else: don't update tracking - keep previous suggested value
        
        self._last_formulas[row_idx] = clean_formula
        self._last_state_abbrs[row_idx] = detected_state_abbr

    def _update_table_incremental(self, new_compounds):
        """Update table - set exact row count and update all cells."""
        self.compounds_table.setRowCount(len(new_compounds))

        for row, compound in enumerate(new_compounds):
            logging.info(f"[UpdateTable] Row {row}: compound dict = {compound}")
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
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
        """Update state cell (column 4) - read-only, must use formula suffix."""
        display_state = STATE_NAMES.get(state_value, state_value)
        self._get_or_create_item(row, 4, display_state, editable=False)

    def _update_notes_cell(self, row, notes):
        """Update notes cell (column 5) - preserve user data, only fill if empty."""
        item = self.compounds_table.item(row, 5)
        if not item:
            self.compounds_table.setItem(row, 5, QTableWidgetItem(notes))
        # If item exists, preserve user-entered notes

    def _update_name_cell(self, row, suggested_name):
        """Update name cell (column 2) - preserve user data unless it was auto-suggested or empty."""
        name_item = self.compounds_table.item(row, 2)
        prev_suggested = getattr(self, '_last_suggested_names', {}).get(row)
        current = name_item.text() if name_item else ''
        
        is_empty = not current.strip()
        was_auto_suggested = current == prev_suggested
        
        import inspect
        caller = inspect.stack()[1].function if len(inspect.stack()) > 1 else 'unknown'
        logging.info(f"[UpdateName] Row {row}: caller={caller}, current='{current}', prev_suggested='{prev_suggested}', new='{suggested_name}', is_empty={is_empty}, was_auto={was_auto_suggested}")
        
        if not name_item:
            self.compounds_table.setItem(row, 2, QTableWidgetItem(suggested_name))
            # Track this as the suggested name (includes PubChem names)
            self._last_suggested_names[row] = suggested_name
            logging.info(f"[UpdateName] Row {row}: Created new name cell with '{suggested_name}'")
        elif was_auto_suggested or is_empty:
            # Was auto-suggested or empty, update with new suggestion
            name_item.setText(suggested_name)
            # Update tracking so this new name (including PubChem) is now the "suggested" baseline
            self._last_suggested_names[row] = suggested_name
            logging.info(f"[UpdateName] Row {row}: Updated name to '{suggested_name}' (was_auto={was_auto_suggested}, is_empty={is_empty})")
        else:
            logging.info(f"[UpdateName] Row {row}: Preserving user-entered name '{current}'")

    @staticmethod
    def _should_update_color(color_item: QTableWidgetItem | None, suggested_color: str,
                             prev_suggested: str | None) -> bool:
        """Check if color cell should be updated based on tracking."""
        if not suggested_color:
            return False
        if not color_item:
            return True
        current = color_item.text()
        # Update if empty, default, or matches previous suggestion
        return current.strip() == '' or current.lower() == DEFAULT_COLOR.lower() or current == prev_suggested

    def _update_color_cell(self, row, suggested_color):
        """Update color cell (column 3) - preserve user data unless it was auto-suggested."""
        color_item = self.compounds_table.item(row, 3)
        prev_suggested = getattr(self, '_last_suggested_colors', {}).get(row)
        if not self._should_update_color(color_item, suggested_color, prev_suggested):
            return

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
        formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        formula_item.setData(Qt.ItemDataRole.UserRole, compound['id'])
        self.compounds_table.setItem(row, 0, formula_item)

        # Type (not editable)
        type_item = QTableWidgetItem(compound['type'])
        # noinspection PyTypeChecker
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
        except Exception as e:
            logging.error(f"Failed to train compound learner: {e}")

    def _get_suggested_name(self, formula):
        """Get suggested name for a compound formula"""
        name = self.compound_learner.get_name(formula)
        logging.info(f"[NameSuggestion] Formula '{formula}' -> '{name}'")
        return name

    def _get_suggested_color(self, formula, state):
        """Get suggested color for a compound based on formula and state"""
        color = self.compound_learner.get_color(formula, state)
        return color

    def _make_row_readonly(self, row):
        """Make all cells in a row readonly"""
        for col in range(6):
            item = self.compounds_table.item(row, col)
            if item:
                # noinspection PyTypeChecker
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _load_and_display_elements(self, compounds):
        """Extract elements from compounds and display them"""
        reaction_elements = ChemLabParser.extract_elements_from_compounds(compounds)
        elements_data = ChemLabParser.load_elements_data(reaction_elements)
        self.update_elements_table_preview(elements_data)

    def add_reaction(self):
        """Add or update a reaction in database with auto-balancing (threaded)"""
        reaction = self.reaction_entry.text().strip()
        reaction_type = self.reaction_type_cb.currentText().strip() or 'Unknown'

        # Parse heat value (optional) - can be empty or a positive number
        heat_value = None
        heat_text = self.heat_value_entry.text().strip()
        if heat_text:
            try:
                heat_value = float(heat_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid Heat Value", "Heat value must be a number (e.g., 286)")
                return

        # Get heat type (optional) - Exothermic, Endothermic, or empty
        heat_type = self.heat_type_cb.currentText().strip()
        if heat_type:
            heat_type = heat_type.lower()  # Store as 'exothermic' or 'endothermic'
        logging.info(f"[AddReaction] Saving heat_value={heat_value}, heat_type={heat_type}")

        # Basic check for arrow
        validate = self._validate_reaction_input(reaction)
        if not reaction or not validate:
            return

        # Check for duplicate reactions (skip if in edit mode)
        if not self.current_reaction_id:
            existing_reactions = [r['reaction_text'] for r in self.db.get_all_reactions()]
            is_duplicate, matching_reaction = ChemLabParser.is_duplicate_reaction(reaction, existing_reactions)
            if is_duplicate:
                logging.warning("Duplicate reaction detected!")
                reply = QMessageBox.question(
                    self,
                    "Duplicate Reaction Found",
                    f"A reaction with the same reactants and products already exists:\n\n{matching_reaction}\n\nDo you want to save anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
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

        # Create and start worker thread
        self._worker = SaveReactionWorker(
            self.db, reaction, reaction_type, heat_value, heat_type, self.current_reaction_id, compounds_data
        )
        self._worker.balanced_reaction.connect(self._on_balanced_reaction)
        self._worker.finished.connect(self._on_save_finished)
        self._worker.start()

    def _on_balanced_reaction(self, balanced):
        """Handle balanced reaction from worker thread"""
        # Store the balanced reaction for the toast notification
        self._last_balanced_reaction = balanced
        # Update the entry with balanced version
        self.reaction_entry.blockSignals(True)
        self.reaction_entry.setText(balanced)
        self.reaction_entry.blockSignals(False)

    def _on_save_finished(self, success, error_message, reaction_id):
        """Handle save completion from worker thread"""
        self.add_reaction_btn.setEnabled(True)
        self.add_reaction_btn.setText(
            "💾 Update Reaction" if self.current_reaction_id else ADD_REACTION_BTN_TEXT
        )

        if success:
            # Set target reaction ID to jump to its page after loading
            self._target_reaction_id = reaction_id
            self._finalize_add_reaction()
            # Update the learner with new data
            self._train_compound_learner()
            self.update_reaction_type_combobox()
        else:
            logging.error(f"Failed to add/update reaction: {error_message}")
            QMessageBox.critical(self, "Error", f"Failed to save reaction: {error_message}")

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

    def _get_table_text(self, row, col):
        """Get text from table cell, return empty string if cell doesn't exist"""
        item = self.compounds_table.item(row, col)
        return item.text() if item else ''

    def _finalize_add_reaction(self, reaction_id=None):
        """Emit signal and close dialog after successful save"""
        self.reaction_saved.emit(True, "Reaction saved successfully!", reaction_id or 0)
        self.accept()

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

        except Exception as e:
            logging.error(f"Failed to update reaction type combobox: {e}")

    def reset_form_to_normal(self):
        """Reset the form back to normal add mode"""
        self.reaction_entry.clear()
        self.reaction_entry.setReadOnly(False)
        self.reaction_type_cb.setCurrentText("")
        self.reaction_type_cb.setEnabled(True)
        self.heat_value_entry.clear()
        self.heat_type_cb.setCurrentText("")
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

    def _on_ctrl_n_dialog(self):
        """Handle Ctrl+N in dialog - check for unsaved changes then clear or ask"""
        logging.info("[Ctrl+N Dialog] Checking for unsaved changes")

        # Check if there's any data entered (reaction text or compounds)
        has_reaction = bool(self.reaction_entry.text().strip())
        has_compounds = self.compounds_table.rowCount() > 0

        if has_reaction or has_compounds:
            # Check if this is an edit of existing reaction or new
            if self.current_reaction_id:
                # Editing existing - ask if you want to save changes
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    "You have unsaved changes. Save before clearing?",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Save:
                    self.add_reaction()  # This will save and emit signal
                    return
                elif reply == QMessageBox.StandardButton.Cancel:
                    return
                # Discard = continue to clear
            else:
                # New reaction - just ask to confirm clear
                reply = QMessageBox.question(
                    self,
                    "Clear Form",
                    "Clear the current reaction entry?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        # Clear the form (acts like Clear button)
        self.clear_form()

    def on_compound_item_changed(self, item):
        """Handle compound table item changes - skip read-only columns"""
        # Only update editable columns: 2=Name, 3=Color, 5=Notes (skip 0=Formula, 1=Type, 4=State)
        if item.row() >= 0 and item.column() in [2, 3, 5]:
            formula_item = self.compounds_table.item(item.row(), 0)
            if not formula_item:
                return

            compound_id = formula_item.data(Qt.ItemDataRole.UserRole)
            if compound_id:
                column_name = COMPOUNDS_COLUMNS[item.column()].lower()
                value = item.text()

                # Update database
                update_data = {column_name: value}
                self.db.update_compound(compound_id, **update_data)

    def _update_elements_table(self):
        """Update the elements table"""
        self.elements_table.setRowCount(len(self.elements_data))

        for row, (symbol, data) in enumerate(self.elements_data.items()):
            self.elements_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.elements_table.setItem(row, 1, QTableWidgetItem(data['name']))
            self.elements_table.setItem(row, 2, QTableWidgetItem(str(data['atomic_number'])))

    def closeEvent(self, event):
        """Handle dialog close - just close keyboard if open, don't close DB"""
        try:
            if self.keyboard_window:
                self.keyboard_window.close()
        except Exception as e:
            logging.error(f"Error during dialog close: {e}")

        event.accept()
