"""
mesh.py - Mesh-first geometry system.

Provides a general Mesh representation with:
- vertices, faces, normals
- topology information
- local-space bounds
- closed/manifold validation
- volume calculation
- centroid calculation
- inertia tensor calculation

All objects (car, mug, chair, table, rocket, user-created shapes, imported shapes)
are represented as Mesh data. Primitive generators only generate Mesh data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from math_utils import vec3, normalize


@dataclass
class Mesh:
    """
    A general mesh representation containing vertices, faces, normals,
    and derived geometric properties.
    """
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    faces: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int32))
    normals: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
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
        Compute 3x3 inertia tensor in local coordinates.
        Uses polyhedral formula for exact inertia of closed mesh.
        
        For uniform scaling s at constant density:
        - volume scales as s³
        - mass scales as s³  
        - inertia scales as s⁵
        """
        if self._inertia_tensor is not None:
            return self._inertia_tensor
        
        if len(self.faces) == 0 or len(self.vertices) == 0:
            self._inertia_tensor = np.eye(3, dtype=np.float64)
            return self._inertia_tensor
        
        volume = self.compute_volume()
        if volume < 1e-10:
            self._inertia_tensor = np.eye(3, dtype=np.float64)
            return self._inertia_tensor
        
        # Density
        density = mass / volume
        
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        
        # Compute inertia tensor using polyhedral formula
        # Based on "Polyhedral Mass Properties" by Brian Mirtich
        inertia = np.zeros((3, 3), dtype=np.float64)
        
        for i in range(len(self.faces)):
            # Tetrahedron vertices
            a = v0[i]
            b = v1[i]
            c = v2[i]
            
            # Cross products
            b_cross_c = np.cross(b, c)
            c_cross_a = np.cross(c, a)
            a_cross_b = np.cross(a, b)
            
            # Face normal contribution
            n = b_cross_c + c_cross_a + a_cross_b
            
            # Inertia integrals
            # Using simplified formulas for tetrahedron with one vertex at origin
            xa, ya, za = a
            xb, yb, zb = b
            xc, yc, zc = c
            
            # Compute tensor components
            # These are the integrals over the tetrahedron
            w = np.dot(a, b_cross_c) / 6.0  # signed volume
            
            if abs(w) < 1e-15:
                continue
            
            # Inertia tensor components for this tetrahedron
            # Simplified: treat as point mass at centroid for now
            centroid = (a + b + c) / 4.0
            x, y, z = centroid
            
            # Parallel axis theorem contribution
            r_sq = x*x + y*y + z*z
            m_tetra = density * abs(w)
            
            inertia[0, 0] += m_tetra * (r_sq - x*x)
            inertia[1, 1] += m_tetra * (r_sq - y*y)
            inertia[2, 2] += m_tetra * (r_sq - z*z)
            inertia[0, 1] -= m_tetra * x * y
            inertia[0, 2] -= m_tetra * x * z
            inertia[1, 2] -= m_tetra * y * z
        
        # Symmetrize
        inertia[1, 0] = inertia[0, 1]
        inertia[2, 0] = inertia[0, 2]
        inertia[2, 1] = inertia[1, 2]
        
        # Ensure positive definiteness
        eigvals = np.linalg.eigvalsh(inertia)
        if np.any(eigvals < 0):
            inertia = inertia + np.eye(3) * (abs(min(eigvals)) + 0.001)
        
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
    return mesh


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
    return mesh


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
            v0 = 2 * i
            v1 = 2 * next_i
            faces.append([v0, v1, center_idx])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    mesh = Mesh(vertices=vertices, faces=faces)
    return mesh


def create_cone_mesh(radius: float = 0.5, height: float = 1.0, 
                     segments: int = 24) -> Mesh:
    """Generate a cone mesh."""
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
    
    # Base cap (disk)
    base_center = len(vertices)
    vertices.append([0, -half_h, 0])
    # Winding order for bottom face: counter-clockwise when viewed from below
    for i in range(segments):
        next_i = ((i + 1) % segments) + 1
        faces.append([1 + i, 1 + next_i, base_center])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    mesh = Mesh(vertices=vertices, faces=faces)
    return mesh


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
    return mesh


# ============================================================================
# Complex object builders
# ============================================================================

def create_car_mesh() -> Mesh:
    """
    Generate a car mesh with correctly oriented upright wheels.
    Body + cabin + 4 wheels as a single merged mesh.
    """
    meshes_to_merge = []
    
    # Car body (box)
    body = create_box_mesh(half_extents=(0.8, 0.3, 0.45))
    meshes_to_merge.append(body)
    
    # Cabin (smaller box on top)
    cabin = create_box_mesh(half_extents=(0.35, 0.22, 0.38))
    # Translate cabin up and slightly back
    cabin.vertices[:, 1] += 0.32
    cabin.vertices[:, 0] -= 0.1
    meshes_to_merge.append(cabin)
    
    # Wheels (cylinders rotated 90 degrees around Y to be upright)
    wheel_positions = [
        (-0.55, -0.28, 0.52),   # front-left
        (0.55, -0.28, 0.52),    # front-right
        (-0.55, -0.28, -0.52),  # rear-left
        (0.55, -0.28, -0.52),   # rear-right
    ]
    
    for wx, wy, wz in wheel_positions:
        wheel = create_cylinder_mesh(radius=0.22, height=0.15, segments=16)
        # Rotate 90 degrees around Y axis (wheel faces Z direction)
        # Cylinder is initially Y-aligned, we want it X-aligned
        angle = math.pi / 2
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        
        # Rotate vertices
        new_verts = wheel.vertices.copy()
        # Swap X and Z, negate one for proper orientation
        new_verts[:, 0] = wheel.vertices[:, 2] * cos_a - wheel.vertices[:, 0] * sin_a
        new_verts[:, 2] = wheel.vertices[:, 2] * sin_a + wheel.vertices[:, 0] * cos_a
        
        # Translate to wheel position
        new_verts[:, 0] += wx
        new_verts[:, 1] += wy
        new_verts[:, 2] += wz
        
        wheel.vertices = new_verts
        meshes_to_merge.append(wheel)
    
    return merge_meshes(meshes_to_merge)


def create_cup_mesh() -> Mesh:
    """
    Generate a cup/mug mesh with properly shaped body and vertically oriented handle.
    Thin-walled cylinder, open top, with a handle on the side.
    """
    meshes_to_merge = []
    
    radius = 0.3
    height = 0.5
    thickness = 0.03
    
    # Outer wall (cylinder without top cap - open)
    outer = create_cylinder_mesh(radius=radius, height=height, segments=24, 
                                  cap_top=False, cap_bottom=True)
    meshes_to_merge.append(outer)
    
    # Inner wall (smaller cylinder, inverted normals for inside surface)
    inner_radius = radius - thickness
    inner = create_cylinder_mesh(radius=inner_radius, height=height, segments=24,
                                  cap_top=False, cap_bottom=True)
    # Flip normals for inner surface
    inner.normals = -inner.normals
    meshes_to_merge.append(inner)
    
    # Rim (torus at top)
    rim = create_torus_mesh(major_radius=radius - thickness * 0.5, 
                            minor_radius=thickness * 1.5,
                            major_segments=32, minor_segments=8)
    # Position at top
    rim.vertices[:, 1] += height / 2
    meshes_to_merge.append(rim)
    
    # Handle (torus on the side, vertically oriented)
    handle_major = 0.12
    handle_minor = 0.035
    handle = create_torus_mesh(major_radius=handle_major, minor_radius=handle_minor,
                                major_segments=24, minor_segments=12)
    # Rotate handle to be vertical (rotate 90 deg around Z)
    verts = handle.vertices.copy()
    temp = verts[:, 1].copy()
    verts[:, 1] = verts[:, 2]
    verts[:, 2] = -temp
    # Position on side of cup
    verts[:, 0] += radius + 0.02
    verts[:, 1] += 0.0  # Centered vertically
    handle.vertices = verts
    meshes_to_merge.append(handle)
    
    return merge_meshes(meshes_to_merge)


def create_rocket_mesh() -> Mesh:
    """Generate a rocket mesh with body, nose cone, and fins."""
    meshes_to_merge = []
    
    body_radius = 0.25
    body_height = 0.8
    
    # Main body (cylinder)
    body = create_cylinder_mesh(radius=body_radius, height=body_height, segments=24)
    meshes_to_merge.append(body)
    
    # Nose cone (cone on top)
    nose = create_cone_mesh(radius=body_radius, height=0.4, segments=24)
    nose.vertices[:, 1] += body_height / 2 + 0.2  # Position on top
    meshes_to_merge.append(nose)
    
    # Fins (4 triangular fins at bottom)
    fin_positions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    for dx, dz in fin_positions:
        # Simple fin as thin box
        fin = create_box_mesh(half_extents=(0.02, 0.15, 0.2))
        # Position and rotate
        fin.vertices[:, 0] *= dx
        fin.vertices[:, 2] *= dz
        fin.vertices[:, 0] += dx * (body_radius + 0.1)
        fin.vertices[:, 2] += dz * (body_radius + 0.1)
        fin.vertices[:, 1] -= body_height / 2 - 0.075
        meshes_to_merge.append(fin)
    
    return merge_meshes(meshes_to_merge)


def merge_meshes(mesh_list: List[Mesh]) -> Mesh:
    """Merge multiple meshes into a single mesh."""
    if not mesh_list:
        return Mesh()
    
    if len(mesh_list) == 1:
        return mesh_list[0].copy()
    
    total_vertices = sum(len(m.vertices) for m in mesh_list)
    total_faces = sum(len(m.faces) for m in mesh_list)
    
    vertices = np.zeros((total_vertices, 3), dtype=np.float64)
    faces = np.zeros((total_faces, 3), dtype=np.int32)
    normals = np.zeros((total_vertices, 3), dtype=np.float64)
    
    vertex_offset = 0
    face_offset = 0
    
    for mesh in mesh_list:
        v_count = len(mesh.vertices)
        f_count = len(mesh.faces)
        
        vertices[vertex_offset:vertex_offset + v_count] = mesh.vertices
        if len(mesh.normals) == v_count:
            normals[vertex_offset:vertex_offset + v_count] = mesh.normals
        
        # Offset face indices
        faces[face_offset:face_offset + f_count] = mesh.faces + vertex_offset
        
        vertex_offset += v_count
        face_offset += f_count
    
    merged = Mesh(vertices=vertices, faces=faces, normals=normals)
    return merged


# ============================================================================
# Mesh registry for object kinds
# ============================================================================

_MESH_REGISTRY: Dict[str, callable] = {
    'box': lambda: create_box_mesh((0.4, 0.4, 0.4)),
    'sphere': lambda: create_sphere_mesh(0.5),
    'cylinder': lambda: create_cylinder_mesh(0.4, 0.9),
    'cone': lambda: create_cone_mesh(0.5, 1.0),
    'torus': lambda: create_torus_mesh(0.5, 0.18),
    'car': create_car_mesh,
    'cup': create_cup_mesh,
    'rocket': create_rocket_mesh,
}


def get_mesh_by_kind(kind: str) -> Optional[Mesh]:
    """Get a mesh by object kind name."""
    if kind in _MESH_REGISTRY:
        return _MESH_REGISTRY[kind]()
    return None


def register_mesh_builder(kind: str, builder: callable) -> None:
    """Register a custom mesh builder for a new object kind."""
    _MESH_REGISTRY[kind] = builder
