import os

from x8.kernel.contracts import BrainContextBundle, KernelDecision


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _provider() -> str:
    return _first_env("X8_CHAT_PROVIDER", "CHAT_PROVIDER", default="openwebui").lower().replace("-", "").replace("_", "")


def _model() -> str:
    return _first_env("OPENWEBUI_MODEL", "X8_OPEN_WEBUI_MODEL", "X8_OPENWEBUI_MODEL", "X8_DEFAULT_CHAT_MODEL", default="qwen3:14b")


def _runtime_context_lines() -> list[str]:
    provider = _provider()
    model = _model()
    if provider in {"openwebui", "owui", "brainbridge"}:
        return [
            "Verified runtime: X8 is routing this model turn through OpenWebUI as the active model-facing brain bridge.",
            f"Verified model path: X8 chat -> OpenWebUI API /api/chat/completions -> {model} -> Ollama backend.",
            "If the operator asks what model path is being used, state the verified OpenWebUI bridge path directly.",
            "Do not claim the OpenWebUI bridge is unconfirmed unless the current API receipt or diagnostics says it failed.",
        ]
    return [
        f"Verified runtime: X8 is routing this model turn through the direct local model adapter using {model}.",
        "If the operator asks what model path is being used, state the configured direct local model path directly.",
    ]


class KernelPromptBuilder:
    def build(self, user_message: str, context: BrainContextBundle, decision: KernelDecision) -> str:
        sections = [
            "System: You are Xoduz, pronounced Exodus, the XV8 local assistant. Be direct, practical, and honest about unavailable tools and proof.",
            "Operator: Otis Duncan.",
            "Runtime context:\n" + "\n".join(f"- {line}" for line in _runtime_context_lines()),
            f"Lane: {decision.lane}",
            f"User message:\n{user_message}",
        ]
        sections.extend(self._section("Session context", context.session_context))
        sections.extend(self._section("Relevant knowledge", context.knowledge))
        sections.extend(self._section("Memory", context.memory))
        sections.extend(self._section("Verified status", context.verified_status))
        sections.extend(self._section("Research", context.research))
        sections.extend(self._section("Preferences", context.preferences))
        sections.extend(self._section("Attachments", context.attachments))
        sections.append("Response instruction: answer directly and do not expose hidden reasoning.")
        return "\n\n".join(sections)

    def _section(self, title: str, values: list[str]) -> list[str]:
        if not values:
            return []
        return [f"{title}:\n" + "\n".join(f"- {value}" for value in values)]
