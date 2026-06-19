import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingResult:
    ok: bool
    vector: list[float]
    model: str
    failure_reason: str = ""


class OllamaEmbeddingClient:
    def __init__(self, base_url: str, model: str = "nomic-embed-text:latest", timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model or "nomic-embed-text:latest"
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> EmbeddingResult:
        body = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        try:
            request = urllib.request.Request(f"{self.base_url}/api/embeddings", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            vector = payload.get("embedding", [])
            if not isinstance(vector, list) or not vector:
                return EmbeddingResult(False, [], self.model, "Ollama embedding response did not include a vector.")
            return EmbeddingResult(True, [float(value) for value in vector], self.model)
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, OSError, ValueError) as exc:
            return EmbeddingResult(False, [], self.model, _safe_reason(exc))


def _safe_reason(exc: BaseException) -> str:
    text = str(exc)
    return text[:240] if text else exc.__class__.__name__
