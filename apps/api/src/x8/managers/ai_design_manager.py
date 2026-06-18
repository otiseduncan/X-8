from x8.managers.knowledge_seed_manager import KnowledgeSeedManager


class AiDesignManager:
    name = "ai_design"
    version = "0.1.0"

    def __init__(self, knowledge: KnowledgeSeedManager) -> None:
        self.knowledge = knowledge

    def checklist(self) -> str:
        return self.knowledge.read_topic("ai", "ai_system_principles")
