"""Opt-in real-service harness checks. No prewritten model success output."""
from dataclasses import replace
import os
import threading
from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.harness import GhostHarness
from app.loader import RepositoryLoader
from app.main import create_app
from app.model import NemotronClient
from app.runner import DockerRunner
from app.store import Store

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("GHOSTPATCH_RUN_UPGRADE_INTEGRATION") != "1",
    reason="Set GHOSTPATCH_RUN_UPGRADE_INTEGRATION=1 to run real Docker and NVIDIA harness checks.")]


def test_real_policy_trial_exposes_gap_while_existing_tests_pass(tmp_path):
    settings = replace(Settings.from_env(), workspace_root=tmp_path/"claims")
    store = Store(settings)
    try:
        repo = RepositoryLoader(store, settings).sample("claims_demo")
        harness = GhostHarness(NemotronClient(settings), DockerRunner(settings), settings, threading.Lock())
        state = harness.prepare(repo, use_model=False)
        assert state.baseline.status == "passed"
        assert state.baseline.counts.passed == 6
        gap = next(r for r in state.report.scenario_results if r.scenario.id == "trial-boundary-age-65")
        assert gap.classification == "unexpected_divergence"
        assert gap.baseline.outcome.output["decision"] == "rejected"
        assert gap.expected.output["decision"] == "approved"
        assert state.report.status == "failed"
        assert sum(w.event_count for w in state.signals.windows) == 66
        print("REAL_POLICY_GAP:", {"existing_pytest_passed":6, "boundary_input":gap.scenario.input,
            "actual":gap.baseline.outcome.output, "independent_policy":gap.expected.output, "classification":gap.classification})
    finally:
        store.close()


def test_real_memory_signals_approved_patch_and_trials(tmp_path):
    settings = replace(Settings.from_env(), workspace_root=tmp_path/"workflow")
    with TestClient(create_app(settings)) as client:
        repo = client.post("/api/repositories/sample?sample_id=claims_demo").json()
        rid = repo["id"]
        response = client.post("/api/repositories/"+rid+"/investigate",
            json={"consent_to_model":True,"use_model":True,"signals_dataset":"both"})
        assert response.status_code == 200, response.text
        investigation = response.json()
        assert investigation["rulebook"]["rules"]
        assert investigation["rulebook"]["model_status"] == "succeeded", investigation["rulebook"].get("model_error")
        assert any(r["origin"] == "nemotron" for r in investigation["rulebook"]["rules"])
        assert investigation["signals"]["hypotheses"]
        assert any(h["source"] == "nemotron" for h in investigation["signals"]["hypotheses"]), investigation["signals"].get("model_error")
        gap = next(r for r in investigation["report"]["scenario_results"] if r["scenario"]["id"] == "trial-boundary-age-65")
        assert gap["classification"] == "unexpected_divergence"
        plan_response = client.post("/api/repositories/"+rid+"/plans", json={"consent_to_model":True,
            "objective":"Correct only the inclusive age-65 eligibility mismatch proven by independent policy trials. Preserve duplicates, rounding, review threshold and error behavior.",
            "intended_rule_changes":["rule-age-eligibility"]})
        assert plan_response.status_code == 200, plan_response.text
        plan = plan_response.json()
        assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True}).status_code == 409
        approved = client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True,"approved_rule_changes":["rule-age-eligibility"]})
        assert approved.status_code == 200, approved.text
        start = client.post("/api/plans/"+plan["id"]+"/execute",json={"approved":True})
        assert start.status_code == 202, start.text
        job = client.get("/api/jobs/"+start.json()["id"]).json()
        report = job["results"]["behavior_report"]
        print("REAL_UPGRADE:", {"status":job["status"],"verification":job["results"]["verification"],
            "memory_model":report["rulebook"]["model_status"],"signals_model":report["signals"]["model_status"],
            "rules":len(report["rulebook"]["rules"]),"scenarios":len(report["scenario_results"]),
            "classifications":report["classifications"],"repairs":len(job["results"]["repairs"]),
            "tools":[t["tool"] for t in report["tool_invocations"]]})
        assert job["status"] == "succeeded", {"error":job["error"],"results":job["results"]}
        assert report["status"] == "passed"
        assert report["classifications"]["intended_change"] >= 1
        assert report["classifications"]["unexpected_divergence"] == 0
        assert job["results"]["baseline"]["counts"]["passed"] == 6
        assert job["results"]["modified"]["counts"]["passed"] == 6
        for resource in ("rules","signals","trials","evidence","evidence/download","patch"):
            response = client.get("/api/jobs/"+job["id"]+"/"+resource)
            assert response.status_code == 200, (resource,response.text)


@pytest.mark.skipif(os.getenv("GHOSTPATCH_RUN_CONTINUOUS_INTEGRATION")!="1",
    reason="Set GHOSTPATCH_RUN_CONTINUOUS_INTEGRATION=1 for the real repeated-evaluation/approval demo.")
def test_real_continuous_drift_policy_and_approved_followup(tmp_path):
    settings=replace(Settings.from_env(),workspace_root=tmp_path/"continuous")
    app=create_app(settings)
    with TestClient(app) as client:
        rid=client.post("/api/repositories/sample?sample_id=claims_demo").json()["id"]
        rules=client.post("/api/repositories/"+rid+"/rules",json={"consent_to_model":True,"use_model":True})
        assert rules.status_code==200,rules.text
        for version in ("before","after"):
            response=client.post("/api/repositories/"+rid+"/signals/import",
                json={"dataset":version,"consent_to_model":True})
            assert response.status_code==200,response.text
        state=client.get("/api/repositories/"+rid+"/investigation").json()
        assert state["signals"]["drifts"]
        assert len(state["reevaluations"])==1 and state["reevaluations"][0]["status"]=="completed",state["reevaluations"]
        assert state["reevaluations"][0]["report_status"]=="failed"
        assert any(h["source"]=="nemotron" and len(h["explanations"])>=2 and any(e["kind"]!="code" for e in h["explanations"])
                   for h in state["signals"]["hypotheses"]),state["signals"].get("model_error")
        invocations=len(state["tool_invocations"])
        client.post("/api/repositories/"+rid+"/signals/import",json={"dataset":"after","consent_to_model":True})
        repeated=client.get("/api/repositories/"+rid+"/investigation").json()
        assert len(repeated["reevaluations"])==1 and repeated["reevaluations"][0]["attempts"]==1
        def run_plan(objective):
            response=client.post("/api/repositories/"+rid+"/plans",json={"consent_to_model":True,
                "intended_rule_changes":["rule-age-eligibility"],"objective":objective})
            assert response.status_code==200,response.text
            plan=response.json()
            assert client.post("/api/plans/"+plan["id"]+"/approve",json={"approved":True}).status_code==409
            approved=client.post("/api/plans/"+plan["id"]+"/approve",
                json={"approved":True,"approved_rule_changes":["rule-age-eligibility"]})
            assert approved.status_code==200,approved.text
            response=client.post("/api/plans/"+plan["id"]+"/execute",json={"approved":True})
            assert response.status_code==202,response.text
            job=client.get("/api/jobs/"+response.json()["id"]).json()
            assert job["status"]=="succeeded",{"error":job["error"],"results":job["results"]}
            return job
        first=run_plan("Correct only the independently evidenced inclusive age-65 mismatch under approved policy 1.0. Preserve rounding, duplicates, review and error behavior.")
        patch=client.get("/api/jobs/"+first["id"]+"/patch").content
        evidence=client.get("/api/jobs/"+first["id"]+"/evidence/download").content
        working_before=(app.state.store.repository(rid).working/"claims.py").read_bytes()
        updated=client.post("/api/repositories/"+rid+"/rules/policy-versions",
            json={"version":"1.1","approved":True,"approved_rule_ids":["rule-age-eligibility"],"consent_to_model":True})
        assert updated.status_code==200,updated.text
        state=client.get("/api/repositories/"+rid+"/investigation").json()
        assert state["rulebook"]["policy_version"]=="1.1"
        assert state["reevaluations"][-1]["report_status"]=="failed",state["reevaluations"]
        assert (app.state.store.repository(rid).working/"claims.py").read_bytes()==working_before
        second=run_plan("Conform only to explicitly approved fictional policy version 1.1: age 66 or older is eligible, age 65 is rejected. Preserve all other behavior.")
        assert second["results"]["baseline_kind"]=="previous_working_copy"
        assert second["results"]["behavior_report"]["classifications"]["intended_change"]>=1
        assert client.get("/api/jobs/"+first["id"]+"/patch").content==patch
        assert client.get("/api/jobs/"+first["id"]+"/evidence/download").content==evidence
        app.state.store.repository(rid).assert_original()
        print("REAL_CONTINUOUS:",{"first_job":first["status"],"followup_job":second["status"],
            "reevaluations":len(state["reevaluations"]),"policy_versions":["1.0","1.1"],
            "classifications":second["results"]["behavior_report"]["classifications"],
            "repairs":len(second["results"]["repairs"]),"old_artifacts_unchanged":True})
