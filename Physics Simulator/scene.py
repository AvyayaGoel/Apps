"""
scene/scene.py – with secondary selection, new shapes, and constraint management.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from body import RigidBody
from config import SimulationConfig, config as global_config
from constraints import HingeConstraint, RopeConstraint, SpringConstraint
from event_bus import bus
from factory import OBJECT_FACTORIES
from force_object import ForceObject
from math_utils import ray_sphere_intersect, vec3, quat_rotate_vector, quat_conjugate
from scene_model import PhysicalSystem, SceneMode
from world import PhysicsWorld

logger = logging.getLogger(__name__)


class Scene:
    def __init__(self, config: SimulationConfig = global_config) -> None:
        self.config = config
        self.world = PhysicsWorld(config)
        self.selected_body: Optional[RigidBody] = None
        self.secondary_selected_body: Optional[RigidBody] = None  # for constraints
        self.selected_force: Optional[ForceObject] = None
        self.selected_constraint: Optional[object] = None
        self.mode = SceneMode.CONSTRUCTION
        self.physical_systems: list[PhysicalSystem] = []
        self.time_of_day = config.time_of_day_hours

        bus.subscribe("input.set_time_of_day", self._on_set_time_of_day)

    # ------------------------------------------------------------------
    # Spawning (added wall, floor_tile, pyramid)
    # ------------------------------------------------------------------

    def spawn(self, kind: str, position=None, color=None) -> RigidBody:
        factory = OBJECT_FACTORIES.get(kind)
        if factory is None:
            raise ValueError(f"Unknown object kind: {kind!r}")
        if position is None:
            position = (random.uniform(-3, 3), 4.0 + random.uniform(0, 2), random.uniform(-3, 3))
        body = factory(self.config, position, color)
        body.velocity[:] = 0.0
        body.angular_velocity[:] = 0.0
        self.world.add_body(body)
        bus.publish("scene.object_spawned", body)
        logger.info(f"Spawned {kind} at {position}")
        return body

    def spawn_force_object(self, position=None) -> ForceObject:
        if position is None:
            position = (random.uniform(-3, 3), 1.0 + random.uniform(0, 1), random.uniform(-3, 3))
        force = ForceObject(position=vec3(*position))
        self.world.add_force_object(force)
        bus.publish("scene.force_spawned", force)
        logger.info(f"Spawned force object at {position}")
        return force

    def add_static(self, body: RigidBody) -> RigidBody:
        self.world.add_body(body)
        return body

    # ------------------------------------------------------------------
    # Selection / deletion / forces
    # ------------------------------------------------------------------

    def select(self, obj) -> None:
        if isinstance(obj, RigidBody):
            # If shift held, set as secondary
            # We'll handle via a method in gl_widget: set_secondary
            self.selected_body = obj
            self.selected_constraint = None
            bus.publish("scene.selection_changed", obj)
            logger.info(f"Selected body {obj.id}")
        elif isinstance(obj, ForceObject):
            self.selected_force = obj
            self.selected_constraint = None
            bus.publish("scene.selection_changed", obj)
            logger.info(f"Selected force object {id(obj)}")
        elif isinstance(obj, (SpringConstraint, RopeConstraint, HingeConstraint)):
            self.selected_constraint = obj
            bus.publish("scene.selection_changed", obj)
        else:
            self.selected_body = None
            self.selected_force = None
            self.selected_constraint = None
            bus.publish("scene.selection_changed", None)

    def set_secondary_selection(self, body: Optional[RigidBody]) -> None:
        self.secondary_selected_body = body

    def pick(self, ray_origin, ray_dir) -> Optional[object]:
        best_obj, best_t = None, float("inf")

        # Check rigid bodies
        for body in self.world.bodies:
            t = ray_sphere_intersect(ray_origin, ray_dir, body.position, body.bounding_radius())
            if t is not None and t < best_t:
                best_t = t
                best_obj = body

        # Check force objects
        for force in self.world.force_objects:
            pos = force.get_world_position()
            t = ray_sphere_intersect(ray_origin, ray_dir, pos, force.bounding_radius())
            if t is not None and t < best_t:
                best_t = t
                best_obj = force

        # Check constraints (maybe pick by position of anchors? skip for now)
        return best_obj

    def delete_selected(self) -> None:
        if self.selected_constraint is not None:
            self.world.remove_constraint(self.selected_constraint)
            self.select(None)
        elif self.selected_force is not None:
            self.detach_force(self.selected_force)
            self.world.remove_force_object(self.selected_force)
            self.selected_force = None
            bus.publish("scene.selection_changed", self.selected_body)
        elif self.selected_body is not None:
            for force in self.world.force_objects:
                if force.attached_to is self.selected_body:
                    self.detach_force(force)
            self.world.remove_body(self.selected_body)
            self.select(None)

    def apply_random_impulse(self, body: Optional[RigidBody] = None) -> None:
        target = body or self.selected_body
        if target is None or target.is_static:
            return
        strength = self.config.impulse_strength
        impulse = vec3(
            random.uniform(-1, 1) * strength,
            random.uniform(0.4, 1.0) * strength,
            random.uniform(-1, 1) * strength,
        ) * target.mass
        target.apply_impulse(impulse)
        bus.publish("scene.impulse_applied", target)

    def move_selected_to(self, world_pos) -> None:
        if self.selected_body is None:
            return
        self.selected_body.position = vec3(*world_pos)
        self.selected_body.velocity[:] = 0.0
        self.selected_body.wake()
        bus.publish("scene.body_transform_changed", self.selected_body)

    def move_selected_force_to(self, world_pos) -> None:
        if self.selected_force is None:
            return
        self.move_force_to(self.selected_force, world_pos)

    def move_force_to(self, force: ForceObject, world_pos) -> None:
        world_pos = vec3(*world_pos)
        if force.attached_to is not None:
            body = force.attached_to
            delta = world_pos - body.position
            force.local_offset = quat_rotate_vector(quat_conjugate(body.orientation), delta)
            force.position = world_pos
        else:
            force.position = world_pos

    def attach_selected_force_to_body(self) -> Optional[PhysicalSystem]:
        if self.selected_force is None or self.selected_body is None:
            return None
        return self.attach_force_to_body(self.selected_force, self.selected_body)

    def attach_force_to_body(self, force: ForceObject, body: RigidBody) -> PhysicalSystem:
        delta = force.get_world_position() - body.position
        force.local_offset = quat_rotate_vector(quat_conjugate(body.orientation), delta)
        system = self._system_for_body(body)
        system.add_force(force)
        force.position = force.get_world_position()
        bus.publish("scene.system_changed", system)
        bus.publish("scene.selection_changed", body)
        return system

    def detach_force(self, force: ForceObject) -> None:
        world_position = force.get_world_position()
        force.attached_to = None
        force.system_id = None
        force.position = world_position
        for system in self.physical_systems:
            if force in system.force_components:
                system.force_components.remove(force)
        self.physical_systems = [s for s in self.physical_systems if s.body in self.world.bodies]

    def _system_for_body(self, body: RigidBody) -> PhysicalSystem:
        for system in self.physical_systems:
            if system.body is body:
                return system
        system = PhysicalSystem(body=body)
        self.physical_systems.append(system)
        return system

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def clear_all(self) -> None:
        self.select(None)
        self.physical_systems.clear()
        self.world.clear(keep_static=True)
        bus.publish("scene.cleared", None)

    def reset_default_scene(self) -> None:
        self.select(None)
        self.physical_systems.clear()
        self.mode = SceneMode.CONSTRUCTION
        self.world.clear(keep_static=False)
        self.spawn("sphere", position=(-1.0, 4.0, 0.0))
        self.spawn("sphere", position=(1.2, 6.0, -0.5), color=(0.2, 0.6, 0.9))
        self.spawn("cube", position=(0.0, 8.0, 1.0))
        self.spawn("ball", position=(-2.0, 3.0, 1.5))
        self.spawn("wall", position=(4.0, 1.0, 0.0))
        self.spawn("floor_tile", position=(0.0, 0.5, 4.0))
        bus.publish("scene.reset", None)

    # ------------------------------------------------------------------
    # Time of day
    # ------------------------------------------------------------------

    def _on_set_time_of_day(self, hours: float) -> None:
        self.time_of_day = hours % 24.0
        self.config.time_of_day_hours = self.time_of_day
        bus.publish("scene.time_of_day_changed", self.time_of_day)

    # ------------------------------------------------------------------
    # Frame update
    # ------------------------------------------------------------------

    def begin_simulation(self) -> None:
        self.mode = SceneMode.SIMULATION
        for body in self.world.bodies:
            body.wake()
        bus.publish("scene.mode_changed", self.mode)

    def stop_simulation(self) -> None:
        self.mode = SceneMode.CONSTRUCTION
        for body in self.world.bodies:
            body.velocity[:] = 0.0
            body.angular_velocity[:] = 0.0
            body.wake()
        bus.publish("scene.mode_changed", self.mode)

    def update(self, dt: float) -> None:
        if self.config.day_length_seconds > 0:
            self.time_of_day = (self.time_of_day + dt * 24.0 / self.config.day_length_seconds) % 24.0
            self.config.time_of_day_hours = self.time_of_day
        for force in self.world.force_objects:
            force.update_position_from_attachment()
        if self.mode is SceneMode.SIMULATION:
            self.world.step(dt)
