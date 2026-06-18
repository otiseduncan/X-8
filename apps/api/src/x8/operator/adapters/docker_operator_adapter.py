class DockerOperatorAdapter:
    name = "docker_operator"

    def status(self) -> dict[str, object]:
        return {"status": "mock_only", "reason": "Docker mutation requires future approval-backed execution."}
