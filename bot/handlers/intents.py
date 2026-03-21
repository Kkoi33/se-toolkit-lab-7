"""
Intent-based natural language routing using LLM.

Routes user messages to appropriate handlers based on LLM tool calls.
"""

import sys
import json
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.llm_client import create_client_from_config, LLMClient, TOOLS, SYSTEM_PROMPT
from services.api_client import create_client_from_config as create_api_client


def route_message(message: str, debug: bool = False) -> str:
    """
    Route a natural language message to appropriate tools and return response.

    Args:
        message: User's message text
        debug: If True, print debug info to stderr

    Returns:
        Bot's response text
    """
    llm_client = create_client_from_config()
    api_client = create_api_client()

    # Initial messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    if debug:
        print(f"[intent] Processing: {message}", file=sys.stderr)

    # Main loop: call LLM, execute tools, feed results back
    max_iterations = 5
    for iteration in range(max_iterations):
        try:
            # Call LLM
            response = llm_client.chat(messages, tools=TOOLS)
            
            # Check if LLM returned content directly (no tool calls)
            if response.get("content") and not response.get("tool_calls"):
                if debug:
                    print(f"[response] Final answer from LLM", file=sys.stderr)
                return response["content"]

            # Extract tool calls
            tool_calls = llm_client.extract_tool_calls(response)
            
            if not tool_calls:
                # LLM didn't call tools and didn't return content
                if response.get("content"):
                    return response["content"]
                return "I didn't understand. Try asking about labs, scores, or students."

            if debug:
                for tc in tool_calls:
                    print(f"[tool] LLM called: {tc['name']}({tc['arguments']})", file=sys.stderr)

            # Execute tool calls
            tool_results = []
            for tc in tool_calls:
                result = execute_tool(tc["name"], tc["arguments"], api_client)
                tool_results.append({
                    "type": "tool_result",
                    "tool_call_id": tc.get("id"),
                    "name": tc["name"],
                    "result": result,
                })
                if debug:
                    result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    print(f"[tool] Result: {result_preview}", file=sys.stderr)

            # Add assistant message with tool calls to conversation
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": response.get("tool_calls", []),
            })

            # Add tool results to conversation
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get("tool_call_id"),
                    "name": tr["name"],
                    "content": json.dumps(tr["result"], ensure_ascii=False) if not isinstance(tr["result"], str) else tr["result"],
                })

            if debug:
                print(f"[summary] Feeding {len(tool_results)} tool result(s) back to LLM", file=sys.stderr)

        except Exception as e:
            if debug:
                print(f"[error] LLM error: {str(e)}", file=sys.stderr)
            return f"LLM error: {str(e)}"

    return "I'm having trouble processing this request. Please try rephrasing."


def execute_tool(name: str, arguments: dict, api_client) -> any:
    """
    Execute a tool call by calling the appropriate API method.

    Args:
        name: Tool/function name
        arguments: Tool arguments dict
        api_client: LMS API client instance

    Returns:
        Tool execution result
    """
    try:
        if name == "get_items":
            return api_client.get_labs()
        
        elif name == "get_learners":
            url = f"{api_client.base_url}/learners/"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers())
                response.raise_for_status()
                return response.json()
        
        elif name == "get_scores":
            lab = arguments.get("lab", "")
            url = f"{api_client.base_url}/analytics/scores"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers(), params={"lab": lab})
                response.raise_for_status()
                return response.json()
        
        elif name == "get_pass_rates":
            lab = arguments.get("lab", "")
            return api_client.get_scores(lab)
        
        elif name == "get_timeline":
            lab = arguments.get("lab", "")
            url = f"{api_client.base_url}/analytics/timeline"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers(), params={"lab": lab})
                response.raise_for_status()
                return response.json()
        
        elif name == "get_groups":
            lab = arguments.get("lab", "")
            url = f"{api_client.base_url}/analytics/groups"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers(), params={"lab": lab})
                response.raise_for_status()
                return response.json()
        
        elif name == "get_top_learners":
            lab = arguments.get("lab", "")
            limit = arguments.get("limit", 5)
            url = f"{api_client.base_url}/analytics/top-learners"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers(), params={"lab": lab, "limit": limit})
                response.raise_for_status()
                return response.json()
        
        elif name == "get_completion_rate":
            lab = arguments.get("lab", "")
            url = f"{api_client.base_url}/analytics/completion-rate"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers(), params={"lab": lab})
                response.raise_for_status()
                return response.json()
        
        elif name == "trigger_sync":
            url = f"{api_client.base_url}/pipeline/sync"
            import httpx
            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.post(url, headers=api_client._get_headers(), json={})
                response.raise_for_status()
                return response.json()
        
        else:
            return f"Unknown tool: {name}"
    
    except Exception as e:
        return f"Error executing {name}: {str(e)}"


def handle_greeting(message: str) -> Optional[str]:
    """
    Check if message is a greeting and return appropriate response.

    Args:
        message: User's message

    Returns:
        Response string or None if not a greeting
    """
    greetings = ["hi", "hello", "hey", "привет", "здравствуйте"]
    if message.lower().strip() in greetings:
        return "Hello! I can help you with information about labs, scores, and students. Try asking 'what labs are available?' or 'show me scores for lab 4'."
    return None


def handle_fallback(message: str) -> str:
    """
    Handle messages that don't match any known pattern.

    Args:
        message: User's message

    Returns:
        Helpful fallback response
    """
    return f"I didn't understand: '{message}'\n\nTry asking about:\n- Available labs\n- Scores for a specific lab\n- Top students\n- Group performance\n\nOr use /help to see all commands."
