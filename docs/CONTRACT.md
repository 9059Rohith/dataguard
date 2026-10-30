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
