"""
core/math_utils.py

Small, dependency-free (beyond numpy) math helpers shared across the
physics and rendering modules: vector helpers, a minimal quaternion
implementation for orientation/rotation, and a ray/plane and ray/sphere
intersection routine used for mouse picking.

We deliberately avoid pulling in a full linear-algebra/game-math library
(e.g. pyrr) to keep the dependency list exactly as small as the brief
requires (PyQt6, PyOpenGL, numpy). Everything here is short enough to
audit at a glance.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np


# ----------------------------------------------------------------------
# Vector helpers
# ----------------------------------------------------------------------

def normalize(v: np.ndarray) -> np.ndarray:
    """Return a unit-length copy of v, or v unchanged if it is ~zero length."""
    n = np.linalg.norm(v)
    if n < 1e-9:
        return v.copy()
    return v / n


def vec3(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> np.ndarray:
    return np.array([x, y, z], dtype=np.float64)


# ----------------------------------------------------------------------
# Quaternion (x, y, z, w) — used for rigid body orientation.
# Stored as a plain 4-element numpy array [x, y, z, w].
# ----------------------------------------------------------------------

IDENTITY_QUAT = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)


def quat_normalize(q: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(q)
    if n < 1e-9:
        return IDENTITY_QUAT.copy()
    return q / n


def quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product a * b, both in (x, y, z, w) form."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], dtype=np.float64)


def quat_from_axis_angle(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = normalize(axis)
    half = angle_rad * 0.5
    s = math.sin(half)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, math.cos(half)], dtype=np.float64)


def quat_integrate(q: np.ndarray, angular_velocity: np.ndarray, dt: float) -> np.ndarray:
    """Advance orientation q by angular_velocity (rad/s) over dt seconds."""
    wx, wy, wz = angular_velocity
    omega = np.array([wx, wy, wz, 0.0], dtype=np.float64)
    dq = quat_multiply(omega, q) * 0.5 * dt
    return quat_normalize(q + dq)


def quat_to_matrix4(q: np.ndarray) -> np.ndarray:
    """Return a 4x4 column-major rotation matrix suitable for glMultMatrixf."""
    x, y, z, w = q
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    m = np.identity(4, dtype=np.float32)
    m[0, 0] = 1 - 2 * (yy + zz)
    m[0, 1] = 2 * (xy + wz)
    m[0, 2] = 2 * (xz - wy)

    m[1, 0] = 2 * (xy - wz)
    m[1, 1] = 1 - 2 * (xx + zz)
    m[1, 2] = 2 * (yz + wx)

    m[2, 0] = 2 * (xz + wy)
    m[2, 1] = 2 * (yz - wx)
    m[2, 2] = 1 - 2 * (xx + yy)
    # numpy stores this row-major; OpenGL wants column-major, and since the
    # rotation part above is written row-major we transpose before upload.
    return m.T.flatten()


# ----------------------------------------------------------------------
# Ray casting (for mouse picking / dragging)
# ----------------------------------------------------------------------

def ray_sphere_intersect(origin: np.ndarray, direction: np.ndarray,
                         center: np.ndarray, radius: float) -> Optional[float]:
    """Return the nearest positive t such that origin + t*direction hits the
    sphere, or None if there is no hit in front of the ray origin."""
    oc = origin - center
    b = np.dot(oc, direction)
    c = np.dot(oc, oc) - radius * radius
    disc = b * b - c
    if disc < 0:
        return None
    sqrt_disc = math.sqrt(disc)
    t0 = -b - sqrt_disc
    t1 = -b + sqrt_disc
    if t0 > 1e-6:
        return t0
    if t1 > 1e-6:
        return t1
    return None


def ray_aabb_intersect(origin: np.ndarray, direction: np.ndarray,
                       box_min: np.ndarray, box_max: np.ndarray) -> Optional[float]:
    """Slab method ray/AABB intersection. Returns nearest positive t or None."""
    t_min, t_max = -math.inf, math.inf
    for i in range(3):
        d = direction[i]
        if abs(d) < 1e-12:
            if origin[i] < box_min[i] or origin[i] > box_max[i]:
                return None
            continue
        t1 = (box_min[i] - origin[i]) / d
        t2 = (box_max[i] - origin[i]) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return None
    if t_max < 1e-6:
        return None
    return t_min if t_min > 1e-6 else t_max


def ray_plane_intersect(origin: np.ndarray, direction: np.ndarray,
                        plane_point: np.ndarray, plane_normal: np.ndarray) -> Optional[float]:
    denom = np.dot(direction, plane_normal)
    if abs(denom) < 1e-9:
        return None
    t = np.dot(plane_point - origin, plane_normal) / denom
    return t if t > 1e-6 else None


def quat_rotate_vector(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector v by quaternion q."""
    # q * (v, 0) * q_conj
    qx, qy, qz, qw = q
    vx, vy, vz = v
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return np.array([
        vx + qw * tx + (qy * tz - qz * ty),
        vy + qw * ty + (qz * tx - qx * tz),
        vz + qw * tz + (qx * ty - qy * tx),
    ], dtype=np.float64)


def quat_conjugate(q: np.ndarray) -> np.ndarray:
    """Return the conjugate of quaternion q (x, y, z, w)."""
    return np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float64)
