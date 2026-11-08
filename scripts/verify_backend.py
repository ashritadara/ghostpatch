"""HTTP-only real trusted-sample smoke test. Never displays a credential."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(base + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urlopen(request, timeout=300) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("detail", "HTTP request failed")
        except ValueError:
            detail = "HTTP request failed"
        raise RuntimeError(str(detail)) from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", choices=["http://127.0.0.1:8000", "http://localhost:8000"])
    parser.add_argument("--run-model", action="store_true", help="Consent to send the built-in synthetic sample to NVIDIA and run its Docker validation.")
    args = parser.parse_args()
    health = call(args.base_url, "/api/health")
    print(json.dumps({"backend": health["status"], "nvidia_configured": health["nvidia_configured"], "docker": health["docker"]}, indent=2))
    if not args.run_model:
        return
    repo = call(args.base_url, "/api/repositories/sample", {})
    print("Analyzed trusted sample:", repo["file_count"], "files;", len(repo["analysis"]["findings"]), "findings", flush=True)
    plan = call(args.base_url, "/api/repositories/" + repo["id"] + "/plans", {
        "consent_to_model": True,
        "objective": "Simplify manual dictionary initialization with standard-library helpers; preserve Decimal arithmetic, ordering, rounding, counts, and exception behavior.",
    })
    call(args.base_url, "/api/plans/" + plan["id"] + "/approve", {"approved": True})
    job = call(args.base_url, "/api/plans/" + plan["id"] + "/execute", {"approved": True})
    deadline = time.monotonic() + 900
    while job["status"] in {"queued", "running"}:
        if time.monotonic() > deadline:
            raise RuntimeError("HTTP smoke-test deadline exceeded; inspect the still-running backend job.")
        time.sleep(1)
        job = call(args.base_url, "/api/jobs/" + job["id"])
    results = job["results"]
    summary = {
        "job_id": job["id"], "status": job["status"], "verification": results["verification"],
        "baseline": results["baseline"]["counts"] if results["baseline"] else None,
        "modified": results["modified"]["counts"] if results["modified"] else None,
        "behavior_cases": len(results["behavior_comparison"]), "repairs": len(results["repairs"]),
        "changed_files": [d["path"] for d in results["diffs"]], "error": job["error"],
    }
    print(json.dumps(summary, indent=2))
    print("Frontend output: http://127.0.0.1:3000/?job=" + job["id"])
    evidence = Path(__file__).resolve().parents[1] / ".ghostpatch"
    evidence.mkdir(exist_ok=True)
    (evidence / "last-run.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    if results["diffs"]:
        with urlopen(args.base_url + "/api/jobs/" + job["id"] + "/patch", timeout=15) as response:
            (evidence / "last-run.patch").write_bytes(response.read())
    if job["status"] != "succeeded" or results["verification"] != "passed":
        raise RuntimeError("Workflow did not verify successfully; inspect .ghostpatch/last-run.json.")


if __name__ == "__main__":
    main()
