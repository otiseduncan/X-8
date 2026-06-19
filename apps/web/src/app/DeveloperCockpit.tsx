import { Activity, Boxes, Code2, FileText, GitBranch, Image, Search, Server, ShieldCheck, Users, Volume2 } from 'lucide-react';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { StatusPill } from '../components/ui/StatusPill';
import type { ChatCard, ChatMessage } from './AssistantComponents';
import { Panel } from './AssistantComponents';

type DeveloperCockpitProps = {
  files: Array<{ path: string }>;
  selectedPath: string;
  setSelectedPath: (path: string) => void;
  proposal: { diff?: string } | null;
  code: string;
  setCode: (value: string) => void;
  proposeDiffCard: (path: string) => void;
  requestApply: (card?: ChatCard) => void | Promise<void>;
  searchStatus: string;
  imageStatus: string;
  selfBuildTrustSummary: string;
  selfBuildTrustStatus: Record<string, unknown>;
  modelDetails: Record<string, unknown>;
  memoryStatus: string;
  memoryDetails: Record<string, unknown>;
  brainDetails: Record<string, unknown>;
  team: Array<{ name: string; responsibility: string }>;
  capabilities: Array<{ name: string; status: string }>;
  integrations: Array<{ name: string; status: string }>;
  githubStatus: string;
  dockerPresets: string[];
  githubAuth: Record<string, unknown>;
  githubOps: Record<string, unknown>;
  githubOpsResult: string;
  refreshGitHubOps: () => void | Promise<void>;
  previewGitHubOp: (kind: 'pull' | 'push') => void | Promise<void>;
  appendMessage: (message: ChatMessage) => void;
  githubApprovalCard: (operation: string, title: string, preview: Record<string, unknown>) => ChatCard;
  nowId: () => string;
  bridgeStatus: string;
  x7ImportStatus: string;
  x6ImportStatus: string;
  legacySignals: string;
  importStatus: string;
  submitConfigScan: () => void | Promise<void>;
  muted: boolean;
  micStatus: string;
  voiceStatus: string;
  voiceName: string;
  volume: number;
  changeVolume: (value: number) => void;
  toggleMute: () => void;
  readAloud: () => void;
  startMicrophone: () => void;
  audioReceipts: unknown[];
};

export function DeveloperCockpit(props: DeveloperCockpitProps) {
  const { files, selectedPath, setSelectedPath, proposal, code, setCode, proposeDiffCard, requestApply, searchStatus, imageStatus, selfBuildTrustSummary, selfBuildTrustStatus, modelDetails, memoryStatus, memoryDetails, brainDetails, team, capabilities, integrations, githubStatus, dockerPresets, githubAuth, githubOps, githubOpsResult, refreshGitHubOps, previewGitHubOp, appendMessage, githubApprovalCard, nowId, bridgeStatus, x7ImportStatus, x6ImportStatus, legacySignals, importStatus, submitConfigScan, muted, micStatus, voiceStatus, voiceName, volume, changeVolume, toggleMute, readAloud, startMicrophone, audioReceipts } = props;
  return (
    <section className="developerCockpit" aria-label="Developer Cockpit Mode">
      <Panel icon={<FileText />} title="Project File Tree">
        <div className="fileList">{files.map((file) => <button key={file.path} className={file.path === selectedPath ? 'file active' : 'file'} onClick={() => setSelectedPath(file.path)}>{file.path}</button>)}</div>
      </Panel>
      <Panel icon={<Code2 />} title="Full Editor">
        <div className="editorHead"><span>{selectedPath}</span><div className="actions"><button className="ghost" onClick={() => proposeDiffCard(selectedPath)}>Propose diff</button><button className="ghost" onClick={() => void requestApply()}>Apply</button></div></div>
        <CodeEditor path={selectedPath} value={code} onChange={setCode} />
      </Panel>
      <Panel icon={<GitBranch />} title="Full Diff Viewer"><pre className="diff">{proposal?.diff || 'No patch proposed yet. Editing here does not mutate the repo.'}</pre></Panel>
      <Panel icon={<Search />} title="SearXNG Panel"><div className="list dense"><div className="row split"><strong>Search</strong><StatusPill label={searchStatus} status={searchStatus} /></div><div className="row"><strong>Provider</strong><span>SearXNG local first</span></div></div></Panel>
      <Panel icon={<Image />} title="Image Studio"><div className="list dense"><div className="row split"><strong>Image</strong><StatusPill label={imageStatus} status={imageStatus} /></div><div className="row split"><strong>Model</strong><span>Juggernaut</span></div><div className="row"><strong>Workflow</strong><span>ComfyUI default</span></div></div></Panel>
      <Panel icon={<ShieldCheck />} title="Self-build trust gate">
        <div className="list dense selfBuildTrustCard" style={{ borderColor: '#22d3ee' }}>
          <div className="row split"><strong>Self-build trust gate</strong><StatusPill label={selfBuildTrustSummary === 'checking' ? 'loading' : selfBuildTrustSummary} status={selfBuildTrustSummary} /></div>
          {selfBuildTrustSummary === 'unavailable' && <div className="row"><strong>Status</strong><span>Trust status unavailable. Check the API route.</span></div>}
          <div className="row split"><strong>Approval required</strong><span>{String(selfBuildTrustStatus.approval_required ?? 'unknown')}</span></div>
          <div className="row split"><strong>Hash approval required</strong><span>{String(selfBuildTrustStatus.approval_hash_required ?? 'unknown')}</span></div>
          <div className="row split"><strong>Writes without approval</strong><span>{String(selfBuildTrustStatus.writes_without_approval ?? 'unknown')}</span></div>
          <div className="row split"><strong>Commit default</strong><span>{String(selfBuildTrustStatus.commit_allowed_by_default ?? 'unknown')}</span></div>
          <div className="row split"><strong>Push default</strong><span>{String(selfBuildTrustStatus.push_allowed_by_default ?? 'unknown')}</span></div>
          <div className="row split"><strong>Validation preset count</strong><span>{Array.isArray(selfBuildTrustStatus.validation_presets) ? selfBuildTrustStatus.validation_presets.length : 'unknown'}</span></div>
          <div className="row"><strong>Validation presets</strong><span>{Array.isArray(selfBuildTrustStatus.validation_presets) ? selfBuildTrustStatus.validation_presets.join(', ') : 'unknown'}</span></div>
          <div className="row split"><strong>Allowed paths</strong><span>{Array.isArray(selfBuildTrustStatus.allowed_paths) ? selfBuildTrustStatus.allowed_paths.length : 'unknown'}</span></div>
          <div className="row split"><strong>Blocked paths</strong><span>{Array.isArray(selfBuildTrustStatus.blocked_paths) ? selfBuildTrustStatus.blocked_paths.length : 'unknown'}</span></div>
        </div>
      </Panel>
      <Panel icon={<Activity />} title="Model + Runtime">
        <div className="list dense">
          <div className="row split"><strong>Ollama mode</strong><span>{String(modelDetails.ollama_mode || 'unknown')}</span></div>
          <div className="row"><strong>Ollama URL</strong><span>{String(modelDetails.ollama_base_url || 'unknown')}</span></div>
          <div className="row split"><strong>Selected chat model</strong><span>{String(modelDetails.selected_model || 'none')}</span></div>
          <div className="row split"><strong>Default chat</strong><span>{String(modelDetails.default_chat_model || 'none')}</span></div>
          <div className="row split"><strong>Reasoning</strong><span>{String(modelDetails.reasoning_model || 'none')}</span></div>
          <div className="row split"><strong>Fallback</strong><span>{String(modelDetails.fallback_chat_model || 'none')}</span></div>
          <div className="row split"><strong>Code</strong><span>{String(modelDetails.code_model || 'none')}</span></div>
          <div className="row split"><strong>Embedding</strong><span>{String(modelDetails.embedding_model || 'none')}</span></div>
          <div className="row"><strong>Blocked models</strong><span>{Array.isArray(modelDetails.blocked_models) && modelDetails.blocked_models.length ? modelDetails.blocked_models.join(', ') : 'none'} / installed: {Array.isArray(modelDetails.installed_but_blocked) && modelDetails.installed_but_blocked.length ? modelDetails.installed_but_blocked.join(', ') : 'none'}</span></div>
          <div className="row split"><strong>Model ready</strong><StatusPill label={String(modelDetails.model_ready ? 'yes' : 'no')} status={modelDetails.model_ready ? 'ready' : 'unavailable'} /></div>
          <div className="row"><strong>Missing models</strong><span>{Array.isArray(modelDetails.missing_models) && modelDetails.missing_models.length ? modelDetails.missing_models.join(', ') : 'none'}</span></div>
        </div>
      </Panel>
      <Panel icon={<ShieldCheck />} title="Memory"><div className="list dense"><div className="row split"><strong>Memory</strong><StatusPill label={memoryStatus} status={memoryStatus} /></div><div className="row split"><strong>Brain ready</strong><span>{String(brainDetails.brain_ready ?? false)}</span></div><div className="row split"><strong>Brain active</strong><span>{String(brainDetails.active_memory_count ?? 0)}</span></div><div className="row split"><strong>Brain pending</strong><span>{String(brainDetails.pending_approval_count ?? 0)}</span></div><div className="row split"><strong>Auto-capture</strong><span>{String(brainDetails.auto_capture_enabled ?? false)}</span></div><div className="row split"><strong>Embedding ready</strong><span>{String(memoryDetails.embedding_ready ? 'yes' : 'no')}</span></div><div className="row split"><strong>Vector store ready</strong><span>{String(memoryDetails.vector_store_ready ? 'yes' : 'no')}</span></div><div className="row split"><strong>Pending</strong><span>{String(memoryDetails.pending_count ?? 0)}</span></div><div className="row split"><strong>Active</strong><span>{String(memoryDetails.active_count ?? 0)}</span></div><div className="row"><strong>Reason</strong><span>{String(memoryDetails.failure_reason || 'ready')}</span></div></div></Panel>
      <Panel icon={<Users />} title="Team Seats"><div className="list dense">{team.slice(0, 6).map((seat) => <div key={seat.name} className="row"><strong>{seat.name}</strong><span>{seat.responsibility}</span></div>)}</div></Panel>
      <Panel icon={<ShieldCheck />} title="Capabilities"><div className="chips">{capabilities.map((capability) => <StatusPill key={capability.name} label={capability.name} status={capability.status} />)}</div></Panel>
      <Panel icon={<Boxes />} title="Future Integrations"><div className="list dense">{integrations.slice(0, 8).map((integration) => <div key={integration.name} className="row split"><strong>{integration.name}</strong><StatusPill label={integration.status} status={integration.status} /></div>)}</div></Panel>
      <Panel icon={<GitBranch />} title="GitHub + Docker"><div className="list dense"><div className="row split"><strong>GitHub</strong><StatusPill label={githubStatus} status={githubStatus} /></div>{dockerPresets.map((preset) => <div key={preset} className="row split"><strong>{preset}</strong><span>preset</span></div>)}</div></Panel>
      <Panel icon={<GitBranch />} title="GitHub Ops">
        <div className="list dense githubOpsPanel">
          <div className="row split"><strong>Token configured</strong><span>{String(githubAuth.token_configured ?? false)}</span></div>
          <div className="row split"><strong>Owner</strong><span>{String(githubAuth.owner || 'not configured')}</span></div>
          <div className="row split"><strong>Branch</strong><span>{String(githubOps.branch || 'not a repo')}</span></div>
          <div className="row"><strong>Remote</strong><span>{String(githubOps.remote_origin_url || 'none')}</span></div>
          <div className="row split"><strong>Dirty</strong><span>{String(githubOps.dirty ?? false)}</span></div>
          <div className="row split"><strong>Changed files</strong><span>{Array.isArray(githubOps.changed_files) ? githubOps.changed_files.length : 0}</span></div>
          <div className="row"><strong>Last commit</strong><span>{String((githubOps.last_commit as Record<string, unknown> | undefined)?.message || 'none')}</span></div>
          <div className="row split"><strong>Ahead / behind</strong><span>{String(githubOps.ahead ?? 'unknown')} / {String(githubOps.behind ?? 'unknown')}</span></div>
          <div className="row"><strong>Result</strong><span>{githubOpsResult}</span></div>
          <div className="inlineActions">
            <button className="chipButton" onClick={() => void refreshGitHubOps()}>Refresh</button>
            <button className="chipButton" onClick={() => void previewGitHubOp('pull')}>Pull preview</button>
            <button className="chipButton" onClick={() => void previewGitHubOp('push')}>Push preview</button>
            <button className="chipButton" onClick={() => appendMessage({ id: nowId(), role: 'assistant', text: 'Create repo requires approval.', cards: [githubApprovalCard('create-repo', 'Create repo', {})] })}>Create repo proposal</button>
            <button className="chipButton" onClick={() => appendMessage({ id: nowId(), role: 'assistant', text: 'Connect remote requires approval.', cards: [githubApprovalCard('connect-remote', 'Connect remote', {})] })}>Connect remote proposal</button>
            <button className="chipButton" onClick={() => appendMessage({ id: nowId(), role: 'assistant', text: 'Initialize repo requires approval.', cards: [githubApprovalCard('init', 'Init repo', {})] })}>Init repo</button>
          </div>
        </div>
      </Panel>
      <Panel icon={<Server />} title="Config Import"><div className="list dense"><div className="row split"><strong>Bridge</strong><StatusPill label={bridgeStatus} status={bridgeStatus} /></div><div className="row"><strong>X7 source path</strong><span>{'X:\\XV7\\xv7 -> /imports/x7'}</span></div><div className="row split"><strong>X7 import</strong><span>{x7ImportStatus}</span></div><div className="row"><strong>X6 source path</strong><span>{'X:\\X-V-6.1 -> /imports/x6'}</span></div><div className="row split"><strong>X6 import</strong><span>{x6ImportStatus}</span></div><div className="row"><strong>Setup wizard</strong><span>{legacySignals}</span></div><div className="row split"><strong>Import</strong><span>{importStatus}</span></div><button className="ghost" onClick={submitConfigScan}>Scan X6/X7 Configs</button></div></Panel>
      <Panel icon={<Volume2 />} title="Avatar + Speech">
        <div className="list dense">
          <div className="row split"><strong>TTS</strong><span>{muted ? 'disabled' : 'enabled'}</span></div>
          <div className="row split"><strong>Microphone</strong><span>{micStatus}</span></div>
          <div className="row split"><strong>Voice preference</strong><span>US Google female</span></div>
          <div className="row split"><strong>Resolved voice</strong><span>{voiceName}</span></div>
          <div className="row split"><strong>Auto-read responses</strong><span>off</span></div>
          <div className="row split"><strong>Push-to-talk</strong><span>available</span></div>
          <div className="row split"><strong>Provider</strong><span>{voiceStatus === 'unavailable' ? 'unavailable' : 'browser_speech_synthesis'}</span></div>
          <div className="row split"><strong>Permission</strong><span>{micStatus}</span></div>
          <div className="row split"><strong>Volume</strong><input aria-label="Settings voice volume" type="range" min="0" max="100" value={muted ? 0 : volume} onChange={(event) => changeVolume(Number(event.target.value))} /></div>
          <button className="ghost" onClick={toggleMute}>{muted ? 'Unmute voice' : 'Mute voice'}</button>
          <button className="ghost" onClick={readAloud}>Test voice</button>
          <button className="ghost" onClick={startMicrophone}>Test microphone</button>
          <pre className="codeBlock smallBlock">{JSON.stringify(audioReceipts[0] || { status: 'no_audio_receipts_yet' }, null, 2)}</pre>
        </div>
      </Panel>
    </section>
  );
}
