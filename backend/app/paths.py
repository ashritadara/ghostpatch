from pathlib import Path, PurePosixPath
import re

from .errors import GhostPatchError

RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".next", "dist", "build", ".aws", ".ssh"}
ARCHIVES = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar")
TEXT_SUFFIXES = {".py", ".txt", ".md", ".json", ".toml", ".cfg", ".ini", ".csv", ".yaml", ".yml"}


def safe_relative(value: str) -> str:
    if not value or len(value) > 180 or "\\" in value or ":" in value or value.startswith("/"):
        raise GhostPatchError("Unsafe repository path.")
    if re.search(r"[\x00-\x1f\x7f]", value):
        raise GhostPatchError("Control characters are not allowed in paths.")
    parts = value.split("/")
    if len(parts) > 16 or any(p in {"", ".", ".."} or p.endswith((".", " ")) or p.split(".")[0].upper() in RESERVED for p in parts):
        raise GhostPatchError("Unsafe or ambiguous repository path.")
    return str(PurePosixPath(value))


def within(root: Path, relative: str) -> Path:
    relative = safe_relative(relative)
    root = root.resolve()
    target = root / relative
    if any(part.is_symlink() for part in [target, *target.parents] if part != root and root in part.parents):
        raise GhostPatchError("Symlinks are not allowed.")
    if not target.resolve().is_relative_to(root):
        raise GhostPatchError("Path escaped the repository.")
    return target


def ignored(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    return (any(p.lower() in IGNORED_DIRS for p in parts)
            or name.startswith(".env") or name in {"credentials.json", "id_rsa", "id_ed25519"}
            or name.endswith((".pem", ".key", ".p12", ".pfx")))


def source_path(path: str) -> bool:
    name = PurePosixPath(path).name
    return (path.endswith(".py") and not ignored(path)
            and not any(p.lower() in {"test", "tests"} for p in PurePosixPath(path).parts)
            and not name.startswith("test_") and not name.endswith("_test.py")
            and name not in {"conftest.py", "setup.py", "sitecustomize.py", "usercustomize.py"})
