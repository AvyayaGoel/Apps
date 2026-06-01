import logging
import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, END, INFO, LEFT, RIGHT, SECONDARY, SUCCESS, WARNING, X, YES, W
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from constants import (
    KEY_RELEASE_EVENT, FOCUS_IN_EVENT,
    FOCUS_OUT_EVENT, BUTTON_PRESS_1_EVENT,
    B1_MOTION_EVENT
)
from toast_manager import show_toast


class MacroManagerWindow:
    def __init__(self, parent):
        self.parent = parent
        self.win = tb.Toplevel(parent.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry("400x550")

        # Center relative to Settings or Main Window
        px = parent.root.winfo_x() + (parent.root.winfo_width() // 2) - 200
        py = parent.root.winfo_y() + (parent.root.winfo_height() // 2) - 275
        self.win.geometry(f"+{px}+{py}")

        self.drag_data = {"x": 0, "y": 0}
        self.last_cursor_pos = 0

        self.editing_index = None

        # Main Container
        self.container = tb.Frame(self.win, bootstyle=SECONDARY, padding=2)
        self.container.pack(fill=BOTH, expand=YES)

        # Custom Title Bar
        self.title_bar = tb.Frame(self.container, bootstyle=SECONDARY)
        self.title_bar.pack(fill=X)
        self.title_bar.bind(BUTTON_PRESS_1_EVENT, self.start_move)
        self.title_bar.bind(B1_MOTION_EVENT, self.do_move)

        title_lbl = tb.Label(
            self.title_bar,
            text=" ⌨️ MANAGE KEYPAD BUTTONS",
            font=("Arial", 9, "bold"),
            bootstyle="inverse-secondary"
        )
        title_lbl.pack(side=LEFT, padx=10)

        # 🔥 bind to label too
        title_lbl.bind(BUTTON_PRESS_1_EVENT, self.start_move)
        title_lbl.bind(B1_MOTION_EVENT, self.do_move)

        tb.Button(
            self.title_bar,
            text="✕",
            width=3,
            bootstyle="danger",
            command=self.on_close
        ).pack(side=RIGHT)

        # Content Area
        content = tb.Frame(self.container, padding=20)
        content.pack(fill=BOTH, expand=YES)

        tb.Label(content, text="Create New Button", font=("Arial", 11, "bold")).pack(anchor=W)

        input_f = tb.Frame(content)
        input_f.pack(fill=X, pady=10)

        self.new_lab = tb.Entry(input_f, width=12)
        self.lab_placeholder = "Label (e.g. π)"
        _restore_placeholder(self.new_lab, self.lab_placeholder)
        self.new_lab.pack(side=LEFT, padx=2)

        self.new_con = tb.Entry(input_f)
        _restore_placeholder(self.new_con, "Content")
        self.new_con.pack(side=LEFT, fill=X, expand=YES, padx=2)

        # Placeholder bindings
        self.new_lab.bind(FOCUS_IN_EVENT, lambda e: _clear_placeholder(self.new_lab, self.lab_placeholder))
        self.new_con.bind(FOCUS_IN_EVENT, lambda e: _clear_placeholder(self.new_con, "Content"))
        self.new_lab.bind(FOCUS_OUT_EVENT, lambda e: _restore_placeholder(self.new_lab, self.lab_placeholder))
        self.new_con.bind(FOCUS_OUT_EVENT, lambda e: _restore_placeholder(self.new_con, "Content"))

        self.add_btn = tb.Button(
            content,
            text="+ Add to Keypad",
            bootstyle=INFO,
            command=self.add_macro_logic
        )
        self.add_btn.pack(fill=X, pady=10)

        tb.Separator(content).pack(pady=10)

        self.manage_lbl = tb.Label(content, text="Existing Buttons", font=("Arial", 10, "bold"))
        self.manage_lbl.pack(anchor=W)

        self.macro_list_frame = ScrolledFrame(content, height=250, autohide=True)
        self.macro_list_frame.pack(fill=BOTH, expand=YES, pady=5)

        self.refresh_macro_list()

        # Cursor capture for 'warp' logic
        self.new_con.bind(KEY_RELEASE_EVENT, lambda e: self.capture_cursor())
        self.new_con.bind("<ButtonRelease-1>", lambda e: self.capture_cursor())

    def capture_cursor(self):
        self.last_cursor_pos = self.new_con.index(tk.INSERT)

    def refresh_macro_list(self):
        for widget in self.macro_list_frame.winfo_children():
            widget.destroy()

        for i, macro in enumerate(self.parent.user_macros):
            row = tb.Frame(self.macro_list_frame)
            row.pack(fill=X, pady=2)

            tb.Label(row, text=f"• {macro['label']}", font=("Arial", 9)) \
                .pack(side=LEFT)

            tb.Button(
                row,
                text="Edit",
                bootstyle="secondary-link",
                command=lambda idx=i: self.edit_macro(idx)
            ).pack(side=RIGHT, padx=4)

            tb.Button(
                row,
                text="Delete",
                bootstyle="danger-link",
                command=lambda idx=i: self.delete_macro(idx)
            ).pack(side=RIGHT)

    def edit_macro(self, index):
        macro = self.parent.user_macros[index]

        # Load data into inputs
        _clear_placeholder(self.new_lab, self.lab_placeholder)
        self.new_lab.insert(0, macro["label"])

        _clear_placeholder(self.new_con, "Content")
        self.new_con.insert(0, macro["content"])

        # Restore cursor position for warp logic
        self.last_cursor_pos = len(macro["content"]) - macro.get("warp", 0)

        self.editing_index = index

        # Switch button to UPDATE mode
        self.add_btn.configure(text="✔ Update Macro", bootstyle=SUCCESS)

    def on_close(self):
        self.parent.windows["macro"] = None
        self.win.destroy()

    def add_macro_logic(self):
        lab = self.new_lab.get().strip()
        con = self.new_con.get().strip()

        if not lab or not con or lab == self.lab_placeholder or con == "Content":
            return

        offset = len(con) - self.last_cursor_pos

        if self.editing_index is not None:
            # 🔄 UPDATE EXISTING
            self.parent.user_macros[self.editing_index] = {
                "label": lab,
                "content": con,
                "warp": offset
            }

            show_toast(f"Macro '{lab}' updated", bootstyle=SUCCESS)

            self.editing_index = None
            self.add_btn.configure(text="+ Add to Keypad", bootstyle=INFO)

        else:
            # ➕ ADD NEW
            self.parent.user_macros.append({
                "label": lab,
                "content": con,
                "warp": offset
            })

            show_toast(f"Macro '{lab}' added", bootstyle=SUCCESS)

        # Reset fields
        self.new_lab.delete(0, END)
        _restore_placeholder(self.new_lab, self.lab_placeholder)

        self.new_con.delete(0, END)
        _restore_placeholder(self.new_con, "Content")

        self.last_cursor_pos = 0

        self.refresh_macro_list()
        self.save_and_sync()

    def delete_macro(self, index):
        label = self.parent.user_macros[index]["label"]

        confirm = Messagebox.yesno(
            f"Delete macro '{label}'?",
            "Confirm Delete",
            parent=self.win
        )

        if confirm != "Yes":
            return

        self.parent.user_macros.pop(index)
        self.refresh_macro_list()
        self.save_and_sync()

        show_toast(f"Macro '{label}' deleted", bootstyle=WARNING)

    def save_and_sync(self):
        """Forces the main app to save the new macro list to file."""
        # This calls the parent's logic to save config.json
        if hasattr(self.parent, 'save_config'):
            self.parent.save_config()
        # Refresh the keypad if it's open (preserves position)
        if self.parent.keypad_manager.is_keypad_open():
            try:
                # Just update macros - position will be preserved
                self.parent.keypad_manager.update_macros(self.parent.user_macros)
            except Exception as e:
                logging.error(f"Error syncing keypad: {e}")

    def start_move(self, event):
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def do_move(self, event):
        dx = event.x_root - self.drag_data["x"]
        dy = event.y_root - self.drag_data["y"]

        x = self.win.winfo_x() + dx
        y = self.win.winfo_y() + dy

        self.win.geometry(f"+{x}+{y}")

        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root


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
