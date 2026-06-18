# ComfyUI Image Generation

XV8 uses ComfyUI as the default Docker-local image-generation provider.

Juggernaut is the preferred checkpoint family. Supported checkpoint names:

- `juggernaut*.safetensors`
- `Juggernaut*.safetensors`
- `juggernaut*.ckpt`
- `Juggernaut*.ckpt`

If the checkpoint is missing, XV8 reports `status: model_missing`, `reason: Juggernaut checkpoint was not found`, and `image_generated: false`.

Image generation requires click approval because it can consume local CPU/GPU resources.
