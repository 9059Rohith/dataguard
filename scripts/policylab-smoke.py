"""Actual HTTP PolicyLab proof against a caller-started minimal image and *_test DB.

Run with DATABASE_URL, DATAGUARD_TOKEN and DATAGUARD_SMOKE_URL in the environment.
Secrets are never printed. This intentionally creates synthetic accepted and
rejected batches, but refuses any database whose name does not end in _test.
"""

import json
import os
import platform
import time
import uuid
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy.engine import make_url

from dataguard.cli import fixture
from dataguard.service import Pipeline


def main():
    url = os.environ["DATABASE_URL"]
    if not (make_url(url).database or "").endswith("_test"):
        raise ValueError("Smoke database must end in _test")
    address = os.environ.get("DATAGUARD_SMOKE_URL", "http://127.0.0.1:18087")
    if address != "http://127.0.0.1:18087":
        raise ValueError("Smoke address must be the fixed loopback endpoint")
    token = os.environ["DATAGUARD_TOKEN"]
    pipeline = Pipeline(url)
    pipeline.initialize()
    prefix = "policylab-http-" + uuid.uuid4().hex
    proofs = {}

    def request(path, body=None, authenticated=True):
        headers = {"Authorization": "Bearer " + token} if authenticated else {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        raw = None if body is None else json.dumps(body).encode()
        try:
            # Address is restricted above to fixed loopback, paths are fixed by this probe.
            with urlopen(Request(address + path, data=raw, headers=headers), timeout=30) as r:  # nosec B310
                return r.status, json.loads(r.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    try:
        for _ in range(50):
            try:
                if request("/ready")[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Minimal-image HTTP service did not become ready")
        ids = []
        for count in (2, 10000):
            source = fixture(count)
            status, result = request("/batches", {"key": f"{prefix}-{count}", "payload": source})
            assert status == 201
            batch_id = result["batch_id"]
            assert request(f"/batches/{batch_id}/run", {})[1]["status"] == "published"
            ids.append(batch_id)
        baseline = {
            "version": 1,
            "rules": [
                {
                    "id": "amount-cap",
                    "kind": "range",
                    "table": "trades",
                    "field": "amount_cents",
                    "minimum": 1,
                    "maximum": 100000,
                }
            ],
        }
        candidate = {"version": 1, "rules": [dict(baseline["rules"][0], maximum=500)]}
        body = {
            "baseline": baseline,
            "candidate": candidate,
            "sample_limit": 5,
            "versions": [{"period": source["period"], "batch_id": batch_id} for batch_id in ids],
        }
        head_before = pipeline.current(source["period"])
        attempts_before = pipeline.summary()
        denied = request("/policies/impact", body, authenticated=False)
        assert denied[0] == 401
        started = time.perf_counter()
        status, report = request("/policies/impact", body)
        elapsed = (time.perf_counter() - started) * 1000
        assert status == 200, status
        assert report["summary"] == {
            "evaluated_versions": 2,
            "unchanged_accept": 1,
            "new_rejection": 1,
            "new_acceptance": 0,
            "unchanged_reject": 0,
        }
        assert [
            version["candidate"]["rules"][0]["violation_count"] for version in report["versions"]
        ] == [0, 9599]
        large = report["versions"][1]["candidate"]["rules"][0]
        assert large["evaluated_rows"] == 10000 and len(large["sample_tokens"]) == 5
        assert large["samples_truncated"]
        assert report["recommendation"]["stage"] == "block_candidate"
        assert pipeline.current(source["period"]) == head_before
        assert pipeline.summary() == attempts_before
        assert prefix not in json.dumps(report)
        assert '"USD"' not in json.dumps(report)
        assert request("/policies/impact", {"secret-bad-field": "private-value"}) == (
            422,
            {"detail": "Invalid policy request"},
        )
        invalid = fixture(2)
        invalid["settlements"][0]["amount_cents"] += 1
        bad_id = request("/batches", {"key": prefix + "-invalid", "payload": invalid})[1][
            "batch_id"
        ]
        assert request(f"/batches/{bad_id}/run", {})[1]["status"] == "rejected"
        body["versions"] = [{"period": source["period"], "batch_id": bad_id}]
        assert request("/policies/impact", body) == (404, {"detail": "Record not found"})
        schema = request("/openapi.json")[1]
        operation = schema["paths"]["/policies/impact"]["post"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/ImpactReport")
        proofs.update(
            {
                "actual_http": True,
                "unauthenticated_denied": True,
                "typed_openapi": True,
                "invalid_input_redacted": True,
                "quarantined_version_excluded": True,
                "published_state_unchanged": True,
                "max_admitted_trade_version_evaluated": True,
                "bounded_opaque_samples": True,
                "overstrict_candidate_blocked": True,
            }
        )
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "probe_python": platform.python_version(),
                    "database": pipeline.engine.dialect.name,
                    "source_versions": [2, 10000],
                    "observed_violation_counts": [0, 9599],
                    "single_request_ms": round(elapsed, 3),
                    "response_bytes": len(json.dumps(report).encode()),
                    "proofs": proofs,
                    "scope": "one synthetic max-trade HTTP experiment; not a performance distribution or production-accuracy estimate",
                },
                indent=2,
            )
        )
    finally:
        pipeline.engine.dispose()


if __name__ == "__main__":
    main()
