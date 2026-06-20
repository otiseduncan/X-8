import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
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
            ? { action: body.action, command: 'git clean -fdn', allowed: true, approval_required: false, reason: 'Preview only; no files deleted.' }
            : {
                command: body.command,
                category: body.command === 'docker compose config' ? 'destructive/protected' : 'validation/test',
                allowed: body.command !== 'docker compose config',
                blocked: body.command === 'docker compose config',
                approval_required: body.command === 'docker compose config',
                reason: body.command === 'docker compose config' ? 'Protected or secret-revealing command is blocked by default.' : 'Known local validation command is allowed.'
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
  expect(await screen.findByText('export function App() {}')).toBeInTheDocument();
});

test('surfaces blocked command proposals without running them', async () => {
  render(<ChatIDESurface />);
  fireEvent.change(await screen.findByLabelText('IDE command selector'), { target: { value: 'docker compose config' } });
  fireEvent.click(screen.getByRole('button', { name: 'Propose' }));
  expect(await screen.findByText(/Protected or secret-revealing command is blocked by default/i)).toBeInTheDocument();
});
