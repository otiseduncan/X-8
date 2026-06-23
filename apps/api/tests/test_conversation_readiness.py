from x8.kernel.response_planner import ResponsePlanner


def test_conversation_repair_routes_to_self_build() -> None:
    planner = ResponsePlanner()
    assert planner.classify("fix conversation") == "self_build"
    assert planner.classify("language issues") == "self_build"
    assert planner.classify("expand the system prompt") == "self_build"


def test_repo_review_routes_to_inspection() -> None:
    planner = ResponsePlanner()
    assert planner.classify("examine the repo") == "repo_inspection"
    assert planner.classify("production ready") == "repo_inspection"
    assert planner.classify("ready to pull") == "github_pull"
