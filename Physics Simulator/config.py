"""
core/config.py – expanded world size and added extra parameters.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class SimulationConfig:
    # --- Physics -----------------------------------------------------
    gravity: float = 9.8
    fixed_timestep: float = 1.0 / 120.0
    max_substeps: int = 8
    ground_friction: float = 0.6
    ground_restitution: float = 0.4
    air_damping: float = 0.999
    angular_damping: float = 0.995
    sleep_linear_threshold: float = 0.05
    sleep_angular_threshold: float = 0.05
    sleep_time_required: float = 1.0

    # --- World bounds --------------------------------------------------
    playing_surface_half_extent: float = 20.0  # expanded
    kill_plane_y: float = -50.0

    # --- Time of day -----------------------------------------------------
    time_of_day_hours: float = 10.0
    day_length_seconds: float = 0.0

    # --- Camera -----------------------------------------------------------
    camera_fov_deg: float = 55.0
    camera_near: float = 0.1
    camera_far: float = 500.0
    orbit_sensitivity: float = 0.4
    pan_sensitivity: float = 0.02
    zoom_sensitivity: float = 1.1

    # --- Rendering / performance -------------------------------------------
    target_fps: int = 60
    frustum_culling_enabled: bool = True
    shadow_enabled: bool = True
    tree_count: int = 32  # more trees
    cloud_count: int = 14
    mountain_segments: int = 48

    # --- Object defaults -----------------------------------------------
    default_object_mass: float = 1.0
    default_object_restitution: float = 0.5
    default_object_friction: float = 0.5
    impulse_strength: float = 6.0

    # --- Colors (unchanged) ---------------------------------------
    grass_color: Tuple[float, float, float] = (0.30, 0.55, 0.22)
    dirt_color: Tuple[float, float, float] = (0.40, 0.30, 0.20)
    mountain_color: Tuple[float, float, float] = (0.45, 0.42, 0.48)
    trunk_color: Tuple[float, float, float] = (0.36, 0.24, 0.12)
    foliage_color: Tuple[float, float, float] = (0.16, 0.42, 0.18)
    cloud_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    sky_zenith_day: Tuple[float, float, float] = (0.25, 0.55, 0.92)
    sky_horizon_day: Tuple[float, float, float] = (0.78, 0.88, 0.96)
    sky_zenith_night: Tuple[float, float, float] = (0.02, 0.03, 0.10)
    sky_horizon_night: Tuple[float, float, float] = (0.06, 0.08, 0.18)
    sky_zenith_sunset: Tuple[float, float, float] = (0.20, 0.20, 0.45)
    sky_horizon_sunset: Tuple[float, float, float] = (0.95, 0.55, 0.35)

    def clamp_time_of_day(self) -> None:
        self.time_of_day_hours %= 24.0


config = SimulationConfig()
