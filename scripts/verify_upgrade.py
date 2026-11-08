"""Real HTTP upgrade demo: synthetic evidence only, explicit semantic approval flag."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(base + path, data=data, headers={"Content-Type":"application/json"} if data else {})
    try:
        with urlopen(request, timeout=900) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("detail", "HTTP request failed")
        except ValueError:
            detail = "HTTP request failed"
        raise RuntimeError(str(detail)) from None


def wait_for_evaluation(base,rid):
    deadline=time.monotonic()+900
    while True:
        state=call(base,"/api/repositories/"+rid+"/investigation")
        if not any(e["status"] in {"queued","running"} for e in state["reevaluations"]):
            return state
        if time.monotonic()>deadline:
            raise RuntimeError("Re-evaluation timed out; inspect the running backend.")
        time.sleep(1)


def continuous(args,evidence):
    rid=call(args.base_url,"/api/repositories/sample?sample_id=claims_demo",{})["id"]
    if args.run_model:
        call(args.base_url,"/api/repositories/"+rid+"/rules",{"consent_to_model":True,"use_model":True})
    for dataset in ("before","after"):
        call(args.base_url,"/api/repositories/"+rid+"/signals/import",{"dataset":dataset,"consent_to_model":args.run_model})
        state=wait_for_evaluation(args.base_url,rid)
    original=state["reevaluations"]
    call(args.base_url,"/api/repositories/"+rid+"/signals/import",{"dataset":"after","consent_to_model":args.run_model})
    repeated=wait_for_evaluation(args.base_url,rid)
    if [(e["id"],e["attempts"]) for e in original]!=[(e["id"],e["attempts"]) for e in repeated["reevaluations"]]:
        raise RuntimeError("Duplicate ingestion unexpectedly changed evaluation attempts.")
    (evidence/"last-continuous-investigation.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    print(json.dumps({"repository_id":rid,"synthetic":True,"model_status":state["signals"]["model_status"],
        "windows":[{"dataset":w["dataset_version"],"version":w["software_version"],
            "return_rate":next(m for m in w["metrics"] if m["kind"]=="return_rate")} for w in state["signals"]["windows"]],
        "drifts":[{"metric":d["metric"],"category":d["category"],"status":d["status"]} for d in state["signals"]["drifts"]],
        "reevaluations":state["reevaluations"],"duplicate_ingestion_idempotent":True},indent=2),flush=True)
    if not state["reevaluations"] or state["reevaluations"][-1]["status"]!="completed":
        raise RuntimeError("Continuous trial execution did not complete; inspect saved evidence.")
    if args.run_model and state["signals"]["model_status"]!="succeeded":
        raise RuntimeError("Model hypotheses were not accepted; deterministic findings remain available.")

    def approved_patch(objective,label):
        plan=call(args.base_url,"/api/repositories/"+rid+"/plans",{"consent_to_model":True,
            "intended_rule_changes":["rule-age-eligibility"],"objective":objective})
        call(args.base_url,"/api/plans/"+plan["id"]+"/approve",{"approved":True,"approved_rule_changes":["rule-age-eligibility"]})
        job=call(args.base_url,"/api/plans/"+plan["id"]+"/execute",{"approved":True})
        deadline=time.monotonic()+1200
        while job["status"] in {"queued","running"}:
            if time.monotonic()>deadline:
                raise RuntimeError("Approved demo job timed out; it may still be running.")
            time.sleep(1)
            job=call(args.base_url,"/api/jobs/"+job["id"])
        (evidence/("last-continuous-"+label+"-job.json")).write_text(json.dumps(job,indent=2),encoding="utf-8")
        print(json.dumps({"job_id":job["id"],"status":job["status"],"baseline_kind":job["results"]["baseline_kind"],
            "verification":job["results"]["verification"],"repairs":len(job["results"]["repairs"]),
            "classifications":job["results"]["behavior_report"]["classifications"]},indent=2),flush=True)
        if job["status"]!="succeeded":
            raise RuntimeError("Approved job did not verify; no successful result is inferred.")
        return job

    if not args.approve_demo_policy_change:
        print("No patch approved or applied. Use explicit approval flags for the isolated fictional-policy demo.")
        return
    first=approved_patch("Correct only the inclusive age-65 mismatch under approved fictional policy 1.0. Preserve all other behavior.","first")
    with urlopen(args.base_url+"/api/jobs/"+first["id"]+"/patch",timeout=15) as response:
        first_patch=response.read()
    (evidence/"last-continuous-first.patch").write_bytes(first_patch)
    if args.approve_demo_policy_update:
        call(args.base_url,"/api/repositories/"+rid+"/rules/policy-versions",{"version":"1.1","approved":True,
            "approved_rule_ids":["rule-age-eligibility"],"consent_to_model":args.run_model})
        updated=wait_for_evaluation(args.base_url,rid)
        (evidence/"last-continuous-policy-investigation.json").write_text(json.dumps(updated,indent=2),encoding="utf-8")
        if updated["reevaluations"][-1]["report_status"]!="failed":
            raise RuntimeError("Updated-policy trials did not expose the expected discrepancy; inspect evidence before editing.")
        last=approved_patch("Conform only to explicitly approved fictional policy 1.1: age 66 or older is eligible; age 65 is rejected. Preserve all other behavior.","followup")
        with urlopen(args.base_url+"/api/jobs/"+first["id"]+"/patch",timeout=15) as response:
            if response.read()!=first_patch:
                raise RuntimeError("Earlier patch artifact changed.")
        with urlopen(args.base_url+"/api/jobs/"+last["id"]+"/patch",timeout=15) as response:
            (evidence/"last-continuous-followup.patch").write_bytes(response.read())
    else:
        last=first
    report=call(args.base_url,"/api/jobs/"+last["id"]+"/evidence")
    (evidence/"last-continuous-evidence.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Frontend output: http://127.0.0.1:3000/?job="+last["id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", choices=["http://127.0.0.1:8000","http://localhost:8000"])
    parser.add_argument("--run-model", action="store_true", help="Consent to send only the synthetic sample and aggregate signals to NVIDIA.")
    parser.add_argument("--approve-demo-policy-change", action="store_true", help="Explicitly approve correcting the fictional inclusive age-65 rule in an isolated sample.")
    parser.add_argument("--continuous",action="store_true",help="Import two windows separately, trigger re-evaluation and check duplicate ingestion.")
    parser.add_argument("--approve-demo-policy-update",action="store_true",help="Explicitly approve fictional policy 1.1 and a second isolated patch; requires --continuous and --approve-demo-policy-change.")
    args = parser.parse_args()
    if args.approve_demo_policy_change and not args.run_model:
        parser.error("--approve-demo-policy-change also requires --run-model")
    if args.approve_demo_policy_update and not (args.continuous and args.approve_demo_policy_change):
        parser.error("--approve-demo-policy-update requires --continuous and --approve-demo-policy-change")
    evidence = Path(__file__).resolve().parents[1]/".ghostpatch"
    evidence.mkdir(exist_ok=True)
    if args.continuous:
        continuous(args,evidence)
        return
    repo = call(args.base_url, "/api/repositories/sample?sample_id=claims_demo", {})
    rid = repo["id"]
    state = call(args.base_url, "/api/repositories/"+rid+"/investigate", {
        "consent_to_model":args.run_model,"use_model":args.run_model,"signals_dataset":"both"})
    (evidence/"last-upgrade-investigation.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    gap = next(r for r in state["report"]["scenario_results"] if r["scenario"]["id"] == "trial-boundary-age-65")
    print(json.dumps({"repository_id":rid,"memory_model":state["rulebook"]["model_status"],
        "signals_model":state["signals"]["model_status"],"rules":len(state["rulebook"]["rules"]),
        "synthetic_events":sum(w["event_count"] for w in state["signals"]["windows"]),
        "existing_pytest":state["baseline"]["counts"],"boundary_input":gap["scenario"]["input"],
        "legacy_actual":gap["baseline"]["outcome"] if gap["baseline"] else None,
        "independent_expected":gap["expected"],"classification":gap["classification"]},indent=2),flush=True)
    if not args.approve_demo_policy_change:
        print("Investigation saved. No patch was approved or applied. Use the explicit approval flag to exercise the full synthetic demo.")
        return
    plan = call(args.base_url,"/api/repositories/"+rid+"/plans",{
        "consent_to_model":True,"intended_rule_changes":["rule-age-eligibility"],
        "objective":"Correct only the inclusive age-65 eligibility mismatch proven by independent policy trials. Preserve duplicate, decimal rounding, review and error behavior."})
    call(args.base_url,"/api/plans/"+plan["id"]+"/approve",{"approved":True,"approved_rule_changes":["rule-age-eligibility"]})
    job = call(args.base_url,"/api/plans/"+plan["id"]+"/execute",{"approved":True})
    deadline = time.monotonic()+1200
    while job["status"] in {"queued","running"}:
        if time.monotonic()>deadline:
            raise RuntimeError("HTTP demo timed out; the backend job may still be running.")
        time.sleep(1)
        job = call(args.base_url,"/api/jobs/"+job["id"])
    report = job["results"]["behavior_report"]
    (evidence/"last-upgrade-job.json").write_text(json.dumps(job,indent=2),encoding="utf-8")
    (evidence/"last-upgrade-evidence.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    if job["results"]["diffs"]:
        with urlopen(args.base_url+"/api/jobs/"+job["id"]+"/patch",timeout=15) as response:
            (evidence/"last-upgrade.patch").write_bytes(response.read())
    print(json.dumps({"job_id":job["id"],"status":job["status"],"verification":job["results"]["verification"],
        "memory_model":report["rulebook"]["model_status"],"signals_model":report["signals"]["model_status"],
        "classifications":report["classifications"],"rule_coverage":report["rule_coverage"],
        "baseline_tests":job["results"]["baseline"]["counts"],"modified_tests":job["results"]["modified"]["counts"],
        "repairs":len(job["results"]["repairs"]),"changed_files":[d["path"] for d in job["results"]["diffs"]],
        "error":job["error"]},indent=2))
    print("Frontend output: http://127.0.0.1:3000/?job="+job["id"])
    if job["status"]!="succeeded" or report["status"]!="passed":
        raise RuntimeError("Demo did not verify; inspect .ghostpatch/last-upgrade-evidence.json without claiming success.")


if __name__=="__main__":
    main()
