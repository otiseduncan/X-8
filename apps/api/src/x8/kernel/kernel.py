import os
import re
from datetime import datetime, timezone

from x8.brain.continuity_manager import BrainContinuityManager
from x8.brain.memory_manager import BrainMemoryManager
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.contracts import KernelDecision, KernelRequest, KernelResponse, KernelTrace, ResponseCard
from x8.kernel.event_bus import EventBus
from x8.kernel.model_router import ModelRouter
from x8.kernel.receipt_builder import KernelReceiptBuilder
from x8.kernel.response_planner import ResponsePlanner
from x8.kernel.safety_gate import SafetyGate
from x8.kernel.tool_decision import ToolDecisionEngine

UNAVAILABLE = "The assistant model is unavailable right now.\nNo model response was generated.\nCheck Settings > Model + Runtime."
AUTO_CAPTURE_BLOCKED_LANES = {"conversation_repair", "reasoning", "code_help", "prompt_generation", "settings_request", "model_status_request"}


def _unavailable_message(reason: str | None = None) -> str:
    clean_reason = (reason or "").strip()
    if not clean_reason:
        return UNAVAILABLE
    return (
        f"{UNAVAILABLE}\n\n"
        "Bridge failure:\n"
        f"{clean_reason}\n\n"
        "Run /api/brain/health?probe=true or scripts/Test-X8BrainBridge.ps1 for the full bridge check."
    )


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
        brain_manager: BrainMemoryManager | None = None,
        continuity_manager: BrainContinuityManager | None = None,
    ) -> None:
        self.context_assembler = context_assembler
        self.model_router = model_router
        self.planner = planner or ResponsePlanner()
        self.tool_decision = tool_decision or ToolDecisionEngine()
        self.safety_gate = safety_gate or SafetyGate()
        self.receipt_builder = receipt_builder or KernelReceiptBuilder()
        self.events = event_bus or EventBus()
        self.brain_manager = brain_manager
        self.continuity_manager = continuity_manager

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
        brain_result = self._brain_command_result(request, lane)
        continuity_result = self._continuity_command_result(request, lane)
        command_result = brain_result if brain_result and brain_result.handled else continuity_result
        deterministic = (command_result.message, command_result.status if command_result.status != "approval_required" else "passed", getattr(command_result, "limitations", [])) if command_result and command_result.handled else self._deterministic_response(request, lane, context.context_bundle, selection)
        deterministic_used = deterministic is not None
        content, status, limitations = deterministic or self._respond(selection, context.prompt)
        model_status.selected_model = selection.selected_model
        model_status.fallback_used = selection.fallback_used
        model_status.timed_out = selection.timed_out
        model_status.timeout_seconds = selection.timeout_seconds
        if deterministic_used:
            model_status.failure_reason = ""
        elif selection.reason_if_unavailable:
            model_status.failure_reason = selection.reason_if_unavailable
        if not deterministic_used:
            limitations.extend(context.context_bundle.limitations)
        if model_status.failure_reason and model_status.failure_reason not in limitations:
            limitations.append(model_status.failure_reason)
        cards = self._cards(lane, status, limitations, request)
        extra_receipts = []
        if brain_result and brain_result.handled:
            cards.extend(brain_result.cards)
            extra_receipts.extend(brain_result.receipts)
        if continuity_result and continuity_result.handled:
            cards.extend(continuity_result.cards)
            extra_receipts.extend(continuity_result.receipts)
        if self.brain_manager and self._x8_memory_capture_allowed(lane):
            auto_capture = self.brain_manager.auto_capture(request.user_message, lane=lane, session_id=request.session_id or "")
            if auto_capture.handled:
                cards.extend(auto_capture.cards)
                extra_receipts.extend(auto_capture.receipts)
        if self.continuity_manager and self._x8_memory_capture_allowed(lane):
            continuity_capture = self.continuity_manager.auto_capture(request.user_message, lane=lane, session_id=request.session_id or "")
            if continuity_capture.handled:
                cards.extend(continuity_capture.cards)
                extra_receipts.extend(continuity_capture.receipts)
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
            failure_reason="" if deterministic_used else selection.reason_if_unavailable,
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
            extra_receipts=extra_receipts,
            trace_summary=trace,
            limitations=limitations,
        )

    def _respond(self, selection, prompt: str) -> tuple[str, str, list[str]]:
        if not selection.model_ready:
            reason = selection.reason_if_unavailable or "Model router selected no ready model."
            return _unavailable_message(reason), "unavailable", [reason]
        ok, content, reason = self.model_router.generate(selection, prompt)
        if ok and content:
            self.events.emit("model_response_received")
            return content, "passed", []
        reason = reason or "Model returned an empty response."
        return _unavailable_message(reason), "unavailable", [reason]

    def _deterministic_response(self, request: KernelRequest, lane: str, bundle, selection=None) -> tuple[str, str, list[str]] | None:
        lower = request.user_message.lower().strip()
        if "currently working on" in lower or "what are we working on" in lower or "current task" in lower:
            recent = [item for item in bundle.session_context if item.strip()][-4:]
            if not recent:
                return "I do not have an explicit active task recorded in this XV8 chat yet.", "passed", []
            return "Current XV8 chat context is based on recent messages:\n" + "\n".join(f"- {item}" for item in recent), "passed", []
        if lane.startswith("brain_"):
            if lane == "brain_continuity" and not self.continuity_manager:
                return "Brain continuity is unavailable right now.", "unavailable", ["Brain continuity manager unavailable."]
            if not self.brain_manager and lane != "brain_continuity":
                return "Brain memory is unavailable right now.", "unavailable", ["Brain manager unavailable."]
        if lower in {"hi", "hi xv8", "hi xoduz", "hello", "hello xv8", "hello xoduz", "hey", "hey xv8", "hey xoduz", "good morning", "good afternoon", "good evening"}:
            return "Hello. I'm Xoduz, pronounced Exodus.", "passed", []
        if "what is your name" in lower or lower in {"who are you", "who are you?"}:
            return self._identity_response(selection), "passed", []
        if "say github" in lower:
            return "GitHub.", "passed", []
        if lane == "github_status":
            return "GitHub status loaded without mutation.", "passed", []
        if lane == "github_create_repo":
            if "proof" in lower or "x8-git-proof" in lower:
                return "GitHub proof lab approval is ready. No GitHub operation has run. Use the Approve or Deny popup to continue.", "passed", []
            return "GitHub repo creation requires approval before any write.", "passed", []
        if lane == "github_push":
            return "Push preview loaded. No push occurred.", "passed", []
        if lane == "github_pull":
            return "Pull preview loaded. No pull occurred.", "passed", []
        if lane == "github_connect_init":
            return "GitHub repository setup requires approval before any write.", "passed", []
        if lane == "self_build":
            return "Self-build prompt detected. Patch proposal requires approval before apply.", "passed", []
        if ("github" in lower and any(word in lower for word in ("access", "can you", "available", "status"))) or lower in {"github", "github?"}:
            return ("XV8 has GitHub Ops routes for status, previews, and approval-gated writes. "
                    "I should not claim GitHub is inaccessible; write operations still require explicit approval."), "passed", []
        if lane == "attachment_question":
            if bundle.attachments:
                return "I can access the uploaded attachment text included in this turn:\n" + "\n".join(f"- {item}" for item in bundle.attachments), "passed", []
            return "An attachment was referenced, but no extracted attachment text is available in this turn.", "passed", bundle.limitations
        return None

    def _identity_response(self, selection=None) -> str:
        model = getattr(selection, "selected_model", "") or os.getenv("OPENWEBUI_MODEL") or os.getenv("X8_DEFAULT_CHAT_MODEL") or "the selected local model"
        provider = (os.getenv("X8_CHAT_PROVIDER") or os.getenv("X8_MODEL_PROVIDER") or "").strip().lower()
        mode = (os.getenv("X8_OLLAMA_MODE") or os.getenv("X8_MODEL_MODE") or "").strip().lower()
        base_url = (os.getenv("OPENWEBUI_BASE_URL") or os.getenv("X8_OPEN_WEBUI_BASE_URL") or os.getenv("X8_OPENWEBUI_BASE_URL") or "").rstrip("/")
        if provider in {"openwebui", "owui", "brainbridge"} or "openwebui" in mode or base_url:
            return (
                "My name is Xoduz, pronounced Exodus. I am the XV8 local assistant. "
                f"This runtime is configured to route chat through X8 to OpenWebUI at /api/chat/completions, using {model} on the Ollama backend."
            )
        return f"My name is Xoduz, pronounced Exodus. I am the XV8 local assistant using {model}."

    def _brain_command_result(self, request: KernelRequest, lane: str):
        if lane == "brain_continuity" or not lane.startswith("brain_") or not self.brain_manager:
            return None
        return self.brain_manager.handle_chat_command(request.user_message, session_id=request.session_id or "")

    def _continuity_command_result(self, request: KernelRequest, lane: str):
        if lane != "brain_continuity" or not self.continuity_manager:
            return None
        return self.continuity_manager.handle_chat_command(request.user_message, session_id=request.session_id or "")

    def _x8_memory_capture_allowed(self, lane: str) -> bool:
        if lane.startswith("brain_"):
            return False
        return lane not in AUTO_CAPTURE_BLOCKED_LANES

    def _cards(self, lane: str, status: str, limitations: list[str], request: KernelRequest) -> list[ResponseCard]:
        cards: list[ResponseCard] = []
        if limitations:
            unavailable = status == "unavailable"
            cards.append(ResponseCard(
                type="info",
                title="Bridge failure" if unavailable else "Kernel limitations",
                status=status,
                summary=limitations[0] if unavailable else "Some context or model capabilities were unavailable.",
                payload={"limitations": limitations},
            ))
        if lane == "github_status":
            cards.append(ResponseCard(type="receipt", title="GitHub Ops status", status="ready", summary="Local git and GitHub auth status should be loaded through GitHub Ops without mutation.", payload={"provider": "github_ops", "operation": "status", "read_only": True, "github_write_ran": False}))
        if lane == "github_create_repo":
            repo = self._parse_github_repo_request(request.user_message)
            cards.append(ResponseCard(type="approval", title="GitHub create-repo", status="pending_click", summary="GitHub create-repo requires explicit approval. No GitHub write has run.", payload={"provider": "github_ops", "operation": "create-repo", "repo_name": repo["repo_name"], "owner": repo["owner"], "visibility": repo["visibility"], "approval_required": True, "apply_safe": True, "github_write_ran": False, "local_repo_mutation": False, "code_push": False}))
        if lane == "github_push":
            cards.append(ResponseCard(type="receipt", title="GitHub push preview", status="preview", summary="Push preview loaded without pushing.", payload={"provider": "github_ops", "operation": "push-preview", "github_write_ran": False}))
            cards.append(ResponseCard(type="approval", title="Push this repo", status="pending_click", summary="Push this repo requires explicit approval. No GitHub write has run.", payload={"provider": "github_ops", "operation": "push", "approval_required": True, "apply_safe": True, "github_write_ran": False, "local_repo_mutation": False, "code_push": False}))
        if lane == "github_pull":
            cards.append(ResponseCard(type="receipt", title="GitHub pull preview", status="preview", summary="Pull preview loaded without pulling.", payload={"provider": "github_ops", "operation": "pull-preview", "github_write_ran": False}))
            cards.append(ResponseCard(type="approval", title="Pull latest", status="pending_click", summary="Pull latest requires explicit approval. No GitHub write has run.", payload={"provider": "github_ops", "operation": "pull", "approval_required": True, "apply_safe": True, "github_write_ran": False, "local_repo_mutation": False, "code_push": False}))
        if lane == "github_connect_init":
            cards.append(ResponseCard(type="approval", title="GitHub repository setup", status="pending_click", summary="Repository init/connect requires explicit approval. No write has run.", payload={"provider": "github_ops", "operation": "connect-or-init", "approval_required": True, "apply_safe": True, "github_write_ran": False, "local_repo_mutation": False, "code_push": False}))
        if lane == "self_build":
            cards.append(ResponseCard(type="receipt", title="Self-build prompt detected", status="planned", summary="Self-build is routed before GitHub Ops. No files changed.", payload={"provider": "self_build", "operation": "proposal", "approval_required": True, "local_repo_mutation": False, "code_push": False}))
            cards.append(ResponseCard(type="approval", title="Self-build patch proposal", status="pending_click", summary="Self-build patch proposal requires exact approval before apply.", payload={"provider": "self_build", "operation": "proposal", "approval_required": True, "apply_safe": False, "local_repo_mutation": False, "code_push": False}))
        if lane == "brain_retrieve":
            cards.append(ResponseCard(type="receipt", title="Memory used", status=status, summary="Retrieved saved Brain memory without dumping raw records.", payload={"provider": "brain", "lane": lane, "auto_capture": False}))
        elif lane.startswith("brain_"):
            cards.append(ResponseCard(type="receipt", title="Brain memory", status=status, summary="Explicit Brain command handled without model fallback.", payload={"provider": "brain", "lane": lane, "auto_capture": False}))
        if lane in {"web_search", "image_generation", "repo_inspection", "approval_required_action"}:
            cards.append(ResponseCard(type="status", title=f"Kernel lane: {lane}", status=status, summary="The kernel selected a tool-capable lane; tool execution remains routed through approved managers."))
        return cards

    def _parse_github_repo_request(self, message: str) -> dict[str, str]:
        quoted = re.search(r"[`'\"]([^`'\"]+)[`'\"]", message)
        named = re.search(r"\bnamed\s+([A-Za-z0-9_.-]+)", message, flags=re.IGNORECASE)
        owner = re.search(r"\b(?:owner|under)\s+([A-Za-z0-9_.-]+)", message, flags=re.IGNORECASE)
        repo_name = (quoted.group(1) if quoted else named.group(1) if named else "xv8-lab-repo").strip()
        visibility = "public" if re.search(r"\bpublic\b", message, flags=re.IGNORECASE) else "private"
        return {"repo_name": repo_name, "owner": owner.group(1) if owner else "", "visibility": visibility}

    def _is_github_proof_request(self, message: str, repo_name: str) -> bool:
        lower = message.lower()
        return repo_name.startswith("x8-git-proof") or ("github" in lower and "proof" in lower and ("push" in lower or "pull" in lower or "repo" in lower))
