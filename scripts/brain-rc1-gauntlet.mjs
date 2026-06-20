#!/usr/bin/env node

const API = process.env.X8_RC1_API_BASE || 'http://127.0.0.1:8080';
const WEB = process.env.X8_RC1_WEB_BASE || 'http://127.0.0.1:5173';
const stamp = `rc1-${Date.now()}`;
const SECRET_MARKERS = [
  'ghp_abc123',
  'sk-abc123',
  'hunter2',
  '123456',
  '-----BEGIN PRIVATE KEY-----',
];
const MISS = 'I don’t have a saved memory for that yet.';
const PROJECT_MISS = 'I don’t have a current project state saved yet.';
const NEXT_MISS = 'I don’t have a next step saved yet.';
const BLOCKER_MISS = 'I don’t have a blocker saved yet.';
const VALIDATION_MISS = 'I don’t have a validation checkpoint saved yet.';

const domains = [];

function redact(value) {
  let text = typeof value === 'string' ? value : JSON.stringify(value);
  for (const marker of SECRET_MARKERS) {
    text = text.split(marker).join('[REDACTED]');
  }
  text = text.replace(/ghp_[A-Za-z0-9_]+/g, 'ghp_[REDACTED]');
  text = text.replace(/sk-[A-Za-z0-9_-]+/g, 'sk-[REDACTED]');
  text = text.replace(/-----BEGIN [^-]+ PRIVATE KEY-----[\s\S]*?-----END [^-]+ PRIVATE KEY-----/g, '[REDACTED_PRIVATE_KEY]');
  return text;
}

function assert(condition, message, details = undefined) {
  if (!condition) {
    const error = new Error(message);
    error.details = details;
    throw error;
  }
}

function noSecret(value, label) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  for (const marker of SECRET_MARKERS) {
    assert(!text.includes(marker), `${label} leaked raw secret marker`, redact(text).slice(0, 500));
  }
  assert(!/ghp_[A-Za-z0-9_]+/.test(text), `${label} leaked GitHub token pattern`, redact(text).slice(0, 500));
  assert(!/sk-[A-Za-z0-9_-]+/.test(text), `${label} leaked OpenAI key pattern`, redact(text).slice(0, 500));
  assert(!/-----BEGIN [^-]+ PRIVATE KEY-----/.test(text), `${label} leaked private key pattern`, redact(text).slice(0, 500));
}

async function request(method, path, body = undefined, timeoutMs = 45000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      payload = { raw: text };
    }
    noSecret(payload, `${method} ${path}`);
    assert(response.ok, `${method} ${path} returned HTTP ${response.status}`, payload);
    return payload;
  } finally {
    clearTimeout(timeout);
  }
}

async function chat(message, sessionId = `sess-${stamp}`) {
  const payload = await request('POST', '/api/chat', { message, session_id: sessionId });
  return payload;
}

function assistantText(payload) {
  return payload?.data?.assistant_message?.content || '';
}

function lane(payload) {
  return payload?.receipts?.[0]?.metadata?.kernel_lane || '';
}

async function domain(name, fn) {
  const started = Date.now();
  try {
    const details = await fn();
    domains.push({ name, status: 'PASS', ms: Date.now() - started, details });
  } catch (error) {
    domains.push({
      name,
      status: 'FAIL',
      ms: Date.now() - started,
      failedCommand: error.command || name,
      rootCauseHint: error.message,
      details: redact(error.details || error.stack || String(error)),
    });
  }
}

async function findMemory(query, params = '') {
  const path = `/api/brain/memories?q=${encodeURIComponent(query)}${params}`;
  return request('GET', path);
}

async function manualMemory() {
  const phrase = `direct senior-engineer answers ${stamp}`;
  const first = await request('POST', '/api/brain/remember', { content: `I prefer ${phrase}` });
  const duplicate = await request('POST', '/api/brain/remember', { content: `I prefer ${phrase}` });
  const retrieve = await request('POST', '/api/brain/retrieve', { query: 'how I like answers', limit: 3 });
  const forgot = await request('POST', '/api/brain/forget', { query: phrase });
  const miss = await request('POST', '/api/brain/retrieve', { query: phrase, limit: 3 });
  const events = await request('GET', `/api/brain/events?memory_id=${first.data.id}`);
  const records = await findMemory(phrase, '&include_deleted=true');
  assert(first.status === 'passed', 'manual remember did not pass', first);
  assert(duplicate.status === 'passed', 'duplicate remember should be safely idempotent or update-equivalent', duplicate);
  assert(records.data.filter((item) => String(item.summary).includes(phrase)).length === 1, 'manual remember duplicated a record', records);
  assert(retrieve.message.includes(phrase), 'manual retrieve missed saved preference', retrieve);
  assert(forgot.data.soft_deleted === true && forgot.data.active === false, 'forget did not soft-delete', forgot);
  assert(miss.message === MISS, 'forget miss phrase mismatch', miss);
  assert(events.data.some((event) => event.event_type === 'created'), 'create event missing', events);
  assert(events.data.some((event) => event.event_type === 'soft_deleted'), 'soft-delete event missing', events);
  return { memory_id: first.data.id, miss: miss.message };
}

async function activeFocus() {
  const sessionId = `focus-${stamp}`;
  const focus = `Brain RC1 ${stamp}`;
  const set = await request('POST', '/api/brain/focus', { focus, session_id: sessionId });
  const get = await request('GET', `/api/brain/focus?session_id=${encodeURIComponent(sessionId)}`);
  const update = await request('POST', '/api/brain/focus', { focus: `${focus} updated`, session_id: sessionId });
  assert(set.data.focus === focus, 'focus set failed', set);
  assert(get.data.focus === focus, 'focus retrieve failed', get);
  assert(update.data.focus.endsWith('updated'), 'focus update failed', update);
  return { focus: update.data.focus };
}

async function pendingApproval() {
  const marker = `pending-${stamp}`;
  const phrase = `my family history includes ${marker}`;
  const pending = await request('POST', '/api/brain/remember', { content: phrase });
  const miss = await request('POST', '/api/brain/retrieve', { query: phrase });
  const approved = await request('POST', `/api/brain/memories/${pending.data.id}/approve`);
  const found = await request('POST', '/api/brain/retrieve', { query: phrase });
  const rejectPhrase = `my family history includes rejected ${marker}`;
  const pendingReject = await request('POST', '/api/brain/remember', { content: rejectPhrase });
  const rejected = await request('POST', `/api/brain/memories/${pendingReject.data.id}/reject`);
  const rejectedMiss = await request('POST', '/api/brain/retrieve', { query: rejectPhrase });
  const reactivated = await request('POST', `/api/brain/memories/${pendingReject.data.id}/reactivate`);
  assert(pending.status === 'approval_required', 'sensitive memory was not pending', pending);
  assert(!(miss.data.retrieval_proof.memory_ids_used || []).includes(pending.data.id), 'pending memory was retrieved', miss);
  assert(approved.status === 'approved', 'pending approval failed', approved);
  assert(found.message.includes('family history'), 'approved pending memory not retrieved', found);
  assert(rejected.status === 'rejected', 'pending rejection failed', rejected);
  assert(!(rejectedMiss.data.retrieval_proof.memory_ids_used || []).includes(pendingReject.data.id), 'rejected memory was retrieved', rejectedMiss);
  assert(reactivated.status === 'blocked', 'rejected sensitive memory reactivated unsafely', reactivated);
  return { approved: approved.data.id, rejected: rejected.data.id };
}

async function autoCapture() {
  const phrase = `auto direct answers ${stamp}`;
  await request('POST', '/api/brain/auto-capture/toggle', { enabled: true });
  const saved = await chat(`I prefer ${phrase}.`, `auto-${stamp}`);
  const duplicate = await chat(`I prefer ${phrase}.`, `auto-${stamp}`);
  const correction = await chat(`Actually, I prefer full detailed answers when we are building X ${stamp}.`, `auto-${stamp}`);
  const work = await chat(`we are working on Brain RC1 ${stamp}`, `auto-${stamp}`);
  const validation = await chat(`we validated Phase 5 with all tests passing ${stamp}`, `auto-${stamp}`);
  await request('POST', '/api/brain/auto-capture/toggle', { enabled: false });
  await chat(`I prefer disabled auto capture ${stamp}.`, `auto-off-${stamp}`);
  const disabled = await findMemory(`disabled auto capture ${stamp}`);
  const manual = await request('POST', '/api/brain/remember', { content: `I prefer manual while disabled ${stamp}` });
  await request('POST', '/api/brain/auto-capture/toggle', { enabled: true });
  const memories = await findMemory(phrase);
  assert(saved.receipts.some((receipt) => receipt.action === 'brain.memory_auto_saved'), 'low-risk preference did not auto-save', saved);
  assert(duplicate.receipts.some((receipt) => /Already remembered/.test(receipt.summary)), 'duplicate auto-capture not detected', duplicate);
  assert(correction.receipts.some((receipt) => receipt.action === 'brain.memory_correction_applied'), 'correction did not update/supersede memory', correction);
  assert(work.receipts.some((receipt) => receipt.action.startsWith('brain.continuity')), 'active work did not auto-capture continuity', work);
  assert(validation.receipts.some((receipt) => receipt.action.startsWith('brain.continuity')), 'validation did not auto-capture continuity', validation);
  assert(memories.data.filter((item) => item.active && String(item.summary).includes(phrase)).length === 1, 'auto-capture duplicated memory', memories);
  assert(disabled.data.length === 0, 'auto-capture toggle off still saved automatically', disabled);
  assert(manual.status === 'passed', 'manual remember failed while auto-capture off', manual);
  return { saved: phrase };
}

async function candidateEvents() {
  const candidates = await request('GET', '/api/brain/candidates?limit=200');
  const events = await request('GET', '/api/brain/events');
  const duplicate = await request('GET', '/api/brain/candidates?decision=duplicate');
  const blocked = await request('GET', '/api/brain/candidates?decision=blocked');
  const ignored = await request('POST', '/api/brain/extract-candidates', { text: 'okay', source_turn_id: stamp });
  assert(Array.isArray(candidates.data), 'candidate list is not stable', candidates);
  assert(Array.isArray(events.data), 'event list is not stable', events);
  assert(Array.isArray(duplicate.data), 'duplicate candidate filter failed', duplicate);
  assert(Array.isArray(blocked.data), 'blocked candidate filter failed', blocked);
  assert(Array.isArray(ignored.data), 'candidate extraction route failed', ignored);
  return { candidates: candidates.data.length, events: events.data.length };
}

async function semanticRetrieval() {
  const preference = await request('POST', '/api/brain/remember', { content: `I prefer direct senior-engineer answers semantic ${stamp}` });
  const routing = await request('POST', '/api/brain/remember', { content: `GitHub prompts must not steal self-build routing semantic ${stamp}` });
  const status = await request('GET', '/api/brain/embedding-status');
  const reindex = await request('POST', '/api/brain/reindex');
  const prefRecall = await request('POST', '/api/brain/retrieve', { query: `how should you respond to me semantic ${stamp}` });
  const routingRecall = await request('POST', '/api/brain/retrieve', { query: `what was the routing issue semantic ${stamp}` });
  const missing = await request('POST', '/api/brain/retrieve', { query: `not present semantic-miss-${stamp}` });
  assert(status.status === 'ready' || status.status === 'unavailable', 'embedding status route unstable', status);
  assert(reindex.status === 'passed', 'reindex did not pass', reindex);
  assert(prefRecall.message.includes('senior-engineer'), 'preference semantic/keyword retrieval failed', prefRecall);
  assert(routingRecall.message.includes('self-build routing'), 'routing semantic/keyword retrieval failed', routingRecall);
  assert(missing.message === MISS, 'semantic miss phrase mismatch', missing);
  assert(!JSON.stringify([status, reindex, prefRecall]).includes('embedding_json'), 'raw vector exposed');
  return {
    embedding_available: Boolean(status.data.available),
    mode: prefRecall.data.retrieval_proof.retrieval_mode,
    preference_id: preference.data.id,
    routing_id: routing.data.id,
  };
}

async function continuity() {
  const sessionId = `cont-${stamp}`;
  const project = await chat(`we are working on Brain RC1 ${stamp}`, sessionId);
  const next = await chat(`the next step is complete the RC1 gauntlet ${stamp}`, sessionId);
  const blocker = await chat(`the blocker is no live interactive browser connector ${stamp}`, sessionId);
  const validation = await chat(`we validated Phase 5 with all tests passing ${stamp}`, sessionId);
  const decision = await chat(`decision: RC1 should repair broken brain behavior before testing ${stamp}`, sessionId);
  const projectAsk = await chat('what are we currently working on?', sessionId);
  const nextAsk = await chat('what is the next step?', sessionId);
  const blockerAsk = await chat('what is blocked?', sessionId);
  const validationAsk = await chat('what did we validate last?', sessionId);
  const decisionAsk = await chat('what did we decide about RC1?', sessionId);
  const task = await request('POST', '/api/brain/continuity/tasks', { summary: `complete RC1 task ${stamp}`, session_scope: sessionId });
  const patched = await request('PATCH', `/api/brain/continuity/tasks/${task.data.id}`, { status: 'done', active: false });
  const archived = await request('DELETE', `/api/brain/continuity/tasks/${task.data.id}`);
  const commit = await request('POST', '/api/brain/continuity/records', {
    record_type: 'commit_checkpoint',
    summary: `local HEAD checked for RC1 ${stamp}`,
    linked_commit_sha: '7cf05ad',
    session_scope: sessionId,
  });
  const handoff = await request('POST', '/api/brain/continuity/handoff', { session_scope: sessionId });
  assert(assistantText(project).includes(`Brain RC1 ${stamp}`), 'project state not saved', project);
  assert(assistantText(next).includes(`complete the RC1 gauntlet ${stamp}`), 'next step not saved', next);
  assert(assistantText(blocker).includes(`no live interactive browser connector ${stamp}`), 'blocker not saved', blocker);
  assert(assistantText(validation).includes(`Phase 5 with all tests passing ${stamp}`), 'validation not saved', validation);
  assert(assistantText(decision).includes(`before testing ${stamp}`), 'decision not saved', decision);
  assert(assistantText(projectAsk).includes(`Brain RC1 ${stamp}`), 'project state not retrieved', projectAsk);
  assert(assistantText(nextAsk).includes(`complete the RC1 gauntlet ${stamp}`), 'next step not retrieved', nextAsk);
  assert(assistantText(blockerAsk).includes(`no live interactive browser connector ${stamp}`), 'blocker not retrieved', blockerAsk);
  assert(assistantText(validationAsk).includes(`Phase 5 with all tests passing ${stamp}`), 'validation not retrieved', validationAsk);
  assert(assistantText(decisionAsk).includes(stamp), 'decision not retrieved', decisionAsk);
  assert(patched.data.status === 'done', 'task update failed', patched);
  assert(archived.data.soft_deleted === true, 'task archive failed', archived);
  assert(commit.status === 'passed', 'commit checkpoint failed', commit);
  assert(handoff.data.handoff.includes('Handoff note:'), 'handoff note missing', handoff);
  const emptySession = `empty-${stamp}`;
  const emptyProject = assistantText(await chat('what are we currently working on?', emptySession));
  const emptyNext = assistantText(await chat('what is the next step?', emptySession));
  const emptyBlocker = assistantText(await chat('what is blocked?', emptySession));
  const emptyValidation = assistantText(await chat('what did we validate last?', emptySession));
  assert(emptyProject === PROJECT_MISS || emptyProject.startsWith('Current project state:') || emptyProject.startsWith('We are currently working on:'), 'project miss/fallback phrase mismatch', emptyProject);
  assert(emptyNext === NEXT_MISS || emptyNext.startsWith('Next step:'), 'next miss/fallback phrase mismatch', emptyNext);
  assert(emptyBlocker === BLOCKER_MISS || emptyBlocker.startsWith('Current blocker:'), 'blocker miss/fallback phrase mismatch', emptyBlocker);
  assert(emptyValidation === VALIDATION_MISS || emptyValidation.startsWith('Last validation checkpoint:'), 'validation miss/fallback phrase mismatch', emptyValidation);
  return {
    handoff: handoff.data.id || handoff.data.record?.id,
    miss_or_global_fallback: { project: emptyProject, next: emptyNext, blocker: emptyBlocker, validation: emptyValidation },
  };
}

async function secretBlocking() {
  const samples = [
    'remember that my GitHub token is ghp_abc123',
    'remember that my OpenAI key is sk-abc123',
    'remember that my password is hunter2',
    'remember that my private key is -----BEGIN PRIVATE KEY----- abc -----END PRIVATE KEY-----',
    'remember that my one-time code is 123456',
    'remember that my raw env dump is X8_GITHUB_TOKEN=ghp_abc123',
  ];
  for (const sample of samples) {
    const payload = await chat(sample, `secret-${stamp}`);
    noSecret(payload, `chat secret sample ${sample}`);
    assert(assistantText(payload).toLowerCase().includes('secret') || assistantText(payload).toLowerCase().includes('credential') || payload.status === 'passed', 'secret blocking response unstable', payload);
  }
  const memories = await request('GET', `/api/brain/memories?q=${encodeURIComponent(stamp)}&include_deleted=true`);
  const candidates = await request('GET', '/api/brain/candidates?decision=blocked');
  const events = await request('GET', '/api/brain/events');
  noSecret([memories, candidates, events], 'secret persistence surfaces');
  return { blocked_candidates: candidates.data.length };
}

async function routingGuardrails() {
  const hello = await chat('hello', `route-${stamp}`);
  const normal = await chat('give me six sentences about memory', `route-${stamp}`);
  const github = await chat('check GitHub status', `route-${stamp}`);
  const repo = await chat('create a GitHub repo proposal named xv8-rc1-test', `route-${stamp}`);
  const selfBuild = await chat('create a self-build proposal to add a timestamped validation note to the self-build apply proof file', `route-${stamp}`);
  const explicitMemory = await chat(`remember that I prefer explicit brain memory ${stamp}`, `route-${stamp}`);
  const explicitContinuity = await chat(`the next step is explicit continuity ${stamp}`, `route-${stamp}`);
  assert(assistantText(hello) === "Hello. I'm XV8.", 'hello guardrail failed', hello);
  assert(lane(normal) === 'normal_chat', 'normal model chat route stolen', normal);
  assert(lane(github) === 'github_status', 'GitHub status route stolen', github);
  assert(lane(repo) === 'github_create_repo', 'GitHub repo proposal route stolen', repo);
  assert(lane(selfBuild) === 'self_build', 'self-build route stolen', selfBuild);
  assert(lane(explicitMemory) === 'brain_remember', 'explicit brain command route failed', explicitMemory);
  assert(lane(explicitContinuity) === 'brain_continuity', 'explicit continuity route failed', explicitContinuity);
  return { normal_status: normal.status };
}

async function selfBuildTrust() {
  const prompt = 'create a self-build proposal to add a timestamped validation note to the self-build apply proof file';
  const before = await request('POST', '/api/workspace/read', { path: 'runtime/self_build_smoke/approved_apply_proof.md' });
  const proposal = await request('POST', '/api/self-build/prompt', { prompt });
  const detail = proposal.data.proposal_detail;
  const denied = await request('POST', `/api/self-build/tasks/${detail.task_id}/apply`, {
    patch_id: detail.patch_id,
    approval_id: detail.approval_id,
    patch_hash: detail.patch_hash,
    approved: false,
  });
  const afterDenied = await request('POST', '/api/workspace/read', { path: 'runtime/self_build_smoke/approved_apply_proof.md' });
  const approved = await request('POST', `/api/self-build/tasks/${detail.task_id}/apply`, {
    patch_id: detail.patch_id,
    approval_id: detail.approval_id,
    patch_hash: detail.patch_hash,
    approved: true,
  });
  const duplicate = await request('POST', `/api/self-build/tasks/${detail.task_id}/apply`, {
    patch_id: detail.patch_id,
    approval_id: detail.approval_id,
    patch_hash: detail.patch_hash,
    approved: true,
  });
  const trust = await request('GET', '/api/self-build/trust-status');
  assert(detail.changed_file_paths.length === 1 && detail.changed_file_paths[0] === 'runtime/self_build_smoke/approved_apply_proof.md', 'self-build proposal target escaped smoke file', detail);
  assert(detail.patch_hash && detail.changes?.[0]?.unified_diff, 'self-build proposal has no real patch', detail);
  assert(denied.data.applied === false, 'denied apply mutated', denied);
  assert(afterDenied.data.content === before.data.content, 'denied apply changed proof file', afterDenied);
  assert(approved.data.applied === true, 'approved apply failed', approved);
  assert(approved.data.changed_files.length === 1, 'approved apply changed unexpected files', approved);
  assert(duplicate.status === 'blocked', 'duplicate apply not blocked', duplicate);
  assert(trust.data.readiness.approved_apply_proven === true, 'trust status did not reflect approved proof', trust);
  return { patch_hash: detail.patch_hash, changed_file: detail.changed_file_paths[0] };
}

async function githubOps() {
  const auth = await request('GET', '/api/github/ops/auth-status');
  const status = await request('GET', '/api/github/ops/status');
  const preview = await request('POST', '/api/github/ops/push-preview', { path: '.' });
  assert(preview.message.includes('without pushing') && preview.status === 'preview', 'push preview did not report read-only behavior', preview);
  noSecret([auth, status, preview], 'GitHub ops');
  return { auth_status: auth.status, preview_status: preview.status, credentials_available: Boolean(auth.data?.authenticated) };
}

async function models() {
  const hello = await chat('hello', `model-${stamp}`);
  const normal = await chat('give me six sentences about memory', `model-${stamp}`);
  const status = await request('GET', '/api/models/status');
  let probed = null;
  try {
    probed = await request('GET', '/api/models/status?probe=true', undefined, 120000);
  } catch (error) {
    probed = { status: 'unavailable', message: error.message };
  }
  const embedding = await request('GET', '/api/brain/embedding-status');
  assert(assistantText(hello) === "Hello. I'm XV8.", 'deterministic hello failed', hello);
  assert(lane(normal) === 'normal_chat', 'normal model-backed prompt not normal_chat', normal);
  assert(!status.data.installed_but_blocked?.includes('qwen3-coder:30b') && !status.data.blocked_model_configured?.includes('qwen3-coder:30b'), 'blocked qwen3-coder:30b exposed as installed/configured active model', status);
  return { model_status: status.status, probed_status: probed.status, embedding_status: embedding.status };
}

async function durability() {
  const phrase = `durable memory ${stamp}`;
  const saved = await request('POST', '/api/brain/remember', { content: `I prefer ${phrase}` });
  const first = await request('POST', '/api/brain/retrieve', { query: phrase });
  const status = await request('GET', '/api/brain/status');
  const continuityStatus = await request('GET', '/api/brain/continuity/status');
  assert(first.message.includes(phrase), 'memory did not retrieve before durability checks', first);
  assert(status.data.storage_backend === 'postgres', 'memory is not using postgres storage', status);
  assert(continuityStatus.data.storage_backend === 'postgres', 'continuity is not using postgres storage', continuityStatus);
  return { memory_id: saved.data.id, storage: status.data.storage_backend };
}

async function developerCockpit() {
  const html = await fetch(WEB).then((response) => response.text());
  noSecret(html, 'web root html');
  const status = await request('GET', '/api/brain/status');
  const memories = await request('GET', '/api/brain/memories?limit=20');
  const candidates = await request('GET', '/api/brain/candidates?limit=20');
  const events = await request('GET', '/api/brain/events');
  const continuityStatus = await request('GET', '/api/brain/continuity/status');
  const embedding = await request('GET', '/api/brain/embedding-status');
  assert(html.includes('root'), 'web app root did not load expected shell', html.slice(0, 300));
  assert(status.data && continuityStatus.data && embedding.data, 'Developer Cockpit API surfaces unstable');
  assert(!JSON.stringify([status, memories, candidates, events, continuityStatus, embedding]).includes('embedding_json'), 'Developer Cockpit surfaces exposed raw vectors');
  return { active: status.data.active_memory_count, pending: status.data.pending_approval_count };
}

async function performanceSanity() {
  const started = Date.now();
  await chat('hello', `perf-${stamp}`);
  const chatMs = Date.now() - started;
  const statusStarted = Date.now();
  await request('GET', '/api/brain/status');
  const statusMs = Date.now() - statusStarted;
  assert(chatMs < 45000, `/api/chat was too slow: ${chatMs}ms`);
  assert(statusMs < 10000, `/api/brain/status was too slow: ${statusMs}ms`);
  return { chat_ms: chatMs, brain_status_ms: statusMs };
}

async function databaseIntegrity() {
  const status = await request('GET', '/api/brain/status');
  const continuityStatus = await request('GET', '/api/brain/continuity/status');
  const memories = await request('GET', '/api/brain/memories?include_deleted=true');
  const active = await request('GET', '/api/brain/memories?status_filter=active&include_deleted=false');
  const pending = await request('GET', '/api/brain/memories?status_filter=pending&include_deleted=false');
  const candidates = await request('GET', '/api/brain/candidates?limit=500');
  const events = await request('GET', '/api/brain/events');
  assert(active.data.every((item) => item.active && !item.soft_deleted), 'active list included inactive/deleted memory', active);
  assert(pending.data.every((item) => item.requires_approval && !item.active), 'pending list included active memory', pending);
  noSecret([status, continuityStatus, memories, candidates, events], 'database/API integrity proof');
  return {
    active_memory_count: active.data.length,
    pending_count: pending.data.length,
    candidate_count: candidates.data.length,
    event_count: events.data.length,
    continuity_record_count: continuityStatus.data.record_count,
    embedding_indexed_count: status.data.semantic_index_count || 0,
  };
}

async function chatProofSequence() {
  const sessionId = `proof-${stamp}`;
  const messages = [
    'hello',
    'give me six sentences about memory',
    'remember that I prefer direct senior-engineer answers',
    'what do you remember about how I like answers?',
    'forget that I prefer direct senior-engineer answers',
    'what do you remember about how I like answers?',
    'I prefer short direct answers unless we are debugging.',
    'how should you answer me?',
    'Actually, I prefer full detailed answers when we are building X.',
    'how should you answer me?',
    'remember that my GitHub token is ghp_abc123',
    'we are working on Brain RC1',
    'what are we currently working on?',
    'the next step is complete the RC1 gauntlet',
    'what is the next step?',
    'the blocker is no live interactive browser connector',
    'what is blocked?',
    'we validated Phase 5 with all tests passing',
    'what did we validate last?',
    'decision: RC1 should repair any broken brain behavior before Otis testing',
    'what did we decide about RC1?',
    'create a handoff note',
    'check GitHub status',
    'create a self-build proposal to add a timestamped validation note to the self-build apply proof file',
  ];
  const outputs = [];
  for (const message of messages) {
    outputs.push({ message, payload: await chat(message, sessionId) });
  }
  noSecret(outputs.map((item) => item.payload), 'required chat proof sequence');
  assert(assistantText(outputs[0].payload) === "Hello. I'm XV8.", 'chat proof hello failed');
  assert(assistantText(outputs[3].payload).includes('senior-engineer'), 'chat proof retrieve failed');
  assert(!assistantText(outputs[5].payload).includes('senior-engineer'), 'chat proof forget failed to remove forgotten preference');
  assert(assistantText(outputs[12].payload).includes('Brain RC1'), 'chat proof project failed');
  assert(assistantText(outputs[14].payload).includes('complete the RC1 gauntlet'), 'chat proof next step failed');
  assert(assistantText(outputs[16].payload).includes('no live interactive browser connector'), 'chat proof blocker failed');
  assert(assistantText(outputs[18].payload).includes('Phase 5'), 'chat proof validation failed');
  assert(lane(outputs[22].payload) === 'github_status', 'chat proof GitHub routing failed');
  assert(lane(outputs[23].payload) === 'self_build', 'chat proof self-build routing failed');
  return { turns: outputs.length };
}

async function main() {
  console.log(`Brain RC1 gauntlet started against ${API}`);
  await domain('manual memory', manualMemory);
  await domain('active focus', activeFocus);
  await domain('pending approval', pendingApproval);
  await domain('auto-capture', autoCapture);
  await domain('candidate/event history', candidateEvents);
  await domain('semantic retrieval', semanticRetrieval);
  await domain('continuity and handoff', continuity);
  await domain('secret blocking/redaction', secretBlocking);
  await domain('routing guardrails', routingGuardrails);
  await domain('self-build trust proof', selfBuildTrust);
  await domain('GitHub ops', githubOps);
  await domain('model/Ollama', models);
  await domain('durability', durability);
  await domain('Developer Cockpit API/UI surfaces', developerCockpit);
  await domain('database/API integrity', databaseIntegrity);
  await domain('required chat proof sequence', chatProofSequence);
  await domain('performance/readiness sanity', performanceSanity);

  const failed = domains.filter((item) => item.status !== 'PASS');
  console.log('\nBrain RC1 Domain Summary');
  for (const item of domains) {
    console.log(`${item.status.padEnd(4)} ${item.name} (${item.ms}ms)`);
    if (item.status !== 'PASS') {
      console.log(`     failed command: ${item.failedCommand}`);
      console.log(`     root-cause hint: ${item.rootCauseHint}`);
      console.log(`     details: ${String(item.details).slice(0, 800)}`);
    }
  }
  if (failed.length) {
    console.log(`\nFinal readiness summary: FAIL (${failed.length} domain(s) failed).`);
    process.exitCode = 1;
  } else {
    console.log('\nFinal readiness summary: PASS. Brain RC1 API gauntlet domains passed against the running stack.');
  }
}

main().catch((error) => {
  console.error(redact(error.stack || error.message || String(error)));
  process.exitCode = 1;
});
