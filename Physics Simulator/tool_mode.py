"""
scene/tool_mode.py

The active interaction tool for the viewport - orthogonal to SceneMode
(construction vs simulation). SceneMode controls whether physics is
stepping; ToolMode controls what a click/drag in the viewport currently
does.
"""

from __future__ import annotations

from enum import Enum


class ToolMode(Enum):
    SELECT = "select"  # click to select; gizmo shows both translate + rotate handles
    MOVE = "move"  # click to select; gizmo shows only translate handles
    ROTATE = "rotate"  # click to select; gizmo shows only rotate handles
    SCALE = "scale"  # click+drag vertically on a body to resize it uniformly
    PLACE = "place"  # click in the viewport to spawn the armed catalog object
    DELETE = "delete"  # click a body to delete it immediately
