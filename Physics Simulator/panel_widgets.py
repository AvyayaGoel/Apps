"""
ui/panel_widgets.py

Small reusable widgets for integrated, collapsible side panels.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget


class CollapsiblePanel(QWidget):
    """A lightweight collapsible panel for the main-window sidebars."""

    def __init__(self, title: str, content: QWidget, *, expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.content = content

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.clicked.connect(self.set_expanded)
        layout.addWidget(self.toggle_button)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("collapsibleContent")
        self.content_frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(self.content_frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.addWidget(content)
        layout.addWidget(self.content_frame)

        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.content_frame.setVisible(expanded)
