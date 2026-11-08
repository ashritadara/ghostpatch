"""Strict synthetic-only ingestion and deterministic signals before AI interpretation."""
from collections import defaultdict
from datetime import timezone, timedelta
import json

from pydantic import ValidationError

from .errors import GhostPatchError
from .harness_schemas import (CompetingExplanation, DriftFinding, ObservationWindow, ScenarioCandidate,
    SignalHypothesis, SignalMetric, SignalWindow, SignalsReport, SyntheticEvent)
from .memory import add_conflict, stable_id, validate_reference


def parse_events(data: bytes) -> list[SyntheticEvent]:
    if len(data) > 128 * 1024:
        raise GhostPatchError("Synthetic event fixture exceeds 128 KiB.", 413)
    try:
        text = data.decode("utf-8")
        if text.lstrip().startswith("["):
            values = json.loads(text)
        else:
            values = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not isinstance(values, list) or not 1 <= len(values) <= 500:
            raise ValueError()
        return [SyntheticEvent.model_validate(item) for item in values]
    except (ValueError, UnicodeDecodeError, ValidationError):
        raise GhostPatchError("Invalid synthetic JSON/JSONL event fixture; unknown/sensitive fields are prohibited.") from None


def ingest(state, events, dataset_version: str, observation_window=None) -> int:
    if len(json.dumps([e.model_dump(mode="json") for e in events])) > 128 * 1024:
        raise GhostPatchError("Synthetic event payload exceeds 128 KiB.", 413)
    known = {r.id for r in state.rulebook.rules}
    additions = {}
    session_users = {}
    for _, event in state.events.values():
        if event.user_id:
            session_users.setdefault(event.session_id, event.user_id)
    windows = getattr(state, "observation_windows", {})
    previous_window = windows.get(dataset_version)
    if previous_window and observation_window and previous_window != observation_window:
        raise GhostPatchError("An existing dataset's observation window cannot be silently changed.", 409)
    window = previous_window or observation_window
    related = [e for version, e in state.events.values() if version == dataset_version] + list(events)
    if window and any(not window.start <= e.timestamp < window.end for e in related):
        raise GhostPatchError("Synthetic event timestamp falls outside its declared observation window.")
    for event in events:
        if event.user_id and event.session_id in session_users and session_users[event.session_id] != event.user_id:
            raise GhostPatchError("A pseudonymous session cannot silently change user identity.")
        if event.user_id:
            session_users[event.session_id] = event.user_id
        if not set(event.rule_context).issubset(known):
            raise GhostPatchError("Synthetic event cites an unknown rule.")
        item = (dataset_version, event)
        old = state.events.get(event.event_id) or additions.get(event.event_id)
        if old and (old[0] != dataset_version or old[1].model_dump(mode="json") != event.model_dump(mode="json")):
            raise GhostPatchError("Conflicting duplicate event ID; original event was retained.", 409)
        if event.event_id not in state.events:
            additions[event.event_id] = item
    if len(state.events) + len(additions) > 500:
        raise GhostPatchError("Maximum 500 unique synthetic events per repository.", 413)
    state.events.update(additions)
    window_added = bool(observation_window and not previous_window)
    if window_added:
        state.observation_windows[dataset_version] = observation_window
    if additions or window_added:
        state.revision += 1
        state.signals = aggregate(state.events, state.observation_windows, state.rulebook.policy_version)
    return len(additions)


def aggregate(events, observation_windows=None, policy_version=None) -> SignalsReport:
    windows = []
    groups = defaultdict(list)
    for version, event in events.values():
        groups[version].append(event)
    for version, records in sorted(groups.items()):
        sessions = {e.session_id for e in records}
        submits = [e for e in records if e.action == "submit"]
        denominator = len(submits)
        enough = denominator >= 10 and len(sessions) >= 5
        ids = sorted({r for e in records for r in e.rule_context})
        metrics = []
        for kind, action in (("manual_overrides", "manual_override"), ("retries", "retry"), ("abandonment", "abandon")):
            count = sum(e.action == action for e in records)
            metrics.append(SignalMetric(kind=kind, numerator=count, denominator=denominator,
                rate=count / denominator if denominator else None, eligible=enough and count >= 3, rule_ids=ids,
                explanation="Events per submit, not unique affected people. Detection requires 10 submits, 5 sessions and 3 matching events."))
        errors = sum(e.outcome == "error" for e in records)
        metrics.append(SignalMetric(kind="recurring_errors", numerator=errors, denominator=len(records),
            rate=errors / len(records) if records else None, eligible=enough and errors >= 3, rule_ids=ids,
            explanation="Error events / all events; minimum 10 submits, 5 sessions, 3 errors."))
        days = defaultdict(set)
        for event in records:
            days[event.session_id].add(event.timestamp.astimezone(timezone.utc).date())
        reused = sum(len(value) >= 2 for value in days.values())
        metrics.append(SignalMetric(kind="session_reuse", numerator=reused, denominator=len(sessions),
            rate=reused / len(sessions) if sessions else None, eligible=len(sessions) >= 5, rule_ids=ids,
            explanation="Pseudonymous sessions seen on at least two UTC calendar dates / distinct sessions. Synthetic fixture only."))
        overrides = [e for e in records if e.action == "manual_override"]
        at_boundary = sum(e.metadata.age_band == "at_threshold" for e in overrides)
        metrics.append(SignalMetric(kind="threshold_override_concentration", numerator=at_boundary, denominator=len(overrides),
            rate=at_boundary / len(overrides) if overrides else None, eligible=enough and at_boundary >= 3, rule_ids=ids,
            explanation="Threshold-band override events / all override events. Association is not causation."))
        window = (observation_windows or {}).get(version)
        for metric in metrics:
            metric.sample_size = len(sessions)
            metric.window_start = window.start.isoformat() if window else None
            metric.window_end = window.end.isoformat() if window else None
        # This older indicator is explicitly session reuse, never user retention.
        next(m for m in metrics if m.kind == "session_reuse").explanation += " This is not a user-return or retention metric."
        known_users = {e.user_id for e in records if e.user_id is not None}
        missing = sum(e.user_id is None for e in records)
        reason = None
        if missing:
            reason = f"Stable pseudonymous user IDs are missing for {missing}/{len(records)} events."
        elif not window:
            reason = "An explicit complete observation window is required."
        elif (window.end - window.start).total_seconds() < 2 * 86400:
            reason = "A full two-day window is required for next-day return observation."
        elif any(t.astimezone(timezone.utc).time().isoformat() != "00:00:00" for t in (window.start, window.end)):
            reason = "User-return windows must align to UTC calendar-day boundaries."
        dates = defaultdict(set)
        for e in records:
            if e.user_id:
                dates[e.user_id].add(e.timestamp.astimezone(timezone.utc).date())
        first_day = window.start.astimezone(timezone.utc).date() if window else None
        cohort = {e.user_id for e in submits if e.user_id and e.timestamp.astimezone(timezone.utc).date() == first_day}
        returned = sum(first_day + timedelta(days=1) in dates[user] for user in cohort) if first_day else 0
        repeats = sum(max(0, len(days) - 1) for days in dates.values())
        for kind, number, denom, explanation in (
            ("return_rate", returned, len(cohort), "First-day submitters active on the next UTC day / eligible first-day submitters. Full declared follow-up window required."),
            ("repeat_visits", repeats, len(known_users), "Additional active UTC user-days beyond each user's first day / identified users; not session counts."),
        ):
            metrics.append(SignalMetric(kind=kind, numerator=number if not reason else 0, denominator=denom if not reason else 0,
                rate=number / denom if not reason and denom else None, available=reason is None and denom>0,
                unavailable_reason=reason or ("No eligible identified users in the declared cohort." if not denom else None), eligible=not reason and denom >= 5, rule_ids=ids,
                explanation=explanation, sample_size=denom if not reason else 0,
                window_start=window.start.isoformat() if window else None, window_end=window.end.isoformat() if window else None))
        submitted_sessions = {e.session_id for e in submits}
        last = {}
        for e in sorted(records, key=lambda item: item.timestamp):
            if e.session_id in submitted_sessions:
                last[e.session_id] = e
        completed = sum(e.outcome in {"approved", "rejected", "completed"} and e.action != "abandon" for e in last.values())
        metrics.append(SignalMetric(kind="workflow_completion", numerator=completed, denominator=len(submitted_sessions),
            rate=completed / len(submitted_sessions) if submitted_sessions else None, eligible=enough,
            rule_ids=ids, sample_size=len(submitted_sessions), window_start=window.start.isoformat() if window else None,
            window_end=window.end.isoformat() if window else None,
            explanation="Submitted sessions whose latest observed event has a terminal approved/rejected/completed outcome / submitted sessions. Not business success."))
        versions = {e.software_version for e in records}
        categories = defaultdict(int)
        for event in submits:
            categories[event.metadata.age_band or "unknown"] += 1
        windows.append(SignalWindow(dataset_version=version, event_count=len(records), session_count=len(sessions), metrics=metrics,
            user_count=len(known_users) if known_users else None, identified_event_count=len(records) - missing,
            unidentified_event_count=missing, observation_window=window,
            software_version=next(iter(versions)) if len(versions) == 1 and None not in versions else None,
            reported_policy_versions=sorted({e.policy_version for e in records if e.policy_version}),
            input_categories={"age_band": dict(categories)}, workflows=sorted({e.workflow for e in records})))
    trends = []
    before = next((w for w in windows if w.dataset_version == "before-v1"), None)
    after = next((w for w in windows if w.dataset_version == "after-v1"), None)
    if before and after:
        for left, right in zip(before.metrics, after.metrics):
            if left.rate is not None and right.rate is not None:
                trends.append({"kind": left.kind, "before_rate": left.rate, "after_rate": right.rate,
                               "delta": right.rate - left.rate, "before_denominator": left.denominator,
                               "after_denominator": right.denominator, "interpretation": "Synthetic descriptive change; no causal claim."})
    result = SignalsReport(windows=windows, trends=trends,
        warnings=["Synthetic demonstration only; no real-user tracking.",
                  "Repeated events may reflect the same session. Denominators and minimum sample sizes are explicit.",
                  "Usage patterns propose investigations and cannot authorize a policy change."])
    result.drifts = detect_drift(windows, policy_version)
    return result


def deterministic_hypotheses(repo, state):
    state.signals.hypotheses = [h for h in state.signals.hypotheses if h.source == "nemotron"]
    metrics = [m for w in state.signals.windows for m in w.metrics if m.kind == "threshold_override_concentration" and m.eligible]
    policy = next((r for r in state.rulebook.rules if r.id == "rule-age-eligibility"), None)
    if metrics and policy is not None:
        scenario = ScenarioCandidate(title="Investigate inclusive eligibility boundary", category="boundary",
        rule_ids=[policy.id], input={"age": 65, "amount": "10"}, oracle="legacy_observation",
        rationale="Repeated synthetic threshold overrides suggest testing the exact documented boundary; expected output must come from independent policy.")
        hypothesis = SignalHypothesis(id=stable_id("hypothesis", [policy.id, "threshold-overrides"]),
        title="Investigate threshold-related manual overrides",
        description="Repeated synthetic overrides concentrate at the eligibility boundary. The legacy comparison may disagree with the documented inclusive threshold; trials must decide.",
        rule_ids=[policy.id], alternate_explanations=["Operators may be following a different or stale procedure.", "Retry instrumentation or duplicate event emission may inflate the pattern."],
        confidence=0.65, references=policy.references, suggested_scenarios=[scenario], source="deterministic")
        state.signals.hypotheses.append(hypothesis)
        add_conflict(state.rulebook, [policy.id], hypothesis.description, "signal_hypothesis", [hypothesis.id])
    known = {r.id:r for r in state.rulebook.rules}
    for drift in state.signals.drifts:
        if drift.status != "meaningful":
            continue
        linked = [known[r] for r in drift.rule_ids if r in known]
        if not linked:
            continue
        suggestions = []
        if repo.sample_id == "claims_demo":
            suggestions = [ScenarioCandidate(title="Recheck eligibility at active policy boundary", category="boundary",
                rule_ids=[linked[0].id], input={"age":65,"amount":"10"}, oracle="legacy_observation",
                rationale="Targeted re-evaluation of observed drift; independent policy supplies expectations.")]
        elif not repo.trusted:
            suggestions = [ScenarioCandidate(title="Suggested boundary investigation (not executable)", category="boundary",
                rule_ids=[linked[0].id], input={"synthetic_boundary_case":True}, oracle="hypothesis",
                rationale="Human review and a supported trusted adapter are required before any execution.")]
        hypothesis = SignalHypothesis(id=stable_id("hypothesis",[drift.id]),title="Investigate "+drift.metric,
            description="Comparable synthetic windows show "+drift.category+" drift. Competing explanations remain unverified.",
            rule_ids=drift.rule_ids, alternate_explanations=["Non-code workflow changes.","Input mix or instrumentation changes."],
            confidence=.5, references=linked[0].references, suggested_scenarios=suggestions, source="deterministic",
            drift_ids=[drift.id],explanations=explanations_for_drift(drift),policy_version=state.rulebook.policy_version,
            recommendation="Run targeted independent trials; request a human-approved plan only if a discrepancy is supported.")
        state.signals.hypotheses.append(hypothesis)
        add_conflict(state.rulebook,drift.rule_ids,hypothesis.description+" ("+drift.id+")","signal_hypothesis",drift.evidence_ids)
    update_memory_investigations(state)


def update_memory_investigations(state):
    records = {(entry["drift_id"],entry.get("policy_version")):entry for entry in state.rulebook.investigations}
    for drift in state.signals.drifts:
        if drift.status != "meaningful":
            continue
        hypotheses = [h for h in state.signals.hypotheses if drift.id in h.drift_ids]
        records[(drift.id,state.rulebook.policy_version)] = {"drift_id":drift.id,"category":drift.category,"rule_ids":drift.rule_ids,
            "policy_version":state.rulebook.policy_version,
            "hypothesis_ids":[h.id for h in hypotheses],
            "explanations":[e.model_dump() for h in hypotheses for e in h.explanations],
            "status":"hypothesis","uncertainty":"Association is not causation. No automatic policy or code change."}
    state.rulebook.investigations = list(records.values())[-24:]


def merge_interpretation(repo, state, interpretation):
    known = {r.id for r in state.rulebook.rules}
    from .trials import validate_candidate
    accepted = 0
    meaningful = {d.id:d for d in state.signals.drifts if d.status == "meaningful"}
    evidence_catalog = {item for d in meaningful.values() for item in [d.id,*d.evidence_ids]}
    evidence_catalog.update(ref.sha256 for r in state.rulebook.rules for ref in r.references)
    for candidate in interpretation.hypotheses:
        try:
            if not set(candidate.rule_ids).issubset(known):
                raise GhostPatchError("Signal hypothesis cites an unknown rule.")
            refs = [validate_reference(repo, ref) for ref in candidate.references]
            for scenario in candidate.suggested_scenarios:
                validate_candidate(repo, scenario, state.rulebook)
            if candidate.drift_ids and not set(candidate.drift_ids).issubset(meaningful):
                raise GhostPatchError("Model explanation cites an unknown or non-meaningful drift.")
            if any(not set(e.evidence_for+e.evidence_against).issubset(evidence_catalog) for e in candidate.explanations):
                raise GhostPatchError("Model explanation cites unavailable supporting or contrary evidence.")
        except GhostPatchError as exc:
            state.signals.warnings.append("Rejected model signal hypothesis: " + exc.message)
            continue
        hypothesis = SignalHypothesis(id=stable_id("hypothesis", candidate.model_dump()),
            **{k: v for k, v in candidate.model_dump().items() if k not in {"references", "suggested_scenarios", "explanations", "drift_ids"}},
            references=refs, suggested_scenarios=candidate.suggested_scenarios, source="nemotron",
            drift_ids=candidate.drift_ids or list(meaningful),policy_version=state.rulebook.policy_version,
            explanations=candidate.explanations)
        if meaningful and (len(hypothesis.explanations)<2 or all(e.kind=="code" for e in hypothesis.explanations)):
            # Backward-compatible structured versions of the model's actual
            # alternative text, not invented model output or causal evidence.
            for kind,text in [("code",candidate.description),*zip(("workflow","instrumentation"),candidate.alternate_explanations[:2])]:
                hypothesis.explanations.append(CompetingExplanation(id=stable_id("explanation",[hypothesis.id,kind]),kind=kind,
                    description=text[:800],evidence_for=[refs[0].sha256],evidence_against=[],
                    uncertainty="Model hypothesis only; no contrary evidence was supplied and causal verification remains outstanding.",source="nemotron"))
        state.signals.hypotheses.append(hypothesis)
        add_conflict(state.rulebook, hypothesis.rule_ids, hypothesis.description, "signal_hypothesis", [hypothesis.id])
        accepted += 1
    state.signals.model_status = "succeeded" if accepted else "failed"
    state.signals.model_error = None if accepted else "No source-valid model hypotheses were accepted; deterministic signals remain available."
    state.signals.warnings[:] = state.signals.warnings[-50:]
    update_memory_investigations(state)
    return accepted


def metric_evidence_id(window, metric):
    return stable_id("metric", [window.dataset_version, window.software_version,
        window.observation_window.model_dump(mode="json") if window.observation_window else None,
        metric.kind, metric.numerator, metric.denominator, metric.available])


def detect_drift(windows, policy_version=None):
    """Descriptive fixed-threshold drift, never statistical or causal proof."""
    ordered = sorted(windows, key=lambda w: (w.observation_window.start.isoformat() if w.observation_window else "", w.dataset_version))
    findings = []
    for left, right in zip(ordered, ordered[1:]):
        reasons = []
        lw, rw = left.observation_window, right.observation_window
        if not lw or not rw:
            reasons.append("Both explicit observation windows are required.")
        elif lw.end > rw.start or (lw.end-lw.start) != (rw.end-rw.start):
            reasons.append("Windows must be non-overlapping, ordered, and equal in duration.")
        if not left.software_version or not right.software_version:
            reasons.append("Missing or mixed software versions prevent a comparable version analysis.")
        if len(left.workflows)!=1 or left.workflows!=right.workflows:
            reasons.append("A single consistent workflow is required in both comparison cohorts.")
        left_metrics = {m.kind:m for m in left.metrics}
        right_metrics = {m.kind:m for m in right.metrics}
        for kind in ("manual_overrides","retries","abandonment","recurring_errors","return_rate","workflow_completion"):
            before, after = left_metrics[kind], right_metrics[kind]
            issues = list(reasons)
            enough = left.session_count >= 5 and right.session_count >= 5
            enough = enough and next(m.denominator for m in left.metrics if m.kind=="manual_overrides") >= 10
            enough = enough and next(m.denominator for m in right.metrics if m.kind=="manual_overrides") >= 10
            if not before.available or not after.available or before.rate is None or after.rate is None:
                enough = False
                issues.append(before.unavailable_reason or after.unavailable_reason or "Metric unavailable.")
            if kind == "return_rate":
                enough = enough and before.denominator >= 5 and after.denominator >= 5
            delta = after.rate-before.rate if before.rate is not None and after.rate is not None else None
            meaningful = enough and delta is not None and abs(delta) >= 0.20
            status = "not_comparable" if reasons else "meaningful" if meaningful else "insufficient_data"
            issues.append("Fixed 20-percentage-point descriptive threshold; at least 10 submits and 5 sessions per window. Not a significance test or causal claim.")
            if status=="insufficient_data":
                issues.append("Minimum sample or fixed effect-size threshold not met.")
            evidence = [metric_evidence_id(left,before),metric_evidence_id(right,after)]
            findings.append(DriftFinding(id=stable_id("drift", [kind,evidence]),category="user_behavior",metric=kind,
                rule_ids=sorted(set(before.rule_ids+after.rule_ids)),policy_version=policy_version,
                before_dataset=left.dataset_version,after_dataset=right.dataset_version,
                before_version=left.software_version,after_version=right.software_version,
                before_rate=before.rate,after_rate=after.rate,delta=delta,
                before_numerator=before.numerator,after_numerator=after.numerator,
                before_denominator=before.denominator,after_denominator=after.denominator,
                before_window=lw,after_window=rw,status=status,reasons=issues,evidence_ids=evidence))
        before_categories=left.input_categories.get("age_band",{})
        after_categories=right.input_categories.get("age_band",{})
        bn,an=sum(before_categories.values()),sum(after_categories.values())
        variation = sum(abs(before_categories.get(k,0)/bn-after_categories.get(k,0)/an)
                        for k in set(before_categories)|set(after_categories))/2 if bn and an else None
        enough = bn>=10 and an>=10 and before_categories.get("unknown",0)==0 and after_categories.get("unknown",0)==0
        category_reasons=list(reasons)
        if left.reported_policy_versions != right.reported_policy_versions:
            category_reasons.append("Reported policy versions differ; threshold-band category definitions may have changed.")
        status = "not_comparable" if category_reasons else "meaningful" if enough and variation is not None and variation>=.20 else "insufficient_data"
        evidence=[stable_id("categories",[left.dataset_version,before_categories]),stable_id("categories",[right.dataset_version,after_categories])]
        findings.append(DriftFinding(id=stable_id("drift",["age_band",evidence]),category="input_data",metric="age_band_distribution",
            rule_ids=sorted({r for m in left.metrics+right.metrics for r in m.rule_ids}),policy_version=policy_version,
            before_dataset=left.dataset_version,after_dataset=right.dataset_version,before_version=left.software_version,after_version=right.software_version,
            before_rate=None,after_rate=None,delta=variation,before_numerator=before_categories.get("at_threshold",0),
            after_numerator=after_categories.get("at_threshold",0),before_denominator=bn,after_denominator=an,
            before_window=lw,after_window=rw,status=status,reasons=category_reasons+[
                "Total variation distance on allowlisted age-band counts; threshold 0.20, at least 10 categorized submits per window. No raw ages or causal claim."],
            evidence_ids=evidence))
    return findings


def explanations_for_drift(drift, source="deterministic"):
    """Explicit alternatives; lack of contrary evidence is not verification."""
    evidence=list(drift.evidence_ids)
    values=[
        ("code","A boundary or exception-handling rule may no longer match the intended workflow."),
        ("workflow","Operator training, manual procedures, or a changed workflow may explain the behavior without a code defect."),
        ("input_mix","The distribution of approved non-sensitive input categories may have changed."),
        ("instrumentation","Synthetic event instrumentation or retry emission may inflate event-based rates."),
    ]
    return [CompetingExplanation(id=stable_id("explanation",[drift.id,kind]),kind=kind,description=text,
        evidence_for=evidence,evidence_against=[],uncertainty="Aggregates do not identify causation; counter-evidence has not yet been established.",
        source=source) for kind,text in values]
