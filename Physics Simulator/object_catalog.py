"""
object_catalog.py

Data-driven object catalog. Reads data/objects.json once at import time and
replaces factory.py's hardcoded OBJECT_FACTORIES dict (one Python function
per object). Adding a new object - including, eventually, a user-created
one - means adding a JSON entry, not writing a new Python function.

Exposes:
  - CATALOG: Dict[str, ObjectDef]
  - categories() -> [(category_name, [ObjectDef, ...]), ...] in file order -
    the object palette reads this instead of keeping its own hardcoded list
  - spawn(kind, config, position, color) -> RigidBody
  - get_parts(kind) / get_legacy_mesh(kind) - used by meshes.py to decide
    how to draw each object kind: a data-driven "parts" list (composed from
    the existing primitive shapes) for most objects, or a named reference
    to a pre-existing Python builder for the handful of objects (cup, car,
    ramp, pyramid) with genuinely bespoke vertex geometry that isn't just a
    composition of primitives.
  - reload() - re-reads the JSON file, so catalog edits (or future
    user-created objects) can be picked up without restarting the app.

Falls back to a tiny built-in catalog (sphere + cube) if data/objects.json
is missing or fails to parse, so a broken/missing data file degrades
gracefully instead of preventing the app from starting.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from body import RigidBody
from math_utils import vec3

RGB = Tuple[float, float, float]
logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent / "data" / "objects.json"

_RANDOM_PALETTE = [
    (0.85, 0.25, 0.25), (0.25, 0.45, 0.85), (0.95, 0.75, 0.15),
    (0.35, 0.75, 0.35), (0.75, 0.35, 0.80), (0.95, 0.55, 0.15),
    (0.25, 0.75, 0.75), (0.90, 0.90, 0.90),
]


def random_color() -> RGB:
    return random.choice(_RANDOM_PALETTE)


@dataclass
class ObjectDef:
    kind: str
    display_name: str
    category: str
    icon_family: str
    icon_color: RGB
    shape: str
    shape_params: dict
    density: float = 1.0
    restitution: float = 0.5
    friction: float = 0.5
    is_static: bool = False
    color: Optional[RGB] = None
    random_color: bool = False
    parts: Optional[list] = None
    legacy_mesh: Optional[str] = None


def _load() -> Dict[str, ObjectDef]:
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        catalog: Dict[str, ObjectDef] = {}
        for entry in raw["objects"]:
            obj = ObjectDef(
                kind=entry["kind"],
                display_name=entry.get("display_name", entry["kind"].replace("_", " ").title()),
                category=entry.get("category", "Misc"),
                icon_family=entry.get("icon_family", "rect"),
                icon_color=tuple(entry.get("icon_color", (0.6, 0.6, 0.6))),
                shape=entry["shape"],
                shape_params=entry.get("shape_params", {}),
                density=entry.get("density", 1.0),
                restitution=entry.get("restitution", 0.5),
                friction=entry.get("friction", 0.5),
                is_static=entry.get("is_static", False),
                color=tuple(entry["color"]) if "color" in entry else None,
                random_color=entry.get("random_color", False),
                parts=entry.get("parts"),
                legacy_mesh=entry.get("legacy_mesh"),
            )
            catalog[obj.kind] = obj
        if not catalog:
            raise ValueError("objects.json parsed but contained no objects")
        return catalog
    except Exception:
        logger.exception(
            f"Failed to load object catalog from {_DATA_PATH} - "
            f"falling back to a minimal built-in catalog (sphere, cube) so the app can still start"
        )
        return {
            "sphere": ObjectDef(
                kind="sphere", display_name="Sphere", category="Primitives",
                icon_family="circle", icon_color=(0.25, 0.45, 0.85),
                shape="sphere", shape_params={"radius": 0.5}, density=2.0,
                restitution=0.6, friction=0.4, random_color=True,
            ),
            "cube": ObjectDef(
                kind="cube", display_name="Cube", category="Primitives",
                icon_family="rect", icon_color=(0.35, 0.75, 0.35),
                shape="box", shape_params={"half_extents": (0.4, 0.4, 0.4)}, density=5.0,
                restitution=0.3, friction=0.6, random_color=True,
            ),
        }


CATALOG: Dict[str, ObjectDef] = _load()


def categories() -> List[Tuple[str, List[ObjectDef]]]:
    """Object defs grouped by category, in first-seen order."""
    seen_order: List[str] = []
    groups: Dict[str, List[ObjectDef]] = {}
    for obj in CATALOG.values():
        if obj.category not in groups:
            groups[obj.category] = []
            seen_order.append(obj.category)
        groups[obj.category].append(obj)
    return [(cat, groups[cat]) for cat in seen_order]


def get_parts(kind: str) -> Optional[list]:
    obj = CATALOG.get(kind)
    return obj.parts if obj is not None else None


def get_legacy_mesh(kind: str) -> Optional[str]:
    obj = CATALOG.get(kind)
    return obj.legacy_mesh if obj is not None else None


def spawn(kind: str, position, color: Optional[RGB] = None) -> RigidBody:
    obj = CATALOG.get(kind)
    if obj is None:
        raise ValueError(f"Unknown object kind: {kind!r}")
    final_color = color
    if final_color is None:
        if obj.random_color:
            final_color = random_color()
        elif obj.color is not None:
            final_color = obj.color
        else:
            final_color = (0.7, 0.7, 0.7)
    return RigidBody(
        shape=obj.shape,
        shape_params=dict(obj.shape_params),
        position=vec3(*position),
        density=obj.density,
        restitution=obj.restitution,
        friction=obj.friction,
        is_static=obj.is_static,
        color=final_color,
        object_kind=obj.kind,
    )


def reload() -> None:
    """Re-read data/objects.json from disk, so catalog edits (or future
    user-created objects) can be picked up without restarting the app."""
    global CATALOG
    CATALOG = _load()
    import meshes
    meshes.clear_cache()
