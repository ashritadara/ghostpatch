from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import stat
import tempfile
import threading
import time
import uuid

from .config import Settings
from .errors import GhostPatchError
from .schemas import Analysis, Job, Plan, RepositorySummary
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .harness import InvestigationState


def identifier() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprints(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()}


@dataclass
class Repository:
    id: str
    name: str
    root: Path
    trusted: bool = False
    trust_digest: str = ""
    sample_id: str | None = None
    investigation: "InvestigationState | None" = None
    execution_snapshots: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)
    job_baselines: dict[str, Path] = field(default_factory=dict, repr=False)
    analysis: Analysis | None = None
    hashes: dict[str, str] = field(default_factory=dict)
    created: float = field(default_factory=time.monotonic)
    busy: bool = False
    job_id: str | None = None
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def original(self) -> Path:
        return self.root / "original"

    @property
    def working(self) -> Path:
        return self.root / "working"

    def summary(self) -> RepositorySummary:
        if self.analysis is None:
            raise GhostPatchError("Repository analysis is unavailable.", 409)
        return RepositorySummary(id=self.id, name=self.name, file_count=len(self.hashes),
            trusted=self.trusted, analysis=self.analysis, sample_id=self.sample_id,
            execution_policy="Built-in trusted sample: Docker validation permitted." if self.trusted
            else "Untrusted source: static analysis and reviewed patch only; code execution prohibited.")

    def assert_original(self) -> None:
        if fingerprints(self.original) != self.hashes:
            raise GhostPatchError("Original snapshot integrity check failed.", 409)


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repositories: dict[str, Repository] = {}
        self.plans: dict[str, Plan] = {}
        self.jobs: dict[str, Job] = {}
        self.lock = threading.RLock()
        settings.workspace_root.mkdir(parents=True, exist_ok=True)

    def allocate(self, name: str) -> Repository:
        with self.lock:
            self.cleanup()
            if len(self.repositories) >= self.settings.max_repositories:
                raise GhostPatchError("Workspace limit reached. Delete an old repository or restart the local service.", 429)
            root = Path(tempfile.mkdtemp(prefix="gp-", dir=self.settings.workspace_root))
            (root / "original").mkdir()
            repo = Repository(identifier(), name[:100], root)
            self.repositories[repo.id] = repo
            return repo

    def repository(self, repo_id: str) -> Repository:
        with self.lock:
            repo = self.repositories.get(repo_id)
        if repo is None:
            raise GhostPatchError("Repository not found; local state may have expired or the server restarted.", 404)
        return repo

    def plan(self, plan_id: str) -> Plan:
        with self.lock:
            plan = self.plans.get(plan_id)
        if plan is None:
            raise GhostPatchError("Plan not found.", 404)
        return plan

    def job(self, job_id: str) -> Job:
        with self.lock:
            job = self.jobs.get(job_id)
        if job is None:
            raise GhostPatchError("Job not found.", 404)
        return job

    def remove(self, repo: Repository) -> None:
        with repo.lock, self.lock:
            if repo.busy:
                raise GhostPatchError("Repository is busy; try cleanup after the operation completes.", 409)
            root = repo.root.resolve()
            if root.parent != self.settings.workspace_root.resolve() or not root.name.startswith("gp-"):
                raise GhostPatchError("Refusing cleanup outside the owned workspace.", 500)
            def writable_retry(function, path, exc):
                # Git object files can be read-only on Windows; all targets are
                # inside this verified, app-owned temporary directory.
                if not Path(path).resolve().is_relative_to(root):
                    raise exc
                Path(path).chmod(stat.S_IWRITE | stat.S_IREAD)
                function(path)
            shutil.rmtree(root, onexc=writable_retry)
            self.repositories.pop(repo.id, None)
            self.plans = {k: v for k, v in self.plans.items() if v.repository_id != repo.id}
            self.jobs = {k: v for k, v in self.jobs.items() if v.repository_id != repo.id}

    def cleanup(self) -> None:
        # Caller holds the store lock. Never wait for a repository lock here.
        for repo in list(self.repositories.values()):
            if not repo.busy and time.monotonic() - repo.created > self.settings.retention_seconds and repo.lock.acquire(blocking=False):
                try:
                    self.remove(repo)
                finally:
                    repo.lock.release()

    def close(self) -> None:
        for repo in list(self.repositories.values()):
            if not repo.busy:
                self.remove(repo)
