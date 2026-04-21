"""Calculate dialog for chemistry calculations - Main entry point.

This module provides the main CalculateDialog class which coordinates
between different view modes (Formula and Compound) using separate
handler modules for clean separation of concerns.
"""
import logging

from calculate_dialog_base import CalculateDialogBase
from calculate_dialog_compound import CompoundViewHandler
from calculate_dialog_formula import FormulaViewHandler
from calculate_dialog_views import ViewState


class CalculateDialog(CalculateDialogBase):
    """Dialog for selecting calculation type and reference.
    
    Uses ViewManager for clean view transitions and separates
    Formula and Compound mode logic into dedicated handlers.
    """

    def __init__(self, db, parent=None):
        """Initialize the dialog with handlers."""
        super().__init__(db, parent)

        # Initialize handlers
        self.formula_handler = FormulaViewHandler(self)
        self.compound_handler = CompoundViewHandler(self)

        # Connect button signals
        self._connect_signals()

        logging.info("[DEBUG] CalculateDialog initialized with handlers")

    def _connect_signals(self):
        """Connect button signals to handlers."""
        # Formula button -> Formula handler
        self.formula_btn.clicked.connect(self.formula_handler.on_formula_selected)

        # Compound button -> Compound handler
        self.compound_btn.clicked.connect(self.compound_handler.on_compound_selected)

        # Continue button -> Route to appropriate handler
        self.continue_btn.clicked.connect(self._on_continue_clicked)

        # Back button -> Go back
        self.back_btn.clicked.connect(self._on_back_clicked)

    def _on_continue_clicked(self):
        """Route continue button to appropriate handler."""
        logging.info(f"[DEBUG] Continue clicked, mode: {self.current_mode}")

        if self.current_mode == 'formula':
            self.formula_handler.on_continue_clicked()
        elif self.current_mode == 'compound':
            self.compound_handler.on_continue_clicked()
        else:
            logging.warning("Continue clicked but no mode selected")

    def _on_back_clicked(self):
        """Handle back button based on current state."""
        current_state = self.view_manager.get_current_state()
        logging.info(f"[DEBUG] Back clicked from state: {current_state.name}")

        if current_state in [ViewState.INITIAL]:
            # Already at main screen, nothing to do
            pass
        elif current_state in [ViewState.FORMULA_WAITING, ViewState.FORMULA_SELECTION]:
            # Cancel formula mode
            if self.parent_window and hasattr(self.parent_window, 'disable_reaction_selection_mode'):
                self.parent_window.disable_reaction_selection_mode()
            self.reset_dialog()
        elif current_state == ViewState.FORMULA_COMPOUND_EDITOR:
            # Back to formula selection
            self.formula_handler.show_compound_selection()
        elif current_state in [ViewState.COMPOUND_ENTRY, ViewState.COMPOUND_EDITOR]:
            # Back to main screen
            self.reset_dialog()
        elif current_state == ViewState.RESULTS:
            # Back to appropriate previous screen
            if self.current_mode == 'formula':
                self.formula_handler.show_compound_selection()
            else:
                self.reset_dialog()
        else:
            # Default: reset to initial
            self.reset_dialog()

    def on_reaction_selected(self, reaction):
        """Handle reaction selection from main window.
        
        Delegates to formula handler.
        """
        self.formula_handler.on_reaction_selected(reaction)

    def on_selection_cancelled(self):
        """Handle selection cancellation from main window."""
        self.status_label.setText("Selection cancelled. Select an option to try again.")
        self.status_label.setStyleSheet("color: #666;")
        self.formula_btn.setEnabled(True)
        self.compound_btn.setEnabled(True)
        self.selection_cancelled.emit()

    def show_calculation_menu(self):
        """Show calculation menu based on current mode.

        This method avoids circular imports by delegating to the appropriate handler
        that is already initialized in __init__.
        """
        if self.current_mode == 'formula':
            self.formula_handler._show_calculation_buttons()
        elif self.current_mode == 'compound':
            self.formula_handler._show_compound_calculation_menu()
        else:
            logging.warning("Cannot show calculation menu: no mode selected")


# Keep backward compatibility
__all__ = ['CalculateDialog']
