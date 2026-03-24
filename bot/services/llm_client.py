"""
LLM Client with tool calling support.

Handles communication with the LLM API for intent recognition.
The LLM decides which tool to call - no regex or keyword matching in routing.
"""

import httpx
import json
from typing import Optional, Any, List, Dict


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

CRITICAL: You MUST call tools to get data. Never make up numbers or guess.

When a user asks a question:
1. Identify what data you need
2. Call the appropriate tool(s) with correct parameters
3. Wait for tool results
4. Analyze the results
5. Provide a clear, specific answer with actual numbers and names from the data

Available tools:
- get_items: List all labs and tasks (no parameters) - use this first to get lab identifiers
- get_learners: List enrolled students and their groups (no parameters)
- get_scores: Score distribution for a specific lab (requires: lab)
- get_pass_rates: Per-task pass rates for a lab (requires: lab)
- get_timeline: Submissions timeline for a lab (requires: lab)
- get_groups: Per-group performance for a lab (requires: lab)
- get_top_learners: Top N learners (requires: lab, limit)
- get_completion_rate: Completion rate percentage (requires: lab)
- trigger_sync: Refresh data from autochecker (no parameters)

Examples:
- "what labs are available?" → call get_items(), then list the labs from results
- "show me scores for lab 4" → call get_pass_rates(lab="lab-04"), report the scores
- "how many students are enrolled?" → call get_learners(), count and report
- "which group is best in lab 3?" → call get_groups(lab="lab-03"), find highest scoring group
- "which lab has the lowest pass rate?" → call get_items(), then get_pass_rates for each lab, compare and report

For multi-step questions: You may need to call multiple tools. After receiving tool results, you can call more tools if needed.

Always include specific data in your answer: lab names, numbers, percentages, student counts."""


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

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
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
            # No keyword matching - always return get_items
            # The response formatting in intents.py will handle the rest
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

    def extract_tool_calls(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response."""
        tool_calls = message.get("tool_calls", [])
        result = []
        for tc in tool_calls:
            # Qwen may store function info directly or under 'function' key
            func = tc.get("function", {})
            if not func:
                # Try direct access for alternative formats
                func = tc if "name" in tc else {}
            
            name = func.get("name") or tc.get("name")
            if not name:
                continue
                
            arguments_str = func.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            
            result.append(
                {
                    "id": tc.get("id", f"call_{len(result)}"),
                    "name": name,
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
