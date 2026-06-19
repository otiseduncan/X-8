import re
from dataclasses import dataclass, field
from typing import Any

from x8.brain.brain_receipts import brain_card, brain_receipt
from x8.brain.active_focus_manager import ActiveFocusManager
from x8.brain.memory_policy import MemoryPolicyManager
from x8.brain.memory_store import BrainMemoryStore
from x8.contracts.receipts import Receipt

MISS_PHRASE = "I don’t have a saved memory for that yet."


@dataclass
class BrainCommandResult:
    handled: bool
    message: str
    status: str = "passed"
    receipts: list[Receipt] = field(default_factory=list)
    cards: list[Any] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


class BrainMemoryManager:
    def __init__(self, database_url: str, memory_enabled: bool = True) -> None:
        self.store = BrainMemoryStore(database_url)
        self.policy = MemoryPolicyManager()
        self.focus = ActiveFocusManager(self.store)
        self.memory_enabled = memory_enabled

    def status(self) -> dict[str, Any]:
        data = self.store.status()
        data["enabled"] = self.memory_enabled
        data["auto_capture_enabled"] = False
        data["semantic_retrieval_enabled"] = False
        return data

    def handle_chat_command(self, message: str, session_id: str = "") -> BrainCommandResult:
        lowered = message.strip().lower()
        if lowered.startswith("remember that ") or lowered.startswith("remember this "):
            content = re.sub(r"(?i)^remember (that|this)\s+", "", message.strip()).strip()
            return self.remember(content, session_id=session_id)
        if lowered.startswith("forget that ") or lowered.startswith("forget this "):
            content = re.sub(r"(?i)^forget (that|this)\s+", "", message.strip()).strip()
            return self.forget(content)
        if lowered.startswith("what do you remember"):
            query = re.sub(r"(?i)^what do you remember( about)?\s*", "", message.strip()).strip(" ?")
            return self.retrieve(query or message)
        if lowered.startswith("update your focus to "):
            focus = re.sub(r"(?i)^update your focus to\s+", "", message.strip()).strip()
            return self.set_focus(focus, session_id=session_id)
        if lowered in {"what are we currently working on?", "what are we currently working on", "what are we working on?", "what are we working on"}:
            answer = self.focus.current_work_answer(session_id=session_id)
            receipt = brain_receipt("brain.focus_retrieved", "passed", "Active focus retrieved.", {"session_id": session_id})
            return BrainCommandResult(True, answer, receipts=[receipt], cards=[brain_card("Active focus", "passed", answer)])
        return BrainCommandResult(False, "")

    def remember(self, content: str, session_id: str = "") -> BrainCommandResult:
        if not self.memory_enabled:
            receipt = brain_receipt("brain.memory_blocked", "disabled", "Brain memory is disabled.")
            return BrainCommandResult(True, "Brain memory is disabled.", "disabled", [receipt])
        decision = self.policy.decide(content)
        if decision.blocked:
            receipt = brain_receipt("brain.memory_blocked", "blocked", "Memory blocked because it looked like a secret.", {"policy": "secret_blocked"})
            return BrainCommandResult(True, "I can’t save secrets or credentials in memory.", "blocked", [receipt], [brain_card("Memory blocked", "blocked", "Secret-like content was not saved.")])
        if decision.requires_approval:
            receipt = brain_receipt("brain.memory_approval_required", "approval_required", "Sensitive memory requires approval before save.", {"sensitivity": decision.sensitivity})
            return BrainCommandResult(True, "That memory needs approval before I save it.", "approval_required", [receipt], [brain_card("Memory needs approval", "approval_required", "That memory needs approval before I save it.")])
        summary = self._summary(content)
        record = self.store.create_memory(
            summary,
            layer=self._layer(summary),
            memory_type=self._type(summary),
            title=self._title(summary),
            summary=summary,
            source_turn_id=session_id,
            sensitivity=decision.sensitivity,
            requires_approval=False,
            approved_by_user=True,
            tags=self._tags(summary),
        )
        message = f"Remembered: {summary}."
        receipt = brain_receipt("brain.memory_remembered", "passed", message, {"memory_id": record.get("id"), "layer": record.get("layer"), "type": record.get("type")})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Memory saved", "passed", message, {"memory_id": record.get("id")})], {"memory": record})

    def retrieve(self, query: str, limit: int = 3) -> BrainCommandResult:
        matches = self.store.search(query, limit=limit)
        if not matches:
            receipt = brain_receipt("brain.memory_retrieved", "no_matches", MISS_PHRASE, {"query": query, "count": 0})
            return BrainCommandResult(True, MISS_PHRASE, "passed", [receipt], [brain_card("Memory recall", "no_matches", MISS_PHRASE)])
        summaries = [str(item.get("summary") or item.get("content")) for item in matches]
        if len(summaries) == 1:
            answer = f"You prefer {self._preference_fragment(summaries[0])}." if "prefer" in summaries[0].lower() else summaries[0]
        else:
            answer = "Here is what I remember: " + "; ".join(summaries) + "."
        receipt = brain_receipt("brain.memory_retrieved", "passed", "Memory retrieved.", {"count": len(matches), "memory_ids": [item["id"] for item in matches]})
        return BrainCommandResult(True, answer, "passed", [receipt], [brain_card("Memory recall", "passed", "Retrieved saved memory.", {"count": len(matches)})], {"memories": matches})

    def forget(self, query: str) -> BrainCommandResult:
        target = self.store.find_forget_target(query)
        if not target:
            receipt = brain_receipt("brain.memory_forget", "no_matches", MISS_PHRASE, {"query": query})
            return BrainCommandResult(True, MISS_PHRASE, "passed", [receipt], [brain_card("Memory forget", "no_matches", MISS_PHRASE)])
        forgotten = self.store.soft_delete_memory(target["id"])
        summary = str((forgotten or target).get("summary") or (forgotten or target).get("content"))
        message = f"Forgotten: {summary}."
        receipt = brain_receipt("brain.memory_forgotten", "passed", message, {"memory_id": target["id"]})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Memory forgotten", "passed", message)], {"memory": forgotten or target})

    def set_focus(self, focus: str, session_id: str = "") -> BrainCommandResult:
        data = self.focus.set_focus(focus, session_id=session_id)
        message = f"Focus updated: {focus}."
        receipt = brain_receipt("brain.focus_updated", "passed", message, {"focus_id": data["id"], "session_id": session_id})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Focus updated", "passed", message)], {"focus": data})

    def _summary(self, content: str) -> str:
        cleaned = content.strip().rstrip(".")
        if re.match(r"(?i)^i prefer ", cleaned):
            return "you prefer " + cleaned[9:]
        if re.match(r"(?i)^my preference is ", cleaned):
            return "you prefer " + cleaned[17:]
        return cleaned

    def _title(self, summary: str) -> str:
        return summary[:80]

    def _layer(self, summary: str) -> str:
        return "preferences" if "prefer" in summary.lower() or "answer" in summary.lower() else "memory"

    def _type(self, summary: str) -> str:
        return "communication_preference" if "answer" in summary.lower() or "senior-engineer" in summary.lower() else "manual_memory"

    def _tags(self, summary: str) -> list[str]:
        tags = ["manual"]
        lower = summary.lower()
        if "answer" in lower:
            tags.append("answers")
        if "prefer" in lower:
            tags.append("preference")
        return tags

    def _preference_fragment(self, summary: str) -> str:
        return re.sub(r"(?i)^you prefer\s+", "", summary).rstrip(".")
