from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QRect
)
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QDialog, QGraphicsOpacityEffect,
    QSizePolicy, QScrollArea
)

from formula_entry import FormulaEntry
from notification_manager import show_notification


class FormulaRenderWidget(QWidget):
    def __init__(self, formula_text: str, parent=None):
        super().__init__(parent)
        self.formula_text = formula_text

        # Prevent the QVBoxLayout from crushing our drawing canvas width to 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        formula_len = len(formula_text)
        if formula_len > 100:
            self.font_size = 15
        elif formula_len > 60:
            self.font_size = 18
        elif formula_len > 35:
            self.font_size = 26
        else:
            self.font_size = 32

        # Setup the font
        self.math_font = QFont()
        self.math_font.setFamilies([
            "STIX Two Math", "Cambria Math", "DejaVu Serif", "Times New Roman"
        ])
        self.math_font.setPointSize(self.font_size)
        self.math_font.setBold(True)

        # Calculate the logical bounds of the text
        metrics = QFontMetrics(self.math_font)

        # Use raw integer to prevent PyQt6 Enum typing crashes
        wrap_flag = Qt.TextFlag.TextWordWrap.value

        rect = metrics.boundingRect(
            QRect(0, 0, 650, 9999),
            wrap_flag,
            self.formula_text
        )

        # THE MAGIC BUFFER:
        # Add 40px to the top and 40px to the bottom of the logical text height.
        self.vertical_buffer = 40
        self.setFixedHeight(rect.height() + (self.vertical_buffer * 2))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        painter.setFont(self.math_font)
        painter.setPen(QColor("#F5F5F5"))

        # THE ACTUAL CULPRIT FIXED:
        # Extract the integer .value first, THEN combine them.
        draw_flags = Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value

        # Draw text dead center inside the padded widget
        painter.drawText(
            self.rect(),
            draw_flags,
            self.formula_text
        )

        # Always gracefully close the painter to prevent memory leak warnings
        painter.end()


# =============================================================================
# Formula Details Dialog
# =============================================================================

class FormulaDetailsDialog(QDialog):
    def __init__(self, parent, entry: FormulaEntry, subject_colors: dict):
        super().__init__(parent)

        self.entry = entry
        self.subject_colors = subject_colors

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(780, 600)
        self.resize(850, 700)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)

        container = QFrame()
        container.setObjectName("mainContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(28)

        subject_color = self.subject_colors.get(self.entry.subject.strip(), "#3B82F6")

        # ── Build sections ──
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_formula_box(self.entry.formula_text))
        if self.entry.has_notes:
            layout.addWidget(self._build_notes_section(self.entry.notes))
        layout.addWidget(self._build_meta_chips(subject_color))

        if self.entry.tags:
            layout.addWidget(self._build_tags_section(self.entry.tags))

        layout.addWidget(self._build_variables_section(self.entry.variables))

        layout.addStretch()
        layout.addWidget(self._build_button_bar())

        scroll.setWidget(scroll_content)
        container_layout.addWidget(scroll)
        outer.addWidget(container)

    @staticmethod
    def _build_header():
        title = QLabel("FORMULA ANALYSIS")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title

    @staticmethod
    def _build_formula_box(formula_text: str):
        box = QFrame()
        box.setObjectName("formulaBox")

        box_layout = QVBoxLayout(box)
        # Keep standard margins for the outer box
        box_layout.setContentsMargins(24, 24, 24, 24)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        render_widget = FormulaRenderWidget(formula_text)
        box_layout.addWidget(render_widget)

        return box

    def _build_meta_chips(self, subject_color: str):
        frame = QFrame()
        frame.setObjectName("metaFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        meta_items = [
            ("SUBJECT", self.entry.subject),
            ("TOPIC", self.entry.topic),
            ("SUB-TOPIC", self.entry.display_sub_topic),
        ]

        for label_text, value in meta_items:
            chip = self._make_meta_chip(label_text, value, subject_color)
            layout.addWidget(chip)

        return frame

    @staticmethod
    def _make_meta_chip(label_text: str, value: str, color: str):
        chip = QFrame()
        chip.setObjectName("metaChip")
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(18, 14, 18, 14)
        chip_layout.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #888; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val = QLabel(value)
        val.setWordWrap(True)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")

        chip_layout.addWidget(lbl)
        chip_layout.addWidget(val)
        return chip

    @staticmethod
    def _build_tags_section(tags: list):
        title = QLabel("TAGS")
        title.setObjectName("sectionTitle")

        frame = QFrame()
        frame.setObjectName("tagsFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        for tag in tags:
            tag_label = QLabel(f"#{tag}")
            tag_label.setObjectName("tagChip")
            layout.addWidget(tag_label)

        layout.addStretch()

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(title)
        container_layout.addWidget(frame)
        return container

    @staticmethod
    def _build_notes_section(notes: str):
        title = QLabel("NOTES")
        title.setObjectName("sectionTitle")

        frame = QFrame()
        frame.setObjectName("notesFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        text = QLabel(notes)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setObjectName("notesText")
        layout.addWidget(text)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(title)
        container_layout.addWidget(frame)
        return container

    def _build_variables_section(self, variables: list):
        title = QLabel("VARIABLE ENTITIES")
        title.setObjectName("sectionTitle")

        if not variables:
            return self._build_empty_variables(title)

        frame = QFrame()
        frame.setObjectName("varsFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        for var in variables:
            card = self._build_var_card(var)
            layout.addWidget(card)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(title)
        container_layout.addWidget(frame)
        return container

    @staticmethod
    def _build_var_card(var):
        card = QFrame()
        card.setObjectName("varCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        symbol = QLabel(var.symbol)
        symbol.setObjectName("varSymbol")
        symbol.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        name = QLabel(var.name)
        name.setWordWrap(True)
        name.setObjectName("varName")

        unit_text = var.unit
        unit = QLabel(unit_text if unit_text.strip() else "—")
        unit.setAlignment(Qt.AlignmentFlag.AlignRight)
        unit.setObjectName("varUnit")

        layout.addWidget(symbol)
        layout.addWidget(name, 1)
        layout.addWidget(unit)
        return card

    @staticmethod
    def _build_empty_variables(title: QLabel):
        frame = QFrame()
        frame.setObjectName("emptyFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)

        empty = QLabel("NO VARIABLES DETECTED")
        empty.setObjectName("emptyLabel")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(empty)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(title)
        container_layout.addWidget(frame)
        return container

    def _build_button_bar(self):
        frame = QFrame()
        frame.setObjectName("btnFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(14)
        layout.addStretch()

        copy_btn = QPushButton("📋  COPY FORMULA")
        copy_btn.setObjectName("copyBtn")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy)

        close_btn = QPushButton("✕  CLOSE")
        close_btn.setObjectName("closeBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)

        layout.addWidget(copy_btn)
        layout.addWidget(close_btn)
        return frame

    def _copy(self):
        QApplication.clipboard().setText(self.entry.formula_text)
        show_notification("Formula extracted from system memory", "success")

    def _apply_styles(self):
        self.setStyleSheet("""
            #mainContainer {
                background-color: rgba(18, 18, 18, 245);
                border: 2px solid #3B82F6;
                border-radius: 20px;
            }

            #titleLabel {
                font-size: 26px;
                font-weight: bold;
                color: #3B82F6;
                letter-spacing: 3px;
                padding-bottom: 8px;
            }

            #formulaBox {
                background-color: #161616;
                border: 1px solid #3B82F6;
                border-radius: 16px;
            }

            #metaFrame {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 14px;
            }

            #metaChip {
                background-color: #1C1C1C;
                border: 1px solid #2A2A2A;
                border-radius: 12px;
                min-width: 140px;
            }

            #metaChip:hover {
                border-color: #3B82F6;
            }

            #sectionTitle {
                font-size: 16px;
                color: #888;
                font-weight: bold;
                letter-spacing: 2px;
                padding-top: 8px;
            }

            #tagsFrame {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 12px;
            }

            #tagChip {
                background-color: #2563EB;
                color: white;
                padding: 6px 14px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 500;
            }

            #notesFrame {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-left: 4px solid #F59E0B;
                border-radius: 12px;
            }

            #notesText {
                color: #D1D5DB;
                font-size: 14px;
                line-height: 1.6;
            }

            #varsFrame {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 14px;
            }

            #varCard {
                background-color: #1C1C1C;
                border: 1px solid #2A2A2A;
                border-left: 4px solid #3B82F6;
                border-radius: 10px;
            }

            #varCard:hover {
                background-color: #222222;
                border-color: #3B82F6;
            }

            #varSymbol {
                font-size: 20px;
                color: #3B82F6;
                font-weight: bold;
                min-width: 32px;
            }

            #varName {
                color: #ECECEC;
                font-size: 14px;
            }

            #varUnit {
                color: #888;
                font-size: 13px;
                font-style: italic;
                min-width: 60px;
            }

            #emptyFrame {
                background-color: #161616;
                border: 1px solid #2A2A2A;
                border-radius: 14px;
            }

            #emptyLabel {
                color: #555;
                font-size: 14px;
                letter-spacing: 2px;
            }

            #btnFrame {
                border-top: 1px solid #2A2A2A;
            }

            #copyBtn {
                background-color: #1C1C1C;
                color: #3B82F6;
                border: 1px solid #3B82F6;
                padding: 12px 24px;
                border-radius: 10px;
                font-weight: bold;
                font-size: 13px;
            }

            #copyBtn:hover {
                background-color: #3B82F6;
                color: #121212;
            }

            #closeBtn {
                background-color: #1C1C1C;
                color: #ECECEC;
                border: 1px solid #444;
                padding: 12px 24px;
                border-radius: 10px;
                font-weight: bold;
                font-size: 13px;
            }

            #closeBtn:hover {
                background-color: #2A2A2A;
                border-color: #666;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollBar:vertical {
                width: 10px;
                background: #161616;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                background: #3B82F6;
                border-radius: 5px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #60A5FA;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                height: 10px;
                background: #161616;
                border-radius: 5px;
            }

            QScrollBar::handle:horizontal {
                background: #3B82F6;
                border-radius: 5px;
                min-width: 30px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #60A5FA;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
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

    @staticmethod
    def _setup_opacity_effect(widget: QWidget, initial_opacity: float):
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

    @staticmethod
    def _safe_enable(widget: QWidget):
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

        self.in_anim = QPropertyAnimation(self, b"pos")
        self.out_anim = QPropertyAnimation(self, b"pos")

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

        self.in_anim.setDuration(350)
        self.in_anim.setStartValue(self._hidden_position())
        self.in_anim.setEndValue(self._target_position())
        self.in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.in_anim.start()

        self.in_anim.finished.connect(
            lambda: QTimer.singleShot(3500, self.slide_out)
        )

    def slide_out(self):
        self.out_anim.setDuration(300)
        self.out_anim.setStartValue(self.pos())
        self.out_anim.setEndValue(self._hidden_position())
        self.out_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        self.out_anim.finished.connect(self.deleteLater)
        self.out_anim.start()
