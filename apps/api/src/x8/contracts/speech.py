from pydantic import BaseModel


class SpeechPreference(BaseModel):
    enabled: bool = True
    default_provider: str = "google"
    locale: str = "en-US"
    gender: str = "female"
    voice: str = "Google US English Female"


class SpeechStatus(BaseModel):
    status: str
    provider: str
    voice: str
    locale: str
    gender_preference: str
    cloud_tts_used: bool = False
    reason: str = ""
