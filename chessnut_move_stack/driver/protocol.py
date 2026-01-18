"""
Protocol types and constants for the Chessnut Move board.

Derived from reverse engineering of the official app.
"""

from dataclasses import dataclass
from enum import IntEnum

# =============================================================================
# BLE UUIDs
# =============================================================================

FEN_SERVICE_UUID = "1b7e8261-2877-41c3-b46e-cf057c562023"
FEN_NOTIFY_UUID = "1b7e8262-2877-41c3-b46e-cf057c562023"

COMMAND_SERVICE_UUID = "1b7e8271-2877-41c3-b46e-cf057c562023"
COMMAND_WRITE_UUID = "1b7e8272-2877-41c3-b46e-cf057c562023"
COMMAND_NOTIFY_UUID = "1b7e8273-2877-41c3-b46e-cf057c562023"


# =============================================================================
# Piece values
# =============================================================================

class PieceValue(IntEnum):
    """Nibble values for pieces in board state encoding."""

    EMPTY = 0
    BLACK_QUEEN = 1
    BLACK_KING = 2
    BLACK_BISHOP = 3
    BLACK_PAWN = 4
    BLACK_KNIGHT = 5
    WHITE_ROOK = 6
    WHITE_PAWN = 7
    BLACK_ROOK = 8
    WHITE_BISHOP = 9
    WHITE_KNIGHT = 10
    WHITE_QUEEN = 11
    WHITE_KING = 12


PIECE_TO_VALUE: dict[str, int] = {
    " ": PieceValue.EMPTY,
    "q": PieceValue.BLACK_QUEEN,
    "k": PieceValue.BLACK_KING,
    "b": PieceValue.BLACK_BISHOP,
    "p": PieceValue.BLACK_PAWN,
    "n": PieceValue.BLACK_KNIGHT,
    "R": PieceValue.WHITE_ROOK,
    "P": PieceValue.WHITE_PAWN,
    "r": PieceValue.BLACK_ROOK,
    "B": PieceValue.WHITE_BISHOP,
    "N": PieceValue.WHITE_KNIGHT,
    "Q": PieceValue.WHITE_QUEEN,
    "K": PieceValue.WHITE_KING,
}

VALUE_TO_PIECE: dict[int, str] = {
    0: " ",
    1: "q",
    2: "k",
    3: "b",
    4: "p",
    5: "n",
    6: "R",
    7: "P",
    8: "r",
    9: "B",
    10: "N",
    11: "Q",
    12: "K",
}


# =============================================================================
# Message and command types
# =============================================================================

class MessageType(IntEnum):
    BOARD_STATE = 0x01
    BATTERY_LEVEL = 0x2A
    COMMAND_RESPONSE = 0x41


class CommandSubType(IntEnum):
    WIFI_IP = 0x01
    CONNECT_WIFI_RESULT = 0x05
    FIRMWARE_VERSION = 0x09
    FW_UPDATE_RESULT = 0x0A
    MOVE_PIECE_STATE = 0x0B
    POWER_LEVEL = 0x0C
    PAIR_MODE_DISABLE = 0x11
    BOARD_CHANNEL = 0x13
    SET_BOARD_CHANNEL = 0x14
    START_PAIRING = 0x10
    PAIR_MODE_ENABLE = 0x0F
    CAR_CHANNEL_ON_BOARD = 0x19
    BOARD_CHANNEL_SETTINGS = 0x1B
    WIFI_SSID = 0x1C
    WIFI_SWITCH_STATE = 0x1F
    SHUTDOWN_CHANNEL = 0x20
    BLE_FW_UPDATE_PROGRESS = 0x22
    BLE_FW_UPDATE_RESULT = 0x23


class CommandType(IntEnum):
    CONFIG = 0x0B
    BUZZER_ENABLE = 0x1B
    KEEPALIVE = 0x21
    CONTROL = 0x41
    SYNC = 0x42
    LED = 0x43


class LEDColor(IntEnum):
    OFF = 0
    RED = 1
    GREEN = 2
    BLUE = 3


# =============================================================================
# Initialization commands
# =============================================================================

INIT_COMMAND = bytes([0x21, 0x01, 0x00])
CONFIG_COMMAND = bytes([0x0B, 0x04, 0x03, 0xE8, 0x00, 0xC8])


# =============================================================================
# Data classes
# =============================================================================

@dataclass(frozen=True)
class PiecePosition:
    x: int
    y: int
    battery: int


@dataclass(frozen=True)
class BoardState:
    fen_board: str
    raw_data: bytes

    @property
    def full_fen(self) -> str:
        return f"{self.fen_board} w KQkq - 0 1"


@dataclass(frozen=True)
class PowerLevel:
    charging: bool
    percentage: int


# =============================================================================
# Protocol constants
# =============================================================================

BOARD_STATE_LENGTH = 38
SET_MOVE_BOARD_LENGTH = 35
LED_COMMAND_LENGTH = 34
MOVE_PIECE_STATE_LENGTH = 139
NUM_ROBOTIC_PIECES = 34
