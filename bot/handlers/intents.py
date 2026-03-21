"""
Intent-based natural language routing using LLM.

The LLM decides which tool to call based on tool descriptions.
When LLM is unavailable, a simple fallback provides basic functionality.
"""

import sys
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional

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
    """Route a natural language message to appropriate tools and return response."""
    llm_client = create_client_from_config()
    api_client = create_api_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    if debug:
        print(f"[intent] Processing: {message}", file=sys.stderr)

    try:
        return _llm_routing(llm_client, api_client, messages, debug)
    except Exception as e:
        if debug:
            print(f"[intent] LLM failed: {str(e)}, using fallback", file=sys.stderr)
        return _fallback_routing(message, api_client, debug)


def _llm_routing(llm_client, api_client, messages: list, debug: bool) -> str:
    """Main LLM-based routing loop."""
    max_iterations = 5
    for iteration in range(max_iterations):
        response = llm_client.chat(messages, tools=TOOLS)

        if response.get("content") and not response.get("tool_calls"):
            if debug:
                print(f"[response] Final answer from LLM", file=sys.stderr)
            return response["content"]

        tool_calls = llm_client.extract_tool_calls(response)

        if not tool_calls:
            if response.get("content"):
                return response["content"]
            return "I didn't understand. Try asking about labs, scores, or students."

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
                    str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
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

    return "I'm having trouble processing this request. Please try rephrasing."


def _fallback_routing(message: str, api_client, debug: bool) -> str:
    """Fallback routing when LLM is unavailable."""
    msg_lower = message.lower()

    # "what labs are available" -> GET /items/
    if "lab" in msg_lower and (
        "available" in msg_lower or "what" in msg_lower or "list" in msg_lower
    ):
        try:
            if debug:
                print(f"[fallback] Calling get_items()", file=sys.stderr)
            labs = api_client.get_labs()
            if not labs:
                return "No labs available."
            lines = ["Available labs:"]
            for lab in labs:
                if isinstance(lab, dict):
                    title = lab.get("title", "Unknown")
                    lines.append(f"- {title}")
                else:
                    lines.append(f"- {lab}")
            return "\n".join(lines)
        except Exception as e:
            if debug:
                print(f"[fallback] Error: {str(e)}", file=sys.stderr)
            return f"Error fetching labs: {str(e)}"

    # "which lab has the lowest/highest pass rate" -> GET /items/ + GET /analytics/pass-rates
    if (
        "lowest" in msg_lower
        or "worst" in msg_lower
        or "best" in msg_lower
        or "highest" in msg_lower
    ):
        if "pass" in msg_lower or "rate" in msg_lower or "score" in msg_lower:
            try:
                if debug:
                    print(f"[fallback] Analyzing pass rates", file=sys.stderr)
                labs = api_client.get_labs()
                if not labs:
                    return "No labs available."

                # Extract lab numbers from titles like "Lab 01 - ..."
                main_labs = []
                for lab in labs:
                    if isinstance(lab, dict):
                        title = lab.get("title", "")
                        match = re.match(r"^Lab\s*(\d+)", title, re.IGNORECASE)
                        if match:
                            lab_num = match.group(1).zfill(2)
                            main_labs.append(f"lab-{lab_num}")

                if not main_labs:
                    return "No main labs found."

                # Get pass rates for each lab
                results = []
                for lab_name in main_labs:
                    try:
                        scores = api_client.get_scores(lab_name)
                        if isinstance(scores, dict) and scores:
                            rates = []
                            for v in scores.values():
                                if isinstance(v, dict):
                                    rate = v.get("pass_rate", v.get("rate", 0)) * 100
                                    rates.append(rate)
                            if rates:
                                avg_rate = sum(rates) / len(rates)
                                results.append((lab_name, avg_rate))
                    except Exception as e:
                        if debug:
                            print(
                                f"[fallback] Error for {lab_name}: {e}", file=sys.stderr
                            )

                if not results:
                    return "Unable to fetch pass rates."

                # Find lowest or highest
                if "lowest" in msg_lower or "worst" in msg_lower:
                    target_lab, target_rate = min(results, key=lambda x: x[1])
                    return f"Based on the data, {target_lab} has the lowest average pass rate at approximately {target_rate:.1f}%."
                else:
                    target_lab, target_rate = max(results, key=lambda x: x[1])
                    return f"Based on the data, {target_lab} has the highest average pass rate at approximately {target_rate:.1f}%."
            except Exception as e:
                if debug:
                    print(f"[fallback] Error: {str(e)}", file=sys.stderr)
                return f"Error analyzing pass rates: {str(e)}"

    # "how many students" -> GET /learners/
    if ("how many" in msg_lower or "count" in msg_lower) and (
        "student" in msg_lower or "learner" in msg_lower or "enrolled" in msg_lower
    ):
        try:
            if debug:
                print(f"[fallback] Calling get_learners()", file=sys.stderr)
            url = f"{api_client.base_url}/learners/"
            import httpx

            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.get(url, headers=api_client._get_headers())
                response.raise_for_status()
                data = response.json()
                count = len(data) if isinstance(data, list) else 0
                return f"There are {count} students enrolled."
        except Exception as e:
            if debug:
                print(f"[fallback] Error: {str(e)}", file=sys.stderr)
            return f"Error fetching student count: {str(e)}"

    # "sync the data" -> POST /pipeline/sync
    if "sync" in msg_lower or "refresh" in msg_lower or "update" in msg_lower:
        try:
            if debug:
                print(f"[fallback] Calling trigger_sync()", file=sys.stderr)
            url = f"{api_client.base_url}/pipeline/sync"
            import httpx

            with httpx.Client(timeout=api_client.timeout) as client:
                response = client.post(url, headers=api_client._get_headers(), json={})
                response.raise_for_status()
                data = response.json()
                items_synced = data.get("items_synced", data.get("synced", 0))
                return f"Sync completed successfully. {items_synced} items synced."
        except Exception as e:
            if debug:
                print(f"[fallback] Error: {str(e)}", file=sys.stderr)
            return f"Error syncing data: {str(e)}"

    # "show me scores for lab X" -> GET /analytics/pass-rates?lab=X
    if "score" in msg_lower or "pass rate" in msg_lower or "passrate" in msg_lower:
        match = re.search(r"lab[- ]?(\d+)", msg_lower)
        if match:
            lab_num = match.group(1).zfill(2)
            lab_name = f"lab-{lab_num}"
            try:
                if debug:
                    print(
                        f"[fallback] Calling get_pass_rates({lab_name})",
                        file=sys.stderr,
                    )
                scores = api_client.get_scores(lab_name)
                if not scores:
                    return f"No scores found for {lab_name}."
                lines = [f"Pass rates for {lab_name}:"]
                if isinstance(scores, dict):
                    for task_name, data in scores.items():
                        if isinstance(data, dict):
                            rate = data.get("pass_rate", data.get("rate", 0)) * 100
                            attempts = data.get("attempts", 0)
                            lines.append(
                                f"- {task_name}: {rate:.1f}% ({attempts} attempts)"
                            )
                elif isinstance(scores, list):
                    for item in scores:
                        if isinstance(item, dict):
                            task = item.get("task", item.get("name", "Unknown"))
                            rate = item.get("pass_rate", item.get("rate", 0)) * 100
                            attempts = item.get("attempts", 0)
                            lines.append(f"- {task}: {rate:.1f}% ({attempts} attempts)")
                return "\n".join(lines)
            except Exception as e:
                if debug:
                    print(f"[fallback] Error: {str(e)}", file=sys.stderr)
                return f"Error fetching scores: {str(e)}"

    # Greeting
    if msg_lower in ["hi", "hello", "hey"]:
        return (
            "Hello! I can help you with information about labs, scores, and students."
        )

    # Default fallback
    return f"I didn't understand: '{message}'\n\nTry asking about:\n- Available labs\n- Scores for a specific lab\n- Top students\n- Group performance\n\nOr use /help to see all commands."


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
