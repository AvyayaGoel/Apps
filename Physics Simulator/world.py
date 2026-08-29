"""
physics/world.py – now includes constraint handling.
"""

from __future__ import annotations

import logging
from typing import List

from body import RigidBody
from collision import broad_phase_pairs, resolve_ground_contact, resolve_pair
from config import SimulationConfig
from constraints import Constraint
from event_bus import bus
from force_object import ForceObject

logger = logging.getLogger(__name__)


class PhysicsWorld:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.bodies: List[RigidBody] = []
        self.force_objects: List[ForceObject] = []
        self.constraints: List[Constraint] = []
        self._accumulator: float = 0.0
        self.ground_y: float = 0.0

    def add_body(self, body: RigidBody) -> RigidBody:
        self.bodies.append(body)
        bus.publish("physics.body_added", body)
        logger.info(f"Added body {body.id} ({body.object_kind})")
        return body

    def remove_body(self, body: RigidBody) -> None:
        if body in self.bodies:
            self.bodies.remove(body)
            bus.publish("physics.body_removed", body)

    def add_force_object(self, force: ForceObject) -> ForceObject:
        self.force_objects.append(force)
        bus.publish("physics.force_added", force)
        logger.info(f"Added force object at {force.position}")
        return force

    def remove_force_object(self, force: ForceObject) -> None:
        if force in self.force_objects:
            self.force_objects.remove(force)
            bus.publish("physics.force_removed", force)

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)
        bus.publish("physics.constraint_added", constraint)

    def remove_constraint(self, constraint: Constraint) -> None:
        if constraint in self.constraints:
            self.constraints.remove(constraint)
            bus.publish("physics.constraint_removed", constraint)

    def clear(self, keep_static: bool = False) -> None:
        self.bodies = [b for b in self.bodies if keep_static and b.is_static]
        self.force_objects = []
        self.constraints = []
        bus.publish("physics.cleared", None)

    def step(self, frame_dt: float) -> None:
        frame_dt = min(frame_dt, 0.25)
        self._accumulator += frame_dt
        dt = self.config.fixed_timestep
        steps_taken = 0
        while self._accumulator >= dt and steps_taken < self.config.max_substeps:
            self._substep(dt)
            self._accumulator -= dt
            steps_taken += 1
        if steps_taken == self.config.max_substeps:
            self._accumulator = 0.0

    def _substep(self, dt: float) -> None:
        cfg = self.config

        # 1. Apply forces from force objects
        for force in self.force_objects:
            if not force.is_active:
                continue
            if force.attached_to is not None and force.attached_to in self.bodies:
                if not force.attached_to.is_static:
                    force.apply(force.attached_to, dt)

        # 2. Integrate
        for body in self.bodies:
            body.integrate(dt, cfg.gravity, cfg.air_damping, cfg.angular_damping)

        # 3. Ground contact
        for body in self.bodies:
            resolve_ground_contact(body, self.ground_y, cfg.ground_friction, cfg.ground_restitution)

        # 4. Body-body collisions. Multiple solver passes improve resting contacts
        # and stacking without adding fake placement rules.
        for _ in range(cfg.collision_solver_iterations):
            for a, b in broad_phase_pairs(self.bodies):
                resolve_pair(a, b)

        # 5. Constraints (position-based)
        for constraint in self.constraints:
            constraint.solve(dt)

        # 6. Sleep
        for body in self.bodies:
            body.update_sleep_state(dt, cfg.sleep_linear_threshold,
                                    cfg.sleep_angular_threshold, cfg.sleep_time_required)

        # 7. Remove fallen
        self._remove_fallen_bodies()

    def _remove_fallen_bodies(self) -> None:
        kill_y = self.config.kill_plane_y
        fallen = [b for b in self.bodies if b.position[1] < kill_y]
        for b in fallen:
            self.remove_body(b)
