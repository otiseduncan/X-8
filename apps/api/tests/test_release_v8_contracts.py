from pathlib import Path

from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.kernel.response_planner import ResponsePlanner
from x8.settings import Settings


ADAS_PROMPT = """X, build a real project using your V8 Project Builder.

Project name:
ADAS Workflow Command Center

Goal:
Create a small, polished local web app that helps manage ADAS calibration workflow across multiple body shops. This is a functional proof project, not just a toy demo.

Build requirements:

* Create a responsive dark-theme dashboard.
* Use a black/dark gray background with red/cyan accent highlights.
* Include a top header with project name and status summary.
* Include shop cards for Macon, Perry, and Warner Robins.
* Include job status columns:

  * Pending Review
  * Submitted OK
  * In Progress
  * Hold
  * Complete
* Include sample RO/job cards with:

  * RO number
  * vehicle year/make/model
  * VIN placeholder
  * insurance
  * required calibrations
  * due date
  * status
  * notes
* Include simple projected revenue and completed-count summary cards.
* Include a filter/search bar.
* Include a Create New Job form section with fields:

  * shop
  * RO number
  * VIN
  * vehicle
  * insurance
  * calibration type
  * due date
  * notes
* The form can be frontend-only for now, but the UI should look production-ready.
* Include clear empty-state and hold-warning styling.
* Include a README explaining how to run or open the project.

Technical requirements:

* Generate plain runnable frontend files unless your Project Builder supports a better scaffold.
* Include at minimum:

  * README.md
  * manifest.json
  * index.html
  * src or app files if needed
  * CSS/styles file
* Keep files clean and modular.
* No external paid APIs.
* No secrets.
* No Git commit.
* No push.
* No writes outside the approved sandbox path.

Approval:
I approve writing this generated project only inside the configured V8 sandbox/project output path. Use the project folder name:
adas-workflow-command-center

After writing:

* Verify the files exist.
* Return the exact output path.
* Return the file list.
* Return the manifest summary.
* Tell me how to open or run it locally.
* If anything is unavailable, report it honestly and do not fake success.

Final response format:

1. Build result
2. Output path
3. Files created
4. How to run/open
5. Any warnings or blocked items"""


def client(settings: Settings | None = None) -> TestClient:
    if settings is None:
        settings = Settings(knowledge_root="/app/knowledge", x7_import_root="/missing/x7", x6_import_root="/missing/x6")
        settings.ollama_base_url = "http://127.0.0.1:9"
        settings.default_chat_model = ""
        settings.fallback_chat_model = ""
        settings.code_model = ""
        settings.reasoning_model = ""
    return TestClient(create_app(settings))


def test_integrations_report_rich_non_fake_status() -> None:
    payload = client().get("/api/integrations").json()
    by_name = {item["name"]: item for item in payload["data"]}
    required = {"docker", "github", "ollama", "local_bridge", "searxng", "comfyui", "browser", "filesystem", "speech_tts", "memory_database", "self_build_operator"}
    assert required <= set(by_name)
    assert by_name["searxng"]["live"] is False
    assert by_name["comfyui"]["live"] is False
    assert by_name["self_build_operator"]["status"] == "implemented"
    for item in by_name.values():
        assert "safe_actions" in item
        assert "blocked_actions" in item
        assert item["receipt"]["action"] == "integration.status"


def test_operator_blocks_arbitrary_shell_and_gates_commit_push() -> None:
    api = client()
    shell = api.post("/api/operator/tasks", json={"prompt": "run shell rm -rf runtime", "action_type": "inspect"}).json()
    push = api.post("/api/operator/tasks", json={"prompt": "git push origin main", "action_type": "inspect"}).json()
    assert shell["data"]["task"]["status"] == "blocked"
    assert shell["data"]["task"]["actions"][0]["action_type"] == "arbitrary_shell"
    assert shell["data"]["approvals"]
    assert push["data"]["task"]["actions"][0]["action_type"] == "git_push"
    assert push["data"]["task"]["actions"][0]["requires_approval"] is True
    assert push["data"]["results"] == []


def test_chat_operator_boundary_does_not_claim_remote_control() -> None:
    payload = client().post("/api/chat", json={"message": "run powershell and then remote control my browser"}).json()
    content = payload["data"]["assistant_message"]["content"]
    card = payload["data"]["assistant_message"]["cards"][0]
    assert payload["status"] == "blocked"
    assert "cannot run arbitrary shell" in content
    assert card["payload"]["arbitrary_shell"] is False
    assert card["payload"]["remote_control"] is False


def test_project_builder_preview_then_approved_sandbox_write(tmp_path: Path) -> None:
    settings = Settings(
        workspace_root=str(tmp_path),
        project_builder_sandbox_path=str(tmp_path / "runtime" / "generated-projects"),
        knowledge_root="/app/knowledge",
        x7_import_root="/missing/x7",
        x6_import_root="/missing/x6",
    )
    api = client(settings)
    preview = api.post("/api/project-builder/preview", json={"prompt": "build a tiny dashboard", "project_name": "v8-release-proof-project"}).json()
    plan = preview["data"]["plan"]
    denied = api.post("/api/project-builder/write", json={"prompt": "build a tiny dashboard", "project_name": "v8-release-proof-project", "manifest_hash": plan["manifest_hash"], "approved": False}).json()
    written = api.post("/api/project-builder/write", json={"prompt": "build a tiny dashboard", "project_name": "v8-release-proof-project", "manifest_hash": plan["manifest_hash"], "approved": True}).json()
    assert preview["status"] == "preview"
    assert denied["status"] == "blocked"
    assert written["status"] == "written"
    output = Path(written["data"]["plan"]["output_path"])
    assert output.is_relative_to(tmp_path / "runtime" / "generated-projects")
    assert (output / "manifest.json").exists()
    assert (output / "README.md").exists()
    assert (output / "index.html").exists()


def test_project_builder_routing_precedence_beats_readme_mentions() -> None:
    planner = ResponsePlanner()
    assert planner.classify("open README.md") == "repo_inspection"
    assert planner.classify(ADAS_PROMPT) == "project_builder"


def test_exact_adas_prompt_chat_routes_to_project_builder_and_writes_sandbox(tmp_path: Path) -> None:
    settings = Settings(
        workspace_root=str(tmp_path),
        project_builder_sandbox_path=str(tmp_path / "runtime" / "generated-projects"),
        knowledge_root="/app/knowledge",
        x7_import_root="/missing/x7",
        x6_import_root="/missing/x6",
    )
    settings.ollama_base_url = "http://127.0.0.1:9"
    settings.default_chat_model = ""
    settings.fallback_chat_model = ""
    settings.code_model = ""
    settings.reasoning_model = ""
    payload = client(settings).post("/api/chat", json={"message": ADAS_PROMPT}).json()
    content = payload["data"]["assistant_message"]["content"]
    cards = payload["data"]["assistant_message"]["cards"]
    output = tmp_path / "runtime" / "generated-projects" / "adas-workflow-command-center"
    assert payload["status"] == "passed"
    assert "Project Builder wrote the approved generated project" in content
    assert str(output) in content
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "project_builder"
    assert cards[0]["title"] == "Project Builder result"
    assert cards[0]["payload"]["output_path"] == str(output)
    for path in ["manifest.json", "README.md", "index.html", "src/main.js", "src/styles.css"]:
        assert (output / path).exists()
    manifest = (output / "manifest.json").read_text(encoding="utf-8")
    html = (output / "index.html").read_text(encoding="utf-8")
    css = (output / "src" / "styles.css").read_text(encoding="utf-8")
    readme = (output / "README.md").read_text(encoding="utf-8")
    assert '"template": "adas_workflow_command_center"' in manifest
    assert "Macon" in html and "Perry" in html and "Warner Robins" in html
    assert "Pending Review" in html and "Submitted OK" in html and "In Progress" in html and "Hold" in html and "Complete" in html
    assert "#050607" in css and "#ff384d" in css and "#20e5ff" in css
    assert "Open `index.html`" in readme
    assert not (tmp_path / "adas-workflow-command-center").exists()


def test_project_builder_hash_mismatch_blocks_write(tmp_path: Path) -> None:
    settings = Settings(workspace_root=str(tmp_path), project_builder_sandbox_path=str(tmp_path / "runtime" / "generated-projects"), knowledge_root="/app/knowledge", x7_import_root="/missing/x7", x6_import_root="/missing/x6")
    payload = client(settings).post("/api/project-builder/write", json={"prompt": "build", "project_name": "bad-hash", "manifest_hash": "wrong", "approved": True}).json()
    assert payload["status"] == "blocked"
    assert "manifest_hash" in payload["message"]
