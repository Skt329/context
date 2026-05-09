"""Tool execution engine for LLM function calling.

Provides built-in tools that the LLM can invoke during conversations:
  - calculate: Evaluate mathematical expressions safely
  - get_current_time: Return current date/time
  - web_search: Placeholder for web search (requires user-provided API key)
  - summarize_memory: Summarize all memory for the active space

Integration: Pass TOOL_DEFINITIONS to LiteLLM's `tools` parameter,
parse tool_calls from the response, execute via execute_tool(), and
feed results back into the conversation.
"""

import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger("contextai.tools")


# ── Tool Handlers ─────────────────────────────────────────────

async def _calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    # Allow only safe math operations
    allowed_names = {
        k: v for k, v in math.__dict__.items()
        if not k.startswith("_")
    }
    allowed_names.update({"abs": abs, "round": round, "min": min, "max": max})

    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating '{expression}': {e}"


async def _get_current_time(**kwargs) -> str:
    """Return the current date and time in ISO format."""
    now = datetime.now(timezone.utc)
    local = datetime.now()
    return (
        f"UTC: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"Local: {local.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Timezone offset: {local.astimezone().strftime('%z')}"
    )


async def _get_memory_summary(space_id: str = "", **kwargs) -> str:
    """Summarize the memory for a given space."""
    from app.db import get_db

    conn = get_db()
    try:
        memories = []
        # Global memory
        row = conn.execute(
            "SELECT content FROM memory WHERE scope = 'global' AND space_id = ''"
        ).fetchone()
        if row and row["content"].strip():
            memories.append(f"**Global Memory:**\n{row['content'][:500]}")

        # Space memory
        if space_id:
            row = conn.execute(
                "SELECT content FROM memory WHERE scope = 'space' AND space_id = ?",
                (space_id,),
            ).fetchone()
            if row and row["content"].strip():
                memories.append(f"**Space Memory:**\n{row['content'][:500]}")

        return "\n\n".join(memories) if memories else "No memory found."
    finally:
        conn.close()


# ── Tool Registry ─────────────────────────────────────────────

BUILTIN_TOOLS = {
    "calculate": {
        "description": "Evaluate a mathematical expression. Supports basic arithmetic, trig functions, log, sqrt, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g. 'sqrt(144) + 2**3'",
                },
            },
            "required": ["expression"],
        },
        "handler": _calculate,
    },
    "get_current_time": {
        "description": "Get the current date and time in UTC and local timezone.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "handler": _get_current_time,
    },
    "get_memory_summary": {
        "description": "Retrieve a summary of the user's stored memory and preferences for the current space.",
        "parameters": {
            "type": "object",
            "properties": {
                "space_id": {
                    "type": "string",
                    "description": "The space ID to get memory for. Optional.",
                },
            },
        },
        "handler": _get_memory_summary,
    },
}


# ── Public API ────────────────────────────────────────────────

def get_tool_definitions() -> list[dict]:
    """Return OpenAI-compatible tool definitions for LiteLLM."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for name, tool in BUILTIN_TOOLS.items()
    ]


async def execute_tool(name: str, params: dict) -> str:
    """Execute a registered tool by name and return the result as a string."""
    tool = BUILTIN_TOOLS.get(name)
    if not tool:
        logger.warning(f"Unknown tool requested: {name}")
        return f"Error: Unknown tool '{name}'"

    try:
        result = await tool["handler"](**params)
        logger.info(f"Tool executed: {name}")
        return str(result)
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}")
        return f"Error executing {name}: {e}"
