from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from conftest import DeterministicModelDouble, SequenceRunnerDouble, zip_bytes


def test_upload_schema_consent_approval_and_untrusted_no_execution(client):
    response = client.post("/api/repositories/upload", files={"file": ("repo.zip", zip_bytes({"main.py": "value = 1\n"}), "application/zip")})
    assert response.status_code == 201
    repo = response.json()
    assert repo["trusted"] is False and "prohibited" in repo["execution_policy"]
    path = f'/api/repositories/{repo["id"]}/plans'
    assert client.post(path, json={"consent_to_model": False}).status_code == 403
    plan = client.post(path, json={"consent_to_model": True}).json()
    assert client.post(f'/api/plans/{plan["id"]}/execute', json={"approved": True}).status_code == 409
    assert client.post(f'/api/plans/{plan["id"]}/approve', json={"approved": True}).status_code == 200
    job = client.post(f'/api/plans/{plan["id"]}/execute', json={"approved": True}).json()
    finished = client.get(f'/api/jobs/{job["id"]}').json()
    assert finished["status"] == "needs_review"
    assert finished["results"]["verification"] == "not_verified"
    assert finished["results"]["baseline"] is None
    assert "skipped" in finished["results"]["warnings"][0]
    patch = client.get(f'/api/jobs/{job["id"]}/patch')
    assert patch.status_code == 200 and "--- a/main.py" in patch.text
    repeated = client.post(f'/api/plans/{plan["id"]}/execute', json={"approved": True}).json()
    assert repeated["id"] == job["id"]


def test_trusted_regression_and_one_repair_with_test_doubles(settings):
    model = DeterministicModelDouble(regress=True)
    runner = SequenceRunnerDouble()
    with TestClient(create_app(settings, model=model, runner=runner)) as client:
        repo = client.post("/api/repositories/sample").json()
        plan = client.post(f'/api/repositories/{repo["id"]}/plans', json={"consent_to_model": True}).json()
        client.post(f'/api/plans/{plan["id"]}/approve', json={"approved": True})
        job = client.post(f'/api/plans/{plan["id"]}/execute', json={"approved": True}).json()
        result = client.get(f'/api/jobs/{job["id"]}').json()
        assert result["status"] == "succeeded"
        assert len(result["results"]["repairs"]) == 1
        assert result["results"]["initial_modified"]["status"] == "failed"
        assert model.patch_calls == 2 and len(runner.calls) == 3
        assert result["results"]["behavior_comparison"][0]["status"] == "matched"


def test_repair_limit_two_and_failure_not_greenwashed(settings):
    model = DeterministicModelDouble(regress=True)
    runner = SequenceRunnerDouble(["passed", "failed", "failed", "failed"])
    with TestClient(create_app(settings, model=model, runner=runner)) as client:
        repo = client.post("/api/repositories/sample").json()
        plan = client.post(f'/api/repositories/{repo["id"]}/plans', json={"consent_to_model": True}).json()
        client.post(f'/api/plans/{plan["id"]}/approve', json={"approved": True})
        job = client.post(f'/api/plans/{plan["id"]}/execute', json={"approved": True}).json()
        result = client.get(f'/api/jobs/{job["id"]}').json()
        assert result["status"] == "needs_review"
        assert result["results"]["verification"] == "failed"
        assert len(result["results"]["repairs"]) == 2
        assert model.patch_calls == 3


def test_api_validation_origin_and_missing_ids(client):
    assert client.get("/api/repositories/missing").status_code == 404
    assert client.post("/api/repositories/import-git", json={"url": "https://github.com/a/b", "trusted": True}).status_code == 422
    assert client.post("/api/repositories/sample", headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert client.post("/api/repositories/upload", files={"file": ("a.txt", b"x")}).status_code == 400
    assert client.get("/api/health").json()["status"] == "ok"


def test_cleanup_endpoint_and_expired_state(client):
    repo = client.post("/api/repositories/sample").json()
    assert client.delete(f'/api/repositories/{repo["id"]}').status_code == 204
    assert client.get(f'/api/repositories/{repo["id"]}').status_code == 404


def test_host_header_and_streamed_body_limit(settings):
    from dataclasses import replace
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from app.body_limit import BodyLimitMiddleware

    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health", headers={"Host": "rebinding.invalid"}).status_code == 400

    async def read_body(request: Request):
        await request.body()
        return JSONResponse({"ok": True})

    app = BodyLimitMiddleware(Starlette(routes=[Route("/", read_body, methods=["POST"])]), limit=4)
    with TestClient(app) as client:
        assert client.post("/", content=iter([b"123", b"456"])).status_code == 413

    with TestClient(create_app(replace(settings, max_archive_bytes=4))) as client:
        headers = {"Content-Type": "multipart/form-data; boundary=gp"}
        data = iter([b'--gp\r\nContent-Disposition: form-data; name="file"; filename="x.zip"\r\n\r\n', b'x' * (1024 * 1024 + 10), b'\r\n--gp--\r\n'])
        assert client.post("/api/repositories/upload", content=data, headers=headers).status_code == 413
