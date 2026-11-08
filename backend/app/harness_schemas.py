"""Evidence, rule, trial, and synthetic-signal DTOs; no executable model output."""
from datetime import datetime, timezone
import json
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCandidate(EvidenceDTO):
    file_path: str = Field(min_length=1, max_length=180)
    function: str | None = Field(default=None, max_length=100)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=2000)


class SourceReference(SourceCandidate):
    sha256: str
    file_sha256: str
    role: Literal["code", "test", "documentation", "policy"]


class RuleCandidate(EvidenceDTO):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1200)
    kind: Literal["observed_implementation", "intended_policy", "test_expectation"]
    references: list[SourceCandidate] = Field(min_length=1, max_length=4)
    confidence: float = Field(ge=0, le=1)
    uncertainty: str = Field(min_length=1, max_length=600)


class RuleExtraction(EvidenceDTO):
    rules: list[RuleCandidate] = Field(min_length=1, max_length=10)


class RuleHistory(EvidenceDTO):
    version: int
    status: Literal["hypothesis", "verified", "conflicted", "superseded"]
    timestamp: str
    reason: str
    evidence_ids: list[str]
    policy_version: str | None = None


class BusinessRule(EvidenceDTO):
    id: str
    title: str
    description: str
    kind: Literal["observed_implementation", "intended_policy", "test_expectation"]
    references: list[SourceReference]
    confidence: float = Field(ge=0, le=1)
    uncertainty: str
    status: Literal["hypothesis", "verified", "conflicted", "superseded"] = "hypothesis"
    version: int = 1
    history: list[RuleHistory] = Field(default_factory=list)
    origin: Literal["deterministic", "nemotron", "trusted_policy"]


class RuleConflict(EvidenceDTO):
    id: str
    rule_ids: list[str]
    description: str
    basis: Literal["source_contradiction", "signal_hypothesis", "trial_evidence"]
    status: Literal["proposed", "observed", "resolved"]
    evidence_ids: list[str]
    policy_version: str | None = None


class RuleBook(EvidenceDTO):
    repository_id: str
    source_digest: str
    version: int = 1
    rules: list[BusinessRule] = Field(default_factory=list)
    conflicts: list[RuleConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_status: Literal["not_requested", "succeeded", "failed"] = "not_requested"
    model_error: str | None = None
    policy_version: str | None = None
    investigations: list[dict[str, Any]] = Field(default_factory=list)


class Outcome(EvidenceDTO):
    output: Any = None
    exception_type: str | None = None


class ScenarioCandidate(EvidenceDTO):
    title: str = Field(min_length=1, max_length=160)
    category: Literal["normal", "edge", "boundary", "negative", "duplicate", "regression"]
    rule_ids: list[str] = Field(min_length=1, max_length=5)
    input: Any
    oracle: Literal["legacy_observation", "metamorphic_invariant", "hypothesis"]
    invariant: Literal["input_unchanged", "repeatability"] | None = None
    rationale: str = Field(min_length=1, max_length=800)

    @field_validator("input")
    @classmethod
    def bounded_input(cls, value):
        def check(part, depth=0):
            if depth > 6:
                raise ValueError("Scenario nesting exceeds the limit.")
            if isinstance(part, str) and len(part) > 256:
                raise ValueError("Scenario string exceeds the limit.")
            if isinstance(part, dict):
                if len(part) > 20 or any(not isinstance(k, str) or len(k) > 64 for k in part):
                    raise ValueError("Invalid scenario object.")
                for child in part.values(): check(child, depth + 1)
            elif isinstance(part, list):
                if len(part) > 30: raise ValueError("Scenario list exceeds the limit.")
                for child in part: check(child, depth + 1)
        check(value)
        if len(json.dumps(value, allow_nan=False)) > 4096:
            raise ValueError("Scenario input exceeds 4 KiB.")
        return value


class ScenarioProposals(EvidenceDTO):
    scenarios: list[ScenarioCandidate] = Field(min_length=1, max_length=8)


class Scenario(ScenarioCandidate):
    id: str
    oracle: Literal["approved_policy", "legacy_observation", "metamorphic_invariant", "hypothesis"]
    expected: Outcome | None = None
    oracle_reference: SourceReference | None = None
    origin: Literal["trusted_fixture", "deterministic", "nemotron", "signal"]
    trigger_ids: list[str] = Field(default_factory=list, max_length=6)


class TrialExecution(EvidenceDTO):
    scenario_id: str
    input_digest: str
    outcome: Outcome
    duration_ms: int = Field(ge=0)
    stdout: str = Field(default="", max_length=5000)
    stderr: str = Field(default="", max_length=5000)
    input_mutated: bool = False
    created_files: list[str] = Field(default_factory=list, max_length=20)
    invariant_passed: bool | None = None


class ScenarioResult(EvidenceDTO):
    scenario: Scenario
    baseline: TrialExecution | None
    modified: TrialExecution | None
    classification: Literal["preserved", "intended_change", "unexpected_divergence", "unverified", "execution_error"]
    reason: str
    expected: Outcome | None = None


class ToolInvocation(EvidenceDTO):
    id: str
    tool: str
    started_at: str
    completed_at: str
    duration_ms: int
    status: Literal["succeeded", "failed"]
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    evidence_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class SafeMetadata(EvidenceDTO):
    age_band: Literal["below_threshold", "at_threshold", "above_threshold"] | None = None
    error_code: Literal["AGE_THRESHOLD", "DUPLICATE", "INVALID_INPUT"] | None = None
    attempt: int | None = Field(default=None, ge=1, le=5)


class SyntheticEvent(EvidenceDTO):
    event_id: str = Field(pattern=r"^ev_[0-9a-f]{8,24}$")
    session_id: str = Field(pattern=r"^s_[0-9a-f]{8,16}$")
    timestamp: AwareDatetime
    workflow: Literal["eligibility", "claim_submission"]
    action: Literal["submit", "manual_override", "retry", "abandon", "return"]
    outcome: Literal["approved", "rejected", "review", "error", "abandoned", "completed"]
    rule_context: list[str] = Field(min_length=1, max_length=4)
    synthetic: Literal[True]
    metadata: SafeMetadata = Field(default_factory=SafeMetadata)
    user_id: str | None = Field(default=None, pattern=r"^u_[0-9a-f]{8,16}$")
    software_version: Literal["legacy-v1", "candidate-v2", "policy-v3"] | None = None
    policy_version: Literal["1.0", "1.1"] | None = None

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value):
        return value.astimezone(timezone.utc)

    @field_validator("synthetic", mode="before")
    @classmethod
    def only_synthetic(cls, value):
        if value is not True:
            raise ValueError("Only explicitly synthetic events are accepted.")
        return value


class SignalMetric(EvidenceDTO):
    kind: str
    numerator: int
    denominator: int
    rate: float | None
    eligible: bool
    explanation: str
    rule_ids: list[str]
    available: bool = True
    unavailable_reason: str | None = None
    sample_size: int = 0
    window_start: str | None = None
    window_end: str | None = None


class ObservationWindow(EvidenceDTO):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def valid_window(self):
        self.start=self.start.astimezone(timezone.utc)
        self.end=self.end.astimezone(timezone.utc)
        seconds = (self.end - self.start).total_seconds()
        if not 0 < seconds <= 31 * 86400:
            raise ValueError("Observation windows must be positive and at most 31 days.")
        return self


class SignalWindow(EvidenceDTO):
    dataset_version: str
    event_count: int
    session_count: int
    metrics: list[SignalMetric]
    user_count: int | None = None
    identified_event_count: int = 0
    unidentified_event_count: int = 0
    observation_window: ObservationWindow | None = None
    software_version: str | None = None
    reported_policy_versions: list[str] = Field(default_factory=list)
    input_categories: dict[str, dict[str, int]] = Field(default_factory=dict)
    workflows: list[str] = Field(default_factory=list)


class DriftFinding(EvidenceDTO):
    id: str
    category: Literal["user_behavior", "input_data", "policy"]
    metric: str
    rule_ids: list[str]
    policy_version: str | None = None
    before_dataset: str
    after_dataset: str
    before_version: str | None
    after_version: str | None
    before_rate: float | None
    after_rate: float | None
    delta: float | None
    before_numerator: int
    after_numerator: int
    before_denominator: int
    after_denominator: int
    before_window: ObservationWindow | None
    after_window: ObservationWindow | None
    status: Literal["meaningful", "insufficient_data", "not_comparable"]
    reasons: list[str]
    evidence_ids: list[str]


class CompetingExplanation(EvidenceDTO):
    id: str
    kind: Literal["code", "workflow", "instrumentation", "input_mix", "policy"]
    description: str = Field(min_length=1, max_length=800)
    evidence_for: list[str] = Field(default_factory=list, max_length=8)
    evidence_against: list[str] = Field(default_factory=list, max_length=8)
    uncertainty: str = Field(min_length=1, max_length=500)
    source: Literal["deterministic", "nemotron"] = "nemotron"


class SignalHypothesisCandidate(EvidenceDTO):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    rule_ids: list[str] = Field(min_length=1, max_length=4)
    alternate_explanations: list[str] = Field(min_length=2, max_length=4)
    confidence: float = Field(ge=0, le=1)
    references: list[SourceCandidate] = Field(min_length=1, max_length=3)
    suggested_scenarios: list[ScenarioCandidate] = Field(min_length=1, max_length=3)
    drift_ids: list[str] = Field(default_factory=list, max_length=12)
    explanations: list[CompetingExplanation] = Field(default_factory=list, max_length=4)
    recommendation: str | None = Field(default=None, max_length=800)


class SignalInterpretation(EvidenceDTO):
    hypotheses: list[SignalHypothesisCandidate] = Field(min_length=1, max_length=3)


class SignalHypothesis(EvidenceDTO):
    id: str
    title: str
    description: str
    rule_ids: list[str]
    alternate_explanations: list[str]
    confidence: float
    references: list[SourceReference]
    suggested_scenarios: list[ScenarioCandidate]
    status: Literal["hypothesis"] = "hypothesis"
    source: Literal["deterministic", "nemotron"]
    drift_ids: list[str] = Field(default_factory=list)
    explanations: list[CompetingExplanation] = Field(default_factory=list)
    policy_version: str | None = None
    recommendation: str | None = None


class Reevaluation(EvidenceDTO):
    id: str
    trigger: Literal["signal_drift", "approved_policy_update"]
    evidence_digest: str
    drift_ids: list[str]
    rule_ids: list[str]
    policy_version: str | None
    source_evidence: list[str]
    status: Literal["queued", "running", "completed", "failed", "suggested_only"] = "queued"
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    attempts: int = Field(default=0, ge=0, le=1)
    allow_model: bool = False
    candidate_kind: str = "unchanged_working_copy"
    scenario_ids: list[str] = Field(default_factory=list)
    report_status: str | None = None
    classifications: dict[str, int] = Field(default_factory=dict)
    tool_ids: list[str] = Field(default_factory=list)
    approval_state: Literal["human_required", "no_action", "not_applicable"] = "human_required"
    recommended_action: str | None = None
    uncertainty: str = "Synthetic association is not causation; trial coverage is partial."
    error: str | None = None
    plan_id: str | None = None


class SignalsReport(EvidenceDTO):
    synthetic: Literal[True] = True
    windows: list[SignalWindow] = Field(default_factory=list)
    trends: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[SignalHypothesis] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_status: Literal["not_requested", "succeeded", "failed"] = "not_requested"
    model_error: str | None = None
    retention: str = "Synthetic events expire with the local repository snapshot; maximum 500 unique events."
    drifts: list[DriftFinding] = Field(default_factory=list)
    reevaluations: list[Reevaluation] = Field(default_factory=list)


class BehaviorReport(EvidenceDTO):
    repository_id: str
    rulebook: RuleBook
    signals: SignalsReport
    scenario_results: list[ScenarioResult]
    rule_coverage: dict[str, int]
    classifications: dict[str, int]
    status: Literal["passed", "failed", "not_verified"]
    approved_rule_changes: list[str]
    limitations: list[str]
    test_evidence: dict[str, Any]
    diffs: list[dict[str, str]] = Field(default_factory=list)
    tool_invocations: list[ToolInvocation] = Field(default_factory=list)
    policy_version: str | None = None
    reevaluations: list[Reevaluation] = Field(default_factory=list)
    approval_state: str = "human_required"


class InvestigationRequest(EvidenceDTO):
    consent_to_model: bool = False
    use_model: bool = True
    signals_dataset: Literal["before", "after", "both", "none"] = "both"


class SignalsRequest(EvidenceDTO):
    dataset_version: Literal["before-v1", "after-v1", "custom-synthetic-v1"] = "custom-synthetic-v1"
    events: list[SyntheticEvent] = Field(min_length=1, max_length=500)
    observation_window: ObservationWindow | None = None
    consent_to_model: bool = False
    reevaluate: bool = True


class SignalFixtureRequest(EvidenceDTO):
    dataset: Literal["before", "after"]
    consent_to_model: bool = False
    reevaluate: bool = True


class ReevaluationRequest(EvidenceDTO):
    consent_to_model: bool = False


class PolicyVersionRequest(EvidenceDTO):
    version: Literal["1.0", "1.1"]
    approved: Literal[True]
    approved_rule_ids: list[str] = Field(min_length=1, max_length=5)
    consent_to_model: bool = False


class TrialsRequest(EvidenceDTO):
    execute: bool = True
    consent_to_model: bool = False
    use_model: bool = False
