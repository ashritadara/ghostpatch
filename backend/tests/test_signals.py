import json
import threading
import pytest
from pydantic import ValidationError

from app.errors import GhostPatchError
from app.harness import GhostHarness
from app.harness_schemas import SyntheticEvent
from app.signals import aggregate, ingest, parse_events
from conftest import DeterministicModelDouble, SequenceRunnerDouble


def service(settings):
    return GhostHarness(DeterministicModelDouble(), SequenceRunnerDouble(), settings, threading.Lock())


def test_synthetic_before_after_metrics_and_proposed_conflict(loader, settings):
    repo = loader.sample("claims_demo")
    harness = service(settings)
    harness.import_fixture(repo, "before")
    state = harness.ensure(repo)
    before = state.signals.windows[0]
    assert before.event_count == 27 and before.session_count == 12
    metrics = {m.kind:m for m in before.metrics}
    assert metrics["manual_overrides"].numerator == 4 and metrics["manual_overrides"].denominator == 12
    assert metrics["session_reuse"].numerator == 6
    harness.import_fixture(repo, "after")
    after = next(w for w in state.signals.windows if w.dataset_version == "after-v1")
    metrics = {m.kind:m for m in after.metrics}
    assert after.event_count == 39 and metrics["manual_overrides"].numerator == 8
    assert metrics["session_reuse"].numerator == 2
    assert len(state.events) == 66 and state.signals.hypotheses
    assert all(h.status == "hypothesis" for h in state.signals.hypotheses)
    assert any(c.basis == "signal_hypothesis" and c.status == "proposed" for c in state.rulebook.conflicts)
    assert next(r for r in state.rulebook.rules if r.id == "rule-age-eligibility").status == "verified"
    assert harness.import_fixture(repo, "after") == 0


@pytest.mark.parametrize("change", [{"email":"private@example.invalid"}, {"synthetic":False},
    {"session_id":"someone@example.invalid"}, {"metadata":{"name":"person"}}, {"metadata":{"raw_claim":{}}}])
def test_sensitive_unknown_and_nonsynthetic_fields_rejected(loader, change):
    repo = loader.sample("claims_demo")
    event = json.loads((repo.original/"signals_before.jsonl").read_text().splitlines()[0])
    event.update(change)
    with pytest.raises(ValidationError):
        SyntheticEvent.model_validate(event)


def test_deduplicate_conflicting_payload_and_sample_size(loader, settings):
    repo = loader.sample("claims_demo")
    harness = service(settings)
    state = harness.ensure(repo)
    events = parse_events((repo.original/"signals_before.jsonl").read_bytes())
    ingest(state, events[:1], "before-v1")
    assert all(not m.eligible for m in state.signals.windows[0].metrics)
    assert ingest(state, events[:1], "before-v1") == 0
    changed = events[0].model_copy(update={"outcome":"error"})
    with pytest.raises(GhostPatchError, match="Conflicting"):
        ingest(state, [changed], "before-v1")
    fresh = harness.memory.deterministic(repo)
    from app.harness import InvestigationState
    new_state = InvestigationState(fresh, [])
    with pytest.raises(GhostPatchError):
        ingest(new_state, [events[0], changed], "before-v1")
    assert not new_state.events


def test_jsonl_limits_and_aggregates_omit_sessions(loader, settings):
    repo = loader.sample("claims_demo")
    harness = service(settings)
    harness.import_fixture(repo, "before")
    dumped = harness.ensure(repo).signals.model_dump_json()
    assert "session_id" not in dumped and "s_00000001" not in dumped
    with pytest.raises(GhostPatchError):
        parse_events(b"x" * (128*1024 + 1))
    with pytest.raises(GhostPatchError):
        parse_events(b'{"unknown":"sensitive"}')


def test_model_receives_aggregates_not_raw_events_or_sessions(loader, settings):
    class CapturingModel:
        received = None
        def investigate_signals(self, context):
            self.received = context
            raise GhostPatchError("Intentional model-outage test", 503)
    model = CapturingModel()
    repo = loader.sample("claims_demo")
    harness = GhostHarness(model, SequenceRunnerDouble(), settings, threading.Lock())
    harness.import_fixture(repo, "before")
    state = harness.interpret(repo, True, True)
    encoded = json.dumps(model.received)
    assert "aggregated_signals" in encoded
    assert "s_00000001" not in encoded and "ev_00000001" not in encoded
    assert state.signals.model_status == "failed" and state.signals.hypotheses
