import copy
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from dataguard.service import Conflict, Pipeline


def fixture_payload():
    now = datetime.now(UTC)
    return {
        "period": now.date().isoformat(),
        "produced_at": now.isoformat(),
        "trades": [
            {
                "trade_id": "t1",
                "settlement_id": "s1",
                "amount_cents": 1200,
                "currency": "USD",
                "event_time": now.isoformat(),
            }
        ],
        "settlements": [{"settlement_id": "s1", "amount_cents": 1200, "currency": "USD"}],
    }


@pytest.fixture
def pipeline(tmp_path):
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    if url.startswith("postgresql") and not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Refusing destructive integration setup: database name must end in _test")
    p = Pipeline(url, lease_seconds=1)
    p.initialize()
    # PostgreSQL test URL must refer to a disposable dedicated database.
    if url.startswith("postgresql"):
        with p.engine.begin() as c:
            c.execute(
                text(
                    "TRUNCATE heads, published_trades, published_settlements, attempts, batches CASCADE"
                )
            )
    return p


def test_valid_publication_is_idempotent_and_payload_is_immutable(pipeline):
    body = fixture_payload()
    batch = pipeline.stage("first", body)
    assert pipeline.stage("first", body) == batch
    assert pipeline.process(batch)["status"] == "published"
    assert pipeline.process(batch)["status"] == "published"
    assert pipeline.current(body["period"])["trades"][0]["amount_cents"] == 1200
    changed = copy.deepcopy(body)
    changed["trades"][0]["amount_cents"] = 99
    with pytest.raises(Conflict):
        pipeline.stage("first", changed)
    with pytest.raises(DBAPIError), pipeline.engine.begin() as c:
        c.execute(text("UPDATE batches SET payload = '{}' WHERE id = :id"), {"id": batch})


@pytest.mark.parametrize(
    "fault,rule",
    [
        ("duplicate", "unique"),
        ("malformed", "type"),
        ("missing", "required"),
        ("foreign", "foreign_key"),
        ("currency", "allowed_value"),
        ("total", "settlement_total"),
        ("stale", "freshness"),
        ("extra", "schema"),
        ("negative", "range"),
        ("bool", "type"),
    ],
)
def test_rejection_preserves_previous_snapshot_and_quarantines(pipeline, fault, rule):
    body = fixture_payload()
    good = pipeline.stage("good", body)
    pipeline.process(good)
    bad = copy.deepcopy(body)
    if fault == "duplicate":
        bad["trades"].append(copy.deepcopy(bad["trades"][0]))
    elif fault == "malformed":
        bad["trades"][0]["amount_cents"] = "1200"
    elif fault == "missing":
        del bad["trades"][0]["trade_id"]
    elif fault == "foreign":
        bad["trades"][0]["settlement_id"] = "unknown"
    elif fault == "currency":
        bad["trades"][0]["currency"] = "FAKE"
    elif fault == "total":
        bad["settlements"][0]["amount_cents"] += 1
    elif fault == "stale":
        bad["produced_at"] = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    elif fault == "extra":
        bad["trades"][0]["unexpected"] = 1
    elif fault == "negative":
        bad["trades"][0]["amount_cents"] = -1
    else:
        bad["trades"][0]["amount_cents"] = True
    batch = pipeline.stage(fault, bad)
    result = pipeline.process(batch)
    assert result["status"] == "rejected"
    assert rule in {e["rule"] for e in result["diagnostics"]}
    assert pipeline.current(body["period"])["batch_id"] == good
    assert pipeline.batch(batch)["payload"] == bad
    assert pipeline.quarantine()[0]["batch_id"] == batch


def test_interrupted_transaction_rolls_back_and_recovers_exact_batch(pipeline):
    body = fixture_payload()
    good = pipeline.stage("good", body)
    pipeline.process(good)
    newer = pipeline.stage("new", body)
    with pytest.raises(RuntimeError, match="injected"):
        pipeline.process(newer, fault="after_insert")
    assert pipeline.current(body["period"])["batch_id"] == good
    assert pipeline.process(newer)["status"] == "published"
    assert pipeline.current(body["period"])["batch_id"] == newer
    with pipeline.engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM published_trades WHERE batch_id=:id"), {"id": newer}
            ).scalar()
            == 1
        )


def test_backfill_preserves_other_partition(pipeline):
    body = fixture_payload()
    today = pipeline.stage("today", body)
    pipeline.process(today)
    old = copy.deepcopy(body)
    old["period"] = "2024-01-01"
    old["trades"][0]["event_time"] = "2024-01-01T12:00:00+00:00"
    historical = pipeline.stage("backfill-2024", old)
    assert pipeline.process(historical)["status"] == "published"
    assert pipeline.current(body["period"])["batch_id"] == today
    assert pipeline.current(old["period"])["batch_id"] == historical


def test_duplicate_concurrent_ingestion_has_one_identity(pipeline):
    body = fixture_payload()
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: pipeline.stage("concurrent", body), range(8)))
    assert len(set(ids)) == 1


def test_newest_version_cannot_be_replaced_by_older_retry(pipeline):
    body = fixture_payload()
    older = pipeline.stage("older", body)
    newer = pipeline.stage("newer", body)
    pipeline.process(newer)
    assert pipeline.process(older)["status"] == "superseded"
    assert pipeline.current(body["period"])["batch_id"] == newer
