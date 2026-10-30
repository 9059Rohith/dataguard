# Contract v1

Root keys are exactly `period`, `produced_at`, `trades`, `settlements`. Unknown columns are rejected so a renamed amount column cannot silently disappear. All timestamps must include a timezone. `period` is a canonical ISO date; event timestamps are converted to UTC before comparing their date.

| Table | Fields | Rules |
|---|---|---|
| trades | trade_id, settlement_id, currency, event_time (strings), amount_cents (integer) | unique trade_id; existing same-batch settlement; currency matches; 1..10^12 minor units; event UTC date equals period |
| settlements | settlement_id, currency (strings), amount_cents (integer) | unique settlement_id; 0..10^12 minor units; amount equals sum of all referenced trades |

Allowed currency codes are USD, EUR, GBP, INR, SGD, JPY. This whitelist is a contract decision, not a complete ISO registry. Strings are 1..100 characters; blank/control-character strings (including NUL, which PostgreSQL text cannot store) are rejected. Trade/settlement tables each contain 1..10,000 rows. A zero settlement with no trades is accepted when other trades exist in the batch; negative amounts, refunds, netting and exchange-rate arithmetic are outside v1.

`produced_at` must be within the last 24 hours and no more than 5 minutes ahead of worker UTC time. An old partition can be backfilled with a freshly produced export. A batch staged more than 24 hours before eventual execution will fail freshness and remain quarantined; obtain and stage a new export with a new key. Host clocks must be synchronized.

Diagnostics include table, zero-based row index, field, rule and explanatory message; totals include expected/observed amounts. At most 1,000 diagnostics are retained per validation. Original inputs are stored intact in protected staging for investigation. One invalid row rejects the entire partition, preserving cross-table consistency.

Idempotency hashes canonical JSON with sorted object keys; array order remains significant. A key replay with different payload is a conflict even if the new payload is logically equivalent. Batch IDs represent ingestion order, not business revision numbers: a later staged valid export takes precedence in its partition. An older still-pending retry is marked superseded after a newer valid batch is published.

New idempotency keys are 1–128 ASCII characters, begin with a letter/digit, and contain only letters, digits, underscore, dot, colon or hyphen. Invalid Unicode, excessive nesting/structure and over-budget HTTP requests are rejected before staging; ordinary bounded contract failures still retain their immutable source and quarantine diagnostics. The HTTP public boundary is documented in PUBLIC_DEMO.md.

## Accepted-version comparison

`GET /snapshots/{period}/compare?from_batch=1&to_batch=2` requires the operator bearer
token, including in public-demo mode. The trusted database CLI is
`python -m dataguard.cli compare YYYY-MM-DD --from-batch 1 --to-batch 2`.
The period must be a canonical ISO date and both IDs integers in 1..2147483647.
Both IDs must have a committed `published` attempt and belong to that exact
period. A formerly active accepted version remains valid after a newer head is
published. A never-published `superseded` input is not an accepted version.

The response has `period`, `from`, `to` and `tables`. Each provenance object has
`batch_id`, `key`, `sha256`, `attempt_id` and `published_at` (Unix seconds from the
successful attempt, not the current head timestamp). Each of `tables.trades` and
`tables.settlements` contains `before`, `after`, `added`, `removed`, `changed` and
`unchanged` integer counts. The public response never contains record IDs, values,
source payloads or diagnostics. Provenance is privileged metadata.

Identity is trade_id / settlement_id. Added means only in the destination;
removed means only in the source. A shared identity is changed if any stored
non-key field differs, excluding batch_id. Thus changed counts records, not
fields. Timestamp comparison uses exact stored text, not instant normalization;
array order and export-level produced_at do not change record counts. Invariants:
`before = removed + changed + unchanged` and
`after = added + changed + unchanged`. Reversing the direction exchanges added
and removed; self-comparison is valid and has zero changes.

SQL unions both retained materialized versions with old/new side markers (at
most 10,000 rows per admitted table/version), groups by record ID, uses MAX for
side presence and MIN/MAX of each NONNULL stored field to detect edits, then
aggregates counts. No record self join or repeated per-key scan is required;
UNION ALL preserves both sides even for self-comparison. Only provenance and aggregate counts reach Python;
response size does not grow with record count. No extra schema, third-party
dependency, mutation, publication lock, export freshness recheck or raw staging
read is required. Unknown, wrong-period and unpublished IDs share 404; malformed
identifiers receive 422. CLI returns nonzero for invalid selection. There is no
tenant identity model: ownership here means the requested date partition under
the shared operator authorization.
