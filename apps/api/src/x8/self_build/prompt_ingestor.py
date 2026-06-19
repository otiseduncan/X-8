import re

SMOKE_PROOF_FILE = "runtime/self_build_smoke/approved_apply_proof.md"


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
        "wire",
        "wires",
        "wired",
        "wiring",
    )
    SELF_BUILD_MARKERS = ("self-build", "self build", "patch proposal", "proposal-only", "approval", "patch hash")
    DESTRUCTIVE_PHRASES = ("delete", "remove", "wipe", "erase", "destroy", "drop table", "rm -rf", "credential", "token", "secret", "password", "push")
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
        return self.classify_intent(text) != "none"

    def classify_intent(self, text: str) -> str:
        lower = text.lower()
        is_self_build = self._is_self_build_context(lower)
        if is_self_build and self._has_apply_intent(lower):
            return "approval_apply"
        if is_self_build and self._has_create_verb(lower):
            return "create_proposal"
        if is_self_build and self._has_validation_report_intent(lower):
            return "validation_report"
        if is_self_build and self._has_trust_status_intent(lower):
            return "trust_status"
        if is_self_build:
            return "inspect_proposal"
        if self._has_validation_report_intent(lower):
            return "validation_report"
        if self._has_trust_status_intent(lower):
            return "trust_status"
        if any(phrase in lower for phrase in self.INSPECT_PHRASES):
            return "inspect_proposal"
        return "none"

    def _is_self_build_context(self, lower: str) -> bool:
        return any(marker in lower for marker in self.SELF_BUILD_MARKERS) or sum(1 for needle in self.NEEDLES if needle in lower) >= 3

    def _has_create_verb(self, lower: str) -> bool:
        normalized = lower.replace("self-build", "selfbuild").replace("self build", "selfbuild")
        for verb in self.CREATE_VERBS:
            for match in re.finditer(rf"\b{re.escape(verb)}\b", normalized):
                prefix = normalized[max(0, match.start() - 20) : match.start()]
                if any(negation in prefix for negation in ("do not ", "don't ", "dont ", "never ")):
                    continue
                return True
        return False

    def _has_apply_intent(self, lower: str) -> bool:
        if any(phrase in lower for phrase in ("do not apply", "do not write", "before approval", "until i approve", "until approved")):
            return False
        action = re.search(r"\b(apply|approve|write)\b", lower) is not None
        hash_context = any(phrase in lower for phrase in ("patch_hash", "patch hash", "approval_id", "approval id", "approved=true"))
        return action and hash_context

    def _has_trust_status_intent(self, lower: str) -> bool:
        direct = any(phrase in lower for phrase in ("show trust status", "show self-build trust status", "current trust status", "what is the trust status"))
        return direct and not self._has_create_verb(lower)

    def _has_validation_report_intent(self, lower: str) -> bool:
        direct = any(phrase in lower for phrase in ("show validation report", "show latest validation report", "show latest self-build validation report", "latest validation report"))
        return direct and not self._has_create_verb(lower)

    def extract(self, text: str) -> dict[str, object]:
        lower = text.lower()
        files = sorted(set(re.findall(r"[\w./-]+\.(?:py|ts|tsx|js|jsx|css|md|yaml|yml|json|toml)|README\.md|compose\.yaml", text)))
        task_type = self.classify_task_type(text)
        if self._mentions_smoke_proof(lower) and SMOKE_PROOF_FILE not in files:
            files = [SMOKE_PROOF_FILE, *files]
        if not files:
            files = self.default_files_for_task(task_type)
        tests = [name for name in ("architecture_guard", "api_tests", "web_tests", "e2e_tests", "web_build", "compose_config") if name.replace("_", " ") in lower or name in lower]
        if not tests and ("architecture guard" in lower or "validation" in lower):
            tests = ["architecture_guard"]
        if task_type == "ui_feature":
            tests = self._dedupe([*tests, "architecture_guard", "web_tests", "web_build"])
        return {
            "goal": text.strip().splitlines()[0][:240] if text.strip() else "Self-build task",
            "task_type": task_type,
            "files_to_inspect": files,
            "constraints": self._lines_matching(text, ("must", "should", "keep", "only", "never")),
            "blocked_actions": [*self._lines_matching(text, ("do not", "never", "not acceptable")), *[phrase for phrase in self.DESTRUCTIVE_PHRASES if phrase in lower]],
            "required_tests": tests,
            "completion_rule": "\n".join(self._lines_matching(text, ("completion", "expected")))[:1000],
            "commit_instruction": "do_not_commit" if "do not commit" in lower or "commit" not in lower else "commit_requires_approval",
            "risk_level": "normal_mutation",
        }

    def _lines_matching(self, text: str, needles: tuple[str, ...]) -> list[str]:
        return [line.strip() for line in text.splitlines() if any(needle in line.lower() for needle in needles)][:20]

    def classify_task_type(self, text: str) -> str:
        lower = text.lower()
        if self._mentions_smoke_proof(lower):
            return "smoke_proof"
        if any(word in lower for word in ("readme", "documentation", "docs", "document ")):
            return "docs_only"
        if any(word in lower for word in ("test only", "tests only", "add test", "unit test", "api test", "web test")):
            return "test_only"
        if any(word in lower for word in ("compose", ".env", "config", "configuration")):
            return "config_change"
        if any(word in lower for word in ("ui", "frontend", "web", "dashboard", "card", "label", "screen", "panel")):
            return "ui_feature"
        if any(word in lower for word in ("api", "endpoint", "route", "manager", "backend")):
            return "api_feature"
        return "unknown_safe"

    def _mentions_smoke_proof(self, lower: str) -> bool:
        return "self-build apply proof file" in lower or "self build apply proof file" in lower or "smoke proof file" in lower or SMOKE_PROOF_FILE in lower

    def default_files_for_task(self, task_type: str) -> list[str]:
        if task_type == "ui_feature":
            return ["apps/web/src/app/App.tsx", "apps/web/src/services/apiClient.ts"]
        if task_type == "api_feature":
            return ["apps/api/src/x8/api/routes/self_build.py", "apps/api/src/x8/self_build/manager.py", "apps/api/tests/test_api_contracts.py"]
        if task_type == "test_only":
            return ["apps/api/tests/test_api_contracts.py"]
        if task_type == "docs_only":
            return ["README.md"]
        if task_type == "config_change":
            return [".env.example"]
        return []

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value not in result:
                result.append(value)
        return result
