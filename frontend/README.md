# GhostPatch frontend

Minimal Next.js/React/TypeScript UI connected to the real FastAPI backend. Black background, readable boxes, basic controls, and actual evidence; no demo fixtures, graph, animations, or Monaco.

From this directory:

    npm.cmd ci
    npm.cmd run dev -- --hostname 127.0.0.1

Open http://127.0.0.1:3000 with the backend running on http://127.0.0.1:8000.

    npm.cmd run lint
    npm.cmd run build

lib/api.ts resolves the public backend origin, sends typed requests, and downloads patch artifacts. types/api.ts mirrors backend/app/schemas.py. The page polls queued/running jobs every two seconds and never replaces errors with mock data. Final approve/reject decisions are session-only.

NEXT_PUBLIC_API_BASE_URL can be set in an ignored .env.local. It must be an HTTP(S) origin without credentials/path/query/fragment; Next.js inlines it at build time. Never place an NVIDIA key in frontend configuration.

The original sibling frontend repository is preserved. This copy is the canonical application. Read AGENTS.md and the relevant installed Next.js guides before changes.

See the root README for backend setup, Docker build, trusted sample workflow, tests, and limitations.

## Living Harness evidence

The same basic black UI now exposes Ghost Memory rules/provenance/history, Ghost Signals synthetic aggregates/hypotheses, and Ghost Trials independent outcomes. Load claims policy demo, consent, investigate, select an evidenced semantic correction, generate the plan and approve. The backend enforces matching rule IDs and investigation revision. components/harness-evidence.tsx only presents server evidence; it does not invent oracles or execute code. See docs/LIVING_HARNESS.md at repository root.
