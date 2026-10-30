import json
import os
import subprocess
import sys

from dataguard.cli import fixture
from dataguard.service import Pipeline


def test_demo_proves_actual_killed_worker_recovery(tmp_path):
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{tmp_path / 'demo.db'}")
    result = subprocess.run(
        [sys.executable, "-m", "dataguard.cli", "demo", "--samples", "10", "--rows", "5"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["proofs"]["killed_worker_exit_code"] == 91
    assert evidence["proofs"]["previous_snapshot_preserved"]
    assert evidence["proofs"]["recovered_without_duplicates"]
    assert evidence["proofs"]["rejection_preserved_snapshot"]
    assert evidence["benchmark"]["samples"] == 10
    assert 0 < evidence["benchmark"]["p50_ms"] <= evidence["benchmark"]["p99_ms"]


def test_cli_compare_reads_published_versions_without_republishing(tmp_path):
    url = f"sqlite:///{tmp_path / 'comparison.db'}"
    pipeline = Pipeline(url)
    pipeline.initialize()
    payload = fixture(2)
    before = pipeline.stage("cli-before", payload)
    pipeline.process(before)
    after = pipeline.stage("cli-after", payload)
    pipeline.process(after)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dataguard.cli",
            "--database",
            url,
            "compare",
            payload["period"],
            "--from-batch",
            str(before),
            "--to-batch",
            str(after),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    comparison = json.loads(result.stdout)
    assert comparison["tables"]["trades"]["unchanged"] == 2
    assert comparison["tables"]["trades"]["changed"] == 0
    assert pipeline.summary() == {"published": 2}
