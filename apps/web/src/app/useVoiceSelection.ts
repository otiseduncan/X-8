import { useEffect, useState } from 'react';
import type { ResolvedVoice, TextToSpeechAdapter, VoiceOption } from '../audio/speechManagers';

const STORAGE_KEY = 'x8.voiceURI';
const EMPTY_RESOLVED: ResolvedVoice = {
  requestedLabel: 'US Google female',
  voice: null,
  actualName: '',
  actualURI: '',
  actualLang: '',
  matchedPreference: false,
  fallbackReason: 'No browser voices are available.'
};

export function useVoiceSelection(tts: TextToSpeechAdapter) {
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [selectedVoiceURI, setSelectedVoiceURI] = useState(() => window.localStorage.getItem(STORAGE_KEY) || '');
  const [resolvedVoice, setResolvedVoice] = useState<ResolvedVoice>(EMPTY_RESOLVED);

  function refreshVoices(nextURI = selectedVoiceURI) {
    const nextVoices = tts.voices();
    const resolved = tts.resolve(nextURI);
    setVoices(nextVoices);
    setResolvedVoice(resolved);
    if (!nextURI && resolved.actualURI && resolved.matchedPreference) {
      setSelectedVoiceURI(resolved.actualURI);
      window.localStorage.setItem(STORAGE_KEY, resolved.actualURI);
    }
    return resolved;
  }

  function selectVoice(voiceURI: string) {
    setSelectedVoiceURI(voiceURI);
    window.localStorage.setItem(STORAGE_KEY, voiceURI);
    refreshVoices(voiceURI);
  }

  useEffect(() => {
    refreshVoices(selectedVoiceURI);
    const synth = window.speechSynthesis;
    if (!synth) return undefined;
    const handler = () => refreshVoices(selectedVoiceURI);
    synth.addEventListener?.('voiceschanged', handler);
    synth.onvoiceschanged = handler;
    return () => {
      synth.removeEventListener?.('voiceschanged', handler);
      if (synth.onvoiceschanged === handler) synth.onvoiceschanged = null;
    };
  }, [selectedVoiceURI]);

  return {
    voices,
    selectedVoiceURI,
    requestedVoiceLabel: resolvedVoice.requestedLabel,
    actualVoiceName: resolvedVoice.actualName,
    actualVoiceURI: resolvedVoice.actualURI,
    actualVoiceLang: resolvedVoice.actualLang,
    actualVoiceMatched: resolvedVoice.matchedPreference,
    voiceFallbackReason: resolvedVoice.fallbackReason,
    displayVoiceName: resolvedVoice.actualName || resolvedVoice.requestedLabel,
    refreshVoices,
    selectVoice,
    recordResolvedVoice: setResolvedVoice
  };
}
