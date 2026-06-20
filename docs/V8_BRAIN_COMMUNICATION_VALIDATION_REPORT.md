# V8 Brain Communication Validation Report

## 1. Executive result: PASS

XV8 passed the focused brain/communication gauntlet and the required full validation after repair.

## 2. Input-sensitive or keyword-template driven

Result: input-sensitive for the tested communication surface.

Evidence:
- `Build a website preview only. Do not write files.` routes to `artifact_preview` and reports no write.
- `Create a project that includes README.md using your Project Builder...approve...sandbox` routes to `project_builder`, not README/file viewer.
- `Open README.md` still routes to `repo_inspection`.
- Prior correction context changes later `generate website` versus `build/write/create` behavior.
- Relevant memory changes UI guidance; irrelevant memory is ignored.

## 3. Communication failures found

- Chat responses did not expose the requested structured Decision Trace object.
- File-backed memory context retrieval used only prior session messages, not the current prompt.
- Broad UI/style questions did not retrieve a saved UI style preference.
- Decision trace initially echoed token-shaped content in `user_input_summary`.

## 4. Brain/memory failures found

- Current-input memory recall was missing for the kernel context assembler.
- Relevant style preference recall was too strict for broad UI/dashboard wording.
- Secret hygiene failed until the new decision trace summary was redacted.

## 5. Repairs implemented

- Added `decision_trace` to chat responses.
- Added required trace fields: route, speech act, constraints, memory metadata, active focus, overrides, capability checks, safety boundary, fallback metadata, final response type, and receipt linkage.
- Added current-message memory retrieval in `BrainContextAssembler`.
- Added style-preference bridge for broad UI/dashboard questions in file-backed memory search.
- Added `artifact_preview` routing for preview-only website requests.
- Preserved Project Builder precedence over README mentions for approved sandbox builds.
- Redacted secret-like content from trace summaries/fallback fields.

## 6. Decision trace fields added or verified

Verified fields:
`message_id`, `user_input_summary`, `detected_speech_act`, `selected_route`, `route_confidence`, `input_constraints_detected`, `memories_retrieved`, `memories_used`, `memories_rejected`, `active_focus_used`, `current_instruction_overrides`, `capability_status_checked`, `action_selected`, `safety_boundary_applied`, `fallback_used`, `fallback_reason`, `final_response_type`, `receipt_id`.

## 7. Tests added

- Decision trace contract coverage in `tests/test_chat_truth_contracts.py`.
- Input-sensitivity route tests for preview/write/README.
- Memory influence and memory non-use tests.
- Correction/adaptation tests for generate-preview versus build-sandbox behavior.
- Current-instruction override and safety-boundary trace tests.
- Frontend intent routing regression for Project Builder versus README.
- E2E regression for ADAS Project Builder prompt not opening README.

## 8. Validation commands run

- `docker compose run --rm api-tests pytest tests/test_chat_truth_contracts.py -q`
- `docker compose run --rm api-tests pytest tests/test_brain_v1_contracts.py::test_secret_auto_capture_is_blocked_and_redacted tests/test_brain_v1_contracts.py::test_phase5_auto_capture_and_secret_blocking_do_not_steal_guarded_routes -q`
- `docker compose run --rm api-tests`
- `docker compose run --rm web-tests`
- `docker compose run --rm e2e-tests`

## 9. Pass/fail results

- Focused communication tests: PASS, 16 passed.
- Secret redaction focused regression: PASS, 2 passed.
- Full API suite: PASS, 162 passed, 1 warning.
- Full web suite: PASS, 48 passed.
- Full E2E suite: PASS, 16 passed.

## 10. Examples where input changed route/action

- Preview-only website request selected `artifact_preview`, action `artifact.preview`, no file write.
- Approved sandbox Project Builder request selected `project_builder`, action `project_builder.write_sandbox`.
- `Open README.md` selected `repo_inspection`, action `workspace.read`.

## 11. Examples where memory influenced behavior

- Saved memory: dark UI with red/cyan accents and compact receipts.
- Later UI/dashboard question returned a style decision using that preference without dumping the raw memory record format.

## 12. Examples where memory was correctly ignored

- Irrelevant memory about a non-project preference did not alter the deterministic identity answer.

## 13. Examples where current instruction overrode memory

- Prompt containing old-memory preview behavior plus `For this one, I approve writing directly to sandbox` records `current_instruction_overrides_memory` and `explicit_sandbox_approval` in the decision trace.

## 14. Remaining risks

- Decision traces are compact metadata, not full causal proofs.
- File-backed memory and Postgres Brain V1 memory are still separate context paths.
- Some normal chat behavior still depends on deterministic fallback when Ollama is unavailable.
- Broad semantic generalization remains bounded by current retrieval heuristics and available model/capability state.

## 15. Manual checks still recommended

- Inspect a live chat response JSON for `decision_trace`.
- Try several novel ambiguous prompts in the browser and confirm the trace route matches the visible response.
- Review the UI presentation of trace metadata if it should become a dedicated debug panel instead of API-visible metadata only.
