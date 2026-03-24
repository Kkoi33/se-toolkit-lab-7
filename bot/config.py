"""
Configuration loader for the bot.

Loads environment variables from .env.bot.secret file.
Uses python-dotenv for loading.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def load_config() -> dict[str, str]:
    """
    Load configuration from environment variables.

    Returns:
        Dictionary with configuration values
    """
    # Path to .env file in the bot directory
    env_file = Path(__file__).parent / ".env"

    # Load environment variables from file
    if env_file.exists():
        load_dotenv(env_file)

    return {
        "BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("BOT_TOKEN", "")),
        "LMS_API_BASE_URL": os.getenv("LMS_API_BASE_URL", "http://localhost:42002"),
        "LMS_API_KEY": os.getenv("LMS_API_KEY", "six-seven"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY", "six-seven"),
        "LLM_API_BASE_URL": os.getenv("LLM_API_BASE_URL", "http://localhost:42005"),
        "LLM_MODEL": os.getenv("LLM_API_MODEL", "coder-model"),
        "BACKEND_URL": os.getenv("BACKEND_URL", "http://localhost:42002"),
    }


def get_config(key: str, default: str = "") -> str:
    """Get a specific configuration value."""
    config = load_config()
    return config.get(key, default)
