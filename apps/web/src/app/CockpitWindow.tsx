import { useEffect, useMemo, useState } from 'react';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { loadFiles, proposeUpdate, readFile } from '../services/apiClient';
import type { FileEntry, PatchProposal } from '../types/contracts';
import './cockpitWindow.css';

type EditorView = 'code' | 'preview';

const VIEWABLE_EXTENSIONS = ['.html', '.htm', '.md', '.markdown', '.json', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif'];

function extensionOf(path: string) {
  const match = path.toLowerCase().match(/\.[^.]+$/);
  return match?.[0] ?? '';
}

function canPreview(path: string) {
  return VIEWABLE_EXTENSIONS.includes(extensionOf(path));
}

function previewUrl(path: string, stamp: number) {
  const params = new URLSearchParams({ path, t: String(stamp) });
  return `/api/workspace/preview?${params.toString()}`;
}

function escapeHtml(value: string) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function markdownHtml(value: string) {
  return value
    .split('\n')
    .map((line) => {
      if (line.startsWith('### ')) return `<h3>${escapeHtml(line.slice(4))}</h3>`;
      if (line.startsWith('## ')) return `<h2>${escapeHtml(line.slice(3))}</h2>`;
      if (line.startsWith('# ')) return `<h1>${escapeHtml(line.slice(2))}</h1>`;
      if (line.trim().startsWith('- ')) return `<p>• ${escapeHtml(line.trim().slice(2))}</p>`;
      if (!line.trim()) return '<br />';
      return `<p>${escapeHtml(line)}</p>`;
    })
    .join('');
}

function renderPreview(path: string, draft: string, stamp: number) {
  const ext = extensionOf(path);
  if (!path) return <div className="emptyPreview">Open a viewable file to preview it here.</div>;
  if (!canPreview(path)) return <pre className="cockpitPre">{draft || 'This file type uses code view.'}</pre>;
  if (ext === '.md' || ext === '.markdown') return <article className="markdownPreview" dangerouslySetInnerHTML={{ __html: markdownHtml(draft) }} />;
  if (ext === '.json') return <pre className="cockpitPre">{draft}</pre>;
  return <iframe title={`Preview ${path}`} src={previewUrl(path, stamp)} />;
}

export function CockpitWindow() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState('');
  const [draft, setDraft] = useState('');
  const [proposal, setProposal] = useState<PatchProposal | null>(null);
  const [status, setStatus] = useState('loading cockpit workspace');
  const [query, setQuery] = useState('');
  const [view, setView] = useState<EditorView>('code');
  const [previewStamp, setPreviewStamp] = useState(Date.now());

  const visibleFiles = useMemo(() => {
    const filtered = files.filter((file) => file.kind === 'file');
    if (!query.trim()) return filtered;
    const needle = query.toLowerCase();
    return filtered.filter((file) => file.path.toLowerCase().includes(needle));
  }, [files, query]);

  async function refreshFiles(nextPath?: string) {
    try {
      const payload = await loadFiles();
      const nextFiles = payload.data ?? [];
      setFiles(nextFiles);
      const fallback = nextFiles.find((file) => file.kind === 'file')?.path ?? '';
      const pathToOpen = nextPath || selectedPath || fallback;
      setStatus(`workspace ready · ${nextFiles.length} visible entries`);
      if (pathToOpen) await openFile(pathToOpen);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'workspace unavailable');
    }
  }

  async function openFile(path: string) {
    setSelectedPath(path);
    setProposal(null);
    try {
      const payload = await readFile(path);
      setDraft(payload.data.content);
      setStatus(`opened ${path}`);
      if (canPreview(path)) setPreviewStamp(Date.now());
    } catch (error) {
      setDraft('');
      setStatus(error instanceof Error ? error.message : `could not open ${path}`);
    }
  }

  async function proposeDiff() {
    if (!selectedPath) return;
    try {
      const payload = await proposeUpdate(selectedPath, draft);
      setProposal(payload.data);
      setStatus('guarded diff proposed; no repository mutation happened');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'diff proposal failed');
    }
  }

  useEffect(() => {
    void refreshFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="cockpitWindow" aria-label="X8 Native Operator Cockpit">
      <header className="cockpitTopbar">
        <div className="cockpitBrand"><div className="cockpitMark">X</div><div><p className="cockpitEyebrow">Operator cockpit</p><h1>Xoduz Builder Surface</h1></div></div>
        <div className="projectSwitcher"><label><span>Editor mode</span><select value={view} onChange={(event) => setView(event.target.value as EditorView)}><option value="code">Code</option><option value="preview">Preview</option></select></label></div>
        <div className="cockpitStatusStrip"><span className="statusBadge good">sandbox scoped</span><span className="statusBadge">preview enabled</span></div>
        <div className="cockpitTopActions"><button className="primary" type="button" onClick={() => void refreshFiles()}>Refresh</button></div>
      </header>

      <div className="projectBar"><strong>Status</strong><span>{status}</span></div>

      <section className="cockpitGrid">
        <aside className="cockpitPanel fileExplorer">
          <div className="panelHeader split"><span>Sandbox Files</span><span className="muted">{visibleFiles.length}</span></div>
          <input className="cockpitSearch" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter files…" />
          <div className="fileScroll">{visibleFiles.map((file) => <button key={file.path} className={file.path === selectedPath ? 'fileButton active' : 'fileButton'} type="button" onClick={() => void openFile(file.path)}>{file.path}</button>)}</div>
        </aside>

        <section className="cockpitPanel editorPanel">
          <div className="panelHeader split"><span>{selectedPath || 'No file selected'}</span><span className="muted">flip between code and preview</span></div>
          <div className="editorToolbar"><button className={view === 'code' ? 'primary compact' : 'ghost compact'} type="button" onClick={() => setView('code')}>Code</button><button className={view === 'preview' ? 'primary compact' : 'ghost compact'} type="button" onClick={() => { setView('preview'); setPreviewStamp(Date.now()); }} disabled={!canPreview(selectedPath)}>Preview</button><button className="ghost compact" type="button" onClick={() => selectedPath && void openFile(selectedPath)}>Reload file</button></div>
          {view === 'code' ? <CodeEditor path={selectedPath} value={draft} onChange={setDraft} /> : <div className="editorPreview">{renderPreview(selectedPath, draft, previewStamp)}</div>}
          <div className="editorActions"><button className="ghost" type="button" onClick={() => void proposeDiff()} disabled={!selectedPath}>Propose diff</button></div>
        </section>

        <aside className="cockpitPanel statusPanel"><div className="panelHeader">Bridge / Proof</div><div className="statusCards"><div className="statusCard"><strong>Preview</strong><span>Viewable files render in the main editor surface instead of the tiny card.</span></div><div className="statusCard"><strong>Selected file</strong><span>{selectedPath || 'none'}</span></div></div></aside>

        <section className="cockpitPanel diffPanel"><div className="panelHeader">Guarded Diff</div><pre className="cockpitPre diffText">{proposal?.diff || 'No diff proposal yet. Edit a draft and click Propose diff. No repository mutation happens here.'}</pre></section>
      </section>
    </main>
  );
}
