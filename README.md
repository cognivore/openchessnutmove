# Chessnut Move Stack

Clean driver, server, and client layers for the Chessnut Move board.

## Overview

- `driver`: BLE transport + protocol encoding for the physical board.
- `server`: FastAPI service that owns application state (FEN/PGN) and
  syncs it to the board via the driver.
- `client`: HTTP client + CLI for third-party consumers that want to set
  the board using FEN or PGN.

```
client  ->  server  ->  driver  ->  Chessnut Move board
```

## Quickstart

### Nix (recommended)

```
nix develop
python -m chessnut_move_stack.server
```

### Plain virtualenv

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m chessnut_move_stack.server
```

## Client usage

```
python -m chessnut_move_stack.client state
python -m chessnut_move_stack.client set-fen "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
python -m chessnut_move_stack.client set-pgn --file ./game.pgn
python -m chessnut_move_stack.client driver-autoconnect --enable
python -m chessnut_move_stack.client driver-autoconnect --disable
```

## Server API (HTTP)

- `GET /api/state` -> current state snapshot
- `POST /api/state/fen` -> set position from FEN
- `POST /api/state/pgn` -> set position from PGN (final position)
- `POST /api/state/reset` -> reset to starting position
- `GET /api/driver/status` -> driver/board status
- `POST /api/driver/connect` -> connect to board
- `POST /api/driver/disconnect` -> disconnect from board
- `POST /api/driver/autoconnect` -> toggle auto-connect loop (`{"enabled": true}`)

## Configuration

Environment variables:

- `CHESSNUT_DRIVER=off` to run the server without hardware.
- `CHESSNUT_AUTO_CONNECT=0` to disable auto-connect on startup (can be toggled via API).
- `CHESSNUT_HOST`, `CHESSNUT_PORT`, `CHESSNUT_LOG_LEVEL` for server options.

## Notes

- FEN strings may be full FEN or board-only. Missing fields are filled
  with defaults in the server (`w KQkq - 0 1`).
- BLE uses `bleak`. On macOS, grant Bluetooth permissions to Python.
