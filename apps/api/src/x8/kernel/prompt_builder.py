from x8.kernel.contracts import BrainContextBundle, KernelDecision


class KernelPromptBuilder:
    def build(self, user_message: str, context: BrainContextBundle, decision: KernelDecision) -> str:
        sections = [
            "System: You are XV8, a local assistant. Be honest about unavailable tools and proof.",
            f"Lane: {decision.lane}",
            f"User message:\n{user_message}",
        ]
        sections.extend(self._section("Session context", context.session_context))
        sections.extend(self._section("Relevant knowledge", context.knowledge))
        sections.extend(self._section("Memory", context.memory))
        sections.extend(self._section("Verified status", context.verified_status))
        sections.extend(self._section("Research", context.research))
        sections.extend(self._section("Preferences", context.preferences))
        sections.extend(self._section("Attachments", context.attachments))
        sections.append("Response instruction: answer directly and do not expose hidden reasoning.")
        return "\n\n".join(sections)

    def _section(self, title: str, values: list[str]) -> list[str]:
        if not values:
            return []
        return [f"{title}:\n" + "\n".join(f"- {value}" for value in values)]
