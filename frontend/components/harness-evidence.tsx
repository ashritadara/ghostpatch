"use client";
import type { ReactNode } from "react";
import type { BehaviorReport, Investigation, SourceReference } from "@/types/api";
import WorkspaceIcon from "./workspace-icon";
import WorkspaceDetails from "./workspace-details";

function EvidenceGroup({ title, description, kind, bubbleLayout, children }: {
  title: string; description: string; kind: "rules" | "signals" | "tests"; bubbleLayout: boolean; children: ReactNode;
}) {
  if (!bubbleLayout) return <div><h3>{title}</h3>{children}</div>;
  return <WorkspaceDetails className="gp-bubble gp-evidence-bubble"><summary><WorkspaceIcon kind={kind} /><span><strong>{title}</strong><small>{description}</small></span><span className="gp-bubble-arrow" aria-hidden="true">↗</span></summary><div className="gp-bubble-content">{children}</div></WorkspaceDetails>;
}

function References({ values }: { values: SourceReference[] }) {
  return <>{values.map(ref => <WorkspaceDetails key={ref.sha256 + ref.file_path + ref.line_start}>
    <summary><code>{ref.file_path}:{ref.line_start}-{ref.line_end}</code> ({ref.role}{ref.function ? " / " + ref.function : ""})</summary>
    <pre>{ref.quote}</pre><small>Evidence SHA-256: {ref.sha256}</small>
  </WorkspaceDetails>)}</>;
}

export default function HarnessEvidence({ investigation, report, intended, disabled, onSelect, canProposeChange = true, bubbleLayout = false }: {
  investigation: Investigation | null; report: BehaviorReport | null; intended: string[];
  disabled: boolean; onSelect: (ids: string[]) => void;
  canProposeChange?: boolean;
  bubbleLayout?: boolean;
}) {
  const book = report?.rulebook ?? investigation?.rulebook;
  const signals = report?.signals ?? investigation?.signals;
  const behavior = report ?? investigation?.report;
  if (!book) return <p className="muted">Run the investigation to extract source-backed candidate rules and execute trusted baseline trials.</p>;
  const affected = book.rules.filter(rule => rule.kind === "intended_policy" &&
    behavior?.scenario_results.some(result => result.classification === "unexpected_divergence" && result.scenario.rule_ids.includes(rule.id)));
  return <>
    <div className={bubbleLayout ? "gp-evidence-grid" : undefined}>
    <EvidenceGroup title="Ghost Memory" description="Discover rules and supporting source" kind="rules" bubbleLayout={bubbleLayout}>
    <p>{book.rules.length} candidate/policy rules | Contract version {book.version} | Policy {book.policy_version ?? "unavailable"} | Model extraction: {book.model_status}</p>
    {book.model_error && <p className="warning">{book.model_error}</p>}
    <p className="muted">Observed code is not automatically correct policy. Confidence is a heuristic, not a calibrated probability.</p>
    <div className="table-wrap"><table><thead><tr><th>Rule</th><th>Kind / status</th><th>Evidence / history</th></tr></thead><tbody>
      {book.rules.map(rule => <tr key={rule.id}><td data-label="Rule"><strong>{rule.title}</strong><p>{rule.description}</p><small>{rule.id}</small></td>
        <td data-label="Kind / status">{rule.kind}<br /><strong>{rule.status}</strong> | v{rule.version}<br />{rule.origin}<p className="muted">{rule.uncertainty}</p></td>
        <td data-label="Evidence / history"><References values={rule.references} /><WorkspaceDetails><summary>Version history</summary><ul>{rule.history.map(item => <li key={item.version}>v{item.version} {item.status}: {item.reason}</li>)}</ul></WorkspaceDetails></td>
      </tr>)}
    </tbody></table></div>
    {book.conflicts.length > 0 && <WorkspaceDetails open><summary>Competing evidence and proposed conflicts ({book.conflicts.length})</summary>
      <ul>{book.conflicts.map(conflict => <li key={conflict.id}><strong>{conflict.status} / {conflict.basis}</strong>: {conflict.description}</li>)}</ul>
    </WorkspaceDetails>}
    </EvidenceGroup>
    <EvidenceGroup title="Ghost Signals" description="Inspect synthetic windows and drift" kind="signals" bubbleLayout={bubbleLayout}>
    <p className="warning">Synthetic demonstration only. These are not observations of real users and do not authorize policy changes.</p>
    {signals?.windows.length ? <div className="table-wrap"><table><thead><tr><th>Dataset</th><th>Sample size</th><th>Deterministic metrics</th></tr></thead><tbody>
      {signals.windows.map(window => <tr key={window.dataset_version}><td data-label="Dataset">{window.dataset_version}<p>Software: {window.software_version ?? "unavailable"}</p>
        {window.observation_window && <small>{window.observation_window.start} to {window.observation_window.end} (UTC cohort)</small>}</td><td data-label="Sample size">{window.event_count} events<br />{window.session_count} pseudonymous sessions<br />{window.user_count ?? "unavailable"} identified synthetic users</td><td data-label="Deterministic metrics">
        <ul>{window.metrics.map(metric => <li key={metric.kind}><strong>{metric.kind}</strong>: {metric.available === false ? "unavailable: " + metric.unavailable_reason : metric.numerator + "/" + metric.denominator}
          {metric.rate === null ? "" : " (" + (metric.rate * 100).toFixed(1) + "%)"} | {metric.eligible ? "minimum sample met" : "insufficient evidence"}
          <p className="muted">{metric.explanation}</p></li>)}</ul>
      </td></tr>)}
    </tbody></table></div> : <p>No synthetic events ingested for this repository.</p>}
    {signals?.model_error && <p className="warning">{signals.model_error}</p>}
    {signals?.hypotheses.map(hypothesis => <WorkspaceDetails key={hypothesis.id}><summary>Hypothesis ({hypothesis.source}): {hypothesis.title}</summary>
      <p>{hypothesis.description}</p><p>Confidence: {hypothesis.confidence.toFixed(2)} (heuristic)</p>
      <p>Alternate explanations:</p><ul>{hypothesis.alternate_explanations.map((text, index) => <li key={index}>{text}</li>)}</ul>
      {hypothesis.explanations?.map(explanation => <WorkspaceDetails key={explanation.id}><summary>{explanation.kind} ({explanation.source})</summary>
        <p>{explanation.description}</p><p className="muted">{explanation.uncertainty}</p>
        <pre>{JSON.stringify({evidence_for:explanation.evidence_for,evidence_against:explanation.evidence_against},null,2)}</pre></WorkspaceDetails>)}
      <References values={hypothesis.references} />
    </WorkspaceDetails>)}
    {(signals?.drifts?.length ?? 0)>0 && <WorkspaceDetails open><summary>Comparable behavior and input-category drift</summary><ul>
      {signals?.drifts?.map(drift => <li key={drift.id}><strong>{drift.category} / {drift.metric}: {drift.status}</strong>
        <p>Change: {drift.delta === null ? "unavailable" : drift.delta.toFixed(3)} | denominators {drift.before_denominator} / {drift.after_denominator}</p>
        <WorkspaceDetails><summary>Comparison limits</summary><ul>{drift.reasons.map((reason,index)=><li key={index}>{reason}</li>)}</ul></WorkspaceDetails></li>)}
    </ul></WorkspaceDetails>}
    {(investigation?.reevaluations?.length ?? 0)>0 && <WorkspaceDetails open><summary>Bounded re-evaluations</summary><ul>
      {investigation?.reevaluations?.map(item => <li key={item.id}><strong>{item.trigger} / policy {item.policy_version}: {item.status}</strong>
        <p>Attempt {item.attempts}/1 | report {item.report_status ?? "not run"} | {item.approval_state}</p>
        <p>{item.recommended_action}</p><p className="muted">{item.uncertainty}</p>{item.error && <p className="error">{item.error}</p>}
        <pre>{JSON.stringify(item.classifications,null,2)}</pre></li>)}
    </ul></WorkspaceDetails>}
    </EvidenceGroup>
    <EvidenceGroup title="Ghost Trials" description="Review independent behavioral evidence" kind="tests" bubbleLayout={bubbleLayout}>
    {behavior ? <>
      <p>Report: <strong>{behavior.status}</strong> | Rule coverage: {behavior.rule_coverage.covered}/{behavior.rule_coverage.total}
        {" | "}{behavior.rule_coverage.scenarios} scenarios</p>
      <pre>{JSON.stringify(behavior.classifications, null, 2)}</pre>
      <div className="table-wrap"><table><thead><tr><th>Scenario / oracle</th><th>Classification</th><th>Input and evidence</th></tr></thead><tbody>
        {behavior.scenario_results.map(result => <tr key={result.scenario.id}>
          <td data-label="Scenario / oracle">{result.scenario.title}<p><strong>{result.scenario.oracle}</strong></p><small>{result.scenario.rule_ids.join(", ")}</small></td>
          <td data-label="Classification">{result.classification}<p>{result.reason}</p></td>
          <td data-label="Input and evidence"><WorkspaceDetails><summary>Exact inputs, outputs and exceptions</summary><pre>{JSON.stringify({
            input: result.scenario.input, expected: result.expected, baseline: result.baseline, modified: result.modified,
          }, null, 2)}</pre>{result.scenario.oracle_reference && <References values={[result.scenario.oracle_reference]} />}</WorkspaceDetails></td>
        </tr>)}
      </tbody></table></div>
      <WorkspaceDetails><summary>Limitations and actual tool invocations</summary>
        <ul>{behavior.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul>
        <ol>{behavior.tool_invocations.map(tool => <li key={tool.id}>{tool.tool} | {tool.status} | {tool.duration_ms} ms
          <pre>{JSON.stringify({ input_summary: tool.input_summary, output_summary: tool.output_summary, error: tool.error }, null, 2)}</pre></li>)}</ol>
      </WorkspaceDetails>
    </> : <p>Baseline trials have not executed. Hypotheses are not pass/fail oracles.</p>}
    </EvidenceGroup>
    </div>
    {affected.length > 0 && canProposeChange && <div className="panel"><h3>Explicit semantic-change scope</h3>
      <p>Select the independently evidenced policy correction to request in the plan. Execution still requires your plan approval.</p>
      {affected.map(rule => <label className="check" key={rule.id}><input type="checkbox" disabled={disabled} checked={intended.includes(rule.id)}
        onChange={event => onSelect(event.target.checked ? [...intended, rule.id] : intended.filter(id => id !== rule.id))} />
        <span>{rule.title}: {rule.description}</span></label>)}
    </div>}
  </>;
}
