"""
Game history and analysis data structures.
"""

from dataclasses import dataclass
from typing import List, Optional

from engine import UltimateBoard, Move


@dataclass
class HistoryEntry:
    """One ply of a recorded game."""
    move: Move
    player: int
    state: UltimateBoard
    eval_after: Optional[float] = None  # centipawn-style score (-10..+10), X-perspective
    mate_after: Optional[int] = None  # signed plies-to-mate, X-perspective; None if no forced mate found
    best_move: Optional[Move] = None
    eval_if_best: Optional[float] = None
    mate_if_best: Optional[int] = None
    eval_loss: float = 0.0
    is_blunder: bool = False


class GameHistory:
    """Chronological record of one game."""

    def __init__(self) -> None:
        self.entries: List[HistoryEntry] = []
        self.initial_state = UltimateBoard()
        self.analyzed = False

    def record(self, move: Move, player: int, state_after: UltimateBoard) -> None:
        self.entries.append(HistoryEntry(move=move, player=player, state=state_after.clone()))

    def state_at(self, ply: int) -> UltimateBoard:
        if ply <= 0:
            return self.initial_state
        return self.entries[ply - 1].state

    def __len__(self) -> int:
        return len(self.entries)
