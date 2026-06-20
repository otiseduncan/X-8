from pathlib import Path

from x8.kernel.contracts import BrainContextBundle
from x8.managers.memory_manager import MemoryManager


class BrainContextAssembler:
    def __init__(self, knowledge_root: str, limits: dict[str, int], memory_manager: MemoryManager | None = None) -> None:
        self.knowledge_root = Path(knowledge_root)
        self.limits = limits
        self.memory_manager = memory_manager

    def assemble(self, session_messages: list[dict[str, object]], attachments: list[dict[str, object]], current_user_message: str = "") -> BrainContextBundle:
        bundle = BrainContextBundle()
        bundle.session_context = self._session_context(session_messages)
        bundle.attachments, attachment_limits = self._attachment_context(attachments)
        bundle.memory, memory_limits = self._memory_context(session_messages, current_user_message)
        bundle.knowledge, knowledge_limits = self._knowledge_context()
        bundle.preferences = ["Use concise, honest, action-oriented engineering responses."]
        bundle.verified_status = ["Runtime status is only included when produced by live endpoints in this turn."]
        bundle.limitations.extend(attachment_limits + memory_limits + knowledge_limits)
        bundle.limitations.extend(["Research source unavailable; no web research injected."])
        return bundle

    def _session_context(self, messages: list[dict[str, object]]) -> list[str]:
        max_messages = self.limits["context_max_messages"]
        selected = messages[-max_messages:]
        return [f"{item.get('role', 'unknown')}: {str(item.get('content', ''))[:500]}" for item in selected if item.get("content")]

    def _attachment_context(self, attachments: list[dict[str, object]]) -> tuple[list[str], list[str]]:
        max_chars = self.limits["context_max_attachment_chars"]
        values: list[str] = []
        limitations: list[str] = []
        for attachment in attachments:
            text = str(attachment.get("extracted_text", ""))
            name = str(attachment.get("filename", "attachment"))
            if text:
                truncated = text[:max_chars]
                values.append(f"{name}: {truncated}")
                if len(text) > max_chars:
                    limitations.append(f"{name} attachment text truncated to {max_chars} chars.")
            else:
                limitations.append(f"{name} has no extracted text available.")
        return values, limitations

    def _knowledge_context(self) -> tuple[list[str], list[str]]:
        if not self.knowledge_root.exists():
            return [], [f"Knowledge root unavailable: {self.knowledge_root}"]
        max_items = self.limits["context_max_knowledge_items"]
        values: list[str] = []
        for path in sorted(self.knowledge_root.rglob("*.md"))[:max_items]:
            try:
                values.append(f"{path.name}: {path.read_text(encoding='utf-8')[:800]}")
            except OSError:
                continue
        return values, []

    def _memory_context(self, messages: list[dict[str, object]], current_user_message: str = "") -> tuple[list[str], list[str]]:
        if not self.memory_manager:
            return [], ["memory_recall: unavailable; reason: embedding model or vector store not ready"]
        query = current_user_message
        for item in reversed(messages):
            if not query and item.get("role") == "user" and item.get("content"):
                query = str(item.get("content"))
                break
        items, receipt = self.memory_manager.brain_recall.context_items(query, self.limits["context_max_memory_items"])
        limitations = receipt.limitations if not items else []
        return items, limitations
