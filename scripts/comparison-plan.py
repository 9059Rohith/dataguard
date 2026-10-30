"""One fresh max-trade comparison and its actual PostgreSQL execution plan."""

import copy
import json
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

from sqlalchemy import event

from dataguard.cli import fixture
from dataguard.service import Pipeline


class Captured(Exception):
    pass


pipeline = Pipeline(os.environ["DATABASE_URL"])
pipeline.initialize()
source = fixture(10000)
prefix = "comparison-plan-" + uuid.uuid4().hex
before = pipeline.stage(prefix + "-old", source)
assert pipeline.process(before)["status"] == "published"
target = copy.deepcopy(source)
target["trades"][0]["amount_cents"] += 50
target["settlements"][0]["amount_cents"] += 50
after = pipeline.stage(prefix + "-new", target)
assert pipeline.process(after)["status"] == "published"
captured = []


def capture(_connection, _cursor, statement, parameters, _context, _many):
    if "published_trades" in statement:
        captured.append((statement, parameters))
        raise Captured


event.listen(pipeline.engine, "before_cursor_execute", capture)
try:
    try:
        pipeline.compare(source["period"], before, after)
    except Captured:
        pass
finally:
    event.remove(pipeline.engine, "before_cursor_execute", capture)
assert len(captured) == 1
statement, parameters = captured[0]
with pipeline.engine.begin() as connection:
    connection.exec_driver_sql("SET LOCAL statement_timeout = '60s'")
    settings = {
        key: connection.exec_driver_sql("SHOW " + key).scalar()
        for key in ("server_version", "jit", "jit_above_cost", "work_mem")
    }
    start = time.perf_counter()
    plan = connection.exec_driver_sql(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
    ).scalar()
    measured_ms = (time.perf_counter() - start) * 1000

proofs = {}
if os.getenv("DATAGUARD_CHECK_HTTP", "").lower() == "true":
    comparison = pipeline.compare(source["period"], before, after)
    assert comparison["tables"]["trades"] == {
        "before": 10000,
        "after": 10000,
        "added": 0,
        "removed": 0,
        "changed": 1,
        "unchanged": 9999,
    }
    assert comparison["tables"]["settlements"] == {
        "before": 1,
        "after": 1,
        "added": 0,
        "removed": 0,
        "changed": 1,
        "unchanged": 0,
    }
    invalid = copy.deepcopy(target)
    invalid["settlements"][0]["amount_cents"] += 1
    rejected = pipeline.stage(prefix + "-rejected", invalid)
    assert pipeline.process(rejected)["status"] == "rejected"
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
            # Scheme/host fixed to loopback by this probe, never caller supplied.
            with urlopen(
                Request(f"http://127.0.0.1:{port}" + path, headers=headers), timeout=5
            ) as r:  # nosec B310
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
        code, value = request(route, True)
        assert code == 200 and value["tables"] == comparison["tables"]
        assert "amount_cents" not in json.dumps(value)
        assert request(route.replace(f"to_batch={after}", f"to_batch={rejected}"), True)[0] == 404
        assert request(route.replace(source["period"], "2024-01-01"), True)[0] == 404
        assert pipeline.current(source["period"])["batch_id"] == after
        schema = request("/openapi.json")[1]
        assert schema["paths"]["/snapshots/{period}/compare"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/VersionComparison")
        proofs = {
            "counts_correct": True,
            "anonymous_http": 401,
            "authenticated_http": 200,
            "rejected_version_http": 404,
            "wrong_period_http": 404,
            "head_preserved": True,
            "raw_record_values_absent": True,
            "typed_openapi": True,
        }
    finally:
        child.terminate()
        child.wait(timeout=10)
print(
    json.dumps(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "python": platform.python_version(),
            "os": platform.platform(),
            "trades_per_version": 10000,
            "settlements_per_version": 1,
            "method": "Actual first trade-count statement intercepted before execution; EXPLAIN ANALYZE executes it once on freshly published versions. Provenance lookup excluded from timing.",
            "wall_ms": round(measured_ms, 3),
            "settings": settings,
            "statement": statement,
            "parameters": parameters,
            "plan": plan,
            "proofs": proofs,
        },
        indent=2,
    )
)
