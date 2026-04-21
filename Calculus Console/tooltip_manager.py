import tkinter as tk

from ttkbootstrap.widgets.tooltip import ToolTip


class TopMostToolTip(ToolTip):
    """Extended ToolTip that ensures it's always on top and properly cleans up."""

    def __init__(self, widget, text, bootstyle=None, wraplength=None, **kwargs):
        # Set alpha and topmost in kwargs
        kwargs["alpha"] = 0.95
        self._is_topmost = True

        # Initialize parent ToolTip
        super().__init__(widget, text=text, bootstyle=bootstyle, wraplength=wraplength, **kwargs)

        # Override the show_tip method to ensure topmost
        self._original_show_tip = self.show_tip
        self.show_tip = self._show_tip_topmost

        # Bind window focus events to clean up
        self.widget.winfo_toplevel().bind("<FocusOut>", self._cleanup_on_focus_loss)
        self.widget.winfo_toplevel().bind("<Unmap>", self._cleanup_on_unmap)

    def _show_tip_topmost(self, *_args):
        """Override show_tip to ensure proper layering."""
        self._original_show_tip()
        if self.toplevel:
            # Set topmost to ensure it appears above other windows
            self.toplevel.attributes("-topmost", True)
            # Ensure proper positioning after setting topmost
            x = self.widget.winfo_pointerx() + 25
            y = self.widget.winfo_pointery() + 10
            self.toplevel.geometry(f"+{x}+{y}")

    def _cleanup_on_focus_loss(self, _event=None):
        """Cleanup tooltip when parent window loses focus."""
        self.hide_tip()

    def _cleanup_on_unmap(self, _event=None):
        """Cleanup tooltip when parent window is minimized/hidden."""
        self.hide_tip()

    def hide_tip(self, *_args):
        """Override hide_tip to ensure proper cleanup."""
        if self.toplevel:
            # Just destroy directly like the original - don't try to remove topmost
            try:
                self.toplevel.destroy()
                self.toplevel = None
            except (tk.TclError, AttributeError):
                # Window might already be destroyed, just clear reference
                self.toplevel = None
