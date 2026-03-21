"""
Message handlers for plain text messages.

Used in Task 3 for LLM-based intent routing.
"""


def handle_unknown_message(message: str) -> str:
    """
    Handle messages that don't match any known intent.
    
    Args:
        message: The user's message text
        
    Returns:
        A helpful response suggesting available commands
    """
    return f"I didn't understand: '{message}'\n\nTry /help to see available commands."
