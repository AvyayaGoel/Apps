"""Base CalculateDialog with common functionality and ViewManager integration."""
import logging
import re

from PyQt6.QtCore import Qt, pyqtSignal, QCoreApplication
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QLineEdit, QComboBox, QScrollArea,
    QWidget, QDoubleSpinBox, QTableWidget
)
from mendeleev import element as get_element

from calculate_dialog_views import ViewManager, ViewState
from chemlab_parser import ChemLabParser


class CalculateDialogBase(QDialog):
    """Base dialog for chemistry calculations with ViewManager integration."""

    reaction_selected = pyqtSignal(dict)
    selection_cancelled = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        logging.info("[DEBUG] CalculateDialogBase __init__ - START")

        self.db = db
        self.parent_window = parent

        # Initialize all widgets first
        self._init_widgets()

        # State tracking
        self.selected_reaction = None
        self.selected_compound = None
        self.compound_data = {}
        self.configured_side = None
        self.compound_side_map = {}
        self.current_mode = None
        self.mode_data = {}

        # UI setup
        self.setWindowTitle("Calculate - Select Reference")
        self.setGeometry(300, 300, 450, 400)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self._init_ui()

        # Initialize view manager after UI is ready
        self.view_manager = ViewManager(self)

        logging.info("[DEBUG] CalculateDialogBase __init__ - END")

    def _init_widgets(self):
        """Initialize all widget variables."""
        # Scroll area and main container
        self.scroll = QScrollArea()
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)

        # Title and status
        self.title_label = QLabel("What would you like to calculate in reference to?")
        self.status_label = QLabel("Select an option above to continue")

        # Selection buttons
        self.selection_group = QGroupBox("Select Reference Type")
        self.formula_btn = QPushButton("🧪 Formula (from Saved Reactions)")
        self.compound_btn = QPushButton("⚗️ Specific Compound")

        # Common controls
        self.reaction_display = QLabel("")
        self.continue_btn = QPushButton("Continue →")
        self.back_btn = QPushButton("← Back")

        # Dynamic content area
        self.dynamic_area = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_area)

        # Formula/Entry widgets
        self.compound_formula_entry = QLineEdit()
        self.compound_state_combo = QComboBox()

        # Results table
        self.results_table = QTableWidget()

        # Mode buttons (for compound editor)
        self.mass_mode_btn = None
        self.solution_mode_btn = None
        self.gas_mode_btn = None

        # Input stack (QStackedWidget)
        self.input_stack = None
        self.mass_page = None
        self.solution_page = None
        self.gas_page = None

        # Input widgets
        self.mass_input = None
        self.mass_unit_combo = None
        self.conc_input = None
        self.conc_unit_combo = None
        self.solution_volume_input = None
        self.solution_volume_unit = None
        self.gas_pressure_input = None
        self.gas_pressure_unit = None
        self.gas_volume_input = None
        self.gas_volume_unit = None
        self.gas_temp_input = None
        self.gas_temp_unit = None

        # Other widgets
        self.mode_description_label = QLabel('')
        self.calc_moles_display = QLabel('0.0 mol')
        self.purity_spin = QDoubleSpinBox()
        self.compound_buttons = {}
        self.configured_label = QLabel("No compounds configured yet")
        self.to_calculations_btn = QPushButton("Continue to Calculations →")

    def _init_ui(self):
        """Initialize the UI layout."""
        logging.info("[DEBUG] _init_ui - START")

        # Scroll area setup
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        # Main layout
        self.main_layout.setSpacing(15)

        # Create initial view
        self._create_initial_view()

        # Set scroll widget
        self.scroll.setWidget(self.main_widget)

        # Outer layout
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.scroll)

        logging.info("[DEBUG] _init_ui - END")

    def _create_initial_view(self):
        """Create the initial selection view."""
        logging.info("[DEBUG] _create_initial_view - START")

        # Title
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.title_label)

        # Selection group
        selection_layout = QVBoxLayout()
        selection_layout.setSpacing(10)

        self.formula_btn.setMinimumHeight(50)
        self.formula_btn.setFont(QFont("Segoe UI", 11))
        selection_layout.addWidget(self.formula_btn)

        self.compound_btn.setMinimumHeight(50)
        self.compound_btn.setFont(QFont("Segoe UI", 11))
        selection_layout.addWidget(self.compound_btn)

        self.selection_group.setLayout(selection_layout)
        self.main_layout.addWidget(self.selection_group)

        # Reaction display (hidden)
        self.reaction_display.setFont(QFont("Segoe UI", 10))
        self.reaction_display.setWordWrap(True)
        self.reaction_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reaction_display.setStyleSheet(
            "background-color: #000000; color: #ffffff; padding: 10px; "
            "border-radius: 5px; border: 1px solid #0078d4;"
        )
        self.reaction_display.setVisible(False)
        self.main_layout.addWidget(self.reaction_display)

        # Continue button (hidden)
        self.continue_btn.setMinimumHeight(40)
        self.continue_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.continue_btn.setEnabled(False)
        self.continue_btn.setVisible(False)
        self.main_layout.addWidget(self.continue_btn)

        # Back button (hidden)
        self.back_btn.setMinimumHeight(35)
        self.back_btn.setVisible(False)
        self.main_layout.addWidget(self.back_btn)

        # Status label
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666;")
        self.main_layout.addWidget(self.status_label)

        # Dynamic area
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.dynamic_area)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reset_and_close)
        self.main_layout.addWidget(close_btn)

        self.main_layout.addStretch()

        logging.info("[DEBUG] _create_initial_view - END")

    def clear_dynamic_area(self):
        """Clear all widgets from dynamic area."""
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def auto_resize(self):
        """Auto-resize dialog to fit content."""
        QCoreApplication.processEvents()

        self.main_widget.adjustSize()
        self.scroll.adjustSize()

        size_hint = self.main_widget.sizeHint()
        scroll_hint = self.scroll.sizeHint()

        frame_margin = 50
        new_width = max(size_hint.width(), scroll_hint.width()) + frame_margin
        new_height = max(size_hint.height(), scroll_hint.height()) + frame_margin

        # Min size
        min_width, min_height = 500, 400
        new_width = max(new_width, min_width)
        new_height = max(new_height, min_height)

        # Max size (screen limits)
        screen = self.screen()
        if screen:
            max_width = int(screen.availableGeometry().width() * 0.9)
            max_height = int(screen.availableGeometry().height() * 0.9)
            new_width = min(new_width, max_width)
            new_height = min(new_height, max_height)

        current_geom = self.geometry()
        self.setGeometry(current_geom.x(), current_geom.y(), new_width, new_height)
        logging.info(f"[auto_resize] Resized to {new_width}x{new_height}")

    def reset_and_close(self):
        """Reset and close dialog."""
        self.reset_dialog()
        self.close()

    def reset_dialog(self):
        """Reset dialog to initial state."""
        if self.parent_window and hasattr(self.parent_window, 'disable_reaction_selection_mode'):
            self.parent_window.disable_reaction_selection_mode()

        self.selected_reaction = None
        self.selected_compound = None
        self.compound_data = {}
        self.configured_side = None
        self.compound_side_map = {}
        self.current_mode = None

        self.compound_formula_entry.clear()
        self.compound_formula_entry.setStyleSheet("")

        # Use view manager to go to initial state
        if hasattr(self, 'view_manager'):
            self.view_manager.switch_to(ViewState.INITIAL)

    def closeEvent(self, event):
        """Handle close event."""
        self.reset_dialog()
        event.accept()

    def validate_compound_formula(self, formula=None):
        """Validate compound formula. Returns True if valid."""
        if formula is None:
            formula = self.compound_formula_entry.text().strip()

        if not formula:
            return False

        normalized = ChemLabParser.normalize_formula(formula)
        clean_formula = re.sub(r'\([a-z]+\)$', '', normalized, flags=re.IGNORECASE)

        try:
            elements_dict = ChemLabParser.parse_formula(clean_formula)
            elements = list(elements_dict.keys())
        except:
            return False

        if not elements:
            return False

        for elem in elements:
            try:
                get_element(elem)
            except (ValueError, KeyError):
                return False

        return True
