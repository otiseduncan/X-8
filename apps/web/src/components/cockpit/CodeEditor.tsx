import CodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { RangeSetBuilder } from '@codemirror/state';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { Decoration, EditorView, ViewPlugin } from '@codemirror/view';
import { tags } from '@lezer/highlight';
import { useEffect, useMemo, useRef } from 'react';

type DiffHighlightEntry = { line_number: number; kind: string };

interface CodeEditorProps {
  path: string;
  value: string;
  onChange: (value: string) => void;
  highlightLineStart?: number;
  highlightLineEnd?: number;
  diffEntries?: DiffHighlightEntry[];
}

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
  '.cm-line.artifactLineLocate': {
    backgroundColor: 'rgba(250, 204, 21, 0.22)'
  },
  '.cm-line.artifactLineAdded, .cm-line.artifactLineModifiedNew': {
    backgroundColor: 'rgba(16, 185, 129, 0.22)'
  },
  '.cm-line.artifactLineDeleted, .cm-line.artifactLineModifiedOld': {
    backgroundColor: 'rgba(244, 63, 94, 0.18)'
  },
  '.cm-line.artifactLineReplaced': {
    backgroundImage: 'linear-gradient(90deg, rgba(244, 63, 94, 0.18) 0%, rgba(244, 63, 94, 0.18) 46%, rgba(16, 185, 129, 0.22) 54%, rgba(16, 185, 129, 0.22) 100%)'
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
  { tag: [tags.keyword, tags.operatorKeyword, tags.controlKeyword], color: '#22d3ee', fontWeight: '700' },
  { tag: [tags.variableName, tags.definition(tags.variableName)], color: '#e6edf7' },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: '#38bdf8' },
  { tag: [tags.number, tags.integer, tags.float, tags.unit], color: '#fbbf24' },
  { tag: tags.color, color: '#fb7185', fontWeight: '700' },
  { tag: [tags.atom, tags.bool, tags.null], color: '#fbbf24' },
  { tag: [tags.punctuation, tags.separator], color: '#94a3b8' },
  { tag: [tags.bracket, tags.squareBracket, tags.paren], color: '#93c5fd' },
  { tag: [tags.operator, tags.derefOperator, tags.compareOperator, tags.logicOperator, tags.arithmeticOperator], color: '#f472b6' },
  { tag: tags.invalid, color: '#fecdd3', backgroundColor: '#7f1d1d' }
]));

function clampLineNumber(doc: EditorView['state']['doc'], lineNumber: number) {
  return Math.max(1, Math.min(lineNumber, doc.lines));
}

function classNameForDiffKinds(kinds: Set<string>) {
  const hasNew = kinds.has('added') || kinds.has('modified_new');
  const hasOld = kinds.has('deleted') || kinds.has('modified_old');
  if (hasNew && hasOld) return 'artifactLineReplaced';
  if (kinds.has('modified_new')) return 'artifactLineModifiedNew';
  if (kinds.has('modified_old')) return 'artifactLineModifiedOld';
  if (kinds.has('added')) return 'artifactLineAdded';
  if (kinds.has('deleted')) return 'artifactLineDeleted';
  return '';
}

function lineHighlightExtension(args: { highlightLineStart?: number; highlightLineEnd?: number; diffEntries?: DiffHighlightEntry[] }) {
  const { diffEntries = [], highlightLineEnd, highlightLineStart } = args;
  return ViewPlugin.fromClass(class {
    decorations;

    constructor(view: EditorView) {
      this.decorations = this.buildDecorations(view);
    }

    update(update: { view: EditorView; docChanged: boolean; viewportChanged: boolean }) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = this.buildDecorations(update.view);
      }
    }

    buildDecorations(view: EditorView) {
      const builder = new RangeSetBuilder<Decoration>();
      const diffMap = new Map<number, Set<string>>();
      diffEntries.forEach((entry) => {
        const lineNumber = clampLineNumber(view.state.doc, Number(entry.line_number || 1));
        const kinds = diffMap.get(lineNumber) || new Set<string>();
        kinds.add(String(entry.kind || ''));
        diffMap.set(lineNumber, kinds);
      });

      if (diffMap.size > 0) {
        diffMap.forEach((kinds, lineNumber) => {
          const className = classNameForDiffKinds(kinds);
          if (!className) return;
          const line = view.state.doc.line(lineNumber);
          builder.add(line.from, line.from, Decoration.line({ attributes: { class: className, 'data-artifact-line-kind': className } }));
        });
        return builder.finish();
      }

      if (highlightLineStart && highlightLineStart > 0) {
        const start = clampLineNumber(view.state.doc, highlightLineStart);
        const end = clampLineNumber(view.state.doc, highlightLineEnd && highlightLineEnd >= start ? highlightLineEnd : start);
        for (let lineNumber = start; lineNumber <= end; lineNumber += 1) {
          const line = view.state.doc.line(lineNumber);
          builder.add(line.from, line.from, Decoration.line({ attributes: { class: 'artifactLineLocate', 'data-artifact-line-kind': 'artifactLineLocate' } }));
        }
      }
      return builder.finish();
    }
  }, {
    decorations: (value) => value.decorations
  });
}

export function CodeEditor({ path, value, onChange, highlightLineEnd, highlightLineStart, diffEntries = [] }: CodeEditorProps) {
  const editorRef = useRef<EditorView | null>(null);
  const decorationExtension = useMemo(() => lineHighlightExtension({ highlightLineStart, highlightLineEnd, diffEntries }), [diffEntries, highlightLineEnd, highlightLineStart]);
  const highlightKey = useMemo(() => `${path}:${highlightLineStart || 0}:${highlightLineEnd || 0}:${diffEntries.map((entry) => `${entry.line_number}-${entry.kind}`).join('|')}`, [diffEntries, highlightLineEnd, highlightLineStart, path]);
  const targetLine = diffEntries.find((entry) => entry.kind === 'added' || entry.kind === 'modified_new')?.line_number
    || diffEntries[0]?.line_number
    || highlightLineStart
    || 0;

  useEffect(() => {
    const view = editorRef.current;
    if (!view || !targetLine) return;
    const safeLine = clampLineNumber(view.state.doc, targetLine);
    const line = view.state.doc.line(safeLine);
    view.dispatch({ effects: EditorView.scrollIntoView(line.from, { y: 'center' }) });
  }, [highlightKey, targetLine]);

  return (
    <div className="codeMirrorShell">
      <CodeMirror
        key={highlightKey}
        value={value}
        height="318px"
        extensions={[languageFor(path), artifactEditorTheme, artifactHighlighting, decorationExtension].flat()}
        basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true }}
        onChange={onChange}
        onCreateEditor={(view) => {
          editorRef.current = view;
        }}
      />
    </div>
  );
}
