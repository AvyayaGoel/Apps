from ttkbootstrap.constants import INFO
from ttkbootstrap.widgets.toast import ToastNotification

from constants import TOAST_BASE_OFFSET, TOAST_SPACING, TOAST_DURATION

MAX_TOASTS = 5          # maximum visible toasts
REMOVE_DELAY = 1300     # 1-second delay before removing the oldest toast


class ToastManager:
    def __init__(self):
        self.root = None
        self.active = []

    def bind_root(self, root):
        self.root = root

    def show(self, message, bootstyle=INFO, duration=TOAST_DURATION):

        if len(self.active) >= MAX_TOASTS:
            # Wait, remove oldest, then create new toast
            self.root.after(
                REMOVE_DELAY,
                lambda: self._remove_then_create(message, bootstyle, duration)
            )
        else:
            self._create_toast(message, bootstyle, duration)

    def _remove_then_create(self, message, bootstyle, duration):

        if self.active:
            self.remove_toast(self.active[0])

        self._create_toast(message, bootstyle, duration)

    def _create_toast(self, message, bootstyle, duration):

        toast = ToastNotification(
            title="Formula Sheet",
            message=message,
            duration=duration,
            bootstyle=bootstyle,
        )

        self.active.append(toast)

        toast.show_toast()

        self.root.after(10, lambda: self.position_toast(toast))

        self.root.after(duration, lambda: self.remove_toast(toast))

    def position_toast(self, toast):

        if not toast.toplevel:
            return

        toast.toplevel.update_idletasks()

        screen_w = toast.toplevel.winfo_screenwidth()
        screen_h = toast.toplevel.winfo_screenheight()

        toast_w = toast.toplevel.winfo_width() or 300
        toast_h = toast.toplevel.winfo_height() or 80

        index = self.active.index(toast)

        # stick fully to the right
        x = screen_w - toast_w

        # stack upward from bottom
        y = screen_h - toast_h - TOAST_BASE_OFFSET - (index * TOAST_SPACING)

        toast.toplevel.geometry(f"+{x}+{y}")

    def remove_toast(self, toast):

        if toast not in self.active:
            return

        if toast.toplevel:
            toast.hide_toast()

        self.active.remove(toast)

        self.reposition()

    def reposition(self):

        for toast in self.active:
            self.position_toast(toast)


toast_manager = ToastManager()


def manage_toasts(root):
    toast_manager.bind_root(root)


def show_toast(message, bootstyle=INFO, duration=TOAST_DURATION):
    toast_manager.show(message, bootstyle, duration)