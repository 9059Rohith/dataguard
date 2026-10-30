# Architecture decisions

## ADR 001 — immutable input, mutable publication pointer

Accepted. Store canonical JSON and SHA256 in an append-only batches table. Separate attempts hold operational state. Materialized trades/settlements and the date-partition head are committed in one database transaction. SQL PKs, FKs and amount checks add structural constraints behind the executable contract. Batch-trigger immutability prevents ordinary UPDATE/DELETE, while audit preserves failed attempts.

Why: mutating a live table before validation risks partial/bad publication. A head swap gives readers a stable batch identity and allows history/backfill without destructive replacement. The costs are history growth and storage duplication. Retention/archive needs a privileged, audited operator workflow; the API intentionally has no delete route.

## ADR 002 — database gate and fencing, not a distributed lock service

Accepted for the project's batch scale. A single gate row serializes claim/publication transactions across all processes; PostgreSQL row locking and SQLite's write serialization provide the mechanism. Each claim creates a durable running attempt and lease. Before publishing, the worker verifies it is still the latest attempt. Expired attempts are abandoned and recovery creates a new attempt. Long operations hold the SQL gate, so a recovery worker waits rather than publishing concurrently. A lower batch ID cannot replace a newer published partition.

Why: Redis leases alone can expire while a worker still writes. The gate and attempt fence share the actual database with the publication. Costs: one global writer lane, clock assumptions for deciding abandoned attempts, and queue scans. A future scaling step is partition-scoped gate rows with a carefully tested absent-partition bootstrap and bounded indexed queue, not simply adding more worker replicas.

## ADR 003 — strict integer money contract with explicit freshness

Accepted. Store integer minor units; no float rounding or automatic correction. Validate schema, types, keys, references, currencies, amounts and cross-table totals before opening a visible publication. `produced_at` freshness applies to a fresh export; event date applies to its UTC historical partition. Rejected input is terminal and requires a new source artifact/key after correction.

Why: historical backfills should be possible without pretending old events are recent. A fresh export of an old date is different from an old export waiting indefinitely. Costs: clock synchronization and explicit export regeneration after long outages. Currency precision and business refund/netting policy require contract v2.

## ADR 004 — orchestration delegates correctness to the database service

Accepted. Airflow's stage task returns a batch ID, not source rows; publish task calls the same Pipeline used by CLI/API. Airflow retries preserve idempotency keys and exact staged bytes. Scheduler retries are a delivery mechanism; the database still guards publication. Airflow SDK 3 is explicitly targeted; 2.x is not claimed as supported.

## ADR 005 — portable local store, PostgreSQL deployment target

Accepted. SQLite allows a reviewer to run the system with one command and no daemon. PostgreSQL is exercised by an independent integration suite and real-process crash demonstration. SQLAlchemy Core keeps transaction boundaries explicit. SQLite is not used as evidence for distributed production locking. `create_all` bootstraps schema v1 but cannot migrate an existing changed schema; introduce Alembic with upgrade/rollback tests before schema evolution.

## Primary implementation references

The transaction design uses SQLAlchemy's explicit begin/commit/rollback context managers: [SQLAlchemy connections and transactions](https://docs.sqlalchemy.org/en/20/core/connections.html). Airflow imports follow the documented public SDK: [Airflow DAG declaration](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html). Local integration targets PostgreSQL 16; cloud architecture is an authored deployment design, not a claim of an existing AWS installation.
