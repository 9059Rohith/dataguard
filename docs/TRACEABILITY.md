# Requirements traceability

| Requirement | Implementation | Verification |
|---|---|---|
| Required/types/uniqueness/FK/allowed values/ranges | dataguard/contracts.py | test_pipeline parameterized rejection matrix |
| Fresh export and UTC partition event time | contracts.py | stale rejection + test_event_partition_uses_utc_date |
| Settlement totals across tables | contracts.py integer aggregation | total mismatch rejection and exact valid publication |
| Immutable staging | batches + digest + DB UPDATE/DELETE triggers | direct SQL mutation blocked; key conflict tests |
| Atomic publication, last valid preserved | service.py gate + transaction + heads | rollback test, rejection matrix, real killed worker demo |
| Idempotent replay and concurrency | unique key/hash + terminal attempts | repeated publication and concurrent staging tests |
| Recovery/backfill | leases, fencing, recover(), partition heads | killed worker CLI test, backfill and monotonic version tests |
| Useful quarantine | row/table/field/rule/message + source history | rejection matrix + HTTP smoke script |
| Read API/dashboard | api.py + dashboard.html/js | TestClient and container HTTP smoke |
| Auth fail-closed | authorize() minimum token + byte compare | missing/invalid token, blank config, malformed non-ASCII tests |
| Health/readiness/metrics | dedicated endpoints + Prometheus registry | API tests and container HTTP smoke |
| Airflow integration | SDK 3 DAG, actual mounted artifact stage/publish | CI import job defined; local official image download pending at checkpoint |
| PostgreSQL deployment | Compose Postgres 16 + SQLAlchemy psycopg | dedicated PostgreSQL suite and 100-sample benchmark |
| Container hardening | Dockerfile + Compose restrictions | build/start/health + image scan evidence |
| Kubernetes controls | deploy/kubernetes.yaml | manifest/schema checks; no live cluster rollout claimed |
| AWS infrastructure | infra/main.tf + provider lock | terraform fmt/init/validate passed against AWS v6.71.0; no apply claimed |
| CI/security/release | .github/workflows | local equivalent checks; remote run status after publication |
| Interview readiness | architecture, ADR, runbooks, Q&A | documented rationale and bounded claims |
