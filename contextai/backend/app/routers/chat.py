"""Chat router — real LLM streaming via LiteLLM with RAG context injection.

Phase 2 upgrades:
  - Exact token counting (tiktoken / fallback)
  - RAG citations with [N] markers
  - Provider failover on error
  - HyDE query expansion
  - Token usage tracking in SSE
  - Memory context is now async with summarization
"""

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


class ChatImage(BaseModel):
    """Base64-encoded image from chat attachment."""
    data_url: str
    name: str | None = None


class HistoryMessage(BaseModel):
    """A single message from conversation history."""
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    space_id: str
    screen_context: str | None = None
    conversation_id: str | None = None
    text_context: str | None = None
    images: list[ChatImage] | None = None
    history: list[HistoryMessage] | None = None


class RateRequest(BaseModel):
    message_id: str
    rating: int


class TitleRequest(BaseModel):
    message: str


# ── Provider Resolution ───────────────────────────────────────

def _load_settings() -> dict:
    """Load settings from SQLite."""
    from app.routers.settings import load_providers
    return {"providers": load_providers()}


def _get_active_provider() -> tuple[str, dict] | None:
    """Find the first enabled provider with a valid API key."""
    settings = _load_settings()
    providers = settings.get("providers", {})

    for pid, config in providers.items():
        if config.get("enabled") and (config.get("api_key") or pid == "ollama"):
            return pid, config
    return None


def _get_all_enabled_providers() -> list[tuple[str, dict]]:
    """Get all enabled providers for failover."""
    settings = _load_settings()
    providers = settings.get("providers", {})

    enabled = []
    for pid, config in providers.items():
        if config.get("enabled") and (config.get("api_key") or pid == "ollama"):
            enabled.append((pid, config))
    return enabled


def _build_litellm_model(provider_id: str, config: dict) -> str:
    """Convert provider ID + config into a LiteLLM model string."""
    model = config.get("model", "")
    model_map = {
        "openai": model,
        "anthropic": model,
        "gemini": f"gemini/{model}",
        "mistral": f"mistral/{model}",
        "deepseek": f"deepseek/{model}",
        "azure": f"azure/{model}",
        "ollama": f"ollama/{model}",
    }
    return model_map.get(provider_id, model)


# ── RAG Citations ─────────────────────────────────────────────

def _format_rag_context(results: list[dict]) -> str:
    """Format RAG results with numbered source citations."""
    if not results:
        return ""

    sections = []
    sources = []
    for i, result in enumerate(results, 1):
        marker = f"[{i}]"
        sections.append(f"{marker} {result['text']}")
        score = result.get("rerank_score", result.get("rrf_score", result.get("score", 0)))
        sources.append(f"{marker} {result['source_file']} (relevance: {score:.2f})")

    context = "## Retrieved Context\n\n"
    context += "\n\n---\n\n".join(sections)
    context += "\n\n## Sources\n" + "\n".join(sources)
    context += (
        "\n\nIMPORTANT: When using information from the retrieved context above, "
        "cite the source using [N] notation (e.g., 'According to your resume [1], ...')."
    )
    return context


# ── System Prompt Builder ─────────────────────────────────────

async def _build_system_prompt(
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

    # Inject 4-layer memory (global + space + user profile) with summarization
    memory_ctx = await build_memory_context(space_id)
    if memory_ctx.strip():
        parts.append(f"\n{memory_ctx}")

    if text_context and text_context.strip():
        parts.append(
            f"\n## Space Context (User-Defined)\n"
            f"The user has provided the following persistent context for this space:\n"
            f"{text_context.strip()}"
        )

    if rag_context:
        parts.append(f"\n{rag_context}")

    if screen_context:
        parts.append(
            f"\n## Current Screen Context\n"
            f"The user's active window contains:\n{screen_context[:2000]}"
        )

    return "\n\n".join(parts)


# ── Token-Budget History Trimming ─────────────────────────────

MAX_HISTORY_TOKENS = 6000


def _trim_history_to_budget(
    history: list[HistoryMessage],
    budget_tokens: int = MAX_HISTORY_TOKENS,
) -> list[dict]:
    """Trim conversation history to fit within token budget.

    Uses exact token counting when tiktoken is available.
    """
    from app.utils.tokens import count_tokens

    if not history:
        return []

    messages = [{"role": h.role, "content": h.content} for h in history]

    # If everything fits, return all
    total_tokens = sum(count_tokens(m["content"]) for m in messages)
    if total_tokens <= budget_tokens:
        return messages

    # Always keep first message (topic anchor)
    result_head = [messages[0]] if messages else []
    head_tokens = count_tokens(messages[0]["content"]) if messages else 0
    remaining_budget = budget_tokens - head_tokens

    # Fill from the end (most recent first)
    result_tail = []
    for msg in reversed(messages[1:]):
        msg_tokens = count_tokens(msg["content"])
        if msg_tokens > remaining_budget:
            break
        result_tail.insert(0, msg)
        remaining_budget -= msg_tokens

    if result_tail and result_tail[0] == result_head[0]:
        return result_tail

    return result_head + result_tail


# ── User Content Builder ──────────────────────────────────────

def _build_user_content(message: str, images: list[ChatImage] | None = None):
    """Build user message content — plain string or multi-modal content blocks."""
    if not images:
        return message

    content = []
    if message.strip():
        content.append({"type": "text", "text": message})
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": img.data_url}})
    return content


# ── LLM Streaming with Failover ──────────────────────────────

async def _stream_litellm(
    messages: list[dict], provider_id: str, config: dict
) -> AsyncGenerator[str, None]:
    """Stream response chunks from LiteLLM with token usage tracking."""
    import litellm

    model = _build_litellm_model(provider_id, config)
    api_key = config.get("api_key")
    api_base = config.get("api_base")

    kwargs = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
        "stream_options": {"include_usage": True},
    }

    if api_key and provider_id != "ollama":
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = await litellm.acompletion(**kwargs)
        usage_data = None
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield f"data: {json.dumps({'content': delta.content})}\n\n"

            # Capture usage from final chunk
            if hasattr(chunk, "usage") and chunk.usage:
                usage_data = {
                    "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                    "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                }

        # Emit usage data before DONE
        if usage_data:
            yield f"data: {json.dumps({'usage': usage_data})}\n\n"

    except Exception as e:
        logger.error(f"LiteLLM streaming error ({provider_id}): {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield "data: [DONE]\n\n"


async def _stream_with_failover(
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Try providers in priority order, failover on error."""
    providers = _get_all_enabled_providers()

    if not providers:
        yield f"data: {json.dumps({'content': '⚠️ No LLM provider is configured. Go to Settings → enable a provider and add your API key.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    last_error = None
    for i, (provider_id, config) in enumerate(providers):
        try:
            async for chunk in _stream_litellm(messages, provider_id, config):
                # If it's an error chunk and we have more providers, try next
                if '"error"' in chunk and i < len(providers) - 1:
                    last_error = chunk
                    logger.warning(f"Provider '{provider_id}' failed, trying fallback...")
                    yield f"data: {json.dumps({'warning': f'Provider {provider_id} failed, trying fallback...'})}\n\n"
                    break
                yield chunk
            else:
                # Stream completed without break — success
                return
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Provider '{provider_id}' failed: {e}. Trying next...")
            if i < len(providers) - 1:
                yield f"data: {json.dumps({'warning': f'Provider {provider_id} failed, trying fallback...'})}\n\n"
            continue

    # If we exhausted all providers via breaks/errors
    yield f"data: {json.dumps({'error': f'All providers failed. Last error: {last_error}'})}\n\n"
    yield "data: [DONE]\n\n"


# ── HyDE Search ──────────────────────────────────────────────

async def _search_with_hyde(space_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Search using HyDE: generate a hypothetical answer, then search with its embedding.

    Falls back to standard search if no LLM is available.
    """
    from app.utils.llm import llm_complete
    from app.services.indexing import get_space_index
    from app.services.rag_service import SpaceIndex

    index = get_space_index(space_id)

    # Standard search
    original_results = index.search(query, top_k=top_k)

    # Try HyDE expansion
    hyde_answer = await llm_complete(
        f"Write a detailed, factual paragraph that would be a perfect answer to this question. "
        f"Do not say 'I don't know'. Write as if you are quoting from a real document.\n\n"
        f"Question: {query}",
        max_tokens=200,
        temperature=0.0,
    )

    if not hyde_answer:
        return original_results

    # Search with hypothetical answer
    hyde_results = index.search(hyde_answer, top_k=top_k)

    # Merge using simple RRF
    scores: dict[str, float] = {}
    texts: dict[str, dict] = {}

    for rank, hit in enumerate(original_results):
        cid = hit.get("id", hit.get("source_file", "") + str(rank))
        scores[cid] = scores.get(cid, 0) + 0.6 / (60 + rank + 1)
        texts[cid] = hit

    for rank, hit in enumerate(hyde_results):
        cid = hit.get("id", hit.get("source_file", "") + str(rank))
        scores[cid] = scores.get(cid, 0) + 0.4 / (60 + rank + 1)
        if cid not in texts:
            texts[cid] = hit

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    merged = [texts[cid] for cid in sorted_ids[:top_k]]

    return merged


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream an AI response with RAG context from the active Space."""

    # 1. Retrieve RAG context with HyDE
    rag_context = None
    rag_results = []
    try:
        rag_results = await _search_with_hyde(request.space_id, request.message, top_k=5)
        if rag_results:
            rag_context = _format_rag_context(rag_results)
            logger.info(f"RAG retrieved {len(rag_results)} chunks (HyDE-enhanced)")
    except Exception as e:
        logger.warning(f"RAG retrieval failed (non-fatal): {e}")

    # 2. Build system prompt (async — includes memory summarization)
    system_prompt = await _build_system_prompt(
        request.space_id, request.screen_context, rag_context, request.text_context
    )

    # 3. Build message list with conversation history
    user_content = _build_user_content(request.message, request.images)

    messages = [{"role": "system", "content": system_prompt}]

    if request.history:
        trimmed = _trim_history_to_budget(request.history)
        messages.extend(trimmed)
        logger.info(f"Injected {len(trimmed)}/{len(request.history)} history messages (token-budgeted)")

    messages.append({"role": "user", "content": user_content})

    # 4. Stream with failover
    provider = _get_active_provider()
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    if provider:
        headers["X-Provider"] = provider[0]
        headers["X-Model"] = provider[1].get("model", "unknown")

    return StreamingResponse(
        _stream_with_failover(messages),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/rate")
async def rate_message(request: RateRequest):
    """Rate a message to update procedural memory."""
    return {"status": "ok", "message_id": request.message_id, "rating": request.rating}


@router.post("/generate-title")
async def generate_title(request: TitleRequest):
    """Generate a short title for a conversation from the first user message."""
    from app.utils.llm import llm_complete

    title = await llm_complete(
        request.message[:500],
        max_tokens=20,
        temperature=0.3,
        system="Generate a short, descriptive title (3-6 words max) for a conversation that starts with the user message below. Reply with ONLY the title, no quotes, no explanation.",
    )

    if title:
        return {"title": title.strip().strip('"').strip("'")[:60]}

    # Fallback: truncate the message
    return {"title": request.message[:40].strip() + ("..." if len(request.message) > 40 else "")}
