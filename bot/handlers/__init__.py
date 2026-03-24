"""Command handlers - pure functions, no Telegram dependency."""

from .commands import (
    handle_start,
    handle_help,
    handle_health,
    handle_labs,
    handle_scores,
)
from .intents import route_message
from .messages import handle_unknown_message
from .keyboard import get_main_keyboard

__all__ = [
    "handle_start",
    "handle_help",
    "handle_health",
    "handle_labs",
    "handle_scores",
    "route_message",
    "handle_unknown_message",
    "get_main_keyboard",
]
