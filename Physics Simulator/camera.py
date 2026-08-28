"""
rendering/camera.py – added free fly mode.
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np

from math_utils import normalize, vec3


class OrbitCamera:
    def __init__(self, target=(0.0, 1.0, 0.0), distance: float = 12.0,
                 yaw_deg: float = -45.0, pitch_deg: float = 22.0) -> None:
        self.target = vec3(*target)
        self.distance = distance
        self.yaw = math.radians(yaw_deg)
        self.pitch = math.radians(pitch_deg)
        self.min_distance = 2.0
        self.max_distance = 80.0
        self.min_pitch = math.radians(-5.0)
        self.max_pitch = math.radians(85.0)

        # Free mode parameters
        self.free_mode = False
        self.free_position = vec3(0, 5, 15)  # initial position for free mode
        self.free_yaw = self.yaw
        self.free_pitch = self.pitch

        self.viewport: Tuple[int, int] = (800, 600)
        self.fov_deg = 55.0
        self.near = 0.1
        self.far = 500.0

    def set_free_mode(self, enabled: bool) -> None:
        if enabled and not self.free_mode:
            # Switch to free: store current orbit parameters as free ones
            self.free_position = self.position()
            self.free_yaw = self.yaw
            self.free_pitch = self.pitch
        elif not enabled and self.free_mode:
            # Switch back to orbit: set orbit parameters from free position?
            # We'll just set target to the free position and keep distance.
            self.target = self.free_position
            self.yaw = self.free_yaw
            self.pitch = self.free_pitch
        self.free_mode = enabled

    # ------------------------------------------------------------------
    # Position / basis vectors (works for both modes)
    # ------------------------------------------------------------------

    def position(self) -> np.ndarray:
        if self.free_mode:
            return self.free_position.copy()
        cp = math.cos(self.pitch)
        offset = vec3(
            self.distance * cp * math.cos(self.yaw),
            self.distance * math.sin(self.pitch),
            self.distance * cp * math.sin(self.yaw),
        )
        return self.target + offset

    def forward(self) -> np.ndarray:
        if self.free_mode:
            # Look direction from yaw/pitch
            cp = math.cos(self.free_pitch)
            return normalize(vec3(
                cp * math.cos(self.free_yaw),
                math.sin(self.free_pitch),
                cp * math.sin(self.free_yaw)
            ))
        return normalize(self.target - self.position())

    def right(self) -> np.ndarray:
        return normalize(np.cross(self.forward(), vec3(0, 1, 0)))

    def up(self) -> np.ndarray:
        return normalize(np.cross(self.right(), self.forward()))

    # ------------------------------------------------------------------
    # Interaction (orbit/pan/zoom) – adjusted for free mode
    # ------------------------------------------------------------------

    def orbit(self, dx_px: float, dy_px: float, sensitivity: float) -> None:
        if self.free_mode:
            # Rotate view direction
            self.free_yaw += math.radians(dx_px * sensitivity)
            self.free_pitch += math.radians(-dy_px * sensitivity)
            self.free_pitch = max(-math.pi / 2 + 0.01, min(math.pi / 2 - 0.01, self.free_pitch))
        else:
            self.yaw += math.radians(dx_px * sensitivity)
            self.pitch += math.radians(-dy_px * sensitivity)
            self.pitch = max(self.min_pitch, min(self.max_pitch, self.pitch))

    def pan(self, dx_px: float, dy_px: float, sensitivity: float) -> None:
        if self.free_mode:
            # Pan: move camera right/up relative to view
            right = self.right()
            up = self.up()
            scale = sensitivity * 0.1  # arbitrary scale
            self.free_position += right * (-dx_px * scale) + up * (dy_px * scale)
        else:
            right = self.right()
            up = vec3(0, 1, 0)
            scale = self.distance * sensitivity
            self.target += (-right * dx_px + up * dy_px) * scale

    def zoom(self, wheel_steps: float, sensitivity: float) -> None:
        if self.free_mode:
            # Move forward/backward
            factor = sensitivity ** (-wheel_steps)
            self.free_position += self.forward() * (wheel_steps * 0.5)  # simple zoom
        else:
            factor = sensitivity ** (-wheel_steps)
            self.distance = max(self.min_distance, min(self.max_distance, self.distance * factor))

    # Free movement with WASD
    def move_forward(self, amount: float) -> None:
        if self.free_mode:
            self.free_position += self.forward() * amount

    def move_right(self, amount: float) -> None:
        if self.free_mode:
            self.free_position += self.right() * amount

    def move_up(self, amount: float) -> None:
        if self.free_mode:
            self.free_position += vec3(0, amount, 0)

    # ------------------------------------------------------------------
    # Picking (unchanged)
    # ------------------------------------------------------------------

    def screen_to_ray(self, screen_x: float, screen_y: float) -> Tuple[np.ndarray, np.ndarray]:
        w, h = self.viewport
        if w <= 0 or h <= 0:
            return self.position(), self.forward()

        ndc_x = (2.0 * screen_x / w) - 1.0
        ndc_y = 1.0 - (2.0 * screen_y / h)

        aspect = w / h
        tan_fov = math.tan(math.radians(self.fov_deg) * 0.5)

        cam_forward = self.forward()
        cam_right = self.right()
        cam_up = self.up()

        dir_camera_space = (
                cam_forward
                + cam_right * (ndc_x * tan_fov * aspect)
                + cam_up * (ndc_y * tan_fov)
        )
        return self.position(), normalize(dir_camera_space)
