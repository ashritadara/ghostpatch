from dataclasses import replace
import json
import threading

import pytest
from pydantic import ValidationError

from app.errors import GhostPatchError
from app.harness import GhostHarness
from app.harness_schemas import ObservationWindow, SyntheticEvent
from app.signals import aggregate, ingest, parse_events
from conftest import DeterministicModelDouble, SequenceRunnerDouble


def setup(loader, settings):
    repo=loader.sample("claims_demo")
    harness=GhostHarness(DeterministicModelDouble(),SequenceRunnerDouble(["passed"]),settings,threading.Lock())
    return repo,harness


def test_identity_cohort_windows_and_drift_are_reproducible(loader,settings):
    repo,harness=setup(loader,settings)
    harness.import_fixture(repo,"before")
    harness.import_fixture(repo,"after")
    state=harness.ensure(repo)
    before=next(w for w in state.signals.windows if w.dataset_version=="before-v1")
    after=next(w for w in state.signals.windows if w.dataset_version=="after-v1")
    bm={m.kind:m for m in before.metrics};am={m.kind:m for m in after.metrics}
    assert before.user_count==12 and after.user_count==12
    assert bm["return_rate"].numerator==6 and bm["return_rate"].denominator==12
    assert am["return_rate"].numerator==2 and am["return_rate"].denominator==12
    assert bm["return_rate"].available and bm["return_rate"].window_start
    assert before.software_version=="legacy-v1" and after.software_version=="candidate-v2"
    meaningful=[d for d in state.signals.drifts if d.status=="meaningful"]
    assert any(d.metric=="return_rate" for d in meaningful)
    assert any(d.category=="input_data" for d in meaningful)
    assert all(d.before_window and d.after_window and d.evidence_ids for d in meaningful)
    assert len(state.reevaluations)==1
    assert harness.import_fixture(repo,"after")==0 and len(state.reevaluations)==1
    assert state.rulebook.investigations
    assert all(len(i["explanations"])>=2 for i in state.rulebook.investigations)
    assert all(any(e["kind"]!="code" for e in i["explanations"]) for i in state.rulebook.investigations)


def test_missing_users_never_invent_retention(loader,settings):
    repo,harness=setup(loader,settings)
    state=harness.ensure(repo)
    events=[e.model_copy(update={"user_id":None}) for e in parse_events((repo.original/"signals_before.jsonl").read_bytes())]
    window=ObservationWindow(start="2026-11-01T00:00:00Z",end="2026-11-03T00:00:00Z")
    ingest(state,events,"before-v1",window)
    metrics={m.kind:m for m in state.signals.windows[0].metrics}
    for name in ("return_rate","repeat_visits"):
        assert metrics[name].rate is None and metrics[name].available is False
        assert metrics[name].numerator==metrics[name].denominator==0
        assert "IDs" in metrics[name].unavailable_reason
    assert "not a user-return" in metrics["session_reuse"].explanation


def test_explicit_followup_and_comparable_versions_required(loader,settings):
    repo,harness=setup(loader,settings)
    state=harness.ensure(repo)
    for version in ("before","after"):
        events=parse_events((repo.original/("signals_"+version+".jsonl")).read_bytes())
        ingest(state,events,version+"-v1")
    assert all(not m.available for w in state.signals.windows for m in w.metrics if m.kind=="return_rate")
    assert all(d.status=="not_comparable" for d in state.signals.drifts)
    assert harness.enqueue(repo) is None


def test_noncomparable_duration_and_mixed_versions_do_not_trigger(loader,settings):
    repo,harness=setup(loader,settings)
    state=harness.ensure(repo)
    before=parse_events((repo.original/"signals_before.jsonl").read_bytes())
    after=parse_events((repo.original/"signals_after.jsonl").read_bytes())
    ingest(state,before,"before-v1",ObservationWindow(start="2026-11-01T00:00:00Z",end="2026-11-03T00:00:00Z"))
    after[0]=after[0].model_copy(update={"software_version":"legacy-v1"})
    ingest(state,after,"after-v1",ObservationWindow(start="2026-11-05T00:00:00Z",end="2026-11-08T00:00:00Z"))
    assert all(d.status=="not_comparable" for d in state.signals.drifts)
    assert harness.enqueue(repo) is None


def test_event_window_bounds_and_pii_fields(loader,settings):
    repo,harness=setup(loader,settings)
    state=harness.ensure(repo)
    event=parse_events((repo.original/"signals_before.jsonl").read_bytes())[0]
    with pytest.raises(GhostPatchError,match="outside"):
        ingest(state,[event],"before-v1",ObservationWindow(start="2026-11-05T00:00:00Z",end="2026-11-07T00:00:00Z"))
    for changes in ({"user_id":"person@example.invalid"},{"software_version":"email@private.invalid"},{"comment":"change code now"}):
        data=event.model_dump(mode="json");data.update(changes)
        with pytest.raises(ValidationError):
            SyntheticEvent.model_validate(data)
    with pytest.raises(ValidationError):
        ObservationWindow(start="2026-11-01T00:00:00",end="2026-11-03T00:00:00Z")


def test_queue_and_evaluation_idempotency_and_budget(loader,settings):
    repo,harness=setup(loader,settings)
    harness.import_fixture(repo,"before");harness.import_fixture(repo,"after")
    state=harness.ensure(repo);item=state.reevaluations[0]
    harness.evaluate(repo,item)
    count=len(harness.runner.calls)
    harness.evaluate(repo,item)
    assert len(harness.runner.calls)==count and item.attempts==1
    assert item.status=="completed"
    existing=parse_events((repo.original/"signals_after.jsonl").read_bytes())[12]
    window=state.observation_windows["after-v1"]
    for number in range(6):
        event=existing.model_copy(update={"event_id":"ev_"+format(10000+number,"08x")})
        harness.ingest_events(repo,[event],"after-v1",window)
    assert len(state.reevaluations)==4
    assert any("budget exhausted" in warning for warning in state.signals.warnings)


def test_untrusted_re_evaluation_never_calls_runner(loader,settings,monkeypatch):
    from conftest import zip_bytes
    repo=loader.zip(zip_bytes({"app.py":"if True:\n    value=1\n"}),"untrusted.zip")
    harness=GhostHarness(DeterministicModelDouble(),SequenceRunnerDouble(["passed"]),settings,threading.Lock())
    state=harness.ensure(repo)
    # A policy-shaped request label cannot confer authority. Exercise the shared
    # queue executor directly with a diagnostic trigger, still without execution.
    item=harness.enqueue(repo,"approved_policy_update",evidence=["unit-test-only"])
    monkeypatch.setattr(harness.runner,"run",lambda *a,**k:pytest.fail("No uploaded code may execute"))
    monkeypatch.setattr(harness.runner,"run_with_trials",lambda *a,**k:pytest.fail("No uploaded code may execute"))
    harness.evaluate(repo,item)
    assert item.status=="suggested_only" and item.report_status=="not_verified"


def test_workflow_cohorts_must_match(loader,settings):
    repo,harness=setup(loader,settings);state=harness.ensure(repo)
    before=parse_events((repo.original/"signals_before.jsonl").read_bytes())
    after=[e.model_copy(update={"workflow":"claim_submission"}) for e in parse_events((repo.original/"signals_after.jsonl").read_bytes())]
    ingest(state,before,"before-v1",ObservationWindow(start="2026-11-01T00:00:00Z",end="2026-11-03T00:00:00Z"))
    ingest(state,after,"after-v1",ObservationWindow(start="2026-11-05T00:00:00Z",end="2026-11-07T00:00:00Z"))
    assert all(d.status=="not_comparable" for d in state.signals.drifts)
    assert harness.enqueue(repo) is None


def test_session_cannot_switch_pseudonymous_user_and_windows_are_immutable(loader,settings):
    repo,harness=setup(loader,settings);state=harness.ensure(repo)
    harness.import_fixture(repo,"before")
    event=parse_events((repo.original/"signals_before.jsonl").read_bytes())[0]
    changed=event.model_copy(update={"event_id":"ev_11111111","user_id":"u_99999999"})
    with pytest.raises(GhostPatchError,match="identity"):
        ingest(state,[changed],"before-v1",state.observation_windows["before-v1"])
    with pytest.raises(GhostPatchError,match="silently changed"):
        ingest(state,[event],"before-v1",ObservationWindow(start="2026-11-01T00:00:00Z",end="2026-11-04T00:00:00Z"))


def test_adding_missing_windows_to_existing_events_triggers_once(loader,settings):
    repo,harness=setup(loader,settings);state=harness.ensure(repo)
    for version in ("before","after"):
        events=parse_events((repo.original/("signals_"+version+".jsonl")).read_bytes())
        harness.ingest_events(repo,events,version+"-v1")
    assert not state.reevaluations
    for version,start,end in (("before","2026-11-01","2026-11-03"),("after","2026-11-05","2026-11-07")):
        events=parse_events((repo.original/("signals_"+version+".jsonl")).read_bytes())
        assert harness.ingest_events(repo,events,version+"-v1",ObservationWindow(start=start+"T00:00:00Z",end=end+"T00:00:00Z"))==0
    assert len(state.reevaluations)==1
    harness.import_fixture(repo,"after")
    assert len(state.reevaluations)==1


def test_signal_grounding_retry_rejects_invented_evidence(loader,settings):
    from app.harness_schemas import SignalInterpretation
    class GroundingModel:
        def __init__(self):self.calls=[]
        def investigate_signals(self,context):
            self.calls.append(dict(context))
            evidence=context["evidence_catalog"][0] if len(self.calls)>1 else "invented-evidence"
            return SignalInterpretation.model_validate({"hypotheses":[{
                "title":"Investigate boundary","description":"Boundary behavior may explain the aggregate change.",
                "rule_ids":["rule-age-eligibility"],"alternate_explanations":["Workflow changes.","Input mix changed."],
                "confidence":.5,"references":[context["reference_options"][0]],
                "suggested_scenarios":[{"title":"Boundary","category":"boundary","rule_ids":["rule-age-eligibility"],
                    "input":{"age":65,"amount":"10"},"oracle":"legacy_observation","rationale":"Check independently."}],
                "explanations":[{"id":"code","kind":"code","description":"Boundary mismatch.",
                    "evidence_for":[evidence],"uncertainty":"No causal evidence."}]}]})
    repo,harness=setup(loader,settings);model=GroundingModel();harness.model=model
    harness.import_fixture(repo,"before");harness.import_fixture(repo,"after")
    state=harness.interpret(repo,True,True)
    assert len(model.calls)==2 and state.signals.model_status=="succeeded"
    assert "validation_feedback" in model.calls[1]
    assert any(t.tool=="nemotron.investigate_signals" and t.status=="failed" for t in state.trace)
    assert all("invented-evidence" not in e.evidence_for for h in state.signals.hypotheses for e in h.explanations)
    payload=json.dumps(model.calls)
    assert '"user_id"' not in payload and '"session_id"' not in payload
