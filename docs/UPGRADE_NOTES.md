# Living Software Harness upgrade


## Continuous extension verification (0.3, current)

The earlier 0.2 results below describe the previous upgrade. This section records the continuous-evaluation extension.

Changed existing production files: app/harness_schemas.py (additive contracts), signals.py (cohorts/drift/explanations), memory.py (pinned evolving policy/history), harness.py (bounded queue/evaluation/grounding), main.py (additive endpoints), model.py (bounded grounded investigation), orchestrator.py (fresh approved follow-ups/repair authorization), schemas.py/store.py/patcher.py/runner.py (frozen internal baselines and immutable job exports). The existing runner/check.py adapter is reused. The existing frontend page, evidence component and shared DTOs expose these results with basic controls. No new production feature module, service, database, dashboard or dependency family was added.

The synthetic claims fixtures now include optional user/version metadata and explicit two-day windows, plus independently pinned optional policy 1.1. Claims implementation and its six legacy tests were preserved. Manifest changes are intentional. Added focused continuous unit/API tests and an opt-in real case in test_upgrade_live.py. Extended the existing scripts/verify_upgrade.py rather than introducing another feature.

Actual checks:

- Full suite with GHOSTPATCH_RUN_INTEGRATION=1, GHOSTPATCH_RUN_UPGRADE_INTEGRATION=1 and GHOSTPATCH_RUN_CONTINUOUS_INTEGRATION=1: **100 passed**, one existing Starlette/httpx deprecation warning, 174.99 seconds. This includes all six real-service checks.
- The default unit/API suite at the earlier checkpoint: 91 passed, 6 opt-in skipped. Three additional focused tests were then added and passed in the full 100-test suite.
- Final authorization/repair feedback check after limiting repair payloads to actionable failures: **11 passed**, 3.65 seconds.
- Real existing expense-report modernization, public GitHub import, Docker regression detection/restoration, prior Memory/Signals/Trials demo, and the new repeated-evaluation workflow passed.
- Real continuous case: initial age-65 mismatch independently exposed despite six passing existing tests; approved policy-1.0 patch succeeded; policy-1.1 approval re-evaluated unchanged candidate and found a discrepancy; separately approved follow-up succeeded against a frozen previous working copy. Final 11 preserved / 2 intended changes / 0 unexpected divergences / 0 unverified / 0 execution errors; zero repairs required. Prior patch/evidence bytes and immutable original were checked unchanged. Scenario counts vary with validated model proposals.
- Frontend ESLint, production build and TypeScript checks passed. Local frontend HTTP returned 200; backend OpenAPI reports 0.3.0. No browser automation was used.
- Source credential-pattern audit: 73 selected source/documentation files, zero matches for checked NVIDIA/OpenAI credential and private-key patterns. This is a bounded pattern check, not a guarantee. Existing .env, venv, frontend local config and runtime evidence are ignored. Original sibling frontend Git status remains clean.

The real model initially returned a hypothesis whose source/evidence grounding was rejected. Exact reference options, a known evidence catalog and one bounded correction request improved reliability while preserving validation. Invalid results remain visibly failed with deterministic fallback. The suite also covers missing identities/windows, incompatible workflows/versions/durations, conflicting identities, window immutability, late window completion, queue budget/idempotency, untrusted suggested-only evaluation, policy approval, immutable follow-up artifacts, aggregate-only model disclosure and unauthorized semantic-repair prevention.

New endpoints are under the existing resources: POST rules/policy-versions; GET/POST trials/reevaluations; GET trials/reevaluations/{evaluation_id}. Existing signals ingestion/import accepts observation_window, consent_to_model and reevaluate. Exact bodies, status semantics and safe follow-up flow are in API_CONTRACT.md. See LIVING_HARNESS.md for reproducible cohort formulas, thresholds, demo commands and limits.

Remaining scope: synthetic fixture telemetry only, two pinned fictional policy versions, fixed descriptive drift thresholds, partial scenario coverage, one bounded Python source file per approved plan, at most four re-evaluations per snapshot, one attempt each and two authorized regression repairs per job. No durable queue/job history, real analytics connector, general policy editor, authentication, production monitoring, deployment, commits or pushes. Local IDs expire on restart; saved ignored evidence persists independently of those IDs.


### Final local HTTP handoff

The documented two-policy HTTP command passed against the restarted final backend (OpenAPI 0.3.0). Both approved jobs succeeded. The follow-up used previous_working_copy and reported 12 preserved, 3 intended changes, zero unexpected divergences/unverified/execution errors and zero repairs. These counts describe this actual model run, not a fixed promised output. The earlier patch remained byte-identical.

Current saved files: .ghostpatch/last-continuous-investigation.json, last-continuous-policy-investigation.json, last-continuous-first-job.json, last-continuous-followup-job.json, last-continuous-evidence.json, last-continuous-first.patch, and last-continuous-followup.patch. They are ignored local synthetic evidence. The result link printed by the script is valid only until the backend restarts.

Final default test run after the repair-feedback tightening: **94 passed, 6 opt-in skipped**, one existing dependency deprecation warning, 11.61 seconds. The preceding full real-service suite passed all 100 tests. Backend and frontend remain running on 127.0.0.1:8000 and 127.0.0.1:3000.

## Continuous evaluation extension approach

Extend the existing Signals aggregation with optional stable pseudonymous identities, explicit observation windows, version-aware drift and honest unavailable retention. Extend Memory with policy-version provenance and competing explanations with supporting/counter evidence. Extend Trials and the existing harness with idempotent bounded re-evaluation triggers, trusted-only execution, safe follow-up plans and immutable job artifacts. Preserve the current APIs and original samples; keep the same minimal evidence view. No additional top-level feature/service modules, deployment or development approval gates.

## Approach recorded before implementation

Extend the existing FastAPI services, Pydantic schemas, repository store, bounded Nemotron client, patcher, and hardened Docker runner. Preserve the existing ZIP/GitHub and expense-report workflow. Do not replace the application or overwrite backend/.env.

1. Ghost Memory: deterministic AST candidates plus Nemotron extraction; validate exact file/function/line evidence; separate observation from intended policy; maintain stable IDs, history and conflicts.
2. Ghost Trials: bounded scenarios with policy, observation, invariant or hypothesis oracles; no model assertion as sole oracle. Execute identical synthetic inputs and unchanged tests before/after and after repairs.
3. Ghost Signals: strict synthetic-only ingestion, deduplication, counts/denominators/trends, aggregate-only model interpretation, and proposed conflicts.
4. Add a hash-pinned fictional eligibility sample whose existing tests miss an independent policy boundary. Preserve the expense sample.
5. Integrate the existing single orchestrator with explicit semantic-change approval and investigation-revision checks.
6. Extend the basic black frontend, then validate via unit/API and real service tests, lint/build, and HTTP. No browser automation.

## Implemented files

New backend modules: harness_schemas.py, memory.py, trials.py, signals.py, harness.py, trusted.py.
Extended existing modules: schemas.py, model.py, store.py, loader.py, patcher.py, runner.py, orchestrator.py, main.py, body_limit.py, and runner/check.py.

Added the pinned claims_demo source, six unchanged legacy tests, independent policy fixtures, before/after synthetic event fixtures, and manifest. Existing legacy_reports source/manifest remain unchanged.

Added Memory/Trials/Signals/API/live tests, scripts/verify_upgrade.py, minimal frontend evidence tables, and Living Harness documentation. No new service, database, account, dependency family, deployment, commit or push was introduced. backend/.env was not overwritten.

## Actual verification

- The full backend suite with both integration flags passed **80 tests** in 65.53 seconds at that checkpoint, including all five real-service integration checks.
- Final unit/API suite after aggregate-only privacy, post-approval revision and exact-source-quote checks: **78 passed, 5 opt-in integration tests skipped**, in 13.87 seconds. All five real-service integration tests had already passed in the combined run.
- Real legacy expense-report Nemotron/Docker workflow still succeeded.
- Real GitHub static ingestion and Docker regression-detection/restoration tests passed.
- New real Docker baseline: **6/6 existing tests passed**, while the age-65 trial returned rejected versus the independent expected approved outcome.
- New real end-to-end run: Memory model extraction and Signals interpretation succeeded with accepted grounded outputs. **18 rules, 12 scenarios, 11 preserved, 1 intended change, 0 unexpected divergences, 0 unverified, 0 execution errors**. Six tests passed before/after; zero repair attempts were needed.
- Latest HTTP run on the final 0.2.0 server: **18 rules, 66 synthetic events, 11 scenarios, 10 preserved, 1 intended change, zero divergences/unverified/errors**, six tests passed before/after, zero repairs. Rule coverage was explicitly **5/18**. Model-generated scenario additions vary by run; duplicate proposals do not invent additional coverage. Saved .ghostpatch/last-upgrade-investigation.json, last-upgrade-job.json, last-upgrade-evidence.json, and last-upgrade.patch.
- Frontend ESLint and Next.js build/TypeScript checks passed. Browser automation was not used.

An initial live model extraction failed and correctly fell back to deterministic hypotheses. Bounded output instructions, numbered source lines, and sanitized schema-feedback retries corrected it. Invalid source references remain rejected rather than being presented as facts.

One test-client dependency warning remains: Starlette deprecates its httpx compatibility path. It did not cause test failures.

## Remaining limitations

Only pinned synthetic samples execute. Model hypotheses and source observations do not prove policy correctness. Rule coverage is partial and explicitly counted. Usage fixtures are synthetic, not real-user tracking or measured post-patch improvement. IDs/events/history remain temporary and single-user; no authentication, durable job store, cancellation, GitHub PRs or public hosting.

See LIVING_HARNESS.md for commands, API resources, scenario oracles, product approval gates and the reproducible judging demo.

## Final handoff checks

- HTTP 200 for the frontend with the claims-demo control; backend health reports 0.2.0 and all three harness features.
- Source secret-pattern scan: 87 source/documentation files, zero matches for the checked credential/private-key patterns (not a guarantee of secret absence).
- Git ignore checks cover backend/.env, the virtual environment, frontend local configuration and runtime evidence. The original sibling frontend working tree remains clean.
- No credential was displayed or overwritten. No commit, push, deployment, account or paid resource was created.
- The current local result link is recorded in the final handoff; IDs expire on backend restart. Saved evidence files remain ignored local artifacts.
