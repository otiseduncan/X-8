from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings


def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_github_ops_create_repo_422_reports_sanitized_details(tmp_path, monkeypatch) -> None:
    class FakeResponse:
        status_code = 422

        def json(self):
            return {
                "message": "Repository creation failed.",
                "errors": [{"resource": "Repository", "field": "name", "code": "custom", "message": "name already exists on this account"}],
                "documentation_url": "https://docs.github.com/rest/repos/repos#create-a-repository-for-the-authenticated-user",
            }

    def fake_post(url, headers, json, timeout):
        return FakeResponse()

    monkeypatch.setattr("x8.managers.github_ops_manager.httpx.post", fake_post)
    settings = Settings(workspace_root=str(tmp_path), knowledge_root="/app/knowledge")
    settings.github_token = "ghp_secret_test"
    settings.github_owner = "otis"
    api = client(settings)

    payload = api.post("/api/github/ops/create-repo", json={"repo_name": "xv8-lab", "visibility": "private", "approved": True}).json()

    assert payload["status"] == "blocked"
    assert payload["data"]["github_status_code"] == 422
    assert payload["data"]["github_message"] == "Repository creation failed."
    assert payload["data"]["validation_errors"][0]["field"] == "name"
    assert payload["data"]["documentation_url"].startswith("https://docs.github.com/")
    assert payload["data"]["likely_repo_already_exists"] is True
    assert "likely already exists" in payload["message"]
    assert "ghp_secret_test" not in str(payload)
    assert "Authorization" not in str(payload)
