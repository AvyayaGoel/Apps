import ttkbootstrap as tb
from ttkbootstrap.constants import INFO
from ttkbootstrap.widgets.toast import ToastNotification


COMBOBOX_SELECTED_EVENT = "<<ComboboxSelected>>"
KEY_RELEASE_EVENT = "<KeyRelease>"
FOCUS_IN_EVENT = "<FocusIn>"
FOCUS_OUT_EVENT = "<FocusOut>"
RETURN_EVENT = '<Return>'
BUTTON_1_EVENT = "<Button-1>"
BUTTON_PRESS_1_EVENT = "<ButtonPress-1>"
B1_MOTION_EVENT = "<B1-Motion>"


def show_toast(message, bootstyle=INFO, duration=3000):
    """Show a toast notification with the given message."""
    toast = ToastNotification(
        title="Formula Sheet",
        message=message,
        duration=duration,
        bootstyle=bootstyle
    )
    toast.show_toast()


class ToastManager:
    def __init__(self):
        self.root = None
        self.active = []
        self.base_offset = 60
        self.spacing = 80

    def bind_root(self, toast_root):
        self.root = toast_root

    def show(self, win):
        if not win or not win.winfo_exists():
            return

        # Calculate position to avoid overlap
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # Get all existing toplevel windows
        existing_windows = []
        for widget in self.root.winfo_children():
            if isinstance(widget, tb.Toplevel):
                existing_windows.append(widget)

        # Calculate position for new toast
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 100
        y = self.base_offset + len(self.active) * self.spacing

        # Adjust if toast would go off-screen
        if x + 200 > sw:
            x = sw - 210
        if y + 100 > sh:
            y = sh - 110

        win.geometry(f"+{x}+{y}")
        self.active.append(win)

        # Auto-remove after toast destroys itself
        self.root.after(10000, lambda: self._remove(win))

    def _remove(self, win):
        if win in self.active:
            self.active.remove(win)
            self._reposition()

    def _reposition(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        for i, win in enumerate(self.active):
            if win.winfo_exists():
                x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 100
                y = self.base_offset + i * self.spacing

                # Adjust if toast would go off-screen
                if x + 200 > sw:
                    x = sw - 210
                if y + 100 > sh:
                    y = sh - 110

                win.geometry(f"+{x}+{y}")


# Global toast manager instance
toast_manager = ToastManager()


def manage_toasts(root_window):
    """Initialize toast manager with root window."""
    toast_manager.bind_root(root_window)
