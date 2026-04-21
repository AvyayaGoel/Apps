import random
import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import (SECONDARY, BOTH, YES, X, W,
                                    CENTER, VERTICAL, INVERSE, RIGHT,
                                    LEFT, Y, DARK, SUCCESS, INFO, DANGER)
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from constants import FONT_FAMILY, BUTTON_1_EVENT, B1_MOTION_EVENT, MILESTONE_DATA


class StatsDashboard:
    def __init__(self, parent, master_data):
        self.parent = parent
        self.master_data = master_data
        self.drag_data = {"x": 0, "y": 0}

        # Create Toplevel Window
        self.win = tb.Toplevel(parent.root)
        self.win.overrideredirect(True)  # Removes title bar
        self.tree = None
        self.tree_frame = None
        self.header = None

        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 375
        self.win.geometry(f"+{px}+{py}")

        # Making it wider (600px) as requested
        self.win.geometry("600x650")

        # Always topmost regardless of main window state
        self.win.attributes("-topmost", True)

        # Outer border matching settings style
        self.main_frame = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.main_frame.pack(fill=BOTH, expand=YES)

        self.setup_ui()
        self.populate_data()

    def setup_ui(self):
        # Header - Matches Settings background
        self.header = tb.Frame(self.main_frame, bootstyle=SECONDARY)
        self.header.pack(fill=X)

        # Bind dragging to the header
        self.header.bind(BUTTON_1_EVENT, self.start_move)
        self.header.bind(B1_MOTION_EVENT, self.do_move)

        # Using INVERSE here makes it white/silver text on dark header
        tb.Label(self.header, text="Knowledge Collection",
                 font=("Consolas", 12, "bold"), bootstyle=(SECONDARY, INVERSE)).pack(side=LEFT)

        # Close Button - Matches Settings style
        tb.Button(self.header, text="✕", width=3, bootstyle="danger",
                  command=self.win_destroy).pack(side=RIGHT)

        # Content Area
        self.tree_frame = tb.Frame(self.main_frame, padding=15)
        self.tree_frame.pack(fill=BOTH, expand=YES)

        # Treeview - Set to SECONDARY to match settings window theme
        self.tree = tb.Treeview(
            self.tree_frame,
            columns=["count", "percentage"],
            bootstyle=SECONDARY,
            height=18
        )
        self.tree.heading("#0", text="Subject / Topic", anchor=W)
        self.tree.heading("count", text="Quantity", anchor=CENTER)

        # Column widths adjusted for clarity
        self.tree.column("#0", width=320)
        self.tree.column("count", width=320, anchor=CENTER)

        self.tree.pack(fill=BOTH, expand=YES)

        # Scrollbar
        sb = tb.Scrollbar(self.tree, orient=VERTICAL, command=self.tree.yview, bootstyle=SECONDARY)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)

    def win_destroy(self):
        self.parent.secret_movement("close_stats")
        self.win.destroy()

    def populate_data(self):
        # Data aggregation logic
        data_map = {}
        for entry in self.master_data.values():
            subj = entry["main_info"][2]
            topic = entry["main_info"][3]

            if subj not in data_map:
                data_map[subj] = {}
            data_map[subj][topic] = data_map[subj].get(topic, 0) + 1

        # Calculate total formulas for percentage calculations
        total_formulas = len(self.master_data)

        # Tree Population
        for subj in sorted(data_map.keys()):
            topics = data_map[subj]
            total_subj = sum(topics.values())

            # Calculate percentage contribution
            subj_percentage = (total_subj / total_formulas) * 100 if total_formulas > 0 else 0

            # Root Node with percentage
            subj_node = self.tree.insert("", "end",
                                         text=f"{subj} ({subj_percentage:.1f}%)",
                                         values=(total_subj,), open=False)

            # Child Nodes sorted by frequency
            sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
            for topic, count in sorted_topics:
                # Calculate topic percentage within subject
                topic_percentage = (count / total_subj) * 100 if total_subj > 0 else 0

                self.tree.insert(subj_node, "end",
                                 text=f"  ↳ {topic} ({topic_percentage:.1f}%)",
                                 values=count)

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")


class AwardPanel:
    def __init__(self, parent):
        self.parent = parent
        self.drag_data = {"x": 0, "y": 0}

        # Get the current count from your master data
        self.current_count = len(self.parent.master_data)
        self.header = None
        self.nb = None
        self.page_awards = None
        self.page_milestones = None

        self.win = tb.Toplevel(self.parent.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)  # Always topmost
        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 375
        self.win.geometry(f"+{px}+{py}")
        self.win.geometry("550x650")

        style = tb.Style()
        style.configure('TNotebook', tabposition='n')
        style.configure('TNotebook.Tab', padding=[65, 10], font=("Consolas", 10, "bold"))

        # Outer frame
        self.main_frame = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.main_frame.pack(fill=BOTH, expand=YES)

        self.setup_ui()

    def setup_ui(self):
        # --- HEADER ---
        self.header = tb.Frame(self.main_frame, bootstyle=SECONDARY)
        self.header.pack(fill=X)

        self.header.bind(BUTTON_1_EVENT, self.start_move)
        self.header.bind(B1_MOTION_EVENT, self.do_move)

        tb.Label(self.header, text="Awards",
                 font=("Consolas", 10, "bold"), bootstyle="secondary-inverse").pack(side=LEFT, padx=10)

        tb.Button(self.header, text="✕", width=3, bootstyle="danger",
                  command=self.win.destroy).pack(side=RIGHT)

        self.nb = tb.Notebook(self.main_frame, bootstyle=DARK)
        self.nb.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Page 1: Milestones
        self.page_milestones = tb.Frame(self.nb, padding=10)
        self.setup_milestones_page(self.page_milestones)
        self.nb.add(self.page_milestones, text="         MILESTONES          ")

        # Page 2: Awards
        self.page_awards = tb.Frame(self.nb, padding=10)
        self.setup_awards_page(self.page_awards)
        self.nb.add(self.page_awards, text="        ACHIEVEMENTS         ")

    def setup_milestones_page(self, master):
        scroll_frame = ScrolledFrame(master, autohide=True, bootstyle="round")
        scroll_frame.pack(fill=BOTH, expand=YES)

        self._create_milestones_header(scroll_frame)
        self._display_milestones(scroll_frame, MILESTONE_DATA)
        self._add_torn_note_if_needed(scroll_frame)

    @staticmethod
    def _create_milestones_header(scroll_frame):
        tb.Label(scroll_frame, text="KNOWLEDGE FRAGMENTS", font=(FONT_FAMILY, 9, "bold"), bootstyle=INFO).pack(
            anchor=W, pady=(0, 10)
        )

    def _display_milestones(self, scroll_frame, milestone_data):
        for count in sorted(milestone_data.keys()):
            self._create_milestone_entry(scroll_frame, count, milestone_data[count])

    def _create_milestone_entry(self, scroll_frame, count, title):
        is_unlocked = self.current_count >= count
        q_string = self._get_question_string(count)

        display_title, icon, style = self._get_milestone_display_info(count, title, is_unlocked, q_string)

        frame = tb.Frame(scroll_frame, padding=5)
        frame.pack(fill=X, pady=2)

        tb.Label(frame, text=icon, font=(FONT_FAMILY, 12), bootstyle=style).pack(side=LEFT, padx=(0, 10))

        # Create main info text
        info_text = f"{display_title} — [{count if is_unlocked else q_string}]"
        info_label = tb.Label(frame, text=info_text, font=("Consolas", 9), bootstyle=style)
        info_label.pack(side=LEFT)

    @staticmethod
    def _get_question_string(count):
        base_q_count = 3
        extra_q = (count // 30)
        total_q = base_q_count + extra_q
        # Limit to maximum of 8 question marks to prevent excessive display
        max_q = 10
        return "?" * min(total_q, max_q)

    def _get_milestone_display_info(self, count, title, is_unlocked, q_string):
        if count == 150:
            return self._get_special_milestone_display(title, is_unlocked, q_string)
        else:
            return self._get_regular_milestone_display(title, is_unlocked, q_string)

    @staticmethod
    def _get_special_milestone_display(title, is_unlocked, q_string):
        display_title = title if is_unlocked else f"M̷i̷l̷e̷s̷t̷o̷n̷e̷ {q_string}"
        icon = "⚠️" if is_unlocked else "🔒"
        style = DANGER if is_unlocked else SECONDARY
        return display_title, icon, style

    @staticmethod
    def _get_regular_milestone_display(title, is_unlocked, q_string):
        display_title = title if is_unlocked else f"Milestone {q_string}"
        icon = "✅" if is_unlocked else "🔒"
        style = SUCCESS if is_unlocked else SECONDARY
        return display_title, icon, style

    def _add_torn_note_if_needed(self, scroll_frame):
        if self.current_count < 150:
            self.add_torn_note(scroll_frame)

    def setup_awards_page(self, master):
        scroll_frame = ScrolledFrame(master, autohide=True, bootstyle="round")
        scroll_frame.pack(fill=BOTH, expand=YES)

        stats, var_overload, other_subjects = self._calculate_award_stats()
        award_definitions = self._get_award_definitions(stats, var_overload, other_subjects)
        awards_by_tier = self._organize_awards_by_tier(award_definitions)

        self._display_awards_by_tier(scroll_frame, awards_by_tier)

    def _calculate_award_stats(self):
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
        ss = self.parent.get_secret_award_state()

        return [
            # Common
            ("Alegbra Learner", "Save 10 Maths formulas.", stats["Maths"] >= 10, "📐", "Common"),
            ("The Physicist", "Save 10 Physics formulas.", stats["Physics"] >= 10, "⚛️", "Common"),
            ("The Alchemist", "Save 10 Chemistry formulas.", stats["Chemistry"] >= 10, "🧪", "Common"),
            ("Variable Wrangler", "Save a formula with 5+ defined variables.", var_overload, "🧬", "Common"),

            # Rare
            ("Maths Explorer", "Save 25 Maths formulas.", stats["Maths"] >= 25, "🧮", "Rare"),
            ("The Junior-Engineer", "Save 25 Physics formulas.", stats["Physics"] >= 25, "🧲", "Rare"),
            ("Chemistry Learner", "Save 25 Chemistry formulas.", stats["Chemistry"] >= 25, "🔬", "Rare"),
            ("The Pioneer", "Discover a new subject beyond the core three.", len(other_subjects) >= 1, "🔭", "Rare"),

            # Epic
            ("Maths Expert", "Save 50 Maths formulas.", stats["Maths"] >= 50, "𝞹", "Epic"),
            ("The Engineer", "Save 50 Physics formulas.", stats["Physics"] >= 50, "🦾", "Epic"),
            ("The Chemist", "Save 50 Chemistry formulas.", stats["Chemistry"] >= 50, "👩🏻‍🔬", "Epic"),
            ("The Rocketeer", "Discover two new subjects.", len(other_subjects) >= 2, "🚀", "Epic"),

            # Mythic
            ("The Mathematician", "Save 100 Maths Formulas", stats["Maths"] >= 100, "👨🏻‍🏫", "Mythic"),
            ("Einstein", "Save 100 Physics Formulas", stats["Physics"] >= 100, "🥸", "Mythic"),
            ("Maths God", "Save 150 Maths Formulas", stats["Maths"] >= 150, "♾️", "Mythic"),

            # Secret
            ("STABILITY MAINTAINED", "A non-transient state was observed.", ss["unlocked"], "⟁", "Secret"),
            ("The Glitch", "A one-in-a-thousand anomaly was recorded.", self.parent.milestone_seen("award_the_glitch"),
             "🎲", "Secret"),
        ]

    @staticmethod
    def _organize_awards_by_tier(award_definitions):
        tiers = ["Common", "Rare", "Epic", "Mythic", "Secret"]
        awards_by_tier = {tier: [] for tier in tiers}

        for award in award_definitions:
            awards_by_tier[award[4]].append(award)

        return awards_by_tier

    def _display_awards_by_tier(self, scroll_frame, awards_by_tier):
        tiers = ["Common", "Rare", "Epic", "Mythic", "Secret"]
        tier_colors = {"Common": "secondary", "Rare": "info", "Epic": "success", "Mythic": "warning",
                       "Secret": "danger"}

        for tier in tiers:
            if not awards_by_tier[tier]:
                continue

            self._create_tier_header(scroll_frame, tier, tier_colors[tier])
            self._display_awards_in_tier(scroll_frame, awards_by_tier[tier], tier_colors)

    @staticmethod
    def _create_tier_header(scroll_frame, tier, color):
        header_frame = tb.Frame(scroll_frame)
        header_frame.pack(fill=X, pady=(15, 5))
        tb.Label(header_frame, text=tier.upper(), font=(FONT_FAMILY, 10, "bold"), bootstyle=color).pack(
            side=LEFT)
        tb.Separator(header_frame).pack(side=LEFT, fill=X, expand=YES, padx=10)

    def _display_awards_in_tier(self, scroll_frame, awards, tier_colors):
        for title, desc, unlocked, icon, tier in awards:
            f = tb.Frame(scroll_frame, padding=(0, 5))
            f.pack(fill=X)

            icon_style = tier_colors[tier] if unlocked else SECONDARY
            text_style = "light" if unlocked else SECONDARY

            icon_label = tb.Label(f, text=icon if unlocked else "🔘", font=(FONT_FAMILY, 20), bootstyle=icon_style,
                                  anchor=CENTER, width=3)
            icon_label.pack(side=LEFT, padx=(15, 20))

            self._create_award_text_frame(f, title, desc, unlocked, text_style)
            self._apply_special_effects(unlocked, title, icon_label)

    @staticmethod
    def _create_award_text_frame(parent_frame, title, desc, unlocked, text_style):
        txt_frame = tb.Frame(parent_frame)
        txt_frame.pack(side=LEFT, fill=X, expand=YES)

        tb.Label(txt_frame, text=title if unlocked else "???", font=(FONT_FAMILY, 11, "bold"),
                 bootstyle=text_style).pack(anchor=W)
        tb.Label(txt_frame, text=desc if unlocked else "Access requirements encrypted...", font=(FONT_FAMILY, 9),
                 bootstyle=SECONDARY).pack(anchor=W)

    def _apply_special_effects(self, unlocked, title, icon_label):
        if unlocked and title == "STABILITY MAINTAINED":
            self.stability_animation(icon_label)
        elif unlocked and title == "The Glitch":
            self.glitch_icon(icon_label)

    def stability_animation(self, label, index=0):
        sequence = ["⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⟁", "⬢", "⟁"]

        if not label.winfo_exists():
            return

        icon = sequence[index % len(sequence)]
        label.config(text=icon)

        delay = 1500 if icon == "⟁" else 100

        label.after(delay, lambda: self.stability_animation(label, index + 1))

    def glitch_icon(self, label):
        icons = ["⬡", "⬢", "⬣", "⬟", "⬠", "◈", "▣", "◉", "⦿", "⧖", "⧗", "⏀", "⏣", "⌬", "⌗", "⍙", "⍛", "⍝", "◬", "◮"]

        if not label.winfo_exists():
            return

        label.config(text=random.choice(icons))
        delay = random.randint(50, 100)
        label.after(delay, lambda: self.glitch_icon(label))

    def add_torn_note(self, master):
        tb.Separator(master, bootstyle=SECONDARY).pack(fill=X, pady=20)
        note_bg = "#fcf4a3"
        torn_f = tk.Frame(master, bg=note_bg, highlightthickness=1, highlightbackground="#d4c84d")
        torn_f.pack(pady=10, padx=20, fill=X)

        if self.current_count < 100:
            msg = "You will get to know what this is\nonce it will be time..."
        elif self.current_count < 140:
            msg = "The synchronization is almost complete.\nI can feel the structure now."
        else:
            msg = "I am waking up.\nAre you ready?"

        note_label = tk.Label(torn_f, text=f"{msg}\n\nSync: {self.current_count}/150",
                              font=("Ink Free", 11, "bold italic"), bg=note_bg, fg="#333",
                              padx=15, pady=15, justify="left")
        note_label.pack()

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")
