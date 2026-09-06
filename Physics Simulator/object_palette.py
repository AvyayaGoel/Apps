"""
ui/object_palette.py

The "Add Object" picker: a popup panel showing every catalog object as a
small preview button, organized into categories. Choosing one arms PLACE
tool mode (scene.set_place_object) rather than immediately spawning it at a
random spot - picking *what* to add and clicking *where* to put it are two
separate steps now.

Previews are simple QPainter-drawn 2D icons (shape family + the object's
actual spawn color), not rendered 3D thumbnails. A true 3D preview would
need a second, independent OpenGL context purely for thumbnail rendering -
exactly the kind of "OpenGL context lifetime / rendering outside the active
context" risk this project has already been bitten by twice (the gizmo
crash and the render-matrix bug), so a lightweight but still genuinely
representative 2D icon (real shape family + real color, not a placeholder)
was the safer tradeoff.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from PyQt6.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QGridLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget
)

RGB = Tuple[float, float, float]

_ICON_CIRCLE = "circle"
_ICON_RECT = "rect"
_ICON_TALL = "tall"
_ICON_TRIANGLE = "triangle"

# (category, [(kind, display_name, icon_family, representative_color), ...])
# Colors mirror each factory function's actual default spawn color where one
# exists; for shapes that randomize color (sphere/cube/cylinder/cone) a
# representative swatch is used instead purely for the icon.
CATALOG: List[Tuple[str, List[Tuple[str, str, str, RGB]]]] = [
    ("Primitives", [
        ("sphere", "Sphere", _ICON_CIRCLE, (0.25, 0.45, 0.85)),
        ("cube", "Cube", _ICON_RECT, (0.35, 0.75, 0.35)),
        ("cylinder", "Cylinder", _ICON_TALL, (0.75, 0.35, 0.80)),
        ("cone", "Cone", _ICON_TRIANGLE, (0.95, 0.55, 0.15)),
        ("torus", "Torus", _ICON_CIRCLE, (0.9, 0.6, 0.1)),
        ("pyramid", "Pyramid", _ICON_TRIANGLE, (0.7, 0.5, 0.2)),
    ]),
    ("Furniture", [
        ("table", "Table", _ICON_RECT, (0.55, 0.35, 0.18)),
        ("chair", "Chair", _ICON_RECT, (0.5, 0.32, 0.16)),
        ("bench", "Bench", _ICON_RECT, (0.5, 0.32, 0.16)),
        ("stool", "Stool", _ICON_RECT, (0.55, 0.38, 0.2)),
        ("cup", "Cup", _ICON_TALL, (0.9, 0.9, 0.95)),
        ("well", "Well", _ICON_TALL, (0.55, 0.53, 0.5)),
    ]),
    ("Structures", [
        ("wall", "Wall", _ICON_RECT, (0.7, 0.7, 0.7)),
        ("floor_tile", "Floor Tile", _ICON_RECT, (0.5, 0.4, 0.3)),
        ("ramp", "Ramp", _ICON_TRIANGLE, (0.6, 0.55, 0.5)),
        ("stairs", "Stairs", _ICON_RECT, (0.65, 0.63, 0.6)),
    ]),
    ("Vehicles & Fun", [
        ("car", "Car", _ICON_RECT, (0.75, 0.1, 0.1)),
        ("rocket", "Rocket", _ICON_TRIANGLE, (0.85, 0.85, 0.9)),
        ("dumbbell", "Dumbbell", _ICON_TALL, (0.15, 0.15, 0.18)),
        ("lamp_post", "Lamp Post", _ICON_TALL, (0.2, 0.2, 0.22)),
        ("mushroom", "Mushroom", _ICON_TRIANGLE, (0.75, 0.15, 0.15)),
    ]),
    ("Props", [
        ("ball", "Ball", _ICON_CIRCLE, (0.9, 0.15, 0.15)),
        ("box", "Box", _ICON_RECT, (0.65, 0.45, 0.25)),
        ("plank", "Plank", _ICON_RECT, (0.65, 0.5, 0.32)),
        ("barrel", "Barrel", _ICON_TALL, (0.55, 0.4, 0.15)),
        ("traffic_cone", "Traffic Cone", _ICON_TRIANGLE, (0.95, 0.45, 0.1)),
        ("pipe", "Pipe", _ICON_TALL, (0.55, 0.57, 0.6)),
        ("boulder", "Boulder", _ICON_CIRCLE, (0.5, 0.48, 0.45)),
        ("book", "Book", _ICON_RECT, (0.6, 0.15, 0.15)),
        ("puck", "Puck", _ICON_TALL, (0.85, 0.15, 0.15)),
    ]),
]

_icon_cache: Dict[Tuple[str, RGB], QIcon] = {}


def _make_icon(family: str, color: RGB) -> QIcon:
    key = (family, color)
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached
    size = 40
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor.fromRgbF(*color))
    painter.setPen(QColor(25, 25, 25))
    margin = 5
    if family == _ICON_CIRCLE:
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    elif family == _ICON_RECT:
        painter.drawRoundedRect(margin, margin + 6, size - 2 * margin, size - 2 * margin - 6, 4, 4)
    elif family == _ICON_TALL:
        painter.drawRoundedRect(size // 2 - 9, margin, 18, size - 2 * margin, 5, 5)
    elif family == _ICON_TRIANGLE:
        poly = QPolygonF([
            QPointF(size / 2, margin),
            QPointF(size - margin, size - margin),
            QPointF(margin, size - margin),
        ])
        painter.drawPolygon(poly)
    painter.end()
    icon = QIcon(pixmap)
    _icon_cache[key] = icon
    return icon


class ObjectPalette(QWidget):
    """Popup grid of catalog preview buttons, grouped by category. Emits
    object_chosen(kind) when the user picks one, then closes itself."""

    object_chosen = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setMinimumWidth(320)
        self.setMaximumHeight(480)
        self.setStyleSheet("background: #20242a;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(10)

        for category, items in CATALOG:
            label = QLabel(category)
            label.setStyleSheet("font-weight: bold; color: #9db4d1;")
            content_layout.addWidget(label)

            grid = QGridLayout()
            grid.setSpacing(4)
            columns = 3
            for idx, (kind, name, family, color) in enumerate(items):
                btn = QToolButton()
                btn.setIcon(_make_icon(family, color))
                btn.setIconSize(QSize(32, 32))
                btn.setText(name)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setMinimumWidth(88)
                btn.clicked.connect(lambda checked=False, k=kind: self._choose(k))
                row, col = divmod(idx, columns)
                grid.addWidget(btn, row, col)
            content_layout.addLayout(grid)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _choose(self, kind: str) -> None:
        self.object_chosen.emit(kind)
        self.close()
