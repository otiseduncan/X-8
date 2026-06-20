import type { FileEntry, FileRead } from '../types/contracts';

export type PresentationRow = { label: string; value: string };

export function HumanFirstDetails({ rows, recommendation, safety, raw }: { rows: PresentationRow[]; recommendation?: string; safety?: string; raw?: unknown }) {
  return (
    <div className="stack">
      <div className="list dense">
        {rows.map((row) => <div className="row split" key={`${row.label}-${row.value}`}><strong>{row.label}</strong><span>{row.value}</span></div>)}
        {recommendation && <div className="row"><strong>Recommendation</strong><span>{recommendation}</span></div>}
        {safety && <div className="row"><strong>Safety</strong><span>{safety}</span></div>}
      </div>
      {raw !== undefined && (
        <details>
          <summary>Details</summary>
          <pre className="codeBlock smallBlock">{JSON.stringify(raw, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}

export function IDECodeViewer({ path, content }: { path: string; content: string }) {
  const lines = content.split('\n');
  return (
    <pre className="codeBlock ideCodeBlock" aria-label={`Source code for ${path}`}>
      {lines.map((line, index) => (
        <span className="codeLine" key={`${index}-${line}`}>
          <span className="codeLineNumber">{String(index + 1).padStart(3, ' ')}</span>
          <SyntaxLine line={line} />
          {index < lines.length - 1 ? '\n' : ''}
        </span>
      ))}
    </pre>
  );
}

function SyntaxLine({ line }: { line: string }) {
  const parts = tokenize(line);
  return <>{parts.map((part, index) => <span key={`${index}-${part.text}`} style={{ color: part.color }}>{part.text}</span>)}</>;
}

function tokenize(line: string) {
  const tokens: Array<{ text: string; color: string }> = [];
  const pattern = /(\/\/.*|\/\*.*\*\/|(["'`])(?:\\.|(?!\2).)*\2|\b(?:import|export|from|const|let|var|function|return|if|else|try|catch|async|await|type|interface|class|extends|new)\b|\b[A-Z][A-Za-z0-9_]*\b|<\/?[A-Za-z][A-Za-z0-9.]*)/g;
  let lastIndex = 0;
  for (const match of line.matchAll(pattern)) {
    if (match.index === undefined) continue;
    if (match.index > lastIndex) tokens.push({ text: line.slice(lastIndex, match.index), color: '#dbeafe' });
    const text = match[0];
    tokens.push({ text, color: tokenColor(text) });
    lastIndex = match.index + text.length;
  }
  if (lastIndex < line.length) tokens.push({ text: line.slice(lastIndex), color: '#dbeafe' });
  if (!tokens.length) tokens.push({ text: line, color: '#dbeafe' });
  return tokens;
}

function tokenColor(token: string) {
  if (token.startsWith('//') || token.startsWith('/*')) return '#86efac';
  if (/^["'`]/.test(token)) return '#fbbf24';
  if (token.startsWith('<')) return '#67e8f9';
  if (/^[A-Z]/.test(token)) return '#c4b5fd';
  return '#60a5fa';
}

export function fileSummaryRows(file: FileRead | null, path: string): PresentationRow[] {
  const resolvedPath = file?.path || path;
  return [
    { label: 'Path', value: resolvedPath },
    { label: 'Type', value: languageForPath(resolvedPath) },
    { label: 'Lines', value: String(file?.line_count || 0) },
    { label: 'Mode', value: 'Read-only' },
    { label: 'Actions', value: 'Show code, propose edit, show summary, copy path.' }
  ];
}

export function workspaceRows(files: FileEntry[], root = 'X8'): PresentationRow[] {
  const folders = Array.from(new Set(files.map((file) => file.path.split('/')[0]).filter(Boolean))).slice(0, 8);
  return [
    { label: 'Workspace', value: 'loaded' },
    { label: 'Root', value: root },
    { label: 'Top folders', value: folders.join(', ') || 'none' },
    { label: 'Files shown', value: String(files.length) },
    { label: 'Hidden', value: 'Ignored, generated, and vendor folders stay out of the default view.' }
  ];
}

export function gitRows(git: Record<string, unknown>): PresentationRow[] {
  return [
    { label: 'Branch', value: String(git.branch || 'unknown') },
    { label: 'Status', value: git.dirty ? 'dirty' : 'clean' },
    { label: 'Ahead / behind', value: `${String(git.ahead ?? 'unknown')} / ${String(git.behind ?? 'unknown')}` },
    { label: 'Changed files', value: changedFileSummary(git) }
  ];
}

export function changedFileRecommendations(git: Record<string, unknown>): PresentationRow[] {
  const recommendations = Array.isArray(git.file_recommendations) ? git.file_recommendations as Array<Record<string, unknown>> : [];
  if (!recommendations.length) return [{ label: 'Commit review', value: git.dirty ? 'Review changed files before staging.' : 'Nothing to commit.' }];
  return recommendations.map((item) => ({ label: String(item.path || 'unknown'), value: `${String(item.recommendation || 'review first')} - ${String(item.reason || 'Inspect before staging.')}` }));
}

export function commandRows(data: Record<string, unknown>): PresentationRow[] {
  return [
    { label: 'Command', value: String(data.command || 'none') },
    { label: 'Category', value: String(data.category || 'unknown') },
    { label: 'Approval required', value: String(data.approval_required ?? false) },
    { label: 'Mutation happened', value: data.status === 'passed' && data.category === 'write/mutation' ? 'true' : 'false' },
    { label: 'Reason', value: String(data.reason || data.blocked_reason || 'Prepared for review.') }
  ];
}

export function rollbackRows(data: Record<string, unknown>): PresentationRow[] {
  return [
    { label: 'Action', value: String(data.action || 'rollback') },
    { label: 'Command', value: String(data.command || 'none') },
    { label: 'Approval required', value: String(data.approval_required ?? true) },
    { label: 'Mutation happened', value: 'false' },
    { label: 'Reason', value: String(data.reason || 'Rollback proposal is waiting for approval.') },
    { label: 'Safe first step', value: 'Preview cleanup with git clean -fdn.' }
  ];
}

export function languageForPath(path: string) {
  if (path.endsWith('.tsx')) return 'TypeScript React';
  if (path.endsWith('.ts')) return 'TypeScript';
  if (path.endsWith('.py')) return 'Python';
  if (path.endsWith('.md')) return 'Markdown';
  if (path.endsWith('.json')) return 'JSON';
  return 'Text';
}

function changedFileSummary(git: Record<string, unknown>) {
  const files = Array.isArray(git.changed_files) ? git.changed_files : [];
  if (!files.length) return 'none';
  return `${files.length} changed`;
}
