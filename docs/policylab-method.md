# PolicyLab: policy compatibility before enforcement

PolicyLab evaluates a baseline and proposed quality policy against explicitly selected, retained published versions. Its question is concrete: **which previously accepted versions would the proposed policy reject?** A tighter business cap, restricted currency set, or an inappropriate uniqueness assumption can reject perfectly valid settlement data. The existing admission contract remains authoritative for ingestion. PolicyLab never installs policy, stages data, replays publication, or updates a head.

## Version 1 language

Every document is `{"version":1,"rules":[...]}`. Rule IDs use safe ASCII names and are unique inside a policy. All keys and values are typed strictly; booleans are not integer bounds. Unknown fields, tables, rule kinds and columns are rejected. No executable expression, Python, SQL fragment, regular expression or arbitrary join can be submitted.

| kind | Required parameters | Meaning |
| --- | --- | --- |
| `range` | `id`, `table`, `field:"amount_cents"`, `minimum`, `maximum` | Inclusive integer minor-unit bounds; null fails |
| `categories` | `id`, `table`, `field:"currency"`, `values` | Nonempty subset of the six admission currencies; null fails |
| `complete` | `id`, `table`, `field` | Text is non-null and nonempty after SQL TRIM of ASCII spaces |
| `unique` | `id`, `table`, `field` | Count every member of a repeated text-value group, including repeated nulls |
| `freshness` | `id`, `max_age_seconds` | Trade event age relative to successful publication time; optional `future_tolerance_seconds` defaults to 300 |
| `reference` | `id` | Trade settlement exists in the same version; `match_currency` defaults to true |
| `totals` | `id` | Settlement amount differs from its trade sum by no more than optional `tolerance_cents` (default zero) |

Text fields are `trade_id`, `settlement_id`, `currency`, `event_time` where present. Only trades have `trade_id` and `event_time`. A uniqueness rule on `trades.settlement_id` is legal but often inappropriate: multiple trades normally contribute to one settlement. This is a useful false-rejection experiment rather than a copy of admission's primary-key constraint.

Amount bounds lie in ±10^12, total tolerance in 0..10^12, freshness age in 0..604800 seconds, future tolerance in 0..86400 seconds. The language supports at most 16 rules per policy, 8 distinct selected batch IDs, 5 sample tokens per rule and 64 KiB request/file JSON. Selectors require an exact canonical period and positive 32-bit batch ID. Empty policies are permitted as explicit acceptance baselines.

Canonicalization sorts rules by ID and categories lexically, expands defaults, then hashes compact sorted-key JSON with SHA-256. Rule/category order does not affect the digest. Semantic bounds, field selection, rule IDs and the version do. Reports include the policy digests, not the supplied document or source values.

## Evidence and execution

Eligibility requires the exact period, an attempt with status `published`, and retained nonempty tables. An old retained version remains eligible after a newer head is published. Staged, rejected, failed, running, superseded-before-publication, unknown and wrong-period selections cannot supply evidence. Missing and ineligible versions receive the same generic response. A successful attempt whose rows were externally purged is not interpreted as a passing policy. A report includes the batch digest, successful attempt ID and finish time, period and batch ID; it excludes the idempotency key and staged document.

Both policies and every selected version are evaluated in one consistent read snapshot. PostgreSQL uses `REPEATABLE READ`, `READ ONLY`, a maximum 10-second statement timeout and a 20-second overall deadline. The timeout shrinks to the remaining deadline. SQLite uses an explicit read transaction, `query_only`, a VM progress deadline and the same whole-experiment deadline. Cleanup rolls back and restores pooled connection settings even after failure. Size checks count at most 10,001 rows per table and refuse versions above the existing 10,000-row admission bound; no partial report is returned on timeout or oversized source.

Range, categories, completeness, uniqueness, references and totals execute as bound SQLAlchemy queries over allowlisted metadata. Uniqueness uses window grouping; total checks aggregate trades before the settlement join. Counts are exact within the stated work bounds; samples are separately limited, ordered by record key and selected within the same snapshot. The source primary key is converted to HMAC-SHA256 using a random per-report secret and version/table domain. The secret is discarded. Tokens let operators correlate checks within a report without exposing IDs or enabling unkeyed dictionary attacks; they intentionally differ across reports and cannot locate source rows independently.

Freshness parses at most 10,000 ISO timestamps per version with the same Python semantics as admission. The storage column is text and accepted Python ISO forms differ from SQLite/PostgreSQL timestamp casts; parsing avoids backend-dependent age decisions. Age is measured against the immutable successful attempt finish time, so rerunning historical evidence tomorrow does not create new stale records. Invalid stored text fails conservatively. This fallback is bounded and source timestamps never leave the evaluator.

Each rule counts violating rows independently; overlapping counts must not be summed into a unique rejection total. A version is accepted only when all its rules have zero violations. Decision transitions are `unchanged_accept`, `new_rejection`, `new_acceptance`, and `unchanged_reject`. Per-rule deltas distinguish added/removed rules, more/fewer violations and equal counts, and separately flag changed definitions. Equal counts never imply the same violating rows or equivalent policies.

## Staged recommendation

A new rejection produces `block_candidate`: review the proposed rule against previously accepted evidence before enforcement. Rejections under both policies, newly accepted versions, any changed/added/removed rule definition, an empty candidate, or fewer than two selected versions produce `shadow_only`. Equal sampled counts cannot prove that a widened rule is safe. Only a canonically unchanged nonempty candidate with at least two accepted selected versions permits `limited_canary`, still with explicit operator review and rollback. All responses state that no policy is installed. These recommendations describe compatibility on selected evidence; a previously published version can still contain a business problem the original contract did not capture.

## Reproduce the controlled study

Set a configured operator token of at least 32 characters and supply the same value separately in `DATAGUARD_OPERATOR_TOKEN`; then run `python -m dataguard.cli policy-evaluate --output evidence/policylab-controlled.json`. Token literals are intentionally absent from CLI arguments. This command always creates and cleans a disposable SQLite database and does not use the configured database for the study.

The three synthetic accepted versions contain two trades each: `[100,200] USD`, `[100,900] USD`, and `[100,200] EUR`, each reconciled to one settlement. Literal labels are fixed before executing policies. A cap of 2000 accepts all three; a cap of 500 rejects only the second; USD-only rejects only the third; settlement-reference uniqueness rejects all three with two violations each. The runner aborts if observed decisions/counts differ from those independent labels. It also executes SQL-column-injection, boolean-bound and unknown-version policy rejection, and negative/duplicate/unbalanced batch exclusion cases. This is controlled executable evidence, not an anomaly model or fabricated model benchmark.

The native-image HTTP probe in `scripts/policylab-smoke.py` uses a separate PostgreSQL database ending `_test`. It publishes versions with 2 and 10,000 trades through HTTP. A cap of 500 accepts the small version and counts exactly 9,599 violations in the large one. It verifies authentication, typed OpenAPI, redacted errors, bounded tokens, quarantined-input exclusion and unchanged publication state. The recorded elapsed duration is a single observation, not a latency percentile or throughput claim.

## Limitations

Three hand-built versions and four policies establish these regression decisions only. They do not estimate production accuracy, false-positive rate, confidence intervals or generalization. Admission already ensures primary-key uniqueness, required fields, settlement references and reconciled totals, so many checks are expected to pass on ordinary published data. Adverse-storage integration tests deliberately bypass normal publication to validate cross-table detection and source bounds; those fixtures are not represented as naturally occurring data. Domain-specific thresholds/categories and publication-relative freshness supply the distinct compatibility experiment. Rule discovery, automatic threshold fitting and policy activation are deliberately outside this version.
