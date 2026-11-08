# Cyberpunk frontend and real backend workflow

The existing Next.js backend UI is shared by the basic page and the cyberpunk
scene. FastAPI, NVIDIA integration, Docker execution, DTOs, and approval endpoints
are unchanged. There are no mock results or simulated AI tasks.

## Open locally

Start FastAPI as documented in the root README, then start Next.js from
`frontend/` with `npm.cmd run dev -- --hostname 127.0.0.1 --port 3000`.

- Combined scene: http://127.0.0.1:3000/cyberpunk
- Original basic interface: http://127.0.0.1:3000
- Embedded interface: http://127.0.0.1:3000/scene-workspace
- API documentation: http://127.0.0.1:8000/docs

The `/cyberpunk` handler serves only the fixed repository-root
`cyberpunk_front.html` file; it does not expose a directory or arbitrary paths.
Run Next.js from `frontend/` and retain that HTML file beside the frontend folder.
The existing standalone preview on loopback port 3001 is also supported.

## Diamond mapping

| Diamond | Real controls and evidence |
| --- | --- |
| 1 | Existing city introduction and cursor ghost; no model execution |
| 2 | 1. Import and analyze: ZIP, GitHub, trusted samples; source-disclosure consent and real Nemotron connectivity validation |
| 3 | 2. Static analysis: findings, files, dependencies, trust/execution policy |
| 4 | 3. Nemotron planning: Ghost Memory, Signals and Trials investigation, synthetic windows, explicit policy approval, semantic scope, plan generation and approval |
| 5 | 4. Actual execution events, Docker baseline/modified tests, bounded repairs and behavior comparisons |
| 6 | 5. Exact diff, session-only patch approval/rejection, and patch download |

Previous/Next and the diamonds change the visible step. The backend interface is
loaded once, on first entering diamond 2 or later, and remains mounted when
changing diamonds or returning to the intro. Repository, consent, objective, plan,
job polling, selected rule changes, and review state are retained during those
transitions. Scrolling inside the workspace scrolls its evidence; use the diamonds
or Previous/Next to move deliberately between steps.

Next is disabled until a repository is loaded for analysis, until execution has
started for the execution step, and while waiting for results. Direct diamond
navigation always remains available, with actionable empty states for unfinished
steps. Navigation never approves a plan, invokes a model, or starts tests.

## Data, approval, and integration boundaries

- The iframe uses the existing `frontend/lib/api.ts` and shared DTOs. Its requests
  originate from the existing allowed Next.js origin; no backend CORS expansion
  or security changes are needed.
- Window messages carry only readiness, chapter navigation and actual pointer
  positions. Both sides check the window and local origin. Messages cannot invoke
  backend operations or grant source-disclosure/plan/policy consent.
- Plan and fictional-policy approvals use a scoped in-page confirmation dialog,
  with Cancel focused initially. Confirmation checks that the repository/plan
  still matches the displayed scope. Changing diamonds dismisses pending approval.
  This also avoids [cross-origin JavaScript-popup restrictions in Chrome](https://developer.chrome.com/blog/deps-rems-91)
  when using the standalone port-3001 preview. Backend approval requirements are
  unchanged.
- The cursor ghost follows the pointer inside the panel as well as the scene.
  Only its tail uses idle animation. Scene progress still requires click/scroll.
- NVIDIA validation is a real small final-response check, not a code verification
  result. Plans, investigations, edits and tests require their respective controls.
- Uploaded and GitHub repositories remain static-analysis-only for execution;
  only pinned, built-in developer-controlled samples can execute in Docker.
- Refreshing the scene resets the iframe's UI session. No new persistence is
  claimed. Backend IDs still expire on restart or cleanup, and final patch review
  remains session-only. Do not treat navigation as cancellation of a running job.
- Startup failures show connection guidance, Retry connection, and a link to the
  basic interface. Retrying before readiness reloads the iframe.

## Checks

Run from the repository root:

    node scripts/verify_scene.cjs

This exercises the actual standalone controller with a small DOM substitute:
origin/source filtering, malformed message rejection, six-step navigation,
single iframe loading, rewind, cursor relay and absence of scene autoplay. It is
not a browser layout or React hydration test.

Run frontend lint/build from `frontend/`, and the existing backend pytest suite
from `backend/`, as documented in the root README. Model/Docker execution is
never fabricated by the frontend or the controller check.

Local integration verification (2026-11-08):

- `npm.cmd run lint`: passed.
- `npm.cmd run build`: passed with no build warnings after adapting the scoped
  styles to the project's existing CSS loader.
- `node scripts/verify_scene.cjs`: passed.
- `/`, `/scene-workspace`, `/cyberpunk`: HTTP 200. The combined route returns the
  exact HTML file, with no-store caching; a `file` query cannot select another
  file. The outer standalone preview copy matches the canonical repository copy.
- Backend `pytest -q`: 94 passed, 6 opt-in live integration tests skipped. The
  existing httpx/Starlette deprecation warning remains.
- Backend health: connected, NVIDIA configured, Docker/image available. No new
  live model planning, approved patch, Docker job, or download is claimed by
  these integration checks.
- Browser automation was unavailable; React hydration, real cross-frame pointer
  behavior, and the complete live workflow still need a browser smoke test.
