from datetime import datetime, timezone

from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.contracts import KernelDecision, KernelRequest, KernelResponse, KernelTrace, ResponseCard
from x8.kernel.event_bus import EventBus
from x8.kernel.model_router import ModelRouter
from x8.kernel.receipt_builder import KernelReceiptBuilder
from x8.kernel.response_planner import ResponsePlanner
from x8.kernel.safety_gate import SafetyGate
from x8.kernel.tool_decision import ToolDecisionEngine

UNAVAILABLE = "The assistant model is unavailable right now.\nNo model response was generated.\nCheck Settings > Model + Runtime."


class XV8Kernel:
    def __init__(
        self,
        context_assembler: KernelContextAssembler,
        model_router: ModelRouter,
        planner: ResponsePlanner | None = None,
        tool_decision: ToolDecisionEngine | None = None,
        safety_gate: SafetyGate | None = None,
        receipt_builder: KernelReceiptBuilder | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.context_assembler = context_assembler
        self.model_router = model_router
        self.planner = planner or ResponsePlanner()
        self.tool_decision = tool_decision or ToolDecisionEngine()
        self.safety_gate = safety_gate or SafetyGate()
        self.receipt_builder = receipt_builder or KernelReceiptBuilder()
        self.events = event_bus or EventBus()

    def handle(self, request: KernelRequest) -> KernelResponse:
        started_at = datetime.now(timezone.utc)
        self.events.emit("prompt_received", session_id=request.session_id)
        lane = self.planner.classify(request.user_message, bool(request.attachments))
        safety = self.safety_gate.decide(lane)
        tool_intent, artifact_intent = self.tool_decision.decide(lane)
        decision = KernelDecision(lane=lane, tool_intent=tool_intent, artifact_intent=artifact_intent, safety=safety)
        context = self.context_assembler.assemble(request, decision)
        self.events.emit("context_assembled", sources=context.sources_used)
        model_status, selection = self.model_router.select(lane)
        self.events.emit("model_selected", model=selection.selected_model, ready=selection.model_ready)
        deterministic = self._deterministic_response(request, lane, context.context_bundle)
        content, status, limitations = deterministic or self._respond(selection, context.prompt)
        model_status.selected_model = selection.selected_model
        model_status.fallback_used = selection.fallback_used
        model_status.timed_out = selection.timed_out
        model_status.timeout_seconds = selection.timeout_seconds
        if selection.reason_if_unavailable:
            model_status.failure_reason = selection.reason_if_unavailable
        limitations.extend(context.context_bundle.limitations)
        if model_status.failure_reason and model_status.failure_reason not in limitations:
            limitations.append(model_status.failure_reason)
        cards = self._cards(lane, status, limitations)
        tools = [tool_intent.name] if tool_intent else []
        receipt = self.receipt_builder.build(
            lane=lane,
            status=status,
            started_at=started_at,
            model=selection.selected_model,
            context_sources=context.sources_used,
            attachments=[str(item.get("attachment_id", item.get("filename", ""))) for item in request.attachments],
            tools=tools,
            limitations=limitations,
            fallback_used=selection.fallback_used,
            timed_out=selection.timed_out,
            timeout_seconds=selection.timeout_seconds,
            failure_reason=selection.reason_if_unavailable,
        )
        self.events.emit("receipt_created", receipt_id=receipt.receipt_id)
        trace = KernelTrace(lane_selected=lane, model_selected=selection.selected_model, context_sources_included=context.sources_used, tools_requested=tools, final_status=status)
        return KernelResponse(
            session_id=request.session_id or "",
            assistant_message=content,
            cards=cards,
            model_used=selection.selected_model,
            decision=decision,
            receipt=receipt,
            trace_summary=trace,
            limitations=limitations,
        )

    def _respond(self, selection, prompt: str) -> tuple[str, str, list[str]]:
        if not selection.model_ready:
            return UNAVAILABLE, "unavailable", [selection.reason_if_unavailable]
        ok, content, reason = self.model_router.generate(selection, prompt)
        if ok and content:
            self.events.emit("model_response_received")
            return content, "passed", []
        return UNAVAILABLE, "unavailable", [reason or "Model returned an empty response."]

    def _deterministic_response(self, request: KernelRequest, lane: str, bundle) -> tuple[str, str, list[str]] | None:
        lower = request.user_message.lower().strip()
        if "what is your name" in lower or lower in {"who are you", "who are you?"}:
            return "My name is XV8.", "passed", []
        if "say github" in lower:
            return "GitHub.", "passed", []
        if ("github" in lower and any(word in lower for word in ("access", "can you", "available", "status"))) or lower in {"github", "github?"}:
            return ("XV8 has GitHub Ops routes for status, previews, and approval-gated writes. "
                    "I should not claim GitHub is inaccessible; write operations still require explicit approval."), "passed", []
        if "currently working on" in lower or "what are we working on" in lower or "current task" in lower:
            recent = [item for item in bundle.session_context if item.strip()][-4:]
            if not recent:
                return "I do not have an explicit active task recorded in this XV8 chat yet.", "passed", []
            return "Current XV8 chat context is based on recent messages:\n" + "\n".join(f"- {item}" for item in recent), "passed", []
        if lane == "attachment_question":
            if bundle.attachments:
                return "I can access the uploaded attachment text included in this turn:\n" + "\n".join(f"- {item}" for item in bundle.attachments), "passed", []
            return "An attachment was referenced, but no extracted attachment text is available in this turn.", "passed", bundle.limitations
        return None

    def _cards(self, lane: str, status: str, limitations: list[str]) -> list[ResponseCard]:
        cards: list[ResponseCard] = []
        if limitations:
            cards.append(ResponseCard(type="info", title="Kernel limitations", status=status, summary="Some context or model capabilities were unavailable.", payload={"limitations": limitations}))
        if lane in {"web_search", "image_generation", "repo_inspection", "approval_required_action"}:
            cards.append(ResponseCard(type="status", title=f"Kernel lane: {lane}", status=status, summary="The kernel selected a tool-capable lane; tool execution remains routed through approved managers."))
        return cards
