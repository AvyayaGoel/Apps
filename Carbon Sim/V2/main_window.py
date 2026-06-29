"""Main application window."""

import logging
import math
from pathlib import Path
from typing import Optional, Set

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QPoint, QSettings
)
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QProgressDialog, QStatusBar, QMenu
)

from action_toolbar import ActionToolbar
from canvas_view import CanvasView
from chemistry import (
    compute_name, compute_smiles, clear_up_molecule,
    save_scene, load_scene, find_fragments, extract_fragment_mol,
    compute_fragment_formula, format_formula_html, build_from_name
)
from config import (
    WINDOW_W, WINDOW_H, COLORS, VALENCES, RADIUS, VISIBLE_ELEMENTS,
    SHOW_GRID_DEFAULT, SNAP_TO_GRID_DEFAULT, SMART_JOIN_DEFAULT,
    IONIC_DISTANCE, ICON_PATH, NAME_RESOLUTION_DEBOUNCE_MS
)
from mode_toolbar import ModeToolbar
from models import Molecule
from panels import (
    InfoPanel, ElementPanel, PeriodicDialog, HelpOverlay, NameInputDialog
)
from undo import UndoManager
from zoom_widget import CanvasZoomWidget

logger = logging.getLogger(__name__)

STATUS_LABEL_STYLE = 'color: #8ca0c0; font-size: 12px; padding: 2px 8px;'
MAX_RECENTS = 10
RECENTS_SETTINGS_KEY = "recentFiles"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Carbon Simulator')
        self.setMinimumSize(WINDOW_W, WINDOW_H)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(WINDOW_W, WINDOW_H)
        self.setStyleSheet('background-color: #060c16;')

        self.mol = Molecule()
        self.undo_manager = UndoManager()
        self._recents: list[str] = []
        self._recents_menu: QMenu | None = None
        self._load_recents()
        self.last_save_path: Optional[str] = None
        self.display_name = ''
        self._current_name_worker: Optional[QThread] = None
        self._fragment_name_worker: Optional[QThread] = None
        self._build_worker: Optional[QThread] = None
        self._progress: Optional[QProgressDialog] = None
        self._name_debounce = QTimer(self)
        self._name_debounce.setSingleShot(True)
        self._name_debounce.timeout.connect(self._resolve_name_now)
        self._name_recheck_pending = False
        self._last_x = 0.0
        self._last_y = 0.0
        self._name_cache: dict[str, str] = {}
        self._current_whole_smiles: Optional[str] = None
        self._current_fragment_smiles: Optional[str] = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            'QStatusBar { background-color: #0c121e; color: #8ca0c0; border-top: 1px solid #1a2438; }'
        )
        self.setStatusBar(self.status_bar)
        self._status_coords = QLabel('X: 0.0  Y: 0.0')
        self._status_zoom = QLabel('Zoom: 100%')
        self._status_mol = QLabel('Atoms: 0  Bonds: 0')
        self._status_coords.setStyleSheet(STATUS_LABEL_STYLE)
        self._status_zoom.setStyleSheet(STATUS_LABEL_STYLE)
        self._status_mol.setStyleSheet(STATUS_LABEL_STYLE)
        self.status_bar.addWidget(self._status_coords)
        self.status_bar.addWidget(self._status_zoom)
        self.status_bar.addPermanentWidget(self._status_mol)

        self.mode_toolbar = ModeToolbar(central)
        self.mode_toolbar.mode_changed.connect(self._on_mode_changed)
        self.mode_toolbar.rotate_requested.connect(self._on_rotate_requested)
        self.mode_toolbar.flip_requested.connect(self._on_flip_requested)

        self.action_toolbar = ActionToolbar(central)
        self.action_toolbar.bond_mode_changed.connect(self._on_bond_mode_changed)
        self.action_toolbar.clear_up_requested.connect(self._clear_up)
        self.action_toolbar.marquee_mode_changed.connect(self._on_marquee_mode_changed)
        self.action_toolbar.undo_requested.connect(self._undo)
        self.action_toolbar.redo_requested.connect(self._redo)
        self.action_toolbar.formal_charge_toggled.connect(self._on_formal_charge_toggled)
        self.action_toolbar.chain_toggled.connect(self._on_chain_toggled)
        self.action_toolbar.edit_mode_requested.connect(lambda: self.mode_toolbar.set_mode('edit'))

        self.canvas = CanvasView(self.mol, self.undo_manager)
        self.canvas.atom_added.connect(self._on_topology_changed)
        self.canvas.bond_added.connect(self._on_topology_changed)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.atoms_deleted.connect(self._on_topology_changed)
        self.canvas.atom_erased.connect(self._on_topology_changed)
        self.canvas.drag_started.connect(self._on_topology_changed)
        self.canvas.structure_placed.connect(self._on_topology_changed)
        self.canvas.formal_charge_changed.connect(self._on_topology_changed)
        self.canvas.formal_charge_rejected.connect(self._on_formal_charge_rejected)
        self.canvas.formal_charge_mode_exited.connect(self.action_toolbar.untoggle_formal_charge)
        self.canvas.chain_built.connect(self._on_topology_changed)
        self.canvas.chain_mode_exited.connect(self.action_toolbar.untoggle_chain)
        self.canvas.transform_applied.connect(self._on_topology_changed)
        self.canvas.selection_empty_for_transform.connect(self._on_transform_no_target)
        self.canvas.bond_type_changed.connect(self._on_topology_changed)
        self.canvas.bond_type_change_rejected.connect(self._on_bond_type_change_rejected)
        layout.addWidget(self.canvas)

        self.zoom_widget = CanvasZoomWidget(self.canvas)
        self.zoom_widget.zoom_in_requested.connect(self._zoom_in)
        self.zoom_widget.zoom_out_requested.connect(self._zoom_out)

        self.info_panel = InfoPanel()
        self._collapse_btn = QPushButton('◀', central)
        self._collapse_btn.setFixedSize(24, 40)
        self._collapse_btn.hide()
        self._collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2435;
                color: #8ca0c0;
                border: 1px solid #2a3a50;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2a3a58;
                color: #dce8ff;
            }
        """)
        self._collapse_btn.clicked.connect(self._toggle_info_panel)
        self._collapse_btn.setToolTip('Collapse Info Panel')
        self.info_panel.collapse_changed.connect(self._on_panel_anim_step)
        layout.addWidget(self.info_panel)

        self.element_panel = ElementPanel(central)
        self.element_panel.element_selected.connect(self._on_element_selected)
        self.element_panel.periodic_requested.connect(self._show_periodic)
        self.element_panel.size_changed.connect(self._position_panels)

        self.clear_btn = QPushButton('✕', central)
        self.clear_btn.setFixedSize(52, 36)
        self.clear_btn.setStyleSheet(
            'QPushButton { background-color: #5c1c1c; color: #f0c0c0; font-size: 13px; '
            'border: 1px solid #8c2c2c; border-radius: 4px; font-weight: bold; }'
            'QPushButton:hover { background-color: #7c2c2c; }'
        )
        self.clear_btn.setToolTip('Clear Canvas (C)')
        self.clear_btn.clicked.connect(self._clear_scene)

        self.help_overlay = HelpOverlay(central)

        self.info_panel.structure_selected.connect(self._on_structure_selected)
        self.info_panel.molecule_card_clicked.connect(self._on_molecule_card_clicked)

        self._setup_menu()
        self._setup_shortcuts()
        self.canvas.reset_view()
        self._update_layout()

        self.canvas.mouse_moved.connect(self._update_status_coords)
        self.canvas.zoom_changed.connect(self._update_status_zoom)
        self._update_status_zoom(self.canvas.get_zoom())
        self._update_status_mol_counts()
        self._clear_scene()
        self.undo_manager.clear()
        self._update_undo_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_layout()
        self._collapse_btn.show()

    def _available_height(self):
        h = self.height() - self.menuBar().height()
        sb = self.statusBar()
        if sb is not None and sb.isVisible():
            h -= sb.height()
        return h

    def _update_layout(self):
        if hasattr(self, 'canvas') and self.canvas is not None and hasattr(self, 'info_panel'):
            available_w = self.width() - self.info_panel.width()
            new_size = max(400, available_w)
            self.canvas.setFixedSize(new_size, self._available_height())
        self._position_panels()

    def _position_panels(self):
        if not hasattr(self, 'element_panel') or not hasattr(self, 'info_panel'):
            return
        central = self.centralWidget()
        if central and central.layout():
            central.layout().activate()
        info_top_left = self.info_panel.mapTo(central, QPoint(0, 0))
        ep_w = self.element_panel.width()
        x = info_top_left.x() - 10 - ep_w
        y = info_top_left.y() + self._collapse_btn.height() + 12 + 5
        self.element_panel.move(x, y)
        self.element_panel.show()
        ep_h = self.element_panel.height()
        self.clear_btn.move(x, y + ep_h + 12 - 2)
        self.clear_btn.show()

        canvas_geo = self.canvas.geometry()
        hx = canvas_geo.x() + (canvas_geo.width() - self.help_overlay.width()) // 2
        self.help_overlay.move(hx, 120)

        if hasattr(self, 'mode_toolbar'):
            mt_x = canvas_geo.x() + 12
            mt_y = canvas_geo.y() + (canvas_geo.height() - self.mode_toolbar.height()) // 2
            self.mode_toolbar.move(mt_x, mt_y)
            self.mode_toolbar.show()
            self.mode_toolbar.raise_()
        if hasattr(self, 'action_toolbar'):
            at_x = canvas_geo.x() + (canvas_geo.width() - self.action_toolbar.width()) // 2
            at_y = canvas_geo.y() + 12
            self.action_toolbar.move(at_x, at_y)
            self.action_toolbar.show()
            self.action_toolbar.raise_()
        if hasattr(self, 'zoom_widget'):
            zw_x = self.canvas.width() - self.zoom_widget.width() - 12
            zw_y = self.canvas.height() - self.zoom_widget.height() - 12
            self.zoom_widget.move(zw_x, zw_y)
            self.zoom_widget.show()
            self.zoom_widget.raise_()
        self._position_collapse_button()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout()

    def _on_panel_anim_step(self, _collapsed: bool):
        self._update_layout()

    def _position_collapse_button(self):
        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()
        panel_top_left = self.info_panel.mapTo(self.centralWidget(), QPoint(0, 0))
        btn_w = self._collapse_btn.width()
        x = panel_top_left.x() - btn_w + 1
        y = panel_top_left.y() + 20
        self._collapse_btn.move(x, y)
        self._collapse_btn.raise_()

    def _toggle_info_panel(self):
        collapsed = self.info_panel.toggle_collapse()
        self._collapse_btn.setText('▶' if collapsed else '◀')
        self._collapse_btn.setToolTip('Expand Info Panel' if collapsed else 'Collapse Info Panel')
        self._position_collapse_button()

    # ---- Menu ----
    def _setup_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(
            'QMenuBar { background-color: #181a22; color: #ebedff; padding: 4px; }'
            'QMenuBar::item:selected { background-color: #2d3748; border-radius: 4px; }'
            'QMenu { background-color: #1e2430; color: #ebedff; border: 1px solid #3a4050; }'
            'QMenu::item:selected { background-color: #2d3a50; }'
        )

        file_menu = menubar.addMenu('File')
        new_action = QAction('New', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self._new_scene)
        file_menu.addAction(new_action)

        open_action = QAction('Open...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        save_action = QAction('Save', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction('Save As...', self)
        save_as_action.setShortcut('Ctrl+Shift+S')
        save_as_action.triggered.connect(self._save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()
        export_menu = file_menu.addMenu('Export')
        for fmt, label in [('png', 'PNG Image...'), ('svg', 'SVG Vector...'), ('pdf', 'PDF Document...')]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked, f=fmt: self._export_as(f))
            export_menu.addAction(act)

        file_menu.addSeparator()
        self._recents_menu = file_menu.addMenu('Recents')
        self._build_recents_menu()
        file_menu.addSeparator()
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu('Edit')
        undo_action = QAction('Undo', self)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)
        redo_action = QAction('Redo', self)
        redo_action.setShortcut('Ctrl+Y')
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        select_all_action = QAction('Select All', self)
        select_all_action.setShortcut('Ctrl+A')
        select_all_action.triggered.connect(self.canvas.select_all)
        edit_menu.addAction(select_all_action)
        delete_action = QAction('Delete', self)
        delete_action.setShortcut('Delete')
        delete_action.triggered.connect(self.canvas.delete_selected)
        edit_menu.addAction(delete_action)
        edit_menu.addSeparator()
        copy_action = QAction('Copy', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self._copy_selection)
        edit_menu.addAction(copy_action)
        paste_action = QAction('Paste', self)
        paste_action.setShortcut('Ctrl+V')
        paste_action.triggered.connect(self._paste_clipboard)
        edit_menu.addAction(paste_action)
        duplicate_action = QAction('Duplicate', self)
        duplicate_action.setShortcut('Ctrl+D')
        duplicate_action.triggered.connect(self.canvas.duplicate_selection)
        edit_menu.addAction(duplicate_action)

        view_menu = menubar.addMenu('View')
        center_action = QAction('Center Molecule', self)
        center_action.triggered.connect(self.canvas.center_molecule)
        view_menu.addAction(center_action)
        reset_zoom_action = QAction('Reset Zoom', self)
        reset_zoom_action.setShortcut('Ctrl+R')
        reset_zoom_action.triggered.connect(self.canvas.reset_view)
        view_menu.addAction(reset_zoom_action)
        grid_action = QAction('Show Grid', self)
        grid_action.setCheckable(True)
        grid_action.setChecked(SHOW_GRID_DEFAULT)
        grid_action.triggered.connect(self._toggle_grid)
        view_menu.addAction(grid_action)
        snap_action = QAction('Snap to Grid', self)
        snap_action.setCheckable(True)
        snap_action.setChecked(SNAP_TO_GRID_DEFAULT)
        snap_action.triggered.connect(self._toggle_snap)
        view_menu.addAction(snap_action)
        smart_action = QAction('Smart Join', self)
        smart_action.setCheckable(True)
        smart_action.setChecked(SMART_JOIN_DEFAULT)
        smart_action.triggered.connect(self._toggle_smart_join)
        view_menu.addAction(smart_action)

        help_menu = menubar.addMenu('Help')
        help_action = QAction('Help', self)
        help_action.setShortcut('H')
        help_action.triggered.connect(self._toggle_help)
        help_menu.addAction(help_action)
        about_action = QAction('About', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ---- Recents ----
    def _load_recents(self):
        settings = QSettings('CarbonSim', 'CarbonSimulator')
        recents = settings.value(RECENTS_SETTINGS_KEY, [])
        if isinstance(recents, str):
            self._recents = [recents] if recents else []
        elif recents is None:
            self._recents = []
        else:
            self._recents = [str(r) for r in recents if r]

    def _save_recents(self):
        settings = QSettings('CarbonSim', 'CarbonSimulator')
        settings.setValue(RECENTS_SETTINGS_KEY, self._recents)

    def _add_to_recents(self, path: str):
        if not path:
            return
        path = str(Path(path).resolve())
        if path in self._recents:
            self._recents.remove(path)
        self._recents.insert(0, path)
        if len(self._recents) > MAX_RECENTS:
            self._recents = self._recents[:MAX_RECENTS]
        self._save_recents()
        self._build_recents_menu()

    def _build_recents_menu(self):
        if self._recents_menu is None:
            return
        self._recents_menu.clear()
        if not self._recents:
            no_recent = QAction('No Recent Files', self)
            no_recent.setEnabled(False)
            self._recents_menu.addAction(no_recent)
            return
        for path in self._recents:
            p = Path(path)
            display = f'{p.name}  —  {p.parent.name}' if p.parent.name else p.name
            action = QAction(display, self)
            action.setToolTip(str(p))
            action.triggered.connect(lambda checked, f=path: self._open_recent(f))
            self._recents_menu.addAction(action)
        self._recents_menu.addSeparator()
        clear_action = QAction('Clear Menu', self)
        clear_action.triggered.connect(self._clear_recents)
        self._recents_menu.addAction(clear_action)

    def _open_recent(self, path: str):
        try:
            mol, cam_x, cam_y, zoom = load_scene(path)
            self.undo_manager.snapshot(self.mol)
            self.mol.atoms = mol.atoms
            self.mol.bonds = mol.bonds
            self.mol.next_id = mol.next_id
            self.canvas.scene.rebuild()
            self.canvas.set_camera(cam_x, cam_y)
            self.canvas.set_zoom(zoom)
            self.last_save_path = path
            self._add_to_recents(path)
            filename = Path(path).name
            self.setWindowTitle(f'Carbon Simulator - {filename}')
            self._on_topology_changed()
        except Exception as e:
            logger.exception(f'_open_recent error: {e}')
            QMessageBox.critical(self, 'Error', f'Failed to open recent file:\n{e}')
            if path in self._recents:
                self._recents.remove(path)
                self._save_recents()
                self._build_recents_menu()

    def _clear_recents(self):
        self._recents.clear()
        self._save_recents()
        self._build_recents_menu()

    # ---- Shortcuts ----
    def _setup_shortcuts(self):
        shortcuts = [
            ('S', lambda: self.mode_toolbar.set_mode('select')),
            ('E', lambda: self.mode_toolbar.set_mode('edit')),
            ('D', lambda: self.mode_toolbar.set_mode('delete')),
            ('1', lambda: self._set_bond_mode('S')),
            ('2', lambda: self._set_bond_mode('D')),
            ('3', lambda: self._set_bond_mode('T')),
            ('4', lambda: self._set_bond_mode('A')),
            ('5', lambda: self._set_bond_mode('DA')),
            ('C', self._clear_scene),
            ('N', self._show_name_dialog),
        ]
        for key, slot in shortcuts:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)

    # ---- Signal handlers ----
    def _on_mode_changed(self, mode: str):
        if mode == 'delete':
            selected = self.canvas.get_selected_atoms()
            if selected:
                self.canvas.delete_selected()
        self.canvas.set_tool_mode(mode)
        self.canvas.cancel_structure_placement()
        self.action_toolbar.set_edit_mode_active(mode == 'edit')
        if self.help_overlay.isVisible():
            self.help_overlay.highlight_mode(mode)

    def _on_bond_mode_changed(self, mode: str):
        self.canvas.set_bond_mode(mode)

    def _on_formal_charge_toggled(self, sign: str):
        self.canvas.set_formal_charge_sign(sign or None)

    def _on_chain_toggled(self, active: bool):
        if active and self.mode_toolbar.current_mode != 'edit':
            self.mode_toolbar.set_mode('edit')
        self.canvas.set_chain_active(active)

    def _on_formal_charge_rejected(self, reason: str):
        self.statusBar().showMessage(f'Formal charge not applied — {reason}', 4000)

    def _on_bond_type_change_rejected(self, reason: str):
        self.statusBar().showMessage(reason, 4000)

    def _on_rotate_requested(self, degrees: float):
        self.canvas.rotate_selection(degrees)

    def _on_flip_requested(self, axis: str):
        self.canvas.flip_selection(axis)

    def _on_transform_no_target(self):
        self.statusBar().showMessage('Nothing to transform — canvas is empty', 3000)

    def _set_bond_mode(self, mode: str):
        self.canvas.set_bond_mode(mode)
        self.action_toolbar.set_bond_mode(mode)

    def _on_element_selected(self, element: str):
        self.canvas.set_selected_element(element)
        self.mode_toolbar.set_mode('edit')

    def _show_periodic(self):
        dialog = PeriodicDialog(self)
        dialog.element_selected.connect(self._on_periodic_selected)
        dialog.exec()

    def _on_periodic_selected(self, element: str):
        if element not in VISIBLE_ELEMENTS:
            VISIBLE_ELEMENTS.append(element)
            COLORS.setdefault(element, (200, 200, 200))
            VALENCES.setdefault(element, 4)
            RADIUS.setdefault(element, 22)
        self.element_panel.add_recent(element)
        self.element_panel.select_element(element)
        self._on_element_selected(element)

    def _on_structure_selected(self, entry):
        atoms, bonds = entry.ghost_geometry()
        if not atoms:
            QMessageBox.warning(self, 'Structure Unavailable',
                                f"Could not load the structure for '{entry.name}'.")
            return
        self.mode_toolbar.set_mode('edit')
        self.canvas.begin_structure_placement(atoms, bonds, entry.name)
        self.statusBar().showMessage(
            f"Placing {entry.name} — click on the canvas to drop it, Esc to cancel", 4000
        )

    def _on_molecule_card_clicked(self, atom_ids: set):
        if not atom_ids:
            return
        self.mode_toolbar.set_mode('select')
        self.canvas.scene.set_selected_atoms(set(atom_ids))
        self.canvas.selection_changed.emit()
        self.canvas.setFocus()

    def _on_selection_changed(self):
        self._update_info_panel()
        self._update_status_mol_counts()

    def _on_topology_changed(self):
        self._update_info_panel()
        self._update_undo_buttons()
        self._update_status_mol_counts()
        self._check_name_update()

    def _copy_selection(self):
        n = len(self.canvas.get_selected_atoms())
        if n == 0:
            self.status_bar.showMessage('Nothing selected to copy', 2500)
            return
        if self.canvas.copy_selection():
            self.status_bar.showMessage(f'Copied {n} atom{"s" if n != 1 else ""}', 2500)

    def _paste_clipboard(self):
        if not self.canvas.has_clipboard_content():
            self.status_bar.showMessage('Clipboard is empty — copy something first', 2500)
            return
        self.canvas.paste_clipboard()
        self.status_bar.showMessage('Click on the canvas to place — Esc to cancel', 3000)

    def _undo(self):
        if self.undo_manager.undo():
            self.canvas.scene.rebuild()
            self._update_info_panel()
            self._update_undo_buttons()
            self._update_status_mol_counts()
            self._check_name_update()

    def _redo(self):
        if self.undo_manager.redo():
            self.canvas.scene.rebuild()
            self._update_info_panel()
            self._update_undo_buttons()
            self._update_status_mol_counts()
            self._check_name_update()

    def _update_undo_buttons(self):
        self.action_toolbar.set_undo_enabled(self.undo_manager.can_undo)
        self.action_toolbar.set_redo_enabled(self.undo_manager.can_redo)

    def _clear_scene(self):
        self.undo_manager.clear()
        self.mol.clear()
        self.canvas.scene.rebuild()
        self.canvas.reset_view()
        self._update_info_panel()
        self._update_undo_buttons()
        self._update_status_mol_counts()
        self.display_name = ''
        self._current_whole_smiles = None
        self._current_fragment_smiles = None

    def _new_scene(self):
        self._clear_scene()
        self.last_save_path = None
        self.setWindowTitle('Carbon Simulator - Untitled')

    def _clear_up(self):
        self.undo_manager.snapshot(self.mol)
        new_mol = clear_up_molecule(self.mol)
        self.mol.atoms = new_mol.atoms
        self.mol.bonds = new_mol.bonds
        self.mol.next_id = new_mol.next_id
        self.canvas.scene.rebuild()
        self.canvas.center_molecule()
        self._on_topology_changed()

    def _show_name_dialog(self):
        dialog = NameInputDialog(self)
        dialog.build_requested.connect(self._build_from_name)
        dialog.exec()

    def _build_from_name(self, name: str):
        self._progress = QProgressDialog('Building molecule...', '', 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setWindowTitle('Please Wait')
        self._progress.setCancelButton(None)
        self._progress.show()
        self._build_worker = BuildWorker(name)
        self._build_worker.molecule_ready.connect(self._on_build_ready)
        self._build_worker.finished.connect(self._progress.close)
        self._build_worker.finished.connect(self._build_worker.deleteLater)
        self._build_worker.start()

    def _on_build_ready(self, new_mol):
        if new_mol:
            self.undo_manager.snapshot(self.mol)
            self.mol.atoms = new_mol.atoms
            self.mol.bonds = new_mol.bonds
            self.mol.next_id = new_mol.next_id
            self.canvas.scene.rebuild()
            self.canvas.reset_view()
            self._on_topology_changed()
        else:
            QMessageBox.warning(self, 'Build Failed', 'Could not build molecule from that name.')

    def _check_name_update(self):
        if not self.mol.atoms:
            self.display_name = ''
            self._current_whole_smiles = None
            self._name_debounce.stop()
            self._update_info_panel()
            return
        smiles = compute_smiles(self.mol)
        if not smiles or smiles == self._current_whole_smiles:
            return
        self._current_whole_smiles = smiles
        self._name_debounce.start(NAME_RESOLUTION_DEBOUNCE_MS)

    def _resolve_name_now(self):
        smiles = self._current_whole_smiles
        if not smiles:
            return
        if smiles in self._name_cache:
            self.display_name = self._name_cache[smiles]
            self._update_info_panel()
            return
        if self._current_name_worker and self._current_name_worker.isRunning():
            self._name_recheck_pending = True
            return
        self._current_name_worker = NameWorker(self.mol.to_dict(), compute_name)
        self._current_name_worker.name_ready.connect(lambda name, s=smiles: self._on_name_ready(name, s))
        self._current_name_worker.finished.connect(self._cleanup_name_worker)
        self._current_name_worker.start()

    def _on_name_ready(self, name: str, smiles: str):
        self._name_cache[smiles] = name
        if smiles == self._current_whole_smiles:
            self.display_name = name
            self._update_info_panel()

    def _cleanup_name_worker(self):
        sender = self.sender()
        if sender == self._current_name_worker:
            self._current_name_worker.deleteLater()
            self._current_name_worker = None
        if self._name_recheck_pending:
            self._name_recheck_pending = False
            self._resolve_name_now()

    def _lookup_fragment_name(self, frag_mol, smiles):
        if smiles in self._name_cache:
            self.info_panel.update_fragment_name(self._name_cache[smiles])
            return
        if self._fragment_name_worker and self._fragment_name_worker.isRunning():
            return
        self._fragment_name_worker = NameWorker(frag_mol.to_dict(), compute_name)
        self._fragment_name_worker.name_ready.connect(lambda name, s=smiles: self._on_fragment_name_ready(name, s))
        self._fragment_name_worker.finished.connect(self._cleanup_fragment_name_worker)
        self._fragment_name_worker.start()

    def _on_fragment_name_ready(self, name: str, smiles: str):
        self._name_cache[smiles] = name
        self.info_panel.update_fragment_name(name)

    def _cleanup_fragment_name_worker(self):
        sender = self.sender()
        if sender == self._fragment_name_worker:
            self._fragment_name_worker.deleteLater()
            self._fragment_name_worker = None

    def _update_info_panel(self):
        selected = self.canvas.get_selected_atoms()
        fragments = find_fragments(self.mol)
        fragment_smiles = self._compute_fragment_smiles_map(fragments)
        if len(selected) == 0:
            self._show_no_selection_case(fragments, fragment_smiles)
        elif len(selected) == 1:
            self._show_single_atom_case(selected, fragments, fragment_smiles)
        else:
            self._show_multi_atom_case(selected, fragments, fragment_smiles)

    def _compute_fragment_smiles_map(self, fragments):
        fragment_smiles = {}
        for frag in fragments:
            frag_mol = extract_fragment_mol(self.mol, frag)
            smiles = compute_smiles(frag_mol)
            fragment_smiles[frozenset(frag)] = smiles
        return fragment_smiles

    @staticmethod
    def _fragment_dedup_key(info: dict, smiles: str) -> str:
        return smiles if smiles else f"{info['formula_plain']}_{info['atom_count']}_{info['charge']}"

    def _show_no_selection_case(self, fragments, fragment_smiles):
        self._current_fragment_smiles = None
        frag_data = []
        seen = {}
        for frag in fragments:
            smiles = fragment_smiles.get(frozenset(frag), '')
            info = self._compute_fragment_info(frag, detailed=False)
            info['smiles'] = smiles
            info['count'] = 1
            key = self._fragment_dedup_key(info, smiles)
            if key in seen:
                seen[key]['count'] += 1
                seen[key]['atom_ids'] |= info['atom_ids']
            else:
                seen[key] = info
                frag_data.append(info)
        self.info_panel.set_case_1(frag_data)

    def _show_single_atom_case(self, selected, fragments, fragment_smiles):
        atom_id = next(iter(selected))
        target_frag = set(next((frag for frag in fragments if atom_id in frag), ()))
        if not target_frag:
            self.info_panel.set_empty()
            return
        info = self._show_fragment_detail(target_frag, fragment_smiles)
        atom = self.mol.get_atom(atom_id)
        self.info_panel.set_case_2(info, atom, self.mol)

    def _show_multi_atom_case(self, selected, fragments, fragment_smiles):
        touched = [frag for frag in fragments if frag & selected]
        if len(touched) == 1:
            info = self._show_fragment_detail(touched[0], fragment_smiles)
            self.info_panel.set_case_2(info, None, self.mol)
            return
        self._current_fragment_smiles = None
        frag_data = []
        seen_keys = set()
        for frag in touched:
            smiles = fragment_smiles.get(frozenset(frag), '')
            info = self._compute_fragment_info(frag, detailed=False)
            info['smiles'] = smiles
            key = self._fragment_dedup_key(info, smiles)
            if key not in seen_keys:
                seen_keys.add(key)
                frag_data.append(info)
        self.info_panel.set_case_3(frag_data)

    def _show_fragment_detail(self, target_frag, fragment_smiles):
        frag_smiles = fragment_smiles.get(frozenset(target_frag), '')
        info = self._compute_fragment_info(target_frag, detailed=True)
        info['smiles'] = frag_smiles
        if frag_smiles and frag_smiles != self._current_fragment_smiles:
            self._current_fragment_smiles = frag_smiles
            if frag_smiles in self._name_cache:
                self.info_panel.update_fragment_name(self._name_cache[frag_smiles])
            elif len(target_frag) >= 2:
                frag_mol = extract_fragment_mol(self.mol, target_frag)
                self._lookup_fragment_name(frag_mol, frag_smiles)
            else:
                self.info_panel.update_fragment_name('')
        if len(target_frag) == len(self.mol.atoms) and self.display_name:
            info['name'] = self.display_name
        return info

    def _compute_fragment_info(self, atom_ids: Set[int], detailed: bool = False) -> dict:
        frag_mol = extract_fragment_mol(self.mol, atom_ids)
        formula, mass, charge = compute_fragment_formula(frag_mol)
        formula_html = format_formula_html(formula, charge)
        bond_count = sum(1 for b in self.mol.bonds if b.a1 in atom_ids and b.a2 in atom_ids)
        composition = {}
        for a in self.mol.atoms:
            if a.id in atom_ids:
                composition[a.element] = composition.get(a.element, 0) + 1
        info = {
            'formula_html': formula_html, 'formula_plain': formula, 'mass': mass,
            'charge': charge, 'atom_count': len(atom_ids), 'bond_count': bond_count,
            'composition': composition, 'atom_ids': set(atom_ids)
        }
        if detailed:
            info['ionic_pairs'] = self._count_ionic_pairs(atom_ids)
            info['smiles'] = compute_smiles(frag_mol) if len(atom_ids) > 1 else ''
            if len(atom_ids) == len(self.mol.atoms) and self.display_name:
                info['name'] = self.display_name
        return info

    def _count_ionic_pairs(self, atom_ids: Set[int]) -> int:
        charged = [a for a in self.mol.atoms if a.id in atom_ids and a.formal_charge != 0]
        ionic_pairs = 0
        for i, a1 in enumerate(charged):
            for a2 in charged[i + 1:]:
                if a1.formal_charge * a2.formal_charge >= 0:
                    continue
                d = math.hypot(a1.x - a2.x, a1.y - a2.y)
                if d <= IONIC_DISTANCE:
                    ionic_pairs += 1
        return ionic_pairs

    def _update_status_coords(self, wx: float, wy: float):
        self._status_coords.setText(f'X: {wx:.1f}  Y: {wy:.1f}')

    def _update_status_zoom(self, zoom: float):
        self._status_zoom.setText(f'Zoom: {zoom * 100:.0f}%')

    def _update_status_mol_counts(self):
        self._status_mol.setText(f'Atoms: {len(self.mol.atoms)}  Bonds: {len(self.mol.bonds)}')

    def _toggle_help(self):
        visible = self.help_overlay.isVisible()
        self.help_overlay.setVisible(not visible)
        if self.help_overlay.isVisible():
            self.help_overlay.highlight_mode(self.canvas.tool_mode)
            self.help_overlay.raise_()

    def _show_about(self):
        QMessageBox.about(self, 'About Carbon Simulator',
                          '<h2>Carbon Simulator</h2><p>Created by Avyaya &bull; 2025</p>'
                          '<p>A molecular structure editor built with PyQt6 and RDKit.</p>')

    def _toggle_grid(self, checked):
        self.canvas.set_grid_visible(checked)

    def _toggle_snap(self, checked):
        self.canvas.set_snap_enabled(checked)

    def _toggle_smart_join(self, checked):
        self.canvas.set_smart_join(checked)

    def _on_marquee_mode_changed(self, mode: str):
        self.canvas.set_marquee_mode(mode)

    def _save_file(self):
        if self.last_save_path:
            cam = self.canvas.get_camera()
            save_scene(self.mol, self.last_save_path, cam[0], cam[1], self.canvas.get_zoom())
            self._add_to_recents(self.last_save_path)
        else:
            self._save_as()

    def _save_as(self):
        result = QFileDialog.getSaveFileName(self, 'Save Molecule', '', 'JSON Molecule (*.json)')
        path: str = result[0]
        if path:
            cam = self.canvas.get_camera()
            save_scene(self.mol, path, cam[0], cam[1], self.canvas.get_zoom())
            self.last_save_path = path
            self._add_to_recents(path)
            filename = Path(path).name
            self.setWindowTitle(f'Carbon Simulator - {filename}')

    _EXPORT_FILTERS = {
        'png': 'PNG Image (*.png)',
        'svg': 'SVG Vector (*.svg)',
        'pdf': 'PDF Document (*.pdf)',
    }

    def _export_as(self, fmt: str):
        if not self.mol.atoms:
            QMessageBox.information(self, 'Nothing to Export', 'The canvas is empty — draw something first.')
            return
        filt = self._EXPORT_FILTERS[fmt]
        result = QFileDialog.getSaveFileName(self, f'Export as {fmt.upper()}', '', filt)
        path: str = result[0]
        if not path:
            return
        if not path.lower().endswith(f'.{fmt}'):
            path = f'{path}.{fmt}'
        try:
            if fmt == 'png':
                self.canvas.export_image(path, 'png', transparent=True, scale=2.0)
            else:
                self.canvas.export_image(path, fmt)
        except Exception as e:
            logger.exception(f'Error in _export_as ({fmt}): {e}')
            QMessageBox.warning(self, 'Export Failed', f"Couldn't export as {fmt.upper()}: {e}")

    def _open_file(self):
        result = QFileDialog.getOpenFileName(self, 'Open Molecule', '', 'JSON Molecule (*.json)')
        path: str = result[0]
        if path:
            try:
                mol, cam_x, cam_y, zoom = load_scene(path)
                self.undo_manager.snapshot(self.mol)
                self.mol.atoms = mol.atoms
                self.mol.bonds = mol.bonds
                self.mol.next_id = mol.next_id
                self.canvas.scene.rebuild()
                self.canvas.set_camera(cam_x, cam_y)
                self.canvas.set_zoom(zoom)
                self.last_save_path = path
                self._add_to_recents(path)
                filename = Path(path).name
                self.setWindowTitle(f'Carbon Simulator - {filename}')
                self._on_topology_changed()
            except Exception as e:
                logger.exception(f'Failed to load file: {e}')
                QMessageBox.critical(self, 'Error', f'Failed to load file:\n{e}')

    def _zoom_in(self):
        self.canvas.set_zoom(self.canvas.get_zoom() * 1.2)

    def _zoom_out(self):
        self.canvas.set_zoom(self.canvas.get_zoom() / 1.2)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canvas.cancel_structure_placement()
            self.help_overlay.hide()
        super().keyPressEvent(event)


# ---- Worker classes ----
class NameWorker(QThread):
    name_ready = pyqtSignal(str)

    def __init__(self, mol_dict: dict, compute_name_func):
        super().__init__()
        self.mol_dict = mol_dict
        self.compute_name_func = compute_name_func

    def run(self):
        mol = Molecule()
        mol.from_dict(self.mol_dict)
        name = self.compute_name_func(mol)
        self.name_ready.emit(name)


class BuildWorker(QThread):
    molecule_ready = pyqtSignal(object)

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def run(self):
        mol = build_from_name(self.name)
        self.molecule_ready.emit(mol)
