import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, ChevronDown, ChevronUp, Code2, Copy, FileText, GitBranch, Image, Info, Mic, MicOff, Pause, Play, Search, ShieldCheck, Square, Trash2, Volume2, VolumeX, X } from 'lucide-react';
import type { SpeechReceipt, SttStatus, TtsStatus } from '../audio/speechManagers';
import type { VoiceOption } from '../audio/speechManagers';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import type { AttachmentReference, PromptReceipt, Receipt } from '../types/contracts';

export type CardKind = 'artifact' | 'file' | 'editor' | 'diff' | 'image' | 'research' | 'test' | 'receipt' | 'approval' | 'error';

export interface ChatCard {
  id: string;
  type: CardKind;
  title: string;
  status: string;
  summary: string;
  receipt?: Receipt;
  payload?: Record<string, unknown>;
  collapsed?: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'assistant' | 'user';
  text: string;
  createdAt?: string;
  attachments?: AttachmentReference[];
  cards?: ChatCard[];
}

export interface StoredChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export type InfoReceipt = Receipt | SpeechReceipt | PromptReceipt | null;
export type AvatarRuntimeState = 'idle' | 'listening' | 'thinking' | 'responded' | 'speaking' | 'muted' | 'error';

export interface AvatarManifestAsset {
  id: string;
  label: string;
  type: 'video' | string;
  src: string;
  states: string[];
  loop: boolean;
  muted: boolean;
}

export interface AvatarManifestDocument {
  version: string;
  defaultAvatar: string;
  assets: AvatarManifestAsset[];
  fallback: {
    type: string;
    label: string;
    src?: string;
  };
}

const FALLBACK_AVATAR = '/avatar/fallback.svg';

export function selectAvatarAsset(manifest: AvatarManifestDocument | null, state: AvatarRuntimeState, failedSrc = '') {
  const assets = manifest?.assets || [];
  const byState = (candidate: string) => assets.find((asset) => asset.states.includes(candidate));
  const idle = byState('idle') || assets[0];
  const selected = state === 'speaking'
    ? byState('speaking')
    : state === 'listening'
      ? byState('listening') || byState('thinking')
      : state === 'thinking'
        ? byState('thinking') || byState('listening')
        : idle;
  const asset = selected || idle;
  if (!asset || asset.src === failedSrc) {
    if (asset?.src === failedSrc && idle && idle.src !== failedSrc) return idle;
    return null;
  }
  return asset;
}

export function AvatarStateController({ state, fallbackSrc = FALLBACK_AVATAR }: { state: AvatarRuntimeState; fallbackSrc?: string }) {
  return <AvatarStage state={state} fallbackSrc={fallbackSrc} />;
}

export function AvatarStage({ state, fallbackSrc = FALLBACK_AVATAR }: { state: AvatarRuntimeState; fallbackSrc?: string }) {
  const [manifest, setManifest] = useState<AvatarManifestDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [failedSrc, setFailedSrc] = useState('');

  useEffect(() => {
    let active = true;
    fetch('/avatar/manifest.json')
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('manifest unavailable'))))
      .then((data: AvatarManifestDocument) => {
        if (!active) return;
        setManifest(data);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setManifest(null);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = useMemo(() => selectAvatarAsset(manifest, state, failedSrc), [failedSrc, manifest, state]);
  const fallback = manifest?.fallback.src || fallbackSrc || FALLBACK_AVATAR;
  const badgeState = loading ? 'loading' : selected ? state : 'fallback';

  return (
    <div className={`avatarStage ${state}`} data-testid="avatar-stage" data-avatar-state={state}>
      {selected ? (
        <AvatarVideo key={`${selected.src}-${state}`} asset={selected} state={state} onFailed={() => setFailedSrc(selected.src)} />
      ) : (
        <img src={fallback} alt="XV8 avatar fallback" className={`avatar fallback ${state}`} data-testid="avatar-fallback" />
      )}
      <AvatarStatusBadge state={badgeState} />
    </div>
  );
}

export function AvatarVideo({ asset, state, onFailed }: { asset: AvatarManifestAsset; state: AvatarRuntimeState; onFailed: () => void }) {
  return (
    <video
      aria-label="XV8 avatar"
      className={`avatar avatarVideo ${state}`}
      data-testid="avatar-video"
      autoPlay
      loop={asset.loop}
      muted
      playsInline
      preload="metadata"
      onError={onFailed}
    >
      <source src={asset.src} type="video/mp4" />
    </video>
  );
}

export function AvatarStatusBadge({ state }: { state: string }) {
  return <span className={`avatarStatusBadge ${state}`}>{state}</span>;
}

export function messageCopyText(message: ChatMessage) {
  const speaker = message.role === 'assistant' ? 'XV8' : 'You';
  const parts = [`${speaker}:\n${message.text}`];
  if (message.attachments?.length) {
    parts.push(`Attachments:\n${message.attachments.map((attachment) => `- ${attachment.filename} (${attachment.mime_type}, ${attachment.status})`).join('\n')}`);
  }
  if (message.cards?.length) {
    parts.push(`Cards:\n${message.cards.map((card) => `- ${card.title}: ${card.summary}`).join('\n')}`);
  }
  return parts.join('\n\n');
}

export function transcriptMarkdown(messages: ChatMessage[], includeReceipts = false) {
  const sections = ['# XV8 Conversation Transcript'];
  messages.forEach((message) => {
    const timestamp = message.createdAt ? ` - ${new Date(message.createdAt).toLocaleString()}` : '';
    sections.push(`## ${message.role === 'assistant' ? 'XV8' : 'User'}${timestamp}`);
    sections.push(message.text);
    if (message.attachments?.length) {
      sections.push(`Attachments:\n${message.attachments.map((attachment) => `- ${attachment.filename} (${attachment.mime_type}, ${attachment.status})`).join('\n')}`);
    }
    if (message.cards?.length) {
      sections.push(`Cards:\n${message.cards.map((card) => `- ${card.title}: ${card.summary}`).join('\n')}`);
      if (includeReceipts) {
        const receipts = message.cards.filter((card) => card.receipt).map((card) => `- ${card.receipt?.action}: ${card.receipt?.status}`);
        if (receipts.length) sections.push(`Receipts:\n${receipts.join('\n')}`);
      }
    }
  });
  return sections.join('\n\n');
}

export function ThinkingIndicator({ active, stage, status }: { active: boolean; stage: string; status: string }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!active) {
      setElapsed(0);
      return undefined;
    }
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  if (!active) return null;
  const label = status === 'timeout' ? 'Timed out - reset available' : elapsed > 10 ? 'Still working...' : stage === 'thinking' ? 'Thinking...' : 'Working...';
  return (
    <article className={`thinkingIndicator ${elapsed > 10 ? 'caution' : ''}`} aria-label="XV8 thinking" data-testid="thinking-indicator">
      <span className="thinkingDots" aria-hidden="true"><i /><i /><i /></span>
      <div>
        <strong>{label}</strong>
        <span>Stage: {stage || 'working'} / elapsed {elapsed}s</span>
      </div>
    </article>
  );
}

export function ChatTimeline({ messages, onToggle, onRequestApply, onCopyMessage }: { messages: ChatMessage[]; onToggle: (cardId: string, patch: Partial<ChatCard>) => void; onRequestApply: (card: ChatCard) => void; onCopyMessage: (message: ChatMessage) => Promise<void> | void }) {
  const [copiedId, setCopiedId] = useState('');
  async function copy(message: ChatMessage) {
    await onCopyMessage(message);
    setCopiedId(message.id);
    window.setTimeout(() => setCopiedId((current) => (current === message.id ? '' : current)), 1200);
  }
  return (
    <section className="chatTimeline" aria-label="Chat timeline">
      {messages.length === 0 && <div className="emptyChat">New chat is ready.</div>}
      {messages.map((message) => (
        <article key={message.id} className={`message ${message.role}`}>
          <div className="messageBubble">
            <p className="messageRole">{message.role === 'assistant' ? 'XV8' : 'You'}</p>
            <button className="messageCopyButton" type="button" aria-label={`Copy ${message.role === 'assistant' ? 'XV8' : 'You'} message`} data-testid="copy-message-button" onClick={() => void copy(message)}>
              <Copy size={13} /> {copiedId === message.id ? 'Copied' : 'Copy message'}
            </button>
            <p>{message.text}</p>
            {message.attachments && message.attachments.length > 0 && (
              <div className="messageAttachments" aria-label="Message attachments">
                {message.attachments.map((attachment) => (
                  <span className="attachmentChip" key={attachment.attachment_id}>
                    {attachment.filename} <small>{attachment.mime_type} / {attachment.status}</small>
                  </span>
                ))}
              </div>
            )}
            {message.cards?.map((card) => (
              <InlineChatCard key={card.id} card={card} onToggle={onToggle} onRequestApply={onRequestApply} />
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}

export function ChatHistoryPanel({ sessions, activeId, onNew, onRestore, onDelete }: { sessions: StoredChatSession[]; activeId: string; onNew: () => void; onRestore: (session: StoredChatSession) => void; onDelete: (id: string) => void }) {
  return (
    <section className="historyPanel" aria-label="Chat history">
      <header>
        <div>
          <p className="eyebrow">Local history</p>
          <h2>Recent chats</h2>
        </div>
        <button className="chipButton" type="button" onClick={onNew}><FileText size={14} /> New chat</button>
      </header>
      <div className="historyList">
        {sessions.length === 0 && <p className="cardSummary">No saved chats yet.</p>}
        {sessions.map((session) => (
          <article className={session.id === activeId ? 'historyItem active' : 'historyItem'} key={session.id}>
            <button type="button" onClick={() => onRestore(session)}>
              <strong>{session.title}</strong>
              <span>{new Date(session.updatedAt).toLocaleString()}</span>
            </button>
            <button className="ghost iconButton" type="button" aria-label={`Delete ${session.title}`} onClick={() => onDelete(session.id)}><Trash2 size={16} /></button>
          </article>
        ))}
      </div>
    </section>
  );
}

export function InfoDropdown({ open, onToggle, bridgeStatus, modelStatus, memoryStatus, githubStatus, voiceStatus, voiceName, latestReceipt, latestResult, onCopyTranscript, onCopyTranscriptWithReceipts, onDownloadTranscript }: { open: boolean; onToggle: () => void; bridgeStatus: string; modelStatus: string; memoryStatus: string; githubStatus: string; voiceStatus: TtsStatus; voiceName: string; latestReceipt: InfoReceipt; latestResult: string; onCopyTranscript: () => void; onCopyTranscriptWithReceipts: () => void; onDownloadTranscript: () => void }) {
  return (
    <div className="infoDropdown">
      <button className="ghost infoButton" aria-expanded={open} onClick={onToggle}>
        <Info size={16} /> Info {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div className="infoMenu" aria-label="Info details">
          <div className="row split"><strong>Runtime</strong><span>{bridgeStatus}</span></div>
          <div className="row split"><strong>Model</strong><span>{modelStatus}</span></div>
          <div className="row split"><strong>Memory</strong><span>{memoryStatus}</span></div>
          <div className="row split"><strong>GitHub</strong><span>{githubStatus}</span></div>
          <div className="row split"><strong>Voice</strong><span>{voiceStatus} / {voiceName}</span></div>
          <div className="row"><strong>Latest result</strong><span>{latestResult}</span></div>
          <div className="row"><strong>Latest receipt</strong><span>{latestReceipt ? receiptSummary(latestReceipt) : 'No receipts yet.'}</span></div>
          <div className="row"><strong>Limitations</strong><span>Model and attachment limits are shown in receipts when they apply.</span></div>
          <button className="chipButton"><Copy size={14} /> Copy diagnostics</button>
          <button className="chipButton" data-testid="copy-transcript-button" onClick={onCopyTranscript}><Copy size={14} /> Copy transcript</button>
          <button className="chipButton" onClick={onCopyTranscriptWithReceipts}><Copy size={14} /> Copy transcript with receipts</button>
          <button className="chipButton" onClick={onDownloadTranscript}>Download transcript .md</button>
        </div>
      )}
    </div>
  );
}

function receiptSummary(receipt: InfoReceipt) {
  if (!receipt) return 'No receipts yet.';
  if ('action_type' in receipt) return `${receipt.action_type}: ${receipt.status}`;
  if ('receipt_id' in receipt) return `${receipt.status} / ${receipt.provider}`;
  return `${receipt.action}: ${receipt.status}`;
}

type ArtifactTopTab = 'Preview' | 'Pages' | 'Code' | 'Files' | 'Assets' | 'Metadata' | 'History' | 'Export';
type ArtifactApprovalState = 'proposed' | 'approved' | 'denied' | 'applied';

interface ArtifactPage {
  id: string;
  label: string;
  path: string;
  content: string;
}

interface ArtifactFile {
  path: string;
  content: string;
}

interface ArtifactAsset {
  id: string;
  label: string;
  path: string;
}

interface ArtifactPackageState {
  packageId: string;
  title: string;
  packageType: string;
  activeTopTab: ArtifactTopTab;
  activePageId: string;
  pages: ArtifactPage[];
  files: ArtifactFile[];
  assets: ArtifactAsset[];
  draftCodeByPage: Record<string, string>;
  dirtyByPage: Record<string, boolean>;
  packageDirty: boolean;
  approvalState: ArtifactApprovalState;
  selectedLineByPage: Record<string, number>;
  savedDraftByPage: Record<string, string>;
  approvedDraftSignature: string;
  hasBeenApproved: boolean;
  historyLog: string[];
}

const ARTIFACT_TOP_TABS_BASE: ArtifactTopTab[] = ['Preview', 'Code', 'Files', 'Assets', 'Metadata', 'History', 'Export'];

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback;
}

function pageIdFromPath(path: string, index: number) {
  return path ? path.replace(/[^a-zA-Z0-9_-]/g, '-').toLowerCase() : `page-${index + 1}`;
}

function pageLabelFromPath(path: string, index: number) {
  if (!path) return `Page ${index + 1}`;
  const segment = path.split('/').pop() || path;
  const clean = segment.replace(/\.[a-z0-9]+$/i, '').replace(/[-_]+/g, ' ').trim();
  if (!clean) return `Page ${index + 1}`;
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

function buildArtifactPages(payload: Record<string, unknown>) {
  const rawPages = Array.isArray(payload.pages) ? payload.pages : [];
  if (rawPages.length > 0) {
    return rawPages.map((entry, index) => {
      const page = asRecord(entry);
      const path = asString(page.path, index === 0 ? 'index.html' : `page-${index + 1}.html`);
      return {
        id: asString(page.id, pageIdFromPath(path, index)),
        label: asString(page.label, pageLabelFromPath(path, index)),
        path,
        content: asString(page.content, '')
      } as ArtifactPage;
    });
  }
  const html = asString(payload.html, '');
  return [{ id: 'home', label: 'Home', path: 'index.html', content: html }];
}

function buildArtifactFiles(payload: Record<string, unknown>, pages: ArtifactPage[]) {
  const rawFiles = Array.isArray(payload.files) ? payload.files : [];
  if (rawFiles.length > 0) {
    return rawFiles.map((entry, index) => {
      const file = asRecord(entry);
      return {
        path: asString(file.path, `file-${index + 1}.txt`),
        content: asString(file.content, '')
      } as ArtifactFile;
    });
  }
  const files: ArtifactFile[] = pages.map((page) => ({ path: page.path, content: page.content }));
  const css = asString(payload.css, '');
  if (css) files.push({ path: 'styles.css', content: css });
  return files;
}

function buildArtifactAssets(payload: Record<string, unknown>) {
  const rawAssets = Array.isArray(payload.assets) ? payload.assets : [];
  return rawAssets.map((entry, index) => {
    const asset = asRecord(entry);
    const path = asString(asset.path, `asset-${index + 1}`);
    return {
      id: asString(asset.id, `asset-${index + 1}`),
      label: asString(asset.label, path),
      path
    } as ArtifactAsset;
  });
}

function draftSignature(draftByPage: Record<string, string>) {
  const ordered = Object.keys(draftByPage).sort().map((key) => [key, draftByPage[key]]);
  return JSON.stringify(ordered);
}

function packageStatusBadge(state: ArtifactPackageState) {
  if (state.approvalState === 'applied') return 'applied';
  if (state.approvalState === 'approved') return 'approved';
  if (state.approvalState === 'denied') return 'denied';
  if (state.packageDirty) return 'edited';
  if (draftSignature(state.savedDraftByPage) !== draftSignature(state.draftCodeByPage)) return 'saved';
  return 'proposed';
}

function buildArtifactPackageState(card: ChatCard): ArtifactPackageState {
  const payload = asRecord(card.payload);
  const pages = buildArtifactPages(payload);
  const files = buildArtifactFiles(payload, pages);
  const assets = buildArtifactAssets(payload);
  const draftCodeByPage = pages.reduce<Record<string, string>>((acc, page) => {
    acc[page.id] = page.content;
    return acc;
  }, {});
  const savedDraftByPage = { ...draftCodeByPage };
  const approvedDraftSignature = draftSignature(savedDraftByPage);
  return {
    packageId: card.id,
    title: card.title,
    packageType: asString(payload.package_type, 'website_package'),
    activeTopTab: 'Preview',
    activePageId: pages[0]?.id || 'home',
    pages,
    files,
    assets,
    draftCodeByPage,
    dirtyByPage: {},
    packageDirty: false,
    approvalState: 'proposed',
    selectedLineByPage: {},
    savedDraftByPage,
    approvedDraftSignature,
    hasBeenApproved: false,
    historyLog: ['Package generated. Review and approve before apply.']
  };
}

function artifactTopTabs(state: ArtifactPackageState) {
  if (state.pages.length > 1) return ['Preview', 'Pages', 'Code', 'Files', 'Assets', 'Metadata', 'History', 'Export'] as ArtifactTopTab[];
  return ARTIFACT_TOP_TABS_BASE;
}

function InlineChatCard({ card, onToggle, onRequestApply }: { card: ChatCard; onToggle: (cardId: string, patch: Partial<ChatCard>) => void; onRequestApply: (card: ChatCard) => void }) {
  const [artifactPackage, setArtifactPackage] = useState<ArtifactPackageState | null>(() => (card.type === 'artifact' ? buildArtifactPackageState(card) : null));

  useEffect(() => {
    if (card.type !== 'artifact') {
      setArtifactPackage(null);
      return;
    }
    setArtifactPackage((current) => (current && current.packageId === card.id ? current : buildArtifactPackageState(card)));
  }, [card.id, card.type]);

  const icon = {
    artifact: <Play size={17} />,
    file: <FileText size={17} />,
    editor: <Code2 size={17} />,
    diff: <GitBranch size={17} />,
    image: <Image size={17} />,
    research: <Search size={17} />,
    test: <Activity size={17} />,
    receipt: <ShieldCheck size={17} />,
    approval: <ShieldCheck size={17} />,
    error: <X size={17} />
  }[card.type];

  const stableMarkerTestId = stableCardTestId(card);
  return (
    <section className={`inlineCard ${card.type}`} data-testid={`inline-${card.type}-card`}>
      {stableMarkerTestId && <span className="srOnly" data-testid={stableMarkerTestId} aria-hidden="true" />}
      <header className="inlineCardHeader">
        <span className="icon small">{icon}</span>
        <div>
          <p className="cardMeta">{card.type} / {card.status}</p>
          <h2 data-testid={card.title === 'Self-build patch plan' ? 'self-build-patch-plan-text' : undefined}>{card.title}</h2>
        </div>
        <button className="ghost iconButton" aria-label={`${card.collapsed ? 'Expand' : 'Collapse'} ${card.title}`} onClick={() => onToggle(card.id, { collapsed: !card.collapsed })}>
          {card.collapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
        </button>
      </header>
      <p className="cardSummary">{card.summary}</p>
      <div className="inlineActions">
        <button className="chipButton"><Copy size={14} /> Copy</button>
        {card.type === 'approval' && canApplyCard(card) && <button className="chipButton" onClick={() => onRequestApply(card)} disabled={card.status === 'applying'}>{card.status === 'applying' ? 'Applying' : 'Apply'}</button>}
      </div>
      {!card.collapsed && (
        <div className="cardBody">
          {card.type === 'artifact' && artifactPackage && <ArtifactBody card={card} state={artifactPackage} onStateChange={setArtifactPackage} onToggle={onToggle} />}
          {card.type === 'file' && <FileBody card={card} />}
          {card.type === 'editor' && <EditorBody card={card} />}
          {card.type === 'diff' && <DiffBody card={card} />}
          {card.type === 'research' && <ResearchBody card={card} />}
          {card.type === 'image' && <ImageBody card={card} />}
          {card.type === 'test' && <TestBody card={card} />}
          {card.type === 'receipt' && <ReceiptBody card={card} />}
          {card.type === 'approval' && <ApprovalBody card={card} />}
          {card.type === 'error' && <ErrorBody card={card} />}
        </div>
      )}
    </section>
  );
}

function ArtifactBody({ card, state, onStateChange, onToggle }: { card: ChatCard; state: ArtifactPackageState; onStateChange: (next: ArtifactPackageState) => void; onToggle: (cardId: string, patch: Partial<ChatCard>) => void }) {
  const payload = asRecord(card.payload);
  const css = asString(payload.css, '');
  const activePage = state.pages.find((page) => page.id === state.activePageId) || state.pages[0];
  const activeCode = activePage ? state.draftCodeByPage[activePage.id] || '' : '';
  const applyEnabled = state.approvalState === 'approved' && !state.packageDirty;
  function writeState(next: ArtifactPackageState, summary?: string) {
    const nextBadge = packageStatusBadge(next);
    onStateChange(next);
    onToggle(card.id, { status: nextBadge, summary: summary || card.summary });
  }

  function setTopTab(tab: ArtifactTopTab) {
    writeState({ ...state, activeTopTab: tab });
  }

  function setActivePage(pageId: string) {
    writeState({ ...state, activePageId: pageId });
  }

  function approvePackage() {
    const next: ArtifactPackageState = {
      ...state,
      approvalState: 'approved',
      approvedDraftSignature: draftSignature(state.savedDraftByPage),
      hasBeenApproved: true,
      historyLog: [`Approved package draft at ${new Date().toISOString()}`, ...state.historyLog]
    };
    writeState(next, 'Package approved. Apply is enabled for this saved draft.');
  }

  function denyPackage() {
    const next: ArtifactPackageState = {
      ...state,
      approvalState: 'denied',
      historyLog: [`Denied package draft at ${new Date().toISOString()}`, ...state.historyLog]
    };
    writeState(next, 'Package denied. Apply remains disabled until re-approved.');
  }

  function saveDraft() {
    const nextSaved = { ...state.savedDraftByPage, ...state.draftCodeByPage };
    const changedAfterApproval = state.hasBeenApproved && draftSignature(nextSaved) !== state.approvedDraftSignature;
    const next: ArtifactPackageState = {
      ...state,
      savedDraftByPage: nextSaved,
      dirtyByPage: {},
      packageDirty: false,
      approvalState: changedAfterApproval ? 'proposed' : state.approvalState,
      historyLog: [
        changedAfterApproval
          ? `Saved changed draft at ${new Date().toISOString()} (re-approval required).`
          : `Saved draft at ${new Date().toISOString()}.`,
        ...state.historyLog
      ]
    };
    writeState(next, changedAfterApproval ? 'Draft changed after approval. Re-approve to enable Apply.' : 'Draft saved.');
  }

  function updateCode(value: string, selectionStart = value.length) {
    if (!activePage) return;
    const previousApprovalState = state.approvalState;
    const dirtyByPage = { ...state.dirtyByPage, [activePage.id]: value !== (state.savedDraftByPage[activePage.id] || '') };
    const packageDirty = Object.values(dirtyByPage).some(Boolean);
    const line = value.slice(0, selectionStart).split('\n').length;
    const invalidated = state.hasBeenApproved && draftSignature({ ...state.draftCodeByPage, [activePage.id]: value }) !== state.approvedDraftSignature;
    const next: ArtifactPackageState = {
      ...state,
      draftCodeByPage: { ...state.draftCodeByPage, [activePage.id]: value },
      dirtyByPage,
      packageDirty,
      approvalState: invalidated ? 'proposed' : previousApprovalState,
      selectedLineByPage: { ...state.selectedLineByPage, [activePage.id]: line },
      historyLog: invalidated ? [`Edited approved draft at ${new Date().toISOString()} (re-approval required).`, ...state.historyLog] : state.historyLog
    };
    writeState(next, invalidated ? 'Draft changed after approval. Re-approve to enable Apply.' : card.summary);
  }

  function applyPackage() {
    if (!applyEnabled) return;
    const applyEndpoint = asString(payload.apply_endpoint, '');
    if (!applyEndpoint) {
      const next: ArtifactPackageState = {
        ...state,
        historyLog: [`Apply attempted at ${new Date().toISOString()}: apply backend not configured.`, ...state.historyLog]
      };
      writeState(next, 'Apply backend not configured. Approval remains valid for the current saved draft.');
      return;
    }
    const next: ArtifactPackageState = {
      ...state,
      approvalState: 'applied',
      historyLog: [`Applied package through ${applyEndpoint} at ${new Date().toISOString()}.`, ...state.historyLog]
    };
    writeState(next, 'Package applied.');
  }

  const iframeMarkup = activePage ? `<style>${css}</style>${state.draftCodeByPage[activePage.id] || ''}` : '';

  return (
    <div className="artifactPackageShell" data-testid="artifact-package-shell">
      <header className="artifactPackageHeader" data-testid="artifact-package-header">
        <div className="artifactPackageMeta">
          <h3>{state.title}</h3>
          <p>{state.packageType}</p>
          <span className={`artifactStatusBadge ${packageStatusBadge(state)}`}>{packageStatusBadge(state)}</span>
        </div>
        <div className="artifactPackageActions">
          <button className="chipButton" type="button" onClick={approvePackage}>Approve</button>
          <button className="chipButton" type="button" onClick={denyPackage}>Deny</button>
          <button className="chipButton" type="button" onClick={applyPackage} disabled={!applyEnabled}>Apply</button>
        </div>
      </header>
      <div className="tabs artifactTopTabs" aria-label="Artifact package tabs">
        {artifactTopTabs(state).map((name) => <button key={name} className={state.activeTopTab === name ? 'tab active' : 'tab'} onClick={() => setTopTab(name)}>{name === 'History' ? 'History/Log' : name}</button>)}
      </div>
      {state.activeTopTab === 'Preview' && <iframe title="Inline website preview" srcDoc={iframeMarkup} sandbox="" />}
      {state.activeTopTab === 'Pages' && (
        <div className="stack">
          <div className="tabs" aria-label="Artifact page tabs">
            {state.pages.map((page) => <button key={page.id} className={state.activePageId === page.id ? 'tab active' : 'tab'} onClick={() => setActivePage(page.id)}>{page.label}</button>)}
          </div>
          <div className="row split"><strong>Active page</strong><span>{activePage?.path || 'none'}</span></div>
          <div className="row split"><strong>Draft state</strong><span>{state.dirtyByPage[state.activePageId] ? 'edited' : 'clean'}</span></div>
        </div>
      )}
      {state.activeTopTab === 'Code' && activePage && (
        <div className="stack">
          {state.pages.length > 1 && (
            <div className="tabs" aria-label="Code page selector">
              {state.pages.map((page) => <button key={page.id} className={state.activePageId === page.id ? 'tab active' : 'tab'} onClick={() => setActivePage(page.id)}>{page.label}</button>)}
            </div>
          )}
          <label className="row split" htmlFor={`artifact-code-${card.id}`}>
            <strong>Editing</strong><span>{activePage.path}</span>
          </label>
          <textarea
            id={`artifact-code-${card.id}`}
            aria-label="Artifact page code editor"
            className="artifactCodeEditor"
            value={activeCode}
            onChange={(event) => updateCode(event.target.value, event.target.selectionStart)}
            onClick={(event) => updateCode(activeCode, (event.target as HTMLTextAreaElement).selectionStart)}
            onKeyUp={(event) => updateCode(activeCode, (event.target as HTMLTextAreaElement).selectionStart)}
          />
          <div className="inlineActions">
            <button className="chipButton" type="button" onClick={saveDraft}>Save draft</button>
            <span className="cardSummary">Line {state.selectedLineByPage[state.activePageId] || 1}</span>
          </div>
        </div>
      )}
      {state.activeTopTab === 'Files' && (
        <div className="stack">
          {state.files.map((file) => (
            <div className="row split" key={file.path}>
              <strong>{file.path}</strong>
              <span>{file.content.length} chars</span>
            </div>
          ))}
          {!state.files.length && <p className="cardSummary">No files are attached to this package.</p>}
        </div>
      )}
      {state.activeTopTab === 'Assets' && (
        <div className="stack">
          {state.assets.map((asset) => <div className="row split" key={asset.id}><strong>{asset.label}</strong><span>{asset.path}</span></div>)}
          {!state.assets.length && <p className="cardSummary">No assets were generated for this package.</p>}
        </div>
      )}
      {state.activeTopTab === 'Metadata' && <pre className="codeBlock">{JSON.stringify(payload.metadata || {}, null, 2)}</pre>}
      {state.activeTopTab === 'History' && (
        <div className="stack" aria-label="Artifact approval history">
          {state.historyLog.map((entry, index) => <p className="cardSummary" key={`${entry}-${index}`}>{entry}</p>)}
        </div>
      )}
      {state.activeTopTab === 'Export' && (
        <div className="inlineActions">
          <button className="chipButton" type="button">Export package</button>
          <span className="cardSummary">Export is package-scoped and does not change approval state.</span>
        </div>
      )}
    </div>
  );
}

function FileBody({ card }: { card: ChatCard }) {
  return <pre className="codeBlock">{String(card.payload?.content || '')}</pre>;
}

function EditorBody({ card }: { card: ChatCard }) {
  return <CodeEditor path={String(card.payload?.path || 'draft.txt')} value={String(card.payload?.content || '')} onChange={() => undefined} />;
}

function DiffBody({ card }: { card: ChatCard }) {
  return (
    <div className="stack">
      <div className="row split"><strong>Affected files</strong><span>{String(card.payload?.path || 'unknown')}</span></div>
      <div className="row split"><strong>Risk level</strong><span>{String(card.payload?.risk || 'medium')}</span></div>
      <div className="row split"><strong>Approval state</strong><span>{String(card.payload?.approvalState || 'pending')}</span></div>
      <div className="row"><strong>Before / after</strong><span>{String(card.payload?.beforeAfter || '')}</span></div>
      <pre className="diff">{String(card.payload?.diff || '')}</pre>
      <div className="inlineActions"><button className="chipButton">Cancel</button></div>
    </div>
  );
}

function ResearchBody({ card }: { card: ChatCard }) {
  const results = Array.isArray(card.payload?.results) ? card.payload?.results as Array<Record<string, unknown>> : [];
  return (
    <div className="stack">
      <div className="row split"><strong>Query</strong><span>{String(card.payload?.query || '')}</span></div>
      <div className="row split"><strong>Provider</strong><span>{String(card.payload?.provider || 'SearXNG')}</span></div>
      <div className="row"><strong>Freshness note</strong><span>{String(card.payload?.freshness || '')}</span></div>
      {results.length ? results.map((result, index) => (
        <div className="source" key={`${result.url}-${index}`}>
          <strong>{String(result.title || `Source ${index + 1}`)}</strong>
          <span>{String(result.snippet || result.url || '')}</span>
        </div>
      )) : <p className="cardSummary">Provider unavailable is shown honestly if search is down.</p>}
      <button className="chipButton">Copy citations</button>
    </div>
  );
}

function ImageBody({ card }: { card: ChatCard }) {
  const imageUrl = String(card.payload?.imageUrl || '');
  return (
    <div className="stack">
      <div className="row"><strong>Prompt summary</strong><span>{String(card.payload?.prompt || '')}</span></div>
      <div className="row split"><strong>Model</strong><span>{String(card.payload?.model || 'Juggernaut')}</span></div>
      <div className="row split"><strong>Workflow</strong><span>{String(card.payload?.workflow || 'ComfyUI')}</span></div>
      <div className="row split"><strong>Seed</strong><span>{String(card.payload?.seed || 'pending')}</span></div>
      {imageUrl ? <img src={imageUrl} alt="Generated result" className="generatedImage" /> : <p className="cardSummary">No image was generated.</p>}
      <div className="inlineActions"><button className="chipButton">Download</button><button className="chipButton">Regenerate</button></div>
    </div>
  );
}

function TestBody({ card }: { card: ChatCard }) {
  return <pre className="codeBlock">{String(card.payload?.command || 'No command queued.')}</pre>;
}

function ReceiptBody({ card }: { card: ChatCard }) {
  const content = card.payload && Object.keys(card.payload).length ? card.payload : card.receipt || {};
  return <pre className="codeBlock">{JSON.stringify(content, null, 2)}</pre>;
}

function ApprovalBody({ card }: { card: ChatCard }) {
  const applyResult = (card.payload?.apply_result || {}) as Record<string, unknown>;
  const changedFiles: unknown[] = Array.isArray(applyResult.changed_files) ? applyResult.changed_files : Array.isArray(card.payload?.changed_file_paths) ? card.payload.changed_file_paths : [];
  const backupPaths: unknown[] = Array.isArray(applyResult.backup_paths) ? applyResult.backup_paths : [];
  const provider = String(card.payload?.provider || '');
  const operation = String(card.payload?.operation || '');
  const reason = String(applyResult.reason || '');
  const repoName = card.payload?.repo_name === undefined ? '' : String(card.payload.repo_name);
  const owner = card.payload?.owner === undefined ? '' : String(card.payload.owner);
  const visibility = card.payload?.visibility === undefined ? '' : String(card.payload.visibility);
  return (
    <div className="stack">
      <p className="cardSummary">{card.summary}</p>
      <div className="row split"><strong>Task</strong><span>{String(card.payload?.task_id || 'unknown')}</span></div>
      {provider && <div className="row split"><strong>Provider</strong><span>{provider}</span></div>}
      {operation && <div className="row split"><strong>Operation</strong><span>{operation}</span></div>}
      {repoName && <div className="row split"><strong>Repo name</strong><span>{repoName}</span></div>}
      {owner && <div className="row split"><strong>Owner</strong><span>{owner}</span></div>}
      {visibility && <div className="row split"><strong>Visibility</strong><span>{visibility}</span></div>}
      {card.payload?.approval_required !== undefined && <div className="row split"><strong>Approval required</strong><span>{String(card.payload.approval_required)}</span></div>}
      {card.payload?.github_write_ran !== undefined && <div className="row split"><strong>GitHub write ran</strong><span>{String(card.payload.github_write_ran)}</span></div>}
      {card.payload?.local_repo_mutation !== undefined && <div className="row split"><strong>Local repo mutation</strong><span>{String(card.payload.local_repo_mutation)}</span></div>}
      {card.payload?.code_push !== undefined && <div className="row split"><strong>Code push</strong><span>{String(card.payload.code_push)}</span></div>}
      <div className="row split"><strong>Patch</strong><span>{String(card.payload?.patch_id || 'unknown')}</span></div>
      <div className="row split"><strong>Approval</strong><span>{String(card.payload?.approval_id || 'unknown')}</span></div>
      <div className="row"><strong>Patch hash</strong><span>{String(card.payload?.patch_hash || 'unknown')}</span></div>
      <div className="row split"><strong>Apply safe</strong><span>{String(card.payload?.apply_safe ?? false)}</span></div>
      <div className="row split"><strong>Validation passed</strong><span>{String(applyResult.validation_passed ?? card.payload?.validation_passed ?? card.payload?.validation_status ?? 'unknown')}</span></div>
      <div className="row"><strong>Changed files</strong><span>{changedFiles.length ? changedFiles.map(String).join(', ') : 'unknown'}</span></div>
      {reason && <div className="row"><strong>Reason</strong><span>{reason}</span></div>}
      {backupPaths.length > 0 && <div className="row"><strong>Backups</strong><span>{backupPaths.map(String).join(', ')}</span></div>}
    </div>
  );
}

function canApplyCard(card: ChatCard) {
  const payload = card.payload || {};
  if (payload.provider === 'github_ops') return card.status !== 'applied' && card.status !== 'blocked' && payload.apply_safe === true && Boolean(payload.operation);
  return card.status !== 'applied'
    && card.status !== 'blocked'
    && payload.apply_safe === true
    && Boolean(payload.task_id)
    && Boolean(payload.patch_id)
    && Boolean(payload.approval_id)
    && Boolean(payload.patch_hash)
    && payload.validation_status !== 'failed'
    && payload.validation_passed !== false;
}

function stableCardTestId(card: ChatCard) {
  if (card.title === 'Self-build patch proposal') return 'self-build-proposal-card';
  if (card.title === 'Self-build patch plan') return 'self-build-patch-plan-card';
  if (card.payload?.provider === 'github_ops' && card.payload?.operation === 'create-repo') return 'github-create-repo-approval-card';
  return '';
}

function ErrorBody({ card }: { card: ChatCard }) {
  return <p className="cardSummary">{card.summary}</p>;
}

export function MicrophoneButton({ status, onStart }: { status: SttStatus; onStart: () => void }) {
  const unavailable = status === 'unavailable' || status === 'permission_denied';
  return (
    <button className="ghost" aria-label="Microphone" onClick={onStart} disabled={status === 'listening'}>
      {unavailable ? <MicOff size={18} /> : <Mic size={18} />}
      {status === 'listening' ? 'Listening' : 'Microphone'}
    </button>
  );
}

export function PushToTalkButton({ status, onToggle }: { status: SttStatus; onToggle: () => void }) {
  const listening = status === 'listening';
  return (
    <button className="ghost" aria-label={listening ? 'Listening...' : 'Push to talk'} onMouseDown={onToggle} type="button">
      <Mic size={18} /> {listening ? 'Listening...' : 'Push to talk'}
    </button>
  );
}

export function MicrophoneStatusBadge({ status }: { status: SttStatus }) {
  const text = status === 'permission_denied'
    ? 'Microphone permission was denied. Speech input is unavailable until permission is granted.'
    : `Mic: ${status}`;
  return <span className="statusText">{text}</span>;
}

export function MuteToggle({ muted, onToggle }: { muted: boolean; onToggle: () => void }) {
  return (
    <button className="ghost" aria-label={muted ? 'Unmute' : 'Mute'} onClick={onToggle}>
      {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
      {muted ? 'Unmute' : 'Mute'}
    </button>
  );
}

export function ReadAloudButton({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return <button className="ghost" aria-label="Read aloud" disabled={disabled} onClick={onClick}><Volume2 size={18} /> Read aloud</button>;
}

export function VoiceSelector({ voiceName }: { voiceName: string }) {
  return (
    <label className="voiceSelector">
      <span>Voice</span>
      <select aria-label="Voice selector" value={voiceName} onChange={() => undefined}>
        <option>{voiceName}</option>
        <option>US Google female</option>
      </select>
    </label>
  );
}

export function SpeechStatusBadge({ status, voiceName }: { status: TtsStatus; voiceName: string }) {
  return (
    <span className="statusText">Voice: {status} / {voiceName}</span>
  );
}

export function PlaybackControls({ onPause, onResume, onStop }: { onPause: () => void; onResume: () => void; onStop: () => void }) {
  return (
    <div className="playbackControls" aria-label="Playback controls">
      <button className="ghost iconButton" aria-label="Pause speech" onClick={onPause}><Pause size={18} /></button>
      <button className="ghost iconButton" aria-label="Resume speech" onClick={onResume}><Play size={18} /></button>
      <button className="ghost iconButton" aria-label="Stop speech" onClick={onStop}><Square size={18} /></button>
    </div>
  );
}

export function AudioDiagnosticsPanel({ chat, audio, avatar }: { chat: Record<string, unknown>; audio: Record<string, unknown>; avatar: Record<string, unknown> }) {
  const row = (label: string, value: unknown) => <div className="row split" key={label}><strong>{label}</strong><span>{String(value ?? '')}</span></div>;
  return (
    <details className="audioDiagnostics" aria-label="Audio diagnostics">
      <summary>Audio diagnostics</summary>
      <div className="diagnosticGrid">
        <section>{row('chat pending', chat.pending)}{row('current stage', chat.stage)}{row('last stage transition', chat.lastStageTransition)}{row('last API status', chat.lastApiStatus)}{row('last API error', chat.lastApiError)}{row('last timeout reason', chat.lastTimeoutReason)}{row('last response kind', chat.lastResponseKind)}{row('last response had text', chat.lastResponseHadText)}{row('last response had cards', chat.lastResponseHadCards)}{row('speech trigger reason', chat.speechTriggerReason)}{row('speech skip reason', chat.speechSkipReason)}</section>
        <section>{row('webAudioAvailable', audio.webAudioAvailable)}{row('audioContextState', audio.audioContextState)}{row('audioUnlocked', audio.audioUnlocked)}{row('rawBeepStarted', audio.rawBeepStarted)}{row('rawBeepEnded', audio.rawBeepEnded)}{row('rawBeepError', audio.rawBeepError)}{row('speechSynthesisAvailable', audio.speechSynthesisAvailable)}{row('speechSpeakCalled', audio.speechSpeakCalled)}{row('speechStarted', audio.speechStarted)}{row('speechEnded', audio.speechEnded)}{row('speechError', audio.speechError)}{row('muted', audio.muted)}{row('volume', audio.volume)}{row('lastAudibleProof', audio.lastAudibleProof)}{row('lastAudibleProofMethod', audio.lastAudibleProofMethod)}</section>
        <section>{row('requested voice label', audio.requestedVoiceLabel)}{row('actual selected voice name', audio.actualVoiceName)}{row('actual selected voice URI', audio.actualVoiceURI)}{row('actual selected voice lang', audio.actualVoiceLang)}{row('actual voice matched preference', audio.actualVoiceMatched)}{row('fallback reason', audio.voiceFallbackReason)}{row('last speak requested', audio.lastSpeakRequestedAt)}{row('last speak text length', audio.lastSpeakTextLength)}{row('last speak started', audio.lastSpeakStartedAt)}{row('last speak ended', audio.lastSpeakEndedAt)}{row('last speak error', audio.lastSpeakError)}{row('last speak timeout', audio.lastSpeakTimeout)}</section>
        <section>{row('avatar state', avatar.state)}{row('avatar waiting on audio', avatar.waitingOnAudio)}{row('video readyState', avatar.videoReadyState)}{row('video paused', avatar.videoPaused)}{row('video error', avatar.videoError)}{row('sync claimed', avatar.syncClaimed)}</section>
      </div>
    </details>
  );
}

export function AvatarPresencePanel({
  state,
  fallbackSrc,
  muted,
  volume,
  voices,
  selectedVoiceURI,
  voiceStatus,
  requestedVoiceLabel,
  actualVoiceName,
  voiceFallbackReason,
  micStatus,
  chatDiagnostics,
  audioDiagnostics,
  avatarDiagnostics,
  onToggleMute,
  onVolumeChange,
  onVoiceSelect,
  onRefreshVoices,
  onPreviewSelectedVoice,
  onResetStage,
  onStopAudio,
  onUnlockTestVoice,
  onPlayRawAudioTest
}: {
  state: AvatarRuntimeState;
  fallbackSrc: string;
  muted: boolean;
  volume: number;
  voices: VoiceOption[];
  selectedVoiceURI: string;
  voiceStatus: TtsStatus;
  requestedVoiceLabel: string;
  actualVoiceName: string;
  voiceFallbackReason: string;
  micStatus: SttStatus;
  chatDiagnostics: Record<string, unknown>;
  audioDiagnostics: Record<string, unknown>;
  avatarDiagnostics: Record<string, unknown>;
  onToggleMute: () => void;
  onVolumeChange: (value: number) => void;
  onVoiceSelect: (voiceURI: string) => void;
  onRefreshVoices: () => void;
  onPreviewSelectedVoice: () => void;
  onResetStage: () => void;
  onStopAudio: () => void;
  onUnlockTestVoice: () => void;
  onPlayRawAudioTest: () => void;
}) {
  return (
    <aside className="avatarPresence" aria-label="Avatar presence">
      <AvatarStage state={state} fallbackSrc={fallbackSrc} />
      <div className="assistantIdentityCard">
        <p className="eyebrow">Xoduz XV8</p>
        <h1>Assistant conversation</h1>
        <p className="avatarState">State: {state}</p>
      </div>
      <div className="compactStatus">
        <span>Mic: {micStatus}</span>
        <span>Voice: {voiceStatus} / {actualVoiceName || requestedVoiceLabel}</span>
      </div>
      {voiceFallbackReason && <p className="voiceFallback">{voiceFallbackReason}</p>}
      <details className="audioControls" aria-label="Audio controls" data-testid="avatar-audio-controls-panel">
        <summary data-testid="audio-controls-toggle">Audio controls</summary>
        <div className="audioControlGrid" aria-label="Avatar audio controls" data-testid="avatar-audio-controls">
          <button className="ghost iconButton speakerButton" aria-label={muted ? 'Unmute voice' : 'Mute voice'} data-testid="mute-button" onClick={onToggleMute}>
            {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <label className="volumeControl">
            <span>Volume</span>
            <input aria-label="Voice volume" data-testid="volume-slider" type="range" min="0" max="100" value={muted ? 0 : volume} onChange={(event) => onVolumeChange(Number(event.target.value))} />
          </label>
          <label className="voiceSelector">
            <span>Voice</span>
            <select aria-label="Voice selector" value={selectedVoiceURI} onChange={(event) => onVoiceSelect(event.target.value)}>
              {voices.length ? voices.map((voice) => <option key={voice.voiceURI || voice.name} value={voice.voiceURI}>{voice.label}</option>) : <option value="">No browser voices loaded</option>}
            </select>
          </label>
          <button className="ghost" type="button" onClick={onRefreshVoices}>Refresh voices</button>
          <button className="ghost" type="button" onClick={onPreviewSelectedVoice}>Preview selected voice</button>
          <button className="ghost" type="button" data-testid="reset-stage-button" onClick={onResetStage}>Reset stage</button>
          <button className="ghost" type="button" data-testid="stop-audio-button" onClick={onStopAudio}>Stop audio</button>
          <button className="ghost" type="button" data-testid="raw-audio-test-button" onClick={onPlayRawAudioTest}>Play raw audio test</button>
          <button className="ghost" type="button" data-testid="unlock-test-voice-button" onClick={onUnlockTestVoice}>Unlock/Test Voice</button>
        </div>
      </details>
      <AudioDiagnosticsPanel chat={chatDiagnostics} audio={audioDiagnostics} avatar={avatarDiagnostics} />
    </aside>
  );
}

export function Panel({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <article className="panel">
      <header>
        <span className="icon">{icon}</span>
        <h2>{title}</h2>
      </header>
      {children}
    </article>
  );
}
