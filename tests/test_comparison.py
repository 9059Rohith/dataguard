"""Catch wrong direction, raw-input leakage, cross-period selection and state mutation."""

import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_pipeline import fixture_payload

from dataguard.api import create_app

pytest_plugins = ["test_pipeline"]


def publish_pair(p):
    first = fixture_payload()
    first["trades"] += [
        dict(first["trades"][0], trade_id="removed", amount_cents=200),
        dict(first["trades"][0], trade_id="stable", amount_cents=300),
    ]
    first["settlements"][0]["amount_cents"] = 1700
    before = p.stage("before", first)
    assert p.process(before)["status"] == "published"
    second = copy.deepcopy(first)
    second["trades"] = [
        dict(first["trades"][0], amount_cents=1300),
        dict(first["trades"][1], trade_id="added", amount_cents=400),
        first["trades"][2],
    ]
    second["settlements"][0]["amount_cents"] = 2000
    after = p.stage("after", second)
    assert p.process(after)["status"] == "published"
    return first["period"], before, after


def test_comparison_counts_retained_versions_and_never_mutates_state(pipeline):
    period, before, after = publish_pair(pipeline)
    old = pipeline.batch(before)
    new = pipeline.batch(after)
    head = pipeline.current(period)
    result = pipeline.compare(period, before, after)
    assert result["period"] == period
    assert result["tables"] == {
        "trades": {"before": 3, "after": 3, "added": 1, "removed": 1, "changed": 1, "unchanged": 1},
        "settlements": {
            "before": 1,
            "after": 1,
            "added": 0,
            "removed": 0,
            "changed": 1,
            "unchanged": 0,
        },
    }
    for label, batch in (("from", old), ("to", new)):
        assert result[label] == {
            "batch_id": batch["id"],
            "key": batch["key"],
            "sha256": batch["digest"],
            "attempt_id": batch["attempts"][-1]["id"],
            "published_at": batch["attempts"][-1]["finished_at"],
        }
    assert "amount_cents" not in json.dumps(result)
    assert pipeline.batch(before) == old
    assert pipeline.batch(after) == new
    assert pipeline.current(period) == head
    same = pipeline.compare(period, before, before)["tables"]["trades"]
    assert same == {"before": 3, "after": 3, "added": 0, "removed": 0, "changed": 0, "unchanged": 3}


def test_reverse_comparison_swaps_additions_and_removals(pipeline):
    first = fixture_payload()
    before = pipeline.stage("one", first)
    pipeline.process(before)
    second = copy.deepcopy(first)
    second["trades"].append(dict(first["trades"][0], trade_id="extra"))
    second["settlements"][0]["amount_cents"] = 2400
    after = pipeline.stage("two", second)
    pipeline.process(after)
    assert pipeline.compare(first["period"], before, after)["tables"]["trades"]["added"] == 1
    reverse = pipeline.compare(first["period"], after, before)["tables"]["trades"]
    assert reverse["removed"] == 1
    assert reverse["added"] == 0


@pytest.mark.parametrize(
    "state", ["staged", "rejected", "failed", "running", "superseded", "missing", "foreign"]
)
def test_comparison_excludes_unpublished_and_foreign_partition(pipeline, state):
    body = fixture_payload()
    candidate = pipeline.stage("candidate", body)
    good = pipeline.stage("published", body)
    pipeline.process(good)
    if state == "rejected":
        body["trades"][0]["amount_cents"] = -10
        candidate = pipeline.stage("invalid", body)
        pipeline.process(candidate)
    elif state == "failed":
        candidate = pipeline.stage("interrupted", body)
        with pytest.raises(RuntimeError):
            pipeline.process(candidate, fault="after_insert")
    elif state == "running":
        with pipeline.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO attempts (batch_id,status,started_at,lease_until,diagnostics) "
                    "VALUES (:id,'running',0,0,'[]')"
                ),
                {"id": candidate},
            )
    elif state == "superseded":
        assert pipeline.process(candidate)["status"] == "superseded"
    elif state == "missing":
        candidate = 2147483647
    elif state == "foreign":
        body["period"] = "2024-01-01"
        body["trades"][0]["event_time"] = "2024-01-01T12:00:00+00:00"
        candidate = pipeline.stage("foreign-period", body)
        pipeline.process(candidate)
    for start, end in ((good, candidate), (candidate, good)):
        with pytest.raises(KeyError):
            pipeline.compare(fixture_payload()["period"], start, end)


@pytest.mark.parametrize(
    "period,start,end",
    [
        ("20261030", 1, 2),
        ("invalid", 1, 2),
        ("2026-10-30", 0, 2),
        ("2026-10-30", True, 2),
        ("2026-10-30", 1, 2147483648),
    ],
)
def test_comparison_validates_identifiers_before_querying(pipeline, period, start, end):
    with pytest.raises(ValueError):
        pipeline.compare(period, start, end)


def test_comparison_api_is_private_in_public_demo_and_checks_ownership(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAGUARD_TOKEN", "comparison-token-with-at-least-32-characters")
    monkeypatch.setenv("DATAGUARD_PUBLIC_DEMO", "true")
    monkeypatch.setenv("DATAGUARD_SEED_DEMO", "false")
    app = create_app(f"sqlite:///{tmp_path / 'compare.db'}")
    with TestClient(app) as client:
        period, before, after = publish_pair(app.state.pipeline)
        route = f"/snapshots/{period}/compare?from_batch={before}&to_batch={after}"
        assert client.get(route).status_code == 401
        headers = {"Authorization": "Bearer comparison-token-with-at-least-32-characters"}
        response = client.get(route, headers=headers)
        assert response.status_code == 200
        assert response.json()["tables"]["trades"]["changed"] == 1
        schema = client.get("/openapi.json").json()
        model = schema["paths"]["/snapshots/{period}/compare"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        assert model.get("$ref", "").endswith("/VersionComparison")
        assert client.get(route.replace(period, "2024-01-01"), headers=headers).status_code == 404
        assert client.get(route.replace(period, "20261030"), headers=headers).status_code == 422
        assert (
            client.get(
                route.replace(f"to_batch={after}", "to_batch=0"), headers=headers
            ).status_code
            == 422
        )
        monkeypatch.delenv("DATAGUARD_TOKEN")
        assert client.get(route).status_code == 503
