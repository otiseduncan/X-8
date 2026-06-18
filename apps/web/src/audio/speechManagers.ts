export type SttStatus = 'ready' | 'listening' | 'transcribing' | 'permission_required' | 'permission_denied' | 'unavailable' | 'error';
export type TtsStatus = 'ready' | 'speaking' | 'paused' | 'muted' | 'unavailable' | 'error';

export interface SpeechReceipt {
  receipt_id: string;
  provider: string;
  status: string;
  started_at: string;
  completed_at?: string;
  voice_name?: string;
  locale: string;
  permission_status?: string;
  transcript_length?: number;
  error?: string;
  cloud_tts_used?: boolean;
  gender_preference?: string;
}

type RecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechRecognitionEventLike {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

function receiptId() {
  return `speech-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function now() {
  return new Date().toISOString();
}

export class MicrophonePermissionManager {
  async status(): Promise<PermissionState | 'unknown'> {
    if (!navigator.permissions?.query) return 'unknown';
    try {
      const permission = await navigator.permissions.query({ name: 'microphone' as PermissionName });
      return permission.state;
    } catch {
      return 'unknown';
    }
  }
}

export class TranscriptManager {
  private value = '';

  set(transcript: string) {
    this.value = transcript.trim();
    return this.value;
  }

  append(transcript: string) {
    this.value = `${this.value} ${transcript}`.trim();
    return this.value;
  }

  clear() {
    this.value = '';
  }

  current() {
    return this.value;
  }
}

export class SpeechRecognitionAdapter {
  private recognition: SpeechRecognitionLike | null = null;

  supported() {
    return Boolean(this.getCtor());
  }

  start(callbacks: {
    onStatus: (status: SttStatus) => void;
    onTranscript: (transcript: string) => void;
    onReceipt: (receipt: SpeechReceipt) => void;
  }) {
    const ctor = this.getCtor();
    const startedAt = now();
    if (!ctor) {
      callbacks.onStatus('unavailable');
      callbacks.onReceipt(this.inputReceipt('speech_input_failed', 'unavailable', startedAt, 'unavailable', 0, 'Browser Web Speech API is unavailable.'));
      return;
    }
    this.recognition = new ctor();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = 'en-US';
    callbacks.onReceipt(this.inputReceipt('speech_input_started', 'listening', startedAt, 'prompt'));
    this.recognition.onstart = () => callbacks.onStatus('listening');
    this.recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ')
        .trim();
      callbacks.onTranscript(transcript);
      callbacks.onStatus('transcribing');
    };
    this.recognition.onerror = (event) => {
      const denied = event.error === 'not-allowed' || event.error === 'service-not-allowed';
      callbacks.onStatus(denied ? 'permission_denied' : 'error');
      callbacks.onReceipt(this.inputReceipt('speech_input_failed', denied ? 'permission_denied' : 'error', startedAt, denied ? 'denied' : 'unknown', 0, denied ? 'Microphone permission was denied.' : event.error || 'Speech recognition failed.'));
    };
    this.recognition.onend = () => callbacks.onStatus('ready');
    this.recognition.start();
  }

  stop() {
    this.recognition?.stop();
  }

  private getCtor(): RecognitionCtor | null {
    const speechWindow = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
    return speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition || null;
  }

  private inputReceipt(action: string, status: string, startedAt: string, permission: string, transcriptLength = 0, error?: string): SpeechReceipt {
    return {
      receipt_id: receiptId(),
      provider: 'browser_web_speech_api',
      status: action,
      started_at: startedAt,
      completed_at: now(),
      locale: 'en-US',
      permission_status: permission,
      transcript_length: transcriptLength,
      error
    };
  }
}

export class SpeechInputManager {
  permission = new MicrophonePermissionManager();
  transcript = new TranscriptManager();
  recognition = new SpeechRecognitionAdapter();

  supported() {
    return this.recognition.supported();
  }
}

export class VoicePreferenceManager {
  readonly locale = 'en-US';
  readonly genderPreference = 'female';
  readonly preferredVoice = 'Google US English Female';

  resolveVoice(voices: SpeechSynthesisVoice[]) {
    return voices.find((voice) => voice.name === this.preferredVoice)
      || voices.find((voice) => voice.lang === this.locale && voice.name.toLowerCase().includes('female'))
      || voices.find((voice) => voice.lang === this.locale)
      || voices[0]
      || null;
  }
}

export class AudioPlaybackManager {
  pause() {
    window.speechSynthesis?.pause();
  }

  resume() {
    window.speechSynthesis?.resume();
  }

  stop() {
    window.speechSynthesis?.cancel();
  }
}

export class TextToSpeechAdapter {
  preference = new VoicePreferenceManager();

  supported() {
    return Boolean(window.speechSynthesis && typeof SpeechSynthesisUtterance !== 'undefined');
  }

  speak(text: string, callbacks: {
    onStatus: (status: TtsStatus) => void;
    onVoice: (voiceName: string) => void;
    onReceipt: (receipt: SpeechReceipt) => void;
  }, volume = 0.8) {
    const startedAt = now();
    if (!this.supported()) {
      callbacks.onStatus('unavailable');
      callbacks.onReceipt(this.outputReceipt('speech_output_failed', 'unavailable', startedAt, '', 'Speech synthesis is unavailable.'));
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.volume = Math.max(0, Math.min(1, volume));
    const voice = this.preference.resolveVoice(window.speechSynthesis.getVoices());
    if (voice) utterance.voice = voice;
    utterance.lang = this.preference.locale;
    callbacks.onVoice(voice?.name || 'browser_default');
    utterance.onstart = () => {
      callbacks.onStatus('speaking');
      callbacks.onReceipt(this.outputReceipt('speech_output_started', 'speaking', startedAt, voice?.name || 'browser_default'));
    };
    utterance.onend = () => callbacks.onStatus('ready');
    utterance.onerror = () => {
      callbacks.onStatus('error');
      callbacks.onReceipt(this.outputReceipt('speech_output_failed', 'error', startedAt, voice?.name || 'browser_default', 'Speech playback failed.'));
    };
    window.speechSynthesis.speak(utterance);
  }

  outputReceipt(action: string, status: string, startedAt: string, voiceName: string, error?: string): SpeechReceipt {
    return {
      receipt_id: receiptId(),
      provider: 'browser_speech_synthesis',
      status: action,
      started_at: startedAt,
      completed_at: now(),
      voice_name: voiceName,
      locale: this.preference.locale,
      error,
      cloud_tts_used: false,
      gender_preference: this.preference.genderPreference
    };
  }
}

export class SpeechOutputManager {
  tts = new TextToSpeechAdapter();
  playback = new AudioPlaybackManager();
  preference = new VoicePreferenceManager();
}
