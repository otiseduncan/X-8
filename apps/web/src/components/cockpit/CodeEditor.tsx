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
    color: '#e5f4ff',
    backgroundColor: '#05070d',
    fontSize: '0.84rem'
  },
  '.cm-content': {
    caretColor: '#67e8f9',
    fontFamily: '"Cascadia Code", "Fira Code", Consolas, "SFMono-Regular", monospace'
  },
  '.cm-cursor, .cm-dropCursor': {
    borderLeftColor: '#67e8f9'
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(34, 211, 238, 0.10)'
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'rgba(34, 211, 238, 0.14)',
    color: '#e0f2fe'
  },
  '.cm-gutters': {
    backgroundColor: '#030712',
    color: '#7891aa',
    borderRight: '1px solid rgba(34, 211, 238, 0.22)'
  },
  '.cm-line:nth-child(odd)': {
    backgroundColor: 'rgba(5, 7, 13, 0.76)'
  },
  '.cm-line:nth-child(even)': {
    backgroundColor: 'rgba(13, 20, 35, 0.76)'
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: 'rgba(34, 211, 238, 0.28)'
  },
  '&.cm-focused': {
    outline: '1px solid rgba(34, 211, 238, 0.55)'
  }
}, { dark: true });

const artifactHighlighting = syntaxHighlighting(HighlightStyle.define([
  { tag: tags.comment, color: '#64748b', fontStyle: 'italic' },
  { tag: [tags.tagName, tags.className, tags.definition(tags.className)], color: '#22d3ee', fontWeight: '700' },
  { tag: tags.angleBracket, color: '#7dd3fc' },
  { tag: [tags.attributeName, tags.propertyName, tags.definition(tags.propertyName)], color: '#67e8f9' },
  { tag: [tags.attributeValue, tags.string, tags.special(tags.string)], color: '#dbeafe' },
  { tag: [tags.keyword, tags.operatorKeyword, tags.controlKeyword], color: '#7dd3fc', fontWeight: '700' },
  { tag: [tags.variableName, tags.definition(tags.variableName)], color: '#e5f4ff' },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: '#67e8f9' },
  { tag: [tags.number, tags.integer, tags.float, tags.unit], color: '#bfdbfe' },
  { tag: tags.color, color: '#67e8f9', fontWeight: '700' },
  { tag: [tags.atom, tags.bool, tags.null], color: '#dbeafe' },
  { tag: [tags.punctuation, tags.separator], color: '#94a3b8' },
  { tag: [tags.bracket, tags.squareBracket, tags.paren], color: '#7dd3fc' },
  { tag: tags.invalid, color: '#fecdd3', backgroundColor: 'rgba(244, 63, 94, 0.24)' }
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
