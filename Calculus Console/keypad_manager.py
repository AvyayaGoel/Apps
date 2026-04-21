"""
Keypad Manager - Handles mathematical symbol keypad functionality.
Extracted from Sheet class for better separation of concerns.
"""

import logging
import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, X, YES, SECONDARY, LEFT

from constants import BUTTON_1_EVENT, MAIN_SYMBOL_SETS, SUPER_SCRIPT_SYMBOLS, SUB_SCRIPT_SYMBOLS, SUB_SCRIPT, SUPER_SCRIPT


class KeypadManager:
    """Manages the mathematical symbol keypad window and functionality."""

    def __init__(self, parent_root, insert_text_callback, user_macros=None,
                 drag_start_callback=None, drag_move_callback=None):
        """
        Initialize the KeypadManager.
        
        Args:
            parent_root: The root window of the parent application
            insert_text_callback: Function to call when inserting text
            user_macros: List of user-defined macro buttons
            drag_start_callback: Function to call when drag starts
            drag_move_callback: Function to call when dragging
        """
        self.parent_root = parent_root
        self.insert_text_callback = insert_text_callback
        self.user_macros = user_macros or []
        self.drag_start_callback = drag_start_callback
        self.drag_move_callback = drag_move_callback
        self.window = None
        self.is_open = False
        self.current_layout = "main"  # Track current layout: "main", "super", or "sub"
        self.last_position = None  # Store last keypad position

    def toggle_keypad(self, keypad_button_widget=None, reflection_mode_active=False):
        """
        Toggle the keypad window open/closed.
        
        Args:
            keypad_button_widget: The button that triggered this toggle
            reflection_mode_active: Whether reflection mode is active (blocks keypad)
            
        Returns:
            bool: True if keypad was opened, False if closed/blocked
        """
        if reflection_mode_active:
            return False

        if self.is_open:
            self.close_keypad()
            return False

        return self.open_keypad(keypad_button_widget)

    def open_keypad(self, keypad_button_widget=None):
        """
        Open the keypad window.
        
        Args:
            keypad_button_widget: The button that triggered opening
            
        Returns:
            bool: True if successfully opened
        """
        try:
            self.window = tb.Toplevel(self.parent_root)
            self.is_open = True

            # Configure window properties
            self.window.overrideredirect(True)
            self.window.attributes("-topmost", True)
            self.window.wm_attributes("-toolwindow", True)

            # CRITICAL: Prevent keypad window from ever taking focus
            self.window.focus_set = lambda: None  # Disable focus entirely
            self.window.bind("<FocusIn>", self._prevent_focus)
            self.window.bind(BUTTON_1_EVENT, self._prevent_focus)

            # Use last saved position if available, otherwise position relative to button
            if self.last_position:
                self.window.geometry(f"+{self.last_position[0]}+{self.last_position[1]}")
            elif keypad_button_widget:
                x = keypad_button_widget.winfo_rootx()
                y = keypad_button_widget.winfo_rooty() - 530
                self.window.geometry(f"+{x}+{y}")

            self._create_keypad_content()
            return True

        except Exception as e:
            logging.error(f"Error opening keypad: {e}", exc_info=True)
            return False

    def close_keypad(self):
        """Close the keypad window and save position."""
        if self.window and self.is_open:
            try:
                # Save current position before closing
                self.last_position = (self.window.winfo_x(), self.window.winfo_y())
                self.window.destroy()
            except Exception as e:
                logging.error(f"Error closing keypad: {e}", exc_info=True)
            finally:
                self.window = None
                self.is_open = False

    def _create_keypad_content(self):
        """Create the content inside the keypad window."""
        # Drag handle
        self._create_drag_handle()

        # Main container
        main_frame = tb.Frame(self.window, padding=5, bootstyle="dark")
        main_frame.pack(fill=BOTH, expand=YES)

        # Layout-specific content
        if self.current_layout == "main":
            self._create_main_layout(main_frame)
        elif self.current_layout == "super":
            self._create_super_script_layout(main_frame)
        elif self.current_layout == "sub":
            self._create_sub_script_layout(main_frame)

        # User macro buttons (shown in all layouts)
        if self.user_macros:
            self._create_macro_buttons(main_frame)

    def _create_drag_handle(self):
        """Create the drag handle for moving the keypad."""
        drag_handle = tb.Frame(self.window, bootstyle=SECONDARY, height=20)
        drag_handle.pack(fill=X)

        grip_label = tb.Label(drag_handle, text=":::: Grip to Move ::::",
                              bootstyle="inverse-secondary", font=("Arial", 8))
        grip_label.pack(pady=2)

        # Bind drag events if callbacks are provided
        if self.drag_start_callback and self.drag_move_callback:
            drag_handle.bind(BUTTON_1_EVENT, self.drag_start_callback)
            drag_handle.bind("<B1-Motion>", self.drag_move_callback)
            grip_label.bind(BUTTON_1_EVENT, self.drag_start_callback)
            grip_label.bind("<B1-Motion>", self.drag_move_callback)

    def _create_main_layout(self, parent_frame):
        """Create the main mathematical symbol layout."""
        # Symbol buttons
        self._create_symbol_buttons(parent_frame, MAIN_SYMBOL_SETS)
        
        # Layout switching buttons
        layout_frame = tb.Frame(parent_frame)
        layout_frame.pack(fill=X, pady=5)
        
        tb.Button(layout_frame, text=SUPER_SCRIPT, width=12, bootstyle=SECONDARY,
                  command=lambda: self._switch_layout("super"), takefocus=False).pack(side=LEFT, padx=1, fill=X, expand=YES)
        tb.Button(layout_frame, text=SUB_SCRIPT, width=12, bootstyle=SECONDARY,
                  command=lambda: self._switch_layout("sub"), takefocus=False).pack(side=LEFT, padx=1, fill=X, expand=YES)

    def _create_super_script_layout(self, parent_frame):
        """Create the super script layout."""
        # Back button
        back_frame = tb.Frame(parent_frame)
        back_frame.pack(fill=X, pady=2)
        tb.Button(back_frame, text="← Back", width=10, bootstyle=SECONDARY,
                  command=lambda: self._switch_layout("main"), takefocus=False).pack(side=LEFT)
        tb.Button(back_frame, text=SUB_SCRIPT, width=10, bootstyle=SECONDARY,
                  command=lambda: self._switch_layout("sub"), takefocus=False).pack(side=LEFT)
        tb.Label(back_frame, text=SUPER_SCRIPT).pack(side=LEFT, padx=10, fill=X, expand=YES)
        
        # Super script symbols
        self._create_symbol_buttons(parent_frame, SUPER_SCRIPT_SYMBOLS)

    def _create_sub_script_layout(self, parent_frame):
        """Create the sub script layout."""
        # Back button
        back_frame = tb.Frame(parent_frame)
        back_frame.pack(fill=X, pady=2)
        tb.Button(back_frame, text="← Back", width=10, bootstyle=SECONDARY,
                  command=lambda: self._switch_layout("main"), takefocus=False).pack(side=LEFT)
        tb.Button(back_frame, text=SUPER_SCRIPT, width=10, bootstyle=SECONDARY,
                  command=lambda: self._switch_layout("super"), takefocus=False).pack(side=LEFT)
        tb.Label(back_frame, text=SUB_SCRIPT).pack(side=LEFT, padx=10, fill=X, expand=YES)
        
        # Sub script symbols
        self._create_symbol_buttons(parent_frame, SUB_SCRIPT_SYMBOLS)

    def _create_symbol_buttons(self, parent_frame, symbol_sets):
        """Create symbol buttons from given symbol sets."""
        for row_idx, row_symbols in enumerate(symbol_sets):
            row_frame = tb.Frame(parent_frame)
            row_frame.pack(fill=X, pady=1)

            for symbol in row_symbols:
                btn = tb.Button(row_frame, text=symbol, width=3, bootstyle=SECONDARY,
                                command=lambda s=symbol: self._insert_symbol(s),
                                takefocus=False)
                btn.pack(side=LEFT, padx=1)

    def _switch_layout(self, new_layout):
        """Switch between different keypad layouts."""
        self.current_layout = new_layout
        
        # Store current position
        if self.window:
            self.last_position = (self.window.winfo_x(), self.window.winfo_y())
            
            # Clear existing content
            for widget in self.window.winfo_children():
                widget.destroy()
            
            # Recreate content with new layout
            self._create_keypad_content()
            
            # Force window to update and recalculate size
            self.window.update_idletasks()
            
            # Get the required size for the new content
            required_width = self.window.winfo_reqwidth()
            required_height = self.window.winfo_reqheight()
            
            # Restore position with proper size
            if self.last_position:
                self.window.geometry(f"{required_width}x{required_height}+{self.last_position[0]}+{self.last_position[1]}")
            else:
                self.window.geometry(f"{required_width}x{required_height}")

    def _create_macro_buttons(self, parent_frame):
        """Create user-defined macro buttons."""
        tb.Separator(parent_frame, bootstyle=SECONDARY).pack(fill=X, pady=10)

        current_row = tb.Frame(parent_frame, bootstyle="dark")
        current_row.pack(fill=X, pady=2)

        for i, macro in enumerate(self.user_macros):
            # Wrap to new row every 5 buttons
            if i > 0 and i % 5 == 0:
                current_row = tb.Frame(parent_frame, bootstyle="dark")
                current_row.pack(fill=X, pady=2)

            warp_value = macro.get('warp', 0)
            tb.Button(current_row, text=macro['label'], bootstyle="info-outline",
                      command=lambda c=macro['content'], w=warp_value: self._insert_symbol(c, w),
                      takefocus=False).pack(side=LEFT, padx=2, expand=YES, fill=X)

    def _insert_symbol(self, symbol_text, warp_value=0):
        """
        Insert a symbol into the focused widget without stealing focus.
        
        Args:
            symbol_text: The symbol text to insert
            warp_value: Warp value for cursor positioning
        """
        try:
            if self.insert_text_callback:
                # Store current focus before insertion
                current_focus = None
                if hasattr(self, 'parent_root') and hasattr(self.parent_root, 'focus_get'):
                    current_focus = self.parent_root.focus_get()

                # Insert the symbol
                self.insert_text_callback(symbol_text, warp_value)

                # Restore focus to the original widget
                if current_focus:
                    # Small delay to ensure insertion completes
                    self.parent_root.after(10, lambda: current_focus.focus_set())

        except Exception as e:
            logging.error(f"Error inserting symbol '{symbol_text}': {e}", exc_info=True)

    def update_macros(self, new_macros):
        """
        Update the user macros and refresh the keypad if open.
        
        Args:
            new_macros: New list of user macro definitions
        """
        self.user_macros = new_macros or []

        # If keypad is open, preserve position and refresh content
        if self.is_open and self.window:
            # Store current position
            current_geometry = self.window.geometry()
            current_x = self.window.winfo_x()
            current_y = self.window.winfo_y()

            # Clear existing content
            for widget in self.window.winfo_children():
                widget.destroy()

            # Recreate content with new macros (maintains current layout)
            self._create_keypad_content()

            # Restore position
            self.window.geometry(current_geometry)

            # Ensure position is maintained (fallback)
            if self.window.winfo_x() != current_x or self.window.winfo_y() != current_y:
                self.window.geometry(f"+{current_x}+{current_y}")

    def is_keypad_open(self):
        """Check if the keypad window is currently open."""
        return self.is_open and self.window and self.window.winfo_exists()

    def bring_to_front(self):
        """Bring the keypad window to the front."""
        if self.is_keypad_open():
            try:
                self.window.lift()
                self.window.attributes("-topmost", True)
            except Exception as e:
                logging.error(f"Error bringing keypad to front: {e}", exc_info=True)

    def _prevent_focus(self, _event):
        """
        Prevent the keypad window from taking focus.
        This ensures the original text entry field retains focus.
        """
        # Immediately return focus to the last focused widget (if available)
        if hasattr(self, 'parent_root') and hasattr(self.parent_root, 'focus_get'):
            try:
                # Try to get the currently focused widget and return focus to it
                focused = self.parent_root.focus_get()
                if focused:
                    focused.focus_set()
            except (tk.TclError, AttributeError, RuntimeError):
                pass  # Silently fail if we can't return focus

        # Prevent the keypad window itself from taking focus
        return "break"  # Prevent the focus event from processing
