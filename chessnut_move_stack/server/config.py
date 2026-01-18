"""Server configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    log_level: str
    auto_connect: bool
    enable_driver: bool


def load_config(env: dict[str, str] | None = None) -> ServerConfig:
    env = env or os.environ

    host = env.get("CHESSNUT_HOST", "127.0.0.1")
    port = int(env.get("CHESSNUT_PORT", "8675"))
    log_level = env.get("CHESSNUT_LOG_LEVEL", "info").lower()

    driver_env = env.get("CHESSNUT_DRIVER", "on").strip().lower()
    enable_driver = driver_env not in {"0", "false", "off", "disabled"}

    auto_connect = _env_bool(env.get("CHESSNUT_AUTO_CONNECT"), True)

    if not enable_driver:
        auto_connect = False

    return ServerConfig(
        host=host,
        port=port,
        log_level=log_level,
        auto_connect=auto_connect,
        enable_driver=enable_driver,
    )
