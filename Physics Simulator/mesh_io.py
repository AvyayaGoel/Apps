"""
mesh_io.py - import geometry from standard mesh files (OBJ, STL) into the
same generic `mesh.Mesh` representation everything else in the engine uses.

This is the final piece of the "objects are just geometry" architecture:
an imported mesh is NOT a special kind of object. Once parsed it is an
ordinary Mesh, so it automatically gets the same treatment as a primitive
or a parts-recipe object - real volume/centroid/inertia from its actual
geometry, the same ground-placement math, the same collision
representation, the same renderer. Nothing downstream needs to know or
care that the geometry came from a file.

Supported formats:
  .obj  - Wavefront OBJ (v / f lines; normals and texcoords are parsed but
          normals are recomputed from topology, see below). Handles
          negative (relative) indices, polygonal faces (fan-triangulated),
          and the v/vt/vn index syntax.
  .stl  - Stereolithography, both binary and ASCII. STL is a "triangle
          soup" format with no shared vertices at all, so imported STL is
          always welded (see below) or it would have zero valid topology.

Post-import processing (why it's needed, not just nice-to-have):
  - Vertex welding: many real-world files (and ALL STL files) duplicate
    vertices per-face. Un-welded, such a mesh has no shared edges, so it
    is not a manifold, `validate_mesh` fails it, and - more importantly -
    the closed-volume/inertia integrals and the collision representation
    are meaningless. Welding is what turns triangle soup into real
    topology.
  - Normal recomputation: file-supplied normals are frequently absent,
    wrong, or inconsistent with face winding. Since face winding (not the
    normal attribute) is what drives backface culling and the volume
    integral, normals are always recomputed from the final topology.
  - Optional recentering/normalizing: imported files come in wildly
    different units and origins (a model might be 1000 units tall and sit
    entirely above the origin). Both are off by default - nothing is
    silently changed - but available for the common "just make this
    usable" case.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from geometry import Mesh, validate_mesh, ensure_outward_winding, weld_vertices

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".obj", ".stl")


class MeshImportError(Exception):
    """Raised when a mesh file can't be parsed into usable geometry."""


def load_mesh_file(path: str, weld: bool = True, weld_epsilon: float = 1e-6,
                   recenter: bool = False, normalize_size: Optional[float] = None,
                   fix_winding: bool = True) -> Mesh:
    """
    Load an OBJ or STL file into a Mesh.

    weld:           merge coincident vertices into shared ones (required
                    for valid topology; always effectively on for STL).
    recenter:       translate so the mesh's bounding-box center sits at
                    the local origin. Most of the engine assumes an
                    object's geometry is roughly centered on its own
                    origin (that's where rotation happens), so an
                    off-origin import will spin oddly without this.
    normalize_size: if given, uniformly scale so the largest bounding-box
                    dimension equals this value - handy since file units
                    are arbitrary.
    fix_winding:    if the mesh comes out closed but inside-out (negative
                    signed volume), flip it so faces point outward.
    """
    p = Path(path)
    if not p.exists():
        raise MeshImportError(f"File not found: {path}")
    ext = p.suffix.lower()
    if ext == ".obj":
        vertices, faces = _parse_obj(p)
    elif ext == ".stl":
        vertices, faces = _parse_stl(p)
        weld = True  # STL is triangle soup; without welding there is no topology at all
    else:
        raise MeshImportError(
            f"Unsupported mesh format {ext!r}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    if len(vertices) == 0 or len(faces) == 0:
        raise MeshImportError(f"{p.name}: no geometry found (0 vertices or 0 faces)")

    if weld:
        vertices, faces, _ = weld_vertices(vertices, faces, weld_epsilon, None)

    # Drop degenerate triangles (two or more identical corners). These
    # carry no area, contribute nothing to volume/inertia, and would show
    # up as spurious "degenerate faces" in validation - they're common in
    # exported files and after welding.
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    dropped = int((~keep).sum())
    if dropped:
        logger.info(f"{p.name}: dropped {dropped} degenerate triangles")
        faces = faces[keep]

    if len(faces) == 0:
        raise MeshImportError(f"{p.name}: no non-degenerate triangles remained")

    if recenter:
        center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
        vertices = vertices - center

    if normalize_size is not None and normalize_size > 0:
        extent = vertices.max(axis=0) - vertices.min(axis=0)
        largest = float(extent.max())
        if largest > 1e-12:
            vertices = vertices * (normalize_size / largest)

    mesh = Mesh(vertices=vertices, faces=faces)  # normals computed from final topology
    if fix_winding:
        mesh = ensure_outward_winding(mesh)
    return mesh


def describe_mesh_file(path: str, **load_kwargs) -> Tuple[Mesh, str]:
    """Load a mesh and return it alongside a short human-readable report
    of what came in and whether it's usable as a solid - intended for an
    import dialog, so the user finds out about an open/non-manifold mesh
    at import time rather than discovering weird physics later."""
    mesh = load_mesh_file(path, **load_kwargs)
    report = validate_mesh(mesh)
    lo, hi = mesh.bounds
    size = hi - lo
    lines = [
        f"{Path(path).name}: {len(mesh.vertices)} vertices, {len(mesh.faces)} triangles",
        f"size: {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f}",
    ]
    if report.is_valid:
        lines.append(f"closed solid - volume {abs(report.signed_volume):.4f}")
    else:
        lines.append(f"warning: {report.summary()}")
        lines.append("(an open/non-manifold mesh still renders, but its volume, "
                     "mass and inertia are unreliable - consider repairing it)")
    return mesh, "\n".join(lines)


# ---------------------------------------------------------------------------
# OBJ
# ---------------------------------------------------------------------------

def _parse_obj(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    vertices: List[List[float]] = []
    faces: List[List[int]] = []

    with path.open("r", errors="replace") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            tag = parts[0]
            if tag == "v":
                try:
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                except (IndexError, ValueError):
                    raise MeshImportError(f"{path.name}:{line_no}: malformed vertex line: {line!r}")
            elif tag == "f":
                idx: List[int] = []
                for token in parts[1:]:
                    # Face tokens look like "v", "v/vt", "v//vn" or "v/vt/vn";
                    # only the position index matters here since normals are
                    # recomputed from topology anyway.
                    vert_token = token.split("/")[0]
                    if not vert_token:
                        continue
                    try:
                        i = int(vert_token)
                    except ValueError:
                        raise MeshImportError(f"{path.name}:{line_no}: malformed face index {token!r}")
                    # OBJ indices are 1-based; negative indices count back
                    # from the most recently defined vertex.
                    idx.append(i - 1 if i > 0 else len(vertices) + i)
                if len(idx) < 3:
                    continue
                # Fan-triangulate any polygon (quads are extremely common).
                for k in range(1, len(idx) - 1):
                    faces.append([idx[0], idx[k], idx[k + 1]])

    if not vertices:
        raise MeshImportError(f"{path.name}: no vertices found - is this really an OBJ file?")

    vertices_arr = np.array(vertices, dtype=np.float64)
    faces_arr = np.array(faces, dtype=np.int32) if faces else np.zeros((0, 3), dtype=np.int32)

    if len(faces_arr) and (faces_arr.min() < 0 or faces_arr.max() >= len(vertices_arr)):
        raise MeshImportError(
            f"{path.name}: face references a vertex outside the file's vertex list"
        )
    return vertices_arr, faces_arr


# ---------------------------------------------------------------------------
# STL
# ---------------------------------------------------------------------------

def _parse_stl(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    data = path.read_bytes()
    if _looks_like_ascii_stl(data):
        return _parse_stl_ascii(data, path)
    return _parse_stl_binary(data, path)


def _looks_like_ascii_stl(data: bytes) -> bool:
    """An ASCII STL starts with "solid", but so do some binary files'
    80-byte headers - so also require that the declared binary triangle
    count matches the actual file size before trusting the binary path."""
    if not data[:5].lower().startswith(b"solid"):
        return False
    if len(data) < 84:
        return True
    (tri_count,) = struct.unpack("<I", data[80:84])
    expected_binary_size = 84 + tri_count * 50
    return len(data) != expected_binary_size


def _parse_stl_ascii(data: bytes, path: Path) -> Tuple[np.ndarray, np.ndarray]:
    vertices: List[List[float]] = []
    for raw in data.decode("utf-8", errors="replace").splitlines():
        parts = raw.strip().split()
        if len(parts) == 4 and parts[0] == "vertex":
            try:
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            except ValueError:
                raise MeshImportError(f"{path.name}: malformed vertex line: {raw.strip()!r}")
    if len(vertices) < 3:
        raise MeshImportError(f"{path.name}: no triangles found in ASCII STL")
    if len(vertices) % 3 != 0:
        logger.warning(f"{path.name}: vertex count {len(vertices)} isn't a multiple of 3; "
                       f"ignoring {len(vertices) % 3} trailing vertices")
        vertices = vertices[:len(vertices) - (len(vertices) % 3)]
    vertices_arr = np.array(vertices, dtype=np.float64)
    faces_arr = np.arange(len(vertices_arr), dtype=np.int32).reshape(-1, 3)
    return vertices_arr, faces_arr


def _parse_stl_binary(data: bytes, path: Path) -> Tuple[np.ndarray, np.ndarray]:
    if len(data) < 84:
        raise MeshImportError(f"{path.name}: file too short to be a binary STL")
    (tri_count,) = struct.unpack("<I", data[80:84])
    expected = 84 + tri_count * 50
    if len(data) < expected:
        raise MeshImportError(
            f"{path.name}: truncated binary STL (header declares {tri_count} triangles, "
            f"needs {expected} bytes, file is {len(data)})"
        )
    # Each record: 12 floats (normal + 3 vertices) then a 2-byte attribute
    # count. Read as a structured array and keep only the 9 position floats.
    record = np.dtype([("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    records = np.frombuffer(data, dtype=record, count=tri_count, offset=84)
    vertices_arr = records["v"].reshape(-1, 3).astype(np.float64)
    faces_arr = np.arange(len(vertices_arr), dtype=np.int32).reshape(-1, 3)
    return vertices_arr, faces_arr
