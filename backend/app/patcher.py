import ast
import difflib
import hashlib
import os
from pathlib import Path

from .errors import GhostPatchError
from .paths import source_path, within
from .schemas import PatchProposal
from .store import Repository, identifier


def allowed_sources(repo: Repository) -> list[str]:
    paths = [p for p in repo.hashes if source_path(p) and (repo.original / p).stat().st_size <= 16000]
    target = "claims.py" if repo.sample_id == "claims_demo" else "reports.py"
    return [p for p in paths if p == target] if repo.trusted else paths[:8]


def apply_patch(repo: Repository, proposal: PatchProposal, allowed: list[str]) -> None:
    repo.assert_original()
    prepared: list[tuple[Path, bytes, bytes]] = []
    seen = set()
    for edit in proposal.edits:
        if edit.path not in allowed or not source_path(edit.path) or edit.path in seen:
            raise GhostPatchError("Model patch targeted an unapproved, duplicate, or protected path.")
        seen.add(edit.path)
        path = within(repo.working, edit.path)
        if not path.is_file():
            raise GhostPatchError("MVP patches may only replace existing allowlisted Python files.")
        before = path.read_bytes()
        if hashlib.sha256(before).hexdigest() != edit.original_sha256:
            raise GhostPatchError("Patch hash mismatch: current source differs from the model's input.", 409)
        content = edit.new_content.encode("utf-8")
        if len(content) > 20000 or b"\x00" in content or content == before:
            raise GhostPatchError("Patch is oversized, binary, or makes no change.")
        try:
            ast.parse(edit.new_content, filename=edit.path)
        except (SyntaxError, ValueError, RecursionError):
            raise GhostPatchError("Proposed patch failed Python syntax validation; nothing was applied.") from None
        diff = list(difflib.unified_diff(before.decode().splitlines(), edit.new_content.splitlines()))
        if len(diff) > 500:
            raise GhostPatchError("Patch exceeds the 500-line change budget.")
        prepared.append((path, before, content))
    try:
        for path, before, content in prepared:
            temporary = path.with_name(path.name + "." + identifier() + ".tmp")
            try:
                temporary.write_bytes(content)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    except Exception:
        for path, before, content in prepared:
            path.write_bytes(before)
        raise


def collect_diffs(repo: Repository, baseline: Path | None = None) -> list[dict[str, str]]:
    repo.assert_original()
    baseline = baseline or repo.original
    if baseline != repo.original:
        from .store import fingerprints
        if repo.execution_snapshots.get(str(baseline.resolve())) != fingerprints(baseline):
            raise GhostPatchError("Frozen job baseline integrity check failed.", 409)
    changes = []
    for relative in sorted(repo.hashes):
        before = within(baseline, relative).read_bytes().decode("utf-8")
        after = within(repo.working, relative).read_bytes().decode("utf-8")
        if before != after:
            # Preserve EOF differences in the downloadable patch.
            lines = list(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                            fromfile=f"a/{relative}", tofile=f"b/{relative}"))
            output = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)
            changes.append({"path": relative, "before": before, "after": after, "unified_diff": output})
    return changes
