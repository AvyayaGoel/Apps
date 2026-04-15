"""Calculation handlers for CalculateDialog.

This module provides actual calculation implementations for each type:
- Mass/Mole conversion
- Concentration (Molarity)
- Ideal Gas Law
- Stoichiometry
- Percent Yield
- Percent Composition
"""
import re
from mendeleev import element as get_element
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QDoubleSpinBox, QComboBox, QLineEdit
)

from calculate_dialog_views import ViewState
from chemlab_parser import ChemLabParser


class CalculationHandler:
    """Handles all calculation types with intelligent field questioning."""

    def __init__(self, dialog):
        """Initialize with parent dialog."""
        self.dialog = dialog
        self.current_calc = None

    def show_calculation(self, calc_type):
        """Show the calculation form for the selected type."""
        self.current_calc = calc_type

        # Switch to results/calculation view
        self.dialog.view_manager.switch_to(ViewState.RESULTS, clear_dynamic=True)

        # Set title based on calculation type
        titles = {
            'mass_mole': 'Mass ↔ Moles Conversion',
            'concentration': 'Concentration (Molarity)',
            'gas_law': 'Ideal Gas Law (PV=nRT)',
            'stoichiometry': 'Stoichiometric Amounts',
            'percent_yield': 'Percent Yield',
            'percent_composition': 'Percent Composition'
        }
        self.dialog.title_label.setText(titles.get(calc_type, 'Calculation'))
        self.dialog.status_label.setText("Fill in the known values, leave unknown empty")

        # Create appropriate input form
        if calc_type == 'mass_mole':
            self._create_mass_mole_form()
        elif calc_type == 'concentration':
            self._create_concentration_form()
        elif calc_type == 'gas_law':
            self._create_gas_law_form()
        elif calc_type == 'stoichiometry':
            self._create_stoichiometry_form()
        elif calc_type == 'percent_yield':
            self._create_percent_yield_form()
        elif calc_type == 'percent_composition':
            self._create_percent_composition_form()

        self.dialog.auto_resize()

    def _create_mass_mole_form(self):
        """Create Mass ↔ Moles conversion form."""
        form_group = QGroupBox("Enter Known Values (leave one empty)")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Get compound info if available
        compound = self._get_current_compound()
        molar_mass = None
        if compound:
            molar_mass = self._get_molar_mass(compound)
            info_label = QLabel(f"Compound: {compound} | Molar Mass: {molar_mass:.2f} g/mol")
            info_label.setStyleSheet("color: #0078d4; font-weight: bold;")
            layout.addWidget(info_label)

        # Mass input
        mass_layout = QHBoxLayout()
        mass_label = QLabel("Mass:")
        self.mass_input = QDoubleSpinBox()
        self.mass_input.setRange(0, 9999999)
        self.mass_input.setDecimals(4)
        self.mass_input.setValue(0)
        self.mass_input.setSpecialValueText("?")
        self.mass_unit = QComboBox()
        self.mass_unit.addItems(["g", "kg", "mg"])

        mass_layout.addWidget(mass_label)
        mass_layout.addWidget(self.mass_input)
        mass_layout.addWidget(self.mass_unit)
        layout.addLayout(mass_layout)

        # Moles input
        moles_layout = QHBoxLayout()
        moles_label = QLabel("Moles:")
        self.moles_input = QDoubleSpinBox()
        self.moles_input.setRange(0, 9999999)
        self.moles_input.setDecimals(6)
        self.moles_input.setValue(0)
        self.moles_input.setSpecialValueText("?")
        moles_layout.addWidget(moles_label)
        moles_layout.addWidget(self.moles_input)
        moles_layout.addWidget(QLabel("mol"))
        layout.addLayout(moles_layout)

        # Calculate button
        calc_btn = QPushButton("Calculate")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        calc_btn.clicked.connect(self._calculate_mass_mole)
        layout.addWidget(calc_btn)

        # Result display
        self.result_label = QLabel("Enter values and click Calculate")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: white;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.result_label)

        form_group.setLayout(layout)
        self.dialog.dynamic_layout.addWidget(form_group)

        # Back button
        back_btn = QPushButton("← Back to Calculations")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self._back_to_menu)
        self.dialog.dynamic_layout.addWidget(back_btn)

    def _create_concentration_form(self):
        """Create Molarity calculation form."""
        form_group = QGroupBox("Molarity = Moles / Volume (in L)")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Moles input
        moles_layout = QHBoxLayout()
        moles_label = QLabel("Moles (n):")
        self.moles_input = QDoubleSpinBox()
        self.moles_input.setRange(0, 9999999)
        self.moles_input.setDecimals(6)
        self.moles_input.setValue(0)
        self.moles_input.setSpecialValueText("?")
        moles_layout.addWidget(moles_label)
        moles_layout.addWidget(self.moles_input)
        moles_layout.addWidget(QLabel("mol"))
        layout.addLayout(moles_layout)

        # Volume input
        vol_layout = QHBoxLayout()
        vol_label = QLabel("Volume (V):")
        self.vol_input = QDoubleSpinBox()
        self.vol_input.setRange(0, 9999999)
        self.vol_input.setDecimals(4)
        self.vol_input.setValue(0)
        self.vol_input.setSpecialValueText("?")
        self.vol_unit = QComboBox()
        self.vol_unit.addItems(["L", "mL"])
        self.vol_unit.currentTextChanged.connect(self._update_conc_calc)

        vol_layout.addWidget(vol_label)
        vol_layout.addWidget(self.vol_input)
        vol_layout.addWidget(self.vol_unit)
        layout.addLayout(vol_layout)

        # Concentration input
        conc_layout = QHBoxLayout()
        conc_label = QLabel("Molarity (M):")
        self.conc_input = QDoubleSpinBox()
        self.conc_input.setRange(0, 9999999)
        self.conc_input.setDecimals(6)
        self.conc_input.setValue(0)
        self.conc_input.setSpecialValueText("?")
        conc_layout.addWidget(conc_label)
        conc_layout.addWidget(self.conc_input)
        conc_layout.addWidget(QLabel("mol/L"))
        layout.addLayout(conc_layout)

        # Calculate button
        calc_btn = QPushButton("Calculate")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        calc_btn.clicked.connect(self._calculate_concentration)
        layout.addWidget(calc_btn)

        # Result
        self.result_label = QLabel("Enter values and click Calculate")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: white;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.result_label)

        form_group.setLayout(layout)
        self.dialog.dynamic_layout.addWidget(form_group)

        back_btn = QPushButton("← Back to Calculations")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self._back_to_menu)
        self.dialog.dynamic_layout.addWidget(back_btn)

    def _create_gas_law_form(self):
        """Create Ideal Gas Law form."""
        form_group = QGroupBox("PV = nRT (Solve for one unknown)")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        info = QLabel("R = 0.08206 L·atm/(mol·K)")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)

        # Pressure
        p_layout = QHBoxLayout()
        p_label = QLabel("Pressure (P):")
        self.pressure_input = QDoubleSpinBox()
        self.pressure_input.setRange(0, 9999999)
        self.pressure_input.setDecimals(4)
        self.pressure_input.setValue(0)
        self.pressure_input.setSpecialValueText("?")
        self.pressure_unit = QComboBox()
        self.pressure_unit.addItems(["atm", "kPa", "mmHg"])
        p_layout.addWidget(p_label)
        p_layout.addWidget(self.pressure_input)
        p_layout.addWidget(self.pressure_unit)
        layout.addLayout(p_layout)

        # Volume
        v_layout = QHBoxLayout()
        v_label = QLabel("Volume (V):")
        self.gas_vol_input = QDoubleSpinBox()
        self.gas_vol_input.setRange(0, 9999999)
        self.gas_vol_input.setDecimals(4)
        self.gas_vol_input.setValue(0)
        self.gas_vol_input.setSpecialValueText("?")
        self.gas_vol_unit = QComboBox()
        self.gas_vol_unit.addItems(["L", "mL"])
        v_layout.addWidget(v_label)
        v_layout.addWidget(self.gas_vol_input)
        v_layout.addWidget(self.gas_vol_unit)
        layout.addLayout(v_layout)

        # Moles
        n_layout = QHBoxLayout()
        n_label = QLabel("Moles (n):")
        self.gas_moles_input = QDoubleSpinBox()
        self.gas_moles_input.setRange(0, 9999999)
        self.gas_moles_input.setDecimals(6)
        self.gas_moles_input.setValue(0)
        self.gas_moles_input.setSpecialValueText("?")
        n_layout.addWidget(n_label)
        n_layout.addWidget(self.gas_moles_input)
        n_layout.addWidget(QLabel("mol"))
        layout.addLayout(n_layout)

        # Temperature
        t_layout = QHBoxLayout()
        t_label = QLabel("Temperature (T):")
        self.temp_input = QDoubleSpinBox()
        self.temp_input.setRange(0, 9999999)
        self.temp_input.setDecimals(2)
        self.temp_input.setValue(0)
        self.temp_input.setSpecialValueText("?")
        self.temp_unit = QComboBox()
        self.temp_unit.addItems(["K", "°C"])
        t_layout.addWidget(t_label)
        t_layout.addWidget(self.temp_input)
        t_layout.addWidget(self.temp_unit)
        layout.addLayout(t_layout)

        # Calculate button
        calc_btn = QPushButton("Calculate")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        calc_btn.clicked.connect(self._calculate_gas_law)
        layout.addWidget(calc_btn)

        # Result
        self.result_label = QLabel("Enter 3 values, leave 1 as '?' to calculate")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: white;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.result_label)

        form_group.setLayout(layout)
        self.dialog.dynamic_layout.addWidget(form_group)

        back_btn = QPushButton("← Back to Calculations")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self._back_to_menu)
        self.dialog.dynamic_layout.addWidget(back_btn)

    def _create_stoichiometry_form(self):
        """Create stoichiometry calculation form."""
        form_group = QGroupBox("Stoichiometric Ratios")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Show reaction if available
        reaction = getattr(self.dialog, 'selected_reaction', None)
        if reaction:
            reaction_text = reaction.get('reaction_text', 'No reaction selected')
            r_label = QLabel(f"Reaction: {reaction_text}")
            r_label.setWordWrap(True)
            r_label.setStyleSheet("color: #0078d4; font-weight: bold; padding: 10px; background: #1e1e1e; border-radius: 5px;")
            layout.addWidget(r_label)

        info = QLabel("Enter moles of one compound, calculate moles of another using coefficients")
        info.setStyleSheet("color: #666; font-style: italic;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Compound A (known)
        a_layout = QHBoxLayout()
        a_label = QLabel("Known Compound:")
        self.known_compound = QLineEdit()
        self.known_compound.setPlaceholderText("e.g., 2H2O or H2O")
        a_layout.addWidget(a_label)
        a_layout.addWidget(self.known_compound)
        layout.addLayout(a_layout)

        # Moles of A
        moles_a_layout = QHBoxLayout()
        moles_a_label = QLabel("Moles of Known:")
        self.known_moles = QDoubleSpinBox()
        self.known_moles.setRange(0, 9999999)
        self.known_moles.setDecimals(6)
        self.known_moles.setValue(0)
        self.known_moles.setSpecialValueText("?")
        moles_a_layout.addWidget(moles_a_label)
        moles_a_layout.addWidget(self.known_moles)
        moles_a_layout.addWidget(QLabel("mol"))
        layout.addLayout(moles_a_layout)

        # Compound B (unknown)
        b_layout = QHBoxLayout()
        b_label = QLabel("Target Compound:")
        self.target_compound = QLineEdit()
        self.target_compound.setPlaceholderText("e.g., CO2")
        b_layout.addWidget(b_label)
        b_layout.addWidget(self.target_compound)
        layout.addLayout(b_layout)

        # Calculate button
        calc_btn = QPushButton("Calculate Moles of Target")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e56b0a;
            }
        """)
        calc_btn.clicked.connect(self._calculate_stoichiometry)
        layout.addWidget(calc_btn)

        # Result
        self.result_label = QLabel("Enter compounds and moles, then calculate")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: white;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.result_label)

        form_group.setLayout(layout)
        self.dialog.dynamic_layout.addWidget(form_group)

        back_btn = QPushButton("← Back to Calculations")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self._back_to_menu)
        self.dialog.dynamic_layout.addWidget(back_btn)

    def _create_percent_yield_form(self):
        """Create percent yield calculation form."""
        form_group = QGroupBox("Percent Yield = (Actual / Theoretical) × 100")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Actual yield
        actual_layout = QHBoxLayout()
        actual_label = QLabel("Actual Yield:")
        self.actual_yield = QDoubleSpinBox()
        self.actual_yield.setRange(0, 9999999)
        self.actual_yield.setDecimals(4)
        self.actual_yield.setValue(0)
        self.actual_yield.setSpecialValueText("?")
        self.actual_unit = QComboBox()
        self.actual_unit.addItems(["g", "kg", "mg", "mol"])
        actual_layout.addWidget(actual_label)
        actual_layout.addWidget(self.actual_yield)
        actual_layout.addWidget(self.actual_unit)
        layout.addLayout(actual_layout)

        # Theoretical yield
        theor_layout = QHBoxLayout()
        theor_label = QLabel("Theoretical Yield:")
        self.theoretical_yield = QDoubleSpinBox()
        self.theoretical_yield.setRange(0, 9999999)
        self.theoretical_yield.setDecimals(4)
        self.theoretical_yield.setValue(0)
        self.theoretical_yield.setSpecialValueText("?")
        self.theor_unit = QComboBox()
        self.theor_unit.addItems(["g", "kg", "mg", "mol"])
        theor_layout.addWidget(theor_label)
        theor_layout.addWidget(self.theoretical_yield)
        theor_layout.addWidget(self.theor_unit)
        layout.addLayout(theor_layout)

        # Calculate button
        calc_btn = QPushButton("Calculate Percent Yield")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #20c997;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1ba87e;
            }
        """)
        calc_btn.clicked.connect(self._calculate_percent_yield)
        layout.addWidget(calc_btn)

        # Result
        self.result_label = QLabel("Enter yields and click Calculate")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: white;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.result_label)

        form_group.setLayout(layout)
        self.dialog.dynamic_layout.addWidget(form_group)

        back_btn = QPushButton("← Back to Calculations")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self._back_to_menu)
        self.dialog.dynamic_layout.addWidget(back_btn)

    def _create_percent_composition_form(self):
        """Create percent composition calculation form."""
        form_group = QGroupBox("Percent Composition by Mass")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Compound input
        compound_layout = QHBoxLayout()
        compound_label = QLabel("Compound Formula:")
        self.comp_formula_input = QLineEdit()

        # Pre-fill if compound selected
        compound = self._get_current_compound()
        if compound:
            # Remove state suffix if present
            clean = re.sub(r'\([a-z]+\)$', '', compound, flags=re.IGNORECASE)
            self.comp_formula_input.setText(clean)

        compound_layout.addWidget(compound_label)
        compound_layout.addWidget(self.comp_formula_input)
        layout.addLayout(compound_layout)

        # Calculate button
        calc_btn = QPushButton("Calculate Composition")
        calc_btn.setMinimumHeight(40)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #e83e8c;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d62a7a;
            }
        """)
        calc_btn.clicked.connect(self._calculate_percent_composition)
        layout.addWidget(calc_btn)

        # Result (multi-line)
        self.result_label = QLabel("Enter formula and click Calculate")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: white;
                padding: 15px;
                border-radius: 5px;
                font-size: 13px;
                min-height: 100px;
            }
        """)
        layout.addWidget(self.result_label)

        # Auto-calculate if compound is pre-filled
        if compound:
            self._calculate_percent_composition()

        form_group.setLayout(layout)
        self.dialog.dynamic_layout.addWidget(form_group)

        back_btn = QPushButton("← Back to Calculations")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self._back_to_menu)
        self.dialog.dynamic_layout.addWidget(back_btn)

    # ========== CALCULATION METHODS ==========

    def _calculate_mass_mole(self):
        """Calculate mass/mole conversion."""
        mass = self.mass_input.value()
        moles = self.moles_input.value()
        mass_unit = self.mass_unit.currentText()

        # Get molar mass
        compound = self._get_current_compound()
        if not compound:
            self.result_label.setText("Error: No compound selected")
            return

        molar_mass = self._get_molar_mass(compound)
        if not molar_mass:
            self.result_label.setText("Error: Could not calculate molar mass")
            return

        # Convert mass to grams
        if mass_unit == "kg":
            mass_g = mass * 1000
        elif mass_unit == "mg":
            mass_g = mass / 1000
        else:
            mass_g = mass

        # Determine what to calculate
        if mass == 0 and moles > 0:
            # Calculate mass from moles
            mass_g_calc = moles * molar_mass
            if mass_unit == "kg":
                result_mass = mass_g_calc / 1000
            elif mass_unit == "mg":
                result_mass = mass_g_calc * 1000
            else:
                result_mass = mass_g_calc
            self.result_label.setText(
                f"Result: {result_mass:.4f} {mass_unit} of {compound}\n"
                f"({moles:.6f} mol × {molar_mass:.2f} g/mol = {mass_g_calc:.2f} g)"
            )
            self.mass_input.setValue(result_mass)
        elif moles == 0 and mass > 0:
            # Calculate moles from mass
            calc_moles = mass_g / molar_mass
            self.result_label.setText(
                f"Result: {calc_moles:.6f} moles of {compound}\n"
                f"({mass_g:.2f} g ÷ {molar_mass:.2f} g/mol = {calc_moles:.6f} mol)"
            )
            self.moles_input.setValue(calc_moles)
        elif mass > 0 and moles > 0:
            # Verify
            calc_moles = mass_g / molar_mass
            error = abs(calc_moles - moles) / moles * 100 if moles > 0 else 0
            self.result_label.setText(
                f"Verification:\n"
                f"Given: {moles:.6f} mol\n"
                f"Calculated: {calc_moles:.6f} mol\n"
                f"Difference: {error:.2f}%"
            )
        else:
            self.result_label.setText("Error: Enter at least one value (mass or moles)")

    def _calculate_concentration(self):
        """Calculate concentration (molarity)."""
        moles = self.moles_input.value()
        vol = self.vol_input.value()
        conc = self.conc_input.value()
        vol_unit = self.vol_unit.currentText()

        # Convert volume to liters
        if vol_unit == "mL":
            vol_L = vol / 1000
        else:
            vol_L = vol

        # Count how many are set
        set_values = sum([1 for v in [moles, vol, conc] if v > 0])

        if set_values < 2:
            self.result_label.setText("Error: Enter at least 2 values")
            return

        if moles > 0 and vol > 0 and conc == 0:
            # Calculate M
            M = moles / vol_L if vol_L > 0 else 0
            self.result_label.setText(
                f"Molarity = {M:.6f} M\n"
                f"({moles:.4f} mol / {vol_L:.4f} L = {M:.4f} mol/L)"
            )
            self.conc_input.setValue(M)
        elif conc > 0 and vol > 0 and moles == 0:
            # Calculate moles
            n = conc * vol_L
            self.result_label.setText(
                f"Moles = {n:.6f} mol\n"
                f"({conc:.4f} M × {vol_L:.4f} L = {n:.4f} mol)"
            )
            self.moles_input.setValue(n)
        elif conc > 0 and moles > 0 and vol == 0:
            # Calculate volume
            V_L = moles / conc if conc > 0 else 0
            if vol_unit == "mL":
                V = V_L * 1000
            else:
                V = V_L
            self.result_label.setText(
                f"Volume = {V:.4f} {vol_unit}\n"
                f"({moles:.4f} mol / {conc:.4f} M = {V_L:.4f} L)"
            )
            self.vol_input.setValue(V)
        else:
            # Verify
            calc_M = moles / vol_L if vol_L > 0 else 0
            error = abs(calc_M - conc) / conc * 100 if conc > 0 else 0
            self.result_label.setText(
                f"Verification:\n"
                f"Given M: {conc:.4f}\n"
                f"Calculated M: {calc_M:.4f}\n"
                f"Difference: {error:.2f}%"
            )

    def _update_conc_calc(self, unit):
        """Update concentration calculation when unit changes."""
        pass  # Values are converted on calculate

    def _calculate_gas_law(self):
        """Calculate using ideal gas law."""
        P = self.pressure_input.value()
        V = self.gas_vol_input.value()
        n = self.gas_moles_input.value()
        T = self.temp_input.value()

        P_unit = self.pressure_unit.currentText()
        V_unit = self.gas_vol_unit.currentText()
        T_unit = self.temp_unit.currentText()

        # Convert to standard units (atm, L, K)
        if P_unit == "kPa":
            P_atm = P / 101.325
        elif P_unit == "mmHg":
            P_atm = P / 760
        else:
            P_atm = P

        if V_unit == "mL":
            V_L = V / 1000
        else:
            V_L = V

        if T_unit == "°C":
            T_K = T + 273.15
        else:
            T_K = T

        R = 0.08206

        # Count unknowns
        unknowns = sum([1 for v in [P, V, n, T] if v == 0])

        if unknowns != 1:
            self.result_label.setText("Error: Leave exactly ONE value as '?' to calculate")
            return

        if P == 0:
            # Calculate P
            P_atm_calc = (n * R * T_K) / V_L if V_L > 0 else 0
            if P_unit == "kPa":
                result = P_atm_calc * 101.325
            elif P_unit == "mmHg":
                result = P_atm_calc * 760
            else:
                result = P_atm_calc
            self.result_label.setText(
                f"Pressure = {result:.4f} {P_unit}\n"
                f"(P = nRT/V = {n:.4f}×{R}×{T_K:.2f}/{V_L:.4f})"
            )
            self.pressure_input.setValue(result)
        elif V == 0:
            # Calculate V
            V_L_calc = (n * R * T_K) / P_atm if P_atm > 0 else 0
            if V_unit == "mL":
                result = V_L_calc * 1000
            else:
                result = V_L_calc
            self.result_label.setText(
                f"Volume = {result:.4f} {V_unit}\n"
                f"(V = nRT/P = {n:.4f}×{R}×{T_K:.2f}/{P_atm:.4f})"
            )
            self.gas_vol_input.setValue(result)
        elif n == 0:
            # Calculate n
            n_calc = (P_atm * V_L) / (R * T_K) if T_K > 0 else 0
            self.result_label.setText(
                f"Moles = {n_calc:.6f} mol\n"
                f"(n = PV/RT = {P_atm:.4f}×{V_L:.4f}/({R}×{T_K:.2f}))"
            )
            self.gas_moles_input.setValue(n_calc)
        elif T == 0:
            # Calculate T
            T_K_calc = (P_atm * V_L) / (n * R) if n > 0 else 0
            if T_unit == "°C":
                result = T_K_calc - 273.15
            else:
                result = T_K_calc
            self.result_label.setText(
                f"Temperature = {result:.2f} {T_unit}\n"
                f"(T = PV/nR = {P_atm:.4f}×{V_L:.4f}/({n:.4f}×{R}))"
            )
            self.temp_input.setValue(result)

    def _calculate_stoichiometry(self):
        """Calculate stoichiometric amounts."""
        known = self.known_compound.text().strip()
        target = self.target_compound.text().strip()
        known_moles = self.known_moles.value()

        if not known or not target:
            self.result_label.setText("Error: Enter both compounds")
            return

        if known_moles == 0:
            self.result_label.setText("Error: Enter moles of known compound")
            return

        # Extract coefficients and formulas
        known_coef, known_formula = self._parse_compound_string(known)
        target_coef, target_formula = self._parse_compound_string(target)

        # Calculate moles of target using mole ratio
        # mole_ratio = target_coef / known_coef
        if known_coef == 0:
            known_coef = 1
        if target_coef == 0:
            target_coef = 1

        ratio = target_coef / known_coef
        target_moles = known_moles * ratio

        # Get molar mass of target
        target_mm = self._get_molar_mass(target_formula)

        result_text = (
            f"Mole Ratio: {target_coef}:{known_coef} = {ratio:.4f}\n"
            f"Moles of {target}: {target_moles:.6f} mol\n"
        )

        if target_mm:
            target_mass = target_moles * target_mm
            result_text += f"Mass of {target}: {target_mass:.2f} g"

        self.result_label.setText(result_text)

    def _calculate_percent_yield(self):
        """Calculate percent yield."""
        actual = self.actual_yield.value()
        theoretical = self.theoretical_yield.value()

        if actual == 0 or theoretical == 0:
            self.result_label.setText("Error: Enter both actual and theoretical yields")
            return

        percent = (actual / theoretical) * 100

        self.result_label.setText(
            f"Percent Yield = {percent:.2f}%\n"
            f"({actual:.4f} / {theoretical:.4f} × 100 = {percent:.2f}%)\n"
            f"Efficiency: {'Excellent' if percent >= 90 else 'Good' if percent >= 70 else 'Fair' if percent >= 50 else 'Poor'}"
        )

    def _calculate_percent_composition(self):
        """Calculate percent composition by mass."""
        formula = self.comp_formula_input.text().strip()

        if not formula:
            self.result_label.setText("Error: Enter a formula")
            return

        try:
            # Normalize and calculate
            normalized = ChemLabParser.normalize_formula(formula)
            molar_mass = ChemLabParser.calculate_molar_mass(normalized)

            if not molar_mass:
                self.result_label.setText("Error: Could not calculate molar mass")
                return

            # Parse elements
            elements = ChemLabParser.parse_formula(normalized)

            # Calculate composition
            result_lines = [f"Total Molar Mass: {molar_mass:.2f} g/mol\n"]
            result_lines.append("Element Composition:")
            result_lines.append("-" * 30)

            for element, count in sorted(elements.items()):
                try:

                    elem_data = get_element(element)
                    atomic_mass = elem_data.atomic_weight
                    mass_in_compound = count * atomic_mass
                    percent = (mass_in_compound / molar_mass) * 100
                    result_lines.append(
                        f"{element:2s}: {count:3.0f} atoms × {atomic_mass:6.2f} = "
                        f"{mass_in_compound:7.2f} g ({percent:5.2f}%)"
                    )
                except:
                    pass

            self.result_label.setText("\n".join(result_lines))

        except Exception as e:
            self.result_label.setText(f"Error: {str(e)}")

    # ========== UTILITY METHODS ==========

    def _get_current_compound(self):
        """Get the currently selected compound."""
        # First check dialog's selected_compound
        if hasattr(self.dialog, 'selected_compound') and self.dialog.selected_compound:
            return self.dialog.selected_compound

        # Check compound_data keys
        if hasattr(self.dialog, 'compound_data') and self.dialog.compound_data:
            compounds = list(self.dialog.compound_data.keys())
            if compounds:
                return compounds[0]

        # Check if there's a reaction selected - extract first compound
        reaction = getattr(self.dialog, 'selected_reaction', None)
        if reaction:
            reaction_text = reaction.get('reaction_text', '')
            data = self._extract_compounds_from_reaction(reaction_text)
            if data['reactants']:
                return data['reactants'][0]

        return None

    def _get_molar_mass(self, compound):
        """Calculate molar mass of a compound."""
        if not compound:
            return None

        try:
            # Remove state suffix
            clean = re.sub(r'\([a-z]+\)$', '', compound, flags=re.IGNORECASE)
            normalized = ChemLabParser.normalize_formula(clean)
            return ChemLabParser.calculate_molar_mass(normalized)
        except:
            return None

    def _parse_compound_string(self, text):
        """Parse compound string like '2H2O' into (coefficient, formula)."""
        match = re.match(r'(\d+)?([A-Za-z0-9]+)', text.strip())
        if match:
            coef = int(match.group(1)) if match.group(1) else 1
            formula = match.group(2)
            return coef, formula
        return 1, text

    def _extract_compounds_from_reaction(self, reaction_text):
        """Extract compounds from reaction text."""
        try:
            reactants_str, products_str = ChemLabParser.split_reaction(reaction_text)

            reactants = [c.strip() for c in reactants_str.split('+') if c.strip()]
            products = [c.strip() for c in products_str.split('+') if c.strip()]

            arrow = '→'
            for a in ['→', '←', '⇌', '⇋', '↔']:
                if a in reaction_text:
                    arrow = a
                    break

            return {
                'reactants': reactants,
                'products': products,
                'arrow': arrow
            }
        except:
            return {'reactants': [], 'products': [], 'arrow': '→'}

    def _back_to_menu(self):
        """Go back to calculation menu."""
        self.dialog.show_calculation_menu()
