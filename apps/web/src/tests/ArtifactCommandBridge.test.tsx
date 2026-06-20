import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from '../app/App';

vi.mock('../components/cockpit/CodeEditor', () => ({
  CodeEditor: ({
    value,
    onChange,
    highlightLineStart,
    highlightLineEnd,
    diffEntries = []
  }: {
    value: string;
    onChange: (next: string) => void;
    highlightLineStart?: number;
    highlightLineEnd?: number;
    diffEntries?: Array<{ line_number: number; kind: string }>;
  }) => (
    <div
      data-testid="mock-code-editor"
      data-highlight-line-start={highlightLineStart || ''}
      data-highlight-line-end={highlightLineEnd || ''}
      data-diff-kinds={diffEntries.map((entry) => `${entry.line_number}:${entry.kind}`).join('|')}
    >
      <textarea aria-label="Artifact page code editor" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}));

const artifactHtml = [
  '<html>',
  '<head><title>Inline website preview</title></head>',
  '<body>',
  '  <nav class="topbar">',
  '    <strong>Inline website preview</strong>',
  '  </nav>',
  '  <section class="hero">',
  '    <h1>Inline website preview</h1>',
  '    <a href="#contact" class="button primary">Request service</a>',
  '  </section>',
  '</body>',
  '</html>'
].join('\n');

const artifactCss = [
  'html,body{margin:0;min-height:100%;font-family:Inter,system-ui,Segoe UI,sans-serif;background:#1b0909;color:#fff7ed;}',
  '.site-shell{min-height:100vh;background:radial-gradient(circle at top left,#e11d2444,transparent 34%),linear-gradient(135deg,#1b0909,#2a1010);}',
  '.button{border-radius:999px;padding:13px 19px;text-decoration:none;font-weight:900;}',
  '.primary{background:#ffd21f;color:#1b1200;}',
  '.secondary{border:1px solid rgba(255,255,255,.26);color:#fff7ed;}'
].join('\n');

let chatBodies: Array<Record<string, unknown>> = [];

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
          assets: [],
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

function openHistory(artifactCard: HTMLElement) {
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'History/Log' }));
}

test('background locate asks what to change and stores pending revision', async () => {
  const artifactCard = await generateArtifact();
  await send('what is the color for the background?');
  expect(chatBodies).toHaveLength(0);
  expect(await screen.findByText(/Current colors include/i)).toBeInTheDocument();
  expect(screen.getByText(/black \(#1b0909\)/i)).toBeInTheDocument();
  expect(screen.getByText(/red \(#e11d24\)/i)).toBeInTheDocument();
  expect(screen.queryByText(/The current value is/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/from html,body/i)).not.toBeInTheDocument();
  expect(screen.queryByTestId('inline-receipt-card')).not.toBeInTheDocument();
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /styles\.css/i }));
  const codeEditor = within(artifactCard).getByTestId('mock-code-editor');
  expect(codeEditor).toHaveAttribute('data-highlight-line-start', '1');
  expect(codeEditor).toHaveAttribute('data-highlight-line-end', '4');
  expect(codeEditor).toHaveAttribute('data-diff-kinds', '');
  openHistory(artifactCard);
  expect(within(artifactCard).getByTestId('artifact-pending-revision')).toHaveTextContent(/background_color/);
  expect(within(artifactCard).getByTestId('artifact-pending-revision')).toHaveTextContent(/styles\.css/);
});

test('I want blue after background locate edits styles.css and refreshes preview', async () => {
  const artifactCard = await generateArtifact();
  await send('what controls the background color?');
  await send('I want blue');
  expect(chatBodies).toHaveLength(0);
  expect(await screen.findByText(/I changed the background to blue in styles\.css and refreshed the preview\./i)).toBeInTheDocument();
  expect(screen.queryByTestId('inline-receipt-card')).not.toBeInTheDocument();
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /styles\.css/i }));
  const mockEditor = within(artifactCard).getByTestId('mock-code-editor');
  expect(mockEditor.getAttribute('data-diff-kinds') || '').toMatch(/1:modified_old/);
  expect(mockEditor.getAttribute('data-diff-kinds') || '').toMatch(/1:modified_new/);
  const cssEditor = within(artifactCard).getByLabelText('Artifact page code editor') as HTMLTextAreaElement;
  expect(cssEditor.value).toContain('#0b3b8f');
});

test('button color locate asks what to change', async () => {
  const artifactCard = await generateArtifact();
  await send('show me where the button color is controlled');
  expect(chatBodies).toHaveLength(0);
  expect(await screen.findByText(/What would you like to change it to\?/i)).toBeInTheDocument();
  openHistory(artifactCard);
  expect(within(artifactCard).getByTestId('artifact-pending-revision')).toHaveTextContent(/button_color/);
});

test('make it purple with white text edits button css', async () => {
  const artifactCard = await generateArtifact();
  await send('show me where the button color is controlled');
  await send('make it purple with white text');
  expect(chatBodies).toHaveLength(0);
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /styles\.css/i }));
  const cssEditor = within(artifactCard).getByLabelText('Artifact page code editor') as HTMLTextAreaElement;
  expect(cssEditor.value).toContain('.primary{background:#6d28d9;color:#ffffff;}');
});

test('website-name locate asks what to change then applies Harrys Hot Dogs', async () => {
  const artifactCard = await generateArtifact();
  await send('show me where to edit the main website name');
  expect(await screen.findByText(/What would you like to change it to\?/i)).toBeInTheDocument();
  openHistory(artifactCard);
  expect(within(artifactCard).getByTestId('artifact-pending-revision')).toHaveTextContent(/website_name/);
  await send("Harry's Hot Dogs");
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /index\.html/i }));
  const htmlEditor = within(artifactCard).getByLabelText('Artifact page code editor') as HTMLTextAreaElement;
  expect(htmlEditor.value).toContain("Harry's Hot Dogs");
});

test('direct change background to blue edits without asking', async () => {
  const artifactCard = await generateArtifact();
  await send('change the background to blue');
  expect(chatBodies).toHaveLength(0);
  expect(await screen.findByText(/I changed the background to blue in styles\.css and refreshed the preview\./i)).toBeInTheDocument();
  expect(screen.queryByText(/What would you like to change it to\?/i)).not.toBeInTheDocument();
  expect(screen.queryByTestId('inline-receipt-card')).not.toBeInTheDocument();
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /styles\.css/i }));
  expect(within(artifactCard).getByTestId('mock-code-editor').getAttribute('data-diff-kinds') || '').toMatch(/modified_new/);
});

test('sandbox edits do not create new artifact packages', async () => {
  await generateArtifact();
  await send('what controls the background color?');
  await send('I want blue');
  await send('show me where the button color is controlled');
  await send('make it purple with white text');
  expect(screen.getAllByTestId('inline-artifact-card')).toHaveLength(1);
});

test('diff history marks added lines green and deleted lines red', async () => {
  const artifactCard = await generateArtifact();
  await send('what controls the background color?');
  await send('I want blue');
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Code' }));
  fireEvent.click(within(artifactCard).getByRole('button', { name: /styles\.css/i }));
  expect(within(artifactCard).getByTestId('mock-code-editor').getAttribute('data-diff-kinds') || '').toMatch(/modified_new/);
  openHistory(artifactCard);
  const diffPanel = within(artifactCard).getByTestId('artifact-diff-history');
  expect(within(diffPanel).getAllByText(/\+ /i).length).toBeGreaterThan(0);
  expect(within(diffPanel).getAllByText(/- /i).length).toBeGreaterThan(0);
  expect(diffPanel.querySelectorAll('.artifactDiffLine.added').length).toBeGreaterThan(0);
  expect(diffPanel.querySelectorAll('.artifactDiffLine.deleted').length).toBeGreaterThan(0);
});

test('editing after approval disables Apply until re-approved', async () => {
  const artifactCard = await generateArtifact();
  const applyBtn = within(artifactCard).getByRole('button', { name: 'Apply' });
  fireEvent.click(within(artifactCard).getByRole('button', { name: 'Approve' }));
  await send('change the background to blue');
  await waitFor(() => expect(applyBtn).toBeDisabled());
});

test('no Kernel limitations card appears for active artifact revision commands', async () => {
  await generateArtifact();
  await send('what controls the background color?');
  await send('I want blue');
  await send('show me where to edit the main website name');
  await send("Harry's Hot Dogs");
  expect(chatBodies).toHaveLength(0);
  expect(screen.queryByText('Kernel limitations')).not.toBeInTheDocument();
});

test('includes active artifact context with normal non-intercepted chat', async () => {
  await generateArtifact();
  await send('tell me something unrelated');
  await waitFor(() => expect(chatBodies).toHaveLength(1));
  const artifactContext = chatBodies[0].artifact_context as Record<string, unknown>;
  expect(artifactContext).toBeTruthy();
  expect(Array.isArray(artifactContext.available_files)).toBe(true);
});
