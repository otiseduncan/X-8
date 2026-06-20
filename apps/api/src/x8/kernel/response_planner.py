class ResponsePlanner:
    LANES = {
        "project_builder": ("v8 project builder", "project builder", "build a real project", "generated project", "project output path"),
        "self_build": ("self-build", "self build", "self-build proposal", "repair loop"),
        "local_system_body": (
            "how many drives",
            "what drives",
            "show my drives",
            "scan my drives",
            "disk space",
            "storage available",
            "local system scan",
            "what hardware do you see",
            "body status",
            "check local system",
            "check my computer",
            "show your body",
            "show body status",
        ),
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
        "web_search": ("search", "searxng", "web research", "browse the web", "search the web", "search online", "look up"),
        "repo_inspection": ("open readme", "read file", "show file"),
        "approval_required_action": ("edit file", "apply patch", "delete"),
        "operator_blocked": ("run shell", "run powershell", "run cmd", "arbitrary shell", "rm -rf", "commit and push", "send sms", "remote control"),
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
        # Priority 1: GitHub and self-build routes beat brain_continuity
        for priority_lane in ("github_status", "github_create_repo", "github_connect_init", "github_push", "github_pull", "self_build"):
            needles = self.LANES.get(priority_lane, ())
            if any(needle in lower for needle in needles):
                return priority_lane
        # Priority 2: Explicit brain write/read commands (remember/forget/retrieve/focus) beat normal LANES
        for brain_lane in ("brain_remember", "brain_forget", "brain_retrieve", "brain_focus_update"):
            needles = self.LANES.get(brain_lane, ())
            if any(needle in lower for needle in needles):
                return brain_lane
        # Priority 3: All remaining LANES in order (brain_continuity included)
        for lane, needles in self.LANES.items():
            if any(needle in lower for needle in needles):
                return lane
        return "normal_chat"

    def _is_project_builder_request(self, lower: str) -> bool:
        build_markers = ("build", "create", "generate", "scaffold", "write")
        project_markers = ("project builder", "real project", "generated project", "project output path", "project folder name")
        generated_file_markers = ("readme.md", "manifest.json", "index.html", "css", "styles", "src", "app files")
        if "self-build" in lower or "self build" in lower:
            return False
        if "preview only" in lower or "do not write files" in lower or "no files" in lower:
            return False
        # Brain commands starting with explicit brain triggers take precedence
        if lower.startswith(("remember that ", "remember this ", "forget that ", "forget this ", "update your focus to ", "what do you remember")):
            return False
        has_build_intent = any(marker in lower for marker in build_markers)
        has_project_intent = any(marker in lower for marker in project_markers)
        generated_file_hits = sum(1 for marker in generated_file_markers if marker in lower)
        # Treat generated file requirement lists as project-builder intent when coupled with explicit build+project wording.
        has_generated_requirements = "project" in lower and generated_file_hits >= 2
        return has_build_intent and (has_project_intent or has_generated_requirements)
