import os
from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from dataguard.api import create_app
from dataguard.service import Pipeline


def test_opt_in_startup_seed_publishes_real_synthetic_data_once(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_SEED_DEMO", "true")
    monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
    monkeypatch.delenv("DATAGUARD_TOKEN", raising=False)
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    with TestClient(create_app(url)) as client:
        summary = client.get("/summary").json()
        assert summary["public_demo"] is True
        assert summary["attempts"]["published"] == 1
        batch_id = summary["snapshots"][0]["batch_id"]
        pipeline = client.app.state.pipeline
        snapshot = pipeline.current(summary["snapshots"][0]["period"])
        assert len(snapshot["trades"]) == 3
        assert all(t["trade_id"].startswith("synthetic-") for t in snapshot["trades"])
        assert client.post("/recover").status_code == 503
    with TestClient(create_app(url)) as client:
        again = client.get("/summary").json()
        assert again["attempts"]["published"] == 1
        assert again["snapshots"][0]["batch_id"] == batch_id


def test_startup_seed_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DATAGUARD_SEED_DEMO", raising=False)
    monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
    with TestClient(create_app(f"sqlite:///{tmp_path / 'empty.db'}")) as client:
        assert client.get("/summary").json()["snapshots"] == []


def test_background_bootstrap_keeps_console_available_and_recovers(tmp_path, monkeypatch):
    available = Event()
    attempted = Event()
    initialize = Pipeline.initialize

    def initialize_when_available(pipeline):
        attempted.set()
        if not available.is_set():
            raise OperationalError(None, None, ConnectionError("database connection refused"))
        initialize(pipeline)

    monkeypatch.setenv("DATAGUARD_BACKGROUND_INIT", "true")
    monkeypatch.setenv("DATAGUARD_AUTO_INIT", "false")
    monkeypatch.setattr(Pipeline, "initialize", initialize_when_available)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'recovery.db'}")) as client:
        assert attempted.wait(timeout=2)
        assert client.get("/console/overview").status_code == 200
        assert client.get("/health").status_code == 200
        pending = client.get("/ready")
        assert pending.status_code == 503
        assert pending.headers["retry-after"] == "1"

        available.set()
        deadline = monotonic() + 8
        while monotonic() < deadline and client.get("/ready").status_code == 503:
            sleep(0.05)
        assert client.get("/ready").json() == {"status": "ready"}


def test_container_entrypoint_uses_validated_port_and_omits_access_query_logs(monkeypatch):
    from dataguard import entrypoint

    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("PORT", "7860")
    monkeypatch.setenv("DATAGUARD_AUTO_INIT", "true")
    monkeypatch.setenv("DATAGUARD_BACKGROUND_INIT", "false")
    executed = []
    monkeypatch.setattr(os, "execvp", lambda program, args: executed.append((program, args)))
    entrypoint.main()
    assert executed[0][0] == "uvicorn"
    assert executed[0][1][-2:] == ["--port", "7860"]
    assert "--no-access-log" in executed[0][1]
    assert os.environ["DATAGUARD_BACKGROUND_INIT"] == "true"


@pytest.mark.parametrize("port", ["0", "65536", "--port=1", "bogus"])
def test_container_rejects_invalid_ports_before_bootstrap(monkeypatch, port):
    from dataguard.entrypoint import main

    monkeypatch.setenv("PORT", port)
    with pytest.raises(ValueError, match="PORT"):
        main()


def test_seed_identity_cannot_be_reused_for_non_synthetic_input(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'collision.db'}"
    pipeline = Pipeline(url)
    pipeline.initialize()
    pipeline.stage("synthetic-demo-v1", {"unexpected": "not-demo-data"})
    monkeypatch.setenv("DATAGUARD_SEED_DEMO", "true")
    with pytest.raises(ValueError, match="unexpected input"), TestClient(create_app(url)):
        pass
