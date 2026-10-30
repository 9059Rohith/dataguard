# Executed verification — 2026-10-30

Environment: Windows 11, host Python 3.12.14, pinned minimal Linux runtime Python 3.15.1, Docker Engine 28.5.1, PostgreSQL 16.13. Isolated `.venv` and independent Git repository. Synthetic data only. Commands were executed locally; this document does not claim remote CI or cloud deployment success.

| Check | Result | Retained evidence |
|---|---|---|
| Full `python -m pytest -q` | **55 passed**, 17.24 seconds, no warnings | unit-tests.txt |
| PostgreSQL `pytest -q tests/test_pipeline.py` | **19 passed** against real PostgreSQL in dedicated dataguard_test database, including unsafe-key rejection before storage | postgres-tests.txt |
| Ruff check + format check | Passed | tool execution output |
| Python compileall for service/DAG/scripts | Passed | tool execution output |
| Runtime pip-audit (exact complete pinned closure, --no-deps --disable-pip) | **19 packages; zero known vulnerabilities** | dependency-audit.json |
| Bandit `-r dataguard -ll` | **0 medium, 0 high**; 11 low-severity observations (demo assertions/fixed SQL construction) below configured threshold | bandit.json |
| Compose image build + actual PostgreSQL/API start | Passed; service healthcheck healthy | Docker image metadata and container-smoke.json |
| HTTP end-to-end smoke | Passed readiness, dashboard, unauthenticated write denial, valid publish, exact replay, duplicate quarantine, old snapshot preservation and Prometheus DB-up metric | container-smoke.json |
| Chromium Playwright 1.62.1 | Desktop 1440x1000 and mobile 390x844 pass identity/content/console/overflow/refresh checks | dashboard-check.json and dashboard-1440.png, dashboard-390.png |
| Interactive API documentation | Swagger renders at desktop/mobile; actual GET /health execution returns 200 alive with no console/CSP errors; ReDoc also renders without console errors | docs-check.json, docs-1440.png, docs-390.png |
| Kubeconform v0.7.0 strict | **4 valid, 0 invalid, 0 errors, 0 skipped** | command: `docker run --rm -v "${PWD}/deploy:/manifests:ro" ghcr.io/yannh/kubeconform:v0.7.0 -strict -summary /manifests/kubernetes.yaml` |
| Kubernetes client OpenAPI validation | Blocked: local Docker Kubernetes API at 127.0.0.1:6443 refused connection; independent schema check above passed | no live cluster rollout claimed |
| Terraform fmt -check | Passed | infra/main.tf |
| Terraform init / validate | **Passed**, provider AWS v6.71.0; validation reports valid=true, 0 errors, 0 warnings | terraform-validation.json, infra/.terraform.lock.hcl |
| Actual Airflow 3.1.0 DAG import | **Passed**, DAG and both tasks discovered; older-runtime compatibility evidence | Details and image digest below; configured 3.3.2 CI runtime remains unexecuted |
| Trivy ALL-severity vulnerability + secret scan | **0 vulnerabilities, 0 secrets**, exit 0; no severity filters, ignore flags or suppressions | container-scan.json; database updated **2026-10-30**, context in container-scan-context.json |

The initial Debian image used a transparently dated October 20 scan while a large database download was slow. The final pinned minimal runtime supersedes that evidence: it was scanned for all known vulnerability severities and secrets using a same-day database updated October 30 13:06 UTC and downloaded 14:09 UTC. No findings or suppressions were used. The source cache volume was read-only and unrelated containers were not modified. Remote CI remains separately scoped below.

## Measured fault/recovery and publication latency

Both demos stage and publish valid input, reject duplicate and malformed input, kill an actual child worker with exit code 91 after SQL inserts and before publication commit, prove the old snapshot remains, wait for the committed one-second demo lease, recover the immutable batch, and prove exact materialized row counts and idempotent retry. API's normal lease is 30 seconds.

| Database | Samples | Trades/settlements per batch | Concurrency | p50 ms | p95 ms | p99 ms | Crash-to-recovery ms incl. startup/lease |
|---|---:|---|---:|---:|---:|---:|---:|
| SQLite file | 100 | 100 / 1 | 1 | 42.267 | 56.033 | 60.838 | 3176.752 |
| PostgreSQL 16.13 via Docker port | 100 | 100 / 1 | 1 | 151.880 | 319.956 | 396.599 | 3400.225 |

Raw samples and environment metadata are committed in sqlite-benchmark.json and postgres-benchmark.json. Operation measured is stage + full validation + SQL publication, with `perf_counter`; percentile is nearest rank. Other builds/downloads were active on the same machine, so there is scheduling/I/O contention. These numbers are neither an SLA nor an apples-to-apples database performance comparison; PostgreSQL includes Windows-to-Docker network overhead. No throughput saturation, production data-size, multi-AZ failover or distributed chaos result is claimed.

## Negative/regression evidence

Ten fault matrix cases cover duplicates, malformed numeric schema, missing field, missing FK, forbidden currency, mismatched totals, stale export, extra columns, negative amounts and bool-as-integer. Every case checks old head preservation plus original source/quarantine diagnostics. Additional observed red/green regressions fixed UTC offset date handling, non-ASCII bearer token crashes, blank token configuration and NUL/control identifiers. The streamed body cap test confirms 413 without publication. Direct SQL input UPDATE is blocked by triggers; same-key changed-payload staging is a conflict.

## Unexecuted external checks

No AWS credentials, ACM certificate, domain, deployment role or approved cloud budget were supplied. No Terraform apply, production rollout, remote CI success or public registry artifact is asserted. The parent task owns repository publication and can record later external checks in an appended verification entry.

## Publication and additional runtime verification

The complete source and all three workflow files are published at https://github.com/9059Rohith/dataguard. Local and remote source trees were compared after publication. Remote Actions jobs could not start because of an account-level runner restriction; no passing hosted-CI result is claimed.

An actual **Airflow 3.1.0** Linux container imported the DAG successfully: `dataguard_settlement_publication`, tasks `stage` and `validate_and_publish`, exit 0. Image digest: `sha256:e81cb98fe4e5f60fadde8cc6a1c926a363720339062cd53db04b6442950ab9ee`. This is an older-runtime compatibility check; the configured Airflow **3.3.2** CI runtime remains unexecuted while hosted runners are unavailable. It is not a production Airflow deployment.

## Terraform verification follow-up

The initial slow provider download was stopped after the parent task supplied an extracted provider mirror verified against HashiCorp's official SHA256. `terraform init -backend=false -plugin-dir=... -input=false` and `terraform validate -json` then passed. The provider lock retains the Windows installed-package h1 and official archive zh hashes for all released platforms, including Linux CI. Official checksums were fetched from [HashiCorp's v6.71.0 release](https://releases.hashicorp.com/terraform-provider-aws/6.71.0/terraform-provider-aws_6.71.0_SHA256SUMS), saved as provider-sha256sums.txt and added by scripts/lock-provider.py. This validates provider schemas locally; it does not validate credentials, AWS quotas, regional capacity, deployment cost or an actual apply.

## Documentation CSP regression

An actual browser reproduced `/docs` returning HTTP 200 with no rendered Swagger UI because the global CSP blocked its CDN script, stylesheet, favicon and inline bootstrap. Three regression cases failed for Swagger, ReDoc and OAuth redirect hashes/assets before the fix. Documentation HTML now receives narrowly scoped asset sources and SHA256 hashes of its exact bootstrap bytes; ordinary API, dashboard and non-documentation error responses keep the existing self-only script policy. The full suite passes 25 tests.

`scripts/docs-check.cjs` is a reproducible headless Chromium test: load `/docs`, render the actual OpenAPI UI, open GET /health, select Try it out, execute and check its real 200/alive response. Desktop 1440x1000 and mobile 390x844 runs have zero console errors/CSP violations. ReDoc is separately rendered with zero console errors. This does not simulate or claim a hosted CI run.

The final browser run targets the rebuilt Compose service at `http://127.0.0.1:8003`, with `/ready` reporting ready and Docker reporting healthy. The dashboard's desktop/mobile refresh checks also pass against that rebuilt service.

## Public-boundary and minimal-runtime follow-up

See public-security.md for the observed red/green security regressions. Metadata/metrics are authenticated by default; explicit synthetic-demo mode exposes only bounded aggregate state. Authenticated uploads are bounded before parsing, and unauthenticated mutations do not read their bodies. Raw records/quarantine remain private. The opt-in startup seed uses real staging, validation and SQL publication, and an actual container restart preserves its batch identity without duplicate publication.

The final Dockerfile pins builder/runtime digests, installs cp315 native wheels, copies only the app virtualenv and writable data directory, removes installer/build tools, and runs UID 10001. Actual Python 3.15.1 image tests passed SQLite public startup, PostgreSQL stage/validate/reject/retry, real killed-worker recovery and authenticated HTTP API flows. A 100-sample native PostgreSQL run records p50/p95/p99 **34.884/57.207/86.589 ms** with 100 trades per batch at concurrency one; this local CLI acceptance run is not a production capacity/SLA claim. Details are in minimal-runtime-pg.json and minimal-runtime-pg-http.json.

Public-profile browser checks now target the local minimal-runtime test container on port 18085 (container PORT=7860): dashboard and Swagger desktop/mobile checks pass, GET /health executes with 200/alive, ReDoc renders, and no console/CSP errors were observed. Public read-only HTTP checks and actual restart evidence are in public-demo-smoke.json and public-demo-restart.json. These localhost addresses are test fixtures, not claimed public deployment links.
