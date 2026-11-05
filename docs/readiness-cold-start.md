# Cold-start readiness and real database failures

The background-bootstrap container starts its HTTP listener before initializing persistence. Previously, `/ready` immediately returned 503 whenever `bootstrap_complete` was false, including requests racing a healthy bootstrap. Pipeline setup completes before quality-table setup, quota initialization and installation of the immutable public capture. A successful pipeline gate query alone cannot establish completion of that entire sequence.

Two regressions reproduced the problem before the change: concurrent readiness requests returned `[503, 503]` instead of waiting for delayed quality initialization; a pending readiness request returned before its wait budget. They passed after the change. This identifies the cold-start readiness race, not the cause of any historical production HTTP 500 whose logs contained no causal stack trace.

## Behavior

- One lifespan bootstrap task retains the existing retry/backoff behavior and administrative initialization. Each readiness request asynchronously joins its shared completion event for at most 15 seconds. Requests do not initiate extra bootstrap or DDL work.
- If bootstrap remains incomplete, readiness returns 503 with `Database initialization pending` and `Retry-After: 1`. A bootstrap that takes longer than the budget legitimately requires another probe.
- After bootstrap completes, every readiness request probes PostgreSQL through `Pipeline.ready`; the completion event never substitutes for current connectivity. SQL errors return only `Database unavailable`, with status 503.
- Liveness and static console routes remain responsive while initialization waits or persistence is unavailable. Authenticated routes and public quota behavior are unchanged.
- The Docker probe allows 22 seconds on the HTTP client and 25 seconds externally, accommodating the 15-second startup join and the existing five-second new PostgreSQL connection timeout. These are probe budgets, not universal SQL execution deadlines. Database-side statement/lock timeouts remain deployment responsibilities.

There is no schema-version migration marker that verifies all tables, columns, triggers, default settings and the installed source capture. Consequently this fix does not infer schema readiness from the existence of `publication_gate` or skip initialization. `create_all` remains bootstrap rather than schema migration; separating migrations and runtime identities is still an operational improvement.

## Reproduction

Run from the repository with a **stopped, disposable, locally initialized trust-authenticated PostgreSQL cluster inside `.vercel`**. The script refuses a running cluster, selects OS-assigned loopback ports, creates a random database ending in `_test`, and stops only its own API and PostgreSQL processes in cleanup. It never reads hosting credentials or sends production/model requests.

```powershell
.venv/Scripts/python.exe scripts/run_readiness_drill.py `
  --postgres-data .vercel/<your-disposable-cluster> `
  --postgres-bin 'C:/Program Files/PostgreSQL/18/bin' `
  --output evidence/readiness-cold-start-drill.json --run-tests
```

The source is the actual checked-in eight-repository GitHub capture. Controlled faults are local database stop/start and an exclusive `publication_gate` lock used to delay bootstrap. They do not alter source records and are not presented as naturally occurring data problems. The script records the actual PostgreSQL binary version, sanitized statuses, elapsed times and capture fingerprints. [Observed drill](../evidence/readiness-cold-start-drill.json) · [Executable harness](../scripts/run_readiness_drill.py) · [Regression tests](../tests/test_startup.py)

The local drill verifies startup with PostgreSQL absent, bounded 503, cold recovery, concurrent startup join while static routes remain available, a subsequent real database outage, unauthorized metrics rejection and recovery with the same source ID/digest. It does not simulate hosted network latency, establish a production uptime guarantee, or test every PostgreSQL lock/query timeout. No production fault injection or deployment was performed for this change; rollout and canonical retesting are separate.

Verification on 2026-11-05: PostgreSQL 18.2; absent-database readiness 503 after 15.094 seconds; concurrent startup requests `[200, 200]` after 0.907 seconds, including a deliberate 0.6-second pause after launching those probes before releasing the startup lock. The complete suite passed **199 tests, zero skipped**, with `TEST_DATABASE_URL` pointing only to the generated disposable local database. Ruff lint passed and all 82 Python files passed its formatting check.
