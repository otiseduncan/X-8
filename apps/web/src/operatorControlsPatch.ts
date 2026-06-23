type SpeechRecognitionEventLike = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
    __x8OperatorControlsPatchInstalled?: boolean;
  }
}

const SESSION_KEY = 'x8-chat-session-id';
const WELCOME_TEXT = 'Ready. Exodus avatar restored. Ask me what you want to build, inspect, search, preview, or fix.';

function getChatData(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== 'object') return {};
  const root = payload as Record<string, unknown>;
  return root.data && typeof root.data === 'object' ? (root.data as Record<string, unknown>) : root;
}

function patchChatSessionFetch() {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const isChatPost = url.includes('/api/chat') && String(init?.method || 'GET').toUpperCase() === 'POST';
    let nextInit = init;
    if (isChatPost && typeof init?.body === 'string') {
      try {
        const body = JSON.parse(init.body) as Record<string, unknown>;
        const existing = typeof body.session_id === 'string' ? body.session_id : '';
        const stored = window.sessionStorage.getItem(SESSION_KEY) || '';
        body.session_id = existing || stored || null;
        nextInit = { ...init, body: JSON.stringify(body) };
      } catch {
        nextInit = init;
      }
    }
    const response = await nativeFetch(input, nextInit);
    if (isChatPost) {
      response.clone().json().then((payload: unknown) => {
        const sessionId = getChatData(payload).session_id;
        if (typeof sessionId === 'string' && sessionId) window.sessionStorage.setItem(SESSION_KEY, sessionId);
      }).catch(() => undefined);
    }
    return response;
  };
}

function transcriptText() {
  const articles = Array.from(document.querySelectorAll('article'));
  const rows = articles
    .filter((article) => !article.textContent?.includes(WELCOME_TEXT))
    .map((article) => article.textContent?.trim() || '')
    .filter(Boolean);
  return rows.length ? rows.join('\n\n---\n\n') : 'No chat messages yet.';
}

async function copyTranscript() {
  const text = transcriptText();
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement('textarea');
  area.value = text;
  area.style.position = 'fixed';
  area.style.left = '-9999px';
  document.body.appendChild(area);
  area.focus();
  area.select();
  document.execCommand('copy');
  document.body.removeChild(area);
}

function downloadTranscript() {
  const blob = new Blob([transcriptText()], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `x8-transcript-${new Date().toISOString().replace(/[:.]/g, '-')}.md`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function styleHeaderButton(button: HTMLButtonElement) {
  button.style.border = '1px solid rgba(125, 211, 252, 0.28)';
  button.style.borderRadius = '999px';
  button.style.padding = '8px 12px';
  button.style.color = '#e0f2fe';
  button.style.background = 'rgba(14, 165, 233, 0.12)';
  button.style.fontWeight = '800';
  button.style.cursor = 'pointer';
}

function addHeaderTranscriptControls() {
  if (document.querySelector('[data-x8-header-transcript-controls="true"]')) return;
  const cockpitButton = Array.from(document.querySelectorAll('button')).find((button) => button.textContent?.trim() === 'Open Cockpit') as HTMLButtonElement | undefined;
  const headerActions = cockpitButton?.parentElement;
  if (!headerActions) return;

  const copy = document.createElement('button');
  copy.type = 'button';
  copy.dataset.x8HeaderTranscriptControls = 'true';
  copy.textContent = 'Copy Transcript';
  copy.setAttribute('aria-label', 'Copy transcript');
  copy.onclick = () => { void copyTranscript(); };
  styleHeaderButton(copy);

  const download = document.createElement('button');
  download.type = 'button';
  download.textContent = 'Download Transcript';
  download.setAttribute('aria-label', 'Download transcript');
  download.onclick = downloadTranscript;
  styleHeaderButton(download);

  headerActions.insertBefore(copy, cockpitButton);
  headerActions.insertBefore(download, cockpitButton);
}

function setTextareaValue(textarea: HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
  setter?.call(textarea, value);
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
  textarea.dispatchEvent(new Event('change', { bubbles: true }));
}

function addMicButton(form: HTMLFormElement, textarea: HTMLTextAreaElement) {
  if (form.querySelector('[data-x8-mic-button="true"]')) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.x8MicButton = 'true';
  button.textContent = '🎙';
  button.setAttribute('aria-label', 'Start microphone dictation');
  button.title = 'Microphone dictation';
  button.style.width = '42px';
  button.style.minWidth = '42px';
  button.style.alignSelf = 'stretch';
  button.style.border = '1px solid rgba(125, 211, 252, 0.28)';
  button.style.borderRadius = '14px';
  button.style.padding = '0';
  button.style.color = '#e0f2fe';
  button.style.background = 'rgba(14, 165, 233, 0.12)';
  button.style.fontWeight = '900';
  button.style.fontSize = '18px';
  button.style.cursor = 'pointer';

  form.style.gridTemplateColumns = 'minmax(0, 1fr) 42px auto';

  let recognition: SpeechRecognitionLike | null = null;
  let listening = false;
  button.onclick = () => {
    if (listening) {
      recognition?.stop();
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      button.textContent = '×';
      window.setTimeout(() => { button.textContent = '🎙'; }, 1600);
      return;
    }
    recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onstart = () => {
      listening = true;
      button.textContent = '■';
      button.setAttribute('aria-label', 'Stop microphone dictation');
      button.style.background = 'rgba(127, 29, 29, 0.5)';
      button.style.color = '#fecaca';
    };
    recognition.onresult = (event) => {
      const spoken = Array.from(event.results).map((result) => result[0]?.transcript || '').join(' ').trim();
      if (spoken) {
        const nextValue = [textarea.value.trim(), spoken].filter(Boolean).join(' ');
        setTextareaValue(textarea, nextValue);
        textarea.focus();
      }
    };
    recognition.onerror = () => undefined;
    recognition.onend = () => {
      listening = false;
      button.textContent = '🎙';
      button.setAttribute('aria-label', 'Start microphone dictation');
      button.style.background = 'rgba(14, 165, 233, 0.12)';
      button.style.color = '#e0f2fe';
      textarea.focus();
    };
    recognition.start();
  };

  const sendButton = form.querySelector('button[type="submit"]');
  if (sendButton) form.insertBefore(button, sendButton);
  else form.appendChild(button);
}

function removeMisplacedTranscriptControls() {
  document.querySelectorAll('[data-x8-transcript-controls="true"]').forEach((node) => node.remove());
}

function hideStarterAssistantBox() {
  document.querySelectorAll('article').forEach((article) => {
    if (article.textContent?.includes(WELCOME_TEXT)) article.remove();
  });
}

function mountControls() {
  removeMisplacedTranscriptControls();
  hideStarterAssistantBox();
  addHeaderTranscriptControls();
  const textarea = document.querySelector('textarea') as HTMLTextAreaElement | null;
  const form = textarea?.closest('form') as HTMLFormElement | null;
  if (!textarea || !form) return;
  addMicButton(form, textarea);
}

export function installOperatorControlsPatch() {
  if (window.__x8OperatorControlsPatchInstalled) return;
  window.__x8OperatorControlsPatchInstalled = true;
  patchChatSessionFetch();
  mountControls();
  const observer = new MutationObserver(mountControls);
  observer.observe(document.body, { childList: true, subtree: true });
}

if (typeof window !== 'undefined') installOperatorControlsPatch();
