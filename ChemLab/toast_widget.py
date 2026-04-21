"""Toast notification widget for ChemLab - shows temporary popup messages."""
import os

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QFont, QPixmap
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QVBoxLayout, QLabel,
                             QGraphicsOpacityEffect, QStyleOption, QStyle,
                             QApplication)

from constants import ICON_PATH


class ToastWidget(QFrame):
    """
    A toast notification widget that appears temporarily at the bottom right of the screen.
    Supports success, error, info, and warning message types.
    Styled like ttkbootstrap with app logo on the left.
    """

    # Duration constants (in milliseconds)
    SHORT_DURATION = 3000  # 3 seconds for simple actions
    MEDIUM_DURATION = 4000  # 4 seconds for standard notifications
    LONG_DURATION = 6000  # 6 seconds for errors or important messages

    # Fixed size for the toast (wide rectangular)
    TOAST_WIDTH = 450
    TOAST_HEIGHT = 80
    LOGO_SIZE = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Set fixed size for rectangular toast
        self.setFixedSize(self.TOAST_WIDTH, self.TOAST_HEIGHT)

        # Main horizontal layout (icon left, text right)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 20, 10)
        self.main_layout.setSpacing(15)

        # App logo on the left
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(self.LOGO_SIZE, self.LOGO_SIZE)
        self.logo_label.setScaledContents(True)
        self._load_app_logo()
        self.main_layout.addWidget(self.logo_label)

        # Text container (vertical layout for message and optional subtext)
        self.text_container = QVBoxLayout()
        self.text_container.setSpacing(5)
        self.text_container.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Message label
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.text_container.addWidget(self.label)

        self.main_layout.addLayout(self.text_container, 1)  # Stretch factor 1

        # Opacity effect for fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        # Animation
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Timer for auto-hide
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self._start_hide_animation)

        # Style presets
        self.styles = {
            'success': {
                'bg': '#0dcaf0',  # Cyan/blue for success
                'text': '#000000'
            },
            'error': {
                'bg': '#dc3545',  # Red for errors
                'text': '#FFFFFF'
            },
            'warning': {
                'bg': '#ffc107',  # Yellow for warnings
                'text': '#000000'
            },
            'info': {
                'bg': '#198754',  # Green for info
                'text': '#FFFFFF'
            }
        }

        self.current_message = ""

    def _load_app_logo(self):
        """Load the ChemLab app logo."""
        if os.path.exists(ICON_PATH):
            pixmap = QPixmap(ICON_PATH)
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap)
                return

        # If logo not found, show a placeholder
        self.logo_label.setText("🔬")
        self.logo_label.setStyleSheet("font-size: 32px; background: transparent;")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        """Custom paint event to ensure background is rendered with WA_TranslucentBackground."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        super().paintEvent(event)

    def _apply_style(self, message_type='info'):
        """Apply the style for the given message type."""
        style = self.styles.get(message_type, self.styles['info'])

        self.setStyleSheet(f"""
            ToastWidget {{
                background-color: {style['bg']};
                border: none;
                border-radius: 0px;
            }}
            QLabel {{
                color: {style['text']};
                background: transparent;
                font-weight: bold;
            }}
        """)

        # Set text color for the label
        self.label.setStyleSheet(f"color: {style['text']}; background: transparent;")

    def show_message(self, message, message_type='info'):
        """
        Show a toast message.

        Args:
            message: The text to display
            message_type: 'success', 'error', 'warning', or 'info'
        """
        if not self.parent():
            return

        self.current_message = message
        self.label.setText(message)
        self._apply_style(message_type)

        # Show after a short delay to ensure styling is applied
        QTimer.singleShot(0, self._finalize_show)

    def _finalize_show(self):
        """Finalize showing the toast after layout is calculated."""
        # Position at bottom right of screen
        self._position_widget()

        # Show and animate in
        self.show()
        self._start_show_animation(self._get_default_duration_for_current())

    def _get_default_duration_for_current(self):
        """Get duration based on current message type."""
        # Check current style to determine type
        style_sheet = self.styleSheet()
        if '#0dcaf0' in style_sheet:  # success (cyan)
            return self.MEDIUM_DURATION
        elif '#dc3545' in style_sheet:  # error (red)
            return self.LONG_DURATION
        elif '#ffc107' in style_sheet:  # warning (yellow)
            return self.SHORT_DURATION
        else:
            return self.SHORT_DURATION

    def _get_default_duration(self, message_type):
        """Get default duration based on message type."""
        if message_type == 'error':
            return self.LONG_DURATION
        elif message_type == 'success':
            return self.MEDIUM_DURATION
        else:
            return self.SHORT_DURATION

    def _position_widget(self):
        """Position the toast in the bottom right corner of the screen."""

        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geo = screen.availableGeometry()

        # Position at bottom right with 30px margin
        x = screen_geo.x() + screen_geo.width() - self.width()
        y = screen_geo.y() + screen_geo.height() - self.height()
        self.move(x, y)

    def _start_show_animation(self, duration):
        """Start the fade-in animation and set the hide timer."""
        # Reset and stop any existing animation
        self.fade_animation.stop()
        self.hide_timer.stop()

        # Disconnect any existing finished connections to prevent signal accumulation
        try:
            self.fade_animation.finished.disconnect()
        except TypeError:
            pass

        # Fade in
        self.fade_animation.setDuration(150)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

        # Start timer to hide after duration
        self.hide_timer.start(duration)

    def mousePressEvent(self, event):
        """Handle mouse click - dismiss the toast."""
        self._start_hide_animation()

    def _start_hide_animation(self):
        """Start the fade-out animation."""
        self.hide_timer.stop()

        # Disconnect any existing finished connections to prevent signal accumulation
        try:
            self.fade_animation.finished.disconnect()
        except TypeError:
            pass

        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self.hide)
        self.fade_animation.start()

    def resizeEvent(self, event):
        """Reposition when resized."""
        super().resizeEvent(event)
        self._position_widget()


class ToastManager:
    """
    Manager class to handle toast notifications from the main window.
    Provides convenient methods for showing different types of messages.
    """

    def __init__(self, parent):
        self.parent = parent
        self.current_toast = None

    def _show(self, message, message_type):
        """Internal method to show or update a toast."""
        # If there's an existing toast, update it
        if self.current_toast and self.current_toast.isVisible():
            self.current_toast.show_message(message, message_type)
        else:
            # Create new toast
            self.current_toast = ToastWidget(self.parent)
            self.current_toast.show_message(message, message_type)

    def success(self, message):
        """Show a success toast."""
        self._show(message, 'success')

    def error(self, message):
        """Show an error toast."""
        self._show(message, 'error')

    def warning(self, message):
        """Show a warning toast."""
        self._show(message, 'warning')

    def info(self, message):
        """Show an info toast."""
        self._show(message, 'info')
