from x8.brain_bridge_runtime import apply_runtime_patch
from x8.app_factory import create_app

apply_runtime_patch()
app = create_app()
