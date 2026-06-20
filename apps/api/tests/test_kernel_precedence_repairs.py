from x8.kernel.response_planner import ResponsePlanner


def test_kernel_routes_github_publish_before_artifact_or_code() -> None:
    planner = ResponsePlanner()
    assert planner.classify("publish this website to GitHub") == "github_push"
    assert planner.classify("push to GitHub after preview") == "github_push"
    assert planner.classify("check GitHub status for this repo") == "github_status"
    assert planner.classify("create a self-build proposal to fix GitHub push") == "self_build"
