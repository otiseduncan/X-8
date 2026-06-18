from x8.contracts.speech import SpeechPreference, SpeechStatus


class SpeechPreferenceManager:
    name = "speech_preferences"
    version = "0.1.0"

    def __init__(self, enabled: bool, provider: str, locale: str, gender: str, voice: str) -> None:
        self.preference = SpeechPreference(enabled=enabled, default_provider=provider, locale=locale, gender=gender, voice=voice)


class TextToSpeechAdapter:
    name = "text_to_speech"
    version = "0.1.0"

    def __init__(self, google_key: str, credentials: str) -> None:
        self.google_key = google_key
        self.credentials = credentials

    def status(self, preference: SpeechPreference) -> SpeechStatus:
        if self.google_key or self.credentials:
            return SpeechStatus(status="configured", provider="google_cloud_tts", voice=preference.voice, locale=preference.locale, gender_preference=preference.gender, cloud_tts_used=True)
        return SpeechStatus(status="browser_fallback", provider="browser_speech_synthesis", voice=preference.voice, locale=preference.locale, gender_preference=preference.gender, reason="Google Cloud TTS is not configured.")


class SpeechManager:
    name = "speech"
    version = "0.1.0"

    def __init__(self, preference: SpeechPreference, adapter: TextToSpeechAdapter) -> None:
        self.preference = preference
        self.adapter = adapter

    def status(self) -> SpeechStatus:
        if not self.preference.enabled:
            return SpeechStatus(status="unavailable", provider="none", voice="", locale=self.preference.locale, gender_preference=self.preference.gender, reason="Speech is disabled.")
        return self.adapter.status(self.preference)
