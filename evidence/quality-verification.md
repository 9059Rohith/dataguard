# Repository workspace verification — 1 November 2026

## Live deployment and real data

- Public URL: https://rohith-dataguard.vercel.app (also https://dataguard-one.vercel.app).
- Final runtime deployment **READY**: `dpl_CvPd8bxNrh5cDRwcspz25oLc4q3e`, source commit `c40ccb9`, immutable URL https://dataguard-70kzhky4m-rohiths-projects-5e14931b.vercel.app. Final browser verification passed all 13 routes at both viewports, including rendered Unicode checks, search, record inspection, and operator access dialog.
- The final deployment retained both actual public capture versions and the same verified eight-record latest digest. No private uploads were visible to public API requests.
- Thirteen distinct routes under `/console/`: overview, datasets, contracts, checks, batches, quarantine, versions, lineage, incidents, recovery, agent, connections, settings.
- Actual authenticated production `POST /api/quality/sync` returned 201 and persisted eight GitHub repository records in PostgreSQL at `2026-11-01T18:16:18.944038+00:00`.
- Capture ID: `71623033-6147-4fa0-a5b6-2d0019ca5f7a`.
- Normalized record SHA-256: `54d89c05d727cef779eaf4148dd570d2fb21a3f3714cefab86621d44fdf71bd0`.
- Sources are the actual public GitHub repository API, including the canonical Kludex locations of Starlette and Uvicorn. Refresh follows no redirects and accepts no user-controlled source URL.
- Deployment disabled `DATAGUARD_PUBLIC_DEMO` and `DATAGUARD_SEED_DEMO`. Live `/summary`, `/snapshots`, and `/metrics` returned 401 without credentials. Unauthenticated workspace sync and upload also returned 401.
- Machine-readable sanitized evidence: [quality-live.json](quality-live.json). No credential values are saved in evidence.

## Functional verification

- Full Python suite against an isolated local PostgreSQL database: **165 passed, 0 skipped** in 55.64 seconds, including the actual EXPLAIN ANALYZE comparison work-budget regression. A separate local login and an owned database ending in `_test` were created on loopback port 55434; the hosted database was not used for destructive test setup.
- Separate SQLite run: **164 passed, 1 PostgreSQL-only skip**.
- Fourteen new workspace tests cover source provenance, 13 deep links, private upload isolation, quarantine, current-contract restore gating, immutable rechecks, private notes, invalid bearer rejection, source errors, independent data checks, explicit missing-provider behavior, evidence tool roundtrips, rejection of unsupported agent claims, and agent budgets. Workspace tests freeze their evaluation clock relative to the committed historical source, so the CI expectations do not expire as the real capture ages.
- `ruff check .`, `ruff format --check .`, and JavaScript syntax checks passed.
- `pip-audit -r requirements.lock --no-deps --disable-pip` found no known vulnerabilities. The local environment audit also passed after updating the pre-existing local pip 25.0.1 tool to 26.2.2; the production Dockerfile already pins pip 26.2.2.
- Bandit found no issues in the new `quality.py` module, and no medium/high findings across `dataguard`. The full low-severity scan retains 13 existing findings; none are in the new module. Nine flag assertions inside the synthetic CLI demo/benchmark verification, two flag the trusted fixed Uvicorn launcher and PATH lookup in the container entrypoint, and two flag environment-variable name literals rather than credential values. No blanket claim of zero full-scan findings is made.
- Production Playwright Chromium: **13 desktop and 13 mobile routes**, repository search, exact record inspection, operator dialog, zero browser errors, and zero document overflow. Browser plugin skill was absent, so regular Playwright was used.
- Desktop viewport: **1440 × 1100**. Mobile viewport: **390 × 844**. Screenshots: [desktop](quality-desktop.png), [mobile](quality-mobile.png).
- Local operator browser flow passed with actual captured GitHub source records: connect operator → import actual records → save contract → re-evaluate → save private investigation note → select validated recovery reference → disconnect → confirm notes remain private. The local-only token is a test credential, not a hosted credential.
- The hosted AI provider is **not configured**. A valid authenticated investigation request returned **503** with an explicit configuration message. No AI output is fabricated. The actual OpenAI two-tool loop is tested with controlled provider responses; a real model execution could not be verified without a provider credential.

## Visual verification

The shared concept board was inspected using `view_image`: `C:/Users/BhaviChasvi/.codex/generated_images/01a183ed-544d-7fc0-b3ed-90627fdab1d2/exec-e4084587-37db-4d02-b1f9-7205a224f5b7.png`, bottom-left DataGuard panel. The production desktop and mobile screenshots were also inspected with `view_image`.

| Point | Concept / intended direction | Rendered result and decision |
|---|---|---|
| Palette | Forest sidebar, ivory workspace | Preserved forest navigation and muted ivory surfaces. |
| Hierarchy | DataGuard brand, workspace navigation, functional tables | Preserved. Separate deep-linked pages replace cramped multi-panel starter content. |
| Typography | Readable reliability console | Intentional editorial refinement: serif display headings with compact sans-serif data and controls. |
| Data density | Tables for source records and checks | Preserved. Tables use actual GitHub rows; empty views describe real absence. |
| Controls | Real contract, source, quarantine actions | Every visible mutation is connected to an authenticated API; public actions inspect, filter, compare, and export. |
| Responsive layout | Usable smaller viewports | Mobile sidebar collapses; grids stack; wide data tables scroll within their container. A grid minimum-width overflow was fixed. A Windows text-encoding regression was also caught in final QA, repaired, and covered by a rendered Unicode check. |
| Visible copy | No invented real-world metrics | All counts and statuses derive from persisted source records or evaluations. The AI configuration blocker is explicit. |

The editorial typography and expanded thirteen-page information architecture are intentional refinements of the shared concept. The final implementation was visually checked against that direction, including current source data, palette, sidebar hierarchy, spacing, table treatment, and mobile wrapping. No unresolved clipping or placeholder-data mismatch remained in the inspected views.

## Reproduce the browser checks

Install Playwright in a development environment, then run `node scripts/quality-browser.cjs`. Set `QUALITY_BASE_URL` to target the hosted URL; the default is `http://127.0.0.1:8013`. `PLAYWRIGHT_MODULE` can point to an existing Playwright installation. The script writes the two screenshots above.

For the local operator flow, start Uvicorn with `DATAGUARD_TOKEN=quality-local-verification-operator-0000000000` against a disposable local database, then run `node scripts/quality-operator-browser.cjs`. It imports the actual repository records from the committed capture, not generated transaction records.
