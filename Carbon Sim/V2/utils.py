"""Geometry helpers, UndoManager, and functional group builders.

Imports: config.py (constants), models.py (Molecule, Atom)
"""
import logging
import math
from dataclasses import dataclass
from typing import List, Tuple

from config import CHAIN_SEGMENT_LENGTH, CHAIN_ZIGZAG_ANGLE_DEG
from models import Molecule, Atom, Bond

logger = logging.getLogger(__name__)


def dist(a: Atom, b: Atom) -> float:
    try:
        """Euclidean distance between two atoms."""
        return math.hypot(a.x - b.x, a.y - b.y)
    except Exception as e:
        logger.exception(f"dist error: {e}")
        return 0.0


def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    try:
        """Shortest distance from point P to segment AB."""
        vx, vy = (x2 - x1, y2 - y1)
        wx, wy = (px - x1, py - y1)
        vlen2 = vx * vx + vy * vy
        if vlen2 == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / vlen2))
        projx = x1 + t * vx
        projy = y1 + t * vy
        return math.hypot(px - projx, py - projy)
    except Exception as e:
        logger.exception(f"point_to_segment_distance error: {e}")
        return 0.0


@dataclass
class StateSnapshot:
    atoms: List[dict]
    bonds: List[dict]
    next_id: int


class UndoManager:
    """Simple undo/redo stack for Molecule state."""

    def __init__(self, max_history: int = 40):
        self.undo_stack: List[StateSnapshot] = []
        self.redo_stack: List[StateSnapshot] = []
        self.max_history = max_history
        logger.info(f'UndoManager created with max_history={max_history}')

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def snapshot(self, mol: Molecule):
        try:
            """Push current state onto undo stack. Call before mutating."""
            state = self._capture(mol)
            if self.undo_stack and self._same(state, self.undo_stack[-1]):
                return
            if len(self.undo_stack) >= self.max_history:
                self.undo_stack.pop(0)
            self.undo_stack.append(state)
            self.redo_stack.clear()
            logger.info(f'Snapshot pushed. Undo: {len(self.undo_stack)}, Redo: {len(self.redo_stack)}')
        except Exception as e:
            logger.exception(f"UndoManager snapshot error: {e}")

    def undo(self, mol: Molecule) -> bool:
        try:
            logger.info('UndoManager.undo called')
            if not self.undo_stack:
                logger.warning('Undo: stack empty')
                return False
            current = self._capture(mol)
            self.redo_stack.append(current)
            self._restore(mol, self.undo_stack.pop())
            logger.info(f'Undo performed. Undo: {len(self.undo_stack)}, Redo: {len(self.redo_stack)}')
            return True
        except Exception as e:
            logger.exception(f"UndoManager undo error: {e}")
            return False

    def redo(self, mol: Molecule) -> bool:
        try:
            logger.info('UndoManager.redo called')
            if not self.redo_stack:
                logger.warning('Redo: stack empty')
                return False
            current = self._capture(mol)
            self.undo_stack.append(current)
            self._restore(mol, self.redo_stack.pop())
            logger.info(f'Redo performed. Undo: {len(self.undo_stack)}, Redo: {len(self.redo_stack)}')
            return True
        except Exception as e:
            logger.exception(f"UndoManager redo error: {e}")
            return False

    @staticmethod
    def _capture(mol: Molecule) -> StateSnapshot:
        return StateSnapshot(atoms=[a.copy().__dict__ for a in mol.atoms],
                             bonds=[{'a1': b.a1, 'a2': b.a2, 'type': b.type} for b in mol.bonds], next_id=mol.next_id)

    @staticmethod
    def _same(a: StateSnapshot, b: StateSnapshot) -> bool:
        return a.next_id == b.next_id and a.atoms == b.atoms and (a.bonds == b.bonds)

    @staticmethod
    def _restore(mol: Molecule, state: StateSnapshot):
        logger.info(
            f'UndoManager._restore: restoring {len(state.atoms)} atoms, {len(state.bonds)} bonds, next_id={state.next_id}')
        mol.atoms = [Atom(**a) for a in state.atoms]
        mol.bonds = [Bond(b['a1'], b['a2'], b['type']) for b in state.bonds]
        mol.next_id = state.next_id


def compute_chain_zigzag(start_x: float, start_y: float, end_x: float, end_y: float) -> List[Tuple[float, float]]:
    """Turn a drag from (start_x, start_y) to (end_x, end_y) into a list of
    carbon-chain atom positions (not including the starting atom itself),
    zigzagging at CHAIN_ZIGZAG_ANGLE_DEG off the drag axis, alternating
    up/down, each segment CHAIN_SEGMENT_LENGTH long.

    The number of segments is however many whole bond-lengths fit in the
    drag distance (minimum 1 once the drag has moved at all), so the chain
    grows step-by-step as the user drags farther — exactly like dragging out
    a chain in ChemDraw/MarvinSketch. Returns [] if start and end coincide.
    """
    try:
        dx, dy = end_x - start_x, end_y - start_y
        drag_dist = math.hypot(dx, dy)
        if drag_dist < 1e-6:
            return []
        ux, uy = dx / drag_dist, dy / drag_dist
        # Perpendicular to the drag axis, used to offset alternating atoms
        # up/down to form the zigzag.
        nx, ny = -uy, ux
        n_segments = max(1, round(drag_dist / CHAIN_SEGMENT_LENGTH))
        theta = math.radians(CHAIN_ZIGZAG_ANGLE_DEG)
        forward = CHAIN_SEGMENT_LENGTH * math.cos(theta)
        side = CHAIN_SEGMENT_LENGTH * math.sin(theta)
        positions: List[Tuple[float, float]] = []
        cx, cy = start_x, start_y
        sign = 1
        for _ in range(n_segments):
            cx += ux * forward + nx * side * sign
            cy += uy * forward + ny * side * sign
            positions.append((cx, cy))
            sign *= -1
        return positions
    except Exception as e:
        logger.exception(f"compute_chain_zigzag error: {e}")
        return []


def compute_chain_hydrogens(backbone: List[Tuple[float, float]],
                            skip_first: bool = False) -> List[Tuple[float, float, int]]:
    """Given the carbon backbone of a freshly-drawn chain (in drawing order,
    `backbone[0]` being the very first carbon), return where to place the
    implicit hydrogen that complete each carbon's valence to 4 — so a
    drawn chain shows up as a real, fully-saturated alkane immediately on
    release rather than bare unsaturated carbons waiting for a manual
    "Clean Up".

    Each result is (x, y, backbone_index) — backbone_index says which
    backbone atom the H attaches to, so the caller can map it back to the
    real Atom id it created for that position.

    Geometry (matches how RDKit's own 2D depiction places alkane Hs, see
    chemistry.py / structure_library.py ghost geometry for the same
    convention elsewhere in the app):
      - A terminal carbon (one backbone neighbor) gets 3 H's: one straight
        back along the reverse of its one backbone bond, and two more at
        ±90 degrees off that same reverse direction.
      - An internal carbon (two backbone neighbors) gets 2 H's, placed
        symmetric about the external bisector of its two backbone bonds
        (i.e. pointing away from the "inside" of the zigzag's bend), each
        rotated ±90 degrees off that bisector.

    `skip_first=True` omits hydrogen for backbone[0] — used when the chain
    was started on a pre-existing atom, since that atom's real remaining
    valence (it may have other substituents already) isn't something this
    purely-geometric helper can determine; the caller leaves it to normal
    valence rules / a later Cleanup instead.
    """
    try:
        n = len(backbone)
        if n == 0:
            return []
        bond_len = CHAIN_SEGMENT_LENGTH
        results: List[Tuple[float, float, int]] = []
        start_idx = 1 if skip_first else 0
        for i in range(start_idx, n):
            cx, cy = backbone[i]
            neighbors = []
            if i > 0:
                neighbors.append(backbone[i - 1])
            if i < n - 1:
                neighbors.append(backbone[i + 1])
            if len(neighbors) == 1:
                # Terminal carbon: one H straight back, two perpendicular to that.
                nx0, ny0 = neighbors[0]
                dx, dy = cx - nx0, cy - ny0
                d = math.hypot(dx, dy) or 1.0
                bx, by = dx / d, dy / d  # unit vector pointing AWAY from the one neighbor
                perp_x, perp_y = -by, bx
                for (vx, vy) in ((bx, by), (perp_x, perp_y), (-perp_x, -perp_y)):
                    results.append((cx + vx * bond_len, cy + vy * bond_len, i))
            elif len(neighbors) == 2:
                # Internal carbon: two H's symmetric about the external bisector.
                (ax, ay), (bx2, by2) = neighbors
                d1x, d1y = cx - ax, cy - ay
                d1 = math.hypot(d1x, d1y) or 1.0
                u1x, u1y = d1x / d1, d1y / d1
                d2x, d2y = cx - bx2, cy - by2
                d2 = math.hypot(d2x, d2y) or 1.0
                u2x, u2y = d2x / d2, d2y / d2
                bisx, bisy = u1x + u2x, u1y + u2y
                bis_len = math.hypot(bisx, bisy)
                if bis_len < 1e-6:
                    # Neighbors are collinear through this atom (straight
                    # run) — bisector is undefined, fall back to the
                    # perpendicular of one bond direction.
                    bisx, bisy = -u1y, u1x
                    bis_len = math.hypot(bisx, bisy) or 1.0
                bisx, bisy = bisx / bis_len, bisy / bis_len
                perp_x, perp_y = -bisy, bisx
                half = math.radians(CHAIN_ZIGZAG_ANGLE_DEG)
                for sign in (1, -1):
                    vx = bisx * math.cos(half) + perp_x * math.sin(half) * sign
                    vy = bisy * math.cos(half) + perp_y * math.sin(half) * sign
                    vlen = math.hypot(vx, vy) or 1.0
                    results.append((cx + (vx / vlen) * bond_len, cy + (vy / vlen) * bond_len, i))
            # len(neighbors) == 0 (a 1-carbon "chain", isolated atom) is left
            # to the caller — geometrically under-defined with no drag
            # direction to react to; not expected since compute_chain_zigzag
            # never returns a single point with no implied direction.
        return results
    except Exception as e:
        logger.exception(f"compute_chain_hydrogens error: {e}")
        return []
