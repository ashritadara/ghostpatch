import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError

from app.config import Settings
from app.errors import GhostPatchError, redact
from app.model import NemotronClient, Probe, final_text, parse_structured
from dataclasses import replace


def response(content, finish="stop", reasoning=None):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content, reasoning_content=reasoning))])


def fake_sdk(monkeypatch, outputs):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        result = outputs.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=lambda: None)
    monkeypatch.setattr("app.model.OpenAI", lambda **kwargs: sdk)
    monkeypatch.setattr("app.model.time.sleep", lambda seconds: None)
    return calls


def test_reasoning_is_not_final_text():
    assert final_text(SimpleNamespace(content=None, reasoning_content="hidden reasoning")) == ""
    assert final_text(SimpleNamespace(content="<think>private</think>{\"ok\":true}")) == '{"ok":true}'
    assert parse_structured('```json\n{"ok":true,"message":"verified"}\n```', Probe).ok


def test_retry_empty_truncated_and_then_valid(monkeypatch, settings):
    calls = fake_sdk(monkeypatch, [response(None, reasoning="not final"), response("{", "length"), response('{"ok":true,"message":"verified"}')])
    result = NemotronClient(replace(settings, api_key="not-a-real-key", model="configured-model")).connectivity()
    assert result["ok"] is True and len(calls) == 3
    assert calls[2]["max_tokens"] > calls[0]["max_tokens"]


def test_invalid_json_is_bounded(monkeypatch, settings):
    calls = fake_sdk(monkeypatch, [response("broken")] * 3)
    with pytest.raises(GhostPatchError, match="valid structured"):
        NemotronClient(replace(settings, api_key="not-a-real-key", model="configured-model")).connectivity()
    assert len(calls) == 3


def test_authentication_failure_is_actionable_and_not_retried(monkeypatch, settings):
    error = APIStatusError("do not display raw provider text", response=httpx.Response(401, request=httpx.Request("POST", "https://example.invalid")), body=None)
    calls = fake_sdk(monkeypatch, [error])
    with pytest.raises(GhostPatchError, match="authentication"):
        NemotronClient(replace(settings, api_key="not-a-real-key", model="configured-model")).connectivity()
    assert len(calls) == 1


def test_missing_config_and_redaction(settings):
    with pytest.raises(GhostPatchError, match="Configure"):
        NemotronClient(settings).connectivity()
    text = redact('API_KEY="abc-secret-value" nvapi-' + 'x' * 30)
    assert "abc-secret-value" not in text and "nvapi-" not in text
