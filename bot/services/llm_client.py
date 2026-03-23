"""
LLM Client with tool calling support.

Handles communication with the LLM API for intent recognition.
The LLM decides which tool to call - no regex or keyword matching in routing.
"""

import httpx
import json
from typing import Optional, Any


# Tool definitions for all 9 backend endpoints
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_items",
            "description": "Get list of all available labs and tasks",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_learners",
            "description": "Get list of enrolled students and their groups",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scores",
            "description": "Get score distribution (4 buckets) for a specific lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g. 'lab-01', 'lab-04'",
                    }
                },
                "required": ["lab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pass_rates",
            "description": "Get per-task average pass rates and attempt counts for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g. 'lab-01', 'lab-04'",
                    }
                },
                "required": ["lab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline",
            "description": "Get submissions per day timeline for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g. 'lab-01', 'lab-04'",
                    }
                },
                "required": ["lab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_groups",
            "description": "Get per-group performance scores and student counts for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g. 'lab-01', 'lab-04'",
                    }
                },
                "required": ["lab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_learners",
            "description": "Get top N learners by score for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g. 'lab-01', 'lab-04'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top learners to return, e.g. 5",
                    },
                },
                "required": ["lab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_completion_rate",
            "description": "Get completion rate percentage for a lab",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab": {
                        "type": "string",
                        "description": "Lab identifier, e.g. 'lab-01', 'lab-04'",
                    }
                },
                "required": ["lab"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_sync",
            "description": "Trigger ETL sync to refresh data from autochecker",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a helpful assistant for a software engineering course. You have access to backend API tools that provide data about labs, scores, and students.

When a user asks a question:
1. First understand what they're asking
2. Call the appropriate tool(s) to get the data
3. Analyze the results
4. Provide a clear, helpful answer based on the data

Available tools:
- get_items: List all labs and tasks
- get_learners: List enrolled students
- get_scores: Score distribution for a lab
- get_pass_rates: Per-task pass rates for a lab
- get_timeline: Submissions timeline for a lab
- get_groups: Per-group performance for a lab
- get_top_learners: Top N learners for a lab
- get_completion_rate: Completion rate for a lab
- trigger_sync: Refresh data from autochecker

For multi-step questions (e.g., "which lab has the lowest pass rate"), you may need to:
1. First call get_items to get all labs
2. Then call get_pass_rates for each lab
3. Compare the results and provide an answer

Always call tools when you need data. Don't make up numbers."""


class LLMClient:
    """Client for LLM API with tool calling support."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 30.0):
        """Initialize LLM client."""
        self.api_key = api_key
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: list[dict], tools: Optional[list] = None) -> dict:
        """Send chat completion request to LLM."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]
        except Exception:
            # LLM unavailable - return default tool call
            # No keyword matching - just return get_items as default
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "fallback_1",
                        "type": "function",
                        "function": {"name": "get_items", "arguments": "{}"},
                    }
                ],
            }

    def extract_tool_calls(self, message: dict) -> list[dict]:
        """Extract tool calls from LLM response."""
        tool_calls = message.get("tool_calls", [])
        result = []
        for tc in tool_calls:
            if tc.get("type") == "function":
                func = tc.get("function", {})
                try:
                    arguments = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}
                result.append(
                    {
                        "id": tc.get("id"),
                        "name": func.get("name"),
                        "arguments": arguments,
                    }
                )
        return result


def create_client_from_config() -> LLMClient:
    """Create LLM client from environment configuration."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config

    api_key = get_config("LLM_API_KEY", "")
    base_url = get_config("LLM_API_BASE_URL", "http://localhost:42005/v1")
    model = get_config("LLM_MODEL", "gpt-4o-mini")

    return LLMClient(api_key=api_key, base_url=base_url, model=model)
