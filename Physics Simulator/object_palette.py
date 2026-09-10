"""
ui/object_palette.py

The "Add Object" picker: a popup panel showing every catalog object as a
small preview button, organized into categories read directly from
object_catalog.py (which loads data/objects.json) - so adding a new object,
including a future user-created one, automatically appears here without
touching this file.

Previews are simple QPainter-drawn 2D icons (shape family + the object's
actual spawn color), not rendered 3D thumbnails. A true 3D preview would
need a second, independent OpenGL context purely for thumbnail rendering -
exactly the kind of "OpenGL context lifetime / rendering outside the active
context" risk this project has already been bitten by more than once, so a
lightweight but still genuinely representative 2D icon (real shape family +
real color, not a placeholder) was the safer tradeoff.
"""

from __future__ import annotations

from typing import Dict, Tuple

from PyQt6.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QGridLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget
)

import object_catalog

RGB = Tuple[float, float, float]

_ICON_CIRCLE = "circle"
_ICON_RECT = "rect"
_ICON_TALL = "tall"
_ICON_TRIANGLE = "triangle"

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
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Add Object")
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

        for category, items in object_catalog.categories():
            label = QLabel(category)
            label.setStyleSheet("font-weight: bold; color: #9db4d1;")
            content_layout.addWidget(label)

            grid = QGridLayout()
            grid.setSpacing(4)
            columns = 3
            for idx, obj in enumerate(items):
                btn = QToolButton()
                btn.setIcon(_make_icon(obj.icon_family, obj.icon_color))
                btn.setIconSize(QSize(32, 32))
                btn.setText(obj.display_name)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setMinimumWidth(88)
                btn.clicked.connect(lambda checked=False, k=obj.kind: self._choose(k))
                row, col = divmod(idx, columns)
                grid.addWidget(btn, row, col)
            content_layout.addLayout(grid)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _choose(self, kind: str) -> None:
        self.object_chosen.emit(kind)
        self.close()