import concurrent.futures
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from dataguard.api import create_app

TOKEN = "public-demo-test-secret-000000000000000000"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    monkeypatch.setenv("GEMINI_API_KEY", "unit-public-gemini-key-never-sent")
    monkeypatch.delenv("VERCEL", raising=False)
    from types import SimpleNamespace

    import dataguard.public_demo as demo

    monkeypatch.setattr(demo, "time", SimpleNamespace(time=lambda: 1_800_000_010))
    application = create_app("sqlite:///" + str(tmp_path / "public-demo.db"))
    with TestClient(application):
        yield application


def mock_investigator(monkeypatch):
    import dataguard.quality as module

    calls = []

    def fake(store, question, **kwargs):
        calls.append((question, kwargs))
        return {
            "answer": "Observed public source evidence.",
            "trace": [],
            "provider": "Google Gemini",
            "model": "gemini-3.5-flash-lite",
            "public_data_only": True,
            "provider_requests": 2,
            "created_at": module.stamp(),
        }

    monkeypatch.setattr(module, "investigate", fake)
    return calls


def test_anonymous_endpoint_has_persistent_global_quota_before_model(app, monkeypatch):
    calls = mock_investigator(monkeypatch)
    with TestClient(app, client=("192.0.2.5", 4500)) as client:
        assert (
            client.post(
                "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
            ).status_code
            == 200
        )
        blocked = client.post(
            "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
        )
        assert blocked.status_code == 429
        assert blocked.headers["Cache-Control"] == "no-store"
        assert 1 <= int(blocked.headers["Retry-After"]) <= 600
    assert len(calls) == 2
    assert all(call[1]["public_demo"] is True for call in calls)
    with TestClient(create_app(str(app.state.pipeline.engine.url))) as restarted:
        assert (
            restarted.post(
                "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
            ).status_code
            == 429
        )
    assert len(calls) == 2


def test_public_rate_reservation_is_atomic_across_workers(app):
    from dataguard.public_demo import PublicQuota

    engine = app.state.pipeline.engine

    def reserve(index):
        try:
            PublicQuota(engine).reserve("hashed-client-" + str(index), now=1_800_000_010)
            return 200
        except Exception as error:
            return getattr(error, "status_code", 500)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(8)))
    assert results.count(200) == 2
    assert results.count(429) == 6


def test_per_client_and_daily_buckets(app):
    from dataguard.public_demo import PublicQuota

    quota = PublicQuota(app.state.pipeline.engine)
    base = 1_800_057_610
    base = base // 86400 * 86400 + 10
    for offset in [0, 61, 122]:
        quota.reserve("same-client", now=base + offset)
    with pytest.raises(Exception) as error:
        quota.reserve("same-client", now=base + 183)
    assert error.value.status_code == 429
    for index in range(3, 30):
        quota.reserve("client-" + str(index), now=base + index * 61)
    with pytest.raises(Exception) as error:
        quota.reserve("another-client", now=base + 31 * 61)
    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) > 600


def test_spoofed_forwarded_addresses_do_not_change_identity(app, monkeypatch):
    from starlette.requests import Request

    from dataguard.public_demo import client_hash

    def request(value):
        return Request(
            {
                "type": "http",
                "headers": [(b"x-forwarded-for", value.encode())],
                "client": ("192.0.2.1", 1234),
                "server": ("test", 80),
                "scheme": "http",
                "path": "/",
            }
        )

    assert client_hash(request("203.0.113.1")) == client_hash(request("203.0.113.2"))
    monkeypatch.setenv("VERCEL", "true")
    assert client_hash(request("203.0.113.1")) == client_hash(request("203.0.113.2"))
    monkeypatch.setenv("VERCEL", "1")
    assert client_hash(request("203.0.113.1")) != client_hash(request("203.0.113.2"))
    assert client_hash(request("203.0.113.1, 198.51.100.1")) == client_hash(request("invalid"))
    assert len(client_hash(request("203.0.113.1"))) == 64


def test_public_origin_input_and_private_write_boundaries(app, monkeypatch):
    calls = mock_investigator(monkeypatch)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/quality/public-investigate",
                json={"question": "Inspect evidence."},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/quality/public-investigate", json={"question": "a" * 601}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/quality/public-investigate",
                json={"question": "Inspect evidence.", "model": "paid-model"},
            ).status_code
            == 422
        )
        assert (
            client.post("/api/quality/public-investigate", content=b"x" * 8193).status_code == 413
        )
        assert (
            client.post(
                "/api/quality/public-investigate",
                json={"question": "Inspect evidence."},
                headers={"Origin": "http://testserver"},
            ).status_code
            == 200
        )
        canonical = client.post(
            "/api/quality/public-investigate",
            json={"question": "Inspect evidence."},
            headers={"Origin": "https://rohith-dataguard.vercel.app"},
        )
        assert canonical.status_code == 200
        assert canonical.headers["Cache-Control"] == "no-store"
        for path in [
            "/api/quality/investigate",
            "/api/quality/uploads",
            "/api/quality/sync",
            "/api/quality/recheck",
            "/batches",
            "/recover",
        ]:
            assert client.post(path, json={}).status_code == 401
    assert len(calls) == 2


def test_quota_database_failure_fails_closed(app, monkeypatch):
    from dataguard.public_demo import PublicQuota

    calls = mock_investigator(monkeypatch)

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private connection diagnostic")

    monkeypatch.setattr(PublicQuota, "reserve", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/quality/public-investigate", json={"question": "Inspect evidence."}
        )
    assert response.status_code == 503
    assert "private connection diagnostic" not in response.text
    assert calls == []


def test_no_raw_ip_is_persisted_and_free_provider_is_required(app, monkeypatch):
    from dataguard.public_demo import buckets

    calls = mock_investigator(monkeypatch)
    with TestClient(app, client=("192.0.2.99", 4500)) as client:
        assert (
            client.post(
                "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
            ).status_code
            == 200
        )
        monkeypatch.delenv("GEMINI_API_KEY")
        monkeypatch.setenv("OPENAI_API_KEY", "unit-paid-fallback-must-not-be-used")
        assert (
            client.post(
                "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
            ).status_code
            == 503
        )
    with app.state.pipeline.engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(select(buckets)).mappings()]
    assert "192.0.2.99" not in json.dumps(rows)
    assert len(calls) == 1


@pytest.mark.parametrize("public_demo", [True, False])
@pytest.mark.parametrize("model", [None, "gemini-3.1-flash-lite"])
def test_selected_model_tool_loop_never_includes_private_uploads(
    app, monkeypatch, model, public_demo
):
    import io

    import dataguard.quality as module

    if model is None:
        monkeypatch.delenv("DATAGUARD_GEMINI_MODEL", raising=False)
    else:
        monkeypatch.setenv("DATAGUARD_GEMINI_MODEL", model)
    expected_model = model or "gemini-3.5-flash-lite"
    monkeypatch.setenv("OPENAI_API_KEY", "unit-paid-fallback-must-not-be-used")
    with TestClient(app) as client:
        status = client.get("/api/quality/provider").json()
        assert status["model"] == expected_model
        assert status["configured"] is True
        assert status["public_demo"]["configured"] is True
        public = client.get("/api/quality/workspace").json()["captures"][0]
        private = client.post(
            "/api/quality/uploads",
            headers={"Authorization": "Bearer " + TOKEN},
            json={
                "name": "PRIVATE-UPLOAD-MARKER",
                "records": [{"id": 1, "full_name": "PRIVATE-RECORD-MARKER"}],
            },
        ).json()
        replies = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "list",
                        "type": "function",
                        "function": {"name": "list_captures", "arguments": "{}"},
                    },
                    {
                        "id": "private",
                        "type": "function",
                        "function": {
                            "name": "inspect_capture",
                            "arguments": json.dumps({"capture_id": private["id"]}),
                        },
                    },
                    {
                        "id": "public",
                        "type": "function",
                        "function": {
                            "name": "inspect_capture",
                            "arguments": json.dumps({"capture_id": public["id"]}),
                        },
                    },
                ],
            },
            {
                "role": "assistant",
                "content": "Public capture " + public["id"] + " contains 8 repository records.",
            },
        ]
        sent = []

        def respond(request, timeout):
            assert (
                request.full_url
                == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            )
            sent.append(json.loads(request.data))
            # A configuration change cannot switch a signed conversation mid-turn.
            monkeypatch.setenv(
                "DATAGUARD_GEMINI_MODEL",
                "gemini-3.5-flash-lite" if model else "gemini-3.1-flash-lite",
            )
            return io.BytesIO(json.dumps({"choices": [{"message": replies.pop(0)}]}).encode())

        monkeypatch.setattr(module.urllib.request, "urlopen", respond)
        response = client.post(
            "/api/quality/public-investigate" if public_demo else "/api/quality/investigate",
            headers={} if public_demo else {"Authorization": "Bearer " + TOKEN},
            json={"question": "Inspect the latest public GitHub records."},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["public_data_only"] is True
    assert data["model"] == expected_model
    assert all(payload["model"] == expected_model for payload in sent)
    assert len(sent) == 2
    assert "PRIVATE-UPLOAD-MARKER" not in json.dumps(sent)
    assert "PRIVATE-RECORD-MARKER" not in json.dumps(sent)
    assert data["trace"][1]["result"]["error"] == "Capture is outside public GitHub evidence scope"
    assert data["trace"][2]["result"]["row_count"] == 8
    if public_demo:
        assert data["public_demo"] is True
        assert "records" not in data["trace"][2]["result"]
        assert data["quota"]["remaining"]["global_minute"] == 1


@pytest.mark.parametrize("model", ["paid-model-secret-marker", "", "   ", " gemini-3.1-flash-lite"])
def test_invalid_model_disables_ai_before_quota_or_provider(app, monkeypatch, model):
    import dataguard.quality as module

    monkeypatch.setenv("DATAGUARD_GEMINI_MODEL", model)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-paid-fallback-must-not-be-used")

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid Gemini configuration must not reserve quota or call any provider")

    monkeypatch.setattr(module.PublicQuota, "reserve", forbidden)
    monkeypatch.setattr(module.urllib.request, "urlopen", forbidden)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "alive"}
        assert client.get("/ready").json() == {"status": "ready"}
        assert client.get("/api/quality/workspace").status_code == 200
        status = client.get("/api/quality/provider")
        assert status.status_code == 200
        assert status.json()["provider"] == "Google Gemini"
        assert status.json()["public_data_only"] is True
        assert status.json()["configured"] is False
        assert status.json()["model"] is None
        assert status.json()["public_demo"]["configured"] is False
        for path, headers in [
            ("/api/quality/public-investigate", {}),
            ("/api/quality/investigate", {"Authorization": "Bearer " + TOKEN}),
        ]:
            response = client.post(
                path, headers=headers, json={"question": "Inspect public evidence."}
            )
            assert response.status_code == 503
            assert "paid-model-secret-marker" not in status.text + response.text


@pytest.mark.parametrize("field", ["model", "provider", "endpoint"])
def test_public_caller_cannot_override_server_model(app, monkeypatch, field):
    calls = mock_investigator(monkeypatch)
    monkeypatch.setenv("DATAGUARD_GEMINI_MODEL", "gemini-3.1-flash-lite")
    with TestClient(app) as client:
        response = client.post(
            "/api/quality/public-investigate",
            json={"question": "Inspect public evidence.", field: "caller-controlled"},
        )
    assert response.status_code == 422
    assert calls == []


def test_gemini_selector_does_not_change_private_openai_configuration(app, monkeypatch):
    import io

    import dataguard.quality as module

    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("DATAGUARD_GEMINI_MODEL", "invalid-gemini-only-setting")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-private-openai-key-never-sent")
    monkeypatch.setenv("OPENAI_MODEL", "operator-selected-openai-model")
    payloads = []

    def respond(request, timeout):
        assert request.full_url == "https://api.openai.com/v1/chat/completions"
        payloads.append(json.loads(request.data))
        message = {"role": "assistant", "content": "Observed retained capture evidence."}
        if len(payloads) == 1:
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

    monkeypatch.setattr(module.urllib.request, "urlopen", respond)
    with TestClient(app) as client:
        status = client.get("/api/quality/provider").json()
        assert status["configured"] is True and status["provider"] == "OpenAI"
        assert status["model"] == "operator-selected-openai-model"
        assert status["public_demo"]["configured"] is False
        response = client.post(
            "/api/quality/investigate",
            headers={"Authorization": "Bearer " + TOKEN},
            json={"question": "Inspect retained capture evidence."},
        )
    assert response.status_code == 200
    assert response.json()["public_data_only"] is False
    assert response.json()["trace"][0]["tool"] == "list_captures"
    assert len(payloads) == 2
    assert all(payload["model"] == "operator-selected-openai-model" for payload in payloads)


def test_missing_server_protection_and_oversized_model_output_fail_closed(app, monkeypatch):
    calls = mock_investigator(monkeypatch)
    monkeypatch.delenv("DATAGUARD_TOKEN")
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/quality/public-investigate", json={"question": "Inspect public evidence."}
            ).status_code
            == 503
        )
    assert calls == []
    from dataguard.public_demo import public_result

    with pytest.raises(Exception) as error:
        public_result({"answer": "a" * 6001}, {})
    assert error.value.status_code == 502
