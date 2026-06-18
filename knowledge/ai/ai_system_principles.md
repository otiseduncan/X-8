# AI System Principles

- Route local LLMs by capability and availability, not wishful labels.
- Treat Ollama-compatible providers as optional until health checks prove them live.
- Keep prompt layers explicit: system, developer, tool, memory, knowledge, verified status.
- Separate memory from seeded knowledge and live proof.
- Tool calling requires typed requests, results, receipts, and approval gates.
- Receipts should state what actually happened and what did not.
- Hallucination control starts with capability truth and source-aware responses.
- Evals and gauntlets must be repeatable and Docker-only.
- Fallback behavior should be honest, useful, and explicit.
- Code-assistant workflows should inspect, plan, propose, request approval, apply, test, and receipt.
