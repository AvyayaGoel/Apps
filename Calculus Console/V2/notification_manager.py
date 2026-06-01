"""
Notification Manager (PyQt6 version)
Modern notification system with slide animations, progress bars,
hover pause, queueing, and FULL logging instrumentation.
"""

from collections import deque

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QGraphicsDropShadowEffect
)


# ==========================================================
# Notification Widget
# ==========================================================
class NotificationWidget(QFrame):
    """Single notification popup."""

    STYLES = {
        "info": {"border": "#17a2b8", "icon": "ℹ️", "title": "#17a2b8"},
        "success": {"border": "#28a745", "icon": "✅", "title": "#28a745"},
        "warning": {"border": "#ffc107", "icon": "⚠️", "title": "#ffc107"},
        "danger": {"border": "#dc3545", "icon": "🚫", "title": "#dc3545"},
    }

    def __init__(self, title, message, bootstyle="info", duration=3000, manager=None):
        super().__init__(None)

        self._manager = manager
        self._title = title
        self._duration = duration
        self._remaining = duration
        self._bootstyle = bootstyle

        self._is_hovered = False
        self._fading = False
        self._active = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True
        )

        self._build_ui(title, message)
        self._setup_shadow()

    # ---------------- UI ---------------- #

    def _build_ui(self, title, message):
        style = self.STYLES.get(
            self._bootstyle,
            self.STYLES["info"]
        )

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #2b2b2b;
                border-left: 4px solid {style['border']};
                border-radius: 6px;
            }}

            QLabel {{
                color: white;
                background: transparent;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)

        icon = QLabel(style["icon"])
        layout.addWidget(icon)

        content = QVBoxLayout()

        title_lbl = QLabel(f"<b>{title}</b>")
        content.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setMaximumWidth(260)
        content.addWidget(msg_lbl)

        self._progress = QProgressBar()
        self._progress.setMaximum(self._duration)
        self._progress.setValue(self._duration)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(3)

        content.addWidget(self._progress)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self._close)

        layout.addLayout(content, stretch=1)
        layout.addWidget(close_btn)

        self.setFixedWidth(320)
        self.adjustSize()

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    # ---------------- lifecycle ---------------- #

    def update_progress(self, delta_ms):
        if not self._active:
            return

        if self._is_hovered:
            return

        if self._fading:
            return

        self._remaining -= delta_ms
        self._remaining = max(0, self._remaining)

        self._progress.setValue(self._remaining)

        if self._remaining <= 0:
            self._dismiss()

    def slide_in(self, target_x, target_y):
        self.move(target_x + 60, target_y)
        self.show()
        self.raise_()
        self.setWindowOpacity(0)

        self._fade_in_anim = QPropertyAnimation(
            self,
            b"windowOpacity"
        )
        self._fade_in_anim.setDuration(300)
        self._fade_in_anim.setStartValue(0)
        self._fade_in_anim.setEndValue(1)
        self._fade_in_anim.start()

        self._slide_anim = QPropertyAnimation(
            self,
            b"geometry"
        )
        self._slide_anim.setDuration(300)
        self._slide_anim.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )
        self._slide_anim.setStartValue(self.geometry())
        self._slide_anim.setEndValue(
            QRect(
                target_x,
                target_y,
                self.width(),
                self.height()
            )
        )
        self._slide_anim.start()

        # FIX: don't depend on animation finished signal
        QTimer.singleShot(
            350,
            self._activate_lifecycle
        )

    def _activate_lifecycle(self):
        if self._fading:
            return

        if self._active:
            return

        self._active = True

    def _close(self):
        self._dismiss()

    def _dismiss(self):
        if self._fading:
            return

        self._fading = True
        self._active = False

        self._fade_out_anim = QPropertyAnimation(
            self,
            b"windowOpacity"
        )
        self._fade_out_anim.setDuration(200)
        self._fade_out_anim.setStartValue(1)
        self._fade_out_anim.setEndValue(0)

        self._fade_out_anim.finished.connect(
            self._on_fade_done
        )

        self._fade_out_anim.start()

    def _on_fade_done(self):
        self.hide()

        if self._manager:
            self._manager._remove_notification(self)

        self.deleteLater()

    def enterEvent(self, event):
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        super().leaveEvent(event)


# ==========================================================
# Notification Manager
# ==========================================================
class NotificationManager:
    """Notification manager with full logging."""

    def __init__(self):
        self._notifications = []
        self._queue = deque()

        self._max_notifications = 5
        self._max_queue = 50

        self._spacing = 12
        self._base_offset = 60
        self._edge_margin = 20

        self._root = None

        self._update_timer = QTimer()
        self._update_timer.timeout.connect(
            self._update_notifications
        )
        self._update_timer.start(16)

    def bind_root(self, root):
        self._root = root

    # ---------------- public ---------------- #

    def show(self, message, bootstyle="info", duration=3000):

        if "\n" in message and not message.startswith("\n"):
            title, msg = message.split("\n", 1)
            title = title.strip()
            msg = msg.strip()
        else:
            title = "Formula Sheet"
            msg = message

        payload = (
            title,
            msg,
            bootstyle,
            duration
        )

        if len(self._notifications) >= self._max_notifications:
            if len(self._queue) < self._max_queue:
                self._queue.append(payload)

            return

        self._display_notification(*payload)

    # ---------------- internal ---------------- #

    def _display_notification(self, title, msg, bootstyle, duration):

        notification = NotificationWidget(
            title,
            msg,
            bootstyle,
            duration,
            self
        )

        self._notifications.append(notification)

        x, y = self._compute_position(
            len(self._notifications) - 1
        )

        notification.slide_in(x, y)

    def _update_notifications(self):

        for notification in self._notifications[:]:
            notification.update_progress(16)

    def _remove_notification(self, notification):

        if notification in self._notifications:
            self._notifications.remove(notification)

        self._reposition()

        if self._queue:
            title, msg, style, duration = self._queue.popleft()

            self._display_notification(
                title,
                msg,
                style,
                duration
            )

    def _compute_position(self, index):
        screen = QApplication.primaryScreen()

        if screen:
            geom = screen.availableGeometry()
        else:
            geom = QRect(0, 0, 1920, 1080)

        x = geom.right() - 340 - self._edge_margin
        y = geom.bottom() - self._base_offset

        for i in range(index + 1):
            if i < len(self._notifications):
                y -= self._notifications[i].height()

                if i < index:
                    y -= self._spacing

        return x, y

    def _reposition(self):
        for i, notification in enumerate(self._notifications):
            if notification._fading:
                continue

            x, y = self._compute_position(i)

            notification._reposition_anim = QPropertyAnimation(
                notification,
                b"geometry"
            )

            notification._reposition_anim.setDuration(250)
            notification._reposition_anim.setEasingCurve(
                QEasingCurve.Type.OutCubic
            )

            notification._reposition_anim.setStartValue(
                notification.geometry()
            )

            notification._reposition_anim.setEndValue(
                QRect(
                    x,
                    y,
                    notification.width(),
                    notification.height()
                )
            )

            notification._reposition_anim.start()


# ==========================================================
# Global instance
# ==========================================================
_manager_instance = None


def manage_notifications(root):
    global _manager_instance

    _manager_instance = NotificationManager()
    _manager_instance.bind_root(root)


def show_notification(message, bootstyle="info", duration=3000):
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = NotificationManager()

    _manager_instance.show(
        message,
        bootstyle,
        duration
    )
