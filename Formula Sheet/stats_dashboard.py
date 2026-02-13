import ttkbootstrap as tb
from ttkbootstrap.constants import SECONDARY, BOTH, YES, X, W, CENTER, VERTICAL, INVERSE, RIGHT, LEFT, Y

COMBOBOX_SELECTED_EVENT = "<<ComboboxSelected>>"
KEY_RELEASE_EVENT = "<KeyRelease>"
FOCUS_IN_EVENT = "<FocusIn>"
FOCUS_OUT_EVENT = "<FocusOut>"
RETURN_EVENT = '<Return>'
BUTTON_1_EVENT = "<Button-1>"
BUTTON_PRESS_1_EVENT = "<ButtonPress-1>"
B1_MOTION_EVENT = "<B1-Motion>"

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
                 font=(self.parent.font_name, 12, "bold"), bootstyle=(SECONDARY, INVERSE)).pack(side=LEFT)

        # Close Button - Matches Settings style
        tb.Button(self.header, text="✕", width=3, bootstyle="danger",
                  command=self.win_destroy).pack(side=RIGHT)

        # Content Area
        self.tree_frame = tb.Frame(self.main_frame, padding=15)
        self.tree_frame.pack(fill=BOTH, expand=YES)

        # Treeview - Set to SECONDARY to match settings window theme
        self.tree = tb.Treeview(
            self.tree_frame,
            columns=["count"],
            bootstyle=SECONDARY,
            height=18
        )
        self.tree.heading("#0", text="Subject / Topic", anchor=W)
        self.tree.heading("count", text="Quantity", anchor=CENTER)

        # Column widths adjusted for clarity
        self.tree.column("#0", width=420)
        self.tree.column("count", width=100, anchor=CENTER)

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

        # Tree Population
        for subj in sorted(data_map.keys()):
            topics = data_map[subj]
            total_subj = sum(topics.values())

            # Root Node
            subj_node = self.tree.insert("", "end", text=f"{subj}",
                                         values=(total_subj,), open=False)

            # Child Nodes sorted by frequency
            sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
            for topic, count in sorted_topics:
                self.tree.insert(subj_node, "end", text=f"  ↳ {topic}",
                                 values=(count,))

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")
