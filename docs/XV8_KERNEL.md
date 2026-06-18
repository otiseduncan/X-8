# XV8 Kernel

The XV8 kernel is the stable orchestration path for chat turns.

Current flow:

1. `POST /api/chat` persists the user message and resolves attachment records.
2. The route creates a versioned `KernelRequest`.
3. `XV8Kernel` classifies the lane, applies the safety gate, assembles brain context, selects a model, calls the model router, normalizes cards, and creates a receipt.
4. The route persists the assistant message and kernel receipt metadata.

Context boundaries:

- Memory: reserved for remembered facts. If unavailable, the receipt says so.
- Knowledge: seeded local knowledge files from `knowledge/`.
- Verified Status: only live proof produced by runtime/status endpoints.
- Research: only current search results from approved search paths.
- Preferences: approved working preferences.
- Session Context: recent session messages and attachments.
- Attachments: extracted attachment text under configured character caps.

Extension rules:

- New capabilities register through `CapabilityRegistry` or `ExtensionRegistry`.
- Mutating capabilities must pass through `SafetyGate` and approval.
- Slow work should return a versioned job/card contract instead of blocking chat.
- Kernel files should stay small. Split instead of growing a monolith.
- Optional service failures must degrade, not break basic chat.

Versioned contracts:

- Kernel: `kernel.v1`
- Context bundle: `context.v1`
- Cards: `card.v1`
- Receipts: `receipt.v1`
- Tools/jobs: `tool.v1`
