# GHOSTPATCH — MASTER IMPLEMENTATION PLAN FOR CODEX / CLAUDE CODE

## 0. Mission and operating rules

You are the implementation agent for **GhostPatch**, a cyberpunk-styled, agentic legacy-software modernization platform intended for HackUTD's NVIDIA Nemotron and 8090 challenges. The product imports a legacy repository, diagnoses modernization opportunities, proposes scoped patches, actually edits an isolated working copy, runs tests and behavior comparisons, attempts bounded self-repair, and presents evidence for human approval and patch export.

**CRITICAL: PHASE GATES.** You MUST STOP and ask the human for explicit approval BEFORE beginning EACH numbered phase, including Phase 0. Do not interpret a previous approval as approval for the next phase. At the start of each phase, state (a) exact files to create/change, (b) commands/dependencies, (c) expected output, (d) risks, and ask: `Approve Phase N?`. Wait for an explicit affirmative response. After completing a phase, summarize what actually worked, files changed, test results, and blockers. STOP and ask approval for the following phase. If requirements change, ask again. Never run destructive commands, deploy, create paid cloud resources, publish, push to remote, or commit unless explicitly approved for that action. You may inspect existing files to formulate the plan before asking approval, but do not edit them.

**Never fake results:** mock data is allowed only in frontend demo mode and must be clearly marked. Real test passes, security findings, repairs, and API actions must come from actual tools. Do not promise perfect semantic equivalence or security.

**Priority:** a working, compelling solo-hacker MVP before optional features. Industry-neutral engine; demo with a small synthetic healthcare-claims application if workshop feedback supports it. Do not assume Medicare-specific requirements or use real patient data. Avoid PostgreSQL, Celery/Redis, multi-language, production hosting, GitHub PR automation, or elaborate multi-agent orchestration until MVP works.

## 1. Human prerequisites (do not silently assume installed)

Host: Windows 11, VS Code, PowerShell, optional WSL2. Before implementing, inspect environment and tell the human how to install or configure any missing prerequisite:
- Git and GitHub account, Git Credential Manager or GitHub authentication.
- Node.js **current supported LTS** and npm; check compatibility with current Next.js requirements.
- Python 3.12 with `py -3.12`, venv, pip.
- Docker Desktop with WSL2 backend; engine running and Linux containers available. Docker is required before executing imported repository code.
- NVIDIA hosted API access from NVIDIA Build (`https://build.nvidia.com/`), a valid `NVIDIA_API_KEY`, and a currently available, authorized **Nemotron** model ID. Verify model ID, availability, terms, endpoint, and response format; never hardcode an unverified model ID. Use OpenAI-compatible NVIDIA endpoint only if verified for the selected model. Never require local GPU/model download for the hosted-API path.
- Optional: Figma-generated frontend files, screenshots, or assets; inspect and preserve these if provided.

Human should create/clone GitHub repo named `ghostpatch`. Use a private repository until ready to publish. Avoid committing credentials, uploaded customer code, or confidential information. If repo already contains code, preserve it and propose a migration instead of overwriting.

Suggested checks (PowerShell):
```powershell
git --version
node --version
npm --version
py -3.12 --version
docker --version
docker info
```

## 2. Architecture and deliverables

One monorepo:
```
ghostpatch/
  AGENTS.md
  README.md
  .gitignore
  .env.example                 # root optional documentation only; no secrets
  docs/
    ARCHITECTURE.md
    API_CONTRACT.md
    DEMO_SCRIPT.md
    SECURITY.md
  frontend/
    package.json
    .env.example
    src/
      app/
        layout.tsx
        page.tsx
        globals.css
      components/
        layout/
        upload/
        diagnosis/
        modernization/
        agent/
        diff/
        validation/
        ui/
      lib/
        api.ts
        demo-mode.ts
      data/
        mock-repository.ts
        mock-events.ts
      types/
        api.ts
  backend/
    pyproject.toml             # or requirements.txt; choose one canonical dependency strategy
    .env.example
    app/
      main.py
      core/config.py
      api/routes/{health,repositories,analysis,jobs,results}.py
      schemas/{repository,analysis,job,event,result}.py
      services/{repository_store,scanner,planner,patcher,validator,orchestrator,exporter}.py
      integrations/nemotron.py
      security/{paths,archive,sandbox}.py
    tests/
  sample_repositories/
    toy_legacy/
    claims_demo/               # optional only after workshop confirmation
  scripts/
```
Adapt filenames to the real scaffold, avoid empty placeholder modules and unnecessary abstractions. Update documentation when architecture changes.

**Stack:** Next.js App Router + TypeScript + Tailwind CSS, Lucide React, Motion (current package, e.g. `motion`), React Flow (`@xyflow/react`) for dependency graph, Monaco React for code diffs, Recharts only if needed. FastAPI, Pydantic, Python 3.12, pytest, httpx, NVIDIA hosted Nemotron client, stdlib `difflib`/Git where appropriate. Prefer fetch + SSE (EventSource or fetch streaming as needed) over introducing WebSocket infrastructure prematurely. Start with in-memory job state for one-user local demo, persisting artifacts to isolated per-job directories; make limitations explicit. No database required for MVP.

## 3. Product flow and API contract

User journey: Import ZIP or a permitted Git URL -> inspect files/dependency map -> Nemotron proposes modernization plan -> user explicitly approves plan -> agent patches isolated copy -> sandbox tests -> compare behavior against fixture baseline -> bounded repair attempts -> show event timeline/diff/test evidence -> user approves/rejects and exports patch.

Design stable typed schemas BEFORE wiring UI:
- `RepositorySummary`: id, name, language, file_count, dependency_count, import_status.
- `Diagnosis`: issues with id, file path, line span if known, category, severity, explanation, evidence, recommendation, confidence; graph nodes/edges; counts. Severity is a heuristic, not a verified security score.
- `ModernizationPlan`: id, repository_id, objective, candidate files, proposed steps, risks, test strategy, approval status.
- `Job`: id, repository_id, plan_id, status (queued/running/needs_approval/succeeded/failed/cancelled), started_at, completed_at.
- `AgentEvent`: id, job_id, timestamp, phase, tool, status, message, affected files, structured details. Emit only real events in live mode.
- `ValidationResult`: test command, exit code, duration, passed/failed/skipped counts if parseable, stdout/stderr excerpts, baseline comparisons, warnings, repair attempts.
- `PatchResult`: changed files, unified diffs, final outcome, export link or patch artifact.

Proposed routes (adjust with explicit approval and document contract):
- `GET /api/health`
- `POST /api/repositories/upload` (bounded ZIP)
- `POST /api/repositories/import-git` (optional later; safe allowlist/guardrails)
- `GET /api/repositories/{id}`
- `POST /api/repositories/{id}/analyze`
- `GET /api/repositories/{id}/diagnosis`
- `POST /api/repositories/{id}/plans`
- `POST /api/plans/{id}/approve`
- `POST /api/plans/{id}/execute`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/events` (SSE)
- `GET /api/jobs/{id}/results`
- `GET /api/jobs/{id}/patch` (download)

Do not implement everything at once. Ensure demo mode uses the SAME data shapes as live mode. Frontend must never call NVIDIA directly or expose API keys.

## 4. Phased execution — explicit human approval required at every phase

### Phase 0 — Audit and setup plan (approval required)
- Inspect current repo, Git status, installed tool versions, existing Figma code/assets, existing AGENTS.md, and frontend/backend folders.
- Explain missing installs, confirm repo structure and naming, verify no secrets in repo.
- Present a minimal command-by-command plan. Do not modify files until approved.
- Deliverable: inventory and proposed file change list.
- STOP and request Phase 1 approval.

### Phase 1 — Monorepo + frontend scaffold
- Preserve existing work. If no frontend exists, create current stable Next.js App Router TypeScript + Tailwind + ESLint app under `frontend/` using noninteractive flags where appropriate.
- Create root README, `.gitignore` for `.env*` (while allowing `.env.example`), `node_modules`, `.next`, Python caches/venvs, uploads, working copies, secrets; initial docs.
- Add a minimal shared TypeScript API schema and demo/live configuration switch.
- Install only necessary frontend dependencies: `lucide-react`, `motion`, `@xyflow/react`, `@monaco-editor/react`; add `recharts` only if needed. Avoid unused packages.
- Validate `npm run dev`, `npm run lint` (or project equivalent), `npm run build`.
- STOP and request Phase 2 approval.

### Phase 2 — Cyberpunk landing page and upload UI
- Build GhostPatch branding (render `GHOST//PATCH` if desired visually, product name remains GhostPatch).
- Palette: near-black `#08080D`, charcoal `#15151F`, off-white `#F5F5F7`, neon pink `#FF2D8D`, magenta `#E60073`, purple `#8B5CF6`; warnings amber, success green.
- Desktop-first responsive, accessible contrast, reduced-motion support, subtle glitch/grid/particle ambiance; no excessive animations.
- Landing hero `Give Old Code a New Life`, ZIP dropzone with type/size validation, Git URL input clearly marked upcoming if backend isn't ready, CTA, sticky navigation, scroll sections.
- Use mock upload result in clearly labeled DEMO MODE. Do not pretend file was analyzed.
- If Figma assets are supplied, match their structure/appearance rather than replacing them.
- Validate responsive states and build.
- STOP and request Phase 3 approval.

### Phase 3 — Visual diagnosis dashboard (frontend only)
- Create immersive scrollable diagnosis workspace, repository overview, issue severity counters, file list.
- **Centerpiece:** React Flow dependency graph of files/modules and edges, severity-colored nodes (critical pink/red, warning amber, healthy green), zoom/pan, click node for evidence and recommended change; include legend and list alternative for accessibility.
- Show connected impact/highlighted neighbors on node selection; no made-up precise health score unless explicitly labeled illustrative heuristic.
- Realistic sample data typed to backend contract; clear DEMO MODE label.
- Include `Generate Modernization Plan` CTA and plan preview.
- STOP and request Phase 4 approval.

### Phase 4 — Live-agent and verification UI (frontend only)
- Plan review and explicit `Approve & Execute` control.
- Live workspace: agent tool timeline, status/progress, terminal log excerpts, file changes, Monaco before/after diff, test results, regression/repair events.
- Results: summary of tests and behavior comparisons, failed repairs, warnings, approve/reject/export controls. Demo interactions should work against deterministic mock event sequences and be labeled simulated.
- Do not claim that clicking buttons modifies real files until integrated.
- Ensure mobile fallback and keyboard-accessible actions.
- STOP and request Phase 5 approval.

### Phase 5 — FastAPI foundation and safe repository import
- Set up Python 3.12 virtual environment and dependency manifest. Add FastAPI app, health endpoint, CORS restricted to local frontend origin, config via env.
- Implement bounded ZIP import into per-job isolated directory, preserve original immutable copy, create separate working copy.
- Reject zip-slip path traversal, symlinks/hardlinks and dangerous archive entries, absolute paths, oversized archives, excessive file counts, nested archive abuse, path escapes; never execute files on import.
- Ignore `.git`, `node_modules`, virtualenvs, binaries and sensitive files. Implement file size caps and language detection for Python-only MVP.
- Unit tests for upload and path safety, API smoke tests, docs for local run.
- STOP and request Phase 6 approval.

### Phase 6 — Deterministic analyzer + frontend API connection
- Analyze Python file structure with AST where feasible, imports, requirements, simple module dependencies, TODOs, targeted outdated constructs; clearly separate deterministic facts from LLM suggestions.
- Return graph nodes/edges and issue evidence in documented API schemas. Handle parse errors gracefully.
- Wire upload/diagnosis UI to backend; retain explicit demo mode for offline development; loading, failure, empty states.
- Do not claim vulnerability detection from simple heuristics.
- STOP and request Phase 7 approval.

### Phase 7 — NVIDIA Nemotron analysis and planning
- Implement server-side NVIDIA API integration using a verified hosted endpoint/model ID from environment variables. `.env.example` includes placeholders: `NVIDIA_API_KEY=`, `NVIDIA_MODEL=`, `NVIDIA_BASE_URL=`. Never commit actual secrets or send sensitive repositories without user consent.
- Validate structured outputs with Pydantic, robust parsing, timeouts, bounded retries, token/context limits, minimal relevant file excerpts, redaction of common secret patterns, clear failures if API unavailable.
- Generate scoped modernization plan and test strategy, citing actual files and evidence. Never execute generated shell commands from LLM output.
- Require explicit plan approval before any patch. Unit tests with mocked Nemotron client.
- STOP and request Phase 8 approval.

### Phase 8 — Real patch application and diff
- Implement safe, constrained file editing in isolated working copy only, with allowlisted paths, optimistic file hashes, atomic writes, syntax validation, rollback snapshots, bounded patch sizes.
- Nemotron proposes patches; deterministic patch tool applies them and reports exact changes. No direct arbitrary command execution from model.
- Generate unified diffs; show them in Monaco; preserve original source. Test patch apply, rejection and rollback.
- STOP and request Phase 9 approval.

### Phase 9 — Isolated test runner and behavioral regression checks
- Docker required for executing imported code. Create hardened local test sandbox with non-root user, no network, read-only base image/root filesystem where practical, only necessary writable mounts, CPU/memory/PID/time limits, no privileged mode, no host Docker socket, no secrets, no host source write access except isolated working directory where necessary. Treat Docker as risk reduction, not a perfect security boundary; for untrusted public code prefer stronger isolation and don't run it on sensitive hosts.
- Use a fixed allowlisted pytest command and controlled environment; never blindly run project-provided setup scripts or LLM-proposed commands. Prebuild vetted images; do not pip install arbitrary dependencies from imported code automatically.
- Run baseline tests on original copy and same tests on modified copy; capture stdout/stderr, exit codes, timeouts, test counts, and fixture-based input/output behavior comparisons.
- Important: matching baseline is not proof of correctness; if baseline is wrong, report that caveat. If tests are absent, say 'not verified' and block claims of preserved behavior.
- STOP and request Phase 10 approval.

### Phase 10 — Bounded Nemotron self-repair loop and real event stream
- Orchestrator: analyze -> plan -> human approve -> patch -> test -> diagnose failure -> attempt up to 2 repairs -> retest -> finalize. Store exact events, patch attempts, and evidence.
- Self-repair must be deterministic/bounded, no infinite loops. If unsuccessful, return failed/needs-review and offer rollback, never greenwash.
- Expose SSE event stream; connect to frontend timeline, code diff, graph statuses, and validation panels. Add cancel/timeout handling if feasible.
- Distinguish model reasoning summary from tool execution logs; never fabricate internal chain-of-thought.
- STOP and request Phase 11 approval.

### Phase 11 — Realistic demo repo and end-to-end polish
- Build a small **fictional** Python legacy app (industry chosen after 8090 workshop; healthcare claims only if appropriate) with documented synthetic inputs and expected outputs, intentionally outdated but reproducible API usage, and tests that detect a meaningful regression.
- Demo: upload -> graph -> plan -> approve -> real patch -> failing test -> bounded repair -> passing tests -> inspect diff -> export patch. Ensure failure and repair actually occur, not scripted false outputs. If repair is nondeterministic, have a separate reproducible validation path and be transparent.
- Test clean-install instructions on Windows, browser accessibility, API failures, no-key mode, no-Docker mode, ZIP security, build, pytest, lint.
- Write `docs/DEMO_SCRIPT.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, README setup and troubleshooting. Record known limitations.
- STOP and request Phase 12 approval.

### Phase 12 — Optional extras ONLY if time remains
- Real open-source repo smoke test with license compliance, performance profiling, Git patch export, lightweight job persistence, GitHub OAuth/PR integration, richer impact visualization, more languages. Do not sacrifice working MVP for these.
- Ask approval separately for each optional extra.

## 5. Development commands (adapt to generated manifests)

Frontend PowerShell:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000`.

Backend PowerShell:
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# install dependencies according to generated pyproject.toml / requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/docs`.

For PowerShell execution-policy problems, prefer invoking `.venv\Scripts\python.exe` directly rather than weakening machine-wide policy.

## 6. Security, honesty, and integration rules

- Frontend has no NVIDIA secret; backend uses environment variables. `.env.example` only placeholders.
- No external uploads of repository source to NVIDIA without informed consent; demo uses synthetic or explicitly authorized code.
- Treat repositories and model output as untrusted. No host-shell execution of imported code; no arbitrary LLM shell commands.
- Safe ZIP extraction, directory isolation, resource caps, network restrictions, file allowlists, rollback.
- No actual claims-processing correctness or regulatory compliance assertions. Sample payment rules are fictional.
- Never infer a pass from a zero exit code alone if tests didn't execute; parse and report no-tests condition.
- Mock UI data is labeled. In live mode, show only backend-grounded events and statuses.
- Use semantic HTML, keyboard support, contrast, reduced-motion support, loading/error/empty states.
- Prioritize clean, small, maintainable code and real test coverage over ornate architecture.

## 7. Required agent response format at each gate

Before each phase, respond with:
```
PHASE N — <title>
Goal:
Files to create/change:
Commands/dependencies:
How I will verify:
Risks or decisions:
Approval needed: Approve Phase N?
```

After each phase, respond with:
```
PHASE N COMPLETE
Files changed:
Commands run:
Tests/build results (actual):
Known issues:
Next proposed phase:
STOP — awaiting approval for Phase N+1.
```

Do not skip phase gates even if the human says 'build everything' unless they explicitly change this instruction. Start by inspecting the repository and proposing Phase 0; **do not edit files before approval**.
