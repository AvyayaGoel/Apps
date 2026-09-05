"""
physics/collision.py

Narrow-phase collision detection and impulse-based response.
Now supports proper box-box (SAT) and sphere-box collisions, enabling stable stacking.
"""

from __future__ import annotations

from typing import List, Tuple, Optional

import numpy as np

from body import RigidBody, SHAPE_BOX, SHAPE_SPHERE
from math_utils import vec3, normalize, quat_rotate_vector, quat_conjugate

GROUND_NORMAL = vec3(0.0, 1.0, 0.0)


# ----------------------------------------------------------------------
# Broad phase (unchanged, but AABB now includes scale)
# ----------------------------------------------------------------------

def broad_phase_pairs(bodies: List[RigidBody]) -> List[Tuple[RigidBody, RigidBody]]:
    pairs = []
    n = len(bodies)
    aabbs = [b.aabb() for b in bodies]
    for i in range(n):
        if bodies[i].is_static and bodies[i].is_asleep:
            continue
        a_min, a_max = aabbs[i]
        for j in range(i + 1, n):
            if bodies[i].is_static and bodies[j].is_static:
                continue
            if bodies[i].is_asleep and bodies[j].is_asleep:
                continue
            b_min, b_max = aabbs[j]
            if (a_min[0] <= b_max[0] and a_max[0] >= b_min[0] and
                    a_min[1] <= b_max[1] and a_max[1] >= b_min[1] and
                    a_min[2] <= b_max[2] and a_max[2] >= b_min[2]):
                pairs.append((bodies[i], bodies[j]))
    return pairs


# ----------------------------------------------------------------------
# Ground contact (now uses scaled half-height)
# ----------------------------------------------------------------------

def resolve_ground_contact(body: RigidBody, ground_y: float, friction: float, restitution: float) -> None:
    if body.is_static:
        return
    bottom = body.bottom_y()
    penetration = ground_y - bottom
    if penetration <= 0.0:
        return

    body.wake()
    body.position[1] += penetration

    vy = body.velocity[1]
    if vy < 0.0:
        eff_restitution = body.restitution * restitution
        body.velocity[1] = -vy * eff_restitution
        if abs(body.velocity[1]) < 0.15:
            body.velocity[1] = 0.0

    eff_friction = min(1.0, body.friction * friction * 3.0)
    body.velocity[0] *= (1.0 - eff_friction)
    body.velocity[2] *= (1.0 - eff_friction)

    # Rolling for spheres/cylinders
    if body.shape in ("sphere", "cylinder"):
        radius = body.get_scaled_radius()
        if radius > 1e-6:
            body.angular_velocity[0] = -body.velocity[2] / radius
            body.angular_velocity[2] = body.velocity[0] / radius


# ----------------------------------------------------------------------
# Helper: get vertices of an oriented box
# ----------------------------------------------------------------------

def _box_vertices(body: RigidBody) -> np.ndarray:
    """Return 8 vertices of the oriented box as (8,3) array."""
    he = body.get_scaled_half_extents()
    # Local corners
    local = np.array([
        [-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1],
        [-1, 1, -1], [1, 1, -1], [1, 1, 1], [-1, 1, 1]
    ], dtype=np.float64) * he
    # Rotate and translate
    verts = np.zeros_like(local)
    for i, v in enumerate(local):
        verts[i] = quat_rotate_vector(body.orientation, v) + body.position
    return verts


# ----------------------------------------------------------------------
# SAT for box-box
# ----------------------------------------------------------------------

def _box_box_contact(a: RigidBody, b: RigidBody) -> Optional[Tuple[np.ndarray, float, np.ndarray]]:
    """Returns (normal, penetration, contact_point) or None."""
    # Get vertices and face normals (axes)
    verts_a = _box_vertices(a)
    verts_b = _box_vertices(b)

    # Generate separating axes: 3 face normals of each box, and 9 edge cross products
    axes = []
    # Face normals of A (in world space)
    for i in range(3):
        axis = np.eye(3)[i]
        axes.append(quat_rotate_vector(a.orientation, axis))
    # Face normals of B
    for i in range(3):
        axis = np.eye(3)[i]
        axes.append(quat_rotate_vector(b.orientation, axis))
    # Edge cross products (9 combinations)
    edges_a = [np.eye(3)[i] for i in range(3)]
    edges_b = [np.eye(3)[i] for i in range(3)]
    for e_a in edges_a:
        e_a_world = quat_rotate_vector(a.orientation, e_a)
        for e_b in edges_b:
            e_b_world = quat_rotate_vector(b.orientation, e_b)
            axis = np.cross(e_a_world, e_b_world)
            if np.linalg.norm(axis) > 1e-8:
                axes.append(normalize(axis))

    # Project both boxes onto each axis, find overlap
    best_overlap = float('inf')
    best_axis = None
    for axis in axes:
        # Project vertices of A
        proj_a = np.dot(verts_a, axis)
        min_a, max_a = proj_a.min(), proj_a.max()
        proj_b = np.dot(verts_b, axis)
        min_b, max_b = proj_b.min(), proj_b.max()
        overlap = min(max_a - min_b, max_b - min_a)
        if overlap < 0:
            return None  # Separated
        if overlap < best_overlap:
            best_overlap = overlap
            best_axis = axis

    # Ensure normal points from A to B
    center_diff = b.position - a.position
    if np.dot(center_diff, best_axis) < 0:
        best_axis = -best_axis

    # Compute contact point: use the centroid of the overlapping region (approximation)
    # Simple: use the center of A's projection onto the axis, or the midpoint of the two centers
    # For simplicity, we use the midpoint of the two centers projected onto the axis
    # But a better approach: use the support point in the direction of -normal from A.
    # We'll just use the contact point as the midpoint of the two centers.
    contact_point = (a.position + b.position) * 0.5

    return best_axis, best_overlap, contact_point


# ----------------------------------------------------------------------
# Sphere-box
# ----------------------------------------------------------------------

def _sphere_box_contact(sphere: RigidBody, box: RigidBody) -> Optional[Tuple[np.ndarray, float, np.ndarray]]:
    """Sphere vs oriented box. Returns normal (pointing from box to sphere), penetration, contact point."""
    # Transform sphere center into box's local frame
    local_center = quat_rotate_vector(quat_conjugate(box.orientation), sphere.position - box.position)
    he = box.get_scaled_half_extents()
    # Find closest point on box to sphere center in local space
    closest_local = np.clip(local_center, -he, he)
    delta_local = local_center - closest_local
    dist_local = np.linalg.norm(delta_local)
    if dist_local < 1e-9:
        # Sphere center inside box: choose axis of minimal penetration
        # Use local axis with smallest distance from center to face
        abs_center = np.abs(local_center)
        min_axis = np.argmin(he - abs_center)
        normal_local = np.zeros(3)
        normal_local[min_axis] = 1.0 if local_center[min_axis] > 0 else -1.0
        normal_world = quat_rotate_vector(box.orientation, normal_local)
        penetration = he[min_axis] - abs_center[min_axis] + sphere.get_scaled_radius()
        contact_point = sphere.position - normal_world * sphere.get_scaled_radius()
        return normal_world, penetration, contact_point
    else:
        # Sphere outside box
        normal_local = delta_local / dist_local
        normal_world = quat_rotate_vector(box.orientation, normal_local)
        penetration = sphere.get_scaled_radius() - dist_local
        if penetration <= 0:
            return None
        contact_point = box.position + quat_rotate_vector(box.orientation, closest_local)
        # Normal points from box to sphere
        return normal_world, penetration, contact_point


# ----------------------------------------------------------------------
# Generic resolve function with impulse
# ----------------------------------------------------------------------

def _resolve_contact(a: RigidBody, b: RigidBody, normal: np.ndarray, penetration: float,
                     contact_point: np.ndarray) -> None:
    """Apply impulse-based resolution to separate two bodies and correct velocities."""
    total_inv_mass = a.inv_mass + b.inv_mass
    if total_inv_mass <= 1e-9:
        return

    # Position correction with a small slop prevents jitter in resting stacks.
    slop = 0.001
    percent = 0.8
    correction_mag = max(penetration - slop, 0.0) / total_inv_mass * percent
    correction = normal * correction_mag
    a.position -= correction * a.inv_mass
    b.position += correction * b.inv_mass

    # Velocity resolution
    rel_vel = b.velocity - a.velocity
    vel_along_normal = float(np.dot(rel_vel, normal))
    if vel_along_normal > 0:
        return  # separating

    restitution = min(a.restitution, b.restitution)
    if abs(vel_along_normal) < 0.5:
        restitution = 0.0
    j = -(1.0 + restitution) * vel_along_normal / total_inv_mass
    impulse = normal * j
    a.velocity -= impulse * a.inv_mass
    b.velocity += impulse * b.inv_mass

    # Friction: tangential impulse
    tangent_vel = rel_vel - normal * vel_along_normal
    t_speed = float(np.linalg.norm(tangent_vel))
    if t_speed > 1e-6:
        tangent = tangent_vel / t_speed
        friction_coef = (a.friction + b.friction) * 0.5
        jt = -t_speed * friction_coef / total_inv_mass
        friction_impulse = tangent * jt
        a.velocity -= friction_impulse * a.inv_mass
        b.velocity += friction_impulse * b.inv_mass

    # Angular impulse (approximate)
    if contact_point is not None:
        # Apply angular impulse for both bodies
        r_a = contact_point - a.position
        r_b = contact_point - b.position
        # Compute inertia tensor (sphere approximation)
        radius_a = a.bounding_radius()
        radius_b = b.bounding_radius()
        Ia = 0.4 * a.mass * radius_a * radius_a if a.mass > 0 else 0
        Ib = 0.4 * b.mass * radius_b * radius_b if b.mass > 0 else 0
        if Ia > 0:
            torque_a = np.cross(r_a, impulse)
            a.angular_velocity += torque_a / Ia
        if Ib > 0:
            torque_b = np.cross(r_b, -impulse)
            b.angular_velocity += torque_b / Ib


# ----------------------------------------------------------------------
# Pair dispatcher
# ----------------------------------------------------------------------

def resolve_pair(a: RigidBody, b: RigidBody) -> None:
    if a.is_static and b.is_static:
        return

    # Determine shapes
    shape_a = a.shape
    shape_b = b.shape

    contact = None
    if shape_a == SHAPE_BOX and shape_b == SHAPE_BOX:
        contact = _box_box_contact(a, b)
    elif shape_a == SHAPE_SPHERE and shape_b == SHAPE_BOX:
        # _sphere_box_contact returns a normal pointing box->sphere, i.e.
        # b->a here - but _resolve_contact needs a->b (proven by the
        # sphere-sphere and box-box cases), so this needs negating.
        contact = _sphere_box_contact(a, b)
        if contact:
            normal, pen, pt = contact
            contact = (-normal, pen, pt)
    elif shape_a == SHAPE_BOX and shape_b == SHAPE_SPHERE:
        # Swap args so _sphere_box_contact sees (sphere=b, box=a); it then
        # returns box(a)->sphere(b), which already IS a->b - no negation.
        contact = _sphere_box_contact(b, a)
    elif shape_a == SHAPE_SPHERE and shape_b == SHAPE_SPHERE:
        contact = _sphere_sphere_contact(a, b)
    else:
        # For other shapes (cylinder, cone), fallback to sphere-sphere approximation
        contact = _sphere_sphere_contact(a, b)

    if contact:
        normal, penetration, contact_point = contact
        _resolve_contact(a, b, normal, penetration, contact_point)
        if penetration > 0.001:
            a.wake()
            b.wake()


def _sphere_sphere_contact(a: RigidBody, b: RigidBody):
    delta = b.position - a.position
    dist = float(np.linalg.norm(delta))
    ra, rb = a.bounding_radius(), b.bounding_radius()
    min_dist = ra + rb
    if dist >= min_dist:
        return None
    if dist < 1e-6:
        normal = np.array([0.0, 1.0, 0.0])
        penetration = min_dist
    else:
        normal = delta / dist
        penetration = min_dist - dist
    contact_point = (a.position + b.position) * 0.5
    return normal, penetration, contact_point