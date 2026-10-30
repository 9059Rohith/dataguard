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
The final SQLite and PostgreSQL runs both pass 71 tests.

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
in [comparison-postgres-tests.txt](comparison-postgres-tests.txt).

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
outlier, no causal attribution to concurrent tests is justified. Query-plan and
cold-read behavior remain unresolved performance limits, despite correct counts
and fixed-size output. The [CPU/container observation](comparison-host-observation.json)
is a timestamped snapshot; it does not measure conditions throughout either run.

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
