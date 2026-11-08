from dataclasses import replace
import pytest

from app.errors import GhostPatchError
from app.harness import GhostHarness
from app.harness_schemas import Outcome, RuleCandidate, RuleExtraction, Scenario, ScenarioCandidate, SourceCandidate, TrialExecution
from app.memory import GhostMemory, reference, transition, validate_reference
from app.trials import add_candidates, compare_scenarios, initial_scenarios, input_digest, policy_outcome
from conftest import DeterministicModelDouble, SequenceRunnerDouble
import threading


def test_rulebook_stable_source_backed_and_policy_distinct(loader):
    repo = loader.sample("claims_demo")
    memory = GhostMemory()
    first, second = memory.deterministic(repo), memory.deterministic(repo)
    assert [r.id for r in first.rules] == [r.id for r in second.rules]
    policy = next(r for r in first.rules if r.id == "rule-age-eligibility")
    assert policy.status == "verified" and policy.origin == "trusted_policy"
    observed = [r for r in first.rules if r.kind == "observed_implementation"]
    assert observed and all(r.status == "hypothesis" for r in observed)
    assert any(c.basis == "source_contradiction" and c.status == "proposed" for c in first.conflicts)
    for rule in first.rules:
        for ref in rule.references:
            assert validate_reference(repo, SourceCandidate(**{k:v for k,v in ref.model_dump().items() if k in SourceCandidate.model_fields})).sha256 == ref.sha256


@pytest.mark.parametrize("changes", [
    {"file_path":"missing.py"}, {"line_start":999,"line_end":999}, {"function":"invented"},
    {"quote":"hallucinated evidence"}, {"line_start":10,"line_end":2}
])
def test_hallucinated_references_rejected(loader, changes):
    repo = loader.sample("claims_demo")
    candidate = reference(repo, "claims.py", 17, function="evaluate_claim").model_dump()
    candidate = {k:v for k,v in candidate.items() if k in SourceCandidate.model_fields}
    candidate.update(changes)
    with pytest.raises(GhostPatchError):
        validate_reference(repo, SourceCandidate(**candidate))


def test_rule_status_history_and_independent_verification(loader):
    repo = loader.sample("claims_demo")
    rule = next(r for r in GhostMemory().deterministic(repo).rules if r.kind == "observed_implementation")
    with pytest.raises(GhostPatchError, match="independent"):
        transition(rule, "verified", "unsupported assertion", [])
    transition(rule, "conflicted", "Trial policy mismatch", ["trial-boundary"])
    transition(rule, "superseded", "Approved correction", ["trial-boundary"])
    assert rule.version == 3 and len(rule.history) == 3
    with pytest.raises(GhostPatchError):
        transition(rule, "verified", "silent revival", [], independent=True)


def execution(scenario, output=None, exception=None, invariant=None):
    return TrialExecution(scenario_id=scenario.id, input_digest=input_digest(scenario.input),
        outcome=Outcome(output=output, exception_type=exception), duration_ms=1, invariant_passed=invariant)


def run_with(*executions):
    from app.schemas import TestRun as Run
    return Run(status="passed", trial_outputs=list(executions))


def test_independent_policy_change_requires_semantic_approval(loader):
    repo = loader.sample("claims_demo")
    book = GhostMemory().deterministic(repo)
    scenario = next(s for s in initial_scenarios(repo, book) if s.id == "trial-boundary-age-65")
    wrong = {"decision":"rejected","reason":"age_threshold","payable":"0.00"}
    before = run_with(execution(scenario, wrong))
    after = run_with(execution(scenario, scenario.expected.output))
    assert compare_scenarios([scenario], before)[0].classification == "unexpected_divergence"
    assert compare_scenarios([scenario], before, after)[0].classification == "unexpected_divergence"
    assert compare_scenarios([scenario], before, after, ["rule-age-eligibility"])[0].classification == "intended_change"


def test_hypothesis_is_never_a_correctness_oracle():
    scenario = Scenario(id="hypothesis", title="Unverified", category="normal", rule_ids=["r"], input={},
        oracle="hypothesis", rationale="Unsupported assertion", origin="nemotron", expected=Outcome(output="invented"))
    result = compare_scenarios([scenario], run_with(execution(scenario, "invented")), run_with(execution(scenario, "invented")))[0]
    assert result.classification == "unverified"


def test_generated_scenario_expected_is_independently_selected(loader):
    repo = loader.sample("claims_demo")
    book = GhostMemory().deterministic(repo)
    scenarios = initial_scenarios(repo, book)
    candidate = ScenarioCandidate(title="Different boundary amount", category="boundary",
        rule_ids=["rule-age-eligibility"], input={"age":65,"amount":"0"}, oracle="legacy_observation", rationale="Boundary investigation")
    assert add_candidates(repo, book, scenarios, [candidate]) == 1
    assert scenarios[-1].oracle == "approved_policy"
    assert scenarios[-1].expected.output == {"decision":"approved","reason":"eligible","payable":"0.00"}
    assert scenarios[-1].oracle_reference.role == "policy"


def test_unknown_rule_or_adapter_is_rejected(loader):
    repo = loader.sample("claims_demo")
    book = GhostMemory().deterministic(repo)
    candidate = ScenarioCandidate(title="Unknown rule", category="normal", rule_ids=["invented"],
        input={"age":65,"amount":"1"}, oracle="hypothesis", rationale="Invalid")
    scenarios = []
    assert add_candidates(repo, book, scenarios, [candidate]) == 0
    assert not scenarios and book.warnings


def test_model_failure_keeps_deterministic_memory(loader, settings):
    class FailedModel:
        def extract_rules(self, context):
            raise GhostPatchError("NVIDIA unavailable", 503)
    repo = loader.sample("claims_demo")
    harness = GhostHarness(FailedModel(), SequenceRunnerDouble(), settings, threading.Lock())
    state = harness.extract(repo, True, True)
    assert state.rulebook.rules and state.rulebook.model_status == "failed"
    assert state.trace[-1].status == "failed"
    assert state.rulebook.model_error == "NVIDIA unavailable"


def test_reference_quote_and_hash_match_exact_original_indentation(loader):
    import hashlib
    repo = loader.sample("claims_demo")
    original = (repo.original / "claims.py").read_text().splitlines()[16]
    result = validate_reference(repo, SourceCandidate(file_path="claims.py", function="evaluate_claim",
        line_start=17, line_end=17, quote=original.strip()))
    assert result.quote == original
    assert result.sha256 == hashlib.sha256(result.quote.encode()).hexdigest()
