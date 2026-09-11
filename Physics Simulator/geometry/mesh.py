"""
geometry/mesh.py

A proper mesh-first geometry system containing:
- vertices, faces/triangles
- normals
- topology information
- material information where needed
- local-space bounds
- closed/manifold validation
- volume calculation
- centroid calculation
- inertia tensor calculation

All objects are ultimately represented by meshes.
Primitive generators exist only as procedural mesh-generation functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import numpy as np

from math_utils import vec3, normalize


@dataclass
class Mesh:
    """
    A general mesh representation containing vertices, faces, normals,
    and optional material/topology information.
    """
    # Core geometry
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.float64))
    faces: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=np.int32))
    
    # Computed/optional data
    normals: Optional[np.ndarray] = None
    face_normals: Optional[np.ndarray] = None
    
    # Material info (optional)
    material_id: Optional[int] = None
    
    # Local-space bounds (computed on demand)
    _bounds_min: Optional[np.ndarray] = None
    _bounds_max: Optional[np.ndarray] = None
    
    # Validation state
    _is_closed: Optional[bool] = None
    _volume: Optional[float] = None
    _centroid: Optional[np.ndarray] = None
    _inertia_tensor: Optional[np.ndarray] = None
    
    def __post_init__(self):
        if len(self.vertices) > 0 and self.normals is None:
            self.compute_normals()
    
    @property
    def vertex_count(self) -> int:
        return len(self.vertices)
    
    @property
    def face_count(self) -> int:
        return len(self.faces)
    
    @property
    def bounds_min(self) -> np.ndarray:
        if self._bounds_min is None:
            if len(self.vertices) == 0:
                self._bounds_min = vec3()
            else:
                self._bounds_min = self.vertices.min(axis=0)
        return self._bounds_min
    
    @property
    def bounds_max(self) -> np.ndarray:
        if self._bounds_max is None:
            if len(self.vertices) == 0:
                self._bounds_max = vec3()
            else:
                self._bounds_max = self.vertices.max(axis=0)
        return self._bounds_max
    
    @property
    def center(self) -> np.ndarray:
        return (self.bounds_min + self.bounds_max) * 0.5
    
    @property
    def extents(self) -> np.ndarray:
        return self.bounds_max - self.bounds_min
    
    def compute_normals(self) -> None:
        """Compute per-vertex normals from face geometry."""
        if len(self.faces) == 0 or len(self.vertices) == 0:
            self.normals = np.zeros((0, 3), dtype=np.float64)
            self.face_normals = np.zeros((0, 3), dtype=np.float64)
            return
        
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        
        edge1 = v1 - v0
        edge2 = v2 - v0
        face_normals = np.cross(edge1, edge2)
        
        lengths = np.linalg.norm(face_normals, axis=1, keepdims=True)
        lengths[lengths < 1e-10] = 1.0
        self.face_normals = face_normals / lengths
        
        self.normals = np.zeros_like(self.vertices)
        for i in range(3):
            vertex_indices = self.faces[:, i]
            np.add.at(self.normals, vertex_indices, self.face_normals)
        
        vertex_lengths = np.linalg.norm(self.normals, axis=1, keepdims=True)
        vertex_lengths[vertex_lengths < 1e-10] = 1.0
        self.normals = self.normals / vertex_lengths
    
    def is_closed(self) -> bool:
        """Check if the mesh is closed (manifold without boundary)."""
        if self._is_closed is not None:
            return self._is_closed
        
        if len(self.faces) == 0:
            self._is_closed = False
            return False
        
        edge_count: Dict[Tuple[int, int], int] = {}
        
        for face in self.faces:
            for i in range(3):
                v1, v2 = int(face[i]), int(face[(i + 1) % 3])
                edge = (min(v1, v2), max(v1, v2))
                edge_count[edge] = edge_count.get(edge, 0) + 1
        
        for count in edge_count.values():
            if count != 2:
                self._is_closed = False
                return False
        
        self._is_closed = True
        return True
    
    def compute_volume(self) -> float:
        """Compute the signed volume of the mesh using divergence theorem."""
        if self._volume is not None:
            return self._volume
        
        if not self.is_closed():
            self._volume = 0.0
            return 0.0
        
        if len(self.faces) == 0 or len(self.vertices) == 0:
            self._volume = 0.0
            return 0.0
        
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        
        cross = np.cross(v1, v2)
        dot_products = np.sum(v0 * cross, axis=1)
        total_volume = np.sum(dot_products) / 6.0
        
        self._volume = abs(total_volume)
        return self._volume
    
    def compute_centroid(self) -> np.ndarray:
        """Compute the centroid (center of mass for uniform density)."""
        if self._centroid is not None:
            return self._centroid.copy()
        
        if not self.is_closed() or len(self.faces) == 0:
            if len(self.vertices) == 0:
                self._centroid = vec3()
            else:
                self._centroid = self.vertices.mean(axis=0)
            return self._centroid.copy()
        
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        
        cross = np.cross(v1, v2)
        signed_volumes = np.sum(v0 * cross, axis=1) / 6.0
        
        tetra_centroids = (v0 + v1 + v2) / 4.0
        
        total_volume = np.sum(np.abs(signed_volumes))
        if total_volume < 1e-10:
            self._centroid = self.vertices.mean(axis=0)
        else:
            weighted_sum = np.sum(tetra_centroids * np.abs(signed_volumes)[:, np.newaxis], axis=0)
            self._centroid = weighted_sum / total_volume
        
        return self._centroid.copy()
    
    def compute_inertia_tensor(self, density: float = 1.0) -> np.ndarray:
        """
        Compute the 3x3 inertia tensor in local coordinates.
        Uses tetrahedral decomposition for exact calculation.
        
        For uniform scaling by factor s at constant density:
        - volume scales as s³
        - mass scales as s³  
        - inertia scales as s⁵
        """
        if self._inertia_tensor is not None:
            return self._inertia_tensor.copy()
        
        if not self.is_closed() or len(self.faces) == 0:
            extents = self.extents
            volume = np.prod(extents)
            mass = density * volume
            hx, hy, hz = extents / 2
            Ixx = mass * (hy**2 + hz**2) / 3
            Iyy = mass * (hx**2 + hz**2) / 3
            Izz = mass * (hx**2 + hy**2) / 3
            self._inertia_tensor = np.diag([Ixx, Iyy, Izz])
            return self._inertia_tensor.copy()
        
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        
        total_mass = 0.0
        inertia = np.zeros((3, 3), dtype=np.float64)
        
        for i in range(len(self.faces)):
            p0 = v0[i]
            p1 = v1[i]
            p2 = v2[i]
            
            vol = np.dot(p0, np.cross(p1, p2)) / 6.0
            mass_tetra = density * abs(vol)
            total_mass += mass_tetra
            
            c = (p0 + p1 + p2) / 4.0
            
            tetra_verts = np.array([[0, 0, 0], p0, p1, p2])
            tetra_extents = tetra_verts.max(axis=0) - tetra_verts.min(axis=0)
            dx, dy, dz = tetra_extents
            
            Ixx_local = mass_tetra * (dy**2 + dz**2) / 12
            Iyy_local = mass_tetra * (dx**2 + dz**2) / 12
            Izz_local = mass_tetra * (dx**2 + dy**2) / 12
            
            cx, cy, cz = c
            r_sq = cx**2 + cy**2 + cz**2
            
            inertia[0, 0] += Ixx_local + mass_tetra * (cy**2 + cz**2)
            inertia[1, 1] += Iyy_local + mass_tetra * (cx**2 + cz**2)
            inertia[2, 2] += Izz_local + mass_tetra * (cx**2 + cy**2)
            
            inertia[0, 1] -= mass_tetra * cx * cy
            inertia[0, 2] -= mass_tetra * cx * cz
            inertia[1, 2] -= mass_tetra * cy * cz
        
        inertia[1, 0] = inertia[0, 1]
        inertia[2, 0] = inertia[0, 2]
        inertia[2, 1] = inertia[1, 2]
        
        self._inertia_tensor = inertia
        return inertia.copy()
    
    def get_lowest_point(self, orientation: np.ndarray, position: np.ndarray) -> float:
        """Get the lowest Y coordinate of the transformed mesh."""
        if len(self.vertices) == 0:
            return position[1]
        
        from math_utils import quat_rotate_vector
        
        min_y = float('inf')
        for vertex in self.vertices:
            transformed = quat_rotate_vector(orientation, vertex) + position
            if transformed[1] < min_y:
                min_y = transformed[1]
        
        return min_y
    
    def scale_uniform(self, factor: float) -> 'Mesh':
        """Return a new mesh scaled uniformly."""
        return Mesh(
            vertices=self.vertices * factor,
            faces=self.faces.copy(),
            normals=self.normals.copy() if self.normals is not None else None,
            face_normals=self.face_normals.copy() if self.face_normals is not None else None,
        )
    
    def transform(self, translation: np.ndarray, rotation_quat: np.ndarray, scale: float = 1.0) -> 'Mesh':
        """Return a transformed copy of this mesh."""
        from math_utils import quat_rotate_vector
        
        new_vertices = np.array([
            quat_rotate_vector(rotation_quat, v * scale) + translation
            for v in self.vertices
        ], dtype=np.float64)
        
        return Mesh(
            vertices=new_vertices,
            faces=self.faces.copy(),
        )
    
    def merge(self, other: 'Mesh', transform: Optional[np.ndarray] = None) -> 'Mesh':
        """Merge another mesh into this one."""
        if len(other.vertices) == 0:
            return Mesh(
                vertices=self.vertices.copy(),
                faces=self.faces.copy(),
                normals=self.normals.copy() if self.normals is not None else None,
                face_normals=self.face_normals.copy() if self.face_normals is not None else None,
            )
        
        if len(self.vertices) == 0:
            return Mesh(
                vertices=other.vertices.copy(),
                faces=other.faces.copy(),
                normals=other.normals.copy() if other.normals is not None else None,
                face_normals=other.face_normals.copy() if other.face_normals is not None else None,
            )
        
        offset = len(self.vertices)
        new_faces = np.vstack([
            self.faces,
            other.faces + offset
        ])
        
        new_vertices = np.vstack([self.vertices, other.vertices])
        
        new_normals = None
        if self.normals is not None and other.normals is not None:
            new_normals = np.vstack([self.normals, other.normals])
        
        new_face_normals = None
        if self.face_normals is not None and other.face_normals is not None:
            new_face_normals = np.vstack([self.face_normals, other.face_normals])
        
        return Mesh(
            vertices=new_vertices,
            faces=new_faces,
            normals=new_normals,
            face_normals=new_face_normals,
        )
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate the mesh and return (is_valid, list_of_issues)."""
        issues = []
        
        if len(self.vertices) == 0:
            issues.append("Mesh has no vertices")
            return False, issues
        
        if len(self.faces) == 0:
            issues.append("Mesh has no faces")
            return False, issues
        
        if self.faces.max() >= len(self.vertices):
            issues.append(f"Face indices exceed vertex count")
            return False, issues
        
        if self.faces.min() < 0:
            issues.append("Face indices contain negative values")
            return False, issues
        
        for i, face in enumerate(self.faces):
            v0, v1, v2 = self.vertices[face]
            edge1 = v1 - v0
            edge2 = v2 - v0
            area = np.linalg.norm(np.cross(edge1, edge2)) / 2
            if area < 1e-10:
                issues.append(f"Degenerate face {i}")
        
        if not self.is_closed():
            issues.append("Mesh is not closed")
        
        return len(issues) == 0, issues


def create_box_mesh(half_extents: Tuple[float, float, float] = (0.5, 0.5, 0.5)) -> Mesh:
    """Create a box mesh centered at origin."""
    hx, hy, hz = half_extents
    
    vertices = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ], dtype=np.float64)
    
    faces = np.array([
        [0, 1, 2], [0, 2, 3],
        [5, 4, 7], [5, 7, 6],
        [3, 2, 6], [3, 6, 7],
        [4, 5, 1], [4, 1, 0],
        [1, 5, 6], [1, 6, 2],
        [4, 0, 3], [4, 3, 7],
    ], dtype=np.int32)
    
    return Mesh(vertices=vertices, faces=faces)


def create_sphere_mesh(radius: float = 0.5, subdivisions: int = 3) -> Mesh:
    """Create a sphere mesh using recursive subdivision of an icosahedron."""
    phi = (1 + math.sqrt(5)) / 2
    vertices = np.array([
        [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
        [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
        [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1],
    ], dtype=np.float64)
    
    vertices = vertices / np.linalg.norm(vertices, axis=1, keepdims=True)
    
    faces = np.array([
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ], dtype=np.int32)
    
    for _ in range(subdivisions):
        new_faces = []
        vertex_cache: Dict[Tuple[int, int], int] = {}
        verts_list = vertices.tolist()
        
        def get_midpoint(i: int, j: int) -> int:
            key = (min(i, j), max(i, j))
            if key in vertex_cache:
                return vertex_cache[key]
            
            mid = (np.array(verts_list[i]) + np.array(verts_list[j])) / 2
            mid = mid / np.linalg.norm(mid)
            
            idx = len(verts_list)
            verts_list.append(mid.tolist())
            vertex_cache[key] = idx
            return idx
        
        for face in faces:
            i, j, k = face
            a = get_midpoint(i, j)
            b = get_midpoint(j, k)
            c = get_midpoint(k, i)
            
            new_faces.extend([
                [i, a, c],
                [j, b, a],
                [k, c, b],
                [a, b, c],
            ])
        
        faces = np.array(new_faces, dtype=np.int32)
        vertices = np.array(verts_list, dtype=np.float64)
    
    vertices = vertices * radius
    
    return Mesh(vertices=vertices, faces=faces)


def create_cylinder_mesh(radius: float = 0.4, height: float = 0.9, 
                         segments: int = 32, top: bool = True, bottom: bool = True) -> Mesh:
    """Create a cylinder mesh centered at origin, aligned with Y axis."""
    vertices = []
    faces = []
    
    half_height = height / 2
    
    # Side vertices - alternating bottom/top ring
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        x = math.cos(theta) * radius
        z = math.sin(theta) * radius
        vertices.append([x, -half_height, z])  # Bottom ring vertex
        vertices.append([x, half_height, z])   # Top ring vertex
    
    side_start = 0
    bottom_ring_start = side_start
    top_ring_start = side_start + 1
    
    if top:
        top_center = len(vertices)
        vertices.append([0, half_height, 0])
        for i in range(segments):
            theta = 2 * math.pi * i / segments
            x = math.cos(theta) * radius
            z = math.sin(theta) * radius
            vertices.append([x, half_height, z])
    
    if bottom:
        bottom_center = len(vertices)
        vertices.append([0, -half_height, 0])
        for i in range(segments):
            theta = 2 * math.pi * i / segments
            x = math.cos(theta) * radius
            z = math.sin(theta) * radius
            vertices.append([x, -half_height, z])
    
    vertices = np.array(vertices, dtype=np.float64)
    
    # Side faces - quads as two triangles each
    for i in range(segments):
        i_next = (i + 1) % segments
        # Four corners of the quad
        bl = side_start + i * 2         # bottom-left
        tl = side_start + i * 2 + 1     # top-left
        br = side_start + i_next * 2    # bottom-right
        tr = side_start + i_next * 2 + 1  # top-right
        
        # Two triangles forming the quad
        faces.append([bl, br, tl])  # First triangle
        faces.append([tl, br, tr])  # Second triangle
    
    # Top cap - fan from center
    if top:
        for i in range(segments):
            i_next = (i + 1) % segments
            v_center = top_center
            v1 = top_ring_start + i * 2
            v2 = top_ring_start + i_next * 2
            faces.append([v_center, v1, v2])
    
    # Bottom cap - fan from center
    if bottom:
        for i in range(segments):
            i_next = (i + 1) % segments
            v_center = bottom_center
            v1 = bottom_ring_start + i * 2
            v2 = bottom_ring_start + i_next * 2
            faces.append([v_center, v2, v1])  # Reverse winding for downward normal
    
    return Mesh(vertices=vertices, faces=np.array(faces, dtype=np.int32))


def create_cone_mesh(radius: float = 0.5, height: float = 1.0, segments: int = 32) -> Mesh:
    """Create a cone mesh centered at origin, apex pointing up Y."""
    vertices = []
    faces = []
    
    half_height = height / 2
    apex_idx = 0
    vertices.append([0, half_height, 0])
    
    base_start = 1
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        x = math.cos(theta) * radius
        z = math.sin(theta) * radius
        vertices.append([x, -half_height, z])
    
    base_center = len(vertices)
    vertices.append([0, -half_height, 0])
    
    vertices = np.array(vertices, dtype=np.float64)
    
    for i in range(segments):
        i0 = apex_idx
        i1 = base_start + i
        i2 = base_start + ((i + 1) % segments)
        faces.append([i0, i2, i1])
    
    for i in range(segments):
        i0 = base_center
        i1 = base_start + i
        i2 = base_start + ((i + 1) % segments)
        faces.append([i0, i1, i2])
    
    return Mesh(vertices=vertices, faces=np.array(faces, dtype=np.int32))


def create_torus_mesh(major_radius: float = 0.5, minor_radius: float = 0.15,
                      major_segments: int = 32, minor_segments: int = 16) -> Mesh:
    """Create a torus mesh centered at origin."""
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
    
    vertices = np.array(vertices, dtype=np.float64)
    
    for i in range(major_segments):
        for j in range(minor_segments):
            i0 = i * minor_segments + j
            i1 = i * minor_segments + (j + 1) % minor_segments
            i2 = ((i + 1) % major_segments) * minor_segments + j
            i3 = ((i + 1) % major_segments) * minor_segments + (j + 1) % minor_segments
            
            faces.append([i0, i2, i1])
            faces.append([i1, i2, i3])
    
    return Mesh(vertices=vertices, faces=np.array(faces, dtype=np.int32))


def create_car_mesh() -> Mesh:
    """Create a car mesh with correctly oriented upright wheels."""
    parts = []
    
    body = create_box_mesh(half_extents=(0.8, 0.3, 0.45))
    parts.append(body)
    
    cabin = create_box_mesh(half_extents=(0.35, 0.22, 0.38))
    cabin_verts = cabin.vertices.copy()
    cabin_verts[:, 1] += 0.32
    cabin = Mesh(vertices=cabin_verts, faces=cabin.faces.copy())
    parts.append(cabin)
    
    wheel_radius = 0.22
    wheel_width = 0.15
    wheel_positions = [
        (-0.55, -0.28, 0.52),
        (0.55, -0.28, 0.52),
        (-0.55, -0.28, -0.52),
        (0.55, -0.28, -0.52),
    ]
    
    for wx, wy, wz in wheel_positions:
        wheel = create_cylinder_mesh(radius=wheel_radius, height=wheel_width, segments=24)
        wheel_verts = wheel.vertices.copy()
        temp = wheel_verts[:, 1].copy()
        wheel_verts[:, 1] = wheel_verts[:, 2]
        wheel_verts[:, 2] = -temp
        wheel_verts[:, 0] += wx
        wheel_verts[:, 1] += wy
        wheel_verts[:, 2] += wz
        wheel = Mesh(vertices=wheel_verts, faces=wheel.faces.copy())
        parts.append(wheel)
    
    result = parts[0]
    for part in parts[1:]:
        result = result.merge(part)
    
    return result


def create_cup_mesh() -> Mesh:
    """Create a cup/mug mesh with hollow body and vertical handle."""
    parts = []
    
    radius = 0.3
    height = 0.5
    thickness = 0.03
    
    outer = create_cylinder_mesh(radius=radius, height=height, segments=32, top=False, bottom=True)
    parts.append(outer)
    
    inner_radius = radius - thickness
    inner = create_cylinder_mesh(radius=inner_radius, height=height - thickness*2, 
                                  segments=32, top=False, bottom=False)
    inner_verts = inner.vertices.copy()
    inner_verts[:, 1] += thickness
    inner = Mesh(vertices=inner_verts, faces=inner.faces.copy())
    parts.append(inner)
    
    rim = create_torus_mesh(major_radius=radius - thickness/2, minor_radius=thickness*1.2,
                            major_segments=32, minor_segments=8)
    rim_verts = rim.vertices.copy()
    rim_verts[:, 1] += height / 2
    rim = Mesh(vertices=rim_verts, faces=rim.faces.copy())
    parts.append(rim)
    
    handle_radius = 0.1
    handle_thickness = 0.025
    handle_verts = []
    handle_faces = []
    
    for i in range(20):
        t = math.pi * i / 19
        cx = radius + handle_radius * 0.5
        hx = cx + handle_radius * math.cos(t)
        hy = (t - math.pi/2) * height * 0.5
        hz = 0
        
        for j in range(8):
            phi = 2 * math.pi * j / 8
            rx = handle_thickness * math.cos(phi)
            ry = handle_thickness * math.sin(phi)
            handle_verts.append([hx + rx, hy + ry, hz])
    
    for i in range(19):
        for j in range(8):
            i0 = i * 8 + j
            i1 = i * 8 + (j + 1) % 8
            i2 = (i + 1) * 8 + j
            i3 = (i + 1) * 8 + (j + 1) % 8
            handle_faces.append([i0, i2, i1])
            handle_faces.append([i1, i2, i3])
    
    handle_verts = np.array(handle_verts, dtype=np.float64)
    handle = Mesh(vertices=handle_verts, faces=np.array(handle_faces, dtype=np.int32))
    parts.append(handle)
    
    result = parts[0]
    for part in parts[1:]:
        result = result.merge(part)
    
    return result


def create_rocket_mesh() -> Mesh:
    """Create a rocket with cylindrical body and conical nose."""
    parts = []
    
    body_radius = 0.25
    body_height = 0.8
    body = create_cylinder_mesh(radius=body_radius, height=body_height, segments=24)
    parts.append(body)
    
    nose = create_cone_mesh(radius=body_radius, height=0.4, segments=24)
    nose_verts = nose.vertices.copy()
    nose_verts[:, 1] += body_height / 2
    nose = Mesh(vertices=nose_verts, faces=nose.faces.copy())
    parts.append(nose)
    
    fin_height = 0.25
    fin_length = 0.2
    for i in range(4):
        angle = math.pi / 2 * i
        fx = math.cos(angle) * body_radius
        fz = math.sin(angle) * body_radius
        
        fin_verts = np.array([
            [fx, -body_height/2, fz],
            [fx + math.cos(angle)*fin_length, -body_height/2 - fin_height, fz + math.sin(angle)*fin_length],
            [fx, -body_height/2 - fin_height*0.3, fz],
        ], dtype=np.float64)
        
        fin_faces = np.array([[0, 1, 2], [0, 2, 1]], dtype=np.int32)
        fin = Mesh(vertices=fin_verts, faces=fin_faces)
        parts.append(fin)
    
    result = parts[0]
    for part in parts[1:]:
        result = result.merge(part)
    
    return result


MESH_GENERATORS = {
    "box": lambda: create_box_mesh(),
    "sphere": lambda: create_sphere_mesh(),
    "cylinder": lambda: create_cylinder_mesh(),
    "cone": lambda: create_cone_mesh(),
    "torus": lambda: create_torus_mesh(),
    "car": create_car_mesh,
    "cup": create_cup_mesh,
    "rocket": create_rocket_mesh,
}


def get_primitive_mesh(shape: str, params: dict) -> Mesh:
    """Get a primitive mesh by shape name and parameters."""
    if shape == "box":
        he = params.get("half_extents", (0.5, 0.5, 0.5))
        return create_box_mesh(he)
    elif shape == "sphere":
        r = params.get("radius", 0.5)
        subs = params.get("subdivisions", 3)
        return create_sphere_mesh(r, subs)
    elif shape == "cylinder":
        r = params.get("radius", 0.4)
        h = params.get("height", 0.9)
        return create_cylinder_mesh(r, h)
    elif shape == "cone":
        r = params.get("radius", 0.5)
        h = params.get("height", 1.0)
        return create_cone_mesh(r, h)
    elif shape == "torus":
        major_r = params.get("radius", 0.5)
        minor_r = params.get("tube_radius", 0.15)
        return create_torus_mesh(major_r, minor_r)
    else:
        return create_box_mesh()


def get_object_mesh(object_kind: str) -> Mesh:
    """Get a mesh for a named object kind."""
    if object_kind in MESH_GENERATORS:
        return MESH_GENERATORS[object_kind]()
    
    try:
        import object_catalog
        obj_def = object_catalog.CATALOG.get(object_kind)
        if obj_def:
            return get_primitive_mesh(obj_def.shape, obj_def.shape_params)
    except ImportError:
        pass
    
    return create_box_mesh()
