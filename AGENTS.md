# GhostPatch contributor instructions

Read `GHOSTPATCH_CONTINUOUS_EVALUATION_ADDON.md`, `GHOSTPATCH_BACKEND_UPGRADE_CODEX.md`, and `GHOSTPATCH_MVP_CODEX.md` completely. Extend the existing Signals/Memory/Trials and their orchestration; do not create a fourth subsystem or separate dashboard. Work autonomously with a minimal frontend. Product approval before edits and semantic policy changes remains mandatory. Never commit, push, deploy, publish, or create paid resources without explicit authorization.

## Repository boundaries

- This directory is the GitHub-connected monorepo. Run frontend commands from `frontend/`.
- The sibling `../frontend/` is the preserved original repository. Do not modify or remove it as part of ordinary development.
- Retain the existing App Router `frontend/app/` layout. Create feature modules only when they have an implementation.
- Read `frontend/AGENTS.md` and the relevant installed Next.js guides before changing frontend code.

## Implementation rules

- Use the shared DTOs in `frontend/types/api.ts` for demo fixtures and future FastAPI responses. Document contract changes in `docs/API_CONTRACT.md`.
- The MVP UI calls the actual backend through `frontend/lib/api.ts`. No fabricated fixtures or simulated execution are used. The built-in sample is real synthetic code validated in Docker.
- Keep NVIDIA calls and credentials in the future backend. Never put secrets in `NEXT_PUBLIC_*` variables, tracked environment files, logs, or browser bundles.
- Never transmit repository source to a model provider without informed consent. Never execute imported code on the host or execute model-generated shell commands.
- Preserve immutable originals and isolate working copies. Archive validation, constrained patching, and a hardened Docker runner are required before those features can be enabled.
- Report actual tool evidence. Missing tests mean not verified; matching baseline tests do not prove correctness or security. Bound repair attempts to two.
- Use a minimal black-page UI with readable text, keyboard access, and visible loading/error/empty states. Do not add graph UI, animations, or Monaco for this MVP.
- Execute only the built-in developer-controlled sample in Docker. Uploaded/cloned repositories are always untrusted, including copies of the sample.

## Validation

From `frontend/`, run `npm.cmd run lint` and `npm.cmd run build`; verify local startup. Run backend pytest and real NVIDIA/Docker checks when available, report actual evidence, and fix failures. On other platforms, use `npm` in place of `npm.cmd`.
