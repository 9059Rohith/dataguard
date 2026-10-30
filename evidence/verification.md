# Executed verification — 2026-10-30

Environment: Windows 11, host Python 3.12.14, Docker Engine 28.5.1 with Linux containers, PostgreSQL 16.13. Isolated `.venv` and independent Git repository. Synthetic data only. Commands were executed locally; this document does not claim remote CI or cloud deployment success.

| Check | Result | Retained evidence |
|---|---|---|
| Full `python -m pytest -q` | **22 passed**, 13.67 seconds, no warnings | unit-tests.txt |
| PostgreSQL `pytest -q tests/test_pipeline.py` | **15 passed** against real PostgreSQL; final run uses dedicated dataguard_test database | postgres-tests.txt |
| Ruff check + format check | Passed | tool execution output |
| Python compileall for service/DAG/scripts | Passed | tool execution output |
| Runtime pip-audit (exact complete pinned closure, --no-deps --disable-pip) | **19 packages; zero known vulnerabilities** | dependency-audit.json |
| Bandit `-r dataguard -ll` | **0 medium, 0 high**; 11 low-severity observations (demo assertions/fixed SQL construction) below configured threshold | bandit.json |
| Compose image build + actual PostgreSQL/API start | Passed; service healthcheck healthy | Docker image metadata and container-smoke.json |
| HTTP end-to-end smoke | Passed readiness, dashboard, unauthenticated write denial, valid publish, exact replay, duplicate quarantine, old snapshot preservation and Prometheus DB-up metric | container-smoke.json |
| Chromium Playwright 1.62.1 | Desktop 1440x1000 and mobile 390x844 pass identity/content/console/overflow/refresh checks | dashboard-check.json and dashboard-1440.png, dashboard-390.png |
| Kubeconform v0.7.0 strict | **4 valid, 0 invalid, 0 errors, 0 skipped** | command: `docker run --rm -v "${PWD}/deploy:/manifests:ro" ghcr.io/yannh/kubeconform:v0.7.0 -strict -summary /manifests/kubernetes.yaml` |
| Kubernetes client OpenAPI validation | Blocked: local Docker Kubernetes API at 127.0.0.1:6443 refused connection; independent schema check above passed | no live cluster rollout claimed |
| Terraform fmt -check | Passed | infra/main.tf |
| Terraform init / validate | **Passed**, provider AWS v6.71.0; validation reports valid=true, 0 errors, 0 warnings | terraform-validation.json, infra/.terraform.lock.hcl |
| Actual Airflow 3.1.0 DAG import | **Pending image download**; official image pull began but large layers have not completed at this checkpoint | CI contains actual SDK/DAG import assertion; no local import success claimed |
| Trivy fixable HIGH/CRITICAL | **0 findings**, exit 0, final image scanned | container-scan.json; cache updated **2026-10-20**, context in container-scan-context.json |

Fresh Trivy database download was attempted and stopped after approximately 35 KiB/s transfer implied over an hour for 130.79 MiB. A read-only copy of an existing local DB was used to complete the dated scan. This provides a historical known-vulnerability check, not assurance against advisories after October 20. CI's fresh Trivy scan must pass before release. No unrelated Docker containers or cache source volume were modified.

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
