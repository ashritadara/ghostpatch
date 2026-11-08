# Living Software Harness

GhostPatch 0.2 extends the working MVP in place. The expense-report import/plan/approve/patch/test/export path remains functional. The new judging demo is a fictional, synthetic claims/eligibility application. Nothing here represents real insurance, medical, Medicare, or regulatory policy.

## Ghost Memory

backend/app/memory.py extracts deterministic conditions, assertions, rounding operations and optional Nemotron business-rule hypotheses from bounded code, tests and documentation. Every accepted reference is checked against the original snapshot: path, real function span, inclusive one-based line range, exact source excerpt, excerpt SHA-256 and file SHA-256.

Rules have stable IDs, kind, origin, confidence/uncertainty, status, version and timestamped history. Code observations and model assertions start as hypotheses. Explicit developer-controlled policy is a separate authority. Independent trial mismatches create observed conflicts; synthetic usage creates proposed conflicts only. An approved, independently verified correction can supersede the old observed rule without rewriting original evidence.

The rulebook is a machine-readable Legacy Behavior Contract. It is cached per repository snapshot and included in final job evidence. Model invalid JSON, outages and rejected references are reported; deterministic hypotheses remain available without pretending the model succeeded.

## Ghost Trials

backend/app/trials.py and the extended fixed Docker runner use four explicit oracles:

- approved_policy: expected outcome from hash-pinned independent policy fixtures or their fixed declarative-policy interpreter.
- legacy_observation: actual original behavior used only as a compatibility baseline, not proof of correctness.
- metamorphic_invariant: a fixed independent input-immutability or repeatability assertion.
- hypothesis: reported, never used as a correctness oracle.

Nemotron proposes bounded scenario inputs/categories/rationales linked to known rules. It cannot submit authoritative expected outputs. A matching pinned fixture, or the deterministic interpreter of its approved parameters, supplies policy expectations. Generated scenarios without that authority remain observations or hypotheses.

At most 24 scenarios execute. Original and modified runs receive the same synthetic inputs via a separately mounted read-only JSON file outside the editable source. The unchanged original pytest tests and policy fixtures are mounted read-only. Capture actual outputs, exception types, bounded stdout/stderr, input digests, timing, input mutation and created temporary filenames. No nondeterministic fields are normalized.

Per-scenario classifications are preserved, intended_change, unexpected_divergence, unverified or execution_error, each with an explanation. Intended changes require both independent expected results and explicit approval of a linked policy rule. A model prediction alone never supplies a pass/fail oracle.

A passing baseline pytest run is necessary but insufficient. Final success also requires modified pytest and enforceable trials to pass. Reports retain the initial candidate, each repair's evidence, raw trial results, limitations, source provenance and diffs. Up to two repair attempts remain enforced.

## Ghost Signals

backend/app/signals.py accepts only synthetic=true events. IDs are constrained pseudonymous hexadecimal tokens; workflows/actions/outcomes and metadata are allowlisted. Names, emails, claims, secrets, free text and unknown fields are rejected. JSON/JSONL and API payloads are bounded to 128 KiB and 500 unique events per snapshot. Duplicate IDs are idempotent; conflicting duplicates are rejected atomically.

Deterministic metrics precede interpretation: manual override events/submits, retry events/submits, abandonment events/submits, errors/all events, sessions seen on two UTC dates/distinct sessions, and threshold-band overrides/all overrides. Event rates can exceed 100% because one submit can have multiple retry events. Pattern detection requires the documented minimum sample sizes (normally 10 submits, 5 sessions and 3 matching events). Report all denominators.

The pinned before-v1 fixture contains 27 events across 12 sessions; after-v1 contains 39 events across 12 sessions. Overrides rise from 4/12 to 8/12 submits; reuse is 6/12 then 2/12 sessions. These are authored synthetic usage windows, not real observed users or measured post-patch improvement.

Nemotron receives aggregate windows/trends and relevant numbered source lines, never raw event rows or session identifiers. Its source-validated hypotheses include alternatives, uncertainty and targeted scenarios. They create proposed Memory conflicts, never automatic policy changes.

Raw in-memory synthetic events expire with the temporary repository snapshot. Aggregate reports and fixtures are clearly labeled synthetic. No real-user telemetry collector is installed.

## Genuine demo

The original claims.py uses age > 65, while the independent POLICY.md/policy.json fixture includes age 65. Six existing tests omit this boundary and pass. A real Docker scenario at age 65 exposes rejection versus the independent expected approval.

1. Start the services using the root README.
2. Open http://127.0.0.1:3000 and choose **Load claims policy demo**.
3. Check the NVIDIA disclosure-consent box.
4. Click **Investigate rules, signals & trials**.
5. Read source-backed rules, synthetic metrics, competing hypotheses, and the failing independent boundary trial.
6. Select the explicit inclusive-eligibility policy correction checkbox.
7. Generate the plan, review scope/risks, then approve its listed semantic change.
8. Inspect real Docker results, intended-change classification, exact diff and patch download.

For deterministic investigation without a model call:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py

For real model investigation without approving edits:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py --run-model

For the explicitly approved synthetic end-to-end demonstration:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py --run-model --approve-demo-policy-change

The approval flag authorizes only the fictional age-65 rule in the isolated sample. It is not a general policy-change permission. The script saves ignored investigation, job, report and patch files under .ghostpatch/ and prints a frontend results link. Job links work only while their local in-memory IDs remain available.

Real model output is nondeterministic. Report zero repairs when none were required; never script a fake repair story. The separate deterministic regression test uses explicit fault injection and restoration, not fabricated model activity.

## Extended API

Existing routes remain available. All paths below have the /api prefix.

| Method | Resource | Behavior |
| --- | --- | --- |
| POST | /repositories/sample?sample_id=claims_demo | Load pinned new sample; default without query remains legacy_reports |
| GET | /repositories/{id}/investigation | Safe view of cached rules/signals/scenarios/report/tool trace, never raw events |
| POST | /repositories/{id}/investigate | consent_to_model, use_model, signals_dataset (before/after/both/none); investigate and run eligible baseline |
| GET/POST | /repositories/{id}/rules | Read contract / optionally extract model rules |
| GET/POST | /repositories/{id}/signals | Aggregates / bounded strict synthetic event ingestion |
| POST | /repositories/{id}/signals/import | Import pinned local before/after JSONL fixture |
| GET/POST | /repositories/{id}/trials | Read / generate and execute eligible original scenarios |
| GET | /jobs/{id}/rules | Final rulebook snapshot |
| GET | /jobs/{id}/signals | Final aggregate/hypothesis snapshot |
| GET | /jobs/{id}/trials | Final scenario report plus original/modified test evidence |
| GET | /jobs/{id}/evidence | Behavior Preservation Report |
| GET | /jobs/{id}/evidence/download | Download evidence JSON |

Plan requests can include intended_rule_changes. Only pinned independent policy IDs with observed trial evidence are eligible. Approving a semantic plan requires approved_rule_changes matching its intended IDs. Changes to investigation revision after planning or approval invalidate execution. Existing ordinary requests with no intended semantic change remain compatible.

Rule extraction and direct trial mutation remain pre-execution operations. Idle completed snapshots support event/policy updates and a fresh evidence-gated follow-up plan as documented below. Active jobs keep their approved scenario/oracle set fixed. The backend, not frontend checkbox state, enforces consent, approval, trust and path constraints.

## Tests and limits

From backend/:

    .\.venv\Scripts\python.exe -B -m pytest -q

Opt into real Docker/NVIDIA/public GitHub checks:

    $env:GHOSTPATCH_RUN_INTEGRATION='1'
    $env:GHOSTPATCH_RUN_UPGRADE_INTEGRATION='1'
    .\.venv\Scripts\python.exe -B -m pytest -q -s
    Remove-Item Env:\GHOSTPATCH_RUN_INTEGRATION
    Remove-Item Env:\GHOSTPATCH_RUN_UPGRADE_INTEGRATION

Only the two explicitly registered, hash-pinned samples execute. Uploaded/cloned repositories may receive static Memory candidates and consented model suggestions, but never execute. Policy fixtures in uploads cannot grant authority or execution trust.

State remains temporary, local, single-user, unauthenticated and non-production. No database, accounts, production writes, push/deploy, PR automation or cloud services were added. Coverage is a reported subset, not a blanket guarantee. Browser automation is unnecessary and was not used for this upgrade.

## Continuous evaluation extension (0.3)

This extends the existing Signals, Memory, Trials and single orchestrator. No additional feature service or dashboard was introduced. All event fixtures and policy versions are fictional synthetic demo data.

### Reproducible metrics and drift

The pinned windows are [2026-11-01T00:00:00Z, 2026-11-03T00:00:00Z) and [2026-11-05T00:00:00Z, 2026-11-07T00:00:00Z), labelled legacy-v1 and candidate-v2. Labels are authored fixture metadata, not measurements of an actual deployment or this patch's effect. There are 27/39 events, 12 submitted sessions and 12 identified synthetic users per window.

- Return rate: distinct first-UTC-day submitters active on the following UTC day / distinct eligible first-day submitters. The fixtures yield 6/12 (50%) and 2/12 (16.7%). A declared complete window of at least two days, aligned to UTC midnights, is required. Missing user IDs on any event or an absent/inadequate window makes the metric unavailable with a null rate and an explicit reason. These are declared synthetic windows; ingestion does not establish real instrumentation coverage.
- Repeat visits: additional active UTC user-days beyond each user's first active day / identified users in the declared complete window. This is a descriptive day-based measure, not a count of browser visits.
- Existing session_reuse remains distinct: sessions seen on two or more UTC dates / sessions. It is never labelled user retention.
- Manual overrides, retries and abandonment count events / submits. Repeated events can make a rate exceed one. Recurring errors count error events / all events.
- Workflow completion counts submitted sessions whose latest observed event has a terminal approved/rejected/completed outcome / submitted sessions. It does not mean a business request succeeded.
- Every metric includes numerator, denominator, sample_size, availability and declared time bounds when supplied.

Drift compares adjacent chronological, equal-duration, non-overlapping explicit windows, each with one known software version and the same single workflow. Behavioral detection requires at least 10 submits and 5 sessions per window and an absolute change of 20 percentage points; return-rate cohorts additionally need 5 eligible users each. Input-data drift uses total variation distance of allowlisted age-band submit counts, threshold 0.20 and at least 10 fully categorized submits per window. Different reported policy versions make category comparisons non-comparable. Below-threshold or inadequate results are explicitly marked insufficient_data; incompatible cohorts are not_comparable. Thresholds are descriptive and are not statistical significance or causation.

Reported event policy_version is metadata only. Only explicit approval of a pinned policy fixture can change the active intended rule. New approved policy versions create a distinct approved_policy_update trigger and versioned Memory history; behavior/input changes remain separate drift categories.

### Investigation and re-evaluation

Memory links meaningful findings to rule IDs, source hashes, active policy version and multiple competing explanations. Nemotron receives only aggregate windows/categories/drifts plus bounded relevant source excerpts; it receives no event rows, session IDs or user IDs. Code, workflow, input-mix and instrumentation explanations remain hypotheses. Supporting/counter-evidence IDs are checked against known evidence. Source references must match exact files, functions, lines and quotes. A rejected grounding result receives at most one correction request; invalid references are never accepted. Missing model access leaves deterministic hypotheses labelled as such. Comments/source text are evidence, never commands.

New comparable evidence or explicit policy approval queues existing Ghost Trials. Queues are idempotent by aggregate/source/policy digest, capped at four records per repository snapshot and one attempt per record. Repeated ingestion/evaluation does not repeat Docker or model execution. Trial results never enqueue themselves. Model use needs explicit consent; JSON/API retry limits remain bounded. This is a fixed attempt/token/time budget, not a monetary billing quota.

Trusted claims re-evaluation tests original and existing working copies with targeted boundary inputs and the same unchanged pytest suite. Policy-derived expectations come from pinned independent fixtures, never from a model assertion. Untrusted imports receive suggestions/reports only; no uploaded code executes. Re-evaluation can report a failure and recommend review; it never patches or invokes repair.

Policy 1.0 says age 65 is eligible; the original source incorrectly rejects it while all six old tests pass. A separately approved patch corrects that discrepancy. Optional fictional policy 1.1 changes the minimum age to 66. Approving 1.1 updates intended policy/history and queues trials without editing code. Trials then detect that the first candidate conflicts with 1.1. A fresh plan, exact rule approval and execution approval are required for a follow-up patch.

Follow-up jobs freeze the previous working copy as an internally registered immutable baseline. Their diff is previous candidate to new candidate. Each job owns its evidence JSON and patch, so an earlier download is not replaced. Stale revisions/source hashes invalidate plans. Unchanged pre-existing policy mismatches do not authorize autonomous semantic repair; approved jobs still retain the existing two-regression-repair cap.

### Run the HTTP demo

Start the normal backend and frontend. From the repository root:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py --continuous

This imports the two synthetic windows separately, runs deterministic trusted Docker re-evaluation, checks deduplication, and saves .ghostpatch/last-continuous-investigation.json. No patch is approved.

Add --run-model to consent to real NVIDIA investigation. To explicitly authorize both isolated fictional corrections, including the later policy update:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py --continuous --run-model --approve-demo-policy-change --approve-demo-policy-update

The script prints actual status/classifications, saves ignored evidence and per-job outputs/patches, verifies the earlier patch is unchanged, and prints a local frontend result link. The flags authorize only this pinned synthetic demo, not changes to imported repositories.

In the minimal UI: load the claims sample, optionally consent to NVIDIA, import Before and After, inspect the re-evaluation, select the evidenced rule and generate/approve a plan. After the first job, the explicit fictional-policy-1.1 control updates policy and starts evaluation. Review its evidence before selecting a new correction and approving a fresh plan. No extra dashboard or simulated activity is used.

### Limits

User IDs must be stable synthetic pseudonyms supplied by the caller; GhostPatch cannot establish that they represent real distinct people. No raw PII/free-text event fields, real analytics connector, streaming telemetry, arbitrary policy authoring, durable scheduler or production monitoring was added. Events/history/queues are in-memory and expire with the local snapshot/server. Four evaluations and 500 unique events bound each snapshot. Failed evaluations require review or a fresh snapshot and are not endlessly retried. Security and general correctness are limited to the existing local, unauthenticated, trusted-sample MVP.
