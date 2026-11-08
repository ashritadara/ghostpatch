from contextlib import asynccontextmanager
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .body_limit import BodyLimitMiddleware
from .errors import GhostPatchError
from .loader import RepositoryLoader
from .model import NemotronClient
from .orchestrator import Orchestrator
from .runner import DockerRunner
from .schemas import ConnectivityRequest, ExecuteRequest, GitImportRequest, Job, Plan, PlanRequest, RepositorySummary
from .store import Store
from .harness_schemas import InvestigationRequest, SignalsRequest, SignalFixtureRequest, TrialsRequest, PolicyVersionRequest, ReevaluationRequest
from .signals import deterministic_hypotheses, ingest


def create_app(settings: Settings | None = None, *, model=None, runner=None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings)
    loader = RepositoryLoader(store, settings)
    model = model or NemotronClient(settings)
    runner = runner or DockerRunner(settings)
    orchestrator = Orchestrator(store, model, runner, settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        store.close()

    app = FastAPI(title="GhostPatch", version="0.3.0", lifespan=lifespan)
    app.state.store, app.state.loader, app.state.orchestrator = store, loader, orchestrator
    harness = orchestrator.harness
    app.state.harness = harness
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])
    app.add_middleware(BodyLimitMiddleware, limit=settings.max_archive_bytes + 1024 * 1024)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in {"POST", "DELETE"} and origin and origin not in settings.allowed_origins:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        length = request.headers.get("content-length")
        try:
            if length and int(length) > settings.max_archive_bytes + 1024 * 1024:
                return JSONResponse({"detail": "Request exceeds the upload limit."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
        return await call_next(request)

    @app.exception_handler(GhostPatchError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo request input, which may contain source or credentials.
        return JSONResponse({"detail": "Invalid request payload.", "errors": [{"loc": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "nvidia_configured": bool(settings.api_key and settings.model),
                "features": ["ghost_memory", "ghost_trials", "ghost_signals"],
                "model": settings.model or None, "docker": runner.availability() if hasattr(runner, "availability") else {"available": False, "reason": "Injected test runner."},
                "execution_policy": "Built-in allowlisted sample only; uploads and clones never execute.",
                "persistence": "In-memory IDs; owned workspaces expire after six hours or clean shutdown."}

    @app.post("/api/model/check")
    def model_check(body: ConnectivityRequest):
        with orchestrator.model_lock:
            return model.connectivity()

    @app.post("/api/repositories/upload", response_model=RepositorySummary, status_code=201)
    async def upload(file: UploadFile = File(...)):
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise GhostPatchError("Select a .zip archive.")
        data = bytearray()
        try:
            while chunk := await file.read(65536):
                data.extend(chunk)
                if len(data) > settings.max_archive_bytes:
                    raise GhostPatchError("ZIP exceeds the 20 MiB compressed limit.", 413)
            # Bounded parsing is CPU/file work, not execution of imported code.
            from starlette.concurrency import run_in_threadpool
            repo = await run_in_threadpool(loader.zip, bytes(data), file.filename)
            return repo.summary()
        finally:
            await file.close()

    @app.post("/api/repositories/import-git", response_model=RepositorySummary, status_code=201)
    def import_git(body: GitImportRequest):
        return loader.git(body.url).summary()

    @app.post("/api/repositories/sample", response_model=RepositorySummary, status_code=201)
    def sample(sample_id: Literal["legacy_reports", "claims_demo"] = "legacy_reports"):
        return loader.sample(sample_id).summary()

    @app.get("/api/repositories/{repo_id}", response_model=RepositorySummary)
    def repository(repo_id: str):
        return store.repository(repo_id).summary()

    @app.get("/api/repositories/{repo_id}/diagnosis")
    def diagnosis(repo_id: str):
        return store.repository(repo_id).analysis

    @app.delete("/api/repositories/{repo_id}", status_code=204)
    def remove(repo_id: str):
        store.remove(store.repository(repo_id))

    @app.post("/api/repositories/{repo_id}/plans", response_model=Plan)
    def plans(repo_id: str, body: PlanRequest):
        return orchestrator.create_plan(store.repository(repo_id), body.objective, body.consent_to_model, body.intended_rule_changes)

    @app.get("/api/repositories/{repo_id}/investigation")
    def investigation(repo_id: str):
        return harness.view(store.repository(repo_id))

    @app.post("/api/repositories/{repo_id}/investigate")
    def investigate(repo_id: str, body: InvestigationRequest):
        repo = store.repository(repo_id)
        with harness.operation(repo):
            harness.prepare(repo, body.consent_to_model, body.use_model, body.signals_dataset)
        return harness.view(repo)

    @app.get("/api/repositories/{repo_id}/rules")
    def rules(repo_id: str):
        return harness.ensure(store.repository(repo_id)).rulebook

    @app.post("/api/repositories/{repo_id}/rules")
    def extract_rules(repo_id: str, body: InvestigationRequest):
        repo = store.repository(repo_id)
        with harness.operation(repo):
            return harness.extract(repo, body.consent_to_model, body.use_model).rulebook

    @app.get("/api/repositories/{repo_id}/signals")
    def signals(repo_id: str):
        return harness.ensure(store.repository(repo_id)).signals

    @app.post("/api/repositories/{repo_id}/signals")
    def submit_signals(repo_id: str, body: SignalsRequest, background: BackgroundTasks):
        repo = store.repository(repo_id)
        with harness.operation(repo, allow_completed=True):
            harness.ingest_events(repo, body.events, body.dataset_version, body.observation_window, body.consent_to_model)
        if body.reevaluate and harness.reserve_reevaluation(repo):
            background.add_task(orchestrator.reevaluate, repo.id)
        return harness.view(repo)["signals"]

    @app.post("/api/repositories/{repo_id}/signals/import")
    def import_signals(repo_id: str, body: SignalFixtureRequest, background: BackgroundTasks):
        repo = store.repository(repo_id)
        with harness.operation(repo, allow_completed=True):
            harness.import_fixture(repo, body.dataset)
            for item in harness.ensure(repo).reevaluations:
                if item.status == "queued" and body.consent_to_model:
                    item.allow_model = True
        if body.reevaluate and harness.reserve_reevaluation(repo):
            background.add_task(orchestrator.reevaluate, repo.id)
        return harness.view(repo)["signals"]

    @app.post("/api/repositories/{repo_id}/rules/policy-versions")
    def approve_policy(repo_id: str, body: PolicyVersionRequest, background: BackgroundTasks):
        repo = store.repository(repo_id)
        with harness.operation(repo, allow_completed=True):
            harness.activate_policy(repo, body.version, body.approved_rule_ids, body.consent_to_model)
        if harness.reserve_reevaluation(repo):
            background.add_task(orchestrator.reevaluate, repo.id)
        return harness.view(repo)

    @app.get("/api/repositories/{repo_id}/trials/reevaluations")
    def reevaluations(repo_id: str):
        return harness.ensure(store.repository(repo_id)).reevaluations

    @app.post("/api/repositories/{repo_id}/trials/reevaluations")
    def process_reevaluations(repo_id: str, body: ReevaluationRequest, background: BackgroundTasks):
        repo = store.repository(repo_id)
        with repo.lock:
            for item in harness.ensure(repo).reevaluations:
                if item.status == "queued" and body.consent_to_model:
                    item.allow_model = True
        if harness.reserve_reevaluation(repo):
            background.add_task(orchestrator.reevaluate, repo.id)
        return harness.ensure(repo).reevaluations

    @app.get("/api/repositories/{repo_id}/trials/reevaluations/{evaluation_id}")
    def reevaluation_evidence(repo_id: str, evaluation_id: str):
        state = harness.ensure(store.repository(repo_id))
        item = next((item for item in state.reevaluations if item.id == evaluation_id), None)
        if item is None:
            raise GhostPatchError("Re-evaluation not found.", 404)
        return {"reevaluation": item, "report": state.evaluation_reports.get(item.id)}

    @app.get("/api/repositories/{repo_id}/trials")
    def trials(repo_id: str):
        state = harness.ensure(store.repository(repo_id))
        return {"scenarios": state.scenarios, "baseline": state.baseline, "report": state.report}

    @app.post("/api/repositories/{repo_id}/trials")
    def run_trials(repo_id: str, body: TrialsRequest):
        repo = store.repository(repo_id)
        if body.execute and not repo.trusted:
            raise GhostPatchError("Uploaded/cloned repositories cannot execute Ghost Trials.", 403)
        with harness.operation(repo):
            harness.generate_trials(repo, body.consent_to_model, body.use_model)
            if body.execute:
                harness.baseline(repo)
        return trials(repo_id)

    @app.post("/api/plans/{plan_id}/approve", response_model=Plan)
    def approve(plan_id: str, body: ExecuteRequest):
        plan = store.plan(plan_id)
        repo = store.repository(plan.repository_id)
        with repo.lock:
            if repo.busy or (repo.job_id and (store.job(repo.job_id).plan_id == plan.id or orchestrator.followup(repo, plan) is None)):
                raise GhostPatchError("Cannot change approval after execution starts.", 409)
            if plan.harness_revision != harness.ensure(repo).revision:
                raise GhostPatchError("Investigation changed; generate a fresh plan before approval.", 409)
            if set(body.approved_rule_changes) != set(plan.intended_rule_changes):
                raise GhostPatchError("Explicitly approve exactly the intended business-rule changes listed in this plan.", 409)
            plan.approval_status = "approved"
            plan.policy_changes_approved = bool(plan.intended_rule_changes)
        return plan

    @app.post("/api/plans/{plan_id}/execute", response_model=Job, status_code=202)
    def execute(plan_id: str, body: ExecuteRequest, background: BackgroundTasks):
        job, created = orchestrator.start(store.plan(plan_id))
        if created:
            background.add_task(orchestrator.execute, job.id)
        return job.model_copy(deep=True)

    @app.get("/api/jobs/{job_id}", response_model=Job)
    def job(job_id: str):
        with store.lock:
            return store.job(job_id).model_copy(deep=True)

    @app.get("/api/jobs/{job_id}/events")
    def events(job_id: str):
        with store.lock:
            return [e.model_copy(deep=True) for e in store.job(job_id).events]

    @app.get("/api/jobs/{job_id}/rules")
    def job_rules(job_id: str):
        current = store.job(job_id)
        return current.results.rulebook or harness.ensure(store.repository(current.repository_id)).rulebook

    @app.get("/api/jobs/{job_id}/signals")
    def job_signals(job_id: str):
        current = store.job(job_id)
        return current.results.signals or harness.ensure(store.repository(current.repository_id)).signals

    @app.get("/api/jobs/{job_id}/trials")
    def job_trials(job_id: str):
        current = store.job(job_id)
        report = current.results.behavior_report
        return {"report": report, "baseline": current.results.baseline, "modified": current.results.modified}

    @app.get("/api/jobs/{job_id}/evidence")
    def evidence(job_id: str):
        current = store.job(job_id)
        if current.results.behavior_report is None:
            raise GhostPatchError("Behavior preservation report is not finalized yet.", 409)
        return current.results.behavior_report

    @app.get("/api/jobs/{job_id}/evidence/download")
    def download_evidence(job_id: str):
        current = store.job(job_id)
        path = store.repository(current.repository_id).root / "jobs" / current.id / "evidence.json"
        if current.status in {"queued", "running"} or not path.is_file():
            raise GhostPatchError("Evidence artifact is unavailable or not finalized.", 409)
        return FileResponse(path, filename=f"ghostpatch-{current.id[:8]}-evidence.json", media_type="application/json")

    @app.get("/api/jobs/{job_id}/results")
    def results(job_id: str):
        current = store.job(job_id)
        if current.status in {"queued", "running"}:
            raise GhostPatchError("Job is still running; poll its status.", 409)
        return current.results

    @app.get("/api/jobs/{job_id}/patch")
    def patch(job_id: str):
        current = store.job(job_id)
        if current.status in {"queued", "running"}:
            raise GhostPatchError("Patch is not finalized yet.", 409)
        path = store.repository(current.repository_id).root / "jobs" / current.id / "result.patch"
        if not path.exists() or not current.results.diffs:
            raise GhostPatchError("No patch was produced for this job.", 404)
        return FileResponse(path, filename=f"ghostpatch-{current.id[:8]}.patch", media_type="text/x-diff")

    return app


app = create_app()
