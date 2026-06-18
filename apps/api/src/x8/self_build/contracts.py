from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

SELF_BUILD_CONTRACT_VERSION = "self-build.v1"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class SelfBuildMode(StrEnum):
    PLAN_ONLY = "plan_only"
    PATCH_PROPOSAL = "patch_proposal"
    APPLY_AFTER_APPROVAL = "apply_after_approval"
    TEST_AFTER_APPLY = "test_after_apply"
    COMMIT_AFTER_APPROVAL = "commit_after_approval"


class SelfBuildBase(BaseModel):
    contract_version: str = SELF_BUILD_CONTRACT_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "created"
    limitations: list[str] = Field(default_factory=list)


class SelfBuildRequest(SelfBuildBase):
    request_id: str = Field(default_factory=lambda: _id("sbr"))
    session_id: str | None = None
    user_prompt: str
    mode: SelfBuildMode = SelfBuildMode.PATCH_PROPOSAL
    allowed_paths: list[str] = Field(default_factory=list)
    blocked_paths: list[str] = Field(default_factory=list)
    approval_required: bool = True
    commit_allowed: bool = False
    push_allowed: bool = False
    test_presets: list[str] = Field(default_factory=list)


class SelfBuildPlanStep(SelfBuildBase):
    step_id: str = Field(default_factory=lambda: _id("sbstep"))
    title: str
    summary: str


class RepoContextSnapshot(SelfBuildBase):
    snapshot_id: str = Field(default_factory=lambda: _id("ctx"))
    files_listed: list[str] = Field(default_factory=list)
    files_read: list[str] = Field(default_factory=list)
    git_status: str = ""
    git_diff_summary: str = ""


class FileReadRequest(BaseModel):
    path: str


class FileReadResult(SelfBuildBase):
    path: str
    content: str = ""
    size_bytes: int = 0
    blocked: bool = False


class SelfBuildPlan(SelfBuildBase):
    plan_id: str = Field(default_factory=lambda: _id("plan"))
    summary: str
    target_files: list[str] = Field(default_factory=list)
    new_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    risk_level: str = "normal_mutation"
    approval_required: bool = True
    tests_to_run: list[str] = Field(default_factory=list)
    rollback_plan: str = ""
    known_limitations: list[str] = Field(default_factory=list)
    steps: list[SelfBuildPlanStep] = Field(default_factory=list)


class PatchFileChange(SelfBuildBase):
    file_path: str
    change_type: str = "modify"
    before_summary: str = ""
    after_summary: str = ""
    before_hash: str = ""
    after_hash: str = ""
    proposed_content: str = ""
    unified_diff: str = ""
    risk_level: str = "normal_mutation"


class PatchValidationResult(SelfBuildBase):
    validation_id: str = Field(default_factory=lambda: _id("val"))
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class PatchProposal(SelfBuildBase):
    patch_id: str = Field(default_factory=lambda: _id("patch"))
    task_id: str
    plan_id: str
    changes: list[PatchFileChange] = Field(default_factory=list)
    patch_hash: str
    validation: PatchValidationResult
    approval_id: str = ""


class PatchApplyRequest(BaseModel):
    patch_id: str
    approval_id: str
    patch_hash: str
    approved: bool = False


class PatchApplyResult(SelfBuildBase):
    apply_id: str = Field(default_factory=lambda: _id("apply"))
    patch_id: str
    applied: bool = False
    reverted: bool = False
    validation_passed: bool = False
    changed_files: list[str] = Field(default_factory=list)
    backup_paths: list[str] = Field(default_factory=list)
    reason: str = ""


class SelfBuildTestRun(SelfBuildBase):
    test_run_id: str = Field(default_factory=lambda: _id("test"))
    preset: str
    ran: bool = False
    passed: bool = False
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    output_summary: str = ""


class SelfBuildValidationReport(SelfBuildBase):
    report_id: str = Field(default_factory=lambda: _id("vrep"))
    task_id: str
    patch_id: str = ""
    patch_hash: str = ""
    validation_passed: bool = False
    validation_runs: list[SelfBuildTestRun] = Field(default_factory=list)
    failure_reason: str = ""


class SelfBuildReceipt(SelfBuildBase):
    receipt_id: str = Field(default_factory=lambda: _id("rcpt"))
    action_type: str
    request_id: str = ""
    task_id: str = ""
    patch_id: str = ""
    approval_id: str = ""
    files_read: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    selected_model: str = ""
    fallback_used: bool = False
    timed_out: bool = False
    timeout_seconds: float = 0.0
    failure_reason: str = ""
    patch_hash: str = ""
    validation_passed: bool = False
    applied: bool = False
    reverted: bool = False


class SelfBuildTask(SelfBuildBase):
    task_id: str = Field(default_factory=lambda: _id("task"))
    request: SelfBuildRequest
    goal: str = ""
    constraints: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    required_tests: list[str] = Field(default_factory=list)
    completion_rule: str = ""
    commit_instruction: str = "do_not_commit"
    risk_level: str = "normal_mutation"
    context: RepoContextSnapshot | None = None
    plan: SelfBuildPlan | None = None
    proposal: PatchProposal | None = None
    receipts: list[SelfBuildReceipt] = Field(default_factory=list)
    validation_reports: list[SelfBuildValidationReport] = Field(default_factory=list)
