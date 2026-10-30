import json
from datetime import date, timedelta

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from test_pipeline import fixture_payload

from dataguard.api import create_app
from dataguard.service import Pipeline, heads

TOKEN = "public-boundary-test-credential-0000000000"
HEADERS = {"Authorization": "Bearer " + TOKEN}


def test_metadata_and_metrics_are_private_unless_synthetic_demo_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    monkeypatch.delenv("DATAGUARD_PUBLIC_DEMO", raising=False)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'public.db'}")) as client:
        for path in ("/summary", "/snapshots", "/metrics"):
            assert client.get(path).status_code == 401
            assert client.get(path, headers=HEADERS).status_code == 200
        payload = fixture_payload()
        payload["trades"][0]["trade_id"] = "private-customer-123"
        batch = client.post(
            "/batches", json={"key": "private-key-123", "payload": payload}, headers=HEADERS
        ).json()["batch_id"]
        client.post(f"/batches/{batch}/run", headers=HEADERS)
        monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
        response = client.get("/summary")
        assert response.status_code == 200
        assert response.json()["public_demo"] is True
        assert "private-customer-123" not in response.text
        assert "private-key-123" not in response.text
        assert TOKEN not in response.text
        for path in (
            "/metrics",
            f"/batches/{batch}",
            "/quarantine",
            f"/snapshots/{payload['period']}",
        ):
            assert client.get(path).status_code == 401


def test_unauthenticated_mutation_is_rejected_without_receiving_its_body(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    app = create_app(f"sqlite:///{tmp_path / 'no-body.db'}")
    messages = []
    reads = []

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def send(message):
        messages.append(message)

    async def run():
        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "method": "POST",
                "scheme": "http",
                "path": "/batches",
                "raw_path": b"/batches",
                "query_string": b"",
                "headers": [],
                "server": ("test", 80),
                "client": ("127.0.0.1", 1),
            },
            receive,
            send,
        )

    anyio.run(run)
    assert messages[0]["status"] == 401
    assert reads == []


@pytest.mark.parametrize("kind", ["deep", "wide"])
def test_json_complexity_limits_precede_framework_parsing(tmp_path, monkeypatch, kind):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    if kind == "deep":
        value = "[" * 2000 + "0" + "]" * 2000
    else:
        value = "[" + ",".join("0" for _ in range(300000)) + "]"
    raw = '{"key":"complex","payload":{"nested":' + value + "}}"
    with TestClient(
        create_app(f"sqlite:///{tmp_path / 'complex.db'}"), raise_server_exceptions=False
    ) as client:
        response = client.post(
            "/batches", content=raw, headers={**HEADERS, "Content-Type": "application/json"}
        )
        assert response.status_code == 413
        assert "complex" not in response.text


def test_delimiters_inside_strings_do_not_count_as_json_nesting(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'strings.db'}")) as client:
        response = client.post(
            "/batches",
            json={"key": "literal", "payload": {"value": '[{"escaped": "\\"}]' * 1000}},
            headers=HEADERS,
        )
        assert response.status_code == 201


@pytest.mark.parametrize("key", [" ", "bad\x00key", "bad/key", "\ud800"])
def test_unsafe_keys_are_rejected_before_any_database_effect(tmp_path, key):
    pipeline = Pipeline(f"sqlite:///{tmp_path / 'keys.db'}")
    pipeline.initialize()
    with pytest.raises(ValueError, match="key"):
        pipeline.stage(key, fixture_payload())
    with pipeline.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM batches")).scalar() == 0


def test_invalid_unicode_payload_is_rejected_before_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    with TestClient(
        create_app(f"sqlite:///{tmp_path / 'unicode.db'}"), raise_server_exceptions=False
    ) as client:
        raw = json.dumps({"key": "unicode", "payload": {"value": "\ud800"}})
        response = client.post(
            "/batches", content=raw, headers={**HEADERS, "Content-Type": "application/json"}
        )
        assert response.status_code == 422


def test_excess_inflight_requests_fail_fast_without_blocking_liveness(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
    app = create_app(f"sqlite:///{tmp_path / 'load.db'}")
    app.state.pipeline.initialize()

    async def exercise():
        app.state.request_limiter.total_tokens = 1
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            other_request = object()
            await app.state.request_limiter.acquire_on_behalf_of(other_request)
            try:
                assert (await client.get("/summary")).status_code == 503
                assert (await client.get("/health")).status_code == 200
            finally:
                app.state.request_limiter.release_on_behalf_of(other_request)
            assert (await client.get("/summary")).status_code == 200

    anyio.run(exercise)


def test_slow_authenticated_body_times_out_and_releases_capacity(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    app = create_app(f"sqlite:///{tmp_path / 'slow.db'}")
    app.state.pipeline.initialize()
    app.state.body_timeout_seconds = 0.01
    messages = []

    async def receive():
        await anyio.sleep(0.1)
        return {"type": "http.request", "body": b'{"key":"slow","payload":{}}', "more_body": False}

    async def send(message):
        messages.append(message)

    async def run():
        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "method": "POST",
                "scheme": "http",
                "path": "/batches",
                "raw_path": b"/batches",
                "query_string": b"",
                "headers": [
                    (b"authorization", ("Bearer " + TOKEN).encode()),
                    (b"content-type", b"application/json"),
                ],
                "server": ("test", 80),
                "client": ("127.0.0.1", 1),
            },
            receive,
            send,
        )

    anyio.run(run)
    assert messages[0]["status"] == 408


def test_snapshot_metadata_has_a_fixed_response_bound(tmp_path):
    pipeline = Pipeline(f"sqlite:///{tmp_path / 'metadata.db'}")
    pipeline.initialize()
    batch = pipeline.stage("one", fixture_payload())
    with pipeline.engine.begin() as connection:
        connection.execute(
            heads.insert(),
            [
                {
                    "period": (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
                    "batch_id": batch,
                    "published_at": 1.0,
                }
                for i in range(150)
            ],
        )
    assert len(pipeline.snapshots()) == 100


def test_out_of_range_batch_ids_are_validation_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    with TestClient(
        create_app(f"sqlite:///{tmp_path / 'ids.db'}"), raise_server_exceptions=False
    ) as client:
        assert client.get(f"/batches/{2**70}", headers=HEADERS).status_code == 422


def test_public_metadata_errors_never_expose_connection_or_token_details(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", TOKEN)
    monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
    with TestClient(create_app(f"sqlite:///{tmp_path / 'errors.db'}")) as client:

        def fail():
            raise SQLAlchemyError(
                "postgresql://private-user:private-password@private-host/database " + TOKEN
            )

        monkeypatch.setattr(client.app.state.pipeline, "summary", fail)
        response = client.get("/summary")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert "private" not in response.text
        assert TOKEN not in response.text


@pytest.mark.parametrize("scheme", ["postgresql://", "postgres://"])
def test_standard_postgres_urls_select_the_installed_psycopg_driver(scheme):
    pipeline = Pipeline(scheme + "localhost/dataguard_test")
    assert pipeline.engine.url.drivername == "postgresql+psycopg"
    pipeline.engine.dispose()


def test_postgres_connect_attempts_have_a_finite_timeout():
    pipeline = Pipeline("postgresql://localhost/dataguard_test")
    observed = {}

    class StopBeforeNetwork(Exception):
        pass

    @event.listens_for(pipeline.engine, "do_connect")
    def inspect_connect(_dialect, _record, _args, parameters):
        observed.update(parameters)
        raise StopBeforeNetwork

    with pytest.raises(StopBeforeNetwork):
        pipeline.ready()
    assert observed.get("connect_timeout") == 5
