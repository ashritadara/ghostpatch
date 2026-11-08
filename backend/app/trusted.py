from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .errors import GhostPatchError


@dataclass(frozen=True)
class TrustedSample:
    id: str
    root: Path
    editable: str

    @property
    def manifest(self) -> Path:
        return self.root.parent / (self.id + ".sha256.json")


def sample_spec(settings: Settings, sample_id: str) -> TrustedSample:
    if sample_id == "legacy_reports":
        return TrustedSample(sample_id, settings.sample_root, "reports.py")
    if sample_id == "claims_demo":
        return TrustedSample(sample_id, settings.sample_root.parent / "claims_demo", "claims.py")
    raise GhostPatchError("Unknown trusted sample; execution trust cannot be supplied by a request label.", 403)
