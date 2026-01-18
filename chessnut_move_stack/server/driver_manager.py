"""
Driver manager for orchestrating connection state and auto-connect.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Optional

from chessnut_move_stack.driver.driver import ChessnutDriver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoConnectConfig:
    enabled: bool
    retry_interval: float = 1.0


class DriverManager:
    """Coordinates driver connection state and auto-connect behavior."""

    def __init__(self, driver: ChessnutDriver, config: AutoConnectConfig) -> None:
        self._driver = driver
        self._config = config
        self._lock = asyncio.Lock()
        self._auto_connect_task: Optional[asyncio.Task[None]] = None
        if self._config.enabled:
            self._start_auto_connect()

    @property
    def driver(self) -> ChessnutDriver:
        return self._driver

    @property
    def auto_connect_enabled(self) -> bool:
        return self._config.enabled

    async def connect(self) -> bool:
        async with self._lock:
            return await self._driver.connect()

    async def disconnect(self) -> None:
        async with self._lock:
            await self._driver.disconnect()

    async def set_auto_connect(self, enabled: bool) -> None:
        if enabled == self._config.enabled:
            if enabled and (
                self._auto_connect_task is None or self._auto_connect_task.done()
            ):
                self._start_auto_connect()
            elif not enabled and self._auto_connect_task is not None:
                await self._stop_auto_connect()
            return

        self._config = AutoConnectConfig(
            enabled=enabled,
            retry_interval=self._config.retry_interval,
        )
        if enabled:
            self._start_auto_connect()
        else:
            await self._stop_auto_connect()

    async def shutdown(self) -> None:
        await self.set_auto_connect(False)
        await self.disconnect()

    def _start_auto_connect(self) -> None:
        if self._auto_connect_task is not None and not self._auto_connect_task.done():
            return
        self._auto_connect_task = asyncio.create_task(self._auto_connect_loop())

    async def _stop_auto_connect(self) -> None:
        task = self._auto_connect_task
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._auto_connect_task = None

    async def _auto_connect_loop(self) -> None:
        try:
            while self._config.enabled:
                if not self._driver.is_connected:
                    async with self._lock:
                        if self._config.enabled and not self._driver.is_connected:
                            await self._driver.connect()
                await asyncio.sleep(self._config.retry_interval)
        except asyncio.CancelledError:
            logger.debug("Auto-connect loop cancelled")
            raise
