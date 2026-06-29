"""QGraphicsView with all molecule interaction logic."""

import logging
import math
from enum import Enum, auto
from typing import Optional, Set, Dict, Tuple

from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QSizeF, QMarginsF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QKeyEvent, QMouseEvent, QWheelEvent, QCursor, QPixmap, \
    QPdfWriter, QImage, QPageSize
from PyQt6.QtWidgets import QGraphicsView

from action_toolbar import BondMenu
from commands import (
    AddAtomCommand, RemoveAtomCommand, AddBondCommand, RemoveBondCommand,
    MoveAtomsCommand, RotateAtomsCommand, FlipAtomsCommand,
    ChangeBondTypeCommand, SetFormalChargeCommand
)
from config import (
    RADIUS, CANVAS_W, WINDOW_H, GRID_SIZE, GRID_COLOR, GRID_MAJOR_COLOR,
    GRID_MAJOR_INTERVAL, BOND_IDEAL_LENGTH, BOND_DISPLAY_TO_LETTER, BOND_LETTER_TO_DISPLAY,
    RDKIT_2D_BOND_LENGTH, CHAIN_SEGMENT_LENGTH, BOND_TYPES, NUDGE_STEP, NUDGE_STEP_SHIFT_MULTIPLIER
)
from models import Molecule, Atom
from scene import MoleculeScene
from undo import UndoManager
from utils import compute_chain_zigzag, compute_chain_hydrogens

logger = logging.getLogger(__name__)


class SelectDragMode(Enum):
    NONE = auto()
    ATOMS = auto()
    MARQUEE = auto()
    EMPTY = auto()


class CanvasView(QGraphicsView):
    atoms_moved = pyqtSignal()
    atom_added = pyqtSignal()
    bond_added = pyqtSignal()
    selection_changed = pyqtSignal()
    mouse_moved = pyqtSignal(float, float)
    zoom_changed = pyqtSignal(float)
    atoms_deleted = pyqtSignal()
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
    bond_type_change_about_to_apply = pyqtSignal()
    bond_type_changed = pyqtSignal()
    bond_type_change_rejected = pyqtSignal(str)

    def __init__(self, mol: Molecule, undo_manager: UndoManager, parent=None):
        super().__init__(parent)
        self.mol = mol
        self.undo_manager = undo_manager
        self.scene = MoleculeScene(mol, self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(6, 12, 22)))
        self.setMinimumSize(400, 400)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.tool_mode = 'select'
        self.selected_element = 'C'
        self.bond_mode = 'S'
        self._marquee_mode = 'rectangle'  # new: 'rectangle', 'lasso', 'ellipse'
        self._zoom = 1.0
        self._camera_x = 0.0
        self._camera_y = 0.0
        self._drag_start = QPointF()
        self._drag_offsets: Dict[int, Tuple[float, float]] = {}
        self._drag_undo_pushed = False
        self._drag_start_positions: Dict[int, Tuple[float, float]] = {}
        self._bond_start_id: Optional[int] = None
        self._panning = False
        self._last_pan_pos = QPoint()
        self._select_drag_mode = SelectDragMode.NONE
        self._edit_click_candidate: Optional[Atom] = None
        self._edit_click_pos: QPointF = QPointF(0, 0)
        self._edit_click_threshold = 6
        self._show_grid = True
        self._snap_enabled = False
        self._last_mouse_pos = None
        self._smart_join = True
        self._last_mouse_world = QPointF(0, 0)
        self._pending_structure: Optional[dict] = None
        self._clipboard: Optional[dict] = None
        self._formal_charge_sign: Optional[str] = None
        self._chain_active = False
        self._chain_dragging = False
        self._chain_start_id: Optional[int] = None
        self._chain_start_pos: QPointF = QPointF(0, 0)
        self._chain_preview: list = []
        self._delete_dragging = False
        self._delete_drag_undo_pushed = False
        self._space_held = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._bond_menu = BondMenu(self)
        self._bond_menu.bond_type_selected.connect(self._apply_bond_menu_choice)
        self._bond_menu_target_index: Optional[int] = None
        self._update_transform()

    def set_marquee_mode(self, mode: str):
        self._marquee_mode = mode

    # ---- grid and snap ----
    def set_grid_visible(self, visible: bool):
        self._show_grid = visible
        self.viewport().update()

    def set_snap_enabled(self, enabled: bool):
        self._snap_enabled = enabled

    def set_smart_join(self, enabled: bool):
        self._smart_join = enabled

    def _snap_to_grid(self, x: float, y: float) -> Tuple[float, float]:
        if not self._snap_enabled:
            return x, y
        gs = GRID_SIZE
        return round(x / gs) * gs, round(y / gs) * gs

    # ---- painting ----
    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, QColor(6, 12, 22))
        if not self._show_grid or self._zoom < 0.2:
            return
        gs = GRID_SIZE
        left = int(rect.left()) // gs * gs
        top = int(rect.top()) // gs * gs
        pen_minor = QPen(QColor(*GRID_COLOR), 1)
        pen_major = QPen(QColor(*GRID_MAJOR_COLOR), 1)
        for x in range(left, int(rect.right()) + gs, gs):
            is_major = (x // gs) % GRID_MAJOR_INTERVAL == 0
            painter.setPen(pen_major if is_major else pen_minor)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()) + gs, gs):
            is_major = (y // gs) % GRID_MAJOR_INTERVAL == 0
            painter.setPen(pen_major if is_major else pen_minor)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    def drawForeground(self, painter: QPainter, rect: QRectF):
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
        if self._pending_structure is not None:
            self._draw_ghost_structure(painter)
        if self._chain_dragging and self._chain_preview:
            self._draw_chain_preview(painter)

    def _draw_chain_preview(self, painter: QPainter):
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

    def _draw_ghost_structure(self, painter: QPainter):
        cx, cy = self._last_mouse_world.x(), self._last_mouse_world.y()
        scale = self._pending_structure.get('scale', BOND_IDEAL_LENGTH / RDKIT_2D_BOND_LENGTH)
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

    # ---- transform helpers ----
    def _update_transform(self):
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self.centerOn(self._camera_x, self._camera_y)

    def set_zoom(self, zoom: float):
        self._zoom = max(0.15, min(zoom, 4.0))
        self._update_transform()
        self.zoom_changed.emit(self._zoom)

    def get_zoom(self) -> float:
        return self._zoom

    def set_camera(self, x: float, y: float):
        self._camera_x = x
        self._camera_y = y
        self._update_transform()

    def get_camera(self) -> Tuple[float, float]:
        return self._camera_x, self._camera_y

    def reset_view(self):
        self._zoom = 1.0
        if self.mol.atoms:
            cx, cy = self.mol.center()
            self._camera_x = cx
            self._camera_y = cy
        else:
            self._camera_x = CANVAS_W / 2
            self._camera_y = WINDOW_H / 2
        self._update_transform()
        self.zoom_changed.emit(self._zoom)

    def center_molecule(self):
        if self.mol.atoms:
            cx, cy = self.mol.center()
            self._camera_x = cx
            self._camera_y = cy
            self._update_transform()

    # ---- export ----
    EXPORT_MARGIN = 24

    def _export_rect(self) -> QRectF:
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            rect = QRectF(-50, -50, 100, 100)
        m = self.EXPORT_MARGIN
        return rect.adjusted(-m, -m, m, m)

    def export_image(self, path: str, fmt: str, transparent: bool = True, scale: float = 2.0):
        fmt = fmt.lower()
        export_rect = self._export_rect()
        prev_atoms = self.scene.get_selected_atoms()
        prev_bonds = self.scene.get_selected_bonds()
        if prev_atoms or prev_bonds:
            self.scene.set_selected_atoms(set())
        try:
            if fmt == 'png':
                self._export_png(path, export_rect, transparent, scale)
            elif fmt == 'svg':
                self._export_svg(path, export_rect)
            elif fmt == 'pdf':
                self._export_pdf(path, export_rect)
            else:
                raise ValueError(f'Unsupported export format: {fmt}')
        finally:
            if prev_atoms or prev_bonds:
                self.scene.set_selected_atoms(prev_atoms)

    def _export_png(self, path: str, rect: QRectF, transparent: bool, scale: float):
        w = max(1, int(rect.width() * scale))
        h = max(1, int(rect.height() * scale))
        image = QImage(w, h, QImage.Format.Format_ARGB32)
        if transparent:
            image.fill(Qt.GlobalColor.transparent)
        else:
            image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, QRectF(0, 0, w, h), rect)
        painter.end()
        if not image.save(path, 'PNG'):
            raise IOError(f'Failed to write PNG to {path}')

    def _export_svg(self, path: str, rect: QRectF):
        from PyQt6.QtSvg import QSvgGenerator
        generator = QSvgGenerator()
        generator.setFileName(path)
        size = rect.size().toSize()
        generator.setSize(size)
        generator.setViewBox(QRectF(0, 0, size.width(), size.height()))
        generator.setTitle('Carbon Simulator export')
        painter = QPainter(generator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, QRectF(0, 0, size.width(), size.height()), rect)
        painter.end()

    def _export_pdf(self, path: str, rect: QRectF):
        writer = QPdfWriter(path)
        dpi = 150
        writer.setResolution(dpi)
        width_mm = rect.width() / dpi * 25.4
        height_mm = rect.height() / dpi * 25.4
        page_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter)
        writer.setPageSize(page_size)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        painter = QPainter(writer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        target = QRectF(0, 0, writer.width(), writer.height())
        painter.fillRect(target, QColor(255, 255, 255))
        self.scene.render(painter, target, rect)
        painter.end()

    def screen_to_world(self, pos: QPoint) -> QPointF:
        return self.mapToScene(pos)

    # ---- mouse event handling ----
    def mousePressEvent(self, event: QMouseEvent):
        if self._handle_mouse_press(event):
            event.accept()
        else:
            super().mousePressEvent(event)

    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
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
        return False

    def _start_pan(self, event: QMouseEvent):
        self._panning = True
        self._last_pan_pos = event.pos()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _handle_select_press(self, event: QMouseEvent, pos: QPointF, wx: float, wy: float):
        if event.button() == Qt.MouseButton.RightButton:
            if self.scene.hit_atom(pos) is None:
                bidx = self.scene.hit_bond(pos)
                if bidx is not None:
                    self._open_bond_type_menu(bidx, event.globalPosition().toPoint())
                    return
            # Start marquee (any right‑click drag)
            self._select_drag_mode = SelectDragMode.MARQUEE
            self._drag_start = QPointF(wx, wy)
            if self._marquee_mode == 'lasso':
                self.scene.start_lasso(QPointF(wx, wy))
            else:
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
        selected = self.scene.get_selected_atoms()
        if self._space_held and atom.id in selected and len(selected) > 1:
            self._start_drag(wx, wy)
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._toggle_atom_selection(atom, selected)
            self.scene.set_selected_atoms(selected)
            self.selection_changed.emit()
            return
        self._select_atom_with_modifiers(atom, event.modifiers())
        self._start_drag(wx, wy)

    def _start_marquee(self, wx: float, wy: float):
        self._select_drag_mode = SelectDragMode.MARQUEE
        self._drag_start = QPointF(wx, wy)
        if self._marquee_mode == 'lasso':
            self.scene.start_lasso(QPointF(wx, wy))
        else:
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
            selected.remove(atom.id)
        else:
            selected.add(atom.id)

    @staticmethod
    def _set_single_selection(atom: Atom, selected: Set[int]):
        if atom.id not in selected or len(selected) > 1:
            selected.clear()
            selected.add(atom.id)

    def _start_drag(self, wx: float, wy: float):
        self._select_drag_mode = SelectDragMode.ATOMS
        self._drag_undo_pushed = False
        self._drag_offsets = {}
        self._drag_start_positions = {}
        selected = self.scene.get_selected_atoms()
        for aid in selected:
            a = self.mol.get_atom(aid)
            if a:
                self._drag_offsets[aid] = (a.x - wx, a.y - wy)
                self._drag_start_positions[aid] = (a.x, a.y)

    def _handle_edit_press(self, event: QMouseEvent, pos: QPointF, wx: float, wy: float):
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
            if self.scene.hit_atom(pos) is None:
                bidx = self.scene.hit_bond(pos)
                if bidx is not None:
                    self._open_bond_type_menu(bidx, event.globalPosition().toPoint())
                    self._edit_click_candidate = None
                    return
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
        atom = self.scene.hit_atom(pos)
        self._chain_start_id = atom.id if atom else None
        self._chain_start_pos = QPointF(atom.x, atom.y) if atom else QPointF(pos)
        self._chain_preview = []
        self._chain_dragging = True
        self.viewport().update()

    def _update_chain_preview(self, wx: float, wy: float):
        self._chain_preview = compute_chain_zigzag(
            self._chain_start_pos.x(), self._chain_start_pos.y(), wx, wy)

    def _commit_chain_drag(self):
        self.chain_about_to_build.emit()
        self.undo_manager.begin_macro("Build chain")
        positions = self._chain_preview
        self._chain_dragging = False
        self._chain_preview = []
        self.viewport().update()
        if not positions:
            self.undo_manager.end_macro()
            return
        prev_id = self._chain_start_id
        backbone_ids = []
        if prev_id is not None:
            backbone_ids.append(prev_id)
        for (x, y) in positions:
            cmd = AddAtomCommand(self.mol, self.scene, x, y, self.selected_element)
            cmd.execute()
            self.undo_manager.push(cmd)
            new_id = cmd.atom_id
            backbone_ids.append(new_id)
            if prev_id is not None:
                if self.mol.can_bond(prev_id, new_id, self.bond_mode):
                    bond_cmd = AddBondCommand(self.mol, self.scene, prev_id, new_id, self.bond_mode)
                    bond_cmd.execute()
                    self.undo_manager.push(bond_cmd)
            prev_id = new_id
        if self.selected_element == 'C' and self.bond_mode == 'S':
            self._attach_chain_hydrogens(backbone_ids, started_on_existing_atom=self._chain_start_id is not None)
        self.undo_manager.end_macro()
        self.chain_built.emit()

    def _attach_chain_hydrogens(self, backbone_ids: list, started_on_existing_atom: bool):
        backbone_positions = [(self.mol.get_atom(aid).x, self.mol.get_atom(aid).y) for aid in backbone_ids]
        if any(p is None for p in backbone_positions):
            return
        if len(backbone_positions) == 1 and not started_on_existing_atom:
            cx, cy = backbone_positions[0]
            ax, ay = self._chain_start_pos.x(), self._chain_start_pos.y()
            dx, dy = cx - ax, cy - ay
            d = math.hypot(dx, dy)
            ux, uy = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
            carbon_id = backbone_ids[0]
            room = int(self.mol.free_valence(carbon_id))
            for k in range(min(4, room)):
                angle = math.atan2(uy, ux) + math.radians(45 + 90 * k)
                hx = cx + math.cos(angle) * CHAIN_SEGMENT_LENGTH
                hy = cy + math.sin(angle) * CHAIN_SEGMENT_LENGTH
                cmd = AddAtomCommand(self.mol, self.scene, hx, hy, 'H')
                cmd.execute()
                self.undo_manager.push(cmd)
                bond_cmd = AddBondCommand(self.mol, self.scene, carbon_id, cmd.atom_id, 'S')
                bond_cmd.execute()
                self.undo_manager.push(bond_cmd)
            return
        h_slots = compute_chain_hydrogens(backbone_positions, skip_first=started_on_existing_atom)
        slots_by_index: Dict[int, list] = {}
        for (hx, hy, idx) in h_slots:
            slots_by_index.setdefault(idx, []).append((hx, hy))
        for idx, slots in slots_by_index.items():
            carbon_id = backbone_ids[idx]
            room = int(self.mol.free_valence(carbon_id))
            for (hx, hy) in slots[:room]:
                cmd = AddAtomCommand(self.mol, self.scene, hx, hy, 'H')
                cmd.execute()
                self.undo_manager.push(cmd)
                bond_cmd = AddBondCommand(self.mol, self.scene, carbon_id, cmd.atom_id, 'S')
                bond_cmd.execute()
                self.undo_manager.push(bond_cmd)

    def _start_bond_drawing(self, pos: QPointF):
        atom = self.scene.hit_atom(pos)
        if atom:
            self._bond_start_id = atom.id
            self.viewport().update()

    def _open_bond_type_menu(self, bond_index: int, global_pos: QPoint):
        if not (0 <= bond_index < len(self.mol.bonds)):
            return
        self._bond_menu_target_index = bond_index
        bond = self.mol.bonds[bond_index]
        self._bond_menu.set_active(bond.type)
        allowed = {bt['letter'] for bt in BOND_TYPES
                   if bt['letter'] != bond.type and self.mol.can_change_bond_type(bond_index, bt['letter'])}
        self._bond_menu.set_enabled_types(allowed)
        self._bond_menu.move(global_pos)
        self._bond_menu.show()

    def _apply_bond_menu_choice(self, letter: str):
        idx = self._bond_menu_target_index
        self._bond_menu_target_index = None
        if idx is None or not (0 <= idx < len(self.mol.bonds)):
            return
        bond = self.mol.bonds[idx]
        if letter == bond.type:
            return
        if not self.mol.can_change_bond_type(idx, letter):
            glyph = BOND_LETTER_TO_DISPLAY.get(letter, letter)
            self.bond_type_change_rejected.emit(
                f"Can't change bond to {glyph} — not enough free valence on one or both atoms")
            return
        cmd = ChangeBondTypeCommand(self.mol, self.scene, idx, letter)
        cmd.execute()
        self.undo_manager.push(cmd)
        self.bond_type_changed.emit()

    def _add_new_atom(self, wx: float, wy: float):
        sx, sy = self._snap_to_grid(wx, wy)
        nearest, min_dist = self._find_nearest_atom(sx, sy)
        if nearest and min_dist < 100:
            sx, sy = self._calculate_smart_join_position(nearest, sx, sy)
        cmd = AddAtomCommand(self.mol, self.scene, sx, sy, self.selected_element)
        cmd.execute()
        self.undo_manager.push(cmd)
        new_atom_id = cmd.atom_id
        if nearest and min_dist < 100 and self._smart_join:
            if self.mol.can_bond(nearest.id, new_atom_id, self.bond_mode):
                bond_cmd = AddBondCommand(self.mol, self.scene, nearest.id, new_atom_id, self.bond_mode)
                bond_cmd.execute()
                self.undo_manager.push(bond_cmd)
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

    def _handle_delete_press(self, pos: QPointF):
        self._delete_dragging = True
        self._delete_drag_undo_pushed = False
        self._erase_at(pos)

    def _erase_at(self, pos: QPointF):
        atom = self.scene.hit_atom(pos)
        if atom:
            self.undo_manager.begin_macro("Delete atom")
            cmd = RemoveAtomCommand(self.mol, self.scene, atom.id)
            cmd.execute()
            self.undo_manager.push(cmd)
            self.undo_manager.end_macro()
            self.selection_changed.emit()
            self.atom_erased.emit()
            return
        bidx = self.scene.hit_bond(pos)
        if bidx is not None:
            self.undo_manager.begin_macro("Delete bond")
            cmd = RemoveBondCommand(self.mol, self.scene, bidx)
            cmd.execute()
            self.undo_manager.push(cmd)
            self.undo_manager.end_macro()
            self.selection_changed.emit()
            self.atom_erased.emit()

    # ---- mouse move and release ----
    def mouseMoveEvent(self, event: QMouseEvent):
        self._handle_mouse_move(event)

    def _handle_mouse_move(self, event: QMouseEvent):
        pos = self.mapToScene(event.pos())
        if self._last_mouse_pos is None or (pos - self._last_mouse_pos).manhattanLength() > 5:
            self._last_mouse_pos = pos
            self.mouse_moved.emit(pos.x(), pos.y())
        if self.tool_mode == 'edit' and self._edit_click_candidate is not None and self._select_drag_mode == SelectDragMode.NONE:
            pos = self.screen_to_world(event.pos())
            moved = math.hypot(pos.x() - self._edit_click_pos.x(), pos.y() - self._edit_click_pos.y())
            if moved >= self._edit_click_threshold:
                self._edit_click_candidate = None
        if self._select_drag_mode in (SelectDragMode.EMPTY, SelectDragMode.MARQUEE):
            if self._select_drag_mode == SelectDragMode.MARQUEE:
                pos = self.screen_to_world(event.pos())
                wx, wy = pos.x(), pos.y()
                if self._marquee_mode == 'lasso':
                    self.scene.update_lasso(QPointF(wx, wy))
                else:
                    self.scene.update_marquee(QPointF(wx, wy))
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
            return
        offx, offy = self._drag_offsets[aid]
        nx, ny = wx + offx, wy + offy
        if self._snap_enabled:
            nx, ny = self._snap_to_grid(nx, ny)
        a.x = nx
        a.y = ny

    def mouseReleaseEvent(self, event: QMouseEvent):
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
        if self._marquee_mode == 'lasso':
            selected = self.scene.end_lasso()
        else:
            selected = self.scene.end_marquee()
        self.scene.set_selected_atoms(selected)
        self.selection_changed.emit()
        return True

    def _release_atom_drag(self) -> bool:
        if self._select_drag_mode != SelectDragMode.ATOMS:
            return False
        if self._drag_start_positions:
            aid = next(iter(self._drag_start_positions))
            atom = self.mol.get_atom(aid)
            if atom:
                start_x, start_y = self._drag_start_positions[aid]
                dx = atom.x - start_x
                dy = atom.y - start_y
                if dx != 0 or dy != 0:
                    atom_ids = list(self._drag_start_positions.keys())
                    cmd = MoveAtomsCommand(self.mol, self.scene, atom_ids, dx, dy)
                    self.undo_manager.push(cmd)
        self._select_drag_mode = SelectDragMode.NONE
        self._drag_offsets.clear()
        self._drag_start_positions.clear()
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
            cmd = AddBondCommand(self.mol, self.scene, self._bond_start_id, atom.id, self.bond_mode)
            cmd.execute()
            self.undo_manager.push(cmd)
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

    # ---- wheel event ----
    def wheelEvent(self, event: QWheelEvent):
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
        self.zoom_changed.emit(self._zoom)
        event.accept()

    # ---- key events ----
    _NUDGE_KEYS = {
        Qt.Key.Key_Left: (-1, 0),
        Qt.Key.Key_Right: (1, 0),
        Qt.Key.Key_Up: (0, -1),
        Qt.Key.Key_Down: (0, 1),
    }

    def keyPressEvent(self, event: QKeyEvent):
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
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            event.accept()
            return
        if event.key() in self._NUDGE_KEYS and self.tool_mode == 'select':
            ux, uy = self._NUDGE_KEYS[event.key()]
            step = GRID_SIZE if self._snap_enabled else NUDGE_STEP
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step *= NUDGE_STEP_SHIFT_MULTIPLIER
            self.nudge_selection(ux * step, uy * step, push_undo=not event.isAutoRepeat())
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            event.accept()
            return
        super().keyReleaseEvent(event)

    # ---- public API ----
    def get_selected_atoms(self) -> Set[int]:
        return self.scene.get_selected_atoms()

    def delete_selected(self):
        selected = self.scene.get_selected_atoms()
        if not selected:
            return
        self.undo_manager.begin_macro("Delete selected")
        for aid in selected:
            cmd = RemoveAtomCommand(self.mol, self.scene, aid)
            cmd.execute()
            self.undo_manager.push(cmd)
        self.undo_manager.end_macro()
        self.scene.set_selected_atoms(set())
        self.scene.rebuild()
        self.selection_changed.emit()

    def copy_selection(self) -> bool:
        atom_ids = self.scene.get_selected_atoms()
        if not atom_ids:
            return False
        selected_atoms = [a for a in self.mol.atoms if a.id in atom_ids]
        cx, cy = self.mol.selection_center(atom_ids)
        local_id_map = {a.id: idx for idx, a in enumerate(selected_atoms)}
        atoms_payload = [(a.x - cx, a.y - cy, a.element, a.formal_charge) for a in selected_atoms]
        bonds_payload = [
            (local_id_map[b.a1], local_id_map[b.a2], b.type)
            for b in self.mol.bonds
            if b.a1 in local_id_map and b.a2 in local_id_map
        ]
        self._clipboard = {'atoms': atoms_payload, 'bonds': bonds_payload}
        return True

    def has_clipboard_content(self) -> bool:
        return self._clipboard is not None and bool(self._clipboard.get('atoms'))

    def paste_clipboard(self) -> bool:
        if not self.has_clipboard_content():
            return False
        atoms = self._clipboard['atoms']
        bonds = self._clipboard['bonds']
        self.begin_structure_placement(atoms, bonds, name='__clipboard__', scale=1.0)
        return True

    DUPLICATE_OFFSET = 30

    def duplicate_selection(self) -> bool:
        atom_ids = self.scene.get_selected_atoms()
        if not atom_ids:
            return False
        selected_atoms = [a for a in self.mol.atoms if a.id in atom_ids]
        local_id_map = {a.id: idx for idx, a in enumerate(selected_atoms)}
        bonds_to_copy = [
            (b.a1, b.a2, b.type) for b in self.mol.bonds
            if b.a1 in local_id_map and b.a2 in local_id_map
        ]
        self.undo_manager.begin_macro("Duplicate")
        new_id_map: Dict[int, int] = {}
        d = self.DUPLICATE_OFFSET
        for a in selected_atoms:
            cmd = AddAtomCommand(self.mol, self.scene, a.x + d, a.y + d, a.element, formal_charge=a.formal_charge)
            cmd.execute()
            self.undo_manager.push(cmd)
            new_id_map[a.id] = cmd.atom_id
        for old_a1, old_a2, btype in bonds_to_copy:
            bond_cmd = AddBondCommand(self.mol, self.scene, new_id_map[old_a1], new_id_map[old_a2], btype)
            bond_cmd.execute()
            self.undo_manager.push(bond_cmd)
        self.undo_manager.end_macro()
        self.scene.rebuild()
        self.scene.set_selected_atoms(set(new_id_map.values()))
        self.selection_changed.emit()
        return True

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
        if self.tool_mode == 'select' and mode != 'select':
            self.scene.set_selected_atoms(set())
            self.selection_changed.emit()
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

    def set_formal_charge_sign(self, sign: Optional[str]):
        self._formal_charge_sign = sign or None
        if self._formal_charge_sign is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(self._cursor_for_mode(self.tool_mode))

    def _exit_formal_charge_mode(self):
        if self._formal_charge_sign is not None:
            self._formal_charge_sign = None
            self.formal_charge_mode_exited.emit()

    def _exit_chain_mode(self):
        if self._chain_active:
            self._chain_active = False
            self._chain_start_id = None
            self._chain_preview = []
            self.chain_mode_exited.emit()

    @property
    def formal_charge_active(self) -> Optional[str]:
        return self._formal_charge_sign

    def set_chain_active(self, active: bool):
        self._chain_active = active
        if not active:
            self._chain_start_id = None
            self._chain_preview = []
            self.viewport().update()
        self.setCursor(self._cursor_for_mode(self.tool_mode))

    @property
    def chain_active(self) -> bool:
        return self._chain_active

    def _apply_formal_charge_click(self, atom: Atom):
        delta = 1 if self._formal_charge_sign == '+' else -1
        new_charge = atom.formal_charge + delta
        allowed, reason = self.mol.can_set_formal_charge(atom.id, new_charge)
        if not allowed:
            self.formal_charge_rejected.emit(reason)
            return
        cmd = SetFormalChargeCommand(self.mol, self.scene, atom.id, new_charge)
        cmd.execute()
        self.undo_manager.push(cmd)
        self.formal_charge_changed.emit()

    def _transform_target_ids(self) -> set:
        selected = self.scene.get_selected_atoms()
        if selected:
            return selected
        return {a.id for a in self.mol.atoms}

    def rotate_selection(self, degrees: float):
        ids = list(self._transform_target_ids())
        if not ids:
            self.selection_empty_for_transform.emit()
            return
        cx, cy = self.mol.selection_center(ids)
        cmd = RotateAtomsCommand(self.mol, self.scene, ids, degrees, (cx, cy))
        cmd.execute()
        self.undo_manager.push(cmd)
        self.transform_applied.emit()

    def flip_selection(self, axis: str = 'horizontal'):
        ids = list(self._transform_target_ids())
        if not ids:
            self.selection_empty_for_transform.emit()
            return
        cx, cy = self.mol.selection_center(ids)
        cmd = FlipAtomsCommand(self.mol, self.scene, ids, axis, (cx, cy))
        cmd.execute()
        self.undo_manager.push(cmd)
        self.transform_applied.emit()

    def nudge_selection(self, dx: float, dy: float, push_undo: bool = True):
        ids = list(self.scene.get_selected_atoms())
        if not ids:
            return
        cmd = MoveAtomsCommand(self.mol, self.scene, ids, dx, dy)
        cmd.execute()
        if push_undo:
            self.undo_manager.push(cmd)
        self.transform_applied.emit()

    def get_mouse_world_pos(self) -> QPointF:
        if not self.underMouse():
            return self._last_mouse_world
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        return self.mapToScene(local_pos)

    def begin_structure_placement(self, atoms: list, bonds: list, name: str = '', scale: Optional[float] = None):
        self._pending_structure = {
            'atoms': atoms, 'bonds': bonds, 'name': name,
            'scale': scale if scale is not None else (BOND_IDEAL_LENGTH / RDKIT_2D_BOND_LENGTH),
        }
        self._last_mouse_world = self.get_mouse_world_pos()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().update()

    def cancel_structure_placement(self):
        if self._pending_structure is not None:
            self._pending_structure = None
            self.set_tool_mode(self.tool_mode)
            self.viewport().update()

    def is_placing_structure(self) -> bool:
        return self._pending_structure is not None

    def _commit_structure_placement(self, wx: float, wy: float):
        pending = self._pending_structure
        if pending is None:
            return
        scale = pending.get('scale', BOND_IDEAL_LENGTH / RDKIT_2D_BOND_LENGTH)
        atoms = pending['atoms']
        bonds = pending['bonds']
        sx, sy = self._snap_to_grid(wx, wy)
        self.undo_manager.begin_macro("Place structure")
        local_id_map: Dict[int, int] = {}
        for idx, (ax, ay, element, formal_charge) in enumerate(atoms):
            cmd = AddAtomCommand(self.mol, self.scene, sx + ax * scale, sy + ay * scale, element,
                                 formal_charge=formal_charge)
            cmd.execute()
            self.undo_manager.push(cmd)
            local_id_map[idx] = cmd.atom_id
        for i1, i2, btype in bonds:
            if i1 in local_id_map and i2 in local_id_map:
                bond_cmd = AddBondCommand(self.mol, self.scene, local_id_map[i1], local_id_map[i2], btype)
                bond_cmd.execute()
                self.undo_manager.push(bond_cmd)
        self.undo_manager.end_macro()
        self.scene.rebuild()
        self.scene.set_selected_atoms(set(local_id_map.values()))
        self.structure_placed.emit()
