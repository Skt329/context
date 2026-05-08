"""Settings router — provider configuration, API key management, and Ollama model detection."""

import json
import os
import logging
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("contextai.settings")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
OLLAMA_BASE = "http://localhost:11434"

router = APIRouter()


class ProviderUpdate(BaseModel):
    enabled: bool | None = None
    api_key: str | None = None
    model: str | None = None
    api_base: str | None = None


class BulkProviderSync(BaseModel):
    """Sync all provider configs from frontend."""
    providers: dict[str, dict]


def load_settings() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"providers": {}, "preferences": {}}


def save_settings(settings: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# ── Ollama Detection ──────────────────────────────────────────────


@router.get("/ollama/models")
async def list_ollama_models():
    """Detect locally installed Ollama models by querying the Ollama API."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    models.append({
                        "name": m["name"],
                        "size": m.get("size", 0),
                        "family": m.get("details", {}).get("family", "unknown"),
                        "parameter_size": m.get("details", {}).get("parameter_size", ""),
                        "quantization": m.get("details", {}).get("quantization_level", ""),
                    })
                return {"available": True, "models": models}
            return {"available": False, "models": [], "error": f"Ollama returned {resp.status_code}"}
    except httpx.ConnectError:
        return {"available": False, "models": [], "error": "Ollama not running — start it with 'ollama serve'"}
    except Exception as e:
        return {"available": False, "models": [], "error": str(e)}


@router.get("/ollama/status")
async def ollama_status():
    """Quick check if Ollama is running."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            count = len(resp.json().get("models", []))
            return {"running": True, "model_count": count}
    except Exception:
        return {"running": False, "model_count": 0}


# ── Provider Config ───────────────────────────────────────────────


@router.get("/providers")
async def get_providers():
    """Get all provider configurations."""
    settings = load_settings()
    providers = settings.get("providers", {})
    masked = {}
    for pid, config in providers.items():
        masked[pid] = {**config}
        if config.get("api_key"):
            key = config["api_key"]
            masked[pid]["api_key_preview"] = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
            masked[pid]["has_key"] = True
        else:
            masked[pid]["has_key"] = False
    return masked


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, update: ProviderUpdate):
    """Update a single provider's configuration."""
    settings = load_settings()
    providers = settings.setdefault("providers", {})
    current = providers.get(provider_id, {})

    if update.enabled is not None:
        current["enabled"] = update.enabled
    if update.api_key is not None:
        current["api_key"] = update.api_key
    if update.model is not None:
        current["model"] = update.model
    if update.api_base is not None:
        current["api_base"] = update.api_base

    providers[provider_id] = current
    settings["providers"] = providers
    save_settings(settings)
    logger.info(f"Updated provider '{provider_id}': enabled={current.get('enabled')}, model={current.get('model')}")

    return {"status": "updated", "provider": provider_id}


@router.post("/providers/sync")
async def sync_providers(sync: BulkProviderSync):
    """Bulk sync all provider configs from the frontend."""
    settings = load_settings()
    existing = settings.get("providers", {})

    for pid, frontend_config in sync.providers.items():
        current = existing.get(pid, {})
        if frontend_config.get("enabled") is not None:
            current["enabled"] = frontend_config["enabled"]
        if frontend_config.get("apiKey"):
            current["api_key"] = frontend_config["apiKey"]
        if frontend_config.get("model"):
            current["model"] = frontend_config["model"]
        existing[pid] = current

    settings["providers"] = existing
    save_settings(settings)
    logger.info(f"Synced {len(sync.providers)} provider configs")

    return {"status": "synced", "count": len(sync.providers)}


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """Test a provider connection with a minimal API call."""
    settings = load_settings()
    provider = settings.get("providers", {}).get(provider_id, {})

    if provider_id == "ollama":
        # For Ollama, test by checking if the model exists
        model = provider.get("model", "")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OLLAMA_BASE}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    if model in models:
                        return {"status": "ok", "response": f"Model '{model}' is available"}
                    return {"status": "error", "message": f"Model '{model}' not found. Available: {', '.join(models)}"}
            return {"status": "error", "message": "Ollama not responding"}
        except Exception as e:
            return {"status": "error", "message": f"Ollama connection failed: {e}"}

    if not provider.get("api_key"):
        return {"status": "error", "message": "No API key configured"}

    try:
        import litellm

        model = provider.get("model", "")
        model_map = {
            "openai": model,
            "anthropic": model,
            "gemini": f"gemini/{model}",
            "mistral": f"mistral/{model}",
            "deepseek": f"deepseek/{model}",
            "azure": f"azure/{model}",
        }

        response = await litellm.acompletion(
            model=model_map.get(provider_id, model),
            messages=[{"role": "user", "content": "Say 'connected' in one word."}],
            api_key=provider.get("api_key"),
            api_base=provider.get("api_base"),
            max_tokens=5,
        )
        return {"status": "ok", "response": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}
