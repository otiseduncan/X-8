import re


class BuildPromptIngestor:
    NEEDLES = ("self-build", "build prompt", "patch", "files", "tests", "completion rule", "do not commit", "inspect")

    def is_self_build_prompt(self, text: str) -> bool:
        lower = text.lower()
        return "self-build" in lower or sum(1 for needle in self.NEEDLES if needle in lower) >= 3

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
