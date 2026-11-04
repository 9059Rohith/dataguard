"""Measure DataGuard's authenticated API on the pinned 500-repository source."""

import argparse
import json
import math
import os
import platform
import secrets
import statistics
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import make_url, select

from dataguard.api import create_app
from dataguard.quality import settings
from dataguard.quality_benchmark import benchmark_contract, load_source, replay


@contextmanager
def isolated_database(backend):
    if backend == "sqlite":
        with tempfile.TemporaryDirectory(prefix="dg-quality-bench-") as temp:
            yield "sqlite:///" + (Path(temp) / "benchmark.db").as_posix()
        return
    url = make_url(os.environ["DATAGUARD_BENCH_POSTGRES_ADMIN"])
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use a local disposable PostgreSQL server for the benchmark")
    if url.query:
        raise ValueError("PostgreSQL admin URL query parameters are prohibited")
    database = "dg_quality_bench_" + secrets.token_hex(8)
    with psycopg.connect(
        host=url.host,
        port=url.port,
        dbname=url.database or "postgres",
        user=url.username,
        password=url.password,
        autocommit=True,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            yield url.set(database=database, drivername="postgresql+psycopg")
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def checked_request(client, method, path, expected, **kwargs):
    started = perf_counter_ns()
    response = client.request(method, "/api/quality" + path, **kwargs)
    elapsed_ms = (perf_counter_ns() - started) / 1_000_000
    if response.status_code != expected:
        raise AssertionError(
            f"{method} {path}: expected HTTP {expected}, got {response.status_code}"
        )
    return response.json(), elapsed_ms


def stats(values):
    ordered = sorted(values)
    return {
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "max_ms": ordered[-1],
        "raw_ms": values,
    }


def benchmark(backend, samples):
    source = load_source()
    records = source["records"]
    sha256 = source["sha256"]
    missing_license = sum(not row.get("license") for row in records)
    archived = sum(row.get("archived") is not False for row in records)
    assert missing_license > 0 and archived > 0
    upload = json.dumps({"name": "Apache public repositories", "records": records}).encode()
    measurements = {
        "upload_and_publish": [],
        "recheck_and_quarantine": [],
        "blocked_recovery": [],
        "accepted_recovery": [],
    }
    token = secrets.token_urlsafe(40)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    env = {"DATAGUARD_TOKEN": token, "DATAGUARD_AUTO_INIT": "true", "DATAGUARD_SEED_DEMO": "false"}
    with isolated_database(backend) as url, patch.dict(os.environ, env):
        app = create_app(url)
        with TestClient(app, headers=headers) as client:
            store = app.state.quality
            with store.engine.connect() as connection:
                database_version = ".".join(map(str, connection.dialect.server_version_info))

            def recovery_reference():
                with store.engine.connect() as connection:
                    return connection.execute(
                        select(settings.c.document).where(settings.c.key == "restored")
                    ).scalar()

            for iteration in range(samples + 1):
                checked_request(
                    client, "PUT", "/contract", 200, json=benchmark_contract("baseline")
                )
                published, publish_ms = checked_request(
                    client, "POST", "/uploads", 201, content=upload
                )
                assert published["status"] == "published" and published["digest"] == sha256
                assert published["row_count"] == 500
                reference = {"capture_id": published["id"]}
                checked_request(client, "PUT", "/contract", 200, json=benchmark_contract("strict"))
                quarantined, quarantine_ms = checked_request(
                    client, "POST", "/recheck", 201, json=reference
                )
                assert quarantined["status"] == "quarantined" and quarantined["digest"] == sha256
                assert quarantined["parent_id"] == published["id"]
                assert {
                    check["key"]: check["failed"]
                    for check in quarantined["checks"]
                    if check["failed"]
                } == {
                    "license": missing_license,
                    "archived": archived,
                }
                previous = recovery_reference()
                _, blocked_ms = checked_request(client, "POST", "/restore", 409, json=reference)
                assert recovery_reference() == previous
                checked_request(
                    client, "PUT", "/contract", 200, json=benchmark_contract("baseline")
                )
                restored, recover_ms = checked_request(
                    client, "POST", "/restore", 200, json=reference
                )
                assert restored == recovery_reference()
                assert restored["capture_id"] == published["id"] and restored["digest"] == sha256
                assert store.get(published["id"]) == published
                if iteration:  # The first complete workflow warms the API and database.
                    measurements["upload_and_publish"].append(publish_ms)
                    measurements["recheck_and_quarantine"].append(quarantine_ms)
                    measurements["blocked_recovery"].append(blocked_ms)
                    measurements["accepted_recovery"].append(recover_ms)
    return {
        "database": backend,
        "database_version": database_version,
        "measured_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "samples_per_operation": samples,
        "warmup_cycles": 1,
        "upload_json_bytes": len(upload),
        "operations": {name: stats(values) for name, values in measurements.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("sqlite", "postgresql", "both"), default="sqlite")
    parser.add_argument("--samples", type=int, choices=range(5, 101), default=30, metavar="5..100")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    backends = ["sqlite", "postgresql"] if args.backend == "both" else [args.backend]
    source = load_source()
    output = {
        "source": source["source"],
        "source_sha256": source["sha256"],
        "captured_at": source["captured_at"],
        "source_rows": len(source["records"]),
        "replay": {policy: replay(policy) for policy in ("baseline", "strict")},
        "protocol": "One sequential FastAPI TestClient. Measures request through full response with local SQL. Excludes source retrieval, startup, warmup, contract changes and external HTTP. The production upload API timestamps receipt independently of GitHub observation time.",
        "runs": [benchmark(backend, args.samples) for backend in backends],
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")
    for run in output["runs"]:
        print(
            run["database"],
            "p95 ms",
            {k: round(v["p95_ms"], 2) for k, v in run["operations"].items()},
        )


if __name__ == "__main__":
    main()
