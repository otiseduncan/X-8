from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.contracts import KernelContext, KernelDecision, KernelRequest
from x8.kernel.prompt_builder import KernelPromptBuilder


MODEL_OWNED_LANES = {
    "normal_chat",
    "conversation_repair",
    "reasoning",
    "code_help",
    "prompt_generation",
    "settings_request",
    "model_status_request",
}

OPERATOR_CONTEXT_LANES = {
    "brain_retrieve",
    "brain_continuity",
    "repo_inspection",
    "attachment_question",
}


class KernelContextAssembler:
    def __init__(self, brain: BrainContextAssembler, prompt_builder: KernelPromptBuilder) -> None:
        self.brain = brain
        self.prompt_builder = prompt_builder

    def assemble(self, request: KernelRequest, decision: KernelDecision) -> KernelContext:
        bundle = self.brain.assemble(request.session_messages, request.attachments)
        self._apply_authority_boundary(bundle, decision.lane)
        sources = []
        for name in ("memory", "knowledge", "verified_status", "research", "preferences", "session_context", "attachments"):
            if getattr(bundle, name):
                sources.append(name)
        prompt = self.prompt_builder.build(request.user_message, bundle, decision)
        return KernelContext(context_bundle=bundle, sources_used=sources, prompt=prompt)

    def _apply_authority_boundary(self, bundle, lane: str) -> None:
        if lane in MODEL_OWNED_LANES:
            bundle.memory = []
            bundle.knowledge = []
            bundle.research = []
            bundle.limitations = [item for item in bundle.limitations if "memory_recall" not in item and "Research source" not in item]
        if lane not in OPERATOR_CONTEXT_LANES and not bundle.attachments:
            bundle.attachments = []
