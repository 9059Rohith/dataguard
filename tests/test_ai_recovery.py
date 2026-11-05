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


@pytest.mark.parametrize(
    "status,expected,attempts",
    [(503, 503, 3), (429, 429, 3), (400, 502, 1), (401, 502, 1), (403, 502, 1)],
)
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


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("delay", ["1", "120", "Wed, 01 Jan 2031 00:00:00 GMT"])
def test_provider_retry_after_is_not_ignored(tmp_path, monkeypatch, delay, status):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(quality.time, "sleep", lambda _: None)
    calls = []

    def respond(request, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(
            request.full_url, status, "unit-only", {"Retry-After": delay}, None
        )

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect retained source evidence", public_demo=True)
    assert error.value.status_code == status
    assert error.value.headers["Retry-After"] == delay
    assert len(calls) == 1


TOOL_MESSAGE = {
    "role": "assistant",
    "tool_calls": [
        {
            "id": "read",
            "type": "function",
            "function": {"name": "list_captures", "arguments": "{}"},
        }
    ],
}
ANSWER_MESSAGE = {"role": "assistant", "content": "The retained public capture list is empty."}


@pytest.mark.parametrize(
    "sequence,expected_requests,expected_tools",
    [
        ([503, 503, TOOL_MESSAGE, ANSWER_MESSAGE], 4, 1),
        ([TOOL_MESSAGE, 503, 503, ANSWER_MESSAGE], 4, 1),
        ([503, TOOL_MESSAGE, TOOL_MESSAGE, 503, TOOL_MESSAGE, ANSWER_MESSAGE], 6, 3),
        ([ConnectionResetError, TimeoutError, TOOL_MESSAGE, ANSWER_MESSAGE], 4, 1),
    ],
)
def test_two_faults_recover_with_shared_backoff_and_retained_tool_evidence(
    tmp_path, monkeypatch, sequence, expected_requests, expected_tools
):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    waits, payloads = [], []
    monkeypatch.setattr(quality.time, "sleep", waits.append)

    def respond(request, timeout):
        payloads.append(json.loads(request.data))
        reply = sequence[len(payloads) - 1]
        if isinstance(reply, int):
            raise urllib.error.HTTPError(request.full_url, reply, "secret-body", {}, None)
        if isinstance(reply, type):
            raise reply("secret-body")
        return io.BytesIO(json.dumps({"choices": [{"message": reply}]}).encode())

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    result = investigate(store, "Inspect public evidence.", public_demo=True)
    assert result["provider_requests"] == len(payloads) == expected_requests
    assert len(result["trace"]) == expected_tools
    assert 1 <= waits[0] <= 1.1
    assert 2 <= waits[1] <= 2.1
    assert sum(m["role"] == "tool" for m in payloads[-1]["messages"]) == expected_tools


def test_retry_allowance_does_not_reset_after_successful_tool_turn(tmp_path, monkeypatch):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    waits, calls = [], []
    monkeypatch.setattr(quality.time, "sleep", waits.append)

    def respond(request, timeout):
        calls.append(1)
        if len(calls) == 2:
            return io.BytesIO(json.dumps({"choices": [{"message": TOOL_MESSAGE}]}).encode())
        raise urllib.error.HTTPError(request.full_url, 503, "secret-body", {}, None)

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect public evidence.", public_demo=True)
    assert error.value.status_code == 503
    assert len(calls) == 4
    assert len(waits) == 2


def test_retry_wait_leaves_time_for_provider_response(tmp_path, monkeypatch):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    clock, waits, calls = [0.0], [], []
    monkeypatch.setattr(quality.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(quality.time, "sleep", waits.append)

    def respond(request, timeout):
        calls.append(timeout)
        clock[0] = 58.95
        raise urllib.error.HTTPError(request.full_url, 503, "secret-body", {}, None)

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect public evidence.", public_demo=True)
    assert error.value.status_code == 503
    assert calls == [20]
    assert waits == []


def test_deadline_is_checked_again_after_sleep(tmp_path, monkeypatch):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    clock, calls = [0.0], []
    monkeypatch.setattr(quality.time, "monotonic", lambda: clock[0])

    def oversleep(seconds):
        clock[0] = 61

    monkeypatch.setattr(quality.time, "sleep", oversleep)

    def respond(request, timeout):
        calls.append(timeout)
        raise TimeoutError("secret-body")

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect public evidence.", public_demo=True)
    assert error.value.status_code == 503
    assert calls == [20]


def test_late_provider_answer_cannot_complete_after_deadline(tmp_path, monkeypatch):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    clock, calls = [0.0], []
    monkeypatch.setattr(quality.time, "monotonic", lambda: clock[0])

    def respond(request, timeout):
        calls.append(timeout)
        reply = TOOL_MESSAGE if len(calls) == 1 else ANSWER_MESSAGE
        if len(calls) == 2:
            clock[0] = 61
        return io.BytesIO(json.dumps({"choices": [{"message": reply}]}).encode())

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect public evidence.", public_demo=True)
    assert error.value.status_code == 503
    assert calls == [20, 20]


@pytest.mark.parametrize("body", [b"not-json", b'{"choices": []}'])
def test_malformed_provider_response_is_not_retried(tmp_path, monkeypatch, body):
    from dataguard import quality

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    calls = []

    def respond(request, timeout):
        calls.append(1)
        return io.BytesIO(body)

    monkeypatch.setattr(quality.urllib.request, "urlopen", respond)
    store = QualityStore(create_engine(f"sqlite:///{tmp_path / 'db'}"))
    store.initialize()
    with pytest.raises(HTTPException) as error:
        investigate(store, "Inspect public evidence.", public_demo=True)
    assert error.value.status_code == 502
    assert len(calls) == 1
