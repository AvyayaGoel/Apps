"""
physics/constraints.py

Constraint classes: Spring, Rope (distance), Hinge (revolute).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from body import RigidBody
from math_utils import vec3, normalize, quat_rotate_vector


@dataclass
class Constraint:
    body_a: RigidBody
    body_b: Optional[RigidBody]  # None means world (static)
    anchor_a: np.ndarray  # local offset from body_a's COM
    anchor_b: Optional[np.ndarray]  # local offset from body_b's COM, if any
    stiffness: float = 0.8
    damping: float = 0.1
    enabled: bool = True

    def solve(self, dt: float) -> None:
        """Apply constraint correction. Override in subclasses."""
        pass


@dataclass
class SpringConstraint(Constraint):
    """Linear spring connecting two anchor points."""
    rest_length: float = 1.0
    k: float = 100.0  # spring constant

    def solve(self, dt: float) -> None:
        if not self.enabled:
            return
        # World positions of anchors
        pos_a = self.body_a.position + quat_rotate_vector(self.body_a.orientation, self.anchor_a)
        if self.body_b is not None:
            pos_b = self.body_b.position + quat_rotate_vector(self.body_b.orientation, self.anchor_b)
        else:
            pos_b = self.anchor_b  # world anchor

        delta = pos_b - pos_a
        dist = np.linalg.norm(delta)
        if dist < 1e-9:
            return
        direction = delta / dist

        # Spring force: F = -k * (dist - rest_length) - damping * relative_velocity
        rel_vel = (self.body_b.velocity if self.body_b is not None else vec3()) - self.body_a.velocity
        vel_along = np.dot(rel_vel, direction)
        force_mag = -self.k * (dist - self.rest_length) - self.damping * vel_along
        force = direction * force_mag

        # Apply impulse = force * dt
        impulse = force * dt
        self.body_a.apply_impulse(impulse, pos_a)
        if self.body_b is not None:
            self.body_b.apply_impulse(-impulse, pos_b)


@dataclass
class RopeConstraint(Constraint):
    """Inextensible rope: only pulls, does not push."""
    max_length: float = 1.0

    def solve(self, dt: float) -> None:
        if not self.enabled:
            return
        pos_a = self.body_a.position + quat_rotate_vector(self.body_a.orientation, self.anchor_a)
        if self.body_b is not None:
            pos_b = self.body_b.position + quat_rotate_vector(self.body_b.orientation, self.anchor_b)
        else:
            pos_b = self.anchor_b

        delta = pos_b - pos_a
        dist = np.linalg.norm(delta)
        if dist < self.max_length or dist < 1e-9:
            return
        direction = delta / dist
        penetration = dist - self.max_length

        # Position correction (project)
        total_inv_mass = self.body_a.inv_mass + (self.body_b.inv_mass if self.body_b else 0)
        if total_inv_mass < 1e-9:
            return
        correction = direction * (penetration / total_inv_mass)
        self.body_a.position += correction * self.body_a.inv_mass
        if self.body_b is not None:
            self.body_b.position -= correction * self.body_b.inv_mass

        # Velocity correction (impulse to stop separation)
        rel_vel = (self.body_b.velocity if self.body_b else vec3()) - self.body_a.velocity
        vel_along = np.dot(rel_vel, direction)
        if vel_along > 0:  # already moving together
            return
        # Impulse to cancel relative velocity
        j = -vel_along / total_inv_mass
        impulse = direction * j
        self.body_a.apply_impulse(impulse, pos_a)
        if self.body_b is not None:
            self.body_b.apply_impulse(-impulse, pos_b)


@dataclass
class HingeConstraint(Constraint):
    """Revolute joint: restricts relative translation along a fixed axis."""
    axis: np.ndarray = field(default_factory=lambda: vec3(0, 1, 0))  # world-space axis of rotation
    angle: float = 0.0  # current angle (for limits)
    min_angle: float = -np.inf
    max_angle: float = np.inf

    def solve(self, dt: float) -> None:
        if not self.enabled:
            return
        # For simplicity, we only enforce that the anchor points stay aligned.
        # We project the bodies so that the anchors coincide.
        pos_a = self.body_a.position + quat_rotate_vector(self.body_a.orientation, self.anchor_a)
        if self.body_b is not None:
            pos_b = self.body_b.position + quat_rotate_vector(self.body_b.orientation, self.anchor_b)
        else:
            pos_b = self.anchor_b

        delta = pos_b - pos_a
        # Project delta onto plane perpendicular to axis
        axis = normalize(self.axis)
        proj = delta - np.dot(delta, axis) * axis
        if np.linalg.norm(proj) < 1e-9:
            return
        direction = normalize(proj)
        penetration = np.linalg.norm(proj)

        total_inv_mass = self.body_a.inv_mass + (self.body_b.inv_mass if self.body_b else 0)
        if total_inv_mass < 1e-9:
            return
        correction = direction * (penetration / total_inv_mass)
        self.body_a.position += correction * self.body_a.inv_mass
        if self.body_b is not None:
            self.body_b.position -= correction * self.body_b.inv_mass

        # Velocity correction: cancel relative velocity along the plane
        rel_vel = (self.body_b.velocity if self.body_b else vec3()) - self.body_a.velocity
        vel_along = np.dot(rel_vel, direction)
        if vel_along > 0:
            return
        j = -vel_along / total_inv_mass
        impulse = direction * j
        self.body_a.apply_impulse(impulse, pos_a)
        if self.body_b is not None:
            self.body_b.apply_impulse(-impulse, pos_b)

        # Angle limits (optional) - could be added later
