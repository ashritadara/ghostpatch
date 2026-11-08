from dataclasses import dataclass
from pathlib import Path
import os
import signal
import subprocess
import tempfile
import time


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    limit_reason: str | None = None
    raw_stdout: bytes = b""


def run_bounded(args: list[str], *, timeout: float, cwd: Path | None = None,
                env: dict[str, str] | None = None, monitor_root: Path | None = None,
                max_tree_bytes: int = 50 * 1024 * 1024,
                max_output: int = 1024 * 1024) -> CommandResult:
    """No shell; bounded output, wall time, and optional clone directory size."""
    start = time.monotonic()
    reason = None
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err, **kwargs)
        while proc.poll() is None:
            if time.monotonic() - start > timeout:
                reason = "Command timed out."
            elif os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > max_output:
                reason = "Command exceeded the output limit."
            elif monitor_root and sum(p.stat().st_size for p in monitor_root.rglob("*") if p.is_file()) > max_tree_bytes:
                reason = "Clone exceeded the storage limit."
            if reason:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.kill()
                break
            time.sleep(0.05)
        proc.wait(timeout=5)
        if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > max_output:
            reason = reason or "Command exceeded the output limit."
        out.seek(0)
        err.seek(0)
        raw = out.read(max_output)
        return CommandResult(proc.returncode, raw.decode("utf-8", "replace"),
                             err.read(max_output).decode("utf-8", "replace"),
                             int((time.monotonic() - start) * 1000), reason, raw)
