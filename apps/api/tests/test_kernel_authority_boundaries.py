from x8.kernel.kernel import XV8Kernel


def test_repair_lanes_do_not_auto_capture() -> None:
    kernel = object.__new__(XV8Kernel)
    assert kernel._x8_memory_capture_allowed("conversation_repair") is False
    assert kernel._x8_memory_capture_allowed("reasoning") is False
    assert kernel._x8_memory_capture_allowed("normal_chat") is True
    assert kernel._x8_memory_capture_allowed("repo_inspection") is True
    assert kernel._x8_memory_capture_allowed("brain_retrieve") is False
