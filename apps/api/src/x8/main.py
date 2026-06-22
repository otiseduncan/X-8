from __future__ import annotations

import traceback

from x8.app_factory import create_app

try:
    from x8.brain_bridge_runtime import apply_runtime_patch

    apply_runtime_patch()
except Exception as exc:  # pragma: no cover - startup guard
    print("[x8] brain bridge runtime patch failed; continuing with API startup", flush=True)
    print(f"[x8] bridge patch error: {exc!r}", flush=True)
    traceback.print_exc()

app = create_app()
