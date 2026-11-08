from dataclasses import replace
import io
import stat
import zipfile

import pytest

from app.errors import GhostPatchError
from app.loader import RepositoryLoader, github_url
from app.paths import safe_relative
from app.store import fingerprints
from conftest import zip_bytes


@pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", "C:/file.py", "a\\b.py", "a/../b.py", "a//b.py", "CON.py", "folder/NUL", "a.py:stream", "file.py ", "x\x00.py"])
def test_reject_unsafe_paths(path):
    with pytest.raises(GhostPatchError):
        safe_relative(path)


@pytest.mark.parametrize("path", ["../outside.py", "/outside.py", "C:/outside.py", "CON.py"])
def test_archive_path_rejection_cleans_workspace(loader, store, path):
    with pytest.raises(GhostPatchError):
        loader.zip(zip_bytes({path: "print('never execute')"}), "bad.zip")
    assert store.repositories == {}
    assert list(store.settings.workspace_root.iterdir()) == []


def test_reject_symlink(loader):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        entry = zipfile.ZipInfo("link.py")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, "../target")
    with pytest.raises(GhostPatchError, match="symlinks"):
        loader.zip(buffer.getvalue(), "symlink.zip")


def test_reject_duplicates_and_nested_archives(loader):
    for files in ({"A.py": "x=1", "a.py": "x=2"}, {"main.py": "x=1", "nested.zip": "not allowed"}):
        with pytest.raises(GhostPatchError):
            loader.zip(zip_bytes(files), "bad.zip")


def test_limits(loader, store, settings):
    limited = RepositoryLoader(store, replace(settings, max_files=1))
    with pytest.raises(GhostPatchError):
        limited.zip(zip_bytes({"a.py": "x=1", "b.py": "x=2"}), "count.zip")
    limited = RepositoryLoader(store, replace(settings, max_file_bytes=3))
    with pytest.raises(GhostPatchError):
        limited.zip(zip_bytes({"a.py": "x = 100"}), "size.zip")


def test_skips_sensitive_and_binary_files_and_preserves_original(loader):
    repo = loader.zip(zip_bytes({"project/main.py": "raise RuntimeError('must never execute')\n",
        "project/.env": "SECRET=not-a-real-secret", "project/node_modules/a.py": "bad", "project/image.py": b"\x00binary"}), "input.zip")
    assert set(repo.hashes) == {"main.py"}
    assert repo.trusted is False
    assert fingerprints(repo.original) == fingerprints(repo.working)
    assert repo.analysis.python_file_count == 1


def test_uploaded_sample_never_gains_trust(loader, settings):
    files = {p.relative_to(settings.sample_root).as_posix(): p.read_bytes() for p in settings.sample_root.rglob("*") if p.is_file()}
    assert loader.zip(zip_bytes(files), "legacy_reports.zip").trusted is False
    assert loader.sample().trusted is True


@pytest.mark.parametrize("url", ["http://github.com/a/b", "https://evil.com/a/b", "https://github.com.evil/a/b", "https://u:p@github.com/a/b", "https://github.com/a/b/tree/main", "https://github.com/a/b?x=1", "https://github.com:443/a/b", "https://github.com/a/..", "file:///tmp/repo"])
def test_git_url_allowlist(url):
    with pytest.raises(GhostPatchError):
        github_url(url)


def test_git_url_normalization():
    assert github_url("https://github.com/pypa/sampleproject/") == "https://github.com/pypa/sampleproject.git"
