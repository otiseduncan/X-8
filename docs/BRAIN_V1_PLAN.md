# Brain V1 Implementation Plan

## Executive Summary

Brain V1 should turn XV8 from a project-only assistant into a day-to-day AI assistant that can remember useful, safe, user-approved facts across sessions without confusing memory, knowledge, verified status, research, or current chat context.

The existing codebase already has the right scaffold:

- `POST /api/chat` persists sessions/messages/receipts through `PostgresStore`, then routes through `XV8Kernel`.
- `BrainContextAssembler` already separates session context, attachments, memory, seeded knowledge, preferences, verified status, research limitations, and prompt input.
- `MemoryManager` already has typed records, status gates, secret-pattern blocking, approval flows, keyword recall fallback, and a `VectorStoreAdapter` boundary.
- The web app already shows memory readiness in `InfoDropdown` and `DeveloperCockpit`, but does not yet provide a full memory review/edit/search workflow.

Brain V1 should therefore be a narrow extension of the existing kernel/store/receipt path. It should not introduce a competing chat pipeline or raw memory dumping. The first build should move durable memory into Postgres, preserve the existing context boundaries, add manual remember/forget/search workflows, and only then add auto-capture.

## Current Architecture Read

### Chat And Kernel Flow

Current chat flow:

1. `apps/api/src/x8/api/routes/chat.py` receives `ChatRequest`.
2. `PostgresStore` creates or updates a session.
3. User message and attachment links are persisted.
4. `XV8Kernel.handle()` receives a `KernelRequest`.
5. `ResponsePlanner`, `SafetyGate`, `KernelContextAssembler`, `ModelRouter`, and `KernelReceiptBuilder` produce the assistant response and receipt.
6. Assistant message, cards, and prompt receipt metadata are persisted.

Brain V1 should stay inside this flow. Retrieval should happen during context assembly, writes should be surfaced through memory-specific managers and routes, and every memory-impacting action should produce receipts.

### Storage

`apps/api/src/x8/storage/postgres_store.py` currently owns tables for:

- `sessions`
- `messages`
- `attachments`
- `message_attachments`
- `receipts`
- `model_status_checks`

`apps/api/src/x8/managers/memory_manager.py` currently stores memory records in a local JSON file at `settings.memory_storage_path`. Brain V1 should promote memory records to Postgres while keeping import/export compatibility with the existing JSON structure for migration and rollback.

### Settings

Relevant settings already exist in `apps/api/src/x8/settings.py`:

- `memory_enabled`
- `memory_activation_mode`
- `embedding_required_for_memory`
- `embedding_required_for_basic_chat`
- `embedding_model`
- `vector_collection_memory`
- `memory_storage_path`
- `context_max_memory_items`

Brain V1 should add only explicit, narrowly named settings as needed, such as `memory_auto_capture_enabled`, `memory_auto_capture_default`, `memory_context_max_chars`, and `memory_sensitive_approval_required`.

### Existing Memory Manager

Current `MemoryManager` concepts to preserve:

- Typed records: `user_profile`, `user_preference`, `project_fact`, `workflow_preference`, `assistant_behavior_rule`, `technical_environment`, `model_configuration`, `tool_configuration`, `design_preference`, `voice_avatar_preference`, `verified_status_pointer`.
- Statuses: `pending`, `approved`, `active`, `superseded`, `deleted`, `rejected`.
- Sources: `user_explicit`, `user_correction`, `legacy_import_x7`, `legacy_import_x6`, `runtime_observation`, `verified_status`, `manual_admin`.
- Secret-like text is blocked.
- Active memory can be recalled into `BrainContextAssembler`.
- Semantic recall can be unavailable; keyword fallback must report the limitation.

Brain V1 should expand this into a durable memory system, not weaken the safety model.

### UI Surfaces

Current web surfaces:

- `App.tsx` owns chat, local history, status loading, attachments, speech, and developer cockpit toggles.
- `AssistantComponents.tsx` owns timeline, message cards, history, info dropdown, receipts, avatar/audio controls.
- `DeveloperCockpit.tsx` has a compact Memory panel showing status, embedding readiness, vector readiness, pending count, active count, and reason.
- `apiClient.ts` already exposes `loadMemoryStatus()` and `loadMemoryRecords()`.

Brain V1 UI should extend these surfaces with a proper memory drawer/panel instead of hiding all memory control in raw API responses.

## Brain V1 Architecture

Brain V1 should be split into five small backend units:

1. `MemoryStore`: Postgres-backed CRUD, status transitions, audit references, and JSON import/export.
2. `MemoryPolicyManager`: save/ask/never-save classification, secret blocking, sensitive-topic gating, retention defaults, and record eligibility.
3. `MemoryCaptureManager`: explicit "remember this" handling and later auto-capture proposal generation.
4. `MemoryRetrievalManager`: bounded retrieval across keyword, filters, recency, priority, and later vector search.
5. `BrainContextAssembler`: existing prompt-context bridge, updated to consume structured retrieval results with receipts.

The API route should remain `/api/memory/*` and grow into `/api/brain/*` only if a broader non-memory Brain status route is needed. For V1, "brain" can be the product name while memory remains the storage and API domain.

## Memory Layers

Brain V1 should model layers explicitly so day-to-day assistance does not become project-only memory.

| Layer | Purpose | Example | Default Save Policy |
| --- | --- | --- | --- |
| User profile | Stable user facts useful for assistance | "Otis works on local Windows repos." | Ask unless explicitly stated as rememberable |
| Communication preferences | Response shape and tone | "Use Result / Evidence / Next action for validation." | Auto-save from direct preference statements |
| Workflow preferences | How the user wants work done | "Inspect first, then make narrow patches." | Auto-save from direct preference statements |
| Project facts | Durable facts about a repo/project | "XV8 runs under Docker Compose." | Auto-save when verified or explicit |
| Active project state | Current task/session pointers | "Latest active proposal hash is..." | Never as durable memory; store as session/receipt pointer |
| Technical environment | Local setup facts | "Workspace is X:\X 8." | Ask or save if verified and low risk |
| Tool configuration | Non-secret tool setup | "GitHub owner is otiseduncan." | Ask; never store token values |
| Design preferences | UI/UX tastes | "Prefer dense operational tools over marketing layouts." | Auto-save from direct preference statements |
| Voice/avatar preferences | Speech and presence settings | "Prefer US Google female voice." | Auto-save if user-facing and non-sensitive |
| Relationship/personal-sensitive memory | Family, health, identity, finances, relationships | "Remember my family history..." | Block by default; require explicit approval and category review |
| Verified-status pointers | References to proof, not the proof itself | "Receipt rcpt_123 proved model status on date." | Save compact pointers only; do not treat as current truth |

## Self-Learning Policy

Brain V1 must optimize for useful memory without creepy or unsafe retention.

### Auto-Save

Auto-save only when all conditions are true:

- The statement is clear, low-risk, and likely useful later.
- The user directly states a preference, workflow rule, project fact, or visible setting.
- The content does not contain secrets, credentials, private keys, tokens, service account JSON, passwords, or sensitive personal categories.
- The record can be summarized compactly.
- The assistant can create a receipt explaining why it was saved.

Examples:

- "Prefer concise answers."
- "Use PowerShell in this repo."
- "This project uses Docker-only validation."

### Ask Before Saving

Ask before saving when content is useful but sensitive, ambiguous, personal, durable, or high-impact.

Examples:

- Health, legal, financial, family, relationship, identity, location, employer, or security-sensitive facts.
- "Remember this client detail."
- "Remember my API setup" when the setup may include secrets.
- Any inferred preference that was not directly stated.

### Never Save

Never save:

- API keys, tokens, passwords, private keys, session cookies, service-account JSON, seed phrases, credentials, or `.env` values.
- Raw attachments, logs, receipts, transcripts, or whole files.
- Current runtime status as permanent truth.
- Unverified claims about external systems.
- Hidden chain-of-thought or internal reasoning.
- Background observations not relevant to helping the user.

### Receipts

Every memory write, rejection, approval, deletion, supersession, and retrieval injection should produce a compact receipt with:

- action
- status
- memory IDs affected
- source
- policy decision
- context injection count
- limitations

## Persistent Schema

Add Postgres tables through the existing `PostgresStore.ensure()` pattern or a small migration layer if the repo adopts migrations before implementation.

### `memory_records`

Fields:

- `memory_record_id TEXT PRIMARY KEY`
- `memory_type TEXT NOT NULL`
- `status TEXT NOT NULL`
- `source TEXT NOT NULL`
- `scope TEXT NOT NULL DEFAULT 'global'`
- `project_key TEXT NOT NULL DEFAULT ''`
- `title TEXT NOT NULL DEFAULT ''`
- `text TEXT NOT NULL`
- `summary TEXT NOT NULL DEFAULT ''`
- `sensitivity TEXT NOT NULL DEFAULT 'low'`
- `confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5`
- `priority INTEGER NOT NULL DEFAULT 50`
- `source_session_id TEXT`
- `source_message_id TEXT`
- `source_receipt_id TEXT`
- `source_path TEXT NOT NULL DEFAULT ''`
- `supersedes TEXT NOT NULL DEFAULT ''`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`
- `last_used_at TIMESTAMPTZ`
- `expires_at TIMESTAMPTZ`
- `embedding_id TEXT NOT NULL DEFAULT ''`
- `metadata_json TEXT NOT NULL DEFAULT '{}'`

Indexes:

- `(status, memory_type)`
- `(scope, project_key, status)`
- `(updated_at DESC)`
- `(last_used_at DESC)`
- text search index on `text` and `summary`

### `memory_events`

Append-only audit trail:

- `memory_event_id TEXT PRIMARY KEY`
- `memory_record_id TEXT`
- `event_type TEXT NOT NULL`
- `status TEXT NOT NULL`
- `receipt_id TEXT`
- `actor TEXT NOT NULL DEFAULT 'assistant'`
- `summary TEXT NOT NULL`
- `metadata_json TEXT NOT NULL DEFAULT '{}'`
- `created_at TIMESTAMPTZ NOT NULL`

### `memory_retrievals`

Compact proof for prompt injection:

- `retrieval_id TEXT PRIMARY KEY`
- `session_id TEXT`
- `message_id TEXT`
- `query TEXT NOT NULL`
- `selected_ids_json TEXT NOT NULL DEFAULT '[]'`
- `candidate_count INTEGER NOT NULL DEFAULT 0`
- `injected_count INTEGER NOT NULL DEFAULT 0`
- `limitations_json TEXT NOT NULL DEFAULT '[]'`
- `created_at TIMESTAMPTZ NOT NULL`

## Retrieval Design

Retrieval should stay bounded and explainable.

Ranking inputs:

- exact command intent, such as "what do you remember"
- memory type match
- scope match: global, project, repo path, session
- keyword match
- vector similarity when available
- recency
- priority
- confidence
- not expired
- not superseded/deleted/rejected

Context injection rules:

- Inject only active eligible records.
- Default to a small cap by count and character budget.
- Include memory type, source, confidence, and compact text.
- Never inject raw sensitive records unless the user directly asks and the record is approved for reveal.
- Verified-status pointers must be labeled as pointers, not current proof.
- If retrieval is unavailable, receipt says why.

Natural language commands:

- "remember that..."
- "remember this preference..."
- "what do you remember about me?"
- "what do you remember about this project?"
- "forget that..."
- "delete this memory"
- "show pending memories"
- "approve this memory"
- "do not remember that"
- "turn memory off for this chat"

## API Plan

Keep response shape as `ResultEnvelope` and include receipts.

Routes:

- `GET /api/memory/status`
- `GET /api/memory/records?status=&type=&scope=&q=`
- `POST /api/memory/records`
- `PATCH /api/memory/records/{memory_record_id}`
- `POST /api/memory/records/{memory_record_id}/approve`
- `POST /api/memory/records/{memory_record_id}/reject`
- `POST /api/memory/records/{memory_record_id}/delete`
- `POST /api/memory/records/{memory_record_id}/supersede`
- `POST /api/memory/search`
- `GET /api/memory/retrievals?session_id=`
- `GET /api/memory/policy`
- `PATCH /api/memory/policy`

Request contracts:

- `MemoryCreateRequest`: type, text, scope, project_key, source, confidence, source pointers.
- `MemoryUpdateRequest`: title, text, status, priority, expires_at, metadata.
- `MemorySearchRequest`: query, limit, scope, project_key, include_pending=false.
- `MemoryPolicySettings`: auto_capture_enabled, ask_sensitive, max_context_items, max_context_chars.

## UI Plan

### Assistant Mode

Add lightweight, user-facing memory controls without turning the chat into an admin console:

- Memory status in Info dropdown with active/pending counts.
- Inline memory receipt card after save/forget/approve actions.
- A "Memory used" disclosure on assistant messages when records were injected.
- Plain-language responses for memory questions with compact source pins, not raw record dumps.

### Developer Cockpit

Replace the current compact Memory status-only panel with a functional Brain/Memory panel:

- Status row: enabled, embedding, vector, active, pending.
- Search input and filters.
- Active records list.
- Pending approvals list.
- Record detail drawer with edit, approve, reject, delete, supersede.
- Policy toggles: memory enabled, auto-capture enabled, ask before sensitive memory, context cap.
- Retrieval proof: latest injected record IDs and limitations.

### UX Rules

- Do not show secrets even if blocked content was submitted.
- Do not bury approval-required memory in receipts only.
- Do not make memory feel automatic for sensitive personal facts.
- Do not present old verified-status pointers as current runtime truth.

## Tests

Add focused tests before adding broad behavior:

1. Postgres memory table creation is idempotent.
2. Explicit remember creates an active low-risk record with a receipt.
3. Secret-like memory is blocked and not persisted.
4. Sensitive memory creates a pending proposal requiring approval.
5. Approval changes pending to active and records an event.
6. Reject keeps the record out of retrieval.
7. Delete marks deleted without hard-deleting audit history.
8. Supersede marks the old record superseded and retrieves only the new record.
9. Retrieval excludes pending, rejected, deleted, superseded, and expired records.
10. Retrieval respects count and character caps.
11. Verified-status pointers are injected as pointers only.
12. Brain context reports memory unavailable honestly when dependencies are down.
13. Chat "what do you remember" returns a compact summary, not raw JSON.
14. UI memory panel renders status, pending count, and active count.
15. UI approve/reject/delete actions call the correct API routes.
16. E2E: user says "remember that I prefer concise responses", then a later chat uses that memory and shows a memory-used proof.
17. E2E: user submits secret-like content and the UI shows blocked memory with no stored secret.

## Implementation Batches

### Batch 1: Durable Manual Memory

Scope:

- Add Postgres-backed memory tables and store methods.
- Preserve existing JSON memory import/export as a compatibility path.
- Add manual create/search/list/approve/reject/delete routes.
- Keep auto-capture disabled.
- Keep vector search optional; keyword search is acceptable with an honest limitation.
- Update `BrainContextAssembler` to use the new store through `MemoryManager`.
- Add API tests for schema, policy, manual memory, and context injection.

Do not implement:

- automatic memory capture
- embeddings/Qdrant dependency changes
- UI redesign
- external migrations beyond the repo's chosen storage pattern

### Batch 2: Memory UI Control Surface

Scope:

- Add Brain/Memory panel to Developer Cockpit.
- Add active/pending/search/detail views.
- Add approve/reject/delete/supersede controls.
- Show compact memory receipts in chat.
- Add web tests for rendering and actions.

### Batch 3: Natural Language Memory Commands

Scope:

- Route "remember", "forget", "what do you remember", and approval commands through `ResponsePlanner`.
- Return compact summaries with source pins.
- Add deterministic miss language for no matching memory.

### Batch 4: Safe Auto-Capture Proposals

Scope:

- Add low-risk auto-save for direct preferences.
- Add ask-before-save prompts for sensitive or inferred facts.
- Add a policy settings route and UI toggles.
- Add tests for auto-save/ask/never-save boundaries.

### Batch 5: Semantic Retrieval

Scope:

- Wire `VectorStoreAdapter` to the durable vector backend.
- Use embeddings only when ready.
- Store vector IDs separately from source records.
- Preserve keyword fallback and limitations.

### Batch 6: Lifecycle And Maintenance

Scope:

- Add expiration, last-used updates, archive/export, dedupe, merge, and maintenance receipts.
- Add compact "memory health" diagnostics.
- Add migration/report tooling for legacy memory candidates.

## Risk List

- Over-saving personal or sensitive data.
- Treating runtime status or old receipts as current truth.
- Context flooding that makes answers worse or leaks irrelevant data.
- Duplicating memory, knowledge, preferences, and verified status.
- Storing secrets despite UI redaction.
- Creating hidden behavior users cannot inspect.
- Breaking basic chat when memory/vector dependencies are unavailable.
- Auto-capture saving inferred facts the user never endorsed.
- UI exposing raw records when compact summaries are more appropriate.
- Schema drift between JSON memory and Postgres memory during transition.

## Open Questions

- Should global day-to-day memory and project-specific memory share one table with `scope`, or should project memory have a separate view/table?
- Which sensitive categories should be completely blocked versus approval-gated?
- Should explicit "remember" from Otis auto-activate all non-secret records, or should personal categories still require confirmation?
- Should memory be disabled per chat, per project, globally, or all three?
- What exact deterministic miss phrase should XV8 use when no matching memory exists?
- Should legacy X6/X7 candidates stay pending forever until reviewed, or should there be a bulk archive path?
- Should memory export be plain JSON, redacted JSON, markdown summary, or all three?

## Recommended Batch 1 Build Prompt

Use this prompt for the first implementation batch:

```text
Implement Brain V1 Batch 1 only in X:\X 8.

Scope:
- Add durable Postgres-backed memory storage for manual memory records, memory events, and retrieval proof using the existing storage/manager/ResultEnvelope/Receipt patterns.
- Preserve the existing MemoryManager policy concepts: typed records, status gates, source labels, secret-like content blocking, approval flow, keyword recall fallback, and honest limitations.
- Keep auto-capture disabled.
- Do not add embeddings or Qdrant dependency work yet.
- Do not redesign the frontend yet, except for any tiny API-client additions needed by tests.
- Update BrainContextAssembler to retrieve active eligible memory through the new store path and keep memory, knowledge, preferences, verified status, attachments, and session context separate.
- Add focused API tests for schema creation, explicit remember, secret blocking, approval/reject/delete, retrieval eligibility, context caps, and unavailable-memory receipts.

Rules:
- Do not commit.
- Do not push.
- Do not migrate or import legacy records automatically.
- Do not store secrets, tokens, passwords, private keys, service-account JSON, raw receipts, raw transcripts, or raw attachments as memory.
- Report exact files changed and validation commands run.
```
