"""
rendering/terrain.py – expanded ground to half_size=160.
"""

import math
import random
from typing import Tuple

from OpenGL.GL import *

from config import SimulationConfig

RGB = Tuple[float, float, float]


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (a[0] * (1.0 - t) + b[0] * t, a[1] * (1.0 - t) + b[1] * t, a[2] * (1.0 - t) + b[2] * t)


def _grass_noise(base: RGB, dirt: RGB, x: float, z: float) -> RGB:
    n = (math.sin(x * 1.7) * math.cos(z * 1.3) + math.sin(x * 0.31 + z * 0.7)) * 0.5
    n *= 0.06
    path_band = max(0.0, 1.0 - abs(z + math.sin(x * 0.08) * 3.0) / 4.0)
    clearing = max(0.0, 1.0 - math.hypot(x, z) / 18.0) * 0.35
    color = _mix(base, dirt, max(path_band * 0.55, clearing))
    return (
        max(0.0, min(1.0, color[0] + n * 0.5)),
        max(0.0, min(1.0, color[1] + n)),
        max(0.0, min(1.0, color[2] + n * 0.5)),
    )


class Terrain:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self._ground_list = None
        self._surface_outline_list = None
        self._mountains_list = None

    def invalidate(self) -> None:
        self._ground_list = None
        self._surface_outline_list = None
        self._mountains_list = None

    def draw_ground(self, half_size: float = 160.0, cell: float = 4.0) -> None:
        if self._ground_list is None:
            self._ground_list = glGenLists(1)
            glNewList(self._ground_list, GL_COMPILE)
            self._build_ground(half_size, cell)
            glEndList()
        glCallList(self._ground_list)

    def _build_ground(self, half_size: float, cell: float) -> None:
        base = self.config.grass_color
        dirt = self.config.dirt_color
        steps = int((half_size * 2) / cell)
        glBegin(GL_QUADS)
        glNormal3f(0, 1, 0)
        for i in range(steps):
            x0 = -half_size + i * cell
            x1 = x0 + cell
            for j in range(steps):
                z0 = -half_size + j * cell
                z1 = z0 + cell
                for (x, z) in ((x0, z0), (x0, z1), (x1, z1), (x1, z0)):
                    glColor3f(*_grass_noise(base, dirt, x * 0.3, z * 0.3))
                    glVertex3f(x, 0.0, z)
        glEnd()

    def draw_playing_surface_outline(self) -> None:
        if self._surface_outline_list is None:
            self._surface_outline_list = glGenLists(1)
            glNewList(self._surface_outline_list, GL_COMPILE)
            self._build_surface_outline()
            glEndList()
        glCallList(self._surface_outline_list)

    def _build_surface_outline(self) -> None:
        half = self.config.playing_surface_half_extent
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_LINE_BIT)
        glDisable(GL_LIGHTING)
        glLineWidth(2.0)
        glColor3f(0.85, 0.85, 0.35)
        y = 0.02
        glBegin(GL_LINE_LOOP)
        glVertex3f(-half, y, -half)
        glVertex3f(half, y, -half)
        glVertex3f(half, y, half)
        glVertex3f(-half, y, half)
        glEnd()
        glPopAttrib()

    def draw_mountains(self, distance: float = 150.0, count: int | None = None) -> None:
        if count is None:
            count = self.config.mountain_segments
        if self._mountains_list is None:
            self._mountains_list = glGenLists(1)
            glNewList(self._mountains_list, GL_COMPILE)
            self._build_mountains(distance, count)
            glEndList()
        glCallList(self._mountains_list)

    def _build_mountains(self, distance: float, count: int) -> None:
        rng = random.Random(1234)
        base_color = self.config.mountain_color
        glBegin(GL_TRIANGLES)
        for i in range(count):
            theta0 = 2.0 * math.pi * i / count
            theta1 = 2.0 * math.pi * (i + 1) / count
            height = 18.0 + rng.uniform(0, 30.0)
            shade = 0.85 + rng.uniform(-0.1, 0.1)
            color = (base_color[0] * shade, base_color[1] * shade, base_color[2] * shade)
            x0, z0 = distance * math.cos(theta0), distance * math.sin(theta0)
            x1, z1 = distance * math.cos(theta1), distance * math.sin(theta1)
            xm = (x0 + x1) * 0.5 + rng.uniform(-5, 5)
            zm = (z0 + z1) * 0.5 + rng.uniform(-5, 5)
            glColor3f(*color)
            glVertex3f(x0, -2.0, z0)
            glVertex3f(x1, -2.0, z1)
            glVertex3f(xm, height, zm)
        glEnd()
