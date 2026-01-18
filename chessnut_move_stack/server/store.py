"""State store with functional update semantics."""

from __future__ import annotations

import asyncio
from typing import Callable

from chessnut_move_stack.server.state import AppState


class StateStore:
    """Async-safe state store using pure update functions."""

    def __init__(self, initial_state: AppState) -> None:
        self._state = initial_state
        self._lock = asyncio.Lock()

    async def get(self) -> AppState:
        async with self._lock:
            return self._state

    async def update(self, updater: Callable[[AppState], AppState]) -> AppState:
        async with self._lock:
            self._state = updater(self._state)
            return self._state
