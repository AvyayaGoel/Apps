"""
Main Window - Calculator V3 Application Window.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QScrollArea, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from calculator_tab import CalculatorTab
from converter_tab import SingleConverter
from conversions import ConversionCategory, get_manager
from constants_calculator import FONT, COLOR_INACTIVE, TITLE_STANDARD_CALC, TITLE_SCIENTIFIC_CALC

class CollapsibleSidebar(QFrame):
    """Collapsible sidebar with scrollable content and icon-only collapsed mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.expanded_width = 220
        self.collapsed_width = 60
        self.is_expanded = True
        self.sidebar_buttons = []
        self.section_labels = []
        self.sidebar_title = None
        self.setFixedWidth(self.expanded_width)
        self._setup_ui()

    def _setup_ui(self):
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header area with toggle button
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 15, 10, 10)
        header_layout.setSpacing(0)

        # Toggle button
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.setFont(QFont(FONT, 14))
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        header_layout.addWidget(self.toggle_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addStretch()

        self.main_layout.addWidget(header)

        # Scroll area for content
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Content widget inside scroll area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)

    def toggle(self):
        """Toggle sidebar expanded/collapsed state."""
        self.is_expanded = not self.is_expanded
        self._update_state()

    def _update_state(self):
        """Update sidebar visual state based on is_expanded."""
        target_width = self.expanded_width if self.is_expanded else self.collapsed_width
        self.toggle_btn.setText("☰" if self.is_expanded else "→")
        self.setFixedWidth(target_width)

        # Update content layout margins based on state
        if self.is_expanded:
            self.content_layout.setContentsMargins(10, 10, 10, 10)
        else:
            self.content_layout.setContentsMargins(5, 10, 5, 10)

    def add_widget(self, widget):
        """Add widget to content layout."""
        self.content_layout.addWidget(widget)

    def add_spacing(self, height):
        """Add spacing to content layout."""
        self.content_layout.addSpacing(height)

    def add_stretch(self):
        """Add stretch to content layout."""
        self.content_layout.addStretch()


class SidebarButton(QPushButton):
    """Custom sidebar button with icon and text that adapts to sidebar state."""

    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.label_text = label
        self._active = False
        self._expanded = True
        self._setup_ui()

    def _setup_ui(self):
        self.setCheckable(True)
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Main horizontal layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Icon container (centered)
        icon_container = QWidget()
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(0)

        self.icon_label = QLabel(self.icon_text)
        self.icon_label.setFont(QFont(FONT, 20))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(COLOR_INACTIVE)
        icon_layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.main_layout.addWidget(icon_container)

        # Text label (hidden when collapsed)
        self.text_label = QLabel(self.label_text)
        self.text_label.setFont(QFont(FONT, 13))
        self.text_label.setStyleSheet(COLOR_INACTIVE)
        self.main_layout.addWidget(self.text_label)

        self.main_layout.addStretch()

        self._update_style()

    def set_expanded(self, expanded: bool):
        """Update button layout based on sidebar state."""
        self._expanded = expanded
        if expanded:
            self.setFixedHeight(50)
            self.main_layout.setContentsMargins(10, 5, 15, 5)
            self.main_layout.setSpacing(12)
            self.text_label.show()
            self.icon_label.setFont(QFont(FONT, 18))
        else:
            self.setFixedHeight(50)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)
            self.text_label.hide()
            self.icon_label.setFont(QFont(FONT, 24))
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet("""
                SidebarButton {
                    background-color: #3a3a3a;
                    border: none;
                    border-radius: 10px;
                }
            """)
            self.icon_label.setStyleSheet("color: #ff9500;")
            self.text_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        else:
            self.setStyleSheet("""
                SidebarButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 10px;
                }
                SidebarButton:hover {
                    background-color: #2a2a2a;
                }
            """)
            self.icon_label.setStyleSheet(COLOR_INACTIVE)
            self.text_label.setStyleSheet(COLOR_INACTIVE)

    def set_active(self, active: bool):
        self._active = active
        self.setChecked(active)
        self._update_style()


class MainWindow(QMainWindow):
    """Main application window for Calculator V3."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculator V3")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup the main UI structure."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal layout (sidebar + content)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        # Content area
        self.content = self._create_content()
        main_layout.addWidget(self.content, stretch=1)

    def _create_sidebar(self) -> CollapsibleSidebar:
        """Create the collapsible navigation sidebar."""
        sidebar = CollapsibleSidebar()
        sidebar.setStyleSheet("""
            CollapsibleSidebar {
                background-color: #1e1e1e;
                border-right: 1px solid #2d2d2d;
            }
        """)

        # App title (only shows when expanded)
        self.sidebar_title = QLabel("⚡ Calc V3")
        self.sidebar_title.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        self.sidebar_title.setStyleSheet("color: #ff9500; padding: 10px 0;")
        sidebar.add_widget(self.sidebar_title)

        # Separator
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #2d2d2d;")
        sidebar.add_widget(separator)

        sidebar.add_spacing(20)

        # Section label
        calc_label = QLabel("CALC")
        calc_label.setFont(QFont(FONT, 9, QFont.Weight.Bold))
        calc_label.setStyleSheet("color: #666666; padding-left: 5px;")
        sidebar.add_widget(calc_label)

        # Standard Calculator button
        self.calc_btn = SidebarButton("🧮", "Standard")
        self.calc_btn.clicked.connect(lambda: self._switch_tab(0, TITLE_STANDARD_CALC))
        sidebar.add_widget(self.calc_btn)

        # Scientific Calculator button
        self.sci_btn = SidebarButton("🔬", "Scientific")
        self.sci_btn.clicked.connect(lambda: self._switch_tab(1, TITLE_SCIENTIFIC_CALC))
        sidebar.add_widget(self.sci_btn)

        sidebar.add_spacing(15)

        # Converters section
        conv_label = QLabel("CONVERT")
        conv_label.setFont(QFont(FONT, 9, QFont.Weight.Bold))
        conv_label.setStyleSheet("color: #666666; padding-left: 5px;")
        sidebar.add_widget(conv_label)

        # Individual category buttons with icons
        self.sidebar_buttons = [self.calc_btn, self.sci_btn]  # Start with calculators
        manager = get_manager()
        categories = manager.get_categories()

        # Category icons mapping
        icons = {
            ConversionCategory.LENGTH: "📏",
            ConversionCategory.AREA: "📐",
            ConversionCategory.VOLUME: "🧪",
            ConversionCategory.MASS: "⚖️",
            ConversionCategory.TEMPERATURE: "🌡️",
            ConversionCategory.SPEED: "🚀",
            ConversionCategory.TIME: "⏱️",
            ConversionCategory.PRESSURE: "💨",
            ConversionCategory.ENERGY: "⚡",
            ConversionCategory.POWER: "🔌",
            ConversionCategory.DATA: "💾",
            ConversionCategory.ANGLE: "📐",
        }

        # Create button for each category (starting from index 2 since calc is 0, sci is 1)
        for idx, (category, name) in enumerate(categories, start=2):
            icon = icons.get(category, "🔧")
            btn = SidebarButton(icon, name)
            btn.clicked.connect(lambda checked, i=idx, n=name: self._switch_tab(i, n))
            sidebar.add_widget(btn)
            self.sidebar_buttons.append(btn)

        sidebar.add_stretch()

        # Version info at bottom
        version = QLabel("v3.0")
        version.setFont(QFont(FONT, 9))
        version.setStyleSheet("color: #555555; padding: 10px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar.add_widget(version)

        # Store references for toggle
        sidebar.sidebar_title = self.sidebar_title
        sidebar.section_labels.extend([calc_label, conv_label])
        sidebar.sidebar_buttons.extend(self.sidebar_buttons)

        # Initialize button states
        for btn in sidebar.sidebar_buttons:
            btn.set_expanded(True)

        # Connect sidebar toggle
        sidebar.toggle_btn.clicked.connect(self._on_sidebar_toggled)

        return sidebar

    def _on_sidebar_toggled(self):
        """Handle sidebar toggle - update button layouts."""
        # Toggle the sidebar state
        self.sidebar.toggle()

        # Update all buttons to expanded/collapsed state
        expanded = self.sidebar.is_expanded
        if expanded:
            self.sidebar_title.setText("⚡ Calc V3")
            # Show section labels
            for label in self.sidebar.section_labels:
                label.show()
        else:
            self.sidebar_title.setText("⚡")
            # Hide section labels
            for label in self.sidebar.section_labels:
                label.hide()

        # Update all buttons
        for btn in self.sidebar.sidebar_buttons:
            btn.set_expanded(expanded)

    def _create_content(self) -> QFrame:
        """Create the main content area."""
        content = QFrame()
        content.setStyleSheet("background-color: #252525;")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2d2d2d;
            }
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        self.header_title = QLabel(TITLE_STANDARD_CALC)
        self.header_title.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        self.header_title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(self.header_title)

        header_layout.addStretch()

        layout.addWidget(self.header)

        # Tab content stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #252525;")

        # Standard Calculator tab (index 0)
        self.calculator_tab = CalculatorTab(mode="standard")
        self.stack.addWidget(self.calculator_tab)

        # Scientific Calculator tab (index 1)
        self.scientific_tab = CalculatorTab(mode="scientific")
        self.stack.addWidget(self.scientific_tab)

        # Individual converter tabs for each category (indices 2-13)
        self.converter_tabs = {}
        manager = get_manager()
        categories = manager.get_categories()

        for category, name in categories:
            converter = SingleConverter(category)
            self.converter_tabs[category] = converter
            self.stack.addWidget(converter)

        layout.addWidget(self.stack)

        # Set initial tab
        self._switch_tab(0, TITLE_STANDARD_CALC)

        return content

    def _switch_tab(self, index: int, title: str):
        """Switch to a different tab with fade animation."""
        if self.stack.currentIndex() == index:
            return  # Already on this tab

        target_index = index
        target_title = title

        # Create opacity effect for fade animation
        if not hasattr(self, '_opacity_effect'):
            self._opacity_effect = QGraphicsOpacityEffect(self.stack)
            self.stack.setGraphicsEffect(self._opacity_effect)

        # Fade out (phase 1)
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(100)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def do_switch():
            # Switch tab at midpoint
            self.stack.setCurrentIndex(target_index)
            self.header_title.setText(target_title)

            # Update button states
            for i, btn in enumerate(self.sidebar_buttons):
                btn.set_active(target_index == i)

            # Fade in (phase 2)
            self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._fade_in.setDuration(100)
            self._fade_in.setStartValue(0.0)
            self._fade_in.setEndValue(1.0)
            self._fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_in.start()

        self._fade_out.finished.connect(do_switch)
        self._fade_out.start()

        # Close sidebar on mobile/tablet view if needed
        if self.width() < 800 and self.sidebar.is_expanded:
            self.sidebar.toggle()

    def _apply_styles(self):
        """Apply global styles to the application."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: FONT, sans-serif;
            }
        """)

    def keyPressEvent(self, event):
        """Handle key events - pass to current tab."""
        current = self.stack.currentWidget()
        if hasattr(current, 'keyPressEvent'):
            current.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
