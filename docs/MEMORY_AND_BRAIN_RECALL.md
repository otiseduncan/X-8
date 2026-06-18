# XV8 Memory and Brain Recall

XV8 separates memory from seeded knowledge, verified runtime status, research, session context, preferences, and attachments.

Memory records are typed, source-labeled, and status-gated. New memories are not mass-saved from chat. Explicit user memory requests and high-confidence explicit facts may become active; uncertain corrections and legacy records remain pending for click approval.

Default model wiring:

- Main chat: `qwen3:8b`
- Reasoning: `qwen3:14b`
- Fallback chat: `qwen3:1.7b`
- Code/dev: `qwen3:8b`
- Embeddings: `nomic-embed-text:latest`

Blocked model:

- `qwen3-coder:30b` may be installed on the host, but XV8 must report it as installed-but-blocked and never select it for chat, code, reasoning, or background work.

Memory readiness requires the embedding model and vector store readiness. Basic chat does not require memory readiness.

Compose includes `x8-qdrant` under the `memory` profile as the planned durable vector store. Memory code uses a `VectorStoreAdapter` boundary so the runtime can move between local development storage and Qdrant without mixing vector logic into memory policy.

Kernel context order:

1. system identity
2. active user message
3. session summary
4. attachments
5. active preferences
6. relevant active memory
7. relevant seeded knowledge
8. verified status
9. research when requested
10. tool capability snapshot

When semantic recall is unavailable, XV8 may use bounded keyword recall and records a limitation. If memory is unavailable, receipts must say why instead of inventing recall.
