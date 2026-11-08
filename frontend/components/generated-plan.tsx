"use client";

import type { Plan } from "@/types/api";
import WorkspaceDetails from "./workspace-details";
import WorkspaceIcon from "./workspace-icon";

export default function GeneratedPlan({ plan, embedded, active, trusted, disabled, onApprove }: {
  plan: Plan; embedded: boolean; active: boolean; trusted: boolean; disabled: boolean; onApprove: () => void;
}) {
  return <WorkspaceDetails id="gp-generated-plan" className={embedded ? "gp-bubble gp-plan-review" : "panel"} open
    autoOpenKey={embedded && active ? plan.id : undefined}>
    <summary>{embedded && <WorkspaceIcon kind="code" />}<span><strong>Review generated plan</strong><small>{plan.proposal.changes.length} proposed changes · risks, affected files, and validation</small></span></summary>
    <h3>Modernization goal</h3><p>{plan.proposal.objective}</p>
    {(plan.intended_rule_changes ?? []).length > 0 && <p className="warning">Business-rule changes requiring your explicit approval: {plan.intended_rule_changes.join(", ")}</p>}
    <h3>Files this plan may change</h3><ul>{plan.allowed_paths.map(path => <li key={path}><code>{path}</code></li>)}</ul>
    <h3>Proposed changes</h3><ol className="gp-plan-changes">{plan.proposal.changes.map(change => <li key={change.path}>
      <p><strong>Priority: {change.priority}</strong></p><code>{change.path}</code><p>{change.description}</p>
    </li>)}</ol>
    <h3>Risks to review</h3><ul>{plan.proposal.risks.map((risk, i) => <li key={i}>{risk}</li>)}</ul>
    <h3>How the change will be checked</h3><ul>{plan.proposal.test_strategy.map((test, i) => <li key={i}>{test}</li>)}</ul>
    {!trusted && <p className="warning">Code execution is prohibited for this imported repository. Any exported patch will remain unverified.</p>}
    <div className="gp-plan-approval"><p>Approval modifies an isolated working copy. You will confirm the exact file and policy scope before execution starts.</p>
      <button disabled={disabled} onClick={onApprove}>Review approval and start changes</button></div>
  </WorkspaceDetails>;
}
