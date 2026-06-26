"""Entry point for Carbon Simulator."""
import logging
import os
import sys
from datetime import datetime

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


def setup_logging():
    """Configure logging to file and console."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"carbon_sim_{timestamp}.log")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("=== Carbon Simulator V2 Started ===")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    return logger


def main():
    logger = setup_logging()

    try:
        logger.info("Creating QApplication...")
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        logger.info("QApplication created")

        # Dark palette
        logger.info("Setting up dark palette...")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(6, 12, 22))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(230, 240, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(10, 16, 28))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(18, 24, 40))
        palette.setColor(QPalette.ColorRole.Text, QColor(230, 240, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(30, 40, 60))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(230, 240, 255))
        app.setPalette(palette)
        logger.info("Dark palette applied")

        logger.info("Creating MainWindow...")
        window = MainWindow()
        logger.info("MainWindow created, calling show()")
        window.show()

        logger.info("Entering event loop...")
        exit_code = app.exec()
        logger.info(f"Event loop exited with code {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.exception(f"CRITICAL ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
