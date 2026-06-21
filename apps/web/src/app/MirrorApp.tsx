import { useState } from 'react';
import { AvatarStage } from './AssistantComponents';
import type { AvatarRuntimeState } from './AssistantComponents';
import { OpenWebUIChatMirror, OpenWebUISidebarMirror } from './OpenWebUIMirror';
import './chatUsability.css';
import './openWebUiMirror.css';

export function App() {
  const [avatarState, setAvatarState] = useState<AvatarRuntimeState>('idle');

  return (
    <main className="shell xoduzMirrorShell" data-theme="neon-blue">
      <section className="xoduzMirrorStage" aria-label="Xoduz Open WebUI cockpit">
        <OpenWebUIChatMirror />

        <aside className="xoduzRightRail" aria-label="Xoduz right rail">
          <section className="avatarPresence xoduzRightRailAvatar" aria-label="Xoduz avatar">
            <div className="assistantIdentityCard xoduzMirrorAvatarHeader">
              <p className="eyebrow">Xoduz Shell</p>
              <h1>Avatar overlay</h1>
              <p className="avatarState">Open WebUI owns chat. X8 owns the face, chrome, and operator rail.</p>
            </div>

            <AvatarStage state={avatarState} />

            <div className="xoduzMirrorStateControls" aria-label="Avatar state controls">
              <button className="ghost" type="button" onClick={() => setAvatarState('idle')}>Idle</button>
              <button className="ghost" type="button" onClick={() => setAvatarState('thinking')}>Thinking</button>
              <button className="ghost" type="button" onClick={() => setAvatarState('speaking')}>Speaking</button>
            </div>
          </section>

          <OpenWebUISidebarMirror />
        </aside>
      </section>
    </main>
  );
}

export const MirrorApp = App;
