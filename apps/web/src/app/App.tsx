import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { AvatarStage } from './AssistantComponents';
import type { AvatarRuntimeState } from './AssistantComponents';

type ChatRole = 'assistant' | 'user' | 'system';
type PreviewMode = 'code' | 'preview';

interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  createdAt: string;
}

function nowId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function textFromPayload(payload: unknown): string {
  if (!payload || typeof payload !== 'object') return String(payload || 'No response payload returned.');
  const root = payload as Record<string, unknown>;
  const data = root.data && typeof root.data === 'object' ? (root.data as Record<string, unknown>) : root;
  const assistant = data.assistant_message && typeof data.assistant_message === 'object' ? (data.assistant_message as Record<string, unknown>) : undefined;
  const visible = data.visible && typeof data.visible === 'object' ? (data.visible as Record<string, unknown>) : undefined;
  const candidates = [assistant?.content, assistant?.text, data.text, data.answer, data.response, data.message, data.content, data.output, visible?.text, visible?.content, root.message, root.status];
  const direct = candidates.find((item) => typeof item === 'string' && item.trim().length > 0);
  if (typeof direct === 'string') return direct;
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return 'Response could not be displayed.';
  }
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json() as Promise<T>;
}

async function getJsonWithRetry<T>(url: string, attempts = 3, delayMs = 700): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await getJson<T>(url);
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
  }
  throw lastError instanceof Error ? lastError : new Error(`${url} unavailable`);
}

async function sendMessage(message: string) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, attachments: [] })
  });
  const payload = await response.json().catch(() => ({ status: response.statusText }));
  if (!response.ok) throw new Error(textFromPayload(payload));
  return payload;
}

async function readWorkspaceFile(path: string) {
  const response = await fetch('/api/workspace/read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });
  const payload = await response.json().catch(() => ({ detail: response.statusText }));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'File read failed.');
  const data = payload.data && typeof payload.data === 'object' ? (payload.data as Record<string, unknown>) : {};
  return String(data.content || '');
}

function previewUrl(path: string, stamp: number) {
  const params = new URLSearchParams({ path, t: String(stamp) });
  return `/api/workspace/preview?${params.toString()}`;
}

export function App() {
  const entryRef = useRef<HTMLTextAreaElement>(null);
  const avatarResetRef = useRef<number | null>(null);
  const [entry, setEntry] = useState('');
  const [busy, setBusy] = useState(false);
  const [runtimeStatus, setRuntimeStatus] = useState('checking runtime');
  const [modelStatus, setModelStatus] = useState('checking model');
  const [avatarState, setAvatarState] = useState<AvatarRuntimeState>('idle');
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewMode, setPreviewMode] = useState<PreviewMode>('preview');
  const [previewPath, setPreviewPath] = useState('index.html');
  const [previewCode, setPreviewCode] = useState('Open a sandbox file to view its code here.');
  const [previewStamp, setPreviewStamp] = useState(Date.now());
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'welcome', role: 'assistant', text: 'Ready. Exodus avatar restored. Ask me what you want to build, inspect, search, preview, or fix.', createdAt: new Date().toISOString() }
  ]);

  const canSend = useMemo(() => entry.trim().length > 0 && !busy, [busy, entry]);
  const avatarCaption = useMemo(() => {
    if (avatarState === 'thinking') return 'Thinking through the request';
    if (avatarState === 'responded') return 'Response ready';
    if (avatarState === 'error') return 'Needs attention';
    return 'Standing by';
  }, [avatarState]);

  useEffect(() => {
    getJsonWithRetry<Record<string, unknown>>('/api/health').then((health) => setRuntimeStatus(`API ${String(health.status || 'ok')}`)).catch(() => { setRuntimeStatus('API unavailable'); setAvatarState('error'); });
    getJsonWithRetry<Record<string, unknown>>('/api/models/status')
      .then((model) => {
        const data = model.data && typeof model.data === 'object' ? (model.data as Record<string, unknown>) : model;
        const selectedModel = String(data.selected_model || data.default_chat_model || data.model || 'model');
        const readiness = data.model_ready === false ? 'unavailable' : String(model.status || 'ready');
        setModelStatus(`${selectedModel} / ${readiness}`);
      })
      .catch(() => setModelStatus('model status unavailable'));
  }, []);

  useEffect(() => () => { if (avatarResetRef.current) window.clearTimeout(avatarResetRef.current); }, []);

  useEffect(() => {
    if (!previewOpen || previewMode !== 'code') return;
    readWorkspaceFile(previewPath).then(setPreviewCode).catch((error) => setPreviewCode(error instanceof Error ? error.message : 'Preview code unavailable.'));
  }, [previewOpen, previewMode, previewPath, previewStamp]);

  function flashAvatar(state: AvatarRuntimeState, resetTo: AvatarRuntimeState = 'idle') {
    if (avatarResetRef.current) window.clearTimeout(avatarResetRef.current);
    setAvatarState(state);
    if (state !== 'thinking' && state !== 'listening' && state !== 'speaking') avatarResetRef.current = window.setTimeout(() => setAvatarState(resetTo), 1800);
  }

  function append(message: Omit<ChatMessage, 'id' | 'createdAt'>) {
    setMessages((current) => [...current, { ...message, id: nowId(), createdAt: new Date().toISOString() }]);
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const message = entry.trim();
    if (!message || busy) return;
    setEntry('');
    append({ role: 'user', text: message });
    setBusy(true);
    setAvatarState('thinking');
    try {
      const payload = await sendMessage(message);
      append({ role: 'assistant', text: textFromPayload(payload) });
      flashAvatar('responded');
    } catch (error) {
      append({ role: 'system', text: error instanceof Error ? error.message : 'Chat request failed.' });
      flashAvatar('error');
    } finally {
      setBusy(false);
      window.setTimeout(() => entryRef.current?.focus(), 0);
    }
  }

  function openCockpit() {
    const target = `${window.location.protocol}//${window.location.hostname}:6022/`;
    window.open(target, 'x8-cockpit', 'noopener,noreferrer,width=1460,height=920');
  }

  function refreshPreview() {
    setPreviewOpen(true);
    setPreviewStamp(Date.now());
  }

  return (
    <main style={styles.shell}>
      <header style={styles.header}>
        <div>
          <p style={styles.kicker}>X8 Chat</p>
          <h1 style={styles.title}>Xoduz Operator Chat</h1>
          <p style={styles.subtitle}>Chat stays clean. Cockpit stays on port 6022. Preview can open directly in this chat lane.</p>
        </div>
        <div style={styles.headerActions}>
          <span style={styles.pill}>{runtimeStatus}</span>
          <span style={styles.pill}>{modelStatus}</span>
          <button style={styles.secondaryButton} type="button" onClick={() => { setPreviewOpen((value) => !value); setPreviewStamp(Date.now()); }}>Preview</button>
          <button style={styles.secondaryButton} type="button" onClick={openCockpit}>Open Cockpit</button>
        </div>
      </header>

      <section style={{ ...styles.workspace, ...(previewOpen ? styles.workspaceWithPreview : {}) }}>
        <aside style={styles.avatarRail} aria-label="Exodus avatar presence">
          <div style={styles.avatarCard}>
            <AvatarStage state={avatarState} />
            <div style={styles.avatarIdentity}>
              <p style={styles.kicker}>Exodus presence</p>
              <h2 style={styles.avatarTitle}>Xoduz</h2>
              <p style={styles.avatarState}>State: {avatarState}</p>
              <p style={styles.avatarCaption}>{avatarCaption}</p>
            </div>
          </div>
          <div style={styles.avatarStatusGrid}><span style={styles.statusChip}>Chat: {busy ? 'working' : 'ready'}</span><span style={styles.statusChip}>Runtime: {runtimeStatus}</span></div>
        </aside>

        <section style={styles.chatPane}>
          <section style={styles.timeline} aria-live="polite">
            {messages.map((message) => (
              <article key={message.id} style={{ ...styles.message, ...(message.role === 'user' ? styles.userMessage : message.role === 'system' ? styles.systemMessage : styles.assistantMessage) }}>
                <div style={styles.messageMeta}>{message.role} · {new Date(message.createdAt).toLocaleTimeString()}</div>
                <pre style={styles.messageText}>{message.text}</pre>
              </article>
            ))}
            {busy && <article style={{ ...styles.message, ...styles.assistantMessage }}><div style={styles.messageMeta}>assistant</div><pre style={styles.messageText}>Thinking…</pre></article>}
          </section>

          <form style={styles.composer} onSubmit={(event) => void submit(event)}>
            <textarea ref={entryRef} value={entry} onChange={(event) => setEntry(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder="Type a message. Enter sends, Shift+Enter adds a new line." style={styles.textarea} />
            <button style={canSend ? styles.primaryButton : styles.disabledButton} type="submit" disabled={!canSend}>{busy ? 'Working…' : 'Send'}</button>
          </form>
        </section>

        {previewOpen && (
          <aside style={styles.previewPane} aria-label="Chat preview lane">
            <div style={styles.previewHeader}><strong>Preview</strong><button style={styles.closeButton} type="button" onClick={() => setPreviewOpen(false)}>Close</button></div>
            <div style={styles.previewPathRow}><input style={styles.previewInput} value={previewPath} onChange={(event) => setPreviewPath(event.target.value)} placeholder="index.html or README.md" /><button style={styles.secondaryButton} type="button" onClick={refreshPreview}>Refresh</button></div>
            <div style={styles.previewTabs}><button style={previewMode === 'preview' ? styles.activeTab : styles.tab} type="button" onClick={() => { setPreviewMode('preview'); refreshPreview(); }}>Preview</button><button style={previewMode === 'code' ? styles.activeTab : styles.tab} type="button" onClick={() => { setPreviewMode('code'); refreshPreview(); }}>Code</button></div>
            <div style={styles.previewBody}>{previewMode === 'preview' ? <iframe title="Sandbox preview" src={previewUrl(previewPath, previewStamp)} style={styles.previewFrame} /> : <pre style={styles.previewCode}>{previewCode}</pre>}</div>
          </aside>
        )}
      </section>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  shell: { minHeight: '100vh', display: 'grid', gridTemplateRows: 'auto minmax(0, 1fr)', gap: 16, padding: 18, color: '#f5f7fb', background: 'radial-gradient(circle at top left, rgba(0, 212, 255, 0.14), transparent 34%), linear-gradient(135deg, #05070d, #111827 55%, #05070d)' },
  header: { display: 'flex', justifyContent: 'space-between', gap: 14, alignItems: 'center', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 18, padding: '16px 18px', background: 'rgba(5, 7, 13, 0.82)', boxShadow: '0 18px 40px rgba(0,0,0,0.28)' },
  workspace: { minHeight: 0, display: 'grid', gridTemplateColumns: '340px minmax(0, 1fr)', gap: 18 },
  workspaceWithPreview: { gridTemplateColumns: '300px minmax(0, 1fr) minmax(380px, 0.78fr)' },
  avatarRail: { minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 },
  avatarCard: { border: '1px solid rgba(125, 211, 252, 0.18)', borderRadius: 22, padding: 16, background: 'linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(3, 7, 18, 0.96))', boxShadow: '0 22px 44px rgba(0,0,0,0.32)', overflow: 'hidden' },
  avatarIdentity: { marginTop: 14, display: 'grid', gap: 4 },
  avatarTitle: { margin: 0, fontSize: 28, letterSpacing: '-0.04em' },
  avatarState: { margin: 0, color: '#7dd3fc', fontWeight: 800 },
  avatarCaption: { margin: 0, color: '#aeb7c7', lineHeight: 1.45 },
  avatarStatusGrid: { display: 'grid', gap: 8 },
  statusChip: { border: '1px solid rgba(255,255,255,0.1)', borderRadius: 14, padding: '10px 12px', background: 'rgba(15, 23, 42, 0.7)', color: '#dbeafe', fontSize: 12, fontWeight: 700 },
  chatPane: { minHeight: 0, display: 'grid', gridTemplateRows: 'minmax(0, 1fr) auto', gap: 12 },
  kicker: { margin: 0, color: '#7dd3fc', textTransform: 'uppercase', letterSpacing: '0.16em', fontSize: 12, fontWeight: 800 },
  title: { margin: '4px 0 2px', fontSize: 'clamp(1.4rem, 3vw, 2.2rem)' },
  subtitle: { margin: 0, color: '#aeb7c7' },
  headerActions: { display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' },
  pill: { border: '1px solid rgba(125, 211, 252, 0.26)', borderRadius: 999, padding: '8px 10px', color: '#dbeafe', background: 'rgba(14, 165, 233, 0.1)', fontSize: 12, fontWeight: 700 },
  timeline: { minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 12, padding: 4 },
  message: { maxWidth: 980, border: '1px solid rgba(255,255,255,0.12)', borderRadius: 16, padding: 14, boxShadow: '0 14px 34px rgba(0,0,0,0.18)' },
  assistantMessage: { alignSelf: 'flex-start', background: 'rgba(15, 23, 42, 0.84)' },
  userMessage: { alignSelf: 'flex-end', background: 'rgba(30, 64, 175, 0.34)' },
  systemMessage: { alignSelf: 'center', background: 'rgba(127, 29, 29, 0.34)' },
  messageMeta: { marginBottom: 8, color: '#93c5fd', fontSize: 12, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em' },
  messageText: { margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit', lineHeight: 1.48 },
  composer: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 10, border: '1px solid rgba(255,255,255,0.12)', borderRadius: 18, padding: 12, background: 'rgba(5, 7, 13, 0.9)' },
  textarea: { minHeight: 74, resize: 'vertical', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 14, padding: 12, outline: 'none', color: '#f8fafc', background: 'rgba(15, 23, 42, 0.96)', font: 'inherit' },
  primaryButton: { border: 0, borderRadius: 14, padding: '0 22px', color: '#04111f', background: 'linear-gradient(135deg, #7dd3fc, #22d3ee)', fontWeight: 900, cursor: 'pointer' },
  secondaryButton: { border: '1px solid rgba(125, 211, 252, 0.28)', borderRadius: 999, padding: '8px 12px', color: '#e0f2fe', background: 'rgba(14, 165, 233, 0.12)', fontWeight: 800, cursor: 'pointer' },
  disabledButton: { border: 0, borderRadius: 14, padding: '0 22px', color: '#94a3b8', background: 'rgba(148, 163, 184, 0.16)', fontWeight: 900, cursor: 'not-allowed' },
  previewPane: { minHeight: 0, display: 'grid', gridTemplateRows: 'auto auto auto minmax(0, 1fr)', border: '1px solid rgba(125, 211, 252, 0.22)', borderRadius: 18, background: 'rgba(5, 7, 13, 0.9)', overflow: 'hidden' },
  previewHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', borderBottom: '1px solid rgba(125, 211, 252, 0.16)' },
  previewPathRow: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 8, padding: 10 },
  previewInput: { border: '1px solid rgba(125, 211, 252, 0.2)', borderRadius: 10, background: 'rgba(15, 23, 42, 0.96)', color: '#f8fafc', padding: '8px 10px' },
  previewTabs: { display: 'flex', gap: 8, padding: '0 10px 10px' },
  tab: { border: '1px solid rgba(125, 211, 252, 0.2)', borderRadius: 999, color: '#dbeafe', background: 'transparent', padding: '7px 11px', cursor: 'pointer' },
  activeTab: { border: '1px solid rgba(125, 211, 252, 0.44)', borderRadius: 999, color: '#04111f', background: '#7dd3fc', padding: '7px 11px', cursor: 'pointer', fontWeight: 900 },
  previewBody: { minHeight: 0, overflow: 'hidden', borderTop: '1px solid rgba(125, 211, 252, 0.12)' },
  previewFrame: { width: '100%', height: '100%', border: 0, background: '#ffffff' },
  previewCode: { height: '100%', margin: 0, overflow: 'auto', whiteSpace: 'pre-wrap', padding: 12, color: '#dbeafe', fontFamily: 'Cascadia Code, Consolas, monospace', fontSize: 12, background: 'rgba(2, 6, 23, 0.9)' },
  closeButton: { border: '1px solid rgba(125, 211, 252, 0.2)', borderRadius: 999, color: '#dbeafe', background: 'transparent', padding: '6px 9px', cursor: 'pointer' }
};
