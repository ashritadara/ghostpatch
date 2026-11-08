from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


@dataclass(frozen=True)
class Settings:
    workspace_root: Path = PROJECT_ROOT / ".ghostpatch" / "workspaces"
    sample_root: Path = PROJECT_ROOT / "sample_repositories" / "legacy_reports"
    runner_root: Path = BACKEND_ROOT / "runner"
    api_key: str = field(default="", repr=False)
    base_url: str = "https://integrate.api.nvidia.com/v1"
    model: str = ""
    runner_image: str = "ghostpatch-runner:local"
    model_timeout: float = 90
    max_archive_bytes: int = 20 * 1024 * 1024
    max_uncompressed_bytes: int = 50 * 1024 * 1024
    max_file_bytes: int = 1024 * 1024
    max_files: int = 500
    max_repositories: int = 20
    retention_seconds: int = 6 * 60 * 60
    test_timeout: float = 45
    git_timeout: float = 60
    allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BACKEND_ROOT / ".env", override=False)
        return cls(
            api_key=os.getenv("NVIDIA_API_KEY", ""),
            base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            model=os.getenv("NVIDIA_MODEL", ""),
            runner_image=os.getenv("GHOSTPATCH_RUNNER_IMAGE", "ghostpatch-runner:local"),
            model_timeout=min(180, max(10, float(os.getenv("GHOSTPATCH_MODEL_TIMEOUT", "90")))),
        )
