# Executed public-exposure hardening

Date: 2026-10-30. Synthetic local fixtures only. No external host, cloud mutation, live customer data or provider-specific storage adaptation is claimed.

The regression suite first observed anonymous aggregate/metrics access, unauthorized request-body reads, excessive JSON acceptance, unsafe keys reaching storage, invalid Unicode persistence, unbounded metadata lists, out-of-range integer binding failures, and missing request admission/deadline behavior. The final full suite has 55 passes and PostgreSQL storage suite has 19 passes.

| Boundary | Verified result |
|---|---|
| Default metadata and metrics | Anonymous denied; authorized reads work |
| Explicit public demo | Aggregate metadata only; raw records, original batches, quarantine and metrics remain denied anonymously |
| Unauthorized mutations | ASGI receive callback is never called; fail closed before parsing |
| Upload budget | 8 MB known/streamed cap; depth 32 and structural width checked before parsing; slow body returns 408 |
| Capacity | Excess work returns 503; liveness remains 200; slots release after completion |
| Storage inputs | NUL/control/unsafe keys and invalid Unicode refused before SQL effects; valid literal JSON delimiters remain accepted |
| Public output budget | 150 test heads produce at most 100 returned heads; no source IDs, idempotency keys or raw amounts in summary |
| Error redaction | Simulated database errors containing a connection string and token return only generic 503 |
| PostgreSQL | Unsafe-key regressions plus real contract/recovery tests pass; URI aliases select Psycopg; connection attempts have five-second timeout |
| Startup seed | Known synthetic fixture passes actual stage/contracts/SQL publish; repeat startup uses same batch; unexpected input under seed identity fails |
| Runtime | Python 3.15.1, UID 10001, no installer; pinned multi-stage image uses native wheels |
| Actual container acceptance | SQLite public profile on PORT=7860, native PostgreSQL CLI fault/recovery and authenticated HTTP API flows pass |
| Actual restart | Batch ID remains 1 and published attempt count remains 1 across named-volume container restart |
| Browser | Desktop/mobile synthetic dashboard and Swagger health execution pass; ReDoc renders; zero console/CSP errors |
| Supply chain | Same-day Trivy database, all vulnerability severities plus secret scanner: zero findings, no suppressions |

The app admission limit is per process, not a distributed rate limiter. Database query/lock limits, platform connection limits, TLS, deployment bootstrap and durable storage remain deployment configuration. A free ephemeral-disk profile can recreate genuine synthetic state after restart but cannot claim preserved audit history. The package exposes no user-supplied command, connector destination or chaos parameter through HTTP.
