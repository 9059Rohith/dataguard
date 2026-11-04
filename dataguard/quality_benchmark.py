"""Read-only evaluation of a versioned public repository benchmark source."""

import json
from functools import cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import FileResponse

from dataguard.quality import Contract, digest, evaluate, parse_time

SOURCE_PATH = Path(__file__).with_name("quality_benchmark_source.json")
REPORT_PATH = Path(__file__).with_name("quality_benchmark_report.json")
BenchmarkPolicy = Literal["baseline", "strict"]
router = APIRouter(prefix="/api/quality/benchmark", tags=["Repository quality benchmark"])


@cache
def load_source():
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    rows = source["records"]
    if len(rows) != 500 or len({row["id"] for row in rows}) != 500:
        raise ValueError("Benchmark source must contain 500 distinct repositories")
    if digest(rows) != source["sha256"]:
        raise ValueError("Benchmark source fingerprint does not match its records")
    return source


def benchmark_contract(policy: BenchmarkPolicy):
    strict = policy == "strict"
    return Contract(min_rows=500, require_license=strict, reject_archived=strict).model_dump()


@router.get("")
def replay(policy: BenchmarkPolicy = "baseline"):
    source = load_source()
    captured_at, rows = source["captured_at"], source["records"]
    contract = benchmark_contract(policy)
    checks = evaluate(rows, captured_at, contract, as_of=parse_time(captured_at))
    return {
        "source": source["source"],
        "scope": source["scope"],
        "captured_at": captured_at,
        "evaluated_at": captured_at,
        "sha256": source["sha256"],
        "rows": len(rows),
        "policy": policy,
        "contract": contract,
        "outcome": "quarantined" if any(check["failed"] for check in checks) else "published",
        "checks": [
            {
                "key": check["key"],
                "title": check["title"],
                "failed": check["failed"],
                "tested": check["tested"],
                "examples": [rows[index]["full_name"] for index in check["indices"][:4]],
            }
            for check in checks
        ],
    }


@router.get("/artifacts/{artifact}")
def download(artifact: Literal["source", "report"]):
    path = SOURCE_PATH if artifact == "source" else REPORT_PATH
    return FileResponse(path, media_type="application/json", filename=path.name)
