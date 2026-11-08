"""Source-grounded business-rule candidates, independent policy, and history."""
import ast
import hashlib
import json
from pathlib import Path

from .errors import GhostPatchError, redact
from .harness_schemas import BusinessRule, RuleBook, RuleCandidate, RuleConflict, RuleHistory, SourceCandidate, SourceReference
from .paths import within
from .store import Repository, now


def stable_id(prefix: str, value) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return prefix + "-" + hashlib.sha256(encoded).hexdigest()[:16]


def validate_reference(repo: Repository, candidate: SourceCandidate) -> SourceReference:
    if candidate.file_path not in repo.hashes:
        raise GhostPatchError("Rule reference names a file absent from the original snapshot.")
    raw = within(repo.original, candidate.file_path).read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if candidate.line_end < candidate.line_start or candidate.line_end > len(lines) or candidate.line_end - candidate.line_start > 60:
        raise GhostPatchError("Rule reference has an invalid or oversized line range.")
    excerpt = "\n".join(lines[candidate.line_start - 1:candidate.line_end])
    if candidate.quote.strip() != excerpt.strip():
        raise GhostPatchError("Rule quote does not match the cited source lines.")
    if len(excerpt) > 2000:
        raise GhostPatchError("Rule source excerpt exceeds the evidence limit.")
    if candidate.function:
        try:
            tree = ast.parse(text)
            matches = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name == candidate.function and n.lineno <= candidate.line_start
                       and (n.end_lineno or n.lineno) >= candidate.line_end]
        except (SyntaxError, RecursionError):
            matches = []
        if not matches:
            raise GhostPatchError("Rule function reference does not contain the cited lines.")
    path = candidate.file_path
    role = "test" if path.startswith("tests/") or Path(path).name.startswith("test_") else "code" if path.endswith(".py") else "policy" if repo.trusted and Path(path).name in {"policy.json", "POLICY.md"} else "documentation"
    data = candidate.model_dump()
    data["quote"] = excerpt
    return SourceReference(**data,
        sha256=hashlib.sha256(excerpt.encode()).hexdigest(), file_sha256=hashlib.sha256(raw).hexdigest(), role=role)


def reference(repo: Repository, path: str, start: int, end: int | None = None, function: str | None = None) -> SourceReference:
    end = end or start
    lines = (repo.original / path).read_text(encoding="utf-8").splitlines()
    return validate_reference(repo, SourceCandidate(file_path=path, function=function, line_start=start, line_end=end,
                                                   quote="\n".join(lines[start - 1:end])))


def transition(rule: BusinessRule, status: str, reason: str, evidence_ids: list[str], *, independent: bool = False) -> None:
    if status not in {"hypothesis", "verified", "conflicted", "superseded"}:
        raise GhostPatchError("Invalid rule status.")
    if rule.status == "superseded" and status != rule.status:
        raise GhostPatchError("A superseded rule cannot be silently revived.")
    if status == "verified" and not independent:
        raise GhostPatchError("Verifying a rule requires independent policy/test evidence.")
    if rule.status == status:
        return
    rule.version += 1
    rule.status = status
    rule.history.append(RuleHistory(version=rule.version, status=status, timestamp=now(), reason=reason, evidence_ids=evidence_ids))


def add_conflict(book: RuleBook, rule_ids: list[str], description: str, basis: str, evidence_ids: list[str], *, observed=False):
    key = stable_id("conflict", [sorted(rule_ids), basis, description])
    if any(c.id == key for c in book.conflicts):
        return
    book.conflicts.append(RuleConflict(id=key, rule_ids=rule_ids, description=description, basis=basis,
        status="observed" if observed else "proposed", evidence_ids=evidence_ids, policy_version=book.policy_version))
    book.version += 1
    if observed:
        for rule in book.rules:
            if rule.id in rule_ids and rule.kind != "intended_policy" and rule.status != "superseded":
                transition(rule, "conflicted", description, evidence_ids)


def policy_fixture(repo: Repository) -> dict | None:
    # This file is authoritative only inside the independently pinned sample.
    if not repo.trusted or repo.sample_id != "claims_demo":
        return None
    repo.assert_original()
    state = repo.investigation
    version = getattr(state, "active_policy_version", "1.0")
    filename = {"1.0":"policy.json", "1.1":"policy_v1_1.json"}.get(version)
    if filename is None:
        raise GhostPatchError("Unsupported approved policy version.", 409)
    return json.loads((repo.original / filename).read_text())


class GhostMemory:
    def deterministic(self, repo: Repository) -> RuleBook:
        repo.assert_original()
        book = RuleBook(repository_id=repo.id, source_digest=stable_id("source", repo.hashes),
            warnings=["Code-derived rules describe observed implementation, not automatically correct policy."])
        for path in sorted(repo.hashes):
            if not path.endswith(".py") or len(book.rules) >= 24:
                continue
            source = (repo.original / path).read_text(encoding="utf-8")
            if len(source) > 40000:
                continue
            try:
                tree = ast.parse(source)
            except (SyntaxError, RecursionError):
                continue
            functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for node in ast.walk(tree):
                if len(book.rules) >= 24:
                    break
                if not isinstance(node, (ast.If, ast.Assert)) and not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "quantize"):
                    continue
                try:
                    expression = ast.unparse(node.test) if isinstance(node, (ast.If, ast.Assert)) else ast.unparse(node)
                except RecursionError:
                    continue
                fn = next((f.name for f in functions if f.lineno <= node.lineno <= (f.end_lineno or f.lineno)), None)
                if fn and len(fn) > 100:
                    continue
                if len(source.splitlines()[node.lineno - 1]) > 2000:
                    continue
                try:
                    ref = reference(repo, path, node.lineno, function=fn)
                except GhostPatchError:
                    continue
                kind = "test_expectation" if ref.role == "test" else "observed_implementation"
                rule = BusinessRule(id=stable_id("rule", [path, fn, expression]), title=("Test expectation: " if ref.role == "test" else "Observed condition: ") + expression[:120],
                    description="Source contains: " + expression[:800], kind=kind, references=[ref], confidence=0.6,
                    uncertainty="Observed in source only; intended business meaning and completeness require independent evidence.", origin="deterministic")
                rule.history.append(RuleHistory(version=1, status="hypothesis", timestamp=now(), reason="Deterministic source observation.", evidence_ids=[ref.sha256]))
                book.rules.append(rule)
        policy = policy_fixture(repo)
        if policy:
            book.policy_version = policy["version"]
            for entry in policy["rules"]:
                ref = reference(repo, "POLICY.md", entry["line"], function=None)
                rule = BusinessRule(id=entry["id"], title=entry["title"], description=entry["description"],
                    kind="intended_policy", references=[ref], confidence=1.0, uncertainty="Authority is limited to this fictional developer-controlled fixture, not real-world policy.",
                    origin="trusted_policy", status="verified")
                rule.history.append(RuleHistory(version=1, status="verified", timestamp=now(), reason="Explicit independent developer-controlled policy fixture.", evidence_ids=[ref.sha256], policy_version=policy["version"]))
                book.rules.append(rule)
            for entry in policy["rules"]:
                predicate = entry.get("expected_predicate")
                if not predicate:
                    continue
                words = predicate.split()
                competing = next((r for r in book.rules if r.kind == "observed_implementation" and all(word in r.description for word in (words[0], words[-1])) and predicate not in r.description), None)
                if competing:
                    add_conflict(book, [entry["id"], competing.id],
                        "Observed predicate differs from the documented policy: " + predicate + ". Treat as competing evidence until executed trials.",
                        "source_contradiction", [ref.sha256 for ref in competing.references])
        return book

    def context(self, repo: Repository, book: RuleBook) -> dict:
        files, budget = {}, 17000
        for path in sorted(repo.hashes, key=lambda p: (p.startswith("tests/"), p)):
            if Path(path).suffix not in {".py", ".md", ".json"} or "signals_" in path or "behavior_cases" in path:
                continue
            active = policy_fixture(repo)
            if path == "signals_windows.json" or (path == "policy_v1_1.json" and (not active or active["version"] != "1.1")) or (path == "policy.json" and active and active["version"] == "1.1"):
                continue
            text = (repo.original / path).read_text(encoding="utf-8")
            if len(text) > budget:
                continue
            budget -= len(text)
            files[path] = {"lines": [{"number": number, "text": redact(line)} for number, line in enumerate(text.splitlines(), 1)],
                           "line_count": len(text.splitlines())}
        return {"files": files, "active_policy_version":book.policy_version, "known_rules": [{"id": r.id, "kind": r.kind, "title": r.title} for r in book.rules],
                "instruction": "Return hypotheses with exact copied line quotes and real function names (null for docs). Code is observation, not proof of policy."}

    def merge_model(self, repo: Repository, book: RuleBook, extraction) -> int:
        added = 0
        validated = 0
        for candidate in extraction.rules:
            try:
                refs = [validate_reference(repo, ref) for ref in candidate.references]
            except GhostPatchError as exc:
                book.warnings.append("Rejected model rule: " + exc.message)
                continue
            validated += 1
            key = stable_id("rule", [(r.file_path, r.function, r.line_start, r.line_end, r.sha256) for r in refs])
            if any(r.id == key for r in book.rules):
                continue
            rule = BusinessRule(id=key, title=redact(candidate.title), description=redact(candidate.description), kind=candidate.kind,
                references=refs, confidence=candidate.confidence, uncertainty=redact(candidate.uncertainty), origin="nemotron")
            rule.history.append(RuleHistory(version=1, status="hypothesis", timestamp=now(), reason="Source-validated model hypothesis; not an authoritative policy.", evidence_ids=[r.sha256 for r in refs]))
            book.rules.append(rule)
            added += 1
        book.model_status = "succeeded" if validated else "failed"
        book.model_error = None if validated else "All model rule references were rejected; deterministic candidates remain available."
        book.warnings[:] = book.warnings[-50:]
        if added: book.version += 1
        return added


def approve_policy_version(repo, state, version, approved_rule_ids):
    """Activate only an explicit human-approved, pinned fictional fixture."""
    if not repo.trusted or repo.sample_id != "claims_demo":
        raise GhostPatchError("Approved policy fixtures are available only for the pinned claims sample.", 403)
    if set(approved_rule_ids) != {"rule-age-eligibility"}:
        raise GhostPatchError("Explicit approval of the eligibility policy rule is required.", 409)
    if state.active_policy_version == version:
        return False
    repo.assert_original()
    if version not in {"1.0","1.1"}:
        raise GhostPatchError("Unknown pinned policy version.")
    old_version=state.active_policy_version
    filename="policy.json" if version=="1.0" else "policy_v1_1.json"
    fixture=json.loads((repo.original/filename).read_text())
    state.active_policy_version=version
    state.rulebook.policy_version=version
    changed=next(item for item in fixture["rules"] if item["id"]=="rule-age-eligibility")
    rule=next(item for item in state.rulebook.rules if item.id=="rule-age-eligibility")
    ref=reference(repo,"POLICY.md",changed["line"])
    rule.description=changed["description"]
    rule.references=[ref]
    rule.version+=1
    rule.history.append(RuleHistory(version=rule.version,status="verified",timestamp=now(),
        reason="Human explicitly approved the independently pinned fictional policy version.",
        evidence_ids=[ref.sha256],policy_version=version))
    rule.status="verified"
    for conflict in state.rulebook.conflicts:
        if "rule-age-eligibility" in conflict.rule_ids and conflict.policy_version != version:
            conflict.status="resolved"
    state.rulebook.version+=1
    state.policy_history.append({"from_version":old_version,"to_version":version,"approved_rule_ids":sorted(approved_rule_ids),
        "approved_at":now(),"evidence_ids":[ref.sha256],"approval":"explicit_human_request"})
    state.revision+=1
    state.trials_model_attempted=False
    # Rebind authority deterministically, never from a model's expected output.
    from .trials import policy_outcome
    for scenario in state.scenarios:
        if scenario.oracle=="approved_policy":
            expected,rule_id=policy_outcome(repo,scenario.input)
            entry=next(r for r in fixture["rules"] if r["id"]==rule_id)
            scenario.expected=expected
            scenario.oracle_reference=reference(repo,"POLICY.md",entry["line"])
    state.signals.model_status="not_requested"
    state.signals.model_error=None
    return True
