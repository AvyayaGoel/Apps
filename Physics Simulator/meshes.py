"""
rendering/meshes.py – improved composite objects.
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

from math_utils import normalize

_quadric = None


def _get_quadric():
    global _quadric
    if _quadric is None:
        _quadric = gluNewQuadric()
        gluQuadricNormals(_quadric, GLU_SMOOTH)
    return _quadric


# ----------------------------------------------------------------------
# Base primitives
# ----------------------------------------------------------------------

def draw_sphere(radius: float = 0.5, slices: int = 20, stacks: int = 16) -> None:
    gluSphere(_get_quadric(), radius, slices, stacks)


def draw_box(half_extents: Tuple[float, float, float] = (0.4, 0.4, 0.4)) -> None:
    hx, hy, hz = half_extents
    faces = [
        ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
        ((0, 0, -1), [(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)]),
        ((0, 1, 0), [(-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz)]),
        ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
        ((1, 0, 0), [(hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz)]),
        ((-1, 0, 0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)]),
    ]
    glBegin(GL_QUADS)
    for normal, corners in faces:
        glNormal3f(*normal)
        for c in corners:
            glVertex3f(*c)
    glEnd()


def draw_cylinder(radius: float = 0.4, height: float = 0.9, slices: int = 24,
                  top: bool = True, bottom: bool = True) -> None:
    q = _get_quadric()
    glPushMatrix()
    glTranslatef(0, -height * 0.5, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(q, radius, radius, height, slices, 1)
    if top:
        glPushMatrix()
        glTranslatef(0, 0, height)
        gluDisk(q, 0, radius, slices, 1)
        glPopMatrix()
    if bottom:
        glRotatef(180, 1, 0, 0)
        gluDisk(q, 0, radius, slices, 1)
    glPopMatrix()


def draw_cone(radius: float = 0.5, height: float = 1.0, slices: int = 22) -> None:
    q = _get_quadric()
    glPushMatrix()
    glTranslatef(0, -height * 0.5, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(q, radius, 0.0, height, slices, 1)
    glRotatef(180, 1, 0, 0)
    gluDisk(q, 0, radius, slices, 1)
    glPopMatrix()


def draw_torus(radius: float = 0.5, tube_radius: float = 0.18, sides: int = 16, rings: int = 24) -> None:
    import math
    for i in range(rings):
        theta1 = 2 * math.pi * i / rings
        theta2 = 2 * math.pi * (i + 1) / rings
        glBegin(GL_QUAD_STRIP)
        for j in range(sides + 1):
            phi = 2 * math.pi * j / sides
            for theta in (theta1, theta2):
                cx, cz = math.cos(theta), math.sin(theta)
                nx = math.cos(phi) * cx
                ny = math.sin(phi)
                nz = math.cos(phi) * cz
                x = (radius + tube_radius * math.cos(phi)) * cx
                y = tube_radius * math.sin(phi)
                z = (radius + tube_radius * math.cos(phi)) * cz
                glNormal3f(nx, ny, nz)
                glVertex3f(x, y, z)
        glEnd()


# ----------------------------------------------------------------------
# Composite builders
# ----------------------------------------------------------------------

def _build_cup():
    """A realistic cup: thin-walled cylinder, open top, with a handle."""
    q = _get_quadric()
    radius = 0.3
    height = 0.5
    thickness = 0.03
    # Outer wall
    glPushMatrix()
    glTranslatef(0, -height * 0.5, 0)
    glRotatef(-90, 1, 0, 0)
    # Outer cylinder with top and bottom disks
    gluCylinder(q, radius, radius, height, 24, 1)
    # Bottom disk
    glRotatef(180, 1, 0, 0)
    gluDisk(q, 0, radius, 24, 1)
    glPopMatrix()
    # Inner wall (hollow) - draw inverted normals? We'll just draw a smaller cylinder with reversed normals.
    glPushMatrix()
    glTranslatef(0, -height * 0.5, 0)
    glRotatef(90, 1, 0, 0)  # invert normals by rotating 180? Use gluQuadricOrientation
    q_inner = gluNewQuadric()
    gluQuadricOrientation(q_inner, GLU_INSIDE)
    gluCylinder(q_inner, radius - thickness, radius - thickness, height, 24, 1)
    # Bottom inner disk
    glRotatef(180, 1, 0, 0)
    gluDisk(q_inner, 0, radius - thickness, 24, 1)
    gluDeleteQuadric(q_inner)
    glPopMatrix()
    # Rim (a torus at top)
    glPushMatrix()
    glTranslatef(0, height * 0.5, 0)
    draw_torus(radius=radius - thickness * 0.5, tube_radius=thickness * 1.5, sides=8, rings=16)
    glPopMatrix()
    # Handle: a torus on the side
    glPushMatrix()
    glTranslatef(radius + 0.02, 0.0, 0.0)
    glRotatef(90, 0, 1, 0)
    draw_torus(radius=0.14, tube_radius=0.035, sides=8, rings=16)
    glPopMatrix()


def _build_table():
    half_h, half_w, half_d = 1.0, 0.45, 0.6
    top_half_thickness = 0.05
    top_center_y = half_w - top_half_thickness
    leg_height = half_w + top_center_y - top_half_thickness
    leg_center_y = -half_w + leg_height * 0.5
    leg_radius = 0.06

    # Table top
    glPushMatrix()
    glTranslatef(0, top_center_y, 0)
    draw_box(half_extents=(half_h, top_half_thickness, half_d))
    glPopMatrix()

    # Four legs
    for sx in (-1, 1):
        for sz in (-1, 1):
            glPushMatrix()
            glTranslatef(sx * (half_h - 0.15), leg_center_y, sz * (half_d - 0.1))
            draw_cylinder(radius=leg_radius, height=leg_height, slices=10)
            glPopMatrix()


def _build_car():
    # Car body
    draw_box(half_extents=(0.8, 0.3, 0.45))
    # Cabin
    glPushMatrix()
    glTranslatef(-0.1, 0.32, 0)
    draw_box(half_extents=(0.35, 0.22, 0.38))
    glPopMatrix()
    # Wheels - larger and protruding below body
    glColor3f(0.08, 0.08, 0.08)
    wheel_positions = [
        (-0.55, -0.28, 0.52),  # front-left
        (0.55, -0.28, 0.52),  # front-right
        (-0.55, -0.28, -0.52),  # rear-left
        (0.55, -0.28, -0.52)  # rear-right
    ]
    for wx, wy, wz in wheel_positions:
        glPushMatrix()
        glTranslatef(wx, wy, wz)
        glRotatef(90, 0, 1, 0)
        draw_cylinder(radius=0.22, height=0.15, slices=16)
        glPopMatrix()


def _build_ramp():
    hx, hy, hz = 1.2, 0.15, 1.6
    glBegin(GL_TRIANGLES)
    glNormal3f(0, 0.5, -0.87)
    top_back = (-hx, hy, -hz)
    top_front_low = (-hx, -hy, hz)
    top_front_low2 = (hx, -hy, hz)
    top_back2 = (hx, hy, -hz)
    for tri in ((top_back, top_front_low, top_front_low2), (top_back, top_front_low2, top_back2)):
        for v in tri:
            glVertex3f(*v)
    glEnd()
    glBegin(GL_QUADS)
    glNormal3f(0, -1, 0)
    glVertex3f(-hx, -hy, -hz)
    glVertex3f(hx, -hy, -hz)
    glVertex3f(hx, -hy, hz)
    glVertex3f(-hx, -hy, hz)
    glNormal3f(0, 0, -1)
    glVertex3f(-hx, -hy, -hz)
    glVertex3f(-hx, hy, -hz)
    glVertex3f(hx, hy, -hz)
    glVertex3f(hx, -hy, -hz)
    glEnd()
    glBegin(GL_TRIANGLES)
    glNormal3f(-1, 0, 0)
    glVertex3f(-hx, -hy, -hz)
    glVertex3f(-hx, -hy, hz)
    glVertex3f(-hx, hy, -hz)
    glNormal3f(1, 0, 0)
    glVertex3f(hx, -hy, -hz)
    glVertex3f(hx, hy, -hz)
    glVertex3f(hx, -hy, hz)
    glEnd()


def _build_pyramid():
    # A four-sided pyramid (square base)
    half = 0.5
    height = 1.0
    # base vertices
    base = [(-half, -height / 2, -half), (half, -height / 2, -half), (half, -height / 2, half),
            (-half, -height / 2, half)]
    apex = (0, height / 2, 0)
    # draw 4 triangles for sides
    glBegin(GL_TRIANGLES)
    for i in range(4):
        p1 = base[i]
        p2 = base[(i + 1) % 4]
        # compute normal
        edge1 = np.array(p2) - np.array(p1)
        edge2 = np.array(apex) - np.array(p1)
        normal = normalize(np.cross(edge1, edge2))
        glNormal3f(*normal)
        glVertex3f(*p1)
        glVertex3f(*p2)
        glVertex3f(*apex)
    glEnd()

    # bottom face
    glBegin(GL_QUADS)
    glNormal3f(0, -1, 0)
    for v in reversed(base):
        glVertex3f(*v)
    glEnd()


KIND_BUILDERS: Dict[str, Callable[..., None]] = {
    "cup": _build_cup,
    "table": _build_table,
    "car": _build_car,
    "ramp": _build_ramp,
    "force": lambda: draw_force_arrow(),
    "pyramid": _build_pyramid,
}

_display_list_cache: Dict[Tuple, int] = {}


def _build_shape_geometry(shape: str, shape_params: dict, object_kind: str, scale: float) -> None:
    glPushMatrix()
    glScalef(scale, scale, scale)
    builder = KIND_BUILDERS.get(object_kind)
    if builder is not None:
        builder()
        glPopMatrix()
        return
    if object_kind == "torus":
        draw_torus(shape_params.get("radius", 0.5), shape_params.get("tube_radius", 0.18))
    elif shape == "sphere":
        draw_sphere(shape_params.get("radius", 0.5))
    elif shape == "box":
        draw_box(shape_params.get("half_extents", (0.4, 0.4, 0.4)))
    elif shape == "cylinder":
        draw_cylinder(shape_params.get("radius", 0.4), shape_params.get("height", 0.9))
    elif shape == "cone":
        draw_cone(shape_params.get("radius", 0.5), shape_params.get("height", 1.0))
    else:
        draw_sphere(shape_params.get("radius", 0.5))
    glPopMatrix()


def draw_force_arrow(length: float = 0.8, head_length: float = 0.25,
                     head_radius: float = 0.15, shaft_radius: float = 0.04) -> None:
    q = _get_quadric()
    glPushMatrix()
    glTranslatef(0, -length * 0.5, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(q, shaft_radius, shaft_radius, length - head_length, 8, 1)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(0, length * 0.5 - head_length, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(q, head_radius, 0.0, head_length, 12, 1)
    glPopMatrix()


def get_display_list(shape: str, shape_params: dict, object_kind: str, scale: float = 1.0) -> int:
    key = (object_kind, shape, tuple(sorted(shape_params.items())), scale)
    list_id = _display_list_cache.get(key)
    if list_id is not None:
        return list_id

    list_id = glGenLists(1)
    glNewList(list_id, GL_COMPILE)
    _build_shape_geometry(shape, shape_params, object_kind, scale)
    glEndList()
    _display_list_cache[key] = list_id
    return list_id


def clear_cache() -> None:
    _display_list_cache.clear()
