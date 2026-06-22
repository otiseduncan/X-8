import difflib

from pydantic import BaseModel

from x8.contracts.approvals import ActionIntent, ApprovalRequest, RiskLevel, RollbackHint
from x8.contracts.receipts import Receipt
from x8.managers.approval_manager import ApprovalManager, approval_modal_manager
from x8.managers.workspace_manager import WorkspaceManager


class PatchProposal(BaseModel):
    path: str
    proposed_content: str
    diff: str
    before_line_count: int
    after_line_count: int
    mutated: bool = False
    approval: ApprovalRequest | None = None
    receipt: Receipt


class SafeRepoWriterManager:
    name = "safe_repo_writer"
    version = "0.2.1"

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace

    def propose_update(self, path: str, proposed_content: str) -> PatchProposal:
        try:
            current = self.workspace.read_file(path).content
            fromfile = f"a/{path}"
        except FileNotFoundError:
            current = ""
            fromfile = "/dev/null"
        diff = "\n".join(
            difflib.unified_diff(
                current.splitlines(),
                proposed_content.splitlines(),
                fromfile=fromfile,
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        receipt = Receipt(action="repo.propose_update", status="proposed", summary="Diff proposal created without writing.")
        return PatchProposal(
            path=path,
            proposed_content=proposed_content,
            diff=diff,
            before_line_count=len(current.splitlines()),
            after_line_count=len(proposed_content.splitlines()),
            receipt=receipt,
        )

    def apply_update(self, path: str, proposed_content: str, approved: bool) -> PatchProposal:
        proposal = self.propose_update(path, proposed_content)
        if not approved:
            approval = ApprovalManager().request(
                action="repo.apply_patch",
                risk=RiskLevel.MEDIUM_CHANGE,
                intent=ActionIntent(
                    action="apply patch",
                    files_affected=[path],
                    summary=f"Apply proposed edit to {path}.",
                    will_change_files=True,
                    before_after_summary=f"{proposal.before_line_count} lines -> {proposal.after_line_count} lines",
                    tests_recommended=["architecture_guard", "api_tests"],
                ),
                rollback_hint=RollbackHint(summary=f"Revert {path} from git or restore the previous content."),
                reason="Normal source edit requires click approval.",
            )
            proposal.approval = approval_modal_manager.queue(approval)
            proposal.receipt.status = "blocked"
            proposal.receipt.summary = "Write queued for click approval; no files were changed."
            return proposal
        self.workspace.write_file(path, proposed_content, overwrite=True)
        proposal.mutated = True
        proposal.receipt.status = "applied"
        proposal.receipt.summary = "Approved update written inside workspace root."
        return proposal
