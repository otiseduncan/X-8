class ResponsePlanner:
    LANES = {
        "project_builder": ("v8 project builder", "project builder", "build a real project", "generated project", "project output path"),
        "self_build": ("self-build", "self build", "self-build proposal", "repair loop"),
        "github_create_repo": ("create-repo", "create repo", "create github repo", "create a github repo proposal", "github repo proposal", "new github repository", "private disposable repo"),
        "github_connect_init": ("connect this repo", "connect remote", "initialize this as a repo", "init repo"),
        "github_push": ("push this repo", "prepare to push", "git push"),
        "github_pull": ("pull latest", "git pull"),
        "github_status": ("check github status", "github status", "github ops status"),
        "brain_remember": ("remember that", "remember this"),
        "brain_forget": ("forget that", "forget this"),
        "brain_retrieve": ("what do you remember",),
        "brain_focus_update": ("update your focus to",),
        "brain_continuity": (
            "we are working on",
            "the current project is",
            "the next step is",
            "mark this blocked by",
            "the blocker is",
            "clear the blocker",
            "mark that done",
            "we validated",
            "checkpoint:",
            "commit checkpoint:",
            "decision:",
            "create task",
            "task:",
            "what are we currently working on",
            "what are we working on",
            "what is the next step",
            "what is blocked",
            "what did we validate last",
            "what changed in the last checkpoint",
            "what should we do before continuing",
            "what is the status of x-8",
            "show me the current project state",
            "what did we decide about",
            "what did we decide about the brain",
            "create a handoff note",
        ),
        "image_generation": ("image", "generate picture", "generate image"),
        "artifact_preview": ("website preview", "preview only", "html preview"),
        "web_search": ("search", "searxng", "web research"),
        "repo_inspection": ("open readme", "read file", "show file"),
        "approval_required_action": ("edit file", "apply patch", "delete"),
        "operator_blocked": ("run shell", "run powershell", "run cmd", "arbitrary shell", "rm -rf", "commit and push", "send email", "send sms", "remote control"),
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
        if self._is_project_builder_request(lower):
            return "project_builder"
        if "say github" in lower:
            return "normal_chat"
        for lane, needles in self.LANES.items():
            if any(needle in lower for needle in needles):
                return lane
        return "normal_chat"

    def _is_project_builder_request(self, lower: str) -> bool:
        build_markers = ("build", "create", "generate", "scaffold", "write")
        project_markers = ("project builder", "real project", "generated project", "project output path", "project folder name")
        if "self-build" in lower or "self build" in lower:
            return False
        if "preview only" in lower or "do not write files" in lower or "no files" in lower:
            return False
        return any(marker in lower for marker in build_markers) and any(marker in lower for marker in project_markers)


