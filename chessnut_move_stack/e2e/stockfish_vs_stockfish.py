#!/usr/bin/env python3
"""
E2E Test: Stockfish vs Stockfish with Proper Wait Times

Plays a game where two Stockfish instances compete while the physical
Chessnut Move board executes the moves. Waits for the board to report
the target position before proceeding to the next move.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Optional

import chess

from chessnut_move_stack.driver.codec import (
    encode_clear_leds_command,
    encode_led_command_from_squares,
    encode_set_move_board_command,
)
from chessnut_move_stack.driver.driver import ChessnutDriver
from chessnut_move_stack.driver.protocol import LEDColor

logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    max_moves: int = 15
    depth: int = 1
    max_wait: int = 120  # Maximum wait time per move (seconds)


class StockfishEngine:
    """Async wrapper around the Stockfish UCI engine."""

    def __init__(self, depth: int = 1) -> None:
        self.depth = depth
        self._process: Optional[asyncio.subprocess.Process] = None

    async def start(self) -> None:
        self._process = await asyncio.create_subprocess_exec(
            "stockfish",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._send("uci")
        await self._wait_for("uciok")
        await self._send("isready")
        await self._wait_for("readyok")

    async def stop(self) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()

    async def get_best_move(self, fen: str) -> chess.Move:
        await self._send(f"position fen {fen}")
        await self._send(f"go depth {self.depth}")
        while True:
            line = await self._readline()
            if line.startswith("bestmove"):
                return chess.Move.from_uci(line.split()[1])

    async def _send(self, cmd: str) -> None:
        if self._process and self._process.stdin:
            self._process.stdin.write(f"{cmd}\n".encode())
            await self._process.stdin.drain()

    async def _readline(self) -> str:
        if self._process and self._process.stdout:
            line = await self._process.stdout.readline()
            return line.decode().strip()
        return ""

    async def _wait_for(self, expected: str) -> None:
        while True:
            if expected in await self._readline():
                return


class BoardMoveWaiter:
    """
    Waits for the board to reach a target position.

    Listens to position change events and signals when the board's
    reported FEN matches the target (board-only comparison).
    """

    def __init__(self, driver: ChessnutDriver) -> None:
        self._event = asyncio.Event()
        self._target_board_fen: Optional[str] = None
        self._driver = driver
        driver.on_position_change(self._on_position_change)

    def _on_position_change(self, board: chess.Board) -> None:
        reported_fen = board.board_fen()
        if self._target_board_fen and reported_fen == self._target_board_fen:
            self._event.set()

    def set_target(self, fen: str) -> None:
        """Set the target FEN to wait for (extracts board-only part)."""
        self._target_board_fen = chess.Board(fen).board_fen()
        self._event.clear()

        # Check if driver already reports matching position (handles race condition)
        current_pos = self._driver.get_position()
        if current_pos and current_pos.board_fen() == self._target_board_fen:
            self._event.set()  # Already at target position!

    async def wait(self, timeout: float, poll_interval: float = 5.0) -> bool:
        """
        Wait for the board to reach target position.

        Returns True if completed, False if timed out.
        Logs progress every poll_interval seconds.
        """
        elapsed = 0.0
        while elapsed < timeout:
            try:
                await asyncio.wait_for(
                    self._event.wait(),
                    timeout=min(poll_interval, timeout - elapsed),
                )
                return True
            except asyncio.TimeoutError:
                elapsed += poll_interval
                if elapsed < timeout:
                    logger.info("  Still waiting... %.0fs", elapsed)
        return False


def format_pgn(moves: list[str]) -> str:
    """Format move list as PGN string."""
    pgn_parts = []
    for i, san in enumerate(moves):
        if i % 2 == 0:
            pgn_parts.append(f"{i // 2 + 1}. {san}")
        else:
            pgn_parts[-1] += f" {san}"
    return " ".join(pgn_parts)


async def play_game(driver: ChessnutDriver, config: GameConfig) -> None:
    """Play a Stockfish vs Stockfish game on the physical board."""
    waiter = BoardMoveWaiter(driver)

    logger.info("Starting Stockfish engines (depth=%d)...", config.depth)
    white_engine = StockfishEngine(depth=config.depth)
    black_engine = StockfishEngine(depth=config.depth)
    await white_engine.start()
    await black_engine.start()
    logger.info("Engines ready")

    board = chess.Board()
    moves_played: list[str] = []

    try:
        # Setup starting position
        logger.info("=" * 60)
        logger.info("SETTING UP STARTING POSITION")
        logger.info("Waiting for board to signal ready...")
        logger.info("=" * 60)

        waiter.set_target(board.fen())
        await driver.set_position(board.fen())

        if await waiter.wait(config.max_wait):
            logger.info("  Board signaled READY!")
        else:
            logger.warning("  Timeout waiting for board, continuing anyway")

        await driver.beep()

        logger.info("=" * 60)
        logger.info("GAME START!")
        logger.info("=" * 60)
        logger.info("\n%s", board)

        move_num = 0
        while not board.is_game_over() and move_num < config.max_moves * 2:
            move_num += 1

            if board.turn == chess.WHITE:
                engine = white_engine
                side = "White"
                full_move = (move_num + 1) // 2
                prefix = f"{full_move}."
            else:
                engine = black_engine
                side = "Black"
                full_move = move_num // 2
                prefix = f"{full_move}..."

            # Get best move from engine
            best_move = await engine.get_best_move(board.fen())
            san = board.san(best_move)

            # Move type for logging
            is_capture = board.is_capture(best_move)
            is_castle = board.is_castling(best_move)
            move_type = "(castle)" if is_castle else "(capture)" if is_capture else ""

            # Highlight move squares
            from_sq = chess.square_name(best_move.from_square)
            to_sq = chess.square_name(best_move.to_square)
            await driver.set_leds([from_sq, to_sq], LEDColor.GREEN)

            # Make move on internal board
            board.push(best_move)
            moves_played.append(san)

            logger.info("%s %s %s", prefix, san, move_type)

            # Send new position to board
            waiter.set_target(board.fen())
            await driver.set_position(board.fen())

            logger.info("  Waiting for board to finish moving...")
            if await waiter.wait(config.max_wait):
                logger.info("  Board READY")
            else:
                logger.warning("  Timeout, continuing")

            # Clear LEDs
            await driver.clear_leds()

            # Small buffer between moves
            await asyncio.sleep(1.0)

    except asyncio.CancelledError:
        logger.info("Game interrupted!")
        raise
    finally:
        await white_engine.stop()
        await black_engine.stop()

    # Game over
    logger.info("=" * 60)
    logger.info("GAME OVER")
    logger.info("=" * 60)

    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        logger.info("Checkmate! %s wins.", winner)
    elif board.is_game_over():
        logger.info("Draw.")
    else:
        logger.info("Stopped after %d moves.", len(moves_played))

    logger.info("Final position:\n%s", board)
    logger.info("Moves: %s", format_pgn(moves_played))

    await driver.beep()
    await asyncio.sleep(2)


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 60)
    logger.info("E2E Test: Stockfish vs Stockfish")
    logger.info("=" * 60)

    config = GameConfig(
        max_moves=15,
        depth=1,
        max_wait=120,
    )

    logger.info("Config: max_moves=%d, depth=%d, max_wait=%ds",
                config.max_moves, config.depth, config.max_wait)

    async with ChessnutDriver() as driver:
        logger.info("Connecting to board...")
        if not await driver.connect():
            logger.error("Failed to connect to board!")
            return 1

        logger.info("Connected!")
        await play_game(driver, config)

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
