import { useState } from 'react';

const OPENWEBUI_MIRROR_SRC = '/openwebui/';

export function OpenWebUIMirror() {
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <section className="openWebUiMirror" aria-label="Open WebUI mirror">
      <header className="openWebUiMirrorHeader">
        <div>
          <p className="modeLabel">Open WebUI Mirror</p>
          <h1>Xoduz chat surface</h1>
          <span className="statusText">Open WebUI owns chat, input, history, artifacts, tools, and model context.</span>
        </div>
        <div className="openWebUiMirrorActions">
          <button className="ghost" type="button" onClick={() => setReloadKey((current) => current + 1)}>
            Reload mirror
          </button>
          <a className="ghost" href={OPENWEBUI_MIRROR_SRC} target="_blank" rel="noreferrer">
            Open native
          </a>
        </div>
      </header>

      <div className="openWebUiFrameShell">
        <iframe key={reloadKey} className="openWebUiFrame" title="Open WebUI chat" src={OPENWEBUI_MIRROR_SRC} />
      </div>
    </section>
  );
}
