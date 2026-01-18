"""HTTP client for the Chessnut Move server."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ClientConfig:
    base_url: str = "http://127.0.0.1:8675"
    timeout: float = 10.0


def build_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


class ChessnutServerClient:
    def __init__(self, config: ClientConfig | None = None) -> None:
        self._config = config or ClientConfig()
        self._client = httpx.Client(
            base_url=self._config.base_url, timeout=self._config.timeout
        )

    def close(self) -> None:
        self._client.close()

    def get_state(self) -> dict:
        return self._client.get("/api/state").json()

    def set_fen(self, fen: str, force: bool = True) -> dict:
        payload = {"fen": fen, "force": force}
        return self._client.post("/api/state/fen", json=payload).json()

    def set_pgn(self, pgn: str, force: bool = True) -> dict:
        payload = {"pgn": pgn, "force": force}
        return self._client.post("/api/state/pgn", json=payload).json()

    def reset(self) -> dict:
        return self._client.post("/api/state/reset").json()

    def driver_status(self) -> dict:
        return self._client.get("/api/driver/status").json()

    def driver_connect(self) -> dict:
        return self._client.post("/api/driver/connect").json()

    def driver_disconnect(self) -> dict:
        return self._client.post("/api/driver/disconnect").json()

    def __enter__(self) -> "ChessnutServerClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
