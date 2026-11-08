import hashlib

import pytest

from app.errors import GhostPatchError
from app.patcher import apply_patch, collect_diffs
from app.orchestrator import model_context
from app.schemas import Edit, PatchProposal
from app.store import fingerprints
from conftest import zip_bytes


def proposal(repo, path, content, sha=None):
    return PatchProposal(summary="Test patch", edits=[Edit(path=path, original_sha256=sha or hashlib.sha256((repo.working / path).read_bytes()).hexdigest(), new_content=content)])


def test_analysis_grounded_lines_dependencies_and_parse_errors(loader):
    repo = loader.zip(zip_bytes({"main.py": "import helper\ntry:\n    open('a')\nexcept:\n    pass\n# TODO review\n", "helper.py": "x = 1\n", "broken.py": "def ("}), "project.zip")
    analysis = repo.analysis
    assert {"source": "main.py", "target": "helper.py"} in analysis.local_dependencies
    assert any(f.file_path == "main.py" and f.line == 4 and f.severity == "high" for f in analysis.findings)
    assert any(f.category == "parse_error" for f in analysis.findings)
    assert analysis.warnings


def test_patch_changes_only_working_copy_and_emits_diff(loader):
    repo = loader.zip(zip_bytes({"main.py": "value = 1\n"}), "p.zip")
    before = fingerprints(repo.original)
    apply_patch(repo, proposal(repo, "main.py", "value = 2\n"), ["main.py"])
    assert fingerprints(repo.original) == before
    diff = collect_diffs(repo)[0]
    assert "-value = 1" in diff["unified_diff"] and "+value = 2" in diff["unified_diff"]


@pytest.mark.parametrize("content,sha", [("def (", None), ("value=2\n", "0" * 64)])
def test_rejected_patch_is_atomic(loader, content, sha):
    repo = loader.zip(zip_bytes({"main.py": "value=1\n"}), "p.zip")
    original = fingerprints(repo.working)
    with pytest.raises(GhostPatchError):
        apply_patch(repo, proposal(repo, "main.py", content, sha), ["main.py"])
    assert fingerprints(repo.working) == original


def test_patch_cannot_modify_tests_or_escape(loader):
    repo = loader.sample()
    for path in ("tests/test_reports.py", "../outside.py"):
        edit = PatchProposal(summary="Rejected", edits=[Edit(path=path, original_sha256="0" * 64, new_content="x=1\n")])
        with pytest.raises(GhostPatchError):
            apply_patch(repo, edit, [path])


def test_tampered_original_rejected(loader):
    repo = loader.sample()
    (repo.original / "reports.py").write_text("tampered = True\n")
    with pytest.raises(GhostPatchError, match="integrity"):
        collect_diffs(repo)


def test_windows_line_endings_preserve_optimistic_hash(loader):
    repo = loader.zip(zip_bytes({"main.py": b"value = 1\r\n"}), "windows.zip")
    context = model_context(repo, ["main.py"], "Modernize one line.")
    record = context["files"]["main.py"]
    assert record["original_sha256"] == hashlib.sha256(b"value = 1\r\n").hexdigest()
    apply_patch(repo, PatchProposal(summary="Realistic CRLF edit", edits=[Edit(path="main.py", original_sha256=record["original_sha256"], new_content="value = 2\r\n")]), ["main.py"])
    assert b"value = 1\r\n" == (repo.original / "main.py").read_bytes()
