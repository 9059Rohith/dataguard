from fastapi.testclient import TestClient
from test_pipeline import fixture_payload

from dataguard.api import create_app


def test_write_auth_fails_closed_and_health_dashboard_work(tmp_path, monkeypatch):
    monkeypatch.delenv("DATAGUARD_TOKEN", raising=False)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.db'}")) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 200
        assert c.get("/").status_code == 200
        assert c.get("/metrics").status_code == 200
        assert (
            c.post("/batches", json={"key": "a", "payload": fixture_payload()}).status_code == 503
        )
        monkeypatch.setenv("DATAGUARD_TOKEN", "test-token-that-is-long-enough-12345")
        assert (
            c.post("/batches", json={"key": "a", "payload": fixture_payload()}).status_code == 401
        )
        headers = {"Authorization": "Bearer test-token-that-is-long-enough-12345"}
        r = c.post("/batches", json={"key": "a", "payload": fixture_payload()}, headers=headers)
        assert r.status_code == 201
        bid = r.json()["batch_id"]
        assert c.post(f"/batches/{bid}/run", headers=headers).json()["status"] == "published"
        assert c.get("/snapshots").json()[0]["batch_id"] == bid
        assert c.get(f"/batches/{bid}").status_code == 401
        assert c.get(f"/batches/{bid}", headers=headers).status_code == 200
