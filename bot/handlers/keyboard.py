"""
Inline keyboard buttons for Telegram bot.

Provides quick action buttons for common queries.
"""


def get_main_keyboard():
    """
    Get main inline keyboard with common actions.

    Returns:
        List of button rows for Telegram InlineKeyboardMarkup
    """
    # Import here to avoid errors when telegram is not installed
    from telegram import InlineKeyboardButton
    
    return [
        [
            InlineKeyboardButton("📋 Available Labs", callback_data="cmd_labs"),
            InlineKeyboardButton("💪 Health Check", callback_data="cmd_health"),
        ],
        [
            InlineKeyboardButton("📊 Scores Lab 04", callback_data="cmd_scores_lab04"),
            InlineKeyboardButton("📊 Scores Lab 03", callback_data="cmd_scores_lab03"),
        ],
        [
            InlineKeyboardButton("🏆 Top 5 Students", callback_data="cmd_top5"),
            InlineKeyboardButton("👥 Groups Performance", callback_data="cmd_groups"),
        ],
    ]


def get_lab_selection_keyboard() -> list:
    """
    Get keyboard for selecting a lab.
    
    Returns:
        List of button rows for lab selection
    """
    return [
        [
            {"text": "Lab 01", "callback_data": "select_lab_lab-01"},
            {"text": "Lab 02", "callback_data": "select_lab_lab-02"},
        ],
        [
            {"text": "Lab 03", "callback_data": "select_lab_lab-03"},
            {"text": "Lab 04", "callback_data": "select_lab_lab-04"},
        ],
        [
            {"text": "Lab 05", "callback_data": "select_lab_lab-05"},
            {"text": "Lab 06", "callback_data": "select_lab_lab-06"},
        ],
    ]


def get_back_keyboard() -> list:
    """
    Get simple back button.
    
    Returns:
        List with single back button row
    """
    return [
        [{"text": "« Back to Menu", "callback_data": "cmd_back"}],
    ]


def format_keyboard_description() -> str:
    """
    Format a text description of available keyboard actions.
    
    Returns:
        String describing available quick actions
    """
    return """
Quick actions available:
- 📋 Available Labs — List all labs
- 💪 Health Check — Check backend status
- 📊 Scores — View scores for specific labs
- 🏆 Top 5 Students — See top performers
- 👥 Groups Performance — Compare groups

You can also type questions like:
- "which lab has the lowest pass rate?"
- "show me scores for lab 4"
- "who are the top students?"
"""
