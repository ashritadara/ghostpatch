export interface Finding {
  id: string; file_path: string; line: number | null; category: string;
  severity: "high" | "medium" | "low"; explanation: string;
  evidence: string; recommendation: string; source: "static" | "model";
}
export interface Analysis {
  repository_id: string; files: string[]; python_file_count: number;
  imports: Record<string, string[]>; local_dependencies: { source: string; target: string }[];
  findings: Finding[]; warnings: string[];
}
export interface RepositorySummary {
  id: string; name: string; file_count: number; trusted: boolean;
  execution_policy: string; analysis: Analysis;
  sample_id?: string | null;
}
export interface Plan {
  id: string; repository_id: string; allowed_paths: string[]; approval_status: "pending" | "approved";
  proposal: { objective: string; changes: { path: string; description: string; priority: string }[];
    risks: string[]; test_strategy: string[] };
  intended_rule_changes: string[]; policy_changes_approved: boolean; harness_revision: number | null;
  policy_version?: string | null; trigger_id?: string | null;
}
export interface TestRun {
  status: "passed" | "failed" | "not_verified"; command: string[];
  exit_code: number | null; duration_ms: number;
  counts: { passed: number; failed: number; skipped: number } | null;
  stdout: string; stderr: string; behavior_outputs: Record<string, unknown>; reason: string | null;
  trial_outputs: TrialExecution[];
}
export interface Job {
  id: string; repository_id: string; plan_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "needs_review";
  started_at: string | null; completed_at: string | null; error: string | null;
  events: { id: string; timestamp: string; phase: string; status: string; message: string }[];
  results: { baseline: TestRun | null; initial_modified: TestRun | null; modified: TestRun | null;
    behavior_comparison: { case_id: string; status: string; baseline: unknown; modified: unknown }[];
    repairs: { attempt: number; summary: string; validation: TestRun | null; error: string | null }[];
    diffs: { path: string; before: string; after: string; unified_diff: string }[];
    rulebook?: RuleBook | null; signals?: SignalsReport | null; behavior_report?: BehaviorReport | null;
    warnings: string[]; verification: "passed" | "failed" | "not_verified" };
}
export interface Health {
  status: string; nvidia_configured: boolean; model: string | null;
  docker: { available: boolean; reason?: string; image_id?: string };
  execution_policy: string; persistence: string;
}

export interface SourceReference {
  file_path: string; function: string | null; line_start: number; line_end: number;
  quote: string; sha256: string; file_sha256: string; role: string;
}
export interface BusinessRule {
  id: string; title: string; description: string; kind: string; references: SourceReference[];
  confidence: number; uncertainty: string; status: "hypothesis" | "verified" | "conflicted" | "superseded";
  version: number; origin: string; history: { version: number; status: string; timestamp: string; reason: string; evidence_ids: string[] }[];
}
export interface RuleBook {
  repository_id: string; source_digest: string; version: number; rules: BusinessRule[];
  conflicts: { id: string; rule_ids: string[]; description: string; basis: string; status: string; evidence_ids: string[] }[];
  warnings: string[]; model_status: string; model_error: string | null;
  policy_version?: string | null;
}
export interface Scenario {
  id: string; title: string; category: string; rule_ids: string[]; input: unknown;
  oracle: "approved_policy" | "legacy_observation" | "metamorphic_invariant" | "hypothesis";
  invariant: string | null; expected: Outcome | null; oracle_reference: SourceReference | null;
  rationale: string; origin: string;
}
export interface Outcome { output: unknown; exception_type: string | null; }
export interface TrialExecution {
  scenario_id: string; input_digest: string; outcome: Outcome; duration_ms: number;
  stdout: string; stderr: string; input_mutated: boolean; created_files: string[]; invariant_passed: boolean | null;
}
export interface SignalsReport {
  synthetic: true; windows: { dataset_version: string; event_count: number; session_count: number;
    user_count?: number | null; software_version?: string | null; observation_window?: {start:string;end:string} | null;
    metrics: { kind: string; numerator: number; denominator: number; rate: number | null; eligible: boolean; explanation: string; rule_ids: string[];
      available?:boolean; unavailable_reason?:string|null; sample_size?:number }[] }[];
  trends: { kind: string; before_rate: number; after_rate: number; delta: number }[];
  hypotheses: { id: string; title: string; description: string; rule_ids: string[]; alternate_explanations: string[];
    confidence: number; references: SourceReference[];
    suggested_scenarios: Pick<Scenario, "title" | "category" | "rule_ids" | "input" | "oracle" | "invariant" | "rationale">[];
    status: "hypothesis"; source: string; explanations?: {id:string;kind:string;description:string;evidence_for:string[];evidence_against:string[];uncertainty:string;source:string}[] }[];
  warnings: string[]; model_status: string; model_error: string | null; retention: string;
  drifts?: {id:string;category:string;metric:string;status:string;delta:number|null;before_rate:number|null;after_rate:number|null;before_denominator:number;after_denominator:number;reasons:string[];policy_version:string|null}[];
}
export interface ToolInvocation {
  id: string; tool: string; started_at: string; completed_at: string; duration_ms: number;
  status: string; input_summary: Record<string, unknown>; output_summary: Record<string, unknown>; error: string | null;
}
export interface BehaviorReport {
  repository_id: string; rulebook: RuleBook; signals: SignalsReport;
  scenario_results: { scenario: Scenario; baseline: TrialExecution | null; modified: TrialExecution | null;
    classification: string; reason: string; expected: Outcome | null }[];
  rule_coverage: { covered: number; total: number; scenarios: number };
  classifications: Record<string, number>; status: string; approved_rule_changes: string[];
  limitations: string[]; test_evidence: Record<string, unknown>; diffs: { path: string; unified_diff: string }[];
  tool_invocations: ToolInvocation[];
}
export interface Investigation {
  revision: number; rulebook: RuleBook; signals: SignalsReport; scenarios: Scenario[];
  baseline: TestRun | null; report: BehaviorReport | null; tool_invocations: ToolInvocation[];
  reevaluations?: Reevaluation[];
}

export interface Reevaluation {
  id:string;trigger:string;policy_version:string|null;status:string;created_at:string;completed_at:string|null;
  attempts:number;report_status:string|null;classifications:Record<string,number>;approval_state:string;
  recommended_action:string|null;uncertainty:string;error:string|null;plan_id:string|null;
}
