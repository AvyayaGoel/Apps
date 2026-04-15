"""View state management for CalculateDialog.

This module provides centralized view management to ensure clean transitions
between different views without widget conflicts.
"""
import logging
from enum import Enum, auto


class ViewState(Enum):
    """Enumeration of all possible view states in the CalculateDialog."""
    INITIAL = auto()  # Main selection screen (Formula/Compound buttons)
    FORMULA_WAITING = auto()  # Waiting for reaction selection from main window
    FORMULA_SELECTION = auto()  # Reaction selected, showing compound buttons
    FORMULA_COMPOUND_EDITOR = auto()  # Editing a specific compound in formula mode
    COMPOUND_ENTRY = auto()  # Compound mode - entering formula
    COMPOUND_EDITOR = auto()  # Compound mode - editing compound properties
    CALCULATION_MENU = auto()  # Menu with calculation buttons
    RESULTS = auto()  # Showing calculation results


class ViewManager:
    """Manages view state transitions and widget visibility.
    
    Ensures that when switching views:
    1. ALL widgets are hidden first
    2. Only the widgets for the target view are shown
    3. The dialog resizes appropriately
    """

    def __init__(self, dialog):
        """Initialize the view manager.
        
        Args:
            dialog: The CalculateDialog instance to manage
        """
        self.dialog = dialog
        self.current_state = ViewState.INITIAL
        self._state_widgets = {}
        self._setup_widget_registry()

    def _setup_widget_registry(self):
        """Register which widgets belong to which view states."""
        d = self.dialog

        # Widgets for INITIAL state
        self._state_widgets[ViewState.INITIAL] = [
            d.title_label, d.selection_group, d.formula_btn, d.compound_btn,
            d.status_label, d.dynamic_area
        ]

        # Widgets for FORMULA_WAITING state
        self._state_widgets[ViewState.FORMULA_WAITING] = [
            d.title_label, d.status_label, d.back_btn
        ]

        # Widgets for FORMULA_SELECTION state
        self._state_widgets[ViewState.FORMULA_SELECTION] = [
            d.title_label, d.reaction_display, d.back_btn, d.status_label,
            d.dynamic_area
        ]

        # Widgets for FORMULA_COMPOUND_EDITOR state
        self._state_widgets[ViewState.FORMULA_COMPOUND_EDITOR] = [
            d.title_label, d.status_label, d.back_btn, d.dynamic_area
        ]

        # Widgets for COMPOUND_ENTRY state
        self._state_widgets[ViewState.COMPOUND_ENTRY] = [
            d.title_label, d.continue_btn, d.back_btn, d.status_label,
            d.dynamic_area
        ]

        # Widgets for COMPOUND_EDITOR state
        self._state_widgets[ViewState.COMPOUND_EDITOR] = [
            d.title_label, d.status_label, d.back_btn, d.dynamic_area
        ]

        # Widgets for RESULTS state
        self._state_widgets[ViewState.RESULTS] = [
            d.title_label, d.back_btn, d.status_label, d.dynamic_area
        ]

        # Widgets for CALCULATION_MENU state
        self._state_widgets[ViewState.CALCULATION_MENU] = [
            d.title_label, d.back_btn, d.status_label, d.dynamic_area
        ]

    def switch_to(self, new_state: ViewState, clear_dynamic=True):
        """Switch to a new view state.
        
        This method:
        1. Hides ALL registered widgets
        2. Shows only widgets for the target state
        3. Clears dynamic area if requested
        4. Resizes the dialog
        
        Args:
            new_state: The ViewState to switch to
            clear_dynamic: Whether to clear the dynamic area
        """
        logging.info(f"[ViewManager] Switching from {self.current_state.name} to {new_state.name}")

        # Step 1: Hide ALL registered widgets
        for state_widgets in self._state_widgets.values():
            for widget in state_widgets:
                if widget:
                    widget.setVisible(False)

        # Step 2: Clear dynamic area if requested
        if clear_dynamic:
            self.dialog.clear_dynamic_area()

        # Step 3: Update state
        self.current_state = new_state

        # Step 4: Show only widgets for target state
        target_widgets = self._state_widgets.get(new_state, [])
        for widget in target_widgets:
            if widget:
                widget.setVisible(True)

        # Step 5: Resize the dialog
        self.dialog.auto_resize()

        logging.info(f"[ViewManager] Switch to {new_state.name} complete")

    def get_current_state(self) -> ViewState:
        """Get the current view state."""
        return self.current_state

    def is_in_state(self, state: ViewState) -> bool:
        """Check if currently in a specific state."""
        return self.current_state == state
