"""
Award Panel (PyQt6 version)
Milestones and achievements with modern card-based layout.
"""

import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget, QSizePolicy
)


class AwardPanel(QDialog):
    """Awards and milestones panel with tabbed navigation."""

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
        from constants import MILESTONE_DATA

        header = QLabel("KNOWLEDGE FRAGMENTS")
        header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888; letter-spacing: 1px;")
        self.milestones_layout.insertWidget(0, header)

        for count in sorted(MILESTONE_DATA.keys()):
            self._add_milestone_entry(count, MILESTONE_DATA[count])

        if self.current_count < 150:
            self._add_torn_note()

    def _add_milestone_entry(self, count, title):
        is_unlocked = self.current_count >= count

        frame = QFrame()
        frame.setObjectName("milestoneFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Icon
        if count == 150:
            icon = "⚠️" if is_unlocked else "🔒"
            display = title if is_unlocked else f"M̷i̷l̷e̷s̷t̷o̷n̷e̷ {self._q_string(count)}"
            color = "#e74c3c" if is_unlocked else "#555"
        else:
            icon = "✅" if is_unlocked else "🔒"
            display = title if is_unlocked else f"Milestone {self._q_string(count)}"
            color = "#2ecc71" if is_unlocked else "#555"

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon_lbl)

        # Text
        text = QLabel(
            f"<b>{display}</b>  <span style='color:#666'>[{count if is_unlocked else self._q_string(count)}]</span>")
        text.setStyleSheet(f"color: {color}; font-size: 13px;")
        text.setWordWrap(True)
        layout.addWidget(text, stretch=1)

        frame.setStyleSheet(f"""
            #milestoneFrame {{
                background-color: {'#1a2f1a' if is_unlocked and count != 150 else '#252525'};
                border-radius: 6px;
                border-left: 3px solid {color if is_unlocked else '#333'};
            }}
        """)

        self.milestones_layout.insertWidget(self.milestones_layout.count() - 1, frame)

    def _q_string(self, count):
        base = 3
        extra = count // 30
        total = base + extra
        return "?" * min(total, 10)

    def _add_torn_note(self):
        from PyQt6.QtWidgets import QTextEdit

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
        stats, var_overload, other_subjects = self._calculate_stats()
        award_defs = self._get_award_definitions(stats, var_overload, other_subjects)
        awards_by_tier = self._organize_by_tier(award_defs)

        tiers = ["Common", "Rare", "Epic", "Mythic", "Secret"]
        tier_colors = {
            "Common": "#95a5a6",
            "Rare": "#3498db",
            "Epic": "#2ecc71",
            "Mythic": "#f39c12",
            "Secret": "#e74c3c"
        }

        for tier in tiers:
            if not awards_by_tier.get(tier):
                continue

            self._add_tier_header(tier, tier_colors[tier])
            for award in awards_by_tier[tier]:
                self._add_award_card(award, tier_colors[tier])

    def _calculate_stats(self):
        stats = {"Maths": 0, "Physics": 0, "Chemistry": 0}
        other_subjects = set()
        var_overload = False

        for entry in self.parent.master_data.values():
            if len(entry.get("variables", [])) >= 5:
                var_overload = True
            subj = entry["main_info"][2]
            if subj in stats:
                stats[subj] += 1
            elif subj:
                other_subjects.add(subj)

        return stats, var_overload, other_subjects

    def _get_award_definitions(self, stats, var_overload, other_subjects):
        ss = self.parent.get_secret_award_state() if hasattr(self.parent, 'get_secret_award_state') else {
            "unlocked": False}
        glitch_seen = self.parent.milestone_seen("award_the_glitch") if hasattr(self.parent,
                                                                                'milestone_seen') else False

        return [
            ("Alegbra Learner", "Save 10 Maths formulas.", stats["Maths"] >= 10, "📐", "Common"),
            ("The Physicist", "Save 10 Physics formulas.", stats["Physics"] >= 10, "⚛️", "Common"),
            ("The Alchemist", "Save 10 Chemistry formulas.", stats["Chemistry"] >= 10, "🧪", "Common"),
            ("Variable Wrangler", "Save a formula with 5+ defined variables.", var_overload, "🧬", "Common"),

            ("Maths Explorer", "Save 25 Maths formulas.", stats["Maths"] >= 25, "🧮", "Rare"),
            ("The Junior-Engineer", "Save 25 Physics formulas.", stats["Physics"] >= 25, "🧲", "Rare"),
            ("Chemistry Learner", "Save 25 Chemistry formulas.", stats["Chemistry"] >= 25, "🔬", "Rare"),
            ("The Pioneer", "Discover a new subject beyond the core three.", len(other_subjects) >= 1, "🔭", "Rare"),

            ("Maths Expert", "Save 50 Maths formulas.", stats["Maths"] >= 50, "𝞹", "Epic"),
            ("The Engineer", "Save 50 Physics formulas.", stats["Physics"] >= 50, "🦾", "Epic"),
            ("The Chemist", "Save 50 Chemistry formulas.", stats["Chemistry"] >= 50, "👩🏻‍🔬", "Epic"),
            ("The Rocketeer", "Discover two new subjects.", len(other_subjects) >= 2, "🚀", "Epic"),

            ("The Mathematician", "Save 100 Maths Formulas", stats["Maths"] >= 100, "👨🏻‍🏫", "Mythic"),
            ("Einstein", "Save 100 Physics Formulas", stats["Physics"] >= 100, "🥸", "Mythic"),
            ("Maths God", "Save 150 Maths Formulas", stats["Maths"] >= 150, "♾️", "Mythic"),

            ("STABILITY MAINTAINED", "A non-transient state was observed.", ss.get("unlocked", False), "⟁", "Secret"),
            ("The Glitch", "A one-in-a-thousand anomaly was recorded.", glitch_seen, "🎲", "Secret"),
        ]

    def _organize_by_tier(self, awards):
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

        # Icon
        icon_lbl = QLabel(icon if unlocked else "🔘")
        icon_lbl.setStyleSheet("font-size: 26px;")
        layout.addWidget(icon_lbl)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_lbl = QLabel(title if unlocked else "???")
        title_lbl.setStyleSheet(f"color: {'#e0e0e0' if unlocked else '#555'}; font-size: 14px; font-weight: bold;")
        text_layout.addWidget(title_lbl)

        desc_lbl = QLabel(desc if unlocked else "Access requirements encrypted...")
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
                background-color: {'#1a2a1a' if unlocked and tier != 'Secret' else '#252525'};
                border-radius: 6px;
                border-left: 3px solid {tier_color if unlocked else '#333'};
            }}
            #awardCard:hover {{
                background-color: {'#1f301f' if unlocked and tier != 'Secret' else '#2a2a2a'};
            }}
        """)

        self.awards_layout.insertWidget(self.awards_layout.count() - 1, card)

    def _stability_animation(self, label, index=0):
        sequence = ["⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⬢", "⟁"]
        if not label or not label.isVisible():
            return

        icon = sequence[index % len(sequence)]
        label.setText(icon)

        delay = 1500 if icon == "⟁" else 100
        QTimer.singleShot(delay, lambda: self._stability_animation(label, index + 1))

    def _glitch_animation(self, label):
        icons = ["⬡", "⬢", "⬣", "⬟", "⬠", "◈", "▣", "◉", "⦿", "⧖", "⧗", "⏀", "⏣", "⌬", "⌗", "⍙", "⍛", "⍝", "◬", "◮"]
        if not label or not label.isVisible():
            return

        label.setText(random.choice(icons))
        delay = random.randint(50, 100)
        QTimer.singleShot(delay, lambda: self._glitch_animation(label))

    def closeEvent(self, event):
        if hasattr(self.parent, 'windows') and isinstance(self.parent.windows, dict):
            self.parent.windows["awards"] = None
        event.accept()
