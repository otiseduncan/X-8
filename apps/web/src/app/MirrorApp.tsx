import { useState } from 'react';
import { AvatarStage } from './AssistantComponents';
import type { AvatarRuntimeState } from './AssistantComponents';
import { OpenWebUIMirror } from './OpenWebUIMirror';
import './chatUsability.css';
import './openWebUiMirror.css';

export function App() {
  const [avatarState, setAvatarState] = useState<AvatarRuntimeState>('idle');

  return (
    <main className="shell xoduzMirrorShell" data-theme="neon-blue">
      <section className="xoduzMirrorStage" aria-label="Xoduz Open WebUI cockpit">
        <OpenWebUIMirror />

        <aside className="avatarPresence xoduzMirrorAvatarOverlay" aria-label="Xoduz avatar overlay">
          <div className="assistantIdentityCard xoduzMirrorAvatarHeader">
            <p className="eyebrow">Xoduz Shell</p>
            <h1>Open WebUI mirror</h1>
            <p className="avatarState">X8 now frames the native Open WebUI surface instead of replacing it.</p>
          </div>

          <AvatarStage state={avatarState} />

          <div className="xoduzMirrorStateControls" aria-label="Avatar state controls">
            <button className="ghost" type="button" onClick={() => setAvatarState('idle')}>Idle</button>
            <button className="ghost" type="button" onClick={() => setAvatarState('thinking')}>Thinking</button>
            <button className="ghost" type="button" onClick={() => setAvatarState('speaking')}>Speaking</button>
          </div>

          <div className="compactStatus">
            <div className="row split"><strong>Brain</strong><span>Open WebUI</span></div>
            <div className="row split"><strong>Chat/Input</strong><span>Native mirror</span></div>
            <div className="row split"><strong>X8 role</strong><span>Avatar shell</span></div>
          </div>
        </aside>
      </section>
    </main>
  );
}

export const MirrorApp = App;
