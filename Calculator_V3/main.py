"""
Calculator V3 - A modern PyQt6-based calculator with comprehensive unit conversions.

Features:
- Clean separation between UI and calculation logic
- Advanced expression evaluation with sympy
- Comprehensive unit conversion (12 categories)
- Interactive history panel
- Modern dark theme UI

Usage:
    python main.py

Requirements:
    PyQt6
    sympy
    numexpr
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication


def get_resource_path(filename: str) -> str:
    """Get path to resource file. Works in dev mode and PyInstaller."""
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    # For --onedir, check if we're in _internal folder
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(getattr(sys, '_MEIPASS'), filename)
    # Development mode - file is next to main.py
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# Import after path setup - all modules in same directory
from main_window import MainWindow
# Increase limit for large integer string conversions
sys.set_int_max_str_digits(0)

def setup_fonts():
    """Setup application fonts."""
    # Qt will automatically fall back to available fonts
    app_font = QFont("Segoe UI", 10)
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    QApplication.setFont(app_font)


def main():
    """Application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Calculator V3")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("CalculatorApp")

    # Set application icon
    icon_path = get_resource_path("Calculator-Icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    setup_fonts()

    # Create and show main window
    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()