"""
rendering/gizmo.py

Transform gizmo for construction editing. It exposes translation arrows whose
origins sit on the selected object's local sides plus rotation rings around the
selected object's local axes.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

from math_utils import normalize, quat_from_axis_angle, quat_multiply, quat_rotate_vector, ray_plane_intersect, ray_sphere_intersect, vec3

_AXIS_COLORS = [(1.0, 0.12, 0.12), (0.15, 0.85, 0.15), (0.15, 0.35, 1.0)]
_LOCAL_AXES = [vec3(1, 0, 0), vec3(0, 1, 0), vec3(0, 0, 1)]


class TransformGizmo:
    def __init__(self):
        self.axis_length = 1.2
        self.cone_radius = 0.12
        self.cone_height = 0.25
        self.shaft_radius = 0.025
        self.hit_radius = 0.25
        self.ring_radius = 1.55
        self.ring_hit_radius = 0.18
        self.selected_axis: Optional[int] = None
        self.selected_mode: Optional[str] = None
        self.drag_axis = None
        self.drag_origin = None
        self.drag_start = None
        self.rotation_start_vector = None
        self.rotation_start_orientation = None

    def _axis_world(self, orientation, axis_index: int) -> np.ndarray:
        return normalize(quat_rotate_vector(orientation, _LOCAL_AXES[axis_index]))

    def _object_radius(self, body) -> float:
        return max(0.35, float(body.bounding_radius()))

    def draw(self, body):
        """Draw arrows from object sides and object-oriented rotation rings."""
        position = body.position
        orientation = body.orientation
        radius = self._object_radius(body)
        arrow_length = self.axis_length * max(0.75, body.scale)
        glPushAttrib(GL_ENABLE_BIT | GL_LINE_BIT | GL_CURRENT_BIT | GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)
        glLineWidth(2.0)

        q = gluNewQuadric()
        for i, color in enumerate(_AXIS_COLORS):
            axis = self._axis_world(orientation, i)
            start = position + axis * radius
            glColor3f(*color)
            self._draw_arrow(q, start, axis, arrow_length)
            self._draw_ring(position, orientation, i, radius * self.ring_radius)
        gluDeleteQuadric(q)
        glPopAttrib()

    def _draw_arrow(self, quadric, start, axis, length):
        end_shaft = start + axis * max(0.05, length - self.cone_height)
        glBegin(GL_LINES)
        glVertex3f(*start)
        glVertex3f(*end_shaft)
        glEnd()
        glPushMatrix()
        glTranslatef(*end_shaft)
        self._align_z_to_axis(axis)
        gluCylinder(quadric, self.cone_radius, 0.0, self.cone_height, 14, 1)
        glPopMatrix()

    def _draw_ring(self, position, orientation, axis_index: int, radius: float):
        axis = self._axis_world(orientation, axis_index)
        u = self._axis_world(orientation, (axis_index + 1) % 3)
        v = normalize(np.cross(axis, u))
        glBegin(GL_LINE_LOOP)
        for step in range(72):
            theta = 2.0 * math.pi * step / 72
            p = position + (math.cos(theta) * u + math.sin(theta) * v) * radius
            glVertex3f(*p)
        glEnd()

    @staticmethod
    def _align_z_to_axis(axis):
        axis = normalize(axis)
        z_axis = vec3(0, 0, 1)
        dot = float(np.clip(np.dot(z_axis, axis), -1.0, 1.0))
        if dot > 0.999:
            return
        if dot < -0.999:
            glRotatef(180.0, 1, 0, 0)
            return
        rot_axis = normalize(np.cross(z_axis, axis))
        angle = math.degrees(math.acos(dot))
        glRotatef(angle, *rot_axis)

    def pick(self, ray_origin, ray_dir, body) -> Tuple[Optional[Tuple[str, int]], Optional[np.ndarray]]:
        position = body.position
        orientation = body.orientation
        radius = self._object_radius(body)
        arrow_length = self.axis_length * max(0.75, body.scale)
        best_t = float("inf")
        best_handle = None
        best_hit = None

        for i in range(3):
            axis = self._axis_world(orientation, i)
            tip = position + axis * (radius + arrow_length)
            t = ray_sphere_intersect(ray_origin, ray_dir, tip, self.hit_radius * max(1.0, body.scale))
            if t is not None and t < best_t:
                best_t = t
                best_handle = ("translate", i)
                best_hit = ray_origin + ray_dir * t

            ring_hit = self._pick_ring(ray_origin, ray_dir, position, axis, radius * self.ring_radius)
            if ring_hit is not None:
                t_ring, hit = ring_hit
                if t_ring < best_t:
                    best_t = t_ring
                    best_handle = ("rotate", i)
                    best_hit = hit
        return best_handle, best_hit

    def _pick_ring(self, ray_origin, ray_dir, center, normal, radius):
        t = ray_plane_intersect(ray_origin, ray_dir, center, normal)
        if t is None:
            return None
        hit = ray_origin + ray_dir * t
        dist = float(np.linalg.norm(hit - center))
        if abs(dist - radius) <= self.ring_hit_radius * max(1.0, radius * 0.35):
            return t, hit
        return None

    def start_drag(self, handle, hit_point, body):
        mode, axis = handle
        self.selected_mode = mode
        self.selected_axis = axis
        self.drag_origin = body.position.copy()
        self.drag_axis = self._axis_world(body.orientation, axis)
        self.drag_start = hit_point
        self.rotation_start_orientation = body.orientation.copy()
        if mode == "rotate" and hit_point is not None:
            radial = hit_point - body.position
            radial = radial - np.dot(radial, self.drag_axis) * self.drag_axis
            self.rotation_start_vector = normalize(radial)
        else:
            self.rotation_start_vector = None

    def update_drag(self, ray_origin, ray_dir, body):
        if self.selected_axis is None or self.selected_mode != "translate":
            return None
        w0 = ray_origin - self.drag_origin
        a = np.dot(ray_dir, ray_dir)
        b = np.dot(ray_dir, self.drag_axis)
        c = np.dot(self.drag_axis, self.drag_axis)
        d = np.dot(ray_dir, w0)
        e = np.dot(self.drag_axis, w0)
        denom = a * c - b * b
        if abs(denom) < 1e-9:
            return None
        s = (b * e - c * d) / denom
        t = (a * e - b * d) / denom
        if s < 0:
            return None
        return self.drag_origin + t * self.drag_axis

    def update_rotation(self, ray_origin, ray_dir, body):
        if self.selected_axis is None or self.selected_mode != "rotate" or self.rotation_start_vector is None:
            return None
        t = ray_plane_intersect(ray_origin, ray_dir, body.position, self.drag_axis)
        if t is None:
            return None
        hit = ray_origin + ray_dir * t
        radial = hit - body.position
        radial = radial - np.dot(radial, self.drag_axis) * self.drag_axis
        if np.linalg.norm(radial) < 1e-9:
            return None
        current = normalize(radial)
        sin_angle = float(np.dot(np.cross(self.rotation_start_vector, current), self.drag_axis))
        cos_angle = float(np.clip(np.dot(self.rotation_start_vector, current), -1.0, 1.0))
        angle = math.atan2(sin_angle, cos_angle)
        delta = quat_from_axis_angle(self.drag_axis, angle)
        return quat_multiply(delta, self.rotation_start_orientation)
