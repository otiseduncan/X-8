class BrowserOperatorAdapter:
    name = "browser_operator"

    def status(self) -> dict[str, object]:
        return {"status": "disabled", "reason": "Browser remote control is scaffolded but disabled."}
