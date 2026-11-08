"""Opt-in real-service integration tests. No fabricated model or runner output."""
from dataclasses import replace
import os

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.loader import RepositoryLoader
from app.main import create_app
from app.runner import DockerRunner
from app.store import Store

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("GHOSTPATCH_RUN_INTEGRATION") != "1", reason="Set GHOSTPATCH_RUN_INTEGRATION=1 to use real Docker/NVIDIA/public GitHub.")]


def test_real_docker_detects_regression_and_restored_sample_passes(tmp_path):
    settings = replace(Settings.from_env(), workspace_root=tmp_path / "docker")
    store = Store(settings)
    try:
        repo = RepositoryLoader(store, settings).sample()
        runner = DockerRunner(settings)
        baseline = runner.run(repo, repo.original)
        assert baseline.status == "passed", baseline.model_dump()
        assert baseline.counts.passed == 12
        source = repo.working / "reports.py"
        original = source.read_text()
        source.write_text(original.replace('Decimal(row["amount"])', 'Decimal(row["amount"]) * 2'))
        regressed = runner.run(repo, repo.working)
        assert regressed.status == "failed" and regressed.counts.failed > 0
        source.write_text(original)
        restored = runner.run(repo, repo.working)
        assert restored.status == "passed"
        assert restored.behavior_outputs == baseline.behavior_outputs
    finally:
        store.close()


def test_real_nemotron_docker_workflow(tmp_path):
    settings = replace(Settings.from_env(), workspace_root=tmp_path / "workflow")
    with TestClient(create_app(settings)) as client:
        repo_response = client.post("/api/repositories/sample")
        assert repo_response.status_code == 201, repo_response.text
        repo = repo_response.json()
        plan_response = client.post(f'/api/repositories/{repo["id"]}/plans', json={"consent_to_model": True, "objective": "Simplify manual dictionary initialization using standard-library collection helpers. Preserve Decimal arithmetic, sorting, rounding, counts, input immutability, and exception behavior."})
        assert plan_response.status_code == 200, plan_response.text
        plan = plan_response.json()
        client.post(f'/api/plans/{plan["id"]}/approve', json={"approved": True})
        execution = client.post(f'/api/plans/{plan["id"]}/execute', json={"approved": True})
        assert execution.status_code == 202, execution.text
        job = client.get('/api/jobs/' + execution.json()["id"]).json()
        print("REAL_WORKFLOW:", {"status": job["status"], "verification": job["results"]["verification"], "repairs": len(job["results"]["repairs"]), "changed_files": [d["path"] for d in job["results"]["diffs"]]})
        assert job["status"] == "succeeded", {"error": job["error"], "results": job["results"]}
        assert job["results"]["baseline"]["counts"]["passed"] == 12
        assert job["results"]["modified"]["counts"]["passed"] == 12
        assert job["results"]["diffs"]
        patch = client.get(f'/api/jobs/{job["id"]}/patch')
        assert patch.status_code == 200 and "--- a/reports.py" in patch.text


def test_real_public_github_static_import(tmp_path):
    settings = replace(Settings.from_env(), workspace_root=tmp_path / "git")
    store = Store(settings)
    try:
        repo = RepositoryLoader(store, settings).git("https://github.com/pypa/sampleproject")
        assert repo.analysis.python_file_count > 0 and repo.trusted is False
    finally:
        store.close()
