from x8.kernel.response_planner import ResponsePlanner


def test_conversation_repair_routes_to_self_build() -> None:
    planner = ResponsePlanner()
    assert planner.classify("fix conversation") == "self_build"
    assert planner.classify("language issues") == "self_build"
    assert planner.classify("expand the system prompt") == "self_build"
    assert planner.classify("fixing X where it can communicate correctly with me") == "self_build"
    assert planner.classify("correct the conversational aspect and let me know when it is ready to pull") == "self_build"


def test_repo_review_routes_to_inspection() -> None:
    planner = ResponsePlanner()
    assert planner.classify("examine the repo") == "repo_inspection"
    assert planner.classify("production ready") == "repo_inspection"
    assert planner.classify("ready to pull") == "github_pull"
