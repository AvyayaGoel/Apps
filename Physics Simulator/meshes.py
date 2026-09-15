"""
rendering/meshes.py – improved composite objects.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

import mesh as mesh_module

logger = logging.getLogger(__name__)
_quadric = None


def _get_quadric():
    global _quadric
    if _quadric is None:
        _quadric = gluNewQuadric()
        gluQuadricNormals(_quadric, GLU_SMOOTH)
    return _quadric


def draw_generic_mesh(m: "mesh_module.Mesh") -> None:
    """Draw an arbitrary mesh.Mesh (vertices/faces/normals) via immediate
    mode GL_TRIANGLES. This is the bridge between the generic Mesh-based
    geometry pipeline (mesh.py - used for physics/mass properties AND,
    via this function, rendering) and the renderer: any object kind with
    a "parts" recipe or a registered base primitive (see
    mesh.get_mesh_by_kind) renders from the exact same vertex/face data
    its physics is computed from, instead of a separate hand-written
    drawing function that can silently drift out of sync with it (which
    is precisely how several of the old geometry bugs happened - the car's
    wheels, the mug's handle, the dumbbell's disconnected parts, the
    pyramid's and torus's backface-culled gaps - two or three independent,
    disagreeing implementations of "what this object looks like"). This is
    still immediate-mode OpenGL, not the ModernGL/VBO pipeline called for
    by the redesign - see the project notes for that follow-up work - but
    it does mean there is now exactly one definition of each such
    object's shape, not several.

    If the mesh has per-vertex colors (see Mesh.colors - set when a
    "parts" recipe gives an individual part its own "color", e.g. a car's
    dark tires vs its red body), a vertex with a real (non-NaN) color gets
    its own glColor3f before being emitted; a vertex with no override
    (NaN) is left alone, so it just keeps whatever color was already
    active (normally the object's single base color, set once by the
    caller before this display list runs) - one recipe can freely mix
    "most of this object uses the base color" with "these specific parts
    are always this other color" without every single vertex needing an
    explicit entry.
    """
    vertices = m.vertices
    normals = m.normals if len(m.normals) == len(vertices) else None
    has_colors = len(m.colors) == len(vertices) and len(vertices) > 0
    glBegin(GL_TRIANGLES)
    try:
        for face in m.faces:
            for idx in face:
                if has_colors:
                    c = m.colors[idx]
                    if not np.isnan(c[0]):
                        glColor3f(*c)
                if normals is not None:
                    glNormal3f(*normals[idx])
                glVertex3f(*vertices[idx])
    finally:
        glEnd()


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


_display_list_cache: Dict[Tuple, int] = {}


def _build_shape_geometry(shape: str, shape_params: dict, object_kind: str, scale) -> None:
    glPushMatrix()
    try:
        if isinstance(scale, (int, float)):
            glScalef(scale, scale, scale)
        else:
            sx, sy, sz = scale
            glScalef(sx, sy, sz)

        # Generic path first: covers EVERY object with a "parts" recipe in
        # data/objects.json (car, cup, rocket, pyramid, well, dumbbell,
        # table, chair, stairs, ...) and every kind registered directly in
        # mesh.py's registry (torus, and the bare primitives), all through
        # the exact same, validated (see tests/test_mesh.py and
        # tests/test_parts_pipeline.py) mesh.py pipeline used for physics.
        # This is what replaced the old per-object immediate-mode
        # functions (_build_car, _build_cup, _build_pyramid, and the
        # separate _build_from_parts interpreter) - one geometry
        # definition per object, not a Python rendering path AND a
        # separate physics path that can silently drift apart (which is
        # exactly how several of the reported rendering bugs - the car's
        # wheels, the mug's handle, the dumbbell's disconnected parts, the
        # pyramid's and torus's backface-culled gaps - happened in the
        # first place).
        m = mesh_module.get_mesh_by_kind(object_kind)
        if m is not None:
            draw_generic_mesh(m)
            return

        # No registered/parts-based geometry for this kind - it's a bare
        # primitive (e.g. "cube", "ball", "wall": a plain box/sphere with
        # its own shape_params, not worth routing through the mesh
        # pipeline for). Draw it directly via the simple GLU-based
        # primitive functions.
        if shape == "sphere":
            draw_sphere(shape_params.get("radius", 0.5))
        elif shape == "box":
            draw_box(shape_params.get("half_extents", (0.4, 0.4, 0.4)))
        elif shape == "cylinder":
            draw_cylinder(shape_params.get("radius", 0.4), shape_params.get("height", 0.9))
        elif shape == "cone":
            draw_cone(shape_params.get("radius", 0.5), shape_params.get("height", 1.0))
        else:
            draw_sphere(shape_params.get("radius", 0.5))
    finally:
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


def _make_hashable(value):
    """Convert potentially unhashable values (like lists) to hashable equivalents (tuples)."""
    if isinstance(value, list):
        return tuple(_make_hashable(v) for v in value)
    elif isinstance(value, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in value.items()))
    else:
        return value


def get_display_list(shape: str, shape_params: dict, object_kind: str, scale=1.0) -> int:
    hashable_params = tuple(sorted((k, _make_hashable(v)) for k, v in shape_params.items()))
    hashable_scale = _make_hashable(list(scale)) if not isinstance(scale, (int, float)) else scale
    key = (object_kind, shape, hashable_params, hashable_scale)
    list_id = _display_list_cache.get(key)
    if list_id is not None:
        return list_id

    list_id = glGenLists(1)
    glNewList(list_id, GL_COMPILE)
    try:
        _build_shape_geometry(shape, shape_params, object_kind, scale)
    except Exception:
        logger.exception(
            f"Mesh builder failed for object_kind={object_kind!r} shape={shape!r} - "
            f"finishing the display list anyway so OpenGL isn't left stuck mid-compile"
        )
    finally:
        # glEndList() MUST run no matter what happened above. Leaving a
        # glNewList block open (e.g. because the builder raised) leaves the
        # GL context in "compiling a display list" state indefinitely - every
        # subsequent GL call anywhere in the app gets redirected into this
        # list instead of rendering normally, which can break or crash
        # completely unrelated drawing later in the same frame or session.
        glEndList()
    _display_list_cache[key] = list_id
    return list_id


def clear_cache() -> None:
    _display_list_cache.clear()