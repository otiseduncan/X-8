import re
from dataclasses import dataclass, field


SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{6,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\b(password|passcode|token|api[_ -]?key|secret|private[_ -]?key|one[- ]?time code|otp)\b", re.IGNORECASE),
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
    reasons: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def blocked(self) -> bool:
        return self.decision == "block"


class MemoryPolicyManager:
    def decide(self, content: str) -> MemoryPolicyDecision:
        if self._looks_secret(content):
            return MemoryPolicyDecision(
                decision="block",
                sensitivity="secret",
                requires_approval=False,
                approved_by_user=False,
                reasons=["Secret-like content is blocked from Brain memory."],
            )
        if self._looks_sensitive(content):
            return MemoryPolicyDecision(
                decision="approval_required",
                sensitivity="personal_sensitive",
                requires_approval=True,
                approved_by_user=False,
                reasons=["That memory needs approval before I save it."],
            )
        return MemoryPolicyDecision(decision="allow", sensitivity="low", requires_approval=False, approved_by_user=True)

    def _looks_secret(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in SECRET_PATTERNS)

    def _looks_sensitive(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in SENSITIVE_PATTERNS)

