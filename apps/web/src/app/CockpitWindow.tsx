import { Activity, Check, Code2, ExternalLink, FileText, FolderOpen, GitBranch, Plus, RefreshCcw, Save, Server, ShieldCheck, TerminalSquare, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { StatusPill } from '../components/ui/StatusPill';
import { loadBridgeStatus, loadDockerPresets, loadGitHubOpsAuthStatus, loadGitHubOpsStatus, loadGitHubStatus } from '../services/apiClient';
import type { FileEntry, FileRead, PatchProposal, ResultEnvelope } from '../types/contracts';
import './cockpitWindow.css';

const DEFAULT_PATH = 'README.md';

interface ProjectRoot {
  id: string;
  name: string;
  root: string;
  kind: string;
  exists: boolean;
  current?: boolean;
}

function nowStamp() {
  return new Date().toLocaleTimeString();
}

function statusText(value: unknown, fallback = 'unknown') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

function countChangedFiles(status: Record<string, unknown>) {
  return Array.isArray(status.changed_files) ? status.changed_files.length : 0;
}

async function getProjects() {
  const response = await fetch('/api/projects');
  if (!response.ok) throw new Error('Project registry failed');
  return response.json() as Promise<ResultEnvelope<ProjectRoot[]>>;
}

async function getProjectFiles(projectId: string) {
  const query = new URLSearchParams({ project_id: projectId });
  const response = await fetch(`/api/workspace/files?${query}`);
  if (!response.ok) throw new Error('Project file list failed');
  return response.json() as Promise<ResultEnvelope<FileEntry[]>>;
}

async function readProjectFile(projectId: string, path: string) {
  const response = await fetch('/api/workspace/read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, path })
  });
  if (!response.ok) throw new Error('Project file read failed');
  return response.json() as Promise<ResultEnvelope<FileRead>>;
}

async function proposeProjectUpdate(projectId: string, path: string, proposedContent: string) {
  const response = await fetch('/api/repo/propose-update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, path, proposed_content: proposedContent })
  });
  if (!response.ok) throw new Error('Patch proposal failed');
  return response.json() as Promise<ResultEnvelope<PatchProposal>>;
}

async function applyProjectUpdate(projectId: string, path: string, proposedContent: string, approved: boolean) {
  const response = await fetch('/api/repo/apply-update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, path, proposed_content: proposedContent, approved })
  });
  if (!response.ok) throw new Error('Patch apply failed');
  return response.json() as Promise<ResultEnvelope<PatchProposal>>;
}

export function CockpitWindow() {
  const [projects, setProjects] = useState<ProjectRoot[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('x8');
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState(DEFAULT_PATH);
  const [code, setCode] = useState('');
  const [savedCode, setSavedCode] = useState('');
  const [proposal, setProposal] = useState<PatchProposal | null>(null);
  const [bridgeStatus, setBridgeStatus] = useState('loading');
  const [githubStatus, setGithubStatus] = useState('loading');
  const [githubAuth, setGithubAuth] = useState<Record<string, unknown>>({});
  const [githubOps, setGithubOps] = useState<Record<string, unknown>>({});
  const [dockerPresets, setDockerPresets] = useState<string[]>([]);
  const [operationLog, setOperationLog] = useState<string[]>([`[${nowStamp()}] Cockpit opened. No mutation has run.`]);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('');
  const [previewHtml, setPreviewHtml] = useState('');

  const selectedProject = projects.find((project) => project.id === selectedProjectId) || null;
  const projectClosed = !selectedProjectId;
  const dirtyDraft = code !== savedCode;
  const proposalMatchesDraft = Boolean(proposal && proposal.proposed_content === code);
  const changedCount = countChangedFiles(githubOps);
  const filteredFiles = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const fileList = files.filter((item) => item.kind === 'file');
    if (!needle) return fileList.slice(0, 180);
    return fileList.filter((item) => item.path.toLowerCase().includes(needle)).slice(0, 180);
  }, [files, filter]);

  useEffect(() => {
    void initializeCockpit();
  }, []);

  function log(message: string) {
    setOperationLog((current) => [`[${nowStamp()}] ${message}`, ...current].slice(0, 80));
  }

  async function initializeCockpit() {
    setBusy(true);
    try {
      const projectResponse = await getProjects();
      const availableProjects = projectResponse.data.filter((project) => project.exists);
      setProjects(projectResponse.data);
      const startingProjectId = availableProjects.find((project) => project.id === selectedProjectId)?.id || availableProjects[0]?.id || 'x8';
      setSelectedProjectId(startingProjectId);
      await Promise.allSettled([refreshStatusCards(), refreshProjectFiles(startingProjectId, selectedPath)]);
      log('Loaded approved projects and cockpit status.');
    } catch {
      log('Project registry failed. Check x8-api logs.');
    } finally {
      setBusy(false);
    }
  }

  async function refreshStatusCards() {
    const [bridgeResponse, githubResponse, authResponse, opsResponse, dockerResponse] = await Promise.allSettled([
      loadBridgeStatus(),
      loadGitHubStatus(),
      loadGitHubOpsAuthStatus(),
      loadGitHubOpsStatus(),
      loadDockerPresets()
    ]);
    if (bridgeResponse.status === 'fulfilled') setBridgeStatus(String(bridgeResponse.value.data.bridge_reachable ? 'reachable' : 'unreachable'));
    if (githubResponse.status === 'fulfilled') setGithubStatus(String(githubResponse.value.data.status || githubResponse.value.status));
    if (authResponse.status === 'fulfilled') setGithubAuth(authResponse.value.data || {});
    if (opsResponse.status === 'fulfilled') setGithubOps(opsResponse.value.data || {});
    if (dockerResponse.status === 'fulfilled') setDockerPresets(dockerResponse.value.data || []);
  }

  async function refreshCockpit() {
    if (projectClosed) {
      await initializeCockpit();
      return;
    }
    setBusy(true);
    try {
      await Promise.allSettled([refreshStatusCards(), refreshProjectFiles(selectedProjectId, selectedPath)]);
      log(`Refreshed project ${selectedProject?.name || selectedProjectId}.`);
    } catch {
      log('Refresh failed. Check x8-api logs.');
    } finally {
      setBusy(false);
    }
  }

  async function refreshProjectFiles(projectId: string, preferredPath = DEFAULT_PATH) {
    if (!projectId) return;
    const fileResponse = await getProjectFiles(projectId);
    const fileList = fileResponse.data.filter((item) => item.kind === 'file');
    setFiles(fileList);
    const nextPath = fileList.find((item) => item.path === preferredPath)?.path || fileList.find((item) => item.path === DEFAULT_PATH)?.path || fileList[0]?.path || '';
    if (nextPath) {
      setSelectedPath(nextPath);
      await openFile(nextPath, false, projectId);
    } else {
      setSelectedPath('');
      setCode('');
      setSavedCode('');
      setProposal(null);
      setPreviewHtml('');
      log(`Project ${projectId} has no readable files in the current file limit.`);
    }
  }

  async function openFile(path: string, announce = true, projectId = selectedProjectId) {
    if (!path || !projectId) return;
    setBusy(true);
    try {
      const response = await readProjectFile(projectId, path);
      setCode(response.data.content);
      setSavedCode(response.data.content);
      setProposal(null);
      setPreviewHtml(path.endsWith('.html') ? response.data.content : '');
      if (announce) log(`Opened ${path} from ${selectedProject?.name || projectId}. No write has run.`);
    } catch {
      setCode('File could not be loaded from the selected approved project.');
      setSavedCode('');
      log(`Could not open ${path}.`);
    } finally {
      setBusy(false);
    }
  }

  async function selectProject(projectId: string) {
    if (!projectId || projectId === selectedProjectId) return;
    if (dirtyDraft && !window.confirm('Switch projects and discard the current unsaved draft?')) return;
    setSelectedProjectId(projectId);
    setFiles([]);
    setSelectedPath('');
    setCode('');
    setSavedCode('');
    setProposal(null);
    setPreviewHtml('');
    await refreshProjectFiles(projectId, DEFAULT_PATH);
    const project = projects.find((item) => item.id === projectId);
    log(`Switched cockpit project to ${project?.name || projectId}.`);
  }

  function closeProject() {
    if (dirtyDraft && !window.confirm('Close this project and discard the current unsaved draft?')) return;
    setSelectedProjectId('');
    setFiles([]);
    setSelectedPath('');
    setCode('');
    setSavedCode('');
    setProposal(null);
    setPreviewHtml('');
    log('Closed the current cockpit project. No files were changed.');
  }

  function explainOpenProject() {
    log('Open Project is registry-based right now: mount a folder under /projects or add it to X8_APPROVED_PROJECT_ROOTS, then refresh. Unrestricted host browsing is intentionally blocked.');
  }

  function explainNewFile() {
    log('New File/New Folder is queued for the next protected file-operation slice. Current slice modifies existing files only.');
  }

  async function proposeCurrentDraft() {
    if (!selectedPath || !selectedProjectId) return;
    setBusy(true);
    try {
      const response = await proposeProjectUpdate(selectedProjectId, selectedPath, code);
      setProposal(response.data);
      log(`Prepared guarded diff for ${selectedPath}. Review this exact draft before applying.`);
    } catch {
      log(`Diff proposal failed for ${selectedPath}. No write ran.`);
    } finally {
      setBusy(false);
    }
  }

  async function applyApprovedDraft() {
    if (!selectedProjectId || !selectedPath) return;
    if (!proposal) {
      log(`Apply blocked for ${selectedPath}: no reviewed diff exists.`);
      return;
    }
    if (!proposalMatchesDraft) {
      log(`Apply blocked for ${selectedPath}: editor changed after diff proposal. Propose a fresh diff first.`);
      return;
    }
    const approved = window.confirm(`Apply the reviewed cockpit draft to ${selectedPath} inside ${selectedProject?.name || selectedProjectId}?`);
    if (!approved) {
      log(`Apply cancelled for ${selectedPath}.`);
      return;
    }
    setBusy(true);
    try {
      const response = await applyProjectUpdate(selectedProjectId, selectedPath, proposal.proposed_content, true);
      setProposal(response.data);
      if (response.data.mutated) {
        setSavedCode(proposal.proposed_content);
        setCode(proposal.proposed_content);
        setPreviewHtml(selectedPath.endsWith('.html') ? proposal.proposed_content : '');
        log(`Applied approved change to ${selectedPath} inside ${selectedProject?.name || selectedProjectId}.`);
      } else {
        log(`Apply endpoint returned without mutation for ${selectedPath}.`);
      }
      await refreshStatusCards();
    } catch {
      log(`Apply failed or was blocked for ${selectedPath}.`);
    } finally {
      setBusy(false);
    }
  }

  function openChat() {
    window.open('/', 'x8-chat', 'noopener,noreferrer,width=1180,height=900');
  }

  return (
    <main className="cockpitWindow" aria-label="X8 Native Operator Cockpit">
      <header className="cockpitTopbar">
        <div className="cockpitBrand">
          <div className="cockpitMark">X</div>
          <div>
            <p className="cockpitEyebrow">Native Operator Cockpit</p>
            <h1>Xoduz Builder Surface</h1>
          </div>
        </div>
        <div className="projectSwitcher" aria-label="Project selector">
          <label>
            <span>Project</span>
            <select value={selectedProjectId} onChange={(event) => void selectProject(event.target.value)} disabled={busy || !projects.length}>
              {!selectedProjectId && <option value="">No project open</option>}
              {projects.map((project) => (
                <option key={project.id} value={project.id} disabled={!project.exists}>
                  {project.name}{project.exists ? '' : ' (not mounted)'}
                </option>
              ))}
            </select>
          </label>
          <button className="ghost" type="button" onClick={explainOpenProject} disabled={busy}><FolderOpen size={16} /> Open Project</button>
          <button className="ghost" type="button" onClick={closeProject} disabled={busy || projectClosed}><XCircle size={16} /> Close</button>
        </div>
        <div className="cockpitStatusStrip">
          <StatusPill label={`Bridge ${bridgeStatus}`} status={bridgeStatus} />
          <StatusPill label={`GitHub ${githubStatus}`} status={githubStatus} />
          <StatusPill label={`${changedCount} changed`} status={changedCount ? 'warning' : 'ready'} />
          <StatusPill label={dirtyDraft ? 'draft dirty' : 'draft clean'} status={dirtyDraft ? 'warning' : 'ready'} />
          <StatusPill label={proposalMatchesDraft ? 'diff reviewed' : 'diff needed'} status={proposalMatchesDraft ? 'ready' : 'warning'} />
        </div>
        <div className="cockpitTopActions">
          <button className="ghost" type="button" onClick={openChat}><ExternalLink size={16} /> Chat</button>
          <button className="primary" type="button" onClick={() => void refreshCockpit()} disabled={busy}><RefreshCcw size={16} /> Refresh</button>
        </div>
      </header>

      <section className="projectBar" aria-label="Current project details">
        <strong>{selectedProject ? selectedProject.name : 'No project open'}</strong>
        <span>{selectedProject ? selectedProject.root : 'Select an approved mounted project to operate.'}</span>
        <span>{selectedProject ? selectedProject.kind : 'closed'}</span>
      </section>

      <section className="cockpitGrid">
        <aside className="cockpitPanel fileExplorer">
          <div className="panelHeader"><FileText size={17} /><span>Project Files</span></div>
          <div className="fileToolRow">
            <button className="ghost compact" type="button" onClick={explainNewFile} disabled={busy || projectClosed}><Plus size={14} /> New File</button>
            <button className="ghost compact" type="button" onClick={explainNewFile} disabled={busy || projectClosed}><FolderOpen size={14} /> New Folder</button>
          </div>
          <input className="cockpitSearch" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter files..." disabled={projectClosed} />
          <div className="fileScroll">
            {projectClosed && <div className="emptyPreview small">No project open.</div>}
            {filteredFiles.map((file) => (
              <button key={`${selectedProjectId}:${file.path}`} className={file.path === selectedPath ? 'fileButton active' : 'fileButton'} type="button" onClick={() => { setSelectedPath(file.path); void openFile(file.path); }}>
                {file.path}
              </button>
            ))}
          </div>
        </aside>

        <section className="cockpitPanel editorPanel">
          <div className="panelHeader split">
            <span><Code2 size={17} /> {selectedPath || 'No file selected'}</span>
            <span className="muted">edit here, save by reviewing a diff first</span>
          </div>
          <CodeEditor path={selectedPath || 'closed.txt'} value={code} onChange={setCode} />
          <div className="editorActions">
            <button className="ghost" type="button" onClick={() => void openFile(selectedPath)} disabled={busy || projectClosed || !selectedPath}>Reload file</button>
            <button className="primary" type="button" onClick={() => void proposeCurrentDraft()} disabled={busy || projectClosed || !dirtyDraft || !selectedPath}>Propose diff</button>
            <button className="danger" type="button" onClick={() => void applyApprovedDraft()} disabled={busy || projectClosed || !proposalMatchesDraft}><Save size={16} /> Save reviewed draft</button>
          </div>
        </section>

        <section className="cockpitPanel diffPanel">
          <div className="panelHeader"><GitBranch size={17} /><span>Guarded Diff</span></div>
          <pre className="cockpitPre diffText">{proposal?.diff || 'No diff proposal yet. Edit a draft and click Propose diff. No repository mutation happens here.'}</pre>
        </section>

        <section className="cockpitPanel statusPanel">
          <div className="panelHeader"><ShieldCheck size={17} /><span>Operation Cards</span></div>
          <div className="statusCards">
            <div className="statusCard"><strong>Project</strong><span>{selectedProject?.name || 'closed'}</span></div>
            <div className="statusCard"><strong>Project root</strong><span>{selectedProject?.root || 'none'}</span></div>
            <div className="statusCard"><strong>Token configured</strong><span>{statusText(githubAuth.token_configured, 'false')}</span></div>
            <div className="statusCard"><strong>Owner</strong><span>{statusText(githubAuth.owner, 'not configured')}</span></div>
            <div className="statusCard"><strong>Branch</strong><span>{statusText(githubOps.branch, 'not a repo')}</span></div>
            <div className="statusCard"><strong>Remote</strong><span>{statusText(githubOps.remote_origin_url, 'none')}</span></div>
            <div className="statusCard"><strong>Dirty</strong><span>{statusText(githubOps.dirty, 'false')}</span></div>
            <div className="statusCard"><strong>Docker presets</strong><span>{dockerPresets.length ? dockerPresets.join(', ') : 'none loaded'}</span></div>
          </div>
        </section>

        <section className="cockpitPanel previewPanel">
          <div className="panelHeader"><Activity size={17} /><span>Preview / Proof</span></div>
          {previewHtml ? <iframe title="HTML preview" srcDoc={previewHtml} sandbox="allow-same-origin" /> : <div className="emptyPreview">Open an HTML file to preview it here. App preview routing can be wired into this lane next.</div>}
        </section>

        <section className="cockpitPanel terminalPanel">
          <div className="panelHeader"><TerminalSquare size={17} /><span>Operation Log</span></div>
          <pre className="cockpitPre">{operationLog.join('\n')}</pre>
        </section>

        <section className="cockpitPanel bridgePanel">
          <div className="panelHeader"><Server size={17} /><span>Project Manager Rule</span></div>
          <p>The cockpit can switch only between approved project roots: the default X-8 workspace, roots configured in X8_APPROVED_PROJECT_ROOTS, or mounted folders under /projects.</p>
          <p className="muted">Open Project does not browse the whole host drive. Mount a project folder into /projects or register an approved root, then refresh.</p>
          <div className="doneLine"><Check size={15} /> Select project, edit drafts, review diff, approve before write.</div>
        </section>
      </section>
    </main>
  );
}
