import CodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';

function languageFor(path: string) {
  if (path.endsWith('.py')) return python();
  if (path.endsWith('.json')) return json();
  if (path.endsWith('.html')) return html();
  if (path.endsWith('.css')) return css();
  if (path.endsWith('.ts') || path.endsWith('.tsx') || path.endsWith('.js') || path.endsWith('.jsx')) return javascript({ jsx: true, typescript: path.endsWith('.ts') || path.endsWith('.tsx') });
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

export function CodeEditor({ path, value, onChange }: { path: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="codeMirrorShell xoduzCodeMirrorShell" data-language={languageLabel(path)}>
      <style>{`
        .xoduzCodeMirrorShell { background: #030712; }
        .xoduzCodeMirrorShell::before {
          content: attr(data-language) ' / draft / not run';
          display: flex;
          align-items: center;
          min-height: 30px;
          border-bottom: 1px solid rgba(34, 211, 238, 0.28);
          background: linear-gradient(90deg, rgba(34, 211, 238, 0.14), rgba(15, 23, 42, 0.86));
          color: #67e8f9;
          font-size: 0.72rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          padding: 0 10px;
          text-transform: uppercase;
        }
        .xoduzCodeMirrorShell .cm-editor { background: #030712; color: #dbeafe; }
        .xoduzCodeMirrorShell .cm-gutters { background: #020617; color: #64748b; border-right: 1px solid rgba(34, 211, 238, 0.18); }
        .xoduzCodeMirrorShell .cm-content { font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace; font-size: 0.86rem; }
        .xoduzCodeMirrorShell .cm-line:nth-child(even) { background: rgba(15, 23, 42, 0.78); }
        .xoduzCodeMirrorShell .cm-activeLine { background: rgba(34, 211, 238, 0.12) !important; }
        .xoduzCodeMirrorShell .cm-activeLineGutter { background: rgba(34, 211, 238, 0.14) !important; color: #e0f2fe; }
        .xoduzCodeMirrorShell .cm-scroller { line-height: 1.55; }
      `}</style>
      <CodeMirror
        value={value}
        height="318px"
        theme="dark"
        extensions={[languageFor(path)].flat()}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true }}
        onChange={onChange}
      />
    </div>
  );
}
