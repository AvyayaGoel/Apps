"""
ui/property_panel.py – Property panel with improved layout density and model-view synchronization.
Uses grid layouts for better information density and event-based updates for immediate synchronization.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QGridLayout,
    QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget, QScrollArea,
)

from body import RigidBody
from constraints import SpringConstraint, RopeConstraint, HingeConstraint, Constraint
from event_bus import bus
from force_object import ForceObject, ForceType
from math_utils import quat_from_axis_angle, quat_multiply
from scene import Scene

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
        self._block_updates = False  # Prevent recursive updates

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.empty_label = QLabel("No object selected.\nClick an object in the scene to inspect it.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #888; padding: 10px;")
        content_layout.addWidget(self.empty_label)

        # ---- Rigid body panel ----
        self.info_box = QGroupBox("Selected Object")
        self.info_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4a505a;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        info_layout = QVBoxLayout(self.info_box)
        info_layout.setSpacing(8)

        # Basic info labels (read-only)
        basic_grid = QGridLayout()
        basic_grid.setSpacing(6)

        self.kind_label = QLabel("-")
        self.kind_label.setStyleSheet("color: #7fb0ff;")
        basic_grid.addWidget(QLabel("Kind:"), 0, 0)
        basic_grid.addWidget(self.kind_label, 0, 1)

        self.position_label = QLabel("-")
        basic_grid.addWidget(QLabel("Position:"), 0, 2)
        basic_grid.addWidget(self.position_label, 0, 3)

        self.velocity_label = QLabel("-")
        basic_grid.addWidget(QLabel("Velocity:"), 1, 0)
        basic_grid.addWidget(self.velocity_label, 1, 1)

        info_layout.addLayout(basic_grid)

        # Physical properties grid (2 columns)
        phys_group = QLabel("Physical Properties")
        phys_group.setStyleSheet("font-weight: bold; color: #aaf;")
        info_layout.addWidget(phys_group)

        phys_grid = QGridLayout()
        phys_grid.setSpacing(6)
        phys_grid.setColumnStretch(1, 1)
        phys_grid.setColumnStretch(3, 1)

        self.mass_spin = QDoubleSpinBox()
        self.mass_spin.setRange(0.05, 500.0)
        self.mass_spin.setSingleStep(0.1)
        self.mass_spin.setDecimals(3)
        self.mass_spin.valueChanged.connect(self._on_mass_changed)
        phys_grid.addWidget(QLabel("Mass:"), 0, 0)
        phys_grid.addWidget(self.mass_spin, 0, 1)

        self.density_spin = QDoubleSpinBox()
        self.density_spin.setRange(0.01, 50.0)
        self.density_spin.setSingleStep(0.1)
        self.density_spin.setDecimals(3)
        self.density_spin.valueChanged.connect(self._on_density_changed)
        phys_grid.addWidget(QLabel("Density:"), 0, 2)
        phys_grid.addWidget(self.density_spin, 0, 3)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 10.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setDecimals(3)
        self.scale_spin.valueChanged.connect(self._on_scale_changed)
        phys_grid.addWidget(QLabel("Scale:"), 1, 0)
        phys_grid.addWidget(self.scale_spin, 1, 1)

        self.static_cb = QCheckBox("Static")
        self.static_cb.toggled.connect(self._on_static_toggled)
        phys_grid.addWidget(self.static_cb, 1, 2, 1, 2)

        self.friction_spin = QDoubleSpinBox()
        self.friction_spin.setRange(0.0, 1.0)
        self.friction_spin.setSingleStep(0.05)
        self.friction_spin.setDecimals(2)
        self.friction_spin.valueChanged.connect(self._on_friction_changed)
        phys_grid.addWidget(QLabel("Friction:"), 2, 0)
        phys_grid.addWidget(self.friction_spin, 2, 1)

        self.restitution_spin = QDoubleSpinBox()
        self.restitution_spin.setRange(0.0, 1.0)
        self.restitution_spin.setSingleStep(0.05)
        self.restitution_spin.setDecimals(2)
        self.restitution_spin.valueChanged.connect(self._on_restitution_changed)
        phys_grid.addWidget(QLabel("Restitution:"), 2, 2)
        phys_grid.addWidget(self.restitution_spin, 2, 3)

        info_layout.addLayout(phys_grid)

        # Transform section
        transform_group = QLabel("Transform")
        transform_group.setStyleSheet("font-weight: bold; color: #aaf;")
        info_layout.addWidget(transform_group)

        transform_grid = QGridLayout()
        transform_grid.setSpacing(6)

        # Position XYZ inline
        transform_grid.addWidget(QLabel("Position:"), 0, 0)
        self.pos_x = QDoubleSpinBox()
        self.pos_x.setRange(-100, 100)
        self.pos_x.setSingleStep(0.1)
        self.pos_x.setDecimals(3)
        self.pos_x.valueChanged.connect(self._on_position_changed)
        transform_grid.addWidget(self.pos_x, 0, 1)

        self.pos_y = QDoubleSpinBox()
        self.pos_y.setRange(-100, 100)
        self.pos_y.setSingleStep(0.1)
        self.pos_y.setDecimals(3)
        self.pos_y.valueChanged.connect(self._on_position_changed)
        transform_grid.addWidget(self.pos_y, 0, 2)

        self.pos_z = QDoubleSpinBox()
        self.pos_z.setRange(-100, 100)
        self.pos_z.setSingleStep(0.1)
        self.pos_z.setDecimals(3)
        self.pos_z.valueChanged.connect(self._on_position_changed)
        transform_grid.addWidget(self.pos_z, 0, 3)

        # Rotation YPR inline
        transform_grid.addWidget(QLabel("Rotation:"), 1, 0)
        self.yaw_spin = QDoubleSpinBox()
        self.yaw_spin.setRange(-180, 180)
        self.yaw_spin.setSingleStep(1)
        self.yaw_spin.setSuffix("°")
        self.yaw_spin.setDecimals(1)
        self.yaw_spin.valueChanged.connect(self._on_rotation_changed)
        transform_grid.addWidget(self.yaw_spin, 1, 1)

        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(-180, 180)
        self.pitch_spin.setSingleStep(1)
        self.pitch_spin.setSuffix("°")
        self.pitch_spin.setDecimals(1)
        self.pitch_spin.valueChanged.connect(self._on_rotation_changed)
        transform_grid.addWidget(self.pitch_spin, 1, 2)

        self.roll_spin = QDoubleSpinBox()
        self.roll_spin.setRange(-180, 180)
        self.roll_spin.setSingleStep(1)
        self.roll_spin.setSuffix("°")
        self.roll_spin.setDecimals(1)
        self.roll_spin.valueChanged.connect(self._on_rotation_changed)
        transform_grid.addWidget(self.roll_spin, 1, 3)

        # Velocity XYZ inline
        transform_grid.addWidget(QLabel("Velocity:"), 2, 0)
        self.vel_x = QDoubleSpinBox()
        self.vel_x.setRange(-100, 100)
        self.vel_x.setSingleStep(0.1)
        self.vel_x.setDecimals(2)
        self.vel_x.valueChanged.connect(self._on_velocity_changed)
        transform_grid.addWidget(self.vel_x, 2, 1)

        self.vel_y = QDoubleSpinBox()
        self.vel_y.setRange(-100, 100)
        self.vel_y.setSingleStep(0.1)
        self.vel_y.setDecimals(2)
        self.vel_y.valueChanged.connect(self._on_velocity_changed)
        transform_grid.addWidget(self.vel_y, 2, 2)

        self.vel_z = QDoubleSpinBox()
        self.vel_z.setRange(-100, 100)
        self.vel_z.setSingleStep(0.1)
        self.vel_z.setDecimals(2)
        self.vel_z.valueChanged.connect(self._on_velocity_changed)
        transform_grid.addWidget(self.vel_z, 2, 3)

        info_layout.addLayout(transform_grid)

        # Color button
        self.color_button = QPushButton("Change Color")
        self.color_button.clicked.connect(self._on_change_color)
        info_layout.addWidget(self.color_button)

        content_layout.addWidget(self.info_box)

        # ---- Force object panel ----
        self.force_box = QGroupBox("Force Object")
        self.force_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4a505a;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        force_layout = QVBoxLayout(self.force_box)
        force_layout.setSpacing(8)

        force_grid = QGridLayout()
        force_grid.setSpacing(6)

        self.force_pos_label = QLabel("-")
        force_grid.addWidget(QLabel("World Pos:"), 0, 0)
        force_grid.addWidget(self.force_pos_label, 0, 1, 1, 3)

        force_grid.addWidget(QLabel("Offset:"), 1, 0)
        self.force_offset_x = QDoubleSpinBox()
        self.force_offset_x.setRange(-10, 10)
        self.force_offset_x.setSingleStep(0.05)
        self.force_offset_x.setDecimals(3)
        self.force_offset_x.valueChanged.connect(self._on_force_offset_changed)
        force_grid.addWidget(self.force_offset_x, 1, 1)

        self.force_offset_y = QDoubleSpinBox()
        self.force_offset_y.setRange(-10, 10)
        self.force_offset_y.setSingleStep(0.05)
        self.force_offset_y.setDecimals(3)
        self.force_offset_y.valueChanged.connect(self._on_force_offset_changed)
        force_grid.addWidget(self.force_offset_y, 1, 2)

        self.force_offset_z = QDoubleSpinBox()
        self.force_offset_z.setRange(-10, 10)
        self.force_offset_z.setSingleStep(0.05)
        self.force_offset_z.setDecimals(3)
        self.force_offset_z.valueChanged.connect(self._on_force_offset_changed)
        force_grid.addWidget(self.force_offset_z, 1, 3)

        force_grid.addWidget(QLabel("Magnitude:"), 2, 0)
        self.force_mag_spin = QDoubleSpinBox()
        self.force_mag_spin.setRange(0.0, 1000.0)
        self.force_mag_spin.setSingleStep(0.5)
        self.force_mag_spin.setDecimals(2)
        self.force_mag_spin.valueChanged.connect(self._on_force_mag_changed)
        force_grid.addWidget(self.force_mag_spin, 2, 1, 1, 3)

        force_grid.addWidget(QLabel("Direction:"), 3, 0)
        self.force_dir_x = QDoubleSpinBox()
        self.force_dir_x.setRange(-1, 1)
        self.force_dir_x.setSingleStep(0.05)
        self.force_dir_x.setDecimals(3)
        self.force_dir_x.valueChanged.connect(self._on_force_dir_changed)
        force_grid.addWidget(self.force_dir_x, 3, 1)

        self.force_dir_y = QDoubleSpinBox()
        self.force_dir_y.setRange(-1, 1)
        self.force_dir_y.setSingleStep(0.05)
        self.force_dir_y.setDecimals(3)
        self.force_dir_y.valueChanged.connect(self._on_force_dir_changed)
        force_grid.addWidget(self.force_dir_y, 3, 2)

        self.force_dir_z = QDoubleSpinBox()
        self.force_dir_z.setRange(-1, 1)
        self.force_dir_z.setSingleStep(0.05)
        self.force_dir_z.setDecimals(3)
        self.force_dir_z.valueChanged.connect(self._on_force_dir_changed)
        force_grid.addWidget(self.force_dir_z, 3, 3)

        force_grid.addWidget(QLabel("Type:"), 4, 0)
        self.force_type_cb = QComboBox()
        self.force_type_cb.addItems([t.value for t in ForceType])
        self.force_type_cb.currentTextChanged.connect(self._on_force_type_changed)
        force_grid.addWidget(self.force_type_cb, 4, 1, 1, 3)

        self.force_system_label = QLabel("-")
        force_grid.addWidget(QLabel("System:"), 5, 0)
        force_grid.addWidget(self.force_system_label, 5, 1, 1, 3)

        self.force_active_cb = QCheckBox("Active")
        self.force_active_cb.toggled.connect(self._on_force_active_toggled)
        force_grid.addWidget(self.force_active_cb, 6, 0, 1, 4)

        force_layout.addLayout(force_grid)

        self.force_attach_btn = QPushButton("Attach Selected Force to Selected Body")
        self.force_attach_btn.clicked.connect(self._attach_force_to_selected)
        force_layout.addWidget(self.force_attach_btn)

        self.force_detach_btn = QPushButton("Detach Force")
        self.force_detach_btn.clicked.connect(self._detach_force)
        force_layout.addWidget(self.force_detach_btn)

        content_layout.addWidget(self.force_box)

        # ---- Constraint panel ----
        self.constraint_box = QGroupBox("Constraint")
        self.constraint_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4a505a;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        con_layout = QVBoxLayout(self.constraint_box)
        con_layout.setSpacing(8)

        con_grid = QGridLayout()
        con_grid.setSpacing(6)

        self.con_type_label = QLabel("-")
        con_grid.addWidget(QLabel("Type:"), 0, 0)
        con_grid.addWidget(self.con_type_label, 0, 1)

        self.con_body_a_label = QLabel("-")
        con_grid.addWidget(QLabel("Body A:"), 0, 2)
        con_grid.addWidget(self.con_body_a_label, 0, 3)

        self.con_body_b_label = QLabel("-")
        con_grid.addWidget(QLabel("Body B:"), 1, 0)
        con_grid.addWidget(self.con_body_b_label, 1, 1)

        self.con_stiffness = QDoubleSpinBox()
        self.con_stiffness.setRange(0.0, 500.0)
        self.con_stiffness.setSingleStep(1.0)
        self.con_stiffness.setDecimals(1)
        self.con_stiffness.valueChanged.connect(self._on_constraint_stiffness)
        con_grid.addWidget(QLabel("Stiffness:"), 1, 2)
        con_grid.addWidget(self.con_stiffness, 1, 3)

        self.con_damping = QDoubleSpinBox()
        self.con_damping.setRange(0.0, 10.0)
        self.con_damping.setSingleStep(0.1)
        self.con_damping.setDecimals(2)
        self.con_damping.valueChanged.connect(self._on_constraint_damping)
        con_grid.addWidget(QLabel("Damping:"), 2, 0)
        con_grid.addWidget(self.con_damping, 2, 1)

        self.con_rest_length = QDoubleSpinBox()
        self.con_rest_length.setRange(0.01, 100.0)
        self.con_rest_length.setSingleStep(0.1)
        self.con_rest_length.setDecimals(2)
        self.con_rest_length.valueChanged.connect(self._on_constraint_rest_length)
        con_grid.addWidget(QLabel("Rest Length:"), 2, 2)
        con_grid.addWidget(self.con_rest_length, 2, 3)

        self.con_enabled_cb = QCheckBox("Enabled")
        self.con_enabled_cb.toggled.connect(self._on_constraint_enabled)
        con_grid.addWidget(self.con_enabled_cb, 3, 0, 1, 4)

        con_layout.addLayout(con_grid)

        self.con_delete_btn = QPushButton("Delete Constraint")
        self.con_delete_btn.clicked.connect(self._delete_constraint)
        con_layout.addWidget(self.con_delete_btn)

        content_layout.addWidget(self.constraint_box)

        # ---- Action buttons ----
        action_layout = QVBoxLayout()
        action_layout.setSpacing(6)

        self.kick_button = QPushButton("Kick / Throw (Space)")
        self.kick_button.clicked.connect(lambda: self.scene.apply_random_impulse())
        action_layout.addWidget(self.kick_button)

        self.delete_button = QPushButton("Delete Selected (Del)")
        self.delete_button.clicked.connect(self.scene.delete_selected)
        action_layout.addWidget(self.delete_button)

        content_layout.addLayout(action_layout)
        content_layout.addStretch(1)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # ---- subscriptions ----
        bus.subscribe("scene.selection_changed", self._on_selection_changed)
        bus.subscribe("scene.body_transform_changed", self._on_body_transform_changed)
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
            self._set_constraint_selected(None)
        elif isinstance(obj, ForceObject):
            self._set_force_selected(obj)
            self._set_constraint_selected(None)
        elif isinstance(obj, (SpringConstraint, RopeConstraint, HingeConstraint)):
            self._set_constraint_selected(obj)
        else:
            self._set_selected(None)
            self._set_force_selected(None)
            self._set_constraint_selected(None)

    def _set_selected(self, body: Optional[RigidBody]) -> None:
        self._current = body
        has = body is not None
        self.info_box.setVisible(has)
        self._update_empty_label()
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
        self._update_empty_label()
        self.delete_button.setEnabled(has_force or self._current is not None or self._current_constraint is not None)
        if force is not None:
            self._blocked_set(self.force_mag_spin, force.magnitude)
            self._blocked_set(self.force_dir_x, force.direction[0])
            self._blocked_set(self.force_dir_y, force.direction[1])
            self._blocked_set(self.force_dir_z, force.direction[2])
            self.force_type_cb.setCurrentText(force.force_type.value)
            self.force_active_cb.setChecked(force.is_active)
            self.force_system_label.setText(
                f"Attached to body {force.attached_to.id}" if force.attached_to is not None else "Independent construction force"
            )
            self._blocked_set(self.force_offset_x, force.local_offset[0])
            self._blocked_set(self.force_offset_y, force.local_offset[1])
            self._blocked_set(self.force_offset_z, force.local_offset[2])
            self._refresh_force_live_fields()

    def _set_constraint_selected(self, con: Optional[Constraint]) -> None:
        self._current_constraint = con
        has_con = con is not None
        self.constraint_box.setVisible(has_con)
        self._update_empty_label()
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

    def _update_empty_label(self):
        self.empty_label.setVisible(
            self._current is None and self._current_force is None and self._current_constraint is None
        )

    def _blocked_set(self, spin, value):
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)

    def _update_velocity_spins(self, vel):
        """Update velocity spinboxes without triggering signals."""
        self.vel_x.blockSignals(True)
        self.vel_y.blockSignals(True)
        self.vel_z.blockSignals(True)
        try:
            self.vel_x.setValue(vel[0])
            self.vel_y.setValue(vel[1])
            self.vel_z.setValue(vel[2])
        finally:
            self.vel_x.blockSignals(False)
            self.vel_y.blockSignals(False)
            self.vel_z.blockSignals(False)

    def _update_rotation_spins(self, quat):
        """Update rotation spinboxes without triggering signals."""
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

        self.yaw_spin.blockSignals(True)
        self.pitch_spin.blockSignals(True)
        self.roll_spin.blockSignals(True)
        try:
            self.yaw_spin.setValue(np.degrees(yaw))
            self.pitch_spin.setValue(np.degrees(pitch))
            self.roll_spin.setValue(np.degrees(roll))
        finally:
            self.yaw_spin.blockSignals(False)
            self.pitch_spin.blockSignals(False)
            self.roll_spin.blockSignals(False)

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
        self.force_system_label.setText(
            f"Attached to body {self._current_force.attached_to.id}"
            if self._current_force.attached_to is not None else "Independent construction force"
        )

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

    def _on_position_changed(self):
        if self._current is None:
            return
        pos = np.array([self.pos_x.value(), self.pos_y.value(), self.pos_z.value()])
        self._current.position = pos
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

    def _on_body_transform_changed(self, body: RigidBody) -> None:
        """Handle transform updates from gizmo or other sources."""
        if body is not self._current:
            return
        # Update position spins without triggering recursive updates.
        # blockSignals is what actually prevents _on_position_changed from
        # firing and writing a rounded value back into the model on every
        # gizmo-drag frame; the _block_updates flag alone does nothing
        # unless callbacks check it, and none of them did.
        self._block_updates = True
        self.pos_x.blockSignals(True)
        self.pos_y.blockSignals(True)
        self.pos_z.blockSignals(True)
        try:
            self.pos_x.setValue(body.position[0])
            self.pos_y.setValue(body.position[1])
            self.pos_z.setValue(body.position[2])
            self._update_rotation_spins(body.orientation)
        finally:
            self.pos_x.blockSignals(False)
            self.pos_y.blockSignals(False)
            self.pos_z.blockSignals(False)
            self._block_updates = False

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
        self.scene.attach_force_to_body(self._current_force, self._current)
        self._refresh_force_live_fields()

    def _detach_force(self):
        if self._current_force is not None:
            self.scene.detach_force(self._current_force)
            self._refresh_force_live_fields()

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