class ResponsePlanner:
    LANES = {
        "image_generation": ("image", "generate picture", "generate image"),
        "web_search": ("search", "searxng", "web research"),
        "repo_inspection": ("open readme", "read file", "show file"),
        "approval_required_action": ("edit file", "apply patch", "delete", "git push"),
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
        for lane, needles in self.LANES.items():
            if any(needle in lower for needle in needles):
                return lane
        return "normal_chat"
