"""
Command handlers for the Telegram bot.

Each handler is a pure function that takes no arguments (or simple arguments)
and returns a string response. This makes them testable without Telegram.
"""

from services.api_client import create_client_from_config


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
    """Handle /health command - backend health check."""
    try:
        client = create_client_from_config()
        result = client.get_health()
        if result.get("healthy"):
            count = result.get("item_count", 0)
            return f"✅ Backend is healthy! {count} items available."
        else:
            return "❌ Backend returned unhealthy status."
    except Exception as e:
        return f"❌ Backend unavailable: {e}"


def handle_labs() -> str:
    """Handle /labs command - list available labs."""
    try:
        client = create_client_from_config()
        labs = client.get_labs()
        if not labs:
            return "No labs available."
        
        lines = ["📚 Available labs:"]
        for lab in labs[:10]:  # Limit to 10
            title = lab.get("title", "Unknown")
            lines.append(f"• {title}")
        
        if len(labs) > 10:
            lines.append(f"... and {len(labs) - 10} more")
        
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching labs: {e}"


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

    try:
        client = create_client_from_config()
        scores = client.get_scores(lab_name)
        
        if not scores:
            return f"No score data available for {lab_name}."
        
        lines = [f"📊 Scores for {lab_name}:"]
        for item in scores:
            if isinstance(item, dict):
                task = item.get("task", "Unknown")
                rate = item.get("avg_score", 0)
                attempts = item.get("attempts", 0)
                lines.append(f"• {task}: {rate:.1f}% ({attempts} attempts)")
        
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching scores: {e}"
