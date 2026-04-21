"""Formula mode view handling for CalculateDialog."""
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QWidget, QMessageBox
)

from calculate_dialog_calcs import CalculationHandler
from calculate_dialog_views import ViewState
from chemlab_parser import ChemLabParser
from constants import ARROWS


class FormulaViewHandler:
    """Handles all Formula mode views and transitions."""

    def __init__(self, dialog):
        """Initialize with parent dialog."""
        self.dialog = dialog

    def on_formula_selected(self):
        """Handle Formula button click - enters formula waiting state."""
        if not self.dialog.parent_window:
            QMessageBox.warning(self.dialog, "Error", "Parent window not available")
            return

        if not hasattr(self.dialog.parent_window, 'enable_reaction_selection_mode'):
            QMessageBox.warning(self.dialog, "Error", "Parent window does not support selection mode")
            return

        self.dialog.current_mode = 'formula'
        self.dialog.title_label.setText("Select a Reaction from the Main Window")
        self.dialog.status_label.setText("Please select a reaction from the main window...")
        self.dialog.status_label.setStyleSheet("color: #0078d4; font-weight: bold;")

        self.dialog.parent_window.enable_reaction_selection_mode(self.dialog)

        # Switch to formula waiting view
        self.dialog.view_manager.switch_to(ViewState.FORMULA_WAITING, clear_dynamic=True)

    def on_reaction_selected(self, reaction):
        """Called when a reaction is selected from main window."""
        self.dialog.selected_reaction = reaction
        self.dialog.title_label.setText("Reaction Selected - Continue to Configuration")
        self.dialog.reaction_display.setText(
            f"Selected Reaction:\n{reaction.get('reaction_text', 'Unknown')}"
        )

        # Enable continue button
        self.dialog.continue_btn.setEnabled(True)

        # Update status
        self.dialog.status_label.setText("Click Continue to proceed with calculation options")
        self.dialog.status_label.setStyleSheet("color: #00aa00;")

        # Emit signal
        self.dialog.reaction_selected.emit(reaction)

        # Note: Don't auto-switch - wait for user to click Continue
        self.dialog.view_manager.switch_to(ViewState.FORMULA_WAITING, clear_dynamic=False)
        self.dialog.reaction_display.setVisible(True)
        self.dialog.continue_btn.setVisible(True)
        self.dialog.auto_resize()

    def on_continue_clicked(self):
        """Handle Continue button in formula mode - skip compound config, go straight to calculations."""
        self._show_calculation_buttons()

    def show_compound_selection(self):
        """Show compound selection UI for formula mode."""
        logging.info("[FormulaViewHandler] show_compound_selection - START")

        # Switch to formula selection view
        self.dialog.view_manager.switch_to(ViewState.FORMULA_SELECTION, clear_dynamic=True)

        self.dialog.title_label.setText("Configure Compounds in Reaction")
        self.dialog.status_label.setText("Click on any compound to configure its properties")

        # Get compounds from reaction
        reaction_text = self.dialog.selected_reaction.get('reaction_text', '')
        data = self._extract_compounds_from_reaction(reaction_text)

        # Create compounds group
        compounds_group = QGroupBox("Compounds in Reaction - Click to Configure")
        compounds_layout = QVBoxLayout()
        compounds_layout.setSpacing(15)

        # Create reaction row
        reaction_row = QHBoxLayout()
        reaction_row.setSpacing(5)
        reaction_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add reactants
        self._add_compound_buttons(reaction_row, data['reactants'], 'reactants', data)

        # Add arrow
        arrow_label = QLabel(data['arrow'])
        arrow_label.setFont(QFont("Segoe UI", 16))
        reaction_row.addWidget(arrow_label)

        # Add products
        self._add_compound_buttons(reaction_row, data['products'], 'products', data)

        reaction_row.addStretch()

        # Wrap in widget
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

        # Add configured indicator
        if self.dialog.configured_side:
            side_name = "Reactants" if self.dialog.configured_side == 'reactants' else "Products"
            self.dialog.configured_label.setText(
                f"✓ Configuring {side_name} side only (other side locked)"
            )
            self.dialog.configured_label.setStyleSheet("color: #00aa00; font-weight: bold;")
        else:
            self.dialog.configured_label.setText(
                "No compounds configured yet - Choose Reactants OR Products side"
            )
            self.dialog.configured_label.setStyleSheet("color: #aaaaaa; font-style: italic;")
        self.dialog.configured_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        compounds_layout.addWidget(self.dialog.configured_label)

        compounds_group.setLayout(compounds_layout)
        self.dialog.dynamic_layout.addWidget(compounds_group)

        # Continue button
        self.dialog.to_calculations_btn.setMinimumHeight(40)
        self.dialog.to_calculations_btn.clicked.connect(self._show_calculation_buttons)
        self.dialog.dynamic_layout.addWidget(self.dialog.to_calculations_btn)

        logging.info("[FormulaViewHandler] show_compound_selection - END")
        self.dialog.auto_resize()

    def _add_compound_buttons(self, layout, compounds, side, data):
        """Add compound buttons to layout."""
        for i, compound in enumerate(compounds):
            self.dialog.compound_side_map[compound] = side

            if i > 0:
                plus_label = QLabel("+")
                plus_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                layout.addWidget(plus_label)

            btn = QPushButton(compound)
            btn.setMinimumHeight(40)
            btn.setFont(QFont("Segoe UI", 10))

            # Determine button style based on state
            other_side = 'products' if side == 'reactants' else 'reactants'
            if self.dialog.configured_side == other_side:
                # This side is locked
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
                btn.setToolTip(f"{side.capitalize()} locked - you configured {other_side}")
            elif compound in self.dialog.compound_data:
                # Already configured
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
                    }
                """)
                btn.clicked.connect(lambda checked, c=compound: self._on_compound_clicked(c, side))
            else:
                # Normal button
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
                    }
                """)
                btn.clicked.connect(lambda checked, c=compound: self._on_compound_clicked(c, side))

            layout.addWidget(btn)
            self.dialog.compound_buttons[compound] = btn

    def _on_compound_clicked(self, compound, side):
        """Handle compound button click."""
        self.dialog.configured_side = side
        self._show_compound_editor(compound)

    def _show_compound_editor(self, compound):
        """Show editor for a compound in formula mode."""
        # Lazy import to avoid circular dependency
        from calculate_dialog_compound import CompoundEditor
        editor = CompoundEditor(self.dialog)
        editor.show_for_formula(compound)

    def _show_calculation_buttons(self):
        """Show calculation menu for FORMULA mode (reaction-based calculations)."""
        logging.info("[FormulaViewHandler] Showing formula mode calculation menu")

        # Switch to calculation menu view
        self.dialog.view_manager.switch_to(ViewState.CALCULATION_MENU, clear_dynamic=True)

        self.dialog.title_label.setText("Select Calculation")
        self.dialog.status_label.setText("Calculations based on reaction: " +
                                         self.dialog.selected_reaction.get('reaction_text', 'Unknown')[:50] + "...")

        # Create calculation menu container
        menu_group = QGroupBox("Reaction-Based Calculations")
        menu_layout = QVBoxLayout()
        menu_layout.setSpacing(15)

        # These calculations need a reaction context:

        # 1. Stoichiometry (product/reactant amounts) - needs reaction
        stoich_btn = QPushButton("🔄 Stoichiometric Amounts")
        stoich_btn.setMinimumHeight(50)
        stoich_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        stoich_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #e56b0a;
            }
        """)
        stoich_btn.clicked.connect(lambda: self._on_calc_selected('stoichiometry'))
        menu_layout.addWidget(stoich_btn)

        # 2. Percent yield - needs reaction (actual vs theoretical)
        yield_btn = QPushButton("📊 Percent Yield")
        yield_btn.setMinimumHeight(50)
        yield_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        yield_btn.setStyleSheet("""
            QPushButton {
                background-color: #20c997;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1ba87e;
            }
        """)
        yield_btn.clicked.connect(lambda: self._on_calc_selected('percent_yield'))
        menu_layout.addWidget(yield_btn)

        # 3. Mass/Mole conversion (for any compound in reaction)
        mass_mole_btn = QPushButton("⚖️ Mass ↔ Moles Conversion")
        mass_mole_btn.setMinimumHeight(50)
        mass_mole_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        mass_mole_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        mass_mole_btn.clicked.connect(lambda: self._on_calc_selected('mass_mole'))
        menu_layout.addWidget(mass_mole_btn)

        # 4. Percent composition (for any compound in reaction)
        composition_btn = QPushButton("🧬 Percent Composition")
        composition_btn.setMinimumHeight(50)
        composition_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        composition_btn.setStyleSheet("""
            QPushButton {
                background-color: #e83e8c;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #d62a7a;
            }
        """)
        composition_btn.clicked.connect(lambda: self._on_calc_selected('percent_composition'))
        menu_layout.addWidget(composition_btn)

        menu_layout.addStretch()
        menu_group.setLayout(menu_layout)
        self.dialog.dynamic_layout.addWidget(menu_group)

        # Back button to return to initial selection
        back_btn = QPushButton("← Back")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self.dialog.reset_dialog)
        self.dialog.dynamic_layout.addWidget(back_btn)

        self.dialog.auto_resize()

    def _show_compound_calculation_menu(self):
        """Show calculation menu for COMPOUND mode (single compound calculations)."""
        logging.info("[FormulaViewHandler] Showing compound mode calculation menu")

        # Switch to calculation menu view
        self.dialog.view_manager.switch_to(ViewState.CALCULATION_MENU, clear_dynamic=True)

        compound = self.dialog.selected_compound or "Unknown"
        self.dialog.title_label.setText(f"Calculations for: {compound}")
        self.dialog.status_label.setText("Select a calculation type")

        # Create calculation menu container
        menu_group = QGroupBox("Single Compound Calculations")
        menu_layout = QVBoxLayout()
        menu_layout.setSpacing(15)

        # These work on a single compound:

        # 1. Mass/Mole conversion
        mass_mole_btn = QPushButton("⚖️ Mass ↔ Moles Conversion")
        mass_mole_btn.setMinimumHeight(50)
        mass_mole_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        mass_mole_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        mass_mole_btn.clicked.connect(lambda: self._on_calc_selected('mass_mole'))
        menu_layout.addWidget(mass_mole_btn)

        # 2. Concentration (Molarity) - for solutions
        conc_btn = QPushButton("🧪 Concentration (Molarity)")
        conc_btn.setMinimumHeight(50)
        conc_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        conc_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        conc_btn.clicked.connect(lambda: self._on_calc_selected('concentration'))
        menu_layout.addWidget(conc_btn)

        # 3. Gas law (PV=nRT) - for gases
        gas_btn = QPushButton("💨 Ideal Gas Law (PV=nRT)")
        gas_btn.setMinimumHeight(50)
        gas_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        gas_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        gas_btn.clicked.connect(lambda: self._on_calc_selected('gas_law'))
        menu_layout.addWidget(gas_btn)

        # 4. Percent composition
        composition_btn = QPushButton("🧬 Percent Composition")
        composition_btn.setMinimumHeight(50)
        composition_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        composition_btn.setStyleSheet("""
            QPushButton {
                background-color: #e83e8c;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #d62a7a;
            }
        """)
        composition_btn.clicked.connect(lambda: self._on_calc_selected('percent_composition'))
        menu_layout.addWidget(composition_btn)

        menu_layout.addStretch()
        menu_group.setLayout(menu_layout)
        self.dialog.dynamic_layout.addWidget(menu_group)

        # Back button to return to compound entry
        back_btn = QPushButton("← Back")
        back_btn.setMinimumHeight(35)
        back_btn.clicked.connect(self.dialog.reset_dialog)
        self.dialog.dynamic_layout.addWidget(back_btn)

        self.dialog.auto_resize()

    def _on_calc_selected(self, calc_type):
        """Handle calculation type selection."""
        logging.info(f"[FormulaViewHandler] Calculation selected: {calc_type}")
        # Use the calculation handler to show the proper form

        handler = CalculationHandler(self.dialog)
        handler.show_calculation(calc_type)

    def _extract_compounds_from_reaction(self, reaction_text):
        """Extract compounds from reaction text."""
        try:
            reactants_str, products_str = ChemLabParser.split_reaction(reaction_text)

            if not reactants_str or not products_str:
                return {'reactants': [], 'products': [], 'arrow': '→'}

            reactants = [c.strip() for c in reactants_str.split('+') if c.strip()]
            products = [c.strip() for c in products_str.split('+') if c.strip()]

            arrow = '→'
            for a in ARROWS:
                if a in reaction_text:
                    arrow = a
                    break

            return {'reactants': reactants, 'products': products, 'arrow': arrow}
        except Exception as e:
            logging.error(f"Error extracting compounds: {e}")
            return {'reactants': [], 'products': [], 'arrow': '→'}
