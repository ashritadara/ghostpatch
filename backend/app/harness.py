"""One investigator coordinating Memory, Trials and Signals around existing tools."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import time

from .errors import GhostPatchError, redact
from .harness_schemas import ObservationWindow, Reevaluation, SignalsReport, ToolInvocation
from .memory import GhostMemory, add_conflict, approve_policy_version, policy_fixture, stable_id, transition
from .signals import aggregate, deterministic_hypotheses, ingest, merge_interpretation, parse_events
from .store import identifier, now
from .trials import add_candidates, initial_scenarios, preservation_report


@dataclass
class InvestigationState:
    rulebook: object
    scenarios: list
    signals: SignalsReport = field(default_factory=SignalsReport)
    events: dict = field(default_factory=dict, repr=False)
    revision: int = 1
    trace: list = field(default_factory=list)
    baseline: object = None
    report: object = None
    trials_model_attempted: bool = False
    observation_windows: dict = field(default_factory=dict)
    active_policy_version: str = "1.0"
    policy_history: list = field(default_factory=list)
    reevaluations: list = field(default_factory=list)
    evaluation_reports: dict = field(default_factory=dict)
    prepare_cache: str | None = None


class GhostHarness:
    def __init__(self, model, runner, settings, model_lock):
        self.model, self.runner, self.settings, self.model_lock = model, runner, settings, model_lock
        self.memory = GhostMemory()

    @contextmanager
    def operation(self, repo, allow_completed=False):
        with repo.lock:
            if repo.busy or (repo.job_id and not allow_completed):
                raise GhostPatchError("Snapshot is busy or already executed. Load a fresh snapshot for another investigation.", 409)
            repo.busy = True
        try:
            yield
        finally:
            with repo.lock:
                repo.busy = False

    def ensure(self, repo):
        with repo.lock:
            if repo.investigation is None:
                book = self.memory.deterministic(repo)
                repo.investigation = InvestigationState(book, initial_scenarios(repo, book))
                self.trace(repo.investigation, "source_map_and_memory", {"file_count": len(repo.hashes)},
                           lambda: book, lambda value: {"candidate_rules": len(value.rules), "conflicts": len(value.conflicts)})
            return repo.investigation

    def trace(self, state, tool, inputs, function, summarize=None):
        start, stamp = time.monotonic(), now()
        output, error, status = {}, None, "succeeded"
        evidence_ids = []
        try:
            value = function()
            output = summarize(value) if summarize else {"completed": True}
            if hasattr(value, "trial_outputs"):
                evidence_ids = [item.scenario_id for item in value.trial_outputs]
            elif hasattr(value, "edits"):
                evidence_ids = [edit.original_sha256 for edit in value.edits]
            elif hasattr(value, "rules"):
                evidence_ids = [ref.sha256 for rule in value.rules for ref in getattr(rule, "references", []) if hasattr(ref, "sha256")][:24]
            elif "approved_paths" in inputs:
                evidence_ids = list(inputs["approved_paths"])
            return value
        except Exception as exc:
            status = "failed"
            error = redact(exc.message if isinstance(exc, GhostPatchError) else "Tool failed; no success evidence was inferred.", self.settings.api_key)
            raise
        finally:
            state.trace.append(ToolInvocation(id=identifier(), tool=tool, started_at=stamp, completed_at=now(),
                duration_ms=int((time.monotonic() - start) * 1000), status=status,
                input_summary=inputs, output_summary=output, error=error, evidence_ids=evidence_ids))
            state.trace[:] = state.trace[-100:]

    def model_call(self, state, tool, inputs, function, summarize):
        with self.model_lock:
            return self.trace(state, tool, inputs, function, summarize)

    def extract(self, repo, consent=False, use_model=False):
        state = self.ensure(repo)
        if not use_model:
            return state
        if not consent:
            raise GhostPatchError("Consent is required for model-assisted rule extraction.", 403)
        if state.rulebook.model_status == "succeeded":
            return state
        if not hasattr(self.model, "extract_rules"):
            state.rulebook.warnings.append("Injected client does not support model-assisted rule extraction.")
            return state
        try:
            context = self.memory.context(repo, state.rulebook)
            result = self.model_call(state, "nemotron.extract_rules", {"files": list(context["files"])},
                lambda: self.model.extract_rules(context), lambda value: {"proposed_rules": len(value.rules)})
            added = self.memory.merge_model(repo, state.rulebook, result)
            state.trace[-1].output_summary["accepted_rules"] = added
            state.trace[-1].evidence_ids = [r.id for r in state.rulebook.rules if r.origin == "nemotron"]
        except GhostPatchError as exc:
            state.rulebook.model_status, state.rulebook.model_error = "failed", exc.message
            state.rulebook.warnings.append("Model rule extraction unavailable; deterministic candidates remain hypotheses.")
        state.revision += 1
        return state

    def import_fixture(self, repo, dataset):
        if not repo.trusted or repo.sample_id != "claims_demo":
            raise GhostPatchError("Synthetic signal fixtures exist only for the pinned claims demo.", 422)
        repo.assert_original()
        state = self.ensure(repo)
        events = parse_events((repo.original / ("signals_" + dataset + ".jsonl")).read_bytes())
        windows = json.loads((repo.original / "signals_windows.json").read_text())
        window = ObservationWindow.model_validate(windows[dataset + "-v1"])
        revision = state.revision
        added = self.trace(state, "signals.ingest_fixture", {"dataset_version": dataset + "-v1", "synthetic": True},
            lambda: ingest(state, events, dataset + "-v1", window), lambda value: {"new_events": value})
        deterministic_hypotheses(repo, state)
        if state.revision != revision:
            state.prepare_cache = None
            self.enqueue(repo)
        return added

    def interpret(self, repo, consent=False, use_model=False):
        state = self.ensure(repo)
        deterministic_hypotheses(repo, state)
        if not state.events or not use_model:
            return state
        if not consent:
            raise GhostPatchError("Consent is required for model interpretation of aggregated signals.", 403)
        if state.signals.model_status == "succeeded":
            return state
        if not hasattr(self.model, "investigate_signals"):
            return state
        try:
            source = self.memory.context(repo, state.rulebook)
            # Relevant code and policy lines only; no raw session/event rows.
            source["files"] = {path:value for path,value in source["files"].items() if path in {"claims.py", "reports.py", "POLICY.md"}}
            references = [ref for rule in state.rulebook.rules for ref in rule.references
                          if ref.file_path in {"claims.py", "POLICY.md"}]
            references.sort(key=lambda ref: ("age > 65" not in ref.quote, ref.file_path != "POLICY.md", ref.line_start))
            meaningful = [d for d in state.signals.drifts if d.status == "meaningful"]
            context = {"aggregated_signals": {"windows": [{"dataset_version":w.dataset_version,
                        "software_version":w.software_version,"observation_window":w.observation_window.model_dump(mode="json") if w.observation_window else None,
                        "event_count":w.event_count,"session_count":w.session_count,"user_count":w.user_count,
                        "metrics":[{"kind":m.kind,"numerator":m.numerator,"denominator":m.denominator,"rate":m.rate,"available":m.available} for m in w.metrics],
                        "input_categories":w.input_categories} for w in state.signals.windows],
                        "drifts":[d.model_dump(mode="json") for d in meaningful]},
                       "evidence_catalog":sorted({e for d in meaningful for e in [d.id,*d.evidence_ids]}|{ref.sha256 for rule in state.rulebook.rules for ref in rule.references}),
                       "reference_options":[{k:v for k,v in ref.model_dump().items() if k in {"file_path","function","line_start","line_end","quote"}} for ref in references[:4]],
                       "source_evidence": source}
            if repo.job_id:
                import difflib
                candidate_changes = {}
                for path in ("claims.py", "reports.py"):
                    if path in repo.hashes:
                        original=(repo.original/path).read_text().splitlines()
                        current=(repo.working/path).read_text().splitlines()
                        candidate_changes[path]="\n".join(difflib.unified_diff(original,current))[:6000]
                context["current_candidate_changes"]=candidate_changes
            for grounding_attempt in range(2):
                result = self.model_call(state, "nemotron.investigate_signals" if grounding_attempt==0 else "nemotron.correct_signal_references",
                    {"dataset_versions": [w.dataset_version for w in state.signals.windows], "raw_events_transmitted": 0,"grounding_attempt":grounding_attempt+1},
                    lambda: self.model.investigate_signals(context), lambda value: {"proposed_hypotheses": len(value.hypotheses)})
                accepted = merge_interpretation(repo, state, result)
                state.trace[-1].output_summary["accepted_hypotheses"] = accepted
                state.trace[-1].evidence_ids = [h.id for h in state.signals.hypotheses if h.source == "nemotron"]
                if accepted:
                    break
                state.trace[-1].status="failed"
                state.trace[-1].error=state.signals.model_error
                context["validation_feedback"]=state.signals.warnings[-3:]
                context["correction_instruction"]="Copy one reference_options object exactly, use known rule/drift IDs, and use only exact evidence_catalog IDs. Empty evidence lists are required when no supported evidence exists."
        except GhostPatchError as exc:
            state.signals.model_status, state.signals.model_error = "failed", exc.message
            state.signals.warnings.append("Model interpretation failed; deterministic signals remain available.")
        state.revision += 1
        return state

    def generate_trials(self, repo, consent=False, use_model=False):
        state = self.ensure(repo)
        for hypothesis in state.signals.hypotheses:
            add_candidates(repo, state.rulebook, state.scenarios, hypothesis.suggested_scenarios, "signal")
        if use_model and not state.trials_model_attempted and hasattr(self.model, "propose_trials"):
            if not consent:
                raise GhostPatchError("Consent is required for model-assisted scenario planning.", 403)
            state.trials_model_attempted = True
            context = {
                "rules": [{"id": r.id, "title": r.title, "kind": r.kind, "description": r.description,
                           "reference": r.references[0].model_dump()} for r in state.rulebook.rules][:24],
                "existing_scenarios": [{"input": s.input, "rule_ids": s.rule_ids, "category": s.category} for s in state.scenarios],
                "adapter": "claims: one object with age integer -1..120, amount decimal string, optional duplicate boolean" if repo.sample_id == "claims_demo" else "reports: bounded list of department/amount string objects",
                "allowed_invariants": ["input_unchanged", "repeatability"],
            }
            try:
                result = self.model_call(state, "nemotron.propose_trials", {"rule_count": len(state.rulebook.rules)},
                    lambda: self.model.propose_trials(context), lambda value: {"proposed_scenarios": len(value.scenarios)})
                added = add_candidates(repo, state.rulebook, state.scenarios, result.scenarios)
                state.trace[-1].output_summary["accepted_scenarios"] = added
                state.trace[-1].evidence_ids = [s.id for s in state.scenarios if s.origin == "nemotron"]
            except GhostPatchError as exc:
                state.rulebook.warnings.append("Model scenario generation failed: " + exc.message)
        state.revision += 1
        return state

    def run(self, repo, source):
        state = self.ensure(repo)
        if not repo.trusted:
            raise GhostPatchError("Uploaded/cloned repositories cannot execute Ghost Trials.", 403)
        with_trials = bool(state.scenarios and hasattr(self.runner, "run_with_trials"))
        return self.trace(state, "docker.pytest_and_trials",
            {"snapshot": "original" if source == repo.original else "working" if source == repo.working else "frozen_pre_edit", "scenario_ids": [s.id for s in state.scenarios], "trusted_sample": repo.sample_id},
            lambda: self.runner.run_with_trials(repo, source, state.scenarios) if with_trials else self.runner.run(repo, source),
            lambda run: {"pytest_status": run.status, "exit_code": run.exit_code,
                         "counts": run.counts.model_dump() if run.counts else None, "executed_scenarios": len(run.trial_outputs)})

    def record_conflicts(self, repo, state, baseline):
        report = preservation_report(repo, state, baseline)
        for result in report.scenario_results:
            if result.scenario.oracle != "approved_policy" or result.classification not in {"unexpected_divergence", "execution_error"}:
                continue
            linked = list(result.scenario.rule_ids)
            if "rule-age-eligibility" in linked:
                linked += [r.id for r in state.rulebook.rules if r.kind == "observed_implementation"
                           and any("age > 65" in ref.quote for ref in r.references)]
            add_conflict(state.rulebook, linked,
                "Independent policy mismatch observed by " + result.scenario.id + ": " + result.reason,
                "trial_evidence", [result.scenario.id], observed=True)
        return preservation_report(repo, state, baseline)

    def baseline(self, repo):
        state = self.ensure(repo)
        if not repo.trusted:
            state.rulebook.warnings.append("Trial execution skipped for untrusted source.")
            state.report = preservation_report(repo, state, None)
            return state
        state.baseline = self.run(repo, repo.original)
        state.report = self.record_conflicts(repo, state, state.baseline)
        state.revision += 1
        return state

    def prepare(self, repo, consent=False, use_model=True, signals_dataset="both"):
        state = self.extract(repo, consent, use_model)
        if repo.sample_id == "claims_demo" and signals_dataset != "none":
            for dataset in (["before", "after"] if signals_dataset == "both" else [signals_dataset]):
                self.import_fixture(repo, dataset)
        signature = stable_id("prepare", [[w.model_dump(mode="json") for w in state.signals.windows],state.active_policy_version,use_model,signals_dataset])
        if state.prepare_cache == signature:
            return state
        self.interpret(repo, consent, use_model)
        self.generate_trials(repo, consent, use_model)
        self.baseline(repo)
        pending = [item for item in state.reevaluations if item.status == "queued"]
        for item in pending:
            item.allow_model = consent and use_model
            self.evaluate(repo, item, prepared=True)
        state.prepare_cache = signature
        return state

    def validate_policy_changes(self, repo, ids):
        state = self.ensure(repo)
        fixture = policy_fixture(repo)
        known = {r["id"] for r in fixture["rules"]} if fixture else set()
        if len(ids) != len(set(ids)) or not set(ids).issubset(known):
            raise GhostPatchError("Semantic changes require a known independent trusted policy rule.", 403)
        if ids and (not state.baseline or state.baseline.status != "passed"):
            raise GhostPatchError("Run a passing pytest baseline and Ghost Trials before proposing semantic changes.", 409)
        if ids and not all(any(rule in outcome.scenario.rule_ids and outcome.classification == "unexpected_divergence"
                               for outcome in state.report.scenario_results) for rule in ids):
            raise GhostPatchError("A requested semantic change lacks an independently observed policy mismatch.", 409)

    def plan_context(self, repo, ids, approved=False):
        state = self.ensure(repo)
        fixture = policy_fixture(repo)
        changes = []
        if fixture:
            for rule in fixture["rules"]:
                if rule["id"] in ids:
                    changes.append({"rule_id": rule["id"], "description": rule["description"],
                        "expected_examples": [{"input": s["input"], "expected": s["expected"]} for s in fixture["scenarios"] if rule["id"] in s["rule_ids"]]})
        return {
            "approved_policy_changes" if approved else "requested_policy_changes": changes,
            "memory": [{"id": r.id, "title": r.title, "status": r.status, "kind": r.kind} for r in state.rulebook.rules][:24],
            "signal_hypotheses": [{"title": h.title, "description": h.description, "rule_ids": h.rule_ids, "status": "hypothesis"} for h in state.signals.hypotheses][:4],
            "independent_trial_failures": [{"scenario_id": r.scenario.id, "input": r.scenario.input, "expected": r.expected.model_dump() if r.expected else None,
                                           "actual": r.modified.outcome.model_dump() if r.modified else r.baseline.outcome.model_dump() if r.baseline else None, "reason": r.reason}
                                          for r in (state.report.scenario_results if state.report else []) if r.classification in {"unexpected_divergence", "execution_error"}][:6],
        }

    def report(self, repo, baseline, modified=None, approved_rule_changes=(), diffs=None):
        state = self.ensure(repo)
        report = preservation_report(repo, state, baseline, modified, approved_rule_changes, diffs)
        if report.status == "passed" and approved_rule_changes:
            related = {rule_id for c in state.rulebook.conflicts if c.basis == "trial_evidence" and set(c.rule_ids) & set(approved_rule_changes) for rule_id in c.rule_ids}
            for rule in state.rulebook.rules:
                if rule.id in related and rule.kind == "observed_implementation" and rule.status == "conflicted":
                    transition(rule, "superseded", "Explicitly approved policy correction verified by independent trials.", [r.scenario.id for r in report.scenario_results if r.classification == "intended_change"])
                    state.rulebook.version += 1
            report.rulebook = state.rulebook.model_copy(deep=True)
        state.report = report
        return report

    def view(self, repo):
        state = self.ensure(repo)
        state.signals.reevaluations = state.reevaluations
        return {"revision": state.revision, "rulebook": state.rulebook, "signals": state.signals,
                "scenarios": state.scenarios, "baseline": state.baseline, "report": state.report, "tool_invocations": state.trace,
                "reevaluations":state.reevaluations,"policy_history":state.policy_history}


    def enqueue(self, repo, trigger="signal_drift", allow_model=False, evidence=None):
        state=self.ensure(repo)
        meaningful=[d for d in state.signals.drifts if d.status=="meaningful"]
        if trigger=="signal_drift" and not meaningful:
            return None
        digest=stable_id("evidence",[[w.model_dump(mode="json") for w in state.signals.windows],
            state.active_policy_version,state.rulebook.source_digest,evidence])
        key=stable_id("reevaluation",[trigger,digest])
        existing=next((item for item in state.reevaluations if item.id==key),None)
        if existing:
            if existing.status=="queued" and allow_model:
                existing.allow_model=True
            return existing
        if len(state.reevaluations)>=4:
            if "Re-evaluation budget exhausted (4 per snapshot)." not in state.signals.warnings:
                state.signals.warnings.append("Re-evaluation budget exhausted (4 per snapshot).")
            return None
        ids=sorted({rule for d in meaningful for rule in d.rule_ids})
        if trigger=="approved_policy_update":
            ids=["rule-age-eligibility"]
        item=Reevaluation(id=key,trigger=trigger,evidence_digest=digest,
            drift_ids=[d.id for d in meaningful],rule_ids=ids,policy_version=state.rulebook.policy_version,
            source_evidence=sorted({e for d in meaningful for e in d.evidence_ids}|set(evidence or [])),
            created_at=now(),allow_model=allow_model)
        state.reevaluations.append(item)
        state.signals.reevaluations=state.reevaluations
        state.trials_model_attempted=False
        self.trace(state,"trials.enqueue",{"trigger":trigger,"evidence_digest":digest},
            lambda:item,lambda value:{"reevaluation_id":value.id,"rule_ids":value.rule_ids,"edits_authorized":False})
        return item

    def ingest_events(self, repo, events, dataset_version, observation_window=None, consent=False):
        state=self.ensure(repo)
        revision=state.revision
        added=self.trace(state,"signals.ingest_api",{"dataset_version":dataset_version,"synthetic":True},
            lambda:ingest(state,events,dataset_version,observation_window),lambda count:{"new_events":count})
        deterministic_hypotheses(repo,state)
        if state.revision != revision:
            state.prepare_cache=None
            self.enqueue(repo,allow_model=consent)
        return added

    def activate_policy(self, repo, version, approved_rule_ids, consent=False):
        state=self.ensure(repo)
        if version!=state.active_policy_version and len(state.reevaluations)>=4:
            raise GhostPatchError("Re-evaluation budget exhausted; use a fresh local snapshot.",429)
        changed=self.trace(state,"memory.approve_policy_version",{"version":version,"approved_rule_ids":approved_rule_ids},
            lambda:approve_policy_version(repo,state,version,approved_rule_ids),lambda result:{"changed":result})
        if changed:
            state.prepare_cache=None
            state.baseline,state.report=None,None
            state.signals=aggregate(state.events,state.observation_windows,state.active_policy_version)
            deterministic_hypotheses(repo,state)
            self.enqueue(repo,"approved_policy_update",consent,[state.policy_history[-1]["evidence_ids"][0]])
        return changed

    def evaluate(self, repo, item, prepared=False, approved_rule_changes=()):
        state=self.ensure(repo)
        if item.status!="queued" or item.attempts:
            return item
        item.status,item.started_at,item.attempts="running",now(),1
        start_index=len(state.trace)
        try:
            if not prepared:
                self.interpret(repo,item.allow_model,item.allow_model)
                self.generate_trials(repo,item.allow_model,item.allow_model)
            fixture=policy_fixture(repo)
            if repo.sample_id=="claims_demo" and fixture:
                from .harness_schemas import ScenarioCandidate
                threshold=fixture["parameters"]["minimum_age"]
                candidates=[ScenarioCandidate(title="Active policy boundary re-evaluation",category="boundary",
                    rule_ids=["rule-age-eligibility"],input={"age":age,"amount":"10"},
                    oracle="legacy_observation",rationale="Targeted independent trial after "+item.trigger)
                    for age in (threshold-1,threshold)]
                add_candidates(repo,state.rulebook,state.scenarios,candidates,"signal")
            for scenario in state.scenarios:
                if set(scenario.rule_ids)&set(item.rule_ids) and item.id not in scenario.trigger_ids:
                    scenario.trigger_ids.append(item.id)
            item.scenario_ids=[s.id for s in state.scenarios if item.id in s.trigger_ids]
            if not repo.trusted:
                item.status="suggested_only"
                item.candidate_kind="not_executed_untrusted"
                state.report=preservation_report(repo,state,None)
            else:
                if not prepared or not state.baseline:
                    self.baseline(repo)
                candidate=self.run(repo,repo.working)
                item.candidate_kind="existing_working_copy" if repo.job_id else "unchanged_working_copy"
                state.report=self.report(repo,state.baseline,candidate,approved_rule_changes)
                item.status="completed"
            item.report_status=state.report.status
            item.classifications=dict(state.report.classifications)
            for outcome in state.report.scenario_results:
                if outcome.scenario.oracle=="approved_policy" and outcome.classification in {"unexpected_divergence","execution_error"}:
                    add_conflict(state.rulebook,outcome.scenario.rule_ids,
                        "Re-evaluation "+item.id+" found a candidate mismatch under policy "+str(state.rulebook.policy_version)+" in "+outcome.scenario.id,
                        "trial_evidence",[item.id,outcome.scenario.id],observed=True)
            item.approval_state="no_action" if state.report.status=="passed" else "human_required"
            proposed=next((h.recommendation for h in state.signals.hypotheses if h.source=="nemotron" and h.recommendation),None)
            item.recommended_action=("Independent trials require human review of a bounded action under the active policy. No code changes or repairs are authorized. " + ("Model hypothesis recommendation: "+proposed if proposed else "Generate a fresh plan only for independently evidenced discrepancies.")) if item.approval_state=="human_required" else "Targeted trials did not reproduce a policy discrepancy. No code change is authorized; investigate non-code explanations."
            # Attach independently observed counter-evidence without claiming causation.
            for investigation in state.rulebook.investigations:
                if investigation["drift_id"] not in item.drift_ids:
                    continue
                investigation["trial_evidence_ids"]=item.scenario_ids
                investigation["trial_result"]=state.report.status
                for explanation in investigation["explanations"]:
                    if explanation["kind"]=="code" and state.report.status=="passed":
                        explanation["evidence_against"]=item.scenario_ids[:8]
                        explanation["uncertainty"]="No discrepancy was reproduced by these bounded trials; this does not rule out all code defects."
            state.report.rulebook=state.rulebook.model_copy(deep=True)
        except Exception as exc:
            item.status="failed"
            item.error=redact(exc.message if isinstance(exc,GhostPatchError) else "Re-evaluation failed; no success or edit authorization was inferred.",self.settings.api_key)
            item.approval_state="human_required"
        finally:
            item.completed_at=now()
            item.tool_ids=[t.id for t in state.trace[start_index:]]
            state.revision+=1
            state.signals.reevaluations=state.reevaluations
            if state.report and item.status in {"completed","suggested_only"}:
                state.report.signals=state.signals.model_copy(deep=True)
                state.report.reevaluations=[e.model_copy(deep=True) for e in state.reevaluations]
                state.evaluation_reports[item.id]=state.report.model_copy(deep=True)
        return item

    def reserve_reevaluation(self, repo):
        with repo.lock:
            state=self.ensure(repo)
            if repo.busy or not any(e.status=="queued" for e in state.reevaluations):
                return False
            repo.busy=True
            return True

    def process_pending(self, repo, approved_rule_changes=()):
        try:
            state=self.ensure(repo)
            for item in list(state.reevaluations):
                if item.status=="queued":
                    self.evaluate(repo,item,approved_rule_changes=approved_rule_changes)
        finally:
            with repo.lock:
                repo.busy=False
