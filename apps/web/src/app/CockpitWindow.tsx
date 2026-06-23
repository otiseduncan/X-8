import { useEffect, useMemo, useRef, useState } from 'react';
import { CodeEditor } from '../components/cockpit/CodeEditor';
import { applyUpdate, loadFiles, proposeUpdate, readFile } from '../services/apiClient';
import type { FileEntry, PatchProposal } from '../types/contracts';
import './cockpitWindow.css';

type EditorView = 'code' | 'preview';

const VIEWABLE_EXTENSIONS = ['.html', '.htm', '.md', '.markdown', '.json', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif'];
const LIVE_PRIORITY_FILES = ['README.md', 'proof/X8_VISUAL_OPERATOR_PROOF.md', 'proof/status.json', 'proof/SCREEN_RECORDING_STEPS.md'];
const LOCAL_LAYOUT = '.editorPanel{grid-column:2/3;grid-row:1/3}.statusPanel{grid-column:3/4;grid-row:1/2}.diffPanel{grid-column:3/4;grid-row:2/3}.editorToolbar{display:flex;gap:10px;flex-wrap:wrap;border-bottom:1px solid rgba(0,212,255,.1);padding:8px 10px}.editorPanel .codeMirrorShell,.editorPreview{flex:1;min-height:0;overflow:hidden}.editorPreview{display:flex;background:rgba(5,7,13,.82)}.editorPreview iframe{width:100%;flex:1;min-height:0;border:0;background:white}.markdownPreview{flex:1;overflow:auto;padding:18px 22px;color:#e2e8f0;line-height:1.6}.primary,.ghost{display:inline-flex;align-items:center;justify-content:center;min-height:36px;border-radius:8px;cursor:pointer;font-weight:800;gap:8px;padding:0 12px}.primary{border:1px solid rgba(0,212,255,.45);background:linear-gradient(135deg,#22d3ee,#0ea5e9);color:#03131d}.ghost{border:1px solid rgba(0,212,255,.22);background:rgba(0,212,255,.08);color:#dff7ff}.statusBadge{border:1px solid rgba(0,212,255,.2);border-radius:999px;background:rgba(0,212,255,.08);color:#dbeafe;font-size:.76rem;font-weight:800;padding:6px 10px}.statusBadge.live{border-color:rgba(134,239,172,.58);background:rgba(34,197,94,.14);color:#dcfce7;box-shadow:0 0 24px rgba(34,197,94,.14)}.fileButton.liveTarget{border-color:rgba(134,239,172,.38);box-shadow:inset 3px 0 0 rgba(34,197,94,.72)}.liveWriteBanner{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid rgba(134,239,172,.2);padding:8px 10px;background:linear-gradient(90deg,rgba(22,163,74,.18),rgba(14,165,233,.09));color:#dcfce7;font-size:.78rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase}.liveDot{width:10px;height:10px;border-radius:999px;background:#22c55e;box-shadow:0 0 18px #22c55e;display:inline-block;margin-right:8px}.editorPanel[data-live-pulse="true"]{box-shadow:0 0 0 1px rgba(34,197,94,.42),0 0 34px rgba(34,197,94,.14)}';

function extensionOf(path: string) { const match = path.toLowerCase().match(/\.[^.]+$/); return match?.[0] ?? ''; }
function canPreview(path: string) { return VIEWABLE_EXTENSIONS.includes(extensionOf(path)); }
function previewUrl(path: string, stamp: number) { const params = new URLSearchParams({ path, t: String(stamp) }); return `/api/workspace/preview?${params.toString()}`; }
function escapeHtml(value: string) { return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function markdownHtml(value: string) { return value.split('\n').map((line) => { if (line.startsWith('### ')) return `<h3>${escapeHtml(line.slice(4))}</h3>`; if (line.startsWith('## ')) return `<h2>${escapeHtml(line.slice(3))}</h2>`; if (line.startsWith('# ')) return `<h1>${escapeHtml(line.slice(2))}</h1>`; if (line.trim().startsWith('- ')) return `<p>• ${escapeHtml(line.trim().slice(2))}</p>`; if (!line.trim()) return '<br />'; return `<p>${escapeHtml(line)}</p>`; }).join(''); }
function renderPreview(path: string, draft: string, stamp: number) { const ext = extensionOf(path); if (!path) return <div className="emptyPreview">Open a viewable file to preview it here.</div>; if (!canPreview(path)) return <pre className="cockpitPre">{draft || 'This file type uses code view.'}</pre>; if (ext === '.md' || ext === '.markdown') return <article className="markdownPreview" dangerouslySetInnerHTML={{ __html: markdownHtml(draft) }} />; if (ext === '.json') return <pre className="cockpitPre">{draft}</pre>; return <iframe title={`Preview ${path}`} src={previewUrl(path, stamp)} />; }
function chooseLiveFile(files: FileEntry[], selectedPath: string) { const filePaths = new Set(files.filter((file) => file.kind === 'file').map((file) => file.path)); if (selectedPath && filePaths.has(selectedPath)) return selectedPath; return LIVE_PRIORITY_FILES.find((path) => filePaths.has(path)) || Array.from(filePaths)[0] || ''; }
function fileSignature(files: FileEntry[]) { return files.map((file) => `${file.kind}:${file.path}`).sort().join('|'); }

export function CockpitWindow() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState('');
  const [draft, setDraft] = useState('');
  const [proposal, setProposal] = useState<PatchProposal | null>(null);
  const [status, setStatus] = useState('loading cockpit workspace');
  const [query, setQuery] = useState('');
  const [view, setView] = useState<EditorView>('code');
  const [previewStamp, setPreviewStamp] = useState(Date.now());
  const [livePulse, setLivePulse] = useState(false);
  const [lastLiveEvent, setLastLiveEvent] = useState('watching for X writes');
  const selectedPathRef = useRef('');
  const draftRef = useRef('');
  const signatureRef = useRef('');
  const openingRef = useRef(false);

  const visibleFiles = useMemo(() => { const filtered = files.filter((file) => file.kind === 'file'); if (!query.trim()) return filtered; const needle = query.toLowerCase(); return filtered.filter((file) => file.path.toLowerCase().includes(needle)); }, [files, query]);

  async function openFile(path: string, options?: { live?: boolean; silent?: boolean }) {
    if (!path) return;
    selectedPathRef.current = path;
    setSelectedPath(path);
    setProposal(null);
    openingRef.current = true;
    try {
      const payload = await readFile(path);
      const content = payload.data.content;
      draftRef.current = content;
      setDraft(content);
      if (!options?.silent) setStatus(`${options?.live ? 'live opened' : 'opened'} ${path}`);
      if (options?.live) {
        setLastLiveEvent(`X write detected · opened ${path}`);
        setLivePulse(true);
        window.setTimeout(() => setLivePulse(false), 1600);
      }
      if (canPreview(path)) setPreviewStamp(Date.now());
    } catch (error) {
      draftRef.current = '';
      setDraft('');
      if (!options?.silent) setStatus(error instanceof Error ? error.message : `could not open ${path}`);
    } finally {
      openingRef.current = false;
    }
  }

  async function refreshFiles(nextPath?: string, options?: { live?: boolean; silent?: boolean }) {
    try {
      const payload = await loadFiles();
      const nextFiles = payload.data ?? [];
      const nextSignature = fileSignature(nextFiles);
      const signatureChanged = signatureRef.current !== '' && signatureRef.current !== nextSignature;
      signatureRef.current = nextSignature;
      setFiles(nextFiles);
      const pathToOpen = nextPath || chooseLiveFile(nextFiles, selectedPathRef.current);
      if (!options?.silent) setStatus(`workspace ready · ${nextFiles.length} visible entries`);
      if (pathToOpen) {
        if (signatureChanged || pathToOpen !== selectedPathRef.current || !draftRef.current) await openFile(pathToOpen, { live: options?.live || signatureChanged, silent: options?.silent && !signatureChanged });
      }
    } catch (error) {
      if (!options?.silent) setStatus(error instanceof Error ? error.message : 'workspace unavailable');
    }
  }

  async function pollLiveWorkspace() {
    if (openingRef.current) return;
    try {
      const payload = await loadFiles();
      const nextFiles = payload.data ?? [];
      const nextSignature = fileSignature(nextFiles);
      const signatureChanged = signatureRef.current !== '' && signatureRef.current !== nextSignature;
      signatureRef.current = nextSignature;
      setFiles(nextFiles);
      const pathToOpen = chooseLiveFile(nextFiles, selectedPathRef.current);
      if (!pathToOpen) return;
      const payloadFile = await readFile(pathToOpen);
      const nextDraft = payloadFile.data.content;
      const contentChanged = pathToOpen === selectedPathRef.current && nextDraft !== draftRef.current;
      if (signatureChanged || contentChanged || pathToOpen !== selectedPathRef.current) {
        selectedPathRef.current = pathToOpen;
        setSelectedPath(pathToOpen);
        draftRef.current = nextDraft;
        setDraft(nextDraft);
        setProposal(null);
        setPreviewStamp(Date.now());
        setStatus(`live X workspace update detected · ${pathToOpen}`);
        setLastLiveEvent(`X write detected · ${pathToOpen}`);
        setLivePulse(true);
        window.setTimeout(() => setLivePulse(false), 1600);
      }
    } catch {
      // Keep the live watcher quiet during rebuilds so the recording surface does not spam errors.
    }
  }

  async function proposeDiff() {
    if (!selectedPath) return;
    try { const payload = await proposeUpdate(selectedPath, draft); setProposal(payload.data); setStatus('guarded diff proposed; no repository mutation happened'); } catch (error) { setStatus(error instanceof Error ? error.message : 'diff proposal failed'); }
  }

  async function applyDraft() {
    if (!selectedPath) return;
    try { const payload = await applyUpdate(selectedPath, draft, true); setProposal(payload.data); setStatus(payload.message || 'approved edit applied inside workspace root'); draftRef.current = draft; setPreviewStamp(Date.now()); await refreshFiles(selectedPath); } catch (error) { setStatus(error instanceof Error ? error.message : 'apply failed'); }
  }

  useEffect(() => { void refreshFiles(); }, []);
  useEffect(() => { selectedPathRef.current = selectedPath; }, [selectedPath]);
  useEffect(() => { draftRef.current = draft; }, [draft]);
  useEffect(() => { const timer = window.setInterval(() => void pollLiveWorkspace(), 1250); return () => window.clearInterval(timer); }, []);

  return (
    <main className="cockpitWindow" aria-label="X8 Native Operator Cockpit">
      <style>{LOCAL_LAYOUT}</style>
      <header className="cockpitTopbar"><div className="cockpitBrand"><div className="cockpitMark">X</div><div><p className="cockpitEyebrow">Operator cockpit</p><h1>Xoduz Builder Surface</h1></div></div><div className="projectSwitcher"><label><span>Editor mode</span><select value={view} onChange={(event) => setView(event.target.value as EditorView)}><option value="code">Code</option><option value="preview">Preview</option></select></label></div><div className="cockpitStatusStrip"><span className="statusBadge good">sandbox scoped</span><span className="statusBadge live"><span className="liveDot" />live workspace watcher</span><span className="statusBadge">preview enabled</span></div><div className="cockpitTopActions"><button className="primary" type="button" onClick={() => void refreshFiles()}>Refresh</button></div></header>
      <div className="projectBar"><strong>Status</strong><span>{status}</span></div>
      <section className="cockpitGrid">
        <aside className="cockpitPanel fileExplorer"><div className="panelHeader split"><span>Sandbox Files</span><span className="muted">{visibleFiles.length}</span></div><input className="cockpitSearch" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter files…" /><div className="fileScroll">{visibleFiles.map((file) => <button key={file.path} className={`${file.path === selectedPath ? 'fileButton active' : 'fileButton'} ${LIVE_PRIORITY_FILES.includes(file.path) ? 'liveTarget' : ''}`} type="button" onClick={() => void openFile(file.path)}>{file.path}</button>)}</div></aside>
        <section className="cockpitPanel editorPanel" data-live-pulse={livePulse ? 'true' : 'false'}><div className="panelHeader split"><span>{selectedPath || 'No file selected'}</span><span className="muted">live follow enabled</span></div><div className="liveWriteBanner"><span><span className="liveDot" />{lastLiveEvent}</span><span>{livePulse ? 'WRITING' : 'WATCHING'}</span></div><div className="editorToolbar"><button className={view === 'code' ? 'primary compact' : 'ghost compact'} type="button" onClick={() => setView('code')}>Code</button><button className={view === 'preview' ? 'primary compact' : 'ghost compact'} type="button" onClick={() => { setView('preview'); setPreviewStamp(Date.now()); }} disabled={!canPreview(selectedPath)}>Preview</button><button className="ghost compact" type="button" onClick={() => selectedPath && void openFile(selectedPath)}>Reload file</button></div>{view === 'code' ? <CodeEditor path={selectedPath} value={draft} onChange={setDraft} /> : <div className="editorPreview">{renderPreview(selectedPath, draft, previewStamp)}</div>}<div className="editorActions"><button className="ghost" type="button" onClick={() => void proposeDiff()} disabled={!selectedPath}>Propose diff</button><button className="danger" type="button" onClick={() => void applyDraft()} disabled={!selectedPath}>Apply reviewed draft</button></div></section>
        <aside className="cockpitPanel statusPanel"><div className="panelHeader">Bridge / Proof</div><div className="statusCards"><div className="statusCard"><strong>Live writes</strong><span>The cockpit now watches /projects and auto-opens README/proof files when X writes them.</span></div><div className="statusCard"><strong>Selected file</strong><span>{selectedPath || 'none'}</span></div></div></aside>
        <section className="cockpitPanel diffPanel"><div className="panelHeader">Guarded Diff</div><pre className="cockpitPre diffText">{proposal?.diff || 'No diff proposal yet. Edit a draft and click Propose diff. No repository mutation happens here.'}</pre></section>
      </section>
    </main>
  );
}
