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
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
)

import environment_presets
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

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(environment_presets.preset_names())
        self.preset_combo.setCurrentText(environment_presets.active_preset_name())
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_row)

        self.lock_label = QLabel()
        self.lock_label.setWordWrap(True)
        self.lock_label.setStyleSheet("color: #9aa1ab; font-style: italic;")
        layout.addWidget(self.lock_label)

        self.edit_custom_btn = QPushButton("Edit as Custom")
        self.edit_custom_btn.setToolTip(
            "Built-in presets can't be edited in place - this copies the current "
            "preset's values into the Custom slot and switches to it")
        self.edit_custom_btn.clicked.connect(self._start_custom)
        layout.addWidget(self.edit_custom_btn)

        # (config field, label, slider range, slider->config, config->slider, display)
        self._env_sliders = []
        self._add_env_slider(layout, "time_of_day_hours", "Time of Day", 0, 240,
                             lambda v: v / 10.0, lambda cv: int(cv * 10), lambda cv: f"{cv:.1f}h")
        self._add_env_slider(layout, "ground_friction", "Surface Friction", 0, 100,
                             lambda v: v / 100.0, lambda cv: int(cv * 100), lambda cv: f"{cv:.2f}")
        self._add_env_slider(layout, "ground_restitution", "Surface Bounciness", 0, 100,
                             lambda v: v / 100.0, lambda cv: int(cv * 100), lambda cv: f"{cv:.2f}")
        self._add_env_slider(layout, "gravity", "Gravity", 0, 200,
                             lambda v: v / 10.0, lambda cv: int(cv * 10), lambda cv: f"{cv:.1f} m/s\u00b2")
        self._add_env_slider(layout, "air_damping", "Air Damping", 0, 100,
                             lambda v: 1 - v / 100.0, lambda cv: int((1 - cv) * 100), lambda cv: f"{cv:.3f}")
        self._add_env_slider(layout, "angular_damping", "Angular Damping", 0, 100,
                             lambda v: 1 - v / 100.0, lambda cv: int((1 - cv) * 100), lambda cv: f"{cv:.3f}")

        self._refresh_lock_state()
        return box

    def _add_env_slider(self, layout, field_name, label_text, minimum, maximum,
                        slider_to_config, config_to_slider, display) -> None:
        current_value = getattr(self.config, field_name)
        container, slider, value_label = self._make_slider_row(
            label_text, minimum, maximum, config_to_slider(current_value),
            lambda v: self._on_env_slider_changed(field_name, slider_to_config(v)),
            suffix_fn=lambda v: display(slider_to_config(v)))
        layout.addWidget(container)
        self._env_sliders.append((field_name, slider, value_label, config_to_slider, display))

    def _on_env_slider_changed(self, field_name: str, value: float) -> None:
        # Sliders are disabled while a locked preset is active, so in
        # practice this only fires while Custom is active - but guard it
        # anyway rather than relying on the UI state alone.
        if environment_presets.is_locked(environment_presets.active_preset_name()):
            return
        environment_presets.update_custom(self.config, field_name, value)
        if field_name == "time_of_day_hours":
            # scene.time_of_day (not config.time_of_day_hours directly) is
            # what the sky/sun renderer actually reads - route through the
            # same event the slider always used, or the sky would silently
            # stop following this slider.
            bus.publish("input.set_time_of_day", value)

    def _apply_time_of_day_to_scene(self) -> None:
        bus.publish("input.set_time_of_day", self.config.time_of_day_hours)

    def _on_preset_changed(self, name: str) -> None:
        environment_presets.apply_preset(self.config, name)
        self._refresh_slider_values()
        self._refresh_lock_state()
        self._apply_time_of_day_to_scene()

    def _start_custom(self) -> None:
        environment_presets.start_custom_from_current(self.config)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentText("Custom")
        self.preset_combo.blockSignals(False)
        self._refresh_lock_state()
        self._apply_time_of_day_to_scene()

    def _refresh_slider_values(self) -> None:
        for field_name, slider, value_label, config_to_slider, display in self._env_sliders:
            current_value = getattr(self.config, field_name)
            slider.blockSignals(True)
            slider.setValue(config_to_slider(current_value))
            slider.blockSignals(False)
            value_label.setText(display(current_value))

    def _refresh_lock_state(self) -> None:
        locked = environment_presets.is_locked(environment_presets.active_preset_name())
        self.lock_label.setText(
            "This is a built-in preset - values are fixed. Use 'Edit as Custom' to change them."
            if locked else "Custom environment - sliders below are editable.")
        self.edit_custom_btn.setVisible(locked)
        for _, slider, _, _, _ in self._env_sliders:
            slider.setEnabled(not locked)

    @staticmethod
    def _make_slider_row(label_text, minimum, maximum, value, on_change, suffix_fn):
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
        return container, slider, value_label

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