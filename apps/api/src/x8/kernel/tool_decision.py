from x8.kernel.contracts import ArtifactIntent, ToolIntent


class ToolDecisionEngine:
    def decide(self, lane: str) -> tuple[ToolIntent | None, ArtifactIntent | None]:
        if lane == "web_search":
            return ToolIntent(name="search.searxng"), None
        if lane == "image_generation":
            return ToolIntent(name="image.comfyui"), ArtifactIntent(kind="image", title="Image generation")
        if lane == "repo_inspection":
            return ToolIntent(name="workspace.read", parameters={"read_only": True}), None
        if lane == "approval_required_action":
            return ToolIntent(name="repo.write", requires_approval=True), ArtifactIntent(kind="approval", title="Approval required")
        return None, None
