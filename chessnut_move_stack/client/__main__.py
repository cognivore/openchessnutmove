"""CLI for the Chessnut Move server client."""

from __future__ import annotations

import argparse
import json
import sys

from chessnut_move_stack.client.api import (
    ChessnutServerClient,
    ClientConfig,
    build_base_url,
)


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _resolve_base_url(args: argparse.Namespace) -> str:
    if args.base_url:
        return args.base_url
    return build_base_url(args.host, args.port)


def _load_pgn(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            return handle.read()
    if args.pgn:
        return args.pgn
    raise ValueError("Provide --file or --pgn")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chessnut Move server client")
    parser.add_argument("--base-url", help="Server base URL")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8675)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("state", help="Get current server state")

    fen_parser = subparsers.add_parser("set-fen", help="Set position from FEN")
    fen_parser.add_argument("fen", help="FEN string")
    fen_parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Force immediate movement (default: true)",
    )

    pgn_parser = subparsers.add_parser("set-pgn", help="Set position from PGN")
    pgn_group = pgn_parser.add_mutually_exclusive_group(required=True)
    pgn_group.add_argument("--file", help="PGN file path")
    pgn_group.add_argument("--pgn", help="PGN text")
    pgn_parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Force immediate movement (default: true)",
    )

    subparsers.add_parser("reset", help="Reset to starting position")
    subparsers.add_parser("driver-status", help="Get driver status")
    subparsers.add_parser("driver-connect", help="Connect to the board")
    subparsers.add_parser("driver-disconnect", help="Disconnect from the board")

    args = parser.parse_args()
    base_url = _resolve_base_url(args)

    config = ClientConfig(base_url=base_url)
    with ChessnutServerClient(config) as client:
        if args.command == "state":
            _print_json(client.get_state())
            return 0
        if args.command == "set-fen":
            _print_json(client.set_fen(args.fen, force=args.force))
            return 0
        if args.command == "set-pgn":
            pgn_text = _load_pgn(args)
            _print_json(client.set_pgn(pgn_text, force=args.force))
            return 0
        if args.command == "reset":
            _print_json(client.reset())
            return 0
        if args.command == "driver-status":
            _print_json(client.driver_status())
            return 0
        if args.command == "driver-connect":
            _print_json(client.driver_connect())
            return 0
        if args.command == "driver-disconnect":
            _print_json(client.driver_disconnect())
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
