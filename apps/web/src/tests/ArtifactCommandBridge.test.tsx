import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from '../app/App';

vi.mock('../components/cockpit/CodeEditor', () => ({
  CodeEditor: ({ value, onChange }: { value: string; onChange: (next: string) => void }) => (
    <textarea aria-label="Artifact page code editor" value={value} onChange={(event) => onChange(event.target.value)} />
  )
}));

const artifactHtml = [
  '<main class="site-shell">',
  '  <nav class="topbar">',
  '    <strong>Inline website preview</strong>',
  '    <span>Fresh service · Fast response · Local business</span>',
  '  </nav>',
  '  <section class="hero">',
  '    <p class="eyebrow">XV8 live artifact preview</p>',
  '    <h1>Inline website preview</h1>',
  '    <div class="hero-actions">',
  '      <a href="#contact" class="button primary">Request service</a>',
  '      <a href="#menu" class="button secondary">View highlights</a>',
  '    </div>',
  '  </section>',
  '</main>'
].join('\n');

const artifactCss = [
  'html,body{margin:0;min-height:100%;font-family:Inter,system-ui,Segoe UI,sans-serif;background:#1b0909;color:#fff7ed;}',
  '.site-shell{min-height:100vh;background:radial-gradient(circle at top left,#e11d2444,transparent 34%),linear-gradient(135deg,#1b0909,#2a1010);}',
  '.topbar{display:flex;justify-content:space-between;gap:24px;padding:22px 44px;border-bottom:1px solid rgba(255,255,255,.14);background:rgba(0,0,0,.22);}',
  '.topbar strong{color:#ffd21f;font-size:1.1rem;letter-spacing:.03em;}',
  '.eyebrow{color:#ffd21f;font-weight:900;text-transform:uppercase;letter-spacing:.14em;}',
  '.button{border-radius:999px;padding:13px 19px;text-decoration:none;font-weight:900;}',
  '.primary{background:#ffd21f;color:#1b1200;}',
  '.secondary{border:1px solid rgba(255,255,255,.26);color:#fff7ed;}'
].join('\n');

let chatBodies: Array<Record<string, unknown>> = [];
let artifactPreviewBodies: Array<Record<string, unknown>> = [];

function ok(data: unknown, status = 'ok', receipts: unknown[] = []) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true, status, message: status, data, receipts }) } as Response);
}

function mockRuntime() {
  vi.stubGlobal('fetch', vi.fn((path: string, options?: { body?: BodyInit; method?: string }) => {
    const body = typeof options?.body === 'string' ? JSON.parse(options.body) : {};
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
    if (String(path).includes('/api/chat')) {
      chatBodies.push(body as Record<string, unknown>);
      return ok({
        session_id: 'sess_artifact_bridge',
        message_id: `msg_${chatBodies.length}`,
        assistant_message: {
          role: 'assistant',
          content: 'Kernel fallback was used.',
          cards: [{ type: 'info', title: 'Kernel limitations', status: 'unavailable', summary: 'Kernel fallback was used.', payload: {} }]
        },
        receipt: { receipt_id: 'rcpt_chat', action_type: 'prompt_round_trip', status: 'passed', model: '', limitations: [] },
        attachments: []
      }, 'passed');
    }
    if (String(path).includes('/api/artifacts/preview')) {
      artifactPreviewBodies.push(body as Record<string, unknown>);
      return ok({
        title: 'Inline website preview',
        html: artifactHtml,
        css: artifactCss,
        pages: [{ id: 'home', label: 'Home', path: 'index.html', content: artifactHtml }],
        files: [
          { path: 'index.html', content: artifactHtml },
          { path: 'styles.css', content: artifactCss }
        ],
        assets: []
      }, 'created');
    }
    if (String(path).includes('capabilities')) return ok([{ name: 'artifact_preview', status: 'implemented', summary: '', requires_approval: false }]);
    if (String(path).includes('integrations')) return ok([{ name: 'email', status: 'disabled', summary: '' }]);
    if (String(path).includes('workspace/files')) return ok([{ path: 'README.md', kind: 'file', size: 10 }]);
    if (String(path).includes('workspace/read')) return ok({ path: 'README.md', content: '# XV8\n', line_count: 1 });
    if (String(path).includes('docker/presets')) return ok(['api_tests']);
    if (String(path).includes('github/ops/auth-status')) return ok({ token_configured: true, owner_configured: true, owner: 'otiseduncan', default_visibility: 'private' });
    if (String(path).includes('github/ops/status')) return ok({ is_repo: true, branch: 'main', remote_origin_url: 'https://example.test/repo.git', dirty: false, changed_files: [] });
    if (String(path).includes('github/status')) return ok({ status: 'not_configured' });
    if (String(path).includes('search/status')) return ok({ status: 'unavailable' });
    if (String(path).includes('images/status')) return ok({ status: 'unavailable' });
    if (String(path).includes('local-bridge/status')) return ok({ bridge_reachable: false });
    if (String(path).includes('local-system/status')) return ok({});
    if (String(path).includes('config-import')) return ok({ x7_import_status: 'available', x7_files_found: 1, x6_import_status: 'available', x6_files_found: 1, github_config_found_in_x7: true, comfyui_config_found_in_x6: true, search_config_found_in_x6: true });
    if (String(path).includes('/api/avatar/manifest')) return ok({ default_asset: '/avatar/fallback.svg' });
    if (String(path).includes('speech/status')) return ok({ status: 'browser_fallback' });
    if (String(path).includes('models/status')) return ok({ model_ready: false, selected_model: '', ollama_reachable: false });
    if (String(path).includes('memory/status')) return ok({});
    if (String(path).includes('brain/status')) return ok({ active_focus: 'Artifact bridge' });
    if (String(path).includes('receipts')) return ok([]);
    if (String(path).includes('sessions')) return ok([]);
    if (String(path).includes('self-build/trust-status')) return ok({});
    return ok({});
  }));
}

beforeEach(() => {
  window.localStorage.clear();
  chatBodies = [];
  artifactPreviewBodies = [];
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal('confirm', vi.fn(() => true));
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  mockRuntime();
  class MockRecognition {
    continuous = false;
    interimResults = false;
    lang = 'en-US';
    onstart: (() => void) | null = null;
    onresult: ((event: { results: Array<Array<{ transcript: string }>> }) => void) | null = null;
    onerror: ((event: { error: string }) => void) | null = null;
    onend: (() => void) | null = null;
    start() { this.onstart?.(); }
    stop() { this.onend?.(); }
  }
  vi.stubGlobal('SpeechRecognition', MockRecognition);
  vi.stubGlobal('webkitSpeechRecognition', MockRecognition);
  vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function Utterance(this: Record<string, unknown>, text: string) { this.text = text; }));
  vi.stubGlobal('speechSynthesis', { getVoices: () => [], speak: vi.fn(), pause: vi.fn(), resume: vi.fn(), cancel: vi.fn() });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function send(text: string) {
  fireEvent.change(screen.getByLabelText('Message XV8'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));
}

async function generateArtifact() {
  render(<App />);
  await send('make a simple HTML website preview');
  return await screen.findByTestId('inline-artifact-card');
}

test('includes active artifact context with normal chat after package generation', async () => {
  await generateArtifact();
  await send('tell me something unrelated');
  await waitFor(() => expect(chatBodies).toHaveLength(1));
  expect(screen.getAllByText('Kernel fallback was used.').length).toBeGreaterThan(0);
  expect(chatBodies).toHaveLength(1);
  const artifactContext = chatBodies[0].artifact_context as Record<string, unknown>;
  expect(artifactContext).toBeTruthy();
  expect((artifactContext.package_id as string) || '').not.toBe('');
  expect(artifactContext.active_file_path).toBeDefined();
  expect(Array.isArray(artifactContext.available_files)).toBe(true);
});

test('background locator request routes to active artifact and highlights styles without kernel fallback', async () => {
  const artifactCard = await generateArtifact();
  await send('show me the lines of text that control the color of the background');
  expect(chatBodies).toHaveLength(0);
  expect(within(artifactCard).getByText(/Editing/i)).toBeInTheDocument();
  expect(within(artifactCard).getByTestId('artifact-highlight-summary')).toHaveTextContent(/styles\.css/);
  expect(await screen.findByText(/background styling is in styles\.css/i)).toBeInTheDocument();
  expect(screen.queryByText('Kernel limitations')).not.toBeInTheDocument();
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
});

test('website name locator request highlights index html and does not generate a new artifact', async () => {
  const artifactCard = await generateArtifact();
  await send('show me where to edit the main website name');
  expect(chatBodies).toHaveLength(0);
  expect(within(artifactCard).getByTestId('artifact-highlight-summary')).toHaveTextContent(/index\.html/);
  expect(await screen.findByText(/Edit the main website name in index\.html/i)).toBeInTheDocument();
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
});

test('javascript follow-up for special of the day is intercepted locally and never falls to kernel limitations', async () => {
  const artifactCard = await generateArtifact();
  await send('show me the JavaScript that changes the special of the day');
  expect(chatBodies).toHaveLength(0);
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
  expect(within(artifactCard).getByRole('button', { name: 'Code' })).toHaveClass('active');
  expect(await screen.findByText(/This package currently has no separate JavaScript file or click-handler code\./i)).toBeInTheDocument();
  expect(screen.queryByText('Kernel limitations')).not.toBeInTheDocument();
});

test('main website name edit routes to artifact_edit_active_package using the exact rename prompt', async () => {
  const artifactCard = await generateArtifact();
  await send("change the main website name to Harry's Hot Dogs");
  expect(chatBodies).toHaveLength(0);
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
  expect((await screen.findAllByText(/updated the main website name to Harry's Hot Dogs in index\.html/i)).length).toBeGreaterThan(0);
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /index\.html/i }));
  const htmlEditor = within(artifactCard).getByLabelText('Artifact page code editor') as HTMLTextAreaElement;
  expect(htmlEditor.value).toContain("Harry's Hot Dogs");
  expect(screen.queryByText('Kernel limitations')).not.toBeInTheDocument();
});

test('preview refresh follow-up routes to artifact_preview_refresh and does not generate a new artifact', async () => {
  await generateArtifact();
  await send('refresh the preview');
  expect(chatBodies).toHaveLength(0);
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
  expect(await screen.findByText(/I refreshed the preview for the active package\./i)).toBeInTheDocument();
  expect(screen.queryByText('Kernel limitations')).not.toBeInTheDocument();
});

test('color and button text edit requests update the active package instead of generating a new artifact', async () => {
  const artifactCard = await generateArtifact();
  await send('change the colors of the website to black and purple');
  expect(chatBodies).toHaveLength(0);
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  const cssEditor = within(artifactCard).getByLabelText('Artifact page code editor') as HTMLTextAreaElement;
  expect(cssEditor.value).toContain('#05030a');
  expect(cssEditor.value).toContain('#6d28d9');
  await send('change the button text to Book now');
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /index\.html/i }));
  expect((within(artifactCard).getByLabelText('Artifact page code editor') as HTMLTextAreaElement).value).toContain('Book now');
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
  expect(screen.queryByText('Kernel limitations')).not.toBeInTheDocument();
});
