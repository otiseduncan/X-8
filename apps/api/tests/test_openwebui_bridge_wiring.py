def test_chat_route_kernel_is_openwebui_bridge_when_provider_enabled(monkeypatch):
    monkeypatch.setenv("X8_CHAT_PROVIDER", "openwebui")
    from x8.app_factory import create_app
    from x8.api.routes import chat
    from x8.brain_bridge_runtime import build_bridge_kernel

    create_app()
    assert chat._kernel is build_bridge_kernel
