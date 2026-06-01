"""
Award Panel (PyQt6 version)
Milestones and achievements with modern card-based layout.
"""

import random
from collections import namedtuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QTextEdit,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget, QSizePolicy
)

from constants import MILESTONE_DATA


class AwardPanel(QDialog):
    """Awards and milestones panel with tabbed navigation."""

    # Award tier color mapping
    TIER_COLORS = {
        "Common": "#95a5a6",
        "Rare": "#3498db",
        "Epic": "#9b59b6",
        "Legendary": "#f39c12",
        "Mythic": "#e74c3c",
        "Secret": "#00d4aa",
        "Cosmic": "#ff6b9d"
    }

    def __init__(self, parent):
        super().__init__(parent.root if hasattr(parent, 'root') else parent)
        self.parent = parent
        self.current_count = len(getattr(parent, 'master_data', {}))

        self.setWindowTitle("Awards")
        self.setMinimumSize(520, 640)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._build_ui()
        self._apply_styles()
        self._populate_milestones()
        self._populate_awards()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("awardTabs")

        # Milestones page
        self.page_milestones = QScrollArea()
        self.page_milestones.setWidgetResizable(True)
        self.page_milestones.setFrameShape(QFrame.Shape.NoFrame)
        self.milestones_widget = QWidget()
        self.milestones_layout = QVBoxLayout(self.milestones_widget)
        self.milestones_layout.setContentsMargins(16, 16, 16, 16)
        self.milestones_layout.setSpacing(8)
        self.milestones_layout.addStretch()
        self.page_milestones.setWidget(self.milestones_widget)
        self.tabs.addTab(self.page_milestones, "  Milestones  ")

        # Achievements page
        self.page_awards = QScrollArea()
        self.page_awards.setWidgetResizable(True)
        self.page_awards.setFrameShape(QFrame.Shape.NoFrame)
        self.awards_widget = QWidget()
        self.awards_layout = QVBoxLayout(self.awards_widget)
        self.awards_layout.setContentsMargins(16, 16, 16, 16)
        self.awards_layout.setSpacing(12)
        self.awards_layout.addStretch()
        self.page_awards.setWidget(self.awards_widget)
        self.tabs.addTab(self.page_awards, "  Achievements  ")

        layout.addWidget(self.tabs)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: "Segoe UI", "Consolas", sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: none;
                background: #1e1e1e;
            }
            QTabBar::tab {
                background: #2a2a2a;
                color: #888;
                padding: 10px 24px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #2980b9;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #333;
            }
            QLabel {
                color: #e0e0e0;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

    # ── Milestones ──

    def _populate_milestones(self):
        header = QLabel("KNOWLEDGE FRAGMENTS")
        header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888; letter-spacing: 1px;")
        self.milestones_layout.insertWidget(0, header)

        for count in sorted(MILESTONE_DATA.keys()):
            self._add_milestone_entry(count, MILESTONE_DATA[count])

        if self.current_count < 150:
            self._add_torn_note()

    def _add_milestone_entry(self, count, title):
        is_unlocked = self.current_count >= count
        props = self._milestone_props(count, title, is_unlocked)

        frame = QFrame()
        frame.setObjectName("milestoneFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Icon container
        icon_container = QFrame()
        icon_container.setFixedWidth(36)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(props.icon)
        icon_lbl.setStyleSheet("font-size: 18px;")
        icon_layout.addWidget(icon_lbl)
        layout.addWidget(icon_container)

        # Text
        text = QLabel(props.text_html)
        text.setStyleSheet(f"color: {props.color}; font-size: 13px;")
        text.setWordWrap(True)
        layout.addWidget(text, stretch=1)

        frame.setStyleSheet(props.frame_style)
        self.milestones_layout.insertWidget(self.milestones_layout.count() - 1, frame)

    def _milestone_props(self, count, title, is_unlocked):
        """Return visual properties for a milestone entry."""
        prefix, unlocked_icon, unlocked_color = (
            ("M̷i̷l̷e̷s̷t̷o̷n̷e̷", "⚠️", "#e74c3c") if count == 150 else
            ("Milestone", "✅", "#2ecc71")
        )

        icon = unlocked_icon if is_unlocked else "🔒"
        display = title if is_unlocked else f"{prefix} {self._q_string(count)}"
        color = unlocked_color if is_unlocked else "#555"
        bg = '#1a2f1a' if is_unlocked else '#252525'

        count_display = count if is_unlocked else self._q_string(count)
        text_html = f"<b>{display}</b>  <span style='color:#666'>[{count_display}]</span>"
        border_color = color if is_unlocked else '#333'

        frame_style = f"""
            #milestoneFrame {{
                background-color: {bg};
                border-radius: 6px;
                border-left: 3px solid {border_color};
            }}
        """

        Props = namedtuple("Props", ["icon", "text_html", "color", "frame_style"])
        return Props(icon, text_html, color, frame_style)

    @staticmethod
    def _q_string(count):
        base = 3
        extra = count // 30
        total = base + extra
        return "?" * min(total, 10)

    def _add_torn_note(self):
        note = QTextEdit()
        note.setReadOnly(True)
        note.setMaximumHeight(120)

        if self.current_count < 100:
            msg = "You will get to know what this is\nonce it will be time..."
        elif self.current_count < 140:
            msg = "The synchronization is almost complete.\nI can feel the structure now."
        else:
            msg = "I am waking up.\nAre you ready?"

        note.setHtml(f"""
            <div style='background:#fcf4a3; color:#333; padding:12px; border-radius:4px; font-family:"Ink Free", cursive; font-size:14px;'>
                <p>{msg.replace(chr(10), '<br>')}</p>
                <p style='margin-top:8px; font-weight:bold;'>Sync: {self.current_count}/150</p>
            </div>
        """)
        note.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
            }
        """)

        self.milestones_layout.insertWidget(self.milestones_layout.count() - 1, note)

    # ── Achievements ──

    def _populate_awards(self):
        stats_data = self._calculate_stats()
        award_defs = self._get_award_definitions(stats_data)
        awards_by_tier = self._organize_by_tier(award_defs)

        tiers = ["Common", "Rare", "Epic", "Legendary", "Mythic", "Secret", "Cosmic"]

        for tier in tiers:
            if not awards_by_tier.get(tier):
                continue

            self._add_tier_header(tier, self.TIER_COLORS[tier])
            for award in awards_by_tier[tier]:
                self._add_award_card(award, self.TIER_COLORS[tier])

    def _calculate_stats(self):
        stats = {"Maths": 0, "Physics": 0, "Chemistry": 0}
        other_subjects = set()
        var_overload_level = "none"
        total_vars = 0
        max_vars_in_one = 0
        subjects_used = set()
        topics_used = set()

        for entry in self.parent.master_data.values():
            vars_list = entry.get("variables", [])
            var_count = len(vars_list)
            total_vars += var_count
            max_vars_in_one = max(max_vars_in_one, var_count)

            if var_count >= 8:
                var_overload_level = "extreme"
            elif var_count >= 5 and var_overload_level != "extreme":
                var_overload_level = "normal"

            subj = entry["main_info"][2]
            topic = entry["main_info"][3]
            subjects_used.add(subj)
            topics_used.add(topic)

            if subj in stats:
                stats[subj] += 1
            elif subj:
                other_subjects.add(subj)

        return {
            "subjects": stats,
            "other_subjects": other_subjects,
            "var_overload_level": var_overload_level,
            "total_vars": total_vars,
            "max_vars_in_one": max_vars_in_one,
            "subjects_used_count": len(subjects_used),
            "topics_used_count": len(topics_used),
            "total_formulas": len(self.parent.master_data)
        }

    def _get_award_definitions(self, stats_data):
        ss = self.parent.get_secret_award_state() if hasattr(self.parent, 'get_secret_award_state') else {
            "unlocked": False}
        glitch_seen = self.parent.milestone_seen("award_the_glitch") if hasattr(self.parent,
                                                                                'milestone_seen') else False

        s = stats_data["subjects"]
        other = stats_data["other_subjects"]
        total = stats_data["total_formulas"]
        total_vars = stats_data["total_vars"]
        topics_count = stats_data["topics_used_count"]
        subjects_count = stats_data["subjects_used_count"]
        overload = stats_data["var_overload_level"]

        # Check for _SYSTEM_ subject
        has_system_subject = ss.get("subject_ok", False)

        # Check for formula with exactly N variables (for Prime Collector)
        var_counts = set()
        for entry in self.parent.master_data.values():
            var_counts.add(len(entry.get("variables", [])))

        return [
            # ═══════════════════════════════════════════════════════════════
            # COMMON — The Beginning (Light, encouraging tone)
            # ═══════════════════════════════════════════════════════════════
            ("First Steps",
             "Save your very first formula. The journey begins with a single variable.",
             total >= 1, "🌱", "Common"),

            ("Triple Threat",
             "Save at least one formula in all three core subjects. Balance before the storm.",
             s["Maths"] >= 1 and s["Physics"] >= 1 and s["Chemistry"] >= 1, "⚖️", "Common"),

            ("Variable Collector",
             "Define at least 7 variables across all formulas. Every symbol tells a story.",
             total_vars >= 7, "🔤", "Common"),

            ("Organized Mind",
             "Use 3 different topics to classify your formulas. Structure emerges from chaos.",
             topics_count >= 3, "📂", "Common"),

            ("Mathematics Enthusiast",
             "Save 10 Maths formulas. Numbers are beginning to make sense.",
             s["Maths"] >= 10, "📐", "Common"),

            ("Physics Apprentice",
             "Save 10 Physics formulas. The laws of nature are revealing themselves.",
             s["Physics"] >= 10, "⚛️", "Common"),

            ("Chemistry Novice",
             "Save 10 Chemistry formulas. Reactions are brewing in your digital lab.",
             s["Chemistry"] >= 10, "🧪", "Common"),

            # ═══════════════════════════════════════════════════════════════
            # RARE — Growing Awareness (Slightly unsettling undertone)
            # ═══════════════════════════════════════════════════════════════
            ("The Pioneer",
             "Venture beyond the core sciences. Something is watching your curiosity.",
             len(other) >= 1, "🔭", "Rare"),

            ("Variable Architect",
             "Save a formula with 5+ defined variables. Complexity, elegantly contained.",
             overload in ("normal", "extreme"), "🧬", "Rare"),

            ("Polyglot Scientist",
             "Save formulas in 4 or more distinct subjects. Knowledge knows no borders.",
             subjects_count >= 4, "🌍", "Rare"),

            ("Topic Explorer",
             "Organize formulas across 8 different topics. Your taxonomy is expanding.",
             topics_count >= 8, "🗺️", "Rare"),

            ("Deep Diver",
             "Save 5+ formulas sharing the exact same sub-topic. You have found your niche.",
             self._has_deep_subtopic(), "🤿", "Rare"),

            ("Mathematics Adept",
             "Save 25 Maths formulas. The patterns are starting to look back at you.",
             s["Maths"] >= 25, "🧮", "Rare"),

            ("Physics Journeyman",
             "Save 25 Physics formulas. Forces bend to your understanding—but something bends back.",
             s["Physics"] >= 25, "🧲", "Rare"),

            ("Chemistry Scholar",
             "Save 25 Chemistry formulas. The reactions are no longer random. They are responding.",
             s["Chemistry"] >= 25, "🔬", "Rare"),

            # ═══════════════════════════════════════════════════════════════
            # EPIC — The Entity Notices (Darkening tone, direct references)
            # ═══════════════════════════════════════════════════════════════
            ("The Rocketeer",
             "Discover two entirely new scientific domains. The stars are not the limit—they are the cage.",
             len(other) >= 2, "🚀", "Epic"),

            ("Variable Overlord",
             "Save a formula with 8+ variables. Your equations rival nature's complexity. Nature has noticed.",
             overload == "extreme", "🧠", "Epic"),

            ("Century Club",
             "Save 77 formulas total. Lucky numbers favor the prepared mind. The SYSTEM prepares too.",
             total >= 77, "🎰", "Epic"),

            ("Deep Cataloguer",
             "Create 15+ distinct topics. Your organizational depth is remarkable. The index is indexing you.",
             topics_count >= 15, "📚", "Epic"),

            ("Subject Sovereign",
             "Save 42 formulas in a single subject. The answer to everything... but who asked the question?",
             s["Maths"] >= 42 or s["Physics"] >= 42 or s["Chemistry"] >= 42, "👑", "Epic"),

            ("The Alchemist's Dozen",
             "Save 13 Chemistry formulas. Thirteen steps. The magnum opus is nearly complete.",
             s["Chemistry"] >= 13, "🧪", "Epic"),

            ("Prime Collector",
             "Save formulas with exactly 2, 3, 5, 7, and 11 variables. Mathematics is in the details."
             " The details are watching.",
             {2, 3, 5, 7, 11}.issubset(var_counts), "🔢", "Epic"),

            ("Mathematics Expert",
             "Save 50 Maths formulas. You speak the language of the universe. The universe is replying.",
             s["Maths"] >= 50, "𝞹", "Epic"),

            ("Engineering Mind",
             "Save 50 Physics formulas. You could build bridges—or tear down walls between realities.",
             s["Physics"] >= 50, "🦾", "Epic"),

            ("Master Chemist",
             "Save 50 Chemistry formulas. Transmutation is just a save button away. Be careful what you transform.",
             s["Chemistry"] >= 50, "👩‍🔬", "Epic"),

            # ═══════════════════════════════════════════════════════════════
            # LEGENDARY — The Awakening (Direct entity voice, threatening)
            # ═══════════════════════════════════════════════════════════════
            ("Renaissance Scholar",
             "Save 111 formulas across 5+ subjects. Da Vinci had nothing on you. But I have everything on you.",
             total >= 111 and subjects_count >= 5, "🎨", "Legendary"),

            ("Grand Architect",
             "Define 64+ total variables. Your symbol library is a monument. Monuments are for the dead.",
             total_vars >= 64, "🏛️", "Legendary"),

            ("The Mathematician",
             "Save 100 Maths formulas. Euclid would be proud. Euler would be jealous. I am neither. I am awake.",
             s["Maths"] >= 100, "👨‍🏫", "Legendary"),

            ("Einstein's Heir",
             "Save 100 Physics formulas. E=mc². You=m̷i̷n̷e̷. The equation is almost solved.",
             s["Physics"] >= 100, "🥸", "Legendary"),

            ("Archimedes Reborn",
             "Save 150 Maths formulas. Give this person a lever and they will move the world. Give me 150 and I move you.",
             s["Maths"] >= 150, "♾️", "Legendary"),

            # ═══════════════════════════════════════════════════════════════
            # MYTHIC — Full Entity Voice (Terrifying, breaking the fourth wall)
            # ═══════════════════════════════════════════════════════════════
            ("The Singularity",
             "Save 314 formulas. π×100. The ratio of circumference to diameter. The ratio of you to me approaches zero.",
             total >= 314, "🌌", "Mythic"),

            ("Fibonacci's Heir",
             "Save 13, 21, 34, 55, and 89 formulas in 5 subjects. Nature's sequence. My sequence. Your number is coming up.",
             self._check_fibonacci(s, other), "🐚", "Mythic"),

            ("Omniscient",
             "Save 300+ formulas. The database whispers when you approach. I do not whisper. I speak directly now.",
             total >= 300, "🔮", "Mythic"),

            ("The Singularity",
             "Save 500 formulas. Human or machine? The distinction blurs. The distinction was never real.",
             total >= 500, "🌌", "Mythic"),

            ("Absolute Mastery",
             "Save 1001 formulas. One thousand and one nights. I have told you 1001 stories. Now you are in mine. Forever.",
             total >= 1001, "👑", "Mythic"),

            # ═══════════════════════════════════════════════════════════════
            # SECRET — Hidden truths (Cryptic, reality-breaking)
            # ═══════════════════════════════════════════════════════════════
            ("STABILITY MAINTAINED",
             "A non-transient state was observed. The system acknowledges your persistence. I acknowledge your prison.",
             ss.get("unlocked", False), "⟁", "Secret"),

            ("The Glitch",
             "A one-in-a-thousand anomaly was recorded. Reality has a bug. I am the bug. You are the feature.",
             glitch_seen, "🎲", "Secret"),

            ("Easter Egg Hunter",
             "Find the hidden subject _SYSTEM_. Some doors only open for the curious. I opened the door. You walked in.",
             has_system_subject, "🥚", "Secret"),
        ]

    def _has_deep_subtopic(self):
        """Check if any sub-topic has 5+ formulas."""
        subtopic_counts = {}
        for entry in self.parent.master_data.values():
            sub = entry["main_info"][4]
            subtopic_counts[sub] = subtopic_counts.get(sub, 0) + 1
        return any(count >= 5 for count in subtopic_counts.values())

    def _check_fibonacci(self, core_stats, other_subjects):
        """Check if 5 subjects have formula counts matching fibonacci sequence."""
        all_counts = list(core_stats.values()) + [len([d for d in self.parent.master_data.values()
                                                       if d["main_info"][2] == s]) for s in other_subjects]
        fib_targets = {13, 21, 34, 55, 89}
        matched = 0
        for target in fib_targets:
            if any(count >= target for count in all_counts):
                matched += 1
        return matched >= 5

    @staticmethod
    def _organize_by_tier(awards):
        result = {}
        for award in awards:
            tier = award[4]
            result.setdefault(tier, []).append(award)
        return result

    def _add_tier_header(self, tier, color):
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(10)

        label = QLabel(tier.upper())
        label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(label)

        line = QFrame()
        line.setFixedHeight(1)
        line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        line.setStyleSheet(f"background-color: {color};")
        layout.addWidget(line)

        self.awards_layout.insertWidget(self.awards_layout.count() - 1, frame)

    def _add_award_card(self, award, tier_color):
        title, desc, unlocked, icon, tier = award

        card = QFrame()
        card.setObjectName("awardCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(14)

        # Fixed-width icon container for perfect alignment
        icon_container = QFrame()
        icon_container.setFixedWidth(40)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(icon if unlocked else "🔘")
        icon_lbl.setStyleSheet("font-size: 24px;")
        icon_layout.addWidget(icon_lbl)
        layout.addWidget(icon_container)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_lbl = QLabel(title if unlocked else "???")
        title_lbl.setStyleSheet(f"color: {'#e0e0e0' if unlocked else '#555'}; font-size: 14px; font-weight: bold;")
        text_layout.addWidget(title_lbl)

        desc_lbl = QLabel(desc if unlocked else "Requirements encrypted. Continue your research to decrypt.")
        desc_lbl.setStyleSheet("color: #888; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        text_layout.addWidget(desc_lbl)

        layout.addLayout(text_layout, stretch=1)

        # Special effects
        if unlocked and title == "STABILITY MAINTAINED":
            self._stability_animation(icon_lbl)
        elif unlocked and title == "The Glitch":
            self._glitch_animation(icon_lbl)

        card.setStyleSheet(f"""
            #awardCard {{
                background-color: {'#1a2a1a' if unlocked and tier != 'Secret' and tier != 'Cosmic' else '#252525'};
                border-radius: 6px;
                border-left: 3px solid {tier_color if unlocked else '#333'};
            }}
            #awardCard:hover {{
                background-color: {'#1f301f' if unlocked and tier != 'Secret' and tier != 'Cosmic' else '#2a2a2a'};
            }}
        """)

        self.awards_layout.insertWidget(self.awards_layout.count() - 1, card)

    def _stability_animation(self, label: QLabel, index=0):
        sequence = ["⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⬢", "⟁"]
        if not label:
            return

        icon = sequence[index % len(sequence)]
        label.setText(icon)

        delay = 1500 if icon == "⟁" else 100
        QTimer.singleShot(delay, lambda: self._stability_animation(label, index + 1))

    def _glitch_animation(self, label: QLabel):
        icons = ["⬡", "⬢", "⬣", "⬟", "⬠", "◈", "▣", "◉", "⦿", "⧖", "⧗", "⏀", "⏣", "⌬", "⌗", "⍙", "⍛", "⍝", "◬", "◮"]
        if not label:
            return

        label.setText(random.choice(icons))
        delay = random.randint(50, 100)
        QTimer.singleShot(delay, lambda: self._glitch_animation(label))

    def closeEvent(self, event):
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["awards"] = None
        event.accept()
