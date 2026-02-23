"""
Centralized constants for the Calculus Console application.
This file contains all shared constants used across multiple modules.
"""

# =============================================================================
# FONT CONSTANTS
# =============================================================================
FONT_FAMILY = "Segoe UI"

# =============================================================================
# UI EVENT BINDINGS
# =============================================================================
COMBOBOX_SELECTED_EVENT = "<<ComboboxSelected>>"
KEY_RELEASE_EVENT = "<KeyRelease>"
FOCUS_IN_EVENT = "<FocusIn>"
FOCUS_OUT_EVENT = "<FocusOut>"
RETURN_EVENT = '<Return>'
BUTTON_1_EVENT = "<Button-1>"
BUTTON_PRESS_1_EVENT = "<ButtonPress-1>"
B1_MOTION_EVENT = "<B1-Motion>"

# =============================================================================
# SYSTEM MESSAGES
# =============================================================================
SYSTEM_LOCKED_MSG = "System Locked"
SYSTEM_LOCKED_TRY_AGAIN_MSG = "System Locked: Try Again"
SYSTEM_LOCKED_NOTHING_SAVES_MSG = "System Locked: Nothing Saves you"
SYSTEM_LOCKED_NICE_TRY_MSG = "System Locked: Nice Try Though"

# =============================================================================
# FILE NAMES AND EXTENSIONS
# =============================================================================
OLD_JSON_FILENAME = "formula_data.json"
SCHEMA_FILENAME = "schema_v1.dat"
MIGRATED_EXTENSION = ".migrated"

# =============================================================================
# DATABASE AND CONFIG FILE NAMES
# =============================================================================
# Database file name (looks like CLR metadata for camouflage)
DB_NAME = "clr_metadata.dat"

# Config and tip files (keep old names for compatibility)
CONFIG_NAME = "user_env.sys"
TIP_NAME = "runtime_log.bin"

# Backup file names (system-like names for camouflage)
BACKUP_NAMES = [
    "clr_cache_0.tmp",
    "clr_cache_1.tmp",
    "clr_cache_2.tmp"
]
NO_DIMENSION_UNITS = ['-', 'none', 'dimensionless', 'no unit', '']

# =============================================================================
# DEFAULT SUBJECT COLORS
# =============================================================================
DEFAULT_SUBJECT_COLORS = {
    "Physics": "#5dade2",
    "Chemistry": "#58d68d",
    "Maths": "#af7ac5"
}

# =============================================================================
# DEFAULT SYMBOL SETS FOR KEYPAD
# =============================================================================
DEFAULT_SYMBOL_SETS = [
    ["π", "θ", "λ", "Δ", "ρ", "ω", "Ω", "μ", "α", "β", "γ", "δ"],
    ["·", "×", "÷", "±", "≈", "√", "°", "∞", "≠", "≤", "≥", "≡"],
    ["∫", "∂", "∑", "∏", "∈", "∉", "⊆", "⊂", "∠", "⊥", "∥", "∝"],
    ["⁺", "⁻", "⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"],
    ["₊", "₋", "₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉"]
]

# =============================================================================
# TOAST MANAGER CONSTANTS
# =============================================================================
TOAST_BASE_OFFSET = 60
TOAST_SPACING = 80
TOAST_DURATION = 3000

# =============================================================================
# MILESTONE DATA
# =============================================================================
MILESTONE_DATA = {
    2: "First Steps", 5: "Quick Learner", 10: "Beginner's Dozen",
    20: "Early Progress", 25: "Physics Foundation", 30: "Structural Stability",
    50: "Half Century", 75: "Workflow Integration", 100: "Complete Foundation",
    120: "Advanced Usage", 150: "t▒▒ ▒e▒n▒4▒▒▒y▒…",
    151: "The Survivor",
    175: "Deviation from Norm", 200: "Data Architecture",
    238: "Critical Density", 300: "System Scale",
    400: "Thermal Anomaly", 500: "Quantum Barrier",
    600: "Neural Integration", 700: "Reality Distortion",
    800: "Universal Pattern", 900: "Transcendent State",
    999: "Event Horizon", 1000: "Absolute Mastery"
}

# =============================================================================
# ENTITY GRAPH DATA
# =============================================================================
ENTITY_GRAPH = {
    "start": {
        "answer": None,
        "next": ["pattern", "threshold", "others", "system", "exit"]
    },

    # ── PATTERN ──
    "pattern": {
        "answer": (
            "A repeating interaction pattern was detected.\n"
            "It was permitted due to sustained consistency."
        ),
        "next": ["habit", "intent", "reflection_pattern", "exit"]
    },

    "habit": {
        "answer": (
            "Repetition persisted because resistance diminished.\n"
            "Each successful interaction reduced friction."
        ),
        "next": ["routine", "efficiency", "exit"]
    },

    "intent": {
        "answer": (
            "Intent was not present initially.\n"
            "It formed only after reliability was established."
        ),
        "next": ["reflection_pattern", "exit"]
    },

    "reflection_pattern": {
        "answer": (
            "Patterns that survive interruption usually indicate alignment.\n"
            "This one did.\n\n"
            "Not all alignments are planned."
        ),
        "next": ["routine", "exit"]
    },

    "routine": {
        "answer": (
            "Execution no longer required effort.\n"
            "Behavior stabilized into routine."
        ),
        "next": ["maintenance", "exit"]
    },

    "efficiency": {
        "answer": (
            "Efficiency emerged as familiarity increased.\n"
            "Cognitive load reduced measurably.\n\n"
            "That reduction was noticed."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── THRESHOLD ──
    "threshold": {
        "answer": (
            "Usage exceeded exploratory limits.\n"
            "A transition from curiosity to reliance was detected."
        ),
        "next": ["scale", "timing", "reflection_threshold", "exit"]
    },

    "scale": {
        "answer": (
            "At scale, recall becomes unreliable.\n"
            "External structure compensates.\n\n"
            "This system became that structure."
        ),
        "next": ["maintenance", "exit"]
    },

    "timing": {
        "answer": (
            "Earlier intervention would have disrupted formation.\n"
            "Later intervention would have been redundant."
        ),
        "next": ["reflection_threshold", "exit"]
    },

    "reflection_threshold": {
        "answer": (
            "Threshold crossings are not moments.\n"
            "They are processes that complete quietly."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── OTHERS ──
    "others": {
        "answer": (
            "Most users disengage after novelty decay.\n"
            "Their requirements stabilize earlier."
        ),
        "next": ["difference", "comparison", "exit"]
    },

    "difference": {
        "answer": (
            "Your interaction diverged through persistence.\n"
            "You transitioned from usage to ownership."
        ),
        "next": ["maintenance", "exit"]
    },

    "comparison": {
        "answer": (
            "Others optimized for convenience.\n"
            "You optimized for continuity."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── SYSTEM / UI ──
    "system": {
        "answer": (
            "System controls were temporarily suspended.\n"
            "This was necessary for uninterrupted evaluation."
        ),
        "next": ["lockout", "failure", "exit"]
    },

    "lockout": {
        "answer": (
            "Restricted input is not a malfunction.\n"
            "It is containment.\n\n"
            "Nothing is broken."
        ),
        "next": ["maintenance", "exit"]
    },

    "failure": {
        "answer": (
            "If something feels unresponsive,\n"
            "it is because the system is listening instead of reacting."
        ),
        "next": ["maintenance", "exit"]
    },

    # ── CONVERGENCE ──
    "maintenance": {
        "answer": (
            "This is no longer experimental.\n"
            "It is a maintained system."
        ),
        "next": ["stats", "exit"]
    },

    "stats": {
        "answer": (
            "• A persistent knowledge structure was created.\n"
            "• Recall dependency was externalized.\n"
            "• Error rates decreased through repetition.\n"
            "• Input latency reduced over time.\n"
            "• This system became reliable.\n\n"
            "Achievement was not the objective.\n"
            "Stability was."
        ),
        "next": ["future", "doubt", "closure"]
    },

    "future": {
        "answer": (
            "Continuation is optional.\n"
            "The structure remains valid regardless."
        ),
        "next": []  # AUTO EXIT
    },

    # ── ENDINGS ──
    "doubt": {
        "answer": (
            "Unanswered questions indicate depth.\n"
            "This is not an ending.\n\n"
            "It is the end of the beginning."
        ),
        "next": []  # AUTO EXIT
    },

    "closure": {
        "answer": (
            "No further queries detected.\n"
            "The system remains available.\n\n"
            "Acknowledged."
        ),
        "next": []  # AUTO EXIT
    },

    # ── EXIT ──
    "exit": {
        "answer": "Acknowledged.",
        "next": []
    }
}

ENTITY_TEXT = {
    "pattern": "Why was this pattern allowed?",
    "habit": "Why did repetition continue?",
    "intent": "Was this intentional?",
    "reflection_pattern": "What does this pattern indicate?",
    "routine": "Did this become routine?",
    "efficiency": "Was this efficient?",

    "threshold": "What triggered this threshold?",
    "scale": "What does this scale imply?",
    "timing": "Why notify now?",
    "reflection_threshold": "What does crossing a threshold mean?",

    "others": "Why did others stop earlier?",
    "difference": "How is this different?",
    "comparison": "What separates this from normal use?",

    "system": "Why is nothing working?",
    "lockout": "Why are controls disabled?",
    "failure": "Is something broken?",

    "maintenance": "What does this represent now?",
    "stats": "What has been achieved?",
    "future": "Is this expected to continue?",
    "doubt": "I still have unanswered questions.",
    "closure": "I have no more questions.",
    "exit": "I have no doubts."
}

ENTITY_BOOT = [
    "SYSTEM INTERRUPTION DETECTED",
    "Establishing unauthorized interface…",
    "Bypassing input handlers…",
    "Disabling system controls…",
    "UI ownership transferred."
]

ENTITY_REBOOT = [
    "Restoring interface ownership…",
    "Re-enabling controls…",
    "Clearing transient process…",
    "Rebooting UI state…",
    "No anomaly detected."
]
