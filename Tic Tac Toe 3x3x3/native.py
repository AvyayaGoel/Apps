"""
ctypes wrapper for the native Tic-Tac-Toe engine.
"""

import ctypes
import logging
import os
import platform
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_lib = None


def _load_library():
    """Load the native shared library (once)."""
    global _lib
    if _lib is not None:
        return _lib

    # Determine platform-specific library name
    system = platform.system()
    if system == "Windows":
        lib_name = "ttt_engine.dll"
    elif system == "Darwin":
        lib_name = "libttt_engine.dylib"
    else:
        lib_name = "libttt_engine.so"

    # Look in the native/ subdirectory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_path = os.path.join(base_dir, "native", lib_name)
    if not os.path.exists(lib_path):
        raise FileNotFoundError(f"Native library not found at {lib_path}")

    try:
        lib = ctypes.CDLL(lib_path)

        # --- Function signatures ---
        # All arrays are passed as flat pointers. The C functions expect:
        #   sub_boards: int[9][9] → pointer to 81 ints
        #   sub_winners: int[9]    → pointer to 9 ints

        lib.evaluate.argtypes = [
            ctypes.POINTER(ctypes.c_int),  # sub_boards (81 ints)
            ctypes.POINTER(ctypes.c_int),  # sub_winners (9 ints)
            ctypes.c_int,  # current_player
            ctypes.c_int,  # active_board
            ctypes.c_int,  # depth
            ctypes.c_double,  # time_limit
            ctypes.c_int,  # perspective
            ctypes.POINTER(ctypes.c_double),  # out_score
            ctypes.POINTER(ctypes.c_int),  # out_mate
        ]
        lib.evaluate.restype = ctypes.c_int

        lib.best_move.argtypes = [
            ctypes.POINTER(ctypes.c_int),  # sub_boards
            ctypes.POINTER(ctypes.c_int),  # sub_winners
            ctypes.c_int,  # current_player
            ctypes.c_int,  # active_board
            ctypes.c_int,  # depth
            ctypes.c_double,  # time_limit
            ctypes.c_int,  # player
            ctypes.POINTER(ctypes.c_int),  # out_sub
            ctypes.POINTER(ctypes.c_int),  # out_cell
        ]
        lib.best_move.restype = ctypes.c_int

        lib.choose_move.argtypes = [
            ctypes.POINTER(ctypes.c_int),  # sub_boards
            ctypes.POINTER(ctypes.c_int),  # sub_winners
            ctypes.c_int,  # current_player
            ctypes.c_int,  # active_board
            ctypes.c_int,  # depth
            ctypes.c_double,  # time_limit
            ctypes.c_double,  # randomness
            ctypes.c_double,  # w_global
            ctypes.c_double,  # w_local
            ctypes.c_double,  # w_aggression
            ctypes.c_double,  # w_defense
            ctypes.c_double,  # w_noise
            ctypes.c_int,  # bot_player
            ctypes.POINTER(ctypes.c_int),  # out_sub
            ctypes.POINTER(ctypes.c_int),  # out_cell
        ]
        lib.choose_move.restype = ctypes.c_int

        _lib = lib
        return lib
    except Exception as e:
        raise RuntimeError(f"Failed to load native library: {e}")


def _prepare_board(sub_boards, sub_winners):
    """
    Convert Python lists to flat ctypes arrays.

    sub_boards: list of 9 lists, each of 9 ints
    sub_winners: list of 9 ints
    Returns (flat_boards, win_arr) where each is a ctypes array.
    """
    # Flatten sub_boards into 81 ints
    flat = [cell for row in sub_boards for cell in row]
    arr = (ctypes.c_int * 81)(*flat)
    win_arr = (ctypes.c_int * 9)(*sub_winners)
    return arr, win_arr


def evaluate(
        sub_boards: List[List[int]],
        sub_winners: List[int],
        current_player: int,
        active_board: int,
        depth: int,
        time_limit: float,
        perspective: int,
) -> Tuple[float, Optional[int]]:
    """
    Evaluate a position from `perspective`'s point of view.

    Returns (score, mate_plies) where mate_plies is None if no mate found,
    otherwise a signed integer (positive = perspective mates, negative = perspective gets mated).
    """
    lib = _load_library()
    arr, win_arr = _prepare_board(sub_boards, sub_winners)

    out_score = ctypes.c_double()
    out_mate = ctypes.c_int()

    ret = lib.evaluate(
        arr,
        win_arr,
        current_player,
        active_board,
        depth,
        time_limit,
        perspective,
        ctypes.byref(out_score),
        ctypes.byref(out_mate),
    )
    if ret != 0:
        raise RuntimeError(f"Native evaluate failed with code {ret}")

    mate = out_mate.value if out_mate.value != 0 else None
    return out_score.value, mate


def best_move(
        sub_boards: List[List[int]],
        sub_winners: List[int],
        current_player: int,
        active_board: int,
        depth: int,
        time_limit: float,
        player: int,
) -> Optional[Tuple[int, int]]:
    """Return the best move for `player` as (sub_board, cell), or None if no moves."""
    lib = _load_library()
    arr, win_arr = _prepare_board(sub_boards, sub_winners)

    out_sub = ctypes.c_int()
    out_cell = ctypes.c_int()

    ret = lib.best_move(
        arr,
        win_arr,
        current_player,
        active_board,
        depth,
        time_limit,
        player,
        ctypes.byref(out_sub),
        ctypes.byref(out_cell),
    )
    if ret != 0:
        return None
    return out_sub.value, out_cell.value


def choose_move(
        sub_boards: List[List[int]],
        sub_winners: List[int],
        current_player: int,
        active_board: int,
        depth: int,
        time_limit: float,
        randomness: float,
        w_global: float,
        w_local: float,
        w_aggression: float,
        w_defense: float,
        w_noise: float,
        bot_player: int,
) -> Optional[Tuple[int, int]]:
    """
    Choose a move for `bot_player` with the given personality weights and randomness.
    Returns (sub_board, cell) or None if no moves.
    """
    lib = _load_library()
    arr, win_arr = _prepare_board(sub_boards, sub_winners)
    out_sub = ctypes.c_int()
    out_cell = ctypes.c_int()
    logger = logging.getLogger(__name__)  # add near top
    logger.debug(f"Calling choose_move with depth={depth}, bot_player={bot_player}")

    ret = lib.choose_move(
        arr,
        win_arr,
        current_player,
        active_board,
        depth,
        time_limit,
        randomness,
        w_global,
        w_local,
        w_aggression,
        w_defense,
        w_noise,
        bot_player,
        ctypes.byref(out_sub),
        ctypes.byref(out_cell),
    )
    if ret != 0:
        logger.error(f"choose_move returned error code {ret}")
        return None
    move = (out_sub.value, out_cell.value)
    logger.debug(f"choose_move returned {move}")
    return move
