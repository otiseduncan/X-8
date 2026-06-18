import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, ChevronDown, ChevronUp, Code2, Copy, FileText, GitBranch, Image, Info, Mic, MicOff, Pause, Play, Search, Send, ShieldCheck, Square, Volume2, VolumeX, X } from 'lucide-react';
import type { SpeechReceipt, SttStatus, TtsStatus } from '../audio/speechManagers';
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
  attachments?: AttachmentReference[];
  cards?: ChatCard[];
}

export type InfoReceipt = Receipt | SpeechReceipt | PromptReceipt | null;
export type AvatarRuntimeState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'muted' | 'error';

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

export function AvatarStage({ state, fallbackSrc = FALLBACK_AVATAR, controls }: { state: AvatarRuntimeState; fallbackSrc?: string; controls?: ReactNode }) {
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
      {controls && <div className="avatarAudioDock" aria-label="Avatar audio controls">{controls}</div>}
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
    sections.push(`## ${message.role === 'assistant' ? 'XV8' : 'User'}`);
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

export function ChatTimeline({ messages, onToggle, onRequestApply, onCopyMessage }: { messages: ChatMessage[]; onToggle: (cardId: string, patch: Partial<ChatCard>) => void; onRequestApply: (card: ChatCard) => void; onCopyMessage: (message: ChatMessage) => Promise<void> | void }) {
  const [copiedId, setCopiedId] = useState('');
  async function copy(message: ChatMessage) {
    await onCopyMessage(message);
    setCopiedId(message.id);
    window.setTimeout(() => setCopiedId((current) => (current === message.id ? '' : current)), 1200);
  }
  return (
    <section className="chatTimeline" aria-label="Chat timeline">
      {messages.map((message) => (
        <article key={message.id} className={`message ${message.role}`}>
          <div className="messageBubble">
            <p className="messageRole">{message.role === 'assistant' ? 'XV8' : 'You'}</p>
            <button className="messageCopyButton" type="button" aria-label={`Copy ${message.role === 'assistant' ? 'XV8' : 'You'} message`} onClick={() => void copy(message)}>
              <Copy size={13} /> {copiedId === message.id ? 'Copied' : 'Copy'}
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
          <button className="chipButton" onClick={onCopyTranscript}><Copy size={14} /> Copy transcript</button>
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

function InlineChatCard({ card, onToggle, onRequestApply }: { card: ChatCard; onToggle: (cardId: string, patch: Partial<ChatCard>) => void; onRequestApply: (card: ChatCard) => void }) {
  const [tab, setTab] = useState('Preview');
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

  return (
    <section className={`inlineCard ${card.type}`} data-testid={`inline-${card.type}-card`}>
      <header className="inlineCardHeader">
        <span className="icon small">{icon}</span>
        <div>
          <p className="cardMeta">{card.type} / {card.status}</p>
          <h2>{card.title}</h2>
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
          {card.type === 'artifact' && <ArtifactBody card={card} tab={tab} setTab={setTab} />}
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

function ArtifactBody({ card, tab, setTab }: { card: ChatCard; tab: string; setTab: (tab: string) => void }) {
  const html = String(card.payload?.html || '');
  const css = String(card.payload?.css || '');
  return (
    <>
      <div className="tabs">
        {['Preview', 'Code', 'Metadata'].map((name) => <button key={name} className={tab === name ? 'tab active' : 'tab'} onClick={() => setTab(name)}>{name}</button>)}
      </div>
      {tab === 'Preview' && <iframe title="Inline website preview" srcDoc={`<style>${css}</style>${html}`} sandbox="" />}
      {tab === 'Code' && <pre className="codeBlock">{`<style>${css}</style>\n${html}`}</pre>}
      {tab === 'Metadata' && <pre className="codeBlock">{JSON.stringify(card.payload?.metadata || {}, null, 2)}</pre>}
      <div className="inlineActions"><button className="chipButton">Export</button><button className="chipButton">Apply</button></div>
    </>
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
  const reason = String(applyResult.reason || '');
  return (
    <div className="stack">
      <p className="cardSummary">{card.summary}</p>
      <div className="row split"><strong>Task</strong><span>{String(card.payload?.task_id || 'unknown')}</span></div>
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

export function PushToTalkButton({ onStart }: { onStart: () => void }) {
  return (
    <button className="ghost" aria-label="Push to talk" onMouseDown={onStart}>
      <Mic size={18} /> Push to talk
    </button>
  );
}

export function TranscriptPreview({ transcript, onCancel, onSend }: { transcript: string; onCancel: () => void; onSend: () => void }) {
  return (
    <section className="transcriptPreview" aria-label="Transcript preview">
      <div>
        <p className="cardMeta">STT transcript preview</p>
        <p>{transcript}</p>
      </div>
      <div className="inlineActions">
        <CancelTranscriptButton onCancel={onCancel} />
        <SendTranscriptButton onSend={onSend} />
      </div>
    </section>
  );
}

export function MicrophoneStatusBadge({ status }: { status: SttStatus }) {
  const text = status === 'permission_denied'
    ? 'Microphone permission was denied. Speech input is unavailable until permission is granted.'
    : `Mic: ${status}`;
  return <span className="statusText">{text}</span>;
}

function CancelTranscriptButton({ onCancel }: { onCancel: () => void }) {
  return <button className="chipButton" onClick={onCancel}><X size={14} /> Cancel transcript</button>;
}

function SendTranscriptButton({ onSend }: { onSend: () => void }) {
  return <button className="chipButton" onClick={onSend}><Send size={14} /> Send transcript</button>;
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
