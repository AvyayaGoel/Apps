"""
physics/force_object.py

A visual force object that applies a force to a target body.
"""

from __future__ import annotations

import logging
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from body import RigidBody
from math_utils import vec3, normalize, quat_rotate_vector

logger = logging.getLogger(__name__)


class ForceType(Enum):
    IMPULSE = "impulse"  # One-time impulse (or per-substep if active)
    CONSTANT = "constant"  # Continuous force applied every substep
    VARIABLE = "variable"  # Future: user-controlled magnitude


@dataclass
class ForceObject:
    position: np.ndarray = field(default_factory=lambda: vec3(0, 2, 0))
    direction: np.ndarray = field(default_factory=lambda: vec3(0, 1, 0))
    magnitude: float = 2.0  # Reduced default — was 5.0, too strong per-substep
    force_type: ForceType = ForceType.CONSTANT
    attached_to: Optional["RigidBody"] = None
    local_offset: np.ndarray = field(default_factory=lambda: vec3(0, 0, 0))
    is_active: bool = True
    is_one_shot: bool = False
    color: tuple = (1.0, 0.6, 0.0)

    def __post_init__(self):
        self.direction = normalize(self.direction)

    def bounding_radius(self) -> float:
        """For picking (visual radius)."""
        return 0.5

    def get_world_position(self) -> np.ndarray:
        """Return the force arrow's world position (accounts for attachment)."""
        if self.attached_to is not None:
            return self.attached_to.position + quat_rotate_vector(self.attached_to.orientation, self.local_offset)
        return self.position

    def get_contact_point(self) -> np.ndarray:
        """Return the point where the force is applied (for torque calculation)."""
        return self.get_world_position()

    def apply(self, body: RigidBody, dt: float) -> None:
        """Apply the force to a single RigidBody at the contact point.

        For CONSTANT forces: F = ma, so impulse = F*dt, applied per substep.
        This gives proper acceleration over time without direct velocity hacking.
        """
        if not self.is_active or body is None or body.is_static:
            return
        contact_point = self.get_contact_point()
        if self.force_type == ForceType.IMPULSE:
            impulse = self.direction * self.magnitude
            body.apply_impulse(impulse, contact_point)
            if self.is_one_shot:
                self.is_active = False
        elif self.force_type == ForceType.CONSTANT:
            # Proper physics: force * dt = impulse, then apply at contact point
            # This gives F = ma behavior with proper torque from offset
            force = self.direction * self.magnitude
            impulse = force * dt
            body.apply_impulse(impulse, contact_point)
        elif self.force_type == ForceType.VARIABLE:
            # Placeholder — same as constant for now
            force = self.direction * self.magnitude
            impulse = force * dt
            body.apply_impulse(impulse, contact_point)

    def update_position_from_attachment(self) -> None:
        """Sync position field when attached so renderer doesn't drift."""
        if self.attached_to is not None:
            self.position = self.get_world_position()
