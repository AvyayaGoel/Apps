"""
physics/rigidbody.py

A proper rigid body implementation using mesh-based geometry.
This replaces the primitive-based RigidBody with one that:
- Uses Mesh for both render and collision geometry
- Computes mass properties from actual geometry volume
- Has full 3x3 inertia tensor
- Properly handles off-center contacts for torque
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

import numpy as np

from math_utils import IDENTITY_QUAT, quat_integrate, quat_rotate_vector, vec3
from geometry.mesh import Mesh


_id_counter = itertools.count(1)


@dataclass(eq=False)
class RigidBody:
    """
    A rigid body with mesh-based geometry representation.
    
    The body has:
    - A render mesh (detailed visual geometry)
    - A collision mesh (simplified for physics, can be convex hull or multi-piece)
    - Physical properties derived from the mesh geometry
    
    All transforms are applied to get world-space geometry.
    """
    # Identity
    id: int = field(default_factory=lambda: next(_id_counter))
    name: str = ""
    
    # Transform
    position: np.ndarray = field(default_factory=lambda: vec3())
    orientation: np.ndarray = field(default_factory=lambda: IDENTITY_QUAT.copy())
    
    # Velocities
    linear_velocity: np.ndarray = field(default_factory=lambda: vec3())
    angular_velocity: np.ndarray = field(default_factory=lambda: vec3())
    
    # Mass properties (computed from geometry + density)
    mass: float = 1.0
    inv_mass: float = 1.0
    density: float = 1000.0  # kg/m³ default
    
    # Inertia tensor in local coordinates (3x3 matrix)
    local_inertia: np.ndarray = field(default_factory=lambda: np.eye(3, dtype=np.float64))
    inv_local_inertia: np.ndarray = field(default_factory=lambda: np.eye(3, dtype=np.float64))
    
    # Geometry
    render_mesh: Optional[Mesh] = None
    collision_mesh: Optional[Mesh] = None  # Can be same as render or simplified
    
    # Material properties
    restitution: float = 0.5
    friction: float = 0.5
    
    # State
    is_static: bool = False
    is_asleep: bool = False
    sleep_timer: float = 0.0
    
    # Visual
    color: Tuple[float, float, float] = (0.7, 0.7, 0.7)
    
    def __post_init__(self):
        if self.render_mesh is not None or self.collision_mesh is not None:
            self._compute_mass_properties()
        else:
            self._update_inv_mass()
    
    # ------------------------------------------------------------------
    # Mass property computation from mesh geometry
    # ------------------------------------------------------------------
    
    def _compute_mass_properties(self) -> None:
        """Compute mass, center of mass, and inertia tensor from collision mesh."""
        mesh = self.collision_mesh if self.collision_mesh is not None else self.render_mesh
        
        if mesh is None:
            self._update_inv_mass()
            return
        
        if self.is_static:
            self.mass = 0.0
            self.inv_mass = 0.0
            self.local_inertia = np.zeros((3, 3), dtype=np.float64)
            self.inv_local_inertia = np.zeros((3, 3), dtype=np.float64)
            return
        
        # Compute volume and centroid from mesh
        volume = mesh.volume()
        centroid = mesh.centroid()
        
        # Mass = density * volume
        self.mass = max(0.001, self.density * volume)
        self._update_inv_mass()
        
        # Compute inertia tensor about centroid
        self.local_inertia = mesh.inertia_tensor(self.density)
        
        # Ensure positive definiteness
        eigenvalues = np.linalg.eigvalsh(self.local_inertia)
        if np.any(eigenvalues < 1e-10):
            # Fallback to box approximation
            bounds_min, bounds_max = mesh.compute_bounds()
            size = bounds_max - bounds_min
            m = self.mass
            sx, sy, sz = size
            self.local_inertia = np.array([
                [m * (sy*sy + sz*sz) / 12, 0, 0],
                [0, m * (sx*sx + sz*sz) / 12, 0],
                [0, 0, m * (sx*sx + sy*sy) / 12]
            ], dtype=np.float64)
        
        self._update_inv_inertia()
    
    def _update_inv_mass(self) -> None:
        if self.is_static or self.mass <= 1e-9:
            self.inv_mass = 0.0
        else:
            self.inv_mass = 1.0 / self.mass
    
    def _update_inv_inertia(self) -> None:
        """Compute inverse of local inertia tensor."""
        try:
            self.inv_local_inertia = np.linalg.inv(self.local_inertia)
        except np.linalg.LinAlgError:
            self.inv_local_inertia = np.zeros((3, 3), dtype=np.float64)
    
    def get_world_inertia(self) -> np.ndarray:
        """Get inertia tensor in world coordinates."""
        if self.is_static:
            return np.zeros((3, 3), dtype=np.float64)
        
        # Rotate local inertia to world space: R * I_local * R^T
        R = self._quat_to_rotation_matrix()
        return R @ self.local_inertia @ R.T
    
    def get_world_inv_inertia(self) -> np.ndarray:
        """Get inverse inertia tensor in world coordinates."""
        if self.is_static:
            return np.zeros((3, 3), dtype=np.float64)
        
        R = self._quat_to_rotation_matrix()
        return R @ self.inv_local_inertia @ R.T
    
    def _quat_to_rotation_matrix(self) -> np.ndarray:
        """Convert quaternion to 3x3 rotation matrix."""
        x, y, z, w = self.orientation
        return np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y]
        ], dtype=np.float64)
    
    # ------------------------------------------------------------------
    # Scale and density setters
    # ------------------------------------------------------------------
    
    def set_scale(self, scale: float) -> None:
        """Apply uniform scale to meshes and recompute mass properties."""
        scale = max(0.01, scale)
        if self.render_mesh is not None:
            self.render_mesh = self.render_mesh.scale(scale)
        if self.collision_mesh is not None and self.collision_mesh is not self.render_mesh:
            self.collision_mesh = self.collision_mesh.scale(scale)
        self._compute_mass_properties()
    
    def set_density(self, density: float) -> None:
        """Change density and recompute mass."""
        self.density = max(0.001, density)
        self._compute_mass_properties()
    
    def set_mass(self, mass: float) -> None:
        """Set mass directly, adjusting density to match."""
        mesh = self.collision_mesh if self.collision_mesh is not None else self.render_mesh
        if mesh is not None:
            volume = mesh.volume()
            if volume > 1e-9:
                self.density = mass / volume
        self.mass = max(0.001, mass)
        self._update_inv_mass()
    
    # ------------------------------------------------------------------
    # Geometry queries
    # ------------------------------------------------------------------
    
    def get_world_mesh(self, mesh: Optional[Mesh] = None) -> Optional[Mesh]:
        """Get mesh transformed to world space."""
        if mesh is None:
            mesh = self.render_mesh
        if mesh is None:
            return None
        
        # Build transformation matrix
        R = self._quat_to_rotation_matrix()
        transform = np.eye(4, dtype=np.float64)
        transform[:3, :3] = R
        transform[:3, 3] = self.position
        
        return mesh.transform(transform)
    
    def get_lowest_point(self) -> float:
        """Get the lowest Y coordinate of the transformed geometry."""
        mesh = self.collision_mesh if self.collision_mesh is not None else self.render_mesh
        if mesh is None:
            return self.position[1]
        
        # Transform all vertices and find minimum Y
        R = self._quat_to_rotation_matrix()
        transformed_verts = (R @ mesh.vertices.T).T + self.position
        return float(transformed_verts[:, 1].min())
    
    def bounding_radius(self) -> float:
        """Get bounding sphere radius."""
        mesh = self.collision_mesh if self.collision_mesh is not None else self.render_mesh
        if mesh is None:
            return 0.5
        return mesh.bounding_radius()
    
    def aabb(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get axis-aligned bounding box in world space."""
        mesh = self.collision_mesh if self.collision_mesh is not None else self.render_mesh
        if mesh is None:
            r = 0.5
            return self.position - vec3(r, r, r), self.position + vec3(r, r, r)
        
        world_mesh = self.get_world_mesh(mesh)
        if world_mesh is None:
            r = 0.5
            return self.position - vec3(r, r, r), self.position + vec3(r, r, r)
        
        return world_mesh.compute_bounds()
    
    # ------------------------------------------------------------------
    # Physics integration
    # ------------------------------------------------------------------
    
    def apply_impulse(self, impulse: np.ndarray, contact_point: Optional[np.ndarray] = None) -> None:
        """Apply linear impulse at contact point, generating torque if off-center."""
        if self.is_static or self.inv_mass <= 0.0:
            return
        
        # Linear impulse
        self.linear_velocity += impulse * self.inv_mass
        
        # Angular impulse if contact is off-center
        if contact_point is not None:
            r = contact_point - self.position
            torque_impulse = np.cross(r, impulse)
            inv_inertia_world = self.get_world_inv_inertia()
            self.angular_velocity += inv_inertia_world @ torque_impulse
        
        self.wake()
    
    def apply_force(self, force: np.ndarray, contact_point: Optional[np.ndarray] = None) -> None:
        """Apply force (to be integrated over time)."""
        if self.is_static or self.inv_mass <= 0.0:
            return
        
        # This would typically accumulate forces for later integration
        # For now, apply directly as impulse scaled by timestep
        pass
    
    def wake(self) -> None:
        self.is_asleep = False
        self.sleep_timer = 0.0
    
    def set_static(self, static: bool) -> None:
        self.is_static = static
        if static:
            self.mass = 0.0
            self.inv_mass = 0.0
            self.linear_velocity[:] = 0.0
            self.angular_velocity[:] = 0.0
            self.is_asleep = False
        else:
            self._compute_mass_properties()
            self.wake()
    
    def integrate(self, dt: float, gravity: float, 
                  air_damping: float = 0.999, angular_damping: float = 0.995) -> None:
        """Integrate physics for one timestep."""
        if self.is_static or self.is_asleep:
            return
        
        # Apply gravity
        self.linear_velocity[1] -= gravity * dt
        
        # Apply damping
        self.linear_velocity *= air_damping
        self.angular_velocity *= angular_damping
        
        # Integrate position
        self.position += self.linear_velocity * dt
        
        # Integrate orientation
        self.orientation = quat_integrate(self.orientation, self.angular_velocity, dt)
    
    def update_sleep_state(self, dt: float, lin_threshold: float = 0.05,
                          ang_threshold: float = 0.05, time_required: float = 1.0) -> None:
        """Check if body should go to sleep."""
        if self.is_static:
            return
        
        speed = float(np.linalg.norm(self.linear_velocity))
        ang_speed = float(np.linalg.norm(self.angular_velocity))
        
        if speed < lin_threshold and ang_speed < ang_threshold:
            self.sleep_timer += dt
            if self.sleep_timer >= time_required:
                self.is_asleep = True
                self.linear_velocity[:] = 0.0
                self.angular_velocity[:] = 0.0
        else:
            self.sleep_timer = 0.0
    
    # ------------------------------------------------------------------
    # Legacy compatibility (for transition period)
    # ------------------------------------------------------------------
    
    @property
    def velocity(self) -> np.ndarray:
        return self.linear_velocity
    
    @velocity.setter
    def velocity(self, value: np.ndarray) -> None:
        self.linear_velocity = value
    
    @property
    def shape(self) -> str:
        return "mesh"
    
    @property
    def scale(self) -> float:
        return 1.0


def create_rigid_body_from_mesh(mesh: Mesh, density: float = 1000.0,
                                 static: bool = False,
                                 color: Tuple[float, float, float] = (0.7, 0.7, 0.7)) -> RigidBody:
    """Create a rigid body from a mesh, using it for both render and collision."""
    body = RigidBody(
        render_mesh=mesh,
        collision_mesh=mesh.convex_hull(),  # Use convex hull for collision
        density=density,
        is_static=static,
        color=color
    )
    return body


def create_box_body(half_extents: Tuple[float, float, float] = (0.5, 0.5, 0.5),
                    density: float = 1000.0, static: bool = False,
                    color: Tuple[float, float, float] = None) -> RigidBody:
    """Create a box rigid body."""
    from geometry.mesh import create_box_mesh
    if color is None:
        color = (0.35, 0.75, 0.35)
    mesh = create_box_mesh(half_extents)
    return create_rigid_body_from_mesh(mesh, density, static, color)


def create_sphere_body(radius: float = 0.5, density: float = 1000.0,
                       static: bool = False,
                       color: Tuple[float, float, float] = None) -> RigidBody:
    """Create a sphere rigid body."""
    from geometry.mesh import create_sphere_mesh
    if color is None:
        color = (0.25, 0.45, 0.85)
    mesh = create_sphere_mesh(radius)
    return create_rigid_body_from_mesh(mesh, density, static, color)


def create_cylinder_body(radius: float = 0.4, height: float = 0.9,
                         density: float = 1000.0, static: bool = False,
                         color: Tuple[float, float, float] = None) -> RigidBody:
    """Create a cylinder rigid body."""
    from geometry.mesh import create_cylinder_mesh
    if color is None:
        color = (0.75, 0.35, 0.8)
    mesh = create_cylinder_mesh(radius, height)
    return create_rigid_body_from_mesh(mesh, density, static, color)


def create_car_body(density: float = 1000.0, static: bool = False,
                    color: Tuple[float, float, float] = None) -> RigidBody:
    """Create a car rigid body with properly oriented wheels."""
    from geometry.mesh import create_car_mesh
    if color is None:
        color = (0.8, 0.2, 0.2)
    mesh = create_car_mesh()
    return create_rigid_body_from_mesh(mesh, density, static, color)


def create_cup_body(density: float = 1000.0, static: bool = False,
                    color: Tuple[float, float, float] = None) -> RigidBody:
    """Create a cup/mug rigid body with handle."""
    from geometry.mesh import create_cup_mesh
    if color is None:
        color = (0.9, 0.9, 0.95)
    mesh = create_cup_mesh()
    return create_rigid_body_from_mesh(mesh, density, static, color)
