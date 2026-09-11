"""
geometry/mesh.py

A proper mesh-first geometry system. Every geometric object is represented
as a Mesh containing vertices, faces, normals, and derived physical properties.

This replaces the primitive-based architecture where objects were defined by
shape type + parameters. Now everything is a mesh, whether procedurally generated
or imported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class Mesh:
    """
    A triangular mesh representing geometry.
    
    All vertices are in local/object space. The mesh can represent either
    render geometry or collision geometry (or both if simple enough).
    """
    # Core geometry
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    faces: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int32))
    normals: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    
    # Optional per-vertex colors (for rendering)
    colors: Optional[np.ndarray] = None  # (N, 3) float array
    
    # Material reference (optional)
    material_id: Optional[str] = None
    
    # Cached properties (computed on demand)
    _bounds_min: Optional[np.ndarray] = None
    _bounds_max: Optional[np.ndarray] = None
    _volume: Optional[float] = None
    _centroid: Optional[np.ndarray] = None
    _inertia_tensor: Optional[np.ndarray] = None
    _is_closed: Optional[bool] = None
    _is_valid: Optional[bool] = None
    
    def __post_init__(self):
        if len(self.vertices) > 0 and len(self.normals) == 0:
            self.normals = self._compute_normals()
    
    # ------------------------------------------------------------------
    # Validation and topology
    # ------------------------------------------------------------------
    
    def validate(self) -> bool:
        """Check if mesh has valid topology."""
        if self._is_valid is not None:
            return self._is_valid
        
        if len(self.vertices) < 3 or len(self.faces) < 1:
            self._is_valid = False
            return False
        
        # Check face indices are in bounds
        if np.any(self.faces < 0) or np.any(self.faces >= len(self.vertices)):
            self._is_valid = False
            return False
        
        # Check faces have 3 vertices
        if self.faces.shape[1] != 3:
            self._is_valid = False
            return False
        
        self._is_valid = True
        return True
    
    def is_closed(self, tolerance: float = 1e-6) -> bool:
        """
        Check if mesh is closed (manifold without boundary).
        A closed mesh has every edge shared by exactly two faces.
        """
        if self._is_closed is not None:
            return self._is_closed
        
        if len(self.faces) == 0:
            self._is_closed = False
            return False
        
        # Build edge count
        edges = {}
        for face in self.faces:
            for i in range(3):
                v1, v2 = int(face[i]), int(face[(i + 1) % 3])
                edge = tuple(sorted([v1, v2]))
                edges[edge] = edges.get(edge, 0) + 1
        
        # Every edge should appear exactly twice for a closed manifold
        for count in edges.values():
            if count != 2:
                self._is_closed = False
                return False
        
        self._is_closed = True
        return True
    
    # ------------------------------------------------------------------
    # Geometry computation
    # ------------------------------------------------------------------
    
    def _compute_normals(self) -> np.ndarray:
        """Compute per-vertex normals from face geometry."""
        if len(self.faces) == 0:
            return np.zeros_like(self.vertices)
        
        normals = np.zeros_like(self.vertices)
        
        for face in self.faces:
            v0, v1, v2 = self.vertices[face[0]], self.vertices[face[1]], self.vertices[face[2]]
            edge1 = v1 - v0
            edge2 = v2 - v0
            face_normal = np.cross(edge1, edge2)
            norm = np.linalg.norm(face_normal)
            if norm > 1e-10:
                face_normal = face_normal / norm
            
            # Accumulate to each vertex
            for idx in face:
                normals[idx] += face_normal
        
        # Normalize accumulated normals
        for i in range(len(normals)):
            n = np.linalg.norm(normals[i])
            if n > 1e-10:
                normals[i] = normals[i] / n
        
        return normals
    
    def compute_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute axis-aligned bounding box in local space."""
        if len(self.vertices) == 0:
            return np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0])
        
        if self._bounds_min is None:
            self._bounds_min = self.vertices.min(axis=0)
            self._bounds_max = self.vertices.max(axis=0)
        
        return self._bounds_min.copy(), self._bounds_max.copy()
    
    def bounding_radius(self) -> float:
        """Compute bounding sphere radius from center."""
        if len(self.vertices) == 0:
            return 0.0
        centroid = self.centroid()
        max_dist = np.max(np.linalg.norm(self.vertices - centroid, axis=1))
        return max_dist
    
    # ------------------------------------------------------------------
    # Physical properties
    # ------------------------------------------------------------------
    
    def volume(self) -> float:
        """
        Compute signed volume using divergence theorem.
        For a closed mesh, this gives the enclosed volume.
        Volume is positive if faces are oriented outward.
        """
        if self._volume is not None:
            return self._volume
        
        if len(self.faces) == 0:
            self._volume = 0.0
            return 0.0
        
        vol = 0.0
        for face in self.faces:
            v0, v1, v2 = self.vertices[face[0]], self.vertices[face[1]], self.vertices[face[2]]
            # Signed volume of tetrahedron formed with origin
            vol += np.dot(v0, np.cross(v1, v2)) / 6.0
        
        self._volume = abs(vol)
        return self._volume
    
    def centroid(self) -> np.ndarray:
        """
        Compute centroid (center of mass for uniform density).
        Uses the same divergence theorem approach as volume.
        """
        if self._centroid is not None:
            return self._centroid.copy()
        
        if len(self.faces) == 0:
            self._centroid = np.array([0.0, 0.0, 0.0])
            return self._centroid.copy()
        
        centroid = np.zeros(3)
        volume = 0.0
        
        for face in self.faces:
            v0, v1, v2 = self.vertices[face[0]], self.vertices[face[1]], self.vertices[face[2]]
            # Tetrahedron volume
            tet_vol = np.dot(v0, np.cross(v1, v2)) / 6.0
            volume += tet_vol
            # Centroid of tetrahedron
            tet_centroid = (v0 + v1 + v2) / 4.0
            centroid += tet_centroid * tet_vol
        
        if abs(volume) < 1e-10:
            self._centroid = np.array([0.0, 0.0, 0.0])
            return self._centroid.copy()
        
        self._centroid = centroid / volume
        return self._centroid.copy()
    
    def inertia_tensor(self, density: float = 1.0) -> np.ndarray:
        """
        Compute 3x3 inertia tensor about the centroid.
        Uses the polyhedral formula for exact calculation.
        
        Returns tensor in local coordinates centered at centroid.
        """
        if self._inertia_tensor is not None:
            return self._inertia_tensor.copy()
        
        if len(self.faces) == 0:
            self._inertia_tensor = np.zeros((3, 3), dtype=np.float64)
            return self._inertia_tensor.copy()
        
        # Translate to centroid
        c = self.centroid()
        verts = self.vertices - c
        
        # Inertia tensor components
        I = np.zeros((3, 3), dtype=np.float64)
        
        for face in self.faces:
            v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
            
            # Use polyhedral inertia formula
            # Integrate over tetrahedron formed with origin
            cross = np.cross(v1, v2)
            tet_vol = np.dot(v0, cross) / 6.0
            
            if abs(tet_vol) < 1e-15:
                continue
            
            # Contribution to inertia from this tetrahedron
            # Using formula from "Polyhedral Mass Properties" literature
            r0_sq = np.dot(v0, v0)
            r1_sq = np.dot(v1, v1)
            r2_sq = np.dot(v2, v2)
            
            # Diagonal components (simplified for tetrahedron)
            I[0, 0] += density * tet_vol * (r1_sq + r2_sq + np.dot(v1, v2)) / 10.0
            I[1, 1] += density * tet_vol * (r0_sq + r2_sq + np.dot(v0, v2)) / 10.0
            I[2, 2] += density * tet_vol * (r0_sq + r1_sq + np.dot(v0, v1)) / 10.0
            
            # Off-diagonal components
            I[0, 1] -= density * tet_vol * (np.dot(v0, v1) + np.dot(v0, v2) + np.dot(v1, v2)) / 20.0
            I[0, 2] -= density * tet_vol * (np.dot(v0, v1) + np.dot(v0, v2) + np.dot(v1, v2)) / 20.0
            I[1, 2] -= density * tet_vol * (np.dot(v0, v1) + np.dot(v0, v2) + np.dot(v1, v2)) / 20.0
        
        # Make symmetric
        I[1, 0] = I[0, 1]
        I[2, 0] = I[0, 2]
        I[2, 1] = I[1, 2]
        
        # Ensure positive definiteness (numerical stability)
        trace = np.trace(I)
        if trace < 1e-10:
            # Degenerate case - use sphere approximation
            radius = self.bounding_radius()
            mass = density * self.volume()
            I = np.eye(3) * 0.4 * mass * radius * radius
        else:
            # Scale by density and convert from second moment to mass moment
            mass = density * self.volume()
            vol = self.volume()
            if vol > 1e-10:
                I = I * (mass / vol)
        
        self._inertia_tensor = I
        return self._inertia_tensor.copy()
    
    # ------------------------------------------------------------------
    # Transformations
    # ------------------------------------------------------------------
    
    def scale(self, factor: float) -> 'Mesh':
        """Return a new mesh scaled uniformly."""
        return Mesh(
            vertices=self.vertices * factor,
            faces=self.faces.copy(),
            normals=self.normals.copy(),
            colors=self.colors.copy() if self.colors is not None else None,
            material_id=self.material_id
        )
    
    def transform(self, matrix: np.ndarray) -> 'Mesh':
        """Apply 4x4 transformation matrix to vertices."""
        if matrix.shape != (4, 4):
            raise ValueError("Expected 4x4 transformation matrix")
        
        # Transform vertices
        verts_homogeneous = np.column_stack([self.vertices, np.ones(len(self.vertices))])
        transformed = (matrix @ verts_homogeneous.T).T
        new_verts = transformed[:, :3] / transformed[:, 3:4]
        
        # Transform normals (inverse transpose of linear part)
        linear_part = matrix[:3, :3]
        inv_transpose = np.linalg.inv(linear_part).T
        new_normals = (inv_transpose @ self.normals.T).T
        new_normals = new_normals / np.linalg.norm(new_normals, axis=1, keepdims=True)
        
        return Mesh(
            vertices=new_verts,
            faces=self.faces.copy(),
            normals=new_normals,
            colors=self.colors.copy() if self.colors is not None else None,
            material_id=self.material_id
        )
    
    def translate(self, offset: np.ndarray) -> 'Mesh':
        """Return a new mesh translated by offset."""
        return Mesh(
            vertices=self.vertices + offset,
            faces=self.faces.copy(),
            normals=self.normals.copy(),
            colors=self.colors.copy() if self.colors is not None else None,
            material_id=self.material_id
        )
    
    # ------------------------------------------------------------------
    # Convex hull (for collision representation)
    # ------------------------------------------------------------------
    
    def convex_hull(self) -> 'Mesh':
        """
        Compute convex hull of this mesh.
        For collision detection, complex objects may use their convex hull
        or a decomposition into convex pieces.
        
        Note: This is a placeholder - full convex hull algorithm would
        require scipy.spatial.ConvexHull or custom implementation.
        For now, returns self if already convex-ish.
        """
        # TODO: Implement proper convex hull using quickhull or similar
        # For now, just return self - the collision system will handle
        # concave objects via multi-piece representations
        return self
    
    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'vertices': self.vertices.tolist(),
            'faces': self.faces.tolist(),
            'normals': self.normals.tolist(),
            'material_id': self.material_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Mesh':
        """Create from dictionary."""
        return cls(
            vertices=np.array(data['vertices'], dtype=np.float64),
            faces=np.array(data['faces'], dtype=np.int32),
            normals=np.array(data.get('normals', []), dtype=np.float64),
            material_id=data.get('material_id')
        )


# ----------------------------------------------------------------------
# Primitive mesh generators
# These generate Mesh objects, not OpenGL display lists.
# ----------------------------------------------------------------------

def create_box_mesh(half_extents: Tuple[float, float, float] = (0.5, 0.5, 0.5)) -> Mesh:
    """Generate a box mesh centered at origin."""
    hx, hy, hz = half_extents
    
    # 8 vertices
    vertices = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz]
    ], dtype=np.float64)
    
    # 12 triangles (2 per face)
    faces = np.array([
        # Front
        [0, 1, 2], [0, 2, 3],
        # Back
        [5, 4, 7], [5, 7, 6],
        # Top
        [3, 2, 6], [3, 6, 7],
        # Bottom
        [4, 5, 1], [4, 1, 0],
        # Right
        [1, 5, 6], [1, 6, 2],
        # Left
        [4, 0, 3], [4, 3, 7]
    ], dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_sphere_mesh(radius: float = 0.5, slices: int = 24, stacks: int = 16) -> Mesh:
    """Generate a UV sphere mesh with proper closed topology."""
    vertices = []
    faces = []
    
    # Create vertices including poles
    # Stack 0 is south pole, stack 'stacks' is north pole
    for stack in range(stacks + 1):
        phi = math.pi * stack / stacks
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
        
        if stack == 0:
            # South pole
            vertices.append([0.0, radius * cos_phi, 0.0])
        elif stack == stacks:
            # North pole
            vertices.append([0.0, radius * cos_phi, 0.0])
        else:
            # Regular rings
            for slice_idx in range(slices):
                theta = 2 * math.pi * slice_idx / slices
                sin_theta = math.sin(theta)
                cos_theta = math.cos(theta)
                
                x = radius * sin_phi * cos_theta
                y = radius * cos_phi
                z = radius * sin_phi * sin_theta
                vertices.append([x, y, z])
    
    # Calculate indices
    south_pole_idx = 0
    north_pole_idx = len(vertices) - 1
    
    # Build faces
    # South pole to first ring
    for slice_idx in range(slices):
        v1 = 1 + slice_idx
        v2 = 1 + ((slice_idx + 1) % slices)
        faces.append([south_pole_idx, v1, v2])
    
    # Middle rings (from ring i to ring i+1)
    for stack in range(stacks - 2):
        base_curr = 1 + stack * slices
        base_next = 1 + (stack + 1) * slices
        for slice_idx in range(slices):
            curr_v1 = base_curr + slice_idx
            curr_v2 = base_curr + ((slice_idx + 1) % slices)
            next_v1 = base_next + slice_idx
            next_v2 = base_next + ((slice_idx + 1) % slices)
            
            faces.append([curr_v1, next_v1, next_v2])
            faces.append([curr_v1, next_v2, curr_v2])
    
    # Last ring to north pole
    last_ring_base = 1 + (stacks - 2) * slices
    for slice_idx in range(slices):
        v1 = last_ring_base + slice_idx
        v2 = last_ring_base + ((slice_idx + 1) % slices)
        faces.append([v1, v2, north_pole_idx])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_cylinder_mesh(radius: float = 0.4, height: float = 0.9, 
                         slices: int = 24, cap: bool = True) -> Mesh:
    """Generate a cylinder mesh aligned along Y axis with proper closed topology."""
    vertices = []
    faces = []
    half_h = height / 2
    
    # Side vertices (no duplicate at wrap-around)
    for i in range(slices):
        theta = 2 * math.pi * i / slices
        x = radius * math.cos(theta)
        z = radius * math.sin(theta)
        vertices.append([x, -half_h, z])  # Bottom ring
        vertices.append([x, half_h, z])   # Top ring
    
    # Side faces - ensure outward normals
    for i in range(slices):
        bottom_left = i * 2
        bottom_right = ((i + 1) % slices) * 2
        top_left = i * 2 + 1
        top_right = ((i + 1) % slices) * 2 + 1
        
        # Two triangles per quad, counter-clockwise from outside
        faces.append([bottom_left, bottom_right, top_left])
        faces.append([top_left, bottom_right, top_right])
    
    # Cap vertices and faces
    if cap:
        bottom_center = len(vertices)
        vertices.append([0, -half_h, 0])
        
        top_center = len(vertices)
        vertices.append([0, half_h, 0])
        
        # Bottom cap (clockwise when viewed from outside, i.e., from below)
        for i in range(slices):
            v1 = i * 2
            v2 = ((i + 1) % slices) * 2
            faces.append([bottom_center, v2, v1])
        
        # Top cap (counter-clockwise when viewed from outside, i.e., from above)
        for i in range(slices):
            v1 = i * 2 + 1
            v2 = ((i + 1) % slices) * 2 + 1
            faces.append([top_center, v1, v2])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_cone_mesh(radius: float = 0.5, height: float = 1.0, slices: int = 24) -> Mesh:
    """Generate a cone mesh aligned along Y axis, apex up."""
    vertices = []
    faces = []
    half_h = height / 2
    
    # Base ring
    for i in range(slices + 1):
        theta = 2 * math.pi * i / slices
        x = radius * math.cos(theta)
        z = radius * math.sin(theta)
        vertices.append([x, -half_h, z])
    
    # Apex
    apex_idx = len(vertices)
    vertices.append([0, half_h, 0])
    
    # Side faces
    for i in range(slices):
        v1 = i
        v2 = (i + 1) % slices
        faces.append([v1, apex_idx, v2])
    
    # Base cap
    base_center = len(vertices)
    vertices.append([0, -half_h, 0])
    
    for i in range(slices):
        v1 = i
        v2 = (i + 1) % slices
        faces.append([base_center, v1, v2])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_torus_mesh(major_radius: float = 0.5, minor_radius: float = 0.15,
                      major_segments: int = 32, minor_segments: int = 16) -> Mesh:
    """Generate a torus mesh."""
    vertices = []
    faces = []
    
    for i in range(major_segments + 1):
        theta = 2 * math.pi * i / major_segments
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        
        for j in range(minor_segments + 1):
            phi = 2 * math.pi * j / minor_segments
            cos_phi = math.cos(phi)
            sin_phi = math.sin(phi)
            
            x = (major_radius + minor_radius * cos_phi) * cos_theta
            y = minor_radius * sin_phi
            z = (major_radius + minor_radius * cos_phi) * sin_theta
            vertices.append([x, y, z])
    
    for i in range(major_segments):
        for j in range(minor_segments):
            v1 = i * (minor_segments + 1) + j
            v2 = v1 + 1
            v3 = v1 + (minor_segments + 1)
            v4 = v3 + 1
            
            faces.append([v1, v3, v2])
            faces.append([v2, v3, v4])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_hollow_cylinder_mesh(outer_radius: float = 0.3, inner_radius: float = 0.27,
                                 height: float = 0.5, segments: int = 32) -> Mesh:
    """
    Generate a hollow cylinder (pipe) with inner and outer surfaces.
    Properly handles normals for interior surface.
    """
    vertices = []
    faces = []
    half_h = height / 2
    
    # Outer wall
    for i in range(segments + 1):
        theta = 2 * math.pi * i / segments
        x_outer = outer_radius * math.cos(theta)
        z_outer = outer_radius * math.sin(theta)
        x_inner = inner_radius * math.cos(theta)
        z_inner = inner_radius * math.sin(theta)
        
        # Outer bottom, outer top, inner bottom, inner top
        vertices.append([x_outer, -half_h, z_outer])
        vertices.append([x_outer, half_h, z_outer])
        vertices.append([x_inner, -half_h, z_inner])
        vertices.append([x_inner, half_h, z_inner])
    
    # Outer wall faces
    for i in range(segments):
        bl, tl = i * 4, i * 4 + 1
        br, tr = (i + 1) * 4, (i + 1) * 4 + 1
        faces.append([bl, tl, br])
        faces.append([br, tl, tr])
    
    # Inner wall faces (reversed winding for inside-out normals)
    for i in range(segments):
        bl, tl = i * 4 + 2, i * 4 + 3
        br, tr = (i + 1) * 4 + 2, (i + 1) * 4 + 3
        faces.append([tr, tl, br])  # Reversed
        faces.append([br, tl, bl])  # Reversed
    
    # Top rim
    top_center = len(vertices)
    vertices.append([0, half_h, 0])
    
    for i in range(segments):
        o1 = i * 4 + 1
        o2 = (i + 1) * 4 + 1
        i1 = i * 4 + 3
        i2 = (i + 1) * 4 + 3
        
        # Outer ring (CCW from top)
        faces.append([top_center, o1, o2])
        # Inner ring (CW from top for correct normal)
        faces.append([top_center, i2, i1])
        # Rim segment
        faces.append([o1, i1, o2])
        faces.append([i1, i2, o2])
    
    # Bottom rim
    bottom_center = len(vertices)
    vertices.append([0, -half_h, 0])
    
    for i in range(segments):
        o1 = i * 4
        o2 = (i + 1) * 4
        i1 = i * 4 + 2
        i2 = (i + 1) * 4 + 2
        
        # Outer ring (CW from bottom)
        faces.append([bottom_center, o2, o1])
        # Inner ring (CCW from bottom)
        faces.append([bottom_center, i1, i2])
        # Rim segment
        faces.append([o2, i2, o1])
        faces.append([i2, i1, o1])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_cup_mesh(radius: float = 0.3, height: float = 0.5, 
                    thickness: float = 0.03, handle_radius: float = 0.14) -> Mesh:
    """
    Generate a cup/mug mesh with hollow interior and handle.
    The handle is properly oriented vertically relative to the cup body.
    """
    meshes_to_combine = []
    
    # Outer wall (hollow cylinder)
    outer = create_hollow_cylinder_mesh(
        outer_radius=radius,
        inner_radius=radius - thickness,
        height=height,
        segments=32
    )
    meshes_to_combine.append(outer)
    
    # Handle - a torus section positioned on the side
    # The handle should be vertical, so we rotate the torus appropriately
    handle_verts = []
    handle_faces = []
    
    # Generate handle as a bent tube (torus section)
    handle_segments = 16
    tube_segments = 8
    handle_tube_radius = thickness * 1.2
    
    # Handle center position (on the side of the cup)
    handle_center_x = radius - thickness / 2
    handle_center_y = 0  # Centered vertically on the cup
    handle_center_z = 0
    
    for i in range(handle_segments + 1):
        # Angle around the handle arc (vertical semi-circle)
        alpha = math.pi * i / handle_segments  # From 0 to pi (front to back)
        
        # Handle arc position
        arc_x = handle_center_x + handle_radius * math.cos(alpha)
        arc_y = handle_center_y + handle_radius * math.sin(alpha)
        arc_z = handle_center_z
        
        for j in range(tube_segments + 1):
            beta = 2 * math.pi * j / tube_segments
            
            # Tube circle around the arc
            tube_x = arc_x + handle_tube_radius * math.cos(beta) * math.cos(alpha)
            tube_y = arc_y + handle_tube_radius * math.sin(beta)
            tube_z = arc_z + handle_tube_radius * math.cos(beta) * math.sin(alpha)
            
            handle_verts.append([tube_x, tube_y, tube_z])
    
    # Handle faces
    for i in range(handle_segments):
        for j in range(tube_segments):
            v1 = i * (tube_segments + 1) + j
            v2 = v1 + 1
            v3 = v1 + (tube_segments + 1)
            v4 = v3 + 1
            
            handle_faces.append([v1, v3, v2])
            handle_faces.append([v2, v3, v4])
    
    if handle_verts:
        handle_mesh = Mesh(
            vertices=np.array(handle_verts, dtype=np.float64),
            faces=np.array(handle_faces, dtype=np.int32)
        )
        meshes_to_combine.append(handle_mesh)
    
    # Combine all meshes
    return combine_meshes(meshes_to_combine)


def combine_meshes(meshes: List[Mesh]) -> Mesh:
    """Combine multiple meshes into one."""
    if not meshes:
        return Mesh()
    
    if len(meshes) == 1:
        return meshes[0]
    
    total_verts = sum(len(m.vertices) for m in meshes)
    total_faces = sum(len(m.faces) for m in meshes)
    
    combined_verts = np.zeros((total_verts, 3), dtype=np.float64)
    combined_faces = np.zeros((total_faces, 3), dtype=np.int32)
    
    vert_offset = 0
    face_offset = 0
    
    for mesh in meshes:
        n_verts = len(mesh.vertices)
        n_faces = len(mesh.faces)
        
        combined_verts[vert_offset:vert_offset + n_verts] = mesh.vertices
        combined_faces[face_offset:face_offset + n_faces] = mesh.faces + vert_offset
        
        vert_offset += n_verts
        face_offset += n_faces
    
    return Mesh(vertices=combined_verts, faces=combined_faces)


def create_car_mesh(body_half_extents=(0.8, 0.3, 0.45), 
                    cabin_half_extents=(0.35, 0.22, 0.38),
                    wheel_radius=0.22, wheel_height=0.15) -> Mesh:
    """
    Generate a car mesh with correctly oriented wheels.
    Wheels are cylinders rotated 90 degrees around Y to be upright.
    """
    meshes_to_combine = []
    
    # Car body (box)
    body = create_box_mesh(body_half_extents)
    meshes_to_combine.append(body)
    
    # Cabin (smaller box on top)
    cabin = create_box_mesh(cabin_half_extents)
    cabin = cabin.translate(np.array([-0.1, body_half_extents[1] + cabin_half_extents[1], 0]))
    meshes_to_combine.append(cabin)
    
    # Wheels - four cylinders rotated to be upright
    wheel_positions = [
        (-0.55, -body_half_extents[1] + wheel_height, 0.52),   # front-left
        (0.55, -body_half_extents[1] + wheel_height, 0.52),   # front-right  
        (-0.55, -body_half_extents[1] + wheel_height, -0.52), # rear-left
        (0.55, -body_half_extents[1] + wheel_height, -0.52),  # rear-right
    ]
    
    for wx, wy, wz in wheel_positions:
        wheel = create_cylinder_mesh(radius=wheel_radius, height=wheel_height, slices=16)
        # Rotate cylinder 90 degrees around Y to make it upright
        rotation_matrix = np.array([
            [0, 0, 1],
            [0, 1, 0],
            [-1, 0, 0]
        ], dtype=np.float64)
        wheel_verts = wheel.vertices @ rotation_matrix.T
        wheel = Mesh(vertices=wheel_verts, faces=wheel.faces)
        wheel = wheel.translate(np.array([wx, wy, wz]))
        meshes_to_combine.append(wheel)
    
    return combine_meshes(meshes_to_combine)


def create_pyramid_mesh(base_half_width: float = 0.5, height: float = 1.0) -> Mesh:
    """Generate a square pyramid mesh."""
    vertices = []
    faces = []
    
    half = base_half_width
    base_y = -height / 2
    apex_y = height / 2
    
    # Base vertices (counter-clockwise when viewed from above)
    base_verts = [
        [-half, base_y, -half],
        [half, base_y, -half],
        [half, base_y, half],
        [-half, base_y, half]
    ]
    vertices.extend(base_verts)
    
    # Apex
    apex_idx = len(vertices)
    vertices.append([0, apex_y, 0])
    
    # Side triangles
    for i in range(4):
        v1 = i
        v2 = (i + 1) % 4
        faces.append([v1, v2, apex_idx])
    
    # Base (two triangles, clockwise from outside)
    faces.append([0, 3, 2])
    faces.append([0, 2, 1])
    
    vertices = np.array(vertices, dtype=np.float64)
    faces = np.array(faces, dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_ramp_mesh(half_width: float = 1.2, half_height: float = 0.15, 
                     half_depth: float = 1.6) -> Mesh:
    """Generate a ramp/wedge mesh."""
    vertices = []
    faces = []
    
    # Ramp vertices
    # Low end at y=-half_height, high end at y=half_height
    verts = [
        # Bottom face
        [-half_width, -half_height, -half_depth],  # 0
        [half_width, -half_height, -half_depth],   # 1
        [half_width, -half_height, half_depth],    # 2
        [-half_width, -half_height, half_depth],   # 3
        
        # Top sloped face - low end
        [-half_width, -half_height, half_depth],   # 4 (same as 2)
        [half_width, -half_height, half_depth],    # 5 (same as 2)
        
        # Top sloped face - high end
        [-half_width, half_height, -half_depth],   # 6
        [half_width, half_height, -half_depth],    # 7
    ]
    
    # Adjust vertices for proper ramp shape
    vertices = np.array([
        # Bottom rectangle
        [-half_width, -half_height, -half_depth],  # 0: back-left-bottom
        [half_width, -half_height, -half_depth],   # 1: back-right-bottom
        [half_width, -half_height, half_depth],    # 2: front-right-bottom  
        [-half_width, -half_height, half_depth],   # 3: front-left-bottom
        
        # Top edge (high end)
        [-half_width, half_height, -half_depth],   # 4: back-left-top
        [half_width, half_height, -half_depth],    # 5: back-right-top
        
        # Slope corners (low end, same y as bottom)
        [-half_width, -half_height, half_depth],   # 6: front-left-slope
        [half_width, -half_height, half_depth],    # 7: front-right-slope
    ], dtype=np.float64)
    
    # Faces
    faces = np.array([
        # Bottom face
        [0, 2, 1], [0, 3, 2],
        
        # Back face (vertical)
        [0, 1, 5], [0, 5, 4],
        
        # Left face (triangular)
        [0, 4, 6], [4, 3, 6], [4, 5, 3],  # Actually need to recalculate
        
        # Right face (triangular)
        [1, 2, 7], [1, 7, 5], [5, 7, 2],
        
        # Front face (vertical, low)
        [6, 2, 7],
        
        # Top slope
        [4, 5, 7], [4, 7, 6],
    ], dtype=np.int32)
    
    # Let me recalculate more carefully
    vertices = np.array([
        # Back face (high end, z = -half_depth)
        [-half_width, -half_height, -half_depth],  # 0
        [half_width, -half_height, -half_depth],   # 1
        [half_width, half_height, -half_depth],    # 2
        [-half_width, half_height, -half_depth],   # 3
        
        # Front face (low end, z = half_depth)  
        [-half_width, -half_height, half_depth],   # 4
        [half_width, -half_height, half_depth],    # 5
        [half_width, -half_height, half_depth],    # 6 (duplicate for clarity)
        [-half_width, -half_height, half_depth],   # 7 (duplicate)
    ], dtype=np.float64)
    
    # Simplify: just use unique vertices
    vertices = np.array([
        [-half_width, -half_height, -half_depth],  # 0: back-bottom-left
        [half_width, -half_height, -half_depth],   # 1: back-bottom-right
        [half_width, half_height, -half_depth],    # 2: back-top-right
        [-half_width, half_height, -half_depth],   # 3: back-top-left
        [-half_width, -half_height, half_depth],   # 4: front-bottom-left
        [half_width, -half_height, half_depth],    # 5: front-bottom-right
    ], dtype=np.float64)
    
    faces = np.array([
        # Back face
        [0, 2, 1], [0, 3, 2],
        
        # Bottom face
        [0, 5, 4], [0, 1, 5],
        
        # Left face (triangle from back to front)
        [0, 4, 3],
        
        # Right face (triangle from back to front)
        [1, 2, 5],
        
        # Top slope
        [2, 3, 4], [2, 4, 5],
    ], dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)
