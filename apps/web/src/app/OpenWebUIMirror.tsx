import { useMemo, useState } from 'react';

const DEFAULT_OPENWEBUI_MIRROR_SRC = 'http://localhost:3000/';

function openWebUiMirrorSource() {
  const configured = import.meta.env?.VITE_OPENWEBUI_MIRROR_SRC;
  return String(configured || DEFAULT_OPENWEBUI_MIRROR_SRC);
}

export function OpenWebUIChatSurface() {
  const [reloadKey, setReloadKey] = useState(0);
  const mirrorSrc = useMemo(() => openWebUiMirrorSource(), []);

  return (
    <section className="openWebUiChatSurface" aria-label="Open WebUI chat mirror">
      <header className="openWebUiChatSurfaceHeader">
        <div>
          <p className="modeLabel">Open WebUI Chat Mirror</p>
          <h1>Native responses + native message input</h1>
          <span className="statusText">History, model controls, and Open WebUI chrome are cropped out of the X8 shell.</span>
        </div>
        <div className="openWebUiMirrorActions">
          <button className="ghost" type="button" onClick={() => setReloadKey((current) => current + 1)}>
            Reload chat
          </button>
          <a className="ghost" href={mirrorSrc} target="_blank" rel="noreferrer">
            Open native
          </a>
        </div>
      </header>

      <div className="openWebUiChatCropShell">
        <iframe
          key={reloadKey}
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
