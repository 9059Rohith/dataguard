# Interview discussion guide

## Current interview demonstration

Distinguish the settlement publication engine from the public GitHub quality
workspace. They share reliability themes, but the public records are actual
repository metadata, not a bank's settlement feed.

Open [quality checks](https://rohith-dataguard.vercel.app/console/checks). Replay
the retained 500-repository benchmark under baseline and strict policies. Show
the recorded 96/500 and 177/500 rule failures, the actual repository witnesses,
and the source checksum. Explain why different contract policies can publish or
quarantine the same source records without modifying those records.

Checks attached to a retained capture were evaluated at their recorded time.
A past freshness pass is not evidence that the dataset is fresh today. Separate
live database readiness, immutable source provenance and policy evaluation.

For Data Engineering, explain transaction boundaries, publication head pointers,
version comparison SQL and why rejected data cannot replace the last valid
dataset. For DevOps, use the [actual Prometheus drill](prometheus-alert-drill.md)
and [cold-start recovery](readiness-cold-start.md): distinguish a healthy HTTP
listener from a ready database, and describe the alert hold/evaluation intervals.
Those are local fault experiments, not production outage or AWS failover results.

## Engineering questions

**What is the business failure you prevent?** A malformed export or duplicate delivery can replace a reconciled settlement view with partial or incorrect data. A batch is staged immutably, validated across tables, then published atomically. Invalid input is isolated while the last valid partition remains available.

**How is this different from catching an exception and retrying?** The failure may occur after some rows were inserted. The transaction rolls those rows back, while the separately committed attempt/lease records that work was in flight. Recovery retries exact staged bytes after lease expiration and verifies a fencing identity. The demo kills a real process after row insertion and checks both publication preservation and row uniqueness.

**What exactly is idempotent?** A stable key names canonical JSON. Same key and same digest returns the same batch ID; different bytes conflict. A committed terminal attempt is returned without republishing. Database PKs protect materialized row identities. This is an idempotent database publication guarantee, not an end-to-end exactly-once guarantee for upstream transport or external payments.

**Why a head pointer?** All rows carry batch_id. The per-period head switches only in the transaction that inserted validated rows and completed the attempt. Reads choose one immutable batch identity, so even if a newer head commits during a multi-statement read, the original batch's rows remain coherent.

**How do you investigate a correction without exporting financial records?** The
protected comparison endpoint accepts two successfully published batch IDs in one
date partition. SQL unions side-marked versions, groups identity keys, and uses
MIN/MAX of NONNULL fields to count edits; it returns counts and source SHA256/key plus
the successful publication attempt. Rejected/staged/failed/never-published inputs
cannot be compared. It never switches the active head. This is exact stored-value
comparison, so equivalent timestamp spellings can count as changed. It is not CDC
or semantic reconciliation. Retaining accepted rows costs storage, while database
aggregation keeps the response constant in size.

**How did measurement change the design?** Initial version self joins returned
correct counts but had 15–36 second first-read tails at 10,000 trades/version.
An actual EXPLAIN ANALYZE reproduced two nested loops with about 100 million
rejected join candidates; JIT was absent. A work-budget regression failed at
2,007,004 instrumented tuple/filter visits for 1,000 trades/version. Union/group
aggregation removed those joins. One fresh 10,000-trade before/after plan measured
40,755.019 ms versus 43.985 ms server execution. Both plans and all earlier tails
are retained; this is a targeted algorithmic improvement, not a percentile or SLO.

**Why integer amounts?** Binary floating point can introduce rounding noise into reconciliation. Integer minor units make totals exact within documented bounds. This does not solve currency conversion or precision policy; the v1 contract deliberately has no exchange-rate arithmetic.

**What if a slow worker resumes after recovery?** Publication checks the newest attempt ID while holding the same SQL gate used for claims. A stale attempt is fenced. The gate also prevents the recovery worker from racing a still-open publication transaction. A historical lower batch ID cannot replace a newer partition head.

**How do backfills work?** Historical period/events plus fresh export time pass the same contract. The head for that period changes; unrelated periods remain untouched. Corrected inputs receive a new key/version and retain rejected evidence.

**What is your biggest scaling bottleneck?** The global gate allows one claim/publication writer at a time, and recovery scans history. This makes correctness easy to inspect for modest batches but limits throughput. A measured next step is a bounded indexed queue and partition-scoped fencing, with concurrency/failure tests for absent partitions and lease transfer.

**What do your benchmark numbers prove?** Actual local stage/validation/publication latency for 100-trade batches at concurrency one, with raw samples and machine/database details. Nearest-rank p99 of 100 samples is unstable; it is reproducibility evidence, not a production SLA. Crash recovery timing includes process startup and lease wait.

**Why use Airflow if the service already retries?** Airflow provides task scheduling, delivery retries and operator visibility. Correctness stays in the storage layer because API, CLI, retries and multiple schedulers must share one guarantee. The DAG stages mounted immutable JSON and passes only the batch ID to its publish task.

**Which DevOps practices are present?** Real PostgreSQL integration tests, pinned Python dependencies, container build/security checks, separate liveness/readiness, Prometheus signals, non-root resource-limited deployment, secret references, network controls, Terraform AWS infrastructure and a manual OIDC rollout workflow with rollback detection.

**What would block production rollout?** No live AWS deployment/failover evidence, no schema migration tool, shared operator token instead of user identities, bootstrap owner credentials, deployment-specific TLS identity verification and retention policy, and no tested multi-AZ or high-concurrency capacity. These are explicit engineering work items, not hidden behind a self-healing label.
