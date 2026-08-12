"""
AI personalities and post-game analysis for Ultimate Tic-Tac-Toe.
"""
import json
import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from database import board_hash, get_cached_position, cache_position
from engine import (
    UltimateBoard, Move, LINES, POS_WEIGHT, X, DRAW,
    other_player,
)
from history import GameHistory

logger = logging.getLogger(__name__)

try:
    import native as ne

    # Test that it actually works
    dummy_boards = [[0] * 9 for _ in range(9)]
    dummy_winners = [0] * 9
    ne.evaluate(dummy_boards, dummy_winners, 1, -1, 1, 0.1, 1)
    _NATIVE_AVAILABLE = True
    logger.info("Native engine loaded and verified")
except Exception as e:
    _NATIVE_AVAILABLE = False
    logger.error(f"Native engine NOT available: {e}")

if _NATIVE_AVAILABLE:
    try:
        # Test choose_move on a simple board
        test_board = UltimateBoard()
        sub_boards = [row[:] for row in test_board.sub_boards]
        sub_winners = [w if w is not None else 0 for w in test_board.sub_winners]
        active = test_board.active_board if test_board.active_board is not None else -1
        test_move = ne.choose_move(
            sub_boards, sub_winners,
            test_board.current_player, active,
            1, 0.1, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, X
        )
        if test_move is not None:
            logger.info("Native choose_move test passed, got move %s", test_move)
        else:
            logger.warning("Native choose_move test failed (returned None)")
    except Exception as e:
        logger.exception("Native choose_move test crashed: %s", e)
        _NATIVE_AVAILABLE = False

_LINE_SCORE = (0, 1, 4, 24)


class _TimeUp(Exception):
    """Internal signal used to unwind the search when the clock runs out."""


@dataclass
class BotProfile:
    """Static description of one AI personality."""
    key: str
    name: str
    elo: int
    description: str
    max_depth: int
    time_limit: float
    randomness: float
    weights: Dict[str, float] = field(default_factory=dict)


class Bot:
    """Minimax + alpha-beta search with iterative deepening."""

    def __init__(self, profile: BotProfile, player: int) -> None:
        self.profile = profile
        self.player = player

    def choose_move(self, board: UltimateBoard, cancel_event=None) -> Optional[Move]:
        logger.debug(f"Bot.choose_move called for player {self.player}")
        valid_moves = board.get_valid_moves()
        if not valid_moves:
            logger.debug("No valid moves")
            return None

        p = self.profile

        if secrets.randbelow(100) / 100.0 < p.randomness:
            return secrets.choice(valid_moves)
        if p.max_depth <= 0:
            return secrets.choice(valid_moves)

        # In Bot.choose_move, inside the native block:
        if _NATIVE_AVAILABLE:
            try:
                sub_boards = [row[:] for row in board.sub_boards]
                sub_winners = [w if w is not None else 0 for w in board.sub_winners]
                active = board.active_board if board.active_board is not None else -1
                move = ne.choose_move(
                    sub_boards, sub_winners,
                    board.current_player, active,
                    p.max_depth, p.time_limit,
                    p.randomness,
                    p.weights.get("global", 1.0),
                    p.weights.get("local", 1.0),
                    p.weights.get("aggression", 1.0),
                    p.weights.get("defense", 1.0),
                    p.weights.get("noise", 0.0),
                    self.player
                )
                if move is not None:
                    logger.debug(f"Native choose_move returned {move}")
                    return tuple(move)
                else:
                    logger.debug("Native choose_move returned None, falling back to Python")
            except Exception as e:
                logger.exception("Native choose_move failed: %s", e)

        # Pure Python fallback
        start = time.monotonic()
        best_move = valid_moves[0]
        try:
            for depth in range(1, p.max_depth + 1):
                if time.monotonic() - start > p.time_limit:
                    break
                if cancel_event is not None and cancel_event.is_set():
                    break
                move, _score, _mate = self._root_search(board, depth, start, cancel_event)
                if move is not None:
                    best_move = move
        except _TimeUp:
            pass
        # After the fallback loop, before returning:
        logger.debug(f"Python fallback chose move {best_move}")
        return best_move

    def _deadline_check(self, start: float, cancel_event=None) -> None:
        if time.monotonic() - start > self.profile.time_limit:
            raise _TimeUp()
        if cancel_event is not None and cancel_event.is_set():
            raise _TimeUp()

    def _root_search(self, board: UltimateBoard, depth: int, start: float, cancel_event=None):
        root_maximizing = (board.current_player == self.player)
        best_score = -float("inf") if root_maximizing else float("inf")
        best_move: Optional[Move] = None
        best_mate: Optional[int] = None
        alpha, beta = -float("inf"), float("inf")
        moves = self._order_moves(board.get_valid_moves())

        for move in moves:
            self._deadline_check(start, cancel_event)
            nb = board.clone()
            nb.make_move(*move)
            score, mate = self._minimax(nb, depth - 1, alpha, beta, not root_maximizing, start, 1, cancel_event)
            if root_maximizing:
                if score > best_score:
                    best_score = score
                    best_move = move
                    best_mate = mate
                alpha = max(alpha, best_score)
            else:
                if score < best_score:
                    best_score = score
                    best_move = move
                    best_mate = mate
                beta = min(beta, best_score)
        return best_move, best_score, best_mate

    def _minimax(
            self,
            board: UltimateBoard,
            depth: int,
            alpha: float,
            beta: float,
            maximizing: bool,
            start: float,
            ply: int,
            cancel_event=None,
    ):
        self._deadline_check(start, cancel_event)

        if board.winner is not None:
            if board.winner == self.player:
                return 1_000_000 - ply, ply
            if board.winner == DRAW:
                return 0.0, None
            return -1_000_000 + ply, -ply

        if depth == 0:
            return self._evaluate(board), None

        moves = self._order_moves(board.get_valid_moves())
        if maximizing:
            value = -float("inf")
            value_mate = None
            for move in moves:
                nb = board.clone()
                nb.make_move(*move)
                score, mate = self._minimax(nb, depth - 1, alpha, beta, False, start, ply + 1, cancel_event)
                if score > value:
                    value = score
                    value_mate = mate
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value, value_mate
        else:
            value = float("inf")
            value_mate = None
            for move in moves:
                nb = board.clone()
                nb.make_move(*move)
                score, mate = self._minimax(nb, depth - 1, alpha, beta, True, start, ply + 1, cancel_event)
                if score < value:
                    value = score
                    value_mate = mate
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value, value_mate

    @staticmethod
    def _order_moves(moves: List[Move]) -> List[Move]:
        def key(m: Move) -> int:
            b, c = m
            return -(POS_WEIGHT[c] * 2 + POS_WEIGHT[b])

        return sorted(moves, key=key)

    def _evaluate(self, board: UltimateBoard) -> float:
        me = self.player
        opp = other_player(me)
        w = self.profile.weights
        score = 0.0

        for i in range(9):
            sw = board.sub_winners[i]
            if sw == me:
                score += 20.0 * w.get("global", 1.0)
            elif sw == opp:
                score -= 20.0 * w.get("global", 1.0)

        score += self._meta_line_score(board.sub_winners, me) * w.get("aggression", 1.0)
        score -= self._meta_line_score(board.sub_winners, opp) * w.get("defense", 1.0)

        score += self._tempo_bonus(board, me, opp)

        for i in range(9):
            if board.sub_winners[i] is None:
                score += self._local_score(board.sub_boards[i], me, opp) * w.get("local", 1.0) * 0.5

        noise = w.get("noise", 0.0)
        if noise:
            score += random.uniform(-noise, noise)
        return score

    @staticmethod
    def _local_score(cells: List[int], me: int, opp: int) -> float:
        s = 0.0
        for a, b, c in LINES:
            line = (cells[a], cells[b], cells[c])
            mine = line.count(me)
            theirs = line.count(opp)
            if mine and not theirs:
                s += _LINE_SCORE[mine]
            elif theirs and not mine:
                s -= _LINE_SCORE[theirs]
        if cells[4] == me:
            s += 2
        elif cells[4] == opp:
            s -= 2
        return s

    @staticmethod
    def _meta_line_score(sub_winners: List[Optional[int]], player: int) -> float:
        s = 0.0
        for a, b, c in LINES:
            vals = (sub_winners[a], sub_winners[b], sub_winners[c])
            mine = sum(1 for v in vals if v == player)
            blocked = any(v is not None and v != player for v in vals)
            if blocked or mine == 0:
                continue
            if mine == 2:
                s += 100.0
            elif mine == 1:
                s += 20.0
        return s

    @staticmethod
    def _tempo_bonus(board: UltimateBoard, me: int, opp: int) -> float:
        if board.active_board is None:
            return 0.0
        if board.sub_winners[board.active_board] is not None:
            return 0.0
        sub = board.sub_boards[board.active_board]
        mover = board.current_player
        mine_marks = sub.count(me)
        opp_marks = sub.count(opp)
        if mine_marks == opp_marks:
            return 0.0
        if mover == opp and mine_marks > opp_marks:
            return 15.0
        if mover == me and opp_marks > mine_marks:
            return -15.0
        return 0.0


# ─── Bot roster ───────────────────────────────────────────────────────

BOT_PROFILES: List[BotProfile] = [
    # Beginner (400–800)
    BotProfile(
        key="pip", name="Pip", elo=400,
        description="Just learning the rules. Plays mostly on instinct.",
        max_depth=2, time_limit=0.50, randomness=0.70,
        weights={"global": 0.8, "local": 0.8, "aggression": 0.5, "defense": 0.5, "noise": 4.0},
    ),
    BotProfile(
        key="milo", name="Milo", elo=600,
        description="Knows the basics but still finding its footing.",
        max_depth=2, time_limit=0.50, randomness=0.45,
        weights={"global": 0.9, "local": 0.9, "aggression": 0.7, "defense": 0.7, "noise": 3.0},
    ),
    BotProfile(
        key="juno", name="Juno", elo=800,
        description="A steady club player who thinks a couple moves ahead.",
        max_depth=2, time_limit=0.50, randomness=0.20,
        weights={"global": 1.0, "local": 1.0, "aggression": 0.8, "defense": 0.8, "noise": 1.5},
    ),

    # Intermediate (1000–1400)
    BotProfile(
        key="rex", name="Rex", elo=1000,
        description="Loves to attack — always hunting for the next board to win.",
        max_depth=4, time_limit=1.00, randomness=0.10,
        weights={"global": 1.1, "local": 1.0, "aggression": 1.6, "defense": 0.6, "noise": 1.0},
    ),
    BotProfile(
        key="vale", name="Vale", elo=1200,
        description="A cautious, defensive grinder that hates giving up a board.",
        max_depth=4, time_limit=1.00, randomness=0.05,
        weights={"global": 1.1, "local": 1.0, "aggression": 0.6, "defense": 1.6, "noise": 0.8},
    ),
    BotProfile(
        key="sage", name="Sage", elo=1300,
        description="Balanced and thoughtful, rarely makes a blatant mistake.",
        max_depth=4, time_limit=1.00, randomness=0.03,
        weights={"global": 1.2, "local": 1.1, "aggression": 1.0, "defense": 1.0, "noise": 0.6},
    ),
    BotProfile(
        key="orion", name="Orion", elo=1400,
        description="Well‑rounded and calculating, with no obvious weaknesses.",
        max_depth=4, time_limit=1.00, randomness=0.02,
        weights={"global": 1.3, "local": 1.1, "aggression": 1.1, "defense": 1.1, "noise": 0.4},
    ),

    # Advanced (1600–2000)
    BotProfile(
        key="nova", name="Nova", elo=1600,
        description="Aggressive and relentless, always pushing for forced wins.",
        max_depth=6, time_limit=1.50, randomness=0.01,
        weights={"global": 1.3, "local": 1.2, "aggression": 1.8, "defense": 0.8, "noise": 0.3},
    ),
    BotProfile(
        key="titan", name="Titan", elo=1700,
        description="Powerful and consistent, a solid all‑round player.",
        max_depth=6, time_limit=1.50, randomness=0.0,
        weights={"global": 1.4, "local": 1.2, "aggression": 1.2, "defense": 1.2, "noise": 0.2},
    ),
    BotProfile(
        key="atlas", name="Atlas", elo=1800,
        description="A deep, patient calculator that rarely blunders.",
        max_depth=6, time_limit=1.50, randomness=0.0,
        weights={"global": 1.4, "local": 1.3, "aggression": 1.3, "defense": 1.3, "noise": 0.1},
    ),
    BotProfile(
        key="eclipse", name="Eclipse", elo=1900,
        description="Methodical and precise, always finds the best plan.",
        max_depth=7, time_limit=2.00, randomness=0.0,
        weights={"global": 1.5, "local": 1.3, "aggression": 1.4, "defense": 1.4, "noise": 0.0},
    ),
    BotProfile(
        key="zenith", name="Zenith", elo=2000,
        description="Near‑perfect play. Every move is calculated to the edge of what's possible.",
        max_depth=7, time_limit=2.00, randomness=0.0,
        weights={"global": 1.5, "local": 1.4, "aggression": 1.5, "defense": 1.5, "noise": 0.0},
    ),

    # Expert (2100–2400)
    BotProfile(
        key="vortex", name="Vortex", elo=2100,
        description="Aggressive and deep – hunts for tactical knockouts.",
        max_depth=8, time_limit=2.50, randomness=0.0,
        weights={"global": 1.6, "local": 1.4, "aggression": 1.8, "defense": 0.9, "noise": 0.0},
    ),
    BotProfile(
        key="nemesis", name="Nemesis", elo=2200,
        description="The strongest beatable opponent. Strong but still makes occasional human‑like mistakes.",
        max_depth=8, time_limit=2.50, randomness=0.0,
        weights={"global": 1.6, "local": 1.5, "aggression": 1.6, "defense": 1.6, "noise": 0.0},
    ),
    BotProfile(
        key="omega", name="Omega", elo=2300,
        description="Balanced and nearly flawless – only the best humans can win.",
        max_depth=8, time_limit=2.50, randomness=0.0,
        weights={"global": 1.7, "local": 1.5, "aggression": 1.5, "defense": 1.5, "noise": 0.0},
    ),
    BotProfile(
        key="apocalypse", name="Apocalypse", elo=2400,
        description="The end of all games. Searches deeper than anything else in the roster.",
        max_depth=8, time_limit=2.50, randomness=0.0,
        weights={"global": 1.7, "local": 1.6, "aggression": 1.7, "defense": 1.7, "noise": 0.0},
    ),

    # Master (2500–2800)
    BotProfile(
        key="elysium", name="Elysium", elo=2500,
        description="Divine play – almost perfect, only a god can beat it.",
        max_depth=9, time_limit=4.00, randomness=0.0,
        weights={"global": 1.8, "local": 1.7, "aggression": 1.8, "defense": 1.8, "noise": 0.0},
    ),
    BotProfile(
        key="infinity", name="Infinity", elo=2600,
        description="Unbounded search depth. Every move is optimal.",
        max_depth=9, time_limit=4.00, randomness=0.0,
        weights={"global": 1.9, "local": 1.8, "aggression": 1.9, "defense": 1.9, "noise": 0.0},
    ),
    BotProfile(
        key="deity", name="Deity", elo=2800,
        description="The highest level of play – sees all possibilities.",
        max_depth=9, time_limit=4.00, randomness=0.0,
        weights={"global": 2.0, "local": 1.9, "aggression": 2.0, "defense": 2.0, "noise": 0.0},
    ),

    # Legend (2900+) – now with 30s to reach depth 12
    BotProfile(
        key="legend", name="Legend", elo=3000,
        description="The ultimate Tic‑Tac‑Toe player. Unbeatable, perfect, eternal. Takes his Time",
        max_depth=12, time_limit=30.0, randomness=0.0,
        weights={"global": 2.0, "local": 2.0, "aggression": 2.0, "defense": 2.0, "noise": 0.0},
    ),
]

_PROFILE_BY_KEY = {p.key: p for p in BOT_PROFILES}


def make_bot(profile_key: str, player: int) -> Bot:
    return Bot(_PROFILE_BY_KEY[profile_key], player)


def top_rated_profile() -> BotProfile:
    return max(BOT_PROFILES, key=lambda p: p.elo)


# ---------------------------------------------------------------------------
# Analysis engine
# ---------------------------------------------------------------------------

BLUNDER_THRESHOLD = 2.0
_MATE_COMPARISON_BASE = 500.0


class AnalysisEngine:
    _cache: Dict[str, Dict] = {}

    def __init__(self, depth: Optional[int] = None, time_limit: Optional[float] = None) -> None:
        top = top_rated_profile()
        self.source_profile = top
        self.depth = depth if depth is not None else 40
        self.time_limit = time_limit if time_limit is not None else 3.0
        self._profile = BotProfile(
            key="_analysis", name=f"Analysis ({top.name})", elo=top.elo, description="",
            max_depth=self.depth, time_limit=self.time_limit, randomness=0.0,
            weights={"global": 1.0, "local": 1.0, "aggression": 1.0, "defense": 1.0, "noise": 0.0},
        )

    def _bot_for(self, player: int) -> Bot:
        return Bot(self._profile, player)

    def evaluate(self, board: UltimateBoard, perspective: int = X, cancel_event=None):
        if board.winner is not None:
            if board.winner == DRAW:
                return 0.0, None
            return (10.0, 0) if board.winner == X else (-10.0, 0)

        h = board_hash(board)

        cache_hit = AnalysisEngine._cache.get(h)
        if cache_hit is None:
            cache_hit = get_cached_position(h, min_depth=self.depth)
            if cache_hit:
                AnalysisEngine._cache[h] = cache_hit
        if cache_hit is not None and cache_hit.get("depth", 0) >= self.depth:
            cached_eval = cache_hit.get("eval")
            cached_mate = cache_hit.get("mate")
            if cached_eval is not None or cached_mate is not None:
                return cached_eval, cached_mate

        if _NATIVE_AVAILABLE:
            try:
                sub_boards = [row[:] for row in board.sub_boards]
                sub_winners = [w if w is not None else 0 for w in board.sub_winners]
                active = board.active_board if board.active_board is not None else -1
                val, mate = ne.evaluate(
                    sub_boards, sub_winners,
                    board.current_player, active,
                    self.depth, self.time_limit,
                    perspective
                )
                if perspective != X:
                    val = -val
                    if mate is not None:
                        mate = -mate
                AnalysisEngine._cache[h] = {"eval": val, "mate": mate, "depth": self.depth, "player": perspective}
                cache_position(h, val, mate, None, self.depth, perspective)
                return val, mate
            except Exception:
                pass

        bot = self._bot_for(perspective)
        try:
            _move, raw_score, mate = bot._root_search(board, self.depth, time.monotonic(), cancel_event)
        except _TimeUp:
            raw_score, mate = bot._evaluate(board), None

        if mate is not None:
            val = 10.0 if mate > 0 else -10.0
        else:
            val = max(-10.0, min(10.0, raw_score / 100.0))

        if perspective != X:
            val = -val
            if mate is not None:
                mate = -mate

        AnalysisEngine._cache[h] = {"eval": val, "mate": mate, "depth": self.depth, "player": perspective}
        cache_position(h, val, mate, None, self.depth, perspective)
        return val, mate

    def best_move(self, board: UltimateBoard, player: int, cancel_event=None) -> Optional[Move]:
        h = board_hash(board)
        cached = get_cached_position(h, min_depth=self.depth)
        if cached and cached.get("best_move"):
            bm = json.loads(cached["best_move"])
            return tuple(bm) if bm else None

        if _NATIVE_AVAILABLE:
            try:
                sub_boards = [row[:] for row in board.sub_boards]
                sub_winners = [w if w is not None else 0 for w in board.sub_winners]
                active = board.active_board if board.active_board is not None else -1
                move = ne.best_move(
                    sub_boards, sub_winners,
                    board.current_player, active,
                    self.depth, self.time_limit,
                    player
                )
                if move is not None:
                    move = tuple(move)
                    cache_position(h, None, None, move, self.depth, player)
                    return move
            except Exception:
                pass

        move = self._bot_for(player).choose_move(board, cancel_event)
        if move:
            cache_position(h, None, None, move, self.depth, player)
        return move


# Helper functions (unchanged)
def _comparison_value(cp: float, mate_plies: Optional[int]) -> float:
    if mate_plies is None:
        return cp
    if mate_plies >= 0:
        return _MATE_COMPARISON_BASE - mate_plies
    return -_MATE_COMPARISON_BASE - mate_plies


def _analyze_entry(engine_ai: AnalysisEngine, history: GameHistory, idx: int, cancel_event=None) -> None:
    entry = history.entries[idx]
    state_before = history.state_at(idx)
    player = entry.player

    best = engine_ai.best_move(state_before, player, cancel_event)
    eval_after_actual, mate_after_actual = engine_ai.evaluate(entry.state, perspective=X, cancel_event=cancel_event)

    entry.best_move = best
    entry.eval_after = eval_after_actual
    entry.mate_after = mate_after_actual

    if best is not None and best != entry.move:
        state_after_best = state_before.clone()
        state_after_best.make_move(*best)
        eval_after_best, mate_after_best = engine_ai.evaluate(state_after_best, perspective=X,
                                                              cancel_event=cancel_event)
        entry.eval_if_best = eval_after_best
        entry.mate_if_best = mate_after_best

        cmp_actual = _comparison_value(eval_after_actual, mate_after_actual)
        cmp_best = _comparison_value(eval_after_best, mate_after_best)
        diff = (cmp_best - cmp_actual) if player == X else (cmp_actual - cmp_best)
        entry.eval_loss = max(diff, 0.0)
        entry.is_blunder = diff > BLUNDER_THRESHOLD
    else:
        entry.eval_if_best = eval_after_actual
        entry.mate_if_best = mate_after_actual
        entry.eval_loss = 0.0
        entry.is_blunder = False


def analyze_single_move(
        history: GameHistory,
        idx: int,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
        cancel_event=None,
) -> None:
    if idx < 0 or idx >= len(history.entries):
        return
    engine_ai = AnalysisEngine(depth=depth, time_limit=time_limit)
    _analyze_entry(engine_ai, history, idx, cancel_event)
    if idx == len(history.entries) - 1 and history.entries[-1].state.winner is not None:
        history.analyzed = True


def analyze_game(
        history: GameHistory,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
        progress_cb=None,
        cancel_event=None,
) -> None:
    engine_ai = AnalysisEngine(depth=depth, time_limit=time_limit)
    total = len(history.entries)
    for i, entry in enumerate(history.entries):
        if cancel_event is not None and cancel_event.is_set():
            return
        if entry.eval_after is None or (entry.best_move is None and entry.eval_after != 0.0):
            _analyze_entry(engine_ai, history, i, cancel_event)
        if progress_cb:
            progress_cb(i + 1, total)
    history.analyzed = True
