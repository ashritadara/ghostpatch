import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
from urllib.parse import urlsplit
import zipfile

from .analyzer import analyze
from .config import Settings
from .errors import GhostPatchError
from .paths import ARCHIVES, TEXT_SUFFIXES, ignored, safe_relative, within
from .processes import run_bounded
from .store import Repository, Store, fingerprints
from .trusted import sample_spec


def digest(hashes: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def github_url(value: str) -> str:
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.netloc.lower() != "github.com" or url.query or url.fragment:
            raise ValueError()
        parts = url.path.strip("/").split("/")
        if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", parts[0]):
            raise ValueError()
        repo = parts[1].removesuffix(".git")
        if repo in {"", ".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo):
            raise ValueError()
        return f"https://github.com/{parts[0]}/{repo}.git"
    except ValueError:
        raise GhostPatchError("Use an HTTPS github.com/owner/repository URL without credentials, query, fragment, or extra path.") from None


class RepositoryLoader:
    def __init__(self, store: Store, settings: Settings):
        self.store, self.settings = store, settings

    def _finish(self, repo: Repository, contents: dict[str, bytes]) -> Repository:
        if not contents or not any(p.endswith(".py") for p in contents):
            raise GhostPatchError("No supported UTF-8 Python files found.")
        for path, data in contents.items():
            target = within(repo.original, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        shutil.copytree(repo.original, repo.working)
        repo.hashes = fingerprints(repo.original)
        repo.analysis = analyze(repo.original, repo.id)
        return repo

    def _text(self, path: str, data: bytes) -> bool:
        if ignored(path) or Path(path).suffix.lower() not in TEXT_SUFFIXES or b"\x00" in data:
            return False
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    def zip(self, data: bytes, name: str) -> Repository:
        if len(data) > self.settings.max_archive_bytes:
            raise GhostPatchError("ZIP exceeds the 20 MiB compressed upload limit.", 413)
        repo = self.store.allocate(Path(name).name)
        try:
            contents: dict[str, bytes] = {}
            seen = set()
            total = 0
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > self.settings.max_files:
                    raise GhostPatchError("ZIP exceeds the 500-entry limit.", 413)
                for entry in entries:
                    path = safe_relative(entry.filename.rstrip("/"))
                    if path.casefold() in seen:
                        raise GhostPatchError("ZIP contains duplicate/case-colliding paths.")
                    seen.add(path.casefold())
                    mode = entry.external_attr >> 16
                    if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                        raise GhostPatchError("ZIP symlinks and special entries are prohibited.")
                    if entry.flag_bits & 1 or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                        raise GhostPatchError("Encrypted or unsupported ZIP compression is prohibited.")
                    total += entry.file_size
                    if total > self.settings.max_uncompressed_bytes or entry.file_size > self.settings.max_file_bytes:
                        raise GhostPatchError("ZIP exceeds uncompressed or per-file limits.", 413)
                    if entry.file_size > max(1, entry.compress_size) * 200:
                        raise GhostPatchError("ZIP has an excessive compression ratio.", 413)
                    if entry.is_dir():
                        continue
                    if path.lower().endswith(ARCHIVES):
                        raise GhostPatchError("Nested archives are not supported.")
                    if ignored(path):
                        continue
                    with archive.open(entry) as stream:
                        content = stream.read(self.settings.max_file_bytes + 1)
                    if len(content) != entry.file_size:
                        raise GhostPatchError("ZIP entry size mismatch.")
                    if self._text(path, content):
                        contents[path] = content
            prefixes = {p.split("/")[0] for p in contents}
            if len(prefixes) == 1 and all("/" in p for p in contents):
                contents = {p.split("/", 1)[1]: content for p, content in contents.items()}
            return self._finish(repo, contents)
        except (zipfile.BadZipFile, RuntimeError, EOFError, OSError) as exc:
            self.store.remove(repo)
            raise GhostPatchError("ZIP could not be safely read.") from None
        except Exception:
            self.store.remove(repo)
            raise

    def sample(self, sample_id: str = "legacy_reports") -> Repository:
        spec = sample_spec(self.settings, sample_id)
        expected = json.loads(spec.manifest.read_text(encoding="utf-8"))
        actual = fingerprints(spec.root)
        if actual != expected:
            raise GhostPatchError("Built-in sample integrity mismatch; restore the developer-controlled sample before running it.", 409)
        repo = self.store.allocate(sample_id + " (trusted built-in sample)")
        try:
            self._finish(repo, {p: (spec.root / p).read_bytes() for p in actual})
            repo.trusted, repo.trust_digest = True, digest(actual)
            repo.sample_id = sample_id
            return repo
        except Exception:
            self.store.remove(repo)
            raise

    def git(self, value: str) -> Repository:
        url = github_url(value)
        repo = self.store.allocate(url.split("/")[-1].removesuffix(".git"))
        clone = repo.root / "clone"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "GCM_")) and k not in {"NVIDIA_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "SSH_ASKPASS"}}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
        options = ["-c", "credential.helper=", "-c", "http.followRedirects=false", "-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never", "-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=10"]
        try:
            result = run_bounded(["git", *options, "clone", "--depth=1", "--no-tags", "--no-checkout", "--template=", url, str(clone)], timeout=self.settings.git_timeout, env=env, monitor_root=repo.root)
            if result.exit_code or result.limit_reason:
                raise GhostPatchError(result.limit_reason or "Public GitHub clone failed. Private repositories, credentials, and redirects are unsupported.", 422)
            tree = run_bounded(["git", *options, "-C", str(clone), "ls-tree", "-r", "-l", "-z", "HEAD"], timeout=15, env=env, monitor_root=repo.root)
            if tree.exit_code or tree.limit_reason:
                raise GhostPatchError("Could not inspect the Git tree safely.")
            lines = tree.stdout.rstrip("\0").split("\0") if tree.stdout else []
            if len(lines) > self.settings.max_files:
                raise GhostPatchError("Repository exceeds the 500-file limit.", 413)
            contents, total, seen = {}, 0, set()
            # One overall extraction budget, not a fresh network timeout per file.
            import time
            deadline = time.monotonic() + self.settings.git_timeout
            for line in lines:
                metadata, raw_path = line.split("\t", 1)
                mode, kind, sha, size = metadata.split()
                path = safe_relative(raw_path)
                if mode not in {"100644", "100755"} or kind != "blob" or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
                    raise GhostPatchError("Git symlinks, submodules, and special entries are unsupported.")
                if path.casefold() in seen:
                    raise GhostPatchError("Case-colliding Git paths are unsupported.")
                seen.add(path.casefold())
                length = int(size)
                total += length
                if length > self.settings.max_file_bytes or total > self.settings.max_uncompressed_bytes:
                    raise GhostPatchError("Repository exceeds the file or total size limit.", 413)
                if ignored(path) or Path(path).suffix.lower() not in TEXT_SUFFIXES:
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise GhostPatchError("Git extraction timed out.", 422)
                blob = run_bounded(["git", *options, "-C", str(clone), "cat-file", "blob", sha], timeout=min(15, remaining), env=env, monitor_root=repo.root, max_output=self.settings.max_file_bytes + 1)
                if blob.exit_code or blob.limit_reason:
                    raise GhostPatchError("Git object retrieval failed or exceeded limits.", 422)
                content = blob.raw_stdout
                if len(content) != length:
                    raise GhostPatchError("Git object size mismatch.")
                if self._text(path, content):
                    contents[path] = content
            return self._finish(repo, contents)
        except FileNotFoundError:
            self.store.remove(repo)
            raise GhostPatchError("Git is unavailable on the backend PATH.", 503) from None
        except Exception:
            self.store.remove(repo)
            raise
