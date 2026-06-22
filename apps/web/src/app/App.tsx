import { useEffect, useMemo, useRef, useState } from 'react';

type ChatRole = 'assistant' | 'user' | 'system';

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

  const candidates = [
    data.text,
    data.answer,
    data.response,
    data.message,
    data.content,
    data.output,
    data.visible && typeof data.visible === 'object' ? (data.visible as Record<string, unknown>).text : undefined,
    data.visible && typeof data.visible === 'object' ? (data.visible as Record<string, unknown>).content : undefined,
    root.message,
    root.status
  ];

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

async function sendPrompt(prompt: string) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt })
  });

  const payload = await response.json().catch(() => ({ status: response.statusText }));
  if (!response.ok) {
    throw new Error(textFromPayload(payload));
  }
  return payload;
}

export function App() {
  const entryRef = useRef<HTMLTextAreaElement>(null);
  const [entry, setEntry] = useState('');
  const [busy, setBusy] = useState(false);
  const [runtimeStatus, setRuntimeStatus] = useState('checking runtime');
  const [modelStatus, setModelStatus] = useState('checking model');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Ready. Chat shell restored. Ask me what you want to build, inspect, search, preview, or fix.',
      createdAt: new Date().toISOString()
    }
  ]);

  const canSend = useMemo(() => entry.trim().length > 0 && !busy, [busy, entry]);

  useEffect(() => {
    getJson<Record<string, unknown>>('/api/health')
      .then((health) => setRuntimeStatus(`API ${String(health.status || 'ok')}`))
      .catch(() => setRuntimeStatus('API unavailable'));

    getJson<Record<string, unknown>>('/api/models/status')
      .then((model) => {
        const data = model.data && typeof model.data === 'object' ? (model.data as Record<string, unknown>) : model;
        setModelStatus(`${String(data.selected_model || data.model || 'model')} / ${String(model.status || 'ready')}`);
      })
      .catch(() => setModelStatus('model status unavailable'));
  }, []);

  function append(message: Omit<ChatMessage, 'id' | 'createdAt'>) {
    setMessages((current) => [
      ...current,
      {
        ...message,
        id: nowId(),
        createdAt: new Date().toISOString()
      }
    ]);
  }

  async function submit(event?: React.FormEvent) {
    event?.preventDefault();
    const prompt = entry.trim();
    if (!prompt || busy) return;

    setEntry('');
    append({ role: 'user', text: prompt });
    setBusy(true);

    try {
      const payload = await sendPrompt(prompt);
      append({ role: 'assistant', text: textFromPayload(payload) });
    } catch (error) {
      append({ role: 'system', text: error instanceof Error ? error.message : 'Chat request failed.' });
    } finally {
      setBusy(false);
      window.setTimeout(() => entryRef.current?.focus(), 0);
    }
  }

  function openCockpit() {
    const target = `${window.location.protocol}//${window.location.hostname}:6022/`;
    window.open(target, 'x8-cockpit', 'noopener,noreferrer,width=1460,height=920');
  }

  return (
    <main style={styles.shell}>
      <header style={styles.header}>
        <div>
          <p style={styles.kicker}>X8 Chat</p>
          <h1 style={styles.title}>Xoduz Operator Chat</h1>
          <p style={styles.subtitle}>Clean rescue shell. Cockpit stays on port 6022.</p>
        </div>
        <div style={styles.headerActions}>
          <span style={styles.pill}>{runtimeStatus}</span>
          <span style={styles.pill}>{modelStatus}</span>
          <button style={styles.secondaryButton} type="button" onClick={openCockpit}>Open Cockpit</button>
        </div>
      </header>

      <section style={styles.timeline} aria-live="polite">
        {messages.map((message) => (
          <article key={message.id} style={{ ...styles.message, ...(message.role === 'user' ? styles.userMessage : message.role === 'system' ? styles.systemMessage : styles.assistantMessage) }}>
            <div style={styles.messageMeta}>{message.role} · {new Date(message.createdAt).toLocaleTimeString()}</div>
            <pre style={styles.messageText}>{message.text}</pre>
          </article>
        ))}
        {busy && (
          <article style={{ ...styles.message, ...styles.assistantMessage }}>
            <div style={styles.messageMeta}>assistant</div>
            <pre style={styles.messageText}>Thinking…</pre>
          </article>
        )}
      </section>

      <form style={styles.composer} onSubmit={(event) => void submit(event)}>
        <textarea
          ref={entryRef}
          value={entry}
          onChange={(event) => setEntry(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
          placeholder="Type a message. Enter sends, Shift+Enter adds a new line."
          style={styles.textarea}
        />
        <button style={canSend ? styles.primaryButton : styles.disabledButton} type="submit" disabled={!canSend}>
          {busy ? 'Working…' : 'Send'}
        </button>
      </form>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    minHeight: '100vh',
    display: 'grid',
    gridTemplateRows: 'auto minmax(0, 1fr) auto',
    gap: 16,
    padding: 18,
    color: '#f5f7fb',
    background: 'radial-gradient(circle at top left, rgba(0, 212, 255, 0.14), transparent 34%), linear-gradient(135deg, #05070d, #111827 55%, #05070d)'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 14,
    alignItems: 'center',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 18,
    padding: '16px 18px',
    background: 'rgba(5, 7, 13, 0.82)',
    boxShadow: '0 18px 40px rgba(0,0,0,0.28)'
  },
  kicker: {
    margin: 0,
    color: '#7dd3fc',
    textTransform: 'uppercase',
    letterSpacing: '0.16em',
    fontSize: 12,
    fontWeight: 800
  },
  title: {
    margin: '4px 0 2px',
    fontSize: 'clamp(1.4rem, 3vw, 2.2rem)'
  },
  subtitle: {
    margin: 0,
    color: '#aeb7c7'
  },
  headerActions: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  },
  pill: {
    border: '1px solid rgba(125, 211, 252, 0.26)',
    borderRadius: 999,
    padding: '8px 10px',
    color: '#dbeafe',
    background: 'rgba(14, 165, 233, 0.1)',
    fontSize: 12,
    fontWeight: 700
  },
  timeline: {
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    padding: 4
  },
  message: {
    maxWidth: 980,
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 16,
    padding: 14,
    boxShadow: '0 14px 34px rgba(0,0,0,0.18)'
  },
  assistantMessage: {
    alignSelf: 'flex-start',
    background: 'rgba(15, 23, 42, 0.84)'
  },
  userMessage: {
    alignSelf: 'flex-end',
    background: 'rgba(30, 64, 175, 0.34)'
  },
  systemMessage: {
    alignSelf: 'center',
    background: 'rgba(127, 29, 29, 0.34)'
  },
  messageMeta: {
    marginBottom: 8,
    color: '#93c5fd',
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: '0.08em'
  },
  messageText: {
    margin: 0,
    whiteSpace: 'pre-wrap',
    fontFamily: 'inherit',
    lineHeight: 1.48
  },
  composer: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 10,
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 18,
    padding: 12,
    background: 'rgba(5, 7, 13, 0.9)'
  },
  textarea: {
    minHeight: 74,
    resize: 'vertical',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 14,
    padding: 12,
    outline: 'none',
    color: '#f8fafc',
    background: 'rgba(15, 23, 42, 0.96)',
    font: 'inherit'
  },
  primaryButton: {
    border: 0,
    borderRadius: 14,
    padding: '0 22px',
    color: '#04111f',
    background: 'linear-gradient(135deg, #7dd3fc, #22d3ee)',
    fontWeight: 900,
    cursor: 'pointer'
  },
  secondaryButton: {
    border: '1px solid rgba(125, 211, 252, 0.28)',
    borderRadius: 999,
    padding: '8px 12px',
    color: '#e0f2fe',
    background: 'rgba(14, 165, 233, 0.12)',
    fontWeight: 800,
    cursor: 'pointer'
  },
  disabledButton: {
    border: 0,
    borderRadius: 14,
    padding: '0 22px',
    color: '#94a3b8',
    background: 'rgba(148, 163, 184, 0.16)',
    fontWeight: 900,
    cursor: 'not-allowed'
  }
};
