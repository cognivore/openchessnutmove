"""
High-level driver API for the Chessnut Move board.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

import chess

from chessnut_move_stack.driver.ble import BleakTransport
from chessnut_move_stack.driver.codec import (
    decode_battery_level,
    decode_board_state,
    decode_firmware_version,
    decode_move_piece_state,
    decode_power_level,
    encode_buzzer_beep,
    encode_buzzer_enable,
    encode_clear_leds_command,
    encode_get_firmware_version,
    encode_get_move_piece_state,
    encode_get_power_level,
    encode_led_command_from_squares,
    encode_set_move_board_command,
    normalize_fen,
)
from chessnut_move_stack.driver.protocol import LEDColor, PiecePosition

logger = logging.getLogger(__name__)

PositionCallback = Callable[[chess.Board], None]


@dataclass
class DriverStatus:
    connected: bool
    device_name: Optional[str]
    device_address: Optional[str]
    firmware_version: Optional[str]
    battery_level: Optional[int]
    is_charging: Optional[bool]
    position: Optional[chess.Board]
    fen: Optional[str]


class ChessnutDriver:
    """Async interface for controlling the Chessnut Move board."""

    def __init__(self, transport: Optional[BleakTransport] = None) -> None:
        self._transport = transport or BleakTransport()
        self._position_callbacks: list[PositionCallback] = []
        self._current_position: Optional[chess.Board] = None
        self._current_fen: Optional[str] = None
        self._firmware_version: Optional[str] = None
        self._battery_level: Optional[int] = None
        self._is_charging: Optional[bool] = None
        self._piece_positions: list[PiecePosition] = []

        self._transport.on_board_state(self._on_board_state)
        self._transport.on_command_response(self._on_command_response)

    @property
    def is_connected(self) -> bool:
        return self._transport.is_connected

    def get_status(self) -> DriverStatus:
        state = self._transport.state
        return DriverStatus(
            connected=state.connected,
            device_name=state.device_name,
            device_address=state.device_address,
            firmware_version=self._firmware_version or state.firmware_version,
            battery_level=self._battery_level or state.battery_level,
            is_charging=self._is_charging,
            position=self._current_position,
            fen=self._current_fen,
        )

    def on_position_change(self, callback: PositionCallback) -> None:
        self._position_callbacks.append(callback)

    async def connect(self) -> bool:
        return await self._transport.connect()

    async def disconnect(self) -> None:
        await self._transport.disconnect()

    def get_position(self) -> Optional[chess.Board]:
        return self._current_position

    def get_fen(self) -> Optional[str]:
        return self._current_fen

    async def set_position(self, fen: str, force: bool = True) -> bool:
        if not self.is_connected:
            logger.error("Not connected")
            return False

        try:
            normalized = normalize_fen(fen)
            chess.Board(normalized)
            command = encode_set_move_board_command(normalized, force=force)
            return await self._transport.send_command(command)
        except ValueError as exc:
            logger.error("Invalid FEN: %s", exc)
            return False
        except Exception as exc:
            logger.error("Set position error: %s", exc)
            return False

    async def set_leds(
        self, squares: list[str], color: LEDColor = LEDColor.RED
    ) -> bool:
        if not self.is_connected:
            return False
        command = encode_led_command_from_squares(squares, color)
        return await self._transport.send_command(command)

    async def clear_leds(self) -> bool:
        if not self.is_connected:
            return False
        return await self._transport.send_command(encode_clear_leds_command())

    async def beep(self) -> bool:
        if not self.is_connected:
            return False
        return await self._transport.send_command(encode_buzzer_beep())

    async def set_buzzer_enabled(self, enable: bool) -> bool:
        if not self.is_connected:
            return False
        return await self._transport.send_command(encode_buzzer_enable(enable))

    async def request_battery_level(self) -> None:
        if self.is_connected:
            await self._transport.send_command(encode_get_power_level())

    async def request_firmware_version(self) -> None:
        if self.is_connected:
            await self._transport.send_command(encode_get_firmware_version())

    async def request_piece_state(self) -> None:
        if self.is_connected:
            await self._transport.send_command(encode_get_move_piece_state())

    def get_piece_positions(self) -> list[PiecePosition]:
        return self._piece_positions

    def _on_board_state(self, data: bytes) -> None:
        msg = decode_board_state(data)
        if msg is None:
            level = decode_battery_level(data)
            if level is not None:
                self._battery_level = level
            return

        full_fen = normalize_fen(msg.fen_board)
        position_changed = full_fen != self._current_fen
        self._current_fen = full_fen

        try:
            self._current_position = chess.Board(full_fen)
        except Exception as exc:
            logger.error("Board parse error: %s", exc)
            return

        if position_changed:
            for callback in self._position_callbacks:
                try:
                    callback(self._current_position)
                except Exception as exc:
                    logger.error("Position callback error: %s", exc)

    def _on_command_response(self, data: bytes) -> None:
        fw = decode_firmware_version(data)
        if fw is not None:
            self._firmware_version = fw
            return

        power = decode_power_level(data)
        if power is not None:
            self._is_charging = power.charging
            self._battery_level = power.percentage
            return

        pieces = decode_move_piece_state(data)
        if pieces:
            self._piece_positions = pieces

    async def __aenter__(self) -> "ChessnutDriver":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
