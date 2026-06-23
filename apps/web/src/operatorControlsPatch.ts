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

function styleComposerButton(button: HTMLButtonElement) {
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
  styleComposerButton(button);

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
      button.title = 'Speech recognition is not available in this browser';
      window.setTimeout(() => {
        button.textContent = '🎙';
        button.title = 'Microphone dictation';
      }, 1800);
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

function latestAssistantText() {
  const articles = Array.from(document.querySelectorAll('article')).reverse();
  const article = articles.find((item) => {
    const text = item.textContent?.trim() || '';
    return text.toLowerCase().startsWith('assistant') && !text.includes(WELCOME_TEXT) && !text.includes('Working…');
  });
  const raw = article?.textContent?.trim() || '';
  return raw
    .replace(/^assistant\s*·?\s*[^\n]*/i, '')
    .replace(/^assistant\s*/i, '')
    .trim();
}

function addSpeakButton(form: HTMLFormElement) {
  if (form.querySelector('[data-x8-speak-button="true"]')) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.x8SpeakButton = 'true';
  button.textContent = '🔊';
  button.setAttribute('aria-label', 'Read latest assistant response aloud');
  button.title = 'Read latest assistant response aloud';
  styleComposerButton(button);

  button.onclick = () => {
    if (!('speechSynthesis' in window)) {
      button.textContent = '×';
      button.title = 'Speech synthesis is not available in this browser';
      window.setTimeout(() => {
        button.textContent = '🔊';
        button.title = 'Read latest assistant response aloud';
      }, 1800);
      return;
    }
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      button.textContent = '🔊';
      return;
    }
    const text = latestAssistantText();
    if (!text) {
      button.textContent = '×';
      window.setTimeout(() => { button.textContent = '🔊'; }, 1600);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1;
    utterance.onstart = () => { button.textContent = '■'; };
    utterance.onend = () => { button.textContent = '🔊'; };
    utterance.onerror = () => { button.textContent = '🔊'; };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
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

function injectChatLayoutStyles() {
  if (document.querySelector('[data-x8-chat-layout-patch="true"]')) return;
  const style = document.createElement('style');
  style.dataset.x8ChatLayoutPatch = 'true';
  style.textContent = `
    html, body, #root {
      height: 100%;
      max-height: 100%;
      overflow: hidden;
    }
    body {
      overscroll-behavior: none;
    }
    #root > main {
      height: 100vh !important;
      max-height: 100vh !important;
      overflow: hidden !important;
    }
    #root > main > section {
      min-height: 0 !important;
      overflow: hidden !important;
    }
    section[aria-live="polite"] {
      min-height: 0 !important;
      overflow-y: auto !important;
      overscroll-behavior: contain;
      scroll-behavior: smooth;
      padding-bottom: 12px !important;
    }
    form[data-x8-composer-locked="true"] {
      position: sticky !important;
      bottom: 0 !important;
      z-index: 30 !important;
      box-shadow: 0 -18px 34px rgba(0, 0, 0, 0.28) !important;
      backdrop-filter: blur(12px);
    }
    form[data-x8-composer-locked="true"] textarea {
      max-height: 150px !important;
      resize: none !important;
    }
  `;
  document.head.appendChild(style);
}

function lockComposer(form: HTMLFormElement, textarea: HTMLTextAreaElement) {
  form.dataset.x8ComposerLocked = 'true';
  form.style.gridTemplateColumns = 'minmax(0, 1fr) 42px 42px auto';
  form.style.alignItems = 'stretch';
  textarea.style.resize = 'none';
  textarea.style.maxHeight = '150px';
  textarea.style.overflowY = 'auto';
}

function scrollTimelineToBottom() {
  const timeline = document.querySelector('section[aria-live="polite"]') as HTMLElement | null;
  if (!timeline) return;
  const scroll = () => {
    timeline.scrollTop = timeline.scrollHeight;
    const last = timeline.lastElementChild as HTMLElement | null;
    last?.scrollIntoView({ block: 'end', inline: 'nearest' });
  };
  scroll();
  window.requestAnimationFrame(scroll);
  window.setTimeout(scroll, 90);
  window.setTimeout(scroll, 280);
}

function mountControls() {
  injectChatLayoutStyles();
  removeMisplacedTranscriptControls();
  hideStarterAssistantBox();
  addHeaderTranscriptControls();
  const textarea = document.querySelector('textarea') as HTMLTextAreaElement | null;
  const form = textarea?.closest('form') as HTMLFormElement | null;
  if (!textarea || !form) return;
  lockComposer(form, textarea);
  addMicButton(form, textarea);
  addSpeakButton(form);
  scrollTimelineToBottom();
}

export function installOperatorControlsPatch() {
  if (window.__x8OperatorControlsPatchInstalled) return;
  window.__x8OperatorControlsPatchInstalled = true;
  patchChatSessionFetch();
  mountControls();
  const observer = new MutationObserver(mountControls);
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
}

if (typeof window !== 'undefined') installOperatorControlsPatch();