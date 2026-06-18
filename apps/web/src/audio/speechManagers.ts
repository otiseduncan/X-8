export type SttStatus = 'ready' | 'listening' | 'transcribing' | 'permission_required' | 'permission_denied' | 'unavailable' | 'error';
export type TtsStatus = 'ready' | 'speaking' | 'paused' | 'muted' | 'unavailable' | 'error';

export interface SpeechReceipt {
  receipt_id: string;
  provider: string;
  status: string;
  started_at: string;
  completed_at?: string;
  voice_name?: string;
  voice_uri?: string;
  voice_lang?: string;
  requested_voice_label?: string;
  actual_voice_matched?: boolean;
  fallback_reason?: string;
  locale: string;
  permission_status?: string;
  transcript_length?: number;
  error?: string;
  cloud_tts_used?: boolean;
  gender_preference?: string;
}

export interface VoiceOption {
  name: string;
  voiceURI: string;
  lang: string;
  label: string;
  femaleMatch: boolean;
  maleMatch: boolean;
}

export interface ResolvedVoice {
  requestedLabel: string;
  voice: SpeechSynthesisVoice | null;
  actualName: string;
  actualURI: string;
  actualLang: string;
  matchedPreference: boolean;
  fallbackReason: string;
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
  readonly preferredVoiceLabel = 'US Google female';
  readonly knownFemaleNames = ['google us english female', 'us google female', 'microsoft zira', 'microsoft aria', 'samantha', 'victoria', 'susan', 'karen', 'jenny', 'ava'];
  readonly knownMaleNames = ['david', 'mark', 'george', 'guy', 'alex', 'google us english male', 'microsoft david'];

  toOptions(voices: SpeechSynthesisVoice[]): VoiceOption[] {
    return voices.map((voice) => ({
      name: voice.name,
      voiceURI: voice.voiceURI,
      lang: voice.lang,
      label: `${voice.name} (${voice.lang || 'unknown'})`,
      femaleMatch: this.isFemaleVoice(voice),
      maleMatch: this.isMaleVoice(voice)
    }));
  }

  resolveVoice(voices: SpeechSynthesisVoice[], selectedVoiceURI = ''): ResolvedVoice {
    const selected = selectedVoiceURI ? voices.find((voice) => voice.voiceURI === selectedVoiceURI) || null : null;
    const female = voices.find((voice) => this.isFemaleVoice(voice));
    const englishNonMale = voices.find((voice) => this.isEnglishVoice(voice) && !this.isMaleVoice(voice));
    const english = voices.find((voice) => this.isEnglishVoice(voice));
    const voice = selected || female || englishNonMale || english || voices[0] || null;
    const matchedPreference = Boolean(voice && this.isFemaleVoice(voice));
    const fallbackReason = this.fallbackReason({ selectedVoiceURI, selected, voice, female, matchedPreference });
    return {
      requestedLabel: this.preferredVoiceLabel,
      voice,
      actualName: voice?.name || '',
      actualURI: voice?.voiceURI || '',
      actualLang: voice?.lang || '',
      matchedPreference,
      fallbackReason
    };
  }

  isFemaleVoice(voice: SpeechSynthesisVoice) {
    const name = voice.name.toLowerCase();
    return this.knownFemaleNames.some((candidate) => name.includes(candidate)) || (this.isEnglishVoice(voice) && name.includes('female') && !this.isMaleVoice(voice));
  }

  isMaleVoice(voice: SpeechSynthesisVoice) {
    const name = voice.name.toLowerCase();
    return this.knownMaleNames.some((candidate) => name.includes(candidate)) || name.includes(' male');
  }

  private isEnglishVoice(voice: SpeechSynthesisVoice) {
    return voice.lang.toLowerCase().startsWith('en');
  }

  private fallbackReason({ selectedVoiceURI, selected, voice, female, matchedPreference }: { selectedVoiceURI: string; selected: SpeechSynthesisVoice | null; voice: SpeechSynthesisVoice | null; female: SpeechSynthesisVoice | undefined; matchedPreference: boolean }) {
    if (!voice) return 'No browser voices are available.';
    if (selectedVoiceURI && !selected) return `Persisted voice unavailable. Using fallback: ${voice.name}.`;
    if (selected && !matchedPreference) return `Selected voice does not match the requested female preference: ${voice.name}.`;
    if (!female && !matchedPreference) return `Female voice unavailable in this browser/OS. Using fallback: ${voice.name}.`;
    return '';
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

  voices() {
    if (!window.speechSynthesis) return [];
    return this.preference.toOptions(window.speechSynthesis.getVoices());
  }

  resolve(selectedVoiceURI = '') {
    if (!window.speechSynthesis) return this.preference.resolveVoice([], selectedVoiceURI);
    return this.preference.resolveVoice(window.speechSynthesis.getVoices(), selectedVoiceURI);
  }

  speak(text: string, callbacks: {
    onStatus: (status: TtsStatus) => void;
    onVoice: (voice: ResolvedVoice) => void;
    onReceipt: (receipt: SpeechReceipt) => void;
  }, volume = 0.8, timeoutMs = 20000, selectedVoiceURI = '') {
    const startedAt = now();
    if (!this.supported()) {
      callbacks.onStatus('unavailable');
      callbacks.onReceipt(this.outputReceipt('speech_output_failed', 'unavailable', startedAt, this.preference.resolveVoice([], selectedVoiceURI), 'Speech synthesis is unavailable.'));
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.volume = Math.max(0, Math.min(1, volume));
    const resolved = this.resolve(selectedVoiceURI);
    if (resolved.voice) utterance.voice = resolved.voice;
    utterance.lang = this.preference.locale;
    callbacks.onVoice(resolved);
    let settled = false;
    const finish = (status: TtsStatus, receipt?: SpeechReceipt) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      callbacks.onStatus(status);
      if (receipt) callbacks.onReceipt(receipt);
    };
    const timeout = window.setTimeout(() => {
      window.speechSynthesis.cancel();
      finish('error', this.outputReceipt('speech_output_timeout', 'timeout', startedAt, resolved, `Speech playback timed out after ${timeoutMs}ms.`));
    }, timeoutMs);
    utterance.onstart = () => {
      callbacks.onStatus('speaking');
      callbacks.onReceipt(this.outputReceipt('speech_output_started', 'speaking', startedAt, resolved));
    };
    utterance.onend = () => finish('ready', this.outputReceipt('speech_output_ended', 'ready', startedAt, resolved));
    utterance.onerror = () => {
      finish('error', this.outputReceipt('speech_output_failed', 'error', startedAt, resolved, 'Speech playback failed.'));
    };
    try {
      window.speechSynthesis.speak(utterance);
    } catch (error) {
      finish('error', this.outputReceipt('speech_output_failed', 'error', startedAt, resolved, error instanceof Error ? error.message : 'Speech playback failed before start.'));
    }
  }

  outputReceipt(action: string, status: string, startedAt: string, selected: ResolvedVoice | string, error?: string): SpeechReceipt {
    const resolved = typeof selected === 'string'
      ? { requestedLabel: this.preference.preferredVoiceLabel, voice: null, actualName: selected, actualURI: '', actualLang: this.preference.locale, matchedPreference: selected === this.preference.preferredVoiceLabel, fallbackReason: '' }
      : selected;
    return {
      receipt_id: receiptId(),
      provider: 'browser_speech_synthesis',
      status: action,
      started_at: startedAt,
      completed_at: now(),
      voice_name: resolved.actualName,
      voice_uri: resolved.actualURI,
      voice_lang: resolved.actualLang,
      requested_voice_label: resolved.requestedLabel,
      actual_voice_matched: resolved.matchedPreference,
      fallback_reason: resolved.fallbackReason,
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
