"""Chat router — real LLM streaming via LiteLLM with RAG context injection."""

import json
import os
import uuid
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.indexing import search_space

logger = logging.getLogger("contextai.chat")

router = APIRouter()

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")


class ChatImage(BaseModel):
    """Base64-encoded image from chat attachment."""
    data_url: str  # e.g. "data:image/png;base64,iVBOR..."
    name: str | None = None


class HistoryMessage(BaseModel):
    """A single message from conversation history."""
    role: str  # 'user' | 'assistant'
    content: str


class ChatRequest(BaseModel):
    message: str
    space_id: str
    screen_context: str | None = None
    conversation_id: str | None = None
    text_context: str | None = None
    images: list[ChatImage] | None = None  # Multi-modal image attachments
    history: list[HistoryMessage] | None = None  # Prior conversation messages


class RateRequest(BaseModel):
    message_id: str
    rating: int  # 1-5


def _load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"providers": {}}


def _get_active_provider() -> tuple[str, dict] | None:
    """Find the first enabled provider with a valid API key."""
    settings = _load_settings()
    providers = settings.get("providers", {})

    for pid, config in providers.items():
        if config.get("enabled") and (config.get("api_key") or pid == "ollama"):
            return pid, config

    return None


def _build_litellm_model(provider_id: str, config: dict) -> str:
    """Convert provider ID + config into a LiteLLM model string."""
    model = config.get("model", "")

    model_map = {
        "openai": model,  # e.g., "gpt-4o"
        "anthropic": model,  # e.g., "claude-sonnet-4-5-20250514"
        "gemini": f"gemini/{model}",
        "mistral": f"mistral/{model}",
        "deepseek": f"deepseek/{model}",
        "azure": f"azure/{model}",
        "ollama": f"ollama/{model}",
    }
    return model_map.get(provider_id, model)


def _load_user_profile(space_id: str) -> str:
    """Load the user profile for procedural memory context."""
    profile_path = os.path.join(DATA_DIR, "spaces", space_id, "user_profile.md")
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return ""


def _build_system_prompt(
    space_id: str,
    screen_context: str | None,
    rag_context: str | None,
    text_context: str | None = None,
) -> str:
    """Build the system prompt with all context layers."""
    from app.services.memory_service import build_memory_context

    parts = [
        "You are ContextAI, a personal AI assistant with deep contextual awareness.",
        "You help users with tasks using their uploaded documents, screen context, and memory.",
        "Be concise, helpful, and proactive. Format responses with markdown when appropriate.",
    ]

    # Inject 4-layer memory (global + space + user profile)
    memory_ctx = build_memory_context(space_id)
    if memory_ctx.strip():
        parts.append(f"\n{memory_ctx}")

    if text_context and text_context.strip():
        parts.append(f"\n## Space Context (User-Defined)\nThe user has provided the following persistent context for this space:\n{text_context.strip()}")

    if rag_context:
        parts.append(f"\n## Retrieved Context (from user's documents)\n{rag_context}")

    if screen_context:
        parts.append(f"\n## Current Screen Context\nThe user's active window contains:\n{screen_context[:2000]}")

    return "\n\n".join(parts)


# ─── Smart Token-Budget History Trimming ──────────────────────

MAX_HISTORY_TOKENS = 6000  # Budget for conversation history
CHARS_PER_TOKEN = 4  # Conservative estimate (English text averages ~4 chars/token)


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return len(text) // CHARS_PER_TOKEN


def _trim_history_to_budget(
    history: list[HistoryMessage],
    budget_tokens: int = MAX_HISTORY_TOKENS,
) -> list[dict]:
    """Trim conversation history to fit within token budget.

    Strategy:
    - Always keep the first user message (establishes topic)
    - Fill remaining budget from most recent messages backward
    - Never split a user/assistant pair
    - Returns OpenAI-format message dicts
    """
    if not history:
        return []

    messages = [{"role": h.role, "content": h.content} for h in history]

    # If everything fits, return all
    total_tokens = sum(_estimate_tokens(m["content"]) for m in messages)
    if total_tokens <= budget_tokens:
        return messages

    # Always keep first message (topic anchor)
    result_head = [messages[0]] if messages else []
    head_tokens = _estimate_tokens(messages[0]["content"]) if messages else 0
    remaining_budget = budget_tokens - head_tokens

    # Fill from the end (most recent first)
    result_tail = []
    for msg in reversed(messages[1:]):
        msg_tokens = _estimate_tokens(msg["content"])
        if msg_tokens > remaining_budget:
            break
        result_tail.insert(0, msg)
        remaining_budget -= msg_tokens

    # If the head message is also the first tail message, don't duplicate
    if result_tail and result_tail[0] == result_head[0]:
        return result_tail

    return result_head + result_tail


def _build_user_content(message: str, images: list[ChatImage] | None = None):
    """Build user message content — plain string or multi-modal content blocks.

    When images are attached, returns OpenAI-format content array:
    [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:..."}}]

    LiteLLM automatically translates this for all providers (Anthropic, Gemini, Ollama llava, etc.).
    """
    if not images:
        return message

    content = []

    if message.strip():
        content.append({"type": "text", "text": message})

    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": img.data_url},
        })

    return content


async def _stream_litellm(messages: list[dict], provider_id: str, config: dict) -> AsyncGenerator[str, None]:
    """Stream response chunks from LiteLLM."""
    import litellm

    model = _build_litellm_model(provider_id, config)
    api_key = config.get("api_key")
    api_base = config.get("api_base")

    kwargs = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }

    if api_key and provider_id != "ollama":
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                # SSE format
                yield f"data: {json.dumps({'content': delta.content})}\n\n"
    except Exception as e:
        logger.error(f"LiteLLM streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream an AI response with RAG context from the active Space."""

    # 1. Check for an enabled provider
    provider = _get_active_provider()
    if not provider:
        # Return a helpful error as SSE
        async def no_provider():
            yield f"data: {json.dumps({'content': '⚠️ No LLM provider is configured. Go to Settings → enable a provider and add your API key.'})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(no_provider(), media_type="text/event-stream")

    provider_id, config = provider

    # 2. Retrieve RAG context from hybrid search
    rag_context = None
    try:
        rag_results = search_space(request.space_id, request.message, top_k=5)
        if rag_results:
            rag_chunks = []
            for i, result in enumerate(rag_results):
                source = result.get("source_file", "unknown")
                text = result.get("text", "")
                rag_chunks.append(f"[Source: {source}]\n{text}")
            rag_context = "\n\n---\n\n".join(rag_chunks)
            logger.info(f"RAG retrieved {len(rag_results)} chunks for query")
    except Exception as e:
        logger.warning(f"RAG retrieval failed (non-fatal): {e}")

    # 3. Build system prompt
    system_prompt = _build_system_prompt(request.space_id, request.screen_context, rag_context, request.text_context)

    # 4. Build message list with conversation history
    user_content = _build_user_content(request.message, request.images)

    messages = [{"role": "system", "content": system_prompt}]

    # Inject trimmed conversation history
    if request.history:
        trimmed = _trim_history_to_budget(request.history)
        messages.extend(trimmed)
        logger.info(f"Injected {len(trimmed)}/{len(request.history)} history messages (token-budgeted)")

    messages.append({"role": "user", "content": user_content})

    # 5. Stream response
    return StreamingResponse(
        _stream_litellm(messages, provider_id, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Provider": provider_id,
            "X-Model": config.get("model", "unknown"),
        },
    )


@router.post("/rate")
async def rate_message(request: RateRequest):
    """Rate a message to update procedural memory."""
    # TODO: Parse response quality and update user_profile.md
    return {"status": "ok", "message_id": request.message_id, "rating": request.rating}


class TitleRequest(BaseModel):
    message: str


@router.post("/generate-title")
async def generate_title(request: TitleRequest):
    """Generate a short title for a conversation from the first user message."""
    provider = _get_active_provider()
    if not provider:
        # Fallback: truncate the message
        return {"title": request.message[:40].strip() + ("..." if len(request.message) > 40 else "")}

    provider_id, config = provider
    model = _build_litellm_model(provider_id, config)

    try:
        import litellm
        api_key = config.get("api_key")
        api_base = config.get("api_base")

        kwargs = {"model": model, "api_key": api_key, "max_tokens": 20, "temperature": 0.3}
        if api_base:
            kwargs["api_base"] = api_base

        response = await litellm.acompletion(
            **kwargs,
            messages=[
                {
                    "role": "system",
                    "content": "Generate a short, descriptive title (3-6 words max) for a conversation that starts with the user message below. Reply with ONLY the title, no quotes, no explanation.",
                },
                {"role": "user", "content": request.message[:500]},
            ],
        )
        title = response.choices[0].message.content.strip().strip('"').strip("'")
        return {"title": title[:60]}
    except Exception as e:
        logger.warning(f"Title generation failed: {e}")
        return {"title": request.message[:40].strip() + ("..." if len(request.message) > 40 else "")}
