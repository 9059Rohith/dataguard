# DataGuard

[OpenFX readiness audit](https://github.com/9059Rohith/settlement-recon/blob/main/docs/openfx-interview-readiness.md) · [Interview demonstration](docs/INTERVIEW.md)

**A data reliability workspace with real source evidence.** Inspect public GitHub repository metadata, define quality contracts, investigate failed checks, compare immutable captures, and trace every result to its source and SHA-256 digest.

[Live workspace](https://rohith-dataguard.vercel.app) · [Live API docs](https://rohith-dataguard.vercel.app/docs) · [Source](https://github.com/9059Rohith/dataguard) · [Workspace verification](evidence/quality-verification.md)

![DataGuard field journal with the public quality ledger](evidence/field-journal-production-overview.jpg)

## Repository quality workspace

The public workspace has 14 routes, including the contract impact workbench, quality checks, capture history, version comparison, lineage and AI investigator. Repository counts come from captured GitHub REST responses. The bundled workspace capture was collected on 1 November 2026. The interface displays capture and evaluation timestamps and makes freshness checks explicit.

The field journal pairs self-hosted Instrument Serif and Manrope with 22 original botanical and geological illustrations across the 14 console routes. The overview leads from its forest and ginkgo plates into the real quality ledger, source trail, and repository register. Search, sort, and inspect source records, then follow them into their stored checks or public investigation. Mobile navigation supports Escape and focus restoration. Reduced motion disables the entry and scroll effects. [Design audit and production verification](docs/field-journal-audit.md) · [Artwork manifest](dataguard/archive-manifest.json)

The workspace and investigator use eight allowlisted public repositories covering FastAPI, Pydantic, SQLAlchemy, Starlette, Uvicorn, Prometheus Python client, Psycopg, and Pytest. GitHub open issue counts include pull requests. The separate Apache benchmark has its own source artifact and scope. [Workspace capture](dataguard/source_capture.json) · [GitHub repository API](https://docs.github.com/en/rest/repos/repos#get-a-repository)

- Public visitors can inspect source records, filter them, inspect check evidence, compare versions, trace lineage, export actual JSON evidence, and run the limited public AI investigation without an account or bearer token.
- Operators connect using the existing `DATAGUARD_TOKEN` bearer credential. It stays in tab memory and clears on reload.
- Operators can sync all eight actual GitHub sources, import up to 500 actual repository records, change a typed contract, re-evaluate captures, add private investigation notes, and select a recovery reference after current-contract validation.
- Uploads and notes are always private. Public captures contain only the fixed GitHub source collection. All data and policy mutation requests are authenticated before body parsing. The separate token-free AI demo can only read the fixed public GitHub evidence and reserve its own rate-limit slots.
- A separate SQL schema stores immutable capture documents, contract settings, and audit actions. The existing settlement tables and security boundary are retained. PostgreSQL is used in the hosted deployment.
- Quality checks cover minimum volume, required fields, uniqueness, nonnegative integer counters, valid timezone-aware timestamps, capture freshness, and optional license/archived rules. Stored evaluations retain their exact contract and evaluation time; rechecking creates another capture with a parent reference.
- Recovery selects a repository-quality reference after validation. It does not replay financial transactions or claim to recover another production system.

The AI investigator uses **Google Gemini 3.5 Flash-Lite on the free tier**, with a dedicated server-side API key in a Google project whose billing is disabled. It executes `list_captures` and `inspect_capture` against actual public GitHub evidence, then returns the real model answer alongside its tool trace. Gemini never receives private operator uploads or investigation notes. Google may use unpaid API questions and evidence to improve its models, so the interface asks operators to submit public-data questions only. Known configured credentials are rejected in questions before any provider request.

The server selects the fixed Gemini OpenAI-compatible endpoint when `GEMINI_API_KEY` exists; an existing OpenAI integration remains available only when Gemini is absent. It never switches to paid OpenAI usage after a Gemini error. Opaque Gemini tool-call signatures are preserved between model turns and omitted from responses and saved evidence. The original `/api/quality/investigate` remains bearer-authenticated. The default UI instead calls the separate token-free `/api/quality/public-investigate` endpoint. Both use at most four turns, six read-only tools and five provider requests, with one bounded one-second retry after provider quota exhaustion. Persistent quota errors return explicit HTTP 429 with Retry-After; free limits are shared by the Google project and can change. There is no claim of unlimited requests or guaranteed model correctness. See [live Gemini verification](evidence/quality-gemini-verification.md), [Google compatibility documentation](https://ai.google.dev/gemini-api/docs/openai), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), and [unpaid-service data terms](https://ai.google.dev/gemini-api/terms).

## Public recruiter demo

Open [AI investigator](https://rohith-dataguard.vercel.app/console/agent), enter a public-repository question, and select **Investigate public data**. No account, operator token, upload, or provider key is required from the visitor. This is actual Gemini inference over the eight public GitHub repositories; private uploads and notes are excluded.

`POST /api/quality/public-investigate` accepts only `{ "question": "..." }` with 5–600 characters and an 8 KiB body cap. Model, tools, data-source and provider overrides are rejected. The answer is capped at 6,000 characters and the full response at 64,000 bytes; evidence traces identify the actual records read through bounded summaries. Public requests never fall back to a paid provider.

The existing PostgreSQL database stores atomic fixed-window reservations across all workers and restarts: **3 per visitor / 600 seconds**, **2 globally / 60 seconds**, and **30 globally / 86,400 seconds**. A rejected reservation rolls back all bucket increments; an accepted reservation counts even if the model later fails. Exhaustion returns **429** with **Retry-After**, and the UI shows a countdown. Storage or server-protection failure returns **503** before any model call. Expired buckets are removed within successful reservation transactions.

Client identities use a domain-separated HMAC of the IP and the existing server secret; raw IPs and questions are never stored in these buckets. Only runtime `VERCEL=1` enables the platform-overwritten single valid `X-Forwarded-For` address; malformed, chained, duplicate or otherwise untrusted forwarded headers fall back to the socket peer. Explicit cross-origin requests are rejected; the exact request origin and canonical hosted origins are accepted. Nonbrowser clients without an Origin header receive the same limits. Data imports, contract changes, notes, sync, recovery and the original investigator remain protected by bearer authentication.

See [public-demo verification](evidence/quality-public-demo-verification.md). Google may use unpaid API questions and public evidence to improve its models; visitors should enter public-data questions only. Free provider quotas remain shared and variable, and model answers can make mistakes.

Local verification:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check dataguard tests
node --check dataguard/dashboard.js
node --check dataguard/ui-core.js
node tests/test_ui_core.cjs
```

The production deployment disables `DATAGUARD_PUBLIC_DEMO` and `DATAGUARD_SEED_DEMO`. Existing synthetic settlement fixtures are retained for the authenticated legacy pipeline and tests; the public repository workspace does not display them as real transactions.

## Existing settlement pipeline

DataGuard also stages immutable settlement inputs, checks a cross-table financial data contract, and atomically publishes complete date partitions in SQL. Rejected exports stay quarantined; accepted historical versions remain available for authenticated change analysis. The settlement demonstration records discussed below are synthetic. This is not an OpenFX integration or a production financial service.

## PolicyLab signature: test quality policy against immutable evidence

`POST /policies/impact` compares a baseline and proposed policy against up to eight explicitly selected published versions, including retained versions behind the current head. A stricter amount cap, narrower currency set, or mistaken settlement-reference uniqueness rule can reject already valid data. PolicyLab shows those compatibility regressions before enforcement, with canonical policy hashes, successful publication provenance, exact rule counts, bounded opaque samples and conservative `block_candidate`, `shadow_only` or `limited_canary` recommendations. It never installs a policy or changes publication state.

The typed version-1 language supports ranges, currency categories, completeness, uniqueness, publication-relative event freshness, settlement references and reconciled totals. It accepts no executable expressions or SQL. Both policies run in one read-only snapshot with 10-second statement timeouts, a 20-second experiment budget and strict rule/version/source/input bounds. Operator authentication remains required in public-demo mode. Reports exclude raw source IDs, values, idempotency keys and staged payloads.

Read the [PolicyLab language, method and limitations](docs/policylab-method.md), and adapt the explicit version selectors in the [example request](docs/policylab-impact.example.json). Local commands use `DATAGUARD_TOKEN` plus a separately supplied matching `DATAGUARD_OPERATOR_TOKEN`:

```powershell
# impact.json contains baseline, candidate, versions:[{period,batch_id}], sample_limit
python -m dataguard.cli policy-impact impact.json
# Always uses a disposable synthetic SQLite database; never the operator database
python -m dataguard.cli policy-evaluate --output evidence/policylab-controlled.json
```

The controlled evaluation runs four policies over three synthetic accepted versions with literal expected outcomes: a compatible cap accepts all, a tighter cap rejects one, a currency restriction rejects another, and settlement-reference uniqueness rejects all three. Invalid policies and quarantined batches are also exercised. This is a finite policy-compatibility study, with no production-accuracy or generalization claim. [Recorded study](evidence/policylab-controlled.json) · [Verification](evidence/policylab-verification.md).

## Six implemented capabilities

| Capability | Concrete behavior | Why it matters |
|---|---|---|
| Executable settlement contracts | Reject unknown/missing fields, incorrect types, duplicate IDs, invalid references/currencies, stale exports, wrong UTC dates and inconsistent totals | A malformed export cannot replace the reconciled dataset |
| Immutable, idempotent ingestion | Canonical JSON SHA256; repeated key/payload returns one ID; conflicting reuse returns 409; SQL triggers prohibit staged edits/deletes | Retries and investigations refer to immutable source values |
| Transactional publication and recovery | Rows, partition head and successful attempt commit together; durable leases and attempt fencing recover interrupted workers | A real process killed after insertion leaves the previous version readable |
| Published-version change analysis | Protected SQL counts of added, removed, changed and unchanged trades/settlements with both source digests and publication provenance | Review a correction without exporting raw records or switching the head |
| PolicyLab quality-policy experiments | Strict declarative policies, immutable SQL evidence, baseline/candidate rejection transitions, opaque bounded samples and staged recommendations | Catch a proposed policy rejecting valid historical data before enforcement |
| Operable service and deployment artifacts | FastAPI/CLI, Airflow 3 DAG, private metrics, liveness/readiness, non-root digest-pinned runtime, Compose, Kubernetes and Terraform | Connect correctness to repeatable operational checks and explicit rollout boundaries |

An isolated Prometheus drill observed both database outage and failed-scrape alerts firing and clearing after recovery. [Monitoring drill](docs/prometheus-alert-drill.md)

```mermaid
flowchart LR
  Input[CLI / protected API / Airflow] --> Stage[(Immutable source + SHA256)]
  Stage --> Claim[Durable lease + attempt fencing]
  Claim --> Contract[Cross-table contract]
  Contract -->|invalid| Reject[(Quarantine + diagnostics)]
  Contract -->|valid| Publish[One SQL transaction]
  Publish --> Versions[(Retained accepted rows + date head)]
  Versions --> Read[Protected snapshot / version comparison]
  Versions --> Demo[Opt-in aggregate dashboard]
  Claim -->|expired lease| Retry[Retry exact staged batch]
  Retry --> Contract
```

## Try it locally

Python 3.12+; the pinned Docker runtime uses Python 3.15.1. SQLite needs no database server. Run from this repository in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
$env:DATABASE_URL = 'sqlite:///review.db'
$env:DATAGUARD_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(40))"
$env:DATAGUARD_PUBLIC_DEMO = 'true' # Dedicated synthetic database only
$env:DATAGUARD_SEED_DEMO = 'true'
.\.venv\Scripts\python.exe -m dataguard.cli init
.\.venv\Scripts\uvicorn.exe dataguard.api:app --host 127.0.0.1 --port 8003
```

Open [the local dashboard](http://localhost:8003) and [OpenAPI](http://localhost:8003/docs). Keep this terminal's database/token settings for the walkthrough below. Seeding uses the actual stage/validate/publish path and reuses its immutable seed on restart. Both demo flags default to false.

For PostgreSQL 16 and the restricted service container, stop local Uvicorn on port 8003 first:

```powershell
$env:POSTGRES_PASSWORD = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:DATAGUARD_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(40))"
docker compose up -d --build
```

Compose binds the API to `127.0.0.1:8003` and PostgreSQL to `127.0.0.1:55434`. Save the same environment values for later calls; changing the password variable does not rotate an existing volume's password. `docker compose down` preserves that volume. See [deployment instructions](docs/DEPLOYMENT.md) for bootstrap and configuration.

## Walk through a correction and failure

In the configured SQLite PowerShell terminal, stop Uvicorn with Ctrl+C while retaining its environment, create two accepted versions, and compare them:

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python -m dataguard.cli fixture --rows 3 --output sample.json
$first = & $python -m dataguard.cli stage sample.json --key review-v1 --run | ConvertFrom-Json
$period = (Get-Content sample.json -Raw | ConvertFrom-Json).period
& $python -c "import json; from pathlib import Path; p=json.loads(Path('sample.json').read_text()); p['trades'][0]['amount_cents']+=50; p['settlements'][0]['amount_cents']+=50; Path('sample-v2.json').write_text(json.dumps(p))"
$second = & $python -m dataguard.cli stage sample-v2.json --key review-v2 --run | ConvertFrom-Json
& $python -m dataguard.cli compare $period --from-batch $first.batch_id --to-batch $second.batch_id
```

Expected: trades `changed=1, unchanged=2`; settlements `changed=1`. Added means present only in the destination, removed means present only in the source. Same-ID records with any different stored non-key field count once as changed. A timestamp spelling change counts even if it denotes the same instant. Comparing a version to itself has zero changes. Older publications remain comparable after the head advances.

To demonstrate quarantine, keep the changed trades but put the old settlement total in another export and stage it with a **new key**:

```powershell
& $python -c "import json; from pathlib import Path; p=json.loads(Path('sample-v2.json').read_text()); p['settlements'][0]['amount_cents']-=50; Path('sample-bad.json').write_text(json.dumps(p))"
$bad = & $python -m dataguard.cli stage sample-bad.json --key review-invalid --run | ConvertFrom-Json
$bad # status=rejected; diagnostics include settlement_total
```

The head stays on the second accepted batch; comparison against the rejected ID returns not found. Correct the producer and stage another version; never edit staging. Rerunning with changed source requires new keys because key reuse is deliberately enforced.

The file edits use Python's JSON parser to preserve timestamp strings exactly;
PowerShell date inference followed by reserialization can change their spelling.

Restart Uvicorn with the quickstart command. The same comparison through the protected API is:

```powershell
$headers = @{ Authorization = "Bearer $env:DATAGUARD_TOKEN" }
Invoke-RestMethod -Headers $headers -Uri "http://localhost:8003/snapshots/$period/compare?from_batch=$($first.batch_id)&to_batch=$($second.batch_id)"
```

For a real worker interruption and fresh local measurement, stop Uvicorn again and run:

```powershell
& $python -m dataguard.cli demo --samples 100 --rows 100 --output evidence/local-benchmark.json
```

The demo rejects duplicate and malformed inputs, starts a child process, exits that worker with code 91 **inside an open transaction after row insertion**, verifies the previous head, waits for the committed one-second demo lease, recovers the exact batch, and checks row uniqueness. It then measures stage + validate + publication operations. This writes synthetic history: use a disposable local database. [Incident procedures](docs/RUNBOOKS.md) cover the API's default 30-second lease.

## Contract and consistency model

Root keys are exactly `period`, `produced_at`, `trades`, `settlements`. Both tables contain 1–10,000 rows; staging and HTTP bodies are bounded at 8 MB. Amounts are integer **minor currency units**, despite `amount_cents`; booleans/floats are rejected and no FX conversion occurs. Trades reference settlements in the same batch, use the same currency and sum exactly to each settlement total. Event UTC date equals the canonical date period. Export time must be within the past 24 hours / future five minutes; historical backfills need fresh exports. See [the contract](docs/CONTRACT.md).

A global SQL gate, durable lease and current attempt identity fence workers. Rows, head and successful attempt commit atomically. Validation failure leaves the head unchanged. A later staged valid batch takes precedence; an older pending retry becomes `superseded` without publishing. Retained rows let readers use one captured batch identity even if the head advances mid-read.

Source digests identify canonical parsed JSON, including array order; they do not preserve a file's original whitespace or object-key formatting.

Comparison requires a committed `published` attempt for **both** IDs in the requested period. Staged, running, failed, rejected, never-published superseded, missing and wrong-period IDs share 404. Malformed periods/IDs return 422. SQL unions both versions with explicit side markers, groups by record ID, and compares MIN/MAX of nonnull stored fields. It avoids record self joins. The fixed-size response contains two provenance objects and six counts per table, without row IDs/values. It does not mutate heads or replay validation. Partition ownership is enforced; the application has one shared operator identity, not tenant RBAC.

| Interface | Access and behavior |
|---|---|
| `POST /batches` | Bearer; stage `{key,payload}`; exact replay returns existing ID |
| `POST /batches/{id}/run`, `POST /recover` | Bearer; publish/quarantine or recover pending work |
| `GET /batches/{id}`, `GET /quarantine` | Bearer; immutable source/history or last 100 rejected attempts |
| `GET /snapshots/{period}` | Bearer; complete active trade/settlement records |
| `GET /snapshots/{period}/compare?from_batch=1&to_batch=2` | Bearer even in demo mode; accepted-version counts/provenance |
| `GET /summary`, `GET /snapshots` | Bearer by default; bounded metadata public only with explicit demo opt-in |
| `GET /metrics` | Bearer; Prometheus latency, process and persisted-attempt signals |
| `/`, `/docs`, `/health`, `/ready` | Public shell/docs and process/database readiness |

Missing/blank/short configured tokens fail closed with 503; invalid credentials return 401. Key conflicts/active leases return 409. Contract failure is a persisted `rejected` result. CLI/Airflow are trusted DB clients, using DB credentials rather than the HTTP token. The [Airflow 3 DAG](dags/dataguard_pipeline.py) stages a mounted artifact and publishes its ID; scheduler/workers are separate from the API image.

## Real-source benchmark and verification

Replay the quality contract against 500 distinct Apache repositories captured from the GitHub REST API on 4 November 2026. The baseline passes six checks. The strict policy quarantines the same data because 96 repositories lack license metadata and 177 are archived. The live panel shows the exact source fingerprint, affected repository examples, and downloadable source and measurement files. [Run the live replay](https://rohith-dataguard.vercel.app/console/checks) · [Method and provenance](docs/repository-quality-benchmark.md)

The measured workflow uses the existing authenticated upload, recheck and recovery endpoints against fresh local SQLite and PostgreSQL databases. The harness checks publication, quarantine under a stricter policy, a blocked recovery with an unchanged reference, and a successful recovery after restoring the baseline. The report contains 30 observations per operation and database, raw timings and percentile calculations. [Measured report](dataguard/quality_benchmark_report.json)

| Operation | SQLite 3.53.1 p95 | PostgreSQL 18.2 p95 |
|---|---:|---:|
| Upload and publish 500 records | 238.53 ms | 337.12 ms |
| Recheck and quarantine 500 records | 128.42 ms | 179.05 ms |
| Block recovery under the strict contract | 47.88 ms | 100.22 ms |
| Persist recovery under the baseline contract | 61.21 ms | 134.46 ms |

The measurements use a single sequential in-process client on Windows 11 and Python 3.12.14. Each timing covers the API request through its response and includes the local database operations. [Protocol and limits](docs/repository-quality-benchmark.md)

The legacy settlement comparison artifacts document synthetic engineering regression tests separately. [Comparison verification](evidence/comparison-verification.md) · [Security evidence](evidence/public-security.md)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m bandit -r dataguard -ll
# Dedicated disposable integration database only: tests truncate its tables.
docker compose exec postgres psql -U dataguard -d dataguard -c "CREATE DATABASE dataguard_test"
$env:TEST_DATABASE_URL = "postgresql+psycopg://dataguard:$env:POSTGRES_PASSWORD@127.0.0.1:55434/dataguard_test?connect_timeout=5"
.\.venv\Scripts\python.exe -m pytest -q
```

The suite refuses PostgreSQL test database names without `_test`. Create a dedicated test database and set `TEST_DATABASE_URL` only for that disposable database.

Hosted GitHub Actions are currently blocked by an account-level runner restriction. Definitions exist for SQLite/PostgreSQL tests, lint, audit, Airflow DAG import, container scanning and Terraform validation; executed local evidence is reported independently. No passing hosted badge is claimed.

## Public Contract Impact Workbench

Open [Contract impact](https://rohith-dataguard.vercel.app/console/impact) to compare your own
baseline and candidate acceptance criteria against one actual immutable GitHub capture.
Six bounded rules cover metadata, language, archived status, source push freshness, stars,
and open issues. The explicit UTC clock makes historical and current-age analyses reproducible.
Results show accepted/rejected transitions, exact per-record evidence, rule witnesses, and source
and policy SHA-256 fingerprints. Download the complete report or an OpenLineage dataset assertion
facet validated against the vendored official schema. Disabled rules are omitted from that facet.

This public, side-effect-free experiment does not change stored contracts, inspect private uploads,
call an AI model, or use investigator quota. Criteria express the visitor's selection preferences;
they do not rate software quality or security. [Design and primary sources](docs/contract-impact-design.md),
[API tests](tests/test_contract_impact.py), [measured local benchmark](evidence/contract-impact-benchmark.json).

## Live, local, or configuration only?

| Scope | Status and boundary |
|---|---|
| Vercel repository workspace + durable PostgreSQL + free Gemini investigator | Live; [workspace verification](evidence/quality-verification.md) and [real Gemini verification](evidence/quality-gemini-verification.md). Public visitors inspect actual GitHub captures; private uploads and authenticated operator actions remain protected. |
| Published-version comparison | Deployed and verified over public HTTPS; operator token required. [Live feature proof](evidence/review-public-feature.json) checks accepted-version counts, provenance and denied access. Local tests exercise changed versions and recovery. |
| SQLite/PostgreSQL publication, rejection, killed-worker recovery | Executed locally with committed tests and measurements |
| Digest-pinned Python 3.15.1 image, Compose, HTTP/browser checks | Executed locally; UID 10001, no installer in runtime, restricted Compose service |
| Airflow 3 orchestration | Real SDK DAG; requires separate scheduler/workers and artifact mount |
| Kubernetes / AWS Terraform | Deployment artifacts; Terraform validated. No live Kubernetes rollout or AWS apply claimed |

Terraform describes HTTPS ALB, private encrypted RDS, Fargate, scoped secrets and rollback controls. Kubernetes describes resource limits, probes, restricted security and network policy. Both require environment-specific images, secrets and network/TLS configuration: [deployment scope](docs/DEPLOYMENT.md), [public-demo profile](docs/PUBLIC_DEMO.md).

## Security, tradeoffs and reviewer path

Raw inputs, diagnostics, comparison provenance, metrics and writes require the operator token. Do not expose aggregates from real financial data; the public demo has synthetic records. SQL parameters are bound. Authentication precedes mutation-body reads; size, structure, deadline and per-process capacity limits bound small-service work. Documentation uses exact script CSP hashes; the dashboard uses a self-only script policy. See [security model](SECURITY.md).

The global gate trades throughput for inspectable correctness; recovery scans history. Retained versions consume storage. Comparison is bounded by admitted row counts, but is not a CDC feed, semantic timestamp normalizer or row-level diff. There is no streaming engine, multi-tenant RBAC, schema migration framework, production SLO, tested multi-AZ failover, external exactly-once guarantee or real payment execution. Database-admin tampering, upstream authenticity and backup/restore policy remain outside the application guarantee.

Five-minute review: live dashboard → correction comparison → killed-worker demo → `Pipeline.process` and `Pipeline.compare` in [service.py](dataguard/service.py) → [ADRs](docs/ADR.md) and [interview discussion](docs/INTERVIEW.md). For data engineering, follow [contract](docs/CONTRACT.md), [traceability](docs/TRACEABILITY.md) and provenance. For DevOps, follow [runbooks](docs/RUNBOOKS.md), [Dockerfile](Dockerfile), deployment and verification evidence.

Current release evidence: [protected public feature](evidence/review-public-feature.json), [fresh all-severity runtime image scan](evidence/signature-image-scan.json), and [tracked-source secret scan](evidence/review-source-secret-scan.json). These are executed checks with defined scope, not a guarantee of perfect security.

Current signature release: [actual protected HTTPS checks](evidence/signature-public-feature.json), [all-severity runtime scan](evidence/signature-image-scan.json), and [measured code changes](evidence/signature-code-metrics.json). Application, test and operational-script lines are counted separately; documentation, comments and docstrings are excluded.
