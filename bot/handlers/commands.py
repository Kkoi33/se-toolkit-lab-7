"""
Command handlers for the Telegram bot.

Each handler is a pure function that takes no arguments (or simple arguments)
and returns a string response. This makes them testable without Telegram.
"""


def handle_start() -> str:
    """Handle /start command - welcome message."""
    return """Welcome to SE Toolkit Bot! 🤖

I can help you with information about labs, scores, and students.

Quick actions (buttons below):
- 📋 Available Labs
- 💪 Health Check
- 📊 Scores for specific labs
- 🏆 Top students
- 👥 Groups performance

Or just ask me a question like:
• "which lab has the lowest pass rate?"
• "show me scores for lab 4"
• "who are the top 5 students?"

Use /help to see all commands."""


def handle_help() -> str:
    """Handle /help command - list of available commands."""
    return """Available commands:

/start - Welcome message
/help - Show this help message
/health - Check backend connection status
/labs - List available labs
/scores <lab_name> - Get scores for a specific lab

Example: /scores lab-04
"""


def handle_health() -> str:
    """Handle /health command - backend health check (placeholder)."""
    # TODO: Implement real health check in Task 2
    return "Health check: Backend connection status (not yet implemented)"


def handle_labs() -> str:
    """Handle /labs command - list available labs (placeholder)."""
    # TODO: Implement real labs listing in Task 2
    return "Available labs: (not yet implemented)"


def handle_scores(lab_name: str = None) -> str:
    """
    Handle /scores command - get scores for a lab.

    Args:
        lab_name: Name of the lab (e.g., 'lab-04')

    Returns:
        Scores information for the specified lab
    """
    if lab_name is None:
        return "Usage: /scores <lab_name>\nExample: /scores lab-04"

    # TODO: Implement real scores lookup in Task 2
    return f"Scores for {lab_name}: (not yet implemented)"
