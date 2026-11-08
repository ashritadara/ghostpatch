from fastapi.testclient import TestClient
from app.main import create_app
from conftest import DeterministicModelDouble, SequenceRunnerDouble, zip_bytes


def test_existing_path_and_new_rules_signals_trial_endpoints(settings):
    with TestClient(create_app(settings, model=DeterministicModelDouble(), runner=SequenceRunnerDouble(["passed"]))) as client:
        repo = client.post("/api/repositories/sample?sample_id=claims_demo").json()
        rid = repo["id"]
        rules = client.get("/api/repositories/"+rid+"/rules").json()
        assert any(r["id"] == "rule-age-eligibility" for r in rules["rules"])
        for version in ("before","after"):
            response = client.post("/api/repositories/"+rid+"/signals/import", json={"dataset":version})
            assert response.status_code == 200
        assert len(response.json()["windows"]) == 2
        assert client.post("/api/repositories/"+rid+"/trials", json={"execute":True}).status_code == 200
        # No observed policy mismatch with this all-passing independent runner double.
        result = client.post("/api/repositories/"+rid+"/plans", json={"consent_to_model":True, "intended_rule_changes":["rule-age-eligibility"]})
        assert result.status_code == 409


def test_investigation_revision_invalidates_approval(settings):
    with TestClient(create_app(settings, model=DeterministicModelDouble(), runner=SequenceRunnerDouble(["passed"]))) as client:
        repo = client.post("/api/repositories/sample?sample_id=claims_demo").json()
        rid = repo["id"]
        plan = client.post("/api/repositories/"+rid+"/plans",json={"consent_to_model":True}).json()
        client.post("/api/repositories/"+rid+"/signals/import",json={"dataset":"before"})
        assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True}).status_code == 409


def test_untrusted_never_runs_trials_and_cannot_authorize_policy(client):
    repo = client.post("/api/repositories/upload",files={"file":("code.zip",zip_bytes({"claims.py":"value=1\n"}))}).json()
    rid = repo["id"]
    assert client.post("/api/repositories/"+rid+"/trials",json={"execute":True}).status_code == 403
    assert client.post("/api/repositories/"+rid+"/plans",json={"consent_to_model":True,"intended_rule_changes":["rule-age-eligibility"]}).status_code == 403
    assert client.post("/api/repositories/"+rid+"/signals",json={"events":[{"email":"private@example.invalid"}]}).status_code == 422


def test_investigation_changed_after_approval_blocks_execution(settings):
    with TestClient(create_app(settings, model=DeterministicModelDouble(), runner=SequenceRunnerDouble(["passed"]))) as client:
        repo = client.post("/api/repositories/sample?sample_id=claims_demo").json()
        rid = repo["id"]
        plan = client.post("/api/repositories/"+rid+"/plans",json={"consent_to_model":True}).json()
        assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True}).status_code == 200
        client.post("/api/repositories/"+rid+"/signals/import",json={"dataset":"after"})
        assert client.post("/api/plans/"+plan["id"]+"/execute",json={"approved":True}).status_code == 409
