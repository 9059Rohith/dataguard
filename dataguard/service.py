"""Immutable staged batches, fenced workers and atomic partition publication."""

import hashlib
import json
import os
import time
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    create_engine,
    event,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from dataguard.contracts import validate
from dataguard.limits import SAFE_KEY, check_json_value

metadata = MetaData()
batches = Table(
    "batches",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("key", String(128), nullable=False, unique=True),
    Column("digest", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", Float, nullable=False),
)
attempts = Table(
    "attempts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("batch_id", ForeignKey("batches.id"), nullable=False, index=True),
    Column("status", String(20), nullable=False),
    Column("started_at", Float, nullable=False),
    Column("lease_until", Float, nullable=False),
    Column("finished_at", Float),
    Column("diagnostics", JSON, nullable=False),
)
heads = Table(
    "heads",
    metadata,
    Column("period", String(10), primary_key=True),
    Column("batch_id", ForeignKey("batches.id"), nullable=False),
    Column("published_at", Float, nullable=False),
)
settlements = Table(
    "published_settlements",
    metadata,
    Column("batch_id", ForeignKey("batches.id"), primary_key=True),
    Column("settlement_id", String(100), primary_key=True),
    Column("currency", String(3), nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    CheckConstraint("amount_cents >= 0"),
)
trades = Table(
    "published_trades",
    metadata,
    Column("batch_id", ForeignKey("batches.id"), primary_key=True),
    Column("trade_id", String(100), primary_key=True),
    Column("settlement_id", String(100), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("event_time", String(100), nullable=False),
    ForeignKeyConstraint(
        ["batch_id", "settlement_id"],
        ["published_settlements.batch_id", "published_settlements.settlement_id"],
    ),
    CheckConstraint("amount_cents > 0"),
)
gate = Table(
    "publication_gate",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("revision", BigInteger, nullable=False),
)


class Conflict(Exception):
    """An idempotency key already names different bytes."""


class Busy(Exception):
    """An unexpired worker lease owns this batch."""


class Pipeline:
    def __init__(self, url, lease_seconds=30):
        self.lease_seconds = lease_seconds
        if isinstance(url, str) and url.startswith(("postgresql://", "postgres://")):
            url = "postgresql+psycopg://" + url.split("://", 1)[1]
        connect_args = (
            {"connect_timeout": 5} if make_url(url).get_backend_name() == "postgresql" else {}
        )
        self.engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def configure(dbapi, _):
                dbapi.execute("PRAGMA foreign_keys=ON")
                dbapi.execute("PRAGMA busy_timeout=15000")

    def initialize(self):
        """Administrative bootstrap: run before service replicas start."""
        metadata.create_all(self.engine)
        with self.engine.begin() as c:
            if self.engine.dialect.name == "postgresql":
                c.execute(text("INSERT INTO publication_gate VALUES (1, 0) ON CONFLICT DO NOTHING"))
                c.execute(
                    text("""CREATE OR REPLACE FUNCTION immutable_batch() RETURNS trigger AS $$
                    BEGIN RAISE EXCEPTION 'staging batches are immutable'; END;
                    $$ LANGUAGE plpgsql""")
                )
                c.execute(text("DROP TRIGGER IF EXISTS immutable_batch ON batches"))
                c.execute(
                    text("""CREATE TRIGGER immutable_batch BEFORE UPDATE OR DELETE ON batches
                                FOR EACH ROW EXECUTE FUNCTION immutable_batch()""")
                )
            else:
                c.execute(text("INSERT OR IGNORE INTO publication_gate VALUES (1, 0)"))
                for op in ("UPDATE", "DELETE"):
                    c.execute(
                        text(f"""CREATE TRIGGER IF NOT EXISTS immutable_batch_{op.lower()}
                        BEFORE {op} ON batches BEGIN
                        SELECT RAISE(ABORT, 'staging batches are immutable'); END""")
                    )

    @staticmethod
    def _lock(c):
        c.execute(update(gate).where(gate.c.id == 1).values(revision=gate.c.revision + 1))

    def ready(self):
        with self.engine.connect() as c:
            return c.execute(select(gate.c.id)).scalar() == 1

    def stage(self, key, payload):
        if not isinstance(key, str) or not SAFE_KEY.fullmatch(key):
            raise ValueError("key must be 1..128 safe ASCII identifier characters")
        check_json_value(payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode()) > 8_000_000:
            raise ValueError("batch exceeds 8 MB")
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        try:
            with self.engine.begin() as c:
                result = c.execute(
                    insert(batches).values(
                        key=key, digest=digest, payload=payload, created_at=time.time()
                    )
                )
                return result.inserted_primary_key[0]
        except IntegrityError:
            with self.engine.connect() as c:
                existing = c.execute(select(batches).where(batches.c.key == key)).mappings().one()
            if existing["digest"] != digest:
                raise Conflict("idempotency key already has a different payload") from None
            return existing["id"]

    def batch(self, batch_id):
        with self.engine.connect() as c:
            row = c.execute(select(batches).where(batches.c.id == batch_id)).mappings().first()
            if row is None:
                raise KeyError(batch_id)
            result = dict(row)
            result["attempts"] = [
                dict(r)
                for r in c.execute(
                    select(attempts).where(attempts.c.batch_id == batch_id).order_by(attempts.c.id)
                ).mappings()
            ]
            return result

    def process(self, batch_id, fault=None):
        """Retry staged bytes. Fault injection is CLI-only, never wired to HTTP."""
        with self.engine.begin() as c:
            self._lock(c)
            batch = c.execute(select(batches).where(batches.c.id == batch_id)).mappings().first()
            if batch is None:
                raise KeyError(batch_id)
            recent = (
                c.execute(
                    select(attempts)
                    .where(attempts.c.batch_id == batch_id)
                    .order_by(attempts.c.id.desc())
                )
                .mappings()
                .first()
            )
            if recent and recent["status"] in {"published", "superseded", "rejected"}:
                return {
                    "batch_id": batch_id,
                    "status": recent["status"],
                    "diagnostics": recent["diagnostics"],
                }
            now = time.time()
            if recent and recent["status"] == "running":
                if recent["lease_until"] > now:
                    raise Busy("worker lease has not expired")
                c.execute(
                    update(attempts)
                    .where(attempts.c.id == recent["id"])
                    .values(status="abandoned", finished_at=now)
                )
            attempt_id = c.execute(
                insert(attempts).values(
                    batch_id=batch_id,
                    status="running",
                    started_at=now,
                    lease_until=now + self.lease_seconds,
                    diagnostics=[],
                )
            ).inserted_primary_key[0]
        try:
            with self.engine.begin() as c:
                self._lock(c)
                latest = c.execute(
                    select(attempts.c.id)
                    .where(attempts.c.batch_id == batch_id)
                    .order_by(attempts.c.id.desc())
                ).scalar()
                if latest != attempt_id:
                    raise Busy("attempt fenced by a newer recovery")
                errors = validate(batch["payload"], datetime.now(UTC))
                status = "rejected"
                if not errors:
                    payload = batch["payload"]
                    head = (
                        c.execute(select(heads).where(heads.c.period == payload["period"]))
                        .mappings()
                        .first()
                    )
                    if head and head["batch_id"] > batch_id:
                        status = "superseded"
                    else:
                        c.execute(
                            insert(settlements),
                            [dict(r, batch_id=batch_id) for r in payload["settlements"]],
                        )
                        c.execute(
                            insert(trades), [dict(r, batch_id=batch_id) for r in payload["trades"]]
                        )
                        if fault == "after_insert":
                            raise RuntimeError("injected interruption after row inserts")
                        if fault == "kill_after_insert":
                            os._exit(91)  # Deliberate process crash in explicit CLI chaos mode.
                        values = {"batch_id": batch_id, "published_at": time.time()}
                        if head:
                            c.execute(
                                update(heads)
                                .where(heads.c.period == payload["period"])
                                .values(**values)
                            )
                        else:
                            c.execute(insert(heads).values(period=payload["period"], **values))
                        status = "published"
                c.execute(
                    update(attempts)
                    .where(attempts.c.id == attempt_id)
                    .values(status=status, finished_at=time.time(), diagnostics=errors)
                )
                return {"batch_id": batch_id, "status": status, "diagnostics": errors}
        except Exception:
            with self.engine.begin() as c:
                c.execute(
                    update(attempts)
                    .where(attempts.c.id == attempt_id, attempts.c.status == "running")
                    .values(
                        status="failed",
                        finished_at=time.time(),
                        diagnostics=[
                            {
                                "rule": "worker_failure",
                                "message": "Worker failed; staged input can be retried",
                            }
                        ],
                    )
                )
            raise

    def recover(self):
        with self.engine.connect() as c:
            ids = c.execute(select(batches.c.id).order_by(batches.c.id)).scalars().all()
        results = []
        for batch_id in ids:
            batch = self.batch(batch_id)
            recent = batch["attempts"][-1] if batch["attempts"] else None
            if recent and (
                recent["status"] in {"published", "rejected", "superseded"}
                or recent["status"] == "running"
                and recent["lease_until"] > time.time()
            ):
                continue
            try:
                results.append(self.process(batch_id))
            except Busy:
                continue
        return results

    def snapshots(self):
        with self.engine.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    select(heads).order_by(heads.c.period.desc()).limit(100)
                ).mappings()
            ]

    def current(self, period):
        with self.engine.connect() as c:
            head = c.execute(select(heads).where(heads.c.period == period)).mappings().first()
            if not head:
                raise KeyError(period)
            result = dict(head)
            for label, table in (("trades", trades), ("settlements", settlements)):
                result[label] = [
                    dict(r)
                    for r in c.execute(
                        select(table).where(table.c.batch_id == head["batch_id"])
                    ).mappings()
                ]
            return result

    def compare(self, period, from_batch, to_batch):
        """Directional, constant-size comparison of two retained accepted versions.

        This does not inspect staged records, change heads, or replay validation.
        Published rows and their successful attempt commit in the same transaction.
        """
        try:
            if date.fromisoformat(period).isoformat() != period:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("period must be a canonical YYYY-MM-DD date") from None
        if any(
            type(value) is not int or not 1 <= value <= 2_147_483_647
            for value in (from_batch, to_batch)
        ):
            raise ValueError("batch IDs must be integers in 1..2147483647")
        with self.engine.connect() as c:
            accepted = {
                row["batch_id"]: dict(row)
                for row in c.execute(
                    select(
                        batches.c.id.label("batch_id"),
                        batches.c.key,
                        batches.c.digest.label("sha256"),
                        attempts.c.id.label("attempt_id"),
                        attempts.c.finished_at.label("published_at"),
                    )
                    .select_from(batches.join(attempts, batches.c.id == attempts.c.batch_id))
                    .where(
                        batches.c.id.in_([from_batch, to_batch]),
                        batches.c.payload["period"].as_string() == period,
                        attempts.c.status == "published",
                    )
                ).mappings()
            }
            if from_batch not in accepted or to_batch not in accepted:
                # Unknown, wrong partition and never-published inputs share one result.
                raise KeyError("published version")
            result = {
                "period": period,
                "from": accepted[from_batch],
                "to": accepted[to_batch],
                "tables": {},
            }
            for label, table, key in (
                ("trades", trades, "trade_id"),
                ("settlements", settlements, "settlement_id"),
            ):
                old = select(table).where(table.c.batch_id == from_batch).subquery("old")
                new = select(table).where(table.c.batch_id == to_batch).subquery("new")
                joined = old.join(new, old.c[key] == new.c[key])
                shared = select(func.count()).select_from(joined)
                unchanged = shared.where(
                    and_(
                        *(
                            old.c[col.name] == new.c[col.name]
                            for col in table.c
                            if col.name not in {"batch_id", key}
                        )
                    )
                )
                before, after, common, equal = c.execute(
                    select(
                        select(func.count()).select_from(old).scalar_subquery(),
                        select(func.count()).select_from(new).scalar_subquery(),
                        shared.scalar_subquery(),
                        unchanged.scalar_subquery(),
                    )
                ).one()
                result["tables"][label] = {
                    "before": before,
                    "after": after,
                    "added": after - common,
                    "removed": before - common,
                    "changed": common - equal,
                    "unchanged": equal,
                }
            return result

    def quarantine(self, limit=100):
        with self.engine.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    select(attempts)
                    .where(attempts.c.status == "rejected")
                    .order_by(attempts.c.id.desc())
                    .limit(limit)
                ).mappings()
            ]

    def summary(self):
        with self.engine.connect() as c:
            statuses = c.execute(
                text("SELECT status, count(*) AS n FROM attempts GROUP BY status")
            ).mappings()
            return {r["status"]: r["n"] for r in statuses}
