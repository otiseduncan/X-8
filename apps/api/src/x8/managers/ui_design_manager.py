from x8.managers.knowledge_seed_manager import KnowledgeSeedManager


class UiDesignManager:
    name = "ui_design"
    version = "0.1.0"

    def __init__(self, knowledge: KnowledgeSeedManager) -> None:
        self.knowledge = knowledge

    def checklist(self) -> str:
        return self.knowledge.read_topic("design", "ui_design_principles")
