# GhostPatch Backend Upgrade — Living Software Harness

## Mission
Upgrade the **existing, working GhostPatch repository** into an evidence-driven, behavior-aware legacy software evolution harness for the HackUTD 8090 legacy-modernization challenge and NVIDIA Nemotron agentic challenge.

**Do not rebuild the application.** Inspect the existing source, endpoints, schemas, tests, and Docker workflow first, then extend them. Preserve existing features and API compatibility where practical. Keep the frontend minimal and functional; backend correctness and a compelling reproducible demo take priority. Work autonomously through the tasks without phase-by-phase approval. Do not push/deploy, spend money, or modify external services without permission.

### Product thesis
**GhostPatch observes how software is actually used, discovers undocumented business rules, detects conflicts between historical behavior and evolving requirements, and generates independently verified, human-approved modernization patches.**

A generic AI coding agent rewrites code. GhostPatch provides the **harness** around the agent: observations, evidence, constraints, executable behavioral oracles, differential testing, regression detection, repair, and auditable decisions.

## Existing capabilities to preserve
- Import Python repositories from ZIP and public GitHub URLs.
- Safe archive/path validation and exclusion of sensitive/unsupported files.
- Python source, import, dependency, and modernization analysis.
- NVIDIA Nemotron integration using existing `backend/.env` keys (`NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`).
- Bounded modernization plans with risks and priorities; human plan approval before edits.
- Isolated working-copy edits to an approved Python file.
- Docker baseline/modified testing **for explicitly trusted developer-controlled samples only**.
- Behavior comparison, up to two repair attempts, status/events/logs/evidence/diffs, patch export.
- Temporary jobs; no authentication or GitHub PR creation. Do not silently claim production readiness.

## Priorities and scope
Implement **P0: Ghost Memory + Ghost Trials** end to end first, then **P1: Ghost Signals** and its integration. Favor a robust demo over breadth. Support Python and a single trusted synthetic business application; keep interfaces extensible but do not add Java/COBOL, a database, accounts, or cloud deployment. Do not spend time on complex UI.

## A. Ghost Memory — source-grounded business-rule archaeology (P0)
Create a rule extraction service using Nemotron and deterministic source analysis.

- Extract candidate business rules from code, existing tests, and repository documentation. Examples: eligibility checks, thresholds, duplicate detection, rounding, exception handling, approval states.
- Store each candidate as structured data: stable ID, title, natural-language description, precise source file/function/line references, evidence snippets or hashes, supporting tests/docs, confidence/uncertainty, status (`hypothesis`, `verified`, `conflicted`, `superseded`), and version/history.
- Validate source references against real files and line ranges. Reject hallucinated references and distinguish *observed implementation* from *intended policy*. A rule inferred from code alone is **not automatically correct**.
- Identify contradictions between code, tests, documentation, and later user-behavior signals. Report competing hypotheses rather than silently choosing one.
- Produce a concise machine-readable **Legacy Behavior Contract** / rulebook for the selected trusted sample.
- Keep rule extraction bounded, cached per job where useful, and resilient to invalid model JSON or empty/reasoning-only responses.

## B. Ghost Trials — independent behavioral verification (P0)
Extend the Docker test harness beyond existing pytest tests.

- Generate **bounded, reviewable** scenario candidates from discovered rules: normal, edge, boundary, negative, duplicate, and regression cases. Each scenario has an ID, linked rule IDs, synthetic input, expected-output source/oracle, and rationale.
- Separate oracle types:
  1. `approved_policy`: expected outcome from explicit trusted policy fixture / human-approved rule;
  2. `legacy_observation`: outcome captured from the original system (compatibility baseline, **not proof of correctness**);
  3. `metamorphic_invariant`: deterministic invariant with independently checkable assertion;
  4. `hypothesis`: unverified expected outcome, reported only, **not** used to assert correctness.
- Never allow Nemotron's unsupported assertion to become the sole pass/fail oracle for its own patch.
- For a trusted demo repository, execute original and patched versions on **identical synthetic inputs** in Docker; capture structured outputs, exceptions, exit codes, and relevant side effects. Normalize only known nondeterministic fields. Preserve raw evidence.
- Compare behavior per scenario, classify `preserved`, `intended_change`, `unexpected_divergence`, `unverified`, or `execution_error`. Report exactly why a classification was assigned.
- Run baseline pytest + scenario trials before edits, and repeat after edits and each repair. Do not mark success if test execution was skipped or failed.
- If a regression is found, provide the failing input, linked rule, expected/actual outputs, code locations, and evidence to Nemotron for at most two bounded repair attempts. Keep existing approval/patch constraints and never edit the original repository.
- Return a **Behavior Preservation Report** with rule coverage, scenario outcomes, divergences, limitations, actual test evidence, and patch diffs. Avoid blanket guarantees of correctness.

## C. Ghost Signals — behavior-aware requirements investigation (P1)
Implement a privacy-conscious event ingestion and investigation layer, initially for **synthetic demo data**.

- Define an event schema such as: `event_id`, `session_id` (pseudonymous), `timestamp`, `workflow`, `action`, `outcome`, `rule_context`, `synthetic=true`, and optional safe structured metadata. Do not collect names, emails, raw claims, secrets, or sensitive free text.
- Provide ingestion for a local synthetic JSON/JSONL event fixture and, if easy, a simple API endpoint. Validate types, bound payload size, reject unknown sensitive fields, deduplicate events, and document retention. Do not claim real-user tracking.
- Implement deterministic signal detection before AI interpretation: repeated manual overrides, retries, abandonment, recurring errors, and return/reuse rate across pseudonymous sessions when the fixture supports it. Use minimum sample sizes and report denominators; do not treat correlation as causation.
- Nemotron receives **aggregated** signals and relevant rule/code evidence to propose **hypotheses** about outdated rules or unmet requirements, with alternate explanations, confidence, affected code, and suggested verification scenarios.
- Connect signals to Ghost Memory: create or update **proposed** rule conflicts and targeted Ghost Trials. Do not automatically change policy based only on user behavior. Require human approval for semantic changes.
- Include a versioned synthetic `before` and `after` behavior dataset to demonstrate how changing usage patterns trigger re-evaluation; do not pretend to have observed actual returning users.

## D. Orchestration — Nemotron as a real tool-using investigator
Use one orchestrator with explicit tools/services rather than many cosmetic agents:

1. Inspect repository and build source map.
2. Extract and validate Ghost Memory rules.
3. Analyze available Ghost Signals (if any), identify evidence gaps, and propose hypotheses.
4. Generate Ghost Trials with traceable oracles.
5. Run baseline Docker tests/trials.
6. Generate a bounded modernization or rule-change plan, showing expected behavior and risk.
7. Await **human approval** for edits and any intended business-rule changes (this is a product safety gate, **not** a Codex development approval checkpoint).
8. Patch isolated working copy, rerun tests/trials, investigate divergences, attempt up to two repairs.
9. Produce a decision-ready report and downloadable patch.

Record real tool invocations, timestamps, inputs/outputs summaries, model errors, and evidence references. Do not fabricate agent activity. Validate structured outputs with Pydantic, enforce per-step token/time/retry budgets, and handle invalid JSON, empty `content`, `reasoning_content`, rate limits, and API outages. Never log secrets or full sensitive repository contents.

## E. Trusted demo scenario — the judging moment
Build or enhance a **fictional, synthetic claims/eligibility processing Python repository** with a clearly documented policy fixture and a legacy implementation. Do not use real patient, insurer, or Medicare data.

Demonstrate a meaningful gap between *existing tests passing* and *actual business behavior*: for example, repeated manual overrides in synthetic events suggest a rounding/eligibility/duplicate-handling problem. Nemotron links the signal to a candidate rule, generates targeted trials, and identifies a mismatch against the **independent policy fixture**. It proposes a bounded fix, runs Docker trials, and produces evidence. Optionally include a controlled modernization-induced regression that GhostPatch detects and repairs. Ensure the demonstration is **genuine and reproducible**, not hardcoded success text or prewritten fake Nemotron outputs.

Demo story:
- Initial repository and its existing tests appear healthy.
- Synthetic usage signals show a suspicious pattern with actual counts.
- Ghost Memory locates a specific legacy rule and supporting source lines.
- Ghost Trials exposes a policy mismatch or regression the original tests missed.
- Nemotron proposes a change, a human approves, and Docker verifies it.
- The report shows before/after behavior, rule provenance, remaining uncertainty, and exact diff.

If a model-generated repair is unreliable, preserve an honest, repeatable partial demonstration and explicitly report failures; never spoof successful outcomes.

## F. API contracts and minimal UI
Inspect current API patterns and extend consistently. Suggested resources (adapt names to existing architecture):
- `GET /jobs/{id}/rules` — rulebook, provenance, conflicts.
- `POST /jobs/{id}/signals` or local fixture import — synthetic event ingestion.
- `GET /jobs/{id}/signals` — aggregated patterns and hypotheses.
- `POST /jobs/{id}/trials` — generate/execute eligible trials as appropriate.
- `GET /jobs/{id}/trials` — scenario results and comparisons.
- `GET /jobs/{id}/evidence` — behavior preservation report.
- Existing approval, job, diff, and patch endpoints remain functional.

Minimal black Next.js frontend: repository selection/upload, job status, rules table, signals summary, scenario outcomes, approval button, logs, diffs, and patch export. No React Flow, Monaco, or visual redesign yet. Clearly label synthetic data and distinguish proposed hypotheses from verified facts.

## G. Security and engineering constraints
- Never execute uploaded/cloned repositories. Execute **only allowlisted, developer-controlled trusted samples**; static analysis is allowed for other repositories. No bypass based on user-provided labels.
- Docker: non-root, no privileged mode, no Docker socket mounts inside containers, disabled network where feasible, CPU/memory/PID/time limits, controlled mounts, ephemeral containers, restricted filesystem access. Docker alone is not a complete untrusted-code sandbox.
- Validate ZIP paths, archive sizes, clone URLs, file paths, patch targets, JSON schemas, event payloads, and output sizes. Keep secrets server-side and `.env` gitignored.
- Preserve the original repository and require explicit human approval before edits; no autonomous pushes, deployments, external PRs, or production data writes.
- Keep modular services, typed models, clear logs, deterministic tests, and useful error handling. Use lightweight local persistence (e.g., job files) only if needed; document temporary state limitations.

## H. Testing and acceptance criteria
Implement automated unit tests for source-reference validation, rule status/versioning, event aggregation, oracle selection, scenario comparison, approval enforcement, patch constraints, and failure modes. Add integration tests for the trusted Docker sample and mocked Nemotron failures. Where API credentials/Docker are available, run a real end-to-end smoke test.

**Done means:**
1. Existing GhostPatch upload/analyze/approve/patch/test/export path still works.
2. Rulebook contains source-validated, evidence-backed candidate rules.
3. Synthetic behavior events yield reproducible metrics and at least one actionable, clearly labeled hypothesis.
4. A targeted behavioral scenario reveals a meaningful issue that existing unit tests miss.
5. The trusted sample runs baseline and patched scenarios in Docker with independently grounded oracles.
6. Nemotron contributes genuine investigation, scenario planning, patching, and/or repair; its outputs are not presented as independent proof.
7. Reports show exact inputs, outcomes, rule provenance, test evidence, diffs, and uncertainties.
8. The minimal UI exposes the workflow; README documents setup, commands, demo steps, security limitations, and what was actually verified.

## Implementation instructions
- First inspect the existing repository and briefly record the upgrade approach in `docs/UPGRADE_NOTES.md`, then **proceed without waiting for approval**.
- Implement in priority order: **Ghost Memory → Ghost Trials → Ghost Signals → integrated orchestrator/demo → minimal UI → tests/docs**. Reuse existing code wherever possible.
- Do not delete or replace working modules unnecessarily. Do not overwrite `.env` or expose the API key. Add `.env.example` for placeholders only.
- Run lint/type checks/tests and repair errors as you proceed. Keep the scope achievable for a solo hackathon.
- Do not stop for phase approvals. Only pause for genuine external blockers, security-sensitive actions, payments, deployment, or destructive operations.
- At the end, report: files changed, implemented features, actual test commands/results, real Nemotron/Docker verification status, demo instructions, and known limitations. **Do not claim production readiness.**
