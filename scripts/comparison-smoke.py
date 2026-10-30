"""Real database + HTTP comparison probe; writes synthetic versions to a disposable DB."""

import copy
import json
import math
import os
import platform
import secrets
import socket
import subprocess  # nosec B404
import sys
import time
import uuid
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dataguard.cli import fixture
from dataguard.service import Pipeline

pipeline = Pipeline(os.environ["DATABASE_URL"])
pipeline.initialize()
prefix = "comparison-probe-" + uuid.uuid4().hex
measurements = []
for rows in (100, 10000):
    source = fixture(rows)
    before = pipeline.stage(f"{prefix}-{rows}-before", source)
    assert pipeline.process(before)["status"] == "published"
    target = copy.deepcopy(source)
    target["trades"][0]["amount_cents"] += 50
    target["settlements"][0]["amount_cents"] += 50
    after = pipeline.stage(f"{prefix}-{rows}-after", target)
    assert pipeline.process(after)["status"] == "published"
    timings = []
    for _ in range(50):
        started = time.perf_counter()
        result = pipeline.compare(source["period"], before, after)
        timings.append((time.perf_counter() - started) * 1000)
        assert result["tables"]["trades"] == {
            "before": rows,
            "after": rows,
            "added": 0,
            "removed": 0,
            "changed": 1,
            "unchanged": rows - 1,
        }
    ordered = sorted(timings)
    measurements.append(
        {
            "trades_per_version": rows,
            "settlements_per_version": 1,
            "samples": 50,
            "p50_ms": round(ordered[math.ceil(len(ordered) * 0.50) - 1], 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
            "p99_ms": round(ordered[math.ceil(len(ordered) * 0.99) - 1], 3),
            "raw_ms": [round(value, 3) for value in timings],
            "response_bytes": len(json.dumps(result).encode()),
        }
    )

invalid = copy.deepcopy(target)
invalid["settlements"][0]["amount_cents"] += 1
rejected = pipeline.stage(prefix + "-rejected", invalid)
assert pipeline.process(rejected)["status"] == "rejected"
head = pipeline.current(source["period"])
try:
    pipeline.compare(source["period"], before, rejected)
    raise AssertionError("quarantined input was comparable")
except KeyError:
    pass
assert pipeline.current(source["period"]) == head

with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
token = secrets.token_urlsafe(40)
env = dict(
    os.environ,
    DATAGUARD_TOKEN=token,
    DATAGUARD_PUBLIC_DEMO="true",
    DATAGUARD_SEED_DEMO="false",
    DATAGUARD_AUTO_INIT="false",
)
child = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "dataguard.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "error",
    ],
    env=env,
)  # nosec B603


def request(path, authenticated=False):
    headers = {"Authorization": "Bearer " + token} if authenticated else {}
    try:
        # Fixed loopback HTTP URL; port and paths are created by this probe.
        with urlopen(Request(f"http://127.0.0.1:{port}" + path, headers=headers), timeout=5) as r:  # nosec B310
            return r.status, json.loads(r.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


try:
    for _ in range(100):
        try:
            assert request("/ready")[0] == 200
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise AssertionError("HTTP probe did not start")
    route = f"/snapshots/{source['period']}/compare?from_batch={before}&to_batch={after}"
    assert request(route)[0] == 401
    code, response = request(route, True)
    assert code == 200 and response["tables"]["trades"]["changed"] == 1
    assert "amount_cents" not in json.dumps(response)
    assert request(route.replace(f"to_batch={after}", f"to_batch={rejected}"), True)[0] == 404
    assert request(route.replace(source["period"], "2024-01-01"), True)[0] == 404
finally:
    child.terminate()
    child.wait(timeout=10)

print(
    json.dumps(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "environment": {
                "python": platform.python_version(),
                "os": platform.platform(),
                "database": pipeline.engine.dialect.name,
                "concurrency": 1,
            },
            "operation": "read-only SQL accepted-version comparison (no HTTP timing)",
            "method": "nearest-rank; 50 sequential samples at each row count; no warm-up exclusion",
            "proofs": {
                "max_admitted_trade_count": 10000,
                "head_preserved": True,
                "quarantine_excluded": True,
                "anonymous_http": 401,
                "authenticated_http": 200,
                "wrong_period_http": 404,
                "rejected_version_http": 404,
                "raw_record_values_absent": True,
            },
            "measurements": measurements,
        },
        indent=2,
    )
)
