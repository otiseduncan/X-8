from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.contracts import BrainContextBundle, KernelDecision, KernelRequest, SafetyDecision


class FakeBrain:
    def assemble(self, session_messages, attachments):
        bundle = BrainContextBundle()
        bundle.memory = ["saved memory"]
        bundle.knowledge = ["markdown knowledge"]
        bundle.research = ["research item"]
        bundle.preferences = ["Use direct operator language."]
        bundle.limitations = ["memory_recall: unavailable; reason: test", "Research source unavailable; no web research injected."]
        return bundle


class FakePrompt:
    def build(self, user_message, context, decision):
        return "prompt"


def test_model_owned_conversation_lanes_use_clean_context() -> None:
    context = KernelContextAssembler(FakeBrain(), FakePrompt()).assemble(
        KernelRequest(session_id="s", user_message="this conversation feels off"),
        KernelDecision(lane="conversation_repair", safety=SafetyDecision(allowed=True)),
    )
    assert context.context_bundle.memory == []
    assert context.context_bundle.knowledge == []
    assert context.context_bundle.research == []
    assert "memory" not in context.sources_used
    assert "knowledge" not in context.sources_used
