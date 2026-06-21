import { loadIDEGitStatus, loadIDESummary, openIDEFile, proposeIDECommand, proposeIDERollback } from '../../services/apiClient';
import type { AvatarRuntimeState, ChatCard, ChatMessage, InfoReceipt } from '../AssistantComponents';
import { commandRows, fileSummaryRows, gitRows, changedFileRecommendations, rollbackRows, workspaceRows } from '../idePresentation';

type Setter<T> = (value: T | ((current: T) => T)) => void;

interface ChatIDEHandlersDeps {
  appendMessage: (message: ChatMessage) => void;
  muted: boolean;
  nowId: () => string;
  setCode: Setter<string>;
  setLatestReceipt: Setter<InfoReceipt>;
  setLatestResult: Setter<string>;
  setSelectedPath: Setter<string>;
  setStage: (value: AvatarRuntimeState) => void;
}

const WEB_TEST_COMMAND = 'docker compose -f compose.yaml run --rm --build web-tests';
const API_TEST_COMMAND = 'docker compose -f compose.yaml run --rm --build api-tests';
const ARCHITECTURE_COMMAND = 'docker compose -f compose.yaml run --rm --build architecture-guard';

export function createChatIDEHandlers(deps: ChatIDEHandlersDeps) {
  const { appendMessage, muted, nowId, setCode, setLatestReceipt, setLatestResult, setSelectedPath, setStage } = deps;

  async function createIDECard(text: string) {
    const lower = text.toLowerCase();
    try {
      if (lower.includes('rollback')) return createRollbackCard();
      if (lower.includes('prepare a commit') || lower.includes('commit proposal')) return createCommitCard();
      if (lower.includes('web test')) return createCommandCard(WEB_TEST_COMMAND, 'Web test command prepared. No command has run.');
      if (lower.includes('api test')) return createCommandCard(API_TEST_COMMAND, 'API test command prepared. No command has run.');
      if (lower.includes('architecture guard')) return createCommandCard(ARCHITECTURE_COMMAND, 'Architecture guard command prepared. No command has run.');
      if (lower.includes('diff')) return createDiffCard();
      if (lower.includes('show code') && lower.includes('app.tsx')) return openIDEPath('apps/web/src/app/App.tsx', true);
      if (lower.includes('open app.tsx')) return openIDEPath('apps/web/src/app/App.tsx', false);
      if (lower.includes('branch') || lower.includes('git status') || lower.includes('changed') || lower.includes('dirty') || lower.includes('committed')) return createGitStatusCard(lower);
      return createWorkspaceCard();
    } catch {
      setStage('error');
      appendMessage({ id: nowId(), role: 'assistant', text: 'Chat IDE request could not complete.', cards: [{ id: nowId(), type: 'error', title: 'Chat IDE unavailable', status: 'blocked', summary: 'No workspace mutation was attempted.' }] });
    }
  }

  async function createWorkspaceCard() {
    const response = await loadIDESummary('README.md');
    const files = Array.isArray(response.data.files) ? response.data.files : [];
    appendIDEReceipt('Workspace loaded.', 'Chat IDE workspace tree', response.status, response.message, {
      rows: workspaceRows(files),
      recommendation: 'Open a file or search the repo.',
      safety: 'Ignored, generated, and vendor folders are hidden by default.',
      raw: response.data
    });
  }

  async function openIDEPath(path: string, showCode: boolean) {
    const response = await openIDEFile(path);
    setSelectedPath(path);
    setCode(response.data.content);
    setLatestReceipt(response.receipts?.[0] as InfoReceipt || null);
    setLatestResult(showCode ? `Showing source for ${path}` : `Opened read-only editor view for ${path}`);
    const card: ChatCard = showCode
      ? { id: nowId(), type: 'file', title: path, status: response.status, summary: `${response.data.line_count} lines shown read-only with line numbers.`, payload: { path, content: response.data.content } }
      : {
          id: nowId(),
          type: 'receipt',
          title: 'Chat IDE read-only file',
          status: response.status,
          summary: 'Read-only editor view loaded. Source is hidden until you explicitly ask to show code.',
          payload: {
            rows: fileSummaryRows(response.data, path),
            recommendation: 'Use "show code for App.tsx" when you want the source body.',
            safety: 'Read-only open. No file mutation happened.',
            raw: { path: response.data.path, line_count: response.data.line_count }
          }
        };
    appendMessage({ id: nowId(), role: 'assistant', text: showCode ? `Showing source for ${path}.` : `Opened read-only editor view for ${path}.`, cards: [card] });
    setStage(muted ? 'muted' : 'idle');
  }

  async function createGitStatusCard(prompt: string) {
    const response = await loadIDEGitStatus();
    const rows = [...gitRows(response.data), ...changedFileRecommendations(response.data)];
    appendIDEReceipt(gitStatusText(response.data, prompt), 'Chat IDE Git status', response.status, response.message, {
      rows,
      recommendation: String(response.data.overall_recommendation || 'Review changed files before staging.'),
      safety: 'Read-only Git inspection. No staging, commit, push, or merge occurred.',
      raw: response.data
    });
  }

  async function createDiffCard() {
    const response = await proposeIDECommand('git diff --stat');
    appendIDEReceipt('Diff is read-only. No mutation has happened.', 'Chat IDE diff review', response.status, response.message, {
      rows: commandRows(response.data),
      recommendation: 'Review changed file names first. Ask for terminal output only if you need the raw diff body.',
      safety: 'Category: read-only. Approval required: false. Mutation: false.',
      raw: response.data
    });
  }

  async function createCommandCard(command: string, text: string) {
    const response = await proposeIDECommand(command);
    appendIDEReceipt(text, 'Chat IDE command proposal', response.status, response.message, {
      rows: commandRows(response.data),
      recommendation: 'Approve only after confirming this is the intended local validation command.',
      safety: 'No command has run. Docker starts only after explicit approval.',
      raw: response.data
    });
  }

  async function createCommitCard() {
    const [git, proposal] = await Promise.all([loadIDEGitStatus(), proposeIDECommand('git commit -m "checkpoint"')]);
    const recommendations = changedFileRecommendations(git.data);
    appendIDEReceipt('Commit proposal prepared. No commit has run.', 'Chat IDE commit proposal', proposal.status, proposal.message, {
      rows: [
        { label: 'Suggested title', value: 'Complete Chat IDE presentation repair' },
        { label: 'Approval required', value: 'true' },
        { label: 'Tests first', value: 'architecture-guard, api-tests, web-tests, e2e-fast-tests' },
        ...recommendations
      ],
      recommendation: String(git.data.overall_recommendation || 'Commit only reviewed source changes after tests pass.'),
      safety: 'No staging or commit occurred.',
      raw: { git: git.data, proposal: proposal.data }
    });
  }

  async function createRollbackCard() {
    const response = await proposeIDERollback('discard_working_tree');
    appendIDEReceipt('Rollback proposal prepared. No rollback has run.', 'Chat IDE rollback proposal', response.status, response.message, {
      rows: rollbackRows(response.data),
      recommendation: 'Preview cleanup with git clean -fdn before any destructive cleanup.',
      safety: 'Rollback is mutating/destructive, so explicit approval is required.',
      raw: response.data
    });
  }

  function appendIDEReceipt(text: string, title: string, status: string, summary: string, payload: Record<string, unknown>) {
    setLatestResult(text);
    appendMessage({ id: nowId(), role: 'assistant', text, cards: [{ id: nowId(), type: 'receipt', title, status, summary, payload, collapsed: false }] });
    setStage(muted ? 'muted' : 'idle');
  }

  return { createIDECard };
}

export function gitStatusText(git: Record<string, unknown>, prompt: string) {
  const branch = String(git.branch || 'unknown');
  const dirty = Boolean(git.dirty);
  const changed = changedFiles(git);
  const counts = changedCounts(git);
  const guardPaths = architectureGuardPaths(git);
  const splitPaths = lineCountPolicyPaths(git);
  const commitCandidates = recommendationPaths(git, 'include in commit').filter((path) => !guardPaths.includes(path) && !splitPaths.includes(path));
  const excludes = recommendationPaths(git, 'do not commit');
  const risks = recommendationPaths(git, 'possible secret/risk');
  const excluded = [...excludes, ...risks];
  const branchPrefix = `You are on \`${branch}\`.`;

  if (prompt.includes('branch')) {
    return dirty
      ? `${branchPrefix} Working tree is dirty: ${dirtyCountText(counts)}.`
      : `${branchPrefix} Working tree is clean.`;
  }

  if (prompt.includes('what changed') || prompt.includes('changed')) {
    if (!dirty || !changed.length) return 'No working-tree changes are currently present.';
    return `Working-tree changes are present: ${changed.map(displayPath).join(', ')}.`;
  }

  if (prompt.includes('what should') || prompt.includes('committed')) {
    if (!dirty || !changed.length) return `${branchPrefix} Working tree is clean. Nothing needs to be committed.`;
    const includeText = commitCandidates.length
      ? `Include clean source changes only after tests pass: ${commitCandidates.map(displayPath).join(', ')}.`
      : 'No clean source changes are currently available yet.';
    const guardText = guardPaths.length ? ` Review first: ${guardPaths.map(displayPath).join(', ')} are blocked by architecture guard.` : '';
    const splitText = splitPaths.length ? ` Do not commit yet: ${splitPaths.map(displayPath).join(', ')} must be split before commit.` : '';
    const excludeText = excluded.length ? ` Exclude: ${excluded.map(displayPath).join(', ')}.` : '';
    return `${branchPrefix} Working tree is dirty: ${dirtyCountText(counts)}. ${includeText}${guardText}${splitText}${excludeText} Run validation gates before committing.`;
  }

  if (!dirty || !changed.length) return `${branchPrefix} Working tree is clean. No pending changes.`;
  const candidateText = commitCandidates.length ? ` Commit candidates: ${commitCandidates.map(displayPath).join(', ')}.` : '';
  const excludeText = excluded.length ? ` Exclude: ${excluded.map(displayPath).join(', ')}.` : '';
  return `${branchPrefix} Working tree is dirty: ${dirtyCountText(counts)}.${candidateText}${excludeText}`;
}

function architectureGuardPaths(git: Record<string, unknown>) {
  const items = Array.isArray(git.file_recommendations) ? git.file_recommendations as Array<Record<string, unknown>> : [];
  return items
    .filter((item) => /architecture\s*-?guard/i.test(String(item.reason || '')))
    .map((item) => normalizePath(String(item.path || '').trim(), git))
    .filter(Boolean);
}

function lineCountPolicyPaths(git: Record<string, unknown>) {
  const items = Array.isArray(git.file_recommendations) ? git.file_recommendations as Array<Record<string, unknown>> : [];
  return items
    .filter((item) => /line\s*-?count|line count policy|must split before commit/i.test(String(item.reason || '')))
    .map((item) => normalizePath(String(item.path || '').trim(), git))
    .filter(Boolean);
}

function changedFiles(git: Record<string, unknown>) {
  const files = Array.isArray(git.changed_files) ? git.changed_files : [];
  return files.flatMap((item) => {
    const raw = String(item).trim();
    if (!raw) return [];
    const normalized = normalizePath(raw, git);
    return normalized ? [normalized] : [];
  });
}

function changedCounts(git: Record<string, unknown>) {
  const files = Array.isArray(git.changed_files) ? git.changed_files : [];
  return files.reduce((counts, item) => {
    const raw = String(item).trim();
    const status = raw.slice(0, 2);
    if (status.includes('?')) counts.untracked += 1;
    else if (status.includes('D')) counts.deleted += 1;
    else if (status.includes('M')) counts.modified += 1;
    return counts;
  }, { modified: 0, untracked: 0, deleted: 0 });
}

function dirtyCountText(counts: { modified: number; untracked: number; deleted: number }) {
  const parts = [
    counts.modified ? `${counts.modified} modified` : '',
    counts.untracked ? `${counts.untracked} untracked` : '',
    counts.deleted ? `${counts.deleted} deleted` : ''
  ].filter(Boolean);
  return parts.join(', ') || 'changes present';
}

function recommendationPaths(git: Record<string, unknown>, recommendation: string) {
  const items = Array.isArray(git.file_recommendations) ? git.file_recommendations as Array<Record<string, unknown>> : [];
  return items
    .filter((item) => String(item.recommendation || '') === recommendation)
    .map((item) => normalizePath(String(item.path || '').trim(), git))
    .filter(Boolean);
}

function normalizePath(path: string, git: Record<string, unknown>) {
  const cleaned = displayPath(path);
  if (!cleaned.endsWith('/.') && !cleaned.endsWith('/')) return cleaned;
  const dir = cleaned.replace(/\/(?:\.)?$/, '');
  const candidates = knownFilesUnder(dir, git);
  if (candidates.length === 1) return candidates[0];
  return cleaned;
}

function knownFilesUnder(dir: string, git: Record<string, unknown>) {
  const prefix = `${dir}/`;
  const candidates = new Set<string>();
  const files = Array.isArray(git.changed_files) ? git.changed_files : [];
  files.forEach((item) => {
    const cleaned = displayPath(String(item));
    if (cleaned.startsWith(prefix) && !cleaned.endsWith('/.') && !cleaned.endsWith('/')) {
      candidates.add(cleaned);
    }
  });
  const recommendations = Array.isArray(git.file_recommendations) ? git.file_recommendations as Array<Record<string, unknown>> : [];
  recommendations.forEach((item) => {
    const candidate = String(item.path || '').trim();
    if (candidate.startsWith(prefix) && !candidate.endsWith('/.') && !candidate.endsWith('/')) {
      candidates.add(candidate);
    }
  });
  return Array.from(candidates);
}

function displayPath(path: string) {
  return path.replace(/^[?MADRCU ]{1,2}\s+/, '');
}
