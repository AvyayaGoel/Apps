"""
environment_presets.py

Data-driven environment presets, read from data/environments.json. Built-in
presets (Earth, Moon, Space, ...) are locked: picking one applies its
values to the live SimulationConfig, but those values can't be edited in
place. The "Custom" preset is always unlocked - editing any environment
slider while it's active updates both the live config and the stored
Custom preset, so changes persist across switching away and back.

This mirrors object_catalog.py's shape: read data once at import, expose a
registry, fall back to a minimal built-in default if the file is missing
or broken so a bad data file can't stop the app from starting.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from config import SimulationConfig

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent / "data" / "environments.json"

PRESET_FIELDS = [
    "gravity", "ground_friction", "ground_restitution",
    "air_damping", "angular_damping", "time_of_day_hours",
]

_DEFAULTS = {
    "gravity": 9.8, "ground_friction": 0.6, "ground_restitution": 0.4,
    "air_damping": 0.999, "angular_damping": 0.995, "time_of_day_hours": 10.0,
}


@dataclass
class EnvironmentPreset:
    name: str
    locked: bool
    values: Dict[str, float]


def _load() -> Dict[str, EnvironmentPreset]:
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        presets: Dict[str, EnvironmentPreset] = {}
        for entry in raw["presets"]:
            values = {k: entry[k] for k in PRESET_FIELDS if k in entry}
            presets[entry["name"]] = EnvironmentPreset(
                name=entry["name"], locked=entry.get("locked", True), values=values)
        if "Custom" not in presets:
            # Always guarantee an editable slot exists, even if the data
            # file's author forgot to include one.
            presets["Custom"] = EnvironmentPreset(name="Custom", locked=False, values=dict(_DEFAULTS))
        if not presets:
            raise ValueError("environments.json parsed but contained no presets")
        return presets
    except Exception:
        logger.exception(
            f"Failed to load environment presets from {_DATA_PATH} - "
            f"falling back to a minimal built-in Earth + Custom so the app can still start"
        )
        return {
            "Earth": EnvironmentPreset(name="Earth", locked=True, values=dict(_DEFAULTS)),
            "Custom": EnvironmentPreset(name="Custom", locked=False, values=dict(_DEFAULTS)),
        }


PRESETS: Dict[str, EnvironmentPreset] = _load()

# Which preset is currently active - starts on the first locked preset found
# (normally "Earth"), matching SimulationConfig's own defaults.
_active_name: str = next((p.name for p in PRESETS.values() if p.locked), next(iter(PRESETS)))


def preset_names() -> List[str]:
    return list(PRESETS.keys())


def active_preset_name() -> str:
    return _active_name


def is_locked(name: str) -> bool:
    preset = PRESETS.get(name)
    return preset.locked if preset is not None else True


def apply_preset(config: SimulationConfig, name: str) -> None:
    """Copy a preset's values onto the live config and make it active."""
    global _active_name
    preset = PRESETS.get(name)
    if preset is None:
        return
    for key, value in preset.values.items():
        setattr(config, key, value)
    _active_name = name


def update_custom(config: SimulationConfig, field_name: str, value: float) -> None:
    """Call this when a slider changes while Custom is active, so the edit
    is remembered - otherwise switching to another preset and back would
    silently discard it."""
    if field_name in PRESET_FIELDS:
        PRESETS["Custom"].values[field_name] = value
    setattr(config, field_name, value)


def start_custom_from_current(config: SimulationConfig) -> None:
    """Clone the currently active preset's values into Custom and switch to
    it - this is how a locked preset actually gets 'changed': not in
    place, but by branching into the editable Custom slot."""
    global _active_name
    for key in PRESET_FIELDS:
        PRESETS["Custom"].values[key] = getattr(config, key, _DEFAULTS.get(key))
    _active_name = "Custom"
