# GhostPatch Codex Prompt — Extend Existing Ghost Signals, Ghost Memory, and Ghost Trials

Upgrade the **existing** GhostPatch backend in place. Do **not** create four new standalone features, agents, or top-level modules. Continuous evaluation is an extension of the existing three features and their orchestration. Preserve current APIs, workflows, security boundaries, and tests. Work autonomously without development approval checkpoints; retain product-level human approval for semantic policy changes. Keep the frontend minimal.

## 1. Extend Ghost Signals: Behavior over time
- Reuse the existing validated synthetic JSON/JSONL event ingestion and aggregated metrics pipeline.
- Add optional privacy-preserving, stable pseudonymous user IDs (distinct from session IDs), plus software version and event timestamp, through a strict allowlist. Do not accept raw PII. If IDs are absent, mark return/retention metrics unavailable rather than guessing.
- Compute repeat visits, return rates for clearly defined eligible cohorts and observation windows, workflow completion/abandonment, retries, overrides, and errors; include numerator, denominator, sample size, and time window.
- Compare comparable time windows and software versions to flag meaningful behavior drift. Use sensible minimum sample sizes and avoid claims of causation or certainty from small samples. Also compare approved non-sensitive input categories where supported to flag data drift.
- Keep events synthetic for the demo. Send only aggregated metrics to Nemotron, never raw sessions.

## 2. Extend Ghost Memory: Evolving rules and hypotheses
- Reuse the versioned Legacy Behavior Contract and evidence provenance.
- Link drift findings to existing rule IDs, policy versions, and potential contradictions. Distinguish policy drift, user-behavior drift, and input-data drift.
- Have Nemotron propose **multiple competing explanations** for each meaningful signal, including non-code explanations. Store evidence for/against each, uncertainty, and targeted verification suggestions.
- Do not interpret a user's comment literally as an implementation instruction; treat it as one clue. Never auto-approve or silently modify intended policy.

## 3. Extend Ghost Trials: Trigger re-evaluation
- When Ghost Signals identifies meaningful drift, or Ghost Memory receives a new approved policy version, enqueue a bounded re-evaluation using existing orchestration and trial machinery.
- Generate targeted scenarios linked to the drift finding and affected rule(s). Preserve oracle separation (approved policy, observed legacy behavior, fixed invariant, unverified hypothesis). An LLM-generated expectation alone is never a correctness oracle.
- Reuse the trusted-sample-only Docker execution restriction. For untrusted uploads, generate suggested tests without executing uploaded code.
- Compare baseline and candidate behavior, report preserved/intended change/unexpected divergence/unverified/error, and feed actionable failures into the existing capped repair loop only when authorized.
- Record the trigger, source evidence, tool calls, test results, uncertainty, and approval state in the existing Behavior Preservation Report.

## 4. Connect the existing flow (not a new product feature)
- Make the existing pipeline support: **new synthetic events or approved policy update → Ghost Signals detects a change → Ghost Memory investigates competing explanations → Ghost Trials re-evaluates → Nemotron recommends a bounded action → human approves any semantic change**.
- Extend existing rules/signals/trials/evidence APIs with backward-compatible fields/endpoints only where necessary. Make repeated ingestion and evaluation idempotent; prevent endless retrigger loops and cap costs/attempts.
- Add a trusted synthetic demo with two time windows showing a behavior shift, a hypothesis investigation, and a targeted trial that finds or rules out a genuine discrepancy. Label all data synthetic and show uncertainty.
- Add focused unit/API/integration tests and run the existing suite. Update README/API docs with exact endpoint payloads and limitations.

## Acceptance criteria
- No redundant fourth/fifth subsystem or separate dashboard.
- Existing ZIP/GitHub import, Nemotron planning, approvals, isolated patching, trusted Docker tests, repair, diffs, and export still work.
- Metrics are reproducible and denominators are explicit; missing identity data cannot produce invented retention.
- Drift alone cannot change policy or authorize code execution.
- The demo shows evidence-backed continuous re-evaluation using **Ghost Signals + Ghost Memory + Ghost Trials**.
- At the end, summarize changed files, endpoints, tests run/results, and remaining limitations. Do not claim capabilities that were not implemented or tested.
