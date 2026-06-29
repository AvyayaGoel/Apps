"""Undo/redo manager with command-based deltas."""

import logging
from typing import List

from commands import Command, MacroCommand, SnapshotCommand
from models import Molecule

logger = logging.getLogger(__name__)


class UndoManager:
    def __init__(self):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.macro_stack: List[MacroCommand] = []

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def begin_macro(self, name: str = "") -> None:
        self.macro_stack.append(MacroCommand(name))

    def end_macro(self) -> None:
        if not self.macro_stack:
            logger.warning("end_macro called without begin_macro")
            return
        macro = self.macro_stack.pop()
        if macro.commands:
            self._push(macro)

    def push(self, command: Command) -> None:
        if self.macro_stack:
            self.macro_stack[-1].add(command)
        else:
            self._push(command)

    def snapshot(self, mol: Molecule) -> None:
        """Push a full-state snapshot as a single command."""
        cmd = SnapshotCommand(mol)
        self._push(cmd)

    def _push(self, command: Command) -> None:
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.undo_stack.append(cmd)
        return True

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.macro_stack.clear()
