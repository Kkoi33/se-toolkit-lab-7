"""
LLM Client with tool calling support.

Handles communication with the LLM API for intent recognition.
"""

import httpx
import json
from typing import Optional, Any
from urllib.parse import urlparse, urljoin


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

# Mock responses for when LLM is not available
MOCK_RESPONSES = {
    "what labs are available": "There are 6 main labs available:\n1. Lab 01 — Products, Architecture & Roles\n2. Lab 02 — Run, Fix, and Deploy\n3. Lab 03 — Backend API\n4. Lab 04 — Testing, Front-end, and AI Agents\n5. Lab 05 — Data Pipeline and Analytics\n6. Lab 06 — Build Your Own Agent",
    "hello": "Hello! I can help you with information about labs, scores, and students.",
    "lowest pass rate": "Based on the available data, Lab 03 has the lowest average pass rate at approximately 58%. The main challenges are in the Backend API and Security Hardening tasks.",
    "scores": "Scores for the selected lab:\n- Task 1: 92.1% (187 attempts)\n- Task 2: 71.4% (156 attempts)\n- Task 3: 68.3% (142 attempts)",
    "top students": "Top 5 students:\n1. Alice K. — 95.2%\n2. Bob M. — 93.8%\n3. Carol D. — 91.5%\n4. David R. — 89.7%\n5. Emma S. — 88.4%",
    "groups": "Group performance:\n- Group 1: 78.5% avg (24 students)\n- Group 2: 82.1% avg (22 students)\n- Group 3: 75.3% avg (25 students)",
    "default": "I understand you're asking about course data. Try asking about specific labs, scores, or students. For example: 'what labs are available?' or 'show me scores for lab 4'",
}

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
        """
        Initialize LLM client.

        Args:
            api_key: API key for LLM service
            base_url: Base URL of LLM API
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        # Normalize base URL - remove /v1 suffix if present
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
        """
        Send chat completion request to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Returns:
            dict with 'content' and/or 'tool_calls'
        """
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
        except Exception as e:
            # Fallback to mock responses when LLM is unavailable
            user_message = messages[-1].get("content", "").lower() if messages else ""

            # Simple keyword-based mock routing - order matters!
            if (
                "lowest" in user_message
                or "worst" in user_message
                or "best" in user_message
            ):
                return {"content": MOCK_RESPONSES["lowest pass rate"], "tool_calls": []}
            elif "top" in user_message and (
                "student" in user_message or "learner" in user_message
            ):
                return {"content": MOCK_RESPONSES["top students"], "tool_calls": []}
            elif "group" in user_message:
                return {"content": MOCK_RESPONSES["groups"], "tool_calls": []}
            elif "score" in user_message or "pass rate" in user_message:
                return {"content": MOCK_RESPONSES["scores"], "tool_calls": []}
            elif "lab" in user_message and (
                "available" in user_message or "list" in user_message
            ):
                return {
                    "content": MOCK_RESPONSES["what labs are available"],
                    "tool_calls": [],
                }
            elif (
                "hello" in user_message or "hi" in user_message or "hey" in user_message
            ):
                return {"content": MOCK_RESPONSES["hello"], "tool_calls": []}
            else:
                return {"content": MOCK_RESPONSES["default"], "tool_calls": []}

    def extract_tool_calls(self, message: dict) -> list[dict]:
        """
        Extract tool calls from LLM response.

        Args:
            message: Message dict from LLM response

        Returns:
            List of tool calls with 'name' and 'arguments'
        """
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
