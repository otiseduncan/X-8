import CodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { EditorView } from '@codemirror/view';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags } from '@lezer/highlight';

function languageFor(path: string) {
  if (path.endsWith('.py')) return python();
  if (path.endsWith('.json')) return json();
  if (path.endsWith('.html')) return html();
  if (path.endsWith('.css')) return css();
  if (path.endsWith('.ts') || path.endsWith('.tsx') || path.endsWith('.js') || path.endsWith('.jsx')) return javascript({ jsx: true, typescript: path.endsWith('.ts') || path.endsWith('.tsx') });
  return [];
}

const xoduzSyntax = HighlightStyle.define([
  { tag: tags.keyword, color: '#7dd3fc', fontWeight: '700' },
  { tag: [tags.name, tags.deleted, tags.character, tags.propertyName, tags.macroName], color: '#e0f2fe' },
  { tag: [tags.function(tags.variableName), tags.labelName], color: '#22d3ee' },
  { tag: [tags.color, tags.constant(tags.name), tags.standard(tags.name)], color: '#a7f3d0' },
  { tag: [tags.definition(tags.name), tags.separator], color: '#f8fafc' },
  { tag: [tags.typeName, tags.className, tags.number, tags.changed, tags.annotation, tags.modifier, tags.self, tags.namespace], color: '#facc15' },
  { tag: [tags.operator, tags.operatorKeyword, tags.url, tags.escape, tags.regexp, tags.link], color: '#f0abfc' },
  { tag: [tags.meta, tags.comment], color: '#7f8ea3', fontStyle: 'italic' },
  { tag: tags.strong, fontWeight: '700' },
  { tag: tags.emphasis, fontStyle: 'italic' },
  { tag: tags.strikethrough, textDecoration: 'line-through' },
  { tag: tags.link, color: '#67e8f9', textDecoration: 'underline' },
  { tag: tags.heading, fontWeight: '700', color: '#ffffff' },
  { tag: [tags.atom, tags.bool, tags.special(tags.variableName)], color: '#c084fc' },
  { tag: [tags.processingInstruction, tags.string, tags.inserted], color: '#86efac' },
  { tag: tags.invalid, color: '#fecdd3', backgroundColor: 'rgba(244, 63, 94, 0.22)' }
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
    padding: '0 12px'
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    boxShadow: 'inset 3px 0 0 #22d3ee'
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
        extensions={[languageFor(path), xoduzEditorTheme, syntaxHighlighting(xoduzSyntax)].flat()}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true, highlightActiveLineGutter: true, bracketMatching: true, autocompletion: true }}
        onChange={onChange}
      />
    </div>
  );
}
