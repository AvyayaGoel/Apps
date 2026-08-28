"""
ui/property_panel.py – now includes density, scale, and constraint properties.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from body import RigidBody
from event_bus import bus
from force_object import ForceObject, ForceType
from math_utils import quat_from_axis_angle, quat_multiply, quat_rotate_vector, quat_conjugate
from scene import Scene
from constraints import SpringConstraint, RopeConstraint, HingeConstraint, Constraint

logger = logging.getLogger(__name__)


def _fmt_vec(v) -> str:
    return f"({v[0]:+.2f}, {v[1]:+.2f}, {v[2]:+.2f})"


class PropertyPanel(QWidget):
    def __init__(self, scene: Scene, parent=None) -> None:
        super().__init__(parent)
        self.scene = scene
        self._current: Optional[RigidBody] = None
        self._current_force: Optional[ForceObject] = None
        self._current_constraint: Optional[Constraint] = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.empty_label = QLabel("No object selected.\nClick an object in the scene to inspect it.")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        # ---- Rigid body panel ----
        self.info_box = QGroupBox("Selected Object")
        form = QFormLayout(self.info_box)

        self.kind_label = QLabel("-")
        self.position_label = QLabel("-")
        self.velocity_label = QLabel("-")

        self.mass_spin = QDoubleSpinBox()
        self.mass_spin.setRange(0.05, 500.0)
        self.mass_spin.setSingleStep(0.1)
        self.mass_spin.valueChanged.connect(self._on_mass_changed)

        self.density_spin = QDoubleSpinBox()
        self.density_spin.setRange(0.01, 50.0)
        self.density_spin.setSingleStep(0.1)
        self.density_spin.valueChanged.connect(self._on_density_changed)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 10.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.valueChanged.connect(self._on_scale_changed)

        self.static_cb = QCheckBox("Static")
        self.static_cb.toggled.connect(self._on_static_toggled)

        self.friction_spin = QDoubleSpinBox()
        self.friction_spin.setRange(0.0, 1.0)
        self.friction_spin.setSingleStep(0.05)
        self.friction_spin.valueChanged.connect(self._on_friction_changed)

        self.restitution_spin = QDoubleSpinBox()
        self.restitution_spin.setRange(0.0, 1.0)
        self.restitution_spin.setSingleStep(0.05)
        self.restitution_spin.valueChanged.connect(self._on_restitution_changed)

        self.color_button = QPushButton("Change Color")
        self.color_button.clicked.connect(self._on_change_color)

        # Velocity editing
        self.vel_x = QDoubleSpinBox()
        self.vel_y = QDoubleSpinBox()
        self.vel_z = QDoubleSpinBox()
        for spin in (self.vel_x, self.vel_y, self.vel_z):
            spin.setRange(-100, 100)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            spin.valueChanged.connect(self._on_velocity_changed)

        # Rotation sliders
        self.yaw_spin = QDoubleSpinBox()
        self.pitch_spin = QDoubleSpinBox()
        self.roll_spin = QDoubleSpinBox()
        for spin in (self.yaw_spin, self.pitch_spin, self.roll_spin):
            spin.setRange(-180, 180)
            spin.setSingleStep(1)
            spin.setSuffix("°")
            spin.valueChanged.connect(self._on_rotation_changed)

        form.addRow("Kind:", self.kind_label)
        form.addRow("Position:", self.position_label)
        form.addRow("Velocity:", self.velocity_label)
        form.addRow("Mass:", self.mass_spin)
        form.addRow("Density:", self.density_spin)
        form.addRow("Scale:", self.scale_spin)
        form.addRow("", self.static_cb)
        form.addRow("Friction:", self.friction_spin)
        form.addRow("Restitution:", self.restitution_spin)
        form.addRow("Color:", self.color_button)
        form.addRow("Vel X:", self.vel_x)
        form.addRow("Vel Y:", self.vel_y)
        form.addRow("Vel Z:", self.vel_z)
        form.addRow("Yaw (°):", self.yaw_spin)
        form.addRow("Pitch (°):", self.pitch_spin)
        form.addRow("Roll (°):", self.roll_spin)

        layout.addWidget(self.info_box)

        # ---- Force object panel ----
        self.force_box = QGroupBox("Force Object")
        force_form = QFormLayout(self.force_box)

        self.force_pos_label = QLabel("-")
        self.force_offset_x = QDoubleSpinBox()
        self.force_offset_y = QDoubleSpinBox()
        self.force_offset_z = QDoubleSpinBox()
        for spin in (self.force_offset_x, self.force_offset_y, self.force_offset_z):
            spin.setRange(-10, 10)
            spin.setSingleStep(0.05)
            spin.setDecimals(3)
            spin.valueChanged.connect(self._on_force_offset_changed)

        self.force_mag_spin = QDoubleSpinBox()
        self.force_mag_spin.setRange(0.0, 1000.0)
        self.force_mag_spin.setSingleStep(0.5)
        self.force_mag_spin.valueChanged.connect(self._on_force_mag_changed)

        self.force_dir_x = QDoubleSpinBox()
        self.force_dir_y = QDoubleSpinBox()
        self.force_dir_z = QDoubleSpinBox()
        for spin in (self.force_dir_x, self.force_dir_y, self.force_dir_z):
            spin.setRange(-1, 1)
            spin.setSingleStep(0.05)
            spin.setDecimals(3)
            spin.valueChanged.connect(self._on_force_dir_changed)

        self.force_type_cb = QComboBox()
        self.force_type_cb.addItems([t.value for t in ForceType])
        self.force_type_cb.currentTextChanged.connect(self._on_force_type_changed)

        self.force_active_cb = QCheckBox("Active")
        self.force_active_cb.toggled.connect(self._on_force_active_toggled)

        self.force_attach_btn = QPushButton("Attach to Selected Body")
        self.force_attach_btn.clicked.connect(self._attach_force_to_selected)

        self.force_detach_btn = QPushButton("Detach Force")
        self.force_detach_btn.clicked.connect(self._detach_force)

        force_form.addRow("World Pos:", self.force_pos_label)
        force_form.addRow("Offset X:", self.force_offset_x)
        force_form.addRow("Offset Y:", self.force_offset_y)
        force_form.addRow("Offset Z:", self.force_offset_z)
        force_form.addRow("Magnitude:", self.force_mag_spin)
        force_form.addRow("Dir X:", self.force_dir_x)
        force_form.addRow("Dir Y:", self.force_dir_y)
        force_form.addRow("Dir Z:", self.force_dir_z)
        force_form.addRow("Type:", self.force_type_cb)
        force_form.addRow("", self.force_active_cb)
        force_form.addRow("", self.force_attach_btn)
        force_form.addRow("", self.force_detach_btn)

        layout.addWidget(self.force_box)

        # ---- Constraint panel ----
        self.constraint_box = QGroupBox("Constraint")
        con_form = QFormLayout(self.constraint_box)

        self.con_type_label = QLabel("-")
        self.con_body_a_label = QLabel("-")
        self.con_body_b_label = QLabel("-")
        self.con_stiffness = QDoubleSpinBox()
        self.con_stiffness.setRange(0.0, 500.0)
        self.con_stiffness.setSingleStep(1.0)
        self.con_stiffness.valueChanged.connect(self._on_constraint_stiffness)
        self.con_damping = QDoubleSpinBox()
        self.con_damping.setRange(0.0, 10.0)
        self.con_damping.setSingleStep(0.1)
        self.con_damping.valueChanged.connect(self._on_constraint_damping)
        self.con_rest_length = QDoubleSpinBox()
        self.con_rest_length.setRange(0.01, 100.0)
        self.con_rest_length.setSingleStep(0.1)
        self.con_rest_length.valueChanged.connect(self._on_constraint_rest_length)
        self.con_enabled_cb = QCheckBox("Enabled")
        self.con_enabled_cb.toggled.connect(self._on_constraint_enabled)
        self.con_delete_btn = QPushButton("Delete Constraint")
        self.con_delete_btn.clicked.connect(self._delete_constraint)

        con_form.addRow("Type:", self.con_type_label)
        con_form.addRow("Body A:", self.con_body_a_label)
        con_form.addRow("Body B:", self.con_body_b_label)
        con_form.addRow("Stiffness:", self.con_stiffness)
        con_form.addRow("Damping:", self.con_damping)
        con_form.addRow("Rest Length:", self.con_rest_length)
        con_form.addRow("", self.con_enabled_cb)
        con_form.addRow("", self.con_delete_btn)

        layout.addWidget(self.constraint_box)

        # ---- Action buttons ----
        action_row = QVBoxLayout()
        self.kick_button = QPushButton("Kick / Throw (Space)")
        self.kick_button.clicked.connect(lambda: self.scene.apply_random_impulse())
        self.delete_button = QPushButton("Delete Selected (Del)")
        self.delete_button.clicked.connect(self.scene.delete_selected)
        action_row.addWidget(self.kick_button)
        action_row.addWidget(self.delete_button)
        layout.addLayout(action_row)

        # ---- subscriptions ----
        bus.subscribe("scene.selection_changed", self._on_selection_changed)
        self._set_selected(None)

        # ---- refresh timer ----
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_live_fields)
        self._refresh_timer.start(100)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_selection_changed(self, obj) -> None:
        if isinstance(obj, RigidBody):
            self._set_selected(obj)
            self._set_force_selected(None)
            self._set_constraint_selected(None)
        elif isinstance(obj, ForceObject):
            self._set_selected(None)
            self._set_force_selected(obj)
            self._set_constraint_selected(None)
        elif isinstance(obj, (SpringConstraint, RopeConstraint, HingeConstraint)):
            self._set_selected(None)
            self._set_force_selected(None)
            self._set_constraint_selected(obj)
        else:
            self._set_selected(None)
            self._set_force_selected(None)
            self._set_constraint_selected(None)

    def _set_selected(self, body: Optional[RigidBody]) -> None:
        self._current = body
        has = body is not None
        self.info_box.setVisible(has)
        self.empty_label.setVisible(not has and self._current_force is None and self._current_constraint is None)
        self.kick_button.setEnabled(has)
        self.delete_button.setEnabled(has or self._current_force is not None or self._current_constraint is not None)
        if body is not None:
            self.kind_label.setText(f"{body.object_kind} ({body.shape})")
            self._blocked_set(self.mass_spin, body.mass)
            self._blocked_set(self.density_spin, body.density)
            self._blocked_set(self.scale_spin, body.scale)
            self._blocked_set(self.friction_spin, body.friction)
            self._blocked_set(self.restitution_spin, body.restitution)
            self.static_cb.blockSignals(True)
            self.static_cb.setChecked(body.is_static)
            self.static_cb.blockSignals(False)
            self._update_velocity_spins(body.velocity)
            self._update_rotation_spins(body.orientation)
            self._refresh_live_fields()

    def _set_force_selected(self, force: Optional[ForceObject]) -> None:
        self._current_force = force
        has_force = force is not None
        self.force_box.setVisible(has_force)
        self.empty_label.setVisible(not has_force and self._current is None and self._current_constraint is None)
        self.delete_button.setEnabled(has_force or self._current is not None or self._current_constraint is not None)
        if force is not None:
            self._blocked_set(self.force_mag_spin, force.magnitude)
            self._blocked_set(self.force_dir_x, force.direction[0])
            self._blocked_set(self.force_dir_y, force.direction[1])
            self._blocked_set(self.force_dir_z, force.direction[2])
            self.force_type_cb.setCurrentText(force.force_type.value)
            self.force_active_cb.setChecked(force.is_active)
            self._blocked_set(self.force_offset_x, force.local_offset[0])
            self._blocked_set(self.force_offset_y, force.local_offset[1])
            self._blocked_set(self.force_offset_z, force.local_offset[2])
            self._refresh_force_live_fields()

    def _set_constraint_selected(self, con: Optional[Constraint]) -> None:
        self._current_constraint = con
        has_con = con is not None
        self.constraint_box.setVisible(has_con)
        self.empty_label.setVisible(not has_con and self._current is None and self._current_force is None)
        self.delete_button.setEnabled(has_con or self._current is not None or self._current_force is not None)
        if con is not None:
            self.con_type_label.setText(type(con).__name__)
            self.con_body_a_label.setText(str(con.body_a.id) if con.body_a else "world")
            self.con_body_b_label.setText(str(con.body_b.id) if con.body_b else "world")
            self._blocked_set(self.con_stiffness, getattr(con, 'k', 0.0) if hasattr(con, 'k') else 0.0)
            self._blocked_set(self.con_damping, con.damping)
            rest = getattr(con, 'rest_length', 0.0) if hasattr(con, 'rest_length') else getattr(con, 'max_length', 0.0)
            self._blocked_set(self.con_rest_length, rest)
            self.con_enabled_cb.setChecked(con.enabled)

    def _blocked_set(self, spin, value):
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)

    def _update_velocity_spins(self, vel):
        self.vel_x.setValue(vel[0])
        self.vel_y.setValue(vel[1])
        self.vel_z.setValue(vel[2])

    def _update_rotation_spins(self, quat):
        x, y, z, w = quat
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.sign(sinp) * np.pi / 2
        else:
            pitch = np.arcsin(sinp)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)
        self.yaw_spin.setValue(np.degrees(yaw))
        self.pitch_spin.setValue(np.degrees(pitch))
        self.roll_spin.setValue(np.degrees(roll))

    def _refresh_live_fields(self):
        if self._current is None:
            return
        self.position_label.setText(_fmt_vec(self._current.position))
        self.velocity_label.setText(_fmt_vec(self._current.velocity))

    def _refresh_force_live_fields(self):
        if self._current_force is None:
            return
        pos = self._current_force.get_world_position()
        self.force_pos_label.setText(_fmt_vec(pos))

    # ------------------------------------------------------------------
    # Editing callbacks
    # ------------------------------------------------------------------

    def _on_mass_changed(self, value):
        if self._current is None:
            return
        # Changing mass directly: adjust density to keep volume?
        # We'll allow direct mass change, but update density accordingly.
        vol = self._current._volume() * (self._current.scale ** 3)
        if vol > 1e-9:
            self._current.density = value / vol
        self._current.mass = value
        self._current._update_inv_mass()
        self._current.wake()

    def _on_density_changed(self, value):
        if self._current is not None:
            self._current.set_density(value)

    def _on_scale_changed(self, value):
        if self._current is not None:
            self._current.set_scale(value)

    def _on_static_toggled(self, checked):
        if self._current is None:
            return
        self._current.set_static(checked)
        self._current.wake()

    def _on_friction_changed(self, value):
        if self._current is not None:
            self._current.friction = value

    def _on_restitution_changed(self, value):
        if self._current is not None:
            self._current.restitution = value

    def _on_change_color(self):
        if self._current is None:
            return
        r, g, b = self._current.color
        initial = QColor.fromRgbF(r, g, b)
        color = QColorDialog.getColor(initial, self, "Choose Object Color")
        if color.isValid():
            self._current.color = (color.redF(), color.greenF(), color.blueF())

    def _on_velocity_changed(self):
        if self._current is None:
            return
        vel = np.array([self.vel_x.value(), self.vel_y.value(), self.vel_z.value()])
        self._current.velocity = vel
        self._current.wake()

    def _on_rotation_changed(self):
        if self._current is None:
            return
        yaw = np.radians(self.yaw_spin.value())
        pitch = np.radians(self.pitch_spin.value())
        roll = np.radians(self.roll_spin.value())
        qx = quat_from_axis_angle(np.array([1, 0, 0]), roll)
        qy = quat_from_axis_angle(np.array([0, 1, 0]), pitch)
        qz = quat_from_axis_angle(np.array([0, 0, 1]), yaw)
        self._current.orientation = quat_multiply(qz, quat_multiply(qy, qx))
        self._current.wake()

    # ------------------------------------------------------------------
    # Force object editing
    # ------------------------------------------------------------------

    def _on_force_mag_changed(self, value):
        if self._current_force is not None:
            self._current_force.magnitude = value

    def _on_force_dir_changed(self):
        if self._current_force is not None:
            d = np.array([self.force_dir_x.value(), self.force_dir_y.value(), self.force_dir_z.value()])
            norm = np.linalg.norm(d)
            if norm > 1e-6:
                self._current_force.direction = d / norm

    def _on_force_offset_changed(self):
        if self._current_force is not None:
            self._current_force.local_offset = np.array([
                self.force_offset_x.value(),
                self.force_offset_y.value(),
                self.force_offset_z.value(),
            ])
            if self._current_force.attached_to is None:
                self._current_force.position = self._current_force.local_offset.copy()

    def _on_force_type_changed(self, text):
        if self._current_force is not None:
            self._current_force.force_type = ForceType(text)

    def _on_force_active_toggled(self, checked):
        if self._current_force is not None:
            self._current_force.is_active = checked

    def _attach_force_to_selected(self):
        if self._current_force is None or self._current is None:
            return
        body = self._current
        force = self._current_force
        force.attached_to = body
        delta = force.position - body.position
        force.local_offset = quat_rotate_vector(quat_conjugate(body.orientation), delta)

    def _detach_force(self):
        if self._current_force is not None:
            self._current_force.attached_to = None
            self._current_force.position = self._current_force.get_world_position()

    # ------------------------------------------------------------------
    # Constraint editing
    # ------------------------------------------------------------------

    def _on_constraint_stiffness(self, val):
        if self._current_constraint is not None and hasattr(self._current_constraint, 'k'):
            self._current_constraint.k = val

    def _on_constraint_damping(self, val):
        if self._current_constraint is not None:
            self._current_constraint.damping = val

    def _on_constraint_rest_length(self, val):
        if self._current_constraint is not None:
            if hasattr(self._current_constraint, 'rest_length'):
                self._current_constraint.rest_length = val
            elif hasattr(self._current_constraint, 'max_length'):
                self._current_constraint.max_length = val

    def _on_constraint_enabled(self, checked):
        if self._current_constraint is not None:
            self._current_constraint.enabled = checked

    def _delete_constraint(self):
        if self._current_constraint is not None:
            self.scene.world.remove_constraint(self._current_constraint)
            self._set_constraint_selected(None)
            bus.publish("scene.selection_changed", None)
