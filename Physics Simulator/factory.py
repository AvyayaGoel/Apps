"""
scene/factory.py

DEPRECATED - kept only for backward compatibility. Object definitions now
live in data/objects.json, loaded by object_catalog.py. This module just
re-exposes the old OBJECT_FACTORIES dict shape (kind -> callable) in case
anything else still imports it directly; new code should use
object_catalog.spawn() / object_catalog.CATALOG instead.
"""

from __future__ import annotations

import functools
from typing import Callable, Dict

import object_catalog
from body import RigidBody

OBJECT_FACTORIES: Dict[str, Callable[..., RigidBody]] = {
    kind: functools.partial(object_catalog.spawn, kind) for kind in object_catalog.CATALOG
}