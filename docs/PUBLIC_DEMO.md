# Provider-neutral public synthetic demo

The public profile is a read-only view of real SQL publication state seeded with named synthetic records. It is not a public data-upload or code-execution service. No hosting provider, deployed URL, persistent storage or uptime is implied by this file.

## Runtime settings

| Setting | Meaning |
|---|---|
| `DATABASE_URL` | Existing PostgreSQL SQLAlchemy URL, or a writable SQLite file such as `sqlite:////data/dataguard.db` |
| `PORT` | Validated TCP port 1–65535; default 8000; used by the container command and healthcheck |
| `DATAGUARD_PUBLIC_DEMO=true` | Explicitly allow bounded aggregate `/summary` and `/snapshots` metadata, labeled synthetic in the dashboard |
| `DATAGUARD_SEED_DEMO=true` | Stage, validate and transactionally publish the named `synthetic-demo-v1` fixture at startup |
| `DATAGUARD_TOKEN` | Optional server-side random token of at least 32 non-whitespace characters; absent/invalid means all privileged operations are disabled |

Start the built image with its existing `python -m dataguard.entrypoint` command. The process binds `0.0.0.0:$PORT`. The entrypoint accepts an explicit `DATABASE_URL`, preserves the existing PostgreSQL host/password configuration path, initializes schema v1, then starts Uvicorn without URL access logging. Standard `postgresql://` and `postgres://` URLs select the installed Psycopg 3 driver, and new PostgreSQL connection attempts have a five-second timeout. Configure database-side query/lock limits for the selected deployment; the upload deadline is not a database execution deadline. API lifespan handles the opt-in seed even when schema initialization was already done by the entrypoint. No shell commands or connector destinations can be supplied by HTTP.

Use a **dedicated synthetic database**, never a production database, for public-demo mode. Both demo settings default to false. The seed contains three clearly named synthetic trades and two matching settlements in USD/EUR. It passes the same executable contracts and SQL publication transaction as normal batches. Existing named input is verified against the known fixture; restart reuses its committed batch identity and does not manufacture counters or duplicate data. Unexpected source under the seed identity fails startup. Correcting a failed seed remains an operator action; the application does not edit financial data automatically.

Omitting `DATAGUARD_TOKEN` gives a public read-only demonstration: write routes, raw batches, detailed snapshot records, quarantine and metrics all fail closed. Configuring a token retains authenticated admin capabilities; keep it in the hosting secret store and use an operator API client. Never put it in JavaScript, URLs, screenshots or browser storage.

## Resource and request boundary

Host development uses Python 3.12+; the pinned minimal container runs Python 3.15.1 with native binary wheels and no package installer in its final runtime. One process with 512 MiB memory and one CPU is the verified local container profile. The application allows four in-flight requests per process, with fail-fast 503/Retry-After beyond that capacity; cheap liveness remains available. HTTP mutation authentication happens before receiving the body. Authenticated bodies have an 8 MB cap, a ten-second receive deadline, maximum JSON depth 32 and bounded structural width before framework parsing. Programmatic staging also limits the JSON tree and rejects invalid Unicode. Metadata responses contain at most 100 partition heads. Raw records and diagnostics never enter the public summary.

This is an application budget, not a distributed rate limiter or network DDoS defense. Configure the selected platform's request/connection limits and TLS. Multiple processes multiply the request budget. Expensive writes still serialize through the database gate. Do not expose the PostgreSQL port or grant public callers database credentials. Prometheus `/metrics` now requires authentication; configure its token through a protected credentials file as shown in `deploy/prometheus.yml`.

## Persistence choices

| Deployment shape | Works with current application | Tradeoff |
|---|---|---|
| One container + writable durable SQLite volume | Yes; mount `/data` writable by UID 10001 and set explicit SQLite DATABASE_URL | Retains immutable inputs, audit attempts and accepted snapshots; back up the volume; single-node filesystem semantics |
| Container + external PostgreSQL | Yes; set its secret URL and appropriate TLS; bootstrap once before multiple replicas | Durable state across container replacement; connection limits, roles, migrations and remote database availability remain operator responsibilities |
| Free container with ephemeral writable disk | Functional for a clearly labeled synthetic demo | Restarts can lose all history and recreate the actual synthetic seed; no durability/production recovery claim is appropriate |
| Stateless/serverless HTTP function | Requires deployment-specific adaptation, not implemented here | Use external PostgreSQL; separate schema/seed bootstrap from request cold starts; consider connection pooling, concurrent initialization, request deadlines and process-local admission limits; local ephemeral SQLite cannot provide durable history |

No provider-specific database SDK, storage adapter, account change, paid resource or external deployment is introduced by the public hardening. Airflow and recovery jobs are separate trusted operator processes; a public web function does not replace their durable scheduler.
