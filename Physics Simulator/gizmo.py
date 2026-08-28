"""
rendering/gizmo.py

Simple 3D translate gizmo (arrows + cones) for moving objects along axes.
"""

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

from math_utils import ray_sphere_intersect


class TransformGizmo:
    def __init__(self):
        self.axis_length = 1.2
        self.cone_radius = 0.12
        self.cone_height = 0.25
        self.shaft_radius = 0.025
        self.hit_radius = 0.3  # for picking
        self.selected_axis = None  # 0,1,2 for X,Y,Z
        self.drag_start = None
        self.drag_axis = None
        self.drag_origin = None

    def draw(self, position, orientation, scale=1.0):
        """Draw the gizmo at the given position and orientation."""
        glPushMatrix()
        glTranslatef(*position)
        # Apply rotation from object orientation? We want axes aligned to world, not object.
        # We'll draw in world orientation by not applying object rotation.
        glScalef(scale, scale, scale)
        colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        axes = [np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])]
        for i, axis in enumerate(axes):
            glColor3f(*colors[i])
            glPushMatrix()
            # Rotate to align with axis
            if i == 0:
                pass  # already X
            elif i == 1:
                glRotatef(90, 0, 0, 1)
            else:
                glRotatef(-90, 0, 1, 0)
            # Shaft
            q = gluNewQuadric()
            gluCylinder(q, self.shaft_radius, self.shaft_radius, self.axis_length - self.cone_height, 8, 1)
            glTranslatef(0, 0, self.axis_length - self.cone_height)
            # Cone
            gluCylinder(q, self.cone_radius, 0.0, self.cone_height, 12, 1)
            gluDeleteQuadric(q)
            glPopMatrix()
        glPopMatrix()

    def pick(self, ray_origin, ray_dir, position, orientation, scale=1.0):
        """Check if the ray hits any axis arrow. Returns (axis_index, hit_point) or None."""
        best_t = float('inf')
        best_axis = None
        best_hit = None
        # For each axis, we approximate as a capsule (cylinder + hemisphere caps) but for simplicity,
        # we'll use ray-sphere intersection for the cone and cylinder as a thick line.
        # We'll test a sphere at the tip and a cylinder along the shaft.
        # More robust: test a cylinder.
        # We'll use a simple approach: test a sphere at the tip with radius = hit_radius.
        tip_positions = [position + axis * self.axis_length * scale for axis in
                         [np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])]]
        for i, tip in enumerate(tip_positions):
            t = ray_sphere_intersect(ray_origin, ray_dir, tip, self.hit_radius * scale)
            if t is not None and t < best_t:
                best_t = t
                best_axis = i
                best_hit = ray_origin + ray_dir * t
        return best_axis, best_hit

    def start_drag(self, axis, hit_point, object_pos):
        self.selected_axis = axis
        self.drag_axis = [np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])][axis]
        self.drag_origin = object_pos
        self.drag_start = hit_point

    def update_drag(self, ray_origin, ray_dir, object_pos):
        """Compute new position along the axis based on mouse ray."""
        if self.selected_axis is None:
            return None
        # Project ray onto the axis line passing through the drag_origin
        # We'll find the point on the axis line closest to the ray.
        # Axis line: P = drag_origin + t * drag_axis
        # Ray: R = ray_origin + s * ray_dir
        # Solve for t and s.
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
        if s < 0:  # behind camera
            return None
        hit_world = ray_origin + s * ray_dir
        # Project onto axis line to get new position
        proj = self.drag_origin + t * self.drag_axis
        return proj
