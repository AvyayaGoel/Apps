"""
scene_model.py

Construction/simulation state shared by the Scene. These types deliberately sit
above the low-level physics bodies so construction objects and physical systems
can evolve compositionally without turning every future feature into a RigidBody
special case.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from body import RigidBody
from force_object import ForceObject

_system_ids = itertools.count(1)


class SceneMode(Enum):
    CONSTRUCTION = "construction"
    SIMULATION = "simulation"


@dataclass
class PhysicalSystem:
    body: RigidBody
    force_components: List[ForceObject] = field(default_factory=list)
    id: int = field(default_factory=lambda: next(_system_ids))

    def add_force(self, force: ForceObject) -> None:
        if force not in self.force_components:
            self.force_components.append(force)
        force.attached_to = self.body
        force.system_id = self.id
