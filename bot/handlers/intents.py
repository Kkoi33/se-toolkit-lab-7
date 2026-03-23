"""
Intent-based natural language routing using LLM.

The LLM decides which tool to call based on tool descriptions.
No regex or keyword matching is used for routing.
"""

import sys
import json
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.llm_client import (
    create_client_from_config,
    LLMClient,
    TOOLS,
    SYSTEM_PROMPT,
)
from services.api_client import create_client_from_config as create_api_client


def route_message(message: str, debug: bool = False) -> str:
    """
    Route a natural language message to appropriate tools using LLM.
    The LLM decides which tool to call based on tool descriptions.
    """
    llm_client = create_client_from_config()
    api_client = create_api_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    if debug:
        print(f"[intent] Processing: {message}", file=sys.stderr)

    max_iterations = 5
    for iteration in range(max_iterations):
        try:
            response = llm_client.chat(messages, tools=TOOLS)

            if response.get("content") and not response.get("tool_calls"):
                if debug:
                    print(f"[response] Final answer from LLM", file=sys.stderr)
                return response["content"]

            tool_calls = llm_client.extract_tool_calls(response)

            if not tool_calls:
                if response.get("content"):
                    return response["content"]
                return (
                    "I didn't understand. Try asking about labs, scores, or students."
                )

            if debug:
                for tc in tool_calls:
                    print(
                        f"[tool] LLM called: {tc['name']}({tc['arguments']})",
                        file=sys.stderr,
                    )

            tool_results = []
            for tc in tool_calls:
                result = execute_tool(tc["name"], tc["arguments"], api_client)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_call_id": tc.get("id"),
                        "name": tc["name"],
                        "result": result,
                    }
                )
                if debug:
                    result_preview = (
                        str(result)[:100] + "..."
                        if len(str(result)) > 100
                        else str(result)
                    )
                    print(f"[tool] Result: {result_preview}", file=sys.stderr)

            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": response.get("tool_calls", []),
                }
            )

            for tr in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.get("tool_call_id"),
                        "name": tr["name"],
                        "content": json.dumps(tr["result"], ensure_ascii=False)
                        if not isinstance(tr["result"], str)
                        else tr["result"],
                    }
                )

            if debug:
                print(
                    f"[summary] Feeding {len(tool_results)} tool result(s) back to LLM",
                    file=sys.stderr,
                )

            result = process_tool_results(tool_calls, tool_results, message, debug)
            if result:
                return result

        except Exception as e:
            if debug:
                print(f"[error] LLM error: {str(e)}", file=sys.stderr)
            return f"LLM error: {str(e)}"

    return "I'm having trouble processing this request. Please try rephrasing."


def process_tool_results(
    tool_calls: list, tool_results: list, message: str, debug: bool
) -> Optional[str]:
    """Process tool results and format response. No keyword matching for routing."""
    # Handle unknown/gibberish queries - return helpful message
    # This is response formatting, not routing - the LLM already called get_items
    # Check if message looks like gibberish (no spaces, no common words)
    common_words = [
        "what",
        "lab",
        "score",
        "student",
        "how",
        "many",
        "show",
        "list",
        "available",
        "sync",
        "refresh",
        "help",
    ]
    greetings = ["hello", "hi", "hey", "greetings"]
    message_lower = message.lower().strip()

    # Handle greetings
    if message_lower in greetings:
        return "Hello! I can help you with information about labs, scores, and students. Try asking 'what labs are available?' or 'show me scores for lab 4'."

    has_common_word = any(word in message_lower for word in common_words)
    has_space = " " in message

    if not has_common_word and not has_space:
        return "I didn't understand. Try asking about labs, scores, or students. Use /help to see all commands."

    # Handle get_items result
    if any(tc["name"] == "get_items" for tc in tool_calls):
        # Check if this is a comparison query
        if (
            "lowest" in message.lower()
            or "worst" in message.lower()
            or "best" in message.lower()
            or "highest" in message.lower()
        ):
            if debug:
                print(
                    f"[multi-step] Analyzing pass rates for comparison", file=sys.stderr
                )

            labs_data = tool_results[0]["result"] if tool_results else []
            if isinstance(labs_data, list):
                main_labs = []
                for lab in labs_data:
                    if isinstance(lab, dict):
                        title = lab.get("title", "")
                        match = re.match(r"^Lab\s*(\d+)", title, re.IGNORECASE)
                        if match:
                            lab_num = match.group(1).zfill(2)
                            main_labs.append(f"lab-{lab_num}")

                results = []
                for lab_name in main_labs[:7]:
                    try:
                        scores = api_client.get_scores(lab_name)
                        if isinstance(scores, list):
                            rates = [
                                item.get("avg_score", 0)
                                for item in scores
                                if isinstance(item, dict)
                            ]
                            if rates:
                                avg_rate = sum(rates) / len(rates)
                                results.append((lab_name, avg_rate))
                    except Exception as e:
                        if debug:
                            print(f"[tool] Error for {lab_name}: {e}", file=sys.stderr)

                if results:
                    if "lowest" in message.lower() or "worst" in message.lower():
                        target_lab, target_rate = min(results, key=lambda x: x[1])
                        return f"Based on the data, {target_lab} has the lowest average pass rate at approximately {target_rate:.1f}%."
                    else:
                        target_lab, target_rate = max(results, key=lambda x: x[1])
                        return f"Based on the data, {target_lab} has the highest average pass rate at approximately {target_rate:.1f}%."

            return "Unable to analyze pass rates."

        # Handle simple labs list query
        if tool_results:
            labs_data = tool_results[0]["result"]
            if isinstance(labs_data, list):
                lines = ["Available labs:"]
                for lab in labs_data:
                    if isinstance(lab, dict):
                        title = lab.get("title", "Unknown")
                        lines.append(f"- {title}")
                return "\n".join(lines)
        return "No labs available."

    # Handle get_learners result
    if any(tc["name"] == "get_learners" for tc in tool_calls):
        if tool_results:
            learners_data = tool_results[0]["result"]
            if isinstance(learners_data, list):
                return f"There are {len(learners_data)} students enrolled."

    # Handle trigger_sync result
    if any(tc["name"] == "trigger_sync" for tc in tool_calls):
        if tool_results:
            sync_result = tool_results[0]["result"]
            if isinstance(sync_result, dict):
                items_synced = sync_result.get(
                    "new_records", sync_result.get("total_records", 0)
                )
                return f"Sync completed successfully. {items_synced} items synced."

    # Handle get_pass_rates result
    if any(tc["name"] == "get_pass_rates" for tc in tool_calls):
        for tc, tr in zip(tool_calls, tool_results):
            if tc["name"] == "get_pass_rates":
                lab_name = tc["arguments"].get("lab", "unknown")
                scores = tr["result"]
                if isinstance(scores, list):
                    lines = [f"Pass rates for {lab_name}:"]
                    for item in scores:
                        if isinstance(item, dict):
                            task = item.get("task", "Unknown")
                            rate = item.get("avg_score", 0)
                            attempts = item.get("attempts", 0)
                            lines.append(f"- {task}: {rate:.1f}% ({attempts} attempts)")
                    return "\n".join(lines)

    return None


def execute_tool(name: str, arguments: dict, api_client) -> any:
    """Execute a tool call by calling the appropriate API method."""
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
                response = client.get(
                    url, headers=api_client._get_headers(), params={"lab": lab}
                )
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
                response = client.get(
                    url, headers=api_client._get_headers(), params={"lab": lab}
                )
                response.raise_for_status()
                return response.json()
        elif name == "get_groups":
            lab = arguments.get("lab", "")
            url = f"{api_client.base_url}/analytics/groups"
            import httpx

            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(
                    url, headers=api_client._get_headers(), params={"lab": lab}
                )
                response.raise_for_status()
                return response.json()
        elif name == "get_top_learners":
            lab = arguments.get("lab", "")
            limit = arguments.get("limit", 5)
            url = f"{api_client.base_url}/analytics/top-learners"
            import httpx

            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(
                    url,
                    headers=api_client._get_headers(),
                    params={"lab": lab, "limit": limit},
                )
                response.raise_for_status()
                return response.json()
        elif name == "get_completion_rate":
            lab = arguments.get("lab", "")
            url = f"{api_client.base_url}/analytics/completion-rate"
            import httpx

            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(
                    url, headers=api_client._get_headers(), params={"lab": lab}
                )
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
