"""
physics/collision.py

Narrow-phase collision detection and impulse-based response.
Now supports proper box-box (SAT) and sphere-box collisions, enabling stable stacking.
"""

from __future__ import annotations

from typing import List, Tuple, Optional

import numpy as np

from body import RigidBody
from math_utils import vec3, quat_rotate_vector, quat_conjugate, fast_cross3

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
# Shared point-contact impulse resolution (normal + friction, using each
# body's REAL world-space inverse inertia tensor - not a sphere
# approximation) - used by both ground contact and body-body contact so
# there is exactly one correct implementation of "apply an impulse at a
# contact point", not two diverging ones. An off-center contact point
# (e.g. one corner of a tilted box touching the ground) then naturally
# produces torque and angular velocity change here, which is what actually
# makes objects topple into a stable resting orientation under gravity +
# contact forces alone - no shape-specific "make it topple" rule needed.
# ----------------------------------------------------------------------

def _effective_mass_along(inv_mass_a: float, inv_mass_b: float,
                          r_a: np.ndarray, r_b: np.ndarray,
                          inv_I_a: Optional[np.ndarray], inv_I_b: Optional[np.ndarray],
                          axis: np.ndarray) -> float:
    """K = 1/m_a + 1/m_b + axis . ((invI_a (r_a x axis)) x r_a) + axis . ((invI_b (r_b x axis)) x r_b)
    - the standard effective-mass-along-an-axis formula for a point
    contact between two rigid bodies (either of which may be static /
    infinite-mass, in which case pass inv_mass=0 and inv_I=None)."""
    k = inv_mass_a + inv_mass_b
    if inv_I_a is not None:
        term_a = inv_I_a @ fast_cross3(r_a, axis)
        k += float(np.dot(axis, fast_cross3(term_a, r_a)))
    if inv_I_b is not None:
        term_b = inv_I_b @ fast_cross3(r_b, axis)
        k += float(np.dot(axis, fast_cross3(term_b, r_b)))
    return k


def _apply_point_contact(a: Optional[RigidBody], b: Optional[RigidBody], normal: np.ndarray,
                         penetration: float, contact_point: np.ndarray,
                         restitution_coef: float, friction_coef: float,
                         position_correct: bool = True) -> None:
    """Resolve a single point contact between `a` and `b`, where `normal`
    always points from a's side toward b's side (either may be None for a
    static half-space/ground on that side - e.g. resolve_ground_contact
    calls this with a=None, normal=GROUND_NORMAL, b=the falling body,
    since "up" is the direction from the ground into the body). Applies
    proper normal + Coulomb-friction impulses using each body's real
    world-space inverse inertia tensor, so torque from an off-center
    contact point is not lost the way a "just zero out horizontal
    velocity" ground-contact shortcut would lose it."""
    inv_mass_a = a.inv_mass if a is not None else 0.0
    inv_mass_b = b.inv_mass if b is not None else 0.0
    total_inv_mass = inv_mass_a + inv_mass_b
    if total_inv_mass <= 1e-9:
        return

    r_a = (contact_point - a.position) if a is not None else np.zeros(3)
    r_b = (contact_point - b.position) if b is not None else np.zeros(3)
    inv_I_a = a.get_world_inv_inertia_tensor() if (a is not None and inv_mass_a > 0) else None
    inv_I_b = b.get_world_inv_inertia_tensor() if (b is not None and inv_mass_b > 0) else None

    if position_correct:
        slop = 0.0015
        percent = 0.8
        correction_mag = max(penetration - slop, 0.0) * percent / total_inv_mass
        correction = normal * correction_mag
        if a is not None:
            a.position -= correction * inv_mass_a
        if b is not None:
            b.position += correction * inv_mass_b

    vel_a = (a.velocity + fast_cross3(a.angular_velocity, r_a)) if a is not None else np.zeros(3)
    vel_b = (b.velocity + fast_cross3(b.angular_velocity, r_b)) if b is not None else np.zeros(3)
    rel_vel = vel_b - vel_a
    vn = float(np.dot(rel_vel, normal))
    if vn > 0:
        return  # already separating along the normal

    # Dampen restitution for very slow impacts so resting contacts don't
    # jitter forever (a physically-motivated numerical stabilization, not a
    # per-object special case).
    eff_restitution = restitution_coef if abs(vn) > 0.5 else 0.0

    k_n = _effective_mass_along(inv_mass_a, inv_mass_b, r_a, r_b, inv_I_a, inv_I_b, normal)
    if k_n <= 1e-9:
        return
    j = -(1.0 + eff_restitution) * vn / k_n
    impulse = normal * j

    if a is not None:
        a.velocity -= impulse * inv_mass_a
        if inv_I_a is not None:
            a.angular_velocity -= inv_I_a @ fast_cross3(r_a, impulse)
    if b is not None:
        b.velocity += impulse * inv_mass_b
        if inv_I_b is not None:
            b.angular_velocity += inv_I_b @ fast_cross3(r_b, impulse)

    # Friction: Coulomb, tangential to the contact normal, using the
    # updated relative velocity's tangential component.
    vel_a = (a.velocity + fast_cross3(a.angular_velocity, r_a)) if a is not None else np.zeros(3)
    vel_b = (b.velocity + fast_cross3(b.angular_velocity, r_b)) if b is not None else np.zeros(3)
    rel_vel = vel_b - vel_a
    tangent_vel = rel_vel - normal * float(np.dot(rel_vel, normal))
    t_speed = float(np.linalg.norm(tangent_vel))
    if t_speed > 1e-6:
        tangent = tangent_vel / t_speed
        k_t = _effective_mass_along(inv_mass_a, inv_mass_b, r_a, r_b, inv_I_a, inv_I_b, tangent)
        if k_t > 1e-9:
            jt = -t_speed / k_t
            max_friction = friction_coef * abs(j)
            jt = max(-max_friction, min(max_friction, jt))
            friction_impulse = tangent * jt
            if a is not None:
                a.velocity -= friction_impulse * inv_mass_a
                if inv_I_a is not None:
                    a.angular_velocity -= inv_I_a @ fast_cross3(r_a, friction_impulse)
            if b is not None:
                b.velocity += friction_impulse * inv_mass_b
                if inv_I_b is not None:
                    b.angular_velocity += inv_I_b @ fast_cross3(r_b, friction_impulse)


# ----------------------------------------------------------------------
# Ground contact
# ----------------------------------------------------------------------

def resolve_ground_contact(body: RigidBody, ground_y: float, friction: float, restitution: float) -> None:
    if body.is_static or body.is_asleep:
        # A sleeping body needs no further ground-contact processing until
        # something else (a collision from another body, an explicit
        # wake()) wakes it - see the regression test for why this matters:
        # this function used to call body.wake() unconditionally whenever
        # penetration was positive, but a resting body has a permanent tiny
        # residual penetration by design (the position-correction below
        # only removes 80% of penetration per pass, leaving ~1-2mm forever
        # in steady state - that's normal Baumgarte slop, not a new
        # collision). That meant EVERY resting body called wake() on
        # itself every single substep forever, resetting its own sleep
        # timer back to 0 right before the sleep check ran, so no object
        # could ever actually fall asleep - paying full contact-resolution
        # cost (including a full transformed-mesh-vertex computation)
        # every substep, forever, for every object in the scene.
        return

    # Use the actual lowest point(s) of the transformed mesh as the contact
    # point, not an implicit "whole body moves as one" assumption - this is
    # what lets an off-center/tilted contact generate real torque (see
    # _apply_point_contact) instead of the object being corrected as if the
    # contact were always directly under its center of mass.
    verts = body.transformed_vertices()
    if len(verts) == 0:
        return
    min_y = float(verts[:, 1].min())
    penetration = ground_y - min_y
    if penetration <= 0.0:
        return

    # A flat face resting on the ground has many vertices at (near) the
    # same lowest height at once - use their centroid as a single
    # representative contact point. This correctly produces near-zero net
    # torque for a flat, already-settled face (as it should), while a
    # single low corner (e.g. a tilted box balanced on one edge) still
    # contributes real off-center torque.
    eps = max(1e-4, 0.01 * float(np.max(body.scale)))
    contact_mask = verts[:, 1] <= (min_y + eps)
    contact_point = verts[contact_mask].mean(axis=0)
    contact_point[1] = ground_y

    _apply_point_contact(
        a=None, b=body, normal=GROUND_NORMAL, penetration=penetration,
        contact_point=contact_point,
        restitution_coef=body.restitution * restitution,
        friction_coef=min(1.0, body.friction * friction),
    )

    # NOTE: there is deliberately no "if this is a sphere/cylinder, force
    # rolling" override here any more. That was object-type-specific code
    # that overwrote angular velocity outright, so it (a) only ever fired
    # for two hardcoded shape names - an imported ball or a user-made
    # round shape rolled like a brick - and (b) discarded the angular
    # velocity the friction impulse had just computed. Rolling now emerges
    # from the tangential friction impulse acting off-centre at the
    # contact point, which is the actual physics and works for ANY
    # geometry, named or not.


# ----------------------------------------------------------------------
# Helper: get vertices of an oriented box
# ----------------------------------------------------------------------

_LOCAL_BOX_CORNERS = np.array([
    [-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1],
    [-1, 1, -1], [1, 1, -1], [1, 1, 1], [-1, 1, 1]
], dtype=np.float64)


def _box_vertices(body: RigidBody) -> np.ndarray:
    """Return 8 vertices of the oriented bounding box as (8,3) array.
    Works generically for any shape via get_scaled_half_extents()/
    get_obb_center_offset() (mesh-bounds-derived), not just SHAPE_BOX -
    this is what lets compound objects like the car or mug collide as a
    reasonable OBB instead of the previous inaccurate bounding-sphere
    fallback (see resolve_pair's shape dispatch below).

    Uses a single 3x3 rotation matrix and one vectorized matmul rather
    than 8 individual quat_rotate_vector calls - with many bodies in the
    scene, this function and _box_axes are called extremely often (every
    SAT test, every substep, every pair), and per-call quaternion-rotate
    overhead was a measurable chunk of the physics-step cost profiled
    while chasing a real reported slowdown with more than a few objects
    on screen."""
    he = body.get_scaled_half_extents()
    center_offset = body.get_obb_center_offset()
    local = _LOCAL_BOX_CORNERS * he + center_offset
    R = body.get_rotation_matrix()
    return local @ R.T + body.position


def _box_axes(body: RigidBody) -> np.ndarray:
    """The body's 3 local axes (X, Y, Z) in world space, as a (3,3) array
    of row vectors - these serve as both the box's face normals AND its
    edge directions for SAT purposes (a box's edges run exactly along its
    own local axes, so there is no need to separately rotate a set of
    'edge' vectors - they're the same 3 directions as the face normals)."""
    R = body.get_rotation_matrix()
    return R.T  # rows of R.T = columns of R = the rotated local basis vectors


# ----------------------------------------------------------------------
# SAT for box-box
# ----------------------------------------------------------------------

def _box_box_contact(a: RigidBody, b: RigidBody) -> Optional[Tuple[np.ndarray, float, np.ndarray]]:
    """Returns (normal, penetration, contact_point) or None."""
    verts_a = _box_vertices(a)
    verts_b = _box_vertices(b)

    axes_a = _box_axes(a)  # (3,3): rows are A's world-space local X/Y/Z axes
    axes_b = _box_axes(b)

    # Separating axes: 3 face normals of each box (= their own local axes),
    # plus the 9 cross products between A's and B's edge directions (which,
    # for a box, are exactly those same local axes - no separate "edge"
    # vectors to compute).
    candidate_axes = [axes_a[0], axes_a[1], axes_a[2], axes_b[0], axes_b[1], axes_b[2]]
    for e_a in axes_a:
        for e_b in axes_b:
            axis = fast_cross3(e_a, e_b)
            n = float(np.linalg.norm(axis))
            if n > 1e-8:
                candidate_axes.append(axis / n)

    axes = np.array(candidate_axes)  # (K, 3)

    # Project all 8 vertices of both boxes onto all K axes in one shot
    # instead of per-axis Python-loop dot products.
    proj_a = verts_a @ axes.T  # (8, K)
    proj_b = verts_b @ axes.T
    min_a, max_a = proj_a.min(axis=0), proj_a.max(axis=0)
    min_b, max_b = proj_b.min(axis=0), proj_b.max(axis=0)
    overlaps = np.minimum(max_a - min_b, max_b - min_a)

    if np.any(overlaps < 0):
        return None  # Separated on at least one axis

    best_idx = int(np.argmin(overlaps))
    best_overlap = float(overlaps[best_idx])
    best_axis = axes[best_idx]

    # Ensure normal points from A to B
    center_diff = b.position - a.position
    if np.dot(center_diff, best_axis) < 0:
        best_axis = -best_axis

    # Contact point: midpoint of the two centers (a simple approximation -
    # a full SAT implementation would clip the incident face against the
    # reference face for an exact manifold; this is adequate for the
    # resting-contact behavior this engine currently targets).
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
    """Apply impulse-based resolution to separate two bodies and correct
    velocities/angular velocities. Delegates to _apply_point_contact (the
    same function ground contact uses) so body-body and body-ground contact
    share one correct implementation, using each body's real world-space
    inverse inertia tensor rather than a sphere-shaped approximation."""
    restitution_coef = min(a.restitution, b.restitution)
    friction_coef = (a.friction + b.friction) * 0.5
    _apply_point_contact(
        a=a, b=b, normal=normal, penetration=penetration,
        contact_point=contact_point,
        restitution_coef=restitution_coef,
        friction_coef=friction_coef,
    )


# ----------------------------------------------------------------------
# Pair dispatcher
# ----------------------------------------------------------------------

def resolve_pair(a: RigidBody, b: RigidBody) -> None:
    if a.is_static and b.is_static:
        return

    # Generic dispatch: SPHERE vs everything else, using each body's own
    # exact scaled radius (spheres are common enough, and cheap enough, to
    # deserve exact treatment) - and OBB vs OBB (derived from actual mesh
    # bounds via get_scaled_half_extents/get_obb_center_offset, see
    # _box_vertices) for any other pair, regardless of shape/object_kind.
    # This replaces the old per-shape-name branching (SHAPE_BOX vs
    # SHAPE_BOX, "other shapes fall back to a sphere approximation" for
    # cylinder/cone/compound) with two cases that work for ANY geometry:
    # a compound object like the car or mug now collides as a proper OBB
    # instead of a wildly inaccurate bounding sphere. This is still a
    # simple convex collision representation, not true arbitrary-convex
    # (GJK/EPA) or concave (convex-decomposition) collision - see the
    # module docstring for that follow-up work.
    a_is_sphere = a.is_sphere_like()
    b_is_sphere = b.is_sphere_like()

    contact = None
    if a_is_sphere and b_is_sphere:
        contact = _sphere_sphere_contact(a, b)
    elif a_is_sphere and not b_is_sphere:
        # _sphere_box_contact returns a normal pointing box->sphere, i.e.
        # b->a here - but _resolve_contact needs a->b (proven by the
        # sphere-sphere and box-box cases), so this needs negating.
        contact = _sphere_box_contact(a, b)
        if contact:
            normal, pen, pt = contact
            contact = (-normal, pen, pt)
    elif not a_is_sphere and b_is_sphere:
        # Swap args so _sphere_box_contact sees (sphere=b, box=a); it then
        # returns box(a)->sphere(b), which already IS a->b - no negation.
        contact = _sphere_box_contact(b, a)
    else:
        contact = _box_box_contact(a, b)

    if contact:
        normal, penetration, contact_point = contact
        _resolve_contact(a, b, normal, penetration, contact_point)
        # Wake threshold must sit safely above the steady-state Baumgarte
        # slop (~0.0015, see _apply_point_contact's `slop`), not below it -
        # two settled, touching bodies converge to a permanent residual
        # penetration around that slop value, and waking on ANY penetration
        # above a threshold smaller than the slop itself (this used to be
        # 0.001) meant every touching resting pair rewoke each other every
        # single substep forever, exactly like the analogous ground-contact
        # bug (see resolve_ground_contact) - no pair of touching objects
        # could ever actually fall asleep.
        if penetration > 0.01:
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
        # Centers are (numerically) coincident, so the separating direction
        # is undefined - but returning None here means giving up on
        # separating them at all. With nothing else to push them apart,
        # they stay permanently interpenetrating (this is the "two bodies
        # glitch into each other and stay glitched" bug: it's reproducible
        # any time two centers end up exactly coincident, e.g. typing the
        # same position into both bodies' property panels). Fall back to a
        # fixed direction so the solver still has something to push along.
        normal = np.array([0.0, 1.0, 0.0])
        penetration = min_dist
    else:
        normal = delta / dist
        penetration = min_dist - dist
    contact_point = (a.position + b.position) * 0.5
    return normal, penetration, contact_point