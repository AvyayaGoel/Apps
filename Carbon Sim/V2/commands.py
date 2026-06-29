"""Undo/redo commands with delta state, not full snapshots."""

import logging
import math
from typing import List, Optional, Tuple

from models import Molecule, Atom, Bond
from scene import MoleculeScene

logger = logging.getLogger(__name__)


class Command:
    def execute(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError


class MacroCommand(Command):
    def __init__(self, name: str = ""):
        self.name = name
        self.commands: List[Command] = []

    def add(self, cmd: Command) -> None:
        self.commands.append(cmd)

    def execute(self) -> None:
        for cmd in self.commands:
            cmd.execute()

    def undo(self) -> None:
        for cmd in reversed(self.commands):
            cmd.undo()


class AddAtomCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, x: float, y: float,
                 element: str, formal_charge: int = 0, auto: bool = False):
        self.mol = mol
        self.scene = scene
        self.x = x
        self.y = y
        self.element = element
        self.formal_charge = formal_charge
        self.auto = auto
        self.atom_id: Optional[int] = None

    def execute(self) -> None:
        if self.atom_id is None:
            atom = self.mol.add_atom(self.x, self.y, self.element, self.formal_charge, self.auto)
            self.atom_id = atom.id
        else:
            atom = Atom(self.atom_id, self.x, self.y, self.element, self.formal_charge, self.auto)
            self.mol.atoms.append(atom)
            if self.atom_id >= self.mol.next_id:
                self.mol.next_id = self.atom_id + 1
        self.scene.add_atom_item(self.mol.get_atom(self.atom_id))

    def undo(self) -> None:
        if self.atom_id is None:
            return
        self.mol.remove_atom(self.atom_id)
        self.scene.remove_atom_item(self.atom_id)


class RemoveAtomCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, atom_id: int):
        self.mol = mol
        self.scene = scene
        self.atom_id = atom_id
        self.atom_data: Optional[dict] = None
        self.bonds_data: List[dict] = []

    def execute(self) -> None:
        atom = self.mol.get_atom(self.atom_id)
        if atom is None:
            return
        self.atom_data = {
            'id': atom.id, 'x': atom.x, 'y': atom.y,
            'element': atom.element, 'formal_charge': atom.formal_charge, 'auto': atom.auto
        }
        self.bonds_data = []
        for b in self.mol.bonds[:]:
            if b.a1 == self.atom_id or b.a2 == self.atom_id:
                self.bonds_data.append({'a1': b.a1, 'a2': b.a2, 'type': b.type})
        self.mol.remove_atom(self.atom_id)
        self.scene.remove_atom_item(self.atom_id)

    def undo(self) -> None:
        if self.atom_data is None:
            return
        atom = Atom(self.atom_data['id'], self.atom_data['x'], self.atom_data['y'],
                    self.atom_data['element'], self.atom_data['formal_charge'], self.atom_data['auto'])
        self.mol.atoms.append(atom)
        if atom.id >= self.mol.next_id:
            self.mol.next_id = atom.id + 1
        self.scene.add_atom_item(atom)
        for bdata in self.bonds_data:
            if self.mol.bond_between(bdata['a1'], bdata['a2']) is None:
                self.mol.add_bond(bdata['a1'], bdata['a2'], bdata['type'])
                idx = self.mol.bond_between(bdata['a1'], bdata['a2'])
                if idx is not None:
                    self.scene.add_bond_item(self.mol.bonds[idx])


class AddBondCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, a1: int, a2: int, btype: str):
        self.mol = mol
        self.scene = scene
        self.a1 = a1
        self.a2 = a2
        self.btype = btype
        self.bond_index: Optional[int] = None

    def execute(self) -> None:
        if self.bond_index is None:
            if self.mol.add_bond(self.a1, self.a2, self.btype):
                self.bond_index = self.mol.bond_between(self.a1, self.a2)
        else:
            if self.mol.bond_between(self.a1, self.a2) is None:
                self.mol.add_bond(self.a1, self.a2, self.btype)
                self.bond_index = self.mol.bond_between(self.a1, self.a2)
        if self.bond_index is not None:
            self.scene.add_bond_item(self.mol.bonds[self.bond_index])

    def undo(self) -> None:
        if self.bond_index is not None:
            self.mol.remove_bond(self.bond_index)
            self.scene.remove_bond_item(self.bond_index)
            self.bond_index = None


class RemoveBondCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, bond_index: int):
        self.mol = mol
        self.scene = scene
        self.bond_index = bond_index
        self.bond_data: Optional[dict] = None

    def execute(self) -> None:
        if self.bond_index < 0 or self.bond_index >= len(self.mol.bonds):
            return
        bond = self.mol.bonds[self.bond_index]
        self.bond_data = {'a1': bond.a1, 'a2': bond.a2, 'type': bond.type}
        self.mol.remove_bond(self.bond_index)
        self.scene.remove_bond_item(self.bond_index)

    def undo(self) -> None:
        if self.bond_data is None:
            return
        if self.mol.bond_between(self.bond_data['a1'], self.bond_data['a2']) is None:
            self.mol.add_bond(self.bond_data['a1'], self.bond_data['a2'], self.bond_data['type'])
            idx = self.mol.bond_between(self.bond_data['a1'], self.bond_data['a2'])
            if idx is not None:
                self.scene.add_bond_item(self.mol.bonds[idx])


class MoveAtomsCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, atom_ids: List[int], dx: float, dy: float):
        self.mol = mol
        self.scene = scene
        self.atom_ids = atom_ids
        self.dx = dx
        self.dy = dy

    def execute(self) -> None:
        for aid in self.atom_ids:
            atom = self.mol.get_atom(aid)
            if atom:
                atom.x += self.dx
                atom.y += self.dy
        self.scene.update_atom_positions()

    def undo(self) -> None:
        for aid in self.atom_ids:
            atom = self.mol.get_atom(aid)
            if atom:
                atom.x -= self.dx
                atom.y -= self.dy
        self.scene.update_atom_positions()


class RotateAtomsCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, atom_ids: List[int],
                 angle_deg: float, center: Tuple[float, float]):
        self.mol = mol
        self.scene = scene
        self.atom_ids = atom_ids
        self.angle_deg = angle_deg
        self.cx, self.cy = center

    def execute(self) -> None:
        self._rotate(self.angle_deg)

    def undo(self) -> None:
        self._rotate(-self.angle_deg)

    def _rotate(self, angle: float) -> None:
        theta = math.radians(angle)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        for aid in self.atom_ids:
            atom = self.mol.get_atom(aid)
            if atom:
                dx = atom.x - self.cx
                dy = atom.y - self.cy
                atom.x = self.cx + dx * cos_t - dy * sin_t
                atom.y = self.cy + dx * sin_t + dy * cos_t
        self.scene.update_atom_positions()


class FlipAtomsCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, atom_ids: List[int],
                 axis: str, center: Tuple[float, float]):
        self.mol = mol
        self.scene = scene
        self.atom_ids = atom_ids
        self.axis = axis
        self.cx, self.cy = center

    def execute(self) -> None:
        self._flip()

    def undo(self) -> None:
        self._flip()

    def _flip(self) -> None:
        for aid in self.atom_ids:
            atom = self.mol.get_atom(aid)
            if atom:
                if self.axis == 'horizontal':
                    atom.x = self.cx - (atom.x - self.cx)
                else:
                    atom.y = self.cy - (atom.y - self.cy)
        self.scene.update_atom_positions()


class ChangeBondTypeCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, bond_index: int, new_type: str):
        self.mol = mol
        self.scene = scene
        self.bond_index = bond_index
        self.new_type = new_type
        self.old_type: Optional[str] = None

    def execute(self) -> None:
        if self.bond_index < 0 or self.bond_index >= len(self.mol.bonds):
            return
        bond = self.mol.bonds[self.bond_index]
        if self.old_type is None:
            self.old_type = bond.type
        bond.type = self.new_type
        self.scene.refresh_bond(self.bond_index)

    def undo(self) -> None:
        if self.bond_index < 0 or self.bond_index >= len(self.mol.bonds) or self.old_type is None:
            return
        bond = self.mol.bonds[self.bond_index]
        bond.type = self.old_type
        self.scene.refresh_bond(self.bond_index)


class SetFormalChargeCommand(Command):
    def __init__(self, mol: Molecule, scene: MoleculeScene, atom_id: int, new_charge: int):
        self.mol = mol
        self.scene = scene
        self.atom_id = atom_id
        self.new_charge = new_charge
        self.old_charge: Optional[int] = None

    def execute(self) -> None:
        atom = self.mol.get_atom(self.atom_id)
        if atom is None:
            return
        if self.old_charge is None:
            self.old_charge = atom.formal_charge
        atom.formal_charge = self.new_charge
        self.scene.refresh_atom(self.atom_id)

    def undo(self) -> None:
        if self.old_charge is None:
            return
        atom = self.mol.get_atom(self.atom_id)
        if atom:
            atom.formal_charge = self.old_charge
            self.scene.refresh_atom(self.atom_id)


class SnapshotCommand(Command):
    def __init__(self, mol: Molecule):
        self.mol = mol
        self.state = {
            'atoms': [a.copy().__dict__ for a in mol.atoms],
            'bonds': [{'a1': b.a1, 'a2': b.a2, 'type': b.type} for b in mol.bonds],
            'next_id': mol.next_id
        }

    def execute(self) -> None:
        self._restore(self.state)

    def undo(self) -> None:
        self._restore(self.state)

    def _restore(self, state):
        self.mol.atoms = [Atom(**a) for a in state['atoms']]
        self.mol.bonds = [Bond(b['a1'], b['a2'], b['type']) for b in state['bonds']]
        self.mol.next_id = state['next_id']
