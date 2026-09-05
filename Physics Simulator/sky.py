"""
rendering/sky.py

Draws the sky as a large inverted gradient dome (zenith color at the top
fading to horizon color at the base), plus a sun and moon disc positioned
by the current time-of-day. Rather than a literal 24-hour clock, we treat
6:00 as sunrise (sun on the eastern horizon) and 18:00 as sunset, with
12:00 = sun directly overhead, matching everyday intuition for a
"time of day slider".

The gradient itself is drawn with vertex colors on a hemisphere (GL_FOG /
lighting are disabled while drawing it so the colors show through exactly
as authored) - cheap and looks convincing at sandbox scale.

Extension point: swap `_lerp_color` blending for a proper physically
based Rayleigh-scattering sky model if/when you want photoreal skies;
everything else in this module (sun/moon placement, call sites) stays the
same.
"""

from __future__ import annotations

import math
from typing import Tuple

from OpenGL.GL import *

from config import SimulationConfig

RGB = Tuple[float, float, float]


def _lerp_color(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def sun_direction(hours: float) -> Tuple[float, float, float]:
    """Unit direction FROM the scene TOWARD the sun, for the given hour
    (0-24). The sun rises in +X at 6:00, peaks straight up at 12:00, sets
    in -X at 18:00, and swings below the horizon at night."""
    angle = (hours / 24.0) * 2.0 * math.pi - math.pi / 2.0  # 6:00 -> 0 rad (horizon, rising)
    x = math.cos(angle)
    y = math.sin(angle)
    return x, y, 0.35


def moon_direction(hours: float) -> Tuple[float, float, float]:
    sx, sy, sz = sun_direction(hours)
    return -sx, -sy, -sz


class SkyRenderer:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self._display_list = None
        self._display_list_hours = None

    @staticmethod
    def _daylight_factor(hours: float) -> float:
        """0 at deep night, 1 at midday, smooth in between, using sun
        elevation directly so it naturally matches where the sun disc is
        drawn."""
        _, sy, _ = sun_direction(hours)
        return max(0.0, min(1.0, (sy + 0.15) / 1.15))

    def sky_colors(self, hours: float) -> Tuple[RGB, RGB]:
        cfg = self.config
        _, sun_y, _ = sun_direction(hours)

        if sun_y > 0.15:
            zenith, horizon = cfg.sky_zenith_day, cfg.sky_horizon_day
        elif sun_y > -0.2:
            # dawn/dusk transition band
            blend = (sun_y + 0.2) / 0.35
            zenith = _lerp_color(cfg.sky_zenith_night, cfg.sky_zenith_sunset, min(1.0, blend))
            horizon = _lerp_color(cfg.sky_horizon_night, cfg.sky_horizon_sunset, min(1.0, blend))
            if sun_y > 0.0:
                z2 = _lerp_color(cfg.sky_zenith_sunset, cfg.sky_zenith_day, sun_y / 0.15)
                h2 = _lerp_color(cfg.sky_horizon_sunset, cfg.sky_horizon_day, sun_y / 0.15)
                zenith, horizon = z2, h2
        else:
            zenith, horizon = cfg.sky_zenith_night, cfg.sky_horizon_night
        return zenith, horizon

    def ambient_and_sun_intensity(self, hours: float) -> Tuple[float, float]:
        day_t = self._daylight_factor(hours)
        ambient = 0.15 + 0.35 * day_t
        sun_strength = 0.15 + 0.85 * day_t
        return ambient, sun_strength

    # Below this much simulated-hour change, the gradient is visually
    # indistinguishable, so there's no point rebuilding ~800 vertex/color
    # calls (with trig) for it every single frame - only the sun/moon
    # discs, which are two cheap flat quads, still redraw every frame.
    _REBUILD_THRESHOLD_HOURS = 0.02

    def draw(self, hours: float, radius: float = 200.0) -> None:
        if (self._display_list is None or self._display_list_hours is None or
                abs(hours - self._display_list_hours) >= self._REBUILD_THRESHOLD_HOURS):
            if self._display_list is None:
                self._display_list = glGenLists(1)
            glNewList(self._display_list, GL_COMPILE)
            self._build_dome(hours, radius)
            glEndList()
            self._display_list_hours = hours

        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_FOG)

        glCallList(self._display_list)

        self._draw_celestial_body(sun_direction(hours), radius * 0.92, (1.0, 0.95, 0.75), size=9.0, glow=True)
        day_t = self._daylight_factor(hours)
        if day_t < 0.85:
            self._draw_celestial_body(moon_direction(hours), radius * 0.92, (0.85, 0.88, 0.95), size=6.0, glow=False)

        glPopAttrib()

    def _build_dome(self, hours: float, radius: float) -> None:
        zenith, horizon = self.sky_colors(hours)
        rings, segments = 12, 32
        for i in range(rings):
            t0 = i / rings
            t1 = (i + 1) / rings
            phi0 = t0 * math.pi / 2.0
            phi1 = t1 * math.pi / 2.0
            c0 = _lerp_color(horizon, zenith, t0)
            c1 = _lerp_color(horizon, zenith, t1)
            glBegin(GL_QUAD_STRIP)
            for seg in range(segments + 1):
                theta = 2.0 * math.pi * seg / segments
                for phi, col in ((phi1, c1), (phi0, c0)):
                    x = radius * math.cos(phi) * math.cos(theta)
                    y = radius * math.sin(phi)
                    z = radius * math.cos(phi) * math.sin(theta)
                    glColor3f(*col)
                    glVertex3f(x, y, z)
            glEnd()

    @staticmethod
    def _draw_celestial_body(direction, distance, color, size, glow) -> None:
        dx, dy, dz = direction
        if dy < -0.25:
            return  # well below horizon, don't bother drawing
        x, y, z = dx * distance, dy * distance, dz * distance
        glPushMatrix()
        glTranslatef(x, y, z)
        glColor3f(*color)
        _draw_billboard_quad(size)
        glPopMatrix()


def _draw_billboard_quad(size: float) -> None:
    """A camera-facing-ish flat quad. For a sky dome viewed from near the
    origin, a fixed-orientation quad reads as a disc convincingly enough
    without needing true billboard math."""
    half = size * 0.5
    glBegin(GL_QUADS)
    glVertex3f(-half, -half, 0)
    glVertex3f(half, -half, 0)
    glVertex3f(half, half, 0)
    glVertex3f(-half, half, 0)
    glEnd()