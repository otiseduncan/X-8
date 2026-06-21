import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from '../app/App';
vi.mock('../components/cockpit/CodeEditor', () => ({
  CodeEditor: ({ value }: { value: string }) => <pre aria-label="Code editor">{value}</pre>
}));
let recognitionInstance: {
  onstart: (() => void) | null;
  onresult: ((event: { results: Array<Array<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};
let spokenUtterance: Record<string, unknown> | null = null;
const femaleVoice = { name: 'Microsoft Zira Desktop', voiceURI: 'zira-uri', lang: 'en-US' };
const maleVoice = { name: 'Google US English Male', voiceURI: 'male-uri', lang: 'en-US' };
function mockRuntime() {
  vi.stubGlobal('fetch', vi.fn((path: string, options?: { body?: BodyInit }) => {
    const text = typeof options?.body === 'string' ? JSON.parse(options.body) : {};
    if (String(path) === '/avatar/manifest.json') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          version: '1.0',
          defaultAvatar: 'xoduz',
          assets: [
            { id: 'idle', label: 'Idle', type: 'video', src: '/avatar/xoduz-idle.mp4', states: ['idle'], loop: true, muted: true },
            { id: 'thinking', label: 'Thinking', type: 'video', src: '/avatar/xoduz-thinking.mp4', states: ['thinking', 'listening'], loop: true, muted: true },
            { id: 'speaking', label: 'Speaking', type: 'video', src: '/avatar/xoduz-speaking.mp4', states: ['speaking'], loop: true, muted: true }
          ],
          fallback: { type: 'generated', label: 'Fallback X avatar', src: '/avatar/fallback.svg' }
        })
      });
    }
    const data = String(path).includes('capabilities')
      ? [{ name: 'artifact_preview', status: 'implemented', summary: '', requires_approval: false }]
      : String(path).includes('integrations')
        ? [{ name: 'email', status: 'disabled', summary: '' }]
        : String(path).includes('workspace/files')
          ? [{ path: 'README.md', kind: 'file', size: 10 }]
          : String(path).includes('workspace/read')
            ? { path: 'README.md', content: '# XV8\n', line_count: 1 }
            : String(path).includes('repo/propose-update')
              ? {
                  path: 'README.md',
                  diff: '--- README.md\n+++ README.md\n+<!-- XV8 proposed note -->',
                  proposed_content: '# XV8\n<!-- XV8 proposed note -->\n',
                  mutated: false,
                  approval: {
                    id: 'approval-1',
                    action: 'apply_patch',
                    risk: 'medium',
                    status: 'approval_required',
                    intent: { summary: 'Propose README change.', files_affected: ['README.md'], before_after_summary: 'Adds one note.' },
                    rollback_hint: { summary: 'Revert patch.' }
                  },
                  receipt: { id: 'receipt-1', action: 'patch_proposal', status: 'pending approval', summary: 'Patch requires approval.' }
                }
              : String(path).includes('artifacts/preview')
                ? { title: 'Inline website preview', html: '<main><h1>Hello</h1></main>', css: 'body{color:#111}' }
                : String(path).includes('search/query')
                  ? { provider: 'SearXNG', results: [{ title: 'Source A', url: 'https://example.test', snippet: 'Fresh source snippet.' }] }
                  : String(path).includes('images/generate')
                    ? { seed: 123, image_url: '' }
                    : String(path).includes('docker/presets')
                      ? ['api_tests']
                      : String(path).includes('github/ops/auth-status')
                        ? { token_configured: true, owner_configured: true, owner: 'otiseduncan', default_visibility: 'private' }
                      : String(path).includes('github/ops/status')
                        ? { is_repo: true, branch: 'main', remote_origin_url: 'https://github.com/otiseduncan/X-8.git', dirty: true, changed_files: ['M README.md'], last_commit: { sha: 'abc123', message: 'Latest safe commit' }, ahead: 1, behind: 0 }
                      : String(path).includes('github/ops/push-preview')
                        ? { branch: 'main', remote: 'https://github.com/otiseduncan/X-8.git', commits_to_push: ['abc123 Latest safe commit'], dirty: true, allowed_after_approval: true }
                      : String(path).includes('github/ops/pull-preview')
                        ? { branch: 'main', remote: 'https://github.com/otiseduncan/X-8.git', dirty: true, allowed_after_approval: true }
                      : String(path).includes('github/ops/create-repo')
                        ? { status: text.approved ? 'applied' : 'blocked', reason: text.approved ? 'GitHub repository created.' : 'Approval required before creating GitHub repository.', repo: text.repo_name, owner: text.owner, visibility: text.visibility || 'private', changed_files: [] }
                      : String(path).includes('github/ops/')
                        ? { status: text.approved ? 'blocked' : 'blocked', reason: text.approved ? 'GitHub token not configured.' : 'Approval required before GitHub operation.', changed_files: [] }
                      : String(path).includes('github/status')
                        ? { status: 'not_configured' }
                        : String(path).includes('search/status')
                          ? { status: 'unavailable' }
                          : String(path).includes('images/status')
                            ? { status: 'unavailable' }
                            : String(path).includes('local-bridge/status')
                              ? { bridge_reachable: false }
                              : String(path).includes('config-import')
                                ? { x7_import_status: 'available', x7_files_found: 4, x6_import_status: 'available', x6_files_found: 3, github_config_found_in_x7: true, comfyui_config_found_in_x6: true, search_config_found_in_x6: true }
                                : String(path).includes('avatar/manifest')
                                  ? { default_asset: '/avatar/fallback.svg' }
                                  : String(path).includes('speech/status')
                                    ? { status: 'browser_fallback' }
                                    : String(path).includes('speech/receipt')
                                      ? { ok: true }
                                      : String(path).includes('/api/self-build/tasks/') && String(path).endsWith('/apply')
                                        ? text.patch_hash === 'blocked_hash'
                                          ? { patch_id: text.patch_id, applied: false, validation_passed: false, status: 'blocked', changed_files: [], backup_paths: [], reason: 'File changed since proposal: README.md' }
                                          : { patch_id: text.patch_id, applied: true, validation_passed: true, status: 'applied', changed_files: ['README.md'], backup_paths: ['runtime/self-build-backups/README.md.bak'], reason: 'Patch applied after exact approval hash match.' }
                                      : String(path).includes('self-build/prompt')
                                        ? {
                                            intent: 'create_proposal',
                                            proposal_detail: {
                                              task_id: 'sbtask_1',
                                              patch_id: 'patch_1',
                                              approval_id: 'sbappr_1',
                                              patch_hash: text.prompt?.includes('blocked apply') ? 'blocked_hash' : text.prompt?.includes('missing hash') ? '' : 'hash_1',
                                              files_changed_count: 1,
                                              changed_file_paths: ['README.md'],
                                              validation_status: text.prompt?.includes('unsafe proposal') ? 'failed' : 'passed',
                                              risk_level: 'normal_mutation',
                                              apply_safe: !text.prompt?.includes('unsafe proposal') && !text.prompt?.includes('missing hash'),
                                              message: 'No files changed. Approval required before apply.',
                                              changes: [{ file_path: 'README.md', before_hash: 'before_1', after_hash: 'after_1', unified_diff: '--- a/README.md\n+++ b/README.md\n+## Self-Build Mode' }]
                                            }
                                          }
                                      : String(path).includes('attachments')
                                        ? { attachment_id: 'att_test', filename: 'notes.txt', mime_type: 'text/plain', size_bytes: 5, status: 'uploaded', extracted_text: 'hello', content_extractable: true }
                                        : String(path).includes('sessions')
                                          ? []
                                          : String(path).includes('models/status')
                                            ? { model_ready: false, selected_model: '', ollama_reachable: false }
                                            : String(path).includes('brain/embedding-status')
                                              ? { enabled: true, available: true, embedding_model: 'nomic-embed-text:latest', indexed_memory_count: 2, failure_reason: '' }
                                            : String(path).includes('brain/reindex')
                                              ? { indexed: 2, skipped: 0, embedding_status: { available: true, indexed_memory_count: 2 } }
                                            : String(path).includes('brain/continuity/status')
                                              ? { continuity_ready: true, current_project: { summary: 'Brain V1 Phase 5' }, next_step: { summary: 'Phase 5 validation' }, active_blockers: [{ summary: 'no live browser connector' }], active_tasks: [{ id: 'cont_task_1', title: 'Phase 5 task', summary: 'wire continuity panel', status: 'active', updated_at: new Date().toISOString() }], last_validation_checkpoint: { summary: '139 API tests passing' }, recent_decisions: [{ summary: 'structured before calendar automation' }], latest_commit_checkpoint: { summary: '56858f7 Brain V4' } }
                                            : String(path).includes('brain/continuity/records') && options?.method === 'PATCH'
                                              ? { id: 'cont_task_1', summary: 'wire continuity panel', status: text.status || 'done', active: text.active ?? false }
                                            : String(path).includes('brain/continuity/records')
                                              ? [{ id: 'cont_task_1', record_type: 'task', title: 'Phase 5 task', summary: 'wire continuity panel', status: 'active', updated_at: new Date().toISOString() }]
                                            : String(path).includes('brain/continuity/tasks')
                                              ? { id: 'cont_task_2', record_type: 'task', title: text.summary, summary: text.summary, status: 'active' }
                                            : String(path).includes('brain/continuity/handoff')
                                              ? { handoff: 'Handoff note:\\n- Current project: Brain V1 Phase 5' }
                                            : String(path).includes('brain/status')
                                              ? { brain_ready: true, storage_backend: 'postgres', active_memory_count: 2, pending_approval_count: 1, active_focus: 'Brain V1 Batch 1', last_memory_event: { event_type: 'auto_saved' }, latest_auto_capture_event: { decision: 'auto_save', reason: 'Clear low-risk preference.' }, last_ignored_or_blocked_reason: 'Low-value chatter.', auto_capture_enabled: true, auto_capture_min_confidence: 0.7, auto_capture_max_per_turn: 3, semantic_retrieval_enabled: true, embedding_available: true, indexed_memory_count: 2, embedding_model: 'nomic-embed-text:latest', last_embedding_event: { event_type: 'embedding_indexed' }, latest_retrieval: { retrieval_mode: 'semantic', selected_ids: ['brain_mem_active'], scores: [0.91], fallback_reason: '', embedding_model: 'nomic-embed-text:latest' } }
                                              : String(path).includes('brain/auto-capture/toggle')
                                                ? { brain_ready: true, storage_backend: 'postgres', auto_capture_enabled: text.enabled, auto_capture_min_confidence: 0.7, auto_capture_max_per_turn: 3 }
                                              : String(path).includes('brain/candidates')
                                                ? [
                                                    { id: 'brain_cand_auto', suggested_title: 'Answer preference', summary: 'you prefer direct senior-engineer answers', source_text_redacted: 'I prefer direct senior-engineer answers.', decision: 'auto_save', reason: 'Clear low-risk preference.', confidence: 0.88, linked_memory_id: 'brain_mem_active', created_at: new Date().toISOString() },
                                                    { id: 'brain_cand_pending', suggested_title: 'Sensitive candidate', summary: 'family history note', source_text_redacted: 'family history note', decision: 'pending_approval', reason: 'Sensitive or private memory requires approval.', confidence: 0.78, linked_memory_id: 'brain_mem_pending', created_at: new Date().toISOString() },
                                                    { id: 'brain_cand_blocked', suggested_title: 'Blocked candidate', summary: 'token [redacted]', source_text_redacted: 'token [redacted]', decision: 'blocked', reason: 'Secret-like content is blocked from Brain memory.', confidence: 0.99, linked_memory_id: '', created_at: new Date().toISOString() }
                                                  ].filter((candidate) => !String(path).includes('decision=') || String(path).includes(`decision=${candidate.decision}`))
                                              : String(path).includes('brain/events')
                                                ? [
                                                    { id: 'brain_evt_auto', memory_id: 'brain_mem_active', event_type: 'auto_saved', event_summary: 'Auto-saved memory: you prefer direct senior-engineer answers', source: 'brain', created_at: new Date().toISOString() },
                                                    { id: 'brain_evt_dup', memory_id: 'brain_mem_active', event_type: 'duplicate_detected', event_summary: 'Already remembered: you prefer direct senior-engineer answers', source: 'brain', created_at: new Date().toISOString() }
                                                  ]
                                              : String(path).includes('brain/memories') && String(path).includes('/approve')
                                                ? { id: 'brain_mem_pending', title: 'Pending memory', summary: 'approved sensitive memory', content: 'approved sensitive memory', layer: 'pending', type: 'approval_required', sensitivity: 'personal_sensitive', active: true, soft_deleted: false, requires_approval: false, approved_by_user: true, global_scope: true, tags: ['pending'], updated_at: new Date().toISOString() }
                                              : String(path).includes('brain/memories') && String(path).includes('/reject')
                                                ? { id: 'brain_mem_pending', title: 'Pending memory', summary: 'rejected sensitive memory', content: 'rejected sensitive memory', layer: 'pending', type: 'approval_required', sensitivity: 'personal_sensitive', active: false, soft_deleted: true, requires_approval: true, approved_by_user: false, global_scope: true, tags: ['pending'], updated_at: new Date().toISOString() }
                                              : String(path).includes('brain/memories') && String(path).includes('/reactivate')
                                                ? { id: 'brain_mem_deleted', title: 'Deleted memory', summary: 'reactivated memory', content: 'reactivated memory', layer: 'preferences', type: 'manual_memory', sensitivity: 'low', active: true, soft_deleted: false, requires_approval: false, approved_by_user: true, global_scope: true, tags: ['manual'], updated_at: new Date().toISOString() }
                                              : String(path).includes('brain/memories') && options?.method === 'PATCH'
                                                ? { id: 'brain_mem_active', title: text.title || 'Answer preference', summary: text.summary || 'you prefer direct senior-engineer answers', content: text.content || 'you prefer direct senior-engineer answers', layer: 'preferences', type: 'communication_preference', sensitivity: 'low', active: text.active ?? true, soft_deleted: false, requires_approval: false, approved_by_user: true, global_scope: true, tags: text.tags || ['manual'], updated_at: new Date().toISOString() }
                                              : String(path).includes('brain/memories') && options?.method === 'DELETE'
                                                ? { id: 'brain_mem_active', title: 'Answer preference', summary: 'you prefer direct senior-engineer answers', content: 'you prefer direct senior-engineer answers', layer: 'preferences', type: 'communication_preference', sensitivity: 'low', active: false, soft_deleted: true, requires_approval: false, approved_by_user: true, global_scope: true, tags: ['manual'], updated_at: new Date().toISOString() }
                                              : String(path).includes('brain/memories')
                                                ? [
                                                    { id: 'brain_mem_active', title: 'Answer preference', summary: 'you prefer direct senior-engineer answers', content: 'you prefer direct senior-engineer answers', layer: 'preferences', type: 'communication_preference', sensitivity: 'low', confidence: 0.9, source: 'user_explicit', provenance: 'explicit_user_command', active: true, soft_deleted: false, requires_approval: false, approved_by_user: true, global_scope: true, tags: ['manual', 'answers'], created_at: new Date().toISOString(), updated_at: new Date().toISOString(), last_used_at: '' },
                                                    { id: 'brain_mem_pending', title: 'Sensitive memory', summary: 'family history note', content: 'family history note', layer: 'pending', type: 'approval_required', sensitivity: 'personal_sensitive', confidence: 0.9, source: 'user_explicit', provenance: 'explicit_user_command', active: false, soft_deleted: false, requires_approval: true, approved_by_user: false, project_scope: 'x8', tags: ['pending'], created_at: new Date().toISOString(), updated_at: new Date().toISOString(), last_used_at: '' },
                                                    { id: 'brain_mem_deleted', title: 'Deleted memory', summary: 'old deleted memory', content: 'old deleted memory', layer: 'memory', type: 'manual_memory', sensitivity: 'low', active: false, soft_deleted: true, requires_approval: false, approved_by_user: true, session_scope: 'sess_old', tags: [], created_at: new Date().toISOString(), updated_at: new Date().toISOString() }
                                                  ]
                                                : String(path).includes('brain/retrieve')
                                                  ? { memories: [{ id: 'brain_mem_active', summary: 'you prefer direct senior-engineer answers' }], retrieval_proof: { retrieval_mode: 'semantic', memory_ids_used: ['brain_mem_active'], scores: [0.91], fallback_used: false, fallback_reason: '', embedding_available: true, embedding_model: 'nomic-embed-text:latest', semantic_index_count: 2 } }
                                                : String(path).includes('brain/focus')
                                                  ? { id: 'focus_1', focus: text.focus || 'Brain V1 Batch 1' }
                                            : String(path).includes('receipts')
                                              ? []
                                      : String(path).includes('chat')
                                        ? {
                                            session_id: 'sess_test',
                                            message_id: `msg_reply_${Math.random().toString(16).slice(2)}`,
                                            assistant_message: {
                                              role: 'assistant',
                                              content: text.message?.includes('blocked token') ? 'Memory blocked: secret-like content was not saved.' : `Echo: ${text.message}`,
                                              cards: text.message?.includes('blocked token')
                                                ? [{ type: 'receipt', title: 'Memory blocked', status: 'blocked', summary: 'Memory blocked: secret-like content was not saved.', payload: {} }]
                                                : text.message?.includes('duplicate preference')
                                                  ? [{ type: 'receipt', title: 'Already remembered', status: 'duplicate', summary: 'Already remembered: you prefer duplicate preference.', payload: {} }]
                                                  : text.message?.includes('I prefer')
                                                    ? [{ type: 'receipt', title: 'Memory saved', status: 'auto_saved', summary: 'Remembered: you prefer direct senior-engineer answers.', payload: {} }]
                                                    : [{ type: 'info', title: 'Kernel limitations', status: 'unavailable', summary: 'Kernel fallback was used.', payload: {} }]
                                            },
                                            receipt: { receipt_id: 'rcpt_chat', action_type: 'prompt_round_trip', status: 'unavailable', model: '', limitations: [] },
                                            attachments: text.attachments?.map((attachment: Record<string, unknown>) => ({ ...attachment, status: 'uploaded' })) || []
                                          }
                                        : [{ name: 'Product Lead', responsibility: 'Owns value and scope.', output_style: 'Concise' }];
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', message: 'ok', receipts: [], data }) });
  }));
}
beforeEach(() => {
  window.localStorage.clear();
  spokenUtterance = null;
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal('confirm', vi.fn(() => true));
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  mockRuntime();
  recognitionInstance = { onstart: null, onresult: null, onerror: null, onend: null };
  class MockRecognition {
    continuous = false;
    interimResults = false;
    lang = 'en-US';
    onstart: (() => void) | null = null;
    onresult: ((event: { results: Array<Array<{ transcript: string }>> }) => void) | null = null;
    onerror: ((event: { error: string }) => void) | null = null;
    onend: (() => void) | null = null;
    start() {
      recognitionInstance = this;
      this.onstart?.();
    }
    stop() {
      this.onend?.();
    }
  }
  vi.stubGlobal('SpeechRecognition', MockRecognition);
  vi.stubGlobal('webkitSpeechRecognition', MockRecognition);
  vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function Utterance(this: Record<string, unknown>, text: string) {
    this.text = text;
  }));
  vi.stubGlobal('speechSynthesis', {
    getVoices: () => [maleVoice, femaleVoice],
    speak: vi.fn((utterance: { onstart?: () => void; onend?: () => void }) => {
      spokenUtterance = utterance as unknown as Record<string, unknown>;
      utterance.onstart?.();
      utterance.onend?.();
    }),
    pause: vi.fn(),
    resume: vi.fn(),
    cancel: vi.fn()
  });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
async function send(text: string) {
  fireEvent.change(screen.getByLabelText('Message XV8'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
}
function openAudioControls() {
  const section = screen.getByLabelText('Audio controls') as HTMLDetailsElement;
  if (!section.open) fireEvent.click(within(section).getByText('Audio controls'));
  return screen.getByLabelText('Avatar audio controls');
}
function setScrollMetrics(element: HTMLElement, metrics: { scrollHeight: number; clientHeight: number; scrollTop: number }) {
  Object.defineProperty(element, 'scrollHeight', { configurable: true, value: metrics.scrollHeight });
  Object.defineProperty(element, 'clientHeight', { configurable: true, value: metrics.clientHeight });
  Object.defineProperty(element, 'scrollTop', { configurable: true, writable: true, value: metrics.scrollTop });
}
test('renders assistant mode without permanent dashboard panels', async () => {
  render(<App />);
  expect(document.querySelector('[data-theme="neon-blue"]')).toBeInTheDocument();
  expect(await screen.findByTestId('avatar-video')).toBeInTheDocument();
  expect(screen.getByTestId('avatar-video')).toHaveAttribute('autoplay');
  expect((screen.getByTestId('avatar-video') as HTMLVideoElement).muted).toBe(true);
  expect(screen.getByTestId('avatar-video')).toHaveAttribute('playsinline');
  expect(screen.getByLabelText('Avatar presence')).toBeInTheDocument();
  expect(screen.getByText('State: idle')).toBeInTheDocument();
  expect(screen.getByLabelText('Chat timeline')).toBeInTheDocument();
  expect(screen.getByLabelText('Message XV8')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('Ask XV8 anything...')).toBeInTheDocument();
  expect(screen.getByLabelText('Attach file')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /push to talk/i })).toBeInTheDocument();
  expect(within(screen.getByTestId('avatar-stage')).queryByRole('button')).not.toBeInTheDocument();
  expect((screen.getByLabelText('Audio controls') as HTMLDetailsElement).open).toBe(false);
  expect((screen.getByLabelText('Audio diagnostics') as HTMLDetailsElement).open).toBe(false);
  const controls = openAudioControls();
  expect(within(controls).getByRole('button', { name: /mute voice/i })).toBeInTheDocument();
  expect(within(controls).getByLabelText('Voice volume')).toBeInTheDocument();
  expect(within(controls).getByLabelText('Voice selector')).toBeInTheDocument();
  expect(within(controls).getByRole('button', { name: /refresh voices/i })).toBeInTheDocument();
  expect(within(controls).getByRole('button', { name: /preview selected voice/i })).toBeInTheDocument();
  expect(within(controls).getByRole('button', { name: /reset stage/i })).toBeInTheDocument();
  expect(within(controls).getByRole('button', { name: /stop audio/i })).toBeInTheDocument();
  expect(within(controls).getByRole('button', { name: /play raw audio test/i })).toBeInTheDocument();
  expect(within(controls).getByRole('button', { name: /unlock\/test voice/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^Mute$/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^Read aloud$/i })).not.toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: /^Info/i })).toHaveLength(1);
  expect(screen.queryByText('Runtime ready')).not.toBeInTheDocument();
  expect(screen.queryByTestId('inline-receipt-card')).not.toBeInTheDocument();
  expect(screen.queryByText('Project File Tree')).not.toBeInTheDocument();
  expect(screen.queryByText('Full Editor')).not.toBeInTheDocument();
  expect(screen.queryByText('SearXNG Panel')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /^Info/i }));
  expect(await screen.findByLabelText('Info details')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: /copy transcript$/i }).length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: /copy transcript with receipts/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /download transcript/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  expect(await screen.findByText('Project File Tree')).toBeInTheDocument();
  expect(screen.getByText('Voice preference')).toBeInTheDocument();
  expect(screen.getByText('Backend')).toBeInTheDocument();
  expect(screen.getByText('postgres')).toBeInTheDocument();
  expect(screen.getByText('Brain V1 Batch 1')).toBeInTheDocument();
  expect(screen.getAllByText('auto_saved').length).toBeGreaterThan(0);
});
test('Brain memory panel searches filters opens detail and runs actions', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  expect(await screen.findByText('Brain / Memory')).toBeInTheDocument();
  expect(screen.getByText('postgres')).toBeInTheDocument();
  expect(screen.getByText('Brain V1 Batch 1')).toBeInTheDocument();
  expect(screen.getByText('Latest auto-capture event')).toBeInTheDocument();
  expect(screen.getByText('auto_save')).toBeInTheDocument();
  expect(screen.getByLabelText('Continuity panel')).toBeInTheDocument();
  expect(screen.getByText('Brain V1 Phase 5')).toBeInTheDocument();
  expect(screen.getByText('Phase 5 validation')).toBeInTheDocument();
  expect(screen.getByText('no live browser connector')).toBeInTheDocument();
  expect(screen.getByText('139 API tests passing')).toBeInTheDocument();
  expect(screen.getByText('Semantic retrieval')).toBeInTheDocument();
  expect(screen.getByText('Embedding available')).toBeInTheDocument();
  expect(screen.getByText('Indexed memories')).toBeInTheDocument();
  expect(screen.getByText('nomic-embed-text:latest')).toBeInTheDocument();
  expect(screen.getByText('embedding_indexed')).toBeInTheDocument();
  expect(screen.getByText('semantic')).toBeInTheDocument();
  expect(screen.getByText('Candidate history')).toBeInTheDocument();
  expect(screen.getByText('Latest events')).toBeInTheDocument();
  expect((await screen.findAllByText('Answer preference')).length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText('Search memory records'), { target: { value: 'senior-engineer' } });
  expect(screen.getAllByText('you prefer direct senior-engineer answers').length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText('Search memory records'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('Filter memory status'), { target: { value: 'pending' } });
  expect(screen.getByText('Sensitive memory')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Sensitive memory'));
  expect(screen.getByLabelText('Memory detail')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Memory title'), { target: { value: 'Updated memory title' } });
  fireEvent.click(screen.getByRole('button', { name: /^Save$/ }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/memories/brain_mem_pending', expect.objectContaining({ method: 'PATCH' })));
  fireEvent.click(screen.getByRole('button', { name: /^Approve$/ }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/memories/brain_mem_pending/approve', expect.objectContaining({ method: 'POST' })));
  fireEvent.click(screen.getByRole('button', { name: /^Reject$/ }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/memories/brain_mem_pending/reject', expect.objectContaining({ method: 'POST' })));
  fireEvent.click(screen.getByRole('button', { name: /^Delete$/ }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/memories/brain_mem_pending', expect.objectContaining({ method: 'DELETE' })));
  fireEvent.change(screen.getByLabelText('Filter memory candidates'), { target: { value: 'blocked' } });
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/candidates?decision=blocked'));
  expect(screen.getByText('Blocked candidate')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /disable auto-capture/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/auto-capture/toggle', expect.objectContaining({ method: 'POST' })));
  fireEvent.click(screen.getByRole('button', { name: /enable auto-capture/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/auto-capture/toggle', expect.objectContaining({ method: 'POST' })));
  fireEvent.click(screen.getByRole('button', { name: /reindex active memories/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/reindex', expect.objectContaining({ method: 'POST' })));
  fireEvent.change(screen.getByLabelText('New continuity task'), { target: { value: 'new continuity task' } });
  fireEvent.click(screen.getByRole('button', { name: /add task/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/continuity/tasks', expect.objectContaining({ method: 'POST' })));
  fireEvent.click(screen.getByRole('button', { name: /create handoff note/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/brain/continuity/handoff', expect.objectContaining({ method: 'POST' })));
  expect(screen.getByRole('button', { name: /supersede unavailable/i })).toBeDisabled();
  expect(document.body).not.toHaveTextContent(/ghp_/i);
  expect(document.body).not.toHaveTextContent(/embedding_json/i);
});
test('Brain auto-capture receipts render compactly and redact blocked secrets', async () => {
  render(<App />);
  await send('I prefer direct senior-engineer answers.');
  expect(await screen.findByText('Memory saved')).toBeInTheDocument();
  expect(screen.getByText('Remembered: you prefer direct senior-engineer answers.')).toBeInTheDocument();
  await send('duplicate preference');
  expect(await screen.findByText('Already remembered')).toBeInTheDocument();
  await send('blocked token ghp_secret_should_not_render');
  expect(await screen.findByText('Memory blocked')).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/ghp_secret_should_not_render/i);
});
test('conversation composer stays in the fixed bottom dock after messages and cards update', async () => {
  render(<App />);
  const composer = screen.getByLabelText('Message XV8').closest('form');
  expect(composer).toHaveClass('messageEntry');
  expect(screen.getByLabelText('Message list')).toBeInTheDocument();
  await send('make a simple HTML website preview');
  expect(await screen.findByTestId('inline-artifact-card')).toBeInTheDocument();
  expect(screen.getByLabelText('Message XV8').closest('form')).toBe(composer);
  expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
});
test('message list auto-scrolls and offers jump-to-latest when user scrolls away', async () => {
  render(<App />);
  await screen.findByTestId('avatar-video');
  const scrollCallsBefore = vi.mocked(Element.prototype.scrollIntoView).mock.calls.length;
  await send('hello scroll');
  await screen.findByText(/Echo: hello scroll/i);
  await waitFor(() => expect(vi.mocked(Element.prototype.scrollIntoView).mock.calls.length).toBeGreaterThan(scrollCallsBefore));
  const list = screen.getByLabelText('Message list');
  setScrollMetrics(list, { scrollHeight: 500, clientHeight: 200, scrollTop: 0 });
  fireEvent.scroll(list);
  expect(screen.getByRole('button', { name: /jump to latest/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /jump to latest/i }));
  expect(screen.queryByRole('button', { name: /jump to latest/i })).not.toBeInTheDocument();
});
test('thinking indicator appears while a request is pending and resolves after success', async () => {
  let resolveChat: ((value: Response) => void) | undefined;
  const original = vi.mocked(fetch).getMockImplementation();
  vi.mocked(fetch).mockImplementation((path: string, options?: { body?: BodyInit }) => {
    if (String(path).includes('/api/chat')) return new Promise((resolve) => { resolveChat = resolve; }) as ReturnType<typeof fetch>;
    return original?.(path, options) as ReturnType<typeof fetch>;
  });
  render(<App />);
  await send('slow hello');
  expect(await screen.findByLabelText('XV8 thinking')).toHaveTextContent(/Thinking|Working/);
  resolveChat?.({ ok: true, json: () => Promise.resolve({ status: 'ok', message: 'ok', receipts: [], data: { session_id: 'sess_slow', message_id: 'msg_slow', assistant_message: { role: 'assistant', content: 'Done slowly.', cards: [] }, receipt: { receipt_id: 'rcpt', action_type: 'prompt_round_trip', status: 'ok', model: '', limitations: [] }, attachments: [] } }) } as Response);
  expect(await screen.findByText('Done slowly.')).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByLabelText('XV8 thinking')).not.toBeInTheDocument(), { timeout: 2200 });
});
test('hello text-only response keeps thinking visible and routes through speech lifecycle', async () => {
  const original = vi.mocked(fetch).getMockImplementation();
  vi.mocked(fetch).mockImplementation((path: string, options?: { body?: BodyInit }) => {
    if (String(path).includes('/api/chat')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'passed', message: 'ok', receipts: [], data: { session_id: 'sess_hello', message_id: 'msg_hello', assistant_message: { role: 'assistant', content: "Hello. I'm XV8.", cards: [] }, receipt: { receipt_id: 'rcpt_hello', action_type: 'prompt_round_trip', status: 'passed', model: '', limitations: [] }, attachments: [] } }) } as Response);
    return original?.(path, options) as ReturnType<typeof fetch>;
  });
  render(<App />);
  await send('hello');
  expect(await screen.findByLabelText('XV8 thinking')).toBeInTheDocument();
  expect(await screen.findByText("Hello. I'm XV8.")).toBeInTheDocument();
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'thinking');
  expect(speechSynthesis.speak).not.toHaveBeenCalled();
  await waitFor(() => expect(speechSynthesis.speak).toHaveBeenCalled(), { timeout: 1200 });
  expect(spokenUtterance?.text).toBe("Hello. I'm XV8.");
  expect(spokenUtterance?.voice).toBe(femaleVoice);
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'speaking');
  expect(within(screen.getByLabelText('Audio diagnostics')).getByText('deterministic/text-only')).toBeInTheDocument();
  expect(within(screen.getByLabelText('Audio diagnostics')).getByText('assistant deterministic/text-only response')).toBeInTheDocument();
  (spokenUtterance?.onend as (() => void) | undefined)?.();
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'speaking');
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle'), { timeout: 1400 });
});
test('muted text-only response shows responded stage and speech skip reason', async () => {
  const original = vi.mocked(fetch).getMockImplementation();
  vi.mocked(fetch).mockImplementation((path: string, options?: { body?: BodyInit }) => {
    if (String(path).includes('/api/chat')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'passed', message: 'ok', receipts: [], data: { session_id: 'sess_muted', message_id: 'msg_muted', assistant_message: { role: 'assistant', content: "Hello. I'm XV8.", cards: [] }, receipt: { receipt_id: 'rcpt_muted', action_type: 'prompt_round_trip', status: 'passed', model: '', limitations: [] }, attachments: [] } }) } as Response);
    return original?.(path, options) as ReturnType<typeof fetch>;
  });
  render(<App />);
  fireEvent.click(within(openAudioControls()).getByRole('button', { name: /mute voice/i }));
  await send('hello');
  expect(await screen.findByText("Hello. I'm XV8.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'responded'), { timeout: 1200 });
  expect(speechSynthesis.speak).not.toHaveBeenCalled();
  expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('Muted state prevented speech playback.').length).toBeGreaterThan(0);
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle'), { timeout: 1200 });
});
test('raw Web Audio test updates audible proof diagnostics', async () => {
  class MockAudioContext {
    state = 'running';
    currentTime = 0;
    destination = {};
    createOscillator() {
      const oscillator = {
        frequency: { value: 0 },
        onended: null as (() => void) | null,
        connect: vi.fn(),
        start: vi.fn(),
        stop: vi.fn(function stop(this: { onended: (() => void) | null }) {
          this.onended?.();
        })
      };
      return oscillator;
    }
    createGain() {
      return { gain: { value: 0 }, connect: vi.fn() };
    }
    resume = vi.fn().mockResolvedValue(undefined);
    close = vi.fn().mockResolvedValue(undefined);
  }
  vi.stubGlobal('AudioContext', MockAudioContext);
  render(<App />);
  fireEvent.click(within(openAudioControls()).getByRole('button', { name: /play raw audio test/i }));
  const diagnostics = screen.getByLabelText('Audio diagnostics');
  expect(await within(diagnostics).findByText('web-audio')).toBeInTheDocument();
  expect(within(diagnostics).getAllByText('true').length).toBeGreaterThanOrEqual(3);
});
test('thinking indicator resolves after chat error', async () => {
  const original = vi.mocked(fetch).getMockImplementation();
  vi.mocked(fetch).mockImplementation((path: string, options?: { body?: BodyInit }) => String(path).includes('/api/chat') ? Promise.resolve({ ok: false, json: () => Promise.resolve({}) } as Response) : original?.(path, options) as ReturnType<typeof fetch>);
  render(<App />);
  await send('force error');
  expect(await screen.findByText('The chat request could not complete.')).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByLabelText('XV8 thinking')).not.toBeInTheDocument(), { timeout: 2200 });
});
test('copy transcript copies readable conversation markdown', async () => {
  render(<App />);
  await send('hello transcript');
  await screen.findByText(/Echo: hello transcript/i);
  fireEvent.click(screen.getByRole('button', { name: /^Copy transcript$/i }));
  await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
  const copied = vi.mocked(navigator.clipboard.writeText).mock.calls.at(-1)?.[0] || '';
  expect(copied).toContain('# XV8 Conversation Transcript');
  expect(copied).toContain('hello transcript');
  expect(copied).toContain('Echo: hello transcript');
  expect(copied).not.toContain('Kernel limitations');
});
test('clear chat confirms and resets visible conversation', async () => {
  render(<App />);
  await send('clear me');
  await screen.findByText(/Echo: clear me/i);
  fireEvent.click(screen.getByRole('button', { name: /clear chat/i }));
  expect(confirm).toHaveBeenCalled();
  expect(screen.queryByText(/Echo: clear me/i)).not.toBeInTheDocument();
  expect(screen.getByText('New chat is ready.')).toBeInTheDocument();
});
test('local history opens, starts new chats, restores previous sessions, and deletes sessions', async () => {
  render(<App />);
  await send('first history chat');
  await screen.findByText(/Echo: first history chat/i);
  fireEvent.click(screen.getByRole('button', { name: /history/i }));
  const history = await screen.findByLabelText('Chat history');
  expect(within(history).getByText('first history chat')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /new chat/i }));
  expect(screen.getByText('New chat is ready.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /history/i }));
  fireEvent.click(within(await screen.findByLabelText('Chat history')).getByText('first history chat'));
  expect(await screen.findByText(/Echo: first history chat/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /history/i }));
  fireEvent.click(screen.getByRole('button', { name: /delete first history chat/i }));
  expect(within(screen.getByLabelText('Chat history')).queryByText('first history chat')).not.toBeInTheDocument();
});
test('renders GitHub Ops panel without exposing token values', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  expect(await screen.findByText('GitHub Ops')).toBeInTheDocument();
  expect(screen.getByText('Token configured')).toBeInTheDocument();
  expect(screen.getByText('otiseduncan')).toBeInTheDocument();
  expect(screen.getByText('main')).toBeInTheDocument();
  expect(screen.getByText('Latest safe commit')).toBeInTheDocument();
  expect(screen.queryByText(/ghp_/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /push preview/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/github/ops/push-preview', expect.objectContaining({ method: 'POST' })));
});
test('audio controls stay outside the avatar media frame and collapse', async () => {
  render(<App />);
  const stage = await screen.findByTestId('avatar-stage');
  expect(within(stage).queryByRole('button', { name: /reset stage/i })).not.toBeInTheDocument();
  expect(within(stage).queryByRole('button', { name: /unlock\/test voice/i })).not.toBeInTheDocument();
  const controlsSection = screen.getByLabelText('Audio controls') as HTMLDetailsElement;
  expect(controlsSection.open).toBe(false);
  fireEvent.click(within(controlsSection).getByText('Audio controls'));
  expect(controlsSection.open).toBe(true);
  expect(within(screen.getByLabelText('Avatar audio controls')).getByRole('button', { name: /reset stage/i })).toBeInTheDocument();
});
test('voice dropdown uses real voices, persists voiceURI, and assigns the selected voice object', async () => {
  render(<App />);
  const controls = openAudioControls();
  const selector = within(controls).getByLabelText('Voice selector') as HTMLSelectElement;
  await waitFor(() => expect(selector.value).toBe('zira-uri'));
  expect(within(controls).getByText(/Microsoft Zira Desktop/i)).toBeInTheDocument();
  expect(within(controls).getByText(/Google US English Male/i)).toBeInTheDocument();
  fireEvent.change(selector, { target: { value: 'zira-uri' } });
  expect(window.localStorage.getItem('x8.voiceURI')).toBe('zira-uri');
  fireEvent.click(within(controls).getByRole('button', { name: /preview selected voice/i }));
  await waitFor(() => expect(speechSynthesis.speak).toHaveBeenCalled());
  expect(spokenUtterance?.voice).toBe(femaleVoice);
  const diagnostics = screen.getByLabelText('Audio diagnostics');
  expect(await within(diagnostics).findByText('Microsoft Zira Desktop')).toBeInTheDocument();
  expect(within(diagnostics).getByText('zira-uri')).toBeInTheDocument();
});
test('persisted voiceURI restores and unavailable persisted URI reports fallback', async () => {
  window.localStorage.setItem('x8.voiceURI', 'zira-uri');
  render(<App />);
  let selector = within(openAudioControls()).getByLabelText('Voice selector') as HTMLSelectElement;
  await waitFor(() => expect(selector.value).toBe('zira-uri'));
  cleanup();
  mockRuntime();
  window.localStorage.setItem('x8.voiceURI', 'missing-uri');
  render(<App />);
  selector = within(openAudioControls()).getByLabelText('Voice selector') as HTMLSelectElement;
  expect(selector.value).toBe('male-uri');
  expect(await within(screen.getByLabelText('Audio diagnostics')).findByText(/Persisted voice unavailable/i)).toBeInTheDocument();
});
test('known male voice is not selected while a known female voice is available', async () => {
  render(<App />);
  await waitFor(() => expect(within(screen.getByLabelText('Audio diagnostics')).getByText('Microsoft Zira Desktop')).toBeInTheDocument());
  expect(within(screen.getByLabelText('Audio diagnostics')).queryByText('Google US English Male')).not.toBeInTheDocument();
  expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('true').length).toBeGreaterThan(0);
});
test('diagnostics report fallback honestly when only a male voice is available', async () => {
  vi.stubGlobal('speechSynthesis', {
    getVoices: () => [maleVoice],
    speak: vi.fn((utterance: { onstart?: () => void }) => { spokenUtterance = utterance as unknown as Record<string, unknown>; utterance.onstart?.(); }),
    pause: vi.fn(),
    resume: vi.fn(),
    cancel: vi.fn()
  });
  render(<App />);
  const diagnostics = screen.getByLabelText('Audio diagnostics');
  expect(await within(diagnostics).findByText('Google US English Male')).toBeInTheDocument();
  expect(within(diagnostics).getByText('male-uri')).toBeInTheDocument();
  expect(within(diagnostics).getByText(/Female voice unavailable/i)).toBeInTheDocument();
  expect(within(diagnostics).queryByText('US Google female', { selector: 'span' })).toBeInTheDocument();
  expect(within(diagnostics).getAllByText('false').length).toBeGreaterThan(0);
});
test('renders GitHub operation approval cards before writes', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  await screen.findByText('GitHub Ops');
  fireEvent.click(screen.getByRole('button', { name: /create repo proposal/i }));
  const approvalCard = await screen.findByTestId('inline-approval-card');
  expect(within(approvalCard).getByText('github_ops')).toBeInTheDocument();
  expect(within(approvalCard).getByText('create-repo')).toBeInTheDocument();
  expect(within(approvalCard).getByRole('button', { name: /^Apply$/ })).toBeInTheDocument();
});
test('routes GitHub chat prompts to status, previews, and approval cards', async () => {
  render(<App />);
  await send('Check GitHub status');
  expect(await screen.findByText('GitHub status loaded without mutation.')).toBeInTheDocument();
  expect(screen.getByText('GitHub Ops status')).toBeInTheDocument();
  await send('Prepare to push this repo');
  expect(await screen.findByText('Push preview loaded. No push occurred.')).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/github/ops/push-preview', expect.objectContaining({ method: 'POST' })));
  expect(screen.getByText('Push this repo')).toBeInTheDocument();
  await send('Pull latest');
  expect(await screen.findByText('Pull preview loaded. No pull occurred.')).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/github/ops/pull-preview', expect.objectContaining({ method: 'POST' })));
  let approvalCards = screen.getAllByTestId('inline-approval-card');
  expect(within(approvalCards[approvalCards.length - 1]).getByText('Pull latest')).toBeInTheDocument();
  await send('Create a GitHub repo');
  expect(await screen.findByText('GitHub repo creation requires approval before any write.')).toBeInTheDocument();
  approvalCards = screen.getAllByTestId('inline-approval-card');
  expect(within(approvalCards[approvalCards.length - 1]).getByText('create-repo')).toBeInTheDocument();
});
test('routes self-build prompts mentioning GitHub before GitHub Ops', async () => {
  render(<App />);
  await send('Create a self-build proposal to fix GitHub create-repo chat routing');
  expect(await screen.findByText('Self-build prompt detected')).toBeInTheDocument();
  expect(screen.getByText('Self-build patch plan')).toBeInTheDocument();
  expect(screen.queryByText('GitHub status loaded without mutation.')).not.toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/self-build/prompt', expect.objectContaining({ method: 'POST' })));
  expect((fetch as ReturnType<typeof vi.fn>).mock.calls.some(([path]) => String(path).includes('/api/github/ops/status'))).toBe(true);
  expect((fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/status')).length).toBe(1);
});
test('routes GitHub create-repo chat prompt to approval card without push or status-only response', async () => {
  render(<App />);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/github/ops/status'));
  const pushPreviewCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/push-preview')).length;
  await send('Prepare a GitHub create-repo proposal for a private disposable repo named `x8-github-ops-smoke`');
  expect(await screen.findByText('GitHub repo creation requires approval before any write.')).toBeInTheDocument();
  expect(screen.queryByText('GitHub status loaded without mutation.')).not.toBeInTheDocument();
  expect(screen.queryByText('Push preview loaded. No push occurred.')).not.toBeInTheDocument();
  await waitFor(() => {
    const pushPreviewCallsAfter = (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/push-preview')).length;
    expect(pushPreviewCallsAfter).toBe(pushPreviewCallsBefore);
  });
  const approvalCards = screen.getAllByTestId('inline-approval-card');
  const approvalCard = approvalCards[approvalCards.length - 1];
  expect(within(approvalCard).getByText('github_ops')).toBeInTheDocument();
  expect(within(approvalCard).getByText('create-repo')).toBeInTheDocument();
  expect(within(approvalCard).getByText('x8-github-ops-smoke')).toBeInTheDocument();
  expect(within(approvalCard).getByText('otiseduncan')).toBeInTheDocument();
  expect(within(approvalCard).getByText('private')).toBeInTheDocument();
  expect(within(approvalCard).getAllByText('true').length).toBeGreaterThan(0);
  expect(within(approvalCard).getAllByText('false').length).toBeGreaterThanOrEqual(3);
});
test('literal GitHub chat text is not stolen by GitHub Ops routing', async () => {
  render(<App />);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/github/ops/status'));
  const statusCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/status')).length;
  const pushPreviewCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/push-preview')).length;
  await send('can you say GitHub');
  expect(await screen.findByText('Echo: can you say GitHub')).toBeInTheDocument();
  expect(screen.queryByText('GitHub status loaded without mutation.')).not.toBeInTheDocument();
  expect(screen.queryByText('Push preview loaded. No push occurred.')).not.toBeInTheDocument();
  expect(screen.queryByTestId('inline-approval-card')).not.toBeInTheDocument();
  expect((fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/status')).length).toBe(statusCallsBefore);
  expect((fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([path]) => String(path).includes('/api/github/ops/push-preview')).length).toBe(pushPreviewCallsBefore);
});
test('existing GitHub push and status routing stay intact without token exposure', async () => {
  render(<App />);
  await send('push this repo');
  expect(await screen.findByText('Push preview loaded. No push occurred.')).toBeInTheDocument();
  expect(screen.getByText('Push this repo')).toBeInTheDocument();
  await send('check GitHub status');
  expect(await screen.findByText('GitHub status loaded without mutation.')).toBeInTheDocument();
  expect(screen.getByText('GitHub Ops status')).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/ghp_/i);
});
test('renders generated artifacts and file viewers inline', async () => {
  render(<App />);
  await send('make a simple HTML website preview');
  expect(await screen.findByTestId('inline-artifact-card')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Preview' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Code' })).toBeInTheDocument();
  expect(screen.queryByText('Artifact + Website Preview')).not.toBeInTheDocument();
  await send('open README.md');
  expect(await screen.findByTestId('inline-file-card')).toBeInTheDocument();
  expect(screen.queryByText('Project File Tree')).not.toBeInTheDocument();
});
test('renders inline diff approval without mutating before approval', async () => {
  render(<App />);
  await send('propose a README edit');
  expect(await screen.findByTestId('inline-diff-card')).toBeInTheDocument();
  expect(screen.getByTestId('inline-approval-card')).toBeInTheDocument();
  expect(screen.getByText(/No mutation has happened/i)).toBeInTheDocument();
});
test('renders self-build plan proposal and approval cards', async () => {
  render(<App />);
  await send('Self-build test. Inspect README.md and propose a patch. Do not commit.');
  expect(await screen.findByText('Self-build prompt detected')).toBeInTheDocument();
  expect(screen.getByText('Self-build patch plan')).toBeInTheDocument();
  expect(screen.getByTestId('inline-diff-card')).toBeInTheDocument();
  expect(screen.getByTestId('inline-approval-card')).toBeInTheDocument();
  expect(screen.getAllByText(/No files changed. Approval required before apply./i).length).toBeGreaterThan(0);
  expect(screen.getByText(/1 file change/i)).toBeInTheDocument();
  const approvalCard = screen.getByTestId('inline-approval-card');
  expect(within(approvalCard).getByText('patch_1')).toBeInTheDocument();
  expect(within(approvalCard).getByText('sbappr_1')).toBeInTheDocument();
  expect(within(approvalCard).getByText('hash_1')).toBeInTheDocument();
  expect(within(approvalCard).getByRole('button', { name: /^Apply$/ })).toBeInTheDocument();
  fireEvent.click(within(approvalCard).getByRole('button', { name: /^Apply$/ }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/self-build/tasks/sbtask_1/apply', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ patch_id: 'patch_1', approval_id: 'sbappr_1', patch_hash: 'hash_1', approved: true })
  })));
  expect(await within(approvalCard).findByText(/Patch applied after exact approval hash match./i)).toBeInTheDocument();
  expect(within(approvalCard).getByText('README.md')).toBeInTheDocument();
  expect(within(approvalCard).getByText(/runtime\/self-build-backups\/README.md.bak/i)).toBeInTheDocument();
});
test('renders blocked self-build apply result honestly', async () => {
  render(<App />);
  await send('Self-build test blocked apply. Inspect README.md and propose a patch. Do not commit.');
  const approvalCard = await screen.findByTestId('inline-approval-card');
  fireEvent.click(within(approvalCard).getByRole('button', { name: /^Apply$/ }));
  expect(await within(approvalCard).findByText(/File changed since proposal: README.md/i)).toBeInTheDocument();
  expect(within(approvalCard).getByText(/false/i)).toBeInTheDocument();
});
test('does not render self-build Apply button without safe approval metadata', async () => {
  render(<App />);
  await send('Self-build unsafe proposal. Inspect README.md and propose a patch. Do not commit.');
  expect(await screen.findByText('Self-build patch plan')).toBeInTheDocument();
  expect(screen.queryByTestId('inline-approval-card')).not.toBeInTheDocument();
  cleanup();
  mockRuntime();
  render(<App />);
  await send('Self-build missing hash. Inspect README.md and propose a patch. Do not commit.');
  expect(await screen.findByText('Self-build status')).toBeInTheDocument();
  expect(screen.queryByTestId('inline-approval-card')).not.toBeInTheDocument();
});
test('renders inline research and image cards honestly', async () => {
  render(<App />);
  await send('search with SearXNG for XV8');
  expect(await screen.findByTestId('inline-research-card')).toBeInTheDocument();
  expect(screen.queryByText('SearXNG Panel')).not.toBeInTheDocument();
  await send('generate an image of a console');
  expect(await screen.findByTestId('inline-image-card')).toBeInTheDocument();
  expect(screen.queryByText('Image Studio')).not.toBeInTheDocument();
});
test('frontend source keeps cyan accent vocabulary and blocks old cool-purple tokens', () => {
  const blocked = ['purple-', 'violet-', 'fuchsia-', 'indigo-', 'purple', 'violet', 'fuchsia', 'indigo', '#a855', '#7c3', '#c084', '#9333', '#d946', '#8b5'];
  const root = join(process.cwd(), 'src');
  const files: string[] = [];
  const visit = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (path.includes(`${join('src', 'tests')}`)) continue;
      if (statSync(path).isDirectory()) visit(path);
      else if (/\.(ts|tsx|css)$/.test(path)) files.push(path);
    }
  };
  visit(root);
  const hits = files.flatMap((file) => {
    const text = readFileSync(file, 'utf-8').toLowerCase();
    return blocked.filter((token) => text.includes(token)).map((token) => `${file}:${token}`);
  });
  expect(hits).toEqual([]);
});
test('push-to-talk final transcript inserts text into composer without preview send flow', async () => {
  render(<App />);
  fireEvent.mouseDown(screen.getByRole('button', { name: /push to talk/i }));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'listening');
  expect(screen.getByRole('button', { name: /listening/i })).toBeInTheDocument();
  recognitionInstance.onresult?.({ results: [[{ transcript: 'open README.md' }]] });
  const composer = screen.getByLabelText('Message XV8') as HTMLTextAreaElement;
  await waitFor(() => expect(composer.value).toBe('open README.md'));
  expect(document.activeElement).toBe(composer);
  expect(screen.queryByLabelText('Transcript preview')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /send transcript/i })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /^Send$/i }));
  expect(await screen.findByTestId('inline-file-card')).toBeInTheDocument();
});
test('dictated text appends to existing composer text and can be edited before normal send', async () => {
  render(<App />);
  const composer = screen.getByLabelText('Message XV8') as HTMLTextAreaElement;
  fireEvent.change(composer, { target: { value: 'please' } });
  fireEvent.mouseDown(screen.getByRole('button', { name: /push to talk/i }));
  recognitionInstance.onresult?.({ results: [[{ transcript: 'check status' }]] });
  await waitFor(() => expect(composer.value).toBe('please check status'));
  fireEvent.change(composer, { target: { value: 'please check status now' } });
  fireEvent.click(screen.getByRole('button', { name: /^Send$/i }));
  expect(await screen.findByText('please check status now')).toBeInTheDocument();
  expect(await screen.findByText(/Echo: please check status now/i)).toBeInTheDocument();
});
test('shows permission denied and unavailable speech states honestly', async () => {
  render(<App />);
  const composer = screen.getByLabelText('Message XV8') as HTMLTextAreaElement;
  fireEvent.change(composer, { target: { value: 'keep this draft' } });
  fireEvent.mouseDown(screen.getByRole('button', { name: /push to talk/i }));
  recognitionInstance.onerror?.({ error: 'not-allowed' });
  expect(await screen.findByText('Microphone permission was denied.')).toBeInTheDocument();
  expect(composer.value).toBe('keep this draft');
  expect(screen.queryByLabelText('Transcript preview')).not.toBeInTheDocument();
  cleanup();
  mockRuntime();
  vi.stubGlobal('SpeechRecognition', undefined);
  vi.stubGlobal('webkitSpeechRecognition', undefined);
  render(<App />);
  const pttButtons = screen.getAllByRole('button', { name: /push to talk/i });
  fireEvent.mouseDown(pttButtons[pttButtons.length - 1]);
  expect(await screen.findByText('Speech input is unavailable in this browser.')).toBeInTheDocument();
  expect(screen.queryByText(/Browser Web Speech API is unavailable/i)).not.toBeInTheDocument();
});
test('TTS can speak, creates receipts, and mute stops output', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  fireEvent.click(await screen.findByRole('button', { name: /^Test voice$/i }));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'speaking');
  expect(within(screen.getByLabelText('Audio diagnostics')).getByText('speechStarted')).toBeInTheDocument();
  expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('true').length).toBeGreaterThan(0);
  fireEvent.click(within(openAudioControls()).getByRole('button', { name: /mute voice/i }));
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted'));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted');
});
test('chat send exits pending on success and API error', async () => {
  render(<App />);
  await send('hello XV8');
  await screen.findByText(/Echo: hello XV8/i);
  const diagnostics = screen.getByLabelText('Audio diagnostics');
  expect(within(diagnostics).getByText('chat pending')).toBeInTheDocument();
  expect(within(diagnostics).getAllByText('false').length).toBeGreaterThan(0);
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle'), { timeout: 2200 });
  const original = vi.mocked(fetch).getMockImplementation();
  vi.mocked(fetch).mockImplementation((path: string, options?: { body?: BodyInit }) => {
    if (String(path).includes('/api/chat')) return Promise.resolve({ ok: false, json: () => Promise.resolve({}) } as Response);
    return original?.(path, options) as ReturnType<typeof fetch>;
  });
  await send('force API error');
  expect(await screen.findByText('The chat request could not complete.')).toBeInTheDocument();
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'error');
  expect(within(screen.getByLabelText('Audio diagnostics')).getByText('Chat request failed')).toBeInTheDocument();
});
test('chat send exits pending on timeout', async () => {
  try {
    render(<App />);
    await screen.findByTestId('avatar-video');
    vi.useFakeTimers();
    const original = vi.mocked(fetch).getMockImplementation();
    vi.mocked(fetch).mockImplementation((path: string, options?: { body?: BodyInit; signal?: AbortSignal }) => {
      if (!String(path).includes('/api/chat')) return original?.(path, options) as ReturnType<typeof fetch>;
      return new Promise((_, reject) => {
        if (options?.signal?.aborted) reject(new DOMException('Aborted', 'AbortError'));
        options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }) as ReturnType<typeof fetch>;
    });
    await send('timeout please');
    await vi.advanceTimersByTimeAsync(45000);
    vi.useRealTimers();
    expect(await screen.findByText('The chat request timed out.')).toBeInTheDocument();
    expect(within(screen.getByLabelText('Audio diagnostics')).getByText('timeout')).toBeInTheDocument();
    expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'error');
  } finally {
    vi.useRealTimers();
  }
});
test('reset stage clears active listening state', async () => {
  render(<App />);
  fireEvent.mouseDown(screen.getByRole('button', { name: /push to talk/i }));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'listening');
  fireEvent.click(within(openAudioControls()).getByRole('button', { name: /reset stage/i }));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle');
});
test('muted, unavailable, error, and timeout speech paths report honestly', async () => {
  render(<App />);
  const controls = openAudioControls();
  fireEvent.click(within(controls).getByRole('button', { name: /mute voice/i }));
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted'));
  fireEvent.click(within(controls).getByRole('button', { name: /unlock\/test voice/i }));
  expect((await within(screen.getByLabelText('Audio diagnostics')).findAllByText('Muted state prevented speech playback.')).length).toBeGreaterThan(0);
  expect(speechSynthesis.speak).not.toHaveBeenCalled();
  expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('false').length).toBeGreaterThan(0);
  cleanup();
  mockRuntime();
  vi.stubGlobal('speechSynthesis', undefined);
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /unlock\/test voice/i }));
  expect(await screen.findByText(/Text-to-speech is unavailable/i)).toBeInTheDocument();
  expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('Speech synthesis is unavailable.').length).toBeGreaterThan(0);
  cleanup();
  mockRuntime();
  vi.stubGlobal('speechSynthesis', { getVoices: () => [], speak: vi.fn((utterance: { onerror?: () => void }) => utterance.onerror?.()), pause: vi.fn(), resume: vi.fn(), cancel: vi.fn() });
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /unlock\/test voice/i }));
  expect((await within(screen.getByLabelText('Audio diagnostics')).findAllByText('Speech playback failed.')).length).toBeGreaterThan(0);
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle');
});
test('speech never firing onend times out and returns avatar idle', async () => {
  try {
    vi.stubGlobal('speechSynthesis', {
      getVoices: () => [maleVoice, femaleVoice],
      speak: vi.fn((utterance: { onstart?: () => void }) => {
        spokenUtterance = utterance as unknown as Record<string, unknown>;
        utterance.onstart?.();
      }),
      pause: vi.fn(),
      resume: vi.fn(),
      cancel: vi.fn()
    });
    render(<App />);
    await screen.findByTestId('avatar-video');
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: /unlock\/test voice/i }));
    expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'speaking');
    await vi.advanceTimersByTimeAsync(20000);
    vi.useRealTimers();
    expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('Speech playback timed out after 20000ms.').length).toBeGreaterThan(0);
    expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'idle');
    expect(within(screen.getByLabelText('Audio diagnostics')).getAllByText('true').length).toBeGreaterThan(0);
  } finally {
    vi.useRealTimers();
  }
});
test('copy controls write individual messages and transcripts', async () => {
  render(<App />);
  await send('hello XV8');
  await screen.findByText(/Echo: hello XV8/i);
  const userCopyButtons = screen.getAllByRole('button', { name: /copy you message/i });
  fireEvent.click(userCopyButtons[userCopyButtons.length - 1]);
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('You:\nhello XV8'));
  const assistantCopyButtons = screen.getAllByRole('button', { name: /copy xv8 message/i });
  fireEvent.click(assistantCopyButtons[assistantCopyButtons.length - 1]);
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('XV8:\nEcho: hello XV8'));
  fireEvent.click(screen.getByRole('button', { name: /^Info/i }));
  fireEvent.click((await screen.findAllByRole('button', { name: /copy transcript$/i }))[0]);
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('# XV8 Conversation Transcript'));
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('hello XV8'));
});
test('avatar speaker and volume controls update muted volume preference', async () => {
  render(<App />);
  const controls = openAudioControls();
  fireEvent.change(within(controls).getByLabelText('Voice volume'), { target: { value: '42' } });
  expect(window.localStorage.getItem('x8.voiceVolume')).toBe('42');
  fireEvent.change(within(controls).getByLabelText('Voice volume'), { target: { value: '0' } });
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted');
  expect(window.localStorage.getItem('x8.voiceVolume')).toBe('0');
});
test('uploads file content as a compact chip before sending', async () => {
  render(<App />);
  const input = screen.getByLabelText('Attach file input') as HTMLInputElement;
  const file = new File(['hello'], 'notes.txt', { type: 'text/plain' });
  fireEvent.change(input, { target: { files: [file] } });
  const tray = await screen.findByLabelText('Attached files');
  expect(within(tray).getByText(/notes.txt/i)).toBeInTheDocument();
  expect(await within(tray).findByText(/uploaded/i)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Message XV8'), { target: { value: 'use this reference' } });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
  expect(await screen.findByText(/Echo: use this reference/i)).toBeInTheDocument();
});
