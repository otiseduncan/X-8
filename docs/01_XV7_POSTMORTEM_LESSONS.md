# XV7 Postmortem Lessons

XV7 is paused, not continued. It remains useful as a warning map.

## Observed Risks

- Central files grew too large: `public/app.js`, `core/main.py`, and `core/brain/answer_contract.py` exceeded healthy maintenance limits.
- Routing, response contracts, artifact behavior, and runtime proof became intertwined.
- Browser/runtime truth could blur with local assumptions.
- Website preview, revision, and export flows risked drifting when state was re-inferred.
- Tests became large enough to hide behavior instead of clarifying it.

## XV8 Responses

- Enforce file limits with `scripts/check_file_size.py`.
- Keep app entrypoints thin.
- Split contracts, managers, services, adapters, and routes.
- Make capability state explicit: implemented, disabled, stubbed, unavailable, or blocked.
- Treat receipts and evidence as first-class runtime objects.
- Keep artifact preview separate from repo mutation.
- Require approval before writes, shell mutation, Docker mutation, remote access, email, or SMS.
