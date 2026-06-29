"""QGraphicsScene subclass that manages molecule rendering and interaction state."""

import logging
from typing import Optional, Set, Dict

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsItem, QGraphicsPathItem

from canvas_items import AtomItem, BondItem
from models import Molecule, Atom

logger = logging.getLogger(__name__)


class MoleculeScene(QGraphicsScene):
    def __init__(self, mol: Molecule, parent=None):
        super().__init__(parent)
        self.mol = mol
        self._atom_items: Dict[int, AtomItem] = {}
        self._bond_items: list = []
        self._selected_atoms: Set[int] = set()
        self._selected_bonds: Set[int] = set()
        self._marquee_item: Optional[QGraphicsItem] = None  # can be rect or path
        self._lasso_points = []
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)

    def rebuild(self):
        try:
            self.clear()
            self._atom_items.clear()
            self._bond_items.clear()
            for i, bond in enumerate(self.mol.bonds):
                item = BondItem(bond, self.mol)
                self.addItem(item)
                self._bond_items.append(item)
            for atom in self.mol.atoms:
                item = AtomItem(atom)
                self.addItem(item)
                self._atom_items[atom.id] = item
            self._update_selection()
            for item in self._bond_items:
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            for item in self._atom_items.values():
                item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        except Exception as e:
            logger.exception(f"MoleculeScene rebuild error: {e}")

    def _update_selection(self):
        try:
            for aid, item in self._atom_items.items():
                item.set_selected(aid in self._selected_atoms)
            for i, item in enumerate(self._bond_items):
                item.set_selected(i in self._selected_bonds)
        except Exception as e:
            logger.exception(f"MoleculeScene update_selection error: {e}")

    def refresh_bond(self, bond_index: int):
        try:
            if 0 <= bond_index < len(self._bond_items):
                item = self._bond_items[bond_index]
                item.prepareGeometryChange()
                item.update()
        except Exception as e:
            logger.exception(f"MoleculeScene refresh_bond error: {e}")

    def refresh_atom(self, atom_id: int):
        try:
            item = self._atom_items.get(atom_id)
            if item is not None:
                item.prepareGeometryChange()
                item.update()
        except Exception as e:
            logger.exception(f"MoleculeScene refresh_atom error: {e}")

    def add_atom_item(self, atom: Atom):
        try:
            if atom.id in self._atom_items:
                return
            item = AtomItem(atom)
            self.addItem(item)
            self._atom_items[atom.id] = item
            item.set_selected(atom.id in self._selected_atoms)
        except Exception as e:
            logger.exception(f"MoleculeScene add_atom_item error: {e}")

    def add_bond_item(self, bond):
        try:
            item = BondItem(bond, self.mol)
            self.addItem(item)
            self._bond_items.append(item)
            bond_index = len(self._bond_items) - 1
            item.set_selected(bond_index in self._selected_bonds)
        except Exception as e:
            logger.exception(f"MoleculeScene add_bond_item error: {e}")

    def set_selected_atoms(self, atom_ids: Set[int]):
        try:
            self._selected_atoms = set(atom_ids)
            self._selected_bonds.clear()
            for i, b in enumerate(self.mol.bonds):
                if b.a1 in self._selected_atoms and b.a2 in self._selected_atoms:
                    self._selected_bonds.add(i)
            self._update_selection()
        except Exception as e:
            logger.exception(f"MoleculeScene set_selected_atoms error: {e}")

    def get_selected_atoms(self) -> Set[int]:
        return self._selected_atoms.copy()

    def get_selected_bonds(self) -> Set[int]:
        return self._selected_bonds.copy()

    def hit_atom(self, pos: QPointF) -> Optional[Atom]:
        items = self.items(pos, Qt.ItemSelectionMode.IntersectsItemShape)
        for item in items:
            if isinstance(item, AtomItem):
                return item.atom
        return None

    def hit_bond(self, pos: QPointF, threshold: float = 8) -> Optional[int]:
        rect = QRectF(pos.x() - threshold, pos.y() - threshold, threshold * 2, threshold * 2)
        items = self.items(rect, Qt.ItemSelectionMode.IntersectsItemShape)
        for item in items:
            if isinstance(item, BondItem):
                if item.hit_test(pos.x(), pos.y(), threshold):
                    for i, bond in enumerate(self.mol.bonds):
                        if bond is item.bond:
                            return i
        return None

    def update_atom_positions(self):
        try:
            for atom in self.mol.atoms:
                if atom.id in self._atom_items:
                    self._atom_items[atom.id].update_position()
            for item in self._bond_items:
                item.prepareGeometryChange()
                item.update()
        except Exception as e:
            logger.exception(f"MoleculeScene update_atom_positions error: {e}")

    # ---- rectangle marquee ----
    def start_marquee(self, pos: QPointF):
        try:
            if self._marquee_item:
                self.removeItem(self._marquee_item)
            rect_item = QGraphicsRectItem()
            rect_item.setPen(QPen(QColor(120, 180, 255), 2, Qt.PenStyle.DashLine))
            rect_item.setBrush(QBrush(QColor(100, 160, 255, 60)))
            rect_item.setRect(QRectF(pos, pos))
            rect_item.setZValue(20)
            self._marquee_item = rect_item
            self.addItem(self._marquee_item)
        except Exception as e:
            logger.exception(f"MoleculeScene start_marquee error: {e}")

    def update_marquee(self, pos: QPointF):
        try:
            if self._marquee_item and isinstance(self._marquee_item, QGraphicsRectItem):
                rect = self._marquee_item.rect()
                new_rect = QRectF(rect.topLeft(), pos)
                self._marquee_item.setRect(new_rect)
        except Exception as e:
            logger.exception(f"MoleculeScene update_marquee error: {e}")

    def end_marquee(self) -> Set[int]:
        try:
            selected: Set[int] = set()
            if self._marquee_item and isinstance(self._marquee_item, QGraphicsRectItem):
                rect = self._marquee_item.rect().normalized()
                for a in self.mol.atoms:
                    if rect.contains(QPointF(a.x, a.y)):
                        selected.add(a.id)
                self.removeItem(self._marquee_item)
                self._marquee_item = None
            return selected
        except Exception as e:
            logger.exception(f"MoleculeScene end_marquee error: {e}")
            return set()

    # ---- lasso marquee ----
    def start_lasso(self, pos: QPointF):
        """Start freehand lasso selection."""
        if self._marquee_item:
            self.removeItem(self._marquee_item)
        path = QPainterPath()
        path.moveTo(pos)
        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor(120, 180, 255), 2, Qt.PenStyle.DashLine))
        path_item.setBrush(QBrush(QColor(100, 160, 255, 60)))
        path_item.setZValue(20)
        self._marquee_item = path_item
        self.addItem(self._marquee_item)
        self._lasso_points = [pos]

    def update_lasso(self, pos: QPointF):
        if self._marquee_item and isinstance(self._marquee_item, QGraphicsPathItem):
            self._lasso_points.append(pos)
            path = QPainterPath()
            if len(self._lasso_points) > 1:
                path.moveTo(self._lasso_points[0])
                for p in self._lasso_points[1:]:
                    path.lineTo(p)
            else:
                path.moveTo(pos)
            self._marquee_item.setPath(path)

    def end_lasso(self) -> Set[int]:
        selected: Set[int] = set()
        if self._marquee_item and isinstance(self._marquee_item, QGraphicsPathItem):
            if len(self._lasso_points) > 2:
                from PyQt6.QtGui import QPolygonF
                poly = QPolygonF(self._lasso_points)
                for a in self.mol.atoms:
                    pt = QPointF(a.x, a.y)
                    if poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                        selected.add(a.id)
            self.removeItem(self._marquee_item)
            self._marquee_item = None
            self._lasso_points = []
        return selected

    # ---- incremental removal methods ----
    def remove_atom_item(self, atom_id: int) -> None:
        """Remove the AtomItem and any connected BondItems."""
        to_remove = []
        for i, b in enumerate(self.mol.bonds):
            if b.a1 == atom_id or b.a2 == atom_id:
                to_remove.append(i)
        for i in sorted(to_remove, reverse=True):
            self.remove_bond_item(i)
        item = self._atom_items.pop(atom_id, None)
        if item:
            self.removeItem(item)

    def remove_bond_item(self, bond_index: int) -> None:
        """Remove the BondItem at bond_index from scene."""
        if 0 <= bond_index < len(self._bond_items):
            item = self._bond_items.pop(bond_index)
            self.removeItem(item)
