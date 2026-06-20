import { Check, Copy, FileText, Paperclip, Send, Settings, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { SpeechInputManager, SpeechOutputManager } from '../audio/speechManagers';
import type { SpeechReceipt, SttStatus, TtsStatus } from '../audio/speechManagers';
import { loadAvatarManifest, loadBrainStatus, loadBridgeStatus, loadCapabilities, loadConfigImportStatus, loadDockerPresets, loadFiles, loadGitHubOpsAuthStatus, loadGitHubOpsStatus, loadGitHubStatus, loadImageStatus, loadIntegrations, loadMemoryStatus, loadModelStatus, loadReceipts, loadSearchStatus, loadSession, loadSessions, loadSpeechStatus, loadTeam, readFile, loadSelfBuildTrustStatus } from '../services/apiClient';
import type { AttachmentReference, Capability, FileEntry, IntegrationStatus, PatchProposal, SessionDetail, TeamSeat } from '../types/contracts';
import { AvatarPresencePanel, ChatHistoryPanel, ChatTimeline, InfoDropdown, PushToTalkButton, ThinkingIndicator } from './AssistantComponents';
import type { AvatarRuntimeState, ChatCard, ChatMessage, InfoReceipt } from './AssistantComponents';
import { DeveloperCockpit } from './DeveloperCockpit';
import { createAssistantRuntimeHandlers } from './handlers/assistantRuntimeHandlers';
import { createChatConversationHandlers } from './handlers/chatConversationHandlers';
import { createGitHubApprovalHandlers } from './handlers/githubApprovalHandlers';
import { useAudioLifecycleDiagnostics } from './useAudioLifecycleDiagnostics';
import { useLocalChatHistory } from './useLocalChatHistory';
import { useVoiceSelection } from './useVoiceSelection';
import './chatUsability.css';
const nowId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const speechInput = new SpeechInputManager();
const speechOutput = new SpeechOutputManager();
export function App() {
  const userInteracted = useRef(false);
  const requestStartedAt = useRef(0);
  const speechRun = useRef(0);
  const entryRef = useRef<HTMLTextAreaElement>(null);
  const sttBaseEntryRef = useRef('');
  const timelineScrollRef = useRef<HTMLDivElement>(null);
  const timelineEndRef = useRef<HTMLDivElement>(null);
  const stickToLatestRef = useRef(true);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [team, setTeam] = useState<TeamSeat[]>([]);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [dockerPresets, setDockerPresets] = useState<string[]>([]);
  const [githubStatus, setGithubStatus] = useState('loading');
  const [githubAuth, setGithubAuth] = useState<Record<string, unknown>>({});
  const [githubOps, setGithubOps] = useState<Record<string, unknown>>({});
  const [githubOpsResult, setGithubOpsResult] = useState('No GitHub op run yet.');
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
  const [sttError, setSttError] = useState('');
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(() => Number(window.localStorage.getItem('x8.voiceVolume') || '80'));
  const [previousVolume, setPreviousVolume] = useState(() => Number(window.localStorage.getItem('x8.voicePreviousVolume') || '80'));
  const [audioReceipts, setAudioReceipts] = useState<SpeechReceipt[]>([]);
  const [latestReceipt, setLatestReceipt] = useState<InfoReceipt>(null);
  const [latestResult, setLatestResult] = useState('Ready.');
  const [modelStatus, setModelStatus] = useState('checking');
  const [modelDetails, setModelDetails] = useState<Record<string, unknown>>({});
  const [memoryStatus, setMemoryStatus] = useState('checking');
  const [memoryDetails, setMemoryDetails] = useState<Record<string, unknown>>({});
  const [brainDetails, setBrainDetails] = useState<Record<string, unknown>>({});
  const [selfBuildTrustStatus, setSelfBuildTrustStatus] = useState<Record<string, unknown>>({});
  const [selfBuildTrustSummary, setSelfBuildTrustSummary] = useState('checking');
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [selectedPath, setSelectedPath] = useState('README.md');
  const [code, setCode] = useState('');
  const [proposal, setProposal] = useState<PatchProposal | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [developerOpen, setDeveloperOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [userAwayFromLatest, setUserAwayFromLatest] = useState(false);
  const [entry, setEntry] = useState('');
  const [attachments, setAttachments] = useState<AttachmentReference[]>([]);
  const [localChatId, setLocalChatId] = useState(() => window.localStorage.getItem('x8.localActiveChatId') || nowId());
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: 'welcome', role: 'assistant', text: 'Ready. Ask me what you want to build, inspect, search, preview, or fix.', createdAt: new Date().toISOString() }]);
  const [error, setError] = useState('');
  const voiceSelection = useVoiceSelection(speechOutput.tts);
  const voiceName = voiceSelection.displayVoiceName;
  const audioLifecycle = useAudioLifecycleDiagnostics({
    speechState,
    setSpeechState,
    voiceStatus,
    voiceDetails: { requestedVoiceLabel: voiceSelection.requestedVoiceLabel, actualVoiceName: voiceSelection.actualVoiceName, actualVoiceURI: voiceSelection.actualVoiceURI, actualVoiceLang: voiceSelection.actualVoiceLang, actualVoiceMatched: voiceSelection.actualVoiceMatched, voiceFallbackReason: voiceSelection.voiceFallbackReason },
    muted,
    volume,
    speechSynthesisAvailable: speechOutput.tts.supported()
  });
  const { chatPending, setChatPending, lastApiStatus, setLastApiStatus, setLastApiError, setLastTimeoutReason, setStage, startSpeechAttempt, markSpeechUnavailable, recordResponseLifecycle, markSpeechTriggered, markSpeechSkipped, recordSpeechReceipt, runRawAudioTest } = audioLifecycle;
  const localHistory = useLocalChatHistory(localChatId, messages);
  useEffect(() => {
    Promise.all([loadCapabilities(), loadIntegrations(), loadTeam(), loadFiles(), loadDockerPresets(), loadGitHubStatus(), loadSearchStatus(), loadImageStatus(), loadBridgeStatus(), loadConfigImportStatus(), loadAvatarManifest(), loadSpeechStatus(), loadGitHubOpsAuthStatus(), loadGitHubOpsStatus()])
      .then(([caps, ints, seats, fileList, presets, github, search, image, bridge, configImport, avatar, speech, githubAuthStatus, githubOpsStatus]) => {
        setCapabilities(caps.data);
        setIntegrations(ints.data);
        setTeam(seats.data);
        setFiles(fileList.data.filter((item) => item.kind === 'file').slice(0, 80));
        setDockerPresets(presets.data);
        setGithubStatus(github.data.status);
        setGithubAuth(githubAuthStatus.data || {});
        setGithubOps(githubOpsStatus.data || {});
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
    Promise.allSettled([loadSessions(), loadModelStatus(), loadMemoryStatus(), loadBrainStatus(), loadReceipts()]).then(([sessionsResult, modelResult, memoryResult, brainResult, receiptResult]) => {
      if (modelResult.status === 'fulfilled') { setModelDetails(modelResult.value.data || {}); setModelStatus(`${String(modelResult.value.data?.selected_model || modelResult.value.status)} / ${String(modelResult.value.status)}`); }
      if (memoryResult.status === 'fulfilled') { setMemoryDetails(memoryResult.value.data || {}); setMemoryStatus(String(memoryResult.value.status)); }
      if (brainResult.status === 'fulfilled') setBrainDetails(brainResult.value.data || {});
      if (receiptResult.status === 'fulfilled' && receiptResult.value.data.length > 0) {
        const receipt = receiptResult.value.data[0];
        setLatestResult(String(receipt.status || 'receipt loaded'));
      }
      if (sessionsResult.status !== 'fulfilled') return;
      const saved = window.localStorage.getItem('x8.activeSessionId');
      const candidate = saved || sessionsResult.value.data[0]?.session_id;
      if (!candidate) return;
      loadSession(candidate).then((response) => restoreSession(response.data)).catch(() => undefined);
    });
  }, []);
  function restoreSession(session: SessionDetail) {
    if (userInteracted.current) return;
    setSessionId(session.session_id);
    window.localStorage.setItem('x8.activeSessionId', session.session_id);
    if (session.messages.length === 0) return;
    setMessages(session.messages.map((message) => ({ id: message.message_id, role: message.role, text: message.content, createdAt: new Date().toISOString(), attachments: message.attachments || [] })));
    const latest = session.receipts[0];
    if (latest) {
      setLatestResult(`Session restored: ${String(latest.status || 'ok')}`);
    }
  }
  useEffect(() => {
    loadSelfBuildTrustStatus()
      .then((response) => { setSelfBuildTrustStatus(response.data || {}); setSelfBuildTrustSummary(String(response.status || 'ready')); })
      .catch(() => setSelfBuildTrustSummary('unavailable'));
  }, []);
  useEffect(() => {
    readFile(selectedPath)
      .then((response) => setCode(response.data.content))
      .catch(() => setCode('File could not be loaded from the configured workspace root.'));
  }, [selectedPath]);
  function appendMessage(message: ChatMessage) {
    setMessages((current) => [...current, { ...message, createdAt: message.createdAt || new Date().toISOString() }]);
  }
  function appendAudioReceipt(receipt: SpeechReceipt) {
    setAudioReceipts((current) => [receipt, ...current].slice(0, 8));
    setLatestReceipt(receipt);
    setLatestResult(`Audio: ${receipt.status}`);
    recordSpeechReceipt(receipt);
  }
  function updateCard(cardId: string, patch: Partial<ChatCard>) {
    setMessages((current) =>
      current.map((message) => ({
        ...message,
        cards: message.cards?.map((card) => (card.id === cardId ? { ...card, ...patch } : card))
      }))
    );
  }
  const runtimeHandlers = createAssistantRuntimeHandlers({
    entry,
    messages,
    muted,
    micStatus,
    volume,
    previousVolume,
    voiceName,
    speechInput,
    speechOutput,
    entryRef,
    sttBaseEntryRef,
    speechRun,
    requestStartedAt,
    timelineScrollRef,
    timelineEndRef,
    stickToLatestRef,
    voiceSelection,
    appendAudioReceipt,
    appendMessage,
    nowId,
    runSpeechLifecycle: { markSpeechSkipped, markSpeechTriggered, markSpeechUnavailable, setChatPending, setLastApiError, setLastTimeoutReason, setStage, startSpeechAttempt },
    setAttachments,
    setEntry,
    setHistoryOpen,
    setImportStatus,
    setLatestReceipt,
    setLatestResult,
    setLocalChatId,
    setMessages,
    setMicStatus,
    setMuted,
    setPreviousVolume,
    setSessionId,
    setSttError,
    setUserAwayFromLatest,
    setVoiceStatus,
    setVolume,
    setX6ImportStatus,
    setX7ImportStatus,
    setLegacySignals
  });
  const {
    attachFiles,
    removeAttachment,
    submitConfigScan,
    resetStage,
    unlockTestVoice,
    readAloud,
    finishAssistantResponseLifecycle,
    toggleMute,
    changeVolume,
    copyMessage,
    copyTranscript,
    downloadTranscript,
    stopSpeech,
    scrollToLatest,
    trackTimelineScroll,
    jumpToLatest,
    clearChat,
    startNewChat,
    restoreLocalSession,
    startMicrophone
  } = runtimeHandlers;
  const { createGitHubCards, githubApprovalCard, refreshGitHubOps, previewGitHubOp, requestApply, approveApply } = createGitHubApprovalHandlers({
    githubAuth,
    githubOps,
    selectedPath,
    code,
    appendMessage,
    updateCard,
    nowId,
    setGithubAuth,
    setGithubOps,
    setGithubOpsResult,
    setLatestReceipt,
    setLatestResult,
    setProposal,
    setApprovalOpen
  });
  const { submitMessage, proposeDiffCard } = createChatConversationHandlers({
    entry,
    attachments,
    sessionId,
    muted,
    userInteracted,
    requestStartedAt,
    stickToLatestRef,
    appendMessage,
    createGitHubCards,
    finishAssistantResponseLifecycle,
    nowId,
    recordResponseLifecycle,
    setApprovalOpen,
    setAttachments,
    setChatPending,
    setCode,
    setEntry,
    setError,
    setLastApiError,
    setLastApiStatus,
    setLastTimeoutReason,
    setLatestReceipt,
    setLatestResult,
    setProposal,
    setSelectedPath,
    setSessionId,
    setStage,
    setUserAwayFromLatest
  });
  useEffect(() => { window.localStorage.setItem('x8.localActiveChatId', localChatId); }, [localChatId]);
  useEffect(() => { if (!stickToLatestRef.current) return undefined; scrollToLatest(); const timer = window.setInterval(scrollToLatest, 100); window.setTimeout(() => window.clearInterval(timer), 1600); return () => window.clearInterval(timer); }, [messages, chatPending, speechState, lastApiStatus]);  return (
    <main className="shell" data-theme="neon-blue">
      <section className="assistantFrame" aria-label="Assistant Mode">
        <AvatarPresencePanel state={speechState} fallbackSrc={avatarAsset} muted={muted} volume={volume} voices={voiceSelection.voices} selectedVoiceURI={voiceSelection.selectedVoiceURI} voiceStatus={voiceStatus} requestedVoiceLabel={voiceSelection.requestedVoiceLabel} actualVoiceName={voiceSelection.actualVoiceName} voiceFallbackReason={voiceSelection.voiceFallbackReason} micStatus={micStatus} chatDiagnostics={audioLifecycle.chatDiagnostics} audioDiagnostics={audioLifecycle.audioDiagnostics} avatarDiagnostics={audioLifecycle.avatarDiagnostics} onToggleMute={toggleMute} onVolumeChange={changeVolume} onVoiceSelect={voiceSelection.selectVoice} onRefreshVoices={() => void voiceSelection.refreshVoices()} onPreviewSelectedVoice={() => void readAloud('XV8 selected voice preview.')} onResetStage={resetStage} onStopAudio={stopSpeech} onPlayRawAudioTest={() => void runRawAudioTest()} onUnlockTestVoice={() => void unlockTestVoice()} />
        <section className="conversationPane">
          <header className="conversationHeader">
            <div><div className="modeLabel">Assistant Mode</div><span className="statusText">{latestResult}</span></div>
            <div className="topbarActions">
              <button className="ghost" type="button" data-testid="copy-transcript-button" onClick={() => void copyTranscript(false)}><Copy size={16} /> Copy transcript</button>
              <button className="ghost" type="button" onClick={clearChat}>Clear chat</button>
              <button className="ghost" type="button" aria-expanded={historyOpen} onClick={() => setHistoryOpen((open) => !open)}><FileText size={16} /> History</button>
              <InfoDropdown open={infoOpen} onToggle={() => setInfoOpen((open) => !open)} bridgeStatus={bridgeStatus} modelStatus={modelStatus} memoryStatus={memoryStatus} githubStatus={githubStatus} voiceStatus={voiceStatus} voiceName={voiceName} latestReceipt={latestReceipt} latestResult={latestResult} onCopyTranscript={() => void copyTranscript(false)} onCopyTranscriptWithReceipts={() => void copyTranscript(true)} onDownloadTranscript={downloadTranscript} />
              <button className="ghost iconButton" aria-expanded={developerOpen} aria-label="Settings" onClick={() => setDeveloperOpen((open) => !open)}>
                <Settings size={18} />
              </button>
            </div>
          </header>
          <div className="conversationStatus">{error && <div className="error">{error}</div>}{historyOpen && <ChatHistoryPanel sessions={localHistory.sessions} activeId={localChatId} onNew={startNewChat} onRestore={restoreLocalSession} onDelete={localHistory.deleteSession} />}</div>
          <div className="messageScrollArea" ref={timelineScrollRef} onScroll={trackTimelineScroll} aria-label="Message list">
            <ChatTimeline messages={messages} onToggle={updateCard} onRequestApply={requestApply} onCopyMessage={copyMessage} />
            <ThinkingIndicator active={chatPending} stage={speechState} status={lastApiStatus} />
            <div ref={timelineEndRef} />
          </div>
          {userAwayFromLatest && <button className="jumpLatest" type="button" data-testid="jump-to-latest-button" onClick={jumpToLatest}>Jump to latest</button>}
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
            <div className="inputDock">
              <label className="ghost iconButton attachButton" aria-label="Attach file">
                <Paperclip size={18} />
                <input aria-label="Attach file input" type="file" multiple onChange={(event) => attachFiles(event.target.files)} />
              </label>
              <textarea ref={entryRef} aria-label="Message XV8" data-testid="composer-input" value={entry} onChange={(event) => { setEntry(event.target.value); setSttError(''); }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submitMessage(); } }} placeholder="Ask XV8 anything..." />
              <div className="speechInputSlot">
                <PushToTalkButton status={micStatus} onToggle={startMicrophone} />
                {sttError && <span className="compactSttError" role="status">{sttError}</span>}
              </div>
              <button className="primary" type="submit" data-testid="send-button" disabled={!entry.trim() && attachments.length === 0}>
                <Send size={18} /> Send
              </button>
            </div>
          </form>
        </section>
      </section>
      {developerOpen && <DeveloperCockpit files={files} selectedPath={selectedPath} setSelectedPath={setSelectedPath} proposal={proposal} code={code} setCode={setCode} proposeDiffCard={proposeDiffCard} requestApply={requestApply} searchStatus={searchStatus} imageStatus={imageStatus} selfBuildTrustSummary={selfBuildTrustSummary} selfBuildTrustStatus={selfBuildTrustStatus} modelDetails={modelDetails} memoryStatus={memoryStatus} memoryDetails={memoryDetails} brainDetails={brainDetails} team={team} capabilities={capabilities} integrations={integrations} githubStatus={githubStatus} dockerPresets={dockerPresets} githubAuth={githubAuth} githubOps={githubOps} githubOpsResult={githubOpsResult} refreshGitHubOps={refreshGitHubOps} previewGitHubOp={previewGitHubOp} appendMessage={appendMessage} githubApprovalCard={githubApprovalCard} nowId={nowId} bridgeStatus={bridgeStatus} x7ImportStatus={x7ImportStatus} x6ImportStatus={x6ImportStatus} legacySignals={legacySignals} importStatus={importStatus} submitConfigScan={submitConfigScan} muted={muted} micStatus={micStatus} voiceStatus={voiceStatus} voiceName={voiceName} volume={volume} changeVolume={changeVolume} toggleMute={toggleMute} readAloud={readAloud} startMicrophone={startMicrophone} audioReceipts={audioReceipts} />}
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
