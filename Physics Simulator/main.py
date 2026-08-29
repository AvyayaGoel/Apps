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

from PyQt6.QtWidgets import QApplication

from config import config
from main_window import MainWindow
from scene import Scene

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("3D Physics Sandbox")

    scene = Scene(config)
    window = MainWindow(scene, config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
