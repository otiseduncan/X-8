import re


class BuildPromptIngestor:
    NEEDLES = ("self-build", "build prompt", "patch", "files", "tests", "completion rule", "do not commit", "inspect")
    CREATE_VERBS = (
        "build",
        "change",
        "changes",
        "changed",
        "changing",
        "add",
        "adds",
        "added",
        "adding",
        "implement",
        "implements",
        "implemented",
        "implementing",
        "modify",
        "modifies",
        "modified",
        "modifying",
        "update",
        "updates",
        "updated",
        "updating",
        "refactor",
        "refactors",
        "refactored",
        "refactoring",
        "create",
        "creates",
        "created",
        "creating",
        "fix",
        "fixes",
        "fixed",
        "fixing",
    )
    INSPECT_PHRASES = (
        "show proposal details",
        "show latest proposal",
        "show patch hash",
        "show approval id",
        "before approval",
        "do not apply",
        "do not write anything",
        "do not write anything yet",
        "no files should be changed",
        "what is the current proposal",
        "list proposal ids",
        "full self-build patch proposal details",
        "patch proposal details",
    )
    TRUST_PHRASES = ("show trust status", "trust status")
    VALIDATION_PHRASES = ("show validation report", "validation report")
    APPROVAL_PHRASES = ("approve", "apply", "approval id")

    def is_self_build_prompt(self, text: str) -> bool:
        lower = text.lower()
        return self.classify_intent(text) != "none"

    def classify_intent(self, text: str) -> str:
        lower = text.lower()
        if any(phrase in lower for phrase in self.TRUST_PHRASES):
            return "trust_status"
        if any(phrase in lower for phrase in self.VALIDATION_PHRASES):
            return "validation_report"
        if any(phrase in lower for phrase in self.INSPECT_PHRASES):
            return "inspect_proposal"
        if "self-build" in lower or sum(1 for needle in self.NEEDLES if needle in lower) >= 3:
            if self._has_create_verb(lower):
                return "create_proposal"
            if any(phrase in lower for phrase in self.APPROVAL_PHRASES):
                return "approval_apply"
            return "inspect_proposal"
        return "none"

    def _has_create_verb(self, lower: str) -> bool:
        return any(re.search(rf"\b{re.escape(verb)}\b", lower) for verb in self.CREATE_VERBS)

    def extract(self, text: str) -> dict[str, object]:
        lower = text.lower()
        files = sorted(set(re.findall(r"[\w./-]+\.(?:py|ts|tsx|js|jsx|css|md|yaml|yml|json|toml)|README\.md|compose\.yaml", text)))
        tests = [name for name in ("architecture_guard", "api_tests", "web_tests", "e2e_tests", "web_build", "compose_config") if name.replace("_", " ") in lower or name in lower]
        if not tests and ("architecture guard" in lower or "validation" in lower):
            tests = ["architecture_guard"]
        return {
            "goal": text.strip().splitlines()[0][:240] if text.strip() else "Self-build task",
            "files_to_inspect": files or ["README.md"],
            "constraints": self._lines_matching(text, ("must", "should", "keep", "only", "never")),
            "blocked_actions": self._lines_matching(text, ("do not", "never", "not acceptable")),
            "required_tests": tests,
            "completion_rule": "\n".join(self._lines_matching(text, ("completion", "expected")))[:1000],
            "commit_instruction": "do_not_commit" if "do not commit" in lower or "commit" not in lower else "commit_requires_approval",
            "risk_level": "normal_mutation",
        }

    def _lines_matching(self, text: str, needles: tuple[str, ...]) -> list[str]:
        return [line.strip() for line in text.splitlines() if any(needle in line.lower() for needle in needles)][:20]
