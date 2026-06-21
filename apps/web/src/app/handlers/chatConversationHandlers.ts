import type React from 'react';
import { CHAT_TIMEOUT_MS, createArtifactPreview, proposeUpdate, readFile, requestImage, runSearch, runSelfBuildPrompt, scanX7Configs, sendChat, uploadAttachment } from '../../services/apiClient';
import type { AttachmentReference, PatchProposal } from '../../types/contracts';
import type { AvatarRuntimeState, ChatCard, ChatMessage, InfoReceipt } from '../AssistantComponents';
import { errorCard, mapKernelCard } from '../cardHelpers';
import { classifyRequest } from '../intentRouting';
import { createChatIDEHandlers } from './chatIDEHandlers';

type Setter<T> = (value: T | ((current: T) => T)) => void;

interface ChatConversationHandlersDeps {
  appendMessage: (message: ChatMessage) => void;
  updateCard: (cardId: string, patch: Partial<ChatCard>) => void;
  attachments: AttachmentReference[];
  createGitHubCards: (text: string) => Promise<void>;
  entry: string;
  finishAssistantResponseLifecycle: (text: string, cardCount: number) => Promise<void>;
  muted: boolean;
  nowId: () => string;
  recordResponseLifecycle: (source: string, hasText: boolean, hasCards: boolean) => void;
  requestStartedAt: React.MutableRefObject<number>;
  sessionId: string | undefined;
  setAttachments: Setter<AttachmentReference[]>;
  setChatPending: Setter<boolean>;
  setCode: Setter<string>;
  setEntry: Setter<string>;
  setError: Setter<string>;
  setImportStatus: Setter<string>;
  setLastApiError: Setter<string>;
  setLastApiStatus: Setter<string>;
  setLastTimeoutReason: Setter<string>;
  setLatestReceipt: Setter<InfoReceipt>;
  setLatestResult: Setter<string>;
  setLegacySignals: Setter<string>;
  setProposal: Setter<PatchProposal | null>;
  setSelectedPath: Setter<string>;
  setSessionId: Setter<string | undefined>;
  setStage: (value: AvatarRuntimeState) => void;
  setUserAwayFromLatest: Setter<boolean>;
  setX6ImportStatus: Setter<string>;
  setX7ImportStatus: Setter<string>;
  stickToLatestRef: React.MutableRefObject<boolean>;
  userInteracted: React.MutableRefObject<boolean>;
}

export function createChatConversationHandlers(deps: ChatConversationHandlersDeps) {
  const {
    appendMessage,
    updateCard,
    attachments,
    createGitHubCards,
    entry,
    finishAssistantResponseLifecycle,
    muted,
    nowId,
    recordResponseLifecycle,
    requestStartedAt,
    sessionId,
    setAttachments,
    setChatPending,
    setCode,
    setEntry,
    setError,
    setImportStatus,
    setLastApiError,
    setLastApiStatus,
    setLastTimeoutReason,
    setLatestReceipt,
    setLatestResult,
    setLegacySignals,
    setProposal,
    setSelectedPath,
    setSessionId,
    setStage,
    setUserAwayFromLatest,
    setX6ImportStatus,
    setX7ImportStatus,
    stickToLatestRef,
    userInteracted
  } = deps;
  const { createIDECard } = createChatIDEHandlers({ appendMessage, muted, nowId, setCode, setLatestReceipt, setLatestResult, setSelectedPath, setStage });

  async function submitMessage(event?: React.FormEvent) {
    event?.preventDefault();
    userInteracted.current = true;
    const text = entry.trim();
    if (!text && attachments.length === 0) return;
    const outgoingAttachments = attachments;
    setEntry('');
    setAttachments([]);
    setError('');
    setChatPending(true);
    setLastApiStatus('pending');
    setLastApiError('');
    setLastTimeoutReason('');
    requestStartedAt.current = Date.now();
    setStage('thinking');
    stickToLatestRef.current = true;
    setUserAwayFromLatest(false);
    appendMessage({ id: nowId(), role: 'user', text: redactSecretDisplay(text || 'Attached files for reference.'), attachments: outgoingAttachments });
    try {
      await handleUserText(text || 'Attached files for reference.', outgoingAttachments);
    } finally {
      setChatPending(false);
    }
  }

  function redactSecretDisplay(value: string) {
    return value
      .replace(/\bgh[pousr]_[A-Za-z0-9_]+/gi, '[redacted-token]')
      .replace(/\bsk-[A-Za-z0-9_-]+/gi, '[redacted-api-key]')
      .replace(/(password|passcode|token|api[_ -]?key|secret|one[- ]?time code|otp)\s*(is|=|:)?\s*\S+/gi, '$1 [redacted]');
  }

  const ACTIVE_ARTIFACT_KEY = 'x8.activeArtifact';

  function shouldClearActiveArtifact(text: string) {
    return /\b(new artifact|new website|different website|start over|reset artifact|clear artifact|new project)\b/i.test(text);
  }

  function readActiveArtifact(): Record<string, unknown> | null {
    try {
      const raw = window.localStorage.getItem(ACTIVE_ARTIFACT_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return null;
      if (!String(parsed.content || '').trim()) return null;
      return parsed as Record<string, unknown>;
    } catch {
      return null;
    }
  }

  function writeActiveArtifact(artifact: Record<string, unknown>) {
    window.localStorage.setItem(
      ACTIVE_ARTIFACT_KEY,
      JSON.stringify({
        ...artifact,
        updatedAt: new Date().toISOString(),
      }),
    );
  }

  function activeArtifactForPrompt(text: string): Record<string, unknown> | null {
    if (shouldClearActiveArtifact(text)) {
      window.localStorage.removeItem(ACTIVE_ARTIFACT_KEY);
      return null;
    }

    return readActiveArtifact();
  }

  function payloadLanguage(payload: Record<string, unknown> | undefined) {
    return String(payload?.language || '').toLowerCase();
  }

  function pathLanguage(path: string) {
    if (path.endsWith('.html')) return 'html';
    if (path.endsWith('.css')) return 'css';
    if (path.endsWith('.ps1')) return 'powershell';
    if (path.endsWith('.py')) return 'python';
    if (path.endsWith('.tsx')) return 'tsx';
    if (path.endsWith('.jsx')) return 'jsx';
    if (path.endsWith('.ts')) return 'ts';
    if (path.endsWith('.js')) return 'js';
    return '';
  }

  function activeArtifactLanguage(artifact: Record<string, unknown> | null) {
    if (!artifact) return '';
    return String(artifact.language || pathLanguage(String(artifact.path || '')) || '').toLowerCase();
  }

  function rememberActiveArtifactFromCards(cards: ChatCard[]) {
    const editorCards = cards.filter((card) => card.type === 'editor' && String(card.payload?.content || '').trim());
    if (!editorCards.length) return;

    const existing = readActiveArtifact();
    const existingLanguage = activeArtifactLanguage(existing);

    const preferredCard =
      existingLanguage
        ? editorCards.find((card) => payloadLanguage(card.payload) === existingLanguage) || editorCards[editorCards.length - 1]
        : editorCards.find((card) => payloadLanguage(card.payload) === 'html') || editorCards[editorCards.length - 1];

    const payload = preferredCard.payload || {};
    const artifact = {
      id: preferredCard.id,
      title: preferredCard.title,
      path: String(payload.path || 'generated/openwebui-code-1.html'),
      language: String(payload.language || pathLanguage(String(payload.path || ''))),
      content: String(payload.content || ''),
      pages: Array.isArray(payload.pages) ? payload.pages : undefined,
      updatedAt: new Date().toISOString(),
      source: String(payload.source || 'x8-editor-card'),
    };

    writeActiveArtifact(artifact);
  }

  function isActiveArtifactFollowUp(text: string) {
    if (shouldClearActiveArtifact(text)) return false;
    if (!readActiveArtifact()) return false;

    if (/\b(create|build|generate)\b/i.test(text) && /\b(new website|new artifact|new project|different website)\b/i.test(text)) {
      return false;
    }

    return /\b(change|update|revise|make|set|turn|replace|swap|add|remove|delete|highlight|where|show|line|lines|color|colors|css|html|header|footer|section|button|nav|page|tab|preview|refresh|same|this|that)\b/i.test(text);
  }

  function isHighlightLineRequest(text: string) {
    return /\b(highlight|show|where|which)\b/i.test(text) && /\b(line|lines|text|color|colors|css|change|changes)\b/i.test(text);
  }

  function colorTargetLineDecorations(content: string) {
    return content
      .split(/\r?\n/)
      .map((line, index) => ({
        line,
        lineNumber: index + 1,
      }))
      .filter(({ line }) => /(?:color|background|border|box-shadow|text-shadow|--[A-Za-z0-9_-]+)\s*[:=][^;]*(?:#[0-9A-Fa-f]{3,8}|rgb\(|hsl\(|\bred\b|\bblue\b|\byellow\b|\bpurple\b|\borange\b|\bwhite\b|\bblack\b|\bsilver\b)/i.test(line))
      .map(({ lineNumber }) => ({
        lineNumber,
        type: 'highlight',
        reason: 'Color-related line in the active artifact',
      }));
  }

  function updateExistingActiveCard(activeArtifact: Record<string, unknown>, editorCard: ChatCard, summary = 'Updated the active artifact in this card.') {
    const activeId = String(activeArtifact.id || editorCard.id);
    const payload = editorCard.payload || {};
    const content = String(payload.content || activeArtifact.content || '');
    const path = String(activeArtifact.path || payload.path || 'generated/openwebui-code-1.html');
    const language = String(activeArtifact.language || payload.language || pathLanguage(path));

    const nextPayload = {
      ...activeArtifact,
      ...payload,
      id: activeId,
      path,
      language,
      content,
      active_artifact: true,
      lineDecorations: [],
      updatedAt: new Date().toISOString(),
    };

    updateCard(activeId, {
      title: String(activeArtifact.title || editorCard.title || 'Active artifact'),
      status: 'draft',
      summary,
      payload: nextPayload,
      collapsed: false,
    });

    writeActiveArtifact({
      ...nextPayload,
      title: String(activeArtifact.title || editorCard.title || 'Active artifact'),
    });
  }

  function findMatchingEditorCard(activeArtifact: Record<string, unknown>, cards: ChatCard[]) {
    const activeLanguage = activeArtifactLanguage(activeArtifact);
    const editors = cards.filter((card) => card.type === 'editor' && String(card.payload?.content || '').trim());

    if (!editors.length) return null;
    if (!activeLanguage) return editors[editors.length - 1];

    return editors.find((card) => payloadLanguage(card.payload) === activeLanguage) || null;
  }

  function highlightActiveArtifactLines(text: string) {
    const activeArtifact = activeArtifactForPrompt(text);
    if (!activeArtifact) {
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'I do not have an active artifact selected yet. Generate or select a website/code card first.',
      });
      setStage(muted ? 'muted' : 'idle');
      return;
    }

    const content = String(activeArtifact.content || '');
    const path = String(activeArtifact.path || 'generated/openwebui-code-1.html');
    const decorations = colorTargetLineDecorations(content);
    const cardId = String(activeArtifact.id || nowId());

    updateCard(cardId, {
      summary: decorations.length
        ? 'Yellow highlighted lines mark the current target lines in the active artifact.'
        : 'Active artifact stayed selected, but no matching color lines were found.',
      payload: {
        ...activeArtifact,
        path,
        content,
        lineDecorations: decorations,
        active_artifact: true,
      },
      collapsed: false,
    });

    writeActiveArtifact({
      ...activeArtifact,
      id: cardId,
      path,
      content,
      lineDecorations: decorations,
      active_artifact: true,
    });

    appendMessage({
      id: nowId(),
      role: 'assistant',
      text: decorations.length
        ? 'I highlighted the matching lines in the active artifact.'
        : 'I kept the active artifact selected, but I did not find matching color lines to highlight.',
    });

    setLatestResult('Active artifact lines highlighted');
    setStage(muted ? 'muted' : 'idle');
  }
  async function handleUserText(text: string, outgoingAttachments: AttachmentReference[] = []) {
    if (isHighlightLineRequest(text) && activeArtifactForPrompt(text)) return highlightActiveArtifactLines(text);
    if (isActiveArtifactFollowUp(text)) return createAssistantReply(text, outgoingAttachments);
    const intent = classifyRequest(text);
    if (intent === 'file') return openFileCard('README.md');
    if (intent === 'diff') return proposeDiffCard('README.md');
    if (intent === 'artifact') return createArtifactCard(text);
    if (intent === 'research') return createResearchCard(text);
    if (intent === 'image') return createImageCard(text);
    if (intent === 'test') return createTestCard(text);
    if (intent === 'github') return createGitHubCards(text);
    if (intent === 'ide') return createIDECard(text);
    if (intent === 'self_build') return createSelfBuildCards(text);
    return createAssistantReply(text, outgoingAttachments);
  }

  async function createAssistantReply(text: string, outgoingAttachments: AttachmentReference[] = []) {
    try {
      setLatestResult('Model warming/responding...');
      setLastApiStatus('pending');
      setLastApiError('');
      setLastTimeoutReason('');

      const activeBefore = activeArtifactForPrompt(text);
      const response = await sendChat(text, outgoingAttachments, sessionId, activeBefore);

      setSessionId(response.data.session_id);
      window.localStorage.setItem('x8.activeSessionId', response.data.session_id);
      setLatestReceipt(response.data.receipt || response.receipts?.[0] || null);
      setLatestResult(outgoingAttachments.length ? `Attachments processed: ${response.status}` : response.status);
      setLastApiStatus(response.status || 'ok');

      const responseText = response.data.assistant_message.content;
      const responseCards = response.data.assistant_message.cards.map(mapKernelCard).filter((card): card is ChatCard => Boolean(card));

      let usedExistingCard = false;
      if (activeBefore && isActiveArtifactFollowUp(text)) {
        const matchingEditor = findMatchingEditorCard(activeBefore, responseCards);
        if (matchingEditor) {
          updateExistingActiveCard(activeBefore, matchingEditor, 'Updated the active artifact in this card.');
          usedExistingCard = true;
        }
      }

      if (!usedExistingCard) {
        rememberActiveArtifactFromCards(responseCards);
      }

      recordResponseLifecycle(responseCards.length ? 'text-with-cards' : 'deterministic/text-only', Boolean(responseText.trim()), responseCards.length > 0);

      appendMessage({
        id: response.data.message_id || nowId(),
        role: 'assistant',
        text: responseText,
        attachments: response.data.attachments,
        cards: usedExistingCard ? [] : responseCards
      });

      await finishAssistantResponseLifecycle(responseText, usedExistingCard ? 0 : responseCards.length);
    } catch (exc) {
      const timedOut = exc instanceof DOMException && exc.name === 'AbortError';
      const reason = timedOut ? `Chat request timed out after ${CHAT_TIMEOUT_MS}ms.` : exc instanceof Error ? exc.message : 'API request failed.';
      setLastApiStatus(timedOut ? 'timeout' : 'error');
      setLastApiError(reason);
      if (timedOut) setLastTimeoutReason(reason);
      setStage('error');
      appendMessage({ id: nowId(), role: 'assistant', text: timedOut ? 'The chat request timed out.' : 'The chat request could not complete.', cards: [errorCard(timedOut ? 'Chat timeout' : 'Chat request failed', reason)] });
    }
  }

  async function openFileCard(path: string) {
    try {
      const response = await readFile(path);
      setSelectedPath(path);
      setCode(response.data.content);
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult(`Opened ${path}`);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: `Opened ${path}.`,
        cards: [
          {
            id: nowId(),
            type: 'file',
            title: path,
            status: response.status,
            summary: `${response.data.line_count} lines loaded into an inline file viewer.`,
            receipt: response.receipts?.[0],
            payload: { path, content: response.data.content }
          }
        ]
      });
      setStage(muted ? 'muted' : 'idle');
    } catch {
      setStage('error');
      appendMessage({ id: nowId(), role: 'assistant', text: `I could not open ${path}.`, cards: [errorCard('File read failed', 'The workspace read endpoint returned an error.')] });
    }
  }

  async function proposeDiffCard(path: string) {
    try {
      const current = await readFile(path);
      const next = current.data.content.endsWith('\n') ? `${current.data.content}<!-- XV8 proposed note -->\n` : `${current.data.content}\n<!-- XV8 proposed note -->\n`;
      setSelectedPath(path);
      setCode(next);
      const response = await proposeUpdate(path, next);
      setProposal(response.data);
      setLatestReceipt(response.data.receipt);
      setLatestResult(`Diff proposal for ${path}`);
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult('Generated inline artifact preview');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: `Prepared a local edit proposal for ${path}. No mutation has happened.`,
        cards: [
          {
            id: nowId(),
            type: 'editor',
            title: `Editor draft: ${path}`,
            status: 'draft',
            summary: 'The draft is local to this chat card. Applying it requires click approval.',
            payload: { path, content: next },
            collapsed: true
          },
          {
            id: nowId(),
            type: 'diff',
            title: `Diff proposal: ${path}`,
            status: response.data.receipt.status,
            summary: response.data.receipt.summary,
            receipt: response.data.receipt,
            payload: {
              path,
              diff: response.data.diff,
              risk: response.data.approval?.risk || 'medium',
              beforeAfter: response.data.approval?.intent.before_after_summary || 'Content would change only after approval.',
              approvalState: response.data.approval?.status || 'approval_required'
            }
          },
          {
            id: nowId(),
            type: 'approval',
            title: 'Apply requires approval',
            status: response.data.approval?.status || 'pending',
            summary: 'Click Apply inside this card to open the focused approval dialog.',
            receipt: response.data.receipt,
            payload: { path }
          }
        ]
      });
      setStage(muted ? 'muted' : 'idle');
    } catch {
      setStage('error');
      appendMessage({ id: nowId(), role: 'assistant', text: `I could not prepare a diff for ${path}.`, cards: [errorCard('Diff proposal failed', 'No repository mutation was attempted.')] });
    }
  }

  async function createArtifactCard(prompt: string) {
    try {
      const response = await createArtifactPreview('Inline website preview', prompt);
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult(`Search status: ${response.status}`);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Generated an inline website artifact preview.',
        cards: [
          {
            id: nowId(),
            type: 'artifact',
            title: 'Inline website preview',
            status: response.status,
            summary: 'Preview, code, and metadata are attached to this chat response.',
            receipt: response.receipts?.[0],
            payload: {
              html: response.data.html,
              css: response.data.css,
              metadata: { title: response.data.title, exportable: true }
            }
          }
        ]
      });
      setStage(muted ? 'muted' : 'idle');
    } catch {
      setStage('error');
      appendMessage({ id: nowId(), role: 'assistant', text: 'The artifact preview could not be generated.', cards: [errorCard('Artifact preview failed', 'No files were written.')] });
    }
  }

  async function createSelfBuildCards(prompt: string) {
    try {
      const response = await runSelfBuildPrompt(prompt);
      const detail = response.data?.proposal_detail || {};
      const task = response.data?.task || {};
      const intent = response.data?.intent || 'create_proposal';
      const changes = detail.changes || task.proposal?.changes || [];
      const changedPaths = detail.changed_file_paths || changes.map((change: { file_path?: string }) => change.file_path).filter(Boolean);
      const firstChange = changes[0] || {};
      setLatestResult(intent === 'create_proposal' ? 'Self-build patch plan created' : `Self-build ${response.status}`);
      setLatestReceipt(response.receipts?.[0] || null);
      if (!detail.patch_hash) {
        appendMessage({
          id: nowId(),
          role: 'assistant',
          text: response.message,
          cards: [{ id: nowId(), type: 'receipt', title: 'Self-build status', status: response.status, summary: response.message, payload: response.data, collapsed: false }]
        });
        setStage(muted ? 'muted' : 'idle');
        return;
      }
      const canApplySelfBuild = detail.apply_safe === true && Boolean(detail.task_id) && Boolean(detail.patch_id) && Boolean(detail.approval_id) && Boolean(detail.patch_hash) && detail.validation_status !== 'failed';
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: detail.message || 'No files changed. Approval required before apply.',
        cards: [
          { id: nowId(), type: 'receipt', title: 'Self-build prompt detected', status: response.status, summary: 'No files changed. Approval required before apply.', payload: { task_id: detail.task_id, patch_id: detail.patch_id, approval_id: detail.approval_id, patch_hash: detail.patch_hash } },
          { id: nowId(), type: 'receipt', title: 'Self-build patch plan', status: detail.validation_status || task.plan?.status || 'created', summary: `${detail.files_changed_count || changedPaths.length || 0} file change(s): ${changedPaths.join(', ') || 'none'}`, payload: { ...detail, risk_level: detail.risk_level, validation_status: detail.validation_status }, collapsed: false },
          { id: nowId(), type: 'diff', title: 'Self-build patch proposal', status: detail.validation_status || 'proposed', summary: `${detail.files_changed_count || changedPaths.length || 0} proposed file change(s).`, payload: { diff: firstChange.unified_diff || '', path: firstChange.file_path || changedPaths[0] || '', approvalState: detail.apply_safe ? 'pending_click' : 'blocked', before_hash: firstChange.before_hash, after_hash: firstChange.after_hash }, collapsed: true },
          ...(canApplySelfBuild ? [{ id: nowId(), type: 'approval' as const, title: 'Approval required before apply', status: 'pending_click', summary: 'Applying this patch calls the locked self-build endpoint with the exact approval payload.', payload: { task_id: detail.task_id, patch_id: detail.patch_id, approval_id: detail.approval_id, patch_hash: detail.patch_hash, changed_file_paths: changedPaths, apply_safe: detail.apply_safe, validation_status: detail.validation_status, validation_passed: detail.validation_status === 'passed' } }] : [])
        ]
      });
      setStage(muted ? 'muted' : 'idle');
    } catch {
      setStage('error');
      appendMessage({ id: nowId(), role: 'assistant', text: 'Self-build planning could not complete.', cards: [errorCard('Self-build failed', 'No files were changed.')] });
    }
  }

  async function createResearchCard(query: string) {
    try {
      const response = await runSearch(query.replace(/search|searxng/gi, '').trim() || query);
      const results = response.data.results || [];
      setLatestReceipt(response.receipts?.[0] || null);
      setLatestResult(`Image status: ${response.status}`);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: results.length ? 'Search results are attached inline.' : 'Search was attempted; provider status is shown inline.',
        cards: [
          {
            id: nowId(),
            type: 'research',
            title: 'Inline research results',
            status: response.status,
            summary: response.message,
            receipt: response.receipts?.[0],
            payload: {
              query,
              provider: response.data.provider || 'SearXNG',
              results,
              freshness: 'Runtime provider response; verify dates in cited sources for time-sensitive claims.'
            }
          }
        ]
      });
      setStage(muted ? 'muted' : 'idle');
    } catch {
      setStage('error');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Search is unavailable right now.',
        cards: [errorCard('Provider unavailable', 'SearXNG search could not be reached. No search results were invented.')]
      });
    }
  }

  async function createImageCard(prompt: string) {
    try {
      const response = await requestImage(prompt);
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Image generation status is attached inline.',
        cards: [
          {
            id: nowId(),
            type: response.status === 'ok' ? 'image' : 'error',
            title: response.status === 'ok' ? 'Inline image result' : 'Image generation unavailable',
            status: response.status,
            summary: response.status === 'ok' ? response.message : 'Reason: ComfyUI service unreachable or Juggernaut model missing. No image was generated.',
            receipt: response.receipts?.[0],
            payload: {
              prompt,
              model: 'Juggernaut',
              workflow: 'ComfyUI default',
              seed: response.data.seed || 'pending',
              imageUrl: response.data.image_url || ''
            }
          }
        ]
      });
      setStage(muted ? 'muted' : 'idle');
    } catch {
      setStage('error');
      appendMessage({
        id: nowId(),
        role: 'assistant',
        text: 'Image generation unavailable.',
        cards: [errorCard('Image generation unavailable', 'Reason: ComfyUI service unreachable or Juggernaut model missing. No image was generated.')]
      });
    }
  }

  function createTestCard(text: string) {
    setLatestResult('Test run queued for approval');
    appendMessage({
      id: nowId(),
      role: 'assistant',
      text: 'Test execution needs approval before Docker work starts.',
      cards: [
        {
          id: nowId(),
          type: 'test',
          title: 'Docker test run',
          status: 'approval_required',
          summary: `Requested: ${text}. No test command has run yet.`,
          receipt: { id: nowId(), action: 'test_run', status: 'approval_required', summary: 'Click approval is required before execution.' },
          payload: { command: 'docker compose run --rm api-tests' }
        }
      ]
    });
    setStage(muted ? 'muted' : 'idle');
  }

  async function attachFiles(fileList: FileList | null) {
    if (!fileList) return;
    for (const file of Array.from(fileList)) {
      const pending: AttachmentReference = {
        attachment_id: `pending-${nowId()}`,
        filename: file.name,
        mime_type: file.type || 'application/octet-stream',
        size_bytes: file.size,
        status: 'uploading'
      };
      setAttachments((current) => [...current, pending]);
      try {
        const response = await uploadAttachment(file);
        setAttachments((current) => current.map((attachment) => (attachment.attachment_id === pending.attachment_id ? response.data : attachment)));
        setLatestReceipt(response.receipts?.[0] || null);
        setLatestResult(`${response.data.filename}: ${response.data.status}`);
      } catch {
        setAttachments((current) => current.map((attachment) => (attachment.attachment_id === pending.attachment_id ? { ...attachment, status: 'failed' } : attachment)));
        setLatestResult(`${file.name}: upload failed`);
      }
    }
  }

  function removeAttachment(attachmentId: string) {
    setAttachments((current) => current.filter((attachment) => attachment.attachment_id !== attachmentId));
  }

  async function submitConfigScan() {
    const response = await scanX7Configs();
    setImportStatus(`X7 ${response.data.x7_files_found} files, X6 ${response.data.x6_files_found} files`);
    setX7ImportStatus(`${response.data.x7_import_status.import_status} / ${response.data.x7_files_found} files`);
    setX6ImportStatus(`${response.data.x6_import_status.import_status} / ${response.data.x6_files_found} files`);
    setLegacySignals(`${response.data.providers_found.length} providers, ${response.data.secrets_detected_redacted.length} redacted secrets`);
  }

  return {
    attachFiles,
    createArtifactCard,
    createAssistantReply,
    createImageCard,
    createResearchCard,
    createSelfBuildCards,
    createTestCard,
    handleUserText,
    openFileCard,
    proposeDiffCard,
    redactSecretDisplay,
    removeAttachment,
    submitConfigScan,
    submitMessage
  };
}




