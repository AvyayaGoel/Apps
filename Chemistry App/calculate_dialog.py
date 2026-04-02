"""Calculate dialog for chemistry calculations."""
import logging
import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QLineEdit, QComboBox, QScrollArea,
    QWidget, QDoubleSpinBox, QTableWidgetItem, QTableWidget, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QCoreApplication
from PyQt6.QtGui import QFont
from mendeleev import element as get_element
from chemlab_parser import ChemLabParser
from constants import STATE_NAMES, SUBSCRIPT_DIGITS


class CalculateDialog(QDialog):
    """Dialog for selecting calculation type and reference."""

    # Signal emitted when a reaction is selected from the main window
    reaction_selected = pyqtSignal(dict)
    # Signal emitted when selection is canceled
    selection_cancelled = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.scroll = QScrollArea()
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.title_label = QLabel("What would you like to calculate in reference to?")
        self.selection_group = QGroupBox("Select Reference Type")
        self.formula_btn = QPushButton("🧪 Formula (from Saved Reactions)")
        self.compound_btn = QPushButton("⚗️ Specific Compound")
        self.compound_entry_group = QGroupBox("Enter Compound")
        self.compound_formula_entry = QLineEdit()
        self.compound_state_combo = QComboBox()
        self.compound_property_combo = QComboBox()
        self.value_unit_combo = QComboBox()
        self.compound_value_spin = QDoubleSpinBox()
        self.compound_purity_spin = QDoubleSpinBox()
        self.conditions_combo = QComboBox()
        self.compound_temp_spin = QDoubleSpinBox()
        self.temp_unit_combo = QComboBox()
        self.compound_pressure_spin = QDoubleSpinBox()
        self.pressure_unit_combo = QComboBox()
        self.compound_volume_spin = QDoubleSpinBox()
        self.volume_unit_combo = QComboBox()
        self.compound_conc_spin = QDoubleSpinBox()
        self.conc_unit_combo = QComboBox()
        self.reaction_display = QLabel("")
        self.continue_btn = QPushButton("Continue →")
        self.back_btn = QPushButton("← Back")
        self.status_label = QLabel("Select an option above to continue")
        self.dynamic_area = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_area)
        self.compound_buttons = {}
        self.configured_label = QLabel("No compounds configured yet - Choose Reactants OR Products side")
        self.to_calculations_btn = QPushButton("Continue to Calculations →")
        self.property_combo = QComboBox()
        self.value_spin = QDoubleSpinBox()
        self.unit_label = QLabel("mol")
        self.purity_spin = QDoubleSpinBox()
        self.temp_spin = QDoubleSpinBox()
        self.pressure_spin = QDoubleSpinBox()
        self.volume_spin = QDoubleSpinBox()
        self.conc_spin = QDoubleSpinBox()
        self.results_table = QTableWidget()
        self.db = db
        self.parent_window = parent
        self.selected_reaction = None
        self.selected_compound = None
        self.compound_data = {}  # Store compound properties
        self.configured_side = None  # 'reactants' or 'products' - only one side allowed
        self.compound_side_map = {}  # Maps compound name -> 'reactants' or 'products'
        self.current_mode = None  # 'formula' or 'compound'
        self.setWindowTitle("Calculate - Select Reference")
        self.setGeometry(300, 300, 450, 400)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        # Main scroll area for dynamic content
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self.main_layout.setSpacing(15)

        self.create_initial_view()

        self.scroll.setWidget(self.main_widget)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.scroll)

    def create_initial_view(self):
        """Create the initial selection view."""
        # Store title label as instance variable for dynamic updates
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.title_label)

        # Selection group
        selection_layout = QVBoxLayout()
        selection_layout.setSpacing(10)

        # Formula button
        self.formula_btn.setMinimumHeight(50)
        self.formula_btn.setFont(QFont("Segoe UI", 11))
        self.formula_btn.clicked.connect(self.on_formula_selected)
        selection_layout.addWidget(self.formula_btn)

        # Compound button
        self.compound_btn.setMinimumHeight(50)
        self.compound_btn.setFont(QFont("Segoe UI", 11))
        self.compound_btn.clicked.connect(self.on_compound_selected)
        selection_layout.addWidget(self.compound_btn)

        self.selection_group.setLayout(selection_layout)
        self.main_layout.addWidget(self.selection_group)

        # Compound Entry Section (hidden initially)
        compound_entry_layout = QVBoxLayout()

        formula_layout = QHBoxLayout()
        formula_label = QLabel("Formula:")
        self.compound_formula_entry.setPlaceholderText("e.g., H₂O, NaCl, CO₂")
        self.compound_formula_entry.textChanged.connect(self.on_compound_formula_changed)
        # Add key press event handler for subscript conversion
        self.compound_formula_entry.keyPressEvent = self.on_compound_key_press
        formula_layout.addWidget(formula_label)
        formula_layout.addWidget(self.compound_formula_entry)
        compound_entry_layout.addLayout(formula_layout)

        state_layout = QHBoxLayout()
        state_label = QLabel("State:")
        self.compound_state_combo.addItems(list(set(STATE_NAMES.values())))
        self.compound_state_combo.setCurrentText(STATE_NAMES.get('s', 'Solid'))
        state_layout.addWidget(state_label)
        state_layout.addWidget(self.compound_state_combo)
        compound_entry_layout.addLayout(state_layout)

        # Property type selector for compound mode
        prop_layout = QHBoxLayout()
        prop_label = QLabel("Property:")
        self.compound_property_combo.addItems(["Moles", "Weight (grams)"])
        prop_layout.addWidget(prop_label)
        prop_layout.addWidget(self.compound_property_combo)
        
        # Unit selector for value
        self.value_unit_combo.addItems(["mol", "g", "kg", "mg"])
        self.compound_property_combo.currentTextChanged.connect(self.on_compound_property_changed)
        prop_layout.addWidget(self.value_unit_combo)
        compound_entry_layout.addLayout(prop_layout)

        # Value input for compound mode
        val_layout = QHBoxLayout()
        val_label = QLabel("Value:")
        self.compound_value_spin.setRange(0, 999999)
        self.compound_value_spin.setDecimals(4)
        self.compound_value_spin.setValue(1.0)
        val_layout.addWidget(val_label)
        val_layout.addWidget(self.compound_value_spin)
        compound_entry_layout.addLayout(val_layout)

        # Purity input for compound mode
        purity_layout = QHBoxLayout()
        purity_label = QLabel("Purity (%):")
        self.compound_purity_spin.setRange(0, 100)
        self.compound_purity_spin.setDecimals(2)
        self.compound_purity_spin.setValue(100.0)
        purity_layout.addWidget(purity_label)
        purity_layout.addWidget(self.compound_purity_spin)
        compound_entry_layout.addLayout(purity_layout)

        # Temperature/Pressure Mode selector (STP, NTP, Custom)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Conditions:")
        self.conditions_combo.addItems(["Custom", "STP", "NTP"])
        self.conditions_combo.currentTextChanged.connect(self.on_conditions_changed)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.conditions_combo)
        compound_entry_layout.addLayout(mode_layout)

        # Temperature input for compound mode (with unit selector)
        temp_layout = QHBoxLayout()
        temp_label = QLabel("Temperature:")
        self.compound_temp_spin.setRange(0, 999999)
        self.compound_temp_spin.setDecimals(2)
        self.compound_temp_spin.setValue(298.15)
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.compound_temp_spin)
        
        # Temperature unit selector
        self.temp_unit_combo.addItems(["K", "°C", "°F"])
        self.temp_unit_combo.currentTextChanged.connect(self.on_temp_unit_changed)
        temp_layout.addWidget(self.temp_unit_combo)
        compound_entry_layout.addLayout(temp_layout)

        # Pressure input for compound mode (with unit selector)
        pressure_layout = QHBoxLayout()
        pressure_label = QLabel("Pressure:")
        self.compound_pressure_spin.setRange(0, 999999)
        self.compound_pressure_spin.setDecimals(4)
        self.compound_pressure_spin.setValue(1.0)
        pressure_layout.addWidget(pressure_label)
        pressure_layout.addWidget(self.compound_pressure_spin)
        
        # Pressure unit selector
        self.pressure_unit_combo.addItems(["atm", "Pa", "kPa", "mmHg", "torr", "psi", "bar"])
        pressure_layout.addWidget(self.pressure_unit_combo)
        compound_entry_layout.addLayout(pressure_layout)

        # Volume input for compound mode (with unit selector)
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Volume:")
        self.compound_volume_spin.setRange(0, 999999)
        self.compound_volume_spin.setDecimals(4)
        self.compound_volume_spin.setValue(0.0)
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.compound_volume_spin)
        
        # Volume unit selector
        self.volume_unit_combo.addItems(["L", "mL", "m³", "cm³", "ft³", "gal"])
        volume_layout.addWidget(self.volume_unit_combo)
        compound_entry_layout.addLayout(volume_layout)

        # Concentration input for compound mode (with unit selector)
        conc_layout = QHBoxLayout()
        conc_label = QLabel("Concentration:")
        self.compound_conc_spin.setRange(0, 999999)
        self.compound_conc_spin.setDecimals(6)
        self.compound_conc_spin.setValue(0.0)
        conc_layout.addWidget(conc_label)
        conc_layout.addWidget(self.compound_conc_spin)
        
        # Concentration unit selector
        self.conc_unit_combo.addItems(["M", "mM", "μM", "nM", "mol/L", "mol/m³", "g/L", "mg/L", "ppm", "ppb"])
        conc_layout.addWidget(self.conc_unit_combo)
        compound_entry_layout.addLayout(conc_layout)

        self.compound_entry_group.setLayout(compound_entry_layout)
        self.compound_entry_group.setVisible(False)
        self.main_layout.addWidget(self.compound_entry_group)

        # Selected reaction display (hidden initially)
        self.reaction_display.setFont(QFont("Segoe UI", 10))
        self.reaction_display.setWordWrap(True)
        self.reaction_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reaction_display.setStyleSheet("background-color: #000000; color: #ffffff; padding: 10px; border-radius: 5px; border: 1px solid #0078d4;")
        self.reaction_display.setVisible(False)
        self.main_layout.addWidget(self.reaction_display)

        # Continue button (hidden initially)
        self.continue_btn.setMinimumHeight(40)
        self.continue_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.on_continue_clicked)
        self.continue_btn.setVisible(False)
        self.main_layout.addWidget(self.continue_btn)

        # Back button (hidden initially)
        self.back_btn.setMinimumHeight(35)
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setVisible(False)
        self.main_layout.addWidget(self.back_btn)

        # Status label
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666;")
        self.main_layout.addWidget(self.status_label)

        # Dynamic content area for compound selection or calculation buttons
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.dynamic_area)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reset_and_close)
        self.main_layout.addWidget(close_btn)

        self.main_layout.addStretch()

    def reset_and_close(self):
        """Reset dialog state and close."""
        self.reset_dialog()
        self.close()

    def reset_dialog(self):
        """Reset dialog to initial state."""
        if self.parent_window and hasattr(self.parent_window, 'disable_reaction_selection_mode'):
            self.parent_window.disable_reaction_selection_mode()

        self.current_mode = None
        self.selected_reaction = None
        self.selected_compound = None
        self.compound_data = {}
        self.configured_side = None
        self.compound_side_map = {}

        self.clear_dynamic_area()

        self.formula_btn.setEnabled(True)
        self.formula_btn.setVisible(True)
        self.compound_btn.setEnabled(True)
        self.compound_btn.setVisible(True)
        self.selection_group.setVisible(True)

        self.compound_entry_group.setVisible(False)
        self.compound_formula_entry.clear()
        self.compound_formula_entry.setStyleSheet("")
        self.compound_state_combo.setCurrentText('Solid')

        self.reaction_display.setVisible(False)
        self.continue_btn.setVisible(False)
        self.back_btn.setVisible(False)

        self.status_label.setText("Select an option above to continue")
        self.status_label.setStyleSheet("color: #666;")

    def clear_dynamic_area(self):
        """Clear all widgets from dynamic area."""
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def auto_resize(self):
        """Auto-resize dialog to fit content exactly."""
        # Process events to ensure widgets are laid out
        QCoreApplication.processEvents()
        
        # Calculate the size needed for the main widget
        self.main_widget.adjustSize()
        self.scroll.adjustSize()
        
        # Get the size hint from the main widget
        size_hint = self.main_widget.sizeHint()
        scroll_hint = self.scroll.sizeHint()
        
        # Add margins for dialog frame and some padding
        frame_margin = 50
        new_width = max(size_hint.width(), scroll_hint.width()) + frame_margin
        new_height = max(size_hint.height(), scroll_hint.height()) + frame_margin
        
        # Ensure minimum size
        min_width = 500
        min_height = 400
        new_width = max(new_width, min_width)
        new_height = max(new_height, min_height)
        
        # Resize the dialog
        current_geom = self.geometry()
        self.setGeometry(current_geom.x(), current_geom.y(), new_width, new_height)

    def on_compound_property_changed(self, property_type):
        """Update unit selector based on property type."""
        if property_type == "Moles":
            self.value_unit_combo.setCurrentText("mol")
        elif property_type == "Weight (grams)":
            self.value_unit_combo.setCurrentText("g")

    def on_conditions_changed(self, condition):
        """Handle STP/NTP/Custom condition change."""
        if condition == "STP":
            # Standard Temperature and Pressure: 273.15 K, 1 atm
            self.compound_temp_spin.setValue(273.15)
            self.compound_pressure_spin.setValue(1.0)
            self.temp_unit_combo.setCurrentText("K")
            self.pressure_unit_combo.setCurrentText("atm")
            # Hide temperature and pressure inputs when using preset
            self.compound_temp_spin.setEnabled(False)
            self.compound_pressure_spin.setEnabled(False)
            self.temp_unit_combo.setEnabled(False)
            self.pressure_unit_combo.setEnabled(False)
        elif condition == "NTP":
            # Normal Temperature and Pressure: 293.15 K (20°C), 1 atm
            self.compound_temp_spin.setValue(293.15)
            self.compound_pressure_spin.setValue(1.0)
            self.temp_unit_combo.setCurrentText("K")
            self.pressure_unit_combo.setCurrentText("atm")
            # Hide temperature and pressure inputs when using preset
            self.compound_temp_spin.setEnabled(False)
            self.compound_pressure_spin.setEnabled(False)
            self.temp_unit_combo.setEnabled(False)
            self.pressure_unit_combo.setEnabled(False)
        else:  # Custom
            # Enable temperature and pressure inputs
            self.compound_temp_spin.setEnabled(True)
            self.compound_pressure_spin.setEnabled(True)
            self.temp_unit_combo.setEnabled(True)
            self.pressure_unit_combo.setEnabled(True)

    def on_temp_unit_changed(self, unit):
        """Convert temperature value when unit changes."""
        current_value = self.compound_temp_spin.value()
        # Store the current unit before conversion
        current_unit = getattr(self, '_last_temp_unit', 'K')
        
        if current_unit == unit:
            return
            
        # Convert to Kelvin first
        if current_unit == "K":
            kelvin = current_value
        elif current_unit == "°C":
            kelvin = current_value + 273.15
        elif current_unit == "°F":
            kelvin = (current_value - 32) * 5/9 + 273.15
        else:
            kelvin = current_value
            
        # Convert from Kelvin to new unit
        if unit == "K":
            new_value = kelvin
        elif unit == "°C":
            new_value = kelvin - 273.15
        elif unit == "°F":
            new_value = (kelvin - 273.15) * 9/5 + 32
        else:
            new_value = kelvin
            
        self.compound_temp_spin.setValue(round(new_value, 2))
        self._last_temp_unit = unit

    def on_compound_formula_changed(self):
        """Handle compound formula text change."""
        is_valid = self.validate_compound_formula()
        self.continue_btn.setEnabled(is_valid)

    def on_compound_key_press(self, event):
        """Handle key press events for subscript conversion in compound entry."""
        # Check if a digit key (0-9) is pressed
        if Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9:
            cursor = self.compound_formula_entry.cursorPosition()
            text = self.compound_formula_entry.text()
            
            # Check if the character before cursor is a letter
            if cursor > 0 and text[cursor-1].isalpha():
                # Convert digit to subscript
                digit = str(event.key() - Qt.Key.Key_0)
                subscript_digit = SUBSCRIPT_DIGITS.get(digit)
                new_text = text[:cursor] + subscript_digit + text[cursor:]
                self.compound_formula_entry.setText(new_text)
                self.compound_formula_entry.setCursorPosition(cursor + 1)
                return  # Don't process the event further
        
        # Call original key press event for other keys
        QLineEdit.keyPressEvent(self.compound_formula_entry, event)

    def on_formula_selected(self):
        """Handle Formula button click."""
        if not self.parent_window:
            QMessageBox.warning(self, "Error", "Parent window not available")
            return

        if not hasattr(self.parent_window, 'enable_reaction_selection_mode'):
            QMessageBox.warning(self, "Error", "Parent window does not support selection mode")
            return

        self.current_mode = 'formula'
        self.title_label.setText("Select a Reaction from the Main Window")
        self.status_label.setText("Please select a reaction from the main window...")
        self.status_label.setStyleSheet("color: #0078d4; font-weight: bold;")

        self.parent_window.enable_reaction_selection_mode(self)

        self.formula_btn.setEnabled(False)
        self.compound_btn.setEnabled(False)
        self.continue_btn.setVisible(False)

    def on_compound_selected(self):
        """Handle Compound button click."""
        self.current_mode = 'compound'
        self.title_label.setText("Enter Compound Details")
        self.formula_btn.setVisible(False)
        self.compound_btn.setVisible(False)
        self.selection_group.setVisible(False)
        self.compound_entry_group.setVisible(True)
        self.continue_btn.setVisible(True)
        self.continue_btn.setEnabled(False)
        self.back_btn.setVisible(True)
        self.status_label.setText("Enter a valid compound formula to continue")
        self.status_label.setStyleSheet("color: #0078d4;")
        self.compound_formula_entry.setFocus()
        self.auto_resize()

    def validate_compound_formula(self):
        """Validate compound formula and show border color. Returns True if valid."""
        formula = self.compound_formula_entry.text().strip()

        if not formula:
            self.compound_formula_entry.setStyleSheet("")
            return False

        # Normalize the formula (convert subscripts to regular numbers)
        normalized = ChemLabParser.normalize_formula(formula)
        
        # Remove state symbols for validation
        clean_formula = re.sub(r'\([a-z]+\)$', '', normalized)
        
        # Extract elements using parse_formula instead of extract_elements_from_reaction
        try:
            elements_dict = ChemLabParser.parse_formula(clean_formula)
            elements = list(elements_dict.keys())
        except:
            self.compound_formula_entry.setStyleSheet("border: 2px solid red;")
            return False

        if not elements:
            self.compound_formula_entry.setStyleSheet("border: 2px solid red;")
            return False

        # Validate each element exists
        invalid_elements = []
        for elem in elements:
            try:
                get_element(elem)
            except (ValueError, KeyError):
                invalid_elements.append(elem)

        if invalid_elements:
            self.compound_formula_entry.setStyleSheet("border: 2px solid red;")
            return False
        else:
            self.compound_formula_entry.setStyleSheet("border: 2px solid green;")
            return True

    def on_reaction_selected(self, reaction):
        """Called when a reaction is selected from main window."""
        self.selected_reaction = reaction
        self.title_label.setText("Reaction Selected - Continue to Configuration")
        self.reaction_display.setText(f"Selected Reaction:\n{reaction.get('reaction_text', 'Unknown')}")
        self.reaction_display.setVisible(True)

        self.formula_btn.setVisible(False)
        self.compound_btn.setVisible(False)
        self.selection_group.setVisible(False)
        self.continue_btn.setVisible(True)
        self.continue_btn.setEnabled(True)
        self.back_btn.setVisible(True)

        self.status_label.setText("Click Continue to proceed with calculation options")
        self.status_label.setStyleSheet("color: #00aa00;")

        self.reaction_selected.emit(reaction)
        self.auto_resize()

    def on_selection_cancelled(self):
        """Called when selection is cancelled."""
        self.status_label.setText("Selection cancelled. Select an option to try again.")
        self.status_label.setStyleSheet("color: #666;")
        self.formula_btn.setEnabled(True)
        self.compound_btn.setEnabled(True)
        self.selection_cancelled.emit()

    def closeEvent(self, event):
        """Ensure selection mode is disabled when closing."""
        self.reset_dialog()
        event.accept()

    def on_continue_clicked(self):
        """Handle Continue button click."""
        self.clear_dynamic_area()

        if self.current_mode == 'formula':
            self.show_compound_selection()
        elif self.current_mode == 'compound':
            self.setup_compound_data()
            self.show_calculation_buttons()

    def show_compound_selection(self):
        """Show compound selection UI for formula mode with original reaction structure."""
        self.clear_dynamic_area()
        self.title_label.setText("Configure Compounds in Reaction")
        self.continue_btn.setVisible(False)
        self.reaction_display.setVisible(False)
        self.status_label.setText("Click on any compound to configure its properties")

        # Get compounds from reaction with structure
        reaction_text = self.selected_reaction.get('reaction_text', '')
        data = self.extract_compounds_from_reaction(reaction_text)

        compounds_group = QGroupBox("Compounds in Reaction - Click to Configure")
        compounds_layout = QVBoxLayout()
        compounds_layout.setSpacing(15)

        # Create horizontal layout for the reaction structure
        reaction_row = QHBoxLayout()
        reaction_row.setSpacing(5)
        reaction_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Track compound buttons for styling

        # Add reactants with + signs
        for i, compound in enumerate(data['reactants']):
            self.compound_side_map[compound] = 'reactants'  # Track which side
            
            # Add + sign before all except first
            if i > 0:
                plus_label = QLabel("+")
                plus_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                reaction_row.addWidget(plus_label)

            # Create compound button
            btn = QPushButton(compound)
            btn.setMinimumHeight(40)
            btn.setFont(QFont("Segoe UI", 10))
            
            # Check if this side is locked by the other side being configured
            if self.configured_side == 'products':
                # Products configured, lock all reactants
                btn.setEnabled(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #555555;
                        border: 2px solid #333333;
                        border-radius: 5px;
                        padding: 5px 10px;
                        color: #888888;
                    }
                """)
                btn.setToolTip("Reactants locked - you configured a product (only one side allowed)")
            elif compound in self.compound_data:
                # This compound is already configured
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #28a745;
                        border: 2px solid #1e7e34;
                        border-radius: 5px;
                        padding: 5px 10px;
                        color: white;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #218838;
                        border: 2px solid #1e7e34;
                    }
                """)
                btn.clicked.connect(lambda checked, c=compound: self.on_compound_clicked(c, 'reactants'))
            else:
                # Normal clickable button
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0078d4;
                        border: 2px solid #005a9e;
                        border-radius: 5px;
                        padding: 5px 10px;
                        color: white;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #005a9e;
                        border: 2px solid #0078d4;
                    }
                """)
                btn.clicked.connect(lambda checked, c=compound: self.on_compound_clicked(c, 'reactants'))
            
            reaction_row.addWidget(btn)
            self.compound_buttons[compound] = btn

        # Add arrow
        arrow_label = QLabel(data['arrow'])
        arrow_label.setFont(QFont("Segoe UI", 16))
        reaction_row.addWidget(arrow_label)

        # Add products with + signs
        for i, compound in enumerate(data['products']):
            self.compound_side_map[compound] = 'products'  # Track which side
            
            # Add + sign before all except first
            if i > 0:
                plus_label = QLabel("+")
                plus_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                reaction_row.addWidget(plus_label)

            # Create compound button
            btn = QPushButton(compound)
            btn.setMinimumHeight(40)
            btn.setFont(QFont("Segoe UI", 10))
            
            # Check if this side is locked by the other side being configured
            if self.configured_side == 'reactants':
                # Reactants configured, lock all products
                btn.setEnabled(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #555555;
                        border: 2px solid #333333;
                        border-radius: 5px;
                        padding: 5px 10px;
                        color: #888888;
                    }
                """)
                btn.setToolTip("Products locked - you configured a reactant (only one side allowed)")
            elif compound in self.compound_data:
                # This compound is already configured
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #28a745;
                        border: 2px solid #1e7e34;
                        border-radius: 5px;
                        padding: 5px 10px;
                        color: white;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #218838;
                        border: 2px solid #1e7e34;
                    }
                """)
                btn.clicked.connect(lambda checked, c=compound: self.on_compound_clicked(c, 'products'))
            else:
                # Normal clickable button
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0078d4;
                        border: 2px solid #005a9e;
                        border-radius: 5px;
                        padding: 5px 10px;
                        color: white;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #005a9e;
                        border: 2px solid #0078d4;
                    }
                """)
                btn.clicked.connect(lambda checked, c=compound: self.on_compound_clicked(c, 'products'))
            
            reaction_row.addWidget(btn)
            self.compound_buttons[compound] = btn

        # Add stretch to center the content
        reaction_row.addStretch()

        # Wrap in a widget with border - use dark background
        reaction_widget = QWidget()
        reaction_widget.setLayout(reaction_row)
        reaction_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 2px solid #0078d4;
                border-radius: 10px;
                padding: 15px;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #ffffff;
            }
        """)
        compounds_layout.addWidget(reaction_widget)

        # Add configured indicator with side info
        if self.configured_side:
            side_name = "Reactants" if self.configured_side == 'reactants' else "Products"
            self.configured_label = QLabel(f"✓ Configuring {side_name} side only (other side locked)")
            self.configured_label.setStyleSheet("color: #00aa00; font-weight: bold;")
        else:
            self.configured_label.setStyleSheet("color: #aaaaaa; font-style: italic;")
        self.configured_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        compounds_layout.addWidget(self.configured_label)

        compounds_group.setLayout(compounds_layout)
        self.dynamic_layout.addWidget(compounds_group)

        # Continue to calculations button
        self.to_calculations_btn.setMinimumHeight(40)
        self.to_calculations_btn.clicked.connect(self.show_calculation_buttons)
        self.dynamic_layout.addWidget(self.to_calculations_btn)
        
        self.auto_resize()

    @staticmethod
    def extract_compounds_from_reaction(reaction_text):
        """Extract compound formulas from reaction text, preserving original display format."""
        try:
            # Parse the reaction to get reactants and products
            reactants_str, products_str = ChemLabParser.split_reaction(reaction_text)

            if not reactants_str or not products_str:
                return {'reactants': [], 'products': [], 'arrow': '→'}

            # Split by + to get individual compounds
            reactants = [c.strip() for c in reactants_str.split('+') if c.strip()]
            products = [c.strip() for c in products_str.split('+') if c.strip()]

            # Determine arrow type
            arrow = '→'
            for a in ['→', '←', '⇌', '⇋', '↔', '<=>', '<->']:
                if a in reaction_text:
                    arrow = a
                    break

            return {
                'reactants': reactants,
                'products': products,
                'arrow': arrow
            }
        except Exception as e:
            logging.error(f"Error extracting compounds: {e}")
            return {'reactants': [], 'products': [], 'arrow': '→'}

    def on_compound_clicked(self, compound, side):
        """Handle compound button click, tracking which side is being configured."""
        self.configured_side = side
        self.show_compound_properties_editor(compound)

    def show_compound_properties_editor(self, compound):
        """Show properties editor for a specific compound."""
        self.selected_compound = compound
        self.clear_dynamic_area()

        editor_group = QGroupBox(f"Configure: {compound}")
        editor_layout = QVBoxLayout()

        # Property type selector
        property_layout = QHBoxLayout()
        property_label = QLabel("Property:")
        self.property_combo.addItems(["Moles", "Weight (grams)"])
        self.property_combo.currentTextChanged.connect(self.on_property_changed)
        property_layout.addWidget(property_label)
        property_layout.addWidget(self.property_combo)
        editor_layout.addLayout(property_layout)

        # Value input
        value_layout = QHBoxLayout()
        value_label = QLabel("Value:")
        self.value_spin.setRange(0, 999999)
        self.value_spin.setDecimals(4)
        self.value_spin.setValue(self.compound_data.get(compound, {}).get('value', 1.0))
        value_layout.addWidget(value_label)
        value_layout.addWidget(self.value_spin)
        editor_layout.addLayout(value_layout)

        # Unit label
        self.unit_label.setStyleSheet("color: #666; font-style: italic;")
        editor_layout.addWidget(self.unit_label)

        # Purity input
        purity_layout = QHBoxLayout()
        purity_label = QLabel("Purity (%):")
        self.purity_spin.setRange(0, 100)
        self.purity_spin.setDecimals(2)
        self.purity_spin.setValue(self.compound_data.get(compound, {}).get('purity', 100.0))
        purity_layout.addWidget(purity_label)
        purity_layout.addWidget(self.purity_spin)
        editor_layout.addLayout(purity_layout)

        # Temperature input
        temp_layout = QHBoxLayout()
        temp_label = QLabel("Temperature (K):")
        self.temp_spin.setRange(0, 999999)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setValue(self.compound_data.get(compound, {}).get('temperature', 298.15))
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_spin)
        editor_layout.addLayout(temp_layout)

        # Pressure input
        pressure_layout = QHBoxLayout()
        pressure_label = QLabel("Pressure (atm):")
        self.pressure_spin.setRange(0, 999999)
        self.pressure_spin.setDecimals(4)
        self.pressure_spin.setValue(self.compound_data.get(compound, {}).get('pressure', 1.0))
        pressure_layout.addWidget(pressure_label)
        pressure_layout.addWidget(self.pressure_spin)
        editor_layout.addLayout(pressure_layout)

        # Volume input
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Volume (L):")
        self.volume_spin.setRange(0, 999999)
        self.volume_spin.setDecimals(4)
        self.volume_spin.setValue(self.compound_data.get(compound, {}).get('volume', 0.0))
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_spin)
        editor_layout.addLayout(volume_layout)

        # Concentration input
        conc_layout = QHBoxLayout()
        conc_label = QLabel("Concentration (M):")
        self.conc_spin.setRange(0, 999999)
        self.conc_spin.setDecimals(6)
        self.conc_spin.setValue(self.compound_data.get(compound, {}).get('concentration', 0.0))
        conc_layout.addWidget(conc_label)
        conc_layout.addWidget(self.conc_spin)
        editor_layout.addLayout(conc_layout)

        # Save button
        save_btn = QPushButton("Save Properties")
        save_btn.clicked.connect(self.save_compound_properties)
        editor_layout.addWidget(save_btn)

        # Back to compounds button
        back_compounds_btn = QPushButton("← Back to Compounds")
        back_compounds_btn.clicked.connect(lambda: (self.show_compound_selection(), self.auto_resize()))
        editor_layout.addWidget(back_compounds_btn)

        editor_group.setLayout(editor_layout)
        self.dynamic_layout.addWidget(editor_group)

    def on_property_changed(self, property_type):
        """Update unit label when property changes."""
        units = {
            "Moles": "mol",
            "Weight (grams)": "g"
        }
        self.unit_label.setText(units.get(property_type, ""))

    def save_compound_properties(self):
        """Save properties for the selected compound."""
        # Store the compound that was just configured
        just_configured = self.selected_compound

        self.compound_data[just_configured] = {
            'property': self.property_combo.currentText(),
            'value': self.value_spin.value(),
            'purity': self.purity_spin.value(),
            'temperature': self.temp_spin.value(),
            'pressure': self.pressure_spin.value(),
            'volume': self.volume_spin.value(),
            'concentration': self.conc_spin.value()
        }

        QMessageBox.information(self, "Saved", f"Properties saved for {just_configured}")

        # Now rebuild the compound selection view and restore configured status
        self.show_compound_selection()

        # Apply configured styling to the button that was just saved
        if just_configured in self.compound_buttons:
            btn = self.compound_buttons[just_configured]
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #d4edda;
                    border: 2px solid #28a745;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #28a745;
                    color: white;
                }
            """)

        # Update configured indicator
        configured_count = len(self.compound_data)
        total_count = len(self.compound_buttons)
        self.configured_label.setText(f"Configured: {configured_count}/{total_count} compounds")
        self.configured_label.setStyleSheet("color: #00aa00; font-weight: bold;")

    def setup_compound_data(self):
        """Setup compound data for compound mode."""
        formula = self.compound_formula_entry.text().strip()
        state = self.compound_state_combo.currentText()
        property_type = self.compound_property_combo.currentText()
        value = self.compound_value_spin.value()
        purity = self.compound_purity_spin.value()
        temperature = self.compound_temp_spin.value()
        pressure = self.compound_pressure_spin.value()
        volume = self.compound_volume_spin.value()
        concentration = self.compound_conc_spin.value()
        
        self.selected_compound = formula
        self.compound_data = {
            formula: {
                'state': state,
                'property': property_type,
                'value': value,
                'purity': purity,
                'temperature': temperature,
                'pressure': pressure,
                'volume': volume,
                'concentration': concentration
            }
        }

    def show_calculation_buttons(self):
        """Show all derivable calculation results in a scrollable table."""
        self.clear_dynamic_area()
        self.title_label.setText("Calculation Results")
        self.continue_btn.setVisible(False)
        self.reaction_display.setVisible(False)
        if hasattr(self, 'to_calculations_btn'):
            self.to_calculations_btn.setVisible(False)

        self.status_label.setText("Calculation Results")
        self.status_label.setStyleSheet("color: #0078d4; font-weight: bold;")

        # Create results group
        results_group = QGroupBox("Derivable Results")
        results_layout = QVBoxLayout()

        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Compound", "Property", "Value", "Unit"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Calculate and populate results
        self.populate_results_table()
        
        results_layout.addWidget(self.results_table)
        
        # Add limiting reagent indicator if formula mode
        if self.current_mode == 'formula' and self.compound_data:
            limiting_reagent = self.calculate_limiting_reagent_internal()
            if limiting_reagent:
                lr_label = QLabel(f"⚠️ Limiting Reagent: {limiting_reagent}")
                lr_label.setStyleSheet("color: #ff6600; font-weight: bold; font-size: 14px;")
                lr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                results_layout.addWidget(lr_label)
        
        # Back button
        back_btn = QPushButton("← Back to Configuration")
        back_btn.clicked.connect(self.on_back_to_config)
        results_layout.addWidget(back_btn)
        
        results_group.setLayout(results_layout)
        self.dynamic_layout.addWidget(results_group)
        self.auto_resize()

    def populate_results_table(self):
        """Populate the results table with calculated values."""
        row = 0
        
        for compound, data in self.compound_data.items():
            # Add moles row
            if 'value' in data and data.get('property') == 'Moles':
                self.add_result_row(row, compound, "Moles", data['value'], "mol")
                row += 1
                
                # Calculate mass from moles if possible
                try:
                    from chemlab_parser import ChemLabParser
                    normalized = ChemLabParser.normalize_formula(compound)
                    clean_formula = re.sub(r'\([a-z]+\)$', '', normalized)
                    molar_mass = ChemLabParser.calculate_molar_mass(clean_formula)
                    if molar_mass > 0:
                        mass = data['value'] * molar_mass
                        self.add_result_row(row, compound, "Mass", f"{mass:.4f}", "g")
                        row += 1
                except:
                    pass
            
            # Add weight/mass row
            if 'value' in data and data.get('property') == 'Weight (grams)':
                self.add_result_row(row, compound, "Mass", data['value'], "g")
                row += 1
                
                # Calculate moles from mass if possible
                try:
                    from chemlab_parser import ChemLabParser
                    normalized = ChemLabParser.normalize_formula(compound)
                    clean_formula = re.sub(r'\([a-z]+\)$', '', normalized)
                    molar_mass = ChemLabParser.calculate_molar_mass(clean_formula)
                    if molar_mass > 0:
                        moles = data['value'] / molar_mass
                        self.add_result_row(row, compound, "Moles", f"{moles:.6f}", "mol")
                        row += 1
                except:
                    pass
            
            # Add purity
            if 'purity' in data:
                self.add_result_row(row, compound, "Purity", data['purity'], "%")
                row += 1
            
            # Add other properties with safe type conversion
            if 'temperature' in data:
                try:
                    temp_val = float(data['temperature'])
                    self.add_result_row(row, compound, "Temperature", f"{temp_val:.2f}", "K")
                    row += 1
                except (ValueError, TypeError):
                    pass
            if 'pressure' in data:
                try:
                    press_val = float(data['pressure'])
                    self.add_result_row(row, compound, "Pressure", f"{press_val:.4f}", "atm")
                    row += 1
                except (ValueError, TypeError):
                    pass
            if 'volume' in data:
                try:
                    vol_val = float(data['volume'])
                    self.add_result_row(row, compound, "Volume", f"{vol_val:.4f}", "L")
                    row += 1
                except (ValueError, TypeError):
                    pass
            if 'concentration' in data:
                try:
                    conc_val = float(data['concentration'])
                    if conc_val > 0:
                        self.add_result_row(row, compound, "Concentration", f"{conc_val:.6f}", "M")
                        row += 1
                        
                        # Calculate moles from concentration if volume available
                        if 'volume' in data:
                            try:
                                vol_val = float(data['volume'])
                                if vol_val > 0:
                                    moles = conc_val * vol_val
                                    self.add_result_row(row, compound, "Moles (from Conc)", f"{moles:.6f}", "mol")
                                    row += 1
                            except (ValueError, TypeError):
                                pass
                except (ValueError, TypeError):
                    pass
    
    def add_result_row(self, row, compound, property_name, value, unit):
        """Add a row to the results table."""
        self.results_table.insertRow(row)
        self.results_table.setItem(row, 0, QTableWidgetItem(str(compound)))
        self.results_table.setItem(row, 1, QTableWidgetItem(str(property_name)))
        self.results_table.setItem(row, 2, QTableWidgetItem(str(value)))
        self.results_table.setItem(row, 3, QTableWidgetItem(str(unit)))

    def calculate_limiting_reagent_internal(self):
        """Calculate limiting reagent from configured compounds. Returns compound name or None."""
        if not self.compound_data:
            return None
            
        # Find moles for each compound
        moles_data = {}
        for compound, data in self.compound_data.items():
            if 'value' in data:
                if data.get('property') == 'Moles':
                    moles_data[compound] = data['value']
                elif data.get('property') == 'Weight (grams)':
                    # Convert mass to moles
                    try:
                        from chemlab_parser import ChemLabParser
                        normalized = ChemLabParser.normalize_formula(compound)
                        clean_formula = re.sub(r'\([a-z]+\)$', '', normalized)
                        molar_mass = ChemLabParser.calculate_molar_mass(clean_formula)
                        if molar_mass > 0:
                            moles_data[compound] = data['value'] / molar_mass
                    except:
                        pass
        
        if not moles_data:
            return None
            
        # The limiting reagent is the one with least moles
        limiting = min(moles_data.items(), key=lambda x: x[1])
        return limiting[0]

    def on_back_to_config(self):
        """Go back to compound configuration from results."""
        if self.current_mode == 'formula':
            self.show_compound_selection()
        else:
            # For compound mode, go back to entry
            self.clear_dynamic_area()
            self.compound_entry_group.setVisible(True)
            self.continue_btn.setVisible(True)
            self.back_btn.setVisible(True)
            self.auto_resize()

    def go_back(self):
        """Go back to initial selection view - hide everything and show main screen only."""
        self.clear_dynamic_area()

        # Hide all other UI elements
        self.compound_entry_group.setVisible(False)
        self.reaction_display.setVisible(False)
        self.continue_btn.setVisible(False)
        self.back_btn.setVisible(False)

        # Show only main selection buttons
        self.formula_btn.setVisible(True)
        self.formula_btn.setEnabled(True)
        self.compound_btn.setVisible(True)
        self.compound_btn.setEnabled(True)
        self.selection_group.setVisible(True)

        # Reset state
        self.current_mode = None
        self.selected_reaction = None
        self.selected_compound = None
        self.compound_data = {}
        self.configured_side = None
        self.compound_side_map = {}

        # Disable selection mode in parent if active
        if self.parent_window and hasattr(self.parent_window, 'disable_reaction_selection_mode'):
            self.parent_window.disable_reaction_selection_mode()

        self.status_label.setText("Select an option above to continue")
        self.status_label.setStyleSheet("color: #666;")