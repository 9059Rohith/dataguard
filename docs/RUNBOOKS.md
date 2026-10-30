# Operator runbooks

Use a trusted shell with `DATABASE_URL` and, for HTTP, `DATAGUARD_TOKEN`. Avoid pasting source payloads into shared incidents. `/health` checks the process; `/ready` checks DB/schema. Restarting a healthy process cannot repair invalid source data.

## Quarantined export

Trigger: `rejected` increases or Airflow's publish task fails with a quarantined batch ID.

1. Read `GET /batches/{id}` using the bearer token. Record its SHA256, key, diagnostics table/row/field/rule, and previously active partition ID.
2. Match the original immutable export to the upstream producer. Duplicate IDs require deduplication at the producer; total mismatch needs source reconciliation. Do not guess a corrected amount.
3. Export corrected source under a new idempotency key, retaining the historical period and a fresh produced_at timestamp. Stage/run the new export.
4. Confirm published status, `GET /snapshots/{period}` row counts and totals, and successful downstream read. The rejected source remains for audit; do not update it in place.

## Interrupted worker / expired lease

Trigger: a running attempt persists after worker loss, or a worker raises a transient failure.

1. Check database readiness and the worker's process/orchestration state. An active lease yields HTTP 409, protecting a live owner.
2. Wait until the recorded `lease_until` timestamp (default API lease: 30 seconds). Execute `python -m dataguard.cli recover` or authorized `POST /recover`. Airflow retries the same batch ID and key.
3. Confirm history contains `abandoned` then `published` and no duplicate materialized trade keys. If a newer version already exists, `superseded` is expected and safe.
4. If retry produces `rejected` due to expired export freshness, obtain a fresh upstream artifact/new key. If DB failure repeats, follow outage runbook; do not loop rapid retries or delete attempts manually.

The CLI demo shortens leases to one second and deliberately exits after insert to prove this procedure. Its recovery timing includes child startup and lease waiting. It does not model node loss, network partitions or RDS failover.

## Database outage

1. Distinguish API liveness from readiness. Inspect DB network policy/security group, DNS, credentials, TLS and disk capacity. `/metrics` exposes `dataguard_database_up=0` when its probe fails.
2. Restore connectivity or recover the PostgreSQL instance from the approved backup/point-in-time procedure. Never bootstrap an empty database over the only copy of production data.
3. Check schema and head identities before accepting writes. Execute recovery only after DB readiness. Committed staged batches on intact DB storage are recoverable; source data not yet committed must be replayed from upstream.
4. Compare downstream partition IDs and checksums; backfill missing periods using fresh exports. Record the actual recovery time and any data loss. No RTO/RPO guarantee is inferred from local benchmarks.

## Historical backfill

Generate or retrieve a fresh export whose `period` is the historical day and all event timestamps fall on that UTC day. Stage it under a stable artifact revision key and run. Check that day changed and adjacent days retained their head IDs. Use `dataguard fixture --period 2024-01-01 --output historical.json` only for synthetic demonstrations. A backfill has the same full contract checks as current data.

## Credential rotation

Rotate the HTTP token in its secret store, roll API tasks, then update operator clients. In-flight processes still hold their original environment; old token remains valid until those replicas terminate. For PostgreSQL credentials, rotate DB user/password with an overlap window and restart connection pools. Compose existing volume passwords do not rotate merely by changing environment. Inspect no raw secrets into evidence.

## Rollback

Application rollback uses a previous image digest and stable schema. No schema downgrade mechanism exists in v1. Data rollback is a deliberate new batch containing the approved older source (fresh export metadata and new key), which is revalidated and produces a new audit/version identity. Direct head manipulation bypasses policy and is not supported through the operator API.

## Alert caveats

`dataguard_process_total` and latency histogram count API run calls, including idempotent repeats. CLI/Airflow work does not increment those in-process counters. Persisted `dataguard_attempts{status}` counts every attempt and remains meaningful across API restarts. The example reject alert therefore covers API-triggered processing; schedule a SQL-backed quarantine check or alert on persisted count changes for CLI/Airflow deployments. Metrics are operational signals, not billing totals.
