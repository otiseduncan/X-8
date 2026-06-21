import { expect, test } from 'vitest';
import { classifyRequest, parseGitHubCreateRepo } from '../app/intentRouting';

test('routes GitHub publish language before artifact preview language', () => {
  expect(classifyRequest('publish this website to GitHub')).toBe('github');
});

test('keeps self-build ahead of GitHub routing', () => {
  expect(classifyRequest('create a self-build proposal to fix GitHub routing')).toBe('self_build');
});

test('routes explicit Chat IDE requests without stealing artifact previews', () => {
  expect(classifyRequest('show git status')).toBe('ide');
  expect(classifyRequest('show architecture guard')).toBe('ide');
  expect(classifyRequest('prepare a web test command')).toBe('ide');
  expect(classifyRequest('prepare rollback')).toBe('ide');
  expect(classifyRequest('show code for App.tsx')).toBe('ide');
  expect(classifyRequest('show me a website preview')).toBe('artifact');
});

test('keeps coding and design prompts on the Open WebUI chat path', () => {
  expect(classifyRequest('Build a minimal API contract for cards, sources, actions, nextActions, artifacts, warnings, or messages.')).toBe('chat');
  expect(classifyRequest('Build a tiny validation sidecar design that checks fake repo access. Do not block the model before it answers.')).toBe('chat');
  expect(classifyRequest('Final build test: make Xoduz look like Open WebUI chat with our colors. Give me the first tiny implementation slice only.')).toBe('chat');
  expect(classifyRequest('I approve that preview. Now explain exactly what files you would create. Do not actually write anything.')).toBe('chat');
});

test('keeps negated Docker/test wording on the Open WebUI chat path', () => {
  expect(classifyRequest('Create a PowerShell script that scans the repo read-only and outputs a zip report. Return it as a PowerShell code artifact, not as a website preview, not as a Docker test, and do not run it.')).toBe('chat');
  expect(classifyRequest('Create a test plan, but do not run tests.')).toBe('chat');
  expect(classifyRequest('Return this as code, not as docker test approval.')).toBe('chat');
  expect(classifyRequest('docker test')).toBe('chat');
});

test('only routes explicit execution requests to Docker test approval', () => {
  expect(classifyRequest('run tests')).toBe('test');
  expect(classifyRequest('run api tests')).toBe('ide');
  expect(classifyRequest('give me a build test question')).toBe('chat');
});

test('parses quoted GitHub repository names', () => {
  expect(parseGitHubCreateRepo('create GitHub repo named "x8-demo"', 'otiseduncan').repo_name).toBe('x8-demo');
});
