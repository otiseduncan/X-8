from x8.kernel.response_planner import ResponsePlanner


ADAS_PROJECT_PROMPT = """
X, build a real project using your V8 Project Builder.

Project name:
ADAS Workflow Command Center

Technical requirements:
- Generate plain runnable frontend files unless your Project Builder supports a better scaffold.
- Include at minimum:
  - README.md
  - manifest.json
  - index.html
  - src or app files if needed
  - CSS/styles file

Approval:
I approve writing this generated project only inside the configured V8 sandbox/project output path.
Use the project folder name:
adas-workflow-command-center.

After writing:
- Verify the files exist.
- Return the exact output path.
- Return the file list.
"""


def test_project_builder_beats_readme_output_mentions():
    planner = ResponsePlanner()
    assert planner.classify(ADAS_PROJECT_PROMPT) == "project_builder"


def test_project_builder_beats_generated_file_requirements():
    planner = ResponsePlanner()
    prompt = "Build a project that includes README.md, manifest.json, index.html, CSS, and write it to the approved sandbox."
    assert planner.classify(prompt) == "project_builder"


def test_explicit_readme_open_still_routes_to_repo_inspection():
    planner = ResponsePlanner()
    assert planner.classify("Open README.md") == "repo_inspection"


def test_preview_only_does_not_route_to_project_builder():
    planner = ResponsePlanner()
    route = planner.classify("Generate a website preview only. Do not write files.")
    assert route != "project_builder"
