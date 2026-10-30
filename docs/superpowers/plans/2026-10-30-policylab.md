# PolicyLab Implementation Plan

> **For agentic workers:** Execute this plan inline with test-driven development and verification-before-completion. User requested continuous execution without questions and a commit on existing main.

**Goal:** Evaluate proposed quality policies against selected immutable published SQL versions and expose false rejections before enforcement.

**Architecture:** A strict version-1 declarative policy model compiles only allowlisted SQLAlchemy expressions. A read-only snapshot evaluator returns counts and report-local opaque samples, successful publication provenance, baseline/candidate regressions, and conservative staged rollout advice. This does not alter admission contracts, heads, attempts, or published rows.

**Tech Stack:** Python, existing Pydantic/FastAPI, SQLAlchemy, SQLite and PostgreSQL; no new dependencies.

**Spec:** Parent assignment in this chat; interfaces and exact bounds are pinned below.

## Global Constraints

- Work only in dataguard; no deployment, push, workflow edits, or parent private hosting configuration reads.
- Rules: numeric range, accepted currency categories, completeness, uniqueness, publication-relative event freshness, settlement references and totals.
- At most 16 rules/policy, 8 unique selected period/batch versions, 5 samples/rule and 20,000 published rows/table/version. Version 1 only; strict types and unknown keys forbidden.
- Query timeout 10 seconds; whole experiment 20 seconds; consistent read-only snapshot. Never expose source row IDs, source business values, idempotency keys, or staged payloads in reports/errors.
- Canonical hash ignores rule/category ordering but preserves every semantic parameter and rule ID. Never eval or accept arbitrary SQL.
- Authenticated typed POST /policies/impact and local CLI policy-impact (same bearer-token requirement checked against configured token). CLI reads at most 64 KiB JSON; API policy documents also at most 64 KiB.
- No installation/activation endpoint. Suggestions, if implemented, are descriptive and never installed.
- Controlled synthetic evidence uses independent literal expected decisions; finite cases do not estimate production accuracy.

## Review Focus

- Never-published, wrong-period and unknown versions must share a generic missing result.
- Uniqueness counts every row in repeated groups, with no source-value leakage.
- Read transactions restore SQLite connection state after success and failure; PostgreSQL cannot write within evaluation.
- Unicode, booleans, nonfinite numbers, extra fields, arbitrary columns and coercion attempts must fail before database work.
- Freshness uses stable successful-attempt finish time, not wall-clock time or caller-selected now.

## Tasks

### 1. Typed policy language and report contract

Files: create dataguard/policy_models.py and tests/test_policy_models.py.
Interfaces: Policy.canonical_json()/digest(); ImpactRequest(baseline, candidate, versions, sample_limit); typed ImpactReport.

- [x] Write failing tests for canonical equivalence, semantic hash differences, all rule kinds, invalid fields/types/bounds and duplicate rule/version IDs.
- [x] Run those tests and confirm missing implementation failure.
- [x] Implement strict discriminated rule models and typed output models with validation.
- [x] Run focused tests green.

### 2. SQL experiment engine

Files: create dataguard/policy_engine.py and tests/test_policy_engine.py.
Interfaces: PolicyLab(engine).impact(ImpactRequest) -> ImpactReport; PolicyBudgetExceeded.

- [x] Write failing tests using real published fixtures for range/category/unique/completeness/freshness/totals/references, independent regression decisions, bounded opaque samples, missing-version exclusion and no mutation.
- [x] Run focused tests red.
- [x] Implement fixed SQL query compiler, capped source-size checks, read snapshot/deadline boundary, provenance and conservative recommendations.
- [x] Run focused tests green on SQLite and PostgreSQL; prove read-only and snapshot behavior with real queries.

### 3. Private API and authenticated CLI

Files: modify dataguard/api.py and dataguard/cli.py; add dataguard/policy_io.py and tests/test_policy_api.py.
Interfaces: POST /policies/impact -> ImpactReport; dataguard policy-impact file --token-env NAME.

- [x] Write failing auth/public-demo/error-redaction/OpenAPI/bounded-file/CLI tests.
- [x] Run tests red; implement handlers using the shared strict request model and engine, with sanitized policy errors.
- [x] Verify focused and full suites; preserve global request guards and existing comparison behavior.

### 4. Controlled evaluation and release evidence

Files: create dataguard/policy_evaluation.py, tests/test_policy_evaluation.py, scripts/policylab-smoke.py, docs/policylab-method.md; update README.
Interfaces: controlled_evaluation() returns actual independently checked valid, invalid and overstrict scenario evidence using disposable SQLite only.

- [x] Write failing tests for actual evaluation evidence and its finite-sample scope.
- [x] Implement bounded controlled synthetic evaluation and private CLI policy-evaluate.
- [x] Run full suite on SQLite and isolated PostgreSQL *_test database, lint/security, build dataguard:policylab native Python 3.15 image and actual HTTP smoke.
- [x] Record evidence and meaningful production/test LOC separately; review diff; commit finished changes on main.

## Execution ledger

- Initial inspection: admission already covers core quality invariants. PolicyLab instead tests business-specific thresholds/categories/freshness/uniqueness against accepted immutable evidence. No schema migration needed.
- Ruling: use native inline execution on main as requested; do not pause at skill handoff because user explicitly opted out of questions.

- TDD ledger: model/schema tests failed for missing module then 45 passed; engine tests failed for missing module then passed; API/CLI tests failed for missing boundary module then passed; controlled study failed for missing runner then passed.
- Review fixes: canonical category-order delta, purged-row eligibility, empty/changed-policy rollout recommendations and truly isolated CLI evaluation each reproduced failing behavior before the fix.
- Independent review: parent agent reviewed models/engine and requested conservative rollout handling; fixes are covered by separate regression fixtures.
- Final verification: native Python 3.15.1 PostgreSQL 151 passed; native SQLite 150 passed/1 PostgreSQL-only skip; Windows SQLite 150 passed/1 skip. Ruff clean; Bandit medium/high findings zero. Final production image rebuilt and real HTTP probe passed.
- Source growth: 841 production / 660 tests / 146 verification-script token-bearing Python lines, excluding comments, blanks and standalone docstrings; no line-count padding.
- Ruling: native test harness uses pinned pure-Python test tools only after full dev-lock installation found no PyYAML 3.15 binary wheel; production dependencies and lockfiles unchanged.
