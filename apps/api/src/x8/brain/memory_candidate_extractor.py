import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from x8.brain.memory_policy import redact_secret


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    source_text_redacted: str
    suggested_title: str
    suggested_content: str
    summary: str
    layer: str
    type: str
    confidence: float
    sensitivity: str
    scope: str
    reason: str
    decision: str
    source_turn_id: str = ""
    source_tool: str = "chat"
    project_scope: str = ""
    session_scope: str = ""
    global_scope: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_text_redacted": self.source_text_redacted,
            "suggested_title": self.suggested_title,
            "suggested_content": self.suggested_content,
            "summary": self.summary,
            "layer": self.layer,
            "type": self.type,
            "confidence": self.confidence,
            "sensitivity": self.sensitivity,
            "scope": self.scope,
            "reason": self.reason,
            "decision": self.decision,
            "source_turn_id": self.source_turn_id,
            "source_tool": self.source_tool,
            "project_scope": self.project_scope,
            "session_scope": self.session_scope,
            "global_scope": self.global_scope,
        }


class MemoryCandidateExtractor:
    def extract(
        self,
        source_text: str,
        *,
        source_turn_id: str = "",
        source_tool: str = "chat",
        project_scope: str = "",
        session_scope: str = "",
        global_scope: bool = True,
    ) -> list[MemoryCandidate]:
        text = source_text.strip()
        if not text:
            return []
        redacted = redact_secret(text)
        candidates: list[MemoryCandidate] = []
        for fragment in self._fragments(text):
            candidate = self._candidate(fragment.strip(), redacted, source_turn_id, source_tool, project_scope, session_scope, global_scope)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _fragments(self, text: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"(?:\n+|(?<=[.!?])\s+)", text) if part.strip()]
        return parts[:6] or [text]

    def _candidate(
        self,
        fragment: str,
        redacted_source: str,
        source_turn_id: str,
        source_tool: str,
        project_scope: str,
        session_scope: str,
        global_scope: bool,
    ) -> MemoryCandidate | None:
        lower = fragment.lower()
        scope = "session" if re.search(r"\b(for this chat only|temporary|just for now)\b", lower) else "global"
        session_only = scope == "session"
        summary = ""
        layer = "memory"
        memory_type = "auto_memory"
        confidence = 0.45
        reason = "No durable memory candidate found."

        secretish = re.search(r"\b(gh[pousr]_|sk-|password|passcode|token|api[_ -]?key|secret|private[_ -]?key|one[- ]?time code|otp)\b", lower)
        if secretish:
            summary = redact_secret(fragment).rstrip(".")
            layer = "blocked"
            memory_type = "never_save"
            confidence = 0.99
            reason = "Secret-like candidate must never be saved."

        sensitive = re.search(r"\b(family|spouse|wife|husband|child|children|relationship|health|medical|diagnosis|therapy|medication|finance|salary|bank|debt|ssn|address)\b", lower)
        if sensitive and not summary:
            summary = redact_secret(fragment).rstrip(".")
            layer = "pending"
            memory_type = "sensitive_candidate"
            confidence = 0.78
            reason = "Sensitive or private candidate requires approval."

        preference = re.match(r"(?i)^(?:i prefer|my preference is|use|don't make|do not make|when i say|from now on)\s+(.+)", fragment)
        if preference:
            summary = self._preference_summary(fragment)
            layer = "preferences"
            memory_type = "communication_preference" if re.search(r"\b(answer|style|senior-engineer|concise|direct)\b", lower) else "workflow_preference"
            confidence = 0.88
            reason = "Clear low-risk preference or workflow rule."

        correction = re.match(r"(?i)^(?:actually,?\s*)?(?:that's not right|do not call|don't call|github should not|from now on,?\s*do it this way|actually,?\s*i prefer)\s+(.+)", fragment)
        if correction:
            summary = self._preference_summary(fragment)
            layer = "preferences"
            memory_type = "correction"
            confidence = 0.86
            reason = "Explicit correction or learned behavior."

        work = re.match(r"(?i)^(?:we are working on|the current blocker is|next step is|this project is)\s+(.+)", fragment)
        if work:
            summary = self._active_work_summary(fragment)
            layer = "active_work"
            memory_type = "active_work_context"
            confidence = 0.82
            reason = "Clear active work context."
            scope = "project" if project_scope else "session"

        validation = re.search(r"(?i)\b(api-tests|web-tests|e2e|architecture-guard|build|phase \d+|commit [a-f0-9]{6,})\b.*\b(passed|pushed|commit|warning|warnings)\b", fragment)
        if validation:
            summary = fragment.rstrip(".")
            layer = "validation"
            memory_type = "validation_checkpoint"
            confidence = 0.84
            reason = "Validation or commit checkpoint."
            scope = "project" if project_scope else "global"

        if not summary:
            if len(fragment.split()) <= 5:
                return self._ignored(fragment, redacted_source, "Low-value chatter.", source_turn_id, source_tool, project_scope, session_scope, global_scope)
            return self._ignored(fragment, redacted_source, reason, source_turn_id, source_tool, project_scope, session_scope, global_scope)

        if session_only:
            return self._ignored(fragment, redacted_source, "Temporary/session-only remark without durable meaning.", source_turn_id, source_tool, project_scope, session_scope, global_scope)

        return MemoryCandidate(
            candidate_id=f"brain_cand_{uuid4().hex[:12]}",
            source_text_redacted=redacted_source,
            suggested_title=summary[:80],
            suggested_content=summary,
            summary=summary,
            layer=layer,
            type=memory_type,
            confidence=confidence,
            sensitivity="low",
            scope=scope,
            reason=reason,
            decision="auto_save",
            source_turn_id=source_turn_id,
            source_tool=source_tool,
            project_scope=project_scope,
            session_scope=session_scope,
            global_scope=global_scope,
        )

    def _ignored(
        self,
        fragment: str,
        redacted_source: str,
        reason: str,
        source_turn_id: str,
        source_tool: str,
        project_scope: str,
        session_scope: str,
        global_scope: bool,
    ) -> MemoryCandidate:
        return MemoryCandidate(
            candidate_id=f"brain_cand_{uuid4().hex[:12]}",
            source_text_redacted=redacted_source,
            suggested_title="Ignored candidate",
            suggested_content=redact_secret(fragment)[:240],
            summary=redact_secret(fragment)[:240],
            layer="ignored",
            type="ignored",
            confidence=0.2,
            sensitivity="low",
            scope="none",
            reason=reason,
            decision="ignored",
            source_turn_id=source_turn_id,
            source_tool=source_tool,
            project_scope=project_scope,
            session_scope=session_scope,
            global_scope=global_scope,
        )

    def _preference_summary(self, fragment: str) -> str:
        cleaned = fragment.strip().rstrip(".")
        cleaned = re.sub(r"(?i)^actually,?\s*", "", cleaned)
        if re.match(r"(?i)^i prefer ", cleaned):
            return "you prefer " + cleaned[9:]
        if re.match(r"(?i)^my preference is ", cleaned):
            return "you prefer " + cleaned[17:]
        if re.match(r"(?i)^use ", cleaned):
            return "use " + cleaned[4:]
        if re.match(r"(?i)^from now on,?\s*", cleaned):
            return re.sub(r"(?i)^from now on,?\s*", "", cleaned)
        if re.match(r"(?i)^do not call|^don't call", cleaned):
            return cleaned
        return cleaned

    def _active_work_summary(self, fragment: str) -> str:
        return fragment.strip().rstrip(".")
