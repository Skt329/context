"""Utility: resolve the user's active LLM for internal tasks (memory, chunking, HyDE).

Key design: NEVER assume Ollama. Use whatever provider the user has configured
and enabled. Falls back gracefully to non-LLM methods when no provider is available.
"""

import logging
from app.routers.settings import load_providers

logger = logging.getLogger("contextai.llm")


def get_active_llm() -> tuple[str, dict] | None:
    """Find the user's active (enabled + keyed) LLM provider.

    Returns (litellm_model_string, config_dict) or None.
    Priority: first enabled provider with a valid key or Ollama.
    """
    providers = load_providers()

    for pid, config in providers.items():
        if not config.get("enabled"):
            continue
        if config.get("api_key") or pid == "ollama":
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
            litellm_model = model_map.get(pid, model)
            return litellm_model, config

    return None


async def llm_complete(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.1,
    system: str | None = None,
) -> str | None:
    """Run a single LLM completion using the user's active provider.

    Returns the response text, or None if no provider is available.
    This is a thin convenience wrapper for internal tasks (memory extraction,
    contextual chunking, summarization, HyDE).
    """
    active = get_active_llm()
    if not active:
        logger.debug("No active LLM provider — skipping LLM-powered task")
        return None

    litellm_model, config = active

    import litellm

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": litellm_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    api_key = config.get("api_key")
    api_base = config.get("api_base")
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"LLM completion failed ({litellm_model}): {e}")
        return None
