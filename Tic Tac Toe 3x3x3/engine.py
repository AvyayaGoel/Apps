"""
Ultimate Tic-Tac-Toe rules engine.

This module knows nothing about AI or UI -- only the rules of Ultimate
(a.k.a. "Vsauce") Tic-Tac-Toe: a 3x3 grid of 3x3 tic-tac-toe boards, where
the cell you play in decides which sub-board your opponent must play in
next.

The AI (personalities, search, evaluation) lives in bots.py. Game
recording and post-game analysis (eval bar, best-move, blunders) live in
analysis.py. Both import from here; this file imports nothing of theirs,
so it can be reused (or tested) completely on its own.
"""

from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Core constants
# ---------------------------------------------------------------------------

EMPTY = 0
X = 1
O = 2
DRAW = 3

Move = Tuple[int, int]  # (sub_board_index, cell_index), both 0-8

# The 8 winning lines on any 3x3 grid (rows, columns, diagonals), reused
# both for scoring a single sub-board and for scoring the meta board.
LINES: Tuple[Tuple[int, int, int], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)

POS_WEIGHT: Tuple[int, ...] = (3, 2, 3, 2, 4, 2, 3, 2, 3)


def other_player(player: int) -> int:
    return O if player == X else X


def check_winner(cells: List[int]) -> Optional[int]:
    """Return X, O, DRAW, or None for a single flat 9-cell board."""
    for a, b, c in LINES:
        if cells[a] != EMPTY and cells[a] == cells[b] == cells[c]:
            return cells[a]
    if EMPTY not in cells:
        return DRAW
    return None


def check_meta_winner(sub_winners: List[Optional[int]]) -> Optional[int]:
    """Return X, O, DRAW, or None for the 3x3 grid of sub-board results."""
    for a, b, c in LINES:
        wa = sub_winners[a]
        if wa in (X, O) and wa == sub_winners[b] == sub_winners[c]:
            return wa
    if all(w is not None for w in sub_winners):
        return DRAW
    return None


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

class UltimateBoard:
    """Full game state for one Ultimate Tic-Tac-Toe game."""

    __slots__ = (
        "sub_boards", "sub_winners", "current_player",
        "active_board", "move_history", "winner",
    )

    def __init__(self) -> None:
        self.sub_boards: List[List[int]] = [[EMPTY] * 9 for _ in range(9)]
        self.sub_winners: List[Optional[int]] = [None] * 9
        self.current_player: int = X
        self.active_board: Optional[int] = None  # None => any open board
        self.move_history: List[Move] = []
        self.winner: Optional[int] = None  # X, O, DRAW, or None (in progress)

    # -- state helpers -----------------------------------------------------

    def clone(self) -> "UltimateBoard":
        nb = UltimateBoard.__new__(UltimateBoard)
        nb.sub_boards = [row[:] for row in self.sub_boards]
        nb.sub_winners = self.sub_winners[:]
        nb.current_player = self.current_player
        nb.active_board = self.active_board
        nb.move_history = self.move_history[:]
        nb.winner = self.winner
        return nb

    def is_game_over(self) -> bool:
        return self.winner is not None

    def get_valid_boards(self) -> List[int]:
        if self.winner is not None:
            return []
        if self.active_board is not None and self.sub_winners[self.active_board] is None:
            return [self.active_board]
        return [i for i in range(9) if self.sub_winners[i] is None]

    def get_valid_moves(self) -> List[Move]:
        moves: List[Move] = []
        for b in self.get_valid_boards():
            board = self.sub_boards[b]
            for c in range(9):
                if board[c] == EMPTY:
                    moves.append((b, c))
        return moves

    def is_move_legal(self, board_idx: int, cell_idx: int) -> bool:
        if self.winner is not None:
            return False
        if board_idx not in self.get_valid_boards():
            return False
        return self.sub_boards[board_idx][cell_idx] == EMPTY

    def make_move(self, board_idx: int, cell_idx: int) -> bool:
        """Apply a move in place. Returns False (no-op) if illegal."""
        if not self.is_move_legal(board_idx, cell_idx):
            return False

        player = self.current_player
        self.sub_boards[board_idx][cell_idx] = player
        self.move_history.append((board_idx, cell_idx))

        if self.sub_winners[board_idx] is None:
            result = check_winner(self.sub_boards[board_idx])
            if result is not None:
                self.sub_winners[board_idx] = result

        meta_result = check_meta_winner(self.sub_winners)
        if meta_result is not None:
            self.winner = meta_result

        # Where must the opponent play next?
        if self.sub_winners[cell_idx] is not None:
            self.active_board = None  # sent to a decided board -> free choice
        else:
            self.active_board = cell_idx

        self.current_player = other_player(player)
        return True
