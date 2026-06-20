from x8.kernel.contracts import ArtifactIntent, ToolIntent


class ToolDecisionEngine:
    def decide(self, lane: str) -> tuple[ToolIntent | None, ArtifactIntent | None]:
        if lane == "web_search":
            return ToolIntent(name="search.searxng"), None
        if lane == "image_generation":
            return ToolIntent(name="image.comfyui"), ArtifactIntent(kind="image", title="Image generation")
        if lane == "artifact_preview":
            return ToolIntent(name="artifact.preview", parameters={"mutates_repo": False}), ArtifactIntent(kind="html", title="Website preview")
        if lane == "repo_inspection":
            return ToolIntent(name="workspace.read", parameters={"read_only": True}), None
        if lane == "github_status":
            return ToolIntent(name="github.ops.status", parameters={"read_only": True}), None
        if lane == "github_create_repo":
            return ToolIntent(name="github.ops.create_repo", requires_approval=True), ArtifactIntent(kind="approval", title="GitHub create-repo approval")
        if lane == "github_connect_init":
            return ToolIntent(name="github.ops.connect_or_init", requires_approval=True), ArtifactIntent(kind="approval", title="GitHub repository approval")
        if lane == "github_push":
            return ToolIntent(name="github.ops.push", requires_approval=True), ArtifactIntent(kind="approval", title="GitHub push approval")
        if lane == "github_pull":
            return ToolIntent(name="github.ops.pull", requires_approval=True), ArtifactIntent(kind="approval", title="GitHub pull approval")
        if lane == "self_build":
            return ToolIntent(name="self_build.proposal", requires_approval=True), ArtifactIntent(kind="approval", title="Self-build patch proposal")
        if lane == "project_builder":
            return ToolIntent(name="project_builder.write_sandbox", requires_approval=True), ArtifactIntent(kind="project", title="Project Builder result")
        if lane == "approval_required_action":
            return ToolIntent(name="repo.write", requires_approval=True), ArtifactIntent(kind="approval", title="Approval required")
        return None, None
