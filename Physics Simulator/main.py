#!/usr/bin/env python3
"""
main.py

Entry point: `python main.py`.

Wires together the shared config, the Scene (physics + selection state),
and the Qt MainWindow, then starts the Qt event loop. Intentionally tiny -
almost everything interesting happens inside scene/, physics/,
rendering/, and ui/.
"""

import logging
import sys
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from config import config
from main_window import MainWindow
from scene import Scene

LOG_PATH = Path(__file__).resolve().parent / "physics_simulator.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # visible when run from a terminal
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),  # always visible - check this file
    ],
)

_logger = logging.getLogger("uncaught")


def _log_uncaught_exception(exc_type, exc_value, exc_tb) -> None:
    """Guarantee any exception that would otherwise crash the app silently
    (no console attached, e.g. double-clicking on Windows) is written to
    physics_simulator.log before anything else happens. This does not stop
    the crash or change its behavior - it only makes sure the traceback
    that explains it is never lost."""
    _logger.critical(
        "UNCAUGHT EXCEPTION - the app is likely about to crash:\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _log_uncaught_exception


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("3D Physics Sandbox")

    scene = Scene(config)
    window = MainWindow(scene, config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())