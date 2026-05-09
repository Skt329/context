"""Exact token counting using tiktoken.

Replaces the approximate chars/4 estimation with exact token counts.
Falls back to character estimation when tiktoken is unavailable.
"""

import functools
import logging

logger = logging.getLogger("contextai.tokens")

_tiktoken_available = False
try:
    import tiktoken
    _tiktoken_available = True
except ImportError:
    logger.info("tiktoken not installed — using character-based estimation")


@functools.lru_cache(maxsize=10)
def _get_encoder(model: str):
    """Get the tokenizer for a specific model (cached)."""
    if not _tiktoken_available:
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base (GPT-4 / Claude compatible)
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count exact tokens for a given text and model.

    Falls back to len(text)//4 if tiktoken is unavailable.
    """
    if not text:
        return 0
    encoder = _get_encoder(model)
    if encoder:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    # Fallback
    return len(text) // 4


def count_messages_tokens(messages: list[dict], model: str = "gpt-4") -> int:
    """Count tokens for an array of chat messages (including message overhead)."""
    encoder = _get_encoder(model)
    tokens = 0
    for msg in messages:
        tokens += 4  # per-message overhead (<role>, <content>, etc.)
        content = msg.get("content", "")
        role = msg.get("role", "")
        if encoder:
            try:
                tokens += len(encoder.encode(content if isinstance(content, str) else str(content)))
                tokens += len(encoder.encode(role))
                continue
            except Exception:
                pass
        # Fallback
        tokens += len(content) // 4 if isinstance(content, str) else 0
        tokens += len(role)
    tokens += 2  # priming tokens
    return tokens


def trim_messages_to_budget(
    messages: list[dict],
    budget: int,
    model: str = "gpt-4",
    preserve_system: bool = True,
) -> list[dict]:
    """Trim messages from the beginning to fit within a token budget.

    Always preserves system messages and the most recent messages.
    """
    if not messages:
        return messages

    total = count_messages_tokens(messages, model)
    if total <= budget:
        return messages

    # Separate system messages
    system_msgs = [m for m in messages if m["role"] == "system"] if preserve_system else []
    chat_msgs = [m for m in messages if m["role"] != "system"]

    system_tokens = count_messages_tokens(system_msgs, model) if system_msgs else 0
    remaining_budget = budget - system_tokens

    # Keep removing oldest messages until we fit
    while chat_msgs and count_messages_tokens(chat_msgs, model) > remaining_budget:
        chat_msgs.pop(0)

    return system_msgs + chat_msgs
