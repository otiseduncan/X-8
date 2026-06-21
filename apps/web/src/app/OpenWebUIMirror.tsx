import { useMemo } from 'react';

const DEFAULT_OPENWEBUI_MIRROR_SRC = 'http://localhost:3000/';

function openWebUiMirrorSource() {
  const configured = import.meta.env?.VITE_OPENWEBUI_MIRROR_SRC;
  return String(configured || DEFAULT_OPENWEBUI_MIRROR_SRC);
}

export function OpenWebUIChatSurface() {
  const mirrorSrc = useMemo(() => openWebUiMirrorSource(), []);

  return (
    <section className="openWebUiChatSurface" aria-label="Open WebUI chat responses and message input mirror">
      <div className="openWebUiChatCropShell">
        <iframe
          className="openWebUiChatCropFrame"
          title="Open WebUI chat responses and message input"
          src={mirrorSrc}
          allow="clipboard-read; clipboard-write; microphone; camera"
        />
      </div>
    </section>
  );
}

export function OpenWebUIMirror() {
  return <OpenWebUIChatSurface />;
}
