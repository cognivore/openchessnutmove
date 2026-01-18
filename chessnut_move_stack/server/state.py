"""Pure state transitions for the server."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import io
from typing import Optional

import chess
import chess.pgn


DEFAULT_FEN_TAIL = "w KQkq - 0 1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_fen(fen: str) -> str:
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


@dataclass(frozen=True)
class AppState:
    fen: str
    pgn: Optional[str]
    updated_at: datetime


@dataclass(frozen=True)
class StateSnapshot:
    fen: str
    board_fen: str
    turn: str
    pgn: Optional[str]
    updated_at: str


def initial_state(fen: str = chess.STARTING_FEN) -> AppState:
    normalized = normalize_fen(fen)
    board = chess.Board(normalized)
    return AppState(
        fen=board.fen(),
        pgn=None,
        updated_at=_utc_now(),
    )


def apply_fen(state: AppState, fen: str) -> AppState:
    normalized = normalize_fen(fen)
    board = chess.Board(normalized)
    return AppState(
        fen=board.fen(),
        pgn=None,
        updated_at=_utc_now(),
    )


def apply_pgn(state: AppState, pgn_text: str) -> AppState:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("Invalid PGN")

    board = game.board()
    for move in game.mainline_moves():
        board.push(move)

    normalized_pgn = game.accept(
        chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    )

    return AppState(
        fen=board.fen(),
        pgn=normalized_pgn,
        updated_at=_utc_now(),
    )


def snapshot(state: AppState) -> StateSnapshot:
    board = chess.Board(state.fen)
    turn = "white" if board.turn == chess.WHITE else "black"
    return StateSnapshot(
        fen=state.fen,
        board_fen=board.board_fen(),
        turn=turn,
        pgn=state.pgn,
        updated_at=state.updated_at.isoformat(),
    )
