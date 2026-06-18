class ResponsePlanner:
    LANES = {
        "self_build": ("self-build", "self build", "self-build proposal", "repair loop"),
        "github_create_repo": ("create-repo", "create repo", "create github repo", "new github repository", "private disposable repo"),
        "github_connect_init": ("connect this repo", "connect remote", "initialize this as a repo", "init repo"),
        "github_push": ("push this repo", "prepare to push", "git push"),
        "github_pull": ("pull latest", "git pull"),
        "github_status": ("check github status", "github status", "github ops status"),
        "image_generation": ("image", "generate picture", "generate image"),
        "web_search": ("search", "searxng", "web research"),
        "repo_inspection": ("open readme", "read file", "show file"),
        "approval_required_action": ("edit file", "apply patch", "delete"),
        "attachment_question": ("attachment", "attached", "use this"),
        "model_status_request": ("what model", "model status", "using"),
        "reasoning": ("reason through", "deep plan", "think deeply", "architecture plan"),
        "code_help": ("code", "function", "bug", "python", "typescript"),
        "prompt_generation": ("write a prompt", "prompt for"),
        "settings_request": ("settings", "configure"),
    }

    def classify(self, message: str, has_attachments: bool = False) -> str:
        lower = message.lower()
        if has_attachments:
            return "attachment_question"
        if "say github" in lower:
            return "normal_chat"
        for lane, needles in self.LANES.items():
            if any(needle in lower for needle in needles):
                return lane
        return "normal_chat"
