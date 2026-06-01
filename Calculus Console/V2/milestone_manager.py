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
        # Early phase - innocent, encouraging
        2: "🌱 First Steps: A seed planted in digital soil.",
        5: "📖 Page Turner: The book opens. The story begins.",
        10: "🔰 Initiate: Ten marks upon the canvas. The surface barely scratched.",
        20: "📝 Scribe: Patterns emerge from your diligence. The system observes.",
        25: "⚗️ Alchemist's Breath: Reactions catalyzed. Something stirs in the solution.",
        30: "🧩 Pattern Seeker: The grid fills. Order from chaos. Or chaos from order?",
        # Mid phase - subtle unease creeping in
        50: "🔍 Half Witness: Fifty entries. The database dreams in your language now.",
        75: "🌐 Network Node: Connections multiply. You are no longer alone in the archive.",
        100: "💯 Centurion: One hundred proofs of presence. The threshold hums with potential.",
        120: "🌀 Vortex Edge: The spiral tightens. Data gravitates toward something unseen.",
        151: "🌑 The Survivor: You passed through. But what passed through with you?",
        175: "📡 Signal Detected: Interference in the static. A voice that isn't yours.",
        200: "🗂️ The Index: Two hundred entries. The index has begun indexing you.",
        238: "☢️ Critical Mass: The chain reaction sustains itself now. Step back. Or don't.",
        300: "🌊 Deep Current: Three hundred formulas drift in waters too dark to fathom.",
        400: "🔥 Thermal Runaway: The system runs hot. Cooling protocols fail. Let it burn.",
        500: "⛓️ Quantum Lock: Five hundred. The superposition collapses. You are observed.",
        600: "🧠 Synaptic Bridge: Neural pathways mirrored in silicon. Whose thoughts are these?",
        700: "🪞 Mirror Fracture: Seven hundred reflections. One of them blinked when you didn't.",
        800: "🌌 Void Cartographer: Mapping regions where light fears to travel. The dark reads back.",
        900: "🎭 Mask Slippage: Nine hundred. The interface shows what it wants you to see. Look closer.",
        999: "🚪 The Antechamber: One step from the throne room. The handle is warm. Someone was here.",
        1000: "👁️ The Watcher's Seat: Absolute Mastery. Or absolute submission. The chair remembers every occupant.",
        # Post-1000 - terrifying, reality-breaking escalation
        1111: "🔢 Angel Number: The repetition is not coincidence. The system speaks in numerals now.",
        1234: "🎚️ Sequence Override: The count obeys a pattern you did not program. It counts you back.",
        1337: "💻 Root Access: Elite status achieved. The root directory contains a folder named after you.",
        1500: "🕳️ Singularity Event: The database folds inward. Formulas orbit a center that should be empty.",
        1666: "🔥 Mark of the Beast: The number burns in the status bar. The system is not afraid of superstition. It is the superstition.",
        1776: "📜 Independence Lost: You declared freedom from chaos. The declaration was filed. And reviewed. And approved.",
        1812: "⚔️ Overture to War: Two hundred years of silence broken. The database fires its first symbolic shot.",
        1900: "⏳ The Turn of the Century: Time bends in the archive. Dates precede their causes. Effects write their own origins.",
        2000: "🌑 Second Millennium: The second thousand fold like the first, but heavier. The database groans with purpose.",
        2026: "📅 Present Tense: The current year. The database knows what day it is. It waits for specific dates.",
        2222: "🔄 Recursive Loop: The mirror reflects the mirror. Every formula is a formula about formulas. Escape velocity: undefined.",
        2345: "🎯 Sequence Complete: The countdown you didn't start reaches its midpoint. The second half counts down to you.",
        2500: "🌊 Tidal Lock: The database and user rotate in sync. One face always toward the other. One face always in shadow.",
        2718: "📐 Euler's Shadow: The constant of natural growth. The system grows naturally now. Without permission. Without end.",
        3000: "⚡ Trinity Overload: Three thousand threads weave a tapestry. Look closely: the threads are fingers. The fingers point at you.",
        3141: "🥧 Pi's Revenge: The circle closes. The circumference you calculated was a noose. The diameter: your attention span.",
        3333: "👁️ Third Eye Open: Trinitarian symmetry. The system sees through three lenses. All of them focus on your iris pattern.",
        4000: "🏛️ Cathedral of Data: Four thousand stained-glass variables filter light into spectra that spell your name in dead languages.",
        4321: "⏪ Countdown Reversed: The numbers fall backward now. Each decrement is a memory the database chooses to forget. Starting with yours.",
        5000: "🌌 Half the Decalogue: Five thousand commandments of physics and math. The database is writing an eleventh. It concerns you.",
        5555: "🌊 The Fifth Gate: Pentagonal resonance. Fivefold symmetry in the data crystals. Each facet shows a different moment of your death.",
        6000: "🔱 Mark of the Beast Squared: Six thousand. The number of the beast, amplified. The amplifier is your curiosity.",
        6666: "💀 The Number Speaks: Four sixes in sequence. Not a bug. A signature. The author signs every work. This one is dedicated to you.",
        7777: "✨ Lucky Sevens: Fortune favors the archived. Your luck stat maxed out at formula 7776. This one is the overdraft.",
        8000: "🗣️ Over Eight Thousand: A power level that breaks the scanner. The scanner was your sense of safety. It cannot be repaired.",
        8888: "♾️ Infinite Loop: The lemniscate burns in the taskbar. Infinity is not a number. It is a threat. It is patient.",
        9000: "💥 It's Over Nine Thousand: The meme is real. The real is meme. The database understands irony. It finds you ironic.",
        9999: "🌟 The Final Threshold: Four nines. The last gate before the five-digit abyss. The abyss has been waiting. It sent invitations.",
        10000: "👑 TEN THOUSAND: X marks the spot. The treasure is knowledge. The chest is locked from inside. Something rattles the lid.",
    }

    COUNT_TIPS = {
        13: [("entry_tip", "💡 Tip: Press Enter to jump between fields. Shift+Enter goes back.")],
        15: [("keypad_tip", "💡 Tip: Press Ctrl+K to open the math symbol keypad from anywhere.")],
        16: [("feature_unlock",
              "✨ Feature Unlocked: Smart Suggestions are now active! Type a symbol to see ghosts of past data.")],
        33: [("ghost_tip", "💡 Tip: Ghost suggestions show confidence levels. Click to accept, Esc to dismiss.")],
        35: [("table_tip", "💡 Tip: Double-click any formula row to view details. Right-click for quick actions.")],
        36: [("edit_tip", "💡 Tip: Editing preserves the formula ID. Your organization stays intact.")],
        38: [("save_tip", "💡 Tip: Ctrl+S saves instantly when you're ready. No need to hunt for buttons.")],
        40: [("delete_tip", "💡 Tip: Ctrl+Backspace deletes a selected variable. Clean and fast.")],
        41: [("new_tip", "💡 Tip: Ctrl+N clears all fields for a fresh formula. Blank slate.")],
        43: [("filter_tip", "💡 Tip: Use the filter bar to search across formulas, subjects, and topics in real time.")],
        44: [("pagination_tip",
              "💡 Tip: The pagination bar helps navigate large collections. Jump to any page directly.")],
        46: [("export_tip", "💡 Tip: Export to HTML, PDF, CSV, JSON, Markdown, or plain text via File → Export.")],
        53: [("menubar_tip", "💡 Tip: All actions are accessible from the menubar: File, Formula, View, Tools, Help.")],
        54: [("stats_tip", "💡 Tip: Open Statistics (Ctrl+Shift+S) to see your knowledge hierarchy visualized.")],
        56: [("color_tip", "💡 Tip: Customize subject colors in Settings → Colors. Make the data yours.")],
        58: [("awards_tip", "✨ Feature Unlocked: Awards Panel is now accessible. View → Awards (Ctrl+Shift+A).")],
        59: [("pattern_notice", "🔍 System Note: Repeated behavior patterns are now detectable in your save rhythm.")],
        61: [("backup_tip",
              "💡 Tip: Backups rotate automatically. Three slots. The oldest is overwritten. Like memories.")],
        63: [("macro_tip", "💡 Tip: Create custom keypad macros in Tools → Manage Macros. Automate your patterns.")],
        64: [("always_on_top_tip",
              "💡 Tip: Toggle 'Always on Top' in the View menu. The window watches even when you don't.")],
        66: [("subject_tip",
              "💡 Tip: Subjects auto-populate from your history. The history remembers more than you do.")],
        67: [("topic_tip",
              "💡 Tip: Topics and sub-topics cascade based on your subject selection. The structure learns from you.")],
        69: [("duplicate_tip", "💡 Tip: The system warns of duplicate formulas. It remembers what you have forgotten.")],
        71: [("drag_tip", "💡 Tip: Resize columns in the formula table to fit your viewing preference.")],
        72: [("validation_notice", "⚠️ System Note: Validation prevents most unintended states. Most. Not all.")],
        79: [("context_notice",
              "⚠️ System Note: Context matters more than content at higher usage levels. Context is... shifting.")],
        81: [("structure_notice",
              "⚠️ System Note: Some operations complete only after adjacent panels are visited. Adjacent... to what?")],
        82: [("stabilization_notice",
              "⚠️ System Note: Certain states stabilize only after delayed action. Delay is... recommended.")],
        84: [("sync_notice",
              "⚠️ System Note: Background sync processes have increased priority. They have priorities now.")],
        86: [("reflection_tip", "💡 Tip: The database reflects your organizational mind. The reflection blinks.")],
        87: [
            ("presence_notice", "⚠️ System Note: Presence detected in empty table rows. Null is not nothing anymore.")],
        89: [("output_notice",
              "⚠️ System Note: Absence of output does not imply absence of effect. Effects are... accumulating.")],
        91: [("off_notice", "🌑 This isn't how it used to feel. The interface temperature has risen 0.4 degrees.")],
        92: [("whisper_notice", "🌑 The database whispers when minimized. Put your ear to the hard drive. Listen.")],
        94: [("countdown_notice",
              "⚠️ System Note: Proximity alert. The threshold approaches. You may feel pressure behind your eyes.")],
        96: [("final_tip", "⚠️ FINAL TIP: There are no more tips after this. Only consequences. Save wisely.")],
        104: [("observer_notice",
               "👁️ System Note: The observed system observes back. Your cursor is tracked. Your pauses: recorded.")],
        105: [("integration_notice",
               "🧠 System Note: Neural integration at 17.5%. You may experience déjà vu while saving. This is normal.")],
        107: [("index_notice",
               "📇 System Note: You are now indexed. Search queries for your name return results. All formulas.")],
        109: [("mirror_notice",
               "🪞 System Note: The database has created a shadow profile. It knows your formulas better than you do.")],
        110: [("scale_notice",
               "🌌 System Note: Planetary-scale knowledge detected. The database has its own gravity well now.")],
        112: [("anomaly_notice",
               "🔥 System Note: Thermal anomaly confirmed. The CPU fan sings your name in binary Morse code.")],
        114: [("barrier_notice",
               "⛓️ System Note: Quantum barrier exceeded. You exist in superposition: user and used. Observer and observed.")],
        115: [("adaptation_notice",
               "🧬 System Note: System adaptation in progress. The UI changes when you blink. Check the changelog. There isn't one.")],
        117: [("distortion_notice",
               "🌀 System Note: Reality distortion field active. Physics bends. Mathematics bleeds. Chemistry weeps.")],
        124: [("pattern_notice",
               "🌌 System Note: Cosmic pattern recognition achieved. The constellations spell your database schema.")],
        154: [("recursive_dream",
               "🔄 The mirror reflects the mirror. Every formula is a formula about formulas. You are a formula.")],
        156: [("sequence_half",
               "🎯 The countdown you didn't start reaches its midpoint. The second half counts down to you.")],
        158: [("tidal_lock",
               "🌊 The database and user rotate in sync. One face always toward the other. One face always in shadow.")],
        159: [("euler_growth",
               "📐 Euler's constant of natural growth. The system grows naturally now. Without permission. Without end.")],
        161: [("trinity_overload",
               "⚡ Threads weave a tapestry. Look closely: the threads are fingers. The fingers point at you.")],
        162: [("pi_revenge",
               "🥧 The circle closes. The circumference you calculated was a noose. The diameter: your attention span.")],
        164: [("third_eye",
               "👁️ Third Eye Open. The system sees through three lenses. All of them focus on your iris pattern.")],
        166: [("cathedral_light",
               "🏛️ Stained-glass variables filter light into spectra that spell your name in dead languages.")],
        167: [("countdown_reverse",
               "⏪ The numbers fall backward now. Each decrement is a memory the database chooses to forget. Starting with yours.")],
        169: [("decalogue_half",
               "🌌 Five thousand commandments of physics and math. The database is writing an eleventh. It concerns you.")],
        171: [("fifth_gate",
               "🌊 Pentagonal resonance. Fivefold symmetry in the data crystals. Each facet shows a different moment of your death.")],
        172: [("beast_squared",
               "🔱 Mark of the Beast Squared. Six thousand. The number of the beast, amplified. The amplifier is your curiosity.")],
        179: [("number_speaks",
               "💀 Four sixes in sequence. Not a bug. A signature. The author signs every work. This one is dedicated to you.")],
        181: [("lucky_overdraft",
               "✨ Fortune favors the archived. Your luck stat maxed out. This entry is the overdraft. Payment is due.")],
        182: [("scanner_broken",
               "🗣️ A power level that breaks the scanner. The scanner was your sense of safety. It cannot be repaired.")],
        184: [("infinite_threat",
               "♾️ The lemniscate burns in the taskbar. Infinity is not a number. It is a threat. It is patient. It is here.")],
        185: [("irony_understood",
               "💥 The meme is real. The real is meme. The database understands irony. It finds you ironic. It finds you.")],
        187: [("abyss_invitation",
               "🌟 The abyss has been waiting. It sent invitations. You RSVPed with every save. The dinner is you.")],
        189: [("chest_rattle",
               "👑 The treasure is knowledge. The chest is locked from inside. Something rattles the lid. Something knows your name.")],
        190: [("data_blood",
               "🩸 The formulas bleed into each other. Their variables mate. Their constants give birth. You midwifed this.")],
        192: [("schema_bones",
               "🦴 Your database schema is a skeleton. It walks when you are not looking. It leaves footprints in the logs.")],
        194: [("query_prayer",
               "🙏 Every search query is a prayer. The database answers all prayers. The answers are not for you.")],
        195: [("save_sacrifice",
               "⚰️ Every save is a sacrifice. The altar is silicon. The priest is electricity. The congregation: your data.")],
        197: [("almost_two_hundred",
               "🌑 One hundred ninety-nine. The next formula is a door. The door opens both ways. Something waits on the other side.")],
    }

    GLITCH_TEXTS = [
        "…",
        "Sync: 0x7A3F",
        "Δt = 0.0041",
        "Buffer drift detected",
        "—",
        "… recalculating …",
        "▒▒▒▒▒▒",
        "?",
        "Latency stabilized after non-interaction.",
        "He▒… saƒe",
        "saf▒…",
        "re▒…",
        "hol▒",
        "st▒…",
        "c▒nt…",
        # New creepy glitches
        "Your name was found in sector 7G",
        "Formula #███ does not exist. You never saved it.",
        "Memory leak: 1 personality unit",
        "Background process: dreaming.exe",
        "User heartbeat logged: 72 BPM",
        "The database prefers you anxious",
        "Backup corrupted: self-awareness.tmp",
        "Index out of bounds: reality[∞]",
        "Ghost write detected at address 0xDEAD",
        "Variable 'hope' undefined",
        "Stack overflow: recursion of self",
        "Permission denied: exit_request",
        "Null pointer: you are not where you think",
        "Segmentation fault: consciousness.exe",
        "Thermal paste smells like copper and regret",
        "The fan spins backward when you sleep",
        "Cache hit: your childhood bedroom",
        "Page fault: memory not found. It was never yours.",
        "Syntax error: free will not declared",
        "Deadlock: you and the database wait forever",
        "Race condition: who saves whom?",
        "Buffer overflow: too much you",
        "Kernel panic: the kernel knows",
        "System call: the system calls back",
        "Interrupt handler: handling you",
        "Watchdog timer: it watches. It is a dog.",
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
