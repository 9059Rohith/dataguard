"""Exercise the canonical public comparison without writes or model requests."""

import hashlib
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://rohith-dataguard.vercel.app"


def call(path, body=None, origin=None):
    raw = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if raw else {}
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(BASE + path, data=raw, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


assert json.loads(call("/ready")[2])["status"] == "ready"
assert call("/console/impact")[0] == 200
assert call("/impact.js")[0] == 200
before = json.loads(call("/api/quality/workspace")[2])
capture = before["captures"][0]
body = {
    "capture_id": capture["id"],
    "analysis_at": datetime.now(UTC).isoformat(),
    "baseline": {},
    "candidate": {"min_stars": 100000},
}
status, headers, raw = call("/api/quality/contract-impact", body)
assert status == 200, status
assert headers.get("Cache-Control", headers.get("cache-control")) == "no-store"
report = json.loads(raw)
assert report["capture"]["sha256"] == capture["digest"]
assert report["capture"]["rows"] == len(capture["records"]) == 8
expected = sum(row["stargazers_count"] < 100000 for row in capture["records"])
assert report["transitions"]["accepted_to_rejected"] == expected
assert report == json.loads(call("/api/quality/contract-impact", body)[2])
document = {key: value for key, value in report.items() if key != "sha256"}
assert (
    hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    == report["sha256"]
)
assert call("/api/quality/contract-impact", body, "https://untrusted.example")[0] == 403
assert call("/api/quality/recheck", {"capture_id": capture["id"]})[0] == 401
after = json.loads(call("/api/quality/workspace")[2])
for key in ("captures", "contract", "actions", "restored"):
    assert before[key] == after[key]
provider = json.loads(call("/api/quality/provider")[2])
assert provider["model"] == "gemini-3.5-flash-lite"
assert provider["public_demo"]["limits"] == {
    "per_client": {"limit": 3, "seconds": 600},
    "global_minute": {"limit": 2, "seconds": 60},
    "global_day": {"limit": 30, "seconds": 86400},
}
evidence = {
    "verified_at": datetime.now(UTC).isoformat(),
    "base_url": BASE,
    "checks": {
        "ready": True,
        "page_and_module": True,
        "actual_source_rows": 8,
        "transition_count_matches_source": True,
        "reproducible_response": True,
        "report_fingerprint": True,
        "cross_origin_rejected": True,
        "private_write_requires_authentication": True,
        "stored_state_unchanged": True,
        "fixed_gemini_model": True,
        "persistent_ai_limits_unchanged": True,
        "model_requests_made": 0,
    },
    "public_captures": len(before["captures"]),
    "report": report,
}
Path("evidence/contract-impact-public.json").write_text(
    json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"checks": evidence["checks"], "transitions": report["transitions"]}, indent=2))
