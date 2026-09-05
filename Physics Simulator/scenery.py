"""
rendering/scenery.py – more trees and clouds.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

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
class Rock:
    x: float
    z: float
    scale: float
    rotation_deg: float


@dataclass
class GrassTuft:
    x: float
    z: float
    height: float
    radius: float
    phase: float


@dataclass
class Cloud:
    x: float
    y: float
    z: float
    scale: float
    speed: float
    puffs: List[Tuple[float, float, float, float]]
    display_list: Optional[int] = None


class SceneryManager:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.trees: List[Tree] = []
        self.rocks: List[Rock] = []
        self.grass_tufts: List[GrassTuft] = []
        self.clouds: List[Cloud] = []
        self._tree_list = None
        self._rock_list = None
        self._grass_list = None
        self._quadric = None
        self._generate()

    def _generate(self) -> None:
        rng = random.Random(42)
        cfg = self.config
        min_r = cfg.playing_surface_half_extent + 4.0
        max_r = 145.0
        for _ in range(cfg.tree_count):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(min_r, max_r)
            self.trees.append(Tree(
                x=math.cos(angle) * dist, z=math.sin(angle) * dist,
                scale=rng.uniform(0.7, 2.2), rotation_deg=rng.uniform(0, 360),
            ))

        for _ in range(70):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(cfg.playing_surface_half_extent + 2.0, 130.0)
            self.rocks.append(Rock(
                x=math.cos(angle) * dist, z=math.sin(angle) * dist,
                scale=rng.uniform(0.25, 1.25), rotation_deg=rng.uniform(0, 360),
            ))

        for _ in range(260):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(8.0, 135.0)
            if dist < cfg.playing_surface_half_extent + 2.0 and rng.random() < 0.75:
                continue
            self.grass_tufts.append(GrassTuft(
                x=math.cos(angle) * dist, z=math.sin(angle) * dist,
                height=rng.uniform(0.25, 0.75), radius=rng.uniform(0.08, 0.18), phase=rng.uniform(0, math.pi),
            ))

        for _ in range(cfg.cloud_count):
            puffs = []
            for _ in range(rng.randint(3, 6)):
                puffs.append((
                    rng.uniform(-3.0, 3.0), rng.uniform(-0.5, 0.5), rng.uniform(-1.5, 1.5),
                    rng.uniform(1.0, 2.0),
                ))
            self.clouds.append(Cloud(
                x=rng.uniform(-140, 140), y=rng.uniform(32, 58), z=rng.uniform(-140, 140),
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
        trunk_h = 1.9
        glColor3f(*cfg.trunk_color)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0)
        gluCylinder(q, 0.18, 0.11, trunk_h, 10, 1)
        glPopMatrix()

        glColor3f(*cfg.foliage_color)
        for h, r in ((1.45, 1.05), (2.05, 0.86), (2.62, 0.64), (3.12, 0.40)):
            glPushMatrix()
            glTranslatef(0, h, 0)
            glRotatef(-90, 1, 0, 0)
            gluCylinder(q, r, 0.0, 1.2, 14, 1)
            glPopMatrix()

    def draw_rocks(self) -> None:
        if self._rock_list is None:
            self._rock_list = glGenLists(1)
            glNewList(self._rock_list, GL_COMPILE)
            q = self._get_quadric()
            glColor3f(0.34, 0.33, 0.31)
            glScalef(1.0, 0.45, 0.75)
            gluSphere(q, 0.6, 12, 8)
            glEndList()

        for rock in self.rocks:
            glPushMatrix()
            glTranslatef(rock.x, 0.18 * rock.scale, rock.z)
            glRotatef(rock.rotation_deg, 0, 1, 0)
            glScalef(rock.scale, rock.scale, rock.scale)
            glCallList(self._rock_list)
            glPopMatrix()

    def draw_grass_tufts(self) -> None:
        if self._grass_list is None:
            self._grass_list = glGenLists(1)
            glNewList(self._grass_list, GL_COMPILE)
            self._build_grass_tufts()
            glEndList()
        glCallList(self._grass_list)

    def _build_grass_tufts(self) -> None:
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_LINE_BIT | GL_CURRENT_BIT)
        glDisable(GL_LIGHTING)
        glLineWidth(1.2)
        glColor3f(0.19, 0.46, 0.16)
        glBegin(GL_LINES)
        for tuft in self.grass_tufts:
            for i in range(5):
                angle = tuft.phase + i * 2.0 * math.pi / 5.0
                tip_x = tuft.x + math.cos(angle) * tuft.radius
                tip_z = tuft.z + math.sin(angle) * tuft.radius
                glVertex3f(tuft.x, 0.02, tuft.z)
                glVertex3f(tip_x, tuft.height, tip_z)
        glEnd()
        glPopAttrib()

    def update(self, dt: float) -> None:
        bound = 155.0
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
            if cloud.display_list is None:
                cloud.display_list = glGenLists(1)
                glNewList(cloud.display_list, GL_COMPILE)
                for dx, dy, dz, r in cloud.puffs:
                    glPushMatrix()
                    glTranslatef(dx, dy, dz)
                    gluSphere(q, r, 10, 8)
                    glPopMatrix()
                glEndList()
            glPushMatrix()
            glTranslatef(cloud.x, cloud.y, cloud.z)
            glScalef(cloud.scale, cloud.scale, cloud.scale)
            glCallList(cloud.display_list)
            glPopMatrix()
        glPopAttrib()