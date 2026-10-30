"""Safe read-only check of a running synthetic public profile; no credentials required."""

import json
import os
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = os.getenv("BASE_URL", "http://127.0.0.1:18084")


def call(path, data=None):
    try:
        with urlopen(Request(base + path, data=data), timeout=15) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


assert call("/health") == (200, {"status": "alive"})
assert call("/ready") == (200, {"status": "ready"})
status, summary = call("/summary")
assert status == 200 and summary["public_demo"] is True
assert summary["attempts"].get("published", 0) >= 1
assert 1 <= len(summary["snapshots"]) <= 100
batch = summary["snapshots"][0]["batch_id"]
period = summary["snapshots"][0]["period"]
checks = {}
for path in ("/metrics", f"/batches/{batch}", "/quarantine", f"/snapshots/{period}"):
    code, _ = call(path)
    assert code in (401, 503)
    checks[path] = code
mutation, _ = call("/recover", b"not-json")
assert mutation in (401, 503)
assert "synthetic-trade" not in json.dumps(summary)
print(
    json.dumps(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "base": base,
            "public_demo": True,
            "actual_published_attempts": summary["attempts"]["published"],
            "active_batch_id": batch,
            "public_partition_count": len(summary["snapshots"]),
            "private_routes_denied": checks,
            "unauthenticated_mutation_status": mutation,
            "raw_records_absent_from_summary": True,
        },
        indent=2,
    )
)
