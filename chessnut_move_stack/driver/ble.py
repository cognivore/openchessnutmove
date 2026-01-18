"""
BLE transport layer for Chessnut Move using bleak.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from chessnut_move_stack.driver.protocol import (
    COMMAND_NOTIFY_UUID,
    COMMAND_WRITE_UUID,
    CONFIG_COMMAND,
    FEN_NOTIFY_UUID,
    INIT_COMMAND,
    MessageType,
)

logger = logging.getLogger(__name__)

DEVICE_NAME_PATTERNS = ("Chessnut", "CN Move", "ChessnutMove")
SCAN_TIMEOUT = 10.0
CONNECT_TIMEOUT = 30.0
DEFAULT_MTU = 500


@dataclass
class ConnectionState:
    connected: bool = False
    device_name: Optional[str] = None
    device_address: Optional[str] = None
    firmware_version: Optional[str] = None
    battery_level: Optional[int] = None


BoardStateCallback = Callable[[bytes], None]
CommandResponseCallback = Callable[[bytes], None]


class BleakTransport:
    """Low-level BLE transport with notification callbacks."""

    def __init__(self) -> None:
        self._client: Optional[BleakClient] = None
        self._device: Optional[BLEDevice] = None
        self._state = ConnectionState()
        self._board_state_callbacks: list[BoardStateCallback] = []
        self._command_response_callbacks: list[CommandResponseCallback] = []

    @property
    def is_connected(self) -> bool:
        return (
            self._state.connected
            and self._client is not None
            and self._client.is_connected
        )

    @property
    def state(self) -> ConnectionState:
        return self._state

    def on_board_state(self, callback: BoardStateCallback) -> None:
        self._board_state_callbacks.append(callback)

    def on_command_response(self, callback: CommandResponseCallback) -> None:
        self._command_response_callbacks.append(callback)

    async def scan(self, timeout: float = SCAN_TIMEOUT) -> list[BLEDevice]:
        logger.info("Scanning for Chessnut devices (%ss)...", timeout)
        devices = await BleakScanner.discover(timeout=timeout)
        matches = [d for d in devices if self._is_chessnut_device(d)]
        for device in matches:
            logger.info("Found device: %s (%s)", device.name, device.address)
        return matches

    def _is_chessnut_device(self, device: BLEDevice) -> bool:
        if not device.name:
            return False
        name_lower = device.name.lower()
        return any(pattern.lower() in name_lower for pattern in DEVICE_NAME_PATTERNS)

    async def connect(self, device: Optional[BLEDevice] = None) -> bool:
        if self._client is not None:
            await self.disconnect()

        if device is None:
            matches = await self.scan(timeout=SCAN_TIMEOUT)
            if not matches:
                logger.error("No Chessnut devices found")
                return False
            device = matches[0]

        self._device = device
        logger.info("Connecting to %s (%s)...", device.name, device.address)

        try:
            self._client = BleakClient(
                device,
                disconnected_callback=self._on_disconnect,
            )
            await asyncio.wait_for(self._client.connect(), timeout=CONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.error("Connection timeout")
            return False
        except Exception as exc:
            logger.error("Connection error: %s", exc)
            return False

        if not self._client.is_connected:
            logger.error("Connection failed")
            return False

        self._state.connected = True
        self._state.device_name = device.name
        self._state.device_address = device.address

        try:
            await self._request_mtu(DEFAULT_MTU)
            await self._setup_notifications()
            await self._initialize_board()
        except Exception as exc:
            logger.error("Setup failed: %s", exc)
            await self.disconnect()
            return False

        logger.info("Connected")
        return True

    async def _request_mtu(self, mtu: int) -> None:
        if self._client is None:
            return
        try:
            if hasattr(self._client, "request_mtu"):
                await self._client.request_mtu(mtu)
                logger.debug("Requested MTU: %s", mtu)
        except Exception as exc:
            logger.debug("MTU request failed: %s", exc)

    async def _setup_notifications(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.start_notify(FEN_NOTIFY_UUID, self._on_fen_notification)
            await asyncio.sleep(0.2)
            await self._client.start_notify(
                COMMAND_NOTIFY_UUID, self._on_command_notification
            )
        except Exception as exc:
            logger.error("Notification setup failed: %s", exc)
            raise

    async def _initialize_board(self) -> None:
        await self.send_command(INIT_COMMAND)
        await asyncio.sleep(0.5)
        await self.send_command(CONFIG_COMMAND)
        await asyncio.sleep(0.2)

    def _on_fen_notification(
        self, characteristic: BleakGATTCharacteristic, data: bytes
    ) -> None:
        if not data:
            return
        msg_type = data[0]
        if msg_type == MessageType.BOARD_STATE:
            for callback in self._board_state_callbacks:
                callback(data)
        elif msg_type == MessageType.BATTERY_LEVEL and len(data) >= 3:
            self._state.battery_level = data[2]

    def _on_command_notification(
        self, characteristic: BleakGATTCharacteristic, data: bytes
    ) -> None:
        if not data:
            return
        for callback in self._command_response_callbacks:
            callback(data)

    async def send_command(self, data: bytes, response: bool = True) -> bool:
        if not self.is_connected or self._client is None:
            logger.error("Not connected")
            return False
        try:
            await self._client.write_gatt_char(
                COMMAND_WRITE_UUID, data, response=response
            )
            return True
        except Exception as exc:
            logger.error("Send command error: %s", exc)
            return False

    def _on_disconnect(self, client: BleakClient) -> None:
        logger.warning("Device disconnected")
        self._state.connected = False

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception as exc:
                logger.warning("Disconnect error: %s", exc)
        self._client = None
        self._device = None
        self._state.connected = False
        logger.info("Disconnected")

    async def __aenter__(self) -> "BleakTransport":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
