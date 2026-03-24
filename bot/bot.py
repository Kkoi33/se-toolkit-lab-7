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
from handlers.keyboard import get_main_keyboard
from config import get_config

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def get_handler_for_command(command: str) -> callable | None:
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


def run_test_mode(message: str) -> None:
    """
    Run handler directly and print result to stdout.

    Args:
        message: The message to process (command or plain text)
    """
    # Check if it's a slash command
    if message.strip().startswith("/"):
        # Split command and arguments
        parts = message.strip().split(None, 1)
        cmd = parts[0].lstrip("/").lower()
        arg = parts[1] if len(parts) > 1 else None

        handler = get_handler_for_command(cmd)

        if handler is None:
            print(
                f"Unknown command: {cmd}. Use /help to see available commands."
            )
            sys.exit(0)

        # Call handler with or without argument
        if arg is not None:
            response = handler(arg)
        else:
            response = handler()
        print(response)
    else:
        # Plain text message - use LLM routing
        try:
            response = route_message(message, debug=True)
            print(response)
        except Exception as e:
            logger.error(f"Error in LLM routing: {e}")
            # Fallback to helpful message
            response = handle_unknown_message(message)
            print(response)

    sys.exit(0)


def run_telegram_mode() -> None:
    """Connect to Telegram and handle updates."""
    try:
        from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
        from telegram.ext import (
            Application,
            CommandHandler,
            MessageHandler,
            ContextTypes,
            filters,
            CallbackQueryHandler,
        )
    except ImportError:
        logger.error(
            "python-telegram-bot not installed. Run: uv sync"
        )
        sys.exit(1)

    # Get bot token from config
    bot_token = get_config("BOT_TOKEN", "")

    if not bot_token or bot_token == "<bot-token>":
        logger.error("BOT_TOKEN not configured in .env.bot.secret")
        sys.exit(1)

    logger.info(f"Starting Telegram bot...")

    # Command handler
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
            try:
                if arg:
                    response = handler(arg)
                else:
                    response = handler()
            except Exception as e:
                logger.error(f"Error in handler {cmd}: {e}")
                response = f"Sorry, an error occurred: {e}"
        else:
            response = f"Unknown command: {cmd}. Use /help to see available commands."

        # Send with inline keyboard for /start
        if cmd == "start":
            keyboard = get_main_keyboard()
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(response)

    # Plain text message handler
    async def handle_message(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle plain text messages with LLM routing."""
        message_text = update.message.text

        try:
            response = route_message(message_text, debug=False)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Fallback to helpful message
            response = handle_unknown_message(message_text)
            await update.message.reply_text(response)

    # Callback query handler for inline buttons
    async def handle_callback(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data

        # Route callback data to appropriate action
        if data == "cmd_labs":
            response = handle_labs()
        elif data == "cmd_health":
            response = handle_health()
        elif data == "cmd_scores_lab04":
            response = handle_scores("lab-04")
        elif data == "cmd_scores_lab03":
            response = handle_scores("lab-03")
        elif data == "cmd_top5":
            # Use LLM routing for top learners
            try:
                response = route_message("show me top 5 students", debug=False)
            except Exception as e:
                response = "Top students feature coming soon!"
        elif data == "cmd_groups":
            # Use LLM routing for groups
            try:
                response = route_message("show me groups performance", debug=False)
            except Exception as e:
                response = "Groups feature coming soon!"
        elif data == "cmd_back":
            response = "What would you like to do?"
        else:
            response = "Feature coming soon!"

        await query.edit_message_text(text=response)

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

    # Add callback query handler for inline buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Start the bot
    logger.info("Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    """Main entry point."""
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
