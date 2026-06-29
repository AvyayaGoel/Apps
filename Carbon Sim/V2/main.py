"""Entry point for Carbon Simulator."""
import logging
import sys

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


def setup_logging():
    """Configure logging to file and console."""
    logging.basicConfig(
        filename="carbon_simulator.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    return logger


def main():
    logger = setup_logging()

    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # Dark palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(6, 12, 22))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(230, 240, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(10, 16, 28))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(18, 24, 40))
        palette.setColor(QPalette.ColorRole.Text, QColor(230, 240, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(30, 40, 60))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(230, 240, 255))
        app.setPalette(palette)

        window = MainWindow()
        window.show()
        exit_code = app.exec()
        sys.exit(exit_code)

    except Exception as e:
        logger.exception(f"CRITICAL ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
