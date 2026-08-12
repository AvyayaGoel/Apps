"""
Reusable PyQt6 widgets and background workers for the Ultimate Tic-Tac-Toe UI.
"""

import logging
import sqlite3
import threading
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QRectF, QThread, pyqtSignal, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QSizePolicy, QGraphicsDropShadowEffect, QPushButton,
    QScrollArea,
)

import engine
from bots import BOT_PROFILES, analyze_game, analyze_single_move, BotProfile
from database import load_games, delete_game
from engine import UltimateBoard, X, O, DRAW
from history import GameHistory

logger = logging.getLogger(__name__)

# ─── Palette ──────────────────────────────────────────────────────────

BG = "#14141c"
BG_ALT = "#1b1b26"
SURFACE = "#22222f"
SURFACE_HOVER = "#2b2b3b"
BORDER = "#34344a"
TEXT = "#e9e9f2"
TEXT_DIM = "#9a9ab0"
ACCENT = "#5ad1ff"  # X colour
ACCENT_2 = "#ff6f91"  # O colour
ACCENT_GOOD = "#54e0a5"
WARN = "#ffb347"

FONT_FAMILY = "Segoe UI, Helvetica Neue, Arial"
FONT_FAMILY_QT = "Segoe UI"


def make_shadow(blur=24, alpha=140, dy=6):
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    return eff


GLOBAL_STYLE = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: {FONT_FAMILY};
}}
QLabel#title {{
    font-size: 34px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#subtitle {{
    font-size: 14px;
    color: {TEXT_DIM};
}}
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 22px;
    font-size: 15px;
    font-weight: 600;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
    border: 1px solid {ACCENT};
}}
QPushButton:pressed {{
    background-color: #191925;
}}
QPushButton#primary {{
    background-color: {ACCENT};
    color: #06131a;
    border: none;
}}
QPushButton#primary:hover {{
    background-color: #7bdcff;
}}
QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QPushButton#ghost:hover {{
    color: {TEXT};
    border: 1px solid {TEXT_DIM};
}}
QFrame#card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#card:hover {{
    border: 1px solid {ACCENT};
}}
QScrollArea {{
    border: none;
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: {BORDER};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: {BORDER};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {TEXT};
    border: 2px solid {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT};
    border: 2px solid {TEXT};
}}
QPushButton#navArrow {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0px;
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QPushButton#navArrow:hover {{
    background-color: {SURFACE_HOVER};
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}
QPushButton#navArrow:disabled {{
    color: {BORDER};
    border: 1px solid {BORDER};
}}
QFrame#sidebar {{
    background-color: {BG_ALT};
    border-right: 1px solid {BORDER};
}}
QPushButton#navBtn {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px;
    font-size: 15px;
    font-weight: 600;
    color: {TEXT_DIM};
    text-align: left;
}}
QPushButton#navBtn:hover {{
    background-color: {SURFACE_HOVER};
    color: {TEXT};
}}
QPushButton#navBtn:checked {{
    background-color: {SURFACE};
    color: {ACCENT};
}}
"""


# ─── Board widget ────────────────────────────────────────────────────

class BoardWidget(QWidget):
    cellClicked = pyqtSignal(int, int)

    def __init__(self, parent=None, align_left: bool = False):
        super().__init__(parent)
        self.board: Optional[UltimateBoard] = None
        self.interactive = True
        self.align_left = align_left
        self.setMinimumSize(480, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._hover_cell: Optional[tuple] = None
        self._suggested_cell: Optional[tuple] = None
        self._blunder_cell: Optional[tuple] = None

    def set_board(self, board: UltimateBoard):
        self.board = board
        self.update()

    def set_interactive(self, flag: bool):
        self.interactive = flag
        if not flag:
            self._hover_cell = None
        self.update()

    def set_suggestion(self, suggested_cell: Optional[tuple], blunder_cell: Optional[tuple]):
        self._suggested_cell = suggested_cell
        self._blunder_cell = blunder_cell
        self.update()

    def _board_rect(self) -> QRectF:
        side = min(self.width(), self.height()) - 4
        side = max(side, 60)
        x = 2.0 if self.align_left else (self.width() - side) / 2
        y = (self.height() - side) / 2
        return QRectF(x, y, side, side)

    def _cell_rect(self, sub_idx: int, cell_idx: int) -> QRectF:
        rect = self._board_rect()
        super_size = rect.width() / 3
        cell_size = super_size / 3
        sr, sc = divmod(sub_idx, 3)
        cr, cc = divmod(cell_idx, 3)
        x = rect.x() + sc * super_size + cc * cell_size
        y = rect.y() + sr * super_size + cr * cell_size
        return QRectF(x, y, cell_size, cell_size)

    def _sub_rect(self, sub_idx: int) -> QRectF:
        rect = self._board_rect()
        super_size = rect.width() / 3
        sr, sc = divmod(sub_idx, 3)
        return QRectF(rect.x() + sc * super_size, rect.y() + sr * super_size, super_size, super_size)

    def _pos_to_cell(self, pos: QPointF) -> Optional[tuple]:
        rect = self._board_rect()
        if not rect.contains(pos):
            return None
        super_size = rect.width() / 3
        cell_size = super_size / 3
        col = int((pos.x() - rect.x()) // super_size)
        row = int((pos.y() - rect.y()) // super_size)
        col = min(max(col, 0), 2)
        row = min(max(row, 0), 2)
        sub_idx = row * 3 + col

        local_x = (pos.x() - rect.x()) - col * super_size
        local_y = (pos.y() - rect.y()) - row * super_size
        cc = int(local_x // cell_size)
        cr = int(local_y // cell_size)
        cc = min(max(cc, 0), 2)
        cr = min(max(cr, 0), 2)
        cell_idx = cr * 3 + cc
        return sub_idx, cell_idx

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.board is None:
            return

        valid_boards = set(self.board.get_valid_boards())

        for sub_idx in range(9):
            self._paint_sub_board(painter, sub_idx, sub_idx in valid_boards)

        self._paint_super_grid(painter)
        self._paint_overlays(painter)

    def _paint_overlays(self, painter: QPainter):
        if self._suggested_cell is not None:
            cr = self._cell_rect(*self._suggested_cell)
            pad = cr.width() * 0.14
            ring_rect = cr.adjusted(pad, pad, -pad, -pad)
            pen = QPen(QColor(WARN))
            pen.setWidthF(max(cr.width() * 0.06, 2.0))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring_rect)

        if self._blunder_cell is not None:
            cr = self._cell_rect(*self._blunder_cell)
            badge = cr.width() * 0.32
            badge_rect = QRectF(cr.right() - badge * 0.85, cr.top() - badge * 0.15, badge, badge)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENT_2))
            painter.drawEllipse(badge_rect)
            painter.setPen(QColor("#1a0508"))
            f = QFont(FONT_FAMILY_QT, max(int(badge * 0.62), 8), QFont.Weight.Bold)
            painter.setFont(f)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "!")

    def _paint_super_grid(self, painter: QPainter):
        rect = self._board_rect()
        pen = QPen(QColor(TEXT_DIM))
        pen.setWidthF(4.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        super_size = rect.width() / 3
        for i in (1, 2):
            x = rect.x() + i * super_size
            painter.drawLine(QPointF(x, rect.y()), QPointF(x, rect.y() + rect.height()))
            y = rect.y() + i * super_size
            painter.drawLine(QPointF(rect.x(), y), QPointF(rect.x() + rect.width(), y))
        outer_pen = QPen(QColor(BORDER))
        outer_pen.setWidthF(2.0)
        painter.setPen(outer_pen)
        painter.drawRoundedRect(rect, 6, 6)

    def _paint_sub_board(self, painter: QPainter, sub_idx: int, is_active: bool):
        rect = self._sub_rect(sub_idx)
        winner = self.board.sub_winners[sub_idx]

        if winner == X:
            bg = QColor(ACCENT);
            bg.setAlpha(28)
        elif winner == O:
            bg = QColor(ACCENT_2);
            bg.setAlpha(28)
        elif winner == DRAW:
            bg = QColor(TEXT_DIM);
            bg.setAlpha(18)
        elif is_active and self.interactive:
            bg = QColor(ACCENT);
            bg.setAlpha(16)
        else:
            bg = QColor(0, 0, 0, 0)
        if bg.alpha() > 0:
            painter.fillRect(rect, bg)

        if is_active and self.interactive and winner is None:
            pen = QPen(QColor(ACCENT))
            pen.setWidthF(2.4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = rect.adjusted(2, 2, -2, -2)
            painter.drawRoundedRect(inset, 8, 8)

        pen = QPen(QColor(BORDER))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        cell = rect.width() / 3
        for i in (1, 2):
            x = rect.x() + i * cell
            painter.drawLine(QPointF(x, rect.y() + 4), QPointF(x, rect.y() + rect.height() - 4))
            y = rect.y() + i * cell
            painter.drawLine(QPointF(rect.x() + 4, y), QPointF(rect.x() + rect.width() - 4, y))

        if winner in (X, O):
            self._draw_symbol(painter, rect.adjusted(rect.width() * 0.12, rect.height() * 0.12,
                                                     -rect.width() * 0.12, -rect.height() * 0.12),
                              winner, alpha=235, width_scale=0.11)
            return
        if winner == DRAW:
            painter.setPen(QPen(QColor(TEXT_DIM), 3))
            f = QFont(FONT_FAMILY_QT, int(rect.height() * 0.18), QFont.Weight.Bold)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
            return

        cells = self.board.sub_boards[sub_idx]
        for c_idx, val in enumerate(cells):
            if val == engine.EMPTY:
                continue
            cr = self._cell_rect(sub_idx, c_idx)
            pad = cr.width() * 0.2
            self._draw_symbol(painter, cr.adjusted(pad, pad, -pad, -pad), val,
                              alpha=235, width_scale=0.14)

        if self._hover_cell and self.interactive:
            h_sub, h_cell = self._hover_cell
            if h_sub == sub_idx and is_active and winner is None and cells[h_cell] == engine.EMPTY:
                hr = self._cell_rect(sub_idx, h_cell)
                painter.fillRect(hr.adjusted(2, 2, -2, -2), QColor(255, 255, 255, 14))

    def _draw_symbol(self, painter: QPainter, rect: QRectF, player: int,
                     alpha: int = 255, width_scale: float = 0.14):
        w = max(rect.width(), 8)
        pen_width = max(w * width_scale, 2.0)
        if player == X:
            color = QColor(ACCENT)
            color.setAlpha(alpha)
            pen = QPen(color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
        else:
            color = QColor(ACCENT_2)
            color.setAlpha(alpha)
            pen = QPen(color, pen_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)

    def mouseMoveEvent(self, event):
        if not self.interactive or self.board is None:
            return
        hit = self._pos_to_cell(event.position())
        if hit != self._hover_cell:
            self._hover_cell = hit
            self.update()

    def leaveEvent(self, event):
        self._hover_cell = None
        self.update()

    def mousePressEvent(self, event):
        if not self.interactive or self.board is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._pos_to_cell(event.position())
        if hit is None:
            return
        sub_idx, cell_idx = hit
        if self.board.is_move_legal(sub_idx, cell_idx):
            self.cellClicked.emit(sub_idx, cell_idx)


EMPTY_VAL = engine.EMPTY
_COL_LETTERS = "ABC"


def _cell_label(idx: int) -> str:
    r, c = divmod(idx, 3)
    return f"{_COL_LETTERS[c]}{r + 1}"


def move_to_notation(move: Optional[tuple]) -> str:
    if move is None:
        return "\u2014"
    sub_idx, cell_idx = move
    return f"{_cell_label(sub_idx)}/{_cell_label(cell_idx)}"


# ─── Eval Bar ────────────────────────────────────────────────────────

class EvalBar(QWidget):
    """A chess.com-style vertical evaluation bar. Fills from the CENTER:
    positive (X-favouring) scores push a blue band up from the middle,
    negative (O-favouring) scores push a pink band down from the middle.
    Range is -10.00..+10.00 (pawn-style units, not raw engine points).
    A forced mate overrides the numeric display with '#N' and fills the
    whole bar solid toward the mating side."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(34)
        self.setMinimumHeight(240)
        self._current = 0.0  # displayed value, animates toward _target
        self._target = 0.0
        self._mate: Optional[int] = None
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def set_eval(self, value: float, mate: Optional[int] = None):
        self._mate = mate
        self._target = 10.0 if (mate is not None and mate > 0) else (
            -10.0 if (mate is not None and mate < 0) else max(-10.0, min(10.0, value))
        )
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self):
        diff = self._target - self._current
        if abs(diff) < 0.02:
            self._current = self._target
            self._timer.stop()
        else:
            self._current += diff * 0.22
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(path)
        painter.fillRect(rect, QColor(BG_ALT))

        h = rect.height()
        mid_y = rect.y() + h / 2
        # Fraction of the HALF-bar filled, 0..1, driven by |value|/10.
        frac = min(1.0, abs(self._current) / 10.0) * (h / 2)

        if self._current >= 0:
            band = QRectF(rect.x(), mid_y - frac, rect.width(), frac)
            painter.fillRect(band, QColor(ACCENT))
        else:
            band = QRectF(rect.x(), mid_y, rect.width(), frac)
            painter.fillRect(band, QColor(ACCENT_2))

        # Center line, always visible so "0.00" reads as a clear midpoint.
        mid_pen = QPen(QColor(BG))
        mid_pen.setWidthF(1.5)
        painter.setPen(mid_pen)
        painter.drawLine(QPointF(rect.x(), mid_y), QPointF(rect.x() + rect.width(), mid_y))
        painter.setClipping(False)

        pen = QPen(QColor(BORDER), 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)

        if self._mate is not None:
            label = f"W{abs(self._mate)}"
            label_at_top = self._mate > 0
        else:
            label = f"{self._current:+.2f}"
            label_at_top = self._current >= 0

        text_y = (rect.y() + 14) if label_at_top else (rect.y() + rect.height() - 18)
        painter.setPen(QColor(TEXT))
        f = QFont(FONT_FAMILY_QT, 8, QFont.Weight.Bold)
        painter.setFont(f)
        painter.drawText(QRectF(rect.x() - 6, text_y, rect.width() + 12, 16),
                         Qt.AlignmentFlag.AlignCenter, label)


# ─── Workers ─────────────────────────────────────────────────────────

class BotWorker(QThread):
    moveReady = pyqtSignal(int, int)

    def __init__(self, bot, board_snapshot: UltimateBoard, parent: QWidget):
        super().__init__(parent)
        self.bot = bot
        self.board_snapshot = board_snapshot
        # Cooperative cancellation: checked deep inside the search's
        # deadline check, not just at the top level. This lets callers
        # ask the thread to stop and then `wait()` for it -- normally in
        # well under a second -- instead of calling QThread.terminate(),
        # which can kill the thread mid-write to the shared SQLite cache
        # or mid-mutation of shared state and crash the app.
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        logger.debug("BotWorker started")
        try:
            move = self.bot.choose_move(self.board_snapshot, cancel_event=self._cancel_event)
            if self._cancel_event.is_set():
                logger.debug("BotWorker: cancelled")
                return
            if move is None:
                logger.debug("BotWorker: no move returned")
                return
            logger.debug(f"BotWorker: moveReady emitted: {move}")
            self.moveReady.emit(move[0], move[1])
        except Exception as e:
            logger.exception("BotWorker error: %s", e, exc_info=True)
        logger.debug("BotWorker finished")


class SingleMoveWorker(QThread):
    moveAnalyzed = pyqtSignal(int)

    def __init__(self, history: GameHistory, idx: int, depth: int = 40, time_limit: float = 1.0, parent=None):
        super().__init__(parent)
        self.history = history
        self.idx = idx
        self.depth = depth
        self.time_limit = time_limit
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            analyze_single_move(self.history, self.idx, self.depth, self.time_limit,
                                cancel_event=self._cancel_event)
            if self._cancel_event.is_set():
                return
            self.moveAnalyzed.emit(self.idx)
        except Exception as e:
            logger.exception("SingleMoveWorker error for move %d: %s", self.idx, e, exc_info=True)


class GameAnalysisWorker(QThread):
    progress = pyqtSignal(int, int)
    finished_analysis = pyqtSignal()

    def __init__(self, history: GameHistory, parent: QWidget):
        super().__init__(parent)
        self.history = history
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            analyze_game(self.history, depth=10, time_limit=3.0, progress_cb=self._emit_progress,
                         cancel_event=self._cancel_event)
            if self._cancel_event.is_set():
                return
            self.finished_analysis.emit()
        except Exception as e:
            logger.exception("GameAnalysisWorker error: %s", e, exc_info=True)

    def _emit_progress(self, done: int, total: int):
        self.progress.emit(done, total)


# ─── Bot cards ──────────────────────────────────────────────────────

class BotCard(QFrame):
    def __init__(self, profile: BotProfile, on_pick, selectable: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setGraphicsEffect(make_shadow(blur=18, alpha=110, dy=4))
        self.selectable = selectable
        self._selected = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(profile.name)
        name.setStyleSheet("font-size: 18px; font-weight: 700;")
        top.addWidget(name)
        top.addStretch(1)

        rating = QLabel(f"{profile.elo}")
        rating.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {BG}; "
            f"background-color: {_rating_color(profile.elo)}; "
            "border-radius: 8px; padding: 3px 10px;"
        )
        top.addWidget(rating)
        outer.addLayout(top)

        desc = QLabel(profile.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12.5px;")
        outer.addWidget(desc)

        self._on_pick = on_pick
        self._key = profile.key

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_pick(self._key)

    def set_selected(self, flag: bool):
        self._selected = flag
        if flag:
            self.setStyleSheet(
                f"QFrame#card {{ background-color: {SURFACE_HOVER}; "
                f"border: 2px solid {ACCENT}; border-radius: 14px; }}"
            )
        else:
            self.setStyleSheet("")


def _rating_color(elo: int) -> str:
    if elo < 900:
        return "#8fe3a5"
    if elo < 1300:
        return "#a8d8ff"
    if elo < 1700:
        return "#ffd27f"
    if elo < 2100:
        return "#ffb0c8"
    if elo < 2350:
        return "#d6b3ff"
    return "#ff9d9d"


TIER_ORDER = ("Beginner", "Intermediate", "Advanced", "Master")


def elo_tier(elo: int) -> str:
    if elo < 1100:
        return "Beginner"
    if elo < 1700:
        return "Intermediate"
    if elo < 2300:
        return "Advanced"
    return "Master"


def group_by_tier(profiles) -> List[tuple]:
    groups: Dict[str, list] = {t: [] for t in TIER_ORDER}
    for p in sorted(profiles, key=lambda p: p.elo):
        groups[elo_tier(p.elo)].append(p)
    return [(t, groups[t]) for t in TIER_ORDER if groups[t]]


class TieredBotGrid(QWidget):
    def __init__(self, on_pick, selectable: bool = False, initial_key: Optional[str] = None,
                 columns: int = 3, parent=None):
        super().__init__(parent)
        self.on_pick = on_pick
        self.selectable = selectable
        self.selected_key = initial_key
        self._cards: Dict[str, BotCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(20)

        for tier_name, profiles in group_by_tier(BOT_PROFILES):
            header = QLabel(f"{tier_name.upper()}   \u00b7   {profiles[0].elo}\u2013{profiles[-1].elo} rating")
            header.setStyleSheet(
                f"font-size: 12px; font-weight: 800; color: {TEXT_DIM}; letter-spacing: 1.5px;"
            )
            outer.addWidget(header)

            grid = QGridLayout()
            grid.setSpacing(14)
            for i, profile in enumerate(profiles):
                card = BotCard(profile, self._handle_pick, selectable=selectable)
                self._cards[profile.key] = card
                row, col = divmod(i, columns)
                grid.addWidget(card, row, col)
            outer.addLayout(grid)

        outer.addStretch(1)

        if self.selectable and self.selected_key:
            self._refresh_selection()

    def _handle_pick(self, key: str):
        if self.selectable:
            self.selected_key = key
            self._refresh_selection()
        self.on_pick(key)

    def _refresh_selection(self):
        for key, card in self._cards.items():
            card.set_selected(key == self.selected_key)


# ─── Status bar ─────────────────────────────────────────────────────

class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.turn_dot = QLabel()
        self.turn_dot.setFixedSize(14, 14)
        self.turn_label = QLabel("")
        self.turn_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        layout.addWidget(self.turn_dot)
        layout.addSpacing(8)
        layout.addWidget(self.turn_label)
        layout.addStretch(1)

    def set_turn(self, text: str, color: str):
        self.turn_label.setText(text)
        self.turn_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 7px;"
        )


# ─── Sidebar ─────────────────────────────────────────────────────────

class Sidebar(QFrame):
    """Persistent, collapsible chess.com-style nav rail."""

    pageRequested = pyqtSignal(str)

    NAV_ITEMS = [
        ("play", "\u25B6", "Play"),
        ("history", "\U0001F5C2", "History"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._collapsed = False
        self._width_full = 216
        self._width_collapsed = 68
        self.setFixedWidth(self._width_full)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 18, 10, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        self.brand_icon = QLabel("\u2317")
        self.brand_icon.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {ACCENT};")
        brand_row.addWidget(self.brand_icon)
        self.brand_label = QLabel("Ultimate\nTic-Tac-Toe")
        self.brand_label.setStyleSheet(f"font-size: 12.5px; font-weight: 800; color: {TEXT}; line-height: 120%;")
        brand_row.addWidget(self.brand_label)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)

        layout.addSpacing(14)

        self.toggle_btn = QPushButton("\u2261   Collapse")
        self.toggle_btn.setObjectName("navBtn")
        self.toggle_btn.setFixedHeight(40)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(divider)
        layout.addSpacing(10)

        self.nav_buttons: Dict[str, QPushButton] = {}
        self._labels: Dict[str, str] = {}
        for key, icon, label in self.NAV_ITEMS:
            btn = QPushButton(f"{icon}   {label}")
            btn.setObjectName("navBtn")
            btn.setFixedHeight(46)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._on_nav(k))
            self.nav_buttons[key] = btn
            self._labels[key] = f"{icon}   {label}"
            layout.addWidget(btn)

        layout.addStretch(1)

        self._set_collapsed(False)

    def _on_nav(self, key: str):
        self.set_active(key)
        self.pageRequested.emit(key)

    def _toggle(self):
        self._set_collapsed(not self._collapsed)

    def _set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.setFixedWidth(self._width_collapsed if collapsed else self._width_full)
        self.brand_label.setVisible(not collapsed)
        self.toggle_btn.setText("\u2261" if collapsed else "\u2261   Collapse")
        for key, btn in self.nav_buttons.items():
            icon = self._labels[key].split()[0]
            btn.setText(icon if collapsed else self._labels[key])

    def set_active(self, key: str):
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)


# ─── History List Page ───────────────────────────────────────────────

_WINNER_BADGE = {
    1: ("X WINS", ACCENT),
    2: ("O WINS", ACCENT_2),
    3: ("DRAW", TEXT_DIM),
}

_MODE_LABEL = {"friend": "Friend", "pc": "vs Computer", "ai_vs_ai": "AI vs AI"}


class HistoryRow(QFrame):
    """One row in the game history list: players + a short summary line on
    the left, a winner badge and delete button on the right."""

    clicked = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)

    def __init__(self, row: sqlite3.Row, parent=None):
        super().__init__(parent)
        self.game_id = row["id"]
        self.setObjectName("historyRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame#historyRow {{ background-color: {BG_ALT}; border: 1px solid {BORDER}; "
            f"border-radius: 10px; }}"
            f"QFrame#historyRow:hover {{ border: 1px solid {ACCENT}; background-color: {SURFACE}; }}"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 10, 10)
        outer.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(f"{row['player_x']}  vs  {row['player_o']}")
        title.setStyleSheet(f"font-size: 14.5px; font-weight: 700; color: {TEXT};")
        text_col.addWidget(title)

        mode = _MODE_LABEL.get(row["mode"], row["mode"])
        when = str(row["timestamp"])[:16].replace("T", "  ")
        subtitle = QLabel(f"{mode}  \u00b7  {when}")
        subtitle.setStyleSheet(f"font-size: 11.5px; color: {TEXT_DIM};")
        text_col.addWidget(subtitle)
        outer.addLayout(text_col, 1)

        badge_text, badge_color = _WINNER_BADGE.get(row["winner"], ("\u2014", TEXT_DIM))
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"font-size: 11px; font-weight: 800; color: {BG}; background-color: {badge_color}; "
            "border-radius: 7px; padding: 4px 10px;"
        )
        outer.addWidget(badge)

        delete_btn = QPushButton("\u2715")
        delete_btn.setObjectName("ghost")
        delete_btn.setFixedSize(30, 30)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.game_id))
        outer.addWidget(delete_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.game_id)


class HistoryListPage(QWidget):
    gameSelected = pyqtSignal(int)

    def __init__(self, on_back, parent=None):
        super().__init__(parent)
        self.on_back = on_back

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 30, 36, 30)
        outer.setSpacing(14)

        header = QHBoxLayout()
        back_btn = QPushButton("\u2190 Back")
        back_btn.setObjectName("ghost")
        back_btn.setFixedWidth(100)
        back_btn.clicked.connect(on_back)
        header.addWidget(back_btn)
        header.addStretch(1)

        title = QLabel("Game History")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title)
        header.addStretch(1)
        header.addSpacing(100)  # balance the back button so the title stays centered
        outer.addLayout(header)

        self.empty_label = QLabel("No games saved yet -- play one and it'll show up here.")
        self.empty_label.setObjectName("subtitle")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        outer.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(2, 2, 2, 2)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_container)
        outer.addWidget(self.scroll, 1)

        self._rows: List[sqlite3.Row] = []

    def refresh(self):
        # Clear existing row widgets (leave the trailing stretch in place).
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        try:
            self._rows = load_games(limit=200)
        except Exception as e:
            logger.exception("Failed to refresh history: %s", e, exc_info=True)
            self._rows = []

        self.empty_label.setVisible(len(self._rows) == 0)
        for row in self._rows:
            widget = HistoryRow(row)
            widget.clicked.connect(self.gameSelected.emit)
            widget.deleteRequested.connect(self._delete_row)
            self.list_layout.insertWidget(self.list_layout.count() - 1, widget)

    def _delete_row(self, game_id: int):
        delete_game(game_id)
        self.refresh()
