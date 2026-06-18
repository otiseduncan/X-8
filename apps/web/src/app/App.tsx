import { Activity, Boxes, Check, ChevronDown, ChevronUp, Code2, Copy, FileText, GitBranch, Image, Info, Mic, MicOff, Paperclip, Pause, Play, Search, Send, Server, Settings, ShieldCheck, Square, Users, Volume2, VolumeX, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { SpeechInputManager, SpeechOutputManager } from '../audio/speechManagers';
import type { SpeechReceipt, SttStatus, TtsStatus } from '../audio/speechManagers';
import { applyUpdate, createArtifactPreview, createSpeechReceipt, loadAvatarManifest, loadBridgeStatus, loadCapabilities, loadConfigImportStatus, loadDockerPresets, loadFiles, loadGitHubStatus, loadImageStatus, loadIntegrations, loadMemoryStatus, loadModelStatus, loadReceipts, loadSearchStatus, loadSession, loadSessions, loadSpeechStatus, loadTeam, proposeUpdate, readFile, requestImage, runSearch, runSelfBuildPrompt, scanX7Configs, sendChat, uploadAttachment } from '../services/apiClient';
import type { AttachmentReference, Capability, FileEntry, IntegrationStatus, PatchProposal, SessionDetail, TeamSeat } from '../types/contracts';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { StatusPill } from '../components/ui/StatusPill';
import { AvatarStage, ChatTimeline, InfoDropdown, Panel, PushToTalkButton, TranscriptPreview, messageCopyText, transcriptMarkdown } from './AssistantComponents';
import type { AvatarRuntimeState, ChatCard, ChatMessage, InfoReceipt } from './AssistantComponents';
import { errorCard, mapKernelCard, receiptCards } from './cardHelpers';

const nowId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const speechInput = new SpeechInputManager();
const speechOutput = new SpeechOutputManager();

export function App() {
  const userInteracted = useRef(false);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [team, setTeam] = useState<TeamSeat[]>([]);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [dockerPresets, setDockerPresets] = useState<string[]>([]);
  const [githubStatus, setGithubStatus] = useState('loading');
  const [searchStatus, setSearchStatus] = useState('loading');
  const [imageStatus, setImageStatus] = useState('loading');
  const [bridgeStatus, setBridgeStatus] = useState('loading');
  const [importStatus, setImportStatus] = useState('loading');
  const [x7ImportStatus, setX7ImportStatus] = useState('loading');
  const [x6ImportStatus, setX6ImportStatus] = useState('loading');
  const [legacySignals, setLegacySignals] = useState('No legacy scan yet.');
  const [avatarStatus, setAvatarStatus] = useState('loading');
  const [avatarAsset, setAvatarAsset] = useState('/avatar/fallback.svg');
  const [speechStatus, setSpeechStatus] = useState('loading');
  const [speechState, setSpeechState] = useState<AvatarRuntimeState>('idle');
  const [micStatus, setMicStatus] = useState<SttStatus>('permission_required');
  const [voiceStatus, setVoiceStatus] = useState<TtsStatus>('ready');
  const [transcript, setTranscript] = useState('');
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(() => Number(window.localStorage.getItem('x8.voiceVolume') || '80'));
  const [previousVolume, setPreviousVolume] = useState(() => Number(window.localStorage.getItem('x8.voicePreviousVolume') || '80'));
  const [voiceName, setVoiceName] = useState('US Google female');
  const [audioReceipts, setAudioReceipts] = useState<SpeechReceipt[]>([]);
  const [latestReceipt, setLatestReceipt] = useState<InfoReceipt>(null);
  const [latestResult, setLatestResult] = useState('Ready.');
  const [modelStatus, setModelStatus] = useState('checking');
  const [modelDetails, setModelDetails] = useState<Record<string, unknown>>({});
  const [memoryStatus, setMemoryStatus] = useState('checking');
  const [memoryDetails, setMemoryDetails] = useState<Record<string, unknown>>({});
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [selectedPath, setSelectedPath] = useState('README.md');
  const [code, setCode] = useState('');
  const [proposal, setProposal] = useState<PatchProposal | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [developerOpen, setDeveloperOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [entry, setEntry] = useState('');
  const [attachments, setAttachments] = useState<AttachmentReference[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Ready. Ask me what you want to build, inspect, search, preview, or fix.'
    }
  ]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([loadCapabilities(), loadIntegrations(), loadTeam(), loadFiles(), loadDockerPresets(), loadGitHubStatus(), loadSearchStatus(), loadImageStatus(), loadBridgeStatus(), loadConfigImportStatus(), loadAvatarManifest(), loadSpeechStatus()])
      .then(([caps, ints, seats, fileList, presets, github, search, image, bridge, configImport, avatar, speech]) => {
        setCapabilities(caps.data);
        setIntegrations(ints.data);
        setTeam(seats.data);
        setFiles(fileList.data.filter((item) => item.kind === 'file').slice(0, 80));
        setDockerPresets(presets.data);
        setGithubStatus(github.data.status);
        setSearchStatus(String(search.data.status || search.status));
        setImageStatus(String(image.data.status || image.status));
        setBridgeStatus(String(bridge.data.bridge_reachable ? 'reachable' : 'unreachable'));
        setX7ImportStatus(`${configImport.data.x7_import_status || 'unknown'} / ${configImport.data.x7_files_found || 0} files`);
        setX6ImportStatus(`${configImport.data.x6_import_status || 'unknown'} / ${configImport.data.x6_files_found || 0} files`);
        setImportStatus(`X7 ${configImport.data.x7_files_found || 0}, X6 ${configImport.data.x6_files_found || 0}`);
        setLegacySignals(`GitHub X7: ${configImport.data.github_config_found_in_x7 ? 'yes' : 'no'} | ComfyUI X6: ${configImport.data.comfyui_config_found_in_x6 ? 'yes' : 'no'} | Search X6: ${configImport.data.search_config_found_in_x6 ? 'yes' : 'no'}`);
        setAvatarStatus(String(avatar.status));
        setAvatarAsset(String(avatar.data.default_asset || '/avatar/fallback.svg'));
        setSpeechStatus(String(speech.status));
        setMicStatus(speechInput.supported() ? 'permission_required' : 'unavailable');
        setVoiceStatus(speechOutput.tts.supported() ? 'ready' : 'unavailable');
      })
      .catch(() => setError('Runtime status could not load. Check docker compose logs x8-api.'));
  }, []);

  useEffect(() => {
    Promise.allSettled([loadSessions(), loadModelStatus(), loadMemoryStatus(), loadReceipts()]).then(([sessionsResult, modelResult, memoryResult, receiptResult]) => {
      if (modelResult.status === 'fulfilled') {
        setModelDetails(modelResult.value.data || {});
        setModelStatus(`${String(modelResult.value.data?.selected_model || modelResult.value.status)} / ${String(modelResult.value.status)}`);
      }
      if (memoryResult.status === 'fulfilled') {
        setMemoryDetails(memoryResult.value.data || {});
        setMemoryStatus(String(memoryResult.value.status));
      }
      if (receiptResult.status === 'fulfilled' && receiptResult.value.data.length > 0) {
        const receipt = receiptResult.value.data[0];
        setLatestResult(String(receipt.status || 'receipt loaded'));
      }
      if (sessionsResult.status !== 'fulfilled') return;
      const saved = window.localStorage.getItem('x8.activeSessionId');
      const candidate = saved || sessionsResult.value.data[0]?.session_id;
      if (!candidate) return;
      loadSession(candidate)
        .then((response) => restoreSession(response.data))
        .catch(() => undefined);
    });
  }, []);

  function restoreSession(session: SessionDetail) {
    if (userInteracted.current) return;
    setSessionId(session.session_id);
    window.localStorage.setItem('x8.activeSessionId', session.session_id);
    if (session.messages.length === 0) return;
    setMessages(session.messages.map((message) => ({
      id: message.message_id,
      role: message.role,
      text: message.content,
      attachments: message.attachments || []
    })));
    const latest = session.receipts[0];
    if (latest) {
      setLatestResult(`Session restored: ${String(latest.status || 'ok')}`);
    }
  }
  useEffect(() => {
    readFile(selectedPath)
      .then((response) => setCode(response.data.content))
      .catch(() => setCode('File could not be loaded from the configured workspace root.'));
  }, [selectedPath]);
  function appendMessage(message: ChatMessage) {
    setMessages((current) => [...current, message]);
  }

  function appendAudioReceipt(receipt: SpeechReceipt) {
    setAudioReceipts((current) => [receipt, ...current].slice(0, 8));
    setLatestReceipt(receipt);
    setLatestResult(`Audio: ${receipt.status}`);
  }

  function updateCard(cardId: string, patch: Partial<ChatCard>) {
    setMessages((current) =>
      current.map((message) => ({
        ...message,
        cards: message.cards?.map((card) => (card.id === cardId ? { ...card, ...patch } : card))
      }))
    );
  }

  function classifyRequest(text: string) {
    const lower = text.toLowerCase();
    if (lower.includes('self-build') || (lower.includes('patch') && lower.includes('do not commit')) || (lower.includes('completion rule') && lower.includes('tests'))) return 'self_build';
    if (lower.includes('open') && lower.includes('readme')) return 'file';
    if (lower.includes('propose') && (lower.includes('edit') || lower.includes('diff'))) return 'diff';
    if (lower.includes('website') || lower.includes('preview') || lower.includes('html')) return 'artifact';
    if (lower.includes('search') || lower.includes('searxng')) return 'research';
    if (lower.includes('image') || lower.includes('generate')) return 'image';
    if (lower.includes('test')) return 'test';
    return 'chat';
  }

  async function submitMessage(event?: React.FormEvent) {
    event?.preventDefault();
    userInteracted.current = true;
    const text = entry.trim();
    if (!text && attachments.length === 0) return;
    const outgoingAttachments = attachments;
    setEntry('');
    setAttachments([]);
    setError('');
    setSpeechState('thinking');
    appendMessage({ id: nowId(), role: 'user', text: text || 'Attached files for reference.', attachments: outgoingAttachments });
    return handleUserText(text || 'Attached files for reference.', outgoingAttachments);
  }

  async function handleUserText(text: string, outgoingAttachments: AttachmentReference[] = []) {
    const intent = classifyRequest(text);
    if (intent === 'file') return openFileCard('README.md');
    if (intent === 'diff') return proposeDiffCard('README.md');
    if (intent === 'artifact') return createArtifactCard(text);
    if (intent === 'research') return createResearchCard(text);
    if (intent === 'image') return createImageCard(text);
    if (intent === 'test') return createTestCard(text);
    if (intent === 'self_build') return createSelfBuildCards(text);
    return createAssistantReply(text, outgoingAttachments);
  }

  function startMicrophone() {
    if (!speechInput.supported()) {
      setMicStatus('unavailable');
      setSpeechState('error');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Speech input is unavailable in this browser.',
        cards: [errorCard('STT unavailable', 'Browser Web Speech API is unavailable. No transcription was invented.')]
      });
      return;
    }
    setTranscript('');
    speechInput.transcript.clear();
    setSpeechState('listening');
    speechInput.recognition.start({
      onStatus: (status) => {
        setMicStatus(status);
        if (status === 'listening') setSpeechState('listening');
        if (status === 'transcribing') setSpeechState('thinking');
        if (status === 'permission_denied' || status === 'error') setSpeechState('error');
        if (status === 'permission_denied') {
          appendMessage({
            id: nowId(),
            role: 'assistant',
            text: 'Microphone permission was denied. Speech input is unavailable until permission is granted.',
            cards: [errorCard('Microphone permission denied', 'Microphone permission was denied. Speech input is unavailable until permission is granted.')]
          });
        }
      },
      onTranscript: (value) => {
        setSpeechState('thinking');
        setTranscript(speechInput.transcript.set(value));
      },
      onReceipt: appendAudioReceipt
    });
  }

  function cancelTranscript() {
    speechInput.recognition.stop();
    speechInput.transcript.clear();
    setTranscript('');
    setMicStatus(speechInput.supported() ? 'ready' : 'unavailable');
    setSpeechState(muted ? 'muted' : 'idle');
    appendAudioReceipt({
      receipt_id: nowId(),
      provider: speechInput.supported() ? 'browser_web_speech_api' : 'unavailable',
      status: 'speech_input_cancelled',
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      locale: 'en-US',
      permission_status: micStatus,
      transcript_length: transcript.length
    });
  }

  function sendTranscript() {
    const value = transcript.trim();
    if (!value) return;
    appendAudioReceipt({
      receipt_id: nowId(),
      provider: 'browser_web_speech_api',
      status: 'speech_input_sent',
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      locale: 'en-US',
      permission_status: micStatus,
      transcript_length: value.length
    });
    setEntry('');
    setTranscript('');
    speechInput.transcript.clear();
    setMicStatus(speechInput.supported() ? 'ready' : 'unavailable');
      appendMessage({ id: nowId(), role: 'user', text: value });
      setSpeechState('thinking');
      void handleUserText(value);
  }

  async function createAssistantReply(text: string, outgoingAttachments: AttachmentReference[] = []) {
    try {
      setLatestResult('Model warming/responding...');
      const response = await sendChat(text, outgoingAttachments, sessionId);
      setSessionId(response.data.session_id);
      window.localStorage.setItem('x8.activeSessionId', response.data.session_id);
      setLatestReceipt(response.data.receipt || response.receipts?.[0] || null);
      setLatestResult(outgoingAttachments.length ? `Attachments processed: ${response.status}` : response.status);
      appendMessage({
        id: response.data.message_id || nowId(),
        role: 'assistant',
        text: response.data.assistant_message.content,
        attachments: response.data.attachments,
        cards: response.data.assistant_message.cards.map(mapKernelCard)
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({ id: nowId(), role: 'assistant', text: 'The chat request could not complete.', cards: [errorCard('Chat request failed', 'API request failed.')] });
    }
  }

  async function openFileCard(path: string) {
    try {
      const response = await readFile(path);
      setSelectedPath(path);
      setCode(response.data.content);
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult(`Opened ${path}`);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: `Opened ${path}.`,
        cards: [
          {
            id: nowId(),
            type: 'file',
            title: path,
            status: response.status,
            summary: `${response.data.line_count} lines loaded into an inline file viewer.`,
            receipt: response.receipts?.[0],
            payload: { path, content: response.data.content }
          }
        ]
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({ id: nowId(), role: 'assistant', text: `I could not open ${path}.`, cards: [errorCard('File read failed', 'The workspace read endpoint returned an error.')] });
    }
  }

  async function proposeDiffCard(path: string) {
    try {
      const current = await readFile(path);
      const next = current.data.content.endsWith('\n') ? `${current.data.content}<!-- XV8 proposed note -->\n` : `${current.data.content}\n<!-- XV8 proposed note -->\n`;
      setSelectedPath(path);
      setCode(next);
      const response = await proposeUpdate(path, next);
      setProposal(response.data);
      setLatestReceipt(response.data.receipt);
      setLatestResult(`Diff proposal for ${path}`);
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult('Generated inline artifact preview');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: `Prepared a local edit proposal for ${path}. No mutation has happened.`,
        cards: [
          {
            id: nowId(),
            type: 'editor',
            title: `Editor draft: ${path}`,
            status: 'draft',
            summary: 'The draft is local to this chat card. Applying it requires click approval.',
            payload: { path, content: next },
            collapsed: true
          },
          {
            id: nowId(),
            type: 'diff',
            title: `Diff proposal: ${path}`,
            status: response.data.receipt.status,
            summary: response.data.receipt.summary,
            receipt: response.data.receipt,
            payload: {
              path,
              diff: response.data.diff,
              risk: response.data.approval?.risk || 'medium',
              beforeAfter: response.data.approval?.intent.before_after_summary || 'Content would change only after approval.',
              approvalState: response.data.approval?.status || 'approval_required'
            }
          },
          {
            id: nowId(),
            type: 'approval',
            title: 'Apply requires approval',
            status: response.data.approval?.status || 'pending',
            summary: 'Click Apply inside this card to open the focused approval dialog.',
            receipt: response.data.receipt,
            payload: { path }
          }
        ]
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({ id: nowId(), role: 'assistant', text: `I could not prepare a diff for ${path}.`, cards: [errorCard('Diff proposal failed', 'No repository mutation was attempted.')] });
    }
  }

  async function createArtifactCard(prompt: string) {
    try {
      const response = await createArtifactPreview('Inline website preview', prompt);
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult(`Search status: ${response.status}`);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Generated an inline website artifact preview.',
        cards: [
          {
            id: nowId(),
            type: 'artifact',
            title: 'Inline website preview',
            status: response.status,
            summary: 'Preview, code, and metadata are attached to this chat response.',
            receipt: response.receipts?.[0],
            payload: {
              html: response.data.html,
              css: response.data.css,
              metadata: { title: response.data.title, exportable: true }
            }
          }
        ]
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({ id: nowId(), role: 'assistant', text: 'The artifact preview could not be generated.', cards: [errorCard('Artifact preview failed', 'No files were written.')] });
    }
  }

  async function createSelfBuildCards(prompt: string) {
    try {
      const response = await runSelfBuildPrompt(prompt);
      const detail = response.data?.proposal_detail || {};
      const task = response.data?.task || {};
      const intent = response.data?.intent || 'create_proposal';
      const changes = detail.changes || task.proposal?.changes || [];
      const changedPaths = detail.changed_file_paths || changes.map((change: { file_path?: string }) => change.file_path).filter(Boolean);
      const firstChange = changes[0] || {};
      setLatestResult(intent === 'create_proposal' ? 'Self-build patch plan created' : `Self-build ${response.status}`);
      setLatestReceipt(response.receipts?.[0] || null);
      if (!detail.patch_hash) {
        appendMessage({
          id: nowId(),
          role: 'assistant',
          text: response.message,
          cards: [{ id: nowId(), type: 'receipt', title: 'Self-build status', status: response.status, summary: response.message, payload: response.data, collapsed: false }]
        });
        setSpeechState(muted ? 'muted' : 'idle');
        return;
      }
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: detail.message || 'No files changed. Approval required before apply.',
        cards: [
          { id: nowId(), type: 'receipt', title: 'Self-build prompt detected', status: response.status, summary: 'No files changed. Approval required before apply.', payload: { task_id: detail.task_id, patch_id: detail.patch_id, approval_id: detail.approval_id, patch_hash: detail.patch_hash } },
          { id: nowId(), type: 'receipt', title: 'Self-build patch plan', status: detail.validation_status || task.plan?.status || 'created', summary: `${detail.files_changed_count || changedPaths.length || 0} file change(s): ${changedPaths.join(', ') || 'none'}`, payload: { ...detail, risk_level: detail.risk_level, validation_status: detail.validation_status }, collapsed: false },
          { id: nowId(), type: 'diff', title: 'Self-build patch proposal', status: detail.validation_status || 'proposed', summary: `${detail.files_changed_count || changedPaths.length || 0} proposed file change(s).`, payload: { diff: firstChange.unified_diff || '', path: firstChange.file_path || changedPaths[0] || '', approvalState: detail.approval_id ? 'pending_click' : 'blocked', before_hash: firstChange.before_hash, after_hash: firstChange.after_hash }, collapsed: true },
          { id: nowId(), type: 'approval', title: 'Approval required before apply', status: detail.approval_id ? 'pending_click' : 'blocked', summary: 'Applying this patch requires popup approval tied to the exact patch hash.', payload: { task_id: detail.task_id, patch_id: detail.patch_id, approval_id: detail.approval_id, patch_hash: detail.patch_hash } }
        ]
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({ id: nowId(), role: 'assistant', text: 'Self-build planning could not complete.', cards: [errorCard('Self-build failed', 'No files were changed.')] });
    }
  }

  async function createResearchCard(query: string) {
    try {
      const response = await runSearch(query.replace(/search|searxng/gi, '').trim() || query);
      const results = response.data.results || [];
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult(`Image status: ${response.status}`);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: results.length ? 'Search results are attached inline.' : 'Search was attempted; provider status is shown inline.',
        cards: [
          {
            id: nowId(),
            type: 'research',
            title: 'Inline research results',
            status: response.status,
            summary: response.message,
            receipt: response.receipts?.[0],
            payload: {
              query,
              provider: response.data.provider || 'SearXNG',
              results,
              freshness: 'Runtime provider response; verify dates in cited sources for time-sensitive claims.'
            }
          }
        ]
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Search is unavailable right now.',
        cards: [errorCard('Provider unavailable', 'SearXNG search could not be reached. No search results were invented.')]
      });
    }
  }

  async function createImageCard(prompt: string) {
    try {
      const response = await requestImage(prompt);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Image generation status is attached inline.',
        cards: [
          {
            id: nowId(),
            type: response.status === 'ok' ? 'image' : 'error',
            title: response.status === 'ok' ? 'Inline image result' : 'Image generation unavailable',
            status: response.status,
            summary: response.status === 'ok' ? response.message : 'Reason: ComfyUI service unreachable or Juggernaut model missing. No image was generated.',
            receipt: response.receipts?.[0],
            payload: {
              prompt,
              model: 'Juggernaut',
              workflow: 'ComfyUI default',
              seed: response.data.seed || 'pending',
              imageUrl: response.data.image_url || ''
            }
          }
        ]
      });
      setSpeechState(muted ? 'muted' : 'idle');
    } catch {
      setSpeechState('error');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Image generation unavailable.',
        cards: [errorCard('Image generation unavailable', 'Reason: ComfyUI service unreachable or Juggernaut model missing. No image was generated.')]
      });
    }
  }

  function createTestCard(text: string) {
    setLatestResult('Test run queued for approval');
    appendMessage({
      id: nowId(),
      role: 'assistant',
      text: 'Test execution needs approval before Docker work starts.',
      cards: [
        {
          id: nowId(),
          type: 'test',
          title: 'Docker test run',
          status: 'approval_required',
          summary: `Requested: ${text}. No test command has run yet.`,
          receipt: { id: nowId(), action: 'test_run', status: 'approval_required', summary: 'Click approval is required before execution.' },
          payload: { command: 'docker compose run --rm api-tests' }
        }
      ]
    });
    setSpeechState(muted ? 'muted' : 'idle');
  }

  async function requestApply() {
    const response = await applyUpdate(selectedPath, code, false);
    setProposal(response.data);
    setApprovalOpen(true);
  }

  async function approveApply() {
    const response = await applyUpdate(selectedPath, code, true);
    setProposal(response.data);
    setApprovalOpen(false);
    setLatestReceipt(response.data.receipt);
    setLatestResult(response.data.mutated ? `Applied ${selectedPath}` : `Did not apply ${selectedPath}`);
    appendMessage({
      id: nowId(),
      role: 'assistant',
      text: response.data.mutated ? `Applied the approved change to ${selectedPath}.` : `The change to ${selectedPath} was not applied.`,
      cards: [
        {
          id: nowId(),
          type: 'receipt',
          title: `Receipt: ${response.data.receipt.action}`,
          status: response.data.receipt.status,
          summary: response.data.receipt.summary,
          receipt: response.data.receipt
        }
      ]
    });
  }

  async function attachFiles(fileList: FileList | null) {
    if (!fileList) return;
    for (const file of Array.from(fileList)) {
      const pending: AttachmentReference = {
        attachment_id: `pending-${nowId()}`,
        filename: file.name,
        mime_type: file.type || 'application/octet-stream',
        size_bytes: file.size,
        status: 'uploading'
      };
      setAttachments((current) => [...current, pending]);
      try {
        const response = await uploadAttachment(file);
        setAttachments((current) => current.map((attachment) => (attachment.attachment_id === pending.attachment_id ? response.data : attachment)));
        setLatestReceipt(response.receipts?.[0] || null);
        setLatestResult(`${response.data.filename}: ${response.data.status}`);
      } catch {
        setAttachments((current) => current.map((attachment) => (attachment.attachment_id === pending.attachment_id ? { ...attachment, status: 'failed' } : attachment)));
        setLatestResult(`${file.name}: upload failed`);
      }
    }
  }

  function removeAttachment(attachmentId: string) {
    setAttachments((current) => current.filter((attachment) => attachment.attachment_id !== attachmentId));
  }

  async function submitConfigScan() {
    const response = await scanX7Configs();
    setImportStatus(`X7 ${response.data.x7_files_found} files, X6 ${response.data.x6_files_found} files`);
    setX7ImportStatus(`${response.data.x7_import_status.import_status} / ${response.data.x7_files_found} files`);
    setX6ImportStatus(`${response.data.x6_import_status.import_status} / ${response.data.x6_files_found} files`);
    setLegacySignals(`${response.data.providers_found.length} providers, ${response.data.secrets_detected_redacted.length} redacted secrets`);
  }

  async function readAloud() {
    const latest = [...messages].reverse().find((message) => message.role === 'assistant')?.text || 'XV8 is ready.';
    if (muted) {
      setVoiceStatus('muted');
      setSpeechState('muted');
      return;
    }
    if (!speechOutput.tts.supported()) {
      setVoiceStatus('unavailable');
      setSpeechState('error');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Text-to-speech is unavailable in this browser.',
        cards: [errorCard('TTS unavailable', 'No Google Cloud TTS credentials are configured and browser speech synthesis is unavailable.')]
      });
      return;
    }
    speechOutput.tts.speak(latest, {
      onStatus: (status) => {
        setVoiceStatus(status);
        setSpeechState(status === 'speaking' ? 'speaking' : status === 'error' ? 'error' : 'idle');
      },
      onVoice: setVoiceName,
      onReceipt: appendAudioReceipt
    }, volume / 100);
    try {
      await createSpeechReceipt();
    } catch {
      appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_failed', 'receipt_error', new Date().toISOString(), voiceName, 'Backend speech receipt endpoint failed.'));
    }
  }

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    if (next) {
      if (volume > 0) {
        setPreviousVolume(volume);
        window.localStorage.setItem('x8.voicePreviousVolume', String(volume));
      }
      speechOutput.playback.stop();
      setVoiceStatus('muted');
      setSpeechState('muted');
      appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_stopped', 'muted', new Date().toISOString(), voiceName));
    } else {
      if (volume === 0) {
        setVolume(previousVolume || 80);
        window.localStorage.setItem('x8.voiceVolume', String(previousVolume || 80));
      }
      setVoiceStatus(speechOutput.tts.supported() ? 'ready' : 'unavailable');
      setSpeechState('idle');
    }
  }

  function changeVolume(value: number) {
    const next = Math.max(0, Math.min(100, value));
    setVolume(next);
    window.localStorage.setItem('x8.voiceVolume', String(next));
    if (next > 0) {
      setPreviousVolume(next);
      window.localStorage.setItem('x8.voicePreviousVolume', String(next));
      if (muted) {
        setMuted(false);
        setVoiceStatus(speechOutput.tts.supported() ? 'ready' : 'unavailable');
        setSpeechState('idle');
      }
    } else {
      setMuted(true);
      speechOutput.playback.stop();
      setVoiceStatus('muted');
      setSpeechState('muted');
    }
  }

  async function writeClipboard(text: string) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', 'true');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  }

  async function copyMessage(message: ChatMessage) {
    await writeClipboard(messageCopyText(message));
    setLatestResult('Copied message.');
  }

  function copyTranscript(includeReceipts = false) {
    void writeClipboard(transcriptMarkdown(messages, includeReceipts));
    setLatestResult(includeReceipts ? 'Copied transcript with receipts.' : 'Copied transcript.');
  }

  function downloadTranscript() {
    const blob = new Blob([transcriptMarkdown(messages, false)], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'xv8-transcript.md';
    link.click();
    URL.revokeObjectURL(url);
    setLatestResult('Downloaded transcript.');
  }

  function pauseSpeech() {
    speechOutput.playback.pause();
    setVoiceStatus('paused');
    setSpeechState('idle');
    appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_paused', 'paused', new Date().toISOString(), voiceName));
  }

  function resumeSpeech() {
    speechOutput.playback.resume();
    setVoiceStatus('speaking');
    setSpeechState('speaking');
    appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_resumed', 'speaking', new Date().toISOString(), voiceName));
  }

  function stopSpeech() {
    speechOutput.playback.stop();
    setVoiceStatus(muted ? 'muted' : 'ready');
    setSpeechState(muted ? 'muted' : 'idle');
    appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_stopped', 'stopped', new Date().toISOString(), voiceName));
  }

  return (
    <main className="shell" data-theme="neon-blue">
      <section className="assistantFrame" aria-label="Assistant Mode">
        <aside className="avatarPresence" aria-label="Avatar presence">
          <AvatarStage
            state={speechState}
            fallbackSrc={avatarAsset}
            controls={
              <>
                <button className="ghost iconButton speakerButton" aria-label={muted ? 'Unmute voice' : 'Mute voice'} onClick={toggleMute}>
                  {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
                </button>
                <label className="volumeControl">
                  <span>Voice</span>
                  <input aria-label="Voice volume" type="range" min="0" max="100" value={muted ? 0 : volume} onChange={(event) => changeVolume(Number(event.target.value))} />
                </label>
                <span className="voiceMiniStatus">Voice: {voiceStatus} / {muted ? 0 : volume}%</span>
              </>
            }
          />
          <div className="assistantIdentityCard">
            <p className="eyebrow">Xoduz XV8</p>
            <h1>Assistant conversation</h1>
            <p className="avatarState">State: {speechState}</p>
          </div>
          <div className="compactStatus">
            <span>Mic: {micStatus}</span>
            <span>Voice: {voiceStatus}</span>
          </div>
        </aside>

        <section className="conversationPane">
          <header className="conversationHeader">
            <div className="modeLabel">Assistant Mode</div>
            <div className="topbarActions">
              <InfoDropdown
                open={infoOpen}
                onToggle={() => setInfoOpen((open) => !open)}
                bridgeStatus={bridgeStatus}
                modelStatus={modelStatus}
                memoryStatus={memoryStatus}
                githubStatus={githubStatus}
                voiceStatus={voiceStatus}
                voiceName={voiceName}
                latestReceipt={latestReceipt}
                latestResult={latestResult}
                onCopyTranscript={() => copyTranscript(false)}
                onCopyTranscriptWithReceipts={() => copyTranscript(true)}
                onDownloadTranscript={downloadTranscript}
              />
              <button className="ghost iconButton" aria-expanded={developerOpen} aria-label="Settings" onClick={() => setDeveloperOpen((open) => !open)}>
                <Settings size={18} />
              </button>
            </div>
          </header>

          {error && <div className="error">{error}</div>}

          <ChatTimeline messages={messages} onToggle={updateCard} onRequestApply={requestApply} onCopyMessage={copyMessage} />

          <form className="messageEntry" onSubmit={submitMessage}>
            {attachments.length > 0 && (
              <div className="attachmentTray" aria-label="Attached files">
                {attachments.map((attachment) => (
                  <span className="attachmentChip" key={attachment.attachment_id}>
                    {attachment.filename} <small>{Math.ceil(attachment.size_bytes / 1024)} KB / {attachment.status}</small>
                    <button type="button" aria-label={`Remove ${attachment.filename}`} onClick={() => removeAttachment(attachment.attachment_id)}><X size={13} /></button>
                  </span>
                ))}
              </div>
            )}
            {transcript && (
              <TranscriptPreview
                transcript={transcript}
                onCancel={cancelTranscript}
                onSend={sendTranscript}
              />
            )}
            <div className="inputDock">
              <label className="ghost iconButton attachButton" aria-label="Attach file">
                <Paperclip size={18} />
                <input aria-label="Attach file input" type="file" multiple onChange={(event) => attachFiles(event.target.files)} />
              </label>
              <textarea
                aria-label="Message XV8"
                value={entry}
                onChange={(event) => setEntry(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void submitMessage();
                  }
                }}
                placeholder="Ask XV8 anything..."
              />
              <PushToTalkButton onStart={startMicrophone} />
              <button className="primary" type="submit" disabled={!entry.trim() && attachments.length === 0}>
                <Send size={18} /> Send
              </button>
            </div>
          </form>
        </section>
      </section>

      {developerOpen && (
        <section className="developerCockpit" aria-label="Developer Cockpit Mode">
          <Panel icon={<FileText />} title="Project File Tree">
            <div className="fileList">
              {files.map((file) => (
                <button key={file.path} className={file.path === selectedPath ? 'file active' : 'file'} onClick={() => setSelectedPath(file.path)}>
                  {file.path}
                </button>
              ))}
            </div>
          </Panel>
          <Panel icon={<Code2 />} title="Full Editor">
            <div className="editorHead">
              <span>{selectedPath}</span>
              <div className="actions">
                <button className="ghost" onClick={() => proposeDiffCard(selectedPath)}>Propose diff</button>
                <button className="ghost" onClick={requestApply}>Apply</button>
              </div>
            </div>
            <CodeEditor path={selectedPath} value={code} onChange={setCode} />
          </Panel>
          <Panel icon={<GitBranch />} title="Full Diff Viewer">
            <pre className="diff">{proposal?.diff || 'No patch proposed yet. Editing here does not mutate the repo.'}</pre>
          </Panel>
          <Panel icon={<Search />} title="SearXNG Panel">
            <div className="list dense">
              <div className="row split"><strong>Search</strong><StatusPill label={searchStatus} status={searchStatus} /></div>
              <div className="row"><strong>Provider</strong><span>SearXNG local first</span></div>
            </div>
          </Panel>
          <Panel icon={<Image />} title="Image Studio">
            <div className="list dense">
              <div className="row split"><strong>Image</strong><StatusPill label={imageStatus} status={imageStatus} /></div>
              <div className="row split"><strong>Model</strong><span>Juggernaut</span></div>
              <div className="row"><strong>Workflow</strong><span>ComfyUI default</span></div>
            </div>
          </Panel>
          <Panel icon={<Activity />} title="Model + Runtime">
            <div className="list dense">
              <div className="row split"><strong>Ollama mode</strong><span>{String(modelDetails.ollama_mode || 'unknown')}</span></div>
              <div className="row"><strong>Ollama URL</strong><span>{String(modelDetails.ollama_base_url || 'unknown')}</span></div>
              <div className="row split"><strong>Selected chat model</strong><span>{String(modelDetails.selected_model || 'none')}</span></div>
              <div className="row split"><strong>Default chat</strong><span>{String(modelDetails.default_chat_model || 'none')}</span></div>
              <div className="row split"><strong>Reasoning</strong><span>{String(modelDetails.reasoning_model || 'none')}</span></div>
              <div className="row split"><strong>Fallback</strong><span>{String(modelDetails.fallback_chat_model || 'none')}</span></div>
              <div className="row split"><strong>Code</strong><span>{String(modelDetails.code_model || 'none')}</span></div>
              <div className="row split"><strong>Embedding</strong><span>{String(modelDetails.embedding_model || 'none')}</span></div>
              <div className="row"><strong>Blocked models</strong><span>{Array.isArray(modelDetails.blocked_models) && modelDetails.blocked_models.length ? modelDetails.blocked_models.join(', ') : 'none'} / installed: {Array.isArray(modelDetails.installed_but_blocked) && modelDetails.installed_but_blocked.length ? modelDetails.installed_but_blocked.join(', ') : 'none'}</span></div>
              <div className="row split"><strong>Model ready</strong><StatusPill label={String(modelDetails.model_ready ? 'yes' : 'no')} status={modelDetails.model_ready ? 'ready' : 'unavailable'} /></div>
              <div className="row"><strong>Missing models</strong><span>{Array.isArray(modelDetails.missing_models) && modelDetails.missing_models.length ? modelDetails.missing_models.join(', ') : 'none'}</span></div>
            </div>
          </Panel>
          <Panel icon={<ShieldCheck />} title="Memory">
            <div className="list dense">
              <div className="row split"><strong>Memory</strong><StatusPill label={memoryStatus} status={memoryStatus} /></div>
              <div className="row split"><strong>Embedding ready</strong><span>{String(memoryDetails.embedding_ready ? 'yes' : 'no')}</span></div>
              <div className="row split"><strong>Vector store ready</strong><span>{String(memoryDetails.vector_store_ready ? 'yes' : 'no')}</span></div>
              <div className="row split"><strong>Pending</strong><span>{String(memoryDetails.pending_count ?? 0)}</span></div>
              <div className="row split"><strong>Active</strong><span>{String(memoryDetails.active_count ?? 0)}</span></div>
              <div className="row"><strong>Reason</strong><span>{String(memoryDetails.failure_reason || 'ready')}</span></div>
            </div>
          </Panel>
          <Panel icon={<Users />} title="Team Seats">
            <div className="list dense">
              {team.slice(0, 6).map((seat) => (
                <div key={seat.name} className="row">
                  <strong>{seat.name}</strong>
                  <span>{seat.responsibility}</span>
                </div>
              ))}
            </div>
          </Panel>
          <Panel icon={<ShieldCheck />} title="Capabilities">
            <div className="chips">
              {capabilities.map((capability) => (
                <StatusPill key={capability.name} label={capability.name} status={capability.status} />
              ))}
            </div>
          </Panel>
          <Panel icon={<Boxes />} title="Future Integrations">
            <div className="list dense">
              {integrations.slice(0, 8).map((integration) => (
                <div key={integration.name} className="row split">
                  <strong>{integration.name}</strong>
                  <StatusPill label={integration.status} status={integration.status} />
                </div>
              ))}
            </div>
          </Panel>
          <Panel icon={<GitBranch />} title="GitHub + Docker">
            <div className="list dense">
              <div className="row split"><strong>GitHub</strong><StatusPill label={githubStatus} status={githubStatus} /></div>
              {dockerPresets.map((preset) => (
                <div key={preset} className="row split"><strong>{preset}</strong><span>preset</span></div>
              ))}
            </div>
          </Panel>
          <Panel icon={<Server />} title="Config Import">
            <div className="list dense">
              <div className="row split"><strong>Bridge</strong><StatusPill label={bridgeStatus} status={bridgeStatus} /></div>
              <div className="row"><strong>X7 source path</strong><span>{'X:\\XV7\\xv7 -> /imports/x7'}</span></div>
              <div className="row split"><strong>X7 import</strong><span>{x7ImportStatus}</span></div>
              <div className="row"><strong>X6 source path</strong><span>{'X:\\X-V-6.1 -> /imports/x6'}</span></div>
              <div className="row split"><strong>X6 import</strong><span>{x6ImportStatus}</span></div>
              <div className="row"><strong>Setup wizard</strong><span>{legacySignals}</span></div>
              <div className="row split"><strong>Import</strong><span>{importStatus}</span></div>
              <button className="ghost" onClick={submitConfigScan}>Scan X6/X7 Configs</button>
            </div>
          </Panel>
          <Panel icon={<Volume2 />} title="Avatar + Speech">
            <div className="list dense">
              <div className="row split"><strong>TTS</strong><span>{muted ? 'disabled' : 'enabled'}</span></div>
              <div className="row split"><strong>Microphone</strong><span>{micStatus}</span></div>
              <div className="row split"><strong>Voice preference</strong><span>US Google female</span></div>
              <div className="row split"><strong>Resolved voice</strong><span>{voiceName}</span></div>
              <div className="row split"><strong>Auto-read responses</strong><span>off</span></div>
              <div className="row split"><strong>Push-to-talk</strong><span>available</span></div>
              <div className="row split"><strong>Provider</strong><span>{voiceStatus === 'unavailable' ? 'unavailable' : 'browser_speech_synthesis'}</span></div>
              <div className="row split"><strong>Permission</strong><span>{micStatus}</span></div>
              <div className="row split"><strong>Volume</strong><input aria-label="Settings voice volume" type="range" min="0" max="100" value={muted ? 0 : volume} onChange={(event) => changeVolume(Number(event.target.value))} /></div>
              <button className="ghost" onClick={toggleMute}>{muted ? 'Unmute voice' : 'Mute voice'}</button>
              <button className="ghost" onClick={readAloud}>Test voice</button>
              <button className="ghost" onClick={startMicrophone}>Test microphone</button>
              <pre className="codeBlock smallBlock">{JSON.stringify(audioReceipts[0] || { status: 'no_audio_receipts_yet' }, null, 2)}</pre>
            </div>
          </Panel>
        </section>
      )}

      {approvalOpen && proposal?.approval && (
        <div className="modalBackdrop" role="dialog" aria-modal="true" aria-label="Approval request">
          <div className="modal">
            <p className="eyebrow">{proposal.approval.risk}</p>
            <h2>{proposal.approval.action}</h2>
            <p>{proposal.approval.intent.summary}</p>
            <dl>
              <dt>Files affected</dt>
              <dd>{proposal.approval.intent.files_affected.join(', ')}</dd>
              <dt>Before / after</dt>
              <dd>{proposal.approval.intent.before_after_summary}</dd>
              <dt>Rollback</dt>
              <dd>{proposal.approval.rollback_hint.summary}</dd>
            </dl>
            <div className="modalActions">
              <button className="ghost" onClick={() => setApprovalOpen(false)}><X size={16} /> Cancel</button>
              <button className="primary" onClick={approveApply}><Check size={16} /> Approve</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

