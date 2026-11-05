# Read-only investigator recovery boundary

The 5 November audit observed a public investigator HTTP 502. The former generic
handler retained no underlying status/exception, so its exact cause remains
unconfirmed. The existing 20-second urllib timeout and provider errors previously
shared the same generic response.

The investigator now shares one retry across quota and transient failures for an
entire investigation, with the existing four-turn/five-provider-attempt limits.
HTTP 500/502/503/504 and timeout/connection failures can consume that allowance.
Positive-seconds and future HTTP-date Retry-After values are honored by returning
the delay without retrying early. Exhausted transients return HTTP 503 with a
retry interval; quota errors remain HTTP 429. HTTP 400 and malformed provider
protocols remain explicit errors. Neither unsuccessful inference nor a fabricated
fallback is presented as a completed investigation.

Each new attempt checks a monotonic 60-second scheduling budget and uses a socket
timeout no greater than 20 seconds or the remaining budget. This does not provide
hard cancellation of an already active blocking read. Gemini requests minimal
reasoning under its existing output-token cap. The billing-disabled free provider
selection and public-capture-only tools are unchanged; no paid fallback is used.

The persistent visitor/global allowance is reserved once before the bounded
investigation. Model retries consume provider quota but never introduce write,
shell, source-sync or arbitrary-network tools. Completed tool evidence is kept
in the conversation rather than replayed as a side effect of a model retry.

Diagnostics contain HTTP status, exception class and attempt count rather than
keys, source records, prompts, provider response bodies or database URLs. New
controlled-fault tests exercise the actual public capture-list tool and assert
bounded recovery, redaction, deadline checks and Retry-After handling. These
tests use failure injection; public captures are unchanged source observations.

The final [portfolio audit](https://github.com/9059Rohith/settlement-recon/blob/main/docs/openfx-interview-readiness.md)
separates initial failures, regression proof and deployed requests. Provider
availability and the semantic correctness of generated prose remain external
limits; use the returned capture IDs and source evidence for review.
