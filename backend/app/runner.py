import json
from pathlib import Path
from typing import Protocol

from .config import Settings
from .errors import GhostPatchError, redact
from .loader import digest
from .processes import run_bounded
from .schemas import TestCounts, TestRun
from .store import Repository, fingerprints, identifier
from .trusted import sample_spec
from .harness_schemas import TrialExecution


class TestRunner(Protocol):
    def run(self, repo: Repository, source: Path) -> TestRun: ...


class DockerRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def availability(self) -> dict:
        try:
            engine = run_bounded(["docker", "info", "--format", "{{.OSType}}"], timeout=5)
            if engine.exit_code or engine.limit_reason or engine.stdout.strip() != "linux":
                return {"available": False, "reason": "Start Docker Desktop with its Linux engine."}
            image = run_bounded(["docker", "image", "inspect", self.settings.runner_image, "--format", "{{.Id}}"], timeout=5)
            if image.exit_code or image.limit_reason:
                return {"available": False, "reason": "Build the vetted runner image: docker build -t ghostpatch-runner:local backend/runner"}
            return {"available": True, "image_id": image.stdout.strip()}
        except (OSError, TimeoutError):
            return {"available": False, "reason": "Docker is unavailable on the backend PATH or did not respond."}

    def _trusted(self, repo: Repository, source: Path) -> None:
        if not repo.trusted:
            raise GhostPatchError("Execution denied: uploaded and cloned repositories are never trusted in this MVP.", 403)
        spec = sample_spec(self.settings, repo.sample_id or "legacy_reports")
        expected = json.loads(spec.manifest.read_text())
        repo.assert_original()
        if digest(expected) != repo.trust_digest or repo.hashes != expected:
            raise GhostPatchError("Trusted sample identity/integrity check failed.", 403)
        registered = repo.execution_snapshots.get(str(source.resolve()))
        if source.resolve() not in {repo.original.resolve(), repo.working.resolve()} and registered is None:
            raise GhostPatchError("Runner source is not an owned sample snapshot.", 403)
        current = fingerprints(source)
        if registered is not None and current != registered:
            raise GhostPatchError("Frozen job baseline integrity check failed.", 403)
        if current.keys() != expected.keys() or any(current[p] != expected[p] for p in expected if p != spec.editable):
            raise GhostPatchError("Protected tests, fixtures, or sample files were modified.", 403)

    def run(self, repo: Repository, source: Path) -> TestRun:
        return self._run(repo, source)

    def run_with_trials(self, repo: Repository, source: Path, scenarios) -> TestRun:
        if len(scenarios) > 24:
            raise GhostPatchError("Scenario execution budget exceeded.")
        return self._run(repo, source, scenarios)

    def _run(self, repo: Repository, source: Path, scenarios=None) -> TestRun:
        # Enforce trust before even probing Docker. No request can opt into trust.
        self._trusted(repo, source)
        availability = self.availability()
        if not availability["available"]:
            return TestRun(status="not_verified", reason=availability["reason"])
        name = "ghostpatch-" + identifier()
        mounts = [(source, "/project"), (repo.original / "tests", "/tests"),
                  (repo.original, "/fixtures"), (self.settings.runner_root, "/runner")]
        if scenarios is not None:
            from .trials import canonical
            from .memory import stable_id
            # Outside the editable working copy; the model cannot change inputs.
            encoded = canonical([s.model_dump() for s in scenarios])
            path = repo.root / (stable_id("scenarios", encoded) + ".json")
            path.write_text(encoded, encoding="utf-8")
            mounts.append((path, "/scenarios.json"))
        command = ["docker", "run", "--rm", "--name", name, "--pull=never", "--network=none",
                   "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                   "--cpus=1", "--memory=256m", "--memory-swap=256m", "--pids-limit=64",
                   "--user=65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
                   "--workdir=/project", "--env=PYTHONDONTWRITEBYTECODE=1", "--env=PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"]
        for host, container in mounts:
            command.extend(["--mount", f"type=bind,source={host.resolve()},target={container},readonly"])
        command.extend([availability["image_id"], "python", "-I", "/runner/check.py", "--sample", repo.sample_id or "legacy_reports"])
        if scenarios is not None:
            command.append("--trials")
        try:
            result = run_bounded(command, timeout=self.settings.test_timeout)
        except OSError:
            return TestRun(status="not_verified", reason="Docker could not start the trusted validation container.")
        finally:
            try:
                run_bounded(["docker", "rm", "--force", name], timeout=5)
            except (OSError, TimeoutError):
                pass
        # Never expose host mount paths or environment values through the UI.
        display_command = ["docker", "run", "[restricted trusted-sample sandbox]", "python", "-I", "/runner/check.py"]
        run = TestRun(status="not_verified", command=display_command, exit_code=result.exit_code,
                      duration_ms=result.duration_ms, stdout=redact(result.stdout[-16000:], self.settings.api_key),
                      stderr=redact(result.stderr[-8000:], self.settings.api_key), reason=result.limit_reason)
        if result.limit_reason:
            return run
        marker = next((line.removeprefix("GHOSTPATCH_RESULT=") for line in reversed(result.stdout.splitlines()) if line.startswith("GHOSTPATCH_RESULT=")), None)
        try:
            payload = json.loads(marker or "")
            run.counts = TestCounts.model_validate(payload["counts"])
            run.behavior_outputs = payload["behavior_outputs"]
            run.trial_outputs = [TrialExecution.model_validate(x) for x in payload.get("trial_outputs", [])]
            if scenarios is not None and {x.scenario_id for x in run.trial_outputs} != {s.id for s in scenarios}:
                raise ValueError("Missing or unexpected scenario evidence")
            if payload["exit_code"] != result.exit_code:
                raise ValueError("Exit mismatch")
            if not isinstance(run.behavior_outputs, dict) or not run.behavior_outputs or "runner_error" in run.behavior_outputs:
                raise ValueError("Missing behavior evidence")
            if result.exit_code == 0 and run.counts.passed > 0 and run.counts.failed == 0:
                run.status = "passed"
            elif result.exit_code != 0 or run.counts.failed:
                run.status = "failed"
            else:
                run.reason = "No tests executed; behavior preservation is not verified."
        except (ValueError, TypeError, KeyError):
            run.reason = "Runner returned no valid structured test/behavior evidence."
        return run
