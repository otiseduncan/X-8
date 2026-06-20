import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { gitStatusText } from '../app/handlers/chatIDEHandlers';
import { ChatIDESurface } from '../app/ChatIDESurface';

const summary = {
  files: [
    { path: 'README.md', kind: 'file', size: 20 },
    { path: 'apps/web/src/app/App.tsx', kind: 'file', size: 100 }
  ],
  selected_file: { path: 'README.md', content: '# X8\n', line_count: 1 },
  git_status: { branch: 'feature/chat-ide-core-v1', dirty: true, changed_files: ['M apps/web/src/app/App.tsx'], ahead: 0, behind: 0 },
  checkpoint: { branch: 'feature/chat-ide-core-v1', working_tree_dirty: true, head: { sha: 'abc123', message: 'Checkpoint' }, rollback_guidance: ['Preview cleanup before deletion.'] },
  test_commands: ['docker compose -f compose.yaml run --rm --build web-tests'],
  permissions: [],
  activity: [{ action_type: 'summary', scope: 'workspace', approval_required: false, status: 'ready', proof: 'loaded' }]
};

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((path: string, options?: { body?: BodyInit }) => {
    const body = typeof options?.body === 'string' ? JSON.parse(options.body) : {};
    const data = String(path).includes('/summary')
      ? summary
      : String(path).includes('/open-file')
        ? { path: body.path, content: 'export function App() {}\n', line_count: 1 }
        : String(path).includes('/git/status')
          ? summary.git_status
          : String(path).includes('/rollback/propose')
            ? { action: body.action, command: 'git restore .', allowed: true, approval_required: true, reason: 'Rollback is destructive and requires explicit approval.' }
            : {
                command: body.command,
                category: body.command === 'docker compose config' ? 'destructive/protected' : 'validation/test',
                allowed: body.command !== 'docker compose config',
                blocked: body.command === 'docker compose config',
                approval_required: true,
                reason: body.command === 'docker compose config' ? 'Protected or secret-revealing command is blocked by default.' : 'Known local validation command is prepared. Approval is required before Docker starts.'
              };
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true, status: data.blocked ? 'blocked' : 'ready', message: data.reason || 'ok', data, receipts: [] }) } as Response);
  }));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

test('renders workspace summary and opens files read-only', async () => {
  render(<ChatIDESurface />);
  expect(await screen.findByText('Chat IDE Core v1')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'apps/web/src/app/App.tsx' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/ide/open-file', expect.objectContaining({ method: 'POST' })));
  expect(await screen.findByText('Source is hidden by default. Use Show code when you explicitly want to inspect it.')).toBeInTheDocument();
  expect(screen.queryByText('export function App() {}')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Show code' }));
  await waitFor(() => expect(screen.getByLabelText('Source code for apps/web/src/app/App.tsx')).toHaveTextContent('export function App() {}'));
});

test('surfaces blocked command proposals without running them', async () => {
  render(<ChatIDESurface />);
  const selector = await screen.findByLabelText('IDE command selector');
  fireEvent.change(selector, { target: { value: 'docker compose config' } });
  await waitFor(() => expect(selector).toHaveValue('docker compose config'));
  fireEvent.click(screen.getByRole('button', { name: 'Propose' }));
  expect((await screen.findAllByText(/Protected or secret-revealing command is blocked by default/i))[0]).toBeInTheDocument();
  expect(screen.getAllByText('Details').length).toBeGreaterThan(0);
});

test('shows rollback as approval-required proposal, not a failure', async () => {
  render(<ChatIDESurface />);
  fireEvent.click(await screen.findByRole('button', { name: 'Discard proposal' }));
  expect(await screen.findByText('Rollback is destructive and requires explicit approval.')).toBeInTheDocument();
  expect(screen.getByText('No rollback has run. Destructive rollback actions require explicit approval.')).toBeInTheDocument();
});

test('formats Git IDE answers as human-readable assistant text', () => {
  const git = {
    branch: 'feature/chat-ide-core-v1',
    dirty: true,
    changed_files: ['M apps/web/src/app/App.tsx', '?? test-results/'],
    file_recommendations: [
      { path: 'apps/web/src/app/App.tsx', recommendation: 'include in commit', reason: 'Source change.' },
      { path: 'test-results/', recommendation: 'do not commit', reason: 'Generated runtime output.' }
    ]
  };
  expect(gitStatusText(git, 'what branch are we on')).toBe('You are on `feature/chat-ide-core-v1`. Working tree is dirty: 1 modified, 1 untracked.');
  expect(gitStatusText(git, 'show git status')).toContain('Commit candidates: apps/web/src/app/App.tsx.');
  expect(gitStatusText(git, 'what should be committed')).toContain('Exclude: test-results/.');
  expect(gitStatusText({ branch: 'feature/chat-ide-core-v1', dirty: false, changed_files: [] }, 'what changed')).toBe('No working-tree changes are currently present.');
});
