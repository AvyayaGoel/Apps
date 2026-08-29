"""
rendering/renderer.py – now uses scale from RigidBody and improved selection highlight.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

import meshes
from body import RigidBody
from camera import OrbitCamera
from config import SimulationConfig
from gizmo import TransformGizmo
from math_utils import quat_to_matrix4, quat_from_axis_angle, normalize
from scene import Scene
from scenery import SceneryManager
from sky import SkyRenderer, sun_direction
from terrain import Terrain

logger = logging.getLogger(__name__)


class Renderer:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.sky = SkyRenderer(config)
        self.terrain = Terrain(config)
        self.scenery = SceneryManager(config)
        self.gizmo = TransformGizmo()

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

    def resize(self, width: int, height: int) -> None:
        height = max(1, height)
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

        self.scenery.draw_clouds()
        glEnable(GL_LIGHTING)

    def _draw_force_objects(self, scene: Scene, camera: OrbitCamera) -> None:
        for force in scene.world.force_objects:
            pos = force.get_world_position()
            if not self._is_force_visible_at(pos, camera):
                continue
            try:
                list_id = meshes.get_display_list("force", {"length": 0.8}, "force", scale=1.0)
                glPushMatrix()
                glTranslatef(*pos)
                up = normalize(force.direction)
                angle = np.arccos(np.clip(np.dot(up, [0, 1, 0]), -1, 1))
                if angle > 1e-6:
                    axis = normalize(np.cross([0, 1, 0], up))
                    q = quat_from_axis_angle(axis, angle)
                    glMultMatrixf(quat_to_matrix4(q))
                glColor3f(*force.color)
                glCallList(list_id)
                glPopMatrix()

                if force is scene.selected_force:
                    self._draw_force_selection_highlight(pos)
            except Exception as e:
                logger.exception(f"Failed to draw force object {id(force)}: {e}")

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
        for body in scene.world.bodies:
            if not self._is_visible(body, camera):
                continue
            list_id = meshes.get_display_list(body.shape, body.shape_params, body.object_kind, body.scale)
            glPushMatrix()
            glTranslatef(*body.position)
            glMultMatrixf(quat_to_matrix4(body.orientation))
            glColor3f(*body.color)
            glCallList(list_id)
            glPopMatrix()

            if body is scene.selected_body:
                if self.gizmo and scene.selected_body:
                    body = scene.selected_body
                    self.gizmo.draw(body)

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
        glVertex3f(-s, -s, -s);
        glVertex3f(s, -s, -s);
        glVertex3f(s, s, -s);
        glVertex3f(-s, s, -s)
        glEnd()
        glBegin(GL_LINE_LOOP)
        glVertex3f(-s, -s, s);
        glVertex3f(s, -s, s);
        glVertex3f(s, s, s);
        glVertex3f(-s, s, s)
        glEnd()
        glBegin(GL_LINES)
        glVertex3f(-s, -s, -s);
        glVertex3f(-s, -s, s)
        glVertex3f(s, -s, -s);
        glVertex3f(s, -s, s)
        glVertex3f(s, s, -s);
        glVertex3f(s, s, s)
        glVertex3f(-s, s, -s);
        glVertex3f(-s, s, s)
        glEnd()
        glPopMatrix()
        glPopAttrib()


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
