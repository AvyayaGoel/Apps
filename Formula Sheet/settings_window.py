import ttkbootstrap as tb
from ttkbootstrap.constants import SECONDARY, BOTH, YES, X, Y, VERTICAL, HORIZONTAL, SUCCESS, END, SOLID, DISABLED, \
    WARNING, RIGHT, LEFT, BOTTOM, W, INFO
from ttkbootstrap.dialogs import ColorChooserDialog, Messagebox
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from constants import (
    FONT_FAMILY, FOCUS_IN_EVENT,
    FOCUS_OUT_EVENT, BUTTON_1_EVENT, BUTTON_PRESS_1_EVENT,
    B1_MOTION_EVENT
)
from macro_manager_window import MacroManagerWindow
from toast_manager import show_toast
from tooltip_manager import TopMostToolTip


class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.win = tb.Toplevel(parent.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry("850x600")

        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 425
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 300
        self.win.geometry(f"+{px}+{py}")

        self.drag_data = {"x": 0, "y": 0}

        # Initialize variables
        self.theme_cb = None
        self.new_sub_name = None
        self.selected_color = "#ffffff"
        self.color_preview = None
        self.color_scroll = None
        self.color_list_frame = None
        self.suggestion_strictness_var = None
        self.reflection_scope_var = None
        self.suggest_var = None
        self.save_delay = None
        self.backup_var = None
        self.suggestion_count_var = None
        self.enable_suggestions_cb = None
        self.suggestion_spinbox = None
        self.strictness_radios = []

        self.color_placeholder = "Subject Name"

        self.content_frames = {}
        self.nav_buttons = {}

        self.topmost_var = tb.BooleanVar(value=self.parent.always_on_top)

        # 1. Window Border (Secondary Color)
        self.border_frame = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.border_frame.pack(fill=BOTH, expand=YES)

        # 2. Title Bar
        self.title_bar = tb.Frame(self.border_frame, bootstyle=SECONDARY)
        self.title_bar.pack(fill=X)
        self.title_bar.bind(BUTTON_PRESS_1_EVENT, self.start_move)
        self.title_bar.bind(B1_MOTION_EVENT, self.do_move)

        title_lbl = tb.Label(
            self.title_bar,
            text="  Settings",
            font=(FONT_FAMILY, 10, "bold"),
            bootstyle="inverse-secondary"
        )
        title_lbl.pack(side=LEFT, pady=5)
        title_lbl.bind(BUTTON_1_EVENT, self.start_move)
        title_lbl.bind(B1_MOTION_EVENT, self.do_move)

        tb.Button(
            self.title_bar,
            text="✕",
            bootstyle="danger",
            width=4,
            command=self.win.destroy
        ).pack(side=RIGHT)

        # 3. Main Background Container (Default Theme Background)
        self.main_bg = tb.Frame(self.border_frame)
        self.main_bg.pack(fill=BOTH, expand=YES)

        # 4. Content Layout (Nav | Sep | Content)
        self.body_frame = tb.Frame(self.main_bg)
        self.body_frame.pack(fill=BOTH, expand=YES)

        # Navigation Pane
        self.nav_frame = tb.Frame(self.body_frame, width=200, padding=(10, 20))
        self.nav_frame.pack(side=LEFT, fill=Y)

        # Vertical Separator
        tb.Separator(self.body_frame, orient=VERTICAL).pack(side=LEFT, fill=Y)

        # Content Pane
        self.content_frame = tb.Frame(self.body_frame, padding=20)
        self.content_frame.pack(side=LEFT, fill=BOTH, expand=YES)

        # Initialize Pages
        self.create_page("General", self.setup_general_page)
        self.create_page("Symbol Suggestions", self.setup_suggestions_page)
        self.create_page("Autosave", self.setup_autosave_page)

        self.show_page("General")

        # 5. Bottom Action Bar
        tb.Separator(self.main_bg, orient=HORIZONTAL).pack(fill=X)

        self.bottom_bar = tb.Frame(self.main_bg, padding=15)
        self.bottom_bar.pack(fill=X, side=BOTTOM)

        tb.Button(
            self.bottom_bar,
            text="Apply & Save",
            bootstyle=SUCCESS,
            width=15,
            command=self.apply_all
        ).pack(side=RIGHT)

        tb.Button(
            self.bottom_bar,
            text="Cancel",
            bootstyle="secondary-outline",
            width=10,
            command=self.win.destroy
        ).pack(side=RIGHT, padx=10)

    def create_page(self, name, setup_func):
        frame = tb.Frame(self.content_frame)
        self.content_frames[name] = frame
        setup_func(frame)

        btn = tb.Button(
            self.nav_frame,
            text=name,
            bootstyle="secondary-outline",
            command=lambda n=name: self.show_page(n),
            width=20
        )
        btn.pack(fill=X, pady=2)
        self.nav_buttons[name] = btn

    def show_page(self, name):
        for f in self.content_frames.values():
            f.pack_forget()
        for b in self.nav_buttons.values():
            b.configure(bootstyle="secondary-outline")

        self.content_frames[name].pack(fill=BOTH, expand=YES)
        self.nav_buttons[name].configure(bootstyle=SECONDARY)

    def setup_general_page(self, master):
        content = ScrolledFrame(master, autohide=True, bootstyle="round")
        content.pack(fill=BOTH, expand=YES)

        cb = tb.Checkbutton(
            content,
            text="Keep Window Always on Top",
            variable=self.topmost_var,
            bootstyle="success-square-toggle",
        )
        cb.pack(anchor=W, pady=10)

        tb.Separator(content).pack(fill=X, pady=12)

        tb.Label(content, text="Appearance", font=("Arial", 11, "bold")).pack(anchor=W)

        theme_f = tb.Frame(content)
        theme_f.pack(fill=X, pady=8, padx=5)

        tb.Label(theme_f, text="Theme:").pack(side=LEFT)

        self.theme_cb = tb.Combobox(
            theme_f,
            values=["darkly", "cyborg", "vapor", "solar", "superhero",
                    "litera", "flatly", "minty"],
            state="readonly"
        )
        self.theme_cb.set(self.parent.root.style.theme.name)
        self.theme_cb.pack(side=RIGHT, fill=X, expand=YES, padx=(10, 0))

        tb.Separator(content).pack(fill=X, pady=12)

        tb.Label(
            content,
            text="Subject Color Mapping",
            font=("Arial", 11, "bold")
        ).pack(anchor=W, pady=(0, 6))

        add_color_f = tb.Frame(content)
        add_color_f.pack(fill=X, pady=6, padx=5)

        self.new_sub_name = tb.Entry(add_color_f)
        _restore_placeholder(self.new_sub_name, self.color_placeholder)
        self.new_sub_name.bind(FOCUS_IN_EVENT, lambda e: _clear_placeholder(self.new_sub_name, self.color_placeholder))
        self.new_sub_name.bind(FOCUS_OUT_EVENT,
                               lambda e: _restore_placeholder(self.new_sub_name, self.color_placeholder))
        self.new_sub_name.pack(side=LEFT, fill=X, expand=True, padx=2)

        self.selected_color = "#ffffff"
        self.color_preview = tb.Label(add_color_f, text="  ", background=self.selected_color, relief=SOLID)
        self.color_preview.pack(side=LEFT, padx=5, ipadx=6)

        def pick_color():
            cd = ColorChooserDialog(self.win, initialcolor=self.selected_color)
            cd.show()
            if cd.result:
                self.selected_color = cd.result.hex
                self.color_preview.configure(background=self.selected_color)

        tb.Button(add_color_f, text="Pick", bootstyle="outline-secondary", command=pick_color).pack(side=LEFT, padx=2)
        tb.Button(add_color_f, text="+", bootstyle=SUCCESS, command=self.add_color_mapping).pack(side=LEFT, padx=2)

        self.color_scroll = ScrolledFrame(content, height=200, autohide=False, bootstyle="round")
        self.color_scroll.pack(fill=X, expand=True, pady=(8, 20))

        self.color_list_frame = tb.Frame(self.color_scroll)
        self.color_list_frame.pack(fill=BOTH, expand=True)
        self.color_list_frame.columnconfigure(0, weight=1)
        self.refresh_color_list()

        tb.Separator(content).pack(fill=X, pady=12)

        tb.Label(content, text="Workflow & Macros", font=("Arial", 10, "bold")).pack(anchor=W, padx=5)

        macro_manage_f = tb.Frame(content)
        macro_manage_f.pack(fill=X, pady=10, padx=5)

        tb.Button(
            macro_manage_f,
            text="⌨️ Manage Keypad Buttons",
            bootstyle=INFO,
            command=self.open_macro_manager
        ).pack(fill=X)

    def setup_suggestions_page(self, master):
        content = tb.Frame(master, padding=10)
        content.pack(fill=BOTH, expand=YES)

        # Check if there are enough formulas for suggestions to work
        formula_count = len(self.parent.master_data)
        suggestions_enabled = formula_count >= 6

        if not suggestions_enabled:
            # Show warning message when fewer than 6 formulas
            warning_frame = tb.Frame(content, bootstyle=WARNING)
            warning_frame.pack(fill=X, pady=(0, 10))
            tb.Label(
                warning_frame,
                text=f"⚠️ Smart Suggestions require at least 6 formulas (you have {formula_count})",
                bootstyle="inverse-warning",
                padding=10
            ).pack()

        self.suggestion_strictness_var = tb.StringVar(
            value=self.parent.suggestion_strictness
        )

        lf = tb.Labelframe(content, text=" Suggestion Strictness ", padding=15)
        lf.pack(fill=X, pady=10)

        modes = {
            "Conservative": "Only suggest when meaning is guaranteed.",
            "Balanced": "Suggest on strong context matches (Default).",
            "Aggressive": "Suggest near-context matches for speed."
        }

        for mode, desc in modes.items():
            row = tb.Frame(lf)
            row.pack(fill=X, pady=4)
            radio = tb.Radiobutton(
                row,
                text=mode,
                variable=self.suggestion_strictness_var,
                value=mode,
                state="normal" if suggestions_enabled else "disabled"
            )
            radio.pack(side=LEFT)
            self.strictness_radios.append(radio)
            tb.Label(row, text=f"- {desc}", bootstyle=SECONDARY).pack(side=LEFT, padx=10)

        tb.Separator(content).pack(fill=X, pady=15)

        self.suggest_var = tb.BooleanVar(value=self.parent.enable_suggestions)
        cb = tb.Checkbutton(
            content,
            text="Enable Smart Suggestions",
            variable=self.suggest_var,
            bootstyle="success-square-toggle",
            state="normal" if suggestions_enabled else "disabled"
        )
        cb.pack(anchor=W, pady=6)
        TopMostToolTip(cb, "Globally enable or disable the symbol suggestion system.", bootstyle=INFO)
        self.enable_suggestions_cb = cb

        # Suggestion Count Setting
        lf_count = tb.Labelframe(content, text=" Suggestion Count ", padding=15)
        lf_count.pack(fill=X, pady=10)

        row_count = tb.Frame(lf_count)
        row_count.pack(fill=X, pady=5)

        tb.Label(row_count, text="Max Suggestions:").pack(side=LEFT)

        self.suggestion_count_var = tb.IntVar(value=getattr(self.parent, 'max_suggestions', 3))
        suggestion_spinbox = tb.Spinbox(
            row_count,
            from_=1,
            to=5,
            width=5,
            textvariable=self.suggestion_count_var,
            state="normal" if suggestions_enabled else "disabled"
        )
        suggestion_spinbox.pack(side=RIGHT)
        TopMostToolTip(suggestion_spinbox, "Set maximum number of suggestions to show (1-5)", bootstyle=INFO)
        self.suggestion_spinbox = suggestion_spinbox

    def setup_autosave_page(self, master):
        content = tb.Frame(master, padding=10)
        content.pack(fill=BOTH, expand=YES)

        lf = tb.Labelframe(content, text=" Autosave Configuration ", padding=15)
        lf.pack(fill=X, pady=10)

        row = tb.Frame(lf)
        row.pack(fill=X, pady=5)

        tb.Label(row, text="Auto-save Delay (sec):").pack(side=LEFT)

        self.save_delay = tb.Spinbox(row, from_=1, to=60, width=5)
        self.save_delay.set(self.parent.auto_save_delay // 1000)
        self.save_delay.pack(side=RIGHT)

        self.backup_var = tb.BooleanVar(value=self.parent.enable_backups)
        tb.Checkbutton(
            lf,
            text="Enable backup file creation on launch",
            variable=self.backup_var,
            bootstyle="success-square-toggle"
        ).pack(anchor=W, pady=10)

    def open_macro_manager(self):
        if self.parent.windows["macro"] is not None and self.parent.windows["macro"].win.winfo_exists():
            self.parent.windows["macro"].win.lift()
            return
        self.parent.windows["macro"] = MacroManagerWindow(self.parent)

    def refresh_color_list(self):
        for w in self.color_list_frame.winfo_children():
            w.destroy()

        for r, (sub, col) in enumerate(self.parent.subject_colors.items()):
            row = tb.Frame(self.color_list_frame)
            row.grid(row=r, column=0, sticky="ew", pady=4)
            row.columnconfigure(0, weight=1)

            tb.Label(row, text=sub, anchor=W).grid(row=0, column=0, sticky="w", padx=(4, 8))
            preview = tb.Label(row, width=3, background=col, relief=SOLID)
            preview.grid(row=0, column=1, padx=6)

            def pick_color_closure(subject=sub, p=preview):
                def _pick():
                    cd = ColorChooserDialog(self.win, initialcolor=self.parent.subject_colors.get(subject))
                    cd.show()
                    if cd.result:
                        self.parent.subject_colors[subject] = cd.result.hex
                        p.configure(background=cd.result.hex)

                return _pick

            tb.Button(row, text="Change", bootstyle="outline-secondary", command=pick_color_closure(), width=7).grid(
                row=0, column=2, padx=6)

            if sub in ["Physics", "Chemistry", "Maths"]:
                tb.Button(row, text="✕", bootstyle="secondary-link", state=DISABLED, width=3).grid(row=0, column=3,
                                                                                                   padx=4)
            else:
                tb.Button(row, text="✕", bootstyle="danger-link", command=lambda s=sub: self.delete_color_map(s),
                          width=3).grid(row=0, column=3, padx=4)

    def add_color_mapping(self):
        sub = self.new_sub_name.get().strip()
        if not sub or sub == self.color_placeholder:
            return
        self.parent.subject_colors[sub] = self.selected_color
        self.refresh_color_list()
        self.new_sub_name.delete(0, END)
        _restore_placeholder(self.new_sub_name, self.color_placeholder)
        self.selected_color = "#ffffff"
        self.color_preview.configure(background=self.selected_color)
        show_toast(f"Color set for {sub}!")

    def delete_color_map(self, subject_name):
        if subject_name in ["Physics", "Chemistry", "Maths"]:
            show_toast(f"Cannot delete core subject: {subject_name}", bootstyle="danger")
            return
        confirm = Messagebox.yesno(f"Remove color mapping for '{subject_name}'?", "Confirm Delete", parent=self.win)
        if confirm == "Yes" and subject_name in self.parent.subject_colors:
            del self.parent.subject_colors[subject_name]
            self.refresh_color_list()
            show_toast(f"Removed color for {subject_name}", bootstyle=WARNING)

    def start_move(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        x = self.win.winfo_x() - self.drag_data["x"] + event.x
        y = self.win.winfo_y() - self.drag_data["y"] + event.y
        self.win.geometry(f"+{x}+{y}")

    def apply_all(self):
        # Track previous always-on-top state
        previous_always_on_top = self.parent.always_on_top

        self.parent.root.style.theme_use(self.theme_cb.get())

        self.parent.auto_save_delay = int(self.save_delay.get()) * 1000
        self.parent.enable_backups = self.backup_var.get()
        self.parent.suggestion_strictness = self.suggestion_strictness_var.get()
        self.parent.enable_suggestions = self.suggest_var.get()
        self.parent.max_suggestions = self.suggestion_count_var.get()
        self.parent.always_on_top = self.topmost_var.get()

        self.parent.save_config()

        # Refresh symbol learner when suggestion settings change
        if hasattr(self.parent, 'symbol_learner'):
            self.parent.learn_symbols()
            # Force immediate update of active suggestions
            self.parent.clear_ghost_suggestions()

        show_toast("Settings Saved!")
        self.parent.apply_row_colors()
        self.parent.update_preview()
        self.parent.root.attributes("-topmost", self.parent.always_on_top)
        self.parent.update_child_windows_topmost()  # Update child windows

        # Only destroy settings window if always-on-top setting changed and is now True
        if not previous_always_on_top and self.parent.always_on_top:
            self.win.destroy()


def _clear_placeholder(widget, text):
    if widget.get() == text:
        widget.delete(0, END)
        widget.configure(foreground="")  # Reset to normal theme color


def _restore_placeholder(widget, text):
    """Restores placeholder text if the entry is left empty on focus out."""
    if not widget.get().strip():
        widget.delete(0, END)
        widget.insert(0, text)
        widget.configure(foreground="gray")
