"""
rendering/renderer.py – now uses scale from RigidBody and improved selection highlight.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

import meshes
import object_catalog
from body import RigidBody
from camera import OrbitCamera
from config import SimulationConfig
from constraints import HingeConstraint, RopeConstraint, SpringConstraint
from gizmo import TransformGizmo
from gpu_renderer import GPUMeshRenderer, perspective, look_at
from math_utils import quat_to_matrix4, quat_from_axis_angle, quat_rotate_vector, normalize
from scene import Scene
from scenery import SceneryManager
from sky import SkyRenderer, sun_direction
from terrain import Terrain
from tool_mode import ToolMode

logger = logging.getLogger(__name__)


class Renderer:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.sky = SkyRenderer(config)
        self.terrain = Terrain(config)
        self.scenery = SceneryManager(config)
        self.gizmo = TransformGizmo()
        # ModernGL GPU pipeline for body geometry (see gpu_renderer.py).
        # Created lazily in init_gl, once Qt has made a real GL context
        # current - constructing it here would attach to no context (or
        # the wrong one). Stays None if moderngl or a suitable context
        # isn't available, in which case body drawing transparently falls
        # back to the legacy display-list path, so the app still runs.
        self.gpu: Optional[GPUMeshRenderer] = None
        self._gpu_failed = False
        self._viewport = (1, 1)

    def init_gl(self) -> None:
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_NORMALIZE)
        glShadeModel(GL_SMOOTH)
        glClearColor(0.5, 0.7, 0.9, 1.0)
        self._init_gpu_renderer()

    def _init_gpu_renderer(self) -> None:
        """Attach a ModernGL context to the one Qt has already created and
        made current. Any failure here is non-fatal: `self.gpu` stays None
        and `_draw_bodies` uses the legacy path instead, so a machine
        without a modern-enough driver still gets a working (if slower)
        renderer rather than a black window."""
        if self._gpu_failed or self.gpu is not None:
            return
        if not getattr(self.config, "use_gpu_renderer", False):
            self._gpu_failed = True
            return
        try:
            self.gpu = GPUMeshRenderer()
            logger.info("ModernGL body renderer active")
        except Exception:
            self._gpu_failed = True
            self.gpu = None
            logger.exception("ModernGL unavailable - falling back to legacy display lists")

    def resize(self, width: int, height: int) -> None:
        height = max(1, height)
        self._viewport = (width, height)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = width / height
        gluPerspective(self.config.camera_fov_deg, aspect, self.config.camera_near, self.config.camera_far)
        glMatrixMode(GL_MODELVIEW)

    def update(self, dt: float) -> None:
        self.scenery.update(dt)

    def render(self, scene: Scene, camera: OrbitCamera) -> None:
        hours = scene.time_of_day
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        eye = camera.position()
        center = camera.look_at_point()
        up = camera.up()
        gluLookAt(eye[0], eye[1], eye[2], center[0], center[1], center[2], up[0], up[1], up[2])

        self._configure_lighting(hours)

        # Sky
        glPushMatrix()
        glTranslatef(eye[0], 0.0, eye[2])
        self.sky.draw(hours)
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)

        glEnable(GL_LIGHTING)
        self.terrain.draw_ground()
        self.terrain.draw_mountains()
        self.scenery.draw_rocks()
        self.scenery.draw_grass_tufts()
        self.scenery.draw_trees()
        self.terrain.draw_playing_surface_outline()

        self._draw_bodies(scene, camera)
        self._draw_force_objects(scene, camera)
        self._draw_constraints(scene)

        # Draw placement ghost if in placement mode
        self._draw_placement_ghost(scene)

        self.scenery.draw_clouds()
        glEnable(GL_LIGHTING)

    @staticmethod
    def _constraint_anchor_positions(con):
        """World positions of both anchor points - the exact same formula
        every constraint's solve() uses (body.position + rotated local
        anchor), so what's drawn always matches what's actually being
        solved. anchor_b/pos_b falls back to a fixed world point when
        body_b is None (anchored to the world)."""
        pos_a = con.body_a.position + quat_rotate_vector(con.body_a.orientation, con.anchor_a)
        if con.body_b is not None:
            pos_b = con.body_b.position + quat_rotate_vector(con.body_b.orientation, con.anchor_b)
        else:
            pos_b = con.anchor_b
        return pos_a, pos_b

    def _draw_constraints(self, scene: Scene) -> None:
        glPushAttrib(GL_ENABLE_BIT | GL_LINE_BIT | GL_CURRENT_BIT | GL_LIGHTING_BIT)
        try:
            glDisable(GL_LIGHTING)
            for con in scene.world.constraints:
                try:
                    pos_a, pos_b = self._constraint_anchor_positions(con)
                    dim = not con.enabled
                    if isinstance(con, SpringConstraint):
                        self._draw_spring(pos_a, pos_b, dim)
                    elif isinstance(con, RopeConstraint):
                        self._draw_rope(pos_a, pos_b, dim)
                    elif isinstance(con, HingeConstraint):
                        self._draw_hinge(pos_a, pos_b, con.axis, dim)
                    if con is scene.selected_constraint:
                        self._draw_secondary_selection_highlight((pos_a + pos_b) * 0.5, 0.15)
                except Exception:
                    logger.exception(f"Failed to draw constraint {id(con)}")
        finally:
            glPopAttrib()

    @staticmethod
    def _draw_spring(pos_a: np.ndarray, pos_b: np.ndarray, dim: bool) -> None:
        """Classic zigzag between the two anchors."""
        delta = pos_b - pos_a
        length = float(np.linalg.norm(delta))
        if length < 1e-6:
            return
        axis = delta / length
        up_ref = np.array([0.0, 1.0, 0.0]) if abs(axis[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        side = normalize(np.cross(axis, up_ref))
        coils = 10
        radius = 0.06
        glColor3f(*(0.4, 0.4, 0.42) if dim else (0.75, 0.75, 0.8))
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        glVertex3f(*pos_a)
        for i in range(1, coils):
            t = i / coils
            offset = side * (radius if i % 2 else -radius)
            glVertex3f(*(pos_a + axis * length * t + offset))
        glVertex3f(*pos_b)
        glEnd()

    @staticmethod
    def _draw_rope(pos_a: np.ndarray, pos_b: np.ndarray, dim: bool) -> None:
        glColor3f(*(0.35, 0.3, 0.2) if dim else (0.65, 0.5, 0.3))
        glLineWidth(2.5)
        glBegin(GL_LINES)
        glVertex3f(*pos_a)
        glVertex3f(*pos_b)
        glEnd()

    @staticmethod
    def _draw_hinge(pos_a: np.ndarray, pos_b: np.ndarray, axis: np.ndarray, dim: bool) -> None:
        pivot = (pos_a + pos_b) * 0.5
        glColor3f(*(0.4, 0.35, 0.15) if dim else (0.85, 0.7, 0.15))
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex3f(*pos_a)
        glVertex3f(*pivot)
        glVertex3f(*pivot)
        glVertex3f(*pos_b)
        glEnd()
        # Small ring around the pivot, perpendicular to the hinge axis, so
        # the axis of rotation is visible at a glance.
        ax = normalize(axis)
        up_ref = np.array([0.0, 1.0, 0.0]) if abs(ax[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = normalize(np.cross(ax, up_ref))
        v = normalize(np.cross(ax, u))
        glBegin(GL_LINE_LOOP)
        for step in range(24):
            theta = 2.0 * math.pi * step / 24
            p = pivot + (math.cos(theta) * u + math.sin(theta) * v) * 0.12
            glVertex3f(*p)
        glEnd()

    def _draw_force_objects(self, scene: Scene, camera: OrbitCamera) -> None:
        for force in scene.world.force_objects:
            pos = force.get_world_position()
            if not self._is_force_visible_at(pos, camera):
                continue
            glPushMatrix()
            try:
                list_id = meshes.get_display_list("force", {"length": 0.8}, "force", scale=1.0)
                glTranslatef(*pos)
                up = normalize(force.direction)
                angle = np.arccos(np.clip(np.dot(up, [0, 1, 0]), -1, 1))
                if angle > 1e-6:
                    axis = normalize(np.cross([0, 1, 0], up))
                    q = quat_from_axis_angle(axis, angle)
                    glMultMatrixf(quat_to_matrix4(q))
                glColor3f(*force.color)
                glCallList(list_id)
            except Exception as e:
                logger.exception(f"Failed to draw force object {id(force)}: {e}")
            finally:
                # Must always run - a skipped pop here permanently
                # imbalances the matrix stack, corrupting every subsequent
                # draw call for the rest of the session, not just this one.
                glPopMatrix()

            if force is scene.selected_force:
                try:
                    self._draw_force_selection_highlight(pos)
                except Exception:
                    logger.exception(f"Failed to draw selection highlight for force {id(force)}")

    @staticmethod
    def _is_force_visible_at(position, camera) -> bool:
        dist = np.linalg.norm(position - camera.position())
        return dist < 200.0

    def _configure_lighting(self, hours: float) -> None:
        ambient, sun_strength = self.sky.ambient_and_sun_intensity(hours)
        sx, sy, sz = sun_direction(hours)
        glLightfv(GL_LIGHT0, GL_POSITION, [sx, max(sy, 0.05), sz, 0.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [sun_strength, sun_strength, sun_strength * 0.95, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [ambient, ambient, ambient * 1.05, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.15, 0.15, 0.15, 1.0])

    def _is_visible(self, body: RigidBody, camera: OrbitCamera) -> bool:
        if not self.config.frustum_culling_enabled:
            return True
        to_body = body.position - camera.position()
        dist = float((to_body[0] ** 2 + to_body[1] ** 2 + to_body[2] ** 2) ** 0.5)
        if dist < 1e-6:
            return True
        forward = camera.forward()
        cos_angle = float((to_body[0] * forward[0] + to_body[1] * forward[1] + to_body[2] * forward[2]) / dist)
        half_fov_slack = math.cos(math.radians(self.config.camera_fov_deg * 0.75 + 15))
        margin = body.bounding_radius() / max(dist, 0.001)
        return cos_angle > (half_fov_slack - margin)

    def _draw_bodies(self, scene: Scene, camera: OrbitCamera) -> None:
        visible = [b for b in scene.world.bodies if self._is_visible(b, camera)]

        if self.gpu is not None:
            try:
                self._draw_bodies_gpu(visible, camera)
            except Exception:
                # A GPU-path failure must not take the whole frame down -
                # disable it for the rest of the session and continue with
                # the legacy path, so the user gets a working renderer
                # instead of an unusable window.
                logger.exception("ModernGL body drawing failed - reverting to legacy path")
                self.gpu = None
                self._gpu_failed = True
                self._draw_bodies_legacy(visible)
        else:
            self._draw_bodies_legacy(visible)

        # Selection decorations (gizmo / highlight) still use the legacy
        # immediate-mode path; they're a handful of lines and wires, not
        # the per-frame geometry cost the GPU pipeline exists to solve.
        for body in visible:
            if body is scene.selected_body:
                if self.gizmo and scene.selected_body:
                    body = scene.selected_body
                    try:
                        # getattr with a fallback, not scene.tool_mode
                        # directly: if this attribute is ever missing (e.g.
                        # a partially-applied update) this must not crash
                        # the whole render - it should just show both
                        # handles like it always used to.
                        mode = getattr(scene, "tool_mode", ToolMode.SELECT)
                        show_translate = mode in (ToolMode.SELECT, ToolMode.MOVE)
                        show_rotate = mode in (ToolMode.SELECT, ToolMode.ROTATE)
                        self.gizmo.draw(body, show_translate=show_translate, show_rotate=show_rotate)
                    except Exception:
                        logger.exception(f"Failed to draw gizmo for body {body.id}")
            elif body is scene.secondary_selected_body:
                self._draw_secondary_selection_highlight(body.position, body.bounding_radius())

    def _draw_bodies_gpu(self, bodies, camera: OrbitCamera) -> None:
        """Draw every body through the ModernGL pipeline: one cached
        vertex/index buffer per distinct mesh, one draw call per body,
        with position/orientation/scale/color supplied as uniforms."""
        width, height = self._viewport
        proj = perspective(self.config.camera_fov_deg, width / max(1, height),
                           self.config.camera_near, self.config.camera_far)
        view = look_at(camera.position(), camera.look_at_point(), camera.up())
        self.gpu.set_camera(proj, view)

        # The legacy fixed-function state (lighting, color material, the
        # matrix stacks) doesn't apply to shader-based drawing, and leaving
        # GL_LIGHTING enabled while a program is bound is harmless but
        # pointless - what does matter is restoring whatever the
        # immediate-mode passes around this one expect afterwards.
        glDisable(GL_LIGHTING)
        try:
            for body in bodies:
                mesh_obj = body.mesh
                if mesh_obj is None or len(mesh_obj.faces) == 0:
                    continue
                self.gpu.draw(
                    mesh_obj,
                    body.position,
                    body.get_rotation_matrix(),
                    body.scale,
                    body.color,
                )
        finally:
            glEnable(GL_LIGHTING)

    def _draw_bodies_legacy(self, bodies) -> None:
        """Original immediate-mode/display-list drawing, kept as a fallback
        for environments where ModernGL can't be initialized."""
        for body in bodies:
            glPushMatrix()
            try:
                list_id = meshes.get_display_list(body.shape, body.shape_params, body.object_kind, tuple(body.scale))
                glTranslatef(*body.position)
                glMultMatrixf(quat_to_matrix4(body.orientation))
                glColor3f(*body.color)
                glCallList(list_id)
            except Exception:
                logger.exception(f"Failed to draw body {body.id} (kind={body.object_kind!r})")
            finally:
                # glPopMatrix must run no matter what, or a failure here
                # leaves the matrix stack permanently imbalanced - which
                # would corrupt every other body's rendering for the rest
                # of the session, not just this one's.
                glPopMatrix()

    @staticmethod
    def _draw_secondary_selection_highlight(position: np.ndarray, radius: float) -> None:
        """Marks the 'Body B' pick for constraint creation (section 10:
        attachment/detachment should be visible, not just implied)."""
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_LINE_BIT | GL_CURRENT_BIT)
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glColor3f(0.7, 0.3, 1.0)
        glLineWidth(2.0)
        s = max(0.4, radius * 1.1)
        glPushMatrix()
        glTranslatef(*position)
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, -s)
        glVertex3f(s, -s, -s)
        glVertex3f(s, s, -s)
        glVertex3f(-s, s, -s)
        glEnd()
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, s)
        glVertex3f(s, -s, s)
        glVertex3f(s, s, s)
        glVertex3f(-s, s, s)
        glEnd()
        glBegin(GL_LINES)
        glVertex3f(-s, -s, -s)
        glVertex3f(-s, -s, s)
        glVertex3f(s, -s, -s)
        glVertex3f(s, -s, s)
        glVertex3f(s, s, -s)
        glVertex3f(s, s, s)
        glVertex3f(-s, s, -s)
        glVertex3f(-s, s, s)
        glEnd()
        glPopMatrix()
        glPopAttrib()

    @staticmethod
    def _draw_force_selection_highlight(position: np.ndarray) -> None:
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_LINE_BIT | GL_CURRENT_BIT)
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glColor3f(1.0, 0.85, 0.15)
        glLineWidth(2.0)
        s = 0.6
        glPushMatrix()
        glTranslatef(*position)
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, -s)
        glVertex3f(s, -s, -s)
        glVertex3f(s, s, -s)
        glVertex3f(-s, s, -s)
        glEnd()
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, s)
        glVertex3f(s, -s, s)
        glVertex3f(s, s, s)
        glVertex3f(-s, s, s)
        glEnd()
        glBegin(GL_LINES)
        glVertex3f(-s, -s, -s)
        glVertex3f(-s, -s, s)
        glVertex3f(s, -s, -s)
        glVertex3f(s, -s, s)
        glVertex3f(s, s, -s)
        glVertex3f(s, s, s)
        glVertex3f(-s, s, -s)
        glVertex3f(-s, s, s)
        glEnd()
        glPopMatrix()
        glPopAttrib()

    def _draw_placement_ghost(self, scene: Scene) -> None:
        """Draw a semi-transparent ghost of the object to be placed at the mouse position."""
        if scene.tool_mode is not ToolMode.PLACE:
            return

        mouse_pos_3d = scene.place_cursor_pos
        if mouse_pos_3d is None:
            return

        kind = scene.place_object_kind or scene.last_placed_kind
        if kind is None:
            return

        # Get shape info for the ghost
        try:
            obj_data = object_catalog.CATALOG.get(kind)
            if obj_data is None:
                return

            shape = obj_data.shape
            shape_params = obj_data.shape_params.copy()
            # Ghost must be the SAME size as the object that actually gets
            # spawned (a previous version rendered it at an arbitrary 0.7x
            # "preview" scale, silently different from the real object) -
            # scale is otherwise always 1.0 at spawn time (set_scale is a
            # post-placement edit), so match that directly.
            scale = 1.0

            # Ground placement for the ghost must use the exact same logic
            # as the real spawn (Scene.place_at -> RigidBody.place_on_ground),
            # not a separate approximation - otherwise the ghost and the
            # actual placed object can disagree, and either (or both) can
            # end up partially underground. Build a throwaway body purely to
            # read its real, mesh-derived ground clearance; it is never
            # added to the world.
            ghost_body = object_catalog.spawn(kind, position=mouse_pos_3d)
            ground_y = float(mouse_pos_3d[1])
            draw_pos = (
                float(mouse_pos_3d[0]),
                ground_y + ghost_body.ground_clearance(),
                float(mouse_pos_3d[2]),
            )

            glPushMatrix()
            try:
                glDisable(GL_LIGHTING)
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glColor4f(0.3, 0.8, 0.3, 0.4)  # Semi-transparent green

                list_id = meshes.get_display_list(shape, shape_params, kind, scale)
                glTranslatef(*draw_pos)
                glCallList(list_id)
                
                # Draw a small indicator ring on the ground
                glColor4f(0.3, 0.8, 0.3, 0.6)
                glLineWidth(2.0)
                radius = 0.3
                glBegin(GL_LINE_LOOP)
                for i in range(32):
                    theta = 2.0 * math.pi * i / 32
                    x = math.cos(theta) * radius
                    z = math.sin(theta) * radius
                    glVertex3f(x, 0.0, z)
                glEnd()
            finally:
                glDisable(GL_BLEND)
                glEnable(GL_LIGHTING)
                glPopMatrix()
        except Exception as e:
            logger.exception(f"Failed to draw placement ghost: {e}")


def _draw_wire_sphere(radius: float, meridians: int = 12, parallels: int = 8) -> None:
    for i in range(meridians):
        theta = 2.0 * np.pi * i / meridians
        glBegin(GL_LINE_LOOP)
        for j in range(parallels * 2):
            phi = np.pi * j / (parallels * 2)
            x = radius * np.cos(theta) * np.sin(phi)
            y = radius * np.cos(phi)
            z = radius * np.sin(theta) * np.sin(phi)
            glVertex3f(x, y, z)
        glEnd()
    for j in range(1, parallels):
        phi = np.pi * j / parallels
        y = radius * np.cos(phi)
        r = radius * np.sin(phi)
        glBegin(GL_LINE_LOOP)
        for i in range(32):
            theta = 2.0 * np.pi * i / 32
            glVertex3f(r * np.cos(theta), y, r * np.sin(theta))
        glEnd()