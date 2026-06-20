import re
from dataclasses import dataclass, field
from typing import Any

from x8.brain.active_focus_manager import ActiveFocusManager
from x8.brain.brain_receipts import brain_card, brain_receipt
from x8.brain.continuity_store import BrainContinuityStore
from x8.brain.memory_policy import MemoryPolicyManager, redact_secret
from x8.brain.memory_store import BrainMemoryStore
from x8.contracts.receipts import Receipt

PROJECT_MISS = "I don’t have a current project state saved yet."
NEXT_MISS = "I don’t have a next step saved yet."
BLOCKER_MISS = "I don’t have a blocker saved yet."
VALIDATION_MISS = "I don’t have a validation checkpoint saved yet."


@dataclass
class ContinuityResult:
    handled: bool
    message: str
    status: str = "passed"
    receipts: list[Receipt] = field(default_factory=list)
    cards: list[Any] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


class BrainContinuityManager:
    def __init__(self, database_url: str) -> None:
        self.store = BrainContinuityStore(database_url)
        self.policy = MemoryPolicyManager()
        self.focus = ActiveFocusManager(BrainMemoryStore(database_url))

    def status(self, project_scope: str = "", session_scope: str = "") -> dict[str, Any]:
        project = self.current_project(project_scope=project_scope, session_scope=session_scope)
        next_step = self.latest("next_step", project_scope=project_scope, session_scope=session_scope)
        validation = self.latest("validation_checkpoint", project_scope=project_scope, session_scope=session_scope, statuses=("active", "done"))
        commit = self.latest("commit_checkpoint", project_scope=project_scope, session_scope=session_scope, statuses=("active", "done"))
        blockers = self.records(record_type="blocker", status="active", project_scope=project_scope, session_scope=session_scope)
        tasks = self.records(record_type="task", status="active", project_scope=project_scope, session_scope=session_scope)
        decisions = self.records(record_type="decision", status="active", project_scope=project_scope, session_scope=session_scope, limit=5)
        return {
            "continuity_ready": True,
            "storage_backend": "postgres",
            "record_count": len(self.records(project_scope=project_scope, session_scope=session_scope, limit=500)),
            "current_project": project,
            "next_step": next_step,
            "active_blockers": blockers,
            "active_tasks": tasks,
            "last_validation_checkpoint": validation,
            "latest_commit_checkpoint": commit,
            "recent_decisions": decisions,
            "event_count": len(self.store.list_events(limit=50)),
        }

    def records(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.store.list_records(**kwargs)

    def latest(self, record_type: str, *, project_scope: str = "", session_scope: str = "", statuses: tuple[str, ...] = ("active",)) -> dict[str, Any] | None:
        return self.store.latest(record_type, statuses=statuses, project_scope=project_scope, session_scope=session_scope)

    def current_project(self, project_scope: str = "", session_scope: str = "") -> dict[str, Any] | None:
        return self.latest("project_state", project_scope=project_scope, session_scope=session_scope)

    def create_record(self, record: dict[str, Any]) -> ContinuityResult:
        summary = str(record.get("summary") or record.get("content") or record.get("title") or "").strip()
        blocked = self._blocked(summary)
        if blocked:
            return blocked
        record = self.store.create_record(record | {"summary": summary, "content": record.get("content") or summary})
        return self._result(f"Saved {record['record_type'].replace('_', ' ')}: {record['summary']}.", "brain.continuity_saved", record)

    def update_record(self, record_id: str, patch: dict[str, Any]) -> ContinuityResult:
        summary = str(patch.get("summary") or patch.get("content") or "")
        blocked = self._blocked(summary)
        if blocked:
            return blocked
        record = self.store.update_record(record_id, patch)
        if not record:
            return ContinuityResult(True, "Continuity record not found.", "missing", [brain_receipt("brain.continuity_missing", "missing", "Continuity record not found.", {"record_id": record_id})])
        return self._result("Continuity record updated.", "brain.continuity_updated", record)

    def archive_record(self, record_id: str) -> ContinuityResult:
        record = self.store.soft_delete_record(record_id)
        if not record:
            return ContinuityResult(True, "Continuity record not found.", "missing")
        return self._result("Continuity record archived.", "brain.continuity_archived", record)

    def set_project_state(self, summary: str, **scope: Any) -> ContinuityResult:
        return self._set_singleton("project_state", summary, "Saved current project state", **scope)

    def set_next_step(self, summary: str, **scope: Any) -> ContinuityResult:
        return self._set_singleton("next_step", summary, "Saved next step", **scope)

    def add_blocker(self, summary: str, **scope: Any) -> ContinuityResult:
        return self._set_singleton("blocker", summary, "Saved blocker", priority="high", **scope)

    def clear_blocker(self, **scope: Any) -> ContinuityResult:
        blockers = self.records(record_type="blocker", status="active", project_scope=str(scope.get("project_scope") or ""), session_scope=str(scope.get("session_scope") or ""))
        for blocker in blockers:
            self.store.update_record(blocker["id"], {"status": "done", "active": False})
        receipt = brain_receipt("brain.continuity_blocker_cleared", "passed", "Current blocker cleared.", {"count": len(blockers)})
        return ContinuityResult(True, "Current blocker cleared.", "passed", [receipt], [brain_card("Blocker cleared", "passed", "Current blocker cleared.")], {"cleared": blockers})

    def add_validation(self, summary: str, **scope: Any) -> ContinuityResult:
        return self._create_checkpoint("validation_checkpoint", summary, "Saved validation checkpoint", **scope)

    def add_commit_checkpoint(self, summary: str, **scope: Any) -> ContinuityResult:
        sha = _commit_sha(summary)
        return self._create_checkpoint("commit_checkpoint", summary, "Saved commit checkpoint", linked_commit_sha=sha, **scope)

    def add_decision(self, summary: str, **scope: Any) -> ContinuityResult:
        return self._create_checkpoint("decision", summary, "Saved decision", **scope)

    def create_task(self, summary: str, **scope: Any) -> ContinuityResult:
        blocked = self._blocked(summary)
        if blocked:
            return blocked
        record = self.store.create_record({"record_type": "task", "title": summary[:120], "summary": summary, "content": summary, **scope})
        return self._result(f"Saved task: {record['summary']}.", "brain.continuity_task_saved", record)

    def complete_task(self, record_id: str = "", **scope: Any) -> ContinuityResult:
        task = self.store.get_record(record_id) if record_id else self.latest("task", project_scope=str(scope.get("project_scope") or ""), session_scope=str(scope.get("session_scope") or ""))
        if not task:
            return ContinuityResult(True, "No active task found to complete.", "no_matches")
        record = self.store.update_record(task["id"], {"status": "done", "active": False})
        return self._result(f"Marked task done: {record['summary']}.", "brain.continuity_task_done", record)

    def handoff(self, project_scope: str = "", session_scope: str = "") -> ContinuityResult:
        data = self.status(project_scope=project_scope, session_scope=session_scope)
        lines = [
            "Handoff note:",
            f"- Current project: {_summary(data['current_project'], PROJECT_MISS)}",
            f"- Active focus: {self.focus.current_work_answer(session_id=session_scope, project_scope=project_scope)}",
            f"- Next step: {_summary(data['next_step'], NEXT_MISS)}",
            f"- Blockers: {_join(data['active_blockers'], BLOCKER_MISS)}",
            f"- Last validation: {_summary(data['last_validation_checkpoint'], VALIDATION_MISS)}",
            f"- Decisions: {_join(data['recent_decisions'], 'none')}",
            f"- Latest commit checkpoint: {_summary(data['latest_commit_checkpoint'], 'none')}",
        ]
        note = "\n".join(lines)
        record = self.store.create_record({"record_type": "handoff_note", "title": "Handoff note", "summary": note, "content": note, "project_scope": project_scope, "session_scope": session_scope, "global_scope": not bool(session_scope)})
        receipt = brain_receipt("brain.continuity_handoff", "passed", "Continuity handoff note created.", {"record_id": record["id"]})
        return ContinuityResult(True, note, "passed", [receipt], [brain_card("Handoff note", "passed", "Continuity handoff note created.", {"record_id": record["id"]})], {"handoff": note, "record": record, **data})

    def answer(self, question: str, project_scope: str = "", session_scope: str = "") -> ContinuityResult:
        lower = question.lower().strip(" ?")
        if "currently working on" in lower or "current project state" in lower or "status of x-8" in lower or "show me the current project state" in lower:
            scoped_project = self.records(record_type="project_state", status="active", project_scope=project_scope, session_scope=session_scope, limit=1) if session_scope or project_scope else []
            project = scoped_project[0] if scoped_project else None
            if project:
                return self._answer(f"Current project state: {project['summary']}.", "brain.continuity_project_retrieved", project)
            focus = self.focus.current_work_answer(session_id=session_scope, project_scope=project_scope)
            if "No active focus" not in focus:
                return ContinuityResult(True, focus, "passed", [brain_receipt("brain.continuity_focus_fallback", "passed", "Active focus fallback retrieved.")])
            project = self.current_project(project_scope, session_scope)
            if project:
                return self._answer(f"Current project state: {project['summary']}.", "brain.continuity_project_retrieved", project)
            return self._miss(PROJECT_MISS, "brain.continuity_project_missing")
        if "next step" in lower or "before continuing" in lower:
            return self._latest_answer("next_step", "Next step", NEXT_MISS, "brain.continuity_next_step_retrieved", project_scope, session_scope)
        if "blocked" in lower or "blocker" in lower:
            blockers = self.records(record_type="blocker", status="active", project_scope=project_scope, session_scope=session_scope)
            if blockers:
                return self._answer(f"Current blocker: {blockers[0]['summary']}.", "brain.continuity_blocker_retrieved", blockers[0])
            return self._miss(BLOCKER_MISS, "brain.continuity_blocker_missing")
        if "validate" in lower:
            return self._latest_answer("validation_checkpoint", "Last validation checkpoint", VALIDATION_MISS, "brain.continuity_validation_retrieved", project_scope, session_scope, ("active", "done"))
        if "last checkpoint" in lower or "changed in the last checkpoint" in lower:
            return self._latest_answer("commit_checkpoint", "Last checkpoint", "I don’t have a checkpoint saved yet.", "brain.continuity_checkpoint_retrieved", project_scope, session_scope, ("active", "done"))
        if "decide" in lower or "decision" in lower:
            decisions = self.records(record_type="decision", status="active", project_scope=project_scope, session_scope=session_scope, limit=3)
            if decisions:
                return self._answer("Recent decision: " + "; ".join(item["summary"] for item in decisions) + ".", "brain.continuity_decision_retrieved", decisions[0])
            return self._miss("I don’t have a decision saved yet.", "brain.continuity_decision_missing")
        if "handoff" in lower:
            return self.handoff(project_scope, session_scope)
        return ContinuityResult(False, "")

    def handle_chat_command(self, message: str, session_id: str = "", project_scope: str = "") -> ContinuityResult:
        text = message.strip()
        lowered = text.lower()
        scope = {"session_scope": session_id, "project_scope": project_scope, "global_scope": True}
        patterns = [
            (r"(?i)^we are working on\s+(.+)$", self.set_project_state),
            (r"(?i)^the current project is\s+(.+)$", self.set_project_state),
            (r"(?i)^the next step is\s+(.+)$", self.set_next_step),
            (r"(?i)^mark this blocked by\s+(.+)$", self.add_blocker),
            (r"(?i)^the blocker is\s+(.+)$", self.add_blocker),
            (r"(?i)^we validated\s+(.+)$", self.add_validation),
            (r"(?i)^commit checkpoint:\s*(.+)$", self.add_commit_checkpoint),
            (r"(?i)^checkpoint:\s*(.+)$", self.add_commit_checkpoint),
            (r"(?i)^decision:\s*(.+)$", self.add_decision),
            (r"(?i)^(?:create task|task):\s*(.+)$", self.create_task),
        ]
        for pattern, handler in patterns:
            match = re.match(pattern, text)
            if match:
                return handler(match.group(1).strip(), **scope)
        if lowered in {"clear the blocker", "clear blocker"}:
            return self.clear_blocker(**scope)
        if lowered in {"mark that done", "mark task done", "complete task"}:
            return self.complete_task(**scope)
        return self.answer(text, project_scope=project_scope, session_scope=session_id)

    def auto_capture(self, message: str, lane: str, session_id: str = "", project_scope: str = "") -> ContinuityResult:
        if lane.startswith("github_") or lane == "self_build" or lane.startswith("brain_") or lane in {"approval_required_action", "attachment_question"}:
            return ContinuityResult(False, "")
        return self.handle_chat_command(message, session_id=session_id, project_scope=project_scope)

    def _set_singleton(self, record_type: str, summary: str, label: str, **scope: Any) -> ContinuityResult:
        blocked = self._blocked(summary)
        if blocked:
            return blocked
        record = self.store.upsert_singleton(record_type, redact_secret(summary), title=summary[:120], **scope)
        if record_type == "project_state":
            self.focus.set_focus(record["summary"], session_id=str(scope.get("session_scope") or ""), project_scope=str(scope.get("project_scope") or ""))
        return self._result(f"{label}: {record['summary']}.", f"brain.continuity_{record_type}_saved", record)

    def _create_checkpoint(self, record_type: str, summary: str, label: str, **scope: Any) -> ContinuityResult:
        blocked = self._blocked(summary)
        if blocked:
            return blocked
        record = self.store.create_record({"record_type": record_type, "title": summary[:120], "summary": summary, "content": summary, "status": "done" if "checkpoint" in record_type else "active", **scope})
        return self._result(f"{label}: {record['summary']}.", f"brain.continuity_{record_type}_saved", record)

    def _latest_answer(self, record_type: str, label: str, miss: str, action: str, project_scope: str, session_scope: str, statuses: tuple[str, ...] = ("active",)) -> ContinuityResult:
        record = self.latest(record_type, project_scope=project_scope, session_scope=session_scope, statuses=statuses)
        if not record:
            return self._miss(miss, action.replace("retrieved", "missing"))
        return self._answer(f"{label}: {record['summary']}.", action, record)

    def _answer(self, message: str, action: str, record: dict[str, Any]) -> ContinuityResult:
        receipt = brain_receipt(action, "passed", message, {"record_id": record.get("id"), "record_type": record.get("record_type")})
        return ContinuityResult(True, message, "passed", [receipt], [brain_card("Continuity", "passed", "Continuity record retrieved.", {"record_id": record.get("id")})], {"record": record})

    def _miss(self, message: str, action: str) -> ContinuityResult:
        return ContinuityResult(True, message, "passed", [brain_receipt(action, "no_matches", message)], [brain_card("Continuity", "no_matches", message)])

    def _result(self, message: str, action: str, record: dict[str, Any]) -> ContinuityResult:
        receipt = brain_receipt(action, "passed", message, {"record_id": record.get("id"), "record_type": record.get("record_type")})
        return ContinuityResult(True, message, "passed", [receipt], [brain_card("Continuity saved", "passed", "Continuity record saved.", {"record_id": record.get("id")})], {"record": record})

    def _blocked(self, content: str) -> ContinuityResult | None:
        decision = self.policy.decide(content)
        if decision.blocked:
            receipt = brain_receipt("brain.continuity_blocked", "blocked", "Continuity record blocked because it looked like a secret.", {"policy": "secret_blocked"})
            return ContinuityResult(True, "I can’t save secrets or credentials in continuity memory.", "blocked", [receipt], [brain_card("Continuity blocked", "blocked", "Secret-like content was not saved.")])
        return None


def _summary(record: dict[str, Any] | None, missing: str) -> str:
    return str(record.get("summary")) if record else missing


def _join(records: list[dict[str, Any]], missing: str) -> str:
    return "; ".join(str(item.get("summary")) for item in records) if records else missing


def _commit_sha(text: str) -> str:
    match = re.search(r"\b[0-9a-f]{7,40}\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""
