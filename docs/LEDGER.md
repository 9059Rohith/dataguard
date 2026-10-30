# Implementation ledger

Date: 2026-10-30. Scope: this independent dataguard Git repository only. Branch: codex/initial-build. External cloud and repository publication are owned by the parent task.

| Step | Evidence / decision |
|---|---|
| Plan | docs/superpowers/plans/2026-10-30-dataguard.md records scope and acceptance invariants |
| Red | Initial transactional Pipeline stub raised NotImplementedError when exercised before implementation; tests were authored first. First pytest attempt ran before dependency install completed and could not collect fastapi. |
| Green storage/API/crash | Initial full suite 17 passed; real subprocess exit 91 inside transaction, rejection matrix, backfill, idempotency, immutability and concurrent staging covered |
| Hardening red | Three explicit regression tests failed for UTC offset partition comparison, non-ASCII token header TypeError, and blank token configuration |
| Hardening green | UTC normalization, constant-time byte comparison and blank-token fail-closed behavior fixed those three; NUL identifier rejection then had an observed red/green regression; streamed oversized bodies are blocked; final full suite 22 passed without warnings |
| PostgreSQL | 15 dedicated storage tests passed against Compose PostgreSQL 16.13; Windows localhost resolution hung, so verification uses 127.0.0.1 and connect_timeout=5 |
| Real container HTTP | evidence/container-smoke.json records real API readiness, dashboard, write denial, publication/rejection, exact last-valid preservation and metrics |
| Performance/recovery | evidence/sqlite-benchmark.json and postgres-benchmark.json retain 100 raw measurements each, machine context and actual killed-worker recovery proof |
| Deployment | Compose database/service built and started; K8s client validation encountered unavailable local API server, so independent schema validation is used where available; Terraform init/validate outcomes in evidence/verification.md |
| Security | 19 runtime packages have no known pip-audit vulnerabilities; Bandit has zero medium/high; final container has zero fixable high/critical findings against explicitly dated Oct20 cached Trivy DB; fresh CI scan is required |
| Boundaries | No real upstream/financial data, no deployed AWS resources, no live Kubernetes rollout and no production availability claims |
| Terraform follow-up | Shared Windows provider verified against official HashiCorp SHA256 unblocked init/validate; 0 errors/warnings; official all-platform archive checksums and provider lock committed |
| Documentation CSP follow-up | Browser-reproduced blocked Swagger UI fixed with documentation-only source scopes and exact bootstrap hashes; 3 observed red/green regressions; full suite 25 passes; rebuilt Compose port8003 Swagger Try it out and dashboard desktop/mobile checks pass |
| Public hardening follow-up | Observed failing security regressions fixed with pre-body authentication, bounded JSON/deadline/capacity, private-by-default metadata/metrics, safe keys/Unicode and bounded IDs; final suite 55 passes, PostgreSQL 19 passes |
| Minimal public runtime | Pinned Python 3.15.1 native-wheel runtime has no installer; real SQLite seed/restart, PostgreSQL fault recovery and authenticated HTTP flows pass; same-day all-severity vulnerability/secret scan has zero findings |

Implementation sources: Airflow's public SDK DAG documentation and SQLAlchemy transaction documentation are linked in ADR.md. Dependency versions are resolved and pinned from the verified local environment. New behavioral regressions used observed red/green tests. Low-level deployment configuration is verified by relevant tools rather than unit tests that merely mirror YAML.

Public HTTP publication follow-up: independently verified https://rohith-dataguard.vercel.app with actual SQL aggregate publication/head, health/readiness, private route/recovery 401, documentation/assets 200 and exact CSP hashes. No remote browser, worker crash or CI success is claimed.
