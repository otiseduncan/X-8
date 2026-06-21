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
      <section className="assistantFrame xoduzMirrorFrame" aria-label="Xoduz cockpit">
        <aside className="avatarPresence xoduzMirrorAvatar" aria-label="Xoduz avatar">
          <div className="assistantIdentityCard">
            <p className="eyebrow">Xoduz Shell</p>
            <h1>Open WebUI chat</h1>
            <p className="avatarState">The chat surface is Open WebUI. X8 frames it with the avatar and Xoduz styling.</p>
          </div>

          <AvatarStage state={avatarState} />

          <div className="xoduzMirrorStateControls" aria-label="Avatar state controls">
            <button className="ghost" type="button" onClick={() => setAvatarState('idle')}>Idle</button>
            <button className="ghost" type="button" onClick={() => setAvatarState('thinking')}>Thinking</button>
            <button className="ghost" type="button" onClick={() => setAvatarState('speaking')}>Speaking</button>
          </div>

          <div className="compactStatus">
            <div className="row split"><strong>Chat source</strong><span>Open WebUI</span></div>
            <div className="row split"><strong>X8 role</strong><span>Mirror shell</span></div>
            <div className="row split"><strong>Artifacts</strong><span>Open WebUI</span></div>
          </div>
        </aside>

        <section className="conversationPane xoduzMirrorPane" aria-label="Open WebUI chat mirror">
          <OpenWebUIMirror />
        </section>
      </section>
    </main>
  );
}

export const MirrorApp = App;
