"""
Command handlers for the Telegram bot.

Each handler is a pure function that takes no arguments (or simple arguments)
and returns a string response. This makes them testable without Telegram.
"""

import httpx
from typing import Optional


def _get_client():
    """Lazy import of LMS client to avoid circular imports."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from services.api_client import create_client_from_config

    return create_client_from_config()


def handle_start() -> str:
    """Handle /start command - welcome message."""
    return "Welcome to SE Toolkit Bot! 🤖\n\nUse /help to see available commands."


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
        client = _get_client()
        result = client.get_health()
        if result.get("healthy"):
            count = result.get("item_count", 0)
            return f"Backend is healthy. {count} items available."
        else:
            return "Backend returned unhealthy status."
    except httpx.ConnectError as e:
        return (
            f"Backend error: connection refused. Check that the services are running."
        )
    except httpx.HTTPStatusError as e:
        return f"Backend error: HTTP {e.response.status_code} {e.response.reason_phrase}. The backend service may be down."
    except httpx.RequestError as e:
        return f"Backend error: {str(e)}. Check that the services are running."
    except Exception as e:
        return f"Backend error: {str(e)}"


def handle_labs() -> str:
    """Handle /labs command - list available labs."""
    try:
        client = _get_client()
        labs = client.get_labs()
        if not labs:
            return "No labs available."

        lines = ["Available labs:"]
        for lab in labs:
            if isinstance(lab, dict):
                name = lab.get("name", lab.get("slug", "Unknown"))
                title = lab.get("title", lab.get("name", ""))
                lines.append(f"- {name} — {title}")
            else:
                lines.append(f"- {lab}")

        return "\n".join(lines)
    except httpx.ConnectError as e:
        return (
            f"Backend error: connection refused. Check that the services are running."
        )
    except httpx.HTTPStatusError as e:
        return f"Backend error: HTTP {e.response.status_code} {e.response.reason_phrase}. The backend service may be down."
    except httpx.RequestError as e:
        return f"Backend error: {str(e)}"
    except Exception as e:
        return f"Backend error: {str(e)}"


def handle_scores(lab_name: Optional[str] = None) -> str:
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
        client = _get_client()
        scores = client.get_scores(lab_name)

        if not scores:
            return f"No scores found for {lab_name}."

        lines = [f"Pass rates for {lab_name}:"]

        if isinstance(scores, dict):
            for task_name, data in scores.items():
                if isinstance(data, dict):
                    rate = data.get("pass_rate", data.get("rate", 0)) * 100
                    attempts = data.get("attempts", 0)
                    lines.append(f"- {task_name}: {rate:.1f}% ({attempts} attempts)")
                elif isinstance(data, (int, float)):
                    lines.append(f"- {task_name}: {data:.1f}%")
        elif isinstance(scores, list):
            for item in scores:
                if isinstance(item, dict):
                    task = item.get("task", item.get("name", "Unknown"))
                    rate = item.get("pass_rate", item.get("rate", 0)) * 100
                    attempts = item.get("attempts", 0)
                    lines.append(f"- {task}: {rate:.1f}% ({attempts} attempts)")

        return "\n".join(lines)
    except httpx.ConnectError as e:
        return (
            f"Backend error: connection refused. Check that the services are running."
        )
    except httpx.HTTPStatusError as e:
        return f"Backend error: HTTP {e.response.status_code} {e.response.reason_phrase}. The backend service may be down."
    except httpx.RequestError as e:
        return f"Backend error: {str(e)}"
    except Exception as e:
        return f"Backend error: {str(e)}"
