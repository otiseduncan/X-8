from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.contracts import KernelContext, KernelDecision, KernelRequest
from x8.kernel.prompt_builder import KernelPromptBuilder


class KernelContextAssembler:
    def __init__(self, brain: BrainContextAssembler, prompt_builder: KernelPromptBuilder) -> None:
        self.brain = brain
        self.prompt_builder = prompt_builder

    def assemble(self, request: KernelRequest, decision: KernelDecision) -> KernelContext:
        bundle = self.brain.assemble(request.session_messages, request.attachments, request.user_message)
        sources = []
        for name in ("memory", "knowledge", "verified_status", "research", "preferences", "session_context", "attachments"):
            if getattr(bundle, name):
                sources.append(name)
        prompt = self.prompt_builder.build(request.user_message, bundle, decision)
        return KernelContext(context_bundle=bundle, sources_used=sources, prompt=prompt)
