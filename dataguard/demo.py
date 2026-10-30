"""Opt-in, named synthetic bootstrap through the real contract/publication pipeline."""

from datetime import UTC, datetime

from sqlalchemy import select

from dataguard.service import Conflict, batches

SEED_KEY = "synthetic-demo-v1"


def synthetic_payload(period, produced_at):
    return {
        "period": period,
        "produced_at": produced_at,
        "trades": [
            {
                "trade_id": "synthetic-trade-001",
                "settlement_id": "synthetic-usd",
                "currency": "USD",
                "amount_cents": 12500,
                "event_time": f"{period}T10:00:00+00:00",
            },
            {
                "trade_id": "synthetic-trade-002",
                "settlement_id": "synthetic-usd",
                "currency": "USD",
                "amount_cents": 7500,
                "event_time": f"{period}T11:00:00+00:00",
            },
            {
                "trade_id": "synthetic-trade-003",
                "settlement_id": "synthetic-eur",
                "currency": "EUR",
                "amount_cents": 9000,
                "event_time": f"{period}T12:00:00+00:00",
            },
        ],
        "settlements": [
            {"settlement_id": "synthetic-usd", "currency": "USD", "amount_cents": 20000},
            {"settlement_id": "synthetic-eur", "currency": "EUR", "amount_cents": 9000},
        ],
    }


def seed_synthetic_demo(pipeline):
    def existing_seed():
        with pipeline.engine.connect() as connection:
            return (
                connection.execute(
                    select(batches.c.id, batches.c.payload).where(batches.c.key == SEED_KEY)
                )
                .mappings()
                .first()
            )

    existing = existing_seed()
    if existing is None:
        now = datetime.now(UTC)
        try:
            pipeline.stage(SEED_KEY, synthetic_payload(now.date().isoformat(), now.isoformat()))
        except Conflict:
            # A concurrent bootstrap selected the immutable seed's exact bytes first.
            pass
        existing = existing_seed()
    payload = existing["payload"]
    if not isinstance(payload, dict) or payload != synthetic_payload(
        payload.get("period"), payload.get("produced_at")
    ):
        raise ValueError("Synthetic seed identity already contains unexpected input")
    result = pipeline.process(existing["id"])
    if result["status"] != "published":
        raise RuntimeError("Synthetic demo seed did not publish; inspect operator diagnostics")
    return result
