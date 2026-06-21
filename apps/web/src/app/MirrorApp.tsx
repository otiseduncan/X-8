import { useState } from 'react';
import { AvatarStage } from './AssistantComponents';
import type { AvatarRuntimeState } from './AssistantComponents';
import { OpenWebUIChatSurface } from './OpenWebUIMirror';
import './chatUsability.css';
import './openWebUiMirror.css';

export function App() {
  const [avatarState, setAvatarState] = useState<AvatarRuntimeState>('idle');

  return (
    <main className="shell xoduzMirrorShell" data-theme="neon-blue">
      <section className="xoduzMirrorStage" aria-label="Xoduz Open WebUI chat cockpit">
        <section className="xoduzChatPane" aria-label="Open WebUI chat responses and input">
          <OpenWebUIChatSurface />
        </section>

        <aside className="xoduzAvatarRail" aria-label="Xoduz avatar and shell status">
          <section className="avatarPresence xoduzAvatarCard" aria-label="Xoduz avatar">
            <div className="assistantIdentityCard xoduzMirrorAvatarHeader">
              <p className="eyebrow">Xoduz Shell</p>
              <h1>Avatar online</h1>
              <p className="avatarState">Open WebUI owns the chat. X8 owns the face, shell, and local chrome.</p>
            </div>

            <AvatarStage state={avatarState} />

            <div className="xoduzMirrorStateControls" aria-label="Avatar state controls">
              <button className="ghost" type="button" onClick={() => setAvatarState('idle')}>Idle</button>
              <button className="ghost" type="button" onClick={() => setAvatarState('thinking')}>Thinking</button>
              <button className="ghost" type="button" onClick={() => setAvatarState('speaking')}>Speaking</button>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

export const MirrorApp = App;
