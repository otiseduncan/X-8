import { useMemo, useState } from 'react';

const DEFAULT_OPENWEBUI_MIRROR_SRC = 'http://localhost:3000/';

function openWebUiMirrorSource() {
  const configured = import.meta.env?.VITE_OPENWEBUI_MIRROR_SRC;
  return String(configured || DEFAULT_OPENWEBUI_MIRROR_SRC);
}

export function OpenWebUIMirror() {
  const [reloadKey, setReloadKey] = useState(0);
  const mirrorSrc = useMemo(() => openWebUiMirrorSource(), []);

  return (
    <section className="openWebUiMirror" aria-label="Open WebUI mirror">
      <header className="openWebUiMirrorHeader">
        <div>
          <p className="modeLabel">Open WebUI Native Mirror</p>
          <h1>Xoduz cockpit shell</h1>
          <span className="statusText">Open WebUI owns the sidebar, chat, input, history, artifacts, tools, and context.</span>
        </div>
        <div className="openWebUiMirrorActions">
          <button className="ghost" type="button" onClick={() => setReloadKey((current) => current + 1)}>
            Reload mirror
          </button>
          <a className="ghost" href={mirrorSrc} target="_blank" rel="noreferrer">
            Open native
          </a>
        </div>
      </header>

      <div className="openWebUiNativeFrameShell">
        <iframe
          key={reloadKey}
          className="openWebUiNativeFrame"
          title="Open WebUI native chat"
          src={mirrorSrc}
          allow="clipboard-read; clipboard-write; microphone; camera"
        />
        <div className="openWebUiMirrorRails" aria-hidden="true">
          <div className="openWebUiMirrorRail openWebUiMirrorRailSide">Open WebUI side panel</div>
          <div className="openWebUiMirrorRail openWebUiMirrorRailChat">Open WebUI chat</div>
        </div>
      </div>
    </section>
  );
}
