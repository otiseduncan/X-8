import { useEffect, useMemo, useRef, useState } from 'react';
import { CodeEditor } from '../../components/cockpit/CodeEditor';
import type {
  ArtifactCommand,
  ArtifactDiffEntry,
  ArtifactRevisionHistoryEntry,
  ArtifactWorkbenchSnapshot,
  ArtifactWorkbenchState,
  PendingArtifactRevision,
} from '../../types/contracts';

type ArtifactTopTab = 'Preview' | 'Code' | 'Files' | 'Assets' | 'Console' | 'Metadata' | 'History/Log' | 'Export';
type ApprovalState = 'draft' | 'edited' | 'saved' | 'proposed' | 'approved' | 'denied' | 'applied';

interface WorkbenchFile {
  path: string;
  language: string;
  content: string;
  role: string;
}

interface WorkbenchAsset {
  id: string;
  path: string;
  type: string;
  label: string;
  editable: boolean;
  content: string;
}

interface ConsoleEntry {
  id: string;
  level: 'log' | 'warn' | 'error';
  text: string;
  ts: string;
}

interface RuntimeError {
  id: string;
  text: string;
  ts: string;
}

interface ArtifactCardLike {
  id: string;
  title: string;
  summary: string;
  payload?: Record<string, unknown>;
}

interface ArtifactWorkbenchProps {
  card: ArtifactCardLike;
  onCardUpdate: (patch: { status?: string; summary?: string; payload?: Record<string, unknown> }) => void;
}

function nowId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function detectLanguage(path: string) {
  if (path.endsWith('.html')) return 'html';
  if (path.endsWith('.css')) return 'css';
  if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'typescript';
  if (path.endsWith('.js') || path.endsWith('.jsx')) return 'javascript';
  if (path.endsWith('.json')) return 'json';
  if (path.endsWith('.py')) return 'python';
  return 'text';
}

function textContent(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function normalizePath(input: string) {
  return input.replace(/^\.\//, '').replace(/\\/g, '/');
}

function asRecord(value: unknown) {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {};
}

function packageSignature(filesByPath: Record<string, string>) {
  return JSON.stringify(Object.keys(filesByPath).sort().map((path) => [path, filesByPath[path]]));
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeFiles(payload: Record<string, unknown>) {
  const rawFiles = Array.isArray(payload.files) ? payload.files : [];
  if (rawFiles.length > 0) {
    return rawFiles.map((raw) => {
      const record = typeof raw === 'object' && raw !== null ? raw as Record<string, unknown> : {};
      const path = normalizePath(textContent(record.path));
      return {
        path,
        language: textContent(record.language) || detectLanguage(path),
        role: textContent(record.role) || 'source',
        content: textContent(record.content)
      } satisfies WorkbenchFile;
    }).filter((file) => file.path.length > 0);
  }

  const html = textContent(payload.html);
  const css = textContent(payload.css);
  const javascript = textContent(payload.javascript || payload.js);
  const pages = Array.isArray(payload.pages) ? payload.pages : [];

  const pageFiles = pages.map((raw, index) => {
    const record = typeof raw === 'object' && raw !== null ? raw as Record<string, unknown> : {};
    const path = normalizePath(textContent(record.path) || (index === 0 ? 'index.html' : `page-${index + 1}.html`));
    return {
      path,
      language: 'html',
      role: 'page',
      content: textContent(record.content) || (index === 0 ? html : '')
    } satisfies WorkbenchFile;
  });

  const fallbackHtml = pageFiles.length > 0 ? [] : [{ path: 'index.html', language: 'html', role: 'page', content: html } satisfies WorkbenchFile];
  const fallbackCss = css ? [{ path: 'styles.css', language: 'css', role: 'style', content: css } satisfies WorkbenchFile] : [];
  const fallbackJs = javascript ? [{ path: 'script.js', language: 'javascript', role: 'script', content: javascript } satisfies WorkbenchFile] : [];

  return [...pageFiles, ...fallbackHtml, ...fallbackCss, ...fallbackJs];
}

function normalizeAssets(payload: Record<string, unknown>) {
  const raw = Array.isArray(payload.assets) ? payload.assets : [];
  return raw.map((asset, index) => {
    const record = typeof asset === 'object' && asset !== null ? asset as Record<string, unknown> : {};
    const path = normalizePath(textContent(record.path) || `asset-${index + 1}`);
    return {
      id: textContent(record.id) || `asset-${index + 1}`,
      path,
      type: textContent(record.type) || 'asset',
      label: textContent(record.label) || path,
      editable: Boolean(record.editable),
      content: textContent(record.content)
    } satisfies WorkbenchAsset;
  });
}

function collectPreviewPaths(filesByPath: Record<string, string>) {
  const htmlFiles = Object.keys(filesByPath).filter((path) => path.endsWith('.html'));
  if (htmlFiles.length > 0) return htmlFiles;
  return ['index.html'];
}

function buildPreviewDocument(args: { filesByPath: Record<string, string>; previewPath: string; packageId: string }) {
  const { filesByPath, previewPath, packageId } = args;
  const htmlFiles = collectPreviewPaths(filesByPath);
  const currentPath = htmlFiles.includes(previewPath) ? previewPath : htmlFiles[0];
  const html = filesByPath[currentPath] || '<main><h1>Preview unavailable</h1></main>';
  const cssPaths = Object.keys(filesByPath).filter((path) => path.endsWith('.css'));
  const jsPaths = Object.keys(filesByPath).filter((path) => path.endsWith('.js') || path.endsWith('.ts') || path.endsWith('.tsx') || path.endsWith('.jsx'));
  const cssBlock = cssPaths.map((path) => `/* ${path} */\n${filesByPath[path] || ''}`).join('\n\n');
  const jsBlock = jsPaths.map((path) => `/* ${path} */\n${filesByPath[path] || ''}`).join('\n\n');
  const knownPages = JSON.stringify(htmlFiles);
  const token = escapeHtml(packageId);

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>${cssBlock}</style>
</head>
<body>
${html}
<script>
(() => {
  const token = ${JSON.stringify(token)};
  const pages = ${knownPages};
  const emit = (type, payload) => parent.postMessage({ source: 'x8-artifact-workbench', token, type, payload }, '*');
  ['log', 'warn', 'error'].forEach((level) => {
    const original = console[level];
    console[level] = (...args) => {
      emit('console', { level, args: args.map((arg) => {
        try { return typeof arg === 'string' ? arg : JSON.stringify(arg); } catch { return String(arg); }
      }) });
      original.apply(console, args);
    };
  });
  window.addEventListener('error', (event) => {
    emit('runtime_error', { message: event.message || 'Unknown runtime error', source: event.filename || '', line: event.lineno || 0, col: event.colno || 0 });
  });
  window.addEventListener('unhandledrejection', (event) => {
    emit('runtime_error', { message: String(event.reason || 'Unhandled promise rejection'), source: '', line: 0, col: 0 });
  });
  document.addEventListener('click', (event) => {
    const target = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (!target) return;
    const href = target.getAttribute('href') || '';
    if (!href || href.startsWith('http://') || href.startsWith('https://') || href.startsWith('mailto:') || href.startsWith('#')) return;
    const normalized = href.replace(/^\.\//, '').split('?')[0].split('#')[0];
    if (pages.includes(normalized)) {
      event.preventDefault();
      emit('navigate', { path: normalized });
    }
  });
})();
</script>
<script>${jsBlock}</script>
</body>
</html>`;
}

export function ArtifactWorkbench({ card, onCardUpdate }: ArtifactWorkbenchProps) {
  const payload = card.payload || {};
  const artifactBridge = asRecord(payload.artifactBridge);
  const pendingCommand = asRecord(artifactBridge.command) as Partial<ArtifactCommand>;
  const initialFiles = useMemo(() => normalizeFiles(payload), [payload]);
  const initialAssets = useMemo(() => normalizeAssets(payload), [payload]);

  const initialFilesByPath = useMemo(() => {
    return initialFiles.reduce<Record<string, string>>((acc, file) => {
      acc[file.path] = file.content;
      return acc;
    }, {});
  }, [initialFiles]);

  const [filesByPath, setFilesByPath] = useState<Record<string, string>>(initialFilesByPath);
  const [originalFilesByPath, setOriginalFilesByPath] = useState<Record<string, string>>(initialFilesByPath);
  const [savedFilesByPath, setSavedFilesByPath] = useState<Record<string, string>>(initialFilesByPath);
  const [dirtyByPath, setDirtyByPath] = useState<Record<string, boolean>>({});
  const [activeFilePath, setActiveFilePath] = useState<string>(Object.keys(initialFilesByPath)[0] || 'index.html');
  const [activeTopTab, setActiveTopTab] = useState<ArtifactTopTab>('Preview');
  const [activePreviewPath, setActivePreviewPath] = useState<string>(collectPreviewPaths(initialFilesByPath)[0] || 'index.html');
  const [consoleEntries, setConsoleEntries] = useState<ConsoleEntry[]>([]);
  const [runtimeErrors, setRuntimeErrors] = useState<RuntimeError[]>([]);
  const [highlightedFilePath, setHighlightedFilePath] = useState<string>('');
  const [highlightedLine, setHighlightedLine] = useState<number>(1);
  const [highlightedLineEnd, setHighlightedLineEnd] = useState<number>(1);
  const [highlightedToken, setHighlightedToken] = useState<string>('');
  const [workbenchState, setWorkbenchState] = useState<ArtifactWorkbenchState>('idle');
  const [pendingRevision, setPendingRevision] = useState<PendingArtifactRevision | null>(null);
  const [lastArtifactCommand, setLastArtifactCommand] = useState<string>('');
  const [revisionHistory, setRevisionHistory] = useState<ArtifactRevisionHistoryEntry[]>([]);
  const [diffEntries, setDiffEntries] = useState<ArtifactDiffEntry[]>([]);
  const [approvalState, setApprovalState] = useState<ApprovalState>('proposed');
  const [approvedPackageSignature, setApprovedPackageSignature] = useState<string>('');
  const [historyLog, setHistoryLog] = useState<string[]>(['Package generated and opened in Artifact Workbench.']);
  const [applyReceipt, setApplyReceipt] = useState<string>('');
  const lastPublishedPatchRef = useRef('');
  const lastAppliedCommandIdRef = useRef('');
  const sourceFileSignature = useMemo(() => packageSignature(initialFilesByPath), [initialFilesByPath]);

  useEffect(() => {
    setFilesByPath(initialFilesByPath);
    setOriginalFilesByPath(initialFilesByPath);
    setSavedFilesByPath(initialFilesByPath);
    setDirtyByPath({});
    setActiveFilePath(Object.keys(initialFilesByPath)[0] || 'index.html');
    setActivePreviewPath(collectPreviewPaths(initialFilesByPath)[0] || 'index.html');
    setActiveTopTab('Preview');
    setConsoleEntries([]);
    setRuntimeErrors([]);
    setHighlightedFilePath('');
    setHighlightedLine(1);
    setHighlightedLineEnd(1);
    setHighlightedToken('');
    setWorkbenchState('idle');
    setPendingRevision(null);
    setLastArtifactCommand('');
    setRevisionHistory([]);
    setDiffEntries([]);
    setApprovalState('proposed');
    setApprovedPackageSignature('');
    setHistoryLog(['Package generated and opened in Artifact Workbench.']);
    setApplyReceipt('');
    lastAppliedCommandIdRef.current = '';
  }, [card.id, sourceFileSignature]);

  const filePaths = useMemo(() => Object.keys(filesByPath).sort(), [filesByPath]);
  const pagePaths = useMemo(() => collectPreviewPaths(filesByPath), [filesByPath]);
  const activeFileDiffEntries = useMemo(() => diffEntries.filter((entry) => entry.file_path === activeFilePath), [activeFilePath, diffEntries]);

  const packageDirty = useMemo(() => Object.values(dirtyByPath).some(Boolean), [dirtyByPath]);
  const activeFileContent = filesByPath[activeFilePath] || '';

  const previewDocument = useMemo(() => buildPreviewDocument({ filesByPath, previewPath: activePreviewPath, packageId: card.id }), [filesByPath, activePreviewPath, card.id]);

  const applyEnabled = approvalState === 'approved'
    && !packageDirty
    && (approvedPackageSignature === '' || packageSignature(savedFilesByPath) === approvedPackageSignature);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const data = (event.data || {}) as Record<string, unknown>;
      if (data.source !== 'x8-artifact-workbench') return;
      if (data.token !== card.id) return;
      const type = String(data.type || '');
      const payloadRecord = typeof data.payload === 'object' && data.payload !== null ? data.payload as Record<string, unknown> : {};
      if (type === 'console') {
        const level = (String(payloadRecord.level || 'log') as 'log' | 'warn' | 'error');
        const args = Array.isArray(payloadRecord.args) ? payloadRecord.args.map(String).join(' ') : '';
        setConsoleEntries((current) => [{ id: nowId(), level, text: args, ts: new Date().toISOString() }, ...current].slice(0, 200));
      }
      if (type === 'runtime_error') {
        const message = String(payloadRecord.message || 'Runtime error');
        const source = String(payloadRecord.source || '');
        const line = Number(payloadRecord.line || 0);
        const col = Number(payloadRecord.col || 0);
        const composed = `${message}${source ? ` @ ${source}` : ''}${line ? `:${line}` : ''}${col ? `:${col}` : ''}`;
        setRuntimeErrors((current) => [{ id: nowId(), text: composed, ts: new Date().toISOString() }, ...current].slice(0, 100));
      }
      if (type === 'navigate') {
        const nextPath = normalizePath(String(payloadRecord.path || ''));
        if (nextPath && filesByPath[nextPath]) {
          setActivePreviewPath(nextPath);
          setHistoryLog((current) => [`Preview route switched to ${nextPath}.`, ...current].slice(0, 200));
        }
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [card.id, filesByPath]);

  useEffect(() => {
    const nextPayload = {
      ...payload,
      artifactBridge: {
        ...artifactBridge,
        snapshot: {
          package_id: card.id,
          title: card.title,
          package_type: textContent(payload.package_type) || 'website_package',
          active_file_path: activeFilePath,
          active_tab: activeTopTab,
          active_preview_path: activePreviewPath,
          available_files: filePaths,
          files_by_path: filesByPath,
          saved_files_by_path: savedFilesByPath,
          dirty_by_path: dirtyByPath,
          approval_state: approvalState,
          highlighted_file_path: highlightedFilePath,
          highlighted_line_start: highlightedLine,
          highlighted_line_end: highlightedLineEnd,
          highlighted_token: highlightedToken,
          workbench_state: workbenchState,
          pending_revision: pendingRevision,
          last_artifact_command: lastArtifactCommand,
          revision_history: revisionHistory,
          diff_entries: diffEntries,
        } satisfies ArtifactWorkbenchSnapshot,
        last_applied_command_id: lastAppliedCommandIdRef.current
      }
    };
    if (pendingCommand.id && pendingCommand.id === lastAppliedCommandIdRef.current) {
      delete (nextPayload.artifactBridge as Record<string, unknown>).command;
    }
    const status = approvalState === 'applied'
      ? 'applied'
      : approvalState === 'approved'
        ? 'approved'
        : approvalState === 'denied'
          ? 'denied'
          : packageDirty
            ? 'edited'
            : 'proposed';
    const patch = {
      status,
      summary: applyReceipt || `Workbench ready. ${filePaths.length} files loaded.`,
      payload: nextPayload
    };
    const signature = JSON.stringify(patch);
    if (lastPublishedPatchRef.current === signature) return;
    lastPublishedPatchRef.current = signature;
    onCardUpdate(patch);
  }, [activeFilePath, activePreviewPath, activeTopTab, approvalState, applyReceipt, artifactBridge, card.id, card.title, diffEntries, dirtyByPath, filePaths, filesByPath, highlightedFilePath, highlightedLine, highlightedLineEnd, highlightedToken, lastArtifactCommand, packageDirty, payload, pendingCommand.id, pendingRevision, revisionHistory, savedFilesByPath, workbenchState]);

  useEffect(() => {
    if (!pendingCommand.id || pendingCommand.id === lastAppliedCommandIdRef.current || pendingCommand.package_id !== card.id) return;
    const command = pendingCommand as ArtifactCommand;
    const commandSummary = command.summary || command.explanation || `${command.command_class}:${command.type}`;
    setLastArtifactCommand(commandSummary);
    if (command.workbench_state) {
      setWorkbenchState(command.workbench_state);
    }
    if (Object.prototype.hasOwnProperty.call(command, 'pending_revision')) {
      setPendingRevision(command.pending_revision || null);
    }
    if (command.type === 'select_tab' && command.tab) {
      setActiveTopTab(command.tab as ArtifactTopTab);
    }
    if ((command.type === 'select_file' || command.type === 'highlight_line' || command.type === 'locate' || command.type === 'edit_file' || command.type === 'apply_pending_revision' || command.type === 'explain_location') && command.file_path && filesByPath[command.file_path]) {
      setActiveFilePath(command.file_path);
      setHighlightedFilePath(command.file_path);
    }
    if (command.type === 'highlight_line' || command.type === 'locate' || command.type === 'explain_location') {
      setActiveTopTab('Code');
      setHighlightedLine(Math.max(1, Number(command.line_start || 1)));
      setHighlightedLineEnd(Math.max(Number(command.line_end || command.line_start || 1), Number(command.line_start || 1)));
      setHighlightedToken(command.token || '');
      setHistoryLog((current) => [`Command highlight: ${command.file_path || activeFilePath} ${command.line_start || 1}-${command.line_end || command.line_start || 1}.`, ...current].slice(0, 200));
    }
    if ((command.type === 'edit_file' || command.type === 'apply_pending_revision') && command.file_path && typeof command.replacement === 'string') {
      const path = command.file_path;
      const beforeContent = filesByPath[path] || '';
      const afterContent = command.replacement as string;
      setFilesByPath((current) => ({ ...current, [path]: command.replacement as string }));
      const savedContent = savedFilesByPath[path] || '';
      const changed = command.replacement !== savedContent;
      setDirtyByPath((current) => ({ ...current, [path]: changed }));
      setHighlightedLine(Math.max(1, Number(command.line_start || 1)));
      setHighlightedLineEnd(Math.max(Number(command.line_end || command.line_start || 1), Number(command.line_start || 1)));
      setHighlightedToken(command.token || '');
      const nextDiffEntries = Array.isArray(command.diff_entries) ? command.diff_entries : [];
      if (nextDiffEntries.length > 0) {
        setDiffEntries(nextDiffEntries);
      }
      if (approvalState === 'approved' || approvalState === 'applied') {
        setApprovalState('proposed');
      }
      setRevisionHistory((current) => [{
        id: `revision-${Date.now()}`,
        timestamp: new Date().toISOString(),
        command_summary: commandSummary,
        file_path: path,
        before_snippet: beforeContent.split(/\r?\n/).slice(0, 6).join('\n'),
        after_snippet: afterContent.split(/\r?\n/).slice(0, 6).join('\n'),
        added_lines: command.added_lines || nextDiffEntries.filter((entry) => entry.kind === 'added' || entry.kind === 'modified_new').map((entry) => entry.line_number),
        deleted_lines: command.deleted_lines || nextDiffEntries.filter((entry) => entry.kind === 'deleted' || entry.kind === 'modified_old').map((entry) => entry.line_number),
        modified_lines: command.modified_lines || nextDiffEntries.filter((entry) => entry.kind === 'modified_old' || entry.kind === 'modified_new').map((entry) => entry.line_number),
        approved_state_invalidated: approvalState === 'approved' || approvalState === 'applied',
      }, ...current].slice(0, 80));
      setHistoryLog((current) => [command.explanation || `Edited ${path} from command bridge.`, ...current].slice(0, 200));
      setActiveTopTab((command.tab as ArtifactTopTab) || 'Preview');
      setWorkbenchState('preview_refreshed');
      setPendingRevision(null);
    }
    if (command.type === 'refresh_preview') {
      setActiveTopTab('Preview');
      setWorkbenchState('preview_refreshed');
    }
    lastAppliedCommandIdRef.current = command.id;
  }, [activeFilePath, approvalState, card.id, filesByPath, pendingCommand, savedFilesByPath]);

  function markDirty(path: string, nextContent: string) {
    const isDirty = nextContent !== (savedFilesByPath[path] || '');
    setDirtyByPath((current) => ({ ...current, [path]: isDirty }));
    return isDirty;
  }

  function updateActiveFile(content: string) {
    const path = activeFilePath;
    setFilesByPath((current) => ({ ...current, [path]: content }));
    const changed = markDirty(path, content);
    setWorkbenchState('editing_sandbox');
    if (approvalState === 'approved' || approvalState === 'applied') {
      if (changed || packageSignature({ ...filesByPath, [path]: content }) !== approvedPackageSignature) {
        setApprovalState('proposed');
        setWorkbenchState('awaiting_approval');
        setHistoryLog((current) => [`Edit on ${path} invalidated approval. Re-approval required.`, ...current].slice(0, 200));
      }
    }
  }

  function saveCurrentFile() {
    const path = activeFilePath;
    const content = filesByPath[path] || '';
    setSavedFilesByPath((current) => ({ ...current, [path]: content }));
    setDirtyByPath((current) => ({ ...current, [path]: false }));
    setApprovalState((current) => (current === 'draft' ? 'saved' : current));
    setHistoryLog((current) => [`Saved ${path}.`, ...current].slice(0, 200));
    if (approvalState === 'approved' || approvalState === 'applied') {
      const nextSignature = packageSignature({ ...savedFilesByPath, [path]: content });
      if (nextSignature !== approvedPackageSignature) {
        setApprovalState('proposed');
        setHistoryLog((current) => [`Saved changes on ${path} require re-approval.`, ...current].slice(0, 200));
      }
    }
  }

  function saveDraft() {
    setSavedFilesByPath(filesByPath);
    const cleared = Object.keys(filesByPath).reduce<Record<string, boolean>>((acc, path) => {
      acc[path] = false;
      return acc;
    }, {});
    setDirtyByPath(cleared);
    setHistoryLog((current) => ['Saved full package draft.', ...current].slice(0, 200));
    if (approvalState === 'approved' || approvalState === 'applied') {
      const nextSignature = packageSignature(filesByPath);
      if (nextSignature !== approvedPackageSignature) {
        setApprovalState('proposed');
        setHistoryLog((current) => ['Saved package changed after approval. Re-approval required.', ...current].slice(0, 200));
      }
    }
  }

  function revertFile() {
    const path = activeFilePath;
    const original = originalFilesByPath[path] || '';
    setFilesByPath((current) => ({ ...current, [path]: original }));
    setDirtyByPath((current) => ({ ...current, [path]: original !== (savedFilesByPath[path] || '') }));
    setHistoryLog((current) => [`Reverted ${path} to original content.`, ...current].slice(0, 200));
    if (approvalState === 'approved' || approvalState === 'applied') {
      setApprovalState('proposed');
    }
  }

  function revertPackage() {
    setFilesByPath(originalFilesByPath);
    setSavedFilesByPath(originalFilesByPath);
    const cleared = Object.keys(originalFilesByPath).reduce<Record<string, boolean>>((acc, path) => {
      acc[path] = false;
      return acc;
    }, {});
    setDirtyByPath(cleared);
    setApprovalState('proposed');
    setHistoryLog((current) => ['Reverted package to original generated snapshot.', ...current].slice(0, 200));
  }

  function approve() {
    const signature = packageSignature(savedFilesByPath);
    setApprovalState('approved');
    setWorkbenchState('approved');
    setApprovedPackageSignature(signature);
    setHistoryLog((current) => ['Approved saved package draft.', ...current].slice(0, 200));
  }

  function deny() {
    setApprovalState('denied');
    setHistoryLog((current) => ['Denied package draft.', ...current].slice(0, 200));
  }

  function apply() {
    if (!applyEnabled) return;
    const applyEndpoint = textContent(payload.apply_endpoint);
    if (!applyEndpoint) {
      const message = 'apply backend not configured';
      setApplyReceipt(message);
      setHistoryLog((current) => [`Apply attempted: ${message}.`, ...current].slice(0, 200));
      return;
    }
    setApprovalState('applied');
    setWorkbenchState('applied');
    const message = `Applied package draft via ${applyEndpoint}.`;
    setApplyReceipt(message);
    setHistoryLog((current) => [message, ...current].slice(0, 200));
  }

  function exportSingleHtml() {
    const htmlPath = pagePaths[0] || 'index.html';
    const blob = new Blob([filesByPath[htmlPath] || ''], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = htmlPath.split('/').pop() || 'artifact.html';
    a.click();
    URL.revokeObjectURL(url);
    setHistoryLog((current) => [`Exported ${htmlPath}.`, ...current].slice(0, 200));
  }

  function exportHtmlBundleFallback() {
    const htmlPath = pagePaths[0] || 'index.html';
    const html = filesByPath[htmlPath] || '';
    const cssPaths = filePaths.filter((path) => path.endsWith('.css'));
    const jsPaths = filePaths.filter((path) => path.endsWith('.js') || path.endsWith('.ts') || path.endsWith('.tsx') || path.endsWith('.jsx'));
    const bundled = `<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\"/>\n<style>\n${cssPaths.map((path) => `/* ${path} */\n${filesByPath[path] || ''}`).join('\n\n')}\n</style>\n</head>\n<body>\n${html}\n<script>\n${jsPaths.map((path) => `/* ${path} */\n${filesByPath[path] || ''}`).join('\n\n')}\n</script>\n</body>\n</html>`;
    const blob = new Blob([bundled], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'artifact-bundle-fallback.html';
    a.click();
    URL.revokeObjectURL(url);
    setHistoryLog((current) => ['Exported bundled HTML fallback (ZIP export not implemented).', ...current].slice(0, 200));
  }

  function clearConsole() {
    setConsoleEntries([]);
    setRuntimeErrors([]);
  }

  function goToHighlight() {
    const path = normalizePath(highlightedFilePath);
    if (!path || !filesByPath[path]) return;
    setActiveFilePath(path);
    setActiveTopTab('Code');
    setHistoryLog((current) => [`Navigated to ${path}:${highlightedLine}${highlightedToken ? ` token ${highlightedToken}` : ''}.`, ...current].slice(0, 200));
  }

  const statusBadge = approvalState === 'applied'
    ? 'applied'
    : approvalState === 'approved'
      ? 'approved'
      : approvalState === 'denied'
        ? 'denied'
        : packageDirty
          ? 'edited'
          : 'proposed';

  const topTabs: ArtifactTopTab[] = ['Preview', 'Code', 'Files', 'Assets', 'Console', 'Metadata', 'History/Log', 'Export'];

  return (
    <div className="artifactWorkbench" data-testid="artifact-workbench-shell">
      <header className="artifactPackageHeader" data-testid="artifact-package-header">
        <div className="artifactPackageMeta">
          <h3>{card.title}</h3>
          <p>{textContent(payload.package_type) || 'website_package'}</p>
          <span className={`artifactStatusBadge ${statusBadge}`}>{statusBadge}</span>
        </div>
        <div className="artifactPackageActions">
          <button className="chipButton" type="button" onClick={approve}>Approve</button>
          <button className="chipButton" type="button" onClick={deny}>Deny</button>
          <button className="chipButton" type="button" onClick={apply} disabled={!applyEnabled}>Apply</button>
          <button className="chipButton" type="button" onClick={exportSingleHtml}>Export</button>
        </div>
      </header>

      <div className="tabs artifactTopTabs" aria-label="Artifact package tabs">
        {topTabs.map((tab) => (
          <button key={tab} className={activeTopTab === tab ? 'tab active' : 'tab'} onClick={() => setActiveTopTab(tab)}>{tab}</button>
        ))}
      </div>

      {pagePaths.length > 1 && (
        <div className="tabs" aria-label="Artifact page tabs">
          {pagePaths.map((path) => (
            <button key={path} className={activePreviewPath === path ? 'tab active' : 'tab'} onClick={() => setActivePreviewPath(path)}>
              {path.split('/').pop()?.replace(/\.[^.]+$/, '') || path}
            </button>
          ))}
        </div>
      )}

      {activeTopTab === 'Preview' && (
        <div className="artifactPreviewPanel">
          <div className="row split"><strong>Preview route</strong><span>{activePreviewPath}</span></div>
          <iframe title="Inline website preview" srcDoc={previewDocument} sandbox="allow-scripts allow-forms allow-modals" data-testid="artifact-preview-frame" />
        </div>
      )}

      {activeTopTab === 'Code' && (
        <div className="artifactCodeLayout">
          <aside className="artifactFileTree" aria-label="Artifact file tree">
            <h4>Files</h4>
            <div className="artifactFileTreeList">
              {filePaths.map((path) => (
                <button
                  key={path}
                  type="button"
                  className={path === activeFilePath ? 'tab active' : 'tab'}
                  onClick={() => setActiveFilePath(path)}
                >
                  {path}
                  {dirtyByPath[path] && <span className="artifactDirtyDot" aria-label="dirty">*</span>}
                </button>
              ))}
            </div>
          </aside>
          <section className="artifactEditorPanel">
            <div className="row split"><strong>Editing</strong><span>{activeFilePath}</span></div>
            {(highlightedFilePath || highlightedToken) && (
              <p className="cardSummary" data-testid="artifact-highlight-summary">
                Highlighted {highlightedFilePath || activeFilePath} lines {highlightedLine}{highlightedLineEnd > highlightedLine ? `-${highlightedLineEnd}` : ''}{highlightedToken ? ` for ${highlightedToken}` : ''}.
              </p>
            )}
            <div data-testid="artifact-code-editor">
              <CodeEditor
                path={activeFilePath}
                value={activeFileContent}
                onChange={updateActiveFile}
                highlightLineStart={activeFileDiffEntries.length === 0 ? highlightedLine : undefined}
                highlightLineEnd={activeFileDiffEntries.length === 0 ? highlightedLineEnd : undefined}
                diffEntries={activeFileDiffEntries.map((entry) => ({ line_number: entry.line_number, kind: entry.kind }))}
              />
            </div>
            <div className="inlineActions">
              <button className="chipButton" type="button" onClick={saveCurrentFile}>Save current file</button>
              <button className="chipButton" type="button" onClick={saveDraft}>Save draft</button>
              <button className="chipButton" type="button" onClick={revertFile}>Revert file</button>
              <button className="chipButton" type="button" onClick={revertPackage}>Revert package</button>
            </div>
            <div className="artifactNavigator">
              <label className="fieldStack">
                <span>Highlight file path</span>
                <input value={highlightedFilePath} onChange={(event) => setHighlightedFilePath(event.target.value)} placeholder="e.g. styles.css" />
              </label>
              <label className="fieldStack">
                <span>Line</span>
                <input type="number" min={1} value={highlightedLine} onChange={(event) => setHighlightedLine(Math.max(1, Number(event.target.value || 1)))} />
              </label>
              <label className="fieldStack">
                <span>Token</span>
                <input value={highlightedToken} onChange={(event) => setHighlightedToken(event.target.value)} placeholder="e.g. hero-title" />
              </label>
              <button className="chipButton" type="button" onClick={goToHighlight}>Go to location</button>
            </div>
          </section>
        </div>
      )}

      {activeTopTab === 'Files' && (
        <div className="stack" aria-label="Artifact files panel">
          {filePaths.map((path) => (
            <div className="row split" key={path}>
              <strong>{path}</strong>
              <span>{dirtyByPath[path] ? 'dirty' : 'clean'}</span>
            </div>
          ))}
        </div>
      )}

      {activeTopTab === 'Assets' && (
        <div className="stack" aria-label="Artifact assets panel">
          {initialAssets.length === 0 && <p className="cardSummary">No assets in package.</p>}
          {initialAssets.map((asset) => (
            <div className="row split" key={asset.id}>
              <strong>{asset.path}</strong>
              <span>{asset.type}</span>
            </div>
          ))}
        </div>
      )}

      {activeTopTab === 'Console' && (
        <div className="stack" aria-label="Artifact console panel">
          <div className="inlineActions">
            <button className="chipButton" type="button" onClick={clearConsole}>Clear console</button>
          </div>
          {runtimeErrors.map((error) => (
            <div key={error.id} className="artifactConsoleEntry error">
              <strong>error</strong>
              <span>{error.text}</span>
            </div>
          ))}
          {consoleEntries.map((entry) => (
            <div key={entry.id} className={`artifactConsoleEntry ${entry.level}`}>
              <strong>{entry.level}</strong>
              <span>{entry.text}</span>
            </div>
          ))}
          {runtimeErrors.length === 0 && consoleEntries.length === 0 && <p className="cardSummary">Console is clear.</p>}
        </div>
      )}

      {activeTopTab === 'Metadata' && (
        <pre className="codeBlock">{JSON.stringify(payload.metadata || {}, null, 2)}</pre>
      )}

      {activeTopTab === 'History/Log' && (
        <div className="stack" aria-label="Artifact history panel">
          {applyReceipt && <div className="row"><strong>Apply receipt</strong><span>{applyReceipt}</span></div>}
          <div className="row split" data-testid="artifact-workbench-state">
            <strong>Workbench state</strong>
            <span>{workbenchState}</span>
          </div>
          {pendingRevision && (
            <p className="cardSummary" data-testid="artifact-pending-revision">
              Pending revision: {pendingRevision.revision_kind} in {pendingRevision.target_file_path}:{pendingRevision.line_start}-{pendingRevision.line_end}. {pendingRevision.followup_prompt}
            </p>
          )}
          {revisionHistory.length > 0 && (
            <div className="stack" data-testid="artifact-revision-history">
              <strong>Revision history</strong>
              {revisionHistory.map((entry) => (
                <div className="artifactRevisionCard" key={entry.id}>
                  <p className="cardSummary"><strong>{entry.command_summary}</strong> · {entry.file_path}</p>
                  {entry.approved_state_invalidated && <p className="cardSummary">Approval invalidated: true</p>}
                </div>
              ))}
            </div>
          )}
          {diffEntries.length > 0 && (
            <div className="artifactDiffPanel" data-testid="artifact-diff-history">
              <strong>Diff</strong>
              {diffEntries.map((entry, index) => (
                <p
                  key={`${entry.file_path}-${entry.line_number}-${entry.kind}-${index}`}
                  className={`artifactDiffLine ${entry.kind === 'added' || entry.kind === 'modified_new' ? 'added' : 'deleted'}`}
                >
                  {entry.kind === 'added' || entry.kind === 'modified_new' ? '+' : '-'} {entry.file_path}:{entry.line_number} {entry.content}
                </p>
              ))}
            </div>
          )}
          {historyLog.map((entry, index) => <p className="cardSummary" key={`${entry}-${index}`}>{entry}</p>)}
        </div>
      )}

      {activeTopTab === 'Export' && (
        <div className="stack" aria-label="Artifact export panel">
          <div className="inlineActions">
            <button className="chipButton" type="button" onClick={exportSingleHtml}>Export single HTML</button>
            <button className="chipButton" type="button" onClick={exportHtmlBundleFallback}>Export bundled fallback</button>
          </div>
          {filePaths.length > 1 && <p className="cardSummary">ZIP export not implemented yet. Use bundled HTML fallback for now.</p>}
          {filePaths.length <= 1 && <p className="cardSummary">Single-file artifact export is available.</p>}
        </div>
      )}
    </div>
  );
}
