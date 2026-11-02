"""Bounded local CPU benchmark over the checked-in, actual public source capture."""

import json
import platform
import statistics
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from dataguard.contract_impact import ContractImpactRequest, compare_contracts, content_hash

source = json.loads(Path("dataguard/source_capture.json").read_text(encoding="utf-8"))
document = {
    **source,
    "id": "github-" + content_hash(source)[:24],
    "visibility": "public",
    "digest": content_hash(source["records"]),
}
request = ContractImpactRequest(
    capture_id=document["id"],
    analysis_at=source["captured_at"],
    baseline={},
    candidate={
        "accepted_languages": ["Python"],
        "reject_archived": True,
        "max_push_age_hours": 168,
        "max_open_issues": 1000,
    },
)
samples = []
for _ in range(1000):
    started = perf_counter()
    report = compare_contracts(document, request)
    samples.append((perf_counter() - started) * 1000)
cold_sample_ms = samples[0]
samples.sort()
output = {
    "measured_at": datetime.now(UTC).isoformat(),
    "python": platform.python_version(),
    "platform": platform.system(),
    "samples": len(samples),
    "rows": len(source["records"]),
    "rules_per_policy": 6,
    "capture_sha256": document["digest"],
    "median_ms": statistics.median(samples),
    "p95_ms": samples[949],
    "max_ms": max(samples),
    "first_sample_including_imports_ms": cold_sample_ms,
    "candidate_accepted": report["candidate"]["accepted"],
    "notes": "Local evaluator elapsed time, including first lazy imports; excludes HTTP and database latency.",
}
Path("evidence/contract-impact-benchmark.json").write_text(
    json.dumps(output, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(output, indent=2))
