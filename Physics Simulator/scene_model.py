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
from constraints import Constraint
from force_object import ForceObject

_system_ids = itertools.count(1)


class SceneMode(Enum):
    CONSTRUCTION = "construction"
    SIMULATION = "simulation"


@dataclass
class PhysicalSystem:
    """A body plus everything currently attached to it - forces, and now
    constraints. This is the extensibility point section 5 asks for: new
    component kinds (springs, ropes, pulleys, ...) attach here rather than
    each being tracked as an independent, disconnected list."""
    body: RigidBody
    force_components: List[ForceObject] = field(default_factory=list)
    constraint_components: List[Constraint] = field(default_factory=list)
    id: int = field(default_factory=lambda: next(_system_ids))

    def add_force(self, force: ForceObject) -> None:
        if force not in self.force_components:
            self.force_components.append(force)
        force.attached_to = self.body
        force.system_id = self.id

    def add_constraint(self, constraint: Constraint) -> None:
        if constraint not in self.constraint_components:
            self.constraint_components.append(constraint)

    def remove_constraint(self, constraint: Constraint) -> None:
        if constraint in self.constraint_components:
            self.constraint_components.remove(constraint)
