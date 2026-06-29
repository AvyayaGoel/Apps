"""Data models: Atom, Bond, and Molecule.

These are plain dataclasses with simple container methods.
They only import from config.py (constants).
"""
import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from config import BOND_ORDER_VALUE, VALENCES, formal_charge_range, bonds_valid_for_charge

logger = logging.getLogger(__name__)


@dataclass
class Atom:
    """A single atom in the molecule."""
    id: int
    x: float
    y: float
    element: str
    formal_charge: int = 0
    auto: bool = False

    def copy(self):
        """Deep copy — new ID not needed, caller handles that."""
        return Atom(self.id, self.x, self.y, self.element, self.formal_charge, self.auto)


@dataclass
class Bond:
    """A bond between two atoms."""
    a1: int
    a2: int
    type: str

    def copy(self):
        return Bond(self.a1, self.a2, self.type)


class Molecule:
    """Container for atoms and bonds with utility methods."""

    def __init__(self):
        self.atoms: List[Atom] = []
        self.bonds: List[Bond] = []
        self.next_id: int = 1

    def add_atom(self, x: float, y: float, element: str, formal_charge: int = 0, auto: bool = False) -> Atom:
        try:
            """Create and append a new atom. Returns it."""
            atom = Atom(self.next_id, x, y, element, formal_charge, auto)
            self.atoms.append(atom)
            self.next_id += 1
            return atom
        except Exception as e:
            logger.exception(f"Molecule add_atom error: {e}")
            raise

    def get_atom(self, atom_id: int) -> Optional[Atom]:
        try:
            """Lookup atom by ID. O(n) — fine for small molecules."""
            for a in self.atoms:
                if a.id == atom_id:
                    return a
            logger.warning(f'Atom {atom_id} not found in molecule with {len(self.atoms)} atoms')
            return None
        except Exception as e:
            logger.exception(f"Molecule get_atom error: {e}")
            return None

    def remove_atom(self, atom_id: int) -> Tuple[Optional[Atom], List[Bond]]:
        """Remove atom and its bonds, returning (removed_atom, removed_bonds)."""
        removed_atom = None
        for i, a in enumerate(self.atoms):
            if a.id == atom_id:
                removed_atom = a
                self.atoms.pop(i)
                break
        removed_bonds = []
        if removed_atom is not None:
            remaining_bonds = []
            for b in self.bonds:
                if b.a1 == atom_id or b.a2 == atom_id:
                    removed_bonds.append(b)
                else:
                    remaining_bonds.append(b)
            self.bonds = remaining_bonds
        return removed_atom, removed_bonds

    def remove_bond(self, idx: int) -> Optional[Bond]:
        """Remove bond by index, returning the removed bond."""
        if 0 <= idx < len(self.bonds):
            return self.bonds.pop(idx)
        return None

    def add_bond(self, a1: int, a2: int, btype: str) -> bool:
        try:
            """Add a bond if one does not already exist between these atoms."""
            for b in self.bonds:
                if {b.a1, b.a2} == {a1, a2}:
                    logger.warning(f'Bond between {a1} and {a2} already exists (type={b.type})')
                    return False
            self.bonds.append(Bond(a1, a2, btype))
            return True
        except Exception as e:
            logger.exception(f"Molecule add_bond error: {e}")
            return False

    def bond_between(self, id1: int, id2: int) -> Optional[int]:
        try:
            """Return bond index if atoms are bonded, else None."""
            for i, b in enumerate(self.bonds):
                if {b.a1, b.a2} == {id1, id2}:
                    return i
            return None
        except Exception as e:
            logger.exception(f"Molecule bond_between error: {e}")
            return None

    def clear(self):
        try:
            """Wipe everything."""
            self.atoms.clear()
            self.bonds.clear()
            self.next_id = 1
        except Exception as e:
            logger.exception(f"Molecule clear error: {e}")

    def center(self) -> tuple[float, float]:
        try:
            """Geometric center of all atoms."""
            if not self.atoms:
                return 0.0, 0.0
            cx = sum((a.x for a in self.atoms)) / len(self.atoms)
            cy = sum((a.y for a in self.atoms)) / len(self.atoms)
            return cx, cy
        except Exception as e:
            logger.exception(f"Molecule center error: {e}")
            return 0.0, 0.0

    def selection_center(self, atom_ids) -> tuple[float, float]:
        try:
            """Geometric center of just the given atom IDs (used as the pivot
            for rotate/flip so a fragment reorients in place instead of
            jumping to the whole molecule's center)."""
            atoms = [a for a in self.atoms if a.id in atom_ids]
            if not atoms:
                return 0.0, 0.0
            cx = sum(a.x for a in atoms) / len(atoms)
            cy = sum(a.y for a in atoms) / len(atoms)
            return cx, cy
        except Exception as e:
            logger.exception(f"Molecule selection_center error: {e}")
            return 0.0, 0.0

    def rotate_atoms(self, atom_ids, degrees: float):
        """Rotate the given atoms by `degrees` (clockwise, screen
        coordinates) around their own centroid. Pure coordinate transform —
        bonds/charges are untouched since connectivity doesn't change."""
        try:
            if not atom_ids:
                return
            cx, cy = self.selection_center(atom_ids)
            theta = math.radians(degrees)
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            for a in self.atoms:
                if a.id in atom_ids:
                    dx, dy = a.x - cx, a.y - cy
                    a.x = cx + dx * cos_t - dy * sin_t
                    a.y = cy + dx * sin_t + dy * cos_t
        except Exception as e:
            logger.exception(f"Molecule rotate_atoms error: {e}")

    def flip_atoms(self, atom_ids, axis: str = 'horizontal'):
        """Mirror the given atoms across the given axis through their own
        centroid. 'horizontal' flips left<->right (mirrors x); 'vertical'
        flips top<->bottom (mirrors y). Pure coordinate transform."""
        try:
            if not atom_ids:
                return
            cx, cy = self.selection_center(atom_ids)
            for a in self.atoms:
                if a.id in atom_ids:
                    if axis == 'horizontal':
                        a.x = cx - (a.x - cx)
                    else:
                        a.y = cy - (a.y - cy)
        except Exception as e:
            logger.exception(f"Molecule flip_atoms error: {e}")

    def nudge_atoms(self, atom_ids, dx: float, dy: float):
        """Translate the given atoms by (dx, dy). Pure coordinate
        transform — bonds/charges are untouched since connectivity doesn't
        change. Used for arrow-key nudging of a selection."""
        try:
            if not atom_ids:
                return
            for a in self.atoms:
                if a.id in atom_ids:
                    a.x += dx
                    a.y += dy
        except Exception as e:
            logger.exception(f"Molecule nudge_atoms error: {e}")

    def total_bond_order(self, atom_id: int) -> float:
        try:
            """Sum of bond orders connected to this atom."""
            total = 0
            for b in self.bonds:
                if atom_id in (b.a1, b.a2):
                    total += BOND_ORDER_VALUE.get(b.type, 0)
            return total
        except Exception as e:
            logger.exception(f"Molecule total_bond_order error: {e}")
            return 0

    def free_valence(self, atom_id: int) -> float:
        try:
            """Remaining valence (how many more bonds this atom can take)."""
            atom = self.get_atom(atom_id)
            if not atom:
                logger.warning(f'free_valence: atom {atom_id} not found, returning 0')
                return 0
            max_v = VALENCES.get(atom.element, 4) + atom.formal_charge
            used = self.total_bond_order(atom_id)
            return max(0, max_v - used)
        except Exception as e:
            logger.exception(f"Molecule free_valence error: {e}")
            return 0

    def can_bond(self, id1: int, id2: int, btype: str) -> bool:
        try:
            """Check if both atoms have enough free valence for this bond type."""
            add = BOND_ORDER_VALUE.get(btype, 0)
            f1 = self.free_valence(id1)
            f2 = self.free_valence(id2)
            return f1 >= add and f2 >= add
        except Exception as e:
            logger.exception(f"Molecule can_bond error: {e}")
            return False

    def can_change_bond_type(self, bond_index: int, new_type: str) -> bool:
        try:
            """Check if an EXISTING bond can be retyped to `new_type`. Unlike
            can_bond (used when adding a brand-new bond), this must first
            give each atom back the valence the bond's CURRENT order already
            uses — otherwise every atom would look "full" on its own
            existing bond and no retype (not even to the same type) would
            ever pass."""
            if not (0 <= bond_index < len(self.bonds)):
                logger.warning(f'can_change_bond_type: invalid bond index {bond_index}')
                return False
            bond = self.bonds[bond_index]
            current_order = BOND_ORDER_VALUE.get(bond.type, 0)
            new_order = BOND_ORDER_VALUE.get(new_type, 0)
            f1 = self.free_valence(bond.a1) + current_order
            f2 = self.free_valence(bond.a2) + current_order
            return f1 >= new_order and f2 >= new_order
        except Exception as e:
            logger.exception(f"Molecule can_change_bond_type error: {e}")
            return False

    def can_set_formal_charge(self, atom_id: int, new_charge: int) -> tuple[bool, str]:
        """Decide whether `new_charge` is a chemically sane formal charge for
        this atom right now. Returns (allowed, reason). `reason` is empty on
        success and a short human-readable explanation on failure — used for
        tooltips/status messages so a refusal isn't just a silent no-op.

        Two independent checks, both grounded in real chemistry rather than a
        single "valence electron count" ceiling:
          1. Element-level range — does any real structure ever draw this
             element with this formal charge at all? (config.ELEMENT_CHARGE_RANGE)
          2. Structural consistency — given the bonds already drawn on this
             atom, would this charge make its total valence (bonds + charge
             shift) physically nonsensical, e.g. an already-tetravalent
             carbon cannot also be a carbanion (that would need a 5th bond
             or a lone pair where none can fit).
        """
        try:
            atom = self.get_atom(atom_id)
            if not atom:
                return False, 'Atom not found'
            lo, hi = formal_charge_range(atom.element)
            if not (lo <= new_charge <= hi):
                if lo == hi == 0:
                    return False, f'{atom.element} is not drawn with a formal charge in real structures'
                return False, f'{atom.element} formal charges in real structures range {lo:+d} to {hi:+d}'
            used = self.total_bond_order(atom_id)
            if not bonds_valid_for_charge(atom.element, new_charge, used):
                return False, (f'{atom.element}{new_charge:+d} has no valid electron structure '
                               f'with the {used:g} bond(s) already on this atom')
            return True, ''
        except Exception as e:
            logger.exception(f"Molecule can_set_formal_charge error: {e}")
            return False, 'Internal error checking formal charge'

    def to_dict(self) -> dict:
        try:
            """Export to plain dict (for JSON)."""
            return {
                'atoms': [
                    {'id': a.id, 'x': a.x, 'y': a.y, 'element': a.element, 'formal_charge': a.formal_charge,
                     'auto': a.auto}
                    for a in self.atoms
                ],
                'bonds': [{'a1': b.a1, 'a2': b.a2, 'type': b.type} for b in self.bonds],
                'next_id': self.next_id
            }
        except Exception as e:
            logger.exception(f"Molecule to_dict error: {e}")
            return {}

    def from_dict(self, data: dict):
        try:
            """Import from plain dict (from JSON)."""
            self.clear()
            atoms_data = data.get('atoms', [])
            bonds_data = data.get('bonds', [])
            for a in atoms_data:
                atom = Atom(a['id'], a['x'], a['y'], a['element'], a.get('formal_charge', 0), a.get('auto', False))
                self.atoms.append(atom)
                self.next_id = max(self.next_id, atom.id + 1)
            for b in bonds_data:
                self.bonds.append(Bond(b['a1'], b['a2'], b['type']))
        except Exception as e:
            logger.exception(f"Molecule from_dict error: {e}")
