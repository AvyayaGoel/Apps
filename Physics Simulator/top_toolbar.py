"""
ui/top_toolbar.py

The app-style top toolbar: a horizontal bar above the viewport, organized
into distinct sections instead of one long undifferentiated row of buttons:

    [ Tool Modes ] | [ Add Object ] | [ Scene ] | [ Simulation ]

Tool Modes selects what a viewport click currently does (see tool_mode.py).
Add Object opens a preview picker (object_palette.py) and arms Place mode
with whatever the user chose - picking *what* to add and clicking *where*
to put it are two separate steps, matching how a real editor toolbar works.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QPushButton, QToolButton, QWidget
)

from event_bus import bus
from object_palette import ObjectPalette
from scene import Scene
from tool_mode import ToolMode


def _vsep() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class TopToolbar(QWidget):
    def __init__(self, scene: Scene, parent=None) -> None:
        super().__init__(parent)
        self.scene = scene
        self._palette: ObjectPalette | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        layout.addLayout(self._build_tool_modes())
        layout.addWidget(_vsep())
        layout.addWidget(self._build_add_object_button())
        layout.addWidget(_vsep())
        layout.addLayout(self._build_scene_controls())
        layout.addWidget(_vsep())
        layout.addLayout(self._build_simulation_controls())
        layout.addStretch(1)

        bus.subscribe("scene.tool_mode_changed", self._on_tool_mode_changed)

    # ------------------------------------------------------------------
    # Tool modes
    # ------------------------------------------------------------------

    def _build_tool_modes(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(2)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: dict[ToolMode, QToolButton] = {}

        specs = [
            (ToolMode.SELECT, "Select", "1 - click to select and use the gizmo"),
            (ToolMode.MOVE, "Move", "2 - gizmo shows translate handles only"),
            (ToolMode.ROTATE, "Rotate", "3 - gizmo shows rotate handles only"),
            (ToolMode.SCALE, "Scale", "4 - click a body and drag vertically to resize it"),
            (ToolMode.DELETE, "Delete", "5 - click a body to delete it immediately"),
        ]
        for mode, label, tip in specs:
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setChecked(mode is ToolMode.SELECT)
            btn.clicked.connect(lambda checked=False, m=mode: self.scene.set_tool_mode(m))
            self._mode_group.addButton(btn)
            self._mode_buttons[mode] = btn
            row.addWidget(btn)
        return row

    def _on_tool_mode_changed(self, mode: ToolMode) -> None:
        btn = self._mode_buttons.get(mode)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)
        elif mode is ToolMode.PLACE:
            # Place doesn't have its own persistent button (it's armed via
            # the Add Object picker) - uncheck the mode row entirely so
            # nothing shows a stale, incorrect selection.
            checked = self._mode_group.checkedButton()
            if checked is not None:
                self._mode_group.setExclusive(False)
                checked.setChecked(False)
                self._mode_group.setExclusive(True)

    # ------------------------------------------------------------------
    # Add Object
    # ------------------------------------------------------------------

    def _build_add_object_button(self) -> QPushButton:
        btn = QPushButton("+ Add Object")
        btn.setToolTip("Choose an object to place, then click in the viewport")
        btn.clicked.connect(lambda: self._open_palette(btn))
        return btn

    def _open_palette(self, anchor: QPushButton) -> None:
        if self._palette is None:
            self._palette = ObjectPalette(self)
            self._palette.object_chosen.connect(self.scene.set_place_object)
        pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        self._palette.move(pos)
        self._palette.show()

    # ------------------------------------------------------------------
    # Scene / simulation controls
    # ------------------------------------------------------------------

    def _build_scene_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.scene.clear_all)
        row.addWidget(clear_btn)

        reset_btn = QPushButton("Reset Scene")
        reset_btn.clicked.connect(self.scene.reset_default_scene)
        row.addWidget(reset_btn)
        return row

    def _build_simulation_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)

        simulate_btn = QPushButton("Simulate")
        simulate_btn.clicked.connect(self.scene.begin_simulation)
        row.addWidget(simulate_btn)

        stop_btn = QPushButton("Stop")
        stop_btn.setToolTip("Stop simulation and return to construction mode")
        stop_btn.clicked.connect(self.scene.stop_simulation)
        row.addWidget(stop_btn)
        return row
