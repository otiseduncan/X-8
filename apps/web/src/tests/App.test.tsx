import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from '../app/App';
import { AvatarStage, selectAvatarAsset } from '../app/AssistantComponents';

vi.mock('../components/cockpit/CodeEditor', () => ({
  CodeEditor: ({ value }: { value: string }) => <pre aria-label="Code editor">{value}</pre>
}));

let recognitionInstance: {
  onstart: (() => void) | null;
  onresult: ((event: { results: Array<Array<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function mockRuntime() {
  vi.stubGlobal('fetch', (path: string, options?: { body?: BodyInit }) => {
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
                                      : String(path).includes('attachments')
                                        ? { attachment_id: 'att_test', filename: 'notes.txt', mime_type: 'text/plain', size_bytes: 5, status: 'uploaded', extracted_text: 'hello', content_extractable: true }
                                        : String(path).includes('sessions')
                                          ? []
                                          : String(path).includes('models/status')
                                            ? { model_ready: false, selected_model: '', ollama_reachable: false }
                                            : String(path).includes('receipts')
                                              ? []
                                      : String(path).includes('chat')
                                        ? {
                                            session_id: 'sess_test',
                                            message_id: 'msg_reply',
                                            assistant_message: {
                                              role: 'assistant',
                                              content: `Echo: ${text.message}`,
                                              cards: [{ type: 'info', title: 'Kernel limitations', status: 'unavailable', summary: 'Kernel fallback was used.', payload: {} }]
                                            },
                                            receipt: { receipt_id: 'rcpt_chat', action_type: 'prompt_round_trip', status: 'unavailable', model: '', limitations: [] },
                                            attachments: text.attachments?.map((attachment: Record<string, unknown>) => ({ ...attachment, status: 'uploaded' })) || []
                                          }
                                        : [{ name: 'Product Lead', responsibility: 'Owns value and scope.', output_style: 'Concise' }];
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', message: 'ok', receipts: [], data }) });
  });
}

beforeEach(() => {
  window.localStorage.clear();
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
    getVoices: () => [{ name: 'Google US English Female', lang: 'en-US' }],
    speak: (utterance: { onstart?: () => void; onend?: () => void }) => {
      utterance.onstart?.();
    },
    pause: vi.fn(),
    resume: vi.fn(),
    cancel: vi.fn()
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function send(text: string) {
  fireEvent.change(screen.getByLabelText('Message XV8'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
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
  expect(within(screen.getByLabelText('Avatar audio controls')).getByRole('button', { name: /mute voice/i })).toBeInTheDocument();
  expect(within(screen.getByLabelText('Avatar audio controls')).getByLabelText('Voice volume')).toBeInTheDocument();
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
  expect(screen.getByRole('button', { name: /copy transcript$/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /copy transcript with receipts/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /download transcript/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  expect(await screen.findByText('Project File Tree')).toBeInTheDocument();
  expect(screen.getByText('Voice preference')).toBeInTheDocument();
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

test('renders inline research and image cards honestly', async () => {
  render(<App />);
  await send('search with SearXNG for XV8');
  expect(await screen.findByTestId('inline-research-card')).toBeInTheDocument();
  expect(screen.queryByText('SearXNG Panel')).not.toBeInTheDocument();

  await send('generate an image of a console');
  expect(await screen.findByTestId('inline-image-card')).toBeInTheDocument();
  expect(screen.queryByText('Image Studio')).not.toBeInTheDocument();
});

test('reviews transcript before sending and sends it as normal chat', async () => {
  render(<App />);
  fireEvent.mouseDown(screen.getByRole('button', { name: /push to talk/i }));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'listening');
  recognitionInstance.onresult?.({ results: [[{ transcript: 'open README.md' }]] });
  await waitFor(() => expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'thinking'));
  expect(await screen.findByLabelText('Transcript preview')).toBeInTheDocument();
  expect(screen.getByText('open README.md')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /send transcript/i }));
  expect(await screen.findByTestId('inline-file-card')).toBeInTheDocument();
});

test('shows permission denied and unavailable speech states honestly', async () => {
  render(<App />);
  fireEvent.mouseDown(screen.getByRole('button', { name: /push to talk/i }));
  recognitionInstance.onerror?.({ error: 'not-allowed' });
  expect((await screen.findAllByText(/Microphone permission was denied/i)).length).toBeGreaterThan(0);

  vi.stubGlobal('SpeechRecognition', undefined);
  vi.stubGlobal('webkitSpeechRecognition', undefined);
  render(<App />);
  const pttButtons = screen.getAllByRole('button', { name: /push to talk/i });
  fireEvent.mouseDown(pttButtons[pttButtons.length - 1]);
  expect((await screen.findAllByText(/Browser Web Speech API is unavailable/i)).length).toBeGreaterThan(0);
});

test('TTS can speak, creates receipts, and mute stops output', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /settings/i }));
  fireEvent.click(await screen.findByRole('button', { name: /test voice/i }));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'speaking');
  fireEvent.click(screen.getByRole('button', { name: /^Info/i }));
  expect((await screen.findAllByText(/speech_output_started/i)).length).toBeGreaterThan(0);
  fireEvent.click(within(screen.getByLabelText('Avatar audio controls')).getByRole('button', { name: /mute voice/i }));
  await waitFor(() => expect(screen.getAllByText(/speech_output_stopped/i).length).toBeGreaterThan(0));
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted');
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
  fireEvent.click(await screen.findByRole('button', { name: /copy transcript$/i }));
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('# XV8 Conversation Transcript'));
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('## User\n\nhello XV8'));
});

test('avatar speaker and volume controls update muted volume preference', async () => {
  render(<App />);
  const controls = screen.getByLabelText('Avatar audio controls');
  fireEvent.change(within(controls).getByLabelText('Voice volume'), { target: { value: '42' } });
  expect(window.localStorage.getItem('x8.voiceVolume')).toBe('42');
  fireEvent.change(within(controls).getByLabelText('Voice volume'), { target: { value: '0' } });
  expect(screen.getByTestId('avatar-stage')).toHaveAttribute('data-avatar-state', 'muted');
  expect(window.localStorage.getItem('x8.voiceVolume')).toBe('0');
});

test('avatar manifest maps states to the expected video assets', () => {
  const manifest = {
    version: '1.0',
    defaultAvatar: 'xoduz',
    assets: [
      { id: 'idle', label: 'Idle', type: 'video', src: '/avatar/xoduz-idle.mp4', states: ['idle'], loop: true, muted: true },
      { id: 'thinking', label: 'Thinking', type: 'video', src: '/avatar/xoduz-thinking.mp4', states: ['thinking', 'listening'], loop: true, muted: true },
      { id: 'speaking', label: 'Speaking', type: 'video', src: '/avatar/xoduz-speaking.mp4', states: ['speaking'], loop: true, muted: true }
    ],
    fallback: { type: 'generated', label: 'Fallback X avatar', src: '/avatar/fallback.svg' }
  };
  expect(selectAvatarAsset(manifest, 'idle')?.src).toBe('/avatar/xoduz-idle.mp4');
  expect(selectAvatarAsset(manifest, 'listening')?.src).toBe('/avatar/xoduz-thinking.mp4');
  expect(selectAvatarAsset(manifest, 'thinking')?.src).toBe('/avatar/xoduz-thinking.mp4');
  expect(selectAvatarAsset(manifest, 'speaking')?.src).toBe('/avatar/xoduz-speaking.mp4');
  expect(selectAvatarAsset(manifest, 'error')?.src).toBe('/avatar/xoduz-idle.mp4');
});

test('avatar falls back if the active video fails to load', async () => {
  render(<AvatarStage state="idle" />);
  const video = await screen.findByTestId('avatar-video');
  fireEvent.error(video);
  expect(await screen.findByTestId('avatar-fallback')).toBeInTheDocument();
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
