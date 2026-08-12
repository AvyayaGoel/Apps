"""
Ultimate Tic-Tac-Toe — PyQt6 front end with live analysis, sidebar, DB persistence.
"""

import logging
import secrets
import sys
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QTimer, QCoreApplication, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider, QListWidget,
    QListWidgetItem, QSizePolicy
)

# Set app identity early
QCoreApplication.setApplicationName("UltimateTicTacToe")
QCoreApplication.setOrganizationName("Avyaya")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

from engine import UltimateBoard, X, O, DRAW, other_player
from bots import BOT_PROFILES, make_bot, Bot, BotProfile
from history import GameHistory
from widgets import (
    BG, BG_ALT, SURFACE, SURFACE_HOVER, BORDER, TEXT, TEXT_DIM,
    ACCENT, ACCENT_2, ACCENT_GOOD, WARN, GLOBAL_STYLE,
    make_shadow, move_to_notation, BoardWidget, EvalBar, StatusBar,
    BotWorker, GameAnalysisWorker, TieredBotGrid, Sidebar, HistoryListPage,
    SingleMoveWorker,
)

import database

database.init_db()


# ─── Helpers ─────────────────────────────────────────────────────────

def _winner_name(winner: int, mode: str, human: Optional[int], profiles: Dict[int, BotProfile]) -> str:
    if winner == DRAW:
        return "Draw"
    if mode == "friend":
        return f"Player {'X' if winner == X else 'O'}"
    if mode == "pc":
        if winner == human:
            return "You"
        p = profiles.get(winner)
        return p.name if p else "Bot"
    p = profiles.get(winner)
    return p.name if p else "Bot"


def _blunder_message(entry) -> str:
    """Human-readable explanation for a flagged blunder: distinguishes
    missing a forced mate, walking into one, or an ordinary eval-losing
    move, since a raw point count doesn't mean much once mates are
    involved."""
    if not entry.is_blunder:
        return ""

    mover = entry.player

    def favorable(mate: Optional[int]) -> Optional[int]:
        if mate is None:
            return None
        return mate if mover == X else -mate

    fav_best = favorable(entry.mate_if_best)
    fav_after = favorable(entry.mate_after)

    if fav_best is not None and fav_best > 0 and not (fav_after is not None and fav_after > 0):
        return "❗ Missed a forced win!"
    if fav_after is not None and fav_after < 0:
        return f"❗ Blunder — allows a forced win in {abs(fav_after)} moves"
    return "❗ Blunder"


# ─── Play Page (board + move list) ──────────────────────────────────

class PlayPage(QWidget):
    requestBotSelection = pyqtSignal()
    requestAISelection = pyqtSignal()

    def __init__(self, on_main_menu, on_game_over, parent=None):
        super().__init__(parent)
        self.on_main_menu = on_main_menu
        self.on_game_over = on_game_over

        self.mode = "friend"
        self.human_player: Optional[int] = X
        self.bots: Dict[int, Bot] = {}
        self.bot_profiles: Dict[int, BotProfile] = {}
        self.board = UltimateBoard()
        self.history = GameHistory()
        self.worker: Optional[BotWorker] = None
        self._game_over_shown = False
        self._end_summary = ""
        self._game_id = 0
        self._db_game_id: Optional[int] = None
        self._analysis_workers = []
        self._pending_timers = []
        self._review_timer = QTimer(self)
        self._review_timer.setSingleShot(True)

        # Main layout: board left, move list right
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # Left: board area
        left = QVBoxLayout()
        left.setContentsMargins(20, 16, 20, 16)
        left.setSpacing(10)

        header = QHBoxLayout()
        back_btn = QPushButton("← Menu")
        back_btn.setObjectName("ghost")
        back_btn.setFixedWidth(100)
        back_btn.clicked.connect(self._show_mode_selection)
        header.addWidget(back_btn)
        header.addStretch(1)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet(f"font-size: 16px; color: {TEXT_DIM};")
        header.addWidget(self.title_label)
        header.addStretch(1)

        restart_btn = QPushButton("Restart")
        restart_btn.setFixedWidth(110)
        restart_btn.clicked.connect(self.restart)
        header.addWidget(restart_btn)
        left.addLayout(header)

        self.status_bar = StatusBar()
        left.addWidget(self.status_bar)

        self.board_widget = BoardWidget()
        self.board_widget.cellClicked.connect(self._handle_cell_clicked)
        left.addWidget(self.board_widget, 1)

        self.thinking_label = QLabel("")
        self.thinking_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thinking_label.setStyleSheet(f"color: {WARN}; font-size: 13px; font-style: italic;")
        left.addWidget(self.thinking_label)

        hbox.addLayout(left, 3)

        # Right: move list
        self.right_stack = QStackedWidget()
        self.right_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Page 0: Mode selection buttons
        mode_widget = QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        mode_layout.setContentsMargins(20, 40, 20, 40)
        mode_layout.setSpacing(20)
        mode_layout.addStretch(1)

        friend_btn = QPushButton("👥 Play with a Friend")
        friend_btn.setMinimumHeight(60)
        friend_btn.clicked.connect(self._start_friend)
        mode_layout.addWidget(friend_btn)

        pc_btn = QPushButton("🤖 Play vs Computer")
        pc_btn.setMinimumHeight(60)
        pc_btn.clicked.connect(self._start_pc)
        mode_layout.addWidget(pc_btn)

        ai_btn = QPushButton("⚔️ AI vs AI")
        ai_btn.setMinimumHeight(60)
        ai_btn.clicked.connect(self._start_ai_vs_ai)
        mode_layout.addWidget(ai_btn)

        mode_layout.addStretch(1)
        self.right_stack.addWidget(mode_widget)

        moves_widget = QWidget()
        moves_layout = QVBoxLayout(moves_widget)
        moves_layout.setContentsMargins(16, 20, 20, 20)
        moves_layout.setSpacing(12)
        moves_title = QLabel("Moves")
        moves_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        moves_layout.addWidget(moves_title)
        self.move_list = QListWidget()
        self.move_list.setStyleSheet(
            f"QListWidget {{ background-color: {BG_ALT}; border: 1px solid {BORDER}; border-radius: 8px; }}"
            f"QListWidget::item {{ padding: 7px 10px; }}"
            f"QListWidget::item:selected {{ background-color: {SURFACE_HOVER}; color: {TEXT}; }}"
        )
        moves_layout.addWidget(self.move_list, 1)
        self.move_counter_label = QLabel("Move 0 / 0")
        self.move_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.move_counter_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        moves_layout.addWidget(self.move_counter_label)
        self.right_stack.addWidget(moves_widget)

        hbox.addWidget(self.right_stack, 1)

    # ─── Setup ──────────────────────────────────────────────────────

    def _start_friend(self):
        self.start_friend_game()
        # restart() will switch the right panel to moves

    def _start_pc(self):
        self.requestBotSelection.emit()

    def _start_ai_vs_ai(self):
        self.requestAISelection.emit()

    def start_friend_game(self):
        self.mode = "friend"
        self.human_player = None
        self.bots = {}
        self.bot_profiles = {}
        self.title_label.setText("Player vs Player")
        self.restart()

    def start_pc_game(self, profile_key: str):
        self.mode = "pc"
        self.human_player = X
        opponent = other_player(self.human_player)
        profile = next(p for p in BOT_PROFILES if p.key == profile_key)
        self.bot_profiles = {opponent: profile}
        self.bots = {opponent: make_bot(profile_key, opponent)}
        self.title_label.setText(f"You vs {profile.name}  •  {profile.elo} rating")
        self.restart()

    def start_ai_vs_ai_game(self, key_x: str, key_o: str):
        self.mode = "ai_vs_ai"
        self.human_player = None
        profile_x = next(p for p in BOT_PROFILES if p.key == key_x)
        profile_o = next(p for p in BOT_PROFILES if p.key == key_o)
        self.bot_profiles = {X: profile_x, O: profile_o}
        self.bots = {X: make_bot(key_x, X), O: make_bot(key_o, O)}
        self.title_label.setText(
            f"{profile_x.name} ({profile_x.elo}) vs {profile_o.name} ({profile_o.elo})"
        )
        self.restart()

    def _detach_worker(self):
        if self.worker is not None:
            try:
                self.worker.moveReady.disconnect(self._apply_bot_move)
            except TypeError:
                pass
            self.worker = None

    def restart(self, start_bot: bool = True):
        # Cancel pending timers
        for timer in self._pending_timers:
            if timer.isActive():
                timer.stop()
        self._pending_timers.clear()

        # Stop review timer – do NOT set to None
        self._review_timer.stop()
        try:
            self._review_timer.timeout.disconnect(self._go_review)
        except TypeError:
            pass

        # Stop bot worker. cancel() + wait() lets the search notice the
        # request (checked on every node it visits) and unwind cleanly,
        # instead of QThread.terminate() -- which can kill the thread
        # mid-write to the shared SQLite cache and crash the app.
        if self.worker is not None:
            logger.debug("Cancelling bot worker")
            self.worker.cancel()
            self.worker.wait()
            self._detach_worker()
            logger.debug("Bot worker stopped")

        # Stop analysis workers the same cooperative way.
        for w in self._analysis_workers:
            w.cancel()
            w.wait()
        self._analysis_workers.clear()

        self._game_id += 1
        logger.debug(f"New game_id: {self._game_id}")

        self.board = UltimateBoard()
        self.history = GameHistory()
        self._game_over_shown = False
        self._db_game_id = None
        self.board_widget.set_board(self.board)
        self.board_widget.set_interactive(True)
        self.thinking_label.setText("")
        self.move_list.clear()
        self._update_move_counter()
        self._refresh_status()
        self.right_stack.setCurrentIndex(1)
        if start_bot:
            self._maybe_trigger_bot()

    def _show_mode_selection(self):
        self._detach_worker()
        self.restart(start_bot=False)  # resets board
        self.right_stack.setCurrentIndex(0)  # show mode buttons
        self.title_label.setText("")  # clear title
        # restart() -> _refresh_status() redraws the turn label from
        # self.mode/self.bot_profiles, which are only overwritten when a
        # NEW game actually starts -- so leaving the menu mid AI-vs-AI (or
        # vs-computer) match left the previous match's "<bot> is
        # thinking..." label on screen while the mode-selection buttons
        # were showing. Nothing is "whose turn" here, so clear it.
        self.status_bar.set_turn("", "transparent")

    # ─── Turn handling ──────────────────────────────────────────────

    def _refresh_status(self):
        if self.board.winner is not None:
            self._announce_game_over()
            return

        if self.mode == "friend":
            player = self.board.current_player
            name = "Player X" if player == X else "Player O"
            color = ACCENT if player == X else ACCENT_2
            self.status_bar.set_turn(f"{name}'s turn", color)
        elif self.mode == "pc":
            player = self.board.current_player
            if player == self.human_player:
                self.status_bar.set_turn("Your turn", ACCENT if self.human_player == X else ACCENT_2)
            else:
                profile = self.bot_profiles.get(player)
                if profile:
                    self.status_bar.set_turn(f"{profile.name} is thinking…",
                                             ACCENT_2 if self.human_player == X else ACCENT)
        else:
            player = self.board.current_player
            profile = self.bot_profiles.get(player)
            if profile:
                color = ACCENT if player == X else ACCENT_2
                self.status_bar.set_turn(f"{profile.name} ({'X' if player == X else 'O'}) is thinking…", color)

    def _handle_cell_clicked(self, sub_idx: int, cell_idx: int):
        if self.right_stack.currentIndex() == 0:
            self.start_friend_game()
            # restart already switches to moves panel
            if self.board.is_move_legal(sub_idx, cell_idx):
                self._apply_move(sub_idx, cell_idx)
            return

        if self.board.winner is not None:
            return
        if self.board.current_player in self.bots:
            return
        self._apply_move(sub_idx, cell_idx)

    def _apply_move(self, sub_idx: int, cell_idx: int):
        mover = self.board.current_player
        ok = self.board.make_move(sub_idx, cell_idx)
        if not ok:
            return
        move_idx = len(self.history.entries)
        self.history.record((sub_idx, cell_idx), mover, self.board)
        self._append_move_to_list(mover, (sub_idx, cell_idx))
        self.board_widget.update()
        self._refresh_status()

        worker = SingleMoveWorker(self.history, move_idx, depth=10, time_limit=5.0)
        worker.start()
        self._analysis_workers.append(worker)

        if self.board.winner is not None:
            return
        self._maybe_trigger_bot()

    def _append_move_to_list(self, player: int, move: tuple):
        move_no = (len(self.history.entries) + 1) // 2
        prefix = f"{move_no}. {'X' if player == X else 'O'}"
        text = f"{prefix} — {move_to_notation(move)}"
        self.move_list.addItem(text)
        self.move_list.scrollToBottom()
        self._update_move_counter()

    def _update_move_counter(self):
        total = len(self.history)
        self.move_counter_label.setText(f"Move {total} / {total}")

    def _maybe_trigger_bot(self):
        if self.board.winner is not None:
            return
        if self.board.current_player in self.bots:
            self._trigger_bot_move()

    def _trigger_bot_move(self):
        mover = self.board.current_player
        bot = self.bots.get(mover)
        profile = self.bot_profiles.get(mover)
        if bot is None or profile is None:
            return
        self.board_widget.set_interactive(False)
        self.thinking_label.setText(f"{profile.name} is calculating…")
        snapshot = self.board.clone()
        self.worker = BotWorker(bot, snapshot, parent=self)
        self.worker.moveReady.connect(self._apply_bot_move)
        self.worker.start()

    def _apply_bot_move(self, sub_idx: int, cell_idx: int):
        logger.debug(f"_apply_bot_move received ({sub_idx}, {cell_idx})")
        mover = self.board.current_player
        profile = self.bot_profiles.get(mover)
        if profile is None:
            logger.warning("Profile not found for mover")
            return

        if self.mode == "ai_vs_ai":
            delay = 500 + secrets.randbelow(351)
        else:
            delay = 800 + secrets.randbelow(401)

        self.thinking_label.setText(f"{profile.name} is thinking…")
        self.board_widget.set_interactive(False)

        game_id = self._game_id
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._execute_bot_move(sub_idx, cell_idx, game_id))
        timer.start(delay)
        self._pending_timers.append(timer)

    def _execute_bot_move(self, sub_idx: int, cell_idx: int, game_id: int):
        logger.debug(f"_execute_bot_move called with game_id={game_id}, current _game_id={self._game_id}")
        if game_id != self._game_id:
            logger.debug("Game ID mismatch, ignoring move")
            return
        self.thinking_label.setText("")
        self.board_widget.set_interactive(True)
        self._apply_move(sub_idx, cell_idx)

    # ─── Game Over ──────────────────────────────────────────────────

    def _announce_game_over(self):
        if self._game_over_shown:
            return
        self._game_over_shown = True
        self.board_widget.set_interactive(False)

        winner = self.board.winner
        if winner == DRAW:
            text = "It's a draw!"
            color = TEXT_DIM
        elif self.mode == "friend":
            text = f"Player {'X' if winner == X else 'O'} wins!"
            color = ACCENT if winner == X else ACCENT_2
        elif self.mode == "pc":
            if winner == self.human_player:
                text = "You win! 🎉"
                color = ACCENT_GOOD
            else:
                profile = self.bot_profiles.get(winner)
                name = profile.name if profile else "Bot"
                text = f"{name} wins."
                color = ACCENT_2
        else:
            profile = self.bot_profiles.get(winner)
            name = profile.name if profile else "Bot"
            text = f"{name} wins!"
            color = ACCENT if winner == X else ACCENT_2

        self._end_summary = text
        self.status_bar.set_turn(text, color)

        # Save to DB
        moves = [e.move for e in self.history.entries]
        px = self.bot_profiles.get(X)
        po = self.bot_profiles.get(O)
        player_x = px.name if px else ("You" if self.human_player == X else "Player X")
        player_o = po.name if po else ("You" if self.human_player == O else "Player O")
        try:
            self._db_game_id = database.save_game(self.mode, player_x, player_o, winner, moves)
        except Exception as e:
            logger.exception("Failed to save game: %s", e, exc_info=True)
            self._db_game_id = None

        self._review_timer.stop()
        try:
            self._review_timer.timeout.disconnect(self._go_review)
        except TypeError:
            pass
        self._review_timer.timeout.connect(self._go_review)
        self._review_timer.start(600)

        self._save_analysis_when_ready()

    def _save_analysis_when_ready(self):
        """Poll until all moves are analysed, then save to DB."""
        if self._all_moves_analyzed():
            self._save_analysis_to_db()
            return
        # Check again in 200ms, up to a timeout of 5 seconds
        if not hasattr(self, '_analysis_save_tries'):
            self._analysis_save_tries = 0
        self._analysis_save_tries += 1
        if self._analysis_save_tries > 25:  # 25 * 200ms = 5s
            logger.warning("Timeout waiting for analysis, saving partial")
            self._save_analysis_to_db()
            return
        QTimer.singleShot(200, self._save_analysis_when_ready)

    def _all_moves_analyzed(self) -> bool:
        return all(entry.eval_after is not None for entry in self.history.entries)

    def _save_analysis_to_db(self):
        if self._db_game_id is None:
            return
        analysis = []
        for entry in self.history.entries:
            analysis.append({
                "eval_after": entry.eval_after,
                "mate_after": entry.mate_after,
                "best_move": list(entry.best_move) if entry.best_move else None,
                "eval_if_best": entry.eval_if_best,
                "mate_if_best": entry.mate_if_best,
                "eval_loss": entry.eval_loss,
                "is_blunder": entry.is_blunder,
            })
        database.update_game_analysis(self._db_game_id, analysis)
        self.history.analyzed = True
        logger.debug("Saved analysis for game %d", self._db_game_id)

    def _review_title(self) -> str:
        if self.mode == "friend":
            return "Player vs Player — Review"
        if self.mode == "pc":
            opponent = self.bot_profiles.get(other_player(self.human_player))
            if opponent:
                return f"You vs {opponent.name} — Review"
        px = self.bot_profiles.get(X)
        po = self.bot_profiles.get(O)
        if px and po:
            return f"{px.name} vs {po.name} — Review"
        return "Game Review"

    def _go_review(self):
        try:
            self._review_timer.timeout.disconnect(self._go_review)
        except TypeError:
            pass
        if self.on_game_over is not None:
            self.on_game_over(self.history, self._review_title(), self._end_summary, self._db_game_id)


# ─── Review Page (eval bar left, board centre, moves right) ────────

class ReviewPage(QWidget):
    def __init__(self, on_main_menu, on_play_again, parent=None):
        super().__init__(parent)
        self.on_main_menu = on_main_menu
        self.on_play_again = on_play_again

        self.history: Optional[GameHistory] = None
        self.current_ply = 0
        self.analyzer: Optional[GameAnalysisWorker] = None
        self._suppress_nav_signals = False
        self._db_game_id: Optional[int] = None

        # Main layout: horizontal with eval bar, board, move list
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # Centre: board and controls
        centre = QVBoxLayout()
        centre.setContentsMargins(4, 16, 4, 16)
        centre.setSpacing(10)

        header = QHBoxLayout()
        back_btn = QPushButton("← Menu")
        back_btn.setObjectName("ghost")
        back_btn.setFixedWidth(100)
        back_btn.clicked.connect(self._go_menu)
        header.addWidget(back_btn)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self.title_label = QLabel("Game Review")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_col.addWidget(self.title_label)
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(f"font-size: 12.5px; color: {TEXT_DIM};")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_col.addWidget(self.summary_label)
        header.addLayout(title_col, 1)

        self.play_again_btn = QPushButton("Play Again")
        self.play_again_btn.setObjectName("primary")
        self.play_again_btn.setFixedWidth(140)
        self.play_again_btn.clicked.connect(self._play_again)
        header.addWidget(self.play_again_btn)
        centre.addLayout(header)

        self.analyzing_label = QLabel("")
        self.analyzing_label.setStyleSheet(f"color: {WARN}; font-size: 12.5px; font-style: italic;")
        self.analyzing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        centre.addWidget(self.analyzing_label)

        board_container = QHBoxLayout()
        board_container.setContentsMargins(0, 0, 0, 0)
        board_container.setSpacing(0)

        # Eval bar (left), flush against the board -- no gap.
        self.eval_bar = EvalBar()
        self.eval_bar.setFixedWidth(32)
        self.eval_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        board_container.addWidget(self.eval_bar)

        self.board_widget = BoardWidget(align_left=True)
        self.board_widget.set_interactive(False)
        self.board_widget.setContentsMargins(0, 0, 0, 0)
        board_container.addWidget(self.board_widget, 1)
        centre.addLayout(board_container, 1)

        self.best_move_label = QLabel("")
        self.best_move_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.best_move_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12.5px;")
        centre.addWidget(self.best_move_label)

        self.blunder_label = QLabel("")
        self.blunder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.blunder_label.setStyleSheet(f"color: {ACCENT_2}; font-size: 14px; font-weight: 700;")
        centre.addWidget(self.blunder_label)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)

        def _nav_button(glyph: str, width: int = 40) -> QPushButton:
            b = QPushButton(glyph)
            b.setObjectName("navArrow")
            b.setFixedSize(width, 36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            return b

        self.first_btn = _nav_button("\u23EE")  # |<  jump to start
        self.first_btn.clicked.connect(lambda: self._goto_ply(0))
        self.prev_btn = _nav_button("\u25C0")  # <   step back
        self.prev_btn.clicked.connect(lambda: self._goto_ply(self.current_ply - 1))

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setFixedHeight(28)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.next_btn = _nav_button("\u25B6")  # >   step forward
        self.next_btn.clicked.connect(lambda: self._goto_ply(self.current_ply + 1))
        self.last_btn = _nav_button("\u23ED")  # >|  jump to end
        self.last_btn.clicked.connect(lambda: self._goto_ply(len(self.history) if self.history else 0))

        nav_row.addWidget(self.first_btn)
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.slider, 1)
        nav_row.addWidget(self.next_btn)
        nav_row.addWidget(self.last_btn)
        centre.addLayout(nav_row)

        self.move_counter_label = QLabel("Move 0 / 0")
        self.move_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.move_counter_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        centre.addWidget(self.move_counter_label)

        hbox.addLayout(centre, 3)

        # Right: move list
        right = QVBoxLayout()
        right.setContentsMargins(8, 20, 16, 20)
        right.setSpacing(12)

        list_title = QLabel("Moves")
        list_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        right.addWidget(list_title)

        self.move_list = QListWidget()
        self.move_list.setStyleSheet(
            f"QListWidget {{ background-color: {BG_ALT}; border: 1px solid {BORDER}; border-radius: 8px; }}"
            f"QListWidget::item {{ padding: 7px 10px; }}"
            f"QListWidget::item:selected {{ background-color: {SURFACE_HOVER}; color: {TEXT}; }}"
        )
        self.move_list.currentRowChanged.connect(self._on_list_row_changed)
        right.addWidget(self.move_list, 1)

        hbox.addLayout(right, 2)

    # ─── Loading ────────────────────────────────────────────────────

    def load_game(self, history: GameHistory, title: str, summary: str = "", db_game_id: Optional[int] = None):
        self._stop_analyzer()
        self.history = history
        self._db_game_id = db_game_id
        self.title_label.setText(title)
        self.summary_label.setText(summary)

        # Show moves immediately
        self._populate_move_list()

        self._suppress_nav_signals = True
        self.slider.setMaximum(max(len(history), 0))
        self.slider.setValue(0)
        self._suppress_nav_signals = False

        self.current_ply = 0
        self.board_widget.set_board(history.state_at(0))
        self._update_move_counter()
        self.eval_bar.set_eval(0.0)
        self.board_widget.set_suggestion(None, None)
        self.best_move_label.setText("")
        self.blunder_label.setText("")

        if history.analyzed:
            self.analyzing_label.setText("")
            self._goto_ply(len(history))
            return

        self.analyzing_label.setText("Finalizing analysis...")
        self.slider.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.analyzer = GameAnalysisWorker(history, parent=self)
        self.analyzer.progress.connect(self._on_analysis_progress)
        self.analyzer.finished_analysis.connect(self._on_analysis_done)
        self.analyzer.start()

    def _on_analysis_progress(self, done: int, total: int):
        self.analyzing_label.setText(f"Finalizing analysis... {done}/{total}")
        self._populate_move_list()
        self._goto_ply(self.current_ply)

    def _on_analysis_done(self):
        self.analyzing_label.setText("")
        self._populate_move_list()  # refresh with blunder markers
        self._goto_ply(len(self.history))

        if self._db_game_id is not None:
            analysis = []
            for entry in self.history.entries:
                analysis.append({
                    "eval_after": entry.eval_after,
                    "mate_after": entry.mate_after,
                    "best_move": list(entry.best_move) if entry.best_move else None,
                    "eval_if_best": entry.eval_if_best,
                    "mate_if_best": entry.mate_if_best,
                    "eval_loss": entry.eval_loss,
                    "is_blunder": entry.is_blunder,
                })
            database.update_game_analysis(self._db_game_id, analysis)

    def _populate_move_list(self):
        self.move_list.clear()
        move_no = 0
        for entry in self.history.entries:
            if entry.player == X:
                move_no += 1
            prefix = f"{move_no}. {'X' if entry.player == X else 'O'}"
            text = f"{prefix} — {move_to_notation(entry.move)}"
            if entry.is_blunder:
                text += "  ❗"
            item = QListWidgetItem(text)
            if entry.is_blunder:
                item.setForeground(QColor(ACCENT_2))
            self.move_list.addItem(item)

    # ─── Navigation ─────────────────────────────────────────────────

    def _on_slider_changed(self, value: int):
        if self._suppress_nav_signals:
            return
        self._goto_ply(value)

    def _on_list_row_changed(self, row: int):
        if self._suppress_nav_signals:
            return
        self._goto_ply(row + 1)

    def _goto_ply(self, ply: int):
        if self.history is None:
            return
        ply = max(0, min(ply, len(self.history)))
        self.current_ply = ply

        self._suppress_nav_signals = True
        self.slider.setValue(ply)
        self.move_list.setCurrentRow(ply - 1 if ply > 0 else -1)
        self._suppress_nav_signals = False

        self.board_widget.set_board(self.history.state_at(ply))

        if ply > 0 and self.history.analyzed:
            entry = self.history.entries[ply - 1]
            self.eval_bar.set_eval(entry.eval_after if entry.eval_after is not None else 0.0, entry.mate_after)
            self.board_widget.set_suggestion(
                entry.best_move,
                entry.move if entry.is_blunder else None,
            )
            if entry.best_move is not None and entry.best_move != entry.move:
                if entry.mate_if_best is not None:
                    best_disp = f"Win in {abs(entry.mate_if_best)}"
                else:
                    best_disp = f"{entry.eval_if_best:+.2f}"
                self.best_move_label.setText(f"Engine's pick: {move_to_notation(entry.best_move)}  ({best_disp})")
            elif entry.best_move is not None:
                self.best_move_label.setText(f"Best move played — {move_to_notation(entry.best_move)}")
            else:
                self.best_move_label.setText("")
            self.blunder_label.setText(_blunder_message(entry))
        else:
            self.eval_bar.set_eval(0.0, None)
            self.board_widget.set_suggestion(None, None)
            self.best_move_label.setText("Starting position" if ply == 0 else "")
            self.blunder_label.setText("")

        self._update_move_counter()

    def _update_move_counter(self):
        total = len(self.history) if self.history else 0
        self.move_counter_label.setText(f"Move {self.current_ply} / {total}")

    def _go_menu(self):
        self._stop_analyzer()
        self.on_main_menu()

    def _play_again(self):
        self._stop_analyzer()
        self.on_play_again()

    def _stop_analyzer(self):
        if self.analyzer is not None:
            try:
                self.analyzer.progress.disconnect(self._on_analysis_progress)
            except TypeError:
                pass
            try:
                self.analyzer.finished_analysis.disconnect(self._on_analysis_done)
            except TypeError:
                pass
            self.analyzer.cancel()
            self.analyzer.wait()
            self.analyzer = None


class BotSelectPage(QWidget):
    def __init__(self, on_pick, on_back, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 34, 40, 34)
        outer.setSpacing(16)

        header = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("ghost")
        back_btn.setFixedWidth(100)
        back_btn.clicked.connect(on_back)
        header.addWidget(back_btn)
        header.addStretch(1)
        outer.addLayout(header)

        title = QLabel("Choose Your Opponent")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        subtitle = QLabel("Ten rated opponents, grouped by rating tier like a chess engine ladder.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid = TieredBotGrid(on_pick, selectable=False, columns=3)
        scroll.setWidget(grid)
        outer.addWidget(scroll, 1)


class AIMatchSelectPage(QWidget):
    def __init__(self, on_start, on_back, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 30, 36, 30)
        outer.setSpacing(14)

        header = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("ghost")
        back_btn.setFixedWidth(100)
        back_btn.clicked.connect(on_back)
        header.addWidget(back_btn)
        header.addStretch(1)
        outer.addLayout(header)

        title = QLabel("AI vs AI")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        subtitle = QLabel("Pick a bot for each side, then watch them play it out and review the game.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(subtitle)

        columns = QHBoxLayout()
        columns.setSpacing(20)

        x_col = QVBoxLayout()
        x_head = QLabel("PLAYS AS X")
        x_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x_head.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {ACCENT}; letter-spacing: 1px;")
        x_col.addWidget(x_head)
        x_scroll = QScrollArea()
        x_scroll.setWidgetResizable(True)
        self.grid_x = TieredBotGrid(self._pick_x, selectable=True, initial_key="orion", columns=2)
        x_scroll.setWidget(self.grid_x)
        x_col.addWidget(x_scroll, 1)
        columns.addLayout(x_col, 1)

        o_col = QVBoxLayout()
        o_head = QLabel("PLAYS AS O")
        o_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        o_head.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {ACCENT_2}; letter-spacing: 1px;")
        o_col.addWidget(o_head)
        o_scroll = QScrollArea()
        o_scroll.setWidgetResizable(True)
        self.grid_o = TieredBotGrid(self._pick_o, selectable=True, initial_key="nova", columns=2)
        o_scroll.setWidget(self.grid_o)
        o_col.addWidget(o_scroll, 1)
        columns.addLayout(o_col, 1)

        outer.addLayout(columns, 1)

        self._on_start = on_start
        start_btn = QPushButton("  Start Match")
        start_btn.setObjectName("primary")
        start_btn.setMinimumSize(220, 58)
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setGraphicsEffect(make_shadow(blur=30, alpha=90))
        start_btn.clicked.connect(self._start)
        start_row = QHBoxLayout()
        start_row.addStretch(1)
        start_row.addWidget(start_btn)
        start_row.addStretch(1)
        outer.addLayout(start_row)

    def _pick_x(self, key: str):
        pass

    def _pick_o(self, key: str):
        pass

    def _start(self):
        self._on_start(self.grid_x.selected_key, self.grid_o.selected_key)


# ─── Main Window ────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultimate Tic-Tac-Toe")
        self.resize(1280, 860)
        self.setMinimumSize(900, 680)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.pageRequested.connect(self._on_sidebar_nav)
        main_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        self.bot_select = BotSelectPage(self._go_pc_game, self._go_play_menu)
        self.ai_match_select = AIMatchSelectPage(self._go_ai_vs_ai_game, self._go_play_menu)
        self.play_page = PlayPage(self._go_play_menu, self._go_review)
        self.review_page = ReviewPage(self._go_play_menu, self._go_play_again)
        self.history_page = HistoryListPage(self._go_play_menu)
        self.history_page.gameSelected.connect(self._load_history_game)
        self.play_page.requestBotSelection.connect(self._go_bot_select)
        self.play_page.requestAISelection.connect(self._go_ai_match_select)

        self.stack.addWidget(self.bot_select)  # 1
        self.stack.addWidget(self.ai_match_select)  # 2
        self.stack.addWidget(self.play_page)  # 3
        self.stack.addWidget(self.review_page)  # 4
        self.stack.addWidget(self.history_page)  # 5

        # Start with play page directly
        self._go_play_menu()

    def _on_sidebar_nav(self, key: str):
        if key == "play":
            self._show_play_page()  # new method, no reset
        elif key == "history":
            self.stack.setCurrentWidget(self.history_page)
            self.history_page.refresh()
        self.sidebar.set_active(key)

    def _show_play_page(self):
        # Just bring the play page to front, do NOT reset
        self.stack.setCurrentWidget(self.play_page)
        self.sidebar.set_active("play")

    def _go_play_menu(self):
        # This is called from the "← Menu" button -> resets and shows mode selection
        self.sidebar.set_active("play")
        self.play_page._show_mode_selection()  # resets board and shows mode buttons
        self.stack.setCurrentWidget(self.play_page)

    def _go_friend(self):
        self.play_page.start_friend_game()
        self.stack.setCurrentWidget(self.play_page)

    def _go_bot_select(self):
        self.stack.setCurrentWidget(self.bot_select)

    def _go_pc_game(self, profile_key: str):
        self.play_page.start_pc_game(profile_key)
        self.stack.setCurrentWidget(self.play_page)

    def _go_ai_match_select(self):
        self.stack.setCurrentWidget(self.ai_match_select)

    def _go_ai_vs_ai_game(self, key_x: str, key_o: str):
        self.play_page.start_ai_vs_ai_game(key_x, key_o)
        self.stack.setCurrentWidget(self.play_page)

    def _go_review(self, history: GameHistory, title: str, summary: str, db_game_id: Optional[int] = None):
        self.review_page.load_game(history, title, summary, db_game_id)
        self.stack.setCurrentWidget(self.review_page)

    def _go_play_again(self):
        self.play_page.restart()
        self.stack.setCurrentWidget(self.play_page)

    def _load_history_game(self, game_id: int):
        row = database.get_game(game_id)
        if row is None:
            return
        history = database.history_from_db_row(row)
        px = row["player_x"]
        po = row["player_o"]
        title = f"{px} vs {po} — Review"
        winner = row["winner"]
        summary = {1: "X wins!", 2: "O wins!", 3: "It's a draw!"}.get(winner, "Game over")
        self.review_page.load_game(history, title, summary, game_id)
        self.stack.setCurrentWidget(self.review_page)

    def closeEvent(self, event):
        # Stop any running analysis workers cooperatively (see restart()
        # for why this is preferred over QThread.terminate()).
        for worker in self.play_page._analysis_workers:
            worker.cancel()
            worker.wait()
        if self.play_page.worker is not None:
            self.play_page.worker.cancel()
            self.play_page.worker.wait()
        if self.review_page.analyzer is not None:
            self.review_page.analyzer.cancel()
            self.review_page.analyzer.wait()
        event.accept()


def main():
    try:
        logger.info("Starting application")
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(BG))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
        palette.setColor(QPalette.ColorRole.Base, QColor(BG_ALT))
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
        palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
        app.setPalette(palette)
        app.setStyleSheet(GLOBAL_STYLE)

        window = MainWindow()
        window.show()
        logger.info("Window shown")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
