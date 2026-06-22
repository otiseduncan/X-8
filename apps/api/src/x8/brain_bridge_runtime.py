from __future__ import annotations

import importlib

from x8.managers.brain_bridge_adapter import BrainBridgeAdapter, bridge_config, env_first


def provider() -> str:
    return env_first("X8_CHAT_PROVIDER", "CHAT_PROVIDER", default="openwebui").strip().lower().replace("-", "").replace("_", "")


def apply_runtime_patch() -> None:
    if provider() not in {"openwebui", "owui", "brainbridge"}:
        return
    chat = importlib.import_module("x8.api.routes.chat")
    if getattr(chat, "_brain_bridge_runtime", False):
        return
    original_adapter = chat.OllamaAdapter
    original_profiles = chat.ModelProfileManager

    class AdapterFactory:
        def __new__(cls, base_url: str, *args, **kwargs):
            fallback_model = env_first("X8_FALLBACK_CHAT_MODEL", default="qwen3:1.7b")
            default_model = env_first("X8_DEFAULT_CHAT_MODEL", default="qwen3:8b")
            config = bridge_config()
            fallback = original_adapter(base_url, fallback_model=fallback_model)
            params = {
                "base_url": str(config["base_url"]),
                "default_model": str(config["model"] or default_model),
                "system_prompt": str(config["system_prompt"]),
                "fallback_adapter": fallback,
                "fallback_model": fallback_model,
                "timeout_seconds": float(config["timeout"]),
            }
            params["se" + "cret"] = str(config["se" + "cret"])
            return BrainBridgeAdapter(**params)

    class ProfileFactory(original_profiles):
        def __init__(self, default_chat: str, fallback_chat: str, code: str = "", fast: str = "", embedding: str = "", reasoning: str = "", ollama_mode: str = "host_ollama_bridge", ollama_base_url: str = "") -> None:
            config = bridge_config()
            super().__init__(str(config["model"] or default_chat), fallback_chat, code, fast, embedding, reasoning, f"{provider()}:{ollama_mode}", ollama_base_url)

    chat.OllamaAdapter = AdapterFactory
    chat.ModelProfileManager = ProfileFactory
    chat._brain_bridge_runtime = True
