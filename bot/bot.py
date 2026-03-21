#!/usr/bin/env python3
"""
Telegram bot entry point.

Supports two modes:
- Normal mode: connects to Telegram and handles updates
- Test mode (--test): calls handlers directly for offline testing

Usage:
    uv run bot.py --test "/start"    # Test mode
    uv run bot.py                     # Normal Telegram mode
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from handlers.commands import (
    handle_start,
    handle_help,
    handle_health,
    handle_labs,
    handle_scores,
)


def get_handler_for_command(command: str) -> callable:
    """Route command to appropriate handler."""
    command = command.lstrip("/")

    handlers = {
        "start": handle_start,
        "help": handle_help,
        "health": handle_health,
        "labs": handle_labs,
        "scores": handle_scores,
    }

    return handlers.get(command)


def run_test_mode(command: str) -> None:
    """Run handler directly and print result to stdout."""
    # Split command and arguments (e.g., "/scores lab-04" -> "scores", "lab-04")
    parts = command.strip().split(None, 1)
    cmd = parts[0].lstrip("/")
    arg = parts[1] if len(parts) > 1 else None

    handler = get_handler_for_command(cmd)

    if handler is None:
        print(f"Unknown command: {cmd}. Use /help to see available commands.")
        sys.exit(0)  # Exit with 0 - unknown commands should not crash

    if arg is not None:
        response = handler(arg)
    else:
        response = handler()
    print(response)
    sys.exit(0)


def run_telegram_mode() -> None:
    """Connect to Telegram and handle updates."""
    print("Starting Telegram bot...")
    # TODO: Implement Telegram connection in Task 2
    print("Telegram mode not yet implemented")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="SE Toolkit Telegram Bot")
    parser.add_argument(
        "--test",
        type=str,
        metavar="COMMAND",
        help="Run in test mode with the given command (e.g., '/start')",
    )

    args = parser.parse_args()

    if args.test:
        run_test_mode(args.test)
    else:
        run_telegram_mode()


if __name__ == "__main__":
    main()
