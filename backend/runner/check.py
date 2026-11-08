"""Fixed, separately mounted runner. No model-selected modules or commands."""
import argparse
import copy
import hashlib
import importlib
import io
import json
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

sys.path.insert(0, "/project")
parser = argparse.ArgumentParser()
parser.add_argument("--sample", choices=["legacy_reports", "claims_demo"], default="legacy_reports")
parser.add_argument("--trials", action="store_true")
args = parser.parse_args()


class Counts:
    def __init__(self):
        self.passed = self.failed = self.skipped = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1
        elif report.skipped:
            self.skipped += 1


class BoundedText(io.StringIO):
    def write(self, value):
        remaining = 4000 - self.tell()
        if remaining > 0:
            super().write(value[:remaining])
        return len(value)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def tmp_files():
    return {p.relative_to("/tmp").as_posix() for p in Path("/tmp").rglob("*") if p.is_file()}


def invoke(function, value):
    try:
        return {"output": function(value), "exception_type": None}
    except Exception as exc:
        return {"output": None, "exception_type": type(exc).__name__}


counts = Counts()
exit_code = pytest.main(["/tests", "-q", "-c", "/runner/pytest.ini", "-p", "no:cacheprovider",
                         "--confcutdir=/tests", "--basetemp=/tmp/pytest", "--import-mode=importlib"], plugins=[counts])
outputs, trial_outputs = {}, []
try:
    if args.sample == "claims_demo":
        function = importlib.import_module("claims").evaluate_claim
    else:
        function = importlib.import_module("reports").summarize
    for case in json.loads(Path("/fixtures/behavior_cases.json").read_text()):
        value = case["input"] if args.sample == "claims_demo" else case["rows"]
        result = invoke(function, copy.deepcopy(value))
        outputs[case["id"]] = {"output": result["output"], "error": result["exception_type"]}
    if args.trials:
        scenarios = json.loads(Path("/scenarios.json").read_text())
        if not isinstance(scenarios, list) or len(scenarios) > 24:
            raise ValueError("Invalid scenario budget")
        for scenario in scenarios:
            value = copy.deepcopy(scenario["input"])
            original_value = canonical(value)
            before_files = tmp_files()
            out, err = BoundedText(), BoundedText()
            start = time.monotonic()
            with redirect_stdout(out), redirect_stderr(err):
                result = invoke(function, value)
                invariant = None
                if scenario.get("invariant") == "input_unchanged":
                    invariant = canonical(value) == original_value
                elif scenario.get("invariant") == "repeatability":
                    repeated = invoke(function, copy.deepcopy(scenario["input"]))
                    invariant = canonical(result) == canonical(repeated)
            trial_outputs.append({
                "scenario_id": scenario["id"],
                "input_digest": hashlib.sha256(original_value.encode()).hexdigest(),
                "outcome": result, "duration_ms": int((time.monotonic() - start) * 1000),
                "stdout": out.getvalue(), "stderr": err.getvalue(),
                "input_mutated": canonical(value) != original_value,
                "created_files": sorted(tmp_files() - before_files)[:20],
                "invariant_passed": invariant,
            })
except Exception as exc:
    outputs["runner_error"] = {"output": None, "error": type(exc).__name__}
print("GHOSTPATCH_RESULT=" + json.dumps({"exit_code": int(exit_code), "counts": vars(counts),
      "behavior_outputs": outputs, "trial_outputs": trial_outputs}), flush=True)
sys.exit(int(exit_code))
