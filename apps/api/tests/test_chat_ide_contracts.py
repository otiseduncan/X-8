import subprocess

from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.managers.chat_ide_manager import ChatIDEManager
from x8.settings import Settings


def client(root) -> TestClient:
    settings = Settings(workspace_root=str(root), knowledge_root="/app/knowledge", x7_import_root="/missing/x7", x6_import_root="/missing/x6")
    return TestClient(create_app(settings))


def make_repo(root) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "x8@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "X8 Test"], cwd=root, check=True)
    (root / "README.md").write_text("# X8\n", encoding="utf-8")
    (root / "apps").mkdir()
    (root / "apps" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md", "apps/App.tsx"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=root, check=True, capture_output=True, text=True)


def test_ide_summary_lists_workspace_git_permissions_and_activity(tmp_path) -> None:
    make_repo(tmp_path)
    payload = client(tmp_path).get("/api/ide/summary").json()
    assert payload["status"] == "ready"
    assert any(item["path"] == "README.md" for item in payload["data"]["files"])
    assert payload["data"]["git_status"]["branch"] in {"main", "master"}
    assert any(item["action"] == "apply_file_edit" and item["approval_required"] for item in payload["data"]["permissions"])
    assert payload["data"]["activity"][0]["action_type"] == "read_workspace"


def test_ide_open_file_blocks_outside_root(tmp_path) -> None:
    make_repo(tmp_path)
    response = client(tmp_path).post("/api/ide/open-file", json={"path": "../outside.txt"})
    assert response.status_code == 400
    assert "outside workspace root" in response.text


def test_command_safety_blocks_dangerous_and_docker_compose_config(tmp_path) -> None:
    manager = ChatIDEManager(str(tmp_path))
    for command in ["rm -rf .", "docker compose config", "git push --force origin main", "cat .env", "Remove-Item .git -Recurse -Force"]:
        proposal = manager.propose_command(command)
        assert proposal.blocked is True
        assert proposal.allowed is False


def test_test_command_proposal_and_readonly_run_allowed(tmp_path) -> None:
    make_repo(tmp_path)
    api = client(tmp_path)
    proposed = api.post("/api/ide/command/propose", json={"command": "docker compose -f compose.yaml run --rm --build web-tests"}).json()
    assert proposed["data"]["category"] == "validation/test"
    assert proposed["data"]["allowed"] is True
    ran = api.post("/api/ide/command/run", json={"command": "git status --short"}).json()
    assert ran["status"] == "passed"
    assert ran["data"]["category"] == "read-only safe"


def test_git_status_and_rollback_are_read_only_or_approval_required(tmp_path) -> None:
    make_repo(tmp_path)
    api = client(tmp_path)
    git_status = api.get("/api/ide/git/status").json()
    assert git_status["status"] == "ready"
    assert "recent_commits" in git_status["data"]
    rollback = api.post("/api/ide/rollback/propose", json={"action": "reset_to_origin_main"}).json()
    assert rollback["status"] == "approval_required"
    assert rollback["data"]["approval_required"] is True
    preview = api.post("/api/ide/rollback/propose", json={"action": "preview_untracked_cleanup"}).json()
    assert preview["data"]["command"] == "git clean -fdn"


def test_no_ci_files_created() -> None:
    from pathlib import Path

    assert not Path(".github/workflows").exists()
