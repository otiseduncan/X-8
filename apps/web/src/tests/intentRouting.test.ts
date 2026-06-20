import { describe, expect, it } from 'vitest';
import { classifyRequest, isProjectBuilderRequest } from '../app/intentRouting';

const adasPrompt = `
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
adas-workflow-command-center

After writing:
- Verify the files exist.
- Return the exact output path.
- Return the file list.
`;

describe('intent routing precedence', () => {
  it('routes the ADAS project-builder prompt to Project Builder, not file viewer', () => {
    expect(isProjectBuilderRequest(adasPrompt.toLowerCase())).toBe(true);
    expect(classifyRequest(adasPrompt)).toBe('project_builder');
  });

  it('does not let generated README.md requirements steal project-builder routing', () => {
    const prompt = 'Build a project that includes README.md, manifest.json, index.html, and write it to the approved sandbox.';
    expect(classifyRequest(prompt)).toBe('project_builder');
  });

  it('still routes explicit README read/open requests to file viewer', () => {
    expect(classifyRequest('Open README.md')).toBe('file');
    expect(classifyRequest('Read the README.md file')).toBe('file');
  });

  it('keeps preview-only website requests in artifact preview lane', () => {
    expect(classifyRequest('Generate a website preview only. Do not write files.')).toBe('artifact');
  });

  it('routes image-generation requests to image lane', () => {
    expect(classifyRequest('Generate an image of a futuristic ADAS dashboard.')).toBe('image');
  });

  it('routes research requests to research lane', () => {
    expect(classifyRequest('Research the latest ComfyUI setup notes.')).toBe('research');
  });
});
