#!/usr/bin/env python3
"""
Telegram bot entry point.

Supports two modes:
- Normal mode: connects to Telegram and handles updates
- Test mode (--test): calls handlers directly for offline testing

Usage:
    uv run bot.py --test "/start"    # Test mode
    uv run bot.py --test "hello"     # Test mode with plain text
    uv run bot.py                     # Normal Telegram mode
"""

import argparse
import logging
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
from handlers.intents import route_message
from handlers.messages import handle_unknown_message
from config import get_config

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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

    # Check if it's a slash command
    if command.startswith("/"):
        handler = get_handler_for_command(cmd)

        if handler is None:
            print(f"Unknown command: {cmd}. Use /help to see available commands.")
            sys.exit(0)

        if arg is not None:
            response = handler(arg)
        else:
            response = handler()
        print(response)
        sys.exit(0)
    else:
        # Plain text message - use LLM routing
        response = route_message(command, debug=False)
        print(response)
        sys.exit(0)


def run_telegram_mode() -> None:
    """Connect to Telegram and handle updates."""
    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            CommandHandler,
            MessageHandler,
            ContextTypes,
            filters,
        )
    except ImportError:
        logger.error("python-telegram-bot not installed. Run: uv sync")
        sys.exit(1)

    # Get bot token from config
    bot_token = get_config("BOT_TOKEN", "")

    if not bot_token or bot_token == "<bot-token>":
        logger.error("BOT_TOKEN not configured in .env.bot.secret")
        sys.exit(1)

    logger.info(f"Starting Telegram bot...")

    async def handle_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle slash commands."""
        command = update.message.text
        parts = command.strip().split(None, 1)
        cmd = parts[0].lstrip("/").lower()
        arg = parts[1] if len(parts) > 1 else None

        handler = get_handler_for_command(cmd)

        if handler:
            if arg:
                response = handler(arg)
            else:
                response = handler()
        else:
            response = f"Unknown command: {cmd}. Use /help to see available commands."

        await update.message.reply_text(response)

    async def handle_message(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle plain text messages with LLM routing."""
        message_text = update.message.text

        # Check for greetings first
        if message_text.lower().strip() in ["hello", "hi", "hey"]:
            await update.message.reply_text(
                "Hello! I can help you with information about labs, scores, and students. "
                "Try asking 'what labs are available?' or 'show me scores for lab 4'."
            )
            return

        # Use LLM routing
        try:
            response = route_message(message_text, debug=False)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error. Please try again later."
            )

    # Create application
    app = Application.builder().token(bot_token).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", handle_command))
    app.add_handler(CommandHandler("help", handle_command))
    app.add_handler(CommandHandler("health", handle_command))
    app.add_handler(CommandHandler("labs", handle_command))
    app.add_handler(CommandHandler("scores", handle_command))

    # Add message handler for plain text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    logger.info("Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    parser = argparse.ArgumentParser(description="SE Toolkit Telegram Bot")
    parser.add_argument(
        "--test",
        type=str,
        metavar="MESSAGE",
        help="Run in test mode with the given message (e.g., '/start' or 'hello')",
    )

    args = parser.parse_args()

    if args.test:
        run_test_mode(args.test)
    else:
        run_telegram_mode()


if __name__ == "__main__":
    main()
