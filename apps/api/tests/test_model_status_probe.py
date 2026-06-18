from x8.managers.model_manager import ModelReadinessManager


class _Adapter:
    base_url = "http://host.docker.internal:11434"

    def __init__(self) -> None:
        self.generate_calls = 0

    def models(self):
        return True, ["qwen3:8b", "qwen3:1.7b", "nomic-embed-text:latest"], ""

    def generate(self, model: str, prompt: str):
        self.generate_calls += 1
        return True, "XV8_READY", ""


def test_light_model_status_does_not_generate() -> None:
    adapter = _Adapter()

    status = ModelReadinessManager(
        adapter,
        "qwen3:8b",
        "qwen3:1.7b",
        embedding_model="nomic-embed-text:latest",
    ).status(probe=False)  # type: ignore[arg-type]

    assert status.model_ready is True
    assert status.health_prompt_succeeded is False
    assert status.embedding_ready is True
    assert status.memory_ready is True
    assert adapter.generate_calls == 0


def test_model_status_probe_runs_generation() -> None:
    adapter = _Adapter()

    status = ModelReadinessManager(
        adapter,
        "qwen3:8b",
        "qwen3:1.7b",
        embedding_model="nomic-embed-text:latest",
    ).status(probe=True)  # type: ignore[arg-type]

    assert status.model_ready is True
    assert status.health_prompt_succeeded is True
    assert adapter.generate_calls == 1
