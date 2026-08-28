"""
rendering/scenery.py – more trees and clouds.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from OpenGL.GL import *
from OpenGL.GLU import *
from config import SimulationConfig


@dataclass
class Tree:
    x: float
    z: float
    scale: float
    rotation_deg: float


@dataclass
class Cloud:
    x: float
    y: float
    z: float
    scale: float
    speed: float
    puffs: List[Tuple[float, float, float, float]]


class SceneryManager:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.trees: List[Tree] = []
        self.clouds: List[Cloud] = []
        self._tree_list = None
        self._quadric = None
        self._generate()

    def _generate(self) -> None:
        rng = random.Random(42)
        cfg = self.config
        min_r = cfg.playing_surface_half_extent + 4.0
        max_r = 70.0
        for _ in range(cfg.tree_count):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(min_r, max_r)
            self.trees.append(Tree(
                x=math.cos(angle) * dist, z=math.sin(angle) * dist,
                scale=rng.uniform(0.7, 1.8), rotation_deg=rng.uniform(0, 360),
            ))

        for _ in range(cfg.cloud_count):
            puffs = []
            for _ in range(rng.randint(3, 6)):
                puffs.append((
                    rng.uniform(-3.0, 3.0), rng.uniform(-0.5, 0.5), rng.uniform(-1.5, 1.5),
                    rng.uniform(1.0, 2.0),
                ))
            self.clouds.append(Cloud(
                x=rng.uniform(-100, 100), y=rng.uniform(30, 50), z=rng.uniform(-100, 100),
                scale=rng.uniform(1.5, 3.5), speed=rng.uniform(0.4, 1.2), puffs=puffs,
            ))

    def _get_quadric(self):
        if self._quadric is None:
            self._quadric = gluNewQuadric()
        return self._quadric

    def draw_trees(self) -> None:
        if self._tree_list is None:
            self._tree_list = glGenLists(1)
            glNewList(self._tree_list, GL_COMPILE)
            self._build_single_tree()
            glEndList()

        for tree in self.trees:
            glPushMatrix()
            glTranslatef(tree.x, 0.0, tree.z)
            glRotatef(tree.rotation_deg, 0, 1, 0)
            glScalef(tree.scale, tree.scale, tree.scale)
            glCallList(self._tree_list)
            glPopMatrix()

    def _build_single_tree(self) -> None:
        cfg = self.config
        q = self._get_quadric()
        trunk_h = 1.6
        glColor3f(*cfg.trunk_color)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0)
        gluCylinder(q, 0.14, 0.10, trunk_h, 8, 1)
        glPopMatrix()

        glColor3f(*cfg.foliage_color)
        for i, (h, r) in enumerate(((1.6, 1.0), (2.2, 0.8), (2.8, 0.55))):
            glPushMatrix()
            glTranslatef(0, h, 0)
            glRotatef(-90, 1, 0, 0)
            gluCylinder(q, r, 0.0, 1.1, 10, 1)
            glPopMatrix()

    def update(self, dt: float) -> None:
        bound = 120.0
        for cloud in self.clouds:
            cloud.x += cloud.speed * dt
            if cloud.x > bound:
                cloud.x = -bound

    def draw_clouds(self) -> None:
        glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_LIGHTING)
        glColor4f(*self.config.cloud_color, 0.85)
        q = self._get_quadric()
        for cloud in self.clouds:
            glPushMatrix()
            glTranslatef(cloud.x, cloud.y, cloud.z)
            glScalef(cloud.scale, cloud.scale, cloud.scale)
            for dx, dy, dz, r in cloud.puffs:
                glPushMatrix()
                glTranslatef(dx, dy, dz)
                gluSphere(q, r, 10, 8)
                glPopMatrix()
            glPopMatrix()
        glPopAttrib()
