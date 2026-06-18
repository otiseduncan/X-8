import re
from pathlib import Path

from x8.operator.contracts import OperatorObservation
from x8.operator.resources import ResourceGuard

SECRET_RE = re.compile(r"(?i)(api[_ -]?key|token|password|secret|private[_ -]?key)\s*[:=]\s*\S+")


class OperatorObserver:
    def __init__(self, guard: ResourceGuard) -> None:
        self.guard = guard

    def mock_observation(self, observation_type: str, scope: str, content: str) -> OperatorObservation:
        redacted = SECRET_RE.sub(r"\1=[redacted]", content)
        truncated, was_truncated = self.guard.truncate(redacted)
        return OperatorObservation(observation_type=observation_type, scope=scope, summary=f"{observation_type} observed for {scope}.", content=truncated, truncated=was_truncated, status="completed")

    def file_metadata(self, raw_path: str) -> OperatorObservation:
        path = Path(raw_path)
        if not path.exists():
            return OperatorObservation(observation_type="file_metadata", scope=raw_path, summary="Path does not exist.", status="failed")
        stat = path.stat()
        return self.mock_observation("file_metadata", raw_path, f"is_file={path.is_file()} is_dir={path.is_dir()} size={stat.st_size}")
