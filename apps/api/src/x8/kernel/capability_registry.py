from collections.abc import Callable
from dataclasses import dataclass, field


HealthCheck = Callable[[], str]


@dataclass
class CapabilityRegistration:
    capability_id: str
    display_name: str
    category: str
    status: str = "not_configured"
    risk_level: str = "read_only"
    manager_name: str = ""
    adapter_name: str = ""
    requires_approval: bool = False
    requires_credentials: bool = False
    enabled: bool = True
    health_check: HealthCheck | None = None
    supported_card_types: list[str] = field(default_factory=list)
    supported_events: list[str] = field(default_factory=list)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityRegistration] = {}

    def register(self, capability: CapabilityRegistration) -> None:
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> CapabilityRegistration | None:
        return self._capabilities.get(capability_id)

    def all(self) -> list[CapabilityRegistration]:
        return list(self._capabilities.values())

    def health(self, capability_id: str) -> str:
        capability = self.get(capability_id)
        if capability is None:
            return "not_configured"
        if not capability.enabled:
            return "disabled"
        if capability.health_check:
            return capability.health_check()
        return capability.status


def default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(CapabilityRegistration("chat.model", "Model chat", "model", status="ready", supported_card_types=["text", "error", "receipt"]))
    registry.register(CapabilityRegistration("search.searxng", "SearXNG research", "research", status="degraded", manager_name="WebSearchManager", supported_card_types=["search_results"]))
    registry.register(CapabilityRegistration("image.comfyui", "ComfyUI image generation", "image", status="degraded", manager_name="ImageGenerationManager", supported_card_types=["image", "job_status"]))
    registry.register(CapabilityRegistration("repo.write", "Repository write", "repo", status="ready", risk_level="mutating", requires_approval=True, manager_name="SafeRepoWriterManager", supported_card_types=["diff", "approval"]))
    return registry
