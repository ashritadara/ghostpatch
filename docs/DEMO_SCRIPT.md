# Reproducible MVP demo

1. Start Docker Desktop. From the repository root build:
       docker build -t ghostpatch-runner:local backend/runner
2. Start FastAPI and Next.js using the root README.
3. Open http://127.0.0.1:3000. The UI should say Local MVP ? real backend.
4. Load trusted sample. Inspect real static findings and the execution policy.
5. Consent to relevant synthetic source disclosure to NVIDIA.
6. Generate a plan. Review the one-file scope and risks.
7. Approve and execute. Observe baseline, actual model patch, Docker validation, and any needed repairs.
8. Inspect 12 test results, five behavior comparisons, and the unified diff.
9. Approve the patch for this session and download it.

Do not promise a failure/repair on every model run. The real workflow may succeed on its first patch; report zero repairs when that occurs.

For deterministic real regression detection, run the opt-in test_real_docker_detects_regression_and_restored_sample_passes test. It introduces a known bad arithmetic change in an isolated sample, observes failing tests, restores the source, and observes passes. This is explicit test fault injection, not fabricated model activity.

The default tests also cover consent, approval, trust separation, invalid output, paths/archives, hashes, original preservation, missing Docker, zero tests, initial failure retention, and the two-repair bound. Model/runner doubles exist only in unit tests.

For an HTTP-only end-to-end check:
    .\backend\.venv\Scripts\python.exe -B scripts/verify_backend.py --run-model

For an untrusted-source demo, upload a small Python ZIP or import https://github.com/pypa/sampleproject. Static analysis is real. Any consented patch remains not_verified and the backend never executes that source.

No browser automation is required. Use the UI manually or inspect /docs and the HTTP check output.

## Living Harness judging demo

Use Load claims policy demo, consent, then Investigate rules, signals & trials. Inspect six passing existing tests beside the failing independent age-65 scenario, source-backed rules and synthetic override/reuse metrics. Select the independently evidenced inclusive-age correction, generate the plan and explicitly approve it. Review preserved versus intended-change outcomes, original/modified pytest logs, source provenance, uncertainty and exact diff. HTTP alternative: scripts/verify_upgrade.py --run-model --approve-demo-policy-change. See LIVING_HARNESS.md; no fake model/test outputs or real patient data are involved.
