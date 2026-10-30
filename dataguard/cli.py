"""Operator CLI and reproducible real-process interruption demonstration."""

import argparse
import copy
import json
import math
import os
import platform

# subprocess invokes only the fixed interpreter/module, without a shell.
import subprocess  # nosec B404
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from dataguard.service import Pipeline


def fixture(rows=20, period=None):
    now = datetime.now(UTC)
    day = period or now.date().isoformat()
    values = [
        {
            "trade_id": f"t{i}",
            "settlement_id": "s1",
            "amount_cents": 100 + i,
            "currency": "USD",
            "event_time": f"{day}T12:00:00+00:00",
        }
        for i in range(rows)
    ]
    return {
        "period": day,
        "produced_at": now.isoformat(),
        "trades": values,
        "settlements": [
            {
                "settlement_id": "s1",
                "currency": "USD",
                "amount_cents": sum(v["amount_cents"] for v in values),
            }
        ],
    }


def demo(pipeline, samples, rows):
    if not 1 <= rows <= 10000 or not 10 <= samples <= 10000:
        raise ValueError("rows must be 1..10000; samples must be 10..10000")
    prefix = "demo-" + uuid.uuid4().hex
    body = fixture(rows)
    baseline = pipeline.stage(prefix + "-valid", body)
    assert pipeline.process(baseline)["status"] == "published"
    for fault in ("duplicate", "malformed"):
        bad = copy.deepcopy(body)
        if fault == "duplicate":
            bad["trades"].append(copy.deepcopy(bad["trades"][0]))
        else:
            bad["trades"][0]["amount_cents"] = "invalid"
        rejected = pipeline.stage(prefix + "-" + fault, bad)
        assert pipeline.process(rejected)["status"] == "rejected"
        assert pipeline.current(body["period"])["batch_id"] == baseline
    interrupted = pipeline.stage(prefix + "-interrupted", body)
    env = dict(os.environ, DATABASE_URL=pipeline.engine.url.render_as_string(hide_password=False))
    start = time.perf_counter()
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "dataguard.cli",
            "worker",
            str(interrupted),
            "--fault",
            "kill_after_insert",
        ],
        env=env,
        check=False,
        timeout=30,
    )  # nosec B603
    assert child.returncode == 91
    preserved = pipeline.current(body["period"])["batch_id"] == baseline
    assert preserved
    # Wait only the committed lease, not an arbitrary retry delay.
    lease_until = pipeline.batch(interrupted)["attempts"][-1]["lease_until"]
    time.sleep(max(0, lease_until - time.time()) + 0.02)
    results = pipeline.recover()
    assert any(r["batch_id"] == interrupted and r["status"] == "published" for r in results)
    recovery_ms = (time.perf_counter() - start) * 1000
    with pipeline.engine.connect() as c:
        count = c.execute(
            text("SELECT count(*) FROM published_trades WHERE batch_id=:id"), {"id": interrupted}
        ).scalar()
    assert count == rows
    assert pipeline.process(interrupted)["status"] == "published"
    measurements = []
    for i in range(samples):
        value = fixture(rows)
        before = time.perf_counter()
        batch_id = pipeline.stage(f"{prefix}-bench-{i}", value)
        assert pipeline.process(batch_id)["status"] == "published"
        measurements.append((time.perf_counter() - before) * 1000)
    ordered = sorted(measurements)

    def percentile(p):
        return round(ordered[math.ceil(len(ordered) * p) - 1], 3)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "database": pipeline.engine.dialect.name,
            "concurrency": 1,
        },
        "proofs": {
            "killed_worker_exit_code": child.returncode,
            "previous_snapshot_preserved": preserved,
            "rejection_preserved_snapshot": True,
            "recovered_without_duplicates": count == rows,
            "recovery_ms_including_lease": round(recovery_ms, 3),
        },
        "benchmark": {
            "operation": "stage + validate + transactional publication",
            "samples": samples,
            "trades_per_batch": rows,
            "settlements_per_batch": 1,
            "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95),
            "p99_ms": percentile(0.99),
            "raw_ms": [round(v, 3) for v in measurements],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.getenv("DATABASE_URL", "sqlite:///dataguard.db"))
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init")
    fixture_parser = subs.add_parser("fixture")
    fixture_parser.add_argument("--rows", type=int, default=20)
    fixture_parser.add_argument("--period")
    fixture_parser.add_argument("--output")
    stage = subs.add_parser("stage")
    stage.add_argument("file")
    stage.add_argument("--key", required=True)
    stage.add_argument("--run", action="store_true")
    run = subs.add_parser("run")
    run.add_argument("batch_id", type=int)
    worker = subs.add_parser("worker", help="Explicit local chaos worker; not exposed over HTTP")
    worker.add_argument("batch_id", type=int)
    worker.add_argument("--fault", choices=["after_insert", "kill_after_insert"])
    subs.add_parser("recover")
    compare = subs.add_parser("compare", help="Read-only counts between accepted period versions")
    compare.add_argument("period")
    compare.add_argument("--from-batch", type=int, required=True)
    compare.add_argument("--to-batch", type=int, required=True)
    bench = subs.add_parser("demo")
    bench.add_argument("--samples", type=int, default=100)
    bench.add_argument("--rows", type=int, default=100)
    bench.add_argument("--output")
    args = parser.parse_args()
    pipeline = Pipeline(
        args.database, lease_seconds=1 if args.command in {"demo", "worker"} else 30
    )
    if args.command in {"init", "demo"}:
        pipeline.initialize()
    if args.command == "fixture":
        output = fixture(args.rows, args.period)
    elif args.command == "init":
        output = {"status": "initialized"}
    elif args.command == "stage":
        batch_id = pipeline.stage(args.key, json.loads(Path(args.file).read_text(encoding="utf-8")))
        output = pipeline.process(batch_id) if args.run else {"batch_id": batch_id}
    elif args.command in {"run", "worker"}:
        output = pipeline.process(args.batch_id, getattr(args, "fault", None))
    elif args.command == "recover":
        output = {"results": pipeline.recover()}
    elif args.command == "compare":
        try:
            output = pipeline.compare(args.period, args.from_batch, args.to_batch)
        except (ValueError, KeyError) as error:
            parser.error(
                str(error) if isinstance(error, ValueError) else "Published version not found"
            )
    else:
        output = demo(pipeline, args.samples, args.rows)
    rendered = json.dumps(output, indent=2)
    if getattr(args, "output", None):
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
