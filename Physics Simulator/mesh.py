"""
mesh.py - procedural geometry generators and the data-driven object
geometry pipeline.

Layering (see geometry.py for why): this module imports downward from
`geometry` (the shared Mesh core) and from `mesh_io` (file loading), and
is itself imported by body.py / object_catalog.py / renderer.py. Every
import is at the top of the file; there are no function-local imports
anywhere in this project's geometry stack.

The central idea is that this module knows about SHAPES, never about
OBJECTS. There is no "car" code path, no "mug" code path, and no fixed
list of supported objects anywhere below. Instead:

  * `PART_SHAPE_BUILDERS` maps a shape name to a builder function. The
    built-in entries (box, sphere, cylinder, cone, torus, wedge, disc,
    annulus, file) are just the ones that ship by default -
    `register_part_shape()` adds more at runtime, and a new shape needs
    no edit to any dispatch logic.

  * `build_mesh_from_parts()` turns a plain-data recipe (a list of
    {shape, transform, ...} dicts) into one merged Mesh. This is how
    every composite object in the catalog is defined - as data, not code.

  * `register_parts_recipe()` / `register_mesh_builder()` associate an
    object *kind* with geometry. object_catalog.py calls the former for
    every entry in data/objects.json at load time; an importer or a
    future in-app shape editor calls it for user-created geometry. This
    module never reads the catalog itself, which is what keeps
    object_catalog -> body -> mesh acyclic.

The practical consequence: an arbitrary user-supplied shape - a JSON
recipe they built, an OBJ they dragged in, or output from a generator
that doesn't exist yet - flows through exactly the same path as a
built-in cube. Nothing downstream (mass properties, collision, placement,
rendering) can tell the difference, because there is no difference.
"""
from __future__ import annotations

import logging
import math
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from geometry import (
    Mesh,
    ensure_outward_winding,
    flip_winding,
    merge_meshes,
    translate_mesh,
    rotate_mesh_x,
    rotate_mesh_y,
    rotate_mesh_z,
)
from mesh_io import load_mesh_file

logger = logging.getLogger(__name__)

# ============================================================================
# Primitive mesh generators
# ============================================================================

def create_box_mesh(half_extents: Tuple[float, float, float] = (0.5, 0.5, 0.5)) -> Mesh:
    """Generate a box mesh with given half-extents."""
    hx, hy, hz = half_extents

    # 8 vertices
    vertices = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ], dtype=np.float64)

    # 12 triangles (2 per face)
    faces = np.array([
        [0, 1, 2], [0, 2, 3],  # back
        [5, 4, 7], [5, 7, 6],  # front
        [4, 0, 3], [4, 3, 7],  # left
        [1, 5, 6], [1, 6, 2],  # right
        [3, 2, 6], [3, 6, 7],  # top
        [4, 5, 1], [4, 1, 0],  # bottom
    ], dtype=np.int32)

    mesh = Mesh(vertices=vertices, faces=faces)
    return ensure_outward_winding(mesh)


def create_sphere_mesh(radius: float = 0.5, subdivisions: int = 3) -> Mesh:
    """Generate a sphere mesh using icosphere subdivision."""
    # Start with icosahedron
    phi = (1 + math.sqrt(5)) / 2

    vertices = np.array([
        [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
        [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
        [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1],
    ], dtype=np.float64)

    # Normalize to unit sphere
    vertices /= np.linalg.norm(vertices, axis=1, keepdims=True)

    faces = np.array([
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ], dtype=np.int32)

    # Subdivide
    for _ in range(subdivisions):
        new_faces = []
        edge_midpoints: Dict[Tuple[int, int], int] = {}
        new_vertices = list(vertices)

        for face in faces:
            mid = []
            for i in range(3):
                e0, e1 = int(face[i]), int(face[(i + 1) % 3])
                edge = (min(e0, e1), max(e0, e1))

                if edge not in edge_midpoints:
                    v0 = new_vertices[e0]
                    v1 = new_vertices[e1]
                    midpoint = (v0 + v1) / 2
                    midpoint /= np.linalg.norm(midpoint)
                    edge_midpoints[edge] = len(new_vertices)
                    new_vertices.append(midpoint)

                mid.append(edge_midpoints[edge])

            # Create 4 new faces
            new_faces.append([face[0], mid[0], mid[2]])
            new_faces.append([face[1], mid[1], mid[0]])
            new_faces.append([face[2], mid[2], mid[1]])
            new_faces.append([mid[0], mid[1], mid[2]])

        vertices = np.array(new_vertices, dtype=np.float64)
        faces = np.array(new_faces, dtype=np.int32)

    # Scale to radius
    vertices *= radius

    mesh = Mesh(vertices=vertices, faces=faces)
    return ensure_outward_winding(mesh)


def create_cylinder_mesh(radius: float = 0.4, height: float = 0.9,
                         segments: int = 24, cap_top: bool = True,
                         cap_bottom: bool = True) -> Mesh:
    """Generate a cylinder mesh."""
    vertices = []
    faces = []

    half_h = height / 2

    # Side vertices: pairs of (bottom, top) for each segment
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        x = radius * math.cos(theta)
        z = radius * math.sin(theta)
        vertices.append([x, -half_h, z])  # bottom vertex (even index)
        vertices.append([x, half_h, z])   # top vertex (odd index)

    # Side faces
    for i in range(segments):
        next_i = (i + 1) % segments
        base = i * 2
        next_base = next_i * 2
        faces.append([base, next_base, next_base + 1])
        faces.append([base, next_base + 1, base + 1])

    # Top cap - uses odd-indexed vertices (1, 3, 5, ...)
    if cap_top:
        center_idx = len(vertices)
        vertices.append([0, half_h, 0])
        for i in range(segments):
            next_i = (i + 1) % segments
            # Top ring vertices are at indices 1, 3, 5, ... = 2*i + 1
            v0 = 2 * i + 1
            v1 = 2 * next_i + 1
            faces.append([center_idx, v0, v1])

    # Bottom cap - uses even-indexed vertices (0, 2, 4, ...)
    if cap_bottom:
        center_idx = len(vertices)
        vertices.append([0, -half_h, 0])
        for i in range(segments):
            next_i = (i + 1) % segments
            # Bottom ring vertices are at indices 0, 2, 4, ... = 2*i
            # NOTE: order is (v1, v0, center) rather than (v0, v1, center).
            # The top cap uses (center, v0, v1) walking the ring in
            # increasing-theta order; a bottom cap facing the opposite way
            # needs the *reversed* traversal order, or its winding ends up
            # identical (in cyclic terms) to the top cap's instead of
            # opposite. Getting this wrong doesn't show up in a naive
            # undirected edge-count "is it closed" check - both caps still
            # each individually look like a valid fan - it only shows up as
            # a wrong (or exactly-cancelled) volume/inertia integral and
            # inside-out face normals. See test_mesh.py::test_cylinder_volume.
            v0 = 2 * i
            v1 = 2 * next_i
            faces.append([v1, v0, center_idx])

    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)

    mesh = Mesh(vertices=vertices, faces=faces)
    return ensure_outward_winding(mesh)


def create_wedge_mesh(half_extents: Tuple[float, float, float] = (1.0, 0.15, 1.0)) -> Mesh:
    """
    Generate a wedge/ramp mesh: a triangular prism with a right-triangle
    cross-section (flat bottom, vertical back, sloped top from back-high
    to front-low), extruded along X. This is a genuine new PRIMITIVE type
    (alongside box/sphere/cylinder/cone/torus) rather than a one-off
    "ramp" builder - any object needing a wedge-shaped part (a ramp, a
    doorstop, a roof section, ...) can use it, so a physical ramp object
    is just a single "wedge" part in a JSON recipe, not bespoke code (see
    data/objects.json's "ramp" entry).

    half_extents = (hx, hy, hz): hx is the half-length along the extrusion
    axis (X), hy is the full height of the vertical back edge, hz is the
    half-depth from the back edge to the front (lowest) edge.

    Winding for every face verified numerically against the true outward
    direction (see the wedge winding derivation in the redesign notes) -
    each candidate ordering was checked by computing the winding-implied
    normal and comparing it against the geometric outward direction from
    the wedge's centroid, since guessing triangle vertex order by eye is
    exactly how the pyramid and torus winding bugs happened in the first
    place.
    """
    hx, hy, hz = half_extents
    v0 = np.array([-hx, -hy, -hz])  # left,  bottom, back
    v1 = np.array([-hx, hy, -hz])  # left,  top,    back
    v2 = np.array([-hx, -hy, hz])  # left,  bottom, front
    v3 = np.array([hx, -hy, -hz])  # right, bottom, back
    v4 = np.array([hx, hy, -hz])  # right, top,    back
    v5 = np.array([hx, -hy, hz])  # right, bottom, front
    vertices = np.array([v0, v1, v2, v3, v4, v5], dtype=np.float64)
    faces = np.array([
        [0, 2, 1],  # left end cap (-X)
        [3, 4, 5],  # right end cap (+X)
        [0, 3, 5], [0, 5, 2],  # bottom (-Y)
        [0, 1, 4], [0, 4, 3],  # back (-Z, vertical)
        [2, 4, 1], [2, 5, 4],  # sloped top/front face
    ], dtype=np.int32)
    mesh = Mesh(vertices=vertices, faces=faces)
    return ensure_outward_winding(mesh)


def create_cone_mesh(radius: float = 0.5, height: float = 1.0,
                     segments: int = 24, cap_base: bool = True) -> Mesh:
    """Generate a cone mesh. cap_base=False omits the flat base disc, for
    use as an open component (e.g. a nose cone welded directly onto a
    cylinder's open top - if both the cylinder's top boundary *and* the
    cone's own base cap were present, the shared ring would end up used by
    3 faces instead of 2: manifold, but non-manifold in the strict sense
    that only 2 faces may share an edge. ensure_outward_winding is skipped
    when cap_base=False since the resulting open surface's "signed volume"
    is not a reliable outward/inward indicator - see test_mesh.py)."""
    vertices = []
    faces = []

    half_h = height / 2

    # Apex vertex
    apex_idx = 0
    vertices.append([0, half_h, 0])

    # Base ring vertices
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        x = radius * math.cos(theta)
        z = radius * math.sin(theta)
        vertices.append([x, -half_h, z])

    # Side faces (triangles from apex to base ring)
    # Winding order: base[i] -> base[i+1] -> apex for outward normals
    for i in range(segments):
        next_i = ((i + 1) % segments) + 1  # +1 because index 0 is apex
        faces.append([1 + i, next_i, apex_idx])

    if cap_base:
        # Base cap (disk)
        base_center = len(vertices)
        vertices.append([0, -half_h, 0])
        # Winding order for bottom face: counter-clockwise when viewed from below.
        # `next_i` must be the *ring* index (0..segments-1) - the "+1" ring-to-
        # vertex offset is applied once, below, not baked into next_i itself.
        # Applying it twice (as this used to) skips every other ring vertex,
        # producing both a degenerate triangle and open boundary edges - even
        # though the side faces alone looked fine. See test_mesh.py.
        for i in range(segments):
            next_i = (i + 1) % segments
            # Reversed traversal order relative to the side faces above: the
            # side faces walk (ring[i] -> ring[i+1]) with the apex (+Y) as the
            # third vertex, so the base cap (-Y) needs the opposite traversal
            # direction to be wound consistently with the sides (see the
            # analogous cylinder cap-winding note above).
            faces.append([1 + next_i, 1 + i, base_center])

    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)

    mesh = Mesh(vertices=vertices, faces=faces)
    if not cap_base:
        return mesh
    return ensure_outward_winding(mesh)


def create_torus_mesh(major_radius: float = 0.5, minor_radius: float = 0.15,
                      major_segments: int = 32, minor_segments: int = 16) -> Mesh:
    """Generate a torus mesh."""
    vertices = []
    faces = []

    for i in range(major_segments):
        theta = 2 * math.pi * i / major_segments
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)

        for j in range(minor_segments):
            phi = 2 * math.pi * j / minor_segments
            cos_phi = math.cos(phi)
            sin_phi = math.sin(phi)

            x = (major_radius + minor_radius * cos_phi) * cos_theta
            y = minor_radius * sin_phi
            z = (major_radius + minor_radius * cos_phi) * sin_theta

            vertices.append([x, y, z])

    for i in range(major_segments):
        next_i = (i + 1) % major_segments
        for j in range(minor_segments):
            next_j = (j + 1) % minor_segments

            v0 = i * minor_segments + j
            v1 = next_i * minor_segments + j
            v2 = next_i * minor_segments + next_j
            v3 = i * minor_segments + next_j

            faces.append([v0, v1, v2])
            faces.append([v0, v2, v3])

    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)

    mesh = Mesh(vertices=vertices, faces=faces)
    return ensure_outward_winding(mesh)


def create_disc_mesh(radius: float, segments: int = 24, normal_up: bool = True) -> Mesh:
    """A flat filled disc (triangle fan) in the XZ plane at y=0, facing +Y
    if normal_up else -Y. Used as a standalone cap - e.g. a hollow object's
    solid base, or the interior floor of a mug - independent of any
    particular cylinder."""
    vertices = [[0.0, 0.0, 0.0]]
    faces = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        vertices.append([radius * math.cos(theta), 0.0, radius * math.sin(theta)])
    for i in range(segments):
        cur = i + 1
        nxt = (i + 1) % segments + 1
        # (center, cur, nxt) with theta increasing from cur to nxt has its
        # normal (via center->cur cross center->nxt) pointing -Y, not +Y -
        # verified against known-good closed assemblies in test_mesh.py -
        # so normal_up=True needs the reversed (center, nxt, cur) order.
        if normal_up:
            faces.append([0, nxt, cur])
        else:
            faces.append([0, cur, nxt])
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    return Mesh(vertices=vertices, faces=faces)


def create_annulus_mesh(outer_radius: float, inner_radius: float, segments: int = 24,
                        normal_up: bool = True) -> Mesh:
    """A flat ring (annulus) connecting an inner and outer circle in the XZ
    plane at y=0 - used to close the gap between a hollow object's outer
    and inner walls (e.g. a mug's rim) with an actual watertight connecting
    surface rather than leaving an open ring."""
    vertices = []
    faces = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        c, s = math.cos(theta), math.sin(theta)
        vertices.append([outer_radius * c, 0.0, outer_radius * s])  # 2*i
        vertices.append([inner_radius * c, 0.0, inner_radius * s])  # 2*i+1
    for i in range(segments):
        next_i = (i + 1) % segments
        o0, i0 = 2 * i, 2 * i + 1
        o1, i1 = 2 * next_i, 2 * next_i + 1
        # As with create_disc_mesh, the naive (o0,o1,i1)/(o0,i1,i0) order
        # actually points -Y, not +Y - verified against known-good closed
        # assemblies in test_mesh.py.
        if normal_up:
            faces.append([o0, i1, o1])
            faces.append([o0, i0, i1])
        else:
            faces.append([o0, o1, i1])
            faces.append([o0, i1, i0])
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    return Mesh(vertices=vertices, faces=faces)




# ============================================================================
# Part shape registry
# ============================================================================
#
# A part's "shape" is looked up here rather than matched against a chain of
# hardcoded names. Adding a shape - including one a user or a future
# geometry editor invents - is a registration, not an edit to a dispatch
# branch, so no code anywhere has to enumerate "the shapes we support".
#
# A builder takes the part dict and returns a Mesh. It reads whatever
# parameters it cares about straight from that dict, so shapes can have
# completely different parameter sets without any shared schema.

PartShapeBuilder = Callable[[dict], Mesh]


def _build_box_part(part: dict) -> Mesh:
    return create_box_mesh(tuple(part.get("half_extents", (0.4, 0.4, 0.4))))


def _build_sphere_part(part: dict) -> Mesh:
    return create_sphere_mesh(part.get("radius", 0.5),
                              subdivisions=part.get("subdivisions", 3))


def _build_cylinder_part(part: dict) -> Mesh:
    return create_cylinder_mesh(part.get("radius", 0.4), part.get("height", 0.9),
                                segments=part.get("segments", 24),
                                cap_top=part.get("cap_top", True),
                                cap_bottom=part.get("cap_bottom", True))


def _build_cone_part(part: dict) -> Mesh:
    return create_cone_mesh(part.get("radius", 0.5), part.get("height", 1.0),
                            segments=part.get("segments", 24),
                            cap_base=part.get("cap_base", True))


def _build_torus_part(part: dict) -> Mesh:
    return create_torus_mesh(part.get("radius", 0.5), part.get("tube_radius", 0.18),
                             major_segments=part.get("rings", 32),
                             minor_segments=part.get("sides", 12))


def _build_wedge_part(part: dict) -> Mesh:
    return create_wedge_mesh(tuple(part.get("half_extents", (1.0, 0.15, 1.0))))


def _build_disc_part(part: dict) -> Mesh:
    return create_disc_mesh(part.get("radius", 0.5), segments=part.get("segments", 24),
                            normal_up=part.get("normal_up", True))


def _build_annulus_part(part: dict) -> Mesh:
    return create_annulus_mesh(part.get("radius", 0.5), part.get("inner_radius", 0.3),
                               segments=part.get("segments", 24),
                               normal_up=part.get("normal_up", True))


def _build_file_part(part: dict) -> Mesh:
    """An imported OBJ/STL used as a part, exactly like any primitive - it
    gets the same transform/color treatment, can be mixed with primitive
    parts in one object, and is indistinguishable downstream."""
    return load_mesh_file(
        part["path"],
        recenter=part.get("recenter", True),
        normalize_size=part.get("normalize_size"),
    )


PART_SHAPE_BUILDERS: Dict[str, PartShapeBuilder] = {
    "box": _build_box_part,
    "sphere": _build_sphere_part,
    "cylinder": _build_cylinder_part,
    "cone": _build_cone_part,
    "torus": _build_torus_part,
    "wedge": _build_wedge_part,
    "disc": _build_disc_part,
    "annulus": _build_annulus_part,
    "file": _build_file_part,
}


def register_part_shape(name: str, builder: PartShapeBuilder) -> None:
    """Register a new part shape usable in any recipe from then on.

    This is the extension point for geometry types that don't exist yet -
    a curve/loft generator, a voxel mesher, a parametric surface, an
    importer for another file format. The recipe interpreter, the mass
    property code, collision, placement and the renderer all require no
    changes, because none of them enumerate shapes.
    """
    PART_SHAPE_BUILDERS[name] = builder


def available_part_shapes() -> List[str]:
    return sorted(PART_SHAPE_BUILDERS)


def _apply_part_color(mesh_obj: Mesh, color) -> Mesh:
    out = mesh_obj.copy()
    out.colors = np.tile(np.asarray(color, dtype=np.float64), (len(out.vertices), 1))
    return out


def _apply_part_scale(mesh_obj: Mesh, scale) -> Mesh:
    if isinstance(scale, (int, float)):
        return mesh_obj if float(scale) == 1.0 else mesh_obj.scale(float(scale))
    return mesh_obj.scale_nonuniform(np.asarray(scale, dtype=np.float64))


def build_mesh_from_parts(parts: List[dict]) -> Mesh:
    """
    Build a single merged Mesh from a data-only recipe: a list of parts,
    each a shape plus a transform. This is the generic replacement for
    writing a bespoke Python function per composite object - adding an
    object means adding data, never code.

    Each part is a dict:
        shape:          any key in PART_SHAPE_BUILDERS (extensible - see
                        register_part_shape); shape-specific parameters
                        live alongside it in the same dict
        offset:         [x, y, z]              (default [0,0,0])
        rotation_deg:   [rx, ry, rz]           (default [0,0,0], X then Y then Z)
        scale:          number or [sx, sy, sz] (default 1.0)
        flip_winding:   bool  - face the surface inward, e.g. the inner
                        wall of a hollow shell
        color:          [r, g, b] - per-part color override baked into the
                        mesh's vertex colors, so one object can have parts
                        of different colors without extra draw calls

    A part whose shape isn't registered is skipped with a warning rather
    than aborting the whole object, so one bad entry in a large
    user-authored recipe degrades gracefully instead of losing everything.
    """
    built: List[Mesh] = []
    for part in parts:
        shape = part.get("shape")
        builder = PART_SHAPE_BUILDERS.get(shape)
        if builder is None:
            logger.warning(
                f"build_mesh_from_parts: unknown part shape {shape!r} - skipping. "
                f"Known shapes: {', '.join(available_part_shapes())}"
            )
            continue
        try:
            piece = builder(part)
        except Exception:
            logger.exception(f"build_mesh_from_parts: failed to build part {part!r} - skipping")
            continue

        if part.get("flip_winding"):
            piece = flip_winding(piece)

        color = part.get("color")
        if color is not None:
            piece = _apply_part_color(piece, color)

        scale = part.get("scale", 1.0)
        if scale is not None:
            piece = _apply_part_scale(piece, scale)

        rot = part.get("rotation_deg")
        if rot:
            rx, ry, rz = rot
            if rx:
                piece = rotate_mesh_x(piece, math.radians(rx))
            if ry:
                piece = rotate_mesh_y(piece, math.radians(ry))
            if rz:
                piece = rotate_mesh_z(piece, math.radians(rz))

        offset = part.get("offset")
        if offset:
            piece = translate_mesh(piece, tuple(offset))

        built.append(piece)

    if not built:
        logger.warning("build_mesh_from_parts: recipe produced no usable geometry")
        return Mesh()
    return merge_meshes(built)


# ============================================================================
# Object-kind geometry registry
# ============================================================================
#
# Maps an object KIND (a name like "car", or whatever a user names their
# imported shape) to the geometry for it. Two ways to register:
#
#   register_parts_recipe(kind, parts)  - data recipe; this is what
#       object_catalog.py calls for every entry in data/objects.json, and
#       what an import or in-app editor calls for user-created objects.
#
#   register_mesh_builder(kind, fn)     - a callable returning a Mesh, for
#       geometry that isn't expressible as a parts recipe.
#
# This module never reads the catalog itself. That inversion is what keeps
# the import graph acyclic (object_catalog -> body -> mesh, with nothing
# pointing back), and it means geometry can be registered by anything -
# including code that doesn't exist yet - without this file knowing.

_MESH_BUILDERS: Dict[str, Callable[[], Mesh]] = {}
_PARTS_RECIPES: Dict[str, List[dict]] = {}
_mesh_kind_cache: Dict[str, Mesh] = {}


def register_parts_recipe(kind: str, parts: List[dict]) -> None:
    """Associate an object kind with a data-only parts recipe."""
    _PARTS_RECIPES[kind] = parts
    _mesh_kind_cache.pop(kind, None)


def register_mesh_builder(kind: str, builder: Callable[[], Mesh]) -> None:
    """Associate an object kind with a Python builder returning a Mesh."""
    _MESH_BUILDERS[kind] = builder
    _mesh_kind_cache.pop(kind, None)


def get_parts_recipe(kind: str) -> Optional[List[dict]]:
    """The registered recipe for a kind, if it has one. Used by body.py to
    apply per-instance part overrides without importing the catalog."""
    return _PARTS_RECIPES.get(kind)


def get_mesh_by_kind(kind: str) -> Optional[Mesh]:
    """Geometry for an object kind, or None if nothing is registered (the
    caller then falls back to a bare primitive from its own shape params).

    Cached: builders and recipes are deterministic, so without this every
    spawn would re-tessellate and re-weld identical geometry (measured at
    several ms per spawn for a detailed object). The cache holds one
    shared immutable Mesh per kind - safe because nothing downstream
    mutates a Mesh in place; every transform helper returns a new one.
    """
    cached = _mesh_kind_cache.get(kind)
    if cached is not None:
        return cached

    builder = _MESH_BUILDERS.get(kind)
    if builder is not None:
        built = builder()
        _mesh_kind_cache[kind] = built
        return built

    parts = _PARTS_RECIPES.get(kind)
    if parts:
        built = build_mesh_from_parts(parts)
        _mesh_kind_cache[kind] = built
        return built

    return None


def invalidate_mesh_cache(kind: Optional[str] = None) -> None:
    """Drop cached geometry so it rebuilds on next access - call after
    editing a recipe (e.g. from an in-app editor) so changes take effect."""
    if kind is None:
        _mesh_kind_cache.clear()
    else:
        _mesh_kind_cache.pop(kind, None)


def registered_kinds() -> List[str]:
    return sorted(set(_MESH_BUILDERS) | set(_PARTS_RECIPES))


# Bare primitives are registered as ordinary kinds so that a body spawned
# with shape="sphere" and no catalog entry still resolves through the same
# single path as everything else.
for _name, _factory in (
        ("box", lambda: create_box_mesh((0.4, 0.4, 0.4))),
        ("sphere", lambda: create_sphere_mesh(0.5)),
        ("cylinder", lambda: create_cylinder_mesh(0.4, 0.9)),
        ("cone", lambda: create_cone_mesh(0.5, 1.0)),
        ("torus", lambda: create_torus_mesh(0.5, 0.18)),
        ("wedge", lambda: create_wedge_mesh((1.0, 0.15, 1.0))),
):
    register_mesh_builder(_name, _factory)
