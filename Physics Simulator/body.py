"""
physics/body.py

Defines RigidBody: the physics-only representation of an object.
Now includes density, scale, and automatic mass update from volume.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from math_utils import IDENTITY_QUAT, quat_integrate, quat_rotate_vector, vec3

SHAPE_SPHERE = "sphere"
SHAPE_BOX = "box"
SHAPE_CYLINDER = "cylinder"
SHAPE_CONE = "cone"
SHAPE_COMPOUND = "compound"

_id_counter = itertools.count(1)


@dataclass
class RigidBody:
    shape: str
    shape_params: dict
    position: np.ndarray = field(default_factory=lambda: vec3())
    velocity: np.ndarray = field(default_factory=lambda: vec3())
    orientation: np.ndarray = field(default_factory=lambda: IDENTITY_QUAT.copy())
    angular_velocity: np.ndarray = field(default_factory=lambda: vec3())
    mass: float = 1.0
    density: float = 1.0  # mass per unit volume
    scale: float = 1.0  # uniform scale factor
    restitution: float = 0.5
    friction: float = 0.5
    is_static: bool = False
    is_asleep: bool = False
    sleep_timer: float = 0.0
    color: Tuple[float, float, float] = (0.7, 0.7, 0.7)
    object_kind: str = "shape"
    id: int = field(default_factory=lambda: next(_id_counter))

    def __post_init__(self) -> None:
        self._update_inv_mass()
        self._update_mass_from_density()

    # ------------------------------------------------------------------
    # Mass / density / scale
    # ------------------------------------------------------------------

    def _volume(self) -> float:
        """Compute volume based on shape and base shape_params (before scaling)."""
        if self.shape == SHAPE_SPHERE:
            r = self.shape_params.get("radius", 0.5)
            return (4.0 / 3.0) * math.pi * r ** 3
        elif self.shape == SHAPE_BOX:
            hx, hy, hz = self.shape_params.get("half_extents", (0.4, 0.4, 0.4))
            return (2 * hx) * (2 * hy) * (2 * hz)
        elif self.shape == SHAPE_CYLINDER:
            r = self.shape_params.get("radius", 0.4)
            h = self.shape_params.get("height", 0.9)
            return math.pi * r ** 2 * h
        elif self.shape == SHAPE_CONE:
            r = self.shape_params.get("radius", 0.5)
            h = self.shape_params.get("height", 1.0)
            return (1.0 / 3.0) * math.pi * r ** 2 * h
        else:
            return 1.0

    def _update_mass_from_density(self) -> None:
        """Compute mass = density * volume * scale^3."""
        if self.is_static:
            self.mass = 0.0
            self.inv_mass = 0.0
            return
        vol = self._volume() * (self.scale ** 3)
        self.mass = max(0.001, self.density * vol)
        self._update_inv_mass()

    def _update_inv_mass(self) -> None:
        if self.is_static or self.mass <= 1e-9:
            self.inv_mass = 0.0
        else:
            self.inv_mass = 1.0 / self.mass

    def set_scale(self, new_scale: float) -> None:
        """Change scale and update mass accordingly."""
        new_scale = max(0.01, new_scale)
        self.scale = new_scale
        self._update_mass_from_density()

    def set_density(self, new_density: float) -> None:
        """Change density and update mass."""
        new_density = max(0.001, new_density)
        self.density = new_density
        self._update_mass_from_density()

    # ------------------------------------------------------------------
    # Bounding helpers (use scaled dimensions)
    # ------------------------------------------------------------------

    def bounding_radius(self) -> float:
        base_radius = 0.5
        if self.shape == SHAPE_SPHERE:
            base_radius = self.shape_params.get("radius", 0.5)
        elif self.shape == SHAPE_BOX:
            hx, hy, hz = self.shape_params.get("half_extents", (0.4, 0.4, 0.4))
            base_radius = float(np.linalg.norm([hx, hy, hz]))
        elif self.shape == SHAPE_CYLINDER:
            r = self.shape_params.get("radius", 0.4)
            h = self.shape_params.get("height", 0.9)
            base_radius = float(np.hypot(r, h * 0.5))
        elif self.shape == SHAPE_CONE:
            r = self.shape_params.get("radius", 0.5)
            h = self.shape_params.get("height", 1.0)
            base_radius = float(np.hypot(r, h * 0.5))
        return base_radius * self.scale

    def aabb(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.shape == SHAPE_BOX:
            he = self.get_scaled_half_extents()
            corners = np.array([
                [-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1],
                [-1, 1, -1], [1, 1, -1], [1, 1, 1], [-1, 1, 1],
            ], dtype=np.float64) * he
            vertices = np.array([quat_rotate_vector(self.orientation, c) + self.position for c in corners])
            return vertices.min(axis=0), vertices.max(axis=0)
        r = self.bounding_radius()
        he = vec3(r, r, r)
        return self.position - he, self.position + he

    def bottom_y(self) -> float:
        if self.shape == SHAPE_BOX:
            return self.aabb()[0][1]
        return self.position[1] - self.half_height()

    def half_height(self) -> float:
        if self.shape == SHAPE_SPHERE:
            return self.shape_params.get("radius", 0.5) * self.scale
        if self.shape == SHAPE_BOX:
            he = self.get_scaled_half_extents()
            axes = [quat_rotate_vector(self.orientation, axis) for axis in np.eye(3)]
            return float(sum(abs(axis[1]) * he[i] for i, axis in enumerate(axes)))
        if self.shape in (SHAPE_CYLINDER, SHAPE_CONE):
            return self.shape_params.get("height", 1.0) * 0.5 * self.scale
        return self.bounding_radius()

    # ------------------------------------------------------------------
    # Integration
    # ------------------------------------------------------------------

    def apply_impulse(self, impulse: np.ndarray, contact_point: Optional[np.ndarray] = None) -> None:
        if self.is_static or self.inv_mass == 0.0:
            return
        self.velocity += impulse * self.inv_mass
        self.wake()
        if contact_point is not None:
            r = contact_point - self.position
            torque_impulse = np.cross(r, impulse)
            # Approximate inertia tensor as sphere
            radius = self.bounding_radius()
            inertia = 0.4 * self.mass * radius * radius
            inv_inertia = 1.0 / inertia if inertia > 1e-9 else 0.0
            self.angular_velocity += torque_impulse * inv_inertia

    def wake(self) -> None:
        self.is_asleep = False
        self.sleep_timer = 0.0

    def set_static(self, static: bool) -> None:
        self.is_static = static
        self._update_inv_mass()
        if static:
            self.velocity[:] = 0.0
            self.angular_velocity[:] = 0.0
            self.is_asleep = False
        else:
            self.wake()

    def integrate(self, dt: float, gravity: float, air_damping: float, angular_damping: float) -> None:
        if self.is_static or self.is_asleep:
            return
        self.velocity[0] *= air_damping
        self.velocity[2] *= air_damping
        self.velocity[1] -= gravity * dt
        self.angular_velocity *= angular_damping
        self.position += self.velocity * dt
        self.orientation = quat_integrate(self.orientation, self.angular_velocity, dt)

    def update_sleep_state(self, dt: float, lin_threshold: float, ang_threshold: float, time_required: float) -> None:
        if self.is_static:
            return
        speed = float(np.linalg.norm(self.velocity))
        ang_speed = float(np.linalg.norm(self.angular_velocity))
        if speed < lin_threshold and ang_speed < ang_threshold:
            self.sleep_timer += dt
            if self.sleep_timer >= time_required:
                self.is_asleep = True
                self.velocity[:] = 0.0
                self.angular_velocity[:] = 0.0
        else:
            self.sleep_timer = 0.0

    # ------------------------------------------------------------------
    # Shape accessors for collision
    # ------------------------------------------------------------------

    def get_scaled_half_extents(self) -> np.ndarray:
        if self.shape == SHAPE_BOX:
            return np.array(self.shape_params.get("half_extents", (0.4, 0.4, 0.4))) * self.scale
        return np.array([self.bounding_radius()] * 3)

    def get_scaled_radius(self) -> float:
        if self.shape == SHAPE_SPHERE:
            return self.shape_params.get("radius", 0.5) * self.scale
        if self.shape in (SHAPE_CYLINDER, SHAPE_CONE):
            return self.shape_params.get("radius", 0.4) * self.scale
        return self.bounding_radius()
