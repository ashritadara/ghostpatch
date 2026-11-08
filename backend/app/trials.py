"""Independent oracle selection and classification for bounded Ghost Trials."""
import json

from .errors import GhostPatchError
from .harness_schemas import BehaviorReport, Outcome, Scenario, ScenarioResult
from .memory import policy_fixture, reference, stable_id


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def outcome_equal(left: Outcome, right: Outcome) -> bool:
    return canonical(left.model_dump()) == canonical(right.model_dump())


def input_digest(value) -> str:
    import hashlib
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def policy_outcome(repo, value):
    """Trusted declarative-policy interpreter; never imports repository code."""
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    policy = policy_fixture(repo)
    parameters = policy["parameters"]
    age = value["age"]
    try:
        amount = Decimal(str(value["amount"]))
    except InvalidOperation:
        return Outcome(exception_type="ValueError"), "rule-invalid-input"
    if type(age) is not int or age < 0 or not amount.is_finite() or amount < 0:
        return Outcome(exception_type="ValueError"), "rule-invalid-input"
    if value.get("duplicate", False):
        return Outcome(output={"decision": "rejected", "reason": "duplicate", "payable": "0.00"}), "rule-duplicates"
    if age < parameters["minimum_age"]:
        return Outcome(output={"decision": "rejected", "reason": "age_threshold", "payable": "0.00"}), "rule-age-eligibility"
    result = {"decision": "review" if amount > Decimal(parameters["review_above"]) else "approved", "reason": "eligible",
              "payable": format(amount.quantize(Decimal(parameters["quantum"]), rounding=ROUND_HALF_UP), ".2f")}
    return Outcome(output=result), "rule-age-eligibility" if age == parameters["minimum_age"] else "rule-review" if amount >= Decimal(parameters["review_above"]) else "rule-rounding"


def initial_scenarios(repo, book) -> list[Scenario]:
    scenarios = []
    fixture = policy_fixture(repo)
    if fixture:
        rules = {r["id"]: r for r in fixture["rules"]}
        for item in fixture["scenarios"]:
            scenarios.append(Scenario(**item, oracle="approved_policy", invariant=None, origin="trusted_fixture",
                oracle_reference=reference(repo, "POLICY.md", rules[item["rule_ids"][0]]["line"])))
    elif repo.trusted:
        path = repo.original / "behavior_cases.json"
        rule_ids = [r.id for r in book.rules if r.kind == "observed_implementation"][:1]
        for item in json.loads(path.read_text()):
            if rule_ids:
                scenarios.append(Scenario(id="trial-legacy-" + item["id"], title="Compatibility: " + item["id"],
                    category="normal", rule_ids=rule_ids, input=item["rows"], oracle="legacy_observation",
                    rationale="Capture original output as a compatibility baseline, not proof of correctness.", origin="deterministic"))
    if scenarios:
        example = next((s for s in scenarios if s.category == "normal"), scenarios[0])
        for invariant in ("input_unchanged", "repeatability"):
            scenarios.append(Scenario(id="trial-" + invariant, title=invariant, category="regression",
                rule_ids=example.rule_ids, input=example.input, oracle="metamorphic_invariant", invariant=invariant,
                rationale="Independent fixed assertion implemented in the trusted runner.", origin="deterministic"))
    return scenarios


def validate_candidate(repo, candidate, book):
    known = {r.id for r in book.rules}
    if not set(candidate.rule_ids).issubset(known):
        raise GhostPatchError("Scenario cites an unknown rule.")
    value = candidate.input
    if repo.sample_id == "claims_demo":
        if not isinstance(value, dict) or not {"age", "amount"}.issubset(value) or set(value) - {"age", "amount", "duplicate"}:
            raise GhostPatchError("Claims scenarios must use the fixed synthetic age/amount/duplicate adapter.")
        if type(value["age"]) is not int or not -1 <= value["age"] <= 120:
            raise GhostPatchError("Synthetic scenario age is outside the bounded demo domain.")
        if "duplicate" in value and type(value["duplicate"]) is not bool:
            raise GhostPatchError("Synthetic duplicate flag must be boolean.")
        import re
        if not isinstance(value["amount"], str) or not re.fullmatch(r"-?\d{1,6}(?:\.\d{1,3})?|invalid", value["amount"]):
            raise GhostPatchError("Synthetic scenario amount is outside the bounded demo domain.")
    elif repo.sample_id == "legacy_reports":
        if not isinstance(value, list) or len(value) > 10:
            raise GhostPatchError("Reporting scenarios require a bounded synthetic row list.")
        for row in value:
            if not isinstance(row, dict) or set(row) != {"department", "amount"} or not all(isinstance(x, str) for x in row.values()):
                raise GhostPatchError("Invalid synthetic reporting row.")
    if candidate.oracle == "metamorphic_invariant" and candidate.invariant not in {"input_unchanged", "repeatability"}:
        raise GhostPatchError("Unknown independently implemented invariant.")


def add_candidates(repo, book, scenarios, candidates, origin="nemotron") -> int:
    added = 0
    fixtures = initial_scenarios(repo, book)
    for candidate in candidates:
        try:
            validate_candidate(repo, candidate, book)
        except GhostPatchError as exc:
            book.warnings.append("Rejected scenario: " + exc.message)
            continue
        if len(scenarios) >= 24:
            book.warnings.append("Scenario budget reached (24).")
            break
        # The model cannot supply expected output. Only a matching pinned
        # fixture can upgrade an oracle to approved_policy.
        matching = next((s for s in fixtures if s.oracle == "approved_policy" and canonical(s.input) == canonical(candidate.input)), None)
        if matching:
            if not any(s.id == matching.id for s in scenarios):
                scenarios.append(matching)
                added += 1
            continue
        if repo.trusted and repo.sample_id == "claims_demo" and candidate.oracle != "metamorphic_invariant":
            expected, rule_id = policy_outcome(repo, candidate.input)
            entry = next(r for r in policy_fixture(repo)["rules"] if r["id"] == rule_id)
            if any(canonical(s.input) == canonical(candidate.input) and s.oracle == "approved_policy" for s in scenarios):
                continue
            scenarios.append(Scenario(**{**candidate.model_dump(), "oracle": "approved_policy", "rule_ids": sorted(set(candidate.rule_ids + [rule_id]))},
                id=stable_id("trial", [candidate.input, "approved_policy"]), expected=expected,
                oracle_reference=reference(repo, "POLICY.md", entry["line"]), origin=origin))
            added += 1
            continue
        if any(canonical(s.input) == canonical(candidate.input) and s.oracle == candidate.oracle and s.invariant == candidate.invariant for s in scenarios):
            continue
        oracle = candidate.oracle if repo.trusted else "hypothesis"
        item = Scenario(**{**candidate.model_dump(), "oracle": oracle},
            id=stable_id("trial", [candidate.input, oracle, candidate.invariant, sorted(candidate.rule_ids)]), origin=origin)
        scenarios.append(item)
        added += 1
    return added


def compare_scenarios(scenarios, baseline, modified=None, approved_rule_changes=()):
    old = {x.scenario_id: x for x in (baseline.trial_outputs if baseline else [])}
    new = {x.scenario_id: x for x in (modified.trial_outputs if modified else [])}
    results = []
    for scenario in scenarios:
        before, after = old.get(scenario.id), new.get(scenario.id)
        actual = after if modified else before
        expected = scenario.expected
        classification, reason = "unverified", "No eligible execution evidence is available."
        if scenario.oracle == "hypothesis":
            reason = "Unverified hypothesis: a model assertion is never a pass/fail oracle."
        elif actual is None or (modified and before is None):
            reason = "Missing original or modified scenario execution."
        elif actual.input_digest != input_digest(scenario.input) or (before and before.input_digest != input_digest(scenario.input)):
            classification, reason = "execution_error", "Runner evidence does not match the approved synthetic input."
        elif scenario.oracle == "approved_policy":
            if expected is None or scenario.oracle_reference is None:
                reason = "Independent policy evidence is missing."
            elif outcome_equal(actual.outcome, expected):
                if modified and before and not outcome_equal(before.outcome, actual.outcome):
                    if set(scenario.rule_ids) & set(approved_rule_changes):
                        classification, reason = "intended_change", "Changed behavior matches the pinned independent policy and explicit semantic approval."
                    else:
                        classification, reason = "unexpected_divergence", "Policy-compatible output changed without approval for the linked business rule."
                else:
                    classification, reason = "preserved", "Observed output agrees with the independent policy fixture."
            else:
                classification = "execution_error" if actual.outcome.exception_type and not expected.exception_type else "unexpected_divergence"
                reason = "Actual output/exception disagrees with the independently approved policy fixture."
        elif scenario.oracle == "metamorphic_invariant":
            if actual.invariant_passed is True:
                classification, reason = "preserved", "The fixed independent invariant passed; this does not establish full business correctness."
            else:
                classification, reason = "execution_error", "Independent invariant failed or did not execute."
        elif not modified:
            reason = "Original behavior captured as a compatibility baseline; no modified execution yet."
            expected = before.outcome if before else None
        elif before and outcome_equal(before.outcome, actual.outcome):
            classification, reason = "preserved", "Matches original observation; compatibility is not proof of correct policy."
            expected = before.outcome
        else:
            classification, reason = "unexpected_divergence", "Behavior changed relative to the compatibility baseline without an independent oracle authorizing it."
            expected = before.outcome if before else None
        if actual and (actual.input_mutated or actual.created_files) and classification in {"preserved", "intended_change"}:
            if before is None or before.input_mutated != actual.input_mutated or before.created_files != actual.created_files:
                classification, reason = "unexpected_divergence", "Observed input mutation or file side effect changed."
        results.append(ScenarioResult(scenario=scenario, baseline=before, modified=after, classification=classification, reason=reason, expected=expected))
    return results


def preservation_report(repo, state, baseline, modified=None, approved_rule_changes=(), diffs=None):
    results = compare_scenarios(state.scenarios, baseline, modified, approved_rule_changes)
    classes = {key: sum(r.classification == key for r in results) for key in ("preserved", "intended_change", "unexpected_divergence", "unverified", "execution_error")}
    covered = {rule for r in results if r.baseline or r.modified for rule in r.scenario.rule_ids}
    enforceable = [r for r in results if r.scenario.oracle != "hypothesis"]
    tests_ok = bool(baseline and baseline.status == "passed" and modified and modified.status == "passed")
    failed_tests = any(run and run.status == "failed" for run in (baseline, modified))
    status = "failed" if failed_tests or classes["unexpected_divergence"] or classes["execution_error"] else "passed" if tests_ok and enforceable and all(r.classification in {"preserved", "intended_change"} for r in enforceable) else "not_verified"
    return BehaviorReport(repository_id=repo.id, rulebook=state.rulebook.model_copy(deep=True), signals=state.signals.model_copy(deep=True),
        scenario_results=results, rule_coverage={"covered": len(covered), "total": len(state.rulebook.rules), "scenarios": len(results)},
        classifications=classes, status=status, approved_rule_changes=list(approved_rule_changes),
        limitations=["Code observations and model hypotheses are not authoritative policy.",
                     "Legacy observations establish compatibility only; original behavior may be wrong.",
                     "Only the pinned synthetic sample executes. No real-user tracking or real claims data.",
                     "No nondeterministic fields were normalized; raw trial outputs and exceptions are retained.",
                     "Passing sampled tests/trials does not prove universal correctness or equivalence."],
        test_evidence={"baseline": baseline.model_dump() if baseline else None, "modified": modified.model_dump() if modified else None},
        diffs=diffs or [], tool_invocations=list(state.trace), policy_version=state.rulebook.policy_version,
        reevaluations=[item.model_copy(deep=True) for item in getattr(state,"reevaluations",[])],
        approval_state="explicit_semantic_approval" if approved_rule_changes else "no_edits_authorized")
