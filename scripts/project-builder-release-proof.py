#!/usr/bin/env python
import json
import os
from pathlib import Path

from x8.project_builder.contracts import ProjectBuilderRequest
from x8.project_builder.manager import ProjectBuilderManager

ADAS_PROMPT = """X, build a real project using your V8 Project Builder.

Project name:
ADAS Workflow Command Center

Build requirements:
Create a responsive dark-theme dashboard with red/cyan accents, shop cards for Macon, Perry, and Warner Robins, job status columns, sample RO/job cards, projected revenue summaries, search/filter controls, a Create New Job form, empty-state styling, hold-warning styling, README.md, manifest.json, index.html, app files, and CSS/styles.

Approval:
I approve writing this generated project only inside the configured V8 sandbox/project output path. Use the project folder name:
adas-workflow-command-center"""


def main() -> int:
    workspace = os.environ.get("X8_WORKSPACE_ROOT", "/workspace")
    sandbox = os.environ.get("X8_PROJECT_BUILDER_SANDBOX_PATH", str(Path(workspace) / "runtime" / "generated-projects"))
    manager = ProjectBuilderManager(workspace, sandbox)
    request = ProjectBuilderRequest(prompt=ADAS_PROMPT, project_name="adas-workflow-command-center")
    preview = manager.preview(request)
    write = manager.write(
        ProjectBuilderRequest(
            prompt=request.prompt,
            project_name=request.project_name,
            approved=True,
            manifest_hash=preview.plan.manifest_hash,
            sandbox_path=sandbox,
        )
    )
    output = Path(write.plan.output_path)
    required = ["manifest.json", "README.md", "index.html", "src/main.js", "src/styles.css"]
    missing = [item for item in required if not (output / item).exists()]
    html = (output / "index.html").read_text(encoding="utf-8") if (output / "index.html").exists() else ""
    css = (output / "src" / "styles.css").read_text(encoding="utf-8") if (output / "src" / "styles.css").exists() else ""
    markers = ["ADAS Workflow Command Center", "Macon", "Perry", "Warner Robins", "Pending Review", "Submitted OK", "In Progress", "Hold", "Complete"]
    missing_markers = [item for item in markers if item not in html]
    missing_css_markers = [item for item in ["#050607", "#ff384d", "#20e5ff"] if item not in css]
    report = {
        "status": write.status,
        "output_path": str(output),
        "manifest_hash": write.plan.manifest_hash,
        "files": required,
        "missing": missing,
        "missing_markers": missing_markers,
        "missing_css_markers": missing_css_markers,
        "receipt": write.receipt,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if write.wrote_files and not missing and not missing_markers and not missing_css_markers else 1


if __name__ == "__main__":
    raise SystemExit(main())
