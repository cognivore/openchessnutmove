"""Module entry point for e2e tests."""

import sys

from chessnut_move_stack.e2e.stockfish_vs_stockfish import main

if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
