from pathlib import Path

from x8.contracts.capability import Capability, CapabilityStatus


class KnowledgeSeedManager:
    name = "knowledge_seed"
    version = "0.1.0"

    def __init__(self, knowledge_root: str = "/app/knowledge") -> None:
        self.knowledge_root = Path(knowledge_root)

    def capabilities(self) -> list[Capability]:
        return [Capability(name="seed_knowledge", status=CapabilityStatus.IMPLEMENTED, summary="Reads structured seed knowledge.")]

    def read_topic(self, area: str, name: str) -> str:
        path = self.knowledge_root / area / f"{name}.md"
        if not path.exists():
            return "Seed topic unavailable."
        return path.read_text(encoding="utf-8")

    def available_areas(self) -> list[str]:
        return sorted(path.name for path in self.knowledge_root.iterdir() if path.is_dir())
