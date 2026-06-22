import { Activity, Check, Code2, ExternalLink, FileText, GitBranch, RefreshCcw, Server, ShieldCheck, TerminalSquare } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { StatusPill } from '../components/ui/StatusPill';
import { applyUpdate, loadBridgeStatus, loadDockerPresets, loadFiles, loadGitHubOpsAuthStatus, loadGitHubOpsStatus, loadGitHubStatus, proposeUpdate, readFile } from '../services/apiClient';
import type { FileEntry, PatchProposal } from '../types/contracts';
import './cockpitWindow.css';

const DEFAULT_PATH = 'README.md';

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

export function CockpitWindow() {
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

  const dirtyDraft = code !== savedCode;
  const changedCount = countChangedFiles(githubOps);
  const filteredFiles = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const fileList = files.filter((item) => item.kind === 'file');
    if (!needle) return fileList.slice(0, 180);
    return fileList.filter((item) => item.path.toLowerCase().includes(needle)).slice(0, 180);
  }, [files, filter]);

  useEffect(() => {
    void refreshCockpit();
  }, []);

  useEffect(() => {
    void openFile(selectedPath, false);
  }, [selectedPath]);

  function log(message: string) {
    setOperationLog((current) => [`[${nowStamp()}] ${message}`, ...current].slice(0, 80));
  }

  async function refreshCockpit() {
    setBusy(true);
    try {
      const [fileResponse, bridgeResponse, githubResponse, authResponse, opsResponse, dockerResponse] = await Promise.allSettled([
        loadFiles(),
        loadBridgeStatus(),
        loadGitHubStatus(),
        loadGitHubOpsAuthStatus(),
        loadGitHubOpsStatus(),
        loadDockerPresets()
      ]);
      if (fileResponse.status === 'fulfilled') setFiles(fileResponse.value.data.filter((item) => item.kind === 'file'));
      if (bridgeResponse.status === 'fulfilled') setBridgeStatus(String(bridgeResponse.value.data.bridge_reachable ? 'reachable' : 'unreachable'));
      if (githubResponse.status === 'fulfilled') setGithubStatus(String(githubResponse.value.data.status || githubResponse.value.status));
      if (authResponse.status === 'fulfilled') setGithubAuth(authResponse.value.data || {});
      if (opsResponse.status === 'fulfilled') setGithubOps(opsResponse.value.data || {});
      if (dockerResponse.status === 'fulfilled') setDockerPresets(dockerResponse.value.data || []);
      log('Refreshed workspace, bridge, GitHub, and Docker status.');
    } catch {
      log('Refresh failed. Check x8-api logs.');
    } finally {
      setBusy(false);
    }
  }

  async function openFile(path: string, announce = true) {
    if (!path) return;
    setBusy(true);
    try {
      const response = await readFile(path);
      setCode(response.data.content);
      setSavedCode(response.data.content);
      setProposal(null);
      setPreviewHtml(path.endsWith('.html') ? response.data.content : '');
      if (announce) log(`Opened ${path} read-only into cockpit editor.`);
    } catch {
      setCode('File could not be loaded from the configured workspace root.');
      setSavedCode('');
      log(`Could not open ${path}.`);
    } finally {
      setBusy(false);
    }
  }

  async function proposeCurrentDraft() {
    setBusy(true);
    try {
      const response = await proposeUpdate(selectedPath, code);
      setProposal(response.data);
      log(`Prepared guarded diff for ${selectedPath}. No write has run.`);
    } catch {
      log(`Diff proposal failed for ${selectedPath}. No write ran.`);
    } finally {
      setBusy(false);
    }
  }

  async function applyApprovedDraft() {
    const approved = window.confirm(`Apply the approved cockpit draft to ${selectedPath}?`);
    if (!approved) {
      log(`Apply cancelled for ${selectedPath}.`);
      return;
    }
    setBusy(true);
    try {
      const response = await applyUpdate(selectedPath, code, true);
      setProposal(response.data);
      if (response.data.mutated) {
        setSavedCode(code);
        log(`Applied approved change to ${selectedPath}.`);
      } else {
        log(`Apply endpoint returned without mutation for ${selectedPath}.`);
      }
      await refreshCockpit();
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
        <div className="cockpitStatusStrip">
          <StatusPill label={`Bridge ${bridgeStatus}`} status={bridgeStatus} />
          <StatusPill label={`GitHub ${githubStatus}`} status={githubStatus} />
          <StatusPill label={`${changedCount} changed`} status={changedCount ? 'warning' : 'ready'} />
          <StatusPill label={dirtyDraft ? 'draft dirty' : 'draft clean'} status={dirtyDraft ? 'warning' : 'ready'} />
        </div>
        <div className="cockpitTopActions">
          <button className="ghost" type="button" onClick={openChat}><ExternalLink size={16} /> Chat</button>
          <button className="primary" type="button" onClick={() => void refreshCockpit()} disabled={busy}><RefreshCcw size={16} /> Refresh</button>
        </div>
      </header>

      <section className="cockpitGrid">
        <aside className="cockpitPanel fileExplorer">
          <div className="panelHeader"><FileText size={17} /><span>Project Files</span></div>
          <input className="cockpitSearch" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter files..." />
          <div className="fileScroll">
            {filteredFiles.map((file) => (
              <button key={file.path} className={file.path === selectedPath ? 'fileButton active' : 'fileButton'} type="button" onClick={() => setSelectedPath(file.path)}>
                {file.path}
              </button>
            ))}
          </div>
        </aside>

        <section className="cockpitPanel editorPanel">
          <div className="panelHeader split">
            <span><Code2 size={17} /> {selectedPath}</span>
            <span className="muted">typing is draft-only until approved</span>
          </div>
          <CodeEditor path={selectedPath} value={code} onChange={setCode} />
          <div className="editorActions">
            <button className="ghost" type="button" onClick={() => void openFile(selectedPath)} disabled={busy}>Reload file</button>
            <button className="primary" type="button" onClick={() => void proposeCurrentDraft()} disabled={busy || !dirtyDraft}>Propose diff</button>
            <button className="danger" type="button" onClick={() => void applyApprovedDraft()} disabled={busy || !proposal}>Apply approved</button>
          </div>
        </section>

        <section className="cockpitPanel diffPanel">
          <div className="panelHeader"><GitBranch size={17} /><span>Guarded Diff</span></div>
          <pre className="cockpitPre diffText">{proposal?.diff || 'No diff proposal yet. Edit a draft and click Propose diff. No repository mutation happens here.'}</pre>
        </section>

        <section className="cockpitPanel statusPanel">
          <div className="panelHeader"><ShieldCheck size={17} /><span>Operation Cards</span></div>
          <div className="statusCards">
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
          <div className="panelHeader"><Server size={17} /><span>Rollback Rule</span></div>
          <p>The mirror path is not the primary operator surface. This cockpit uses structured API state, guarded drafts, diffs, receipts, and approvals instead of screen pixels.</p>
          <p className="muted">Live shell/terminal streaming should be added later behind protected local bridge gates.</p>
          <div className="doneLine"><Check size={15} /> View first, draft second, approve before write.</div>
        </section>
      </section>
    </main>
  );
}
