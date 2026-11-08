# GhostPatch MVP

GhostPatch statically analyzes legacy Python repositories, asks a configured NVIDIA Nemotron model for one bounded modernization, patches an isolated working copy, and exports exact diffs. Only the pinned, developer-controlled samples may execute in restricted Docker containers. Uploaded/cloned repositories never execute.

This is a local, single-user MVP. The minimal black-page frontend calls the real FastAPI backend; it has no mock outputs, animations, graph UI, or Monaco. GHOSTPATCH_MVP_CODEX.md supersedes the previous master plan's approval gates and frontend-first sequence.


## Backend upgrade: Ghost Memory, Ghost Trials, Ghost Signals

The existing backend is extended in place by GHOSTPATCH_BACKEND_UPGRADE_CODEX.md. The original expense-report path remains available; the new claims policy demo is the primary investigation workflow.

- **Ghost Memory:** source-validated rule candidates, independent policy references, uncertainty, conflicts and version history.
- **Ghost Trials:** independent policy/observation/invariant/hypothesis oracles, identical original/modified Docker scenarios, explicit semantic approval, and a Behavior Preservation Report.
- **Ghost Signals:** bounded synthetic-only JSON/JSONL ingestion, aggregate metrics with denominators, before/after fixture windows, and source-backed Nemotron hypotheses. No real-user tracking.
- Existing safe imports, original-preserving patches, two-repair bound, logs, diff/export, and trusted-only execution remain.

Open the basic frontend and choose **Load claims policy demo**, check consent, and click **Investigate rules, signals & trials**. The six existing tests pass while a real age-65 policy mismatch is exposed. Select the specific correction, generate a plan, and explicitly approve that semantic change before patching.

HTTP demo from this repository root:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py --run-model --approve-demo-policy-change

Actual verification, extended API, oracle semantics, fixture counts, retention and security limits are documented in [Living Software Harness](docs/LIVING_HARNESS.md) and [Upgrade notes](docs/UPGRADE_NOTES.md). Saved real evidence is under ignored .ghostpatch/last-upgrade-evidence.json.

The before/after usage fixtures are authored synthetic windows, not measured real-user retention or post-patch improvement. Only pinned developer-controlled samples execute; uploaded/cloned repositories remain unverified.

## Continuous evaluation (0.3)

The existing three features now support explicit observation windows, optional stable synthetic user IDs, honest unavailable return metrics, software-version comparisons, input-category drift, competing explanations, approved policy-version history, and bounded idempotent re-evaluation. New evidence can run trusted Trials, but it never authorizes edits. Fresh follow-up plans still require human approval; each job retains its own patch and evidence.

From this repository root, with the backend running:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_upgrade.py --continuous --run-model

This investigates two synthetic windows without approving a patch. The explicitly approved two-policy demo adds --approve-demo-policy-change --approve-demo-policy-update. See [continuous demo, metric definitions and limits](docs/LIVING_HARNESS.md#continuous-evaluation-extension-03) and [exact API payloads](docs/API_CONTRACT.md#continuous-evaluation-api-additions-03).

## Project location

Use this GitHub-connected repository as the project root:

    C:\Users\ashri\Downloads\ghostpatch\ghostpatch

The original sibling frontend repository and the user's outer backend configuration/test script are preserved. The existing NVIDIA configuration was copied into this repository's ignored backend/.env without exposing its key.

## Start the backend (PowerShell, terminal 1)

From this repository root:

    Set-Location backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

If backend/.env does not already exist, copy .env.example to .env and edit it locally. Do not overwrite an existing configured file. Set NVIDIA_API_KEY, NVIDIA_BASE_URL, and NVIDIA_MODEL using your authorized hosted-model settings. No model ID or credential is hardcoded. Never put keys in frontend variables or chat.

    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

API documentation: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/api/health

No activation script or PowerShell execution-policy change is needed. Bind to loopback only and use one worker; the service has no authentication or multi-user isolation.

## Prepare Docker (from repository root)

Start Docker Desktop with its Linux engine, then build the fixed test image:

    docker info
    docker build -t ghostpatch-runner:local backend/runner

The image build installs vetted runner dependencies. Runtime containers never install dependencies, pull images, use networking, receive credentials, or mount the Docker socket. The backend reports an actionable not-verified result if the engine/image is unavailable.

## Start the frontend (terminal 2)

    Set-Location frontend
    npm.cmd ci
    npm.cmd run dev -- --hostname 127.0.0.1

Open http://127.0.0.1:3000. The public backend origin defaults to http://127.0.0.1:8000. To change it, use an ignored frontend/.env.local based on .env.example, then restart development or rebuild production. Public variables must never contain secrets.

Use npm.cmd on PowerShell to avoid npm.ps1 script-policy errors. On other platforms, npm works. The UI uses system fonts and does not require Google Fonts downloads.

## Produce real output

1. Click **Load trusted sample**. This copies and analyzes the pinned synthetic legacy_reports project.
2. Read the findings. Check the disclosure-consent box to permit relevant source/failure excerpts to NVIDIA.
3. Click **Generate plan**. Review the selected file, objective, risks, and validation strategy.
4. Click **Approve & execute** and confirm the displayed scope.
5. Watch actual activity, Docker baseline/post-edit output, and any regression-repair attempts. The original 12 tests and five input/output probes are reused unchanged.
6. Review the exact unified diff. **Approve patch** enables **Download patch**. Final review is session-only and does not merge, apply to your repository, deploy, or persist an approval decision.

Alternatively, select a ZIP or submit a small public HTTPS github.com/owner/repository URL. Both receive real static analysis. Consented planning and patch export work for small eligible Python files, but code execution is prohibited and verification remains **not_verified**. Uploading an identical copy of the built-in sample does not confer trust.

To run the same sample flow over HTTP from the repository root:

    .\backend\.venv\Scripts\python.exe -B scripts/verify_backend.py --run-model

This explicitly sends synthetic sample excerpts to NVIDIA. It prints the real result and saves ignored evidence under .ghostpatch/. No API key is printed.

## Tests and checks

Backend unit/API/security tests (from backend/):

    .\.venv\Scripts\python.exe -B -m pytest -q

Opt-in integration checks use real Docker, NVIDIA, and the public pypa/sampleproject GitHub repository:

    $env:GHOSTPATCH_RUN_INTEGRATION='1'
    .\.venv\Scripts\python.exe -B -m pytest tests/test_live.py -q -s
    Remove-Item Env:\GHOSTPATCH_RUN_INTEGRATION

The Docker regression check deliberately changes a copied sample to double amounts, observes real failing tests, restores it, and observes passing tests. This fault injection is a validation test, not a claim that Nemotron created or repaired that regression. Unit orchestration tests use explicit test doubles to verify the two-repair bound. Application endpoints never use those doubles.

Frontend (from frontend/):

    npm.cmd run lint
    npm.cmd run build

Backend tests, real service workflow, and frontend lint/build have been exercised. Browser automation was unavailable and was stopped; no browser-interaction test is claimed. The test client currently reports a dependency deprecation warning about httpx; it does not affect the passing checks.

## Limits and safety

- Python-only, UTF-8 text; one existing source file per plan; at most two model repair attempts. Test files, dependencies, and runner files cannot be patched.
- ZIP: 20 MiB compressed, 50 MiB declared uncompressed, 1 MiB/file, 500 entries, bounded ratio/path depth. Nested archives, links, traversal, special entries, case collisions, sensitive files, and binaries are rejected or skipped.
- Git: public HTTPS github.com repository URLs only, shallow clone with no checkout/hooks/credentials, bounded time/storage/output. No submodules, private repos, redirects, or arbitrary hosts.
- Model output is untrusted: JSON/Pydantic validation, allowlisted paths, optimistic hashes, syntax validation, atomic replacement, bounded context/output/retries. Invalid output is an error, not a fabricated success.
- Trusted execution: hash-pinned built-in source, unchanged tests/fixtures, non-root Docker user, read-only mounts/root, no network, dropped capabilities, CPU/memory/PID/time/output limits.
- A passing baseline is required for post-change behavior verification. No tests or unavailable counts never count as a pass. Matching tests/fixtures do not prove general correctness, equivalence, or security.
- In-memory IDs; maximum 20 known repositories. Inactive known workspaces are lazily cleaned after six hours, and clean shutdown removes owned workspaces. Job links using ?job=ID restore actual results while the backend is running; unexecuted selections and final review decisions are not persisted. A crashed server can leave ignored directories requiring local cleanup.
- No authentication, durable job store, cancellation, remote deployment, PR automation, arbitrary dependency installation, or public hosting. Keep the service on your own machine.

If the restricted agent account cannot see Python, Docker, or the npm cache, run the commands from your normal Windows account. Do not reinstall working prerequisites based solely on sandbox visibility.

See docs/ARCHITECTURE.md, docs/API_CONTRACT.md, docs/SECURITY.md, and docs/DEMO_SCRIPT.md.
