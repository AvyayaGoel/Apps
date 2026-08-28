"""
scene/factory.py – added wall, floor_tile, pyramid.
"""

from __future__ import annotations

import random
from typing import Callable, Dict, Optional, Tuple

from body import RigidBody, SHAPE_BOX, SHAPE_CONE, SHAPE_CYLINDER, SHAPE_SPHERE
from config import SimulationConfig
from math_utils import vec3

RGB = Tuple[float, float, float]


def _random_color() -> RGB:
    palette = [
        (0.85, 0.25, 0.25), (0.25, 0.45, 0.85), (0.95, 0.75, 0.15),
        (0.35, 0.75, 0.35), (0.75, 0.35, 0.80), (0.95, 0.55, 0.15),
        (0.25, 0.75, 0.75), (0.90, 0.90, 0.90),
    ]
    return random.choice(palette)


def make_sphere(config: SimulationConfig, position, color: Optional[RGB] = None, radius: float = 0.5) -> RigidBody:
    return RigidBody(
        shape=SHAPE_SPHERE, shape_params={"radius": radius},
        position=vec3(*position), density=2.0,
        restitution=0.6, friction=0.4, color=color or _random_color(),
        object_kind="sphere",
    )


def make_ball(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = make_sphere(config, position, color or (0.9, 0.15, 0.15), radius=0.35)
    body.restitution = 0.85
    body.friction = 0.3
    body.object_kind = "ball"
    return body


def make_cube(config: SimulationConfig, position, color: Optional[RGB] = None, size: float = 0.8) -> RigidBody:
    he = size * 0.5
    return RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (he, he, he)},
        position=vec3(*position), density=5.0,
        restitution=0.3, friction=0.6, color=color or _random_color(),
        object_kind="cube",
    )


def make_box(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = make_cube(config, position, color or (0.65, 0.45, 0.25), size=1.0)
    body.object_kind = "box"
    return body


def make_cylinder(config: SimulationConfig, position, color: Optional[RGB] = None,
                  radius: float = 0.4, height: float = 0.9) -> RigidBody:
    return RigidBody(
        shape=SHAPE_CYLINDER, shape_params={"radius": radius, "height": height},
        position=vec3(*position), density=3.0,
        restitution=0.35, friction=0.55, color=color or _random_color(),
        object_kind="cylinder",
    )


def make_cone(config: SimulationConfig, position, color: Optional[RGB] = None,
              radius: float = 0.5, height: float = 1.0) -> RigidBody:
    return RigidBody(
        shape=SHAPE_CONE, shape_params={"radius": radius, "height": height},
        position=vec3(*position), density=3.0,
        restitution=0.3, friction=0.6, color=color or _random_color(),
        object_kind="cone",
    )


def make_pyramid(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    # Approximate as a cone for physics, but render as pyramid via mesh
    body = make_cone(config, position, color or (0.7, 0.5, 0.2), radius=0.6, height=1.0)
    body.object_kind = "pyramid"
    return body


def make_cup(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = make_cylinder(config, position, color or (0.9, 0.9, 0.95), radius=0.3, height=0.5)
    body.mass = 0.4
    body.density = 2.0
    body.restitution = 0.2
    body.object_kind = "cup"
    return body


def make_table(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (1.0, 0.45, 0.6)},
        position=vec3(*position), mass=12.0, density=1.0,
        restitution=0.1, friction=0.7, color=color or (0.55, 0.35, 0.18),
        object_kind="table",
    )
    return body


def make_car(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (0.9, 0.35, 0.5)},
        position=vec3(*position), mass=8.0, density=2.0,
        restitution=0.25, friction=0.65, color=color or (0.75, 0.1, 0.1),
        object_kind="car",
    )
    return body


def make_ramp(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (1.2, 0.15, 1.6)},
        position=vec3(*position), mass=0.0, is_static=True,
        restitution=0.2, friction=0.5, color=color or (0.6, 0.55, 0.5),
        object_kind="ramp",
    )
    return body


def make_plank(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (1.2, 0.06, 0.3)},
        position=vec3(*position), mass=2.0, density=2.0,
        restitution=0.2, friction=0.6, color=color or (0.65, 0.5, 0.32),
        object_kind="plank",
    )
    return body


def make_torus(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = make_sphere(config, position, color or (0.9, 0.6, 0.1), radius=0.5)
    body.object_kind = "torus"
    body.shape_params = {"radius": 0.5, "tube_radius": 0.18}
    return body


def make_wall(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (2.0, 1.0, 0.2)},
        position=vec3(*position), mass=0.0, is_static=True,
        restitution=0.1, friction=0.7, color=color or (0.7, 0.7, 0.7),
        object_kind="wall",
    )
    return body


def make_floor_tile(config: SimulationConfig, position, color: Optional[RGB] = None) -> RigidBody:
    body = RigidBody(
        shape=SHAPE_BOX, shape_params={"half_extents": (1.0, 0.05, 1.0)},
        position=vec3(*position), mass=0.0, is_static=True,
        restitution=0.1, friction=0.6, color=color or (0.5, 0.4, 0.3),
        object_kind="floor_tile",
    )
    return body


OBJECT_FACTORIES: Dict[str, Callable[..., RigidBody]] = {
    "sphere": make_sphere,
    "cube": make_cube,
    "cylinder": make_cylinder,
    "cone": make_cone,
    "torus": make_torus,
    "ball": make_ball,
    "cup": make_cup,
    "table": make_table,
    "car": make_car,
    "ramp": make_ramp,
    "plank": make_plank,
    "box": make_box,
    "pyramid": make_pyramid,
    "wall": make_wall,
    "floor_tile": make_floor_tile,
}
