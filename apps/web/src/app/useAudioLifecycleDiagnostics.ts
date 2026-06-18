import { useEffect, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { SpeechReceipt, TtsStatus } from '../audio/speechManagers';
import type { AvatarRuntimeState } from './AssistantComponents';

type AudioContextCtor = new () => AudioContext;

export function useAudioLifecycleDiagnostics({
  speechState,
  setSpeechState,
  voiceStatus,
  voiceDetails,
  muted,
  volume,
  speechSynthesisAvailable
}: {
  speechState: AvatarRuntimeState;
  setSpeechState: Dispatch<SetStateAction<AvatarRuntimeState>>;
  voiceStatus: TtsStatus;
  voiceDetails: Record<string, unknown>;
  muted: boolean;
  volume: number;
  speechSynthesisAvailable: boolean;
}) {
  const [chatPending, setChatPending] = useState(false);
  const [lastStageTransition, setLastStageTransition] = useState(new Date().toISOString());
  const [lastApiStatus, setLastApiStatus] = useState('idle');
  const [lastApiError, setLastApiError] = useState('');
  const [lastTimeoutReason, setLastTimeoutReason] = useState('');
  const [audioUnlocked, setAudioUnlocked] = useState(false);
  const [lastSpeakRequestedAt, setLastSpeakRequestedAt] = useState('');
  const [lastSpeakTextLength, setLastSpeakTextLength] = useState(0);
  const [lastSpeakStartedAt, setLastSpeakStartedAt] = useState('');
  const [lastSpeakEndedAt, setLastSpeakEndedAt] = useState('');
  const [lastSpeakError, setLastSpeakError] = useState('');
  const [lastSpeakTimeout, setLastSpeakTimeout] = useState(false);
  const [videoDiagnostics, setVideoDiagnostics] = useState({ readyState: 'unknown', paused: 'unknown', error: 'none' });
  const [lastResponseKind, setLastResponseKind] = useState('');
  const [lastResponseHadText, setLastResponseHadText] = useState(false);
  const [lastResponseHadCards, setLastResponseHadCards] = useState(false);
  const [speechTriggerReason, setSpeechTriggerReason] = useState('');
  const [speechSkipReason, setSpeechSkipReason] = useState('');
  const [webAudioAvailable, setWebAudioAvailable] = useState(false);
  const [audioContextState, setAudioContextState] = useState('');
  const [rawBeepStarted, setRawBeepStarted] = useState(false);
  const [rawBeepEnded, setRawBeepEnded] = useState(false);
  const [rawBeepError, setRawBeepError] = useState('');
  const [speechSpeakCalled, setSpeechSpeakCalled] = useState(false);
  const [speechStarted, setSpeechStarted] = useState(false);
  const [speechEnded, setSpeechEnded] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [lastAudibleProof, setLastAudibleProof] = useState(false);
  const [lastAudibleProofMethod, setLastAudibleProofMethod] = useState('');

  useEffect(() => {
    const updateVideoDiagnostics = () => {
      const video = document.querySelector('[data-testid="avatar-video"]') as HTMLVideoElement | null;
      setVideoDiagnostics({
        readyState: video ? String(video.readyState) : 'missing',
        paused: video ? String(video.paused) : 'unknown',
        error: video?.error ? video.error.message || `code ${video.error.code}` : 'none'
      });
    };
    updateVideoDiagnostics();
    const timer = window.setInterval(updateVideoDiagnostics, 1000);
    return () => window.clearInterval(timer);
  }, [speechState]);

  function setStage(state: AvatarRuntimeState) {
    setSpeechState(state);
    setLastStageTransition(new Date().toISOString());
  }

  function startSpeechAttempt(text: string) {
    setLastSpeakRequestedAt(new Date().toISOString());
    setLastSpeakTextLength(text.length);
    setLastSpeakStartedAt('');
    setLastSpeakEndedAt('');
    setLastSpeakError('');
    setLastSpeakTimeout(false);
    setSpeechSpeakCalled(true);
    setSpeechStarted(false);
    setSpeechEnded(false);
    setSpeechError('');
  }

  function markSpeechUnavailable(message: string) {
    setAudioUnlocked(false);
    setLastSpeakError(message);
    setSpeechSkipReason(message);
  }

  function recordResponseLifecycle(kind: string, hasText: boolean, hasCards: boolean) {
    setLastResponseKind(kind);
    setLastResponseHadText(hasText);
    setLastResponseHadCards(hasCards);
    setSpeechTriggerReason('');
    setSpeechSkipReason('');
  }

  function markSpeechTriggered(reason: string) {
    setSpeechTriggerReason(reason);
    setSpeechSkipReason('');
  }

  function markSpeechSkipped(reason: string) {
    setSpeechSkipReason(reason);
    setSpeechTriggerReason('');
  }

  function recordSpeechReceipt(receipt: SpeechReceipt) {
    const completedAt = receipt.completed_at || new Date().toISOString();
    if (receipt.status === 'speech_output_started') {
      setLastSpeakStartedAt(completedAt);
      setLastSpeakError('');
      setLastSpeakTimeout(false);
      setAudioUnlocked(true);
      setSpeechStarted(true);
    }
    if (receipt.status === 'speech_output_ended' || receipt.status === 'speech_output_stopped' || receipt.status === 'speech_output_skipped' || receipt.status === 'speech_output_timeout' || receipt.status === 'speech_output_failed') {
      setLastSpeakEndedAt(completedAt);
      if (receipt.status === 'speech_output_ended') setSpeechEnded(true);
    }
    if (receipt.status === 'speech_output_skipped') {
      const message = receipt.error || 'Speech playback skipped.';
      setLastSpeakError(message);
      setSpeechSkipReason(message);
    }
    if (receipt.status === 'speech_output_timeout') {
      setLastSpeakTimeout(true);
      const message = receipt.error || 'Speech playback timed out.';
      setLastSpeakError(message);
      setSpeechError(message);
    }
    if (receipt.status === 'speech_output_failed') {
      const message = receipt.error || 'Speech playback failed.';
      setLastSpeakError(message);
      setSpeechError(message);
    }
  }

  async function runRawAudioTest() {
    setRawBeepStarted(false);
    setRawBeepEnded(false);
    setRawBeepError('');
    setSpeechSpeakCalled(false);
    setSpeechStarted(false);
    setSpeechEnded(false);
    setSpeechError('');
    setLastAudibleProof(false);
    setLastAudibleProofMethod('');
    const audioWindow = window as unknown as { AudioContext?: AudioContextCtor; webkitAudioContext?: AudioContextCtor };
    const AudioCtor = audioWindow.AudioContext || audioWindow.webkitAudioContext;
    setWebAudioAvailable(Boolean(AudioCtor));
    if (AudioCtor && !muted && volume > 0) {
      try {
        const context = new AudioCtor();
        setAudioContextState(context.state);
        if (context.state === 'suspended') await context.resume();
        setAudioContextState(context.state);
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.frequency.value = 660;
        gain.gain.value = Math.max(0.05, Math.min(1, volume / 100));
        oscillator.connect(gain);
        gain.connect(context.destination);
        setRawBeepStarted(true);
        oscillator.start();
        await new Promise<void>((resolve) => {
          oscillator.onended = () => resolve();
          oscillator.stop(context.currentTime + 0.22);
          window.setTimeout(resolve, 500);
        });
        setRawBeepEnded(true);
        setLastAudibleProof(true);
        setLastAudibleProofMethod('web-audio');
        await context.close();
        setAudioContextState(context.state);
        return;
      } catch (error) {
        setRawBeepError(error instanceof Error ? error.message : 'Web Audio beep failed.');
      }
    } else if (muted || volume <= 0) {
      setRawBeepError('Muted or zero volume prevented Web Audio proof.');
    }
    if (!speechSynthesisAvailable || typeof SpeechSynthesisUtterance === 'undefined' || !window.speechSynthesis) {
      setSpeechError('Speech synthesis is unavailable after Web Audio failed.');
      return;
    }
    try {
      await new Promise<void>((resolve, reject) => {
        const utterance = new SpeechSynthesisUtterance('XV8 raw audio test.');
        utterance.volume = Math.max(0.1, Math.min(1, volume / 100));
        setSpeechSpeakCalled(true);
        utterance.onstart = () => {
          setSpeechStarted(true);
          setAudioUnlocked(true);
          setLastAudibleProof(true);
          setLastAudibleProofMethod('speech-synthesis');
        };
        utterance.onend = () => {
          setSpeechEnded(true);
          resolve();
        };
        utterance.onerror = () => reject(new Error('Speech synthesis raw audio test failed.'));
        window.speechSynthesis.speak(utterance);
        window.setTimeout(() => resolve(), 5000);
      });
    } catch (error) {
      setSpeechError(error instanceof Error ? error.message : 'Speech synthesis raw audio test failed.');
    }
  }

  return {
    chatPending,
    setChatPending,
    lastApiStatus,
    setLastApiStatus,
    setLastApiError,
    setLastTimeoutReason,
    setStage,
    startSpeechAttempt,
    markSpeechUnavailable,
    recordResponseLifecycle,
    markSpeechTriggered,
    markSpeechSkipped,
    recordSpeechReceipt,
    runRawAudioTest,
    chatDiagnostics: { pending: chatPending, stage: speechState, lastStageTransition, lastApiStatus, lastApiError, lastTimeoutReason, lastResponseKind, lastResponseHadText, lastResponseHadCards, speechTriggerReason, speechSkipReason },
    audioDiagnostics: { webAudioAvailable, audioContextState, audioUnlocked, rawBeepStarted, rawBeepEnded, rawBeepError, speechSynthesisAvailable, speechSpeakCalled, speechStarted, speechEnded, speechError, muted, volume: muted ? 0 : volume, lastAudibleProof, lastAudibleProofMethod, ...voiceDetails, lastSpeakRequestedAt, lastSpeakTextLength, lastSpeakStartedAt, lastSpeakEndedAt, lastSpeakError, lastSpeakTimeout },
    avatarDiagnostics: { state: speechState, waitingOnAudio: voiceStatus === 'speaking' && speechState !== 'speaking', videoReadyState: videoDiagnostics.readyState, videoPaused: videoDiagnostics.paused, videoError: videoDiagnostics.error, syncClaimed: voiceStatus === 'speaking' && speechState === 'speaking' && Boolean(lastSpeakStartedAt) }
  };
}
