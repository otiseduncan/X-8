class LocalBridgeOperatorAdapter:
    name = "local_bridge_operator"

    def status(self) -> dict[str, object]:
        return {"status": "ready", "mode": "read_only", "mutation_enabled": False, "remote_control_enabled": False}
