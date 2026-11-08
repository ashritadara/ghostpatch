# Architecture

The active instructions are GHOSTPATCH_MVP_CODEX.md. They replace the former phase gates and elaborate frontend sequence.

## Implemented modules

- backend/app/config.py: environment configuration with python-dotenv; no hardcoded model/key.
- schemas.py: strict-extra-field Pydantic request/response/model DTOs.
- paths.py and loader.py: ZIP safety, public GitHub URL allowlist, bounded no-checkout clone, file filtering, pinned sample registration.
- analyzer.py: Python AST/import/dependency inspection and line-grounded heuristics without execution.
- store.py: bounded in-memory IDs and isolated original/working snapshots; known-workspace cleanup.
- model.py: OpenAI-compatible Nemotron client, meaningful final-answer check, JSON validation, bounded retries, safe errors, reasoning exclusion.
- patcher.py: approved-file scope, protected tests, optimistic hashes, syntax checks, bounded atomic writes, original integrity checks, real diffs.
- runner.py and runner/: trusted-only Docker validation, unchanged baseline tests, actual counts/logs, input/output probes, hard limits.
- orchestrator.py: explicit plan approval, baseline, isolated patch, validation, up to two repairs, evidence finalization/export.
- main.py and body_limit.py: local REST API, Origin/Host checks, streamed request-size limits, background jobs.
- frontend/: one black-page UI, typed API client, two-second polling, actual evidence and patch download.

## Flow

ZIP / public GitHub / built-in sample -> isolated original and working copy -> static diagnosis -> consented Nemotron plan -> explicit product approval -> background job -> patch -> trusted-only Docker validation -> bounded repair if a real regression occurs -> exact evidence and diff.

Untrusted uploads and clones never execute, even if byte-identical to the sample. They can receive consented model plans and isolated patches, with verification explicitly skipped.

The trusted loader reads a developer-controlled SHA-256 manifest. The runner independently checks trust, original integrity, and unchanged test/fixture files. No API request field can grant trust. Original source is never edited by the patcher; integrity checks detect tampering.

## State and boundaries

One local user, one worker, in-memory IDs. Temporary source/evidence directories live under the ignored .ghostpatch/workspaces/. Known inactive workspaces expire lazily after six hours or are removed on clean shutdown. IDs are lost on restart; crash leftovers are a documented limitation.

The backend owns plan approval, job idempotency, paths, commands, execution trust, repair bounds, and patch artifacts. The model chooses neither shell commands nor new dependencies. The frontend cannot turn an untrusted repository into a trusted one.

Final patch review is browser-session state. It enables download but does not merge/deploy or mutate server-side approval state. Plan approval is a real backend prerequisite for execution.

The simple UI deliberately omits graphs, animation, Monaco, a database, queues, and hosting. Future refinement should retain the current backend contract and security boundaries.

## Living Harness extension (0.2)

The working modules are extended by memory.py, trials.py, signals.py, harness.py, harness_schemas.py and trusted.py. The single existing orchestrator uses their actual evidence, keeps product approval before edits/semantic changes, and preserves the original MVP path. See [Living Software Harness](LIVING_HARNESS.md) for implementation boundaries, source-grounding, oracle independence, aggregate-only synthetic signals and trusted sample execution.
