#!/usr/bin/env python3
"""
Calculus Console v2
Main Application (PyQt6)

Upgrades from ttkbootstrap version:
• Menubar-driven dialog layout (File / Formula / View / Tools / Help)
• Real-time search & hierarchical filtering (Subject → Topic → Sub-Topic)
• Sortable formula table with subject-color coding
• Integrated reflection overlay for the 150-formula entity sequence
• Global toast / notification system
• Non-modal keypad that injects into any focused QLineEdit across all windows
• Full CRUD via FormulaDialog with ghost suggestions & variable chips
• One-click duplicate, inline details dialog, and backup rotation
"""

import logging
import os
import shutil
import sys
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import (Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
, QObject, QEvent)
from PyQt6.QtGui import (
    QAction, QKeySequence, QColor, QPalette, QIntValidator
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QStatusBar, QMessageBox, QFrame,
    QGraphicsDropShadowEffect, QDialog, QTextEdit, QGraphicsOpacityEffect
)

from award_panel import AwardPanel
# ---------------------------------------------------------------------------
# Local imports – all pre-converted PyQt6 modules
# ---------------------------------------------------------------------------
from constants import (
    DB_NAME, CONFIG_NAME, TIP_NAME, BACKUP_NAMES,
    DEFAULT_SUBJECT_COLORS,
    SYSTEM_LOCKED_MSG, SYSTEM_LOCKED_TRY_AGAIN_MSG,
    SYSTEM_LOCKED_NOTHING_SAVES_MSG, SYSTEM_LOCKED_NICE_TRY_MSG,
    NO_FORMULA_SELECTED, ALL_SUBJECTS, ALL_TOPICS, ALL_SUB_TOPICS
)
from database_manager import DatabaseManager
from export_dialog import ExportDialog
from formula_dialog import FormulaDialog
from formula_utils import FormulaUtils
from keypad_manager import KeypadManager
from macro_manager_window import MacroManagerWindow
from milestone_manager import MilestoneManager
from notification_manager import manage_notifications, show_notification
from settings_window import SettingsWindow
from stats_dashboard import StatsDashboard
from symbol_learner import SymbolLearner

logging.basicConfig(
    filename="calculus_console_v2.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =============================================================================
# Global Keypad Event Filter (Ctrl+K works from any dialog/window)
# =============================================================================

class KeypadEventFilter(QObject):
    """Application-wide event filter that catches Ctrl+K to toggle keypad."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_K and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.main_window.toggle_keypad()
                return True
        return super().eventFilter(obj, event)


# =============================================================================
# Formula Details Dialog
# =============================================================================

class FormulaDetailsDialog(QDialog):
    def __init__(self, parent, data: dict, subject_colors: dict):
        super().__init__(parent)

        self.data = data
        self.subject_colors = subject_colors

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(700, 500)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        container = QFrame()
        container.setObjectName("mainContainer")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        info = self.data["main_info"]
        variables = self.data.get("variables", [])

        # HEADER
        title = QLabel("FORMULA ANALYSIS")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Formula Display
        formula_box = QFrame()
        formula_box.setObjectName("formulaBox")

        formula_layout = QVBoxLayout(formula_box)

        formula_text = QLabel(info[1])
        formula_text.setWordWrap(True)
        formula_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formula_text.setObjectName("formulaText")
        formula_layout.addWidget(formula_text)

        layout.addWidget(formula_box)

        # Metadata Chips
        meta_row = QHBoxLayout()

        for label, value in [
            ("SUBJECT", info[2]),
            ("TOPIC", info[3]),
            ("SUB-TOPIC", info[4])
        ]:
            chip = QLabel(f"{label}\n{value}")
            chip.setObjectName("metaChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            meta_row.addWidget(chip)

        layout.addLayout(meta_row)

        # Variables section
        var_title = QLabel("VARIABLE ENTITIES")
        var_title.setObjectName("sectionTitle")
        layout.addWidget(var_title)

        if variables:
            for var in variables:
                card = QFrame()
                card.setObjectName("varCard")

                card_layout = QHBoxLayout(card)

                symbol = QLabel(var["symbol"])
                symbol.setObjectName("varSymbol")

                name = QLabel(var["name"])
                unit = QLabel(var.get("unit", "N/A"))

                card_layout.addWidget(symbol)
                card_layout.addWidget(name)
                card_layout.addStretch()
                card_layout.addWidget(unit)

                layout.addWidget(card)

        else:
            empty = QLabel("NO VARIABLES DETECTED")
            empty.setObjectName("emptyLabel")
            layout.addWidget(empty)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton("COPY")
        copy_btn.clicked.connect(self._copy)

        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        outer.addWidget(container)

    def _copy(self):
        QApplication.clipboard().setText(
            self.data["main_info"][1]
        )
        show_notification(
            "Formula extracted from system memory",
            "success"
        )

    def _apply_styles(self):
        self.setStyleSheet("""
            #mainContainer {
                background-color: rgba(10,10,10,230);
                border: 2px solid #00ffcc;
                border-radius: 20px;
            }

            #titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #00ffcc;
                letter-spacing: 2px;
            }

            #formulaBox {
                background-color: #111;
                border: 1px solid #00ffcc;
                border-radius: 15px;
            }

            #formulaText {
                font-size: 26px;
                color: white;
                font-weight: bold;
            }

            #metaChip {
                background-color: #191919;
                border: 1px solid #ff0077;
                border-radius: 12px;
                padding: 15px;
                color: white;
            }

            #sectionTitle {
                font-size: 18px;
                color: #ff0077;
                font-weight: bold;
            }

            #varCard {
                background-color: #151515;
                border-left: 4px solid #00ffcc;
                border-radius: 10px;
                padding: 10px;
            }

            #varSymbol {
                font-size: 20px;
                color: #00ffcc;
                font-weight: bold;
            }

            QPushButton {
                background-color: #111;
                border: 1px solid #00ffcc;
                padding: 10px 20px;
                border-radius: 10px;
            }

            QPushButton:hover {
                background-color: #00ffcc;
                color: black;
            }
        """)


# =============================================================================
# Reflection Overlay (150-formula entity sequence)
# =============================================================================

class ReflectionOverlay(QFrame):
    """
    Cinematic reflection overlay with user-paced Continue button.

    Features:
    - Banner fades in/out cleanly between messages
    - Prompt fades in/out with proper lifecycle
    - Option buttons appear with staggered fade-in
    - Continue button pinned at BOTTOM-RIGHT of overlay
    - "I have no doubts ->" button for instant exit
    - Click within 200px radius of banner acts as Continue
    - BOOT/REBOOT sequences fade out each message before showing the next
    - No conflicting animations; safe against widget deletion
    """

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)

        self.main_window = main_window

        self.setObjectName("reflectionOverlay")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._active_animations: dict = {}
        self._pending_timers: list = []

        self._build_ui()
        self._apply_styles()

        # Enable click tracking for banner-area Continue
        self.setMouseTracking(True)
        self.banner_lbl.setMouseTracking(True)
        self._continue_active = False
        self._no_doubts_active = False
        self._corrupt_timer = None
        self._corrupt_base_text = ""

        self.hide()

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Top content area (banner + prompt + options)
        self.content_area = QWidget()
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Banner
        self.banner_lbl = QLabel("")
        self.banner_lbl.setWordWrap(True)
        self.banner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_lbl.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #f39c12;
        """)
        self._setup_opacity_effect(self.banner_lbl, 0.0)
        content_layout.addWidget(self.banner_lbl)

        # Prompt
        self.prompt_lbl = QLabel("")
        self.prompt_lbl.setWordWrap(True)
        self.prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt_lbl.setObjectName("ghostPrompt")
        self._setup_opacity_effect(self.prompt_lbl, 0.0)
        content_layout.addWidget(self.prompt_lbl)

        # Option buttons container
        self.option_container = QWidget()
        self._setup_opacity_effect(self.option_container, 0.0)
        self.option_layout = QVBoxLayout(self.option_container)
        self.option_layout.setContentsMargins(0, 0, 0, 0)
        self.option_layout.setSpacing(12)
        content_layout.addWidget(self.option_container, alignment=Qt.AlignmentFlag.AlignCenter)

        content_layout.addStretch()
        self.option_container.hide()

        layout.addWidget(self.content_area, stretch=1)

        # Bottom bar: Continue (right) + I have no doubts (left)
        self.bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(0, 12, 0, 0)
        bottom_layout.setSpacing(16)

        # "I have no doubts" — left side, subtle styling
        self.no_doubts_btn = QPushButton("I have no doubts →")
        self.no_doubts_btn.setObjectName("noDoubtsBtn")
        self.no_doubts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.no_doubts_btn.setEnabled(False)
        self.no_doubts_btn.clicked.connect(self._handle_no_doubts_click)
        self._setup_opacity_effect(self.no_doubts_btn, 0.0)
        bottom_layout.addWidget(self.no_doubts_btn)
        bottom_layout.addStretch()

        # Continue — right side
        self.continue_btn = QPushButton("Do You Want to Continue? →")
        self.continue_btn.setObjectName("continueBtn")
        self.continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self._handle_continue_click)
        self._setup_opacity_effect(self.continue_btn, 0.0)
        bottom_layout.addWidget(self.continue_btn)

        self.bottom_bar.hide()
        layout.addWidget(self.bottom_bar)

    def _setup_opacity_effect(self, widget: QWidget, initial_opacity: float):
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(initial_opacity)

    def _apply_styles(self):
        self.setStyleSheet("""
            #reflectionOverlay {
                background-color: rgba(0, 0, 0, 230);
                border: 3px solid #ff003c;
                border-radius: 18px;
            }
            QLabel {
                color: white;
            }
            #ghostPrompt {
                font-size: 14px;
                color: rgba(255,255,255,50);
                padding: 8px;
            }
            #ghostPrompt:hover {
                color: rgba(255,255,255,255);
            }
            #choiceBtn {
                background-color: rgba(255,255,255,20);
                color: grey;
                border: 1px solid rgba(255,255,255,40);
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                min-width: 350px;
            }
            #choiceBtn:hover {
                background-color: #ff003c;
                border: 1px solid #ff6b8a;
                color: white;
            }
            #choiceBtn:pressed {
                background-color: #cc002f;
            }
            #choiceBtn:disabled {
                background-color: rgba(255,255,255,10);
                color: rgba(255,255,255,70);
                border: 1px solid rgba(255,255,255,20);
            }
            #continueBtn {
                background-color: rgba(255,255,255,15);
                color: #ff6b8a;
                border: 2px solid #ff003c;
                border-radius: 10px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            #continueBtn:hover {
                background-color: #ff003c;
                color: white;
                border-color: #ff6b8a;
            }
            #continueBtn:pressed {
                background-color: #cc002f;
            }
            #continueBtn:disabled {
                background-color: rgba(255,255,255,10);
                color: rgba(255,255,255,50);
                border-color: rgba(255,0,60,30);
            }
            #noDoubtsBtn {
                background-color: transparent;
                color: #666;
                border: 1px solid rgba(255,255,255,20);
                border-radius: 10px;
                padding: 10px 20px;
                font-size: 12px;
            }
            #noDoubtsBtn:hover {
                color: #ff6b8a;
                border-color: rgba(255,0,60,60);
            }
            #noDoubtsBtn:pressed {
                color: #ff003c;
            }
            #noDoubtsBtn:disabled {
                color: #444;
                border-color: rgba(255,255,255,10);
            }
        """)

    # =========================================================
    # Banner / Prompt
    # =========================================================

    def set_banner(self, text: str, instant: bool = False):
        self.show()

        # Stop corruption timer
        if hasattr(self, '_corrupt_timer') and self._corrupt_timer:
            self._corrupt_timer.stop()
            self._corrupt_timer = None

        self.banner_lbl.setText(text)
        self.banner_lbl.show()

        self._stop_animation(self.banner_lbl)

        # INSTANT SWITCH
        if instant:
            if self.banner_lbl.graphicsEffect():
                self.banner_lbl.graphicsEffect().setOpacity(1.0)
            return

        # Normal fade-in
        self._setup_opacity_effect(self.banner_lbl, 0.0)

        self._fade_widget(
            self.banner_lbl,
            fade_in=True,
            duration=500
        )

    def hide_banner(self):
        if hasattr(self, '_corrupt_timer') and self._corrupt_timer:
            self._corrupt_timer.stop()
            self._corrupt_timer = None

        self._stop_animation(self.banner_lbl)

        # Faster fade out
        self._fade_widget(
            self.banner_lbl,
            fade_in=False,
            duration=450,
            on_finished=self.banner_lbl.hide
        )

    def set_prompt(self, text: str):
        self.show()
        self.prompt_lbl.setText(text)
        self.prompt_lbl.show()
        self._stop_animation(self.prompt_lbl)
        self._setup_opacity_effect(self.prompt_lbl, 0.0)
        self._fade_widget(self.prompt_lbl, fade_in=True, duration=2800)

    def hide_prompt(self):
        self._stop_animation(self.prompt_lbl)
        self._fade_widget(
            self.prompt_lbl,
            fade_in=False,
            duration=1500,
            on_finished=self.prompt_lbl.hide
        )

    # =========================================================
    # Bottom Bar (Continue + I have no doubts)
    # =========================================================

    def show_bottom_bar(self):
        self.bottom_bar.show()
        self._continue_active = True
        self._no_doubts_active = True

        # Fade in Continue button
        self.continue_btn.show()
        self.continue_btn.setEnabled(False)
        self._stop_animation(self.continue_btn)
        self._setup_opacity_effect(self.continue_btn, 0.0)
        self._fade_widget(
            self.continue_btn,
            fade_in=True,
            duration=1800,
            on_finished=lambda: self._safe_enable(self.continue_btn)
        )

        # Fade in "I have no doubts" button
        self.no_doubts_btn.show()
        self.no_doubts_btn.setEnabled(False)
        self._stop_animation(self.no_doubts_btn)
        self._setup_opacity_effect(self.no_doubts_btn, 0.0)
        self._fade_widget(
            self.no_doubts_btn,
            fade_in=True,
            duration=1800,
            on_finished=lambda: self._safe_enable(self.no_doubts_btn)
        )

    def hide_bottom_bar(self):
        self._continue_active = False
        self._no_doubts_active = False

        self._stop_animation(self.continue_btn)
        self._fade_widget(
            self.continue_btn,
            fade_in=False,
            duration=2000,
            on_finished=self.continue_btn.hide
        )

        self._stop_animation(self.no_doubts_btn)
        self._fade_widget(
            self.no_doubts_btn,
            fade_in=False,
            duration=2000,
            on_finished=self.no_doubts_btn.hide
        )

    def _handle_continue_click(self):
        if not self._continue_active:
            return
        self._continue_active = False
        self._no_doubts_active = False
        try:
            self.continue_btn.setEnabled(False)
            self.no_doubts_btn.setEnabled(False)
        except RuntimeError:
            pass
        self._send_continue_clicked()

    def _handle_no_doubts_click(self):
        if not self._no_doubts_active:
            return
        self._continue_active = False
        self._no_doubts_active = False
        try:
            self.continue_btn.setEnabled(False)
            self.no_doubts_btn.setEnabled(False)
        except RuntimeError:
            pass
        self._send_no_doubts_clicked()

    def _send_continue_clicked(self):
        if not self.main_window:
            return
        if not hasattr(self.main_window, "milestone_manager"):
            return
        self.main_window.milestone_manager.on_continue_clicked()

    def _send_no_doubts_clicked(self):
        if not self.main_window:
            return
        if not hasattr(self.main_window, "milestone_manager"):
            return
        self.main_window.milestone_manager.on_no_doubts_clicked()

    # =========================================================
    # Click-near-banner = Continue (200px radius)
    # =========================================================

    def mousePressEvent(self, event):
        if not self._continue_active and not self._no_doubts_active:
            super().mousePressEvent(event)
            return

        # Check if click is within 200px of banner center
        if self._is_near_banner(event.pos()):
            self._handle_continue_click()
            return

        super().mousePressEvent(event)

    def _is_near_banner(self, click_pos: QPoint) -> bool:
        """Check if click is within 200px radius of banner center."""
        if not self.banner_lbl.isVisible():
            return False

        banner_rect = self.banner_lbl.geometry()
        banner_center = banner_rect.center()

        dx = click_pos.x() - banner_center.x()
        dy = click_pos.y() - banner_center.y()
        distance = (dx * dx + dy * dy) ** 0.5

        return distance <= 200

    # =========================================================
    # Options
    # =========================================================

    def set_options(self, options: list[str]):
        self._clear_option_buttons()
        self._cancel_pending_timers()
        self.option_container.hide()
        self._setup_opacity_effect(self.option_container, 0.0)

        if not options:
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._show_option_buttons(options))
        timer.start(4200)
        self._pending_timers.append(timer)

    def _show_option_buttons(self, options):
        self._clear_option_buttons()

        for option in options:
            btn = QPushButton(option)
            btn.setObjectName("choiceBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            btn.clicked.connect(
                lambda checked=False, text=option: self._handle_option_click(text)
            )
            self._setup_opacity_effect(btn, 0.0)
            self.option_layout.addWidget(btn)

        self.option_container.show()
        self._stop_animation(self.option_container)
        self._fade_widget(self.option_container, fade_in=True, duration=1800)

        for i in range(self.option_layout.count()):
            widget = self.option_layout.itemAt(i).widget()
            if not isinstance(widget, QPushButton):
                continue
            self._stop_animation(widget)
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda w=widget: self._fade_button_in(w))
            timer.start(i * 100)
            self._pending_timers.append(timer)

    def _fade_button_in(self, btn: QPushButton):
        try:
            if not btn or not btn.isVisible():
                return
        except RuntimeError:
            return
        self._stop_animation(btn)
        self._fade_widget(
            btn,
            fade_in=True,
            duration=1800,
            on_finished=lambda b=btn: self._safe_enable(b)
        )

    def _safe_enable(self, widget: QWidget):
        try:
            if widget and widget.isVisible():
                widget.setEnabled(True)
        except RuntimeError:
            pass

    # =========================================================
    # Click Handling
    # =========================================================

    def _handle_option_click(self, text: str):
        for i in range(self.option_layout.count()):
            widget = self.option_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                try:
                    widget.setEnabled(False)
                except RuntimeError:
                    pass

        # Fade out buttons + container only
        for i in range(self.option_layout.count()):
            widget = self.option_layout.itemAt(i).widget()
            if widget:
                self._stop_animation(widget)
                self._fade_widget(
                    widget,
                    fade_in=False,
                    duration=1500,
                    on_finished=widget.hide
                )

        self._stop_animation(self.option_container)
        self._fade_widget(
            self.option_container,
            fade_in=False,
            duration=1800,
            on_finished=self.option_container.hide
        )

        self._send_selected_option(text)

    def _send_selected_option(self, text: str):
        if not self.main_window:
            return
        if not hasattr(self.main_window, "milestone_manager"):
            return
        self.main_window.milestone_manager.select_entity_option(text)

    # =========================================================
    # Animation Helper
    # =========================================================

    def _fade_widget(
            self,
            widget: QWidget,
            fade_in: bool = True,
            duration: int = 1800,
            on_finished=None
    ):
        if not widget:
            return
        try:
            _ = widget.isVisible()
        except RuntimeError:
            if on_finished:
                on_finished()
            return

        self._stop_animation(widget)
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        start_opacity = effect.opacity()
        end_opacity = 1.0 if fade_in else 0.0

        if abs(start_opacity - end_opacity) < 0.01:
            if on_finished:
                on_finished()
            return

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.setStartValue(start_opacity)
        anim.setEndValue(end_opacity)

        def on_anim_finished():
            self._cleanup_animation(widget)
            if on_finished:
                on_finished()

        anim.finished.connect(on_anim_finished)
        self._active_animations[widget] = anim
        anim.start()

    def _stop_animation(self, widget: QWidget):
        if widget in self._active_animations:
            anim = self._active_animations[widget]
            try:
                anim.stop()
                anim.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._cleanup_animation(widget)

    def _cleanup_animation(self, widget: QWidget):
        if widget in self._active_animations:
            anim = self._active_animations.pop(widget)
            try:
                anim.deleteLater()
            except RuntimeError:
                pass

    def _cancel_pending_timers(self):
        for timer in self._pending_timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
        self._pending_timers.clear()

    # =========================================================
    # Cleanup
    # =========================================================

    def _clear_option_buttons(self):
        for i in range(self.option_layout.count()):
            widget = self.option_layout.itemAt(i).widget()
            if widget:
                self._stop_animation(widget)
        while self.option_layout.count():
            item = self.option_layout.takeAt(0)
            widget = item.widget()
            if widget:
                try:
                    widget.deleteLater()
                except RuntimeError:
                    pass

    def clear(self):
        self._continue_active = False
        self._no_doubts_active = False
        self._cancel_pending_timers()
        widgets_to_clear = [
            self.banner_lbl,
            self.prompt_lbl,
            self.continue_btn,
            self.no_doubts_btn,
            self.option_container
        ]
        for i in range(self.option_layout.count()):
            widget = self.option_layout.itemAt(i).widget()
            if widget:
                widgets_to_clear.append(widget)

        for widget in widgets_to_clear:
            self._stop_animation(widget)
            self._fade_widget(
                widget,
                fade_in=False,
                duration=1800,
                on_finished=widget.hide
            )

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._final_clear)
        timer.start(2000)
        self._pending_timers.append(timer)

    def _final_clear(self):
        self.banner_lbl.clear()
        self.prompt_lbl.clear()
        self.banner_lbl.hide()
        self.prompt_lbl.hide()
        self.bottom_bar.hide()
        self._clear_option_buttons()
        self.option_container.hide()
        self.hide()


# =============================================================================
# Milestone Banner (slide-down toast at top of main window)
# =============================================================================
class MilestoneBanner(QFrame):
    """Animated milestone banner that slides in/out cleanly."""

    TIER_COLORS = {
        "standard": ("#2ecc71", "#1a2f1a"),
        "quantum": ("#3498db", "#1a2a3a"),
        "neural": ("#9b59b6", "#2a1a3a"),
        "dimensional": ("#e74c3c", "#3a1a1a"),
        "cosmic": ("#f39c12", "#3a2a1a"),
        "transcendence": ("#1abc9c", "#1a3a3a"),
        "god_mode": ("#ffd700", "#3a3a1a"),
    }

    def __init__(self, parent, text: str, tier: str = "standard"):
        super().__init__(parent)

        self.parent_window = parent
        self.text = text
        self.tier = tier

        border_color, bg_color = self.TIER_COLORS.get(
            tier,
            self.TIER_COLORS["standard"]
        )

        self.setObjectName("milestoneBanner")

        self.setStyleSheet(f"""
            #milestoneBanner {{
                background-color: {bg_color};
                border-left: 4px solid {border_color};
                border-radius: 8px;
            }}

            QLabel {{
                color: {border_color};
                font-size: 14px;
                font-weight: bold;
            }}
        """)

        self._build_ui()
        self._apply_shadow()

        self.show()
        self.raise_()

        QTimer.singleShot(50, self.slide_in)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.label = QLabel(self.text)
        self.label.setWordWrap(True)

        layout.addWidget(self.label)

        self.resize(420, 70)

    def _apply_shadow(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _target_position(self):
        x = (self.parent_window.width() - self.width()) // 2
        y = 10
        return QPoint(x, y)

    def _hidden_position(self):
        x = (self.parent_window.width() - self.width()) // 2
        y = -self.height() - 20
        return QPoint(x, y)

    def slide_in(self):
        self.move(self._hidden_position())

        self.in_anim = QPropertyAnimation(self, b"pos")
        self.in_anim.setDuration(350)
        self.in_anim.setStartValue(self._hidden_position())
        self.in_anim.setEndValue(self._target_position())
        self.in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.in_anim.start()

        self.in_anim.finished.connect(
            lambda: QTimer.singleShot(3500, self.slide_out)
        )

    def slide_out(self):
        self.out_anim = QPropertyAnimation(self, b"pos")
        self.out_anim.setDuration(300)
        self.out_anim.setStartValue(self.pos())
        self.out_anim.setEndValue(self._hidden_position())
        self.out_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        self.out_anim.finished.connect(self.deleteLater)
        self.out_anim.start()


# =============================================================================
# Main Window
# =============================================================================

class CalculusConsoleV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculus Console v2")
        self.setMinimumSize(800, 700)
        self.resize(1000, 800)

        # Install global Ctrl+K event filter so keypad works from any dialog
        self._keypad_filter = KeypadEventFilter(self)
        QApplication.instance().installEventFilter(self._keypad_filter)

        self._setup_paths()
        self._init_attributes()
        self._setup_managers()
        self._build_menubar()
        self._build_central_ui()
        self._build_statusbar()
        self._apply_global_styles()
        self._load_data()
        self._finalize_startup()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_paths(self):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        self.primary_dir = os.path.join(appdata, "Microsoft", "CLR", "Metadata")
        self.fallback_dir = os.path.join(appdata, "CalculusConsole")
        self.data_dir = self.primary_dir if os.path.exists(self.primary_dir) else self.fallback_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.db_file = os.path.join(self.data_dir, DB_NAME)
        self.config_file = os.path.join(self.data_dir, CONFIG_NAME)
        self.tip_file = os.path.join(self.data_dir, TIP_NAME)
        self.backup_slots = [os.path.join(self.data_dir, b) for b in BACKUP_NAMES]
        self.all_data_dirs = [self.primary_dir, self.fallback_dir]

    def _init_attributes(self):
        self.master_data: Dict[int, dict] = {}
        self.display_to_db_id_map: Dict[int, int] = {}
        self.subject_colors = DEFAULT_SUBJECT_COLORS.copy()
        self.user_macros: List[dict] = []
        self.tip_state = FormulaUtils.load_tip_state(self.tip_file)

        self.enable_backups = True
        self.enable_suggestions = True
        self.suggestion_strictness = "Balanced"
        self.max_suggestions = 3
        self.always_on_top = False

        self.windows: Dict[str, Optional[QWidget]] = {
            "macro": None, "keypad": None, "stats": None,
            "settings": None, "awards": None, "admin": None,  # Add this
        }
        self.in_reflection_mode = False
        self._active_banner: Optional[MilestoneBanner] = None
        self.current_page = 1
        self.items_per_page = 10

    def _setup_managers(self):
        self.db_manager = DatabaseManager(self.db_file)
        self.symbol_learner = SymbolLearner()
        self.milestone_manager = MilestoneManager(self.tip_state, parent=self)
        self._connect_milestone_signals()
        self.keypad_manager = KeypadManager(insert_text_callback=self.insert_text, user_macros=self.user_macros)
        manage_notifications(self)

    def _connect_milestone_signals(self):
        mm = self.milestone_manager
        mm.banner_requested.connect(self._on_milestone_banner)
        mm.toast_requested.connect(lambda msg, bs: show_notification(msg, bs, 4000))
        mm.glitch_requested.connect(lambda txt: show_notification(txt, "warning", 2500))
        mm.award_unlocked.connect(lambda t, d: show_notification(f"🏆 {t}\\n{d}", "success", 5000))
        mm.secret_unlocked.connect(lambda: show_notification("🏆 SECRET AWARD\\nSTABILITY MAINTAINED", "danger", 6000))
        mm.state_modified.connect(self.save_tip_state)
        mm.ui_lock_changed.connect(self._set_reflection_lock)
        mm.entity_banner_show.connect(self._show_entity_banner)
        mm.entity_banner_hide.connect(self._hide_entity_banner)
        mm.entity_prompt_show.connect(self._show_entity_prompt)
        mm.entity_prompt_hide.connect(self._hide_entity_prompt)
        mm.entity_options_ready.connect(self._show_entity_options)
        mm.entity_bottom_bar_show.connect(self._show_entity_bottom_bar)
        mm.entity_bottom_bar_hide.connect(self._hide_entity_bottom_bar)

    # ------------------------------------------------------------------
    # Menubar
    # ------------------------------------------------------------------

    def _build_menubar(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)

        file_menu = menubar.addMenu("File")
        file_menu.addAction(self._action("📄 Export…", self.open_export, "Ctrl+Shift+E"))

        formula_menu = menubar.addMenu("Formula")
        formula_menu.addAction(self._action("➕ New Formula", self.add_formula, "Ctrl+N"))
        formula_menu.addAction(self._action("✎ Edit Formula", self.edit_formula, "Ctrl+E"))
        formula_menu.addAction(self._action("🗑 Delete Formula", self.delete_formula, "Delete"))
        formula_menu.addSeparator()
        formula_menu.addAction(self._action("🔍 View Details", self.view_details, "Ctrl+Return"))

        view_menu = menubar.addMenu("View")
        view_menu.addAction(self._action("📊 Statistics", self.open_stats, "Ctrl+Shift+S"))
        view_menu.addAction(self._action("🏅 Awards", self.open_awards, "Ctrl+Shift+A"))
        view_menu.addSeparator()
        view_menu.addAction(self._action("⌨ Toggle Keypad", self.toggle_keypad, "Ctrl+K"))
        view_menu.addAction(self._action("📌 Always on Top", self.toggle_always_on_top))

        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction(self._action("⛭ Settings", self.open_settings, "Ctrl+,"))
        tools_menu.addAction(self._action("⌨ Manage Macros", self.open_macros, "Ctrl+M"))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(self._action("About", self.show_about))

    def _action(self, text: str, slot, shortcut: str = None) -> QAction:
        act = QAction(text, self)
        act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        return act

    # ------------------------------------------------------------------
    # Central UI
    # ------------------------------------------------------------------

    def _build_central_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filter Bar
        filter_bar = QFrame()
        filter_bar.setObjectName("filterBar")
        fl = QHBoxLayout(filter_bar)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search formulas, subjects, topics…")
        self.search_edit.setMinimumWidth(280)
        self.search_edit.textChanged.connect(self._apply_filters_and_pagination)
        fl.addWidget(self.search_edit, stretch=2)

        self.filter_subject = QComboBox()
        self.filter_subject.setPlaceholderText(ALL_SUBJECTS)
        self.filter_subject.setMinimumWidth(140)
        self.filter_subject.currentTextChanged.connect(self._on_filter_subject_changed)
        fl.addWidget(self.filter_subject)

        self.filter_topic = QComboBox()
        self.filter_topic.setPlaceholderText(ALL_TOPICS)
        self.filter_topic.setMinimumWidth(160)
        self.filter_topic.currentTextChanged.connect(self._on_filter_topic_changed)
        fl.addWidget(self.filter_topic)

        self.filter_subtopic = QComboBox()
        self.filter_subtopic.setPlaceholderText(ALL_SUB_TOPICS)
        self.filter_subtopic.setMinimumWidth(160)
        self.filter_subtopic.currentTextChanged.connect(self._apply_filters_and_pagination)
        fl.addWidget(self.filter_subtopic)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_filters)
        fl.addWidget(clear_btn)

        layout.addWidget(filter_bar)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        for icon, tip, cb in [
            ("➕", "New Formula (Ctrl+N)", self.add_formula),
            ("✎", "Edit Formula (Ctrl+E)", self.edit_formula),
            ("🗑", "Delete Formula (Del)", self.delete_formula),
            ("🔍", "View Details (Ctrl+Enter)", self.view_details)
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("toolBtn")
            btn.clicked.connect(cb)
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # -- Table --
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["#", "Formula", "Subject", "Topic", "Sub-Topic", "Vars"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 160)
        self.table.setColumnWidth(5, 50)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
        self.table.doubleClicked.connect(self.edit_formula)
        layout.addWidget(self.table, stretch=1)

        # -- Pagination Bar --
        pag_bar = QFrame()
        pag_bar.setObjectName("pagBar")
        pl = QHBoxLayout(pag_bar)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(6)

        self.first_page_btn = QPushButton("«")
        self.first_page_btn.setFixedWidth(40)
        self.first_page_btn.setToolTip("First page")
        self.first_page_btn.clicked.connect(self.go_to_first_page)
        pl.addWidget(self.first_page_btn)

        self.prev_page_btn = QPushButton("‹")
        self.prev_page_btn.setFixedWidth(36)
        self.prev_page_btn.setToolTip("Previous page")
        self.prev_page_btn.clicked.connect(self.go_to_prev_page)
        pl.addWidget(self.prev_page_btn)

        self.page_entry = QLineEdit()
        self.page_entry.setFixedWidth(50)
        self.page_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_entry.setText("1")
        self.page_entry.returnPressed.connect(self.on_page_entry_changed)
        pl.addWidget(self.page_entry)

        self.page_label = QLabel("of 1")
        pl.addWidget(self.page_label)

        self.next_page_btn = QPushButton("›")
        self.next_page_btn.setFixedWidth(36)
        self.next_page_btn.setToolTip("Next page")
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        pl.addWidget(self.next_page_btn)

        self.last_page_btn = QPushButton("»")
        self.last_page_btn.setFixedWidth(40)
        self.last_page_btn.setToolTip("Last page")
        self.last_page_btn.clicked.connect(self.go_to_last_page)
        pl.addWidget(self.last_page_btn)

        pl.addSpacing(16)

        pl.addStretch()

        self.result_count_lbl = QLabel("0 formulas")
        self.result_count_lbl.setStyleSheet("color: #888;")
        pl.addWidget(self.result_count_lbl)

        layout.addWidget(pag_bar)

        # Reflection Overlay
        self.reflection_overlay = ReflectionOverlay(
            parent=central,
            main_window=self
        )
        self.reflection_overlay.setGeometry(100, 120, self.width() - 200, 300)

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_count = QLabel("0 formulas")
        self.status_filter = QLabel("")
        self.statusbar.addWidget(self.status_count)
        self.statusbar.addPermanentWidget(self.status_filter)

    def _apply_global_styles(self):
        self.setStyleSheet("""
            /* ---------------- Main Window ---------------- */
            QMainWindow {
                background-color: #121212;
            }

            QWidget {
                font-family: "Segoe UI", "Inter", Arial;
                font-size: 13px;
                color: #ECECEC;
            }

            /* ---------------- Containers ---------------- */
            #filterBar, #pagBar {
                background-color: #1C1C1C;
                border: 1px solid #2A2A2A;
                border-radius: 10px;
            }

            /* ---------------- Input Fields ---------------- */
            QLineEdit {
                background-color: #181818;
                color: #F5F5F5;
                border: 1px solid #303030;
                border-radius: 8px;
                padding: 8px 10px;
                selection-background-color: #3B82F6;
            }

            QLineEdit:focus {
                border: 1px solid #3B82F6;
                background-color: #1E1E1E;
            }

            /* ---------------- Combo Boxes ---------------- */
            QComboBox {
                background-color: #181818;
                color: #F5F5F5;
                border: 1px solid #303030;
                border-radius: 8px;
                padding: 6px 8px;
            }

            QComboBox:hover {
                border: 1px solid #3B82F6;
            }

            QComboBox::drop-down {
                border: none;
                width: 24px;
            }

            QComboBox QAbstractItemView {
                background-color: #1C1C1C;
                color: white;
                border: 1px solid #303030;
                selection-background-color: #3B82F6;
            }

            /* ---------------- Table ---------------- */
            QTableWidget {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 10px;
                gridline-color: #202020;
                selection-background-color: #2563EB;
                alternate-background-color: #1B1B1B;
                padding: 4px;
            }

            QTableWidget::item {
                padding: 10px;
                border: none;
            }

            QTableWidget::item:selected {
                background-color: #2563EB;
                color: white;
            }

            QTableWidget::item:hover:!selected {
                background-color: #222222;
            }

            /* ---------------- Table Headers ---------------- */
            QHeaderView::section {
                background-color: #1E1E1E;
                color: #B0B0B0;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #2A2A2A;
                font-weight: bold;
            }

            /* ---------------- Toolbar Buttons ---------------- */
            #toolBtn {
                background-color: #1F1F1F;
                color: white;
                border: 1px solid #2F2F2F;
                border-radius: 8px;
                font-size: 16px;
            }

            #toolBtn:hover {
                background-color: #2A2A2A;
                border: 1px solid #3B82F6;
            }

            #toolBtn:pressed {
                background-color: #2563EB;
            }

            /* ---------------- Secondary Buttons ---------------- */
            #secondaryBtn {
                background-color: #222222;
                color: white;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px 16px;
            }

            #secondaryBtn:hover {
                background-color: #2D2D2D;
                border: 1px solid #3B82F6;
            }

            /* ---------------- Pagination Buttons ---------------- */
            QPushButton {
                background-color: #1F1F1F;
                border: 1px solid #303030;
                border-radius: 6px;
                padding: 6px;
            }

            QPushButton:hover {
                background-color: #2B2B2B;
            }

            QPushButton:pressed {
                background-color: #2563EB;
            }

            /* ---------------- Menu Bar ---------------- */
            QMenuBar {
                background-color: #181818;
                color: white;
                border-bottom: 1px solid #2A2A2A;
            }

            QMenuBar::item {
                padding: 8px 14px;
                background: transparent;
            }

            QMenuBar::item:selected {
                background-color: #2563EB;
                border-radius: 4px;
            }

            /* ---------------- Dropdown Menus ---------------- */
            QMenu {
                background-color: #1C1C1C;
                color: white;
                border: 1px solid #2A2A2A;
            }

            QMenu::item {
                padding: 8px 20px;
            }

            QMenu::item:selected {
                background-color: #2563EB;
            }

            /* ---------------- Status Bar ---------------- */
            QStatusBar {
                background-color: #181818;
                color: #9A9A9A;
                border-top: 1px solid #2A2A2A;
            }

            /* ---------------- Scrollbars ---------------- */
            QScrollBar:vertical {
                background: #181818;
                width: 10px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                background: #404040;
                border-radius: 5px;
                min-height: 25px;
            }

            QScrollBar::handle:vertical:hover {
                background: #5A5A5A;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                background: #181818;
                height: 10px;
            }

            QScrollBar::handle:horizontal {
                background: #404040;
                border-radius: 5px;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self):
        self._load_from_db()
        self.load_config()
        self.refresh_table()
        self._refresh_filter_combos()
        self.symbol_learner.learn(self.master_data)
        self.current_page = 1
        self._apply_filters_and_pagination()

    def _finalize_startup(self):
        count = len(self.master_data)
        self.status_count.setText(f"{count} formulas loaded")
        self.create_backup()
        QTimer.singleShot(100, lambda: self.milestone_manager.process_count(count, self.master_data))
        self.update_awards_button()

    def _load_from_db(self):
        self.master_data.clear()
        try:
            formulas = self.db_manager.get_all_formulas()
            for f in formulas:
                fid = f["id"]
                self.master_data[fid] = {
                    "main_info": [fid, f["formula_text"], f["field"], f["topic"], f.get("sub_topic", "_GENERAL_")],
                    "variables": f.get("variables", [])
                }
        except Exception as e:
            logging.error(f"DB load failed: {e}")
            self._recover_from_backup()

    def _recover_from_backup(self):
        newest = None
        latest = -1
        for slot in self.backup_slots:
            if os.path.exists(slot) and os.path.getmtime(slot) > latest:
                latest = os.path.getmtime(slot)
                newest = slot
        if newest:
            try:
                if os.path.exists(self.db_file):
                    os.remove(self.db_file)
                shutil.copy2(newest, self.db_file)
                self.db_manager = DatabaseManager(self.db_file)
                self._load_from_db()
                show_notification("Recovered from backup", "warning")
            except Exception as e:
                logging.critical(f"Recovery failed: {e}")

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def apply_settings_live(self):
        """
        Apply updated settings immediately without restart.
        """

        # Always on top
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint,
            self.always_on_top
        )
        self.show()

        # Update child windows
        self.update_child_windows_topmost()

        # Update keypad macros
        self.keypad_manager.update_macros(self.user_macros)

        # Refresh table colors if subject colors changed
        self.apply_row_colors()

        # Refresh UI if suggestion settings changed
        self.symbol_learner.learn(self.master_data)

    def load_config(self):
        cfg = FormulaUtils.load_config(self.config_file)
        self.enable_backups = cfg.get("backups", True)
        self.enable_suggestions = cfg.get("suggestions", True)
        self.suggestion_strictness = cfg.get("suggestion_strictness", "Balanced")
        self.max_suggestions = cfg.get("max_suggestions", 3)
        self.user_macros = cfg.get("macros", [])
        self.always_on_top = cfg.get("always_on_top", False)
        self.subject_colors = cfg.get("subject_colors", DEFAULT_SUBJECT_COLORS.copy())
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.always_on_top)
        self.show()
        self.keypad_manager.update_macros(self.user_macros)

    def save_config(self):
        FormulaUtils.save_config(
            self.config_file, "darkly", self.enable_backups,
            self.enable_suggestions, self.suggestion_strictness,
            self.max_suggestions, self.user_macros, self.always_on_top,
            self.subject_colors
        )

    def save_tip_state(self):
        FormulaUtils.save_tip_state(self.tip_file, self.tip_state)

    # ------------------------------------------------------------------
    # Table & Filtering
    # ------------------------------------------------------------------
    def _adjust_table_row_layout(self):
        """
        Always make exactly 10 rows fill the visible table area.
        Rows auto-resize when window size changes.
        """

        visible_rows = self.items_per_page  # always 10

        viewport_height = self.table.viewport().height()

        if viewport_height <= 0:
            return

        # Divide available space evenly across rows
        row_height = max(30, viewport_height // visible_rows)

        # Tell table header to use this fixed size automatically
        self.table.verticalHeader().setDefaultSectionSize(row_height)

        # Optional font scaling
        font_size = max(10, min(16, int(row_height * 0.35)))

        font = self.table.font()
        font.setPointSize(font_size)
        self.table.setFont(font)

    def refresh_table(self):
        self._apply_filters_and_pagination()

    def _add_table_row(self, display_num: int, data: dict):
        info = data["main_info"]
        row = self.table.rowCount()
        self.table.insertRow(row)
        items = [
            QTableWidgetItem(str(display_num)),
            QTableWidgetItem(info[1]),
            QTableWidgetItem(info[2]),
            QTableWidgetItem(info[3]),
            QTableWidgetItem(info[4]),
            QTableWidgetItem(str(len(data.get("variables", [])))),
        ]
        for col, it in enumerate(items):
            it.setData(Qt.ItemDataRole.UserRole, display_num)
            self.table.setItem(row, col, it)

    def apply_row_colors(self):
        for row in range(self.table.rowCount()):
            subj_item = self.table.item(row, 2)
            if not subj_item:
                continue
            color = self.subject_colors.get(subj_item.text().strip(), "#cccccc")
            for col in range(self.table.columnCount()):
                it = self.table.item(row, col)
                if it:
                    it.setForeground(QColor(color))

    def _refresh_filter_combos(self):
        subjects = set()
        topics_by_subject: Dict[str, set] = {}
        subs_by_topic: Dict[Tuple[str, str], set] = {}
        for d in self.master_data.values():
            info = d["main_info"]
            subj, topic, sub = info[2], info[3], info[4]
            subjects.add(subj)
            topics_by_subject.setdefault(subj, set()).add(topic)
            subs_by_topic.setdefault((subj, topic), set()).add(sub)
        self._topics_by_subject = topics_by_subject
        self._subs_by_topic = subs_by_topic

        current_sub = self.filter_subject.currentText()
        self.filter_subject.blockSignals(True)
        self.filter_subject.clear()
        self.filter_subject.addItem(ALL_SUBJECTS)
        self.filter_subject.addItems(sorted(subjects | {"Physics", "Chemistry", "Maths"}))
        if current_sub:
            self.filter_subject.setCurrentText(current_sub)
        self.filter_subject.blockSignals(False)

    def _on_filter_subject_changed(self, text: str):
        self.filter_topic.blockSignals(True)
        self.filter_topic.clear()
        self.filter_topic.addItem(ALL_TOPICS)
        if text and text != ALL_SUBJECTS:
            self.filter_topic.addItems(sorted(self._topics_by_subject.get(text, set())))
        self.filter_topic.blockSignals(False)
        self.filter_subtopic.blockSignals(True)
        self.filter_subtopic.clear()
        self.filter_subtopic.addItem(ALL_SUB_TOPICS)
        self.filter_subtopic.blockSignals(False)
        self._apply_filters_and_pagination()

    def _on_filter_topic_changed(self, text: str):
        subj = self.filter_subject.currentText()
        self.filter_subtopic.blockSignals(True)
        self.filter_subtopic.clear()
        self.filter_subtopic.addItem(ALL_SUB_TOPICS)
        if subj and subj != ALL_SUBJECTS and text and text != ALL_TOPICS:
            self.filter_subtopic.addItems(sorted(self._subs_by_topic.get((subj, text), set())))
        self.filter_subtopic.blockSignals(False)
        self._apply_filters_and_pagination()

    def _apply_filters_and_pagination(self):
        search = self.search_edit.text().strip().lower()
        f_subj = self.filter_subject.currentText()
        f_topic = self.filter_topic.currentText()
        f_sub = self.filter_subtopic.currentText()

        # Build filtered list of db_ids
        filtered_ids = []
        for db_id, data in self.master_data.items():
            info = data["main_info"]
            matches = True
            if search:
                hay = f"{info[1]} {info[2]} {info[3]} {info[4]}".lower()
                if search not in hay:
                    matches = False
            if f_subj and f_subj != ALL_SUBJECTS and info[2] != f_subj:
                matches = False
            if f_topic and f_topic != ALL_TOPICS and info[3] != f_topic:
                matches = False
            if f_sub and f_sub != ALL_SUB_TOPICS and info[4] != f_sub:
                matches = False
            if matches:
                filtered_ids.append(db_id)

        # Sort by ID
        filtered_ids.sort(key=lambda x: int(x))
        self.filtered_formulas = filtered_ids

        total_pages = self.get_total_pages()
        if self.current_page > total_pages:
            self.current_page = total_pages
        if self.current_page < 1:
            self.current_page = 1

        start = (self.current_page - 1) * self.items_per_page
        end = start + self.items_per_page
        page_ids = self.filtered_formulas[start:end]

        # Build display map and populate table
        self.table.setRowCount(0)
        self.display_to_db_id_map.clear()
        display_num = start + 1
        for db_id in page_ids:
            self.display_to_db_id_map[display_num] = db_id
            self._add_table_row(display_num, self.master_data[db_id])
            display_num += 1

        self.apply_row_colors()

        # Update pagination controls
        self.page_entry.setText(str(self.current_page))
        self.page_label.setText(f"of {total_pages}")
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)
        self.page_entry.setValidator(QIntValidator(1, max(1, total_pages), self))

        # Update status labels
        total = len(self.master_data)
        filtered = len(self.filtered_formulas)
        self.status_count.setText(f"{total} formulas loaded")
        self.status_filter.setText(f"Showing {filtered} of {total}")
        self.result_count_lbl.setText(f"{filtered} results")
        self._adjust_table_row_layout()

    def _clear_filters(self):
        self.search_edit.clear()
        self.filter_subject.setCurrentIndex(0)
        self.filter_topic.clear()
        self.filter_subtopic.clear()
        self._apply_filters_and_pagination()

    def _table_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        menu.addAction("Edit", self.edit_formula)
        menu.addAction("View Details", self.view_details)
        menu.addSeparator()
        menu.addAction("Delete", self.delete_formula)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def selected_db_id(self) -> Optional[int]:
        items = self.table.selectedItems()
        if not items:
            return None
        display_num = items[0].data(Qt.ItemDataRole.UserRole)
        return self.display_to_db_id_map.get(display_num)

    def get_total_pages(self):
        return max(1, (len(self.filtered_formulas) + self.items_per_page - 1) // self.items_per_page)

    # --- Pagination navigation ---

    def go_to_first_page(self):
        self.current_page = 1
        self._apply_filters_and_pagination()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._apply_filters_and_pagination()

    def go_to_next_page(self):
        total = self.get_total_pages()
        if self.current_page < total:
            self.current_page += 1
            self._apply_filters_and_pagination()

    def go_to_last_page(self):
        self.current_page = self.get_total_pages()
        self._apply_filters_and_pagination()

    def on_page_entry_changed(self):
        try:
            page = int(self.page_entry.text().strip())
            total = self.get_total_pages()
            if page < 1:
                page = 1
            elif page > total:
                page = total
            self.current_page = page
            self._apply_filters_and_pagination()
        except ValueError:
            self.page_entry.setText(str(self.current_page))

    def _jump_to_formula_page(self, db_id: int):
        """After save/delete, jump to the page containing this formula."""
        for idx, fid in enumerate(self.filtered_formulas):
            if fid == db_id:
                self.current_page = (idx // self.items_per_page) + 1
                return
        self.current_page = 1

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def add_formula(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_NOTHING_SAVES_MSG, "danger")
            return
        dialog = FormulaDialog(
            parent=self, edit_data=None, master_data=self.master_data,
            symbol_learner=self.symbol_learner, max_suggestions=self.max_suggestions
        )
        dialog.finished.connect(lambda result: self._on_dialog_finished(result, dialog, is_edit=False))
        dialog.open()

    def _on_dialog_finished(self, result_code, dialog, is_edit):
        if result_code == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                self._save_formula_result(result, is_edit=is_edit)

    def edit_formula(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_TRY_AGAIN_MSG, "danger")
            return
        db_id = self.selected_db_id()
        if db_id is None or db_id not in self.master_data:
            show_notification(NO_FORMULA_SELECTED, "warning")
            return
        dialog = FormulaDialog(
            parent=self, edit_data=self.master_data[db_id],
            master_data=self.master_data, symbol_learner=self.symbol_learner,
            max_suggestions=self.max_suggestions
        )
        dialog.finished.connect(lambda result: self._on_dialog_finished(result, dialog, is_edit=True))
        dialog.open()

    def _save_formula_result(self, result: dict, is_edit: bool):
        if not is_edit:
            if self.milestone_manager.check_secret_code(result["field"], result["topic"]):
                show_notification("…", "warning")
                return
        try:
            if is_edit and result["id"] is not None:
                success = self.db_manager.update_formula(
                    result["id"], result["formula"], result["field"],
                    result["topic"], result["sub_topic"], result["variables"]
                )
                if success:
                    self.master_data[result["id"]] = {
                        "main_info": [result["id"], result["formula"], result["field"],
                                      result["topic"], result["sub_topic"]],
                        "variables": result["variables"]
                    }
                    show_notification(f"Formula updated: {result['formula']}", "success")
            else:
                new_id = self.db_manager.add_formula(
                    result["formula"], result["field"], result["topic"],
                    result["sub_topic"], result["variables"]
                )
                if new_id:
                    self.master_data[new_id] = {
                        "main_info": [new_id, result["formula"], result["field"],
                                      result["topic"], result["sub_topic"]],
                        "variables": result["variables"]
                    }
                    show_notification(f"Formula saved: #{new_id}", "success")
                    self.milestone_manager.record_movement("save_formula")
            self._post_data_change()
        except Exception as e:
            logging.error(f"Save error: {e}")
            show_notification("Failed to save formula", "danger")

    def _post_data_change(self):
        self.symbol_learner.learn(self.master_data)
        self.refresh_table()
        self._refresh_filter_combos()
        count = len(self.master_data)
        self.milestone_manager.process_count(count, self.master_data)
        self.update_awards_button()

    def delete_formula(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_TRY_AGAIN_MSG, "danger")
            return
        db_id = self.selected_db_id()
        if db_id is None or db_id not in self.master_data:
            show_notification(NO_FORMULA_SELECTED, "warning")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete", f"Delete formula #{db_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            success = self.db_manager.delete_formula(db_id)
            if success:
                # DB renumbers IDs on delete; reload to stay in sync
                self._load_from_db()
                self.refresh_table()
                self._refresh_filter_combos()
                count = len(self.master_data)
                self.milestone_manager.process_count(count, self.master_data)
                self.update_awards_button()
                show_notification("Formula deleted", "success")
            else:
                show_notification("Failed to delete formula", "danger")
        except Exception as e:
            logging.error(f"Delete error: {e}")
            show_notification("Error deleting formula", "danger")

    def view_details(self):
        db_id = self.selected_db_id()
        if db_id is None or db_id not in self.master_data:
            show_notification(NO_FORMULA_SELECTED, "warning")
            return
        dlg = FormulaDetailsDialog(self, self.master_data[db_id], self.subject_colors)
        dlg.exec()

    # ------------------------------------------------------------------
    # Dialog Launchers
    # ------------------------------------------------------------------

    def open_export(self):
        if not self.master_data:
            show_notification("No formulas to export", "warning")
            return
        dlg = ExportDialog(self, self.master_data)
        dlg.exec()

    def open_stats(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_MSG, "danger")
            return
        if self.windows["stats"] and self.windows["stats"].isVisible():
            self.windows["stats"].raise_()
            self.windows["stats"].activateWindow()
            return
        self.windows["stats"] = StatsDashboard(self, self.master_data)
        self.windows["stats"].show()
        self.milestone_manager.record_movement("open_stats")

    def open_awards(self):
        if self.windows["awards"] and self.windows["awards"].isVisible():
            self.windows["awards"].raise_()
            self.windows["awards"].activateWindow()
            return
        if len(self.master_data) < 30:
            show_notification("Awards unlock at 30 formulas", "info")
            return
        self.windows["awards"] = AwardPanel(self)
        self.windows["awards"].show()

    def open_settings(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_NOTHING_SAVES_MSG, "danger")
            return
        if self.windows["settings"] and self.windows["settings"].isVisible():
            self.windows["settings"].raise_()
            self.windows["settings"].activateWindow()
            return
        self.windows["settings"] = SettingsWindow(self)
        self.windows["settings"].show()

    def open_macros(self):
        if self.windows["macro"] and self.windows["macro"].isVisible():
            self.windows["macro"].raise_()
            self.windows["macro"].activateWindow()
            return
        self.windows["macro"] = MacroManagerWindow(self)
        self.windows["macro"].show()

    def toggle_keypad(self):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_MSG, "danger")
            return
        opened = self.keypad_manager.toggle(parent_widget=self)
        self.windows["keypad"] = self.keypad_manager._window if opened else None

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.always_on_top)
        self.show()
        self.save_config()
        self.update_child_windows_topmost()
        state = "enabled" if self.always_on_top else "disabled"
        show_notification(f"Always on top {state}", "info")

    def show_about(self):
        QMessageBox.about(
            self, "About Calculus Console v2",
            "<h2>Calculus Console v2</h2>"
            "<p>Advanced formula & knowledge management system.</p>"
            "<p>PyQt6 Edition — upgraded with real-time filtering, search, "
            "and menubar-driven dialogs.</p>"
        )

    # ------------------------------------------------------------------
    # Keypad Insertion (works globally across all windows)
    # ------------------------------------------------------------------

    @staticmethod
    def insert_text(text: str, warp: int = 0):
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            cursor = focused.cursorPosition()
            focused.insert(text)
            if warp > 0:
                focused.setCursorPosition(cursor + len(text) - warp)
        elif isinstance(focused, QTextEdit):
            tc = focused.textCursor()
            tc.insertText(text)
            focused.setTextCursor(tc)

    # ------------------------------------------------------------------
    # Milestone & Reflection Delegation
    # ------------------------------------------------------------------

    def _on_milestone_banner(self, text: str, tier: str):
        banner = MilestoneBanner(self, text, tier)
        banner.show()

    def _set_reflection_lock(self, locked: bool):
        self.in_reflection_mode = locked
        self.table.setEnabled(not locked)
        for w in [self.search_edit, self.filter_subject, self.filter_topic, self.filter_subtopic]:
            w.setEnabled(not locked)
        if locked:
            self.reflection_overlay.setGeometry(
                80, 100, self.width() - 160, self.height() - 200
            )
            self.reflection_overlay.show()
            self.reflection_overlay.raise_()
        else:
            self.reflection_overlay.hide()
            self.reflection_overlay.clear()

    def _show_entity_banner(self, text: str, corrupted: bool = False):
        self.reflection_overlay.set_banner(text, corrupted)

    def _hide_entity_banner(self):
        self.reflection_overlay.hide_banner()

    def _show_entity_prompt(self, text: str):
        self.reflection_overlay.set_prompt(text)

    def _show_entity_options(self, options: List[str]):
        self.reflection_overlay.set_options(options)

    def _hide_entity_prompt(self):
        self.reflection_overlay.hide_prompt()

    def _show_entity_bottom_bar(self):
        self.reflection_overlay.show_bottom_bar()

    def _hide_entity_bottom_bar(self):
        self.reflection_overlay.hide_bottom_bar()

    # ------------------------------------------------------------------
    # Secret Award Delegation
    # ------------------------------------------------------------------

    def get_secret_award_state(self) -> dict:
        return self.milestone_manager.get_secret_award_state()

    def milestone_seen(self, key: str) -> bool:
        return self.tip_state.setdefault("shown", {}).get(key, False)

    def secret_movement(self, action: str):
        self.milestone_manager.record_movement(action)

    # ------------------------------------------------------------------
    # Child Window Sync
    # ------------------------------------------------------------------

    def update_child_windows_topmost(self):
        flag = self.always_on_top
        for key in ["stats", "awards", "settings", "macro"]:
            win = self.windows.get(key)
            if win and win.isVisible():
                win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, flag)
                win.show()

    def update_awards_button(self):
        pass

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(self):
        if not self.enable_backups or not os.path.exists(self.db_file):
            return
        oldest = FormulaUtils.find_oldest_backup_slot(self.backup_slots)
        try:
            self.db_manager.backup_database(oldest)
        except Exception as e:
            logging.error(f"Backup failed: {e}")

    # ------------------------------------------------------------------
    # Window Events
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self.in_reflection_mode:
            show_notification(SYSTEM_LOCKED_NICE_TRY_MSG, "danger")
            event.ignore()
            return
        self.save_config()
        self.save_tip_state()
        self.db_manager.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        self._adjust_table_row_layout()

        if self.reflection_overlay.isVisible():
            self.reflection_overlay.setGeometry(
                80, 100, self.width() - 160, self.height() - 200
            )


# =============================================================================
# Entry Point
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#252525"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#2a2a2a"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d2d2d"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#3a3a3a"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2980b9"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    window = CalculusConsoleV2()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
