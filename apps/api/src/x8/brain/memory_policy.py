import re
from dataclasses import dataclass, field


SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{6,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{6,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\b(password|passcode|token|api[_ -]?key|secret|private[_ -]?key|one[- ]?time code|otp|raw secret log)\b", re.IGNORECASE),
)

SENSITIVE_PATTERNS = (
    re.compile(r"\b(family|spouse|wife|husband|child|children|relationship|dating|divorce)\b", re.IGNORECASE),
    re.compile(r"\b(health|medical|diagnosis|therapy|medication|mental health)\b", re.IGNORECASE),
    re.compile(r"\b(finance|salary|bank|debt|credit card|ssn|social security)\b", re.IGNORECASE),
    re.compile(r"\b(address|home address|location|passport|driver'?s license)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class MemoryPolicyDecision:
    decision: str
    sensitivity: str = "low"
    requires_approval: bool = False
    approved_by_user: bool = True
    reason: str = ""
    redacted_content: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def blocked(self) -> bool:
        return self.decision == "block"

    @property
    def approval_required(self) -> bool:
        return self.decision == "approval_required"


class MemoryPolicyManager:
    def decide(self, content: str) -> MemoryPolicyDecision:
        if self._looks_secret(content):
            return MemoryPolicyDecision(
                decision="block",
                sensitivity="secret",
                requires_approval=False,
                approved_by_user=False,
                reason="Secret-like content is blocked from Brain memory.",
                redacted_content=redact_secret(content),
                reasons=["Secret-like content is blocked from Brain memory."],
            )
        if self._looks_sensitive(content):
            return MemoryPolicyDecision(
                decision="approval_required",
                sensitivity="personal_sensitive",
                requires_approval=True,
                approved_by_user=False,
                reason="That memory needs approval before I save it.",
                redacted_content=redact_secret(content),
                reasons=["That memory needs approval before I save it."],
            )
        return MemoryPolicyDecision(decision="allow", sensitivity="low", requires_approval=False, approved_by_user=True, reason="Explicit low-risk manual memory is allowed.", redacted_content=content)

    def _looks_secret(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in SECRET_PATTERNS)

    def _looks_sensitive(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in SENSITIVE_PATTERNS)


def redact_secret(text: str) -> str:
    redacted = re.sub(r"\bgh[pousr]_[A-Za-z0-9_]+", "[redacted-token]", text, flags=re.IGNORECASE)
    redacted = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[redacted-api-key]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*", "[redacted-private-key]", redacted, flags=re.IGNORECASE | re.DOTALL)
    redacted = re.sub(r"(?i)(password|passcode|token|api[_ -]?key|secret|one[- ]?time code|otp)\s*(is|=|:)?\s*\S+", r"\1 [redacted]", redacted)
    return redacted
