import subprocess

import pytest

from x8.managers.github_ops_manager import GitHubOpsManager


def make_git_repo(root) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "x8@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "X8 Test"], cwd=root, check=True)
    (root / "README.md").write_text("# X8\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=root, check=True, capture_output=True, text=True)


def test_github_ops_rejects_host_and_absolute_paths(tmp_path) -> None:
    manager = GitHubOpsManager(str(tmp_path))
    for path in ["X:/project", "C:/Users/Public", "/workspace", "//server/share"]:
        with pytest.raises(ValueError, match="workspace-relative"):
            manager.local_status(path)


def test_github_ops_push_preview_without_remote_is_read_only_and_not_allowed(tmp_path) -> None:
    make_git_repo(tmp_path)
    manager = GitHubOpsManager(str(tmp_path))
    preview = manager.push_preview(".")
    assert preview["remote"] == ""
    assert preview["commits_to_push"] == []
    assert preview["allowed_after_approval"] is False
