from dataclasses import replace
import hashlib
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.loader import RepositoryLoader
from app.main import create_app
from app.schemas import Edit, ModelPlan, PatchProposal, PlannedChange, TestCounts, TestRun
from app.store import Store


def zip_bytes(files: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


@pytest.fixture
def settings(tmp_path):
    return replace(Settings(), workspace_root=tmp_path / "workspaces", api_key="", model="")


@pytest.fixture
def store(settings):
    value = Store(settings)
    yield value
    value.close()


@pytest.fixture
def loader(store, settings):
    return RepositoryLoader(store, settings)


class DeterministicModelDouble:
    """Test-only model double; never used by the application factory by default."""
    def __init__(self, regress=False):
        self.regress = regress
        self.patch_calls = 0

    def connectivity(self):
        return {"ok": True, "message": "Test double"}

    def plan(self, context):
        path = context["allowed_paths"][0]
        return ModelPlan(objective="Simplify one expression without changing outputs.",
            changes=[PlannedChange(path=path, description="Simplify aggregation.", priority="low")],
            risks=["Numeric behavior could regress."], test_strategy=["Use unchanged baseline tests and fixture probes."])

    def patch(self, context, plan, failure=None):
        self.patch_calls += 1
        path = context["allowed_paths"][0]
        content = context["files"][path]["content"]
        if failure:
            changed = content.replace('Decimal(row["amount"]) * 2', 'Decimal(row["amount"])')
        elif self.regress:
            changed = content.replace('Decimal(row["amount"])', 'Decimal(row["amount"]) * 2')
        else:
            changed = content + "\n# Modernization test double: source change for orchestration tests.\n"
        return PatchProposal(summary="Test-only patch", edits=[Edit(path=path,
            original_sha256=context["files"][path]["original_sha256"], new_content=changed)])


class SequenceRunnerDouble:
    """Test-only runner outcomes; real execution is covered by integration tests."""
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or ["passed", "failed", "passed"]
        self.calls = []

    def run(self, repo, source):
        self.calls.append(source)
        status = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
        return TestRun(status=status, command=["test-double"], exit_code=0 if status == "passed" else 1,
                       counts=TestCounts(passed=12 if status == "passed" else 11, failed=0 if status == "passed" else 1, skipped=0),
                       behavior_outputs={"case": {"output": 1 if status == "passed" else 2, "error": None}})

    def run_with_trials(self, repo, source, scenarios):
        from app.harness_schemas import Outcome, TrialExecution
        from app.trials import input_digest
        result = self.run(repo, source)
        for scenario in scenarios:
            outcome = scenario.expected or Outcome(output=1 if result.status == "passed" else 2)
            result.trial_outputs.append(TrialExecution(scenario_id=scenario.id, input_digest=input_digest(scenario.input),
                outcome=outcome, duration_ms=1, invariant_passed=result.status == "passed" if scenario.invariant else None))
        return result


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, model=DeterministicModelDouble(), runner=SequenceRunnerDouble(["passed"]))) as value:
        yield value
