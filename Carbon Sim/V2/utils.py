"""Geometry helpers and chain builders."""

import logging
import math
from typing import List, Tuple

from config import CHAIN_SEGMENT_LENGTH, CHAIN_ZIGZAG_ANGLE_DEG
from models import Atom

logger = logging.getLogger(__name__)


def dist(a: Atom, b: Atom) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    vlen2 = vx * vx + vy * vy
    if vlen2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / vlen2))
    projx = x1 + t * vx
    projy = y1 + t * vy
    return math.hypot(px - projx, py - projy)


def compute_chain_zigzag(start_x: float, start_y: float, end_x: float, end_y: float) -> List[Tuple[float, float]]:
    dx, dy = end_x - start_x, end_y - start_y
    drag_dist = math.hypot(dx, dy)
    if drag_dist < 1e-6:
        return []
    ux, uy = dx / drag_dist, dy / drag_dist
    nx, ny = -uy, ux
    n_segments = max(1, round(drag_dist / CHAIN_SEGMENT_LENGTH))
    theta = math.radians(CHAIN_ZIGZAG_ANGLE_DEG)
    forward = CHAIN_SEGMENT_LENGTH * math.cos(theta)
    side = CHAIN_SEGMENT_LENGTH * math.sin(theta)
    positions: List[Tuple[float, float]] = []
    cx, cy = start_x, start_y
    sign = 1
    for _ in range(n_segments):
        cx += ux * forward + nx * side * sign
        cy += uy * forward + ny * side * sign
        positions.append((cx, cy))
        sign *= -1
    return positions


def compute_chain_hydrogens(backbone: List[Tuple[float, float]],
                            skip_first: bool = False) -> List[Tuple[float, float, int]]:
    n = len(backbone)
    if n == 0:
        return []
    bond_len = CHAIN_SEGMENT_LENGTH
    results: List[Tuple[float, float, int]] = []
    start_idx = 1 if skip_first else 0
    for i in range(start_idx, n):
        cx, cy = backbone[i]
        neighbors = []
        if i > 0:
            neighbors.append(backbone[i - 1])
        if i < n - 1:
            neighbors.append(backbone[i + 1])
        if len(neighbors) == 1:
            nx0, ny0 = neighbors[0]
            dx, dy = cx - nx0, cy - ny0
            d = math.hypot(dx, dy) or 1.0
            bx, by = dx / d, dy / d
            perp_x, perp_y = -by, bx
            for (vx, vy) in ((bx, by), (perp_x, perp_y), (-perp_x, -perp_y)):
                results.append((cx + vx * bond_len, cy + vy * bond_len, i))
        elif len(neighbors) == 2:
            (ax, ay), (bx2, by2) = neighbors
            d1x, d1y = cx - ax, cy - ay
            d1 = math.hypot(d1x, d1y) or 1.0
            u1x, u1y = d1x / d1, d1y / d1
            d2x, d2y = cx - bx2, cy - by2
            d2 = math.hypot(d2x, d2y) or 1.0
            u2x, u2y = d2x / d2, d2y / d2
            bisx, bisy = u1x + u2x, u1y + u2y
            bis_len = math.hypot(bisx, bisy)
            if bis_len < 1e-6:
                bisx, bisy = -u1y, u1x
                bis_len = math.hypot(bisx, bisy) or 1.0
            bisx, bisy = bisx / bis_len, bisy / bis_len
            perp_x, perp_y = -bisy, bisx
            half = math.radians(CHAIN_ZIGZAG_ANGLE_DEG)
            for sign in (1, -1):
                vx = bisx * math.cos(half) + perp_x * math.sin(half) * sign
                vy = bisy * math.cos(half) + perp_y * math.sin(half) * sign
                vlen = math.hypot(vx, vy) or 1.0
                results.append((cx + (vx / vlen) * bond_len, cy + (vy / vlen) * bond_len, i))
    return results
