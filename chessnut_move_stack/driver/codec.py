"""
Pure encoding/decoding helpers for Chessnut Move protocol payloads.
"""

from __future__ import annotations

from typing import Iterable, Optional

from chessnut_move_stack.driver.protocol import (
    BOARD_STATE_LENGTH,
    BoardState,
    CommandSubType,
    CommandType,
    CONFIG_COMMAND,
    LEDColor,
    LED_COMMAND_LENGTH,
    MessageType,
    MOVE_PIECE_STATE_LENGTH,
    NUM_ROBOTIC_PIECES,
    PIECE_TO_VALUE,
    PowerLevel,
    PiecePosition,
    SET_MOVE_BOARD_LENGTH,
    VALUE_TO_PIECE,
)


DEFAULT_FEN_TAIL = "w KQkq - 0 1"


def normalize_fen(fen: str) -> str:
    """
    Normalize FEN to full 6-field form.

    Accepts board-only or partial FEN and fills defaults.
    """
    parts = fen.strip().split()
    if not parts:
        raise ValueError("Empty FEN")

    if len(parts) == 1:
        return f"{parts[0]} {DEFAULT_FEN_TAIL}"
    if len(parts) == 2:
        return f"{parts[0]} {parts[1]} KQkq - 0 1"
    if len(parts) == 3:
        return f"{parts[0]} {parts[1]} {parts[2]} - 0 1"
    if len(parts) == 4:
        return f"{parts[0]} {parts[1]} {parts[2]} {parts[3]} 0 1"
    if len(parts) == 5:
        return f"{parts[0]} {parts[1]} {parts[2]} {parts[3]} {parts[4]} 1"
    if len(parts) == 6:
        return fen

    raise ValueError("Invalid FEN format")


def board_only_fen(fen: str) -> str:
    """Extract the board-only part of a FEN string."""
    parts = fen.strip().split()
    if not parts:
        raise ValueError("Empty FEN")
    return parts[0]


def fen_to_board_array(fen: str) -> list[list[str]]:
    """
    Convert FEN to an 8x8 board array.

    Returns board[row][col] where:
    - row 0 = rank 8 (black's back rank)
    - row 7 = rank 1 (white's back rank)
    - col 0 = a-file
    - col 7 = h-file
    """
    fen_board = board_only_fen(fen)
    board: list[list[str]] = [[" " for _ in range(8)] for _ in range(8)]

    row = 0
    col = 0

    for char in fen_board:
        if char.isdigit():
            col += int(char)
        elif char == "/":
            row += 1
            col = 0
        else:
            if row >= 8 or col >= 8:
                raise ValueError("FEN board out of bounds")
            board[row][col] = char
            col += 1

    if row != 7 or col != 8:
        # Not strictly required, but guards malformed board-only FEN
        raise ValueError("FEN board has incorrect dimensions")

    return board


def encode_set_move_board_command(fen: str, force: bool = True) -> bytes:
    """
    Encode a board position into a SYNC (0x42) command.
    """
    board = fen_to_board_array(fen)

    data = bytearray(SET_MOVE_BOARD_LENGTH)
    data[0] = CommandType.SYNC
    data[1] = 0x21  # payload length

    for row in range(8):
        for col_pair in range(4):
            col = col_pair * 2
            left_piece = board[row][col]
            right_piece = board[row][col + 1]

            left_value = PIECE_TO_VALUE.get(left_piece, 0)
            right_value = PIECE_TO_VALUE.get(right_piece, 0)

            byte_idx = (row * 4) + (3 - col_pair) + 2
            data[byte_idx] = (left_value << 4) | right_value

    data[34] = 0 if force else 1
    return bytes(data)


def encode_led_command(
    squares: Iterable[tuple[int, int]],
    color: LEDColor = LEDColor.RED,
) -> bytes:
    """
    Encode LED command for the given (row, col) squares.
    """
    data = bytearray(LED_COMMAND_LENGTH)
    data[0] = CommandType.LED
    data[1] = 0x20

    leds = [LEDColor.OFF] * 64
    for row, col in squares:
        if 0 <= row < 8 and 0 <= col < 8:
            leds[row * 8 + col] = color

    for row in range(8):
        for col_pair in range(4):
            col = col_pair * 2
            left_led = leds[row * 8 + col]
            right_led = leds[row * 8 + col + 1]

            byte_idx = (row * 4) + (3 - col_pair) + 2
            data[byte_idx] = (left_led << 4) | right_led

    return bytes(data)


def encode_led_command_from_squares(
    squares: Iterable[str],
    color: LEDColor = LEDColor.RED,
) -> bytes:
    """Encode LED command from algebraic square names."""
    coords = []
    for sq in squares:
        if len(sq) < 2:
            continue
        file_idx = ord(sq[0].lower()) - ord("a")
        rank_idx = int(sq[1]) - 1
        row = 7 - rank_idx
        coords.append((row, file_idx))

    return encode_led_command(coords, color)


def encode_clear_leds_command() -> bytes:
    """Clear all LEDs."""
    return bytes([CommandType.LED, 0x20] + [0] * 32)


def encode_buzzer_beep() -> bytes:
    """Trigger a buzzer beep (same payload as config in the app)."""
    return CONFIG_COMMAND


def encode_buzzer_enable(enable: bool) -> bytes:
    """Enable or disable the buzzer."""
    return bytes([CommandType.BUZZER_ENABLE, 0x01, 0x01 if enable else 0x00])


def encode_get_power_level() -> bytes:
    """Request battery/power status."""
    return bytes([CommandType.CONTROL, 0x01, CommandSubType.POWER_LEVEL])


def encode_get_firmware_version() -> bytes:
    """Request firmware version."""
    return bytes([CommandType.CONTROL, 0x01, CommandSubType.FIRMWARE_VERSION])


def encode_get_move_piece_state() -> bytes:
    """Request robotic piece positions."""
    return bytes([CommandType.CONTROL, 0x01, CommandSubType.MOVE_PIECE_STATE])


def decode_board_state(data: bytes) -> Optional[BoardState]:
    """
    Decode a board state notification into a FEN board string.
    """
    if len(data) < BOARD_STATE_LENGTH:
        return None
    if data[0] != MessageType.BOARD_STATE or data[1] != 0x24:
        return None

    fen_parts: list[str] = []
    for row in range(8):
        rank_str = ""
        empty_count = 0

        for col in range(7, -1, -1):
            nibble_offset = (row * 8) + col
            byte_idx = (nibble_offset // 2) + 2
            if col % 2 == 0:
                piece_value = data[byte_idx] & 0x0F
            else:
                piece_value = (data[byte_idx] >> 4) & 0x0F

            piece_char = VALUE_TO_PIECE.get(piece_value, " ")
            if piece_char == " ":
                empty_count += 1
            else:
                if empty_count:
                    rank_str += str(empty_count)
                    empty_count = 0
                rank_str += piece_char

        if empty_count:
            rank_str += str(empty_count)

        fen_parts.append(rank_str)

    fen_board = "/".join(fen_parts)
    return BoardState(fen_board=fen_board, raw_data=bytes(data))


def decode_battery_level(data: bytes) -> Optional[int]:
    if len(data) < 3:
        return None
    if data[0] != MessageType.BATTERY_LEVEL:
        return None
    return data[2] & 0xFF


def decode_power_level(data: bytes) -> Optional[PowerLevel]:
    if len(data) < 5:
        return None
    if data[0] != MessageType.COMMAND_RESPONSE or data[2] != CommandSubType.POWER_LEVEL:
        return None
    return PowerLevel(charging=data[3] == 1, percentage=data[4] & 0xFF)


def decode_firmware_version(data: bytes) -> Optional[str]:
    if len(data) < 4:
        return None
    if data[0] != MessageType.COMMAND_RESPONSE or data[2] != CommandSubType.FIRMWARE_VERSION:
        return None
    length = data[1] - 1
    if len(data) < 3 + length:
        return None
    try:
        return data[3 : 3 + length].decode("utf-8").strip("\x00")
    except Exception:
        return None


def decode_move_piece_state(data: bytes) -> list[PiecePosition]:
    if len(data) < MOVE_PIECE_STATE_LENGTH:
        return []
    pieces: list[PiecePosition] = []
    for idx in range(NUM_ROBOTIC_PIECES):
        offset = idx * 4
        pieces.append(
            PiecePosition(
                x=data[offset + 4] & 0xFF,
                y=data[offset + 5] & 0xFF,
                battery=data[offset + 6] & 0xFF,
            )
        )
    return pieces
