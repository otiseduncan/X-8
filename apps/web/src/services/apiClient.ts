import type { AttachmentReference, Capability, ChatResponse, FileEntry, FileRead, IntegrationStatus, PatchProposal, ResultEnvelope, SessionDetail, SessionSummary, TeamSeat } from '../types/contracts';

const API = '';

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`Request failed: ${path}`);
  return response.json();
}

export function loadCapabilities() {
  return getJson<ResultEnvelope<Capability[]>>('/api/capabilities');
}

export function loadIntegrations() {
  return getJson<ResultEnvelope<IntegrationStatus[]>>('/api/integrations');
}

export function loadTeam() {
  return getJson<ResultEnvelope<TeamSeat[]>>('/api/team/seats');
}

export function loadFiles() {
  return getJson<ResultEnvelope<FileEntry[]>>('/api/workspace/files');
}

export function loadDockerPresets() {
  return getJson<ResultEnvelope<string[]>>('/api/docker/presets');
}

export function loadGitHubStatus() {
  return getJson<ResultEnvelope<Record<string, string>>>('/api/github/status');
}

export function loadSearchStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/search/status');
}

export function loadImageStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/images/status');
}

export function loadBridgeStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/local-bridge/status');
}

export function loadConfigImportStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/config-import/legacy/status');
}

export function loadAvatarManifest() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/avatar/manifest');
}

export function loadSpeechStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/speech/status');
}

export async function createSpeechReceipt() {
  const response = await fetch('/api/speech/receipt', { method: 'POST' });
  if (!response.ok) throw new Error('Speech receipt failed');
  return response.json();
}

export async function runSearch(query: string) {
  const response = await fetch('/api/search/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  if (!response.ok) throw new Error('Search failed');
  return response.json();
}

export async function scanX7Configs() {
  const response = await fetch('/api/config-import/legacy/scan', { method: 'POST' });
  if (!response.ok) throw new Error('Config import scan failed');
  return response.json();
}

export async function requestImage(prompt: string) {
  const response = await fetch('/api/images/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, model: 'juggernaut', approved: false })
  });
  if (!response.ok) throw new Error('Image request failed');
  return response.json();
}

export async function readFile(path: string) {
  const response = await fetch('/api/workspace/read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });
  if (!response.ok) throw new Error('File read failed');
  return response.json() as Promise<ResultEnvelope<FileRead>>;
}

export async function proposeUpdate(path: string, proposed_content: string) {
  const response = await fetch('/api/repo/propose-update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, proposed_content })
  });
  if (!response.ok) throw new Error('Patch proposal failed');
  return response.json() as Promise<ResultEnvelope<PatchProposal>>;
}

export async function applyUpdate(path: string, proposed_content: string, approved: boolean) {
  const response = await fetch('/api/repo/apply-update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, proposed_content, approved })
  });
  if (!response.ok) throw new Error('Patch apply failed');
  return response.json() as Promise<ResultEnvelope<PatchProposal>>;
}

export async function createArtifactPreview(title: string, prompt: string) {
  const response = await fetch('/api/artifacts/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, prompt })
  });
  if (!response.ok) throw new Error('Artifact preview failed');
  return response.json();
}

export async function createSelfBuildTask(prompt: string) {
  const response = await fetch('/api/self-build/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_prompt: prompt, mode: 'patch_proposal', approval_required: true, commit_allowed: false, push_allowed: false })
  });
  if (!response.ok) throw new Error('Self-build task failed');
  return response.json();
}

export async function runSelfBuildPrompt(prompt: string) {
  const response = await fetch('/api/self-build/prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt })
  });
  if (!response.ok) throw new Error('Self-build prompt failed');
  return response.json();
}

export async function uploadAttachment(file: File) {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch('/api/attachments', { method: 'POST', body });
  if (!response.ok) throw new Error('Attachment upload failed');
  return response.json() as Promise<ResultEnvelope<AttachmentReference>>;
}

export function loadSessions() {
  return getJson<ResultEnvelope<SessionSummary[]>>('/api/sessions');
}

export function loadSession(sessionId: string) {
  return getJson<ResultEnvelope<SessionDetail>>(`/api/sessions/${sessionId}`);
}

export function loadModelStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/models/status');
}

export function loadMemoryStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/memory/status');
}

export function loadMemoryRecords() {
  return getJson<ResultEnvelope<Array<Record<string, unknown>>>>('/api/memory/records');
}

export function loadReceipts() {
  return getJson<ResultEnvelope<Array<Record<string, unknown>>>>('/api/receipts');
}

export async function sendChat(message: string, attachments: AttachmentReference[] = [], session_id?: string) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id,
      attachments: attachments
        .filter((attachment) => attachment.attachment_id && attachment.status !== 'blocked' && attachment.status !== 'failed')
        .map((attachment) => ({
          attachment_id: attachment.attachment_id,
          filename: attachment.filename,
          mime_type: attachment.mime_type,
          size_bytes: attachment.size_bytes
        }))
    })
  });
  if (!response.ok) throw new Error('Chat request failed');
  return response.json() as Promise<ResultEnvelope<ChatResponse>>;
}
