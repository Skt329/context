"""Memory Service — 4-layer memory system for ContextAI.

Layers:
  1. Conversation memory: Current chat session (handled by frontend store)
  2. Space memory: Persistent facts learned from chats within a space
  3. Global memory: Cross-space user preferences
  4. Procedural memory: User profile evolved from rated interactions

Storage: All layers persist in SQLite (via app.db).
Intelligence: Uses the user's configured LLM provider for extraction/summarization
              (falls back to regex when no provider is available).
"""

import re
import json
import logging
from datetime import datetime

from app.db import get_db

logger = logging.getLogger("contextai.memory")


# ── Constants ─────────────────────────────────────────────────

MAX_MEMORY_TOKENS = 1500  # Max tokens for memory context injection
SUMMARIZATION_THRESHOLD = 2000  # Trigger summarization above this token count


# ── Database Helpers ─────────────────────────────────────────

def _read_memory(scope: str, space_id: str = "") -> str:
    """Read memory content from SQLite."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT content FROM memory WHERE scope = ? AND space_id = ?",
            (scope, space_id),
        ).fetchone()
        return row["content"] if row else ""
    finally:
        conn.close()


def _write_memory(scope: str, content: str, space_id: str = "") -> None:
    """Write (upsert) memory content to SQLite."""
    now = datetime.utcnow().isoformat()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO memory (scope, space_id, content, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(scope, space_id) DO UPDATE SET content = ?, updated_at = ?""",
            (scope, space_id, content, now, content, now),
        )
        conn.commit()
    finally:
        conn.close()


def _append_memory(scope: str, entry: str, space_id: str = "") -> None:
    """Append a timestamped entry to memory."""
    existing = _read_memory(scope, space_id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n- [{timestamp}] {entry}"

    if existing:
        content = existing.rstrip() + new_entry + "\n"
    else:
        content = f"# Memory\n{new_entry}\n"

    _write_memory(scope, content, space_id)


# ─── Public API ───────────────────────────────────────────────

def get_global_memory() -> str:
    return _read_memory("global")


def set_global_memory(content: str) -> None:
    _write_memory("global", content)


def append_global_memory(entry: str) -> None:
    _append_memory("global", entry)


def get_space_memory(space_id: str) -> str:
    return _read_memory("space", space_id)


def set_space_memory(space_id: str, content: str) -> None:
    _write_memory("space", content, space_id)


def append_space_memory(space_id: str, entry: str) -> None:
    _append_memory("space", entry, space_id)


def get_user_profile(space_id: str) -> str:
    return _read_memory("profile", space_id)


def set_user_profile(space_id: str, content: str) -> None:
    _write_memory("profile", content, space_id)


# ─── LLM-Based Memory Extraction ─────────────────────────────

EXTRACTION_PROMPT = """Analyze this conversation and extract important facts about the user.

Rules:
- Extract ONLY factual information about the user (name, job, preferences, tools, constraints)
- Each fact should be a single, clear sentence
- Do NOT extract opinions about the AI or meta-conversation topics
- Do NOT extract temporary/session-specific information
- Return facts as a JSON array of strings
- If no facts are found, return an empty array: []

Conversation:
{conversation}

Return ONLY a JSON array. Example: ["User's name is John", "User prefers Python over JavaScript"]"""


async def extract_facts_with_llm(messages: list[dict]) -> list[str]:
    """Extract facts from conversation using the user's configured LLM.

    Falls back to regex if no LLM provider is available.
    """
    from app.utils.llm import llm_complete

    # Format conversation for the prompt (last 10 messages)
    convo_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content'][:500]}"
        for msg in messages[-10:]
        if isinstance(msg.get("content"), str)
    )

    raw = await llm_complete(
        EXTRACTION_PROMPT.format(conversation=convo_text),
        max_tokens=500,
        temperature=0.1,
    )

    if raw is None:
        # No LLM available — fall back to regex
        return _extract_facts_regex(messages)

    try:
        # Handle potential markdown wrapping
        text = raw.strip()
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()

        facts = json.loads(text)
        return [f for f in facts if isinstance(f, str) and len(f) > 10]
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"LLM extraction parse failed ({e}), falling back to regex")
        return _extract_facts_regex(messages)


def _extract_facts_regex(messages: list[dict]) -> list[str]:
    """Lightweight regex-based fact extraction (offline fallback)."""
    facts = []

    for msg in messages:
        if msg.get("role") != "user":
            continue

        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if part.get("type") == "text"
            )

        if not content or len(content) < 20:
            continue

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


# ─── Semantic Deduplication ───────────────────────────────────

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded SentenceTransformer model for memory deduplication")
        except ImportError:
            return None
    return _embedding_model


def _is_duplicate_fact(space_id: str, new_fact: str, threshold: float = 0.85) -> bool:
    """Check if a fact is semantically similar to existing memories.

    Uses sentence-transformers for vector similarity.
    Falls back to substring matching if embeddings are unavailable.
    """
    existing = get_space_memory(space_id)
    if not existing:
        return False

    # Extract individual facts from memory
    existing_facts = [
        line.strip().lstrip("- ").strip()
        for line in existing.split("\n")
        if line.strip() and not line.startswith("#") and len(line.strip()) > 10
    ]

    if not existing_facts:
        return False

    # Strip timestamps from existing facts for comparison
    clean_facts = []
    for f in existing_facts:
        # Remove [2024-01-01 12:00] prefix
        cleaned = re.sub(r"^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\]\s*", "", f)
        if cleaned:
            clean_facts.append(cleaned)

    if not clean_facts:
        return False

    model = _get_embedding_model()
    if model is not None:
        import numpy as np

        new_embedding = model.encode([new_fact])
        existing_embeddings = model.encode(clean_facts)

        # Cosine similarity
        similarities = np.dot(existing_embeddings, new_embedding.T).flatten()
        max_similarity = float(similarities.max())

        if max_similarity > threshold:
            most_similar = clean_facts[int(similarities.argmax())]
            logger.info(
                f"Duplicate detected (sim={max_similarity:.2f}): "
                f"'{new_fact[:50]}' ≈ '{most_similar[:50]}'"
            )
            return True
        return False
    else:
        # Fallback: simple substring match
        fact_lower = new_fact.lower()
        return any(fact_lower in f.lower() or f.lower() in fact_lower for f in clean_facts)


# ─── Auto-Update ──────────────────────────────────────────────

async def auto_update_memory_from_chat(
    messages: list[dict],
    space_id: str,
) -> int:
    """After a conversation ends, extract and store learned facts.

    Uses LLM if available, falls back to regex.
    Returns the number of new facts extracted.
    """
    facts = await extract_facts_with_llm(messages)

    if not facts:
        return 0

    new_facts = 0
    for fact in facts:
        if not _is_duplicate_fact(space_id, fact):
            append_space_memory(space_id, fact)
            new_facts += 1
            logger.info(f"Stored fact for space {space_id}: {fact[:60]}")

    return new_facts


# ─── Memory Summarization ────────────────────────────────────

async def _summarize_memory(memory_text: str) -> str | None:
    """Summarize memory to reduce token count while preserving key facts."""
    from app.utils.llm import llm_complete

    result = await llm_complete(
        f"Summarize these user facts into a concise list. Keep ONLY the most important, "
        f"specific facts. Remove redundancy.\n\n{memory_text}",
        max_tokens=500,
        temperature=0.0,
    )
    return result


# ─── Build Memory Context for System Prompt ───────────────────

async def build_memory_context(space_id: str) -> str:
    """Build the full memory context block for the system prompt.

    Combines all memory layers. Auto-summarizes if over token budget.
    """
    from app.utils.tokens import count_tokens

    parts = []

    global_mem = get_global_memory()
    if global_mem.strip():
        parts.append(f"## Global Memory\n{global_mem.strip()}")

    space_mem = get_space_memory(space_id)
    if space_mem.strip():
        parts.append(f"## Space Memory (Learned)\n{space_mem.strip()}")

    profile = get_user_profile(space_id)
    if profile.strip():
        parts.append(f"## User Profile\n{profile.strip()}")

    combined = "\n\n".join(parts)

    token_count = count_tokens(combined)

    if token_count > SUMMARIZATION_THRESHOLD:
        summarized = await _summarize_memory(combined)
        if summarized:
            logger.info(f"Memory summarized: {token_count} → {count_tokens(summarized)} tokens")
            combined = summarized

    # Hard limit: truncate if still too large
    if count_tokens(combined) > MAX_MEMORY_TOKENS:
        while count_tokens(combined) > MAX_MEMORY_TOKENS and "\n" in combined:
            combined = combined[: combined.rfind("\n")]

    return combined


# ─── Sync wrapper for backward compat ─────────────────────────

def build_memory_context_sync(space_id: str) -> str:
    """Synchronous version for use in non-async contexts."""
    parts = []

    global_mem = get_global_memory()
    if global_mem.strip():
        parts.append(f"## Global Memory\n{global_mem.strip()}")

    space_mem = get_space_memory(space_id)
    if space_mem.strip():
        parts.append(f"## Space Memory (Learned)\n{space_mem.strip()}")

    profile = get_user_profile(space_id)
    if profile.strip():
        parts.append(f"## User Profile\n{profile.strip()}")

    return "\n\n".join(parts)
