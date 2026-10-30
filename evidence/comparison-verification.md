# Accepted-version comparison verification

Executed locally on 2026-10-30. No hosted CI, public deployment of this revision,
AWS apply or Kubernetes rollout is implied. Existing public HTTP evidence refers
to its recorded release. No dependency, database schema, image-base or workflow
change was needed.

## Observed red / green

Before implementation, all 15 comparison cases failed because `Pipeline.compare`
and its protected route were absent. The subprocess CLI test then failed because
`compare` was unregistered. A separate OpenAPI assertion failed with an empty
success schema before the typed `VersionComparison` response model was added.
The initial SQLite and PostgreSQL runs both passed 71 tests. After the plan-work
regression and aggregation rewrite, the final SQLite run passes 71 with one
intentional PostgreSQL-only skip; the PostgreSQL run passes all 72 tests.

Coverage includes hand-derived added/removed/changed/unchanged counts, reverse
direction, self-comparison, retained prior versions, source key/SHA256 and exact
successful-attempt provenance, canonical period/integer ID validation, no state
mutation, auth fail-closed in public-demo mode, typed API docs and trusted CLI.
Staged, running, failed, rejected, never-published superseded, missing and foreign
partition versions are all denied in both comparison directions.

The full suite uses a dedicated `dataguard_comparison_test` PostgreSQL database;
the existing live/local demo database was not truncated. Credentials were read
only from this project's existing local database container into subprocess
environment memory; no secrets were persisted. The final PostgreSQL output is
in [comparison-postgres-tests.txt](comparison-postgres-tests.txt) for the original
implementation and [comparison-postgres-tests-after.txt](comparison-postgres-tests-after.txt)
for the grouping rewrite.

## Native minimal image

Built `dataguard:comparison-review` from the unchanged digest-pinned Dockerfile.
[comparison-native-pg.json](comparison-native-pg.json) records Python 3.15.1,
WSL2 Linux, PostgreSQL and the image ID. A temporary read-only container with no
capabilities, no privilege escalation and a bounded tmpfs used its own disposable
database on the existing local Compose network. Existing services were not
stopped or replaced.

`scripts/comparison-smoke.py` publishes two synthetic versions, compares them 50
times at 100 and 10,000 trades/version (one settlement/version), rejects an
inconsistent third input, confirms head preservation and quarantine exclusion,
then starts the actual Uvicorn server and issues real HTTP requests. It verifies
anonymous 401, authenticated 200, rejected/wrong-period 404 and absence of raw
record values. Raw timings and response sizes are retained. This measures
sequential SQL comparison from one container, not HTTP latency, concurrency,
capacity, all-10,000-settlement performance or an SLA.

The follow-up run after the DataGuard suite finished records comparison p50/p95/
p99 of 14.071/20.368/22.584 ms at 100 trades/version and
48.661/63.904/15169.065 ms at 10,000 trades/version. No first-sample exclusion was
applied: the first 10,000-row read accounts for the 15.17-second tail. The
[concurrent-suite run](comparison-native-pg-contended.json) retains every sample,
including a 36.05-second first-read outlier. Since the follow-up also has an
outlier, no causal attribution to concurrent tests was justified. These are
preserved measurements of the original self-join implementation; the diagnosis
and rewrite below supersede its query shape. The [CPU/container observation](comparison-host-observation.json)
is a timestamped snapshot; it does not measure conditions throughout either run.

## Diagnosed repeated scans and grouping rewrite

At baseline commit `14eae114e4f63ed489dec3ac0c3396175bbd8df6`,
`scripts/comparison-plan.py` published one fresh pair of 10,000-trade versions,
intercepted the actual first trade-comparison statement before execution, then
executed it once with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` and a 60-second
diagnostic timeout. The [full before plan](comparison-plan-before.json) records
40,755.019 ms server execution. Two nested loops used batch-only index scans
10,000 times, rejecting 49,995,000 and 50,005,000 join candidates. JIT was absent;
this is direct evidence of repeated scans, not an inference from host CPU.

A meaningful red regression runs the real comparison statement through EXPLAIN
ANALYZE with hash/merge joins disabled, modeling an unfavorable valid join plan
independently of statistics. At 1,000 trades/version the original implementation
required 2,007,004 instrumented tuple/filter visits, exceeding a generous
32,000-work budget (16 visits per admitted record across all plan nodes). The
grouped implementation passes this test. It asserts actual work, not wall-clock
speed or source/SQL spelling, and skips on SQLite where these PG plans do not exist.

Record comparison now UNION ALLs both versions with explicit old/new markers,
groups by identity, computes MAX side presence and MIN/MAX nonnull field changes,
then aggregates directional counts. There are no record joins; self-comparison
preserves both sides because this is UNION ALL. Successful publication/period
provenance checks and API/CLI output semantics are unchanged.

One fresh-pair after experiment used the rebuilt unchanged-base
`dataguard:comparison-grouped` Python 3.15.1 image and the same first-statement
EXPLAIN method, with 10,000 trades + one settlement per version. The
[full after plan](comparison-plan-after.json) records **43.985 ms server execution**
(49.355 ms measured wall time). Plan work, defined as the sum of reported
rows/filter candidates × loops across all nodes, drops from **200,070,004 to
90,001**. This is not a distinct-row/physical-read count. The new plan has two
index scans, Append, Sort, per-ID aggregation and final aggregation; no record
join or JIT. No repeated runs, warm-up exclusions or percentile claim were used.

Before/after timings exclude provenance lookup, settlement comparison, HTTP and
publication, and EXPLAIN adds instrumentation overhead. Separate fresh pairs,
same local PG database/image base/row counts/method; unrelated host workloads
were uncontrolled. This demonstrates removal of the diagnosed scan explosion,
not a production latency guarantee. All original raw benchmark tails remain
unchanged. After instrumentation, native same-pair correctness and real Uvicorn
HTTP checks verify exact counts, quarantine/wrong-period 404, anonymous 401,
authenticated 200, head preservation, raw-value absence and typed OpenAPI.

The **entire suite also passes all 72 tests inside the actual Python 3.15.1
grouped minimal image**, including PostgreSQL work-budget, real killed-worker
subprocess recovery and all API boundaries: [native full output](comparison-native-full-tests.txt),
[runtime/context](comparison-native-full-context.json). Tests and the existing
pure-Python dev test libraries were mounted read-only; the dev library directory
was appended after native runtime site-packages. Native application, SQLAlchemy,
Pydantic and psycopg packages retained image precedence. No installer/runtime
dependency was added. Plugin auto-load was disabled, test startup auto-init was
enabled, and a separate `dataguard_native_suite_test` database was used. This
does not turn the public image into a dev image or modify running services.

With a disposable database set in `DATABASE_URL`, rerun inside the installed
runtime with `python scripts/comparison-smoke.py`. It writes synthetic accepted
history and starts a temporary loopback HTTP process. It never prints the token
or database connection string. `DATAGUARD_PUBLIC_DEMO=true` is set only for that
temporary HTTP child's auth-boundary check.

[comparison-native-recovery.json](comparison-native-recovery.json) separately
reruns the existing real-process crash demonstration in Python 3.15.1/PostgreSQL:
exit 91 after inserts, last accepted head preserved, exact staged batch recovered,
no duplicate rows. Its ten stage/publish timing samples are a recovery acceptance
probe; the README's larger publication benchmark remains the previous 100-sample
recorded run.

## Documentation and security checks

The README's literal correction/failure PowerShell blocks were executed against
a dedicated SQLite database. They produce one changed/two unchanged trades,
one changed settlement and a rejected inconsistent export; accepted comparison
output is in [comparison-readme.json](comparison-readme.json). This caught and
fixed PowerShell's timestamp reserialization before publication: file edits now
use Python JSON so only the intended amount changes.

Ruff lint and format checks pass. Bandit reports zero medium/high findings in
the application and new native probe; its explicit exemptions cover the fixed
loopback probe URL and deliberate public container bind. A pre-existing B104
annotation was moved to the actual bind argument line, with no runtime behavior
change. The current locked-runtime pip-audit finds no known vulnerabilities.
Relative Markdown targets in the modified documentation were checked for
existence. An independent review by the coordinating agent found no blocking
comparison correctness, authorization or ownership issue.
