import { Activity, Boxes, Code2, FileText, GitBranch, Image, Search, Server, ShieldCheck, Users, Volume2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { StatusPill } from '../components/ui/StatusPill';
import { approveBrainMemory, createContinuityHandoff, createContinuityTask, deleteBrainMemory, loadBrainCandidates, loadBrainEmbeddingStatus, loadBrainEvents, loadBrainMemories, loadContinuityRecords, loadContinuityStatus, previewProjectBuild, reactivateBrainMemory, rejectBrainMemory, reindexBrainMemories, retrieveBrainMemory, toggleBrainAutoCapture, updateBrainFocus, updateBrainMemory, updateContinuityRecord, writeProjectBuild } from '../services/apiClient';
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
  const [projectPrompt, setProjectPrompt] = useState('Build a small local web app scaffold');
  const [projectName, setProjectName] = useState('v8-release-proof-project');
  const [projectStatus, setProjectStatus] = useState('no_preview');
  const [projectPlan, setProjectPlan] = useState<Record<string, unknown> | null>(null);
  const [projectFiles, setProjectFiles] = useState<Array<Record<string, unknown>>>([]);

  async function previewProject() {
    const response = await previewProjectBuild(projectPrompt, projectName);
    const result = response.data || {};
    const plan = (result.plan as Record<string, unknown>) || {};
    setProjectPlan(plan);
    setProjectFiles(Array.isArray(plan.files) ? plan.files as Array<Record<string, unknown>> : []);
    setProjectStatus(String(result.status || response.status));
  }

  async function writeProject() {
    if (!projectPlan?.manifest_hash) return;
    const response = await writeProjectBuild(projectPrompt, projectName, String(projectPlan.manifest_hash));
    const result = response.data || {};
    const plan = (result.plan as Record<string, unknown>) || {};
    setProjectPlan(plan);
    setProjectFiles(Array.isArray(plan.files) ? plan.files as Array<Record<string, unknown>> : projectFiles);
    setProjectStatus(String(result.status || response.status));
  }

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
      <Panel icon={<Boxes />} title="Project Builder">
        <div className="list dense projectBuilderPanel">
          <div className="row split"><strong>Status</strong><StatusPill label={projectStatus} status={projectStatus} /></div>
          <label className="fieldStack"><span>Project name</span><input value={projectName} onChange={(event) => setProjectName(event.target.value)} /></label>
          <label className="fieldStack"><span>Build prompt</span><textarea rows={3} value={projectPrompt} onChange={(event) => setProjectPrompt(event.target.value)} /></label>
          <div className="inlineActions">
            <button className="chipButton" onClick={() => void previewProject()}>Preview manifest</button>
            <button className="chipButton" disabled={!projectPlan?.manifest_hash} onClick={() => void writeProject()}>Write approved sandbox</button>
          </div>
          <div className="row"><strong>Output path</strong><span>{String(projectPlan?.output_path || 'preview required')}</span></div>
          <div className="row"><strong>Manifest hash</strong><span>{String(projectPlan?.manifest_hash || 'none')}</span></div>
          <div className="row"><strong>Files</strong><span>{projectFiles.map((file) => String(file.path)).join(', ') || 'none'}</span></div>
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
      <BrainMemoryPanel memoryStatus={memoryStatus} memoryDetails={memoryDetails} brainDetails={brainDetails} />
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

type BrainRecord = Record<string, unknown> & {
  id: string;
  title?: string;
  content?: string;
  summary?: string;
  layer?: string;
  type?: string;
  sensitivity?: string;
  confidence?: number;
  source?: string;
  provenance?: string;
  active?: boolean;
  soft_deleted?: boolean;
  requires_approval?: boolean;
  approved_by_user?: boolean;
  tags?: string[];
  project_scope?: string;
  session_scope?: string;
  global_scope?: boolean;
  created_at?: string;
  updated_at?: string;
  last_used_at?: string;
};

type BrainCandidate = Record<string, unknown> & {
  id: string;
  suggested_title?: string;
  summary?: string;
  source_text_redacted?: string;
  decision?: string;
  reason?: string;
  confidence?: number;
  linked_memory_id?: string;
};

function BrainMemoryPanel({ memoryStatus, memoryDetails, brainDetails }: { memoryStatus: string; memoryDetails: Record<string, unknown>; brainDetails: Record<string, unknown> }) {
  const [records, setRecords] = useState<BrainRecord[]>([]);
  const [candidates, setCandidates] = useState<BrainCandidate[]>([]);
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [selectedId, setSelectedId] = useState('');
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [candidateFilter, setCandidateFilter] = useState('');
  const [layerFilter, setLayerFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [actionStatus, setActionStatus] = useState('No memory action run yet.');
  const [retrievalProof, setRetrievalProof] = useState<Record<string, unknown> | null>(null);
  const [embeddingStatus, setEmbeddingStatus] = useState<Record<string, unknown>>({});
  const [continuityStatus, setContinuityStatus] = useState<Record<string, unknown>>({});
  const [continuityRecords, setContinuityRecords] = useState<Array<Record<string, unknown>>>([]);
  const [taskDraft, setTaskDraft] = useState('');
  const [handoffNote, setHandoffNote] = useState('');
  const [autoCapture, setAutoCapture] = useState(Boolean(brainDetails.auto_capture_enabled));
  const selected = records.find((record) => record.id === selectedId) || records[0];
  const selectedCandidate = candidates.find((candidate) => candidate.id === selectedCandidateId) || candidates[0];
  const [draft, setDraft] = useState({ title: '', content: '', summary: '', tags: '', active: true });

  useEffect(() => { void refresh(); }, []);
  useEffect(() => { void refresh(); }, [candidateFilter]);
  useEffect(() => { setAutoCapture(Boolean(brainDetails.auto_capture_enabled)); }, [brainDetails.auto_capture_enabled]);

  useEffect(() => {
    if (!selected) return;
    setSelectedId(selected.id);
    setDraft({
      title: String(selected.title || ''),
      content: String(selected.content || ''),
      summary: String(selected.summary || ''),
      tags: Array.isArray(selected.tags) ? selected.tags.join(', ') : '',
      active: selected.active !== false
    });
  }, [selected?.id]);

  const visible = useMemo(() => records.filter((record) => {
    if (query) {
      const haystack = `${record.title || ''} ${record.summary || ''} ${record.content || ''} ${(record.tags || []).join(' ')}`.toLowerCase();
      if (!haystack.includes(query.toLowerCase())) return false;
    }
    if (statusFilter === 'active' && !(record.active && !record.soft_deleted && !record.requires_approval)) return false;
    if (statusFilter === 'pending' && !(record.requires_approval && !record.approved_by_user && !record.soft_deleted)) return false;
    if (statusFilter === 'deleted' && !(record.soft_deleted || !record.active)) return false;
    if (layerFilter && record.layer !== layerFilter && record.type !== layerFilter) return false;
    if (scopeFilter && record.project_scope !== scopeFilter && record.session_scope !== scopeFilter) return false;
    return true;
  }), [records, query, statusFilter, layerFilter, scopeFilter]);

  const layers = Array.from(new Set(records.flatMap((record) => [record.layer, record.type]).filter(Boolean).map(String))).sort();
  const scopes = Array.from(new Set(records.flatMap((record) => [record.project_scope, record.session_scope]).filter(Boolean).map(String))).sort();

  async function refresh() {
    const [response, candidateResponse, eventResponse, embeddingResponse, continuityResponse, continuityRecordResponse] = await Promise.all([
      loadBrainMemories({ include_deleted: 'true' }),
      loadBrainCandidates(candidateFilter ? { decision: candidateFilter } : {}),
      loadBrainEvents({}),
      loadBrainEmbeddingStatus(),
      loadContinuityStatus(),
      loadContinuityRecords({})
    ]);
    const next = (response.data || []) as BrainRecord[];
    setRecords(next);
    if (!selectedId && next[0]) setSelectedId(next[0].id);
    const nextCandidates = (candidateResponse.data || []) as BrainCandidate[];
    setCandidates(nextCandidates);
    if (!selectedCandidateId && nextCandidates[0]) setSelectedCandidateId(nextCandidates[0].id);
    setEvents(eventResponse.data || []);
    setEmbeddingStatus(embeddingResponse.data || {});
    setContinuityStatus(continuityResponse.data || {});
    setContinuityRecords(continuityRecordResponse.data || []);
  }

  async function runAction(label: string, action: () => Promise<unknown>) {
    try {
      await action();
      setActionStatus(label);
      await refresh();
    } catch (exc) {
      setActionStatus(exc instanceof Error ? exc.message : 'Brain memory action failed.');
    }
  }

  async function saveSelected() {
    if (!selected) return;
    await runAction('Brain memory updated.', () => updateBrainMemory(selected.id, {
      title: draft.title,
      content: draft.content,
      summary: draft.summary,
      tags: draft.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      active: draft.active
    }));
  }

  async function retrieve() {
    const response = await retrieveBrainMemory(query || selected?.summary || '');
    const data = response.data || {};
    const memories = Array.isArray(data.memories) ? data.memories : [];
    setRetrievalProof({ status: response.status, message: response.message, count: memories.length, ...((data.retrieval_proof as Record<string, unknown>) || {}) });
    setActionStatus('Memory retrieval proof refreshed.');
  }

  async function reindex() {
    await runAction('Brain memories reindexed.', () => reindexBrainMemories());
  }

  async function updateFocus() {
    const value = draft.summary || draft.title || selected?.summary || 'Brain V1 Phase 2';
    await runAction('Active focus updated.', () => updateBrainFocus(value));
  }

  async function addTask() {
    if (!taskDraft.trim()) return;
    await runAction('Continuity task saved.', () => createContinuityTask(taskDraft.trim()));
    setTaskDraft('');
  }

  async function completeTask(id: string) {
    await runAction('Continuity task completed.', () => updateContinuityRecord(id, { status: 'done', active: false }));
  }

  async function archiveTask(id: string) {
    await runAction('Continuity task archived.', () => updateContinuityRecord(id, { status: 'archived', active: false, soft_deleted: true }));
  }

  async function createHandoff() {
    const response = await createContinuityHandoff();
    setHandoffNote(String((response.data || {}).handoff || response.message || 'Handoff created.'));
    setActionStatus('Continuity handoff created.');
    await refresh();
  }

  async function toggleCapture(enabled: boolean) {
    const response = await toggleBrainAutoCapture(enabled);
    setAutoCapture(Boolean((response.data || {}).auto_capture_enabled));
    setActionStatus(`Auto-capture ${enabled ? 'enabled' : 'disabled'}.`);
    await refresh();
  }

  const latestRetrieval = retrievalProof || (brainDetails.latest_retrieval as Record<string, unknown> | null);
  const lastEvent = brainDetails.last_memory_event as Record<string, unknown> | undefined;
  const latestAuto = brainDetails.latest_auto_capture_event as Record<string, unknown> | undefined;
  const currentProject = continuityStatus.current_project as Record<string, unknown> | null;
  const nextStep = continuityStatus.next_step as Record<string, unknown> | null;
  const blockers = Array.isArray(continuityStatus.active_blockers) ? continuityStatus.active_blockers as Array<Record<string, unknown>> : [];
  const tasks = Array.isArray(continuityStatus.active_tasks) ? continuityStatus.active_tasks as Array<Record<string, unknown>> : continuityRecords.filter((record) => record.record_type === 'task' && record.status === 'active');
  const decisions = Array.isArray(continuityStatus.recent_decisions) ? continuityStatus.recent_decisions as Array<Record<string, unknown>> : [];
  const lastValidation = continuityStatus.last_validation_checkpoint as Record<string, unknown> | null;
  const latestCommit = continuityStatus.latest_commit_checkpoint as Record<string, unknown> | null;

  return (
    <Panel icon={<ShieldCheck />} title="Brain / Memory">
      <div className="brainPanel">
        <section className="brainStatusGrid" aria-label="Brain memory status">
          <div className="row split"><strong>Memory</strong><StatusPill label={memoryStatus} status={memoryStatus} /></div>
          <div className="row split"><strong>Backend</strong><span>{String(brainDetails.storage_backend || 'postgres')}</span></div>
          <div className="row split"><strong>Global</strong><span>{String(brainDetails.global_memory_enabled ?? true)}</span></div>
          <div className="row split"><strong>Project</strong><span>{String(brainDetails.project_memory_enabled ?? true)}</span></div>
          <div className="row split"><strong>Session</strong><span>{String(brainDetails.session_memory_mode || 'enabled')}</span></div>
          <div className="row split"><strong>Active</strong><span>{String(brainDetails.active_memory_count ?? 0)}</span></div>
          <div className="row split"><strong>Pending</strong><span>{String(brainDetails.pending_approval_count ?? 0)}</span></div>
          <div className="row split"><strong>Auto-capture</strong><span>{String(autoCapture)}</span></div>
          <div className="row split"><strong>Semantic retrieval</strong><span>{String(brainDetails.semantic_retrieval_enabled ?? true)}</span></div>
          <div className="row split"><strong>Embedding available</strong><span>{String(embeddingStatus.available ?? brainDetails.embedding_available ?? false)}</span></div>
          <div className="row split"><strong>Indexed memories</strong><span>{String(embeddingStatus.indexed_memory_count ?? brainDetails.indexed_memory_count ?? 0)}</span></div>
          <div className="row split"><strong>Min confidence</strong><span>{String(brainDetails.auto_capture_min_confidence ?? '0.7')}</span></div>
          <div className="row split"><strong>Max per turn</strong><span>{String(brainDetails.auto_capture_max_per_turn ?? '3')}</span></div>
          <div className="row"><strong>Embedding model</strong><span>{String(embeddingStatus.embedding_model ?? brainDetails.embedding_model ?? 'nomic-embed-text:latest')}</span></div>
          <div className="row"><strong>Active focus</strong><span>{String(brainDetails.active_focus || 'none')}</span></div>
          <div className="row"><strong>Last memory event</strong><span>{String(lastEvent?.event_type || 'none')}</span></div>
          <div className="row"><strong>Last embedding event</strong><span>{String((brainDetails.last_embedding_event as Record<string, unknown> | undefined)?.event_type || 'none')}</span></div>
          <div className="row"><strong>Latest auto-capture event</strong><span>{String(latestAuto?.decision || 'none')}</span></div>
          <div className="row"><strong>Last ignored/blocked reason</strong><span>{String(brainDetails.last_ignored_or_blocked_reason || 'none')}</span></div>
          <div className="row"><strong>Last retrieval mode</strong><span>{String(latestRetrieval?.retrieval_mode || 'none')}</span></div>
          <div className="row"><strong>Fallback reason</strong><span>{String(latestRetrieval?.fallback_reason || embeddingStatus.failure_reason || 'none')}</span></div>
          <div className="row"><strong>Memory ids used</strong><span>{Array.isArray(latestRetrieval?.memory_ids_used) ? latestRetrieval.memory_ids_used.join(', ') : Array.isArray(latestRetrieval?.selected_ids) ? latestRetrieval.selected_ids.join(', ') : 'none'}</span></div>
          <div className="row"><strong>Retrieval score</strong><span>{Array.isArray(latestRetrieval?.scores) ? latestRetrieval.scores.join(', ') : 'none'}</span></div>
          <div className="row"><strong>Legacy memory readiness</strong><span>{String(memoryDetails.failure_reason || 'ready')}</span></div>
        </section>

        <section className="brainToolbar" aria-label="Memory record filters">
          <input aria-label="Search memory records" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search memory" />
          <select aria-label="Filter memory status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
            <option value="deleted">Deleted / inactive</option>
          </select>
          <select aria-label="Filter memory layer" value={layerFilter} onChange={(event) => setLayerFilter(event.target.value)}>
            <option value="">All layers/types</option>
            {layers.map((layer) => <option key={layer} value={layer}>{layer}</option>)}
          </select>
          <select aria-label="Filter memory scope" value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)}>
            <option value="">All scopes</option>
            {scopes.map((scope) => <option key={scope} value={scope}>{scope}</option>)}
          </select>
          <button className="chipButton" onClick={() => void refresh()}>Refresh</button>
          <button className="chipButton" onClick={() => void retrieve()}>Retrieve</button>
          <button className="chipButton" onClick={() => void reindex()}>Reindex active memories</button>
          <button className="chipButton" onClick={() => void toggleCapture(false)}>Disable auto-capture</button>
          <button className="chipButton" onClick={() => void toggleCapture(true)}>Enable auto-capture</button>
        </section>

        <section className="memoryDetail" aria-label="Continuity panel">
          <header><strong>Continuity</strong><span>{String(continuityStatus.continuity_ready ?? false)}</span></header>
          <div className="brainStatusGrid">
            <div className="row"><strong>Current project</strong><span>{String(currentProject?.summary || 'none')}</span></div>
            <div className="row"><strong>Next step</strong><span>{String(nextStep?.summary || 'none')}</span></div>
            <div className="row"><strong>Active blockers</strong><span>{blockers.map((item) => String(item.summary)).join('; ') || 'none'}</span></div>
            <div className="row"><strong>Last validation checkpoint</strong><span>{String(lastValidation?.summary || 'none')}</span></div>
            <div className="row"><strong>Recent decisions</strong><span>{decisions.map((item) => String(item.summary)).join('; ') || 'none'}</span></div>
            <div className="row"><strong>Latest commit checkpoint</strong><span>{String(latestCommit?.summary || 'none')}</span></div>
          </div>
          <div className="brainToolbar">
            <input aria-label="New continuity task" value={taskDraft} onChange={(event) => setTaskDraft(event.target.value)} placeholder="Add task" />
            <button className="chipButton" onClick={() => void addTask()}>Add task</button>
            <button className="chipButton" onClick={() => void createHandoff()}>Create handoff note</button>
          </div>
          <div className="memoryRecords compact" aria-label="Continuity tasks">
            {tasks.slice(0, 8).map((task) => (
              <div key={String(task.id)} className="memoryRow">
                <strong>{String(task.title || task.summary || task.id)}</strong>
                <span>{String(task.summary || '').slice(0, 120)}</span>
                <small>{String(task.status || 'active')} / {dateLabel(task.updated_at)}</small>
                <div className="inlineActions"><button className="chipButton" onClick={() => void completeTask(String(task.id))}>Complete</button><button className="chipButton" onClick={() => void archiveTask(String(task.id))}>Archive</button></div>
              </div>
            ))}
          </div>
          {handoffNote && <pre className="codeBlock smallBlock">{handoffNote}</pre>}
        </section>

        <section className="memoryRecords" aria-label="Memory records">
          {visible.length === 0 && <p className="cardSummary">No memory records match.</p>}
          {visible.map((record) => (
            <button key={record.id} className={record.id === selected?.id ? 'memoryRow active' : 'memoryRow'} onClick={() => setSelectedId(record.id)}>
              <strong>{String(record.title || record.summary || record.id)}</strong>
              <span>{String(record.summary || record.content || '').slice(0, 120)}</span>
              <small>{String(record.layer)} / {String(record.type)} / {memoryState(record)} / {String(record.sensitivity || 'low')}</small>
              <small>{scopeLabel(record)} / {dateLabel(record.updated_at)}</small>
            </button>
          ))}
        </section>

        {selected && (
          <section className="memoryDetail" aria-label="Memory detail">
            <header><strong>Memory detail</strong><span>{selected.id}</span></header>
            <label>Title<input aria-label="Memory title" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
            <label>Content<textarea aria-label="Memory content" value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} /></label>
            <label>Summary<textarea aria-label="Memory summary" value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} /></label>
            <label>Tags<input aria-label="Memory tags" value={draft.tags} onChange={(event) => setDraft({ ...draft, tags: event.target.value })} /></label>
            <label className="checkRow"><input aria-label="Memory active" type="checkbox" checked={draft.active} onChange={(event) => setDraft({ ...draft, active: event.target.checked })} /> Active</label>
            <div className="memoryMeta">
              <span>Layer/type: {String(selected.layer)} / {String(selected.type)}</span>
              <span>Sensitivity: {String(selected.sensitivity || 'low')}</span>
              <span>Confidence: {String(selected.confidence ?? 'unknown')}</span>
              <span>Scope: {scopeLabel(selected)}</span>
              <span>Created: {dateLabel(selected.created_at)}</span>
              <span>Updated: {dateLabel(selected.updated_at)}</span>
              <span>Last used: {dateLabel(selected.last_used_at)}</span>
              <span>Source: {String(selected.source || 'unknown')}</span>
              <span>Provenance: {String(selected.provenance || 'unknown')}</span>
              <span>Active/deleted: {String(selected.active)} / {String(selected.soft_deleted)}</span>
            </div>
            <div className="inlineActions">
              <button className="chipButton" onClick={() => void saveSelected()}>Save</button>
              <button className="chipButton" onClick={() => selected && void runAction('Brain memory approved.', () => approveBrainMemory(selected.id))}>Approve</button>
              <button className="chipButton" onClick={() => selected && void runAction('Brain memory rejected.', () => rejectBrainMemory(selected.id))}>Reject</button>
              <button className="chipButton" onClick={() => selected && void runAction('Brain memory deleted.', () => deleteBrainMemory(selected.id))}>Delete</button>
              <button className="chipButton" onClick={() => selected && void runAction('Brain memory reactivated.', () => reactivateBrainMemory(selected.id))}>Reactivate</button>
              <button className="chipButton" disabled>Supersede unavailable</button>
              <button className="chipButton" onClick={() => void updateFocus()}>Set focus</button>
            </div>
            <p className="cardSummary" role="status">{actionStatus}</p>
          </section>
        )}

        <section className="memoryDetail" aria-label="Memory candidate history">
          <header>
            <strong>Candidate history</strong>
            <select aria-label="Filter memory candidates" value={candidateFilter} onChange={(event) => setCandidateFilter(event.target.value)}>
              <option value="">All candidates</option>
              <option value="auto_save">Auto-saved</option>
              <option value="pending_approval">Pending approval</option>
              <option value="ignored">Ignored</option>
              <option value="blocked">Blocked</option>
              <option value="duplicate">Duplicate</option>
              <option value="correction">Correction</option>
            </select>
          </header>
          <div className="memoryRecords compact" aria-label="Memory candidates">
            {candidates.length === 0 && <p className="cardSummary">No memory candidates recorded.</p>}
            {candidates.slice(0, 20).map((candidate) => (
              <button key={candidate.id} className={candidate.id === selectedCandidate?.id ? 'memoryRow active' : 'memoryRow'} onClick={() => setSelectedCandidateId(candidate.id)}>
                <strong>{String(candidate.suggested_title || candidate.summary || candidate.id)}</strong>
                <span>{String(candidate.summary || candidate.source_text_redacted || '').slice(0, 120)}</span>
                <small>{String(candidate.decision)} / {String(candidate.reason || 'no reason')}</small>
              </button>
            ))}
          </div>
          {selectedCandidate && (
            <div className="memoryMeta">
              <span>Decision: {String(selectedCandidate.decision || 'unknown')}</span>
              <span>Reason: {String(selectedCandidate.reason || 'none')}</span>
              <span>Confidence: {String(selectedCandidate.confidence ?? 'unknown')}</span>
              <span>Linked memory: {String(selectedCandidate.linked_memory_id || 'none')}</span>
              <span>Redacted source: {String(selectedCandidate.source_text_redacted || 'none')}</span>
            </div>
          )}
        </section>

        <section className="memoryDetail" aria-label="Brain memory events">
          <header><strong>Latest events</strong><span>{events.length}</span></header>
          <div className="memoryRecords compact" aria-label="Memory events">
            {events.slice(0, 12).map((event) => (
              <div key={String(event.id)} className="memoryRow">
                <strong>{String(event.event_type || 'event')}</strong>
                <span>{String(event.event_summary || '').slice(0, 140)}</span>
                <small>{String(event.memory_id || 'candidate')} / {dateLabel(event.created_at)}</small>
              </div>
            ))}
          </div>
        </section>
      </div>
    </Panel>
  );
}

function memoryState(record: BrainRecord) {
  if (record.soft_deleted || !record.active) return 'inactive';
  if (record.requires_approval && !record.approved_by_user) return 'pending';
  return 'active';
}

function scopeLabel(record: BrainRecord) {
  if (record.project_scope) return `project:${record.project_scope}`;
  if (record.session_scope) return `session:${record.session_scope}`;
  if (record.global_scope) return 'global';
  return 'local';
}

function dateLabel(value: unknown) {
  if (!value) return 'never';
  const date = new Date(String(value));
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}
