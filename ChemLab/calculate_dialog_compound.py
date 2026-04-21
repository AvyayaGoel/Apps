"""Compound mode view handling for CalculateDialog."""
import logging
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QDoubleSpinBox, QComboBox, QStackedWidget, QWidget,
    QLineEdit, QMessageBox
)

from calculate_dialog_formula import FormulaViewHandler
from calculate_dialog_views import ViewState
from chemlab_parser import ChemLabParser
from constants import STATE_NAMES, SUBSCRIPT_DIGITS


class CompoundViewHandler:
    """Handles all Compound mode views and transitions."""

    def __init__(self, dialog):
        """Initialize with parent dialog."""
        self.dialog = dialog

    def on_compound_selected(self):
        """Handle Compound button click - show formula entry."""
        self.dialog.current_mode = 'compound'

        # Switch to compound entry view
        self.dialog.view_manager.switch_to(ViewState.COMPOUND_ENTRY, clear_dynamic=True)

        self.dialog.title_label.setText("Enter Compound Formula")
        self.dialog.status_label.setText("Enter a valid compound formula to continue")
        self.dialog.status_label.setStyleSheet("color: #0078d4;")

        self.dialog.continue_btn.setEnabled(False)

        # Create entry UI in dynamic area
        entry_group = QGroupBox("Enter Compound Formula")
        entry_layout = QVBoxLayout()

        # Formula input
        formula_layout = QHBoxLayout()
        formula_label = QLabel("Formula:")
        self.dialog.compound_formula_entry.setPlaceholderText("e.g., H₂O, NaCl, CO₂")
        self.dialog.compound_formula_entry.textChanged.connect(self._on_formula_changed)
        # Install key press event filter for brackets and subscripts
        self.dialog.compound_formula_entry.keyPressEvent = self._on_formula_key_press

        formula_layout.addWidget(formula_label)
        formula_layout.addWidget(self.dialog.compound_formula_entry)
        entry_layout.addLayout(formula_layout)

        # State selector
        state_layout = QHBoxLayout()
        state_label = QLabel("State:")
        self.dialog.compound_state_combo.clear()
        self.dialog.compound_state_combo.addItems(list(set(STATE_NAMES.values())))
        self.dialog.compound_state_combo.setCurrentText(STATE_NAMES.get('s', 'Solid'))
        state_layout.addWidget(state_label)
        state_layout.addWidget(self.dialog.compound_state_combo)
        entry_layout.addLayout(state_layout)

        entry_group.setLayout(entry_layout)
        self.dialog.dynamic_layout.addWidget(entry_group)

        self.dialog.compound_formula_entry.setFocus()
        self.dialog.auto_resize()

    def _on_formula_changed(self):
        """Handle formula text change."""
        text = self.dialog.compound_formula_entry.text().strip()
        is_valid = self.dialog.validate_compound_formula()
        self.dialog.continue_btn.setEnabled(is_valid)

        # Only show red border for invalid compounds (containing non-element letters)
        # Keep default style (no border) for valid compounds or empty
        if not text:
            self.dialog.compound_formula_entry.setStyleSheet("")
        elif is_valid:
            # Valid compound - keep default style (no border)
            self.dialog.compound_formula_entry.setStyleSheet("")
        else:
            # Invalid compound - show red border
            self.dialog.compound_formula_entry.setStyleSheet("border: 2px solid red;")

    def _on_formula_key_press(self, event):
        """Handle key press for bracket auto-complete and subscript conversion."""
        key = event.key()
        cursor = self.dialog.compound_formula_entry.cursorPosition()
        text = self.dialog.compound_formula_entry.text()
        selected = self.dialog.compound_formula_entry.selectedText()

        # Handle bracket auto-complete for opening brackets
        if key == Qt.Key.Key_ParenLeft:  # (
            if selected:
                start = cursor - len(selected)
                self.dialog.compound_formula_entry.deselect()
                new_text = text[:start] + "(" + selected + ")" + text[cursor:]
                self.dialog.compound_formula_entry.setText(new_text)
                self.dialog.compound_formula_entry.setSelection(start + 1, len(selected))
            else:
                # Auto-complete with ) and place cursor inside
                new_text = text[:cursor] + "()" + text[cursor:]
                self.dialog.compound_formula_entry.setText(new_text)
                self.dialog.compound_formula_entry.setCursorPosition(cursor + 1)
            return

        if key == Qt.Key.Key_BracketLeft:  # [
            if selected:
                # Wrap selected text with brackets - deselect first to avoid duplication
                start = cursor - len(selected)
                self.dialog.compound_formula_entry.deselect()
                new_text = text[:start] + "[" + selected + "]" + text[cursor:]
                self.dialog.compound_formula_entry.setText(new_text)
                self.dialog.compound_formula_entry.setSelection(start + 1, len(selected))
            else:
                # Auto-complete with ] and place cursor inside
                new_text = text[:cursor] + "[]" + text[cursor:]
                self.dialog.compound_formula_entry.setText(new_text)
                self.dialog.compound_formula_entry.setCursorPosition(cursor + 1)
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
                    self.dialog.compound_formula_entry.setText(new_text)
                    self.dialog.compound_formula_entry.setCursorPosition(cursor + 1)
                    return  # Don't process the event further

        # Call original key press event for other keys
        QLineEdit.keyPressEvent(self.dialog.compound_formula_entry, event)

    def on_continue_clicked(self):
        """Handle Continue button in compound mode - skip editor, go straight to calculations."""
        formula = self.dialog.compound_formula_entry.text().strip()
        if formula and self.dialog.validate_compound_formula(formula):
            self.dialog.selected_compound = formula

            # Skip compound editor - go directly to calculation menu
            self.dialog.show_calculation_menu()
        else:
            QMessageBox.warning(self.dialog, "Invalid Formula",
                                "Please enter a valid chemical formula.")


class CompoundEditor:
    """Handles compound property editing UI."""

    def __init__(self, dialog):
        """Initialize with parent dialog."""
        self.dialog = dialog

    def show_for_compound(self, compound, state_from_user=None):
        """Show editor for a specific compound in compound mode."""
        logging.info(f"[CompoundEditor] show_for_compound: {compound}")

        # Switch to compound editor view
        self.dialog.view_manager.switch_to(ViewState.COMPOUND_EDITOR, clear_dynamic=True)

        self.dialog.selected_compound = compound
        self.dialog.title_label.setText(f"Configure: {compound}")
        self.dialog.status_label.setText("Select an input mode and enter values")

        # Determine available modes
        state_code = self._get_compound_state(compound, state_from_user)
        available_modes = self._get_available_modes(state_code)

        logging.info(f"[CompoundEditor] State: {state_code}, Modes: {available_modes}")

        # Create editor UI
        self._create_editor_ui(compound, available_modes, is_formula_mode=False)

        # Restore data if exists
        self._restore_data_if_exists(compound)

        self.dialog.auto_resize()

    def show_for_formula(self, compound):
        """Show editor for a compound in formula mode."""
        logging.info(f"[CompoundEditor] show_for_formula: {compound}")

        # Switch to formula compound editor view
        self.dialog.view_manager.switch_to(ViewState.FORMULA_COMPOUND_EDITOR, clear_dynamic=True)

        self.dialog.selected_compound = compound
        self.dialog.title_label.setText(f"Configure: {compound}")
        self.dialog.status_label.setText("Select an input mode and enter values")

        # Determine available modes from compound string
        state_code = self._get_compound_state(compound, None)
        available_modes = self._get_available_modes(state_code)

        logging.info(f"[CompoundEditor] State: {state_code}, Modes: {available_modes}")

        # Create editor UI
        self._create_editor_ui(compound, available_modes, is_formula_mode=True)

        # Restore data if exists
        self._restore_data_if_exists(compound)

        self.dialog.auto_resize()

    def _create_editor_ui(self, compound, available_modes, is_formula_mode):
        """Create the compound editor UI."""
        editor_group = QGroupBox(f"Configure: {compound}")
        editor_layout = QVBoxLayout()

        # Mode selection buttons
        mode_group = QGroupBox("Select Input Mode")
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(10)

        self.dialog.mass_mode_btn = QPushButton("⚖️ Mass")
        self.dialog.mass_mode_btn.setCheckable(True)
        self.dialog.mass_mode_btn.setMinimumHeight(45)
        self.dialog.mass_mode_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.dialog.mass_mode_btn.clicked.connect(lambda: self._on_mode_selected('mass'))

        self.dialog.solution_mode_btn = QPushButton("🧪 Solution")
        self.dialog.solution_mode_btn.setCheckable(True)
        self.dialog.solution_mode_btn.setMinimumHeight(45)
        self.dialog.solution_mode_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.dialog.solution_mode_btn.clicked.connect(lambda: self._on_mode_selected('solution'))

        self.dialog.gas_mode_btn = QPushButton("💨 Gas")
        self.dialog.gas_mode_btn.setCheckable(True)
        self.dialog.gas_mode_btn.setMinimumHeight(45)
        self.dialog.gas_mode_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.dialog.gas_mode_btn.clicked.connect(lambda: self._on_mode_selected('gas'))

        # Add only available mode buttons
        if 'mass' in available_modes:
            mode_layout.addWidget(self.dialog.mass_mode_btn)
        else:
            self.dialog.mass_mode_btn = None

        if 'solution' in available_modes:
            mode_layout.addWidget(self.dialog.solution_mode_btn)
        else:
            self.dialog.solution_mode_btn = None

        if 'gas' in available_modes:
            mode_layout.addWidget(self.dialog.gas_mode_btn)
        else:
            self.dialog.gas_mode_btn = None

        mode_group.setLayout(mode_layout)
        editor_layout.addWidget(mode_group)

        # Mode description
        self.dialog.mode_description_label = QLabel("Select an input mode above to enter compound data")
        self.dialog.mode_description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialog.mode_description_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        editor_layout.addWidget(self.dialog.mode_description_label)

        # Create input pages
        self._create_input_pages()
        editor_layout.addWidget(self.dialog.input_stack)

        # Calculated moles display
        self.dialog.calc_moles_display = QLabel("Calculated Moles: --")
        self.dialog.calc_moles_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dialog.calc_moles_display.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        self.dialog.calc_moles_display.setVisible(False)
        editor_layout.addWidget(self.dialog.calc_moles_display)

        # Save button
        save_btn = QPushButton("Save Properties")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(lambda: self._save_properties(is_formula_mode))
        editor_layout.addWidget(save_btn)

        # Back button
        back_btn = QPushButton("← Back")
        back_btn.setMinimumHeight(35)
        if is_formula_mode:

            handler = FormulaViewHandler(self.dialog)
            back_btn.clicked.connect(handler.show_compound_selection)
        else:
            handler = CompoundViewHandler(self.dialog)
            back_btn.clicked.connect(handler.on_compound_selected)
        editor_layout.addWidget(back_btn)

        editor_group.setLayout(editor_layout)
        self.dialog.dynamic_layout.addWidget(editor_group)

    def _create_input_pages(self):
        """Create QStackedWidget pages for input modes."""
        self.dialog.input_stack = QStackedWidget()

        # Mass page
        self.dialog.mass_page = QWidget()
        mass_layout = QVBoxLayout(self.dialog.mass_page)
        mass_layout.setContentsMargins(0, 0, 0, 0)

        mass_input_layout = QHBoxLayout()
        mass_label = QLabel("Mass:")
        self.dialog.mass_input = QDoubleSpinBox()
        self.dialog.mass_input.setRange(0, 9999999)
        self.dialog.mass_input.setDecimals(4)
        self.dialog.mass_input.setValue(0)  # Empty by default - user must fill
        self.dialog.mass_input.setSpecialValueText("Required")  # Shows when value is 0
        self.dialog.mass_input.valueChanged.connect(self._update_calculated_moles)

        self.dialog.mass_unit_combo = QComboBox()
        self.dialog.mass_unit_combo.addItems(["g", "kg", "mg"])
        self.dialog.mass_unit_combo.currentTextChanged.connect(self._update_calculated_moles)

        mass_input_layout.addWidget(mass_label)
        mass_input_layout.addWidget(self.dialog.mass_input)
        mass_input_layout.addWidget(self.dialog.mass_unit_combo)
        mass_layout.addLayout(mass_input_layout)
        mass_layout.addStretch()
        self.dialog.input_stack.addWidget(self.dialog.mass_page)

        # Solution page
        self.dialog.solution_page = QWidget()
        solution_layout = QVBoxLayout(self.dialog.solution_page)
        solution_layout.setContentsMargins(0, 0, 0, 0)

        # Concentration
        conc_layout = QHBoxLayout()
        conc_label = QLabel("Concentration:")
        self.dialog.conc_input = QDoubleSpinBox()
        self.dialog.conc_input.setRange(0, 9999999)
        self.dialog.conc_input.setDecimals(6)
        self.dialog.conc_input.setValue(0)
        self.dialog.conc_input.valueChanged.connect(self._update_calculated_moles)

        self.dialog.conc_unit_combo = QComboBox()
        self.dialog.conc_unit_combo.addItems(["M", "mM", "uM", "mol/L"])
        self.dialog.conc_unit_combo.currentTextChanged.connect(self._update_calculated_moles)

        conc_layout.addWidget(conc_label)
        conc_layout.addWidget(self.dialog.conc_input)
        conc_layout.addWidget(self.dialog.conc_unit_combo)
        solution_layout.addLayout(conc_layout)

        # Volume
        vol_layout = QHBoxLayout()
        vol_label = QLabel("Volume:")
        self.dialog.solution_volume_input = QDoubleSpinBox()
        self.dialog.solution_volume_input.setRange(0, 9999999)
        self.dialog.solution_volume_input.setDecimals(4)
        self.dialog.solution_volume_input.setValue(0)
        self.dialog.solution_volume_input.valueChanged.connect(self._update_calculated_moles)

        self.dialog.solution_volume_unit = QComboBox()
        self.dialog.solution_volume_unit.addItems(["L", "mL", "m³", "cm³"])
        self.dialog.solution_volume_unit.currentTextChanged.connect(self._update_calculated_moles)

        vol_layout.addWidget(vol_label)
        vol_layout.addWidget(self.dialog.solution_volume_input)
        vol_layout.addWidget(self.dialog.solution_volume_unit)
        solution_layout.addLayout(vol_layout)
        solution_layout.addStretch()
        self.dialog.input_stack.addWidget(self.dialog.solution_page)

        # Gas page
        self.dialog.gas_page = QWidget()
        gas_layout = QVBoxLayout(self.dialog.gas_page)
        gas_layout.setContentsMargins(0, 0, 0, 0)

        # Pressure
        pressure_layout = QHBoxLayout()
        pressure_label = QLabel("Pressure:")
        self.dialog.gas_pressure_input = QDoubleSpinBox()
        self.dialog.gas_pressure_input.setRange(0, 9999999)
        self.dialog.gas_pressure_input.setDecimals(4)
        self.dialog.gas_pressure_input.setValue(1.0)
        self.dialog.gas_pressure_input.valueChanged.connect(self._update_calculated_moles)

        self.dialog.gas_pressure_unit = QComboBox()
        self.dialog.gas_pressure_unit.addItems(["atm", "Pa", "kPa", "bar", "mmHg", "torr"])
        self.dialog.gas_pressure_unit.currentTextChanged.connect(self._update_calculated_moles)

        pressure_layout.addWidget(pressure_label)
        pressure_layout.addWidget(self.dialog.gas_pressure_input)
        pressure_layout.addWidget(self.dialog.gas_pressure_unit)
        gas_layout.addLayout(pressure_layout)

        # Volume
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Volume:")
        self.dialog.gas_volume_input = QDoubleSpinBox()
        self.dialog.gas_volume_input.setRange(0, 9999999)
        self.dialog.gas_volume_input.setDecimals(4)
        self.dialog.gas_volume_input.setValue(0)
        self.dialog.gas_volume_input.valueChanged.connect(self._update_calculated_moles)

        self.dialog.gas_volume_unit = QComboBox()
        self.dialog.gas_volume_unit.addItems(["L", "mL", "m³", "cm³"])
        self.dialog.gas_volume_unit.currentTextChanged.connect(self._update_calculated_moles)

        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.dialog.gas_volume_input)
        volume_layout.addWidget(self.dialog.gas_volume_unit)
        gas_layout.addLayout(volume_layout)

        # Temperature
        temp_layout = QHBoxLayout()
        temp_label = QLabel("Temperature:")
        self.dialog.gas_temp_input = QDoubleSpinBox()
        self.dialog.gas_temp_input.setRange(0, 9999999)
        self.dialog.gas_temp_input.setDecimals(2)
        self.dialog.gas_temp_input.setValue(298.15)
        self.dialog.gas_temp_input.valueChanged.connect(self._update_calculated_moles)

        self.dialog.gas_temp_unit = QComboBox()
        self.dialog.gas_temp_unit.addItems(["K", "°C", "°F"])
        self.dialog.gas_temp_unit.currentTextChanged.connect(self._update_calculated_moles)

        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.dialog.gas_temp_input)
        temp_layout.addWidget(self.dialog.gas_temp_unit)
        gas_layout.addLayout(temp_layout)
        gas_layout.addStretch()
        self.dialog.input_stack.addWidget(self.dialog.gas_page)

    def _on_mode_selected(self, mode):
        """Handle mode button selection."""
        logging.info(f"[CompoundEditor] Mode selected: {mode}")

        # Uncheck other buttons
        if mode == 'mass':
            if self.dialog.solution_mode_btn:
                self.dialog.solution_mode_btn.setChecked(False)
            if self.dialog.gas_mode_btn:
                self.dialog.gas_mode_btn.setChecked(False)
            self.dialog.mode_description_label.setText(
                "Enter Mass. Moles will be derived automatically from mass / molar mass."
            )
            self.dialog.input_stack.setCurrentWidget(self.dialog.mass_page)
            # Reset values
            self.dialog.mass_input.setValue(0.0)

        elif mode == 'solution':
            if self.dialog.mass_mode_btn:
                self.dialog.mass_mode_btn.setChecked(False)
            if self.dialog.gas_mode_btn:
                self.dialog.gas_mode_btn.setChecked(False)
            self.dialog.mode_description_label.setText(
                "Enter Molarity and Volume to derive Moles (moles = M × V)."
            )
            self.dialog.input_stack.setCurrentWidget(self.dialog.solution_page)
            # Reset values
            self.dialog.conc_input.setValue(0.0)
            self.dialog.solution_volume_input.setValue(0.0)

        elif mode == 'gas':
            if self.dialog.mass_mode_btn:
                self.dialog.mass_mode_btn.setChecked(False)
            if self.dialog.solution_mode_btn:
                self.dialog.solution_mode_btn.setChecked(False)
            self.dialog.mode_description_label.setText(
                "Enter P, V, and T. Moles derived via Ideal Gas Law (n = PV/RT)."
            )
            self.dialog.input_stack.setCurrentWidget(self.dialog.gas_page)
            # Reset values
            self.dialog.gas_pressure_input.setValue(1.0)
            self.dialog.gas_volume_input.setValue(0.0)
            self.dialog.gas_temp_input.setValue(298.15)

        # Clear mode data
        if self.dialog.selected_compound in self.dialog.mode_data:
            del self.dialog.mode_data[self.dialog.selected_compound]

        self.dialog.calc_moles_display.setVisible(True)
        self._update_calculated_moles()
        self.dialog.auto_resize()

    def _update_calculated_moles(self):
        """Update calculated moles display."""
        moles = self._calculate_moles()
        if moles is not None:
            self.dialog.calc_moles_display.setText(f"Calculated Moles: {moles:.6f} mol")
        else:
            self.dialog.calc_moles_display.setText("Calculated Moles: --")

    def _calculate_moles(self):
        """Calculate moles from current inputs."""
        compound = self.dialog.selected_compound
        if not compound:
            return None

        # Get molar mass
        try:
            normalized = ChemLabParser.normalize_formula(compound)
            clean_formula = re.sub(r'\([a-z]+\)$', '', normalized, flags=re.IGNORECASE)
            molar_mass = ChemLabParser.calculate_molar_mass(clean_formula)
            if not molar_mass or molar_mass <= 0:
                return None
        except:
            return None

        # Check which mode is active
        if self.dialog.mass_mode_btn and self.dialog.mass_mode_btn.isChecked():
            if self.dialog.mass_input:
                mass = self.dialog.mass_input.value()
                unit = self.dialog.mass_unit_combo.currentText()
                if unit == "kg":
                    mass_g = mass * 1000
                elif unit == "mg":
                    mass_g = mass / 1000
                else:
                    mass_g = mass
                return mass_g / molar_mass

        elif self.dialog.solution_mode_btn and self.dialog.solution_mode_btn.isChecked():
            if self.dialog.conc_input and self.dialog.solution_volume_input:
                conc = self.dialog.conc_input.value()
                conc_unit = self.dialog.conc_unit_combo.currentText()
                vol = self.dialog.solution_volume_input.value()
                vol_unit = self.dialog.solution_volume_unit.currentText()

                if conc_unit == "mM":
                    conc_mol_L = conc / 1000
                elif conc_unit == "uM":
                    conc_mol_L = conc / 1000000
                else:
                    conc_mol_L = conc

                if vol_unit == "mL" or vol_unit == "cm³":
                    vol_L = vol / 1000
                elif vol_unit == "m³":
                    vol_L = vol * 1000
                else:
                    vol_L = vol

                return conc_mol_L * vol_L

        elif self.dialog.gas_mode_btn and self.dialog.gas_mode_btn.isChecked():
            if self.dialog.gas_pressure_input and self.dialog.gas_volume_input and self.dialog.gas_temp_input:
                P = self.dialog.gas_pressure_input.value()
                P_unit = self.dialog.gas_pressure_unit.currentText()
                V = self.dialog.gas_volume_input.value()
                V_unit = self.dialog.gas_volume_unit.currentText()
                T = self.dialog.gas_temp_input.value()
                T_unit = self.dialog.gas_temp_unit.currentText()

                pressure_conversion = {
                    "Pa": 9.86923e-6, "kPa": 0.00986923, "bar": 0.986923,
                    "mmHg": 0.00131579, "torr": 0.00131579
                }
                P_atm = P * pressure_conversion.get(P_unit, 1.0) if P_unit != "atm" else P

                if V_unit == "mL" or V_unit == "cm³":
                    V_L = V / 1000
                elif V_unit == "m³":
                    V_L = V * 1000
                else:
                    V_L = V

                if T_unit == "°C":
                    T_K = T + 273.15
                elif T_unit == "°F":
                    T_K = (T - 32) * 5 / 9 + 273.15
                else:
                    T_K = T

                R = 0.08206
                if T_K > 0:
                    return (P_atm * V_L) / (R * T_K)

        return None

    def _save_properties(self, is_formula_mode):
        """Save compound properties."""
        compound = self.dialog.selected_compound
        moles = self._calculate_moles()

        # Validate that moles is not None (all fields must be filled)
        if moles is None or moles <= 0:
            QMessageBox.warning(self.dialog, "Invalid Input",
                                "Please fill in all required fields with valid values.")
            return

        # Purity is always 100% (not editable)
        data = {
            'purity': 100.0,
            'value': moles,
            'property': 'Moles',
            'input_mode': ''
        }

        # Store mode-specific data
        if self.dialog.mass_mode_btn and self.dialog.mass_mode_btn.isChecked():
            data['input_mode'] = 'mass'
            data['mass'] = self.dialog.mass_input.value()
            data['mass_unit'] = self.dialog.mass_unit_combo.currentText()
        elif self.dialog.solution_mode_btn and self.dialog.solution_mode_btn.isChecked():
            data['input_mode'] = 'solution'
            data['concentration'] = self.dialog.conc_input.value()
            data['conc_unit'] = self.dialog.conc_unit_combo.currentText()
            data['solution_volume'] = self.dialog.solution_volume_input.value()
            data['solution_volume_unit'] = self.dialog.solution_volume_unit.currentText()
        elif self.dialog.gas_mode_btn and self.dialog.gas_mode_btn.isChecked():
            data['input_mode'] = 'gas'
            data['gas_pressure'] = self.dialog.gas_pressure_input.value()
            data['gas_pressure_unit'] = self.dialog.gas_pressure_unit.currentText()
            data['gas_volume'] = self.dialog.gas_volume_input.value()
            data['gas_volume_unit'] = self.dialog.gas_volume_unit.currentText()
            data['gas_temp'] = self.dialog.gas_temp_input.value()
            data['gas_temp_unit'] = self.dialog.gas_temp_unit.currentText()

        self.dialog.compound_data[compound] = data

        QMessageBox.information(self.dialog, "Saved", f"Properties saved for {compound}")

        # Show calculation menu after saving
        handler = FormulaViewHandler(self.dialog)
        handler._show_calculation_buttons()

    def _restore_data_if_exists(self, compound):
        """Restore previous data if compound was configured."""
        if compound not in self.dialog.compound_data:
            return

        data = self.dialog.compound_data[compound]
        input_mode = data.get('input_mode', '')

        if input_mode == 'mass' and self.dialog.mass_mode_btn:
            self.dialog.mass_mode_btn.setChecked(True)
            self._on_mode_selected('mass')
            if 'mass' in data:
                self.dialog.mass_input.setValue(data['mass'])
            if 'mass_unit' in data:
                self.dialog.mass_unit_combo.setCurrentText(data['mass_unit'])
        elif input_mode == 'solution' and self.dialog.solution_mode_btn:
            self.dialog.solution_mode_btn.setChecked(True)
            self._on_mode_selected('solution')
            if 'concentration' in data:
                self.dialog.conc_input.setValue(data['concentration'])
            if 'conc_unit' in data:
                self.dialog.conc_unit_combo.setCurrentText(data['conc_unit'])
            if 'solution_volume' in data:
                self.dialog.solution_volume_input.setValue(data['solution_volume'])
            if 'solution_volume_unit' in data:
                self.dialog.solution_volume_unit.setCurrentText(data['solution_volume_unit'])
        elif input_mode == 'gas' and self.dialog.gas_mode_btn:
            self.dialog.gas_mode_btn.setChecked(True)
            self._on_mode_selected('gas')
            if 'gas_pressure' in data:
                self.dialog.gas_pressure_input.setValue(data['gas_pressure'])
            if 'gas_pressure_unit' in data:
                self.dialog.gas_pressure_unit.setCurrentText(data['gas_pressure_unit'])
            if 'gas_volume' in data:
                self.dialog.gas_volume_input.setValue(data['gas_volume'])
            if 'gas_volume_unit' in data:
                self.dialog.gas_volume_unit.setCurrentText(data['gas_volume_unit'])
            if 'gas_temp' in data:
                self.dialog.gas_temp_input.setValue(data['gas_temp'])
            if 'gas_temp_unit' in data:
                self.dialog.gas_temp_unit.setCurrentText(data['gas_temp_unit'])

    def _get_compound_state(self, compound, state_from_user):
        """Get compound state code."""
        if state_from_user:
            state_map = {v: k for k, v in STATE_NAMES.items()}
            return state_map.get(state_from_user, 's')

        if compound in self.dialog.compound_data:
            stored_state = self.dialog.compound_data[compound].get('state')
            if stored_state:
                state_map = {v: k for k, v in STATE_NAMES.items()}
                return state_map.get(stored_state, 's')

        state_match = re.search(r'\(([a-z]+)\)$', compound, re.IGNORECASE)
        if state_match:
            state_code = state_match.group(1).lower()
            if state_code in STATE_NAMES:
                return state_code

        return 's'

    def _get_available_modes(self, state_code):
        """Get available input modes based on state."""
        if state_code == 'g':
            return ['gas']
        elif state_code == 'aq':
            return ['solution', 'mass']
        elif state_code in ['s', 'l']:
            return ['mass']
        else:
            return ['mass', 'solution', 'gas']
