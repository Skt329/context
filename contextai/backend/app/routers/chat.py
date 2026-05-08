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


class ChatRequest(BaseModel):
    message: str
    space_id: str
    screen_context: str | None = None
    conversation_id: str | None = None
    text_context: str | None = None
    images: list[ChatImage] | None = None  # Multi-modal image attachments


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

    # 4. Build message list (multi-modal if images present)
    user_content = _build_user_content(request.message, request.images)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

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
