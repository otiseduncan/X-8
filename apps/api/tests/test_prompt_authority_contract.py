from x8.kernel.contracts import BrainContextBundle, KernelDecision, SafetyDecision
from x8.kernel.prompt_builder import KernelPromptBuilder


def test_prompt_includes_conversation_authority_contract() -> None:
    prompt = KernelPromptBuilder().build(
        "this feels off",
        BrainContextBundle(),
        KernelDecision(lane="conversation_repair", safety=SafetyDecision(allowed=True)),
    )
    assert "Use OpenWebUI and the selected local model for natural conversation" in prompt
    assert "Use X8 for operator work" in prompt
    assert "Do not show router wording" in prompt
    assert "ready to pull" in prompt
