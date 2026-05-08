"""Memory Service — 4-layer memory system for ContextAI.

Layers:
  1. Conversation memory: Current chat session (handled by frontend store)
  2. Space memory: Persistent facts learned from chats within a space (space_memory.md)
  3. Global memory: Cross-space user preferences (global_memory.md)
  4. Procedural memory: User profile evolved from rated interactions (user_profile.md)
"""

import os
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger("contextai.memory")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")


# ─── File Paths ───────────────────────────────────────────────

def _global_memory_path() -> str:
    return os.path.join(DATA_DIR, "global_memory.md")


def _space_memory_path(space_id: str) -> str:
    return os.path.join(DATA_DIR, "spaces", space_id, "space_memory.md")


def _user_profile_path(space_id: str) -> str:
    return os.path.join(DATA_DIR, "spaces", space_id, "user_profile.md")


# ─── Read / Write Helpers ────────────────────────────────────

def _read_md(path: str) -> str:
    """Read a markdown memory file, returning empty string if missing."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
    return ""


def _write_md(path: str, content: str) -> None:
    """Write content to a markdown memory file, creating dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _append_md(path: str, entry: str) -> None:
    """Append an entry to a markdown memory file with timestamp."""
    existing = _read_md(path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n- [{timestamp}] {entry}"

    if existing:
        content = existing.rstrip() + new_entry + "\n"
    else:
        content = f"# Memory\n{new_entry}\n"

    _write_md(path, content)


# ─── Public API ───────────────────────────────────────────────

def get_global_memory() -> str:
    """Read the global memory file."""
    return _read_md(_global_memory_path())


def set_global_memory(content: str) -> None:
    """Overwrite the global memory file."""
    _write_md(_global_memory_path(), content)


def append_global_memory(entry: str) -> None:
    """Append a fact to global memory."""
    _append_md(_global_memory_path(), entry)


def get_space_memory(space_id: str) -> str:
    """Read space-specific memory."""
    return _read_md(_space_memory_path(space_id))


def set_space_memory(space_id: str, content: str) -> None:
    """Overwrite space memory."""
    _write_md(_space_memory_path(space_id), content)


def append_space_memory(space_id: str, entry: str) -> None:
    """Append a fact to space memory."""
    _append_md(_space_memory_path(space_id), entry)


def get_user_profile(space_id: str) -> str:
    """Read user profile (procedural memory) for a space."""
    return _read_md(_user_profile_path(space_id))


def set_user_profile(space_id: str, content: str) -> None:
    """Overwrite user profile for a space."""
    _write_md(_user_profile_path(space_id), content)


# ─── Memory Extraction ───────────────────────────────────────

def extract_facts_from_conversation(
    messages: list[dict],
    space_id: str,
) -> list[str]:
    """Extract memorable facts from a conversation using heuristics.

    This is the lightweight, offline extraction approach.
    For LLM-powered extraction, see extract_facts_via_llm().
    """
    facts = []

    for msg in messages:
        if msg.get("role") != "user":
            continue

        content = msg.get("content", "")
        if isinstance(content, list):
            # Multi-modal message — extract text parts
            content = " ".join(
                part.get("text", "") for part in content if part.get("type") == "text"
            )

        if not content or len(content) < 20:
            continue

        # Detect preference statements
        preference_patterns = [
            r"(?:I\s+(?:prefer|like|want|need|use|always|usually|hate|dislike))\s+(.{10,80})",
            r"(?:my\s+(?:name|role|title|job|stack|style)\s+is)\s+(.{5,60})",
            r"(?:I\s+am\s+(?:a|an))\s+(.{5,60})",
            r"(?:call\s+me)\s+(.{2,30})",
            r"(?:I\s+work\s+(?:at|for|with|on))\s+(.{5,60})",
        ]

        for pattern in preference_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                fact = match.strip().rstrip(".,!?")
                if len(fact) > 5:
                    facts.append(fact)

    return facts


def auto_update_memory_from_chat(
    messages: list[dict],
    space_id: str,
) -> int:
    """After a conversation ends, extract and store learned facts.

    Returns the number of new facts extracted.
    """
    facts = extract_facts_from_conversation(messages, space_id)

    if not facts:
        return 0

    existing_memory = get_space_memory(space_id)

    new_facts = 0
    for fact in facts:
        # Avoid duplicates by checking if similar content already exists
        if fact.lower() not in existing_memory.lower():
            append_space_memory(space_id, fact)
            new_facts += 1
            logger.info(f"Stored fact for space {space_id}: {fact[:60]}")

    return new_facts


# ─── Build Memory Context for System Prompt ───────────────────

def build_memory_context(space_id: str) -> str:
    """Build the full memory context block for the system prompt.

    Combines all memory layers into a single markdown section.
    """
    parts = []

    # Layer 1: Global memory
    global_mem = get_global_memory()
    if global_mem.strip():
        parts.append(f"## Global Memory\n{global_mem.strip()}")

    # Layer 2: Space memory (learned from chats)
    space_mem = get_space_memory(space_id)
    if space_mem.strip():
        parts.append(f"## Space Memory (Learned)\n{space_mem.strip()}")

    # Layer 3: User profile (procedural)
    profile = get_user_profile(space_id)
    if profile.strip():
        parts.append(f"## User Profile\n{profile.strip()}")

    return "\n\n".join(parts)
