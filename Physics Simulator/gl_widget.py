"""
ui/gl_widget.py – with free camera, transform gizmo, and placement mode.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QElapsedTimer, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QSurfaceFormat, QWheelEvent
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from body import RigidBody
from camera import OrbitCamera
from config import SimulationConfig
from event_bus import bus
from force_object import ForceObject
from gizmo import TransformGizmo
from math_utils import ray_plane_intersect, vec3
from renderer import Renderer
from scene import Scene

logger = logging.getLogger(__name__)


def make_default_surface_format() -> QSurfaceFormat:
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(4)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setVersion(2, 1)
    return fmt


class SandboxGLWidget(QOpenGLWidget):
    fps_updated = pyqtSignal(float)
    selection_changed = pyqtSignal(object)
    object_count_changed = pyqtSignal(int)

    def __init__(self, scene: Scene, config: SimulationConfig, parent=None) -> None:
        super().__init__(parent)
        self.setFormat(make_default_surface_format())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.scene = scene
        self.config = config
        self.camera = OrbitCamera()
        self.renderer = Renderer(config)
        self.gizmo = TransformGizmo()
        self.show_gizmo = True

        self._last_mouse_pos = None
        self._orbiting = False
        self._panning = False
        self._dragging_body: Optional[RigidBody] = None
        self._dragging_force: Optional[ForceObject] = None
        self._drag_plane_y = 0.0
        self._press_pos = None
        self._pending_deselect = False

        self._placement_mode = False
        self._placement_kind = "sphere"
        self._free_camera = False
        self._pressed_keys = set()

        # Gizmo drag state
        self._gizmo_dragging = False
        self._gizmo_axis = None

        self._clock = QElapsedTimer()
        self._clock.start()
        self._last_frame_ns = self._clock.nsecsElapsed()
        self._fps_smoother = 60.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(int(1000 / config.target_fps))

        bus.subscribe("scene.selection_changed", lambda body: self.selection_changed.emit(body))
        bus.subscribe("input.set_place_mode", self._set_place_mode)
        for evt in ("scene.object_spawned", "scene.object_removed", "physics.body_added",
                    "physics.body_removed", "scene.cleared", "scene.reset"):
            bus.subscribe(evt, lambda *_: self.object_count_changed.emit(len(self.scene.world.bodies)))

        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # QOpenGLWidget overrides
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:
        self.renderer.init_gl()

    def resizeGL(self, w: int, h: int) -> None:
        self.renderer.resize(w, h)
        self.camera.viewport = (w, h)
        self.camera.fov_deg = self.config.camera_fov_deg

    def paintGL(self) -> None:
        # Pass gizmo to renderer
        self.renderer.gizmo = self.gizmo if self.show_gizmo and self.scene.selected_body else None
        self.renderer.render(self.scene, self.camera)

    # ------------------------------------------------------------------
    # Simulation tick
    # ------------------------------------------------------------------

    def _on_tick(self) -> None:
        now_ns = self._clock.nsecsElapsed()
        dt = max(0.0, (now_ns - self._last_frame_ns) / 1e9)
        self._last_frame_ns = now_ns
        dt = min(dt, 0.1)

        self._update_free_camera_motion(dt)
        self.scene.update(dt)
        self.renderer.update(dt)

        if dt > 1e-6:
            instant_fps = 1.0 / dt
            self._fps_smoother = self._fps_smoother * 0.9 + instant_fps * 0.1
            self.fps_updated.emit(self._fps_smoother)

        self.update()

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = event.position()
        pos = event.position()

        if self._placement_mode and event.button() == Qt.MouseButton.LeftButton:
            ray_o, ray_d = self.camera.screen_to_ray(pos.x(), pos.y())
            t = ray_plane_intersect(ray_o, ray_d, vec3(0, 0, 0), vec3(0, 1, 0))
            if t is not None:
                world_pos = ray_o + ray_d * t
                self.scene.spawn(self._placement_kind, position=world_pos)
            return

        # Check gizmo pick first
        if self.show_gizmo and self.scene.selected_body:
            ray_o, ray_d = self.camera.screen_to_ray(pos.x(), pos.y())
            body = self.scene.selected_body
            handle, hit = self.gizmo.pick(ray_o, ray_d, body)
            if handle is not None and event.button() == Qt.MouseButton.LeftButton:
                self._gizmo_dragging = True
                self._gizmo_axis = handle
                self.gizmo.start_drag(handle, hit, body)
                return

        if event.button() == Qt.MouseButton.LeftButton:
            ray_o, ray_d = self.camera.screen_to_ray(pos.x(), pos.y())
            hit = self.scene.pick(ray_o, ray_d)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if isinstance(hit, RigidBody):
                    self.scene.set_secondary_selection(hit)
                    return
            self._press_pos = pos
            if hit is not None:
                self._pending_deselect = False
                self.scene.select(hit)
                if isinstance(hit, RigidBody) and not hit.is_static:
                    self._dragging_body = hit
                    self._drag_plane_y = hit.position[1]
                elif isinstance(hit, ForceObject):
                    self._dragging_force = hit
                    self._drag_plane_y = hit.get_world_position()[1]
            else:
                # Don't clear the current selection here - a click that
                # misses everything is also how every orbit drag starts.
                # Only actually deselect in mouseReleaseEvent, and only if
                # this turns out to have been a plain click rather than a
                # drag (see _pending_deselect handling there).
                self._pending_deselect = True
                if not self._free_camera:
                    self._orbiting = True
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
        elif event.button() == Qt.MouseButton.RightButton:
            self._orbiting = True

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if self._last_mouse_pos is None:
            self._last_mouse_pos = pos
            return
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        self._last_mouse_pos = pos

        # Gizmo drag
        if self._gizmo_dragging and self.scene.selected_body:
            ray_o, ray_d = self.camera.screen_to_ray(pos.x(), pos.y())
            if self._gizmo_axis and self._gizmo_axis[0] == "rotate":
                new_orientation = self.gizmo.update_rotation(ray_o, ray_d, self.scene.selected_body,
                                                             self.camera.forward())
                if new_orientation is not None:
                    self.scene.selected_body.orientation = new_orientation
                    self.scene.selected_body.angular_velocity[:] = 0.0
                    self.scene.selected_body.wake()
            else:
                new_pos = self.gizmo.update_drag(ray_o, ray_d, self.scene.selected_body)
                if new_pos is not None:
                    self.scene.selected_body.position = new_pos
                    self.scene.selected_body.velocity[:] = 0.0
                    self.scene.selected_body.wake()
            return

        if self._dragging_body is not None:
            ray_o, ray_d = self.camera.screen_to_ray(pos.x(), pos.y())
            t = ray_plane_intersect(ray_o, ray_d, vec3(0, self._drag_plane_y, 0), vec3(0, 1, 0))
            if t is not None:
                world_pos = ray_o + ray_d * t
                self.scene.move_selected_to(world_pos)
        elif self._dragging_force is not None:
            ray_o, ray_d = self.camera.screen_to_ray(pos.x(), pos.y())
            t = ray_plane_intersect(ray_o, ray_d, vec3(0, self._drag_plane_y, 0), vec3(0, 1, 0))
            if t is not None:
                world_pos = ray_o + ray_d * t
                self.scene.move_selected_force_to(world_pos)
        elif self._orbiting:
            self.camera.orbit(dx, dy, self.config.orbit_sensitivity)
        elif self._panning:
            self.camera.pan(dx, dy, self.config.pan_sensitivity)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._gizmo_dragging:
            self._gizmo_dragging = False
            self._gizmo_axis = None
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._orbiting = False
            if self._dragging_body is not None:
                self._dragging_body.wake()
            self._dragging_body = None
            self._dragging_force = None
            if self._pending_deselect:
                moved = 0.0
                if self._press_pos is not None:
                    delta = event.position() - self._press_pos
                    moved = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
                if moved < 4.0:
                    self.scene.select(None)
                self._pending_deselect = False
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
        elif event.button() == Qt.MouseButton.RightButton:
            self._orbiting = False
        self._last_mouse_pos = None
        self._press_pos = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y() / 120.0
        self.camera.zoom(steps, self.config.zoom_sensitivity)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.scene.delete_selected()
        elif key == Qt.Key.Key_Space:
            self.scene.apply_random_impulse()
        elif key == Qt.Key.Key_P:
            self._placement_mode = not self._placement_mode
        elif key == Qt.Key.Key_F:
            self._free_camera = not self._free_camera
            self.camera.set_free_mode(self._free_camera)
            self.setWindowTitle(f"3D Physics Sandbox {'[Free Camera]' if self._free_camera else ''}")
        elif key == Qt.Key.Key_G:
            self.show_gizmo = not self.show_gizmo
        elif key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D, Qt.Key.Key_Q, Qt.Key.Key_E):
            self._pressed_keys.add(key)
            if not self._free_camera:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        self._pressed_keys.discard(event.key())
        super().keyReleaseEvent(event)

    def _update_free_camera_motion(self, dt: float) -> None:
        if not self._free_camera:
            return
        speed = 8.0
        amount = speed * dt
        if Qt.Key.Key_W in self._pressed_keys:
            self.camera.move_forward(amount)
        if Qt.Key.Key_S in self._pressed_keys:
            self.camera.move_forward(-amount)
        if Qt.Key.Key_A in self._pressed_keys:
            self.camera.move_right(-amount)
        if Qt.Key.Key_D in self._pressed_keys:
            self.camera.move_right(amount)
        if Qt.Key.Key_Q in self._pressed_keys:
            self.camera.move_up(-amount)
        if Qt.Key.Key_E in self._pressed_keys:
            self.camera.move_up(amount)

    # ------------------------------------------------------------------
    # Placement mode
    # ------------------------------------------------------------------

    def _set_place_mode(self, enabled: bool) -> None:
        self._placement_mode = enabled