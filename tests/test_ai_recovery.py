"""Controlled upstream failures, with actual read-only quality tools and bounded calls."""

import io
import json
import urllib.error

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine

from dataguard.quality import QualityStore, investigate


@pytest.mark.parametrize("fault", [500, 502, 503, 504, "timeout"])
def test_investigator_recovers_one_transient_fault(tmp_path, monkeypatch, fault):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(quality.time, "sleep", lambda _: None)
    calls = []

    def respond(request, timeout):
        calls.append((json.loads(request.data), timeout))
        if len(calls) == 1:
            if fault == "timeout":
                raise TimeoutError("secret-provider-body")
            raise urllib.error.HTTPError(request.full_url, fault, "secret-provider-body", {}, None)
        message = {
            "role": "assistant",
            "content": "The tool returned the retained public capture list.",
        }
        if len(calls) == 2:
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "read",
                        "type": "function",
                        "function": {"name": "list_captures", "arguments": "{}"},
                    }
                ],
            }
        return io.BytesIO(json.dumps({"choices": [{"message": message}]}).encode())

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    result = investigate(store, "Inspect the retained public evidence.", public_demo=True)
    assert result["trace"][0]["tool"] == "list_captures"
    assert result["provider_requests"] == len(calls) == 3
    assert all(payload["reasoning_effort"] == "minimal" for payload, _ in calls)
    assert all(timeout <= 20 for _, timeout in calls)


@pytest.mark.parametrize("status,expected,attempts", [(503, 503, 2), (400, 502, 1)])
def test_provider_failure_is_bounded_and_redacted(
    tmp_path, monkeypatch, caplog, status, expected, attempts
):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(quality.time, "sleep", lambda _: None)
    calls = []

    def respond(request, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url, status, "secret-provider-body", {}, None)

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect the retained public evidence.", public_demo=True)
    assert error.value.status_code == expected
    assert len(calls) == attempts
    if expected == 503:
        assert error.value.headers["Retry-After"] == "60"
    assert "status=" + str(status) in caplog.text
    assert "secret-provider-body" not in caplog.text + str(error.value)
    assert "unit-recovery-key-never-sent" not in caplog.text + str(error.value)


def test_expired_deadline_never_calls_provider(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    clock = iter([0, 61])
    monkeypatch.setattr(
        quality, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None)
    )
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect retained source evidence", public_demo=True)
    assert error.value.status_code == 503


@pytest.mark.parametrize("delay", ["1", "120", "Wed, 01 Jan 2031 00:00:00 GMT"])
def test_provider_retry_after_is_not_ignored(tmp_path, monkeypatch, delay):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(quality.time, "sleep", lambda _: None)
    calls = []

    def respond(request, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(
            request.full_url, 503, "unit-only", {"Retry-After": delay}, None
        )

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect retained source evidence", public_demo=True)
    assert error.value.status_code == 503
    assert error.value.headers["Retry-After"] == delay
    assert len(calls) == 1
