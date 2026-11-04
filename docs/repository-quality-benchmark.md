# Repository quality benchmark

The source consists of 500 distinct public Apache Software Foundation repositories. DataGuard captured five 100-record pages from the GitHub REST organization repository endpoint on 4 November 2026, between 13:10:01 and 13:10:19 UTC. The request sorts by ascending creation date and selects public repositories. The findings apply to that ordered Apache sample. [GitHub source endpoint](https://api.github.com/orgs/apache/repos?type=public&sort=created&direction=asc&per_page=100&page=1) · [GitHub API documentation](https://docs.github.com/en/rest/repos/repos#list-organization-repositories)

The pinned JSON retains the fourteen metadata fields consumed by DataGuard and the actual observation window, request URLs, HTTP dates, encoded response sizes and SHA-256 fingerprints. A second hash records each normalized page and the aggregate hash `319786d03ccb4c50a579a4bb1fb69e3a0f4887411b8e8909dd876139b80f24a1` identifies all 500 normalized records in order. The collector checks the owner, public visibility, page lengths and unique IDs. A fresh collection can differ as GitHub changes. [Pinned capture](../dataguard/quality_benchmark_source.json) · [Collector](../scripts/capture_quality_benchmark.py)

The [Quality checks demo](https://rohith-dataguard.vercel.app/console/checks) replays the evaluator using the capture time. The baseline requires at least 500 rows and passes its six checks. The strict policy also requires license metadata and rejects archived repositories. It quarantines the capture because 96 records lack license metadata and 177 are archived. A row can fail both rules. Missing license metadata is an observation about the response field. The demo has two fixed policies and returns source fingerprints, check counts and up to four actual witnesses per rule. [Strict live replay](https://rohith-dataguard.vercel.app/api/quality/benchmark?policy=strict)

The harness runs one sequential FastAPI TestClient against SQLite and local PostgreSQL. Each database gets one discarded warmup cycle followed by 30 measured cycles. Each cycle uses the 500 pinned source rows and verifies four outcomes through the existing authenticated API.

1. Upload the records under the baseline and check the published status and exact source hash.
2. Apply the strict contract and recheck. Check quarantine, exact failure counts, unchanged source hash and parent capture reference.
3. Attempt recovery of the original capture under the strict contract. Check HTTP 409 and the unchanged recovery reference.
4. Restore the baseline policy and recover the original capture. Check the persisted reference and that the original capture remains unchanged.

Measurements cover request through full response and include SQL persistence and application serialization. The runner pre-encodes the upload body. The measured interval excludes source retrieval, API startup, the warmup cycle, contract changes, assertion work and external HTTP. Upload capture time in the isolated workflow is the time DataGuard received the data. The source artifact preserves the original GitHub observation time independently. Each row in the report gives the median, nearest-rank p95, maximum and all raw elapsed times. These observations describe one sequential client on the recorded machine. [Measured report and raw samples](../dataguard/quality_benchmark_report.json)

Run the same capture with the repository's locked development dependencies installed.

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_repository_quality --backend sqlite --samples 30 --output quality-local-report.json
# Configure DATAGUARD_BENCH_POSTGRES_ADMIN with a loopback URL for a disposable cluster.
.\.venv\Scripts\python.exe -m scripts.benchmark_repository_quality --backend both --samples 30 --output quality-local-both.json
# Collect a new snapshot into a separate file for inspection.
.\.venv\Scripts\python.exe -m scripts.capture_quality_benchmark apache-new-capture.json
```

The runner creates its own SQLite database and randomly named PostgreSQL database. PostgreSQL must be on loopback and the connection must have permission to create and remove the new benchmark database. Keep the checked-in source artifact to reproduce the measured workload. The deployed benchmark serves that artifact independently of operator captures and recovery references. [Benchmark harness](../scripts/benchmark_repository_quality.py)

## Verification

All 195 tests passed with PostgreSQL enabled. The benchmark tests verify source fingerprints, exact replay failures, HTTP method boundaries and raw-sample percentiles. Production deployment `dpl_7tQyQAR3A4Rt3ayheympRP98bow6` returned HTTP 200 on both replay policies and both artifact downloads. The returned results match the local evaluator, the downloads match the committed JSON, and a before-and-after comparison confirmed the same workspace captures, contract, actions and recovery reference. [Production HTTP evidence](../evidence/repository-quality-benchmark-live.json)

The browser ran both policies through the public controls. The baseline displayed `published`, the strict policy displayed `quarantined`, and the two failed rules displayed their exact 96/500 and 177/500 counts with repository witnesses. [Live panel screenshot](../evidence/repository-quality-benchmark-live.jpg) · [Witness screenshot](../evidence/repository-quality-benchmark-witnesses.jpg)
