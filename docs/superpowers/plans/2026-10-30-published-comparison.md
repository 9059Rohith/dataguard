# Published-version comparison

1. Prove directional added/removed/changed/unchanged counts with real published batches;
   test identity, period ownership, never-published states, authentication and immutability.
2. Implement bounded SQL aggregates over retained publication tables, published-attempt
   provenance and strict period/ID validation. Add authenticated GET and trusted CLI.
3. Document the contract, reviewer walkthrough, deployment scope and measured boundaries.
4. Run the full suite, PostgreSQL integration, lint/format and native Python 3.15 image
   checks without modifying running services. Record evidence, inspect diff and commit.

Follow-up: preserve baseline 14eae11 and its first-read tails; diagnose one actual
fresh 10,000-trade EXPLAIN plan. Observed nested-loop repeated scans led to a red
actual-plan work-budget regression, then side-marked UNION ALL/per-ID grouping.
Run the full SQLite/PostgreSQL suites and one same-method native after plan plus
same-pair HTTP checks. Preserve both plans and report method/limits explicitly.
