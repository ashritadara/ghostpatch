# Security implementation and limits

This is a local single-user MVP, not a public code-execution service. Bind FastAPI to 127.0.0.1, use one worker, and do not expose it through a tunnel. Host and Origin restrictions are not authentication.

## Ingestion

ZIP limits: 20 MiB compressed, 50 MiB declared uncompressed, 1 MiB per file, 500 entries, ratio 200, bounded path length/depth. HTTP receipt is limited even without Content-Length. Reject traversal, absolute/drive/backslash/ADS paths, Windows reserved names, control characters, links/special entries, unsupported/encrypted ZIPs, duplicate/case-colliding paths, and nested archives. Validate actual entry length. Keep supported UTF-8 text only; skip .git, dependencies, virtualenvs, binaries, and common sensitive filenames.

Git accepts only canonical public HTTPS github.com/owner/repository URLs. It disables credentials/global/system config, prompts, redirects, checkout, and templates. No imported hooks, scripts, filters, setup, or code are run. Shallow cloning and object inspection have time, storage, file-count, file-size, and output budgets. Git itself remains trusted host software.

## Patches and provider data

Original and working source are separate. Patches replace one approved existing Python source file, never tests, runner files, dependencies, or arbitrary paths. Verify current SHA-256, validate syntax, bound file/diff sizes, and write atomically with rollback on write failure. Recheck original hashes before patching and diff generation. Baseline tests are always taken from the original snapshot.

Only relevant bounded source/evidence excerpts are sent to NVIDIA after explicit consent. Keys remain in the backend's ignored .env. Common secret-pattern redaction reduces accidental disclosure but cannot guarantee confidentiality. Never upload confidential repositories without appropriate authorization.

Model output is untrusted JSON validated by Pydantic and the deterministic patcher. Reasoning fields are not final answers and are not displayed as execution evidence. No generated shell command is executed. SDK retries and repair attempts are bounded.

The configured model's official card and API reference are documented at:
https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b
The service terms and model license linked there govern use. The application takes the authorized model ID from environment; it does not supply this ID as a default.

## Execution trust

Only the built-in sample loaded through the dedicated endpoint can execute. An independently checked SHA-256 manifest pins all its source/tests/fixtures. Uploading or cloning identical content never grants trust. The runner rejects modified protected files before contacting Docker.

Run a prebuilt image by its inspected image ID with no runtime pull or installation, non-root UID, network disabled, read-only root/mounts, all capabilities dropped, no-new-privileges, bounded CPU/memory/PIDs/wall time/output, and a limited temporary filesystem. No credentials, host Docker socket, or unrestricted host write mounts are present.

Docker is risk reduction, not a perfect security boundary. This restriction to known developer-controlled samples is intentional. Arbitrary customer/public repositories never execute on the host or in this runner.

## Evidence and cleanup

Capture real exit codes, pytest counts, logs, baseline/candidate probes, initial failures, and repair results. A missing baseline, unavailable Docker, absent/unknown tests, timeout, or missing runner footer cannot yield verified success. A baseline failure blocks claims of preserved behavior. Fixture matching does not prove correctness, equivalence, security, or regulatory compliance.

UI code/logs render as text. Final approve/reject is session-only; exported patches need human review. There is no automatic merge, production application, deployment, or compliance claim.

Known snapshots and artifacts are ignored by Git, limited in count, lazily expired, and removed on clean shutdown. In-memory IDs do not survive restart; crash leftovers can remain on disk. Protect the machine and its ignored data, and clean owned leftovers when the service is stopped. Authentication, durable state, multi-user isolation, and stronger sandboxes are not implemented.

## Living Harness boundaries

Trusted execution now uses an explicit two-sample registry, each with a separately pinned manifest and one editable source file. No uploaded/cloned label confers trust. Policy and scenario files remain protected. Synthetic events use strict allowlists, pseudonymous tokens, a 128 KiB/500-event cap, and unknown/sensitive-field rejection. Only aggregate metrics and relevant source references reach Nemotron; raw sessions/events are excluded. Policy expectations come from independent developer fixtures or their declarative interpreter; a model prediction is never the sole oracle. Semantic changes require explicit policy-ID approval and a matching investigation revision. See LIVING_HARNESS.md for complete limits.
