import json
import math
import statistics

from fastapi.testclient import TestClient

from dataguard.api import create_app
from dataguard.quality import digest

BASE = "/api/quality/benchmark"


def test_public_replay_uses_real_pinned_source_and_never_publishes(tmp_path, monkeypatch):
    token = "benchmark-test-operator-token-1234567890"
    monkeypatch.setenv("DATAGUARD_TOKEN", token)
    with TestClient(create_app(f"sqlite:///{tmp_path / 'quality.db'}")) as client:
        before = client.get("/api/quality/workspace").json()
        source_response = client.get(BASE + "/artifacts/source")
        assert source_response.status_code == 200
        assert source_response.headers["cache-control"] == "no-store"
        source = source_response.json()
        assert source["sha256"] == digest(source["records"])
        assert len({row["id"] for row in source["records"]}) == 500
        assert all(row["full_name"].startswith("apache/") for row in source["records"])
        for index, page in enumerate(source["pages"]):
            assert page["records_sha256"] == digest(
                source["records"][index * 100 : (index + 1) * 100]
            )
        baseline = client.get(BASE).json()
        strict = client.get(BASE, params={"policy": "strict"}).json()
        assert baseline["outcome"] == "published" and strict["outcome"] == "quarantined"
        assert baseline["sha256"] == strict["sha256"] == source["sha256"]
        assert baseline["evaluated_at"] == strict["evaluated_at"] == source["captured_at"]
        failures = {check["key"]: check["failed"] for check in strict["checks"] if check["failed"]}
        assert failures == {"license": 96, "archived": 177}
        assert client.get(BASE, params={"policy": "custom"}).status_code == 422
        assert client.get(BASE + "/artifacts/private").status_code == 422
        assert client.post(BASE, json={}).status_code == 401
        assert client.post(BASE, headers={"Authorization": f"Bearer {token}"}).status_code == 405
        after = client.get("/api/quality/workspace").json()
        for key in ("captures", "contract", "actions", "restored"):
            assert before[key] == after[key]


def test_benchmark_report_metrics_recompute_from_raw_samples(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'quality.db'}")) as client:
        response = client.get(BASE + "/artifacts/report")
        assert response.status_code == 200
        report = json.loads(response.content)
        assert report["source_rows"] == 500
        assert report["source_sha256"] == client.get(BASE).json()["sha256"]
        assert {run["database"] for run in report["runs"]} == {"sqlite", "postgresql"}
        for run in report["runs"]:
            assert run["samples_per_operation"] >= 30
            for operation in run["operations"].values():
                samples = sorted(operation["raw_ms"])
                assert len(samples) == run["samples_per_operation"] and samples[0] > 0
                assert operation["median_ms"] == statistics.median(samples)
                assert operation["p95_ms"] == samples[math.ceil(0.95 * len(samples)) - 1]
                assert operation["max_ms"] == samples[-1]
