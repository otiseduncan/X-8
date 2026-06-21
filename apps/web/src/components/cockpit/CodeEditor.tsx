import { useMemo, useState } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { EditorState, type Extension } from '@codemirror/state';
import { Decoration, EditorView, ViewPlugin, type DecorationSet, type ViewUpdate } from '@codemirror/view';

type TokenSpan = {
  from: number;
  to: number;
  className: string;
  priority: number;
};

type CodeEditorProps = {
  path: string;
  value: string;
  onChange: (value: string) => void;
  onRun?: (value: string) => Promise<string> | string;
  onSave?: (value: string) => void;
};

function addTokenMatches(spans: TokenSpan[], lineText: string, lineOffset: number, pattern: RegExp, className: string, priority: number) {
  const regex = new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`);
  let match: RegExpExecArray | null;

  while ((match = regex.exec(lineText)) !== null) {
    const value = match[0];
    if (!value) {
      regex.lastIndex += 1;
      continue;
    }

    spans.push({
      from: lineOffset + match.index,
      to: lineOffset + match.index + value.length,
      className,
      priority,
    });
  }
}

function overlaps(a: TokenSpan, b: TokenSpan) {
  return a.from < b.to && b.from < a.to;
}

function powerShellTokensForLine(lineText: string, lineOffset: number) {
  const spans: TokenSpan[] = [];

  addTokenMatches(spans, lineText, lineOffset, /#.*/, 'tok-xoduz-comment', 0);
  addTokenMatches(spans, lineText, lineOffset, /"(?:[^"`]|`.)*"|'(?:[^']|'')*'/, 'tok-xoduz-string', 1);
  addTokenMatches(spans, lineText, lineOffset, /\$[A-Za-z_][\w:]*/, 'tok-xoduz-variable', 2);
  addTokenMatches(spans, lineText, lineOffset, /\b(?:param|try|catch|finally|if|else|elseif|foreach|for|while|switch|function|return|throw|exit|true|false|null)\b/i, 'tok-xoduz-keyword', 3);
  addTokenMatches(spans, lineText, lineOffset, /\b[A-Z][A-Za-z]+-[A-Za-z][A-Za-z]+\b/, 'tok-xoduz-command', 4);
  addTokenMatches(spans, lineText, lineOffset, /-[A-Za-z][A-Za-z0-9]+\b/, 'tok-xoduz-parameter', 5);
  addTokenMatches(spans, lineText, lineOffset, /\b\d+(?:\.\d)?(?:KB|MB|GB)?\b/i, 'tok-xoduz-number', 6);
  addTokenMatches(spans, lineText, lineOffset, /[=|{}()[\],.;]/, 'tok-xoduz-operator', 7);

  const accepted: TokenSpan[] = [];
  for (const span of spans.sort((a, b) => a.priority - b.priority || a.from - b.from || b.to - a.to)) {
    if (!accepted.some((candidate) => overlaps(candidate, span))) {
      accepted.push(span);
    }
  }

  return accepted.sort((a, b) => a.from - b.from || a.to - b.to);
}

function buildPowerShellDecorations(view: EditorView): DecorationSet {
  const marks = [];

  for (const visibleRange of view.visibleRanges) {
    let position = visibleRange.from;

    while (position <= visibleRange.to) {
      const line = view.state.doc.lineAt(position);
      for (const token of powerShellTokensForLine(line.text, line.from)) {
        marks.push(Decoration.mark({ class: token.className }).range(token.from, token.to));
      }

      if (line.to >= visibleRange.to) break;
      position = line.to + 1;
    }
  }

  return Decoration.set(marks, true);
}

const powerShellSyntax = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = buildPowerShellDecorations(view);
    }

    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildPowerShellDecorations(update.view);
      }
    }
  },
  {
    decorations: (value) => value.decorations,
  },
);

function languageFor(path: string): Extension[] {
  if (path.endsWith('.ps1')) return [powerShellSyntax];
  if (path.endsWith('.py')) return [python()];
  if (path.endsWith('.json')) return [json()];
  if (path.endsWith('.html')) return [html()];
  if (path.endsWith('.css')) return [css()];
  if (path.endsWith('.ts') || path.endsWith('.tsx') || path.endsWith('.js') || path.endsWith('.jsx')) {
    return [javascript({ jsx: true, typescript: path.endsWith('.ts') || path.endsWith('.tsx') })];
  }
  return [];
}

function languageLabel(path: string) {
  if (path.endsWith('.ps1')) return 'PowerShell';
  if (path.endsWith('.py')) return 'Python';
  if (path.endsWith('.json')) return 'JSON';
  if (path.endsWith('.html')) return 'HTML';
  if (path.endsWith('.css')) return 'CSS';
  if (path.endsWith('.tsx')) return 'React TSX';
  if (path.endsWith('.jsx')) return 'React JSX';
  if (path.endsWith('.ts')) return 'TypeScript';
  if (path.endsWith('.js')) return 'JavaScript';
  return 'Text';
}

function isExecutable(path: string) {
  return path.endsWith('.ps1') || path.endsWith('.py') || path.endsWith('.js') || path.endsWith('.ts');
}

function isPreviewable(path: string) {
  return path.endsWith('.html');
}

export function CodeEditor({ path, value, onChange, onRun, onSave }: CodeEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const label = languageLabel(path);
  const canPreview = isPreviewable(path);
  const canRun = isExecutable(path);

  const extensions = useMemo(
    () => [
      ...languageFor(path),
      EditorView.editable.of(isEditing),
      EditorState.readOnly.of(!isEditing),
    ],
    [path, isEditing],
  );

  const handleSave = () => {
    onSave?.(value);
    setIsEditing(false);
    setStatusText('Saved in draft.');
  };

  const handlePaste = async () => {
    try {
      const pasted = await navigator.clipboard.readText();
      onChange(pasted);
      setIsEditing(true);
      setStatusText('Pasted into draft.');
    } catch {
      setStatusText('Paste failed. Browser clipboard permission may be blocked.');
    }
  };

  const handleRun = async () => {
    if (!canRun) return;

    if (!onRun) {
      setStatusText('Run is visible, but the sandbox runner is not connected yet.');
      return;
    }

    setIsRunning(true);
    setStatusText('Running in sandbox...');
    try {
      const result = await onRun(value);
      setStatusText(result || 'Run completed.');
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : 'Run failed.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="codeMirrorShell xoduzCodeMirrorShell">
      <style>{`
        .xoduzCodeMirrorShell { background: #030712; border: 1px solid rgba(34, 211, 238, 0.24); border-radius: 9px; overflow: hidden; }
        .xoduzEditorHeader {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          min-height: 30px;
          border-bottom: 1px solid rgba(34, 211, 238, 0.28);
          background: linear-gradient(90deg, rgba(34, 211, 238, 0.14), rgba(15, 23, 42, 0.86));
          padding: 0 8px 0 10px;
        }
        .xoduzEditorTitle {
          color: #67e8f9;
          font-size: 0.72rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .xoduzEditorActions {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 5px;
          flex-wrap: nowrap;
          white-space: nowrap;
        }
        .xoduzEditorButton {
          border: 1px solid rgba(34, 211, 238, 0.28);
          background: rgba(2, 6, 23, 0.86);
          color: #bae6fd;
          border-radius: 6px;
          min-height: 22px;
          padding: 2px 7px;
          font-size: 0.68rem;
          font-weight: 750;
          line-height: 1;
          cursor: pointer;
        }
        .xoduzEditorButton:hover { border-color: rgba(34, 211, 238, 0.58); color: #ecfeff; }
        .xoduzEditorButton:disabled { cursor: not-allowed; opacity: 0.45; }
        .xoduzEditorButtonPrimary { color: #facc15; border-color: rgba(250, 204, 21, 0.4); }
        .xoduzCodeMirrorShell .cm-editor { background: #030712; color: #dbeafe; }
        .xoduzCodeMirrorShell .cm-gutters { background: #020617; color: #64748b; border-right: 1px solid rgba(34, 211, 238, 0.18); }
        .xoduzCodeMirrorShell .cm-content { font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace; font-size: 0.86rem; }
        .xoduzCodeMirrorShell .cm-line:nth-child(even) { background: rgba(15, 23, 42, 0.78); }
        .xoduzCodeMirrorShell .cm-activeLine { background: rgba(34, 211, 238, 0.12) !important; }
        .xoduzCodeMirrorShell .cm-activeLineGutter { background: rgba(34, 211, 238, 0.14) !important; color: #e0f2fe; }
        .xoduzCodeMirrorShell .cm-scroller { line-height: 1.55; }
        .xoduzEditorStatus {
          border-top: 1px solid rgba(34, 211, 238, 0.16);
          background: rgba(15, 23, 42, 0.78);
          color: #bae6fd;
          font-size: 0.72rem;
          padding: 6px 10px;
        }
        .xoduzCodePreview {
          width: 100%;
          min-height: 280px;
          border: 0;
          border-top: 1px solid rgba(34, 211, 238, 0.22);
          background: #ffffff;
        }
        .xoduzCodeMirrorShell .tok-xoduz-keyword,
        .xoduzCodeMirrorShell .tok-keyword { color: #c084fc; font-weight: 700; }
        .xoduzCodeMirrorShell .tok-xoduz-command,
        .xoduzCodeMirrorShell .tok-propertyName { color: #fb923c; font-weight: 650; }
        .xoduzCodeMirrorShell .tok-xoduz-parameter,
        .xoduzCodeMirrorShell .tok-xoduz-number,
        .xoduzCodeMirrorShell .tok-number { color: #facc15; }
        .xoduzCodeMirrorShell .tok-xoduz-string,
        .xoduzCodeMirrorShell .tok-string { color: #fde68a; }
        .xoduzCodeMirrorShell .tok-xoduz-variable,
        .xoduzCodeMirrorShell .tok-variableName { color: #38bdf8; }
        .xoduzCodeMirrorShell .tok-xoduz-comment,
        .xoduzCodeMirrorShell .tok-comment { color: #60a5fa; font-style: italic; opacity: 0.82; }
        .xoduzCodeMirrorShell .tok-xoduz-operator,
        .xoduzCodeMirrorShell .tok-operator { color: #a78bfa; }
        .xoduzCodeMirrorShell .tok-invalid,
        .xoduzCodeMirrorShell .cm-diagnostic-error { color: var(--color-danger); }
      `}</style>

      <div className="xoduzEditorHeader">
        <div className="xoduzEditorTitle">{label} / draft / not run</div>
        <div className="xoduzEditorActions">
          {canPreview ? (
            <button className="xoduzEditorButton" type="button" onClick={() => setShowPreview((current) => !current)}>
              Preview
            </button>
          ) : null}
          <button className="xoduzEditorButton" type="button" onClick={() => setIsEditing((current) => !current)}>
            {isEditing ? 'Lock' : 'Edit'}
          </button>
          <button className="xoduzEditorButton" type="button" onClick={handleSave}>
            Save
          </button>
          <button className="xoduzEditorButton" type="button" onClick={handlePaste}>
            Paste
          </button>
          {canRun ? (
            <button className="xoduzEditorButton xoduzEditorButtonPrimary" type="button" onClick={handleRun} disabled={isRunning}>
              {isRunning ? 'Running' : 'Run'}
            </button>
          ) : null}
        </div>
      </div>

      <CodeMirror
        value={value}
        height="318px"
        theme="dark"
        extensions={extensions}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true }}
        onChange={(nextValue) => {
          if (isEditing) {
            onChange(nextValue);
            setStatusText(null);
          }
        }}
      />

      {statusText ? <div className="xoduzEditorStatus">{statusText}</div> : null}
      {showPreview && canPreview ? <iframe className="xoduzCodePreview" title={`${label} preview`} srcDoc={value} sandbox="allow-scripts allow-forms allow-popups" /> : null}
    </div>
  );
}
