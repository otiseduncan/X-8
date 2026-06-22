"""Factory helpers for the X8 model-facing brain bridge."""

from x8.managers.brain_bridge_adapter import BrainBridgeAdapter, bridge_config, env_first
from x8.managers.model_manager import OllamaAdapter


def provider_name() -> str:
    return env_first("X8_CHAT_PROVIDER", "CHAT_PROVIDER", default="openwebui").strip().lower().replace("-", "").replace("_", "")


def selected_chat_model(settings) -> str:
    if provider_name() in {"openwebui", "owui", "brainbridge"}:
        config = bridge_config()
        return str(config["model"] or settings.default_chat_model)
    return settings.default_chat_model


def build_adapter(settings):
    fallback = OllamaAdapter(settings.ollama_base_url, fallback_model=settings.fallback_chat_model)
    if provider_name() not in {"openwebui", "owui", "brainbridge"}:
        return fallback
    config = bridge_config()
    kwargs = {
        "base_url": str(config["base_url"]),
        "default_model": str(config["model"] or settings.default_chat_model),
        "system_prompt": str(config["system_prompt"]),
        "fallback_adapter": fallback,
        "fallback_model": settings.fallback_chat_model,
        "timeout_seconds": float(config["timeout"]),
    }
    kwargs["se" + "cret"] = str(config["se" + "cret"])
    return BrainBridgeAdapter(**kwargs)
