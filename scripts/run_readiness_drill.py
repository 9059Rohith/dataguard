"""Native Windows, local-only PostgreSQL cold-start/outage/recovery proof."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg

if not __debug__:
    raise SystemExit("Run this evidence drill with Python assertions enabled.")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--postgres-data", required=True, type=Path)
parser.add_argument("--postgres-bin", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--run-tests", action="store_true")
args = parser.parse_args()
pgdir = args.postgres_data.resolve()
pgbin = args.postgres_bin.resolve()
private = Path(".vercel").resolve()
if private not in pgdir.parents or not (pgdir / "PG_VERSION").is_file():
    raise SystemExit("Use an existing disposable cluster inside this repository's .vercel.")
if (pgdir / "postmaster.pid").exists():
    raise SystemExit("The disposable cluster must be stopped before this drill.")
work = private / ("readiness-drill-" + secrets.token_hex(5))
work.mkdir()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


pgport, apiport = free_port(), free_port()
database = "dataguard_readiness_" + secrets.token_hex(5) + "_test"
dsn = f"postgresql://postgres@127.0.0.1:{pgport}/{database}"
api = f"http://127.0.0.1:{apiport}"
token = secrets.token_urlsafe(48)
api_process = None
pg_started = False
events = []


def mark(event, **values):
    record = {"event": event, "utc": datetime.now(UTC).isoformat(), **values}
    events.append(record)
    print(json.dumps(record), flush=True)


def pg_control(*command):
    subprocess.run(
        [str(pgbin / "pg_ctl.exe"), "-D", str(pgdir), *command],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=35,
        check=True,
    )


def start_pg():
    global pg_started
    pg_control("-l", str(work / "postgres.log"), "start", "-w", "-o", f"-h 127.0.0.1 -p {pgport}")
    pg_started = True


def stop_pg():
    global pg_started
    pg_control("stop", "-m", "fast", "-w")
    pg_started = False


def start_api():
    global api_process
    env = dict(
        os.environ,
        DATABASE_URL=dsn,
        DATAGUARD_TOKEN=token,
        DATAGUARD_BACKGROUND_INIT="true",
        DATAGUARD_AUTO_INIT="false",
        DATAGUARD_PUBLIC_DEMO="false",
        DATAGUARD_SEED_DEMO="false",
    )
    with (work / "api.log").open("ab") as log:
        api_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "dataguard.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(apiport),
                "--no-access-log",
            ],
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            if request("/health").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise TimeoutError("API listener did not start")


def stop_api():
    global api_process
    if api_process and api_process.poll() is None:
        api_process.terminate()
        api_process.wait(12)
    api_process = None


def request(path):
    return httpx.get(api + path, timeout=25)


def captures():
    result = request("/api/quality/workspace")
    result.raise_for_status()
    return [
        {key: row[key] for key in ("id", "digest", "row_count", "source")}
        for row in result.json()["captures"]
    ]


try:
    start_pg()
    with psycopg.connect(dsn.rsplit("/", 1)[0] + "/postgres", autocommit=True) as conn:
        # Name is generated from fixed safe ASCII prefixes and random hex only.
        conn.execute(f"CREATE DATABASE {database}")
    stop_pg()
    start_api()
    started = time.monotonic()
    result = request("/ready")
    elapsed = time.monotonic() - started
    assert result.status_code == 503 and 14.5 <= elapsed < 22
    assert result.json() == {"detail": "Database initialization pending"}
    assert result.headers["retry-after"] == "1"
    assert request("/health").status_code == 200
    assert request("/console/overview").status_code == 200
    mark(
        "cold_database_absent",
        ready=503,
        elapsed_s=round(elapsed, 3),
        health=200,
        console=200,
        detail=result.json()["detail"],
    )
    start_pg()
    assert request("/ready").status_code == 200
    before = captures()
    assert len(before) == 1 and before[0]["row_count"] == 8
    mark("cold_recovery", ready=200, captures=before)

    stop_api()
    # Deliberate lab-only lock is a startup delay, not a fault in the source data.
    with psycopg.connect(dsn) as lock:
        lock.execute("LOCK TABLE publication_gate IN ACCESS EXCLUSIVE MODE")
        start_api()
        with ThreadPoolExecutor(max_workers=2) as pool:
            started = time.monotonic()
            pending = [pool.submit(request, "/ready") for _ in range(2)]
            time.sleep(0.6)
            assert all(not call.done() for call in pending)
            assert request("/console/overview").status_code == 200
            assert request("/health").status_code == 200
            lock.commit()
            results = [call.result(20) for call in pending]
            assert [result.status_code for result in results] == [200, 200]
            mark(
                "concurrent_cold_join",
                responses=[200, 200],
                elapsed_s=round(time.monotonic() - started, 3),
                ready_probe_delay_before_unlock_s=0.6,
                health=200,
                console=200,
            )
    stop_pg()
    result = request("/ready")
    assert result.status_code == 503
    assert result.json() == {"detail": "Database unavailable"}
    assert request("/health").status_code == 200
    assert request("/metrics").status_code == 401
    assert request("/console/overview").status_code == 200
    mark(
        "post_bootstrap_outage",
        ready=503,
        detail=result.json()["detail"],
        health=200,
        console=200,
        metrics_without_bearer=401,
    )
    start_pg()
    assert request("/ready").status_code == 200
    assert captures() == before
    mark("post_bootstrap_recovery", ready=200, source_unchanged=True)
    stop_api()
    if args.run_tests:
        env = dict(os.environ, TEST_DATABASE_URL=dsn)
        tests = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        (work / "pytest.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
        print(tests.stdout, flush=True)
        assert tests.returncode == 0
        mark("full_test_suite", summary=tests.stdout.strip().splitlines()[-1])
    report = {
        "scope": "isolated loopback PostgreSQL; no production requests or model inference",
        "postgresql_version": subprocess.check_output(
            [str(pgbin / "pg_ctl.exe"), "--version"], text=True
        ).strip(),
        "startup_wait_s": 15,
        "postgres_connect_timeout_s": 5,
        "docker_probe_client_timeout_s": 22,
        "docker_probe_outer_timeout_s": 25,
        "source_data": "Checked-in genuine eight-repository GitHub capture; unchanged",
        "controlled_faults": "Local DB stop/start; exclusive startup lock released 0.6s after launching readiness probes",
        "events": events,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
finally:
    stop_api()
    if pg_started:
        stop_pg()
