"""Settings router — provider configuration and API key management."""

import json
import os
from fastapi import APIRouter
from pydantic import BaseModel

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

router = APIRouter()


class ProviderUpdate(BaseModel):
    enabled: bool | None = None
    api_key: str | None = None
    model: str | None = None
    api_base: str | None = None


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"providers": {}}


def save_settings(settings: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


@router.get("/providers")
async def get_providers():
    """Get all provider configurations."""
    return load_settings().get("providers", {})


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, update: ProviderUpdate):
    """Update a provider's configuration."""
    settings = load_settings()
    providers = settings.setdefault("providers", {})
    current = providers.get(provider_id, {})

    if update.enabled is not None:
        current["enabled"] = update.enabled
    if update.api_key is not None:
        current["api_key"] = update.api_key  # TODO: Encrypt with DPAPI
    if update.model is not None:
        current["model"] = update.model
    if update.api_base is not None:
        current["api_base"] = update.api_base

    providers[provider_id] = current
    settings["providers"] = providers
    save_settings(settings)

    return {"status": "updated", "provider": provider_id}


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """Test a provider connection with a minimal API call."""
    settings = load_settings()
    provider = settings.get("providers", {}).get(provider_id, {})

    if not provider.get("api_key") and provider_id != "ollama":
        return {"status": "error", "message": "No API key configured"}

    try:
        import litellm

        # Map provider IDs to LiteLLM model strings
        model_map = {
            "openai": provider.get("model", "gpt-4o-mini"),
            "anthropic": provider.get("model", "claude-sonnet-4-5-20250514"),
            "gemini": f"gemini/{provider.get('model', 'gemini-2.0-flash')}",
            "mistral": f"mistral/{provider.get('model', 'mistral-large-latest')}",
            "deepseek": f"deepseek/{provider.get('model', 'deepseek-chat')}",
            "azure": f"azure/{provider.get('model', 'gpt-4o')}",
            "ollama": f"ollama/{provider.get('model', 'llama3')}",
        }

        response = await litellm.acompletion(
            model=model_map.get(provider_id, provider.get("model", "")),
            messages=[{"role": "user", "content": "Say 'connected' in one word."}],
            api_key=provider.get("api_key"),
            api_base=provider.get("api_base"),
            max_tokens=5,
        )
        return {"status": "ok", "response": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}
