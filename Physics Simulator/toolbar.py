"""
ui/toolbar.py – now includes density, scale, and constraint creation.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
)

from config import SimulationConfig
from constraints import SpringConstraint, RopeConstraint, HingeConstraint
from event_bus import bus
from panel_widgets import CollapsiblePanel
from scene import Scene


class ToolbarPanel(QWidget):
    def __init__(self, scene: Scene, config: SimulationConfig, parent=None) -> None:
        super().__init__(parent)
        self.scene = scene
        self.config = config

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(8)

        layout.addWidget(CollapsiblePanel("Objects / Shapes", self._build_spawn_group(), expanded=True))
        layout.addWidget(
            CollapsiblePanel("Construction / Simulation", self._build_scene_controls_group(), expanded=True))
        layout.addWidget(CollapsiblePanel("World", self._build_environment_group(), expanded=True))
        layout.addWidget(CollapsiblePanel("Constraints", self._build_constraints_group(), expanded=False))
        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Object spawning (expanded with walls, pyramid, etc.)
    # ------------------------------------------------------------------

    def _build_spawn_group(self) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        # Two buttons per row rather than one long horizontal row per
        # category - a row of 6-7 buttons doesn't fit in a 230-380px wide
        # panel at all (it needed ~500-600px), which is what was forcing
        # this whole area into a permanent, ugly horizontal scroll.
        columns = 2
        shapes = ("sphere", "cube", "cylinder", "cone", "torus", "pyramid",
                  "ball", "cup", "table", "car", "ramp", "plank", "box",
                  "wall", "floor_tile")
        row = col = 0
        for kind in shapes:
            btn = QPushButton(kind.replace("_", " ").title())
            btn.clicked.connect(lambda checked=False, k=kind: self.scene.spawn(k))
            grid.addWidget(btn, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1
        for c in range(columns):
            grid.setColumnStretch(c, 1)

        force_btn = QPushButton("Force Arrow")
        force_btn.clicked.connect(lambda: self.scene.spawn_force_object())
        if col != 0:
            row += 1
        grid.addWidget(force_btn, row, 0, 1, columns)

        return box

    # ------------------------------------------------------------------
    # Scene controls
    # ------------------------------------------------------------------

    def _build_scene_controls_group(self) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.scene.clear_all)

        reset_btn = QPushButton("Reset Scene")
        reset_btn.clicked.connect(self.scene.reset_default_scene)

        place_btn = QPushButton("Place Mode")
        place_btn.setCheckable(True)
        place_btn.toggled.connect(lambda checked: bus.publish("input.set_place_mode", checked))

        attach_btn = QPushButton("Attach Force")
        attach_btn.setToolTip("Attach the selected force object to the selected body")
        attach_btn.clicked.connect(self.scene.attach_selected_force_to_body)

        simulate_btn = QPushButton("Simulate")
        simulate_btn.clicked.connect(self.scene.begin_simulation)

        stop_btn = QPushButton("Stop")
        stop_btn.setToolTip("Stop simulation and return to construction mode")
        stop_btn.clicked.connect(self.scene.stop_simulation)

        columns = 2
        for idx, btn in enumerate((clear_btn, reset_btn, place_btn, attach_btn, simulate_btn, stop_btn)):
            r, c = divmod(idx, columns)
            grid.addWidget(btn, r, c)
        for c in range(columns):
            grid.setColumnStretch(c, 1)

        return box

    # ------------------------------------------------------------------
    # Environment sliders
    # ------------------------------------------------------------------

    def _build_environment_group(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._make_slider_row(
            "Time of Day", 0, 240, int(self.config.time_of_day_hours * 10),
            self._on_time_of_day_changed, suffix_fn=lambda v: f"{v / 10:.1f}h"))

        layout.addWidget(self._make_slider_row(
            "Surface Friction", 0, 100, int(self.config.ground_friction * 100),
            self._on_friction_changed, suffix_fn=lambda v: f"{v / 100:.2f}"))

        layout.addWidget(self._make_slider_row(
            "Surface Bounciness", 0, 100, int(self.config.ground_restitution * 100),
            self._on_restitution_changed, suffix_fn=lambda v: f"{v / 100:.2f}"))

        layout.addWidget(self._make_slider_row(
            "Gravity", 0, 200, int(self.config.gravity * 10),
            lambda v: setattr(self.config, "gravity", v / 10.0),
            suffix_fn=lambda v: f"{v / 10:.1f} m/s²"))

        layout.addWidget(self._make_slider_row(
            "Air Damping", 0, 100, int((1 - self.config.air_damping) * 100),
            lambda v: setattr(self.config, "air_damping", 1 - v / 100.0),
            suffix_fn=lambda v: f"{1 - v / 100:.3f}"))

        layout.addWidget(self._make_slider_row(
            "Angular Damping", 0, 100, int((1 - self.config.angular_damping) * 100),
            lambda v: setattr(self.config, "angular_damping", 1 - v / 100.0),
            suffix_fn=lambda v: f"{1 - v / 100:.3f}"))

        return box

    @staticmethod
    def _make_slider_row(label_text, minimum, maximum, value, on_change, suffix_fn) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)

        label_row = QHBoxLayout()
        name_label = QLabel(label_text)
        value_label = QLabel(suffix_fn(value))
        label_row.addWidget(name_label)
        label_row.addStretch(1)
        label_row.addWidget(value_label)
        layout.addLayout(label_row)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)

        def handle_change(v):
            value_label.setText(suffix_fn(v))
            on_change(v)

        slider.valueChanged.connect(handle_change)
        layout.addWidget(slider)
        return container

    # ------------------------------------------------------------------
    # Constraints group
    # ------------------------------------------------------------------

    def _build_constraints_group(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        self.secondary_label = QLabel("Body B: none (Shift+click a body to set)")
        self.secondary_label.setStyleSheet("color: #aaa;")
        layout.addWidget(self.secondary_label)
        bus.subscribe("scene.secondary_selection_changed", self._on_secondary_selection_changed)

        # Create buttons for each constraint type
        spring_btn = QPushButton("Add Spring")
        spring_btn.setToolTip("Connect the selected body and Body B with a spring")
        spring_btn.clicked.connect(self._add_spring)
        layout.addWidget(spring_btn)

        rope_btn = QPushButton("Add Rope")
        rope_btn.setToolTip("Connect the selected body and Body B with a rope")
        rope_btn.clicked.connect(self._add_rope)
        layout.addWidget(rope_btn)

        hinge_btn = QPushButton("Add Hinge")
        hinge_btn.setToolTip("Connect the selected body and Body B with a hinge")
        hinge_btn.clicked.connect(self._add_hinge)
        layout.addWidget(hinge_btn)

        return box

    def _on_secondary_selection_changed(self, body) -> None:
        if body is None:
            self.secondary_label.setText("Body B: none (Shift+click a body to set)")
        else:
            self.secondary_label.setText(f"Body B: {body.object_kind} #{body.id}")

    def _add_spring(self):
        body_a = self.scene.selected_body
        body_b = self.scene.secondary_selected_body
        if body_a is None or body_b is None:
            # Fallback: use last selected and world
            return
        # Create spring between anchors at centers
        spring = SpringConstraint(body_a, body_b,
                                  anchor_a=np.zeros(3), anchor_b=np.zeros(3),
                                  rest_length=1.0, k=50.0)
        self.scene.register_constraint(spring)
        self.scene.set_secondary_selection(None)

    def _add_rope(self):
        body_a = self.scene.selected_body
        body_b = self.scene.secondary_selected_body
        if body_a is None or body_b is None:
            return
        rope = RopeConstraint(body_a, body_b,
                              anchor_a=np.zeros(3), anchor_b=np.zeros(3),
                              max_length=1.5)
        self.scene.register_constraint(rope)
        self.scene.set_secondary_selection(None)

    def _add_hinge(self):
        body_a = self.scene.selected_body
        body_b = self.scene.secondary_selected_body
        if body_a is None or body_b is None:
            return
        hinge = HingeConstraint(body_a, body_b,
                                anchor_a=np.zeros(3), anchor_b=np.zeros(3),
                                axis=np.array([0.0, 1.0, 0.0]))
        self.scene.register_constraint(hinge)
        self.scene.set_secondary_selection(None)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _on_time_of_day_changed(raw_value: int) -> None:
        bus.publish("input.set_time_of_day", raw_value / 10.0)

    def _on_friction_changed(self, raw_value: int) -> None:
        self.config.ground_friction = raw_value / 100.0

    def _on_restitution_changed(self, raw_value: int) -> None:
        self.config.ground_restitution = raw_value / 100.0