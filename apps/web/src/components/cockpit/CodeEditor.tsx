import CodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { EditorView } from '@codemirror/view';
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from '@codemirror/language';
import { tags } from '@lezer/highlight';

function languageFor(path: string) {
  const lower = path.toLowerCase();
  if (lower.endsWith('.py')) return python();
  if (lower.endsWith('.json')) return json();
  if (lower.endsWith('.html') || lower.endsWith('.htm')) return html();
  if (lower.endsWith('.css')) return css();
  if (lower.endsWith('.ts') || lower.endsWith('.tsx') || lower.endsWith('.js') || lower.endsWith('.jsx')) return javascript({ jsx: true, typescript: lower.endsWith('.ts') || lower.endsWith('.tsx') });
  return xoduzCommandLanguage;
}

const xoduzCommandLanguage = StreamLanguage.define({
  token(stream) {
    if (stream.sol()) {
      if (stream.match(/^\s*#{1,6}\s+.*/)) return 'heading';
      if (stream.match(/^\s*[-*+]\s+/)) return 'punctuation';
      if (stream.match(/^\s*(PS\s+[^>]+>|[$>]\s*)/)) return 'keyword';
    }
    if (stream.match(/^\s*(function|def|class|const|let|var|async|export|import|from|return|if|else|for|while|try|catch|finally|throw|param|foreach|true|false|null)\b/)) return 'keyword';
    if (stream.match(/^\s*(git|docker|docker\s+compose|npm|pnpm|node|python|pip|Invoke-RestMethod|Invoke-WebRequest|Set-Content|Get-Content|Test-Path|Select-String|Write-Host|Start-Sleep|cd)\b/)) return 'command';
    if (stream.match(/^[A-Za-z_][\w-]*(?=\s*\()/)) return 'function';
    if (stream.match(/^[-]{1,2}[\w-]+/)) return 'attribute';
    if (stream.match(/^#.*|^\/\/.*|^<!--.*?-->/)) return 'comment';
    if (stream.match(/^`{3}.*|^```.*|^~~~.*/)) return 'processingInstruction';
    if (stream.match(/^"(?:[^"\\]|\\.)*"|^'(?:[^'\\]|\\.)*'/)) return 'string';
    if (stream.match(/^\b\d+(?:\.\d+)?\b/)) return 'number';
    if (stream.match(/^[{}[\]().,:;]/)) return 'punctuation';
    if (stream.match(/^[=+*/%<>!|&^-]+/)) return 'operator';
    stream.next();
    return null;
  }
});

const xoduzSyntax = HighlightStyle.define([
  { tag: tags.keyword, color: '#7dd3fc', fontWeight: '800' },
  { tag: [tags.name, tags.deleted, tags.character, tags.propertyName, tags.macroName], color: '#dbeafe' },
  { tag: [tags.function(tags.variableName), tags.labelName], color: '#22d3ee', fontWeight: '800' },
  { tag: [tags.color, tags.constant(tags.name), tags.standard(tags.name)], color: '#a7f3d0' },
  { tag: [tags.definition(tags.name), tags.separator], color: '#f8fafc' },
  { tag: [tags.typeName, tags.className, tags.number, tags.changed, tags.annotation, tags.modifier, tags.self, tags.namespace], color: '#facc15' },
  { tag: [tags.operator, tags.operatorKeyword, tags.url, tags.escape, tags.regexp, tags.link], color: '#f0abfc' },
  { tag: [tags.meta, tags.comment], color: '#7f8ea3', fontStyle: 'italic' },
  { tag: tags.strong, fontWeight: '800' },
  { tag: tags.emphasis, fontStyle: 'italic' },
  { tag: tags.strikethrough, textDecoration: 'line-through' },
  { tag: tags.link, color: '#67e8f9', textDecoration: 'underline' },
  { tag: tags.heading, fontWeight: '900', color: '#ffffff' },
  { tag: [tags.atom, tags.bool, tags.special(tags.variableName)], color: '#c084fc' },
  { tag: [tags.processingInstruction, tags.string, tags.inserted], color: '#86efac' },
  { tag: tags.invalid, color: '#fecdd3', backgroundColor: 'rgba(244, 63, 94, 0.22)' }
]);

const xoduzCommandHighlight = HighlightStyle.define([
  { tag: tags.keyword, color: '#38bdf8', fontWeight: '900' },
  { tag: tags.processingInstruction, color: '#facc15', fontWeight: '900' },
  { tag: tags.heading, color: '#ffffff', fontWeight: '900' },
  { tag: tags.attributeName, color: '#f0abfc' },
  { tag: tags.function(tags.variableName), color: '#22d3ee', fontWeight: '900' },
  { tag: tags.string, color: '#86efac' },
  { tag: tags.number, color: '#facc15' },
  { tag: tags.comment, color: '#7f8ea3', fontStyle: 'italic' },
  { tag: tags.operator, color: '#f0abfc' },
  { tag: tags.punctuation, color: '#94a3b8' }
]);

const xoduzEditorTheme = EditorView.theme({
  '&': {
    height: '100%',
    color: '#dbeafe',
    backgroundColor: '#060a12'
  },
  '.cm-scroller': {
    fontFamily: 'Cascadia Code, Fira Code, Consolas, monospace',
    fontSize: '13px',
    lineHeight: '1.58'
  },
  '.cm-content': {
    caretColor: '#22d3ee',
    padding: '12px 0'
  },
  '.cm-line': {
    padding: '0 14px',
    borderLeft: '3px solid transparent'
  },
  '.cm-line:nth-child(odd)': {
    backgroundColor: 'rgba(15, 23, 42, 0.68)'
  },
  '.cm-line:nth-child(even)': {
    backgroundColor: 'rgba(30, 41, 59, 0.42)'
  },
  '.cm-line:hover': {
    backgroundColor: 'rgba(14, 165, 233, 0.14)'
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(34, 211, 238, 0.18)',
    boxShadow: 'inset 4px 0 0 #22d3ee',
    borderLeftColor: '#22d3ee'
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'rgba(34, 211, 238, 0.18)',
    color: '#e0f2fe'
  },
  '.cm-gutters': {
    backgroundColor: '#08111f',
    color: '#64748b',
    borderRight: '1px solid rgba(34, 211, 238, 0.22)'
  },
  '.cm-lineNumbers .cm-gutterElement': {
    minWidth: '42px',
    padding: '0 12px 0 8px'
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: 'rgba(56, 189, 248, 0.28)'
  },
  '&.cm-focused': {
    outline: '1px solid rgba(34, 211, 238, 0.42)'
  },
  '.cm-cursor': {
    borderLeftColor: '#22d3ee'
  },
  '.cm-foldGutter .cm-gutterElement': {
    color: '#38bdf8'
  },
  '.cm-matchingBracket, .cm-nonmatchingBracket': {
    backgroundColor: 'rgba(250, 204, 21, 0.18)',
    outline: '1px solid rgba(250, 204, 21, 0.42)'
  }
});

export function CodeEditor({ path, value, onChange }: { path: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="codeMirrorShell">
      <CodeMirror
        value={value}
        height="100%"
        theme="dark"
        extensions={[languageFor(path), xoduzEditorTheme, syntaxHighlighting(xoduzSyntax), syntaxHighlighting(xoduzCommandHighlight)].flat()}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true, highlightActiveLineGutter: true, bracketMatching: true, autocompletion: true }}
        onChange={onChange}
      />
    </div>
  );
}
