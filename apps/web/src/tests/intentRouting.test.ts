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

test('parses quoted GitHub repository names', () => {
  expect(parseGitHubCreateRepo('create GitHub repo named "x8-demo"', 'otiseduncan').repo_name).toBe('x8-demo');
});
