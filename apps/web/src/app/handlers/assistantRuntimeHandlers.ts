import type React from 'react';
import { createSpeechReceipt } from '../../services/apiClient';
import type { ResolvedVoice, SpeechInputManager, SpeechOutputManager, SpeechReceipt, SttStatus, TtsStatus } from '../../audio/speechManagers';
import type { AttachmentReference } from '../../types/contracts';
import { messageCopyText, transcriptMarkdown } from '../AssistantComponents';
import type { AvatarRuntimeState, ChatMessage } from '../AssistantComponents';
import { errorCard } from '../cardHelpers';

type Setter<T> = (value: T | ((current: T) => T)) => void;

interface AssistantRuntimeHandlersDeps {
  appendAudioReceipt: (receipt: SpeechReceipt) => void;
  appendMessage: (message: ChatMessage) => void;
  entry: string;
  entryRef: React.RefObject<HTMLTextAreaElement | null>;
  localChatId: string;
  markSpeechSkipped: (reason: string) => void;
  markSpeechTriggered: (reason: string) => void;
  markSpeechUnavailable: (reason: string) => void;
  messages: ChatMessage[];
  micStatus: SttStatus;
  muted: boolean;
  nowId: () => string;
  previousVolume: number;
  requestStartedAt: React.MutableRefObject<number>;
  setAttachments: Setter<AttachmentReference[]>;
  setChatPending: Setter<boolean>;
  setEntry: Setter<string>;
  setHistoryOpen: Setter<boolean>;
  setLastApiError: Setter<string>;
  setLastTimeoutReason: Setter<string>;
  setLatestResult: Setter<string>;
  setLocalChatId: Setter<string>;
  setMessages: Setter<ChatMessage[]>;
  setMicStatus: Setter<SttStatus>;
  setMuted: Setter<boolean>;
  setPreviousVolume: Setter<number>;
  setSessionId: Setter<string | undefined>;
  setStage: (value: AvatarRuntimeState) => void;
  setSttError: Setter<string>;
  setUserAwayFromLatest: Setter<boolean>;
  setVoiceStatus: Setter<TtsStatus>;
  setVolume: Setter<number>;
  speechInput: SpeechInputManager;
  speechOutput: SpeechOutputManager;
  speechRun: React.MutableRefObject<number>;
  startSpeechAttempt: (text: string) => void;
  stickToLatestRef: React.MutableRefObject<boolean>;
  sttBaseEntryRef: React.MutableRefObject<string>;
  timelineEndRef: React.RefObject<HTMLDivElement | null>;
  timelineScrollRef: React.RefObject<HTMLDivElement | null>;
  voiceName: string;
  voiceSelection: {
    recordResolvedVoice: (voice: ResolvedVoice) => void;
    selectedVoiceURI: string;
  };
  voiceStatus: TtsStatus;
  volume: number;
}

const MIN_THINKING_VISIBLE_MS = 500;
const MIN_SPEAKING_VISIBLE_MS = 900;
const RESPONDED_VISIBLE_MS = 650;
const wait = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

export function createAssistantRuntimeHandlers(deps: AssistantRuntimeHandlersDeps) {
  const {
    appendAudioReceipt,
    appendMessage,
    entry,
    entryRef,
    markSpeechSkipped,
    markSpeechTriggered,
    markSpeechUnavailable,
    messages,
    micStatus,
    muted,
    nowId,
    previousVolume,
    requestStartedAt,
    setAttachments,
    setChatPending,
    setEntry,
    setHistoryOpen,
    setLastApiError,
    setLastTimeoutReason,
    setLatestResult,
    setLocalChatId,
    setMessages,
    setMicStatus,
    setMuted,
    setPreviousVolume,
    setSessionId,
    setStage,
    setSttError,
    setUserAwayFromLatest,
    setVoiceStatus,
    setVolume,
    speechInput,
    speechOutput,
    speechRun,
    startSpeechAttempt,
    stickToLatestRef,
    sttBaseEntryRef,
    timelineEndRef,
    timelineScrollRef,
    voiceName,
    voiceSelection,
    volume
  } = deps;

  function startMicrophone() {
    if (micStatus === 'listening') {
      stopSpeechInput();
      return;
    }
    if (!speechInput.supported()) {
      setMicStatus('unavailable');
      setStage('error');
      setSttError('Speech input is unavailable in this browser.');
      entryRef.current?.focus();
      return;
    }
    setSttError('');
    sttBaseEntryRef.current = entry;
    speechInput.transcript.clear();
    setStage('listening');
    speechInput.recognition.start({
      onStatus: (status) => {
        setMicStatus(status);
        if (status === 'listening') setStage('listening');
        if (status === 'transcribing') setStage(muted ? 'muted' : 'idle');
        if (status === 'permission_denied' || status === 'error') setStage('error');
        if (status === 'permission_denied') {
          setSttError('Microphone permission was denied.');
        }
        if (status === 'error') {
          setSttError('Speech recognition failed.');
        }
      },
      onTranscript: (value) => {
        const transcriptValue = speechInput.transcript.set(value);
        setEntry(mergeComposerText(sttBaseEntryRef.current, transcriptValue));
        setStage(muted ? 'muted' : 'idle');
        window.requestAnimationFrame(() => entryRef.current?.focus());
      },
      onReceipt: appendAudioReceipt
    });
  }

  function mergeComposerText(base: string, dictated: string) {
    const cleanBase = base.trimEnd();
    const cleanDictated = dictated.trim();
    if (!cleanBase) return cleanDictated;
    if (!cleanDictated) return cleanBase;
    return `${cleanBase} ${cleanDictated}`;
  }

  function stopSpeechInput() {
    speechInput.recognition.stop();
    speechInput.transcript.clear();
    setMicStatus(speechInput.supported() ? 'ready' : 'unavailable');
    setStage(muted ? 'muted' : 'idle');
    appendAudioReceipt({
      receipt_id: nowId(),
      provider: speechInput.supported() ? 'browser_web_speech_api' : 'unavailable',
      status: 'speech_input_cancelled',
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      locale: 'en-US',
      permission_status: micStatus,
      transcript_length: speechInput.transcript.current().length
    });
    entryRef.current?.focus();
  }

  function resetStage() {
    speechRun.current += 1;
    speechOutput.playback.stop();
    setChatPending(false);
    setVoiceStatus(muted ? 'muted' : speechOutput.tts.supported() ? 'ready' : 'unavailable');
    setStage(muted ? 'muted' : 'idle');
    setLastTimeoutReason('');
    setLastApiError('');
    setLatestResult('Stage reset.');
  }

  async function unlockTestVoice() { await readAloud('XV8 voice test.'); }

  async function readAloud(textOverride = '') {
    const latest = textOverride || [...messages].reverse().find((message) => message.role === 'assistant')?.text || 'XV8 is ready.';
    await speakText(latest, 'manual voice test');
    try { await createSpeechReceipt(); } catch { appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_failed', 'receipt_error', new Date().toISOString(), voiceName, 'Backend speech receipt endpoint failed.')); }
  }

  async function finishAssistantResponseLifecycle(text: string, cardCount: number) {
    const elapsed = requestStartedAt.current ? Date.now() - requestStartedAt.current : MIN_THINKING_VISIBLE_MS;
    if (elapsed < MIN_THINKING_VISIBLE_MS) await wait(MIN_THINKING_VISIBLE_MS - elapsed);
    if (!text.trim()) {
      markSpeechSkipped('No assistant text was available for speech.');
      setStage('responded');
      await wait(RESPONDED_VISIBLE_MS);
      setStage('idle');
      return;
    }
    await speakText(text, cardCount ? 'assistant response text with cards' : 'assistant deterministic/text-only response');
  }

  async function showRespondedThenIdle(reason: string, status: TtsStatus = 'ready') {
    markSpeechSkipped(reason);
    setVoiceStatus(status);
    setStage('responded');
    await wait(RESPONDED_VISIBLE_MS);
    setStage('idle');
  }

  async function speakText(text: string, reason: string) {
    const runId = speechRun.current + 1;
    speechRun.current = runId;
    startSpeechAttempt(text);
    const outputMuted = muted || volume <= 0;
    if (outputMuted) {
      const receipt = speechOutput.tts.outputReceipt('speech_output_skipped', 'muted', new Date().toISOString(), voiceName, 'Muted state prevented speech playback.');
      appendAudioReceipt(receipt);
      await showRespondedThenIdle('Muted state prevented speech playback.', 'muted');
      return;
    }
    if (!speechOutput.tts.supported()) {
      markSpeechUnavailable('Speech synthesis is unavailable.');
      if (reason === 'manual voice test') {
        appendMessage({
          id: nowId(),
          role: 'assistant',
          text: 'Text-to-speech is unavailable in this browser.',
          cards: [errorCard('TTS unavailable', 'No Google Cloud TTS credentials are configured and browser speech synthesis is unavailable.')]
        });
      }
      await showRespondedThenIdle('Speech synthesis is unavailable.', 'unavailable');
      return;
    }
    markSpeechTriggered(reason);
    await new Promise<void>((resolve) => {
      let speakingStartedAt = 0;
      let settled = false;
      let terminalStatus: TtsStatus = 'ready';
      const finish = async () => {
        if (settled) return;
        settled = true;
        if (speakingStartedAt) {
          const remaining = Math.max(0, MIN_SPEAKING_VISIBLE_MS - (Date.now() - speakingStartedAt));
          if (remaining > 0) await wait(remaining);
        } else if ((terminalStatus === 'error' || terminalStatus === 'unavailable') && speechRun.current === runId) {
          setStage('idle');
        } else if (speechRun.current === runId) {
          setStage('responded');
          await wait(RESPONDED_VISIBLE_MS);
        }
        if (speechRun.current === runId) setStage('idle');
        resolve();
      };
      speechOutput.tts.speak(text, {
        onStatus: (status) => {
          terminalStatus = status;
          setVoiceStatus(status);
          if (status === 'speaking') {
            speakingStartedAt = Date.now();
            setStage('speaking');
            return;
          }
          if (status === 'ready' || status === 'error' || status === 'unavailable') void finish();
        },
        onVoice: voiceSelection.recordResolvedVoice,
        onReceipt: (receipt) => {
          appendAudioReceipt(receipt);
          if (receipt.status === 'speech_output_failed' || receipt.status === 'speech_output_timeout' || receipt.status === 'speech_output_ended') void finish();
        }
      }, volume / 100, 20000, voiceSelection.selectedVoiceURI);
    });
  }

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    if (next) {
      if (volume > 0) { setPreviousVolume(volume); window.localStorage.setItem('x8.voicePreviousVolume', String(volume)); }
      speechOutput.playback.stop();
      setVoiceStatus('muted');
      setStage('muted');
      appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_stopped', 'muted', new Date().toISOString(), voiceName));
    } else {
      if (volume === 0) { setVolume(previousVolume || 80); window.localStorage.setItem('x8.voiceVolume', String(previousVolume || 80)); }
      setVoiceStatus(speechOutput.tts.supported() ? 'ready' : 'unavailable');
      setStage('idle');
    }
  }

  function changeVolume(value: number) {
    const next = Math.max(0, Math.min(100, value));
    setVolume(next);
    window.localStorage.setItem('x8.voiceVolume', String(next));
    if (next > 0) {
      setPreviousVolume(next);
      window.localStorage.setItem('x8.voicePreviousVolume', String(next));
      if (muted) { setMuted(false); setVoiceStatus(speechOutput.tts.supported() ? 'ready' : 'unavailable'); setStage('idle'); }
    } else {
      setMuted(true);
      speechOutput.playback.stop();
      setVoiceStatus('muted');
      setStage('muted');
    }
  }

  async function writeClipboard(text: string) {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return; }
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

  async function copyMessage(message: ChatMessage) { await writeClipboard(messageCopyText(message)); setLatestResult('Copied message.'); }

  async function copyTranscript(includeReceipts = false) {
    try {
      await writeClipboard(transcriptMarkdown(messages, includeReceipts));
      setLatestResult(includeReceipts ? 'Copied transcript with receipts.' : 'Copied transcript.');
    } catch { setLatestResult('Copy transcript failed.'); }
  }

  function downloadTranscript() {
    const blob = new Blob([transcriptMarkdown(messages, false)], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'xv8-transcript.md'; link.click(); URL.revokeObjectURL(url);
    setLatestResult('Downloaded transcript.');
  }

  function pauseSpeech() { speechOutput.playback.pause(); setVoiceStatus('paused'); setStage('idle'); appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_paused', 'paused', new Date().toISOString(), voiceName)); }
  function resumeSpeech() { speechOutput.playback.resume(); setVoiceStatus('speaking'); setStage('speaking'); appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_resumed', 'speaking', new Date().toISOString(), voiceName)); }
  function stopSpeech() { speechRun.current += 1; speechOutput.playback.stop(); setVoiceStatus(muted ? 'muted' : 'ready'); setStage(muted ? 'muted' : 'idle'); appendAudioReceipt(speechOutput.tts.outputReceipt('speech_output_stopped', 'stopped', new Date().toISOString(), voiceName)); }

  function scrollToLatest() {
    window.requestAnimationFrame(() => {
      timelineEndRef.current?.scrollIntoView({ block: 'end' });
      const node = timelineScrollRef.current;
      if (node) node.scrollTop = node.scrollHeight;
    });
  }

  function trackTimelineScroll() {
    const node = timelineScrollRef.current;
    if (!node) return;
    const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 48;
    stickToLatestRef.current = nearBottom; setUserAwayFromLatest(!nearBottom);
  }

  function jumpToLatest() {
    stickToLatestRef.current = true;
    setUserAwayFromLatest(false); scrollToLatest();
  }

  function resetChat(nextId: string, result: string) {
    setMessages([]); setEntry(''); setAttachments([]); setSttError(''); setSessionId(undefined); setLocalChatId(nextId);
    setLatestResult(result);
  }

  function clearChat() {
    if (!window.confirm('Clear the current visible chat? Saved history will not be deleted.')) return;
    resetChat(nowId(), 'Started a clear chat.');
  }

  function startNewChat() {
    resetChat(nowId(), 'Started a new chat.');
    setHistoryOpen(false);
  }

  function restoreLocalSession(session: { id: string; messages: ChatMessage[] }) {
    setLocalChatId(session.id);
    setMessages(session.messages);
    setHistoryOpen(false);
    setLatestResult('Restored local chat history.');
  }

  return {
    changeVolume,
    clearChat,
    copyMessage,
    copyTranscript,
    downloadTranscript,
    finishAssistantResponseLifecycle,
    jumpToLatest,
    pauseSpeech,
    readAloud,
    resetStage,
    restoreLocalSession,
    resumeSpeech,
    scrollToLatest,
    speakText,
    startMicrophone,
    startNewChat,
    stopSpeech,
    stopSpeechInput,
    toggleMute,
    trackTimelineScroll,
    unlockTestVoice
  };
}
