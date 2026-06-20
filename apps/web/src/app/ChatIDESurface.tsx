import { useEffect, useMemo, useState } from 'react';
import { Code2, FileText, GitBranch, Play, RotateCcw, ShieldCheck, TerminalSquare } from 'lucide-react';
import { loadIDEGitStatus, loadIDESummary, openIDEFile, proposeIDECommand, proposeIDERollback, runIDECommand } from '../services/apiClient';
import type { FileEntry, FileRead } from '../types/contracts';
import { StatusPill } from '../components/ui/StatusPill';
import { Panel } from './AssistantComponents';

type IDEPermission = { action: string; allowed: boolean; blocked: boolean; approval_required: boolean; reason: string; scope: string };
type IDEActivity = { action_type: string; scope: string; approval_required: boolean; status: string; files_touched?: string[]; command?: string; proof?: string; fallback?: string };
type IDESummary = {
  files: FileEntry[];
  selected_file?: FileRead | null;
  git_status: Record<string, unknown>;
  checkpoint: Record<string, unknown>;
  test_commands: string[];
  permissions: IDEPermission[];
  activity: IDEActivity[];
};

const emptySummary: IDESummary = { files: [], selected_file: null, git_status: {}, checkpoint: {}, test_commands: [], permissions: [], activity: [] };

export function ChatIDESurface() {
  const [summary, setSummary] = useState<IDESummary>(emptySummary);
  const [selectedPath, setSelectedPath] = useState('README.md');
  const [file, setFile] = useState<FileRead | null>(null);
  const [command, setCommand] = useState('docker compose -f compose.yaml run --rm --build web-tests');
  const [commandReceipt, setCommandReceipt] = useState<Record<string, unknown>>({ status: 'idle', reason: 'No command proposed yet.' });
  const [rollback, setRollback] = useState<Record<string, unknown>>({ action: 'none', reason: 'No rollback proposal loaded.' });
  const files = useMemo(() => (summary.files || []).filter((entry) => entry.kind === 'file').slice(0, 80), [summary.files]);
  const git = summary.git_status || {};
  const checkpoint = summary.checkpoint || {};

  useEffect(() => { void refresh(selectedPath); }, []);

  async function refresh(path = selectedPath) {
    try {
      const response = await loadIDESummary(path);
      const data = response.data && !Array.isArray(response.data) ? response.data as IDESummary : emptySummary;
      setSummary(data);
      setFile(data.selected_file || null);
    } catch {
      setCommandReceipt({ status: 'unavailable', reason: 'Chat IDE summary could not load.' });
    }
  }

  async function openPath(path: string) {
    setSelectedPath(path);
    const response = await openIDEFile(path);
    setFile(response.data);
  }

  async function proposeCommand(nextCommand = command) {
    const response = await proposeIDECommand(nextCommand);
    setCommandReceipt(response.data);
  }

  async function runCommand(nextCommand = command) {
    const response = await runIDECommand(nextCommand, false);
    setCommandReceipt(response.data);
  }

  async function refreshGit() {
    const response = await loadIDEGitStatus();
    setSummary((current) => ({ ...current, git_status: response.data }));
  }

  async function loadRollback(action: string) {
    const response = await proposeIDERollback(action);
    setRollback(response.data);
  }

  return (
    <section className="developerCockpit" aria-label="Chat IDE Core">
      <Panel icon={<ShieldCheck />} title="Workspace Status">
        <div className="list dense">
          <div className="row split"><strong>Mode</strong><StatusPill label="Chat IDE Core v1" status="ready" /></div>
          <div className="row split"><strong>Branch</strong><span>{String(git.branch || checkpoint.branch || 'unknown')}</span></div>
          <div className="row split"><strong>Dirty</strong><span>{String(git.dirty ?? checkpoint.working_tree_dirty ?? false)}</span></div>
          <div className="row split"><strong>Files indexed</strong><span>{files.length}</span></div>
          <button className="ghost" type="button" onClick={() => void refresh()}>Refresh IDE</button>
        </div>
      </Panel>
      <Panel icon={<FileText />} title="Workspace Explorer">
        <div className="fileList" aria-label="Chat IDE workspace file list">
          {files.map((entry) => <button key={entry.path} className={entry.path === selectedPath ? 'file active' : 'file'} onClick={() => void openPath(entry.path)}>{entry.path}</button>)}
        </div>
      </Panel>
      <Panel icon={<Code2 />} title="Read-only File Viewer">
        <div className="editorHead"><span>{file?.path || selectedPath}</span><span>{file?.line_count || 0} lines</span></div>
        <pre className="codeBlock smallBlock">{file?.content || 'Select a workspace file to view it read-only.'}</pre>
        <div className="inlineActions"><button className="chipButton" type="button" onClick={() => void proposeCommand('git diff --stat')}>Diff review proposal</button><button className="chipButton" type="button">Edit proposal requires approval</button></div>
      </Panel>
      <Panel icon={<TerminalSquare />} title="Terminal + Test Proposals">
        <div className="list dense">
          <label className="row"><strong>Command</strong><select aria-label="IDE command selector" value={command} onChange={(event) => setCommand(event.target.value)}>{summary.test_commands.map((item) => <option key={item} value={item}>{item}</option>)}<option value="git status --short">git status --short</option><option value="docker compose config">docker compose config</option></select></label>
          <div className="inlineActions"><button className="chipButton" type="button" onClick={() => void proposeCommand()}>Propose</button><button className="chipButton" type="button" onClick={() => void runCommand()}>Run allowed</button></div>
          <pre className="codeBlock smallBlock">{JSON.stringify(commandReceipt, null, 2)}</pre>
        </div>
      </Panel>
      <Panel icon={<GitBranch />} title="Source Control">
        <div className="list dense">
          <div className="row split"><strong>Remote</strong><span>{String(git.remote_origin_url || 'none')}</span></div>
          <div className="row split"><strong>Ahead / behind</strong><span>{String(git.ahead ?? 'unknown')} / {String(git.behind ?? 'unknown')}</span></div>
          <div className="row"><strong>Changed files</strong><span>{Array.isArray(git.changed_files) ? git.changed_files.join(', ') || 'none' : 'unknown'}</span></div>
          <div className="row"><strong>Recent commits</strong><span>{Array.isArray(git.recent_commits) ? git.recent_commits.slice(0, 3).join(' | ') : String((git.last_commit as Record<string, unknown> | undefined)?.message || 'none')}</span></div>
          <div className="inlineActions"><button className="chipButton" type="button" onClick={() => void refreshGit()}>Refresh Git</button><button className="chipButton" type="button" onClick={() => void proposeCommand('git status --short')}>Status card</button><button className="chipButton" type="button" onClick={() => void proposeCommand('git commit -m \"checkpoint\"')}>Commit proposal</button></div>
        </div>
      </Panel>
      <Panel icon={<RotateCcw />} title="Checkpoint + Rollback">
        <div className="list dense">
          <div className="row"><strong>HEAD</strong><span>{String((checkpoint.head as Record<string, unknown> | undefined)?.sha || '')} {String((checkpoint.head as Record<string, unknown> | undefined)?.message || '')}</span></div>
          <div className="row"><strong>Rollback guidance</strong><span>{Array.isArray(checkpoint.rollback_guidance) ? checkpoint.rollback_guidance.join(' ') : 'Rollback requires approval.'}</span></div>
          <div className="inlineActions"><button className="chipButton" type="button" onClick={() => void loadRollback('preview_untracked_cleanup')}>Preview clean</button><button className="chipButton" type="button" onClick={() => void loadRollback('discard_working_tree')}>Discard proposal</button><button className="chipButton" type="button" onClick={() => void loadRollback('reset_to_origin_main')}>Reset proposal</button></div>
          <pre className="codeBlock smallBlock">{JSON.stringify(rollback, null, 2)}</pre>
        </div>
      </Panel>
      <Panel icon={<Play />} title="Agent Activity Log">
        <div className="list dense">{summary.activity.map((item, index) => <div className="row" key={`${item.action_type}-${index}`}><strong>{item.action_type}</strong><span>{item.status} / approval: {String(item.approval_required)} / {item.proof || item.command || item.scope}</span></div>)}</div>
      </Panel>
    </section>
  );
}
