import CodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { EditorView } from '@codemirror/view';
import { tags } from '@lezer/highlight';

function languageFor(path: string) {
  if (path.endsWith('.py')) return python();
  if (path.endsWith('.json')) return json();
  if (path.endsWith('.html')) return html();
  if (path.endsWith('.css')) return css();
  if (path.endsWith('.ts') || path.endsWith('.tsx') || path.endsWith('.js') || path.endsWith('.jsx')) return javascript({ jsx: true, typescript: path.endsWith('.ts') || path.endsWith('.tsx') });
  return [];
}

const artifactEditorTheme = EditorView.theme({
  '&': {
    color: '#e6edf7',
    backgroundColor: '#05070d',
    fontSize: '0.84rem'
  },
  '.cm-scroller': {
    backgroundColor: '#05070d'
  },
  '.cm-content': {
    caretColor: '#67e8f9',
    fontFamily: '"Cascadia Code", "Fira Code", Consolas, "SFMono-Regular", monospace',
    backgroundColor: '#05070d'
  },
  '.cm-cursor, .cm-dropCursor': {
    borderLeftColor: '#67e8f9'
  },
  '.cm-activeLine': {
    backgroundColor: '#142033'
  },
  '.cm-activeLineGutter': {
    backgroundColor: '#101a2a',
    color: '#e0f2fe'
  },
  '.cm-gutters': {
    backgroundColor: '#030712',
    color: '#7891aa',
    borderRight: '1px solid #123244'
  },
  '.cm-line:nth-child(odd)': {
    backgroundColor: '#05070d'
  },
  '.cm-line:nth-child(even)': {
    backgroundColor: '#0d1423'
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: '#164e63'
  },
  '&.cm-focused': {
    outline: '1px solid #22d3ee'
  }
}, { dark: true });

const artifactHighlighting = syntaxHighlighting(HighlightStyle.define([
  { tag: tags.comment, color: '#64748b', fontStyle: 'italic' },
  { tag: [tags.tagName, tags.className, tags.definition(tags.className)], color: '#22d3ee', fontWeight: '700' },
  { tag: tags.angleBracket, color: '#38bdf8' },
  { tag: [tags.attributeName, tags.propertyName, tags.definition(tags.propertyName)], color: '#60a5fa' },
  { tag: [tags.attributeValue, tags.string, tags.special(tags.string)], color: '#f8fafc' },
  { tag: [tags.keyword, tags.operatorKeyword, tags.controlKeyword], color: '#a78bfa', fontWeight: '700' },
  { tag: [tags.variableName, tags.definition(tags.variableName)], color: '#e6edf7' },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: '#38bdf8' },
  { tag: [tags.number, tags.integer, tags.float, tags.unit], color: '#fbbf24' },
  { tag: tags.color, color: '#fb7185', fontWeight: '700' },
  { tag: [tags.atom, tags.bool, tags.null], color: '#c084fc' },
  { tag: [tags.punctuation, tags.separator], color: '#94a3b8' },
  { tag: [tags.bracket, tags.squareBracket, tags.paren], color: '#93c5fd' },
  { tag: [tags.operator, tags.derefOperator, tags.compareOperator, tags.logicOperator, tags.arithmeticOperator], color: '#f472b6' },
  { tag: tags.invalid, color: '#fecdd3', backgroundColor: '#7f1d1d' }
]));

export function CodeEditor({ path, value, onChange }: { path: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="codeMirrorShell">
      <CodeMirror
        value={value}
        height="318px"
        extensions={[languageFor(path), artifactEditorTheme, artifactHighlighting].flat()}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true }}
        onChange={onChange}
      />
    </div>
  );
}
