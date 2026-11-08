"use client";

import { useEffect, useRef, useState } from "react";
import { downloadPatch, post, request } from "@/lib/api";
import type { Health, Job, Plan, RepositorySummary, TestRun } from "@/types/api";
import type { Investigation } from "@/types/api";
import HarnessEvidence from "@/components/harness-evidence";
import { allowedSceneOrigin, isSceneChapter, SCENE_CHANNEL, WORKSPACE_STEPS } from "@/lib/scene-bridge";
import "./backend-workspace.css";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request failure.";
}

type PendingApproval = {
  kind: "execute" | "policy";
  description: string;
  repositoryId: string;
  planId?: string;
};

function ApprovalDialog({ approval, onCancel, onApprove }: {
  approval: PendingApproval; onCancel: () => void; onApprove: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog?.showModal();
    cancelRef.current?.focus();
    return () => { dialog?.close(); if (previous instanceof HTMLElement) previous.focus(); };
  }, []);
  return <dialog ref={ref} className="gp-approval-dialog" aria-labelledby="approval-title"
    onCancel={event => { event.preventDefault(); onCancel(); }}>
    <h2 id="approval-title">{approval.kind === "execute" ? "Approve this exact plan?" : "Approve fictional policy 1.1?"}</h2>
    <p>{approval.description}</p>
    <div className="row"><button ref={cancelRef} className="secondary" onClick={onCancel}>Cancel</button>
      <button onClick={onApprove}>{approval.kind === "execute" ? "Confirm plan approval and execute" : "Confirm policy approval"}</button></div>
  </dialog>;
}

function TestEvidence({ title, run }: { title: string; run: TestRun | null }) {
  return <details open><summary>{title}: {run?.status ?? "not run"}</summary>
    {!run ? <p className="muted">No execution evidence available.</p> : <>
      <p>Exit code: {run.exit_code ?? "unavailable"} ? Duration: {run.duration_ms} ms</p>
      <p>{run.counts ? run.counts.passed + " passed ? " + run.counts.failed + " failed ? " + run.counts.skipped + " skipped" : "Test counts unavailable; no pass is inferred."}</p>
      {run.reason && <p className="warning">{run.reason}</p>}
      {run.command.length > 0 && <pre>{run.command.join(" ")}</pre>}
      <pre aria-label={title + " output"}>{run.stdout || "No stdout captured."}{run.stderr ? "\nSTDERR\n" + run.stderr : ""}</pre>
    </>}
  </details>;
}

export default function BackendWorkspace({ embedded = false }: { embedded?: boolean }) {
  const [chapter, setChapter] = useState(1);
  const [approval, setApproval] = useState<PendingApproval | null>(null);
  const sceneOrigin = useRef<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [gitUrl, setGitUrl] = useState("");
  const [repo, setRepo] = useState<RepositorySummary | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [consent, setConsent] = useState(false);
  const [objective, setObjective] = useState("Simplify one legacy Python construct while preserving numeric types, ordering, exceptions, and public behavior.");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [connection, setConnection] = useState("");
  const [review, setReview] = useState<"pending" | "approved" | "rejected">("pending");
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [intendedChanges, setIntendedChanges] = useState<string[]>([]);
  const jobId = job?.id;
  const jobStatus = job?.status;
  const running = jobStatus === "queued" || jobStatus === "running";
  const reevaluating = investigation?.reevaluations?.some(item => item.status === "queued" || item.status === "running") ?? false;
  const locked = busy !== null || running || reevaluating || approval !== null;
  const repoId = repo?.id;
  const latestEvaluation = investigation?.reevaluations?.at(-1);
  const newerEvidence = !!(job?.completed_at && latestEvaluation?.completed_at && latestEvaluation.completed_at > job.completed_at);
  const followupReady = newerEvidence && latestEvaluation?.status === "completed" && latestEvaluation.approval_state === "human_required" && !latestEvaluation.plan_id;
  const show = (step: number) => !embedded || chapter === step;

  function navigate(step: number) {
    if (!isSceneChapter(step)) return;
    setApproval(null);
    if (sceneOrigin.current && window.parent !== window) {
      window.parent.postMessage({ channel: SCENE_CHANNEL, type: "navigate", chapter: step }, sceneOrigin.current);
    } else if (step === 0) {
      window.location.assign("http://127.0.0.1:3001/cyberpunk_front.html");
    } else {
      setChapter(step);
    }
  }

  useEffect(() => {
    if (!embedded || window.parent === window) return;
    let origin: string;
    try { origin = new URL(document.referrer).origin; } catch { return; }
    if (!allowedSceneOrigin(origin)) return;
    sceneOrigin.current = origin;
    const send = (data: Record<string, unknown>) => window.parent.postMessage({ channel: SCENE_CHANNEL, ...data }, origin);
    function receive(event: MessageEvent) {
      if (event.source !== window.parent || event.origin !== origin || event.data?.channel !== SCENE_CHANNEL) return;
      if (event.data.type === "chapter" && isSceneChapter(event.data.chapter)) {
        setApproval(null);
        if (event.data.chapter > 0) setChapter(event.data.chapter);
      }
    }
    let pointerFrame = 0;
    let pointer = { x: 0, y: 0, pointerType: "mouse" };
    function move(event: PointerEvent) {
      pointer = { x: event.clientX, y: event.clientY, pointerType: event.pointerType };
      if (!pointerFrame) pointerFrame = requestAnimationFrame(() => { pointerFrame = 0; send({ type: "pointer", ...pointer }); });
    }
    function leave() {
      if (pointerFrame) cancelAnimationFrame(pointerFrame);
      pointerFrame = 0;
      send({ type: "pointerleave" });
    }
    window.addEventListener("message", receive);
    window.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    window.addEventListener("blur", leave);
    send({ type: "ready" });
    return () => {
      sceneOrigin.current = null;
      if (pointerFrame) cancelAnimationFrame(pointerFrame);
      window.removeEventListener("message", receive);
      window.removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", leave);
      window.removeEventListener("blur", leave);
    };
  }, [embedded]);

  useEffect(() => {
    if (embedded) window.scrollTo({ top: 0, behavior: "instant" });
  }, [chapter, embedded]);

  useEffect(() => {
    const controller = new AbortController();
    request<Health>("/api/health", { signal: controller.signal }).then(setHealth).catch(e => {
      if (e.name !== "AbortError") setHealthError(message(e));
    });
    const existingJob = new URLSearchParams(window.location.search).get("job");
    if (existingJob && /^[a-f0-9]{32}$/.test(existingJob)) {
      request<Job>("/api/jobs/" + existingJob, { signal: controller.signal }).then(async saved => {
        const repository = await request<RepositorySummary>("/api/repositories/" + saved.repository_id, { signal: controller.signal });
        setRepo(repository);
        setJob(saved);
      }).catch(e => { if (e.name !== "AbortError") setError(message(e)); });
    }
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!jobId || !jobStatus || !["queued", "running"].includes(jobStatus)) return;
    const controller = new AbortController();
    let inFlight = false;
    async function poll() {
      if (inFlight) return;
      inFlight = true;
      try {
        const result = await request<Job>("/api/jobs/" + jobId, { signal: controller.signal });
        setJob(result);
        setPollError("");
      } catch (e) {
        if (!(e instanceof DOMException && e.name === "AbortError")) setPollError("Status refresh failed; the job may still be running. " + message(e));
      } finally { inFlight = false; }
    }
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [jobId, jobStatus]);

  useEffect(() => {
    if (!repoId) return;
    const controller = new AbortController();
    let fetching = false;
    async function refresh() {
      if (fetching) return;
      fetching = true;
      try { setInvestigation(await request<Investigation>("/api/repositories/" + repoId + "/investigation", {signal:controller.signal})); }
      catch (e) { if (!(e instanceof DOMException && e.name === "AbortError")) setPollError(message(e)); }
      finally { fetching = false; }
    }
    void refresh();
    const timer = reevaluating ? setInterval(() => void refresh(), 2000) : null;
    return () => { controller.abort(); if (timer) clearInterval(timer); };
  }, [repoId, reevaluating]);

  async function load(kind: "zip" | "git" | "sample" | "claims") {
    setBusy(kind === "sample" ? "Loading and analyzing trusted sample?" : "Importing and statically analyzing source?");
    setError("");
    try {
      let result: RepositorySummary;
      if (kind === "zip") {
        if (!file || !file.name.toLowerCase().endsWith(".zip") || file.size > 20 * 1024 * 1024) throw new Error("Select one ZIP of 20 MiB or less.");
        const body = new FormData(); body.append("file", file);
        result = await request<RepositorySummary>("/api/repositories/upload", { method: "POST", body });
      } else if (kind === "git") {
        result = await post<RepositorySummary>("/api/repositories/import-git", { url: gitUrl });
      } else {
        result = await post<RepositorySummary>("/api/repositories/sample" + (kind === "claims" ? "?sample_id=claims_demo" : ""), {});
      }
      setRepo(result); setPlan(null); setJob(null); setReview("pending"); setConsent(false); setConnection(""); setPollError("");
      setInvestigation(null); setIntendedChanges([]);
      setObjective(kind === "claims" ? "Correct the inclusive age-65 eligibility mismatch proven by independent policy trials. Preserve duplicates, rounding, review and error behavior." : "Modernize one small Python construct while preserving observable behavior.");
      window.history.replaceState(null, "", window.location.pathname);
    } catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  async function generatePlan() {
    if (!repo || !consent) return;
    setBusy("Requesting a bounded modernization plan from NVIDIA?"); setError("");
    try {
      setPlan(await post<Plan>("/api/repositories/" + repo.id + "/plans", { consent_to_model: true, objective, intended_rule_changes: intendedChanges }));
    } catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  async function execute(confirmed = false) {
    if (!plan || !consent) return;
    const semanticScope = (plan.intended_rule_changes ?? []).length ? " Explicitly approve intended business-rule changes under policy " + (plan.policy_version ?? "unavailable") + ": " + plan.intended_rule_changes.join(", ") + "." : " Preserve existing business behavior.";
    if (!confirmed) {
      setApproval({ kind: "execute", planId: plan.id, repositoryId: plan.repository_id,
        description: "Approve the displayed plan and modify an isolated copy of " + plan.allowed_paths.join(", ") + "?" + semanticScope + " " + (repo?.trusted ? "The built-in sample will run in restricted Docker containers." : "This untrusted repository will NOT execute; verification will be skipped.") });
      return;
    }
    setBusy("Approving plan and starting execution?"); setError("");
    try {
      if (plan.approval_status !== "approved") {
        const approved = await post<Plan>("/api/plans/" + plan.id + "/approve", { approved: true, approved_rule_changes: plan.intended_rule_changes ?? [] });
        setPlan(approved);
      }
      const started = await post<Job>("/api/plans/" + plan.id + "/execute", { approved: true });
      setJob(started);
      window.history.replaceState(null, "", "?job=" + started.id);
      setReview("pending");
    } catch (e) { setError(message(e) + " If execution was accepted before a connection failure, retry this action to recover the same job."); }
    finally { setBusy(null); }
  }

  async function checkModel() {
    setBusy("Checking NVIDIA final-response connectivity?"); setError("");
    try { const result = await post<{ message: string }>("/api/model/check", { consent_to_model: true }); setConnection(result.message); }
    catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  async function exportPatch() {
    if (!job) return;
    setBusy("Downloading patch?"); setError("");
    try { await downloadPatch(job.id); }
    catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  async function investigate() {
    if (!repo || !consent) return;
    setBusy("Investigating source-grounded rules, synthetic signals, and independent Docker trials..."); setError("");
    setPlan(null); setIntendedChanges([]);
    try {
      setInvestigation(await post<Investigation>("/api/repositories/" + repo.id + "/investigate", {
        consent_to_model: true, use_model: true, signals_dataset: "both",
      }));
    } catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  async function importWindow(dataset: "before" | "after") {
    if (!repo) return;
    setBusy("Ingesting the synthetic " + dataset + " window; any meaningful drift queues bounded trials, never edits."); setError(""); setPlan(null);
    try {
      await post("/api/repositories/" + repo.id + "/signals/import", {dataset, consent_to_model:consent});
      setInvestigation(await request<Investigation>("/api/repositories/" + repo.id + "/investigation"));
    } catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  async function approveFuturePolicy(confirmed = false) {
    if (!repo) return;
    if (!confirmed) {
      setApproval({ kind: "policy", repositoryId: repo.id,
        description: "Explicitly approve pinned fictional policy 1.1: eligibility starts at age 66. This updates the intended policy and runs re-evaluation only. Code changes still require a separately approved plan." });
      return;
    }
    setBusy("Activating the explicitly approved fictional policy and queuing re-evaluation..."); setError(""); setPlan(null); setIntendedChanges([]);
    try {
      setInvestigation(await post<Investigation>("/api/repositories/" + repo.id + "/rules/policy-versions", {
        version:"1.1", approved:true, approved_rule_ids:["rule-age-eligibility"], consent_to_model:consent,
      }));
    } catch (e) { setError(message(e)); }
    finally { setBusy(null); }
  }

  const nextDisabled = chapter === 1 || chapter === 2 ? !repo : chapter === 3 ? !job : chapter === 4 ? !job || running : false;

  function confirmApproval() {
    if (!approval) return;
    setApproval(null);
    if (repo?.id !== approval.repositoryId || (approval.kind === "execute" && plan?.id !== approval.planId)) {
      setError("The repository or plan changed. Review the current scope and approve again.");
      return;
    }
    if (approval.kind === "execute") void execute(true);
    else void approveFuturePolicy(true);
  }

  return <main className={embedded ? "gp-workspace" : undefined} data-workspace-step={embedded ? chapter : undefined}>
    <header className={embedded ? "gp-heading" : undefined}>
      {embedded && <p className={"gp-eyebrow"}>GHOSTPATCH / LIVE BACKEND / DIAMOND {chapter + 1} OF 6</p>}
      <h1>{embedded ? WORKSPACE_STEPS[chapter] : "GhostPatch"}</h1>
      {!embedded && <p>Modernize legacy Python. Review the plan, exact changes, and actual validation evidence.</p>}
      {!embedded && <p><a className="scene-link" href="/cyberpunk">Open cyberpunk workflow</a></p>}
      {embedded && <p className={"gp-repository"}>{repo ? "Repository: " + repo.name : "No repository selected"}{job ? " | Job: " + job.status : ""}</p>}
    </header>
    <div className="notice" hidden={embedded && chapter !== 1}><strong>Local MVP — real backend</strong><p>Uploads and GitHub imports receive static analysis only. Only the built-in developer-controlled sample may execute in Docker. No mock results are displayed.</p></div>
    <div aria-live="polite" className={embedded ? "gp-status" : undefined}>
      {health && <p className="muted">Backend connected ? NVIDIA {health.nvidia_configured ? "configured" : "not configured"} ? Docker {health.docker.available ? "ready" : health.docker.reason}</p>}
      {healthError && <p className="error">{healthError}</p>}
      {busy && <p role="status">{busy}</p>}
      {reevaluating && <p role="status">Bounded re-evaluation is running. No code edits are authorized by drift alone.</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {pollError && <p className="warning" role="alert">{pollError}</p>}
      {connection && <p className="success">{connection}</p>}
    </div>

    <div className={embedded && chapter === 1 ? "gp-import-layout" : undefined}>
    <section hidden={!show(1)} aria-labelledby="import-title"><h2 id="import-title">1. Import and analyze</h2>
      <div className={embedded ? "columns " + "gp-import-columns" : "columns"}><div>
        <label htmlFor="zip">Repository ZIP ? maximum 20 MiB</label>
        <input id="zip" type="file" accept=".zip" disabled={locked} onChange={e => { setFile(e.target.files?.[0] ?? null); setError(""); }} />
        {file && <p className="muted">Selected: {file.name}</p>}
        <div className="row"><button disabled={locked || !file} onClick={() => void load("zip")}>Analyze ZIP</button></div>
      </div><div>
        <label htmlFor="git">Public GitHub repository URL</label>
        <input id="git" type="url" placeholder="https://github.com/owner/repository" value={gitUrl} disabled={locked} onChange={e => setGitUrl(e.target.value)} />
        <div className="row"><button disabled={locked || !gitUrl.trim()} onClick={() => void load("git")}>Analyze GitHub</button></div>
      </div></div>
      <p className="muted">Public HTTPS GitHub URLs only. Small UTF-8 Python repositories; no credentials, submodules, nested archives, or dependency installation.</p>
      <div className="row"><button className="secondary" disabled={locked} onClick={() => void load("sample")}>Load trusted sample</button><span className="muted">Synthetic expense reports ? 12 tests ? 5 behavior cases</span></div>
      <div className="row"><button className="secondary" disabled={locked} onClick={() => void load("claims")}>Load claims policy demo</button><span className="muted">Fictional eligibility | Independent policy | Synthetic usage signals</span></div>
      {repo && <p className="success">Analyzed {repo.name}. Continue to Static analysis to review the findings.</p>}
    </section>

    <section hidden={embedded && chapter !== 1 && chapter !== 3} aria-labelledby="model-title"><h2 id="model-title">Nemotron connection validation</h2>
      <label className="check"><input type="checkbox" checked={consent} disabled={locked} onChange={e => setConsent(e.target.checked)} /><span>I allow relevant source excerpts and validation failures to be sent to the configured NVIDIA hosted model for planning, patching, and up to two repairs. Common secret patterns are redacted, but redaction is not a confidentiality guarantee.</span></label>
      <button className="secondary" disabled={locked || !consent} onClick={() => void checkModel()}>Test NVIDIA connection</button>
      <p className="muted">This makes a real Nemotron final-response check. It does not generate a plan, edit code, or run Docker tests.</p>
    </section>

    {repo && <section hidden={!show(2)} aria-labelledby="analysis-title"><h2 id="analysis-title">2. Static analysis ? {repo.name}</h2>
      <p>{repo.file_count} retained files ? {repo.analysis.python_file_count} Python files ? {repo.analysis.findings.length} heuristic findings</p>
      <p className={repo.trusted ? "success" : "warning"}>{repo.execution_policy}</p>
      <p className="muted">Static findings are review suggestions, not verified vulnerabilities or a security score.</p>
      {repo.analysis.warnings.map((warning, i) => <p key={i} className="warning">{warning}</p>)}
      {repo.analysis.findings.length ? <ul>{repo.analysis.findings.map(finding => <li key={finding.id}>
        <strong>{finding.severity.toUpperCase()}</strong> ? <code>{finding.file_path}{finding.line ? ":" + finding.line : ""}</code> ? {finding.explanation}
        <details><summary>Evidence and recommendation</summary><pre>{finding.evidence}</pre><p>{finding.recommendation}</p></details>
      </li>)}</ul> : <p>No findings from the available checks. This does not establish correctness or security.</p>}
      <details><summary>Files and local dependencies</summary><pre>{repo.analysis.files.join("\n")}</pre><pre>{repo.analysis.local_dependencies.map(edge => edge.source + " imports " + edge.target).join("\n") || "No local import edges found."}</pre></details>
    </section>}

    <section hidden={!show(3)} aria-labelledby="plan-title"><h2 id="plan-title">3. Nemotron plan and approval</h2>
      {repo && <div className="panel"><h3>Ghost Memory / Ghost Signals / Ghost Trials</h3>
        <p className="muted">Investigate before planning. Synthetic metrics propose hypotheses; only independently grounded trials can establish a policy mismatch.</p>
        <button className="secondary" disabled={locked || !consent || !!job} onClick={() => void investigate()}>Investigate rules, signals &amp; trials</button>
        {repo.sample_id === "claims_demo" && <><div className="row">
          <button className="secondary" disabled={locked} onClick={() => void importWindow("before")}>Import synthetic before window</button>
          <button className="secondary" disabled={locked} onClick={() => void importWindow("after")}>Import synthetic after window</button>
          <button className="secondary" disabled={locked || investigation?.rulebook.policy_version === "1.1"} onClick={() => void approveFuturePolicy()}>Approve fictional policy 1.1</button>
        </div><p className="muted">Optional stable identities enable declared-cohort return metrics. These synthetic version labels are not real-user tracking or measured patch impact.</p></>}
        <HarnessEvidence investigation={investigation} report={newerEvidence ? investigation?.report ?? null : job?.results.behavior_report ?? null} intended={intendedChanges}
          disabled={locked || (!!job && !followupReady)} canProposeChange={!job || !!followupReady} onSelect={ids => { setIntendedChanges(ids); setPlan(null); }} />
      </div>}
      <label htmlFor="objective">Modernization objective</label>
      <textarea id="objective" value={objective} disabled={locked || (!!job && !followupReady)} maxLength={1000} onChange={e => { setObjective(e.target.value); setPlan(null); }} />
      <div className="row"><button disabled={locked || !repo || !consent || objective.length < 10 || (!!job && !followupReady)} onClick={() => void generatePlan()}>Generate plan</button></div>
      {followupReady && <p className="warning">New independent evidence requires review. Select the specific policy correction and generate a fresh follow-up plan; no automatic repair has run.</p>}
      {job && !plan && <p className="muted">Viewing a saved job. Its original plan is retained on the backend; load a fresh repository to generate another plan.</p>}
      {!repo && <p className="muted">Analyze a repository or load the trusted sample first.</p>}
      {plan && <div className="panel"><h3>{plan.proposal.objective}</h3>
        {(plan.intended_rule_changes ?? []).length > 0 && <p className="warning">Intended business-rule changes requiring explicit approval: {plan.intended_rule_changes.join(", ")}</p>}
        <ul>{plan.proposal.changes.map(change => <li key={change.path}><strong>{change.priority}</strong> ? <code>{change.path}</code><p>{change.description}</p></li>)}</ul>
        <h3>Risks</h3><ul>{plan.proposal.risks.map((risk, i) => <li key={i}>{risk}</li>)}</ul>
        <h3>Validation strategy</h3><ul>{plan.proposal.test_strategy.map((test, i) => <li key={i}>{test}</li>)}</ul>
        {!repo?.trusted && <p className="warning">Code execution is prohibited for this source. Any exported patch will be unverified.</p>}
        <button disabled={locked || !consent || (!!job && !followupReady)} onClick={() => void execute()}>Approve &amp; execute</button>
      </div>}
    </section>

    {job && <section hidden={!show(4)} aria-labelledby="execution-title"><h2 id="execution-title">4. Execution ? {job.status}</h2>
      <p>Job <code>{job.id}</code> ? Verification: <strong>{job.results.verification}</strong></p>
      {running && <p role="status">Work is running on the backend. This page polls for actual progress; leaving it does not cancel the job.</p>}
      {job.error && <p className="error">{job.error}</p>}
      <ol>{job.events.map(event => <li key={event.id}><small>{new Date(event.timestamp).toLocaleTimeString()} ? {event.phase} ? {event.status}</small><p>{event.message}</p></li>)}</ol>
      <div className="columns"><TestEvidence title="Baseline tests" run={job.results.baseline} /><TestEvidence title="Modified tests" run={job.results.modified} /></div>
      {job.results.repairs.length > 0 && <TestEvidence title="Initial modified tests before repair" run={job.results.initial_modified} />}
      {job.results.repairs.map(repair => <details key={repair.attempt}><summary>Repair {repair.attempt} of 2</summary><p>{repair.summary}</p>{repair.error && <p className="error">{repair.error}</p>}<TestEvidence title={"Repair " + repair.attempt + " validation"} run={repair.validation} /></details>)}
      {job.results.behavior_comparison.length > 0 && <><h3>Observed behavior comparisons</h3><ul>{job.results.behavior_comparison.map(item => <li key={item.case_id}><details><summary>{item.case_id}: {item.status}</summary><pre>{JSON.stringify({ baseline: item.baseline, modified: item.modified }, null, 2)}</pre></details></li>)}</ul></>}
      {job.results.warnings.map((warning, i) => <p key={i} className="warning">{warning}</p>)}
    </section>}

    {job && !running && <section hidden={!show(5)} aria-labelledby="result-title"><h2 id="result-title">5. Review and export</h2>
      {job.results.diffs.length ? job.results.diffs.map(diff => <details key={diff.path} open><summary>{diff.path}</summary><pre aria-label={"Unified diff for " + diff.path}>{diff.unified_diff}</pre></details>) : <p>No patch was produced.</p>}
      <p className="muted">Review is session-only. Approving enables download; it does not merge or deploy. Rejecting leaves the isolated evidence available and disables export.</p>
      <p>Review decision: <strong>{review}</strong></p>
      <div className="row"><button className="secondary" disabled={locked || !job.results.diffs.length} onClick={() => setReview("rejected")}>Reject patch</button>
        <button disabled={locked || !job.results.diffs.length} onClick={() => setReview("approved")}>Approve patch</button>
        <button disabled={locked || review !== "approved" || !job.results.diffs.length} onClick={() => void exportPatch()}>Download patch</button>
      </div>
      <p className="muted">To start over, analyze a new import or load a fresh trusted sample above. Local IDs expire on service restart or workspace cleanup.</p>
    </section>}
    </div>
    {embedded && chapter === 2 && !repo && <div className={"gp-empty"}><p>Import a repository or load a trusted sample to see real analysis findings.</p><button onClick={() => navigate(1)}>Go to import</button></div>}
    {embedded && chapter === 4 && !job && <div className={"gp-empty"}><p>No execution has started. Generate a plan and explicitly approve it first.</p><button onClick={() => navigate(3)}>Go to plan and approval</button></div>}
    {embedded && chapter === 5 && (!job || running) && <div className={"gp-empty"}><p>{running ? "The backend job is still running. Review and export appear after it finishes." : "No results yet. Complete an approved execution to inspect its actual diff and test evidence."}</p><button onClick={() => navigate(job ? 4 : 3)}>{job ? "View execution" : "Go to plan and approval"}</button></div>}
    {embedded && <nav className={"gp-navigation"} aria-label="Backend workflow steps">
      <button className="secondary" onClick={() => navigate(chapter - 1)}>{chapter === 1 ? "Back to intro" : "Previous"}</button>
      <span>Diamond {chapter + 1} / 6 · Repository and job state stay available between pages.</span>
      <button disabled={chapter < 5 && nextDisabled} onClick={() => navigate(chapter === 5 ? 1 : chapter + 1)}>{chapter === 5 ? "Back to import" : "Next: " + WORKSPACE_STEPS[chapter + 1]}</button>
    </nav>}
    {approval && <ApprovalDialog approval={approval} onCancel={() => setApproval(null)} onApprove={confirmApproval} />}
  </main>;
}
