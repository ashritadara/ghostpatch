from pathlib import Path
from decimal import Decimal
from fastapi.testclient import TestClient
import pytest

from app.harness_schemas import Outcome, TrialExecution
from app.main import create_app
from app.schemas import Edit, PatchProposal, TestCounts as Counts, TestRun as Run
from app.trials import input_digest, policy_outcome
from conftest import DeterministicModelDouble, SequenceRunnerDouble, zip_bytes


class PolicyRunnerDouble:
    """Explicit test-only runner; real Docker behavior has separate integration tests."""
    def __init__(self):self.calls=[]
    def run_with_trials(self,repo,source,scenarios):
        self.calls.append(source)
        source_text=(source/"claims.py").read_text()
        inclusive="if age >= 65:" in source_text
        run=Run(status="passed",exit_code=0,counts=Counts(passed=6,failed=0,skipped=0),
            behavior_outputs={"normal":{"output":"unchanged","error":None}})
        for scenario in scenarios:
            outcome,_=policy_outcome(repo,scenario.input)
            if scenario.input.get("age")==65 and not scenario.input.get("duplicate",False):
                outcome=Outcome(output={"decision":"approved" if inclusive else "rejected",
                    "reason":"eligible" if inclusive else "age_threshold",
                    "payable":format(Decimal(scenario.input["amount"]),".2f") if inclusive else "0.00"})
            run.trial_outputs.append(TrialExecution(scenario_id=scenario.id,input_digest=input_digest(scenario.input),
                outcome=outcome,duration_ms=1,invariant_passed=True if scenario.invariant else None))
        return run
    def run(self,repo,source):return self.run_with_trials(repo,source,[])


class CorrectingModelDouble(DeterministicModelDouble):
    def patch(self,context,plan,failure=None):
        self.patch_calls+=1
        path=context["allowed_paths"][0];record=context["files"][path]
        changes=context["approved_policy_changes"]
        approve_65=any(example["input"].get("age")==65 and example["expected"]["output"]["decision"]=="approved"
            for change in changes for example in change["expected_examples"])
        content=record["content"]
        updated=content.replace("if age > 65:","if age >= 65:") if approve_65 else content.replace("if age >= 65:","if age > 65:")
        return PatchProposal(summary="Test-only explicit policy correction",edits=[Edit(path=path,
            original_sha256=record["original_sha256"],new_content=updated)])


def test_signals_auto_re_evaluate_idempotently_without_edits(settings):
    runner=PolicyRunnerDouble();model=CorrectingModelDouble()
    with TestClient(create_app(settings,model=model,runner=runner)) as client:
        repo=client.post("/api/repositories/sample?sample_id=claims_demo").json();rid=repo["id"]
        for name in ("before","after"):
            assert client.post("/api/repositories/"+rid+"/signals/import",json={"dataset":name}).status_code==200
        evaluations=client.get("/api/repositories/"+rid+"/trials/reevaluations").json()
        assert len(evaluations)==1 and evaluations[0]["status"]=="completed"
        assert evaluations[0]["report_status"]=="failed"
        count=len(runner.calls)
        for _ in range(2):
            client.post("/api/repositories/"+rid+"/signals/import",json={"dataset":"after"})
            client.post("/api/repositories/"+rid+"/trials/reevaluations",json={})
        assert len(runner.calls)==count and model.patch_calls==0
        evidence=client.get("/api/repositories/"+rid+"/trials/reevaluations/"+evaluations[0]["id"]).json()
        assert evidence["report"]["classifications"]["unexpected_divergence"]>=1
        assert evidence["reevaluation"]["approval_state"]=="human_required"


def test_preexisting_policy_mismatch_does_not_authorize_repairs(settings):
    model=DeterministicModelDouble()
    with TestClient(create_app(settings,model=model,runner=PolicyRunnerDouble())) as client:
        rid=client.post("/api/repositories/sample?sample_id=claims_demo").json()["id"]
        assert client.post("/api/repositories/"+rid+"/investigate",json={"use_model":False}).status_code==200
        plan=client.post("/api/repositories/"+rid+"/plans",json={"consent_to_model":True}).json()
        assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True}).status_code==200
        started=client.post("/api/plans/"+plan["id"]+"/execute",json={"approved":True})
        job=client.get("/api/jobs/"+started.json()["id"]).json()
        assert job["status"]=="needs_review" and not job["results"]["repairs"]
        assert model.patch_calls==1
        assert any("explicit semantic approval" in warning for warning in job["results"]["warnings"])


def test_policy_update_requires_explicit_known_approval_and_is_idempotent(settings):
    with TestClient(create_app(settings,model=CorrectingModelDouble(),runner=PolicyRunnerDouble())) as client:
        repo=client.post("/api/repositories/sample?sample_id=claims_demo").json();rid=repo["id"]
        route="/api/repositories/"+rid+"/rules/policy-versions"
        assert client.post(route,json={"version":"1.1","approved_rule_ids":["rule-age-eligibility"]}).status_code==422
        assert client.post(route,json={"version":"1.1","approved":True,"approved_rule_ids":["invented"]}).status_code==409
        body={"version":"1.1","approved":True,"approved_rule_ids":["rule-age-eligibility"]}
        response=client.post(route,json=body)
        assert response.status_code==200,response.text
        first=client.get("/api/repositories/"+rid+"/investigation").json()
        assert first["rulebook"]["policy_version"]=="1.1"
        assert len(first["policy_history"])==1
        assert first["reevaluations"][0]["trigger"]=="approved_policy_update"
        assert first["reevaluations"][0]["report_status"]=="passed"
        assert client.post(route,json=body).status_code==200
        again=client.get("/api/repositories/"+rid+"/investigation").json()
        assert len(again["policy_history"])==1 and len(again["reevaluations"])==1


def approve_and_execute(client,rid):
    response=client.post("/api/repositories/"+rid+"/plans",json={"consent_to_model":True,
        "intended_rule_changes":["rule-age-eligibility"],"objective":"Correct only the independently evidenced active policy mismatch."})
    assert response.status_code==200,response.text
    plan=response.json()
    assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True}).status_code==409
    assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True,"approved_rule_changes":["rule-age-eligibility"]}).status_code==200
    result=client.post("/api/plans/"+plan["id"]+"/execute",json={"approved":True})
    assert result.status_code==202,result.text
    job=client.get("/api/jobs/"+result.json()["id"]).json()
    assert job["status"]=="succeeded",job
    return job


def test_completed_candidate_re_evaluated_and_followup_artifacts_are_immutable(settings):
    runner=PolicyRunnerDouble();model=CorrectingModelDouble()
    app=create_app(settings,model=model,runner=runner)
    with TestClient(app) as client:
        rid=client.post("/api/repositories/sample?sample_id=claims_demo").json()["id"]
        response=client.post("/api/repositories/"+rid+"/investigate",json={"use_model":False})
        assert response.status_code==200,response.text
        first=approve_and_execute(client,rid)
        first_patch=client.get("/api/jobs/"+first["id"]+"/patch").content
        first_evidence=client.get("/api/jobs/"+first["id"]+"/evidence/download").content
        source_hashes=dict(app.state.store.repository(rid).hashes)
        assert model.patch_calls==1
        policy=client.post("/api/repositories/"+rid+"/rules/policy-versions",
            json={"version":"1.1","approved":True,"approved_rule_ids":["rule-age-eligibility"]})
        assert policy.status_code==200,policy.text
        assert model.patch_calls==1  # Re-evaluation never edits or repairs without a new plan.
        evaluations=client.get("/api/repositories/"+rid+"/trials/reevaluations").json()
        assert evaluations[-1]["report_status"]=="failed"
        second=approve_and_execute(client,rid)
        assert second["id"]!=first["id"] and second["results"]["baseline_kind"]=="previous_working_copy"
        assert client.get("/api/jobs/"+first["id"]+"/patch").content==first_patch
        assert client.get("/api/jobs/"+first["id"]+"/evidence/download").content==first_evidence
        new_patch=client.get("/api/jobs/"+second["id"]+"/patch").text
        assert "-    if age >= 65:" in new_patch and "+    if age > 65:" in new_patch
        app.state.store.repository(rid).assert_original()
        assert app.state.store.repository(rid).hashes==source_hashes
        assert model.patch_calls==2


def test_uploaded_policy_file_or_version_labels_never_grant_authority(client):
    rid=client.post("/api/repositories/upload",files={"file":("code.zip",zip_bytes({"app.py":"x=1\n","policy.json":"{}"}))}).json()["id"]
    response=client.post("/api/repositories/"+rid+"/rules/policy-versions",
        json={"version":"1.1","approved":True,"approved_rule_ids":["rule-age-eligibility"]})
    assert response.status_code==403
