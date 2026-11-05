import argparse
import json
import os
import pathlib
import re
import secrets
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime

import httpx

if not __debug__:
    raise SystemExit("Run the monitoring drill with Python assertions enabled.")

parser = argparse.ArgumentParser(
    description="Observe real DataGuard alerts against a disposable local PostgreSQL cluster."
)
parser.add_argument(
    "--prometheus-workdir",
    required=True,
    type=pathlib.Path,
    help="Ignored work directory with extracted Ubuntu package under ubuntu/.",
)
parser.add_argument(
    "--postgres-data",
    required=True,
    type=pathlib.Path,
    help="Existing stopped disposable test cluster initialized with local trust.",
)
parser.add_argument("--postgres-bin", required=True, type=pathlib.Path)
parser.add_argument("--output", required=True, type=pathlib.Path)
args = parser.parse_args()
root = args.prometheus_workdir.resolve()
pgdir = args.postgres_data.resolve()
pgbin = args.postgres_bin.resolve()
private = pathlib.Path(".vercel").resolve()
if (
    private not in root.parents
    or private not in pgdir.parents
    or not (pgdir / "PG_VERSION").is_file()
    or (pgdir / "postmaster.pid").exists()
):
    raise SystemExit(
        "Use a stopped disposable PostgreSQL cluster and Prometheus work directory inside .vercel."
    )
pg_database = "dataguard_monitoring_" + secrets.token_hex(4) + "_test"
timeseries = "drill-data-" + secrets.token_hex(5)
wsl = ["wsl.exe", "-d", "Ubuntu", "--cd", str(root), "--"]
prometheus_version = subprocess.check_output(
    wsl + ["./ubuntu/usr/bin/prometheus", "--version"],
    stderr=subprocess.STDOUT,
    text=True,
    timeout=15,
).splitlines()[0]
postgresql_version = subprocess.check_output(
    [str(pgbin / "pg_ctl.exe"), "--version"], text=True, timeout=10
).strip()
route = subprocess.check_output(wsl + ["ip", "-4", "route", "show", "default"], text=True)
gateway = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", route)[1]
assert gateway.startswith("172.")


def free_port(host):
    with socket.socket() as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


pg_port = free_port("127.0.0.1")
api_port = free_port(gateway)
api = f"http://{gateway}:{api_port}"
prom_port = int(
    subprocess.check_output(
        wsl
        + [
            "python3",
            "-c",
            'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])',
        ],
        text=True,
    ).strip()
)
prom = f"http://127.0.0.1:{prom_port}"
token = secrets.token_urlsafe(48)
headers = {"Authorization": f"Bearer {token}"}
(root / "bearer-token").write_text(token, encoding="ascii")
(root / "alerts.yml").write_bytes(pathlib.Path("deploy/alerts.yml").read_bytes())
(root / "prometheus.yml").write_text(
    f"""global:
  scrape_interval: 15s
  scrape_timeout: 10s
  evaluation_interval: 2s
rule_files: [alerts.yml]
scrape_configs:
  - job_name: dataguard
    authorization:
      type: Bearer
      credentials_file: bearer-token
    static_configs:
      - targets: ['{gateway}:{api_port}']
""",
    encoding="ascii",
)
api_proc = prom_proc = None
pg_started = False
started = time.monotonic()
observed = []


def mark(event, **values):
    row = {
        "event": event,
        "utc": datetime.now(UTC).isoformat(),
        "elapsed_s": round(time.monotonic() - started, 2),
        **values,
    }
    observed.append(row)
    print(json.dumps(row), flush=True)


def control(command):
    subprocess.run(
        command,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=35,
    )


def start_pg():
    global pg_started
    control(
        [
            str(pgbin / "pg_ctl.exe"),
            "-D",
            str(pgdir),
            "-l",
            str(root / "postgres.log"),
            "start",
            "-w",
            "-o",
            f"-h 127.0.0.1 -p {pg_port}",
        ]
    )
    pg_started = True


def stop_pg():
    global pg_started
    control([str(pgbin / "pg_ctl.exe"), "-D", str(pgdir), "stop", "-w", "-m", "fast"])
    pg_started = False


def start_api():
    global api_proc
    env = dict(
        os.environ,
        DATABASE_URL=f"postgresql+psycopg://postgres@127.0.0.1:{pg_port}/{pg_database}",
        DATAGUARD_TOKEN=token,
        DATAGUARD_AUTO_INIT="true",
        DATAGUARD_BACKGROUND_INIT="true",
        DATAGUARD_SEED_DEMO="false",
        DATAGUARD_PUBLIC_DEMO="false",
    )
    with (root / "api.log").open("ab") as log:
        api_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "dataguard.api:app",
                "--host",
                gateway,
                "--port",
                str(api_port),
                "--no-access-log",
            ],
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


def stop_api():
    global api_proc
    if api_proc and api_proc.poll() is None:
        api_proc.terminate()
        api_proc.wait(timeout=12)
    api_proc = None


def status(path, headers=None):
    return httpx.get(api + path, headers=headers, timeout=6)


def wait_for(fn, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result:
                return result
        except (httpx.TransportError, subprocess.SubprocessError):
            pass
        time.sleep(0.5)
    raise TimeoutError(getattr(fn, "__name__", "predicate"))


def prom_get(path):
    result = subprocess.check_output(
        wsl + ["curl", "-fsS", "--max-time", "5", prom + path],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )
    return json.loads(result)["data"]


def state(name):
    for group in prom_get("/api/v1/rules")["groups"]:
        for rule in group["rules"]:
            if rule["name"] == name:
                return rule["state"]
    return None


def verify_state(alert, desired, timeout=88):
    wait_for(lambda: state(alert) == desired, timeout)
    mark("prometheus_rule_state", alert=alert, state=desired)


def workspace():
    response = status("/api/quality/workspace")
    response.raise_for_status()
    return [
        {k: c[k] for k in ("id", "digest", "row_count", "source")}
        for c in response.json()["captures"]
    ]


try:
    control(wsl + ["./ubuntu/usr/bin/promtool", "check", "config", "prometheus.yml"])
    start_pg()
    control(
        [
            str(pgbin / "psql.exe"),
            "-h",
            "127.0.0.1",
            "-p",
            str(pg_port),
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"CREATE DATABASE {pg_database}",
        ]
    )
    start_api()
    wait_for(lambda: status("/ready").status_code == 200)
    before = workspace()
    assert len(before) == 1 and before[0]["row_count"] == 8
    assert status("/metrics").status_code == 401
    assert status("/metrics", {"Authorization": "Bearer invalid"}).status_code == 401
    assert "dataguard_database_up 1.0" in status("/metrics", headers).text
    mark(
        "healthy",
        ready=200,
        metrics_without_bearer=401,
        metrics_wrong_bearer=401,
        metrics_with_bearer=200,
        captures=before,
    )
    with (root / "prometheus.log").open("ab") as log:
        prom_proc = subprocess.Popen(
            wsl
            + [
                "sh",
                "-c",
                f"echo $$ > prometheus.pid; exec ./ubuntu/usr/bin/prometheus --config.file=prometheus.yml --storage.tsdb.path={timeseries} --web.listen-address=127.0.0.1:{prom_port}",
            ],
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    wait_for(
        lambda: (
            prom_get("/api/v1/query?query=up")["result"][0]["value"][1] == "1"
            if prom_get("/api/v1/query?query=up")["result"]
            else False
        ),
        30,
    )
    dbalert = "DataGuardDatabaseUnavailable"
    scrapealert = "DataGuardMetricsUnavailable"
    verify_state(dbalert, "inactive")
    verify_state(scrapealert, "inactive")
    stop_pg()
    mark("isolated_postgres_stopped")
    assert status("/health").status_code == 200 and status("/ready").status_code == 503
    metrics = status("/metrics", headers)
    assert metrics.status_code == 200 and "dataguard_database_up 0.0" in metrics.text
    replay = status("/api/quality/benchmark?policy=strict")
    assert replay.status_code == 200 and replay.json()["rows"] == 500
    mark(
        "database_outage", health=200, ready=503, metrics=200, database_up=0, public_replay_rows=500
    )
    verify_state(dbalert, "pending")
    verify_state(dbalert, "firing")
    assert state(scrapealert) == "inactive"
    start_pg()
    mark("isolated_postgres_restarted")
    wait_for(lambda: status("/ready").status_code == 200)
    verify_state(dbalert, "inactive")
    assert workspace() == before
    mark("database_recovery", ready=200, capture_identity_unchanged=True)
    stop_api()
    mark("isolated_api_stopped")
    verify_state(scrapealert, "pending")
    verify_state(scrapealert, "firing")
    assert state(dbalert) == "inactive"
    start_api()
    mark("isolated_api_restarted")
    wait_for(lambda: status("/ready").status_code == 200)
    verify_state(scrapealert, "inactive")
    assert workspace() == before
    assert status("/metrics").status_code == 401
    mark("service_recovery", ready=200, metrics_without_bearer=401, capture_identity_unchanged=True)
    result = {
        "prometheus_version": prometheus_version,
        "postgresql_version": postgresql_version,
        "environment": "isolated PostgreSQL and DataGuard with local WSL Prometheus",
        "production_touched": False,
        "hold_seconds": 60,
        "drill_scrape_interval_seconds": 15,
        "drill_scrape_timeout_seconds": 10,
        "drill_evaluation_interval_seconds": 2,
        "rules_copied_unmodified": True,
        "rule_states": observed,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
finally:
    stop_api()
    if prom_proc is not None:
        pid = (
            (root / "prometheus.pid").read_text().strip()
            if (root / "prometheus.pid").exists()
            else ""
        )
        if pid.isdecimal() and prom_proc.poll() is None:
            subprocess.run(
                wsl + ["sh", "-c", f'test "$(cat /proc/{pid}/comm)" = prometheus && kill {pid}'],
                capture_output=True,
            )
        try:
            prom_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            prom_proc.terminate()
    if pg_started:
        stop_pg()
    (root / "bearer-token").unlink(missing_ok=True)
