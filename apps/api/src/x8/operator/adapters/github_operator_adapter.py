class GitHubOperatorAdapter:
    name = "github_operator"

    def status(self) -> dict[str, object]:
        return {"status": "not_configured", "reason": "External repository writes require credentials and approval."}
