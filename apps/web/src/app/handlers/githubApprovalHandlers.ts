import { applySelfBuildPatch, applyUpdate, connectGitHubRemote, createGitHubRepo, loadGitHubOpsAuthStatus, loadGitHubOpsStatus, previewGitHubPull, previewGitHubPush, runGitHubOperation } from '../../services/apiClient';
import type { PatchProposal } from '../../types/contracts';
import type { ChatCard, ChatMessage, InfoReceipt } from '../AssistantComponents';
import { errorCard } from '../cardHelpers';
import { isGitHubCreateRepoRequest, parseGitHubCreateRepo } from '../intentRouting';

type Setter<T> = (value: T | ((current: T) => T)) => void;

export interface GitHubApprovalHandlerDeps {
  githubAuth: Record<string, unknown>;
  githubOps: Record<string, unknown>;
  selectedPath: string;
  code: string;
  appendMessage: (message: ChatMessage) => void;
  updateCard: (cardId: string, patch: Partial<ChatCard>) => void;
  nowId: () => string;
  setGithubAuth: Setter<Record<string, unknown>>;
  setGithubOps: Setter<Record<string, unknown>>;
  setGithubOpsResult: Setter<string>;
  setLatestReceipt: Setter<InfoReceipt>;
  setLatestResult: Setter<string>;
  setProposal: Setter<PatchProposal | null>;
  setApprovalOpen: Setter<boolean>;
}

export function createGitHubApprovalHandlers(deps: GitHubApprovalHandlerDeps) {
  const {
    githubAuth,
    githubOps,
    selectedPath,
    code,
    appendMessage,
    updateCard,
    nowId,
    setGithubAuth,
    setGithubOps,
    setGithubOpsResult,
    setLatestReceipt,
    setLatestResult,
    setProposal,
    setApprovalOpen
  } = deps;

  async function createGitHubCards(text: string) {
    const lower = text.toLowerCase();
    try {
      if (isGitHubCreateRepoRequest(lower)) {
        const repo = parseGitHubCreateRepo(text, String(githubAuth.owner || '').trim());
        appendMessage({ id: nowId(), role: 'assistant', text: 'GitHub repo creation requires approval before any write.', cards: [githubCreateRepoApprovalCard(repo)] });
        return;
      }
      if (lower.includes('status') || lower.includes('check github')) {
        await refreshGitHubOps();
        appendMessage({ id: nowId(), role: 'assistant', text: 'GitHub status loaded without mutation.', cards: [{ id: nowId(), type: 'receipt', title: 'GitHub Ops status', status: 'ready', summary: 'Local git and GitHub auth status loaded.', payload: { auth: githubAuth, status: githubOps }, collapsed: false }] });
        return;
      }
      if (lower.includes('prepare to push') || lower.includes('push this repo') || lower.includes('push')) {
        const response = await previewGitHubPush();
        appendMessage({ id: nowId(), role: 'assistant', text: 'Push preview loaded. No push occurred.', cards: [{ id: nowId(), type: 'receipt', title: 'GitHub push preview', status: response.status, summary: response.message, payload: response.data, collapsed: false }, githubApprovalCard('push', 'Push this repo', response.data)] });
        return;
      }
      if (lower.includes('pull latest')) {
        const response = await previewGitHubPull();
        appendMessage({ id: nowId(), role: 'assistant', text: 'Pull preview loaded. No pull occurred.', cards: [{ id: nowId(), type: 'receipt', title: 'GitHub pull preview', status: response.status, summary: response.message, payload: response.data, collapsed: false }, githubApprovalCard('pull', 'Pull latest', response.data)] });
        return;
      }
      const operation = lower.includes('initialize') ? 'init' : lower.includes('connect') ? 'connect-remote' : 'push';
      appendMessage({ id: nowId(), role: 'assistant', text: 'GitHub operation requires approval before any write.', cards: [githubApprovalCard(operation, `GitHub ${operation}`, {})] });
    } catch {
      appendMessage({ id: nowId(), role: 'assistant', text: 'GitHub operation could not be prepared.', cards: [errorCard('GitHub Ops unavailable', 'No GitHub write occurred.')] });
    }
  }

  function githubCreateRepoApprovalCard(repo: { repo_name: string; owner: string; visibility: string }): ChatCard {
    return githubApprovalCard('create-repo', 'GitHub create-repo', {
      repo_name: repo.repo_name,
      owner: repo.owner,
      visibility: repo.visibility,
      approval_required: true,
      github_write_ran: false,
      local_repo_mutation: false,
      code_push: false,
      approved: false
    });
  }

  function githubApprovalCard(operation: string, title: string, preview: Record<string, unknown>): ChatCard {
    return {
      id: nowId(),
      type: 'approval',
      title,
      status: 'approval_required',
      summary: `${title} requires explicit approval. No GitHub write has run.`,
      payload: {
        provider: 'github_ops',
        operation,
        apply_safe: true,
        validation_status: 'passed',
        changed_file_paths: preview.changed_files || [],
        preview,
        ...preview
      },
      collapsed: false
    };
  }

  async function refreshGitHubOps() {
    const [auth, status] = await Promise.all([loadGitHubOpsAuthStatus(), loadGitHubOpsStatus()]);
    setGithubAuth(auth.data || {});
    setGithubOps(status.data || {});
    setGithubOpsResult(status.message);
  }

  async function previewGitHubOp(kind: 'pull' | 'push') {
    const response = kind === 'pull' ? await previewGitHubPull() : await previewGitHubPush();
    setGithubOpsResult(response.message);
    setGithubOps({ ...githubOps, [`${kind}_preview`]: response.data });
  }

  async function requestApply(card?: ChatCard) {
    const payload = card?.payload || {};
    if (card?.type === 'approval' && payload.provider === 'github_ops' && payload.operation) {
      updateCard(card.id, { status: 'applying', summary: 'Running approved GitHub operation.', collapsed: false });
      try {
        const operation = String(payload.operation);
        const response = operation === 'create-repo'
          ? await createGitHubRepo(String(payload.repo_name || 'xv8-lab-repo'), true, String(payload.owner || ''), String(payload.visibility || 'private'))
          : operation === 'connect-remote'
            ? await connectGitHubRemote('https://github.com/otiseduncan/xv8-lab-repo.git', true)
            : await runGitHubOperation(operation as 'init' | 'pull' | 'push', true);
        updateCard(card.id, { status: response.status, summary: response.message, payload: { ...payload, apply_result: response.data } });
        setGithubOpsResult(response.message);
        setLatestReceipt(response.receipts?.[0] || null);
      } catch {
        updateCard(card.id, { status: 'blocked', summary: 'GitHub operation failed or was blocked before completion.', payload: { ...payload, apply_result: { reason: 'GitHub operation failed or was blocked.', changed_files: [] } } });
      }
      return;
    }
    if (card?.type === 'approval' && payload.apply_safe === true && payload.task_id && payload.patch_id && payload.approval_id && payload.patch_hash) {
      updateCard(card.id, { status: 'applying', summary: 'Applying through the locked self-build endpoint.', collapsed: false });
      try {
        const response = await applySelfBuildPatch(String(payload.task_id), String(payload.patch_id), String(payload.approval_id), String(payload.patch_hash));
        const result = response.data || {};
        updateCard(card.id, {
          status: response.status,
          summary: response.message || String(result.reason || 'Self-build apply completed.'),
          payload: { ...payload, apply_result: result }
        });
        setLatestResult(`Self-build apply: ${response.status}`);
        setLatestReceipt(response.receipts?.[0] || null);
      } catch {
        updateCard(card.id, { status: 'blocked', summary: 'Self-build apply request failed before any confirmed write.', payload: { ...payload, apply_result: { applied: false, validation_passed: false, changed_files: [], backup_paths: [], reason: 'Self-build apply request failed.' } } });
        setLatestResult('Self-build apply blocked');
      }
      return;
    }
    const response = await applyUpdate(selectedPath, code, false);
    setProposal(response.data);
    setApprovalOpen(true);
  }

  async function approveApply() {
    const response = await applyUpdate(selectedPath, code, true);
    setProposal(response.data);
    setApprovalOpen(false);
    setLatestReceipt(response.data.receipt);
    setLatestResult(response.data.mutated ? `Applied ${selectedPath}` : `Did not apply ${selectedPath}`);
    appendMessage({
      id: nowId(),
      role: 'assistant',
      text: response.data.mutated ? `Applied the approved change to ${selectedPath}.` : `The change to ${selectedPath} was not applied.`,
      cards: [{ id: nowId(), type: 'receipt', title: `Receipt: ${response.data.receipt.action}`, status: response.data.receipt.status, summary: response.data.receipt.summary, receipt: response.data.receipt }]
    });
  }

  return { createGitHubCards, githubApprovalCard, refreshGitHubOps, previewGitHubOp, requestApply, approveApply };
}
