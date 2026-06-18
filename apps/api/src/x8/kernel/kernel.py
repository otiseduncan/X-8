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
        content, status, limitations = self._respond(selection, context.prompt)
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

    def _cards(self, lane: str, status: str, limitations: list[str]) -> list[ResponseCard]:
        cards: list[ResponseCard] = []
        if limitations:
            cards.append(ResponseCard(type="info", title="Kernel limitations", status=status, summary="Some context or model capabilities were unavailable.", payload={"limitations": limitations}))
        if lane in {"web_search", "image_generation", "repo_inspection", "approval_required_action"}:
            cards.append(ResponseCard(type="status", title=f"Kernel lane: {lane}", status=status, summary="The kernel selected a tool-capable lane; tool execution remains routed through approved managers."))
        return cards
