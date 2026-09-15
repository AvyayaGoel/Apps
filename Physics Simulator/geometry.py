"""
geometry.py - the shared geometry core.

This module holds everything that BOTH the procedural generators
(mesh.py) and the file importers (mesh_io.py) need: the `Mesh` data
structure itself, topology validation, vertex welding, winding
correction, and the affine transform/merge helpers.

It exists specifically so those two modules never have to import each
other. mesh.py needs mesh_io's file loading (to support a "file" part in
a recipe) and mesh_io needs mesh.py's Mesh/merge/validate - which is a
circular import. Rather than paper over that with function-local imports
(which only delays the failure and leaves a landmine for the next
importer), the shared half lives here and both sides import downward
from it:

    geometry.py          <- no project imports at all
        ^        ^
        |        |
    mesh_io.py   mesh.py  (mesh.py also imports mesh_io)
                    ^
                    |
                 body.py, object_catalog.py, renderer.py, ...

Every import in this project is top-of-file as a result.

Nothing here knows about object kinds, names, or categories. A Mesh is
just vertices/faces/normals/colors - whether it came from a box
generator, a JSON recipe, an imported OBJ, or a shape nobody has
invented yet.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Mesh:
    """
    A general mesh representation containing vertices, faces, normals,
    and derived geometric properties.
    """
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    faces: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int32))
    normals: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    # Optional per-vertex color override (Nx3 RGB, 0-1), same length as
    # vertices when present. NaN entries mean "no override for this
    # vertex - use whatever base color the renderer is already using".
    # This lets a single "parts" recipe give individual parts their own
    # color (e.g. dark tires vs a red car body) without needing per-object
    # rendering code - see the "color" field on a part in
    # mesh.build_mesh_from_parts / data/objects.json's "car" entry.
    colors: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    material: Optional[Dict[str, Any]] = None

    # Cached properties
    _bounds_min: Optional[np.ndarray] = None
    _bounds_max: Optional[np.ndarray] = None
    _volume: Optional[float] = None
    _centroid: Optional[np.ndarray] = None
    _inertia_tensor: Optional[np.ndarray] = None
    _is_closed: Optional[bool] = None

    def __post_init__(self):
        if len(self.vertices) > 0 and len(self.normals) == 0:
            self.normals = self._compute_normals()

    def copy(self) -> Mesh:
        """Create a deep copy of this mesh."""
        return Mesh(
            vertices=self.vertices.copy(),
            faces=self.faces.copy(),
            normals=self.normals.copy(),
            colors=self.colors.copy(),
            material=self.material.copy() if self.material else None
        )

    def _compute_normals(self) -> np.ndarray:
        """Compute face normals from vertices and faces."""
        if len(self.faces) == 0 or len(self.vertices) == 0:
            return np.zeros((0, 3), dtype=np.float64)

        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]

        edge1 = v1 - v0
        edge2 = v2 - v0
        face_normals = np.cross(edge1, edge2)

        # Normalize
        lengths = np.linalg.norm(face_normals, axis=1, keepdims=True)
        lengths[lengths < 1e-10] = 1.0
        face_normals = face_normals / lengths

        # Compute vertex normals by averaging adjacent face normals
        vertex_normals = np.zeros_like(self.vertices)
        for i, face in enumerate(self.faces):
            for j in range(3):
                vertex_normals[face[j]] += face_normals[i]

        # Normalize vertex normals
        lengths = np.linalg.norm(vertex_normals, axis=1, keepdims=True)
        lengths[lengths < 1e-10] = 1.0
        vertex_normals = vertex_normals / lengths

        return vertex_normals

    @property
    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get local-space bounding box (min, max)."""
        if self._bounds_min is None and len(self.vertices) > 0:
            self._bounds_min = self.vertices.min(axis=0)
            self._bounds_max = self.vertices.max(axis=0)
        elif len(self.vertices) == 0:
            return vec3(0, 0, 0), vec3(0, 0, 0)
        return self._bounds_min, self._bounds_max

    @property
    def is_closed(self) -> bool:
        """Check if mesh is a closed manifold."""
        if self._is_closed is not None:
            return self._is_closed

        if len(self.faces) == 0:
            self._is_closed = False
            return False

        # Build edge frequency map
        edge_count: Dict[Tuple[int, int], int] = {}
        for face in self.faces:
            for i in range(3):
                e0, e1 = int(face[i]), int(face[(i + 1) % 3])
                edge = (min(e0, e1), max(e0, e1))
                edge_count[edge] = edge_count.get(edge, 0) + 1

        # In a closed manifold, each edge should appear exactly twice
        self._is_closed = all(count == 2 for count in edge_count.values())
        return self._is_closed

    def compute_volume(self) -> float:
        """
        Compute signed volume using divergence theorem.
        For a closed mesh, volume = (1/6) * sum over faces of (v0 × v1) · v2
        """
        if self._volume is not None:
            return self._volume

        if len(self.faces) == 0 or len(self.vertices) == 0:
            self._volume = 0.0
            return 0.0

        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]

        # Signed volume contribution from each tetrahedron (origin, v0, v1, v2)
        cross = np.cross(v1, v2)
        dot_products = np.sum(v0 * cross, axis=1)
        volume = np.sum(dot_products) / 6.0

        self._volume = abs(volume)
        return self._volume

    def compute_centroid(self) -> np.ndarray:
        """
        Compute centroid (center of mass assuming uniform density).
        Uses weighted average of face tetrahedra centroids.
        """
        if self._centroid is not None:
            return self._centroid

        if len(self.faces) == 0 or len(self.vertices) == 0:
            self._centroid = vec3(0, 0, 0)
            return self._centroid

        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]

        # Centroid of each tetrahedron (origin, v0, v1, v2)
        tetra_centroids = (v0 + v1 + v2) / 4.0

        # Signed volume of each tetrahedron
        cross = np.cross(v1, v2)
        signed_volumes = np.sum(v0 * cross, axis=1) / 6.0

        total_volume = np.sum(np.abs(signed_volumes))
        if total_volume < 1e-10:
            self._centroid = vec3(0, 0, 0)
            return self._centroid

        # Weighted average
        self._centroid = np.sum(tetra_centroids * np.abs(signed_volumes).reshape(-1, 1), axis=0) / total_volume
        return self._centroid

    def compute_inertia_tensor(self, mass: float = 1.0) -> np.ndarray:
        """
        Compute the exact 3x3 inertia tensor (about the mesh's own local
        origin) of the solid enclosed by this closed mesh, assuming uniform
        density, using the exact polyhedral second-moment formula (each face
        forms a signed tetrahedron with the origin; the closed-form integral
        of x_i*x_j over a tetrahedron with vertices (0, a, b, c) is
        (V/20) * (a_i a_j + b_i b_j + c_i c_j + S_i S_j) with S = a+b+c,
        derived and verified against Monte-Carlo/rejection-sampling
        integration - see the inertia unit tests). Summing the signed
        contribution of every face over a closed, consistently-wound mesh
        gives the exact covariance matrix C = ∫ x_i x_j dV of the enclosed
        solid (an internal cavity bounded by oppositely-wound faces
        correctly subtracts its own contribution). The inertia tensor is
        then I = density * (trace(C) * Identity - C).

        For uniform scaling s at constant density:
        - volume scales as s³
        - mass scales as s³
        - inertia scales as s⁵
        (this falls out automatically, since C scales as s^5 when vertices
        are scaled by s, and density = mass/volume is held fixed by the
        caller supplying the already-scaled mass).
        """
        if self._inertia_tensor is not None:
            return self._inertia_tensor

        if len(self.faces) == 0 or len(self.vertices) == 0:
            self._inertia_tensor = np.eye(3, dtype=np.float64)
            return self._inertia_tensor

        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]

        # Signed volume of each (origin, a, b, c) tetrahedron.
        w = np.einsum('ij,ij->i', v0, np.cross(v1, v2)) / 6.0
        total_signed_volume = float(w.sum())

        if abs(total_signed_volume) < 1e-12:
            self._inertia_tensor = np.eye(3, dtype=np.float64)
            return self._inertia_tensor

        s = v0 + v1 + v2  # per-face sum of the three non-origin vertices
        quad = (np.einsum('fi,fj->fij', v0, v0)
                + np.einsum('fi,fj->fij', v1, v1)
                + np.einsum('fi,fj->fij', v2, v2))
        outer_s = np.einsum('fi,fj->fij', s, s)
        per_face_covariance = (quad + outer_s) * (w[:, None, None] / 20.0)
        covariance = per_face_covariance.sum(axis=0)

        # A mesh may be wound so that "outward" faces produce a globally
        # negative signed volume (still perfectly valid/closed, just wound
        # the other way round). Both `covariance` and `total_signed_volume`
        # pick up the same sign flip in that case, so normalizing by the
        # signed volume (not abs()) keeps them consistent.
        density = mass / total_signed_volume
        trace_c = np.trace(covariance)
        inertia = density * (trace_c * np.eye(3) - covariance)

        # Symmetrize to kill floating point asymmetry, then guard against a
        # degenerate/self-intersecting input mesh producing a non-positive
        # eigenvalue (a valid closed solid never should).
        inertia = 0.5 * (inertia + inertia.T)
        eigvals = np.linalg.eigvalsh(inertia)
        if np.any(eigvals < 1e-9):
            inertia = inertia + np.eye(3) * (abs(min(0.0, eigvals.min())) + 1e-6)

        self._inertia_tensor = inertia
        return self._inertia_tensor

    def get_lowest_point(self) -> float:
        """Get the lowest Y coordinate in local space."""
        if len(self.vertices) == 0:
            return 0.0
        return float(self.vertices[:, 1].min())

    def scale(self, factor: float) -> Mesh:
        """Return a new mesh scaled uniformly."""
        if factor <= 0:
            factor = 0.01
        new_mesh = self.copy()
        new_mesh.vertices *= factor
        # Normals don't change with uniform scaling
        new_mesh._volume = None  # Invalidate cache
        new_mesh._centroid = None
        new_mesh._inertia_tensor = None
        new_mesh._bounds_min = None
        new_mesh._bounds_max = None
        return new_mesh

    def scale_nonuniform(self, factors: np.ndarray) -> Mesh:
        """Return a new mesh scaled independently per axis (sx, sy, sz).
        Volume/centroid/inertia are all recomputed from the actual scaled
        vertex positions (see compute_inertia_tensor's docstring) rather
        than via an s^3/s^5 shortcut formula, which only holds for uniform
        scaling - this works correctly for anisotropic resizing too, for
        free, because the underlying divergence-theorem integral only
        ever looks at real vertex positions. Unlike uniform scale(), the
        surface normal direction DOES change under anisotropic scaling
        (a sphere stretched along one axis is no longer isotropic), so
        normals are recomputed rather than left as-is."""
        sx, sy, sz = factors
        if sx <= 0 or sy <= 0 or sz <= 0:
            sx, sy, sz = max(sx, 0.01), max(sy, 0.01), max(sz, 0.01)
        new_mesh = self.copy()
        new_mesh.vertices = new_mesh.vertices * np.array([sx, sy, sz], dtype=np.float64)
        new_mesh.normals = np.zeros((0, 3), dtype=np.float64)
        new_mesh.recompute_normals()
        new_mesh._volume = None
        new_mesh._centroid = None
        new_mesh._inertia_tensor = None
        new_mesh._bounds_min = None
        new_mesh._bounds_max = None
        return new_mesh

    def transform(self, position: np.ndarray, orientation: np.ndarray) -> np.ndarray:
        """
        Get transformed vertices in world space.
        Returns array of shape (N, 3).
        """
        from math_utils import quat_rotate_vector
        if len(self.vertices) == 0:
            return np.zeros((0, 3), dtype=np.float64)

        transformed = np.array([quat_rotate_vector(orientation, v) + position
                                for v in self.vertices])
        return transformed

    def get_world_lowest_point(self, position: np.ndarray, orientation: np.ndarray) -> float:
        """Get the lowest Y coordinate in world space after transformation."""
        transformed = self.transform(position, orientation)
        if len(transformed) == 0:
            return position[1]
        return float(transformed[:, 1].min())

    def recompute_normals(self) -> None:
        """Force-recompute vertex normals from current vertices/faces."""
        self.normals = self._compute_normals()


@dataclass
class MeshValidationReport:
    """Result of validate_mesh(). A mesh is fully valid for use as a closed
    solid iff `is_valid` is True; individual fields let callers/tests pin
    down exactly what is wrong."""
    vertex_count: int
    face_count: int
    degenerate_faces: int
    duplicate_faces: int
    non_manifold_edges: int
    boundary_edges: int
    reversed_edges: int
    is_orientation_consistent: bool
    is_closed_manifold: bool
    signed_volume: float

    @property
    def is_valid(self) -> bool:
        return (self.degenerate_faces == 0 and self.duplicate_faces == 0
                and self.non_manifold_edges == 0 and self.is_closed_manifold
                and self.is_orientation_consistent)

    def summary(self) -> str:
        if self.is_valid:
            return f"valid closed manifold ({self.face_count} faces, volume={abs(self.signed_volume):.6g})"
        problems = []
        if self.degenerate_faces:
            problems.append(f"{self.degenerate_faces} degenerate faces")
        if self.duplicate_faces:
            problems.append(f"{self.duplicate_faces} duplicate faces")
        if self.boundary_edges:
            problems.append(f"{self.boundary_edges} open/boundary edges")
        if self.non_manifold_edges:
            problems.append(f"{self.non_manifold_edges} non-manifold edges")
        if self.reversed_edges:
            problems.append(f"{self.reversed_edges} inconsistently wound edges")
        return "invalid mesh: " + ", ".join(problems)


def validate_mesh(mesh: Mesh) -> MeshValidationReport:
    """
    Validate mesh topology properly, rather than assuming a mesh is correct
    merely because it renders. Checks (per item 4 of the geometry redesign):
      - degenerate triangles (zero area / repeated vertex index)
      - duplicated faces
      - non-manifold edges (an undirected edge used by more than 2 faces)
      - boundary/open edges (an undirected edge used by only 1 face - a hole)
      - consistent winding (for a correctly oriented closed manifold, every
        DIRECTED edge (a, b) must appear exactly once, and its reverse
        (b, a) must appear exactly once on the adjacent face - two faces
        that both list the same directed edge are wound inconsistently,
        even though a naive undirected edge-count of 2 would look "closed")
    """
    n_verts = len(mesh.vertices)
    n_faces = len(mesh.faces)

    degenerate = 0
    seen_faces = set()
    duplicate = 0
    directed_edges: Dict[Tuple[int, int], int] = {}
    undirected_edges: Dict[Tuple[int, int], int] = {}

    for face in mesh.faces:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        if a == b or b == c or a == c:
            degenerate += 1
            continue
        key = tuple(sorted((a, b, c)))
        if key in seen_faces:
            duplicate += 1
        seen_faces.add(key)

        for e0, e1 in ((a, b), (b, c), (c, a)):
            directed_edges[(e0, e1)] = directed_edges.get((e0, e1), 0) + 1
            u_edge = (min(e0, e1), max(e0, e1))
            undirected_edges[u_edge] = undirected_edges.get(u_edge, 0) + 1

    non_manifold = sum(1 for count in undirected_edges.values() if count > 2)
    boundary = sum(1 for count in undirected_edges.values() if count == 1)
    is_closed_manifold = n_faces > 0 and non_manifold == 0 and boundary == 0

    # Orientation consistency: for every directed edge (a,b) used once, its
    # reverse (b,a) should also be used exactly once (by the adjacent face).
    # A directed edge repeated in the SAME direction by two faces (a,b) used
    # twice, or (a,b) present without any (b,a) counterpart despite the
    # undirected edge count being 2, means the two faces sharing that edge
    # wind in the same rather than opposite rotational sense.
    reversed_mismatches = 0
    for (e0, e1), count in directed_edges.items():
        if count > 1:
            reversed_mismatches += count - 1
            continue
        u_edge = (min(e0, e1), max(e0, e1))
        if undirected_edges.get(u_edge, 0) == 2 and directed_edges.get((e1, e0), 0) == 0:
            reversed_mismatches += 1

    signed_volume = 0.0
    if n_faces > 0 and n_verts > 0:
        v0 = mesh.vertices[mesh.faces[:, 0]]
        v1 = mesh.vertices[mesh.faces[:, 1]]
        v2 = mesh.vertices[mesh.faces[:, 2]]
        signed_volume = float(np.sum(np.einsum('ij,ij->i', v0, np.cross(v1, v2))) / 6.0)

    return MeshValidationReport(
        vertex_count=n_verts,
        face_count=n_faces,
        degenerate_faces=degenerate,
        duplicate_faces=duplicate,
        non_manifold_edges=non_manifold,
        boundary_edges=boundary,
        reversed_edges=reversed_mismatches,
        is_orientation_consistent=(reversed_mismatches == 0),
        is_closed_manifold=is_closed_manifold,
        signed_volume=signed_volume,
    )


def ensure_outward_winding(mesh: Mesh) -> Mesh:
    """
    A closed, consistently-wound mesh has one global orientation: either
    every face's winding produces outward-pointing normals (positive signed
    volume via the divergence theorem) or every face is wound the other way
    (negative signed volume - still perfectly closed/consistent, just
    inside-out). Procedural generators are easy to get backwards for a given
    axis convention; rather than hand-verify each one, generate the mesh,
    measure the sign of its total signed volume, and flip every face's
    winding (and normals) if it came out negative. This does NOT fix
    per-face inconsistent winding (see validate_mesh) - only a mesh that is
    already internally consistent but globally inside-out.
    """
    if len(mesh.faces) == 0:
        return mesh
    v0 = mesh.vertices[mesh.faces[:, 0]]
    v1 = mesh.vertices[mesh.faces[:, 1]]
    v2 = mesh.vertices[mesh.faces[:, 2]]
    signed_volume = float(np.sum(np.einsum('ij,ij->i', v0, np.cross(v1, v2))) / 6.0)
    if signed_volume < 0:
        return flip_winding(mesh)
    return mesh


def flip_winding(mesh: Mesh) -> Mesh:
    """Return a copy of mesh with every face's winding order reversed
    (swaps which side of each triangle is 'outward'), normals recomputed
    to match. Used to correct globally inside-out meshes, and to build an
    inward-facing inner shell (e.g. the interior wall of a hollow mug) from
    an outward-facing wall generator."""
    new_mesh = mesh.copy()
    new_mesh.faces = mesh.faces[:, [0, 2, 1]].copy()
    new_mesh.normals = np.zeros((0, 3), dtype=np.float64)
    new_mesh.recompute_normals()
    new_mesh._volume = None
    new_mesh._centroid = None
    new_mesh._inertia_tensor = None
    new_mesh._is_closed = None
    return new_mesh


def rotate_mesh_x(mesh: Mesh, angle_rad: float) -> Mesh:
    """Return a copy of mesh rotated by angle_rad about the local X axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)
    return _apply_rotation(mesh, R)


def rotate_mesh_y(mesh: Mesh, angle_rad: float) -> Mesh:
    """Return a copy of mesh rotated by angle_rad about the local Y axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)
    return _apply_rotation(mesh, R)


def rotate_mesh_z(mesh: Mesh, angle_rad: float) -> Mesh:
    """Return a copy of mesh rotated by angle_rad about the local Z axis."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)
    return _apply_rotation(mesh, R)


def translate_mesh(mesh: Mesh, offset: Tuple[float, float, float]) -> Mesh:
    """Return a copy of mesh translated by offset. Winding/normals are
    unaffected by a pure translation."""
    new_mesh = mesh.copy()
    new_mesh.vertices = new_mesh.vertices + np.asarray(offset, dtype=np.float64)
    new_mesh._volume = None
    new_mesh._centroid = None
    new_mesh._inertia_tensor = None
    new_mesh._bounds_min = None
    new_mesh._bounds_max = None
    return new_mesh


def _apply_rotation(mesh: Mesh, R: np.ndarray) -> Mesh:
    new_mesh = mesh.copy()
    new_mesh.vertices = mesh.vertices @ R.T
    if len(mesh.normals) == len(mesh.vertices):
        new_mesh.normals = mesh.normals @ R.T
    new_mesh._volume = None
    new_mesh._centroid = None
    new_mesh._inertia_tensor = None
    new_mesh._bounds_min = None
    new_mesh._bounds_max = None
    return new_mesh


def merge_meshes(mesh_list: List[Mesh], weld: bool = True, weld_epsilon: float = 1e-6) -> Mesh:
    """Merge multiple meshes into a single mesh.

    Each input mesh has its own independent vertex array, so two parts that
    are meant to share an edge (e.g. a mug's outer wall and its bottom cap)
    only coincide in *position*, not in vertex *index* - naive concatenation
    leaves every such seam as a pair of open boundary edges, invisible to
    rendering but fatal to topology validation, closed-volume computation,
    and collision use. When weld=True (the default), vertices from
    different parts that land on the same position (within weld_epsilon)
    are merged into a single shared vertex, so seams between touching parts
    become real shared edges. Vertices *within* the same generated part are
    never welded to each other, only across parts, so a part's own
    intentionally-separate vertices (e.g. duplicated seam vertices used to
    get flat per-face normals) are left alone.
    """
    if not mesh_list:
        return Mesh()

    if len(mesh_list) == 1:
        return mesh_list[0].copy()

    total_vertices = sum(len(m.vertices) for m in mesh_list)
    total_faces = sum(len(m.faces) for m in mesh_list)

    vertices = np.zeros((total_vertices, 3), dtype=np.float64)
    faces = np.zeros((total_faces, 3), dtype=np.int32)
    colors = np.full((total_vertices, 3), np.nan, dtype=np.float64)
    any_colors = any(len(m.colors) == len(m.vertices) and len(m.vertices) > 0 for m in mesh_list)

    vertex_offset = 0
    face_offset = 0

    for mesh in mesh_list:
        v_count = len(mesh.vertices)
        f_count = len(mesh.faces)

        vertices[vertex_offset:vertex_offset + v_count] = mesh.vertices
        faces[face_offset:face_offset + f_count] = mesh.faces + vertex_offset
        if len(mesh.colors) == v_count and v_count > 0:
            colors[vertex_offset:vertex_offset + v_count] = mesh.colors

        vertex_offset += v_count
        face_offset += f_count

    if weld:
        vertices, faces, colors = weld_vertices(vertices, faces, weld_epsilon, colors)

    merged = Mesh(vertices=vertices, faces=faces,
                  colors=colors if any_colors else np.zeros((0, 3), dtype=np.float64))
    return merged


def weld_vertices(vertices: np.ndarray, faces: np.ndarray, epsilon: float,
                  colors: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Merge vertices at (nearly) identical positions into single shared
    vertices and remap face indices accordingly, dropping any now-unused
    vertex slots. Positions are snapped to a grid of size `epsilon` so
    coincident-within-tolerance points collide to the same dict key. If
    `colors` is given, the first occurrence's color wins for any welded
    group (a welded seam is, by construction, at the boundary between two
    parts, so it's a coin-flip anyway which part's color "should" win
    there - not worth a fancier blend)."""
    if len(vertices) == 0:
        empty_colors = np.zeros((0, 3), dtype=np.float64)
        return vertices, faces, empty_colors

    scale = 1.0 / epsilon
    keys = np.round(vertices * scale).astype(np.int64)
    key_to_new: Dict[Tuple[int, int, int], int] = {}
    remap = np.empty(len(vertices), dtype=np.int32)
    new_vertices: List[np.ndarray] = []
    new_colors: List[np.ndarray] = []

    for old_idx in range(len(vertices)):
        key = (int(keys[old_idx, 0]), int(keys[old_idx, 1]), int(keys[old_idx, 2]))
        new_idx = key_to_new.get(key)
        if new_idx is None:
            new_idx = len(new_vertices)
            key_to_new[key] = new_idx
            new_vertices.append(vertices[old_idx])
            new_colors.append(colors[old_idx] if colors is not None else np.array([np.nan, np.nan, np.nan]))
        remap[old_idx] = new_idx

    new_vertices = np.array(new_vertices, dtype=np.float64)
    new_faces = remap[faces]
    new_colors = np.array(new_colors, dtype=np.float64)
    return new_vertices, new_faces, new_colors


# Backwards-compatible private alias (was _weld_vertices before this
# module was split out of mesh.py).
_weld_vertices = weld_vertices
