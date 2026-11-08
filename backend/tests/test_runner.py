import json
import pytest

from app.errors import GhostPatchError
from app.processes import CommandResult
from app.runner import DockerRunner
from conftest import zip_bytes


def test_runner_rejects_untrusted_before_docker(loader, settings, monkeypatch):
    repo = loader.zip(zip_bytes({"main.py": "raise RuntimeError('must not run')"}), "untrusted.zip")
    monkeypatch.setattr("app.runner.run_bounded", lambda *a, **k: pytest.fail("Docker must not be invoked"))
    with pytest.raises(GhostPatchError, match="Execution denied"):
        DockerRunner(settings).run(repo, repo.working)


def test_runner_missing_docker_is_not_verified(loader, settings, monkeypatch):
    repo = loader.sample()
    runner = DockerRunner(settings)
    monkeypatch.setattr(runner, "availability", lambda: {"available": False, "reason": "Docker unavailable"})
    result = runner.run(repo, repo.original)
    assert result.status == "not_verified" and result.counts is None


def test_runner_flags_and_zero_tests_are_not_a_pass(loader, settings, monkeypatch):
    repo = loader.sample()
    runner = DockerRunner(settings)
    monkeypatch.setattr(runner, "availability", lambda: {"available": True, "image_id": "sha256:test-double"})
    commands = []
    def command(args, **kwargs):
        commands.append(args)
        payload = {"exit_code": 0, "counts": {"passed": 0, "failed": 0, "skipped": 0}, "behavior_outputs": {"empty": {"output": [], "error": None}}}
        return CommandResult(0, "GHOSTPATCH_RESULT=" + json.dumps(payload), "", 1)
    monkeypatch.setattr("app.runner.run_bounded", command)
    result = runner.run(repo, repo.working)
    assert result.status == "not_verified"
    args = commands[0]
    for flag in ("--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--memory=256m", "--pids-limit=64", "--user=65534:65534"):
        assert flag in args
    assert all("readonly" in args[i+1] for i, value in enumerate(args) if value == "--mount")


def test_modified_tests_rejected(loader, settings):
    repo = loader.sample()
    (repo.working / "tests/test_reports.py").write_text("def test_fake(): pass\n")
    with pytest.raises(GhostPatchError, match="Protected"):
        DockerRunner(settings).run(repo, repo.working)
