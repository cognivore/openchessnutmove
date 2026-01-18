"""
FastAPI server that maintains application state and syncs with the board.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from typing import Optional

import chess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from chessnut_move_stack.driver.driver import ChessnutDriver
from chessnut_move_stack.server.config import ServerConfig, load_config
from chessnut_move_stack.server.state import (
    AppState,
    apply_fen,
    apply_pgn,
    initial_state,
    snapshot,
)
from chessnut_move_stack.server.store import StateStore

logger = logging.getLogger(__name__)


class FenRequest(BaseModel):
    fen: str = Field(..., description="FEN string (full or board-only)")
    force: bool = Field(default=True, description="Force immediate movement")


class PgnRequest(BaseModel):
    pgn: str = Field(..., description="PGN text")
    force: bool = Field(default=True, description="Force immediate movement")


class DriverStatusResponse(BaseModel):
    enabled: bool
    connected: bool
    device_name: Optional[str]
    device_address: Optional[str]
    firmware_version: Optional[str]
    battery_level: Optional[int]
    is_charging: Optional[bool]
    fen: Optional[str]


class StateResponse(BaseModel):
    fen: str
    board_fen: str
    turn: str
    pgn: Optional[str]
    updated_at: str
    driver: DriverStatusResponse


class UpdateResponse(StateResponse):
    driver_synced: bool


class DriverCommandResponse(BaseModel):
    success: bool
    message: str
    driver: DriverStatusResponse


def _driver_status(driver: Optional[ChessnutDriver]) -> DriverStatusResponse:
    if driver is None:
        return DriverStatusResponse(
            enabled=False,
            connected=False,
            device_name=None,
            device_address=None,
            firmware_version=None,
            battery_level=None,
            is_charging=None,
            fen=None,
        )

    status = driver.get_status()
    return DriverStatusResponse(
        enabled=True,
        connected=status.connected,
        device_name=status.device_name,
        device_address=status.device_address,
        firmware_version=status.firmware_version,
        battery_level=status.battery_level,
        is_charging=status.is_charging,
        fen=status.fen,
    )


async def _sync_driver(
    driver: Optional[ChessnutDriver], fen: str, force: bool
) -> bool:
    if driver is None or not driver.is_connected:
        return False
    return await driver.set_position(fen, force=force)


def _state_response(state: AppState, driver: Optional[ChessnutDriver]) -> StateResponse:
    snap = snapshot(state)
    return StateResponse(
        fen=snap.fen,
        board_fen=snap.board_fen,
        turn=snap.turn,
        pgn=snap.pgn,
        updated_at=snap.updated_at,
        driver=_driver_status(driver),
    )


def create_app(config: ServerConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = StateStore(initial_state())
        driver = ChessnutDriver() if config.enable_driver else None

        app.state.store = store
        app.state.driver = driver
        app.state.config = config

        if driver is not None:
            def on_position(board: chess.Board) -> None:
                asyncio.create_task(
                    store.update(lambda state: apply_fen(state, board.fen()))
                )

            driver.on_position_change(on_position)

            if config.auto_connect:
                asyncio.create_task(driver.connect())

        yield

        if driver is not None:
            await driver.disconnect()

    app = FastAPI(
        title="Chessnut Move Stack",
        description="Driver + server for Chessnut Move board",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        driver = app.state.driver
        return {
            "status": "ok",
            "driver_enabled": driver is not None,
            "driver_connected": driver.is_connected if driver else False,
        }

    @app.get("/api/state", response_model=StateResponse)
    async def get_state():
        store: StateStore = app.state.store
        driver: Optional[ChessnutDriver] = app.state.driver
        state = await store.get()
        return _state_response(state, driver)

    @app.post("/api/state/fen", response_model=UpdateResponse)
    async def set_state_fen(request: FenRequest):
        store: StateStore = app.state.store
        driver: Optional[ChessnutDriver] = app.state.driver

        try:
            state = await store.update(lambda s: apply_fen(s, request.fen))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        synced = await _sync_driver(driver, state.fen, request.force)
        response = _state_response(state, driver)
        return UpdateResponse(**response.model_dump(), driver_synced=synced)

    @app.post("/api/state/pgn", response_model=UpdateResponse)
    async def set_state_pgn(request: PgnRequest):
        store: StateStore = app.state.store
        driver: Optional[ChessnutDriver] = app.state.driver

        try:
            state = await store.update(lambda s: apply_pgn(s, request.pgn))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        synced = await _sync_driver(driver, state.fen, request.force)
        response = _state_response(state, driver)
        return UpdateResponse(**response.model_dump(), driver_synced=synced)

    @app.post("/api/state/reset", response_model=UpdateResponse)
    async def reset_state():
        store: StateStore = app.state.store
        driver: Optional[ChessnutDriver] = app.state.driver

        state = await store.update(lambda s: apply_fen(s, chess.STARTING_FEN))
        synced = await _sync_driver(driver, state.fen, True)
        response = _state_response(state, driver)
        return UpdateResponse(**response.model_dump(), driver_synced=synced)

    @app.get("/api/driver/status", response_model=DriverStatusResponse)
    async def driver_status():
        driver: Optional[ChessnutDriver] = app.state.driver
        return _driver_status(driver)

    @app.post("/api/driver/connect", response_model=DriverCommandResponse)
    async def driver_connect():
        driver: Optional[ChessnutDriver] = app.state.driver
        if driver is None:
            raise HTTPException(status_code=400, detail="Driver disabled")

        success = await driver.connect()
        return DriverCommandResponse(
            success=success,
            message="Connected" if success else "Connection failed",
            driver=_driver_status(driver),
        )

    @app.post("/api/driver/disconnect", response_model=DriverCommandResponse)
    async def driver_disconnect():
        driver: Optional[ChessnutDriver] = app.state.driver
        if driver is None:
            raise HTTPException(status_code=400, detail="Driver disabled")

        await driver.disconnect()
        return DriverCommandResponse(
            success=True,
            message="Disconnected",
            driver=_driver_status(driver),
        )

    return app


def main() -> None:
    import uvicorn

    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level)


if __name__ == "__main__":
    main()
