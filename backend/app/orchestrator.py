import hashlib
import threading
import shutil

from .config import Settings
from .errors import GhostPatchError, redact
from .model import ModelClient
from .patcher import allowed_sources, apply_patch, collect_diffs
from .runner import TestRunner
from .schemas import Event, Job, Plan, RepairResult
from .store import Repository, Store, fingerprints, identifier, now
from .harness import GhostHarness


def model_context(repo: Repository, paths: list[str], objective: str) -> dict:
    files, budget = {}, 20000
    for path in paths:
        content = (repo.working / path).read_bytes().decode("utf-8")
        if len(content) > budget:
            continue
        budget -= len(content)
        files[path] = {"content": content, "original_sha256": hashlib.sha256(content.encode()).hexdigest()}
    return {"objective": objective, "allowed_paths": list(files), "files": files,
            "static_findings": [f.model_dump() for f in repo.analysis.findings if f.file_path in files][:15],
            "validation_policy": "Docker baseline and unchanged tests for built-in sample only." if repo.trusted else "Untrusted: code will not be executed or behavior-verified."}


def compare(baseline, modified) -> list[dict]:
    if not baseline or not modified:
        return []
    ids = sorted(set(baseline.behavior_outputs) | set(modified.behavior_outputs))
    return [{"case_id": key, "status": "matched" if key in baseline.behavior_outputs and key in modified.behavior_outputs and baseline.behavior_outputs[key] == modified.behavior_outputs[key] else "different",
             "baseline": baseline.behavior_outputs.get(key), "modified": modified.behavior_outputs.get(key)} for key in ids]


class Orchestrator:
    def __init__(self, store: Store, model: ModelClient, runner: TestRunner, settings: Settings):
        self.store, self.model, self.runner, self.settings = store, model, runner, settings
        self.model_lock = threading.Lock()
        self.harness = GhostHarness(model, runner, settings, self.model_lock)

    def followup(self, repo, plan=None):
        if not repo.job_id:
            return None
        previous=self.store.job(repo.job_id)
        if previous.status in {"queued","running"} or not previous.completed_at:
            return None
        state=self.harness.ensure(repo)
        return next((item for item in reversed(state.reevaluations)
            if item.status=="completed" and item.approval_state=="human_required" and not item.plan_id
            and item.completed_at and item.completed_at>previous.completed_at
            and (plan is None or plan.trigger_id==item.id)),None)

    def reevaluate(self, repo_id):
        repo=self.store.repository(repo_id)
        approved=[]
        if repo.job_id:
            previous=self.store.job(repo.job_id)
            plan=self.store.plan(previous.plan_id)
            if plan.policy_changes_approved and plan.policy_version==self.harness.ensure(repo).active_policy_version:
                approved=plan.intended_rule_changes
        self.harness.process_pending(repo,approved)

    def create_plan(self, repo: Repository, objective: str, consent: bool, intended_rule_changes=None) -> Plan:
        if not consent:
            raise GhostPatchError("Explicit consent is required before sending relevant source excerpts to NVIDIA.", 403)
        with repo.lock:
            if repo.busy or (repo.job_id and self.followup(repo) is None):
                raise GhostPatchError("Repository is busy or needs a new completed re-evaluation before another plan; otherwise import a fresh copy.", 409)
            repo.busy = True
        try:
            repo.assert_original()
            intended_rule_changes = intended_rule_changes or []
            state = self.harness.ensure(repo)
            self.harness.validate_policy_changes(repo, intended_rule_changes)
            context = model_context(repo, allowed_sources(repo), objective)
            context.update(self.harness.plan_context(repo, intended_rule_changes))
            if not context["files"]:
                raise GhostPatchError("No small, supported non-test Python source files are available for patching.", 422)
            with self.model_lock:
                proposal = self.harness.trace(state, "nemotron.plan", {"paths": context["allowed_paths"], "requested_rule_changes": intended_rule_changes},
                    lambda: self.model.plan(context), lambda value: {"selected_paths": [c.path for c in value.changes]})
            paths = [change.path for change in proposal.changes]
            if len(set(paths)) != len(paths) or any(p not in context["allowed_paths"] for p in paths):
                raise GhostPatchError("Nemotron proposed a path outside the supplied scope; no plan was accepted.", 502)
            plan = Plan(id=identifier(), repository_id=repo.id, proposal=proposal, allowed_paths=paths,
                        intended_rule_changes=intended_rule_changes, harness_revision=state.revision,
                        policy_version=state.rulebook.policy_version,
                        trigger_id=self.followup(repo).id if repo.job_id else next((e.id for e in reversed(state.reevaluations) if e.status=="completed" and e.approval_state=="human_required"),None),
                        source_hashes={p:hashlib.sha256((repo.working/p).read_bytes()).hexdigest() for p in paths})
            with self.store.lock:
                self.store.plans[plan.id] = plan
            return plan
        finally:
            with repo.lock:
                repo.busy = False

    def start(self, plan: Plan) -> tuple[Job, bool]:
        repo = self.store.repository(plan.repository_id)
        with repo.lock, self.store.lock:
            if plan.approval_status != "approved":
                raise GhostPatchError("Approve the exact plan before execution.", 409)
            if plan.intended_rule_changes and not plan.policy_changes_approved:
                raise GhostPatchError("Explicit approval of intended business-rule changes is required.", 409)
            if repo.job_id:
                existing = self.store.job(repo.job_id)
                if existing.plan_id == plan.id:
                    return existing, False
                if self.followup(repo,plan) is None:
                    raise GhostPatchError("A follow-up job requires a fresh completed re-evaluation and new approval.",409)
            if repo.busy:
                raise GhostPatchError("Repository is busy.", 409)
            if plan.harness_revision != self.harness.ensure(repo).revision:
                raise GhostPatchError("Investigation changed after planning; generate and approve a fresh plan.", 409)
            if plan.policy_version!=self.harness.ensure(repo).rulebook.policy_version:
                raise GhostPatchError("Policy version changed after planning; generate a fresh plan.",409)
            if any(hashlib.sha256((repo.working/path).read_bytes()).hexdigest()!=sha for path,sha in plan.source_hashes.items()):
                raise GhostPatchError("Approved source changed after planning.",409)
            job = Job(id=identifier(), repository_id=repo.id, plan_id=plan.id, status="queued")
            directory=repo.root/"jobs"/job.id
            directory.mkdir(parents=True)
            if repo.job_id:
                baseline=directory/"baseline"
                shutil.copytree(repo.working,baseline)
                repo.execution_snapshots[str(baseline.resolve())]=fingerprints(baseline)
                repo.job_baselines[job.id]=baseline
                job.results.baseline_kind="previous_working_copy"
            if plan.trigger_id:
                evaluation=next(e for e in self.harness.ensure(repo).reevaluations if e.id==plan.trigger_id)
                evaluation.plan_id=plan.id
            self.store.jobs[job.id] = job
            repo.busy, repo.job_id = True, job.id
            return job, True

    def event(self, job: Job, phase: str, status: str, message: str) -> None:
        with self.store.lock:
            job.events.append(Event(id=identifier(), timestamp=now(), phase=phase, status=status,
                                    message=redact(message, self.settings.api_key)))

    def execute(self, job_id: str) -> None:
        job = self.store.job(job_id)
        repo = self.store.repository(job.repository_id)
        plan = self.store.plan(job.plan_id)
        state = self.harness.ensure(repo)
        approved_rules = plan.intended_rule_changes if plan.policy_changes_approved else []
        report = None
        baseline_source=repo.job_baselines.get(job.id,repo.original)

        def context():
            value = model_context(repo, plan.allowed_paths, plan.proposal.objective)
            value.update(self.harness.plan_context(repo, approved_rules, approved=True))
            return value

        def assess():
            return self.harness.report(repo, job.results.baseline, job.results.modified, approved_rules)
        try:
            with self.store.lock:
                job.status, job.started_at = "running", now()
            if repo.trusted:
                self.event(job, "baseline", "started", "Running unchanged baseline tests in the trusted Docker sandbox.")
                job.results.baseline = self.harness.run(repo, baseline_source)
                state.baseline = job.results.baseline
                baseline_report = self.harness.record_conflicts(repo, state, job.results.baseline)
                self.event(job, "baseline", "succeeded" if job.results.baseline.status == "passed" else "warning",
                           "Baseline pytest: " + job.results.baseline.status + "; independent policy divergences: " + str(baseline_report.classifications["unexpected_divergence"]) + (" — " + job.results.baseline.reason if job.results.baseline.reason else ""))
            else:
                warning = "Verification skipped: uploaded/cloned source is untrusted and cannot execute in this MVP."
                job.results.warnings.append(warning)
                self.event(job, "validation", "warning", warning)
            self.event(job, "patch", "started", "Requesting a bounded patch from Nemotron for the approved file.")
            with self.model_lock:
                proposal = self.harness.trace(state, "nemotron.patch", {"paths": plan.allowed_paths, "approved_rule_changes": approved_rules},
                    lambda: self.model.patch(context(), plan.proposal), lambda value: {"proposed_paths": [e.path for e in value.edits]})
            self.harness.trace(state, "patcher.apply", {"approved_paths": plan.allowed_paths},
                lambda: apply_patch(repo, proposal, plan.allowed_paths), lambda value: {"changed_paths": [e.path for e in proposal.edits]})
            self.event(job, "patch", "succeeded", "Applied a syntax-checked, hash-matched patch to the isolated working copy.")
            if repo.trusted and job.results.baseline and job.results.baseline.status == "passed":
                job.results.modified = self.harness.run(repo, repo.working)
                job.results.initial_modified = job.results.modified.model_copy(deep=True)
                job.results.behavior_comparison = compare(job.results.baseline, job.results.modified)
                report = assess()
                self.event(job, "validation", "succeeded" if job.results.modified.status == "passed" and report.status == "passed" else "warning", "Post-change pytest: " + job.results.modified.status + "; Ghost Trials: " + report.status)
                for attempt in range(1, 3):
                    regressed = job.results.modified.status == "failed" or any(c["status"] == "different" for c in job.results.behavior_comparison) or report.status == "failed"
                    if not regressed:
                        break
                    from .trials import outcome_equal
                    actionable = [r for r in report.scenario_results if r.classification in {"unexpected_divergence","execution_error"}
                        and not (r.scenario.oracle=="approved_policy" and not set(r.scenario.rule_ids)&set(approved_rules)
                                 and r.baseline and r.modified and outcome_equal(r.baseline.outcome,r.modified.outcome))]
                    if job.results.modified.status=="passed" and not actionable and all(c["status"]=="matched" for c in job.results.behavior_comparison):
                        job.results.warnings.append("An unchanged pre-existing policy mismatch needs explicit semantic approval; no unauthorized repair was attempted.")
                        break
                    self.event(job, "repair", "started", f"Validation detected a regression; requesting repair {attempt} of 2.")
                    try:
                        failure = {"tests": {"status": job.results.modified.status, "stdout": job.results.modified.stdout[-3000:], "stderr": job.results.modified.stderr[-1000:]},
                            "comparisons": job.results.behavior_comparison[:5],
                            "trial_divergences": [{"scenario_id": r.scenario.id, "input": r.scenario.input, "rule_ids": r.scenario.rule_ids,
                                "oracle": r.scenario.oracle, "expected": r.expected.model_dump() if r.expected else None,
                                "actual": r.modified.outcome.model_dump() if r.modified else None, "reason": r.reason}
                                for r in actionable][:6]}
                        with self.model_lock:
                            repair = self.harness.trace(state, "nemotron.repair", {"attempt": attempt, "failed_scenarios": len(failure["trial_divergences"])},
                                lambda: self.model.patch(context(), plan.proposal, failure), lambda value: {"proposed_paths": [e.path for e in value.edits]})
                        self.harness.trace(state, "patcher.repair", {"attempt": attempt, "approved_paths": plan.allowed_paths},
                            lambda: apply_patch(repo, repair, plan.allowed_paths), lambda value: {"changed_paths": [e.path for e in repair.edits]})
                        validation = self.harness.run(repo, repo.working)
                        job.results.repairs.append(RepairResult(attempt=attempt, summary=redact(repair.summary, self.settings.api_key), validation=validation))
                        job.results.modified = validation
                        job.results.behavior_comparison = compare(job.results.baseline, validation)
                        report = assess()
                        self.event(job, "repair", "succeeded" if validation.status == "passed" and report.status == "passed" else "warning", f"Repair {attempt}: pytest {validation.status}; Ghost Trials {report.status}; inspect evidence.")
                    except GhostPatchError as exc:
                        job.results.repairs.append(RepairResult(attempt=attempt, summary="Repair was not accepted.", error=exc.message))
                        self.event(job, "repair", "failed", exc.message)
                modified = job.results.modified
                if modified.status == "passed" and job.results.behavior_comparison and all(c["status"] == "matched" for c in job.results.behavior_comparison) and report.status == "passed":
                    job.results.verification = "passed"
                    job.status = "succeeded"
                elif modified.status == "failed" or any(c["status"] == "different" for c in job.results.behavior_comparison) or report.status == "failed":
                    job.results.verification, job.status = "failed", "needs_review"
                else:
                    job.status = "needs_review"
            else:
                job.status = "needs_review"
                if repo.trusted:
                    job.results.warnings.append("A passing baseline was unavailable; post-change behavior is not verified.")
            job.results.warnings.append("Observed tests and fixture matches do not prove general correctness, semantic equivalence, or security.")
        except Exception as exc:
            message = exc.message if isinstance(exc, GhostPatchError) else "Operation failed unexpectedly; inspect local service configuration and retry with a fresh snapshot."
            job.error, job.status = redact(message, self.settings.api_key), "failed"
            self.event(job, "execution", "failed", message)
        finally:
            try:
                job.results.diffs = collect_diffs(repo,baseline_source)
                patch = "".join(d["unified_diff"] for d in job.results.diffs)
                directory=repo.root/"jobs"/job.id
                (directory / "result.patch").write_text(patch, encoding="utf-8", newline="")
                report = self.harness.report(repo, job.results.baseline, job.results.modified, approved_rules, job.results.diffs)
                job.results.behavior_report = report
                job.results.rulebook, job.results.signals = report.rulebook, report.signals
                report.test_evidence["baseline_kind"]=job.results.baseline_kind
                (directory / "evidence.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
            except Exception:
                job.error, job.status = "Could not produce trustworthy diff evidence.", "failed"
            self.event(job, "complete", "info", f"Job finished: {job.status}; verification: {job.results.verification}.")
            with repo.lock, self.store.lock:
                job.completed_at, repo.busy = now(), False
