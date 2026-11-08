import re


class GhostPatchError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def redact(text: str, secret: str = "") -> str:
    if secret:
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?:nvapi-|sk-)[A-Za-z0-9_-]{12,}", "[REDACTED]", text)
    text = re.sub(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}", "[REDACTED]", text)
    text = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED]", text)
    text = re.sub(
        r"(?i)((?:api[_-]?key|password|access[_-]?token|secret)\s*[:=]\s*[\"'])([^\"'\r\n]+)",
        r"\1[REDACTED]", text,
    )
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return text
