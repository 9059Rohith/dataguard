# Gemini investigator verification — 2 November 2026

DataGuard now selects the real Google Gemini `gemini-3.5-flash-lite` model using a dedicated API-restricted server-side key. The Google project `rohith-openfx-ai-free-261102` was verified at setup with `billingEnabled: false`. No paid billing account was enabled. The endpoint is fixed to `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`.

A real authenticated local API investigation returned HTTP 200 in 5.19 seconds. It made three actual successful provider requests and executed `list_captures` followed by `inspect_capture` against eight actual captured GitHub repository records before returning a cited 2,591-character answer. [Sanitized local proof](quality-gemini-local.json) contains the actual answer and tool evidence, with no API credentials or opaque thought signatures.

Gemini tools exclude private operator uploads and investigation notes. An exact public-source/allowlisted-repository check also applies to direct capture inspection. Known configured credentials are rejected in questions before any provider request. The UI explains that Google may use unpaid API questions and public evidence to improve its models, and asks operators to enter public-data questions only. See [Google's unpaid-service data terms](https://ai.google.dev/gemini-api/terms).

Every investigation remains bearer-authenticated. Budgets are four model turns, six evidence tools, five total provider requests, and one one-second quota retry. Persistent provider quota/rate limiting returns HTTP 429 and Retry-After 60; it never switches to paid OpenAI usage after a Gemini error. Free quotas are shared per Google project, vary by model and account, and can change. See [Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

Complete assistant messages and their opaque Gemini tool-call signatures are replayed to the provider, as required for multi-turn tool calls. Public API results and verification artifacts contain only the final answer and semantic tool name/arguments/results. No credential or thought-signature values are retained in committed evidence. The [Google compatibility reference](https://ai.google.dev/gemini-api/docs/openai) describes this endpoint.

Nineteen workspace tests passed, including five new Gemini tests for provider precedence, signature preservation, exclusion of private uploads/notes, bounded quota handling, credential rejection, status metadata, and anonymous-request rejection. The full SQLite suite passed 169 tests with the existing one PostgreSQL-specific comparison skip. Ruff, formatting, JavaScript syntax and Bandit for the provider module passed. No new dependency was added.

Production and browser verification follow below after the deployment is ready.
