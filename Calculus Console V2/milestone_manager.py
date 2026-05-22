"""
Milestone Manager (PyQt6)
Handles all progression logic: milestones, count tips, awards, glitches,
secret achievements, and the 150-formula entity reflection sequence.
"""

import random
from typing import Callable, Dict, List

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from constants import (
    ENTITY_BOOT,
    ENTITY_GRAPH,
    ENTITY_REBOOT,
    ENTITY_TEXT
)
from formula_utils import FormulaUtils


class MilestoneManager(QObject):
    """
    Emits signals whenever the UI needs to show something.
    The main app simply connects these to its widgets.
    """

    # ── Regular milestones ──
    banner_requested = pyqtSignal(str, str)
    """(text, tier). tier is one of: standard, quantum, neural, dimensional, cosmic, transcendence, god_mode"""

    toast_requested = pyqtSignal(str, str)
    """(message, bootstyle) e.g. ("...", "info")"""

    glitch_requested = pyqtSignal(str)
    """Glitch text to show as a toast."""

    award_unlocked = pyqtSignal(str, str)
    """(title, description)"""

    secret_unlocked = pyqtSignal()
    """The hidden 'STABILITY MAINTAINED' award was earned."""

    # ── Entity reflection (150 formulas) ──
    ui_lock_changed = pyqtSignal(bool)
    """True = lock the UI, False = restore it."""

    entity_banner_show = pyqtSignal(str, bool)
    """Show the big top banner with this text."""

    entity_banner_hide = pyqtSignal()
    """Hide/destroy the entity banner."""

    entity_prompt_show = pyqtSignal(str)
    """Show the persistent prompt (e.g. 'Query the anomaly.')."""

    entity_options_ready = pyqtSignal(list)
    """List of strings to populate the topic combobox with."""

    reflection_complete = pyqtSignal()
    """Reflection sequence fully finished, UI can be restored."""

    # ── State persistence hint ──
    state_modified = pyqtSignal()
    """Emitted whenever tip_state has been mutated so the main app can save it."""

    entity_continue_show = pyqtSignal()
    """Show the Continue button below the banner."""

    entity_continue_hide = pyqtSignal()
    """Hide the Continue button."""

    entity_prompt_hide = pyqtSignal()
    """Fade out the prompt label."""

    entity_bottom_bar_show = pyqtSignal()
    """Show Continue + 'I have no doubts' buttons."""

    entity_bottom_bar_hide = pyqtSignal()
    """Hide the bottom bar."""

    # Full milestone texts (with emojis). Override via constructor if desired.
    MILESTONES = {
        2: "🌱 First Steps: Initial database established.",
        5: "⚡ Quick Learner: Basic proficiency achieved.",
        10: "🏆 Beginner's Dozen: Foundation of 10 formulas complete.",
        20: "🎉 Early Progress: 20 formulas recorded.",
        25: "🚀 Physics Foundation: 25 physics formulas documented.",
        30: "📐 Structural Stability: Pattern recognition developing.",
        50: "🔥 Half Century: Significant database reached.",
        75: "🧠 Workflow Integration: System becoming part of routine.",
        100: "👑 Complete Foundation: 100 formulas - comprehensive knowledge base.",
        120: "⚠️ Advanced Usage: Complex patterns emerging.",
        151: "🌑 Persistent Usage: Extended engagement detected.",
        175: "🛰️ Deviation from Norm: Usage patterns exceed standard metrics.",
        200: "💎 Data Architecture: 200 formulas - complex information structure.",
        238: "☢️ Critical Density: Information threshold approaching limits.",
        300: "🪐 System Scale: 300 formulas - planetary-level knowledge.",
        400: "🔱 Thermal Anomaly: 400 formulas. System should have failed under normal conditions.",
        500: "🌊 Quantum Barrier: 500 formulas. Simulation parameters exceeded.",
        600: "⚡ Neural Integration: 600 formulas. System adaptation in progress.",
        700: "🔮 Reality Distortion: 700 formulas. Physics bending to data patterns.",
        800: "🌌 Universal Pattern: 800 formulas. Cosmic-level recognition achieved.",
        900: "🎭 Transcendent State: 900 formulas. User-system boundary dissolving.",
        999: "🌟 Event Horizon: 999 formulas. Approaching infinite knowledge.",
        1000: "✨ Absolute Mastery: 1000 formulas. Complete system understanding.",
    }

    COUNT_TIPS = {
        3: [("entry_tip", "Speed Tip: Use Enter to jump between fields instead of clicking.")],
        4: [("keypad_tip", "Speed Tip: Use 'Ctrl + K' to open the math symbol keypad instantly.")],
        6: [("Feature_Unlock", "✨ Feature Unlocked: Smart Suggestions is now active!")],
        7: [("ghost_system_tip",
             "Speed Tip: Smart Suggestions show [1/3] (🟢 High) in ghost text. Ctrl+↓ accept, Ctrl+→/← cycle, Esc dismiss.")],
        9: [("table_tip", "Speed Tip: Double-click any saved formula to instantly view or edit it.")],
        11: [("editing_tip", "Pro Tip: Editing a formula keeps its ID — no need to re-organize later.")],
        12: [("formula_mastery",
              "Pro Tip: Press 'Ctrl + S' anywhere to save the entire formula instantly once variables are added.")],
        14: [("variable_tip", "Speed Tip: Press Ctrl + Backspace to delete a selected variable instantly.")],
        15: [("clear_tip", "Speed Tip: Use 'Ctrl + N' to quickly clear all fields for a new entry.")],
        30: [("Feature_Unlock", "✨ Feature Unlocked: Unlocked Awards Panel")],
        31: [("pattern_notice", "System Note: Repeated behavior patterns are now detectable.")],
        51: [("validation_bypass", "System Note: Validation prevents most unintended states.")],
        57: [("evaluation_notice", "System Note: Context matters more than content at higher usage levels.")],
        83: [("structure_notice", "System Note: Some operations complete only after adjacent panels are visited.")],
        90: [("unease_notice", "System Note: Certain states stabilize only after delayed action.")],
        98: [("unease_notice", "Something feels… different.")],
        121: [("output_effect", "System Note: Absence of output does not imply absence of effect.")],
        123: [("off_notice", "This isn't how it used to feel.")],
    }

    GLITCH_TEXTS = [
        "…", "Sync: 0x7A3F", "Δt = 0.0041", "Buffer drift detected",
        "—", "… recalculating …", "▒▒▒▒▒▒", "?",
        "Latency stabilized after non-interaction.",
        "He▒… saƒe", "saf▒…", "re▒…", "hol▒", "st▒…", "c▒nt…"
    ]

    def __init__(self, tip_state: dict, parent=None):
        super().__init__(parent)
        self.tip_state = tip_state
        self._last_count = 0
        self._ensure_nested_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_count(self, count: int, master_data: Dict[int, Dict]) -> None:
        """
        Call this whenever the formula count changes (save, delete, import).
        It runs all milestone / tip / award / glitch checks.
        """
        self._last_count = count

        self._check_milestone(count)
        self._check_count_tips(count)
        self._maybe_show_glitch(count)
        self._check_special_count(count)

        stats, other_subjects, var_overload = FormulaUtils.calculate_formula_statistics(master_data)
        self._check_awards(stats, other_subjects, var_overload)

        # Symbol consistency tip
        unique_symbols = {
            v["symbol"]
            for d in master_data.values()
            for v in d.get("variables", [])
        }
        if len(unique_symbols) >= 10:
            self.show_tip_once(
                "symbol_consistency",
                "You're building a consistent symbol system across formulas.",
                min_count=1
            )

        # One-in-a-thousand hidden award
        if random.random() < 0.001:
            self.show_tip_once(
                "award_the_glitch",
                "🏆 SECRET AWARD\nThe Glitch: A one-in-a-thousand anomaly was recorded.",
                min_count=1
            )

    def set_formula_count(self, count: int) -> None:
        """Just update the internal counter without running checks."""
        self._last_count = count

    def trigger_milestone_manually(self, milestone_count: int) -> None:
        """Force a milestone banner (debug / cheat). Bypasses 'seen' tracking."""
        text = self.MILESTONES.get(milestone_count)
        if text:
            tier = self._banner_tier(milestone_count)
            self.banner_requested.emit(text, tier)

    def show_tip_once(self, tip_id: str, message: str, *, min_count: int = 1) -> bool:
        """Show a toast only once per tip_id. Returns True if actually shown."""
        shown_map = self.tip_state.setdefault("shown", {})
        if shown_map.get(tip_id):
            return False

        counters = self.tip_state.setdefault("counters", {})
        counters[tip_id] = counters.get(tip_id, 0) + 1
        self.state_modified.emit()

        if counters[tip_id] >= min_count:
            self.toast_requested.emit(message, "info")
            shown_map[tip_id] = True
            self.state_modified.emit()
            return True

        return False

    # ------------------------------------------------------------------
    # Secret Award
    # ------------------------------------------------------------------

    def get_secret_award_state(self) -> Dict:
        ss = self.tip_state.get("secret_award")
        if not isinstance(ss, dict):
            ss = {
                "glitch_seen": False,
                "subject_ok": False,
                "topic_ok": False,
                "movement": [],
                "unlocked": False
            }
            self.tip_state["secret_award"] = ss
            self.state_modified.emit()
        return ss

    def record_movement(self, action: str) -> None:
        ss = self.get_secret_award_state()
        if ss.get("unlocked"):
            return

        ss["movement"].append(action)
        ss["movement"] = ss["movement"][-4:]

        target = ["open_stats", "close_stats", "save_formula"]

        def sequence_in_order(seq, targ):
            it = iter(seq)
            return all(item in it for item in targ)

        if (
                ss.get("glitch_seen")
                and ss.get("subject_ok")
                and ss.get("topic_ok")
                and sequence_in_order(ss["movement"], target)
        ):
            self._unlock_secret_award()

        self.state_modified.emit()

    def check_secret_code(self, subject: str, topic: str) -> bool:
        """Call with raw subject/topic text before saving. Returns True if the easter-egg code was entered."""
        if subject.strip() == "_SYSTEM_" and topic.strip() == "UNDEFINED_BEHAVIOR":
            ss = self.get_secret_award_state()
            ss["subject_ok"] = True
            ss["topic_ok"] = True
            self.state_modified.emit()
            self._check_secret_unlock()
            return True
        return False

    def _check_secret_unlock(self) -> None:
        ss = self.get_secret_award_state()
        if (
                ss.get("glitch_seen")
                and ss.get("subject_ok")
                and ss.get("topic_ok")
        ):
            # Wait for movement sequence; if already satisfied, unlock now
            target = ["open_stats", "close_stats", "save_formula"]
            movement = ss.get("movement", [])
            it = iter(movement)
            if all(item in it for item in target) and not ss.get("unlocked"):
                self._unlock_secret_award()

    def _unlock_secret_award(self) -> None:
        ss = self.get_secret_award_state()
        ss["unlocked"] = True
        self.state_modified.emit()
        self.secret_unlocked.emit()
        # Subtle confirmation toast
        QTimer.singleShot(900, lambda: self.toast_requested.emit("…", "warning"))

    # ------------------------------------------------------------------
    # Reflection 150
    # ------------------------------------------------------------------

    def get_reflection_state(self) -> Dict:
        rs = self.tip_state.get("reflection_150")
        if not isinstance(rs, dict):
            rs = {"active": False, "completed": False}
            self.tip_state["reflection_150"] = rs
            self.state_modified.emit()
        return rs

    def is_reflection_active(self) -> bool:
        return self.get_reflection_state().get("active", False)

    def is_reflection_completed(self) -> bool:
        return self.get_reflection_state().get("completed", False)

    def start_reflection(self) -> None:
        """Begin the 150-formula entity sequence. The manager drives timing via QTimer."""
        rs = self.get_reflection_state()
        if rs.get("completed"):
            return

        if rs.get("active"):
            return

        rs["active"] = True
        self.state_modified.emit()
        self.ui_lock_changed.emit(True)

        self._reflection_fsm = {
            "current": "start",
            "visited": set()
        }
        self._run_sequence(ENTITY_BOOT, self._on_boot_done)

    def select_entity_option(self, text: str) -> None:
        """
        Called when user selects an option from the overlay.
        Shows the answer with Continue + "I have no doubts" buttons.
        """
        chosen = None
        for key, value in ENTITY_TEXT.items():
            if value == text:
                chosen = key
                break

        if not chosen:
            return

        # Prevent duplicate clicking spam
        if chosen in self._reflection_fsm["visited"]:
            return

        self._reflection_fsm["visited"].add(chosen)

        # Disable options immediately so user can't spam
        self.entity_options_ready.emit([])

        node_data = ENTITY_GRAPH.get(chosen)
        if not node_data:
            self._end_reflection()
            return

        answer = node_data.get("answer", "...")
        hint = node_data.get("hint")
        corrupted = node_data.get("corrupted", False)
        next_nodes = node_data.get("next", [])

        # Store pending state for continue handler
        self._reflection_pending = {
            "chosen": chosen,
            "next_nodes": next_nodes,
            "is_ending": chosen == "exit" or not next_nodes
        }

        # Build display text
        display_text = answer
        if hint:
            display_text += "\n\n[SYSTEM HINT]\n" + hint

        # Hide prompt, show answer + bottom bar (Continue + I have no doubts)
        self.entity_prompt_hide.emit()
        self.entity_banner_show.emit(display_text, corrupted)
        self.entity_bottom_bar_show.emit()

    def on_continue_clicked(self) -> None:
        """Called when user clicks Continue in the overlay."""
        if not hasattr(self, '_reflection_pending'):
            return

        pending = self._reflection_pending
        is_ending = pending["is_ending"]

        # Hide banner and bottom bar with fade
        self.entity_banner_hide.emit()
        self.entity_bottom_bar_hide.emit()

        if is_ending:
            QTimer.singleShot(2500, self._end_reflection)
            return

        # Move tree forward
        self._reflection_fsm["current"] = pending["chosen"]

        # Show next prompt and options after fade completes
        def show_next():
            self.entity_prompt_show.emit("Choose your next query.")
            self._load_entity_options()

        QTimer.singleShot(2500, show_next)

    def on_no_doubts_clicked(self) -> None:
        """Called when user clicks 'I have no doubts'. Immediately exits to REBOOT."""
        # Hide everything with fade
        self.entity_banner_hide.emit()
        self.entity_bottom_bar_hide.emit()
        self.entity_prompt_hide.emit()

        # Go straight to REBOOT — same as old "exit" node behavior
        QTimer.singleShot(2500, self._end_reflection)

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_milestone(self, count: int) -> None:
        if count in self.MILESTONES:
            key = f"milestone_{count}"
            if not self._milestone_seen(key):
                self._mark_milestone_seen(key)
                tier = self._banner_tier(count)
                self.banner_requested.emit(self.MILESTONES[count], tier)

    def _check_count_tips(self, count: int) -> None:
        tips = self.COUNT_TIPS.get(count)
        if tips:
            for tip_id, message in tips:
                self.show_tip_once(tip_id, message, min_count=1)

    def _maybe_show_glitch(self, count: int) -> None:
        if not (123 < count < 150):
            return
        if random.random() > 0.08:
            return

        gs = self.tip_state.setdefault("glitch_state", {"shown": 0})
        if gs.get("shown", 0) >= 3:
            return

        text = random.choice(self.GLITCH_TEXTS)
        shown = self.show_tip_once(f"glitch_{count}", text, min_count=1)
        if shown:
            gs["shown"] = gs.get("shown", 0) + 1
            self.state_modified.emit()
            ss = self.get_secret_award_state()
            ss["glitch_seen"] = True
            self.state_modified.emit()

    def _check_special_count(self, count: int) -> None:
        if count == 150:
            rs = self.get_reflection_state()
            if not rs.get("completed") and not rs.get("active"):
                self.start_reflection()

    def _check_awards(self, stats: Dict[str, int], other_subjects: set, var_overload: bool) -> None:
        award_defs = [
            ("The Alchemist", "Save 10 Chemistry formulas.", stats.get("Chemistry", 0) >= 10),
            ("The Physicist", "Save 10 Physics formulas.", stats.get("Physics", 0) >= 10),
            ("Alegbra Learner", "Save 10 Maths formulas.", stats.get("Maths", 0) >= 10),
            ("Chemistry Learner", "Save 25 Chemistry formulas.", stats.get("Chemistry", 0) >= 25),
            ("The Junior-Engineer", "Save 25 Physics formulas.", stats.get("Physics", 0) >= 25),
            ("Maths Explorer", "Save 25 Maths formulas.", stats.get("Maths", 0) >= 25),
            ("Variable Wrangler", "Save a formula with 5+ defined variables.", var_overload),
            ("The Chemist", "Save 50 Chemistry formulas.", stats.get("Chemistry", 0) >= 50),
            ("The Engineer", "Save 50 Physics formulas.", stats.get("Physics", 0) >= 50),
            ("Maths Expert", "Save 50 Maths formulas.", stats.get("Maths", 0) >= 50),
            ("Einstein", "Save 100 Physics Formulas", stats.get("Physics", 0) >= 100),
            ("The Mathematician", "Save 100 Maths Formulas", stats.get("Maths", 0) >= 100),
            ("Maths God", "Save 150 Maths Formulas", stats.get("Maths", 0) >= 150),
            ("The Pioneer", "Have 1 more subject other than Maths, Chemistry And Physics", len(other_subjects) >= 1),
            ("The Rocketeer", "Have 2 more subject other than Maths, Chemistry And Physics", len(other_subjects) >= 2),
        ]

        for title, desc, unlocked in award_defs:
            if unlocked:
                self.show_tip_once(
                    tip_id=f"award_{title.replace(' ', '_')}",
                    message=f"🏆 AWARD UNLOCKED\n{title}: {desc}",
                    min_count=1
                )

    # ------------------------------------------------------------------
    # Entity reflection internals
    # ------------------------------------------------------------------

    def _run_sequence(self, messages: List[str], on_done: Callable) -> None:
        """
        Run a sequence of messages.

        Messages can now be either:
            "some text"
        or:
            {
                "text": "...",
                "instant": True/False
            }

        instant=True:
            - no fade-out
            - immediate switch

        instant=False:
            - normal cinematic fade flow
        """

        self._seq_messages = []

        for msg in messages:
            if isinstance(msg, dict):
                self._seq_messages.append(msg)
            else:
                self._seq_messages.append({
                    "text": msg,
                    "instant": False
                })

        self._seq_index = 0
        self._seq_done_callback = on_done
        self._show_next_seq_message()

    def _show_next_seq_message(self) -> None:
        """Show the next message in the sequence."""

        if self._seq_index >= len(self._seq_messages):
            self.entity_banner_hide.emit()
            QTimer.singleShot(700, self._seq_done_callback)
            return

        entry = self._seq_messages[self._seq_index]

        text = entry["text"]
        instant = entry.get("instant", False)

        # Instant messages:
        # no fade animation at all
        if instant:
            self.entity_banner_show.emit(text, True)

            self._seq_index += 1

            # Slightly faster switching
            QTimer.singleShot(980, self._show_next_seq_message)

        # Normal cinematic messages
        else:
            self.entity_banner_show.emit(text, False)

            self._seq_index += 1

            QTimer.singleShot(1800, self._on_seq_message_done)

    def _on_seq_message_done(self) -> None:
        """Fade out current message before showing the next one."""
        self.entity_banner_hide.emit()
        # Faster transition between messages
        QTimer.singleShot(1300, self._show_next_seq_message)

    def _on_boot_done(self) -> None:
        self.entity_prompt_show.emit("Query the anomaly.")
        self._load_entity_options()

    def _load_entity_options(self) -> None:
        node = self._reflection_fsm["current"]
        next_nodes = ENTITY_GRAPH[node]["next"]
        options = []

        for nid in next_nodes:
            if nid not in self._reflection_fsm["visited"]:
                option_text = ENTITY_TEXT[nid]
                options.append(option_text)

        if not options:
            self.entity_options_ready.emit([])
            QTimer.singleShot(2500, self._end_reflection)
            return

        self.entity_options_ready.emit(options)

    def _end_reflection(self) -> None:
        self._run_sequence(ENTITY_REBOOT, self._on_reboot_done)

    def _on_reboot_done(self) -> None:
        """Called after REBOOT sequence finishes (banner already faded out)."""
        rs = self.get_reflection_state()
        rs["completed"] = True
        rs["active"] = False
        self.state_modified.emit()
        self.ui_lock_changed.emit(False)
        self.reflection_complete.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _milestone_seen(self, key: str) -> bool:
        return self.tip_state.setdefault("shown", {}).get(key, False)

    def _mark_milestone_seen(self, key: str) -> None:
        self.tip_state.setdefault("shown", {})[key] = True
        self.state_modified.emit()

    @staticmethod
    def _banner_tier(count: int) -> str:
        if count >= 1000:
            return "god_mode"
        if count >= 900:
            return "transcendence"
        if count >= 800:
            return "cosmic"
        if count >= 700:
            return "dimensional"
        if count >= 600:
            return "neural"
        if count >= 500:
            return "quantum"
        return "standard"

    def _ensure_nested_state(self) -> None:
        self.tip_state.setdefault("shown", {})
        self.tip_state.setdefault("counters", {})
        self.tip_state.setdefault("glitch_state", {"shown": 0})
