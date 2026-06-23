"""Runtime compatibility shims for container entrypoints.

The kernel router can still classify a normal preference correction as code_help when
phrases contain words such as "debugging". Brain auto-capture must still see those
corrections so existing memory correction contracts keep working.
"""

try:
    from x8.kernel import kernel as _kernel

    _kernel.AUTO_CAPTURE_BLOCKED_LANES.discard("code_help")
except Exception:
    pass
