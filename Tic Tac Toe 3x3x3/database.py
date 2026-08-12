"""
SQLite persistence for games and position analysis cache.
Uses QStandardPaths so it works on Windows, macOS and Linux.
"""

import contextlib
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from PyQt6.QtCore import QStandardPaths

from engine import UltimateBoard
from history import GameHistory

logger = logging.getLogger(__name__)

EVAL_SCHEMA_VERSION = 2


def get_db_path() -> str:
    # Use the app name set earlier
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    # Fallback if the path contains 'python' (due to missing app name)
    if "python" in folder.lower():
        folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "UltimateTicTacToe")
        os.makedirs(folder, exist_ok=True)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "ultimate_ttt.db")


@contextlib.contextmanager
def _connect():
    """Open a connection for exactly one unit of work and guarantee it's
    closed no matter what -- including on error.

    Several QThreads (the bot picking its move, live per-move analysis
    right after, and full-game review analysis) hit this database
    concurrently. Every function here used to open its connection with a
    bare `conn = get_conn()` and only call `conn.close()` on the last
    line of the `try` block, so any exception partway through (including
    a routine "database is locked" from two threads writing at once)
    leaked that connection. Under sustained bot play those leaks piled
    up and made the locking (and eventually crashes) worse over time.
    `busy_timeout` also makes SQLite wait and retry a short-lived lock
    instead of raising immediately, which is by far the more common case
    here (short writes from independent threads) than a genuinely stuck
    lock.
    """
    conn = sqlite3.connect(get_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 8000")
        yield conn
    finally:
        conn.close()


def get_conn():
    """Kept for callers that need a raw connection outside the `with`
    pattern above; prefer `_connect()` for new code so the close is
    guaranteed."""
    conn = sqlite3.connect(get_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn


def _ensure_column(conn, table: str, column: str, coltype: str) -> None:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db():
    try:
        with _connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    player_x TEXT,
                    player_o TEXT,
                    winner INTEGER,
                    moves TEXT NOT NULL,
                    analysis TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS position_cache (
                    hash TEXT PRIMARY KEY,
                    eval REAL,
                    mate INTEGER,
                    best_move TEXT,
                    depth INTEGER,
                    player INTEGER,
                    eval_version INTEGER,
                    frequency INTEGER DEFAULT 1,
                    last_used TEXT
                )
            """)
            # Migrate any pre-existing DB file (from before mate detection /
            # eval versioning existed) to the current column set.
            _ensure_column(conn, "position_cache", "mate", "INTEGER")
            _ensure_column(conn, "position_cache", "eval_version", "INTEGER")
            conn.commit()
        logger.info("Database initialized at %s", get_db_path())
        return True
    except Exception as e:
        logger.exception("Database init failed: %s", e, exc_info=True)
        return False


def board_hash(board) -> str:
    parts = []
    for i in range(9):
        parts.append("".join(str(c) for c in board.sub_boards[i]))
        sw = board.sub_winners[i]
        parts.append(str(sw if sw is not None else 9))
    parts.append(str(board.current_player))
    parts.append(str(board.active_board if board.active_board is not None else 9))
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def save_game(mode: str, player_x: str, player_o: str, winner: Optional[int],
              moves: List[Tuple[int, int]], analysis: Optional[List[Dict]] = None) -> int:
    sql = ("INSERT INTO games (timestamp, mode, player_x, player_o, winner, moves, analysis) "
           "VALUES (?, ?, ?, ?, ?, ?, ?)")
    params = (datetime.now().isoformat(), mode, player_x, player_o, winner,
              json.dumps(moves), json.dumps(analysis) if analysis else None)
    try:
        with _connect() as conn:
            cur = conn.execute(sql, params)
            game_id = cur.lastrowid
            conn.commit()
        logger.debug("Game saved with ID %d", game_id)
        return game_id
    except sqlite3.OperationalError as e:
        if "no such table: games" in str(e):
            logger.warning("Games table missing, re-initializing...")
            init_db()
            # Retry
            with _connect() as conn:
                cur = conn.execute(sql, params)
                game_id = cur.lastrowid
                conn.commit()
            logger.info("Game saved after re-init (ID %d)", game_id)
            return game_id
        else:
            logger.exception("Failed to save game: %s", e, exc_info=True)
            raise


def update_game_analysis(game_id: int, analysis: List[Dict]) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE games SET analysis = ? WHERE id = ?",
                (json.dumps(analysis), game_id)
            )
            conn.commit()
        logger.debug("Analysis updated for game %d", game_id)
    except Exception as e:
        logger.exception("Failed to update analysis: %s", e, exc_info=True)


def load_games(limit: int = 100, offset: int = 0) -> List[sqlite3.Row]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM games ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return rows
    except Exception as e:
        logger.exception("Failed to load games: %s", e, exc_info=True)
        return []


def get_game(game_id: int) -> Optional[sqlite3.Row]:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return row
    except Exception as e:
        logger.exception("Failed to get game %d: %s", game_id, e, exc_info=True)
        return None


def delete_game(game_id: int) -> bool:
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
            conn.commit()
        logger.debug("Game %d deleted", game_id)
        return True
    except Exception as e:
        logger.exception("Failed to delete game %d: %s", game_id, e, exc_info=True)
        return False


def cache_position(pos_hash: str, eval_score: Optional[float], mate: Optional[int],
                   best_move: Optional[Tuple[int, int]], depth: int, player: int) -> None:
    try:
        with _connect() as conn:
            now = datetime.now().isoformat()
            existing = conn.execute("SELECT * FROM position_cache WHERE hash = ?", (pos_hash,)).fetchone()

            if existing is None or existing["eval_version"] != EVAL_SCHEMA_VERSION:
                # No usable prior row (missing, or written under an old eval
                # formula) -- start fresh with whatever this call supplies.
                conn.execute(
                    "INSERT INTO position_cache (hash, eval, mate, best_move, depth, player, eval_version, "
                    "frequency, last_used) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?) "
                    "ON CONFLICT(hash) DO UPDATE SET eval=excluded.eval, mate=excluded.mate, "
                    "best_move=excluded.best_move, depth=excluded.depth, eval_version=excluded.eval_version, "
                    "frequency=1, last_used=excluded.last_used",
                    (pos_hash, eval_score, mate, json.dumps(best_move) if best_move is not None else None,
                     depth, player, EVAL_SCHEMA_VERSION, now)
                )
            elif depth >= existing["depth"]:
                # At least as deep as what's cached: safe to adopt this call's
                # values, but never let a None here blank out a real value
                # that a *different* call (eval-only or best-move-only)
                # already stored for this same position.
                new_eval = eval_score if eval_score is not None else existing["eval"]
                new_mate = mate if mate is not None else existing["mate"]
                new_best = json.dumps(best_move) if best_move is not None else existing["best_move"]
                conn.execute(
                    "UPDATE position_cache SET eval=?, mate=?, best_move=?, depth=?, "
                    "frequency=frequency+1, last_used=? WHERE hash=?",
                    (new_eval, new_mate, new_best, depth, now, pos_hash)
                )
            else:
                # Shallower than what's cached -- only worth filling in gaps,
                # never downgrading a field that's already populated.
                new_eval = existing["eval"] if existing["eval"] is not None else eval_score
                new_mate = existing["mate"] if existing["mate"] is not None else mate
                new_best = existing["best_move"] if existing["best_move"] is not None else (
                    json.dumps(best_move) if best_move is not None else None)
                conn.execute(
                    "UPDATE position_cache SET eval=?, mate=?, best_move=?, frequency=frequency+1, "
                    "last_used=? WHERE hash=?",
                    (new_eval, new_mate, new_best, now, pos_hash)
                )
            conn.commit()
    except Exception as e:
        logger.exception("Failed to cache position: %s", e, exc_info=True)


def get_cached_position(pos_hash: str, min_depth: int = 0) -> Optional[Dict[str, Any]]:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM position_cache WHERE hash = ? AND depth >= ? AND eval_version = ?",
                (pos_hash, min_depth, EVAL_SCHEMA_VERSION)
            ).fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.exception("Failed to get cached position: %s", e, exc_info=True)
        return None


def history_from_db_row(row) -> "GameHistory":
    history = GameHistory()
    moves = json.loads(row["moves"])
    board = UltimateBoard()
    for sub_idx, cell_idx in moves:
        player = board.current_player
        board.make_move(sub_idx, cell_idx)
        history.record((sub_idx, cell_idx), player, board.clone())

    if row["analysis"]:
        analysis = json.loads(row["analysis"])
        for i, entry in enumerate(history.entries):
            if i < len(analysis):
                a = analysis[i]
                entry.eval_after = a.get("eval_after")
                entry.mate_after = a.get("mate_after")
                entry.best_move = tuple(a["best_move"]) if a.get("best_move") else None
                entry.eval_if_best = a.get("eval_if_best")
                entry.mate_if_best = a.get("mate_if_best")
                entry.eval_loss = a.get("eval_loss", 0.0)
                entry.is_blunder = a.get("is_blunder", False)
        history.analyzed = True
    return history
