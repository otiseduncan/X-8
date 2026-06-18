from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.contracts.speech import SpeechPreference, SpeechStatus
from x8.managers.speech_manager import SpeechManager, SpeechPreferenceManager, TextToSpeechAdapter

router = APIRouter(prefix="/api/speech", tags=["speech"])


def manager(request: Request) -> SpeechManager:
    settings = request.app.state.settings
    prefs = SpeechPreferenceManager(
        settings.speech_enabled,
        settings.speech_default_provider,
        settings.speech_default_locale,
        settings.speech_default_gender,
        settings.speech_default_voice,
    ).preference
    adapter = TextToSpeechAdapter(settings.google_tts_api_key, settings.google_application_credentials)
    return SpeechManager(prefs, adapter)


@router.get("/preferences", response_model=ResultEnvelope[SpeechPreference])
def preferences(request: Request) -> ResultEnvelope[SpeechPreference]:
    return ResultEnvelope(ok=True, status="implemented", data=manager(request).preference, message="Speech preferences loaded.")


@router.get("/status", response_model=ResultEnvelope[SpeechStatus])
def status(request: Request) -> ResultEnvelope[SpeechStatus]:
    data = manager(request).status()
    return ResultEnvelope(ok=True, status=data.status, data=data, message=data.reason or "Speech status loaded.")


@router.post("/receipt", response_model=ResultEnvelope[SpeechStatus])
def speech_receipt(request: Request) -> ResultEnvelope[SpeechStatus]:
    data = manager(request).status()
    receipt = Receipt(action="speech.read_aloud", status=data.status, summary=f"Speech requested with {data.provider}.", metadata=data.model_dump())
    return ResultEnvelope(ok=data.status != "unavailable", status=data.status, data=data, message="Speech receipt created.", receipts=[receipt])
