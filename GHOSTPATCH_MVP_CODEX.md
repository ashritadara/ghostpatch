# GhostPatch: Autonomous MVP Implementation Instructions

## Priority and operating mode
Build a working end-to-end GhostPatch MVP now. This document **supersedes the approval gates and frontend-first sequencing** in `GHOSTPATCH_CODEX_MASTER_PLAN.md` wherever they conflict. Inspect the repository first, then implement continuously without stopping for phase approval. Prioritize real backend functionality and integration over visual polish. Do not push commits, deploy, spend money, or expose secrets without explicit authorization.

## Goal
GhostPatch modernizes legacy Python repositories with NVIDIA Nemotron. It ingests source, performs static analysis, proposes a bounded modernization, edits an isolated copy, runs real baseline and post-edit tests in Docker for trusted sample projects, detects regressions, attempts up to two repairs, and returns verifiable diffs, logs, and results. Never fabricate outputs or claim universal behavior preservation.

## Stack
- Existing `frontend/`: Next.js, React, TypeScript, Tailwind. Keep styling minimal: black background and readable text.
- `backend/`: Python 3.12, FastAPI, Pydantic, OpenAI-compatible Python SDK, python-dotenv, pytest.
- NVIDIA hosted endpoint configured through `backend/.env`: `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`. Never hardcode credentials. Use model ID from environment, not a guessed default.
- Docker Desktop with WSL2 for trusted sample-repository test execution. No database required for MVP.

## Work sequence (no approval gates)

### A. Inspect and bootstrap
1. Inspect existing files, package scripts, environment, `.gitignore`, and any prior plan. Preserve working functionality.
2. Set up modular backend dependencies, configuration, schemas, service modules, error handling, and documentation.
3. Ensure `.env`, uploaded source, temporary workspaces, and artifacts with sensitive content are gitignored. Create `.env.example` with placeholders only. Do not print or log API keys.

### B. Minimal frontend
Implement a simple black-page UI with GhostPatch heading, ZIP picker, GitHub URL field, Analyze button, status/progress, analysis and modernization plan, activity log, test results, unified diffs, errors, and patch download. Connect to actual FastAPI endpoints. Clearly identify unsupported features. No animations, dependency-graph UI, Monaco, or cyberpunk redesign now. Avoid misleading mock results.

### C. Repository ingestion and static analysis
- Accept ZIPs with strict size/file-count/uncompressed-size limits; reject zip-slip paths, symlinks, path escapes, and dangerous entries. Store in job-specific temporary directories.
- Validate GitHub URLs against an allowlist of `github.com` HTTPS repository URLs; clone with bounded size/time and no credentials. Treat cloned code as untrusted.
- Scan Python source without executing it. Extract files, imports, local dependencies, and modernization candidates. Return grounded findings with file paths and line numbers when possible.
- Preserve original files. Use a separate writable working copy for modifications.

### D. Nemotron connection and agent
- Read NVIDIA configuration from `.env` with python-dotenv. Call `https://integrate.api.nvidia.com/v1` or configured base URL using OpenAI-compatible SDK.
- Add a connectivity test that verifies meaningful final text or structured output. Handle reasoning fields, `None` content, length-limited responses, invalid JSON, authentication, rate limits, and transient errors with bounded retries.
- Use structured, validated requests/responses for diagnosis, prioritized modernization plan, patch proposals, and repair suggestions. Never blindly trust model output.
- Constrain patches to allowlisted project-relative paths, reject traversal and unexpected binary edits, and capture exact diffs.

### E. Docker test runner
- Implement a test runner interface with a Docker implementation. Run code **only for explicitly allowlisted, developer-controlled sample repositories** in MVP. Arbitrary uploaded/cloned repositories may be analyzed but must never be executed.
- Run baseline tests on an original snapshot, then the same tests on the modified copy. Capture exit codes, stdout/stderr, test counts where available, durations, and structured comparison.
- Use non-root user, no privileged mode, no Docker socket mounts, disabled networking where feasible, CPU/memory/PID limits, bounded wall time, and appropriately read-only mounts. Do not assume Docker is a perfect security boundary.
- Support pytest and deterministic input/output checks when present. Fail safely when Docker is unavailable.

### F. Modernize, verify, repair
1. Ingest and statically analyze repository.
2. Ask Nemotron for a specific, bounded modernization plan.
3. Apply one selected change to the working copy, not original.
4. Run Docker baseline and post-change tests only if repo is trusted and allowlisted.
5. Compare actual outcomes, surface regressions, and send relevant failure information to Nemotron.
6. Attempt at most two bounded repair iterations, retesting after each.
7. Return original/modified diffs, test results, activity timeline, repair attempts, final status, and a patch ZIP or diff for user review.
8. For untrusted uploads, stop before execution and explicitly report that verification was skipped.

### G. APIs and integration
Implement sensible endpoints for ZIP/GitHub submission, job creation, status/progress, static findings, modernization plan, starting approved/supported transformations, activity, test results, diffs, and patch download. Use in-memory or filesystem job persistence for MVP, with clear limits. Use polling from frontend initially. Validate request payloads and return actionable errors.

### H. Reproducible demo and tests
Create one realistic, small, trusted legacy Python sample repository with meaningful pytest tests and a deterministic modernization scenario. Where feasible, demonstrate a regression being detected and a subsequent repair. Do not hardcode fabricated model output or test success. Add unit tests for ingestion, path safety, analysis, patch validation, API schemas, and test runner behavior; integration tests for the real workflow when Docker and NVIDIA credentials are available.

## Engineering requirements
- Modular code with explicit interfaces for model client, repository loader, analyzer, patcher, runner, and job orchestration.
- Reasonable timeouts, input limits, error reporting, logs without secrets, and cleanup of temporary workspaces.
- Never execute arbitrary uploaded code on the host or inside the MVP Docker runner. Restrict executable demos to known trusted samples.
- Make no claims of behavior preservation beyond observed tests.
- Avoid PostgreSQL, extra services, elaborate frontend components, and premature optimization.
- If API or Docker access is unavailable, complete the rest and report the exact blocker. Do not invent passing results.
- Update README with Windows PowerShell setup and commands for backend, frontend, Docker validation, demo, and tests.

## Completion criteria
- User can launch frontend and backend locally.
- User can upload a ZIP or submit an allowed GitHub URL for real static analysis.
- Nemotron generates a usable modernization plan and bounded code patch when credentials are valid.
- Trusted sample project can be tested before/after with Docker, with actual failures and repair attempts reported.
- User can inspect real diff/results and export patch.
- Tests run; README documents what works and known limitations.

## Final report
At the end, summarize files created/changed, functionality completed, tests actually run and their results, outstanding limitations, and exact local launch commands. Proceed without intermediate approval requests unless a truly external blocker requires user action.
