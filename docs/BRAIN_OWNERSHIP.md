# X8 Brain Ownership Contract

Normal conversation memory source: Open Web UI.

X8 deterministic state source: receipts, audit events, approvals, workspace write proof, and protected-action records.

Rules:

1. Normal chat must use the configured brain provider.
2. A kernel identity string is not model-readiness proof.
3. X8 must report provider failures exactly: unreachable service, bad auth, empty model catalog, missing selected model, or failed completion.
4. X8 may store operator receipts and audit records.
5. X8 must not silently create a second conversational memory source unless the operator approves that design change.
