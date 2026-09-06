"""
ui/toolbar.py

The left side panel: environment settings and constraint creation. Object
spawning and scene/simulation controls now live in the top toolbar
(top_toolbar.py) - this panel only holds things that are about *tuning* the
world (gravity, friction, time of day, ...) or connecting existing objects
together (springs/ropes/hinges/forces), not adding or switching modes.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
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

        layout.addWidget(CollapsiblePanel("World", self._build_environment_group(), expanded=True))
        layout.addWidget(CollapsiblePanel("Connect Objects", self._build_constraints_group(), expanded=True))
        layout.addStretch(1)

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

        force_btn = QPushButton("New Force")
        force_btn.setToolTip("Create a force arrow, then select it and a body and click Attach Force")
        force_btn.clicked.connect(lambda: self.scene.spawn_force_object())
        layout.addWidget(force_btn)

        attach_btn = QPushButton("Attach Force")
        attach_btn.setToolTip("Attach the selected force object to the selected body")
        attach_btn.clicked.connect(self.scene.attach_selected_force_to_body)
        layout.addWidget(attach_btn)

        self.secondary_label = QLabel("Body B: none")
        self.secondary_label.setToolTip("Shift+click a body in the viewport to set it as Body B")
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
            self.secondary_label.setText("Body B: none")
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