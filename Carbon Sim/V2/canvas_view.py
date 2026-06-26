"""QGraphicsView + Scene with all molecule interaction logic."""
import logging
import math
from enum import Enum, auto
from typing import Optional, Set, Dict, Tuple

from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent, QWheelEvent, QCursor, QPixmap
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem

from canvas_items import AtomItem, BondItem
from config import (
    RADIUS, BOND_ORDER_VALUE, CANVAS_W, WINDOW_H, GRID_SIZE, GRID_COLOR, GRID_MAJOR_COLOR,
    GRID_MAJOR_INTERVAL, BOND_IDEAL_LENGTH, BOND_DISPLAY_TO_LETTER, RDKIT_2D_BOND_LENGTH,
    CHAIN_SEGMENT_LENGTH
)
from models import Molecule, Atom
from utils import point_to_segment_distance, compute_chain_zigzag, compute_chain_hydrogens

logger = logging.getLogger(__name__)


class SelectDragMode(Enum):
    NONE = auto()
    ATOMS = auto()
    MARQUEE = auto()
    EMPTY = auto()


class MoleculeScene(QGraphicsScene):
    """Custom scene that handles molecule rendering."""

    def __init__(self, mol: Molecule, parent=None):
        super().__init__(parent)
        self.mol = mol
        self._atom_items: Dict[int, AtomItem] = {}
        self._bond_items: list = []
        self._selected_atoms: Set[int] = set()
        self._selected_bonds: Set[int] = set()
        self._marquee_item: Optional[QGraphicsRectItem] = None
        self.setSceneRect(-10000, -10000, 20000, 20000)

    def rebuild(self):
        try:
            """Rebuild all graphics items from molecule data."""
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
        try:
            for atom in reversed(self.mol.atoms):
                r = RADIUS.get(atom.element, 12) + 6
                d = math.hypot(pos.x() - atom.x, pos.y() - atom.y)
                if d <= r:
                    return atom
            return None
        except Exception as e:
            logger.exception(f"MoleculeScene hit_atom error: {e}")
            return None

    def hit_bond(self, pos: QPointF, threshold: float = 8) -> Optional[int]:
        for i, bond in enumerate(self.mol.bonds):
            a1 = self.mol.get_atom(bond.a1)
            a2 = self.mol.get_atom(bond.a2)
            if a1 is None or a2 is None:
                logger.warning(f'hit_bond: missing atom for bond {i} ({bond.a1}-{bond.a2})')
                continue
            dx, dy = (a2.x - a1.x, a2.y - a1.y)
            d = math.hypot(dx, dy) or 1
            nx, ny = (-dy / d, dx / d)
            order = BOND_ORDER_VALUE.get(bond.type, 1)
            spacing = 6
            for o in range(order):
                off = (o - (order - 1) / 2) * spacing
                x1 = a1.x + nx * off
                y1 = a1.y + ny * off
                x2 = a2.x + nx * off
                y2 = a2.y + ny * off
                dist = point_to_segment_distance(pos.x(), pos.y(), x1, y1, x2, y2)
                if dist <= threshold:
                    return i
        return None

    def update_atom_positions(self):
        try:
            for atom in self.mol.atoms:
                if atom.id in self._atom_items:
                    self._atom_items[atom.id].update_position()
            for item in self._bond_items:
                item.update()
        except Exception as e:
            logger.exception(f"MoleculeScene update_atom_positions error: {e}")

    def start_marquee(self, pos: QPointF):
        try:
            if self._marquee_item:
                self.removeItem(self._marquee_item)
            self._marquee_item = QGraphicsRectItem()
            self._marquee_item.setPen(QPen(QColor(120, 180, 255), 2, Qt.PenStyle.DashLine))
            self._marquee_item.setBrush(QBrush(QColor(100, 160, 255, 60)))
            self._marquee_item.setRect(QRectF(pos, pos))
            self.addItem(self._marquee_item)
        except Exception as e:
            logger.exception(f"MoleculeScene start_marquee error: {e}")

    def update_marquee(self, pos: QPointF):
        try:
            if self._marquee_item:
                rect = self._marquee_item.rect()
                new_rect = QRectF(rect.topLeft(), pos)
                self._marquee_item.setRect(new_rect)
        except Exception as e:
            logger.exception(f"MoleculeScene update_marquee error: {e}")

    def end_marquee(self) -> Set[int]:
        try:
            selected: Set[int] = set()
            if self._marquee_item:
                rect = self._marquee_item.rect().normalized()
                logger.info(f'MoleculeScene.end_marquee: rect={rect}')
                for a in self.mol.atoms:
                    if rect.contains(QPointF(a.x, a.y)):
                        selected.add(a.id)
                self.removeItem(self._marquee_item)
                self._marquee_item = None
            return selected
        except Exception as e:
            logger.exception(f"MoleculeScene end_marquee error: {e}")
            return set()


class CanvasView(QGraphicsView):
    """Main canvas with zoom, pan, and molecule editing."""
    atoms_moved = pyqtSignal()
    atom_added = pyqtSignal()
    bond_added = pyqtSignal()
    # Emitted right BEFORE an atom-add / bond-add / formal-charge mutation,
    # so the undo snapshot captures pre-mutation state — mirroring how
    # atoms_deleted already fires before its mutation. Without this, undo
    # had nothing to revert to on the very next press (it only ever held
    # the post-mutation state), so a single Ctrl+Z appeared to do nothing.
    mutation_about_to_apply = pyqtSignal()
    selection_changed = pyqtSignal()
    mouse_moved = pyqtSignal(float, float)
    atoms_deleted = pyqtSignal()
    # Fired once per individual atom/bond removed during a delete-drag, so
    # the info panel / status bar stay live as the user drags through
    # several items — unlike atoms_deleted, this does NOT push undo (the
    # whole drag gesture is one undo step, pushed via atoms_deleted at the
    # start of the gesture only).
    atom_erased = pyqtSignal()
    drag_started = pyqtSignal()
    structure_about_to_place = pyqtSignal()
    structure_placed = pyqtSignal()
    formal_charge_changed = pyqtSignal()
    formal_charge_rejected = pyqtSignal(str)
    formal_charge_mode_exited = pyqtSignal()
    chain_mode_exited = pyqtSignal()
    chain_about_to_build = pyqtSignal()
    chain_built = pyqtSignal()
    transform_about_to_apply = pyqtSignal()
    transform_applied = pyqtSignal()
    selection_empty_for_transform = pyqtSignal()

    def __init__(self, mol: Molecule, parent=None):
        super().__init__(parent)
        self.mol = mol
        self.scene = MoleculeScene(mol, self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(6, 12, 22)))
        self.setMinimumSize(400, 400)
        # Without this, Qt only delivers mouseMoveEvent while a button is held
        # down — plain hover (no click) produces nothing, which is exactly the
        # ghost-placement flow: move the cursor, then click to commit.
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.tool_mode = 'select'
        self.selected_element = 'C'
        self.bond_mode = 'S'
        self._zoom = 1.0
        self._camera_x = 0.0
        self._camera_y = 0.0
        self._drag_start = QPointF()
        self._drag_offsets: Dict[int, Tuple[float, float]] = {}
        self._drag_undo_pushed = False
        self._bond_start_id: Optional[int] = None
        self._panning = False
        self._last_pan_pos = QPoint()
        self._select_drag_mode = SelectDragMode.NONE
        self._edit_click_candidate: Optional[Atom] = None
        self._edit_click_pos: QPointF = QPointF(0, 0)
        self._edit_click_threshold = 6
        self._show_grid = True
        self._snap_enabled = False
        self._smart_join = True
        self._last_mouse_world = QPointF(0, 0)
        self._pending_structure: Optional[
            dict] = None  # {'atoms': [(x,y,el,charge)], 'bonds': [(i1,i2,type)], 'name': str}
        # Formal-charge editing: '+' / '-' / None. When set, the next atom
        # click in edit mode applies that charge delta instead of normal
        # edit-mode behavior (no element placement, no bond drawing start).
        self._formal_charge_sign: Optional[str] = None
        # Chain tool: toggled on from ActionToolbar, active only in Edit
        # mode. Click (on an atom or empty canvas) and drag to grow a
        # zigzag carbon chain; release commits it. Independent of
        # _bond_start_id / _formal_charge_sign — only one of the three is
        # ever "armed" at a time, enforced by ActionToolbar's mutual
        # exclusivity, but the canvas checks its own flag first regardless.
        self._chain_active = False
        self._chain_dragging = False  # True only between chain press and release
        self._chain_start_id: Optional[int] = None  # atom the chain is anchored to, if started on one
        self._chain_start_pos: QPointF = QPointF(0, 0)  # world pos drag began at (atom or empty click)
        self._chain_preview: list = []  # [(x, y)] live zigzag positions while dragging, world coords
        # Delete tool: held-button drag continuously erases whatever the
        # cursor passes over (atoms or bonds), not just a single click.
        # One undo step covers the whole drag gesture, mirroring how
        # atom-move-drag only pushes once via _drag_undo_pushed.
        self._delete_dragging = False
        self._delete_drag_undo_pushed = False
        self._update_transform()

    def set_grid_visible(self, visible: bool):
        try:
            self._show_grid = visible
            self.viewport().update()
        except Exception as e:
            logger.exception(f"CanvasView set_grid_visible error: {e}")

    def set_snap_enabled(self, enabled: bool):
        try:
            self._snap_enabled = enabled
        except Exception as e:
            logger.exception(f"CanvasView set_snap_enabled error: {e}")

    def set_smart_join(self, enabled: bool):
        try:
            self._smart_join = enabled
        except Exception as e:
            logger.exception(f"CanvasView set_smart_join error: {e}")

    def _snap_to_grid(self, x: float, y: float) -> Tuple[float, float]:
        try:
            if not self._snap_enabled:
                return x, y
            gs = GRID_SIZE
            sx = round(x / gs) * gs
            sy = round(y / gs) * gs
            return sx, sy
        except Exception as e:
            logger.exception(f"CanvasView snap_to_grid error: {e}")
            return x, y

    def drawBackground(self, painter: QPainter, rect: QRectF):
        try:
            painter.fillRect(rect, QColor(6, 12, 22))
            if not self._show_grid:
                return
            gs = GRID_SIZE
            r_left = int(rect.left())
            r_top = int(rect.top())
            r_right = int(rect.right())
            r_bottom = int(rect.bottom())
            left = r_left // gs * gs
            top = r_top // gs * gs
            pen_minor = QPen(QColor(*GRID_COLOR), 1)
            pen_major = QPen(QColor(*GRID_MAJOR_COLOR), 1)
            for x in range(left, r_right + gs, gs):
                is_major = x // gs % GRID_MAJOR_INTERVAL == 0
                painter.setPen(pen_major if is_major else pen_minor)
                painter.drawLine(x, r_top, x, r_bottom)
            for y in range(top, r_bottom + gs, gs):
                is_major = y // gs % GRID_MAJOR_INTERVAL == 0
                painter.setPen(pen_major if is_major else pen_minor)
                painter.drawLine(r_left, y, r_right, y)
        except Exception as e:
            logger.exception(f'Error in drawBackground: {e}')

    def drawForeground(self, painter: QPainter, rect: QRectF):
        try:
            if self._bond_start_id is not None and self.tool_mode == 'edit':
                start_atom = self.mol.get_atom(self._bond_start_id)
                if start_atom:
                    pen = QPen(QColor(120, 180, 255), 1, Qt.PenStyle.DashLine)
                    painter.setPen(pen)
                    painter.drawLine(int(start_atom.x), int(start_atom.y), int(self._last_mouse_world.x()),
                                     int(self._last_mouse_world.y()))
                    ideal = int(BOND_IDEAL_LENGTH)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(int(start_atom.x) - ideal, int(start_atom.y) - ideal, ideal * 2, ideal * 2)
                else:
                    logger.warning(f'drawForeground: bond_start_id={self._bond_start_id} atom not found')
            if self._pending_structure is not None:
                self._draw_ghost_structure(painter)
            if self._chain_dragging and self._chain_preview:
                self._draw_chain_preview(painter)
        except Exception as e:
            logger.exception(f'Error in drawForeground: {e}')

    def _draw_chain_preview(self, painter: QPainter):
        try:
            r = max(RADIUS.get(self.selected_element, 12) * 0.6, 6)
            pen = QPen(QColor(120, 200, 255, 200), 2.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            px, py = self._chain_start_pos.x(), self._chain_start_pos.y()
            for (x, y) in self._chain_preview:
                painter.drawLine(int(px), int(py), int(x), int(y))
                px, py = x, y
            painter.setBrush(QBrush(QColor(120, 200, 255, 70)))
            painter.setPen(QPen(QColor(160, 220, 255, 200), 1))
            for (x, y) in self._chain_preview:
                painter.drawEllipse(QPointF(x, y), r, r)
        except Exception as e:
            logger.exception(f'Error in _draw_chain_preview: {e}')

    def _draw_ghost_structure(self, painter: QPainter):
        try:
            cx, cy = self._last_mouse_world.x(), self._last_mouse_world.y()
            scale = BOND_IDEAL_LENGTH / RDKIT_2D_BOND_LENGTH
            atoms = self._pending_structure['atoms']
            bonds = self._pending_structure['bonds']
            positions = [(cx + ax * scale, cy + ay * scale) for ax, ay, _el, _fc in atoms]
            bond_pen = QPen(QColor(120, 200, 255, 170), 2, Qt.PenStyle.DashLine)
            painter.setPen(bond_pen)
            for i1, i2, _btype in bonds:
                if 0 <= i1 < len(positions) and 0 <= i2 < len(positions):
                    x1, y1 = positions[i1]
                    x2, y2 = positions[i2]
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            painter.setBrush(QBrush(QColor(120, 200, 255, 70)))
            painter.setPen(QPen(QColor(160, 220, 255, 200), 1))
            for (x, y), (_ax, _ay, element, _fc) in zip(positions, atoms):
                r = max(RADIUS.get(element, 12) * 0.6, 6)
                painter.drawEllipse(QPointF(x, y), r, r)
        except Exception as e:
            logger.exception(f'Error in _draw_ghost_structure: {e}')

    def _update_transform(self):
        try:
            self.resetTransform()
            self.scale(self._zoom, self._zoom)
            self.centerOn(self._camera_x, self._camera_y)
        except Exception as e:
            logger.exception(f"CanvasView update_transform error: {e}")

    def set_zoom(self, zoom: float):
        try:
            self._zoom = max(0.15, min(zoom, 4.0))
            self._update_transform()
        except Exception as e:
            logger.exception(f"CanvasView set_zoom error: {e}")

    def get_zoom(self) -> float:
        return self._zoom

    def set_camera(self, x: float, y: float):
        try:
            self._camera_x = x
            self._camera_y = y
            self._update_transform()
        except Exception as e:
            logger.exception(f"CanvasView set_camera error: {e}")

    def get_camera(self) -> Tuple[float, float]:
        return self._camera_x, self._camera_y

    def reset_view(self):
        try:
            self._zoom = 1.0
            if self.mol.atoms:
                cx, cy = self.mol.center()
                self._camera_x = cx
                self._camera_y = cy
                logger.info(f'reset_view centered on molecule: ({cx:.1f},{cy:.1f})')
            else:
                self._camera_x = CANVAS_W / 2
                self._camera_y = WINDOW_H / 2
                logger.info(f'reset_view centered on default: ({self._camera_x:.1f},{self._camera_y:.1f})')
            self._update_transform()
        except Exception as e:
            logger.exception(f"CanvasView reset_view error: {e}")

    def center_molecule(self):
        try:
            if self.mol.atoms:
                cx, cy = self.mol.center()
                self._camera_x = cx
                self._camera_y = cy
                logger.info(f'center_molecule: ({cx:.1f},{cy:.1f})')
                self._update_transform()
            else:
                logger.warning('center_molecule: no atoms to center')
        except Exception as e:
            logger.exception(f"CanvasView center_molecule error: {e}")

    def screen_to_world(self, pos: QPoint) -> QPointF:
        try:
            return self.mapToScene(pos)
        except Exception as e:
            logger.exception(f"CanvasView screen_to_world error: {e}")
            return QPointF(0, 0)

    def mousePressEvent(self, event: QMouseEvent):
        try:
            if self._handle_mouse_press(event):
                event.accept()
            else:
                super().mousePressEvent(event)
        except Exception as e:
            logger.exception(f'Error in mousePressEvent: {e}')

    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Return True if we fully handled the event (super must NOT be called)."""
        pos = self.screen_to_world(event.pos())
        wx, wy = pos.x(), pos.y()
        if self._pending_structure is not None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.structure_about_to_place.emit()
                self._commit_structure_placement(wx, wy)
            else:
                self.cancel_structure_placement()
            return True
        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_pan(event)
            return True
        if self.tool_mode == 'select':
            self._handle_select_press(event, pos, wx, wy)
            return True
        elif self.tool_mode == 'edit':
            self._handle_edit_press(event, pos, wx, wy)
            return True
        elif self.tool_mode == 'delete':
            self._handle_delete_press(pos)
            return True
        logger.warning(f'_handle_mouse_press: unhandled tool_mode={self.tool_mode}')
        return False

    def _start_pan(self, event: QMouseEvent):
        self._panning = True
        self._last_pan_pos = event.pos()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        logger.info(f'_start_pan: pos=({event.pos().x()},{event.pos().y()})')

    def _handle_select_press(self, event: QMouseEvent, pos: QPointF, wx: float, wy: float):
        """Always fully handles the click (select-mode clicks never fall
        through to default Qt behavior) — no meaningful return value."""
        if event.button() == Qt.MouseButton.RightButton:
            self._select_drag_mode = SelectDragMode.MARQUEE
            self._drag_start = QPointF(wx, wy)
            self.scene.start_marquee(QPointF(wx, wy))
            self.scene.set_selected_atoms(set())
            self.selection_changed.emit()
            return
        atom = self.scene.hit_atom(pos)
        if atom is None:
            self._select_drag_mode = SelectDragMode.EMPTY
            self.scene.set_selected_atoms(set())
            self.selection_changed.emit()
            return
        self._select_atom_with_modifiers(atom, event.modifiers())
        self._start_drag(wx, wy)

    def _start_marquee(self, wx: float, wy: float):
        self._select_drag_mode = SelectDragMode.MARQUEE
        self._drag_start = QPointF(wx, wy)
        self.scene.start_marquee(QPointF(wx, wy))
        self.scene.set_selected_atoms(set())
        self.selection_changed.emit()

    def _select_atom_with_modifiers(self, atom: Atom, modifiers):
        selected = self.scene.get_selected_atoms()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._toggle_atom_selection(atom, selected)
        else:
            self._set_single_selection(atom, selected)
        self.scene.set_selected_atoms(selected)
        self.selection_changed.emit()

    @staticmethod
    def _toggle_atom_selection(atom: Atom, selected: Set[int]):
        if atom.id in selected:
            logger.info(f'_toggle_atom_selection: removing atom {atom.id}')
            selected.remove(atom.id)
        else:
            logger.info(f'_toggle_atom_selection: adding atom {atom.id}')
            selected.add(atom.id)

    @staticmethod
    def _set_single_selection(atom: Atom, selected: Set[int]):
        if atom.id not in selected or len(selected) > 1:
            logger.info(f'_set_single_selection: clearing {len(selected)} atoms, selecting {atom.id}')
            selected.clear()
            selected.add(atom.id)

    def _start_drag(self, wx: float, wy: float):
        self._select_drag_mode = SelectDragMode.ATOMS
        self._drag_undo_pushed = False
        self._drag_offsets = {}
        selected = self.scene.get_selected_atoms()
        for aid in selected:
            a = self.mol.get_atom(aid)
            if a:
                self._drag_offsets[aid] = (a.x - wx, a.y - wy)

    def _handle_edit_press(self, event: QMouseEvent, pos: QPointF, wx: float, wy: float):
        """Always fully handles the click (edit-mode clicks never fall
        through to default Qt behavior) — no meaningful return value."""
        if self._chain_active and event.button() == Qt.MouseButton.LeftButton:
            self._start_chain_drag(pos)
            return
        if self._formal_charge_sign is not None:
            if event.button() == Qt.MouseButton.LeftButton:
                atom = self.scene.hit_atom(pos)
                if atom:
                    self._apply_formal_charge_click(atom)
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._start_bond_drawing(pos)
            self._edit_click_candidate = None
            return
        atom = self.scene.hit_atom(pos)
        if atom:
            self._edit_click_candidate = atom
            self._edit_click_pos = QPointF(wx, wy)
        else:
            self._edit_click_candidate = None
            self._add_new_atom(wx, wy)

    def _start_chain_drag(self, pos: QPointF):
        """Begin a chain drag. If pos lands on an existing atom, the chain
        grows from (and will smart-bond to) that atom; otherwise it grows
        from a free point and the first atom is created fresh on release."""
        try:
            atom = self.scene.hit_atom(pos)
            self._chain_start_id = atom.id if atom else None
            self._chain_start_pos = QPointF(atom.x, atom.y) if atom else QPointF(pos)
            self._chain_preview = []
            self._chain_dragging = True
            self.viewport().update()
        except Exception as e:
            logger.exception(f"CanvasView _start_chain_drag error: {e}")

    def _update_chain_preview(self, wx: float, wy: float):
        try:
            self._chain_preview = compute_chain_zigzag(
                self._chain_start_pos.x(), self._chain_start_pos.y(), wx, wy)
        except Exception as e:
            logger.exception(f"CanvasView _update_chain_preview error: {e}")

    def _commit_chain_drag(self):
        """Turn the live chain preview into real atoms/bonds. Each
        consecutive pair gets the currently-selected bond type (so the
        chain tool respects single/double/triple/aromatic the same way
        normal bond-drawing does). If the drag started on an existing atom,
        the new chain bonds to it; if it started on empty canvas, the first
        preview position becomes a fresh atom with no incoming bond.

        For the common case — plain carbon chain, single bonds — each new
        carbon also gets its hydrogens attached immediately (not deferred to
        Clean Up), since a drawn skeletal chain should look like the
        complete saturated alkane it represents the moment you let go. Any
        other element or bond type skips this (their valence isn't a flat
        "fill with H" rule), leaving normal Clean Up as the way to add H's."""
        try:
            self._chain_dragging = False
            positions = self._chain_preview
            self._chain_preview = []
            self.viewport().update()
            if not positions:
                return
            self.chain_about_to_build.emit()  # undo push happens BEFORE mutation
            prev_id = self._chain_start_id
            backbone_ids = []
            if prev_id is not None:
                backbone_ids.append(prev_id)
            for (x, y) in positions:
                new_atom = self.mol.add_atom(x, y, self.selected_element)
                backbone_ids.append(new_atom.id)
                if prev_id is not None:
                    if self.mol.can_bond(prev_id, new_atom.id, self.bond_mode):
                        self.mol.add_bond(prev_id, new_atom.id, self.bond_mode)
                prev_id = new_atom.id
            if self.selected_element == 'C' and self.bond_mode == 'S':
                self._attach_chain_hydrogens(backbone_ids, started_on_existing_atom=self._chain_start_id is not None)
            self.scene.rebuild()
            self.chain_built.emit()
            logger.info(f'_commit_chain_drag: built chain of {len(positions)} atom(s)')
        except Exception as e:
            logger.exception(f"CanvasView _commit_chain_drag error: {e}")

    def _attach_chain_hydrogens(self, backbone_ids: list, started_on_existing_atom: bool):
        """Add explicit H atoms to fill each new chain carbon's remaining
        valence, positioned via compute_chain_hydrogens's geometric pattern
        (3 H's splayed off a terminal carbon, 2 off an internal one) but
        capped by that atom's actual free_valence — so a chain started from
        an atom that already has other bonds only gets as many H's as it
        chemically has room for, instead of blindly assuming it's a fresh
        terminal carbon."""
        try:
            backbone_positions = [(self.mol.get_atom(aid).x, self.mol.get_atom(aid).y) for aid in backbone_ids]
            if any(p is None for p in backbone_positions):
                return
            if len(backbone_positions) == 1 and not started_on_existing_atom:
                # Degenerate case: a single fresh carbon with no backbone
                # neighbor to react against (e.g. the smallest possible
                # chain drag — one lone methane carbon). Splay 4 H's evenly
                # around it instead, using the drag axis as a reference
                # direction so it isn't an arbitrary fixed orientation.
                cx, cy = backbone_positions[0]
                ax, ay = self._chain_start_pos.x(), self._chain_start_pos.y()
                dx, dy = cx - ax, cy - ay
                d = math.hypot(dx, dy)
                ux, uy = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
                carbon_id = backbone_ids[0]
                room = int(self.mol.free_valence(carbon_id))
                for k in range(min(4, room)):
                    angle = math.atan2(uy, ux) + math.radians(45 + 90 * k)
                    hx = cx + math.cos(angle) * self._chain_h_bond_length()
                    hy = cy + math.sin(angle) * self._chain_h_bond_length()
                    h_atom = self.mol.add_atom(hx, hy, 'H')
                    self.mol.add_bond(carbon_id, h_atom.id, 'S')
                return
            h_slots = compute_chain_hydrogens(backbone_positions, skip_first=started_on_existing_atom)
            slots_by_index: Dict[int, list] = {}
            for (hx, hy, idx) in h_slots:
                slots_by_index.setdefault(idx, []).append((hx, hy))
            for idx, slots in slots_by_index.items():
                carbon_id = backbone_ids[idx]
                room = int(self.mol.free_valence(carbon_id))
                for (hx, hy) in slots[:room]:
                    h_atom = self.mol.add_atom(hx, hy, 'H')
                    self.mol.add_bond(carbon_id, h_atom.id, 'S')
        except Exception as e:
            logger.exception(f"CanvasView _attach_chain_hydrogens error: {e}")

    @staticmethod
    def _chain_h_bond_length() -> float:
        return CHAIN_SEGMENT_LENGTH

    def _start_bond_drawing(self, pos: QPointF):
        atom = self.scene.hit_atom(pos)
        if atom:
            self._bond_start_id = atom.id
            self.viewport().update()

    def _add_new_atom(self, wx: float, wy: float):
        sx, sy = self._snap_to_grid(wx, wy)
        nearest, min_dist = self._find_nearest_atom(sx, sy)
        if nearest and min_dist < 100:
            sx, sy = self._calculate_smart_join_position(nearest, sx, sy)
        self.mutation_about_to_apply.emit()  # undo push BEFORE mutation, matching delete's ordering
        new_atom = self.mol.add_atom(sx, sy, self.selected_element)
        if nearest and min_dist < 100 and self._smart_join:
            self._try_smart_bond(nearest, new_atom)
        self.scene.rebuild()
        self.atom_added.emit()

    def _find_nearest_atom(self, sx: float, sy: float):
        if not self._smart_join:
            return None, float('inf')
        nearest = None
        min_dist = float('inf')
        for a in self.mol.atoms:
            d = math.hypot(a.x - sx, a.y - sy)
            if d < min_dist:
                min_dist = d
                nearest = a
        return nearest, min_dist

    def _calculate_smart_join_position(self, nearest: Atom, sx: float, sy: float):
        dx, dy = sx - nearest.x, sy - nearest.y
        d = math.hypot(dx, dy) or 1
        ideal = BOND_IDEAL_LENGTH
        new_x = nearest.x + dx / d * ideal
        new_y = nearest.y + dy / d * ideal
        return self._snap_to_grid(new_x, new_y)

    def _try_smart_bond(self, nearest: Atom, new_atom: Atom):
        can = self.mol.can_bond(nearest.id, new_atom.id, self.bond_mode)
        if can:
            self.mol.add_bond(nearest.id, new_atom.id, self.bond_mode)

    def _handle_delete_press(self, pos: QPointF):
        """Begin a delete-drag gesture: erase whatever's under the initial
        click, then keep erasing anything the cursor passes over until
        release (see _handle_mouse_move / _erase_at)."""
        self._delete_dragging = True
        self._delete_drag_undo_pushed = False
        self._erase_at(pos)

    def _erase_at(self, pos: QPointF):
        """Delete whatever atom or bond is at `pos`, if anything. Pushes one
        undo snapshot the FIRST time this fires within the current drag
        gesture (atoms_deleted), then just keeps the info panel/status bar
        live for every subsequent hit in the same gesture (atom_erased)."""
        atom = self.scene.hit_atom(pos)
        if atom:
            self._push_delete_undo_once()
            self.mol.remove_atom(atom.id)
            self.scene.rebuild()
            self.selection_changed.emit()
            self.atom_erased.emit()
            return
        bidx = self.scene.hit_bond(pos)
        if bidx is not None:
            self._push_delete_undo_once()
            self.mol.remove_bond(bidx)
            self.scene.rebuild()
            self.selection_changed.emit()
            self.atom_erased.emit()

    def _push_delete_undo_once(self):
        if not self._delete_drag_undo_pushed:
            self._delete_drag_undo_pushed = True
            self.atoms_deleted.emit()

    def mouseMoveEvent(self, event: QMouseEvent):
        try:
            self._handle_mouse_move(event)
        except Exception as e:
            logger.exception(f'Error in mouseMoveEvent: {e}')

    def _handle_mouse_move(self, event: QMouseEvent):
        if self.tool_mode == 'edit' and self._edit_click_candidate is not None and (
                self._select_drag_mode == SelectDragMode.NONE):
            pos = self.screen_to_world(event.pos())
            moved = math.hypot(pos.x() - self._edit_click_pos.x(), pos.y() - self._edit_click_pos.y())
            if moved >= self._edit_click_threshold:
                self._edit_click_candidate = None
        if self._select_drag_mode in (SelectDragMode.EMPTY, SelectDragMode.MARQUEE):
            if self._select_drag_mode == SelectDragMode.MARQUEE:
                pos = self.screen_to_world(event.pos())
                self.scene.update_marquee(QPointF(pos.x(), pos.y()))
            return
        pos = self.screen_to_world(event.pos())
        wx, wy = pos.x(), pos.y()
        if self._panning:
            self._update_pan(event)
            self._last_mouse_world = QPointF(wx, wy)
            self.mouse_moved.emit(wx, wy)
            return
        if self._select_drag_mode == SelectDragMode.ATOMS and self.tool_mode == 'select':
            self._update_drag_selection(wx, wy)
            self._last_mouse_world = QPointF(wx, wy)
            self.mouse_moved.emit(wx, wy)
            return
        self._last_mouse_world = QPointF(wx, wy)
        self.mouse_moved.emit(wx, wy)
        if self._chain_dragging and self.tool_mode == 'edit':
            self._update_chain_preview(wx, wy)
        if self._delete_dragging and self.tool_mode == 'delete':
            self._erase_at(pos)
        self.viewport().update()
        super().mouseMoveEvent(event)

    def _update_pan(self, event: QMouseEvent):
        delta = event.pos() - self._last_pan_pos
        self._camera_x -= delta.x() / self._zoom
        self._camera_y -= delta.y() / self._zoom
        self._last_pan_pos = event.pos()
        self._update_transform()

    def _update_drag_selection(self, wx: float, wy: float):
        if not self._drag_undo_pushed:
            self._drag_undo_pushed = True
            self.drag_started.emit()
        selected = self.scene.get_selected_atoms()
        for aid in selected:
            self._move_atom_by_offset(aid, wx, wy)
        self.scene.update_atom_positions()
        self.atoms_moved.emit()

    def _move_atom_by_offset(self, aid: int, wx: float, wy: float):
        a = self.mol.get_atom(aid)
        if a is None or aid not in self._drag_offsets:
            logger.warning(f'_move_atom_by_offset: atom {aid} not found or no offset')
            return
        offx, offy = self._drag_offsets[aid]
        nx, ny = wx + offx, wy + offy
        if self._snap_enabled:
            nx, ny = self._snap_to_grid(nx, ny)
        a.x = nx
        a.y = ny

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            pos = self.screen_to_world(event.pos())
            handled = any([
                self._release_pan(event),
                self._release_marquee_selection(),
                self._release_atom_drag(),
                self._release_edit_click_candidate(),
                self._release_empty_select_drag(),
                self._release_bond_drawing(pos),
                self._release_chain_drag(),
                self._release_delete_drag(),
            ])
            if handled:
                event.accept()
            else:
                super().mouseReleaseEvent(event)
        except Exception as e:
            logger.exception(f'Error in mouseReleaseEvent: {e}')

    def _release_pan(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.MiddleButton:
            return False
        self._panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return True

    def _release_marquee_selection(self) -> bool:
        if self._select_drag_mode != SelectDragMode.MARQUEE:
            return False
        self._select_drag_mode = SelectDragMode.NONE
        selected = self.scene.end_marquee()
        self.scene.set_selected_atoms(selected)
        self.selection_changed.emit()
        return True

    def _release_atom_drag(self) -> bool:
        if self._select_drag_mode != SelectDragMode.ATOMS:
            return False
        self._select_drag_mode = SelectDragMode.NONE
        self._drag_offsets.clear()
        self._drag_undo_pushed = False
        return True

    def _release_edit_click_candidate(self) -> bool:
        if self.tool_mode != 'edit' or self._edit_click_candidate is None:
            return False
        self._edit_click_candidate = None
        return True

    def _release_empty_select_drag(self) -> bool:
        if self._select_drag_mode != SelectDragMode.EMPTY:
            return False
        self._select_drag_mode = SelectDragMode.NONE
        return True

    def _release_bond_drawing(self, pos: QPointF) -> bool:
        if self._bond_start_id is None or self.tool_mode != 'edit':
            return False
        atom = self.scene.hit_atom(pos)
        if atom and atom.id != self._bond_start_id and self.mol.can_bond(self._bond_start_id, atom.id, self.bond_mode):
            self.mutation_about_to_apply.emit()  # undo push BEFORE mutation
            self.mol.add_bond(self._bond_start_id, atom.id, self.bond_mode)
            self.scene.rebuild()
            self.bond_added.emit()
        self._bond_start_id = None
        self.viewport().update()
        return True

    def _release_chain_drag(self) -> bool:
        if not self._chain_dragging:
            return False
        self._commit_chain_drag()
        return True

    def _release_delete_drag(self) -> bool:
        if not self._delete_dragging:
            return False
        self._delete_dragging = False
        self._delete_drag_undo_pushed = False
        return True

    def wheelEvent(self, event: QWheelEvent):
        try:
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12
            old_zoom = self._zoom
            new_zoom = max(0.15, min(self._zoom * factor, 4.0))
            mouse_pos = self.mapToScene(event.position().toPoint())
            mx, my = mouse_pos.x(), mouse_pos.y()
            self._camera_x = mx - (mx - self._camera_x) * (old_zoom / new_zoom)
            self._camera_y = my - (my - self._camera_y) * (old_zoom / new_zoom)
            self._zoom = new_zoom
            self._update_transform()
            event.accept()
        except Exception as e:
            logger.exception(f'Error in wheelEvent: {e}')

    def keyPressEvent(self, event: QKeyEvent):
        try:
            if event.key() == Qt.Key.Key_Escape and self._pending_structure is not None:
                self.cancel_structure_placement()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape and self._chain_dragging:
                self._chain_dragging = False
                self._chain_preview = []
                self._chain_start_id = None
                self.viewport().update()
                event.accept()
                return
            super().keyPressEvent(event)
        except Exception as e:
            logger.exception(f'Error in keyPressEvent: {e}')

    def get_selected_atoms(self) -> Set[int]:
        try:
            return self.scene.get_selected_atoms()
        except Exception as e:
            logger.exception(f"MoleculeScene get_selected_atoms error: {e}")
            return set()

    def delete_selected(self):
        self.atoms_deleted.emit()
        selected = self.scene.get_selected_atoms()
        for aid in selected:
            self.mol.remove_atom(aid)
        self.scene.set_selected_atoms(set())
        self.scene.rebuild()
        self.selection_changed.emit()

    def select_all(self):
        self.scene.set_selected_atoms({a.id for a in self.mol.atoms})
        self.selection_changed.emit()

    def set_selected_element(self, element: str):
        self.selected_element = element
        self._exit_formal_charge_mode()

    def set_bond_mode(self, mode: str):
        self.bond_mode = BOND_DISPLAY_TO_LETTER.get(mode, mode)

    def set_tool_mode(self, mode: str):
        if self.tool_mode == 'edit' and mode != 'edit' and self._bond_start_id is not None:
            self._bond_start_id = None
            self.viewport().update()
        if self.tool_mode == 'delete' and mode != 'delete' and self._delete_dragging:
            self._delete_dragging = False
            self._delete_drag_undo_pushed = False
        self._select_drag_mode = SelectDragMode.NONE
        self.tool_mode = mode
        self.setCursor(self._cursor_for_mode(mode))
        if mode != 'edit':
            self._exit_formal_charge_mode()
            self._exit_chain_mode()

    @staticmethod
    def _cursor_for_mode(mode: str) -> QCursor:
        if mode == 'delete':
            return CanvasView._eraser_cursor()
        cursors = {'select': Qt.CursorShape.ArrowCursor, 'edit': Qt.CursorShape.CrossCursor}
        return QCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor))

    _eraser_cursor_cache: Optional[QCursor] = None

    @staticmethod
    def _eraser_cursor() -> QCursor:
        """A small eraser-shaped custom cursor for Delete mode, replacing
        the generic 'forbidden' circle-slash so it actually reads as
        'erase' rather than 'you can't do that here'."""
        if CanvasView._eraser_cursor_cache is not None:
            return CanvasView._eraser_cursor_cache
        size = 28
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            body = QColor(235, 240, 250)
            edge = QColor(40, 46, 60)
            band = QColor(235, 110, 110)
            painter.setPen(QPen(edge, 1.5))
            painter.setBrush(QBrush(body))
            # Eraser body: a small rotated rounded rectangle.
            painter.translate(size / 2, size / 2)
            painter.rotate(-40)
            painter.drawRoundedRect(QRectF(-10, -6, 20, 12), 3, 3)
            painter.setBrush(QBrush(band))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(-10, -6, 7, 12))
        finally:
            painter.end()
        cursor = QCursor(pm, size // 2, size // 2)
        CanvasView._eraser_cursor_cache = cursor
        return cursor

    # ── Formal charge editing ──
    def set_formal_charge_sign(self, sign: Optional[str]):
        """Set (not toggle) the active formal-charge sign. The toolbar is the
        single source of truth for the toggle state; the canvas just mirrors
        it so atom clicks know what to apply. sign is '+', '-', or None/''."""
        try:
            self._formal_charge_sign = sign or None
            if self._formal_charge_sign is not None:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(self._cursor_for_mode(self.tool_mode))
        except Exception as e:
            logger.exception(f"CanvasView set_formal_charge_sign error: {e}")

    def _exit_formal_charge_mode(self):
        """Leave formal-charge mode without it being a direct button-toggle
        (used when the tool mode changes away from 'edit', or a new element
        is selected). Emits a signal so the toolbar can un-press its buttons."""
        if self._formal_charge_sign is not None:
            self._formal_charge_sign = None
            self.formal_charge_mode_exited.emit()

    def _exit_chain_mode(self):
        """Leave chain mode without it being a direct button-toggle (used
        when the tool mode changes away from 'edit'). Emits a signal so the
        toolbar can un-press the chain button."""
        if self._chain_active:
            self._chain_active = False
            self._chain_start_id = None
            self._chain_preview = []
            self.chain_mode_exited.emit()

    @property
    def formal_charge_active(self) -> Optional[str]:
        return self._formal_charge_sign

    # ── Chain tool ──
    def set_chain_active(self, active: bool):
        """Toggle the chain-build tool on/off. The toolbar button is the
        single source of truth (same pattern as set_formal_charge_sign);
        the canvas just mirrors it so mouse events know what to do."""
        try:
            self._chain_active = active
            if not active:
                self._chain_start_id = None
                self._chain_preview = []
                self.viewport().update()
            self.setCursor(self._cursor_for_mode(self.tool_mode))
        except Exception as e:
            logger.exception(f"CanvasView set_chain_active error: {e}")

    @property
    def chain_active(self) -> bool:
        return self._chain_active

    def _apply_formal_charge_click(self, atom: Atom):
        """Apply the active +/- formal-charge delta to the clicked atom, if
        the resulting charge is chemically valid; otherwise reject with a
        reason the caller can surface to the user."""
        try:
            delta = 1 if self._formal_charge_sign == '+' else -1
            new_charge = atom.formal_charge + delta
            allowed, reason = self.mol.can_set_formal_charge(atom.id, new_charge)
            if not allowed:
                self.formal_charge_rejected.emit(reason)
                return
            self.mutation_about_to_apply.emit()  # undo push BEFORE mutation
            atom.formal_charge = new_charge
            self.scene.rebuild()
            self.formal_charge_changed.emit()
        except Exception as e:
            logger.exception(f"CanvasView _apply_formal_charge_click error: {e}")

    # ── Selection transforms (rotate / flip) ──
    def _transform_target_ids(self) -> set:
        """Atoms to transform: the current selection, or — if nothing is
        selected — every atom on the canvas. Rotating/flipping the whole
        structure when nothing is selected matches how a single drawn
        fragment is normally reoriented (no need to marquee-select
        everything first); once there are multiple fragments, selecting one
        scopes the transform to just that piece."""
        selected = self.scene.get_selected_atoms()
        if selected:
            return selected
        return {a.id for a in self.mol.atoms}

    def rotate_selection(self, degrees: float):
        try:
            ids = self._transform_target_ids()
            if not ids:
                self.selection_empty_for_transform.emit()
                return
            self.transform_about_to_apply.emit()
            self.mol.rotate_atoms(ids, degrees)
            self.scene.rebuild()
            self.transform_applied.emit()
        except Exception as e:
            logger.exception(f"CanvasView rotate_selection error: {e}")

    def flip_selection(self, axis: str = 'horizontal'):
        try:
            ids = self._transform_target_ids()
            if not ids:
                self.selection_empty_for_transform.emit()
                return
            self.transform_about_to_apply.emit()
            self.mol.flip_atoms(ids, axis)
            self.scene.rebuild()
            self.transform_applied.emit()
        except Exception as e:
            logger.exception(f"CanvasView flip_selection error: {e}")

    def get_mouse_world_pos(self) -> QPointF:
        """Return world coordinates under mouse cursor, or last known if outside."""
        if not self.underMouse():
            return self._last_mouse_world
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        return self.mapToScene(local_pos)

    # ── Structure placement (ghost preview) ──
    def begin_structure_placement(self, atoms: list, bonds: list, name: str = ''):
        """Enter ghost-placement mode. atoms: [(x, y, element, formal_charge)]
        centered at origin. bonds: [(idx1, idx2, bond_type)] indices into atoms.
        Click on canvas to commit, Escape or right-click to cancel."""
        try:
            self._pending_structure = {'atoms': atoms, 'bonds': bonds, 'name': name}
            # The click that triggered this came from the side panel, not the canvas,
            # so _last_mouse_world may be stale (or still the (0,0) default). Sync it
            # to the real current cursor position so the ghost doesn't jump to origin.
            self._last_mouse_world = self.get_mouse_world_pos()
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.viewport().update()
        except Exception as e:
            logger.exception(f'Error in begin_structure_placement: {e}')

    def cancel_structure_placement(self):
        try:
            if self._pending_structure is not None:
                self._pending_structure = None
                self.set_tool_mode(self.tool_mode)
                self.viewport().update()
        except Exception as e:
            logger.exception(f'Error in cancel_structure_placement: {e}')

    def is_placing_structure(self) -> bool:
        return self._pending_structure is not None

    def _commit_structure_placement(self, wx: float, wy: float):
        try:
            pending = self._pending_structure
            if pending is None:
                return
            scale = BOND_IDEAL_LENGTH / RDKIT_2D_BOND_LENGTH
            atoms = pending['atoms']
            bonds = pending['bonds']
            sx, sy = self._snap_to_grid(wx, wy)
            local_id_map: Dict[int, int] = {}
            for idx, (ax, ay, element, formal_charge) in enumerate(atoms):
                new_atom = self.mol.add_atom(sx + ax * scale, sy + ay * scale, element,
                                             formal_charge=formal_charge)
                local_id_map[idx] = new_atom.id
            for i1, i2, btype in bonds:
                if i1 in local_id_map and i2 in local_id_map:
                    self.mol.add_bond(local_id_map[i1], local_id_map[i2], btype)
            self.scene.rebuild()
            self.structure_placed.emit()
            logger.info(f"Placed structure '{pending.get('name', '')}' with {len(atoms)} atoms at ({sx:.1f},{sy:.1f})")
        except Exception as e:
            logger.exception(f'Error in _commit_structure_placement: {e}')
