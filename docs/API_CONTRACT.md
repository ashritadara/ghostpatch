# API contract

Implemented FastAPI OpenAPI and interactive documentation: http://127.0.0.1:8000/docs.
Canonical backend schemas: backend/app/schemas.py. Frontend mirrors: frontend/types/api.ts.

This MVP adapts the old master plan's routes under the overriding autonomous instructions. Analysis happens during ingestion; activity uses polling rather than SSE.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | /api/health | Local configuration/Docker readiness; never prints the key or calls the model |
| POST | /api/model/check | Requires consent_to_model:true; small real final-answer connectivity check |
| POST | /api/repositories/upload | Multipart file ZIP; bounded safe extraction and static analysis; 201 RepositorySummary |
| POST | /api/repositories/import-git | JSON url; bounded public GitHub clone/static analysis; 201 RepositorySummary |
| POST | /api/repositories/sample | Copies the pinned built-in sample, grants internal execution trust; 201 RepositorySummary |
| GET | /api/repositories/{id} | RepositorySummary including analysis and explicit execution policy |
| GET | /api/repositories/{id}/diagnosis | Grounded static Analysis |
| DELETE | /api/repositories/{id} | Removes an idle owned snapshot and its in-memory records; 204 |
| POST | /api/repositories/{id}/plans | consent_to_model:true and objective (10?1000 chars); returns a pending Plan |
| POST | /api/plans/{id}/approve | approved:true; approves the exact stored plan |
| POST | /api/plans/{id}/execute | approved:true; requires prior approval; starts background job, 202 |
| GET | /api/jobs/{id} | Current Job, actual events, results, errors |
| GET | /api/jobs/{id}/events | Actual event array for polling |
| GET | /api/jobs/{id}/results | Final results; 409 while running |
| GET | /api/jobs/{id}/patch | Final .patch download, or 404 when no changes exist |

## Data and statuses

RepositorySummary contains id, name, file_count, trusted, execution_policy, and analysis. Analysis includes retained file paths, Python count, imports, local dependency edges, findings, and warnings. Findings cite file/line/evidence and heuristic severity; they are not verified vulnerabilities.

Plan contains its immutable proposal, one approved source path, and pending/approved state. The model proposal contains objective, one prioritized change, risks, and descriptive test strategy. Test strategy text never becomes a shell command.

Job statuses: queued, running, succeeded, failed, needs_review. Started/completed timestamps are UTC ISO 8601; event timestamps and statuses describe actual operations.

Results contain baseline, initial_modified, final modified validation, behavior_comparison, repairs, actual diffs, warnings, and verification (passed/failed/not_verified). The initial failing candidate is retained when repaired. Each repair preserves its own validation or rejection error.

TestRun reports status, fixed command description, actual exit code/duration, nullable parsed counts, stdout/stderr excerpts, behavior outputs, and an actionable reason when unavailable. Null counts do not mean zero failures. No tests executed cannot count as a pass.

Diffs contain repository-relative path, before/after source, and unified text. Export never applies the patch to the user's source repository.

## Errors and lifecycle

Errors use a detail string and an appropriate 400/403/404/409/413/422/429/502/503 status. Request-validation errors omit submitted input values. Model authentication, authorization, rate limiting, timeouts, empty/reasoning-only content, truncation, and invalid JSON produce actionable failures after bounded retries.

Approval and execution are separate calls. Retrying execute on the same approved plan returns the same job; it never starts a second execution. A follow-up execution requires a fresh completed re-evaluation and a newly approved plan; otherwise use a fresh repository snapshot. Poll reads can be retried; do not invent success after a dropped mutation response.

Only the pinned built-in samples execute. Consent is required before model source disclosure. Origin/Host checks supplement loopback binding, not authentication. Use only the documented local single-user deployment.

There are no cancellation, persisted final-review, merge, deployment, or rollback endpoints. Final UI review is explicitly session-only.

## Living Harness API additions (0.2)

Existing routes remain compatible. sample_id=claims_demo selects the new pinned fixture. Rules, signals, trials, investigation and report resources are described in [Living Software Harness](LIVING_HARNESS.md). PlanRequest adds intended_rule_changes; approval requires matching approved_rule_changes for semantic plans. Investigation revision changes invalidate stale plans. JobResults adds rulebook, signals and behavior_report; TestRun adds structured trial_outputs. These are additive fields; defaults preserve ordinary MVP requests.

## Continuous evaluation API additions (0.3)

Canonical additive schemas also live in backend/app/harness_schemas.py.

| Method | Route | Behavior |
| --- | --- | --- |
| POST | /api/repositories/{id}/signals | Existing event ingestion; adds observation_window, consent_to_model and reevaluate (default true) |
| POST | /api/repositories/{id}/signals/import | Existing pinned before/after import; adds consent_to_model and reevaluate |
| POST | /api/repositories/{id}/rules/policy-versions | Explicitly activate pinned fictional policy 1.0/1.1; queue existing Trials |
| GET | /api/repositories/{id}/trials/reevaluations | Bounded queue/history with triggers, tool IDs, policy, evidence, status and approval state |
| POST | /api/repositories/{id}/trials/reevaluations | Process existing queued records once; optional consent_to_model |
| GET | /api/repositories/{id}/trials/reevaluations/{evaluation_id} | Record plus its saved Behavior Preservation Report, or 404 |

Example ingestion (synthetic only; one row alone is insufficient for drift):

~~~json
{
  "dataset_version": "before-v1",
  "observation_window": {"start":"2026-11-01T00:00:00Z","end":"2026-11-03T00:00:00Z"},
  "consent_to_model": false,
  "reevaluate": true,
  "events": [{
    "event_id":"ev_00000001",
    "session_id":"s_00000001",
    "user_id":"u_00000001",
    "timestamp":"2026-11-01T09:00:00Z",
    "software_version":"legacy-v1",
    "policy_version":"1.0",
    "workflow":"eligibility",
    "action":"submit",
    "outcome":"rejected",
    "rule_context":["rule-age-eligibility"],
    "synthetic":true,
    "metadata":{"age_band":"at_threshold"}
  }]
}
~~~

Event user_id/software_version/policy_version are optional and backward-compatible. IDs follow u_/s_ plus 8-16 hexadecimal digits; event IDs use ev_ plus 8-24 digits. Software versions are restricted to legacy-v1, candidate-v2, policy-v3; reported policy versions to 1.0/1.1. Timestamp must have a timezone and is normalized to UTC. Observation windows have an exclusive end and span at most 31 days. Missing identities/windows never produce invented user retention. Unknown/sensitive fields are rejected. At most 500 unique events and 128 KiB per event batch; conflicting duplicate IDs, changed existing windows and session identity switches are rejected. Adding missing window metadata to existing events recomputes eligibility and may queue once.

Pinned imports:

~~~json
{"dataset":"before","consent_to_model":true,"reevaluate":true}
~~~

Repeat with dataset after. Setting reevaluate:false defers processing, not detection/queueing. Process later with POST trials/reevaluations and {"consent_to_model":false}. Background processing returns before completion on a real HTTP server; poll GET investigation or reevaluations until no records are queued/running. completed means the tools finished; report_status may still be failed. suggested_only means no execution for an untrusted repository.

Explicit policy activation:

~~~json
{"version":"1.1","approved":true,"approved_rule_ids":["rule-age-eligibility"],"consent_to_model":true}
~~~

Only the pinned claims demo and exactly that known rule are accepted. Repeating the active version is idempotent. Policy approval never approves a code edit. Queue exhaustion rejects a new policy update with 429; further signal findings remain visible with an explicit budget warning.

Signals responses add windows with availability/cohort/version/time fields, drifts, competing explanations and reevaluations. Memory adds policy_version, histories and investigations. Reports add trigger records, policy version, tool evidence and approval state. No raw events or IDs are returned in aggregate reports.

After a completed job, event ingestion/policy approval remain available when idle. A fresh completed re-evaluation requiring human action enables a new plan. It must pass the existing plan/approve/execute gates with the exact intended_rule_changes/approved_rule_changes. Plan adds policy_version, trigger_id and source_hashes; results add baseline_kind (original or previous_working_copy). Per-job patch/evidence downloads are immutable across follow-up jobs. All IDs remain temporary; earlier artifacts are accessible only while the local records/workspace exist.
