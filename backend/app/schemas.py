from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from .harness_schemas import BehaviorReport, RuleBook, SignalsReport, TrialExecution


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(DTO):
    id: str
    file_path: str
    line: int | None = None
    category: str
    severity: Literal["high", "medium", "low"]
    explanation: str
    evidence: str
    recommendation: str
    source: Literal["static", "model"] = "static"


class Analysis(DTO):
    repository_id: str
    files: list[str]
    python_file_count: int
    imports: dict[str, list[str]]
    local_dependencies: list[dict[str, str]]
    findings: list[Finding]
    warnings: list[str]


class RepositorySummary(DTO):
    id: str
    name: str
    file_count: int
    trusted: bool
    execution_policy: str
    analysis: Analysis
    sample_id: str | None = None


class PlannedChange(DTO):
    path: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1, max_length=2000)
    priority: Literal["high", "medium", "low"]


class ModelPlan(DTO):
    objective: str = Field(min_length=1, max_length=2000)
    changes: list[PlannedChange] = Field(min_length=1, max_length=1)
    risks: list[str] = Field(max_length=8)
    test_strategy: list[str] = Field(min_length=1, max_length=8)


class Plan(DTO):
    id: str
    repository_id: str
    proposal: ModelPlan
    allowed_paths: list[str]
    approval_status: Literal["pending", "approved"] = "pending"
    intended_rule_changes: list[str] = Field(default_factory=list, max_length=5)
    policy_changes_approved: bool = False
    harness_revision: int | None = None
    policy_version: str | None = None
    trigger_id: str | None = None
    source_hashes: dict[str, str] = Field(default_factory=dict)


class Edit(DTO):
    path: str = Field(min_length=1, max_length=180)
    original_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    new_content: str = Field(min_length=1, max_length=20000)


class PatchProposal(DTO):
    summary: str = Field(min_length=1, max_length=2000)
    edits: list[Edit] = Field(min_length=1, max_length=1)


class TestCounts(DTO):
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)


class TestRun(DTO):
    status: Literal["passed", "failed", "not_verified"]
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    duration_ms: int = Field(default=0, ge=0)
    counts: TestCounts | None = None
    stdout: str = ""
    stderr: str = ""
    behavior_outputs: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    trial_outputs: list[TrialExecution] = Field(default_factory=list, max_length=24)


class RepairResult(DTO):
    attempt: int = Field(ge=1, le=2)
    summary: str
    validation: TestRun | None = None
    error: str | None = None


class JobResults(DTO):
    baseline: TestRun | None = None
    initial_modified: TestRun | None = None
    modified: TestRun | None = None
    behavior_comparison: list[dict[str, Any]] = Field(default_factory=list)
    repairs: list[RepairResult] = Field(default_factory=list)
    diffs: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    verification: Literal["passed", "failed", "not_verified"] = "not_verified"
    rulebook: RuleBook | None = None
    signals: SignalsReport | None = None
    behavior_report: BehaviorReport | None = None
    baseline_kind: Literal["original", "previous_working_copy"] = "original"


class Event(DTO):
    id: str
    timestamp: str
    phase: str
    status: Literal["started", "succeeded", "failed", "warning", "info"]
    message: str


class Job(DTO):
    id: str
    repository_id: str
    plan_id: str
    status: Literal["queued", "running", "succeeded", "failed", "needs_review"]
    started_at: str | None = None
    completed_at: str | None = None
    events: list[Event] = Field(default_factory=list)
    results: JobResults = Field(default_factory=JobResults)
    error: str | None = None


class GitImportRequest(DTO):
    url: str = Field(min_length=1, max_length=300)


class PlanRequest(DTO):
    consent_to_model: bool
    objective: str = Field(default="Modernize one small Python construct while preserving observable behavior.", min_length=10, max_length=1000)
    intended_rule_changes: list[str] = Field(default_factory=list, max_length=5)


class ExecuteRequest(DTO):
    approved: Literal[True]
    approved_rule_changes: list[str] = Field(default_factory=list, max_length=5)


class ConnectivityRequest(DTO):
    consent_to_model: Literal[True]
