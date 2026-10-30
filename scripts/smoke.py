"""End-to-end HTTP smoke against a running PostgreSQL-backed container."""

import copy
import json
import os
import uuid
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dataguard.cli import fixture

base = os.getenv("BASE_URL", "http://127.0.0.1:8003")
token = os.environ["DATAGUARD_TOKEN"]


def call(path, body=None, auth=True):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = "Bearer " + token
    request = Request(
        base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers
    )
    with urlopen(request, timeout=15) as response:
        raw = response.read().decode()
        return json.loads(raw) if response.headers.get_content_type() == "application/json" else raw


assert call("/ready")["status"] == "ready"
assert "Trust the published data" in call("/")
try:
    call("/recover", {}, auth=False)
    raise AssertionError("unauthenticated write accepted")
except HTTPError as error:
    assert error.code == 401
payload = fixture(30)
key = "smoke-" + uuid.uuid4().hex
batch = call("/batches", {"key": key, "payload": payload})["batch_id"]
assert call(f"/batches/{batch}/run", {})["status"] == "published"
assert call("/batches", {"key": key, "payload": payload})["batch_id"] == batch
bad = copy.deepcopy(payload)
bad["trades"].append(copy.deepcopy(bad["trades"][0]))
rejected = call("/batches", {"key": key + "-bad", "payload": bad})["batch_id"]
result = call(f"/batches/{rejected}/run", {})
assert result["status"] == "rejected"
assert any(d["rule"] == "unique" for d in result["diagnostics"])
current = call("/snapshots/" + payload["period"])
assert current["batch_id"] == batch
assert len(current["trades"]) == 30
assert call("/quarantine")[0]["batch_id"] == rejected
assert "dataguard_database_up 1.0" in call("/metrics")
print(
    json.dumps(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "target": base,
            "database": "PostgreSQL via Compose",
            "ready": True,
            "dashboard_served": True,
            "unauthenticated_write_denied": True,
            "publication": "published",
            "duplicate_input": "rejected",
            "last_valid_batch_preserved": True,
            "idempotent_replay": True,
            "metrics_db_up": True,
        },
        indent=2,
    )
)
